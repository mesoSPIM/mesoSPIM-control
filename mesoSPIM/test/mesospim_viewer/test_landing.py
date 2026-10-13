"""Which files of a store have landed, and how far each stack has got.

Following a store that is being written comes down to one question asked every
second: which files are new? :class:`Landing` answers it from the folders'
modification times, and :class:`Progress` turns the files of the finest copy
into complete planes per stack -- one time point of one channel -- which is
where a live view should look. Python only.
"""

from __future__ import annotations

import os
import time


from mesoSPIM.src.mesospim_viewer import Landing, Progress, read_store
from mesoSPIM.src.mesospim_viewer.demo import write_tile
from mesoSPIM.src.mesospim_viewer.landing import COLD_EVERY, COLD_S, HOT_S
from mesoSPIM.src.mesospim_viewer.omezarr import read_levels

from .stores import Slabs, chunk_files, take_chunks, land, write_store


def progress_of(path) -> Progress:
    store = read_store(path)
    return Progress(store, read_levels(store)[0])


# -- which files are new ------------------------------------------------------------


def test_a_look_reports_each_file_once(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    landing = Landing(tile.path)
    assert landing.look() == [] and not landing.holds_data
    first = tile.write(0)
    assert sorted(landing.look()) == sorted(first)
    assert landing.look() == [] and landing.look() == []
    second = tile.write(1) + tile.write(0, c=1)
    assert sorted(landing.look()) == sorted(second)
    assert landing.look() == []
    assert landing.count == len(first + second) and landing.holds_data and landing.grew


def test_files_are_named_by_their_path_below_the_store_with_slashes(tmp_path):
    v3 = Slabs(tmp_path / "v3.ome.zarr")
    v3.write(1, c=1)
    assert sorted(Landing(v3.path).look()) == [
        "0/c/0/1/1/0/0",
        "0/c/0/1/1/0/1",
        "0/c/0/1/1/1/0",
        "0/c/0/1/1/1/1",
    ]
    v2 = Slabs(tmp_path / "v2.ome.zarr", version="0.4")
    v2.write(0)
    assert sorted(Landing(v2.path).look()) == ["0/0.0.0.0.0", "0/0.0.0.0.1", "0/0.0.0.1.0", "0/0.0.0.1.1"]


def test_metadata_and_files_still_being_written_are_not_chunk_files(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    folder = tile.path / "0" / "c" / "0" / "0" / "0" / "0"
    folder.mkdir(parents=True)
    for name in ("0.partial", "1.tmp", ".hidden", "zarr.json", ".zarray", ".zattrs", ".zgroup", ".zmetadata"):
        (folder / name).write_bytes(b"x")
    landing = Landing(tile.path)
    assert landing.look() == [], "nor the store's own zarr.json files"
    # The writer renames the finished file into place: now it has landed.
    (folder / "0.partial").rename(folder / "0")
    assert landing.look() == ["0/c/0/0/0/0/0"]


def test_a_file_that_changed_is_reported_again(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    (file,) = tile.write(0, only=1)
    landing = Landing(tile.path)
    assert landing.look() == [file]
    (tile.path / file).write_bytes(b"longer than before" * 400)
    assert landing.look() == [file]
    assert landing.look() == []


def test_a_new_folder_deep_in_the_store_is_found(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", timepoints=2)
    landing = Landing(tile.path)
    tile.write(0)
    landing.look()
    later = tile.write(0, t=1, c=1)  # a time point and a channel no file was in yet
    assert sorted(landing.look()) == sorted(later)


def test_a_file_added_without_the_folders_time_moving_is_still_found(tmp_path):
    """Some file systems count a folder's modification time in whole seconds: a file
    added within the same second as the last look leaves the time as it was."""
    tile = Slabs(tmp_path / "tile.ome.zarr", version="0.4")  # zarr v2: every chunk in one folder
    tile.write(0, only=2)
    folder = tile.path / "0"
    landing = Landing(tile.path)
    assert len(landing.look()) == 2
    before = folder.stat()
    added = tile.write(0, skip=2)
    os.utime(folder, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert folder.stat().st_mtime_ns == before.st_mtime_ns
    assert sorted(landing.look()) == sorted(added)


def test_it_knows_when_a_file_last_landed_and_whether_the_store_grew(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    tile.write(0)
    landing = Landing(tile.path)
    assert landing.changed_at == 0.0 and landing.grew is False
    landing.look(now=100.0)
    assert landing.changed_at == 100.0
    assert landing.grew is False, "what was there at the first look did not land while watched"
    landing.look(now=101.0)
    assert landing.changed_at == 100.0 and landing.grew is False
    tile.write(1)
    landing.look(now=102.0)
    assert landing.changed_at == 102.0 and landing.grew is True


def test_a_store_empty_at_first_grew_once_a_file_landed(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    landing = Landing(tile.path)
    landing.look(now=10.0)
    assert landing.changed_at == 0.0 and not landing.grew
    tile.write(0)
    landing.look(now=11.0)
    assert landing.changed_at == 11.0 and landing.grew


def test_a_quiet_part_is_looked_at_only_now_and_then(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    tile.write(0)
    landing = Landing(tile.path)
    assert len(landing.look(now=0.0)) == 4
    # Long after: the store has gone quiet, and is passed over...
    quiet = COLD_S + 100.0
    late = tile.write(1)
    for look in range(2, COLD_EVERY):
        assert landing.look(now=quiet + look) == [], look
    # ...except every so often, when all of it is looked at.
    assert sorted(landing.look(now=quiet + COLD_EVERY)) == sorted(late)


def test_a_thorough_look_reads_the_quiet_parts_too(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    tile.write(0)
    landing = Landing(tile.path)
    landing.look(now=0.0)
    late = tile.write(1)
    assert landing.look(now=COLD_S + 100.0) == []
    assert sorted(landing.look(now=COLD_S + 101.0, thorough=True)) == sorted(late)


def test_stores_looked_at_together_take_their_thorough_looks_in_turn(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    tile.write(0)
    landing = Landing(tile.path, phase=COLD_EVERY - 3)
    landing.look(now=0.0)
    late = tile.write(1)
    assert landing.look(now=COLD_S + 100.0) == []
    assert sorted(landing.look(now=COLD_S + 101.0)) == sorted(late), "its third look is the thorough one"


def test_a_thorough_look_finds_a_file_whose_folders_time_did_not_move(tmp_path):
    """Some file systems do not move a folder's modification time when a file is
    added to it. Nothing about such a file says it is new -- its folder's time
    stands still, and it is too old to be listed again for being recent -- so
    only a look that lists every folder finds it."""
    tile = Slabs(tmp_path / "tile.ome.zarr", version="0.4")  # zarr v2: every chunk in one folder
    first = tile.write(0, only=2)
    folder = tile.path / "0"
    long_ago = time.time() - 100 * HOT_S

    def age(names) -> None:
        for name in names:
            os.utime(tile.path / name, (long_ago, long_ago))

    age(first + ["0"])
    landing = Landing(tile.path)
    assert sorted(landing.look(now=0.0)) == sorted(first)
    before = folder.stat().st_mtime_ns
    added = tile.write(0, skip=2)
    age(added + ["0"])
    assert folder.stat().st_mtime_ns == before
    assert landing.look(now=1.0) == [], "nothing says that the folder has changed"
    assert landing.look(now=2.0) == []
    assert sorted(landing.look(now=3.0, thorough=True)) == sorted(added)
    assert landing.look(now=4.0, thorough=True) == [], "each file once"
    assert landing.count == 4


def test_what_is_remembered_of_a_quiet_folder_shrinks_to_a_count(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", version="0.4")  # zarr v2: every chunk in one folder
    first = tile.write(0) + tile.write(1)
    landing = Landing(tile.path)
    assert len(landing.look(now=0.0)) == 8
    assert sorted(landing._folders["0"].files) == sorted(file[2:] for file in first)
    assert landing.look(now=COLD_S - 1.0, thorough=True) == []
    assert landing._folders["0"].files is not None, "it may still gain files: they are remembered by name"
    assert landing.look(now=COLD_S + 1.0, thorough=True) == []
    assert all(folder.files is None for folder in landing._folders.values()), "the names are let go"
    assert landing._folders["0"].count == 8 and landing.count == 8, "how many there were is not"
    for look in range(2, 2 * COLD_EVERY):
        assert landing.look(now=COLD_S + look) == [], "and nothing is named a second time for it"
    assert landing.look(now=3 * COLD_S, thorough=True) == []
    assert landing.count == 8 and landing.holds_data


def test_a_file_added_to_a_folder_whose_files_were_forgotten_is_reported_once(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", version="0.4")
    tile.write(0)
    landing = Landing(tile.path)
    landing.look(now=0.0)
    quiet = COLD_S + 100.0
    assert landing.look(now=quiet, thorough=True) == [] and landing._folders["0"].files is None
    time.sleep(0.05)  # written later than what was there, as a slab after a pause is
    late = tile.write(1)
    assert sorted(landing.look(now=quiet + 1.0, thorough=True)) == sorted(late), "only what is new"
    assert landing.count == 8 and landing.changed_at == quiet + 1.0
    assert landing.look(now=quiet + 2.0, thorough=True) == [] and landing.look(now=quiet + 3.0) == []
    # Quiet once more, forgotten once more, and the next one is again named alone.
    again = 2 * quiet
    assert landing.look(now=again, thorough=True) == [] and landing._folders["0"].files is None
    time.sleep(0.05)
    (last,) = tile.write(2, only=1)
    assert landing.look(now=again + 1.0, thorough=True) == [last]
    assert landing.look(now=again + 2.0, thorough=True) == []
    assert landing.count == 9


def test_the_ordinary_look_finds_a_file_in_a_forgotten_folder_when_its_turn_comes(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", version="0.4")
    tile.write(0)
    landing = Landing(tile.path)
    landing.look(now=0.0)
    quiet = COLD_S + 100.0
    # A quiet store is passed over at its top: the names go at the next closer look.
    for look in range(COLD_EVERY):
        assert landing.look(now=quiet + look) == []
    assert landing._folders["0"].files is None and landing.count == 4
    time.sleep(0.05)
    late = tile.write(1)
    named = [file for look in range(COLD_EVERY, 4 * COLD_EVERY) for file in landing.look(now=quiet + look)]
    assert sorted(named) == sorted(late), "once each, over all the looks that follow"
    assert landing.count == 8


def test_a_file_that_came_into_a_forgotten_folder_by_another_road_is_not_missed(tmp_path):
    """A file copied in keeps the time it was written at, which may be older than
    the newest that was there: then only the count says that something came."""
    tile = Slabs(tmp_path / "tile.ome.zarr", version="0.4")
    there = tile.write(0, only=3)
    landing = Landing(tile.path)
    landing.look(now=0.0)
    quiet = COLD_S + 100.0
    assert landing.look(now=quiet, thorough=True) == []
    (copied,) = tile.write(0, skip=3)
    long_ago = time.time() - 3600.0
    os.utime(tile.path / copied, (long_ago, long_ago))
    named = landing.look(now=quiet + 1.0, thorough=True)
    assert copied in named and set(named) <= set(there + [copied])
    assert landing.count == 4
    assert landing.look(now=quiet + 2.0, thorough=True) == []


def test_a_probe_finds_a_new_channel_or_time_point_and_leaves_the_quiet_folders_alone(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", timepoints=2)  # zarr v3: 0/c/<t>/<c>/<z>/<y>/<x>
    (first,) = tile.write(0, only=1)
    landing = Landing(tile.path)
    assert landing.look(now=0.0) == [first]
    quiet = COLD_S + 100.0
    assert landing.look(now=quiet, depth=4) == []
    time.sleep(0.05)
    deep = tile.write(0, skip=1)  # more of the slab that was begun: deep in folders that are known
    channel = tile.write(0, c=1)
    time_point = tile.write(0, t=1)
    assert sorted(landing.look(now=quiet + 1.0, depth=4)) == sorted(channel + time_point), (
        "below a folder that has just appeared everything is new; the old ones are not gone down into"
    )
    assert landing.count == 1 + len(channel + time_point)
    assert landing.look(now=quiet + 2.0, depth=4) == [], "each file once"
    # What landed deep in the quiet part waits for a look at all of it.
    assert sorted(landing.look(now=quiet + 3.0, thorough=True)) == sorted(deep)
    assert landing.look(now=quiet + 4.0, thorough=True) == []
    assert landing.count == 12


def test_a_probe_looks_no_deeper_than_it_is_told(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr")
    tile.write(0)
    landing = Landing(tile.path)
    landing.look(now=0.0)
    quiet = COLD_S + 100.0
    landing.look(now=quiet, depth=1)
    time.sleep(0.05)
    channel = tile.write(0, c=1)  # the new folder is 0/c/0/1: three steps below the root
    assert landing.look(now=quiet + 1.0, depth=1) == [], "its parent lies deeper than the probe looks"
    assert sorted(landing.look(now=quiet + 2.0, depth=4)) == sorted(channel)


def test_a_store_that_is_gone_lands_nothing(tmp_path):
    landing = Landing(tmp_path / "never_there.ome.zarr")
    assert landing.look() == [] and landing.look() == []
    assert not landing.holds_data


def test_looking_at_a_big_quiet_store_costs_little(tmp_path):
    path = write_tile(tmp_path / "tile.ome.zarr", origin_um=(0, 0, 0), seed=1)
    landing = Landing(path)
    assert len(landing.look()) == len(chunk_files(path)) > 500
    started = time.perf_counter()
    for _ in range(20):
        assert landing.look() == []
    assert time.perf_counter() - started < 2.0


# -- how far a stack has got ---------------------------------------------------------------


def test_planes_count_slab_by_slab_once_every_file_across_the_sensor_is_there(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", planes=20, slab=8)  # slabs of 8, 8 and 4 planes
    progress = progress_of(tile.path)
    stack = (0, 0)
    assert progress.planes(stack) == 0 and not progress.complete(stack) and progress.newest is None
    progress.add(tile.write(0, only=3))
    assert progress.planes(stack) == 0, "three of the four files across the sensor"
    progress.add(tile.write(0, skip=3))
    assert progress.planes(stack) == 8
    progress.add(tile.write(1, only=1))
    assert progress.planes(stack) == 8, "the slab on top is half written"
    progress.add(tile.write(1, skip=1))
    assert progress.planes(stack) == 16 and not progress.complete(stack)
    progress.add(tile.write(2, only=2))
    assert progress.planes(stack) == 16 and not progress.complete(stack)
    progress.add(tile.write(2, skip=2))
    assert progress.planes(stack) == 20, "the last slab is as deep as the stack has planes left"
    assert progress.complete(stack)


def test_a_file_named_twice_counts_once(tmp_path):
    """A file that changed is reported again by the look at the disk (a stack
    acquired a second time writes over the first): it is still one file."""
    tile = Slabs(tmp_path / "tile.ome.zarr", planes=20, slab=8)
    progress = progress_of(tile.path)
    stack = (0, 0)
    three = tile.write(0, only=3)
    progress.add(three)
    progress.add(three)
    progress.add([three[0], three[0], three[1]])
    assert progress.planes(stack) == 0, "three of the four files across the sensor, however often they are named"
    assert len(progress.slabs[stack][0]) == 3
    last = tile.write(0, skip=3)
    progress.add(last + last)
    assert progress.planes(stack) == 8
    progress.add(three + last)  # a slab that is whole stays whole
    assert progress.planes(stack) == 8
    one = tile.write(1, only=1)
    progress.add(one * 4)
    assert progress.planes(stack) == 8, "one file named four times is not a slab"


def test_each_time_point_of_each_channel_is_a_stack_of_its_own(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", planes=16, slab=8, timepoints=2)
    progress = progress_of(tile.path)
    progress.add(tile.write_stack(t=0, c=0))
    progress.add(tile.write(0, t=0, c=1))
    assert progress.newest == (0, 1)
    assert progress.complete((0, 0)) and progress.planes((0, 1)) == 8
    assert progress.planes((1, 0)) == 0 and not progress.complete((1, 0))
    progress.add(tile.write(0, t=1, c=0, only=1))
    assert progress.newest == (1, 0) and progress.planes((1, 0)) == 0
    assert sorted(progress.slabs) == [(0, 0), (0, 1), (1, 0)]


def test_a_chunk_file_of_any_copy_names_its_stack(tmp_path):
    tile = Slabs(tmp_path / "tile.ome.zarr", timepoints=3)
    progress = progress_of(tile.path)
    assert progress.stack_of("0/c/2/1/0/1/1") == (2, 1)
    assert progress.stack_of("3/c/1/0/0/0/0") == (1, 0), "a coarser copy of the same stack"
    assert progress.stack_of("0/zarr.json") is None and progress.stack_of("zarr.json") is None
    assert progress.stack_of("0/c/2/1/0") is None
    v2 = progress_of(write_tile(tmp_path / "v2.ome.zarr", origin_um=(0, 0, 0), seed=1))
    assert v2.stack_of("0/0.1.5.2.2") == (0, 1) and v2.stack_of("2/0.0.5.0.0") == (0, 0)
    assert v2.stack_of("0/.zarray") is None


def test_only_the_finest_copy_counts_towards_the_planes(tmp_path):
    path = write_tile(tmp_path / "tile.ome.zarr", origin_um=(0, 0, 0), seed=1)
    progress = progress_of(path)
    files = Landing(path).look()
    progress.add([file for file in files if not file.startswith("0/")])
    assert progress.slabs == {} and progress.planes((0, 0)) == 0
    progress.add(files)
    assert progress.complete((0, 0)) and progress.complete((0, 1))
    assert progress.planes((0, 0)) == 24  # one plane to a file, nine files across


def test_a_store_without_time_or_channel_axis_holds_one_stack(tmp_path):
    path = write_store(tmp_path / "zyx.ome.zarr", axes="zyx", version="0.5")
    taken = take_chunks(path, lambda chunk: "/0/c/" in chunk.as_posix() and int(chunk.parts[-3]) >= 10)
    progress = progress_of(path)
    progress.add(Landing(path).look())
    assert list(progress.slabs) == [(0, 0)]
    assert progress.planes((0, 0)) == 10 and not progress.complete((0, 0))
    assert progress.stack_of("0/c/7/1/2") == (0, 0)
    progress.add(land(taken, path))
    assert progress.complete((0, 0))
