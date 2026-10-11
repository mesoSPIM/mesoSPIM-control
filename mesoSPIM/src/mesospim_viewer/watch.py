"""What the Data viewer window shows, without the window.

A mesoSPIM run is one folder holding one ``<Sample>.ome.zarr`` group per
acquisition, and inside it one ``(t, c, z, y, x)`` store per tile (see the
``MP_OME_Zarr_TCZYX_Writer``). Tiles appear as they are acquired, and a time
lapse appends time points to the tiles already there.

:class:`Library` is the one model behind the window. It holds a list of
acquisitions -- those of the folder the microscope writes into, and any the
operator opened from disk -- and for each whether it is shown. It keeps a
:class:`~.viewer.Viewer` in line with that list and with the disk:

- the folder the microscope writes into is *watched*: a new acquisition
  appearing in it is shown at once, in place of the one shown before;
- every acquisition that is shown is looked at once a second. A new tile
  becomes a new source; files that landed in a tile already shown are named to
  the page, which reads exactly those (``landing.py``); a tile whose shape
  changed -- a time point appended -- is read again on its own;
- the stack being acquired right now is shown from memory, plane by plane, when
  the microscope feeds its frames in (:meth:`Library.begin_stack`,
  :meth:`Library.add_plane`; see ``live.py``), and the tile on disk takes its
  place once that stack is complete.

Everything works on plain paths and a viewer, so it is tested without Qt; the
window in ``window.py`` drives :meth:`Library.poll` from a timer.
"""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .landing import Landing, Progress
from .live import Held, PreviewStack, Stack
from .omezarr import Channel, NotAStore, NotSupported, Store, read_levels, read_store
from .viewer import Viewer

logger = logging.getLogger(__name__)

STORE_SUFFIX = ".ome.zarr"

# How closely a tile is looked at depends on how lately it changed.
# One that gained a file this recently is *awake*: looked at every second...
AWAKE_S = 120.0
# ...and all of its folders are listed this often, whatever their modification
# times say (some file systems do not keep those faithfully).
AWAKE_THOROUGH_S = 30.0
# One that may still grow -- its acquisition is the newest, or its newest file
# is not an hour old -- is *dozing*: its top folders are probed this often, and
# all of it listed now and then.
DOZING_S = 15.0
DOZING_THOROUGH_S = 120.0
RECENT_S = 3600.0
# Any other is *asleep*: probed seldom, never listed whole.
ASLEEP_S = 300.0
# A probe looks this many folders deep: far enough to see a new time point or
# channel begin in a tile's finest copy.
PROBE_DEPTH = 4
# An acquisition nobody feeds counts as being written while a file landed this recently.
LIVE_S = 20.0
# A finished stack is given to the page from disk once all of it is there and
# nothing has landed for this long...
SETTLE_S = 2.0
# ...and the page then takes its preview off once the tile's own picture is up.
# This long after, the preview's memory is let go whatever the page did.
HAND_OVER_S = 15.0
# A stack that never completes on disk (the run was stopped) is handed over anyway.
GIVE_UP_S = 90.0
# The preview takes in at most this many planes a second.
PLANES_PER_S = 4.0
# Previews of finished stacks stay in memory up to this much; the oldest go first.
PREVIEW_BYTES = 1 << 30

# The time index mesoSPIM writes into file names while running a time lapse:
# 'Sample.ome.zarr' becomes 'Sample.ome_Time003.zarr'.
_TIME_MARK = re.compile(r"(?:\.ome)?(_Time\d+)$")


def channel_of(store: Store) -> Channel | None:
    """The channel a one-channel store holds, from its own metadata, or None.

    Some writers save one store per tile *and* channel, each without a channel
    axis. Such a store says which channel it holds in its ``omero`` block, with
    exactly one entry; that label, colour and window are used, and stores with
    the same label are shown as one channel. A store with a channel axis says
    what its channels are itself and is left alone, and so is a store without
    an omero block: nothing in it says which channel it is.
    """
    if store.channel_axis is None and len(store.channels) == 1:
        return store.channels[0]
    return None


def free_name(taken, name: str) -> str:
    """``name``, or, when it is taken, a numbered one.

    Two acquisitions of the same name -- the same sample on two days, say -- are
    then two entries in the panel, never one mixing both.
    """
    free, number = name, 1
    while free in taken:
        number += 1
        free = f"{name} ({number})"
    return free


def _is_zarr_group(path: Path) -> bool:
    return path.is_dir() and ((path / "zarr.json").is_file() or (path / ".zgroup").is_file())


def plain_name(path: Path) -> str:
    """A folder's name as the panel lists it: 'Sample.ome.zarr' -> 'Sample', and a
    time point of a time lapse, 'Sample.ome_Time003.zarr' -> 'Sample_Time003'."""
    name = path.name
    if name.endswith(STORE_SUFFIX):
        return name[: -len(STORE_SUFFIX)]
    if name.endswith(".zarr"):
        return _TIME_MARK.sub(r"\1", name[: -len(".zarr")])
    return name


@dataclass(frozen=True)
class Acquisition:
    path: Path
    started: float  # when the folder appeared, as a timestamp

    @property
    def name(self) -> str:
        return plain_name(self.path)


class Acquisitions:
    """The acquisitions inside a data folder, newest first."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser()
        # What each folder turned out to be, so it is opened once and not every second.
        self._known: dict[Path, bool] = {}

    def list(self) -> list[Acquisition]:
        found = []
        try:
            entries = list(os.scandir(self.root))
        except OSError:
            return found
        for entry in entries:
            path = Path(entry.path)
            # '.ome.zarr', and a time lapse's 'Sample.ome_Time003.zarr'.
            if not entry.name.endswith(".zarr"):
                continue
            is_acquisition = self._known.get(path)
            if is_acquisition is None:
                if not _is_zarr_group(path):
                    continue  # not written yet: looked at again next time
                # A tile store has multiscales itself; an acquisition holds tile stores.
                try:
                    read_store(path)
                    is_acquisition = False
                except NotSupported:
                    is_acquisition = False  # an image, only not one this viewer reads
                except NotAStore:
                    is_acquisition = True
                self._known[path] = is_acquisition
            if is_acquisition:
                try:
                    found.append(Acquisition(path=path, started=entry.stat().st_ctime))
                except OSError:
                    continue
        return sorted(found, key=lambda a: (a.started, a.name), reverse=True)

    def newest(self) -> Acquisition | None:
        listed = self.list()
        return listed[0] if listed else None


@dataclass
class Tile:
    """One store of an acquisition that is shown, and what is known of its files."""

    path: Path
    store: Store
    landing: Landing
    progress: Progress | None
    looked_at: float = 0.0
    woken_at: float = -1e9
    listed_at: float = 0.0  # when all of its folders were last listed
    # Stacks of this store, as (time point, channel), that are shown from their
    # preview: their files are kept back from the page until the stack is whole.
    held: set[tuple[int, int]] = field(default_factory=set)

    def held_back(self, file: str) -> bool:
        held, progress = self.held, self.progress
        if not held or progress is None:
            return False
        return progress.stack_of(file) in held

    def stack_key(self, time_point: int, channel: int) -> tuple[int, int]:
        """Where a stack lands in this store: a store without a time or channel axis
        holds one stack, at (0, 0)."""
        names = [axis.name for axis in self.store.axes]
        return (time_point if "t" in names else 0, channel if "c" in names else 0)

    def describe(self, store: Store) -> None:
        """Take in the store's description as it is on disk now."""
        self.store = store
        levels = read_levels(store)
        if not levels:
            return
        if self.progress is None:
            self.progress = Progress(store, levels[0])
        else:
            self.progress.reshape(store, levels[0])

    def awake(self, now: float) -> bool:
        if self.held or now - self.woken_at < AWAKE_S:
            return True
        return self.landing.grew and now - self.landing.changed_at < AWAKE_S

    def recent(self) -> bool:
        """Whether its newest file is young enough for more to follow."""
        return not self.landing.holds_data or time.time() - self.landing.newest_s < RECENT_S


@dataclass
class Dataset:
    """One entry of the panel's list: an acquisition, or a single tile opened on its own."""

    name: str
    path: Path | None  # None for a run that is not saved in a form the viewer reads
    opened: bool = False  # opened from disk by the operator, rather than found in the watched folder
    single: bool = False  # ``path`` is one tile store, not a folder of them
    shown: bool = False
    by_hand: bool = False  # shown because the operator asked, not because it is the newest
    hidden: bool = False  # the operator ticked it off: it is not shown again unasked
    started: float = 0.0
    tiles: dict[Path, Tile] = field(default_factory=dict)
    previews: list[Held] = field(default_factory=list)
    running: Stack | None = None  # the stack the microscope is acquiring into it now
    in_run: bool = False  # the microscope is running it: between its stacks too
    over: bool = False  # the microscope said its run is finished
    _resolved: dict[str, Path] = field(default_factory=dict)

    def tile_paths(self) -> list[Path]:
        if self.path is None:
            return []
        if self.single:
            return [self.path]
        try:
            entries = sorted(os.scandir(self.path), key=lambda e: e.name)
        except OSError:
            return []
        found = []
        for entry in entries:
            if not entry.name.endswith(STORE_SUFFIX):
                continue
            path = self._resolved.get(entry.name)
            if path is None:
                if not entry.is_dir():
                    continue
                path = self._resolved[entry.name] = Path(entry.path).resolve()
            found.append(path)
        return found


class Library:
    """The acquisitions on offer, which of them are shown, and keeping them up to date."""

    def __init__(self, viewer: Viewer, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.viewer = viewer
        self.clock = clock
        self.datasets: list[Dataset] = []
        self.watched: Acquisitions | None = None
        self._top: Path | None = None  # the newest acquisition of the watched folder
        self._retiring: list[tuple[float, Held]] = []
        self._plane_at = -1e9
        self._offered: list[dict] | None = None
        self._closed = False
        self._resolved: dict[Path, Path] = {}
        # poll() runs on a timer, the rest on the page's or the microscope's request.
        self._lock = threading.RLock()
        viewer.on_show(self.show)
        viewer.on_remove(self.remove)

    def close(self) -> None:
        """The window is going: nothing is looked at or shown any more."""
        with self._lock:
            self._closed = True

    # -- what is on offer ----------------------------------------------------------

    @property
    def names(self) -> list[str]:
        with self._lock:
            return [dataset.name for dataset in self.datasets]

    @property
    def shown(self) -> list[str]:
        with self._lock:
            return [dataset.name for dataset in self.datasets if dataset.shown]

    def dataset(self, name: str) -> Dataset | None:
        with self._lock:
            return next((d for d in self.datasets if d.name == name), None)

    def _at(self, path: Path) -> Dataset | None:
        return next((d for d in self.datasets if d.path is not None and d.path == path), None)

    def _new(self, name: str, path: Path | None, **about) -> Dataset:
        dataset = Dataset(name=free_name(self.names, name), path=path, **about)
        self.datasets.append(dataset)
        return dataset

    def _start_time(self) -> float:
        """Now, for a run the microscope begins: after every acquisition listed. On Windows the
        system clock moves in steps of 15.6 ms, and a run begun within one step of another
        would have had the same start time and been taken for the older."""
        now = time.time()
        latest = max((dataset.started for dataset in self.datasets if not dataset.opened), default=now - 1.0)
        return now if now > latest else latest + 1e-3

    def _sort(self) -> None:
        self.datasets.sort(key=lambda d: (d.opened, -d.started))

    # -- the folder the microscope writes into --------------------------------------

    def watch(self, folder: str | Path | None) -> None:
        """Follow a data folder: its acquisitions are listed, the newest is shown, and
        one that starts later is shown in its place. None stops following."""
        with self._lock:
            root = Path(folder).expanduser() if folder is not None else None
            if root is not None and self.watched is not None and self.watched.root == root:
                return
            self.watched = Acquisitions(root) if root is not None else None
            self._top = None
            self.poll()

    @property
    def root(self) -> Path | None:
        return self.watched.root if self.watched is not None else None

    def _list_watched(self) -> None:
        if self.watched is None:
            return
        listed = self.watched.list()
        here = set()
        for found in reversed(listed):  # oldest first, so the newest ends up on top
            path = self._resolved.get(found.path)
            if path is None:
                path = self._resolved[found.path] = found.path.resolve()
            here.add(path)
            if self._at(path) is None:
                self._new(found.name, path, started=found.started)
        for dataset in list(self.datasets):
            # One whose folder was deleted goes from the list.
            gone = dataset.path is not None and not dataset.opened and dataset.path not in here
            if gone and not dataset.in_run and not dataset.previews and not dataset.path.exists():
                self._take_off(dataset)
                self.datasets.remove(dataset)
        top = self._resolved[listed[0].path] if listed else None
        if top is not None and top != self._top:
            # A new acquisition has appeared (or this is the first look): it is what
            # a live view shows, in place of whichever one was shown for being
            # newest -- unless the microscope is running another one right now,
            # which is then the one to watch.
            self._top = top
            if not any(dataset.in_run for dataset in self.datasets):
                self._show_newest(self._at(top))
        self._sort()

    def _show_newest(self, dataset: Dataset | None) -> None:
        if dataset is None or dataset.hidden:
            return
        for other in self.datasets:
            if other is not dataset and other.shown and not other.by_hand:
                self._take_off(other)
        if not dataset.shown:
            dataset.shown = True
            self._put_previews_on(dataset)
            self.viewer.fit()

    # -- opening from disk -----------------------------------------------------------

    def open(self, path: str | Path) -> list[str]:
        """Show a dataset from disk beside what is shown, and return the names it is listed under.

        Three kinds of folder can be opened: one tile store (a ``.ome.zarr`` with
        its own image data), one acquisition (a ``.ome.zarr`` holding tile stores,
        or any folder that holds tile stores directly), or a data folder holding
        acquisitions, of which every one is listed and the newest is shown.
        Anything else raises :class:`NotAStore`, with a sentence saying what was
        expected. A folder that is already listed is simply shown.
        """
        path = Path(path).expanduser().resolve()
        with self._lock:
            held = self._at(path)
            if held is not None:
                self.show(held.name, True)
                return [held.name]
            try:
                read_store(path)
                single, why = True, None
            except NotSupported:
                raise  # an image in a form this viewer does not read: the error says which
            except NotAStore as error:
                single, why = False, error  # not one image: a folder of them, looked at below
            if single:
                dataset = self._new(plain_name(path), path, opened=True, single=True)
            else:
                acquisitions = Acquisitions(path).list()
                if acquisitions:
                    names = []
                    for found in reversed(acquisitions):
                        inside = found.path.resolve()
                        listed = self._at(inside) or self._new(
                            found.name, inside, opened=True, started=found.started
                        )
                        names.append(listed.name)
                    self.show(names[-1], True)
                    return names
                readable = 0
                for tile in Dataset(name="", path=path).tile_paths():
                    try:
                        read_store(tile)
                        readable += 1
                    except NotSupported:
                        raise
                    except NotAStore:
                        continue
                if not readable:
                    if why is not None and why.reason:
                        raise why  # a store, but a broken one
                    raise NotAStore(
                        f"{path} is not a dataset the viewer can open. Pick a .ome.zarr folder "
                        "(one tile, or one acquisition holding tiles), or a folder holding acquisitions."
                    )
                dataset = self._new(plain_name(path), path, opened=True)
            self.show(dataset.name, True)
            return [dataset.name]

    def remove(self, name: str) -> bool:
        """Take an acquisition the operator opened off the list; one of the watched
        folder is only hidden, since it would be listed again at the next look."""
        with self._lock:
            dataset = self.dataset(name)
            if dataset is None:
                return False
            self._take_off(dataset)
            dataset.hidden = True
            if dataset.opened and not dataset.in_run:
                for held in list(dataset.previews):
                    self._drop(held)
                self.datasets.remove(dataset)
            self._offer()
            return True

    # -- shown or not ----------------------------------------------------------------

    def show(self, name: str, visible: bool = True, only: bool = False) -> None:
        """Tick an acquisition on or off; ``only`` shows it alone."""
        with self._lock:
            dataset = self.dataset(name)
            if dataset is None:
                return
            if only:
                for other in self.datasets:
                    if other is not dataset and other.shown:
                        self._take_off(other)
                        other.hidden = True
                visible = True
            if visible:
                dataset.hidden = False
                dataset.by_hand = True
                if not dataset.shown:
                    dataset.shown = True
                    self._look(dataset, self.clock())
                    self._put_previews_on(dataset)
                    if only or len(self.shown) == 1:
                        self.viewer.fit()
            elif dataset.shown:
                self._take_off(dataset)
                dataset.hidden = True
            self._offer()

    def _take_off(self, dataset: Dataset) -> None:
        dataset.shown = False
        dataset.by_hand = False
        for held in dataset.previews:
            if held.name:
                self.viewer.remove_preview(held.name)
                held.name = ""
        for tile in dataset.tiles.values():
            self.viewer.guard(tile.path, None)
        dataset.tiles.clear()
        self.viewer.remove(dataset.name)

    def _put_previews_on(self, dataset: Dataset) -> None:
        for held in dataset.previews:
            # One that the tile on disk has taken over from stays off.
            if not held.name and not held.released:
                held.name = self.viewer.add_preview(dataset.name, held.preview, held.preview.channel())

    # -- one look at the disk ----------------------------------------------------------

    def poll(self) -> None:
        """Bring the list and the viewer up to date with the disk."""
        with self._lock:
            if self._closed:
                return
            now = self.clock()
            self._list_watched()
            for dataset in list(self.datasets):
                if dataset.shown:
                    self._look(dataset, now)
            self._hand_over(now)
            self._offer()
            self._point(now)

    def _look(self, dataset: Dataset, now: float) -> None:
        for path in dataset.tile_paths():
            tile = dataset.tiles.get(path)
            if tile is None:
                self._add_tile(dataset, path, now)
                continue
            if tile.awake(now):
                thorough = now - tile.listed_at >= AWAKE_THOROUGH_S
                depth = None
            else:
                # May it still be growing? The newest acquisition of the watched
                # folder may, and so may one the microscope is running, or one
                # whose files are young; one opened from last year hardly.
                growing = dataset.path == self._top or dataset.in_run or tile.recent()
                if now - tile.looked_at < (DOZING_S if growing else ASLEEP_S):
                    continue
                thorough = growing and now - tile.listed_at >= DOZING_THOROUGH_S
                depth = None if thorough else PROBE_DEPTH
            tile.looked_at = now
            if thorough:
                tile.listed_at = now
            try:
                store = read_store(path)
            except NotAStore:
                continue
            if store.shape != tile.store.shape:
                tile.describe(store)
                tile.woken_at = now
                self.viewer.add(path, layer=dataset.name, channel=channel_of(store), measure=False)
            files = tile.landing.look(now, thorough=thorough, depth=depth)
            if not files:
                continue
            tile.woken_at = now
            if tile.progress is None:
                tile.describe(store)
            if tile.progress is not None:
                tile.progress.add(files)
            kept = [file for file in files if tile.held_back(file)] if tile.held else []
            if kept:
                for held in dataset.previews:
                    if held.store == path and not held.released and held.stack in tile.held:
                        held.files.extend(f for f in kept if tile.progress.stack_of(f) == held.stack)
                kept_back = set(kept)
                files = [file for file in files if file not in kept_back]
            self.viewer.landed(path, files)

    def _add_tile(self, dataset: Dataset, path: Path, now: float) -> None:
        try:
            store = read_store(path)
        except NotAStore:
            return  # being created at this very moment: looked at again next time
        landing = Landing(path, phase=random.randrange(1000))
        files = landing.look(now, thorough=True)  # what is there already: nothing has read it yet
        tile = Tile(path=path, store=store, landing=landing, progress=None, looked_at=now, listed_at=now)
        tile.describe(store)
        if tile.progress is not None:
            tile.progress.add(files)
        if not files or time.time() - landing.newest_s < AWAKE_S:
            # A tile that has just appeared, or was written moments ago, is one to
            # keep an eye on: its next files land any second.
            tile.woken_at = now
        dataset.tiles[path] = tile
        for held in dataset.previews:
            if held.store == path and not held.released:
                held.stack = tile.stack_key(held.preview.stack.time_point, held.preview.stack.channel_index)
                if tile.progress is not None:
                    held.files.extend(f for f in files if tile.progress.stack_of(f) == held.stack)
        self._hold(dataset, tile)
        self.viewer.guard(path, tile.held_back)
        # Its contrast is measured from its data only when nobody is writing it:
        # for one that is being written the page sets it from what is on screen.
        self.viewer.add(
            path, layer=dataset.name, channel=channel_of(store), measure=not self._is_live(dataset, now)
        )

    @staticmethod
    def _hold(dataset: Dataset, tile: Tile) -> None:
        """Work out which stacks of a tile are shown from a preview and so kept back."""
        tile.held = {
            held.stack
            for held in dataset.previews
            if held.store == tile.path and held.stack is not None and not held.released
        }

    # -- the stack being acquired, fed in by the microscope ------------------------------

    def begin_stack(self, stack: Stack) -> None:
        """The microscope is about to acquire a stack: show it from memory as it comes."""
        with self._lock:
            if self._closed:
                return
            now = self.clock()
            folder = stack.folder.expanduser().resolve() if stack.folder is not None else None
            dataset = self._at(folder) if folder is not None else None
            if dataset is None and folder is None:
                dataset = next(
                    (d for d in self.datasets if d.path is None and d.name == stack.acquisition), None
                )
            if dataset is None:
                name = plain_name(folder) if folder is not None else stack.acquisition
                dataset = self._new(name, folder, started=self._start_time())
            self.end_stack()
            if not dataset.in_run:
                # A run begins: it is what a live view shows, even one the operator
                # had ticked off after an earlier run. (Ticked off during a run, it
                # stays off for the rest of it, through every stack and time point.)
                # A time lapse saved as a folder per time point moves on to the next
                # folder without the run having ended: the one before is done, and
                # what the operator ticked off stays off.
                before = [other for other in self.datasets if other.in_run]
                for other in before:
                    other.in_run = False
                    other.over = True
                dataset.in_run = True
                dataset.hidden = any(other.hidden for other in before)
                self._show_newest(dataset)
                self._sort()
            dataset.over = False
            dataset.running = stack
            store = stack.store.expanduser().resolve() if stack.store is not None else None
            earlier = list(dataset.previews)
            preview = PreviewStack(stack)
            held = Held(preview=preview, name="", layer=dataset.name, began=now, store=store)
            dataset.previews.append(held)
            tile = dataset.tiles.get(store) if store is not None else None
            if tile is not None:
                held.stack = tile.stack_key(stack.time_point, stack.channel_index)
                tile.woken_at = now
                tile.landing.wake(now)
                if tile.progress is not None:
                    # Whatever an earlier try left of this stack is written over.
                    tile.progress.slabs.pop(held.stack, None)
                self._hold(dataset, tile)
            for old in earlier:
                # The same stack once more -- stopped and started again -- takes
                # the place of the earlier try, which lets go only now that the
                # new one holds the stack's files back.
                before = old.preview.stack
                same_place = old.store == store if store is not None else (
                    old.store is None and before.origin_um == stack.origin_um
                )
                if same_place and (before.time_point, before.channel) == (stack.time_point, stack.channel):
                    self._drop(old)
            if dataset.shown:
                held.name = self.viewer.add_preview(dataset.name, preview, preview.channel())
            self._plane_at = -1e9
            self._offer()

    def add_plane(self, index: int, frame) -> None:
        """A frame of the stack being acquired: its plane number and its pixels as written."""
        with self._lock:
            if self._closed:
                return
            now = self.clock()
            held = self._acquiring()
            # A little under the pace the window hands frames over at, so that the
            # two do not take turns in passing a frame over.
            if held is None or now - self._plane_at < 0.9 / PLANES_PER_S:
                return
            self._plane_at = now
            preview = held.preview
            unlit = preview.window is None
            first = preview.top < 0
            files = preview.add(index, frame)
            if first and files:
                self._offer()  # no longer waiting for its first planes
            if not held.name:
                return
            if unlit and preview.window is not None:
                self.viewer.set_window(held.layer, preview.stack.channel, preview.window, only_if_unset=True)
            self.viewer.preview_landed(held.name, files)
            self._point(now)

    def end_stack(self) -> None:
        """The microscope has acquired the stack; the writer may still be saving it."""
        with self._lock:
            now = self.clock()
            for dataset in self.datasets:
                if dataset.running is None:
                    continue
                dataset.running = None
                for held in dataset.previews:
                    if held.ended is None:
                        held.ended = now
                        files = held.preview.finish()
                        if held.name:
                            self.viewer.preview_landed(held.name, files)

    def end_run(self) -> None:
        """The microscope has finished the whole run: nothing more is coming."""
        with self._lock:
            self.end_stack()
            for dataset in self.datasets:
                if dataset.in_run:
                    dataset.in_run = False
                    dataset.over = True  # what still lands is the writer finishing
            if self._closed:
                return
            self._offer()
            self._point(self.clock())

    def _acquiring(self) -> Held | None:
        for dataset in self.datasets:
            if dataset.running is not None:
                for held in reversed(dataset.previews):
                    if held.ended is None:
                        return held
        return None

    def _hand_over(self, now: float) -> None:
        """Give finished stacks to the page from disk, and take their previews away after."""
        for dataset in self.datasets:
            for held in list(dataset.previews):
                if held.ended is None or held.released or held.store is None:
                    continue
                tile = dataset.tiles.get(held.store)
                if tile is None or held.stack is None or tile.progress is None:
                    # Its tile has not appeared on disk (yet), or is not shown.
                    if not dataset.shown or now - held.ended >= GIVE_UP_S:
                        self._drop(held)
                    continue
                whole = tile.progress.complete(held.stack) and now - tile.landing.changed_at >= SETTLE_S
                if whole or now - held.ended >= GIVE_UP_S:
                    self._release(dataset, tile, held, now)
        for due, held in list(self._retiring):
            if now >= due:
                self._drop(held)
        # Finished previews stay only within a budget; the oldest go first. Those
        # with nothing on disk to take their place are all there is of their
        # stacks, so the ones that have a tile go before them.
        finished = [(d, h) for d in self.datasets for h in d.previews if h.ended is not None]
        total = sum(held.preview.bytes for _, held in finished)
        for dataset, held in sorted(finished, key=lambda pair: (pair[1].store is None, pair[1].began)):
            if total <= PREVIEW_BYTES:
                break
            total -= held.preview.bytes
            tile = dataset.tiles.get(held.store) if held.store is not None else None
            if tile is not None and not held.released and held.stack is not None:
                self._release(dataset, tile, held, now)
            self._drop(held)

    def _release(self, dataset: Dataset, tile: Tile, held: Held, now: float) -> None:
        """Let the page have a stack from disk, and its preview go once that is drawn."""
        held.released = True
        self._hold(dataset, tile)
        files, held.files = held.files, []
        self._pass_on(dataset, tile, held, files)
        if held.name:
            self.viewer.retire_preview(held.name)
        self._retiring.append((now + HAND_OVER_S, held))

    def _pass_on(self, dataset: Dataset, tile: Tile, held: Held, files: list[str]) -> None:
        """What was kept back for a preview that lets go: named to the page, unless the
        same stack is being acquired once more -- then it stays kept back, for the
        preview that shows it now."""
        if held.stack in tile.held:
            for other in dataset.previews:
                if other is not held and not other.released and (other.store, other.stack) == (held.store, held.stack):
                    other.files.extend(files)
                    return
        # A file written over by a second try was kept back twice.
        self.viewer.landed(tile.path, list(dict.fromkeys(files)))

    def _drop(self, held: Held) -> None:
        """Let a preview go for good."""
        self._retiring = [(due, other) for due, other in self._retiring if other is not held]
        if held.name:
            self.viewer.remove_preview(held.name)
            held.name = ""
        for dataset in self.datasets:
            if held in dataset.previews:
                dataset.previews.remove(held)
                tile = dataset.tiles.get(held.store) if held.store is not None else None
                if tile is not None and not held.released:
                    held.released = True
                    self._hold(dataset, tile)
                    files, held.files = held.files, []
                    self._pass_on(dataset, tile, held, files)

    # -- what the panel lists, and where a live view looks --------------------------------

    def _is_live(self, dataset: Dataset, now: float) -> bool:
        if dataset.running is not None or dataset.in_run:
            return True
        if dataset.over:
            return False
        return any(
            tile.landing.grew and now - tile.landing.changed_at < LIVE_S
            for tile in dataset.tiles.values()
        )

    def _offer(self) -> None:
        now = self.clock()
        offered = []
        for dataset in self.datasets:
            live = self._is_live(dataset, now)
            entry = {
                "name": dataset.name,
                "shown": dataset.shown,
                "live": live,
                "removable": dataset.opened,
                "tiles": self._tile_count(dataset) if dataset.shown else None,
                "note": self._note(dataset),
                # Shown, but with nothing to draw yet: the page says what it waits for.
                "empty": dataset.shown and self._holds_nothing(dataset),
            }
            offered.append(entry)
            if dataset.shown:
                # While it is being written nobody knows its brightness: the page
                # sets the contrast from what is on screen.
                self.viewer.set_auto(dataset.name, live)
        if offered != self._offered:
            self._offered = offered
            self.viewer.offer(offered)

    @staticmethod
    def _tile_count(dataset: Dataset) -> int:
        """How many tiles are shown: stores at different places. A run saved as one
        store per tile and channel has several stores to a tile. A run with nothing
        on disk the viewer reads (TIFF, HDF5, raw) is shown from the camera's frames:
        its tiles are the places of its previews."""
        places = set()
        for tile in dataset.tiles.values():
            store = tile.store
            places.add(
                tuple(
                    round(store.translation[index], 3)
                    for index, axis in enumerate(store.axes)
                    if axis.name in ("z", "y", "x")
                )
            )
        if not places:
            places = {tuple(round(value, 3) for value in held.preview.stack.origin_um) for held in dataset.previews}
        return len(places)

    @staticmethod
    def _holds_nothing(dataset: Dataset) -> bool:
        if any(held.preview.top >= 0 for held in dataset.previews):
            return False
        return not any(tile.landing.holds_data for tile in dataset.tiles.values())

    @staticmethod
    def _note(dataset: Dataset) -> str:
        stack = dataset.running
        if stack is None:
            return ""
        parts = []
        if stack.tile:
            parts.append(f"{stack.tile} of {stack.tiles}" if stack.tiles else stack.tile)
        parts.append(stack.channel)
        return " · ".join(parts)

    def _point(self, now: float) -> None:
        """Say where the newest data is, for a view that follows the acquisition."""
        held = self._acquiring()
        if held is not None and held.name:
            depth = held.preview.newest_um
            if depth is not None:
                preview = held.preview
                self.viewer.look_at_newest(
                    z=depth,
                    t=float(preview.stack.time_point),
                    preview=held.name,
                    chunk=[0, 0, preview.top, preview.stack.channel_index, 0],
                )
                return
        newest: tuple[float, Tile] | None = None
        for dataset in self.datasets:
            if not dataset.shown or dataset.running is not None or dataset.over:
                continue
            for tile in dataset.tiles.values():
                at = tile.landing.changed_at
                if tile.landing.grew and now - at < LIVE_S and (newest is None or at > newest[0]):
                    newest = (at, tile)
        if newest is not None:
            where = _newest_plane(newest[1])
            if where is not None:
                self.viewer.look_at_newest(**where)
                return
        # Between two stacks of a run the view stays where it is, and a run counts
        # as going on: only when nothing is fed or written any more is it over.
        if held is None and not any(self._is_live(dataset, now) for dataset in self.datasets):
            self.viewer.look_at_newest()


def _newest_plane(tile: Tile) -> dict[str, float] | None:
    """Where the last complete plane of the stack a tile is being written into lies."""
    progress = tile.progress
    if progress is None or progress.newest is None or progress.newest in tile.held:
        return None
    planes = progress.planes(progress.newest)
    if planes <= 0:
        return None
    store = tile.store
    z = store.axis_index("z")
    _, factor = store.axes[z].si
    where = {"z": (store.translation[z] + (planes - 1) * store.scale[z]) * factor * 1e6}
    if any(axis.name == "t" for axis in store.axes):
        where["t"] = float(progress.newest[0])
    return where
