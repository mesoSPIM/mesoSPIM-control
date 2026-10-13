"""Which files of a store have landed on disk, and how far a stack has got.

The microscope's writers create a store's arrays when a stack starts and then
add chunk files over the minutes that follow, each written once and never
changed (zarr writes a file under another name and renames it; so does the
shard writer). So following a store that is being written comes down to one
question, asked every second: *which files are new?* The page is told exactly
those, and reads exactly the chunks that come from them (see
``source/src/engine/worker_landed.js``).

:class:`Landing` answers the question cheaply. It remembers each folder's
modification time and lists a folder again only when that has moved, so a
store of thousands of chunk files costs a few hundred ``stat`` calls a look;
a part of the store that has gone quiet is looked at only now and then, and
what it remembers of that part shrinks to a count. A store of a million files
is watched with the memory of the few folders that are still growing.

Three kinds of look, for three ages of a store:

- the ordinary look, every second, for a store that is being written;
- a *probe* (``depth``), for one that has gone quiet: only the folders near
  the top are looked at, which is where a new channel or time point shows;
- a *thorough* look, which lists every folder whatever its modification time
  says, for file systems whose folder times cannot be trusted.

:class:`Progress` turns the landed files of the finest copy into how many
planes of each stack are complete, which is where a live view should be looking.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .omezarr import Level, Store

# A folder changed this shortly before the newest change seen in the store is
# listed again whatever its modification time says: some file systems count
# that time in whole seconds, and a file added within the same second would
# otherwise be missed until the next one. Measured against the store's own
# newest time, not this computer's clock, which a file server need not share.
HOT_S = 3.0
# A part of the store with no new file for this long is looked at only every
# COLD_EVERY-th time, and what is remembered of its files shrinks to a count.
COLD_S = 30.0
COLD_EVERY = 10

# Not chunk files: metadata, and files still being written under another name.
_METADATA = {"zarr.json", ".zarray", ".zattrs", ".zgroup", ".zmetadata"}


def _is_chunk_file(name: str) -> bool:
    return not (name in _METADATA or name.startswith(".") or name.endswith((".partial", ".tmp")))


@dataclass
class _Folder:
    modified: int = -1  # st_mtime_ns when last listed
    changed_at: float = 0.0  # when this folder, or one below it, last gained a file
    folders: list[str] = field(default_factory=list)
    # Its files as (modified, size) by name while it may still gain some; once
    # it has gone quiet only how many there were and the newest of them.
    files: dict[str, tuple[int, int]] | None = field(default_factory=dict)
    count: int = 0
    newest: int = 0


class Landing:
    """The files that have appeared in a store's folder since the last look."""

    def __init__(self, root: str | Path, *, phase: int = 0) -> None:
        self.root = Path(root)
        self._folders: dict[str, _Folder] = {}
        # Stores looked at together take their closer looks in turn (``phase``).
        self._looks = phase
        self._first = True
        self._latest = 0  # the newest modification time seen in the store, in ns
        self.count = 0  # chunk files seen so far
        self.changed_at = 0.0  # when a file last landed, on the monotonic clock
        self.grew = False  # whether a file has landed since the first look

    @property
    def holds_data(self) -> bool:
        """Whether any chunk file has been seen."""
        return self.count > 0

    @property
    def newest_s(self) -> float:
        """When the newest file seen was written, as a timestamp (0 before any)."""
        return self._latest / 1e9

    def wake(self, now: float | None = None) -> None:
        """Files are about to land again (the microscope says so): no part of the
        store counts as quiet, and the next looks are ordinary ones all the way down."""
        now = time.monotonic() if now is None else now
        for folder in self._folders.values():
            folder.changed_at = now

    def look(
        self, now: float | None = None, *, thorough: bool = False, depth: int | None = None
    ) -> list[str]:
        """The chunk files that are new or have changed, as paths below the root with ``/``.

        ``thorough`` lists every folder again, whatever its modification time
        says. ``depth`` looks only at the folders that many steps below the
        root, and below them only at what turns out to be new: a probe for a
        store that has gone quiet. Otherwise the quiet parts are looked at every
        ``COLD_EVERY`` -th time only.
        """
        now = time.monotonic() if now is None else now
        self._looks += 1
        closer = thorough or self._first or self._looks % COLD_EVERY == 0
        landed: list[str] = []
        self._walk("", now, closer, thorough or self._first, depth, 0, landed)
        if landed:
            self.changed_at = now
            self.grew = self.grew or not self._first
        self._first = False
        return landed

    def _walk(
        self,
        relative: str,
        now: float,
        closer: bool,
        every: bool,
        depth: int | None,
        level: int,
        landed: list[str],
    ) -> float:
        """Look at one folder and those below it; return when anything in it last changed.

        ``closer`` looks at folders that have gone quiet too; ``every`` lists
        them whatever their modification time says.
        """
        folder = self._folders.get(relative)
        new = folder is None
        if new:
            folder = self._folders[relative] = _Folder(changed_at=now)
        quiet = now - folder.changed_at > COLD_S
        if quiet and folder.files is not None:
            folder.files = None  # only the count is kept of a part that has gone quiet
        if not new and depth is not None and level > depth:
            return folder.changed_at
        if quiet and not closer and depth is None:
            return folder.changed_at
        path = self.root / relative if relative else self.root
        try:
            modified = path.stat().st_mtime_ns
        except OSError:
            return folder.changed_at
        self._latest = max(self._latest, modified)
        hot = self._latest - modified < HOT_S * 1e9
        found_new = set()
        if every or new or modified != folder.modified or hot:
            folder.modified = modified
            try:
                with os.scandir(path) as entries:
                    found = list(entries)
            except OSError:
                found = []
            known = set(folder.folders)
            folders = []
            files: dict[str, tuple[int, int]] = {}
            for entry in found:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        name = f"{relative}/{entry.name}" if relative else entry.name
                        folders.append(name)
                        if name not in known:
                            found_new.add(name)
                        continue
                    if not _is_chunk_file(entry.name):
                        continue
                    about = entry.stat()
                except OSError:
                    continue
                files[entry.name] = (about.st_mtime_ns, about.st_size)
            folder.folders = folders
            fresh = self._fresh(folder, files)
            if fresh:
                prefix = f"{relative}/" if relative else ""
                landed.extend(prefix + name for name in fresh)
                folder.changed_at = now
                self.count += len(files) - folder.count
            folder.count = len(files)
            if files:
                folder.newest = max(folder.newest, max(seen[0] for seen in files.values()))
                self._latest = max(self._latest, folder.newest)
            folder.files = files if now - folder.changed_at <= COLD_S else None
        for name in folder.folders:
            # Below a folder that has just appeared everything is new.
            below = None if (depth is not None and name in found_new) else depth
            folder.changed_at = max(
                folder.changed_at,
                self._walk(name, now, closer, every, below, level + 1, landed),
            )
        return folder.changed_at

    @staticmethod
    def _fresh(folder: _Folder, files: dict[str, tuple[int, int]]) -> list[str]:
        """Which of a folder's files are new or have changed since it was last listed."""
        if folder.files is not None:
            return [name for name, seen in files.items() if folder.files.get(name) != seen]
        # Its files were forgotten when it went quiet. What was written since is
        # newer than the newest of them; failing that, a changed count says that
        # something came by another road (copied in, say), and all are named.
        newer = [name for name, seen in files.items() if seen[0] > folder.newest]
        if newer or len(files) == folder.count:
            return newer
        return list(files)


WHOLE = None  # stands for a slab of which every file has landed


@dataclass
class Progress:
    """How many planes of each stack of a store are on disk, from its landed files.

    A stack is one time point of one channel. Its planes land a slab at a time
    -- as many planes as one file of the finest copy is deep -- and a slab
    counts once every file across the sensor is there.
    """

    store: Store
    level: Level  # the finest copy
    # (time point, channel) -> slab index -> the places of its files that have
    # landed, or WHOLE once all of them have
    slabs: dict[tuple[int, int], dict[int, set | None]] = field(default_factory=dict)
    newest: tuple[int, int] | None = None  # the stack that last gained a file

    def __post_init__(self) -> None:
        self.reshape(self.store, self.level)

    def reshape(self, store: Store, level: Level) -> None:
        """Take in the store's description as it is now (a time point appended, a
        stack cut short), keeping what is known of its files."""
        self.store, self.level = store, level
        names = [axis.name for axis in store.axes]
        self._t = names.index("t") if "t" in names else None
        self._c = names.index("c") if "c" in names else None
        self._z = names.index("z")
        across = 1
        for axis, name in enumerate(names):
            if name in ("y", "x"):
                across *= level.count(axis)
        self._across = across
        self._prefix = level.path + "/"

    def stack_of(self, file: str) -> tuple[int, int] | None:
        """The (time point, channel) a chunk file of any copy belongs to."""
        index = self._index(file, any_level=True)
        return None if index is None else self._stack(index)

    def add(self, files: list[str]) -> None:
        """Take in files that have landed; one named twice counts once."""
        for file in files:
            index = self._index(file)
            if index is None:
                continue
            stack = self._stack(index)
            slabs = self.slabs.setdefault(stack, {})
            at = index[self._z]
            places = slabs.get(at, set())
            if places is not WHOLE:
                places.add(index)
                slabs[at] = WHOLE if len(places) >= self._across else places
            self.newest = stack

    def planes(self, stack: tuple[int, int]) -> int:
        """How many planes of a stack are complete, counted from its first."""
        slabs = self.slabs.get(stack)
        if not slabs:
            return 0
        top = max(slabs)
        # The slab on top counts once it is whole; the ones beneath it are, since
        # the writer finishes a slab before it starts the next.
        whole = top + 1 if slabs[top] is WHOLE else top
        return min(whole * self.level.files[self._z], self.level.shape[self._z])

    def complete(self, stack: tuple[int, int]) -> bool:
        """Whether every plane of a stack is on disk."""
        return self.planes(stack) >= self.level.shape[self._z] > 0

    def _index(self, file: str, any_level: bool = False) -> tuple[int, ...] | None:
        if any_level:
            _, _, name = file.partition("/")
        elif file.startswith(self._prefix):
            name = file[len(self._prefix) :]
        else:
            return None
        return self.level.index_of(name)

    def _stack(self, index: tuple[int, ...]) -> tuple[int, int]:
        return (
            index[self._t] if self._t is not None else 0,
            index[self._c] if self._c is not None else 0,
        )
