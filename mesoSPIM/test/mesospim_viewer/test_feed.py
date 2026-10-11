"""The stack being acquired, fed to the library by the microscope.

mesoSPIM-control says when a stack begins and ends and hands over the camera's
frames in between (:meth:`Library.begin_stack`, :meth:`Library.add_plane`,
:meth:`Library.end_stack`, :meth:`Library.end_run`). The stack is on screen
from memory plane by plane; what the writer saves of that stack meanwhile is
kept from the page -- not served, not announced -- until all of it is on disk,
and then the tile takes the preview's place. Python only, on a clock the tests
move by hand.
"""

from __future__ import annotations

import time
from dataclasses import replace

import numpy as np
import pytest

from mesoSPIM.src.mesospim_viewer import Acquisitions, Library, Stack
from mesoSPIM.src.mesospim_viewer.demo import write_tile
from mesoSPIM.src.mesospim_viewer.landing import COLD_EVERY
from mesoSPIM.src.mesospim_viewer.watch import GIVE_UP_S, HAND_OVER_S, LIVE_S, PLANES_PER_S, SETTLE_S, plain_name

from .stores import Slabs, an_acquisition
from .tools import follow, landed, offered, sources, status

TILE = "Mag1_Tile{}_Sh0_Rot0.ome.zarr"
PLANE_S = 1.0 / PLANES_PER_S


def a_frame(value: int = 700, size: int = 64) -> np.ndarray:
    frame = np.full((size, size), value, np.uint16)
    frame[:8, :8] = value + 2300
    return frame


def a_stack(root=None, *, tile: int = 0, channel: str = "488", time_point: int = 0, name: str = "run", **about) -> Stack:
    """A stack of 20 planes of 64 x 64; with ``root``, saved as a tile of ``root/<name>.ome.zarr``."""
    folder = root / f"{name}.ome.zarr" if root is not None else None
    described = dict(
        acquisition=name,
        channel=channel,
        channels=("488", "561"),
        planes=20,
        frame=(64, 64),
        voxel_um=(5.0, 1.0, 1.0),
        origin_um=(0.0, 0.0, tile * 64.0),
        time_point=time_point,
        tile=f"Tile {tile + 1}",
        tiles=2,
        folder=folder,
        store=folder / TILE.format(tile) if folder is not None else None,
    )
    return Stack(**{**described, **about})


def feed(library, planes, value: int = 700) -> None:
    """Hand over frames of the running stack, as fast as the preview takes them."""
    for plane in planes:
        library.clock.tick(PLANE_S)
        library.add_plane(plane, a_frame(value))


def look(library, seconds: float = 1.0) -> None:
    library.clock.tick(seconds)
    library.poll()


def previews(view, acquisition: str = "run") -> list[str]:
    """The names of the stacks shown from memory, over every channel of an acquisition."""
    found = []
    for layer in view.scene["layers"]:
        if layer["_acquisition"] == acquisition:
            found += [name for name in layer["_sources"] if name.startswith("live-") and name not in found]
    return found


def retiring(view) -> list[str]:
    return [name for layer in view.scene["layers"] for name in layer["_retiring"]]


# -- a stack begins ---------------------------------------------------------------------


def test_a_stack_that_begins_is_listed_shown_and_given_a_preview(library, tmp_path):
    library.watch(tmp_path)
    view = library.viewer
    assert offered(view) == {}
    library.begin_stack(a_stack(tmp_path))  # the writer has not made anything on disk yet
    assert library.names == ["run"] and library.shown == ["run"]
    assert offered(view)["run"] == {
        "name": "run", "shown": True, "live": True, "removable": False, "tiles": 1,
        "note": "Tile 1 of 2 · 488", "empty": True,
    }
    (layer,) = view.scene["layers"]
    assert layer["name"] == "run · 488" and layer["_sources"] == ["live-1"]
    assert layer["source"] == [{"url": f"{view.url}live/live-1/|zarr2:"}]
    assert layer["localPosition"] == [0] and layer["_auto"] is True
    assert view.scene["dimensions"]["z"] == [pytest.approx(5e-6), "m"]
    assert status(view.url + "live/live-1/.zattrs") == 200
    assert follow(view) == {}, "no plane yet: nowhere to look"


def test_a_run_that_begins_is_shown_in_place_of_the_newest(library, tmp_path):
    older = an_acquisition(tmp_path, "run_a")
    write_tile(older / TILE.format(0), origin_um=(0, 0, 0), seed=1)
    library.watch(tmp_path)
    assert library.shown == ["run_a"]
    library.begin_stack(a_stack(tmp_path, name="run_b"))
    assert library.names == ["run_b", "run_a"] and library.shown == ["run_b"]
    # The writer makes the acquisition's folder a moment later: the same entry, not a second one.
    an_acquisition(tmp_path, "run_b")
    look(library)
    assert library.names == ["run_b", "run_a"] and library.shown == ["run_b"]


def test_the_note_says_which_tile_and_channel_is_being_acquired(library, tmp_path):
    library.begin_stack(a_stack(tmp_path, tile=1, channel="561"))
    assert offered(library.viewer)["run"]["note"] == "Tile 2 of 2 · 561"
    library.begin_stack(a_stack(tmp_path, tile=1, channel="488", tiles=0))
    assert offered(library.viewer)["run"]["note"] == "Tile 2 · 488", "how many there are is not always known"
    library.begin_stack(replace(a_stack(tmp_path), tile="", tiles=0))
    assert offered(library.viewer)["run"]["note"] == "488"
    library.end_stack()
    library.poll()
    assert offered(library.viewer)["run"]["note"] == ""


# -- planes arrive ----------------------------------------------------------------------------


def test_each_plane_is_announced_and_the_live_view_is_pointed_at_it(library, tmp_path):
    library.begin_stack(a_stack(tmp_path, origin_um=(100.0, 0.0, 0.0)))
    view = library.viewer
    library.add_plane(0, a_frame())
    assert landed(view, "live/") == [("live/live-1", ["0/0/0/0/0/0"])]
    assert follow(view) == {"z": 100.0, "t": 0.0, "await": {"store": "live/live-1", "chunk": [0, 0, 0, 0, 0]}}
    assert status(view.url + "live/live-1/0/0/0/0/0/0") == 200
    assert status(view.url + "live/live-1/0/0/0/1/0/0") == 404
    library.clock.tick(PLANE_S)
    library.add_plane(3, a_frame())  # the microscope hands on every few frames
    assert landed(view, "live/")[1] == ("live/live-1", ["0/0/0/1/0/0", "0/0/0/2/0/0", "0/0/0/3/0/0"])
    assert follow(view) == {"z": 115.0, "t": 0.0, "await": {"store": "live/live-1", "chunk": [0, 0, 3, 0, 0]}}
    library.poll()
    assert offered(view)["run"]["empty"] is False, "the panel no longer says it is waiting for planes"


def test_the_chunk_to_wait_for_is_the_stacks_own_channel_and_plane(library, tmp_path):
    library.begin_stack(a_stack(tmp_path, channel="561", time_point=2))
    feed(library, [0, 1, 2])
    assert follow(library.viewer) == {
        "z": 10.0, "t": 2.0, "await": {"store": "live/live-1", "chunk": [0, 0, 2, 1, 0]},
    }, "the chunk as the engine counts: x, y, z, then channel and time"
    assert library.viewer.scene["layers"][0]["localPosition"] == [1]


def test_frames_coming_faster_than_the_preview_takes_them_are_passed_over(library, tmp_path):
    library.begin_stack(a_stack(tmp_path))
    view = library.viewer
    library.add_plane(0, a_frame())
    library.clock.tick(PLANE_S / 2)
    library.add_plane(1, a_frame())
    assert len(landed(view, "live/")) == 1 and follow(view)["z"] == 0.0
    library.clock.tick(PLANE_S / 2)
    library.add_plane(2, a_frame())
    assert landed(view, "live/")[1] == ("live/live-1", ["0/0/0/1/0/0", "0/0/0/2/0/0"]), "and filled in by the next"


def test_the_first_frame_sets_the_channels_contrast_once(library, tmp_path):
    library.begin_stack(a_stack(tmp_path))
    view = library.viewer
    assert "contrast" not in view.scene["layers"][0]["shaderControls"]
    feed(library, [0])
    assert view.scene["layers"][0]["shaderControls"]["contrast"]["range"] == [700.0, pytest.approx(3230.0)]
    feed(library, range(1, 20), value=5000)
    library.end_stack()
    # The same channel of the next tile is brighter: the contrast stays where it was set.
    library.begin_stack(a_stack(tmp_path, tile=1))
    feed(library, [0], value=5000)
    assert view.scene["layers"][0]["shaderControls"]["contrast"]["range"] == [700.0, pytest.approx(3230.0)]
    assert view.scene["layers"][0]["_auto"] is True, "and the page goes on setting it from what is on screen"


def test_frames_are_passed_over_when_no_stack_has_begun(library, tmp_path):
    library.add_plane(0, a_frame())
    assert library.names == [] and landed(library.viewer, "live/") == []
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(20))
    library.end_stack()
    said = len(landed(library.viewer, "live/"))
    feed(library, [5])
    assert len(landed(library.viewer, "live/")) == said, "the stack is over"


def test_the_end_of_a_stack_fills_the_planes_its_last_frames_left_out(library, tmp_path):
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(0, 18))
    library.end_stack()
    assert landed(library.viewer, "live/")[-1] == ("live/live-1", ["0/0/0/18/0/0", "0/0/0/19/0/0"])
    assert status(library.viewer.url + "live/live-1/0/0/0/19/0/0") == 200
    assert library.dataset("run").running is None


# -- the tile on disk is held back until the stack is whole -----------------------------------------


def test_the_stacks_files_on_disk_are_kept_from_the_page_until_all_of_it_has_landed(library, tmp_path):
    library.watch(tmp_path)
    view = library.viewer
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(0, 4))
    # The writer has made the tile's arrays by now, and saves the stack slab by slab.
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=20, slab=8)
    look(library)
    assert sources(view, "run") == {"store-0": "data/0/", "live-1": "live/live-1/"}, "the tile beside its preview"
    first = tile.write(0)
    look(library)
    assert landed(view) == [], "not named to the page"
    assert all(status(view.url + "data/0/" + file) == 404 for file in first), "and not served"
    assert status(view.url + "data/0/zarr.json") == 200 and status(view.url + "data/0/0/zarr.json") == 200
    feed(library, range(4, 20))
    held = first + tile.write(1) + tile.write(2, only=2)
    look(library)
    assert landed(view) == [] and status(view.url + "data/0/" + held[-1]) == 404
    library.end_stack()  # acquired; the writer is still saving the last slab
    look(library, SETTLE_S + 1)
    assert landed(view) == [] and retiring(view) == [], "a slab is still missing"
    held += tile.write(2, skip=2)
    look(library)
    assert landed(view) == [], "all there, but only just: the writer may not be done"
    assert previews(view) == ["live-1"]

    look(library, SETTLE_S)
    (said,) = landed(view)
    assert said[0] == "data/0" and sorted(said[1]) == sorted(held), "every file of the stack, named at once"
    assert all(status(view.url + "data/0/" + file) == 200 for file in held)
    assert retiring(view) == ["live-1"], "the page may let the preview go once the tile is drawn"
    assert previews(view) == ["live-1"], "which it still shows until then"

    look(library, HAND_OVER_S)
    assert previews(view) == [] and retiring(view) == []
    assert sources(view, "run") == {"store-0": "data/0/"}
    assert status(view.url + "live/live-1/.zattrs") == 404, "the preview's memory is let go"
    look(library)
    assert len(landed(view)) == 1, "nothing is named twice"


def test_files_of_other_stacks_in_the_same_tile_are_not_held_back(library, tmp_path):
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=16, slab=8)
    done = tile.write_stack(c=0)  # the first channel is on disk already
    library.watch(tmp_path)
    view = library.viewer
    library.begin_stack(a_stack(tmp_path, channel="561", planes=16))
    feed(library, range(0, 8))
    assert status(view.url + "data/0/" + done[0]) == 200
    held = tile.write(0, c=1)
    look(library)
    assert landed(view) == [] and status(view.url + "data/0/" + held[0]) == 404
    assert status(view.url + "data/0/" + done[-1]) == 200, "the channel that is whole stays readable"
    # A straggler of the first channel (a coarser copy, say) is named as it lands.
    (tile.path / done[0]).write_bytes(b"\0" * 16)
    look(library)
    assert landed(view) == [("data/0", [done[0]])]


def test_a_time_point_appended_to_a_tile_is_held_back_like_any_other_stack(library, tmp_path):
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=16, slab=8, channels=("488",))
    tile.write_stack()
    library.watch(tmp_path)
    view = library.viewer
    tile.create(timepoints=2)
    library.begin_stack(a_stack(tmp_path, channels=("488",), planes=16, time_point=1))
    feed(library, range(0, 8))
    look(library)
    assert sources(view, "run") == {"store-0": "data/0.1/", "live-1": "live/live-1/"}
    held = tile.write(0, t=1)
    look(library)
    assert landed(view) == [] and status(view.url + "data/0.1/" + held[0]) == 404
    assert status(view.url + "data/0.1/" + tile.files(0, t=0)[0]) == 200
    feed(library, range(8, 16))
    library.end_stack()
    held += tile.write(1, t=1)
    look(library)
    look(library, SETTLE_S)
    assert [sorted(files) for _, files in landed(view)] == [sorted(held)]
    assert status(view.url + "data/0.1/" + held[0]) == 200


def test_a_stack_that_never_completes_on_disk_is_handed_over_all_the_same(library, tmp_path):
    library.watch(tmp_path)
    view = library.viewer
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(0, 6))
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=20, slab=8)
    look(library)
    files = tile.write(0)
    look(library)
    library.end_stack()  # the run was stopped: the rest never comes
    look(library, GIVE_UP_S - 5)
    assert landed(view) == [] and status(view.url + "data/0/" + files[0]) == 404
    look(library, 10)
    assert landed(view) == [("data/0", files)] and status(view.url + "data/0/" + files[0]) == 200
    look(library, HAND_OVER_S)
    assert previews(view) == []


def test_a_stack_stopped_and_started_again_stays_held_back_until_the_second_try_is_whole(library, tmp_path, monkeypatch):
    library.watch(tmp_path)
    view = library.viewer
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(0, 6))
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=20, slab=8)
    look(library)
    first = tile.write(0)
    look(library)
    served = lambda files: {status(view.url + "data/0/" + file) for file in files}
    assert landed(view) == [] and served(first) == {404}
    library.end_stack()  # stopped: the rest of the stack never comes
    look(library)
    assert landed(view) == [] and served(first) == {404}

    # Started again: the same store, time point and channel. Every time the library
    # works out afresh what is kept back, the stack is still among it.
    seen = []
    work_out = Library._hold

    def watched(dataset, held_tile):
        work_out(dataset, held_tile)
        seen.append((0, 0) in held_tile.held and held_tile.held_back(first[0]))

    monkeypatch.setattr(Library, "_hold", staticmethod(watched))
    library.begin_stack(a_stack(tmp_path))
    assert seen and all(seen), "at no moment between the two tries was it let through"
    monkeypatch.undo()
    assert landed(view) == [] and served(first) == {404}, "what the first try left is not given out"
    assert previews(view) == ["live-2"], "the second try's preview in place of the first's"
    assert status(view.url + "live/live-1/.zattrs") == 404 and retiring(view) == []
    assert offered(view)["run"]["live"] is True

    feed(library, range(0, 8))
    look(library)
    assert landed(view) == [] and served(first) == {404}
    # The writer saves the stack once more, over what was there.
    again = tile.write(0)
    assert again == first
    look(library)
    assert landed(view) == [] and served(first) == {404}
    look(library, SETTLE_S + 1)
    assert landed(view) == [], "the first slab alone, though settled, is not the stack"
    feed(library, range(8, 20))
    held = again + tile.write(1) + tile.write(2, only=1)
    look(library)
    library.end_stack()
    look(library, SETTLE_S + 1)
    assert landed(view) == [] and served(held) == {404}, "a slab of the second try is still missing"
    held += tile.write(2, skip=1)
    look(library)
    assert landed(view) == [] and served(held) == {404}, "all there, but only just"

    look(library, SETTLE_S)
    (said,) = landed(view)
    assert said[0] == "data/0" and set(said[1]) == set(held), "handed over once, all of it"
    assert served(held) == {200}
    assert retiring(view) == ["live-2"]
    look(library, HAND_OVER_S)
    assert previews(view) == [] and sources(view, "run") == {"store-0": "data/0/"}
    look(library)
    assert len(landed(view)) == 1, "nothing is named twice"


def test_a_stack_started_again_after_its_run_was_ended_is_held_back_all_the_same(library, tmp_path):
    library.watch(tmp_path)
    view = library.viewer
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(0, 6))
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=20, slab=8)
    look(library)
    first = tile.write(0)
    look(library)
    library.end_run()  # the operator pressed stop: the run is over...
    look(library, GIVE_UP_S / 2)
    assert landed(view) == [] and status(view.url + "data/0/" + first[0]) == 404
    library.begin_stack(a_stack(tmp_path))  # ...and started it again
    assert landed(view) == [] and status(view.url + "data/0/" + first[0]) == 404
    assert previews(view) == ["live-2"]
    feed(library, range(0, 6))
    # Long after the first try began: it is the second try that is waited for, not the first given up on.
    look(library, GIVE_UP_S)
    assert landed(view) == [] and status(view.url + "data/0/" + first[0]) == 404
    feed(library, range(6, 20))
    held = tile.write_stack()
    library.end_run()
    look(library)
    assert landed(view) == [] and status(view.url + "data/0/" + first[0]) == 404
    # The tile had gone quiet in between, and a quiet part of a store is looked at
    # only every few looks: the second try is seen to be whole a little later.
    for _ in range(COLD_EVERY):
        look(library)
    look(library, SETTLE_S)
    (said,) = landed(view)
    assert set(said[1]) == set(held) and status(view.url + "data/0/" + first[0]) == 200


def test_the_other_channel_of_a_stack_started_again_is_not_held_back_with_it(library, tmp_path):
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=16, slab=8)
    done = tile.write_stack(c=0)
    library.watch(tmp_path)
    view = library.viewer
    for _ in range(2):  # the second channel, twice
        library.begin_stack(a_stack(tmp_path, channel="561", planes=16))
        feed(library, range(0, 8))
        held = tile.write(0, c=1)
        look(library)
        assert landed(view) == [] and status(view.url + "data/0/" + held[0]) == 404
        assert status(view.url + "data/0/" + done[0]) == 200, "the channel that is whole stays readable"
        library.end_stack()


def test_a_preview_whose_tile_never_appears_is_let_go_in_the_end(library, tmp_path):
    library.watch(tmp_path)
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(20))
    library.end_stack()
    look(library, GIVE_UP_S / 2)
    assert previews(library.viewer) == ["live-1"], "its tile may still appear"
    look(library, GIVE_UP_S)
    look(library)
    assert previews(library.viewer) == [] and library.viewer.layers == []


# -- stacks that are not saved in a form the viewer reads ------------------------------------------------


def test_a_stack_with_no_store_on_disk_keeps_its_preview(library):
    view = library.viewer
    library.begin_stack(a_stack(name="tiffs"))
    assert library.dataset("tiffs").path is None and library.shown == ["tiffs"]
    feed(library, range(20))
    library.end_stack()
    for _ in range(4):
        look(library, GIVE_UP_S)
    assert previews(view, "tiffs") == ["live-1"], "nothing on disk can take its place"
    assert status(view.url + "live/live-1/0/0/0/19/0/0") == 200
    assert offered(view)["tiffs"]["tiles"] == 1 and offered(view)["tiffs"]["empty"] is False
    # The next stack of the run joins the same entry, each channel in its own layer.
    library.begin_stack(a_stack(name="tiffs", channel="561"))
    feed(library, range(20))
    library.end_stack()
    assert library.names == ["tiffs"]
    assert [(layer["name"], layer["_sources"], layer["localPosition"]) for layer in view.scene["layers"]] == [
        ("tiffs · 488", ["live-1"], [0]),
        ("tiffs · 561", ["live-2"], [1]),
    ]


def test_hiding_a_run_takes_its_previews_off_and_showing_it_puts_them_back(library):
    view = library.viewer
    library.begin_stack(a_stack(name="tiffs"))
    feed(library, range(20))
    library.end_stack()
    library.show("tiffs", False)
    assert view.layers == [] and status(view.url + "live/live-1/.zattrs") == 404
    # The run goes on while hidden: its planes are kept, and nothing is announced.
    library.begin_stack(a_stack(name="tiffs", channel="561"))
    feed(library, range(10))
    assert library.shown == [] and view.layers == [], "hidden by the operator, it stays hidden"
    assert landed(view, "live/")[-1][0] == "live/live-1"
    library.show("tiffs")
    assert [layer["name"] for layer in view.scene["layers"]] == ["tiffs · 488", "tiffs · 561"]
    names = previews(view, "tiffs")
    assert len(names) == 2 and all(status(view.url + f"live/{name}/.zattrs") == 200 for name in names)
    feed(library, [10])
    assert landed(view, "live/")[-1][0] == f"live/{names[1]}"


# -- between stacks, and at the end -----------------------------------------------------------------------


def test_a_stack_beginning_ends_the_one_before(library, tmp_path):
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(0, 19))
    library.begin_stack(a_stack(tmp_path, channel="561"))  # no end was said
    view = library.viewer
    assert ("live/live-1", ["0/0/0/19/0/0"]) in landed(view, "live/"), "the first was finished off"
    feed(library, [0])
    assert landed(view, "live/")[-1] == ("live/live-2", ["0/0/1/0/0/0"])
    assert [layer["_sources"] for layer in view.scene["layers"]] == [["live-1"], ["live-2"]]
    assert offered(view)["run"]["note"] == "Tile 1 of 2 · 561"


def test_between_two_stacks_the_run_stays_live_and_the_view_where_it_is(library, tmp_path):
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(20))
    library.end_stack()
    view = library.viewer
    look(library)
    assert offered(view)["run"]["live"] is True and offered(view)["run"]["note"] == ""
    assert follow(view)["z"] == 95.0, "still on the last plane"
    look(library, LIVE_S / 2)
    assert offered(view)["run"]["live"] is True and follow(view) != {}
    # The stage has moved: the next stack of the run.
    library.begin_stack(a_stack(tmp_path, tile=1))
    feed(library, [0])
    assert follow(view)["z"] == 0.0 and follow(view)["await"]["store"] == "live/live-2"
    assert library.shown == ["run"]


def test_the_end_of_the_run_ends_live(library):
    library.begin_stack(a_stack(name="tiffs"))
    feed(library, range(20))
    view = library.viewer
    assert offered(view)["tiffs"]["live"] is True
    library.end_run()
    assert library.dataset("tiffs").running is None
    assert offered(view)["tiffs"] == {
        "name": "tiffs", "shown": True, "live": False, "removable": False, "tiles": 1, "note": "", "empty": False,
    }
    assert follow(view) == {}, "nothing more is coming: nothing to follow"
    assert previews(view, "tiffs") == ["live-1"]


def test_a_run_stays_live_between_its_stacks_until_the_microscope_says_it_is_over(library):
    # A time lapse waits for minutes between two time points: the run is still on.
    library.begin_stack(a_stack(name="tiffs"))
    feed(library, range(20))
    library.end_stack()
    look(library, LIVE_S + 1)
    assert offered(library.viewer)["tiffs"]["live"] is True
    library.end_run()
    look(library, LIVE_S + 1)
    assert offered(library.viewer)["tiffs"]["live"] is False and follow(library.viewer) == {}


def test_the_next_run_is_shown_in_place_of_the_one_before(library):
    library.begin_stack(a_stack(name="first"))
    feed(library, range(20))
    library.end_run()
    look(library, LIVE_S + 1)
    library.begin_stack(a_stack(name="second"))
    assert library.names == ["second", "first"] and library.shown == ["second"]
    assert library.viewer.layers == ["second"]
    library.show("first")
    assert sorted(library.viewer.layers) == ["first", "second"], "its planes were kept"



# -- what else appears in the watched folder while a run is going on -----------------------------------


def test_another_acquisition_appearing_during_a_run_does_not_take_its_place(library, tmp_path):
    library.watch(tmp_path)
    view = library.viewer
    library.begin_stack(a_stack(tmp_path))
    feed(library, range(0, 6))
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=20, slab=8)
    look(library)
    assert library.shown == ["run"]
    # Something else lands in the folder -- copied in, or written by another program.
    time.sleep(0.05)
    write_tile(an_acquisition(tmp_path, "other") / TILE.format(0), origin_um=(0, 0, 0), seed=1)
    look(library)
    assert library.names == ["other", "run"], "it is listed, as the newest"
    assert library.shown == ["run"] and view.layers == ["run"], "but the microscope is running another: that one is watched"
    assert offered(view)["other"]["shown"] is False and offered(view)["run"]["live"] is True
    assert previews(view) == ["live-1"] and sources(view, "run") == {"store-0": "data/0/", "live-1": "live/live-1/"}
    feed(library, range(6, 20))
    tile.write_stack()
    library.end_stack()
    for _ in range(3):  # between two stacks of the run
        look(library)
        assert library.shown == ["run"]
    library.begin_stack(a_stack(tmp_path, tile=1))
    feed(library, range(0, 4))
    look(library, LIVE_S + 1)
    assert library.shown == ["run"] and view.layers == ["run"]
    # The operator may still tick it on beside the run, and off again.
    library.show("other")
    assert library.shown == ["other", "run"]
    library.show("other", False)
    library.end_run()
    look(library)
    assert library.shown == ["run"], "what was just acquired stays on screen when the run is over"
    # With no run going on, an acquisition that appears is shown in its place, as ever.
    time.sleep(0.05)
    write_tile(an_acquisition(tmp_path, "later") / TILE.format(0), origin_um=(0, 0, 0), seed=2)
    look(library)
    assert library.names == ["later", "other", "run"] and library.shown == ["later"]


def test_an_acquisition_appearing_while_a_run_that_is_not_on_disk_goes_on_waits_too(library, tmp_path):
    library.watch(tmp_path)
    library.begin_stack(a_stack(name="tiffs"))  # saved in a form the viewer does not read
    feed(library, range(0, 6))
    write_tile(an_acquisition(tmp_path, "other") / TILE.format(0), origin_um=(0, 0, 0), seed=1)
    look(library)
    assert sorted(library.names) == ["other", "tiffs"] and library.shown == ["tiffs"]
    library.end_stack()
    look(library)
    assert library.shown == ["tiffs"], "between its stacks the run is still going on"


def a_time_point(root, number: int, **about) -> Stack:
    """A stack of a time lapse whose writer saves every time point as a folder of its own."""
    folder = root / f"Sample.ome_Time{number:03d}.zarr"
    return a_stack(folder=folder, store=folder / TILE.format(0), name="Sample", channels=("488",), planes=16, **about)


def test_a_time_lapse_saved_as_a_folder_per_time_point_lists_each_under_its_own_name(tmp_path):
    for name in ("Sample.ome.zarr", "Sample.ome_Time001.zarr", "Sample.ome_Time002.zarr"):
        (tmp_path / name).mkdir()
        (tmp_path / name / ".zgroup").write_text('{"zarr_format": 2}')
        time.sleep(0.05)
    (tmp_path / "Sample.ome_Time003.zarr").mkdir()  # being made: not a zarr group yet
    (tmp_path / "Sample_Time001.tiff").write_text("x")
    listed = Acquisitions(tmp_path).list()
    assert [found.name for found in listed] == ["Sample_Time002", "Sample_Time001", "Sample"], "newest first"
    assert plain_name(tmp_path / "Sample.ome_Time012.zarr") == "Sample_Time012"
    assert plain_name(tmp_path / "Sample_Time012.zarr") == "Sample_Time012"
    assert plain_name(tmp_path / "Sample_Time012.ome.zarr") == "Sample_Time012"


def test_each_time_point_of_such_a_time_lapse_is_shown_when_the_microscope_begins_it(library, tmp_path):
    library.watch(tmp_path)
    view = library.viewer
    tiles = []

    def the_writer_makes(number: int) -> Slabs:
        time.sleep(0.05)
        stack = a_time_point(tmp_path, number)
        stack.folder.mkdir()
        (stack.folder / ".zgroup").write_text('{"zarr_format": 2}')
        tiles.append(Slabs(stack.store, planes=16, slab=8, channels=("488",)))
        return tiles[-1]

    # The first time point: listed under the name its folder will be listed under.
    library.begin_stack(a_time_point(tmp_path, 0))
    feed(library, range(0, 8))
    assert library.names == ["Sample_Time000"] and library.shown == ["Sample_Time000"]
    the_writer_makes(0)
    look(library)
    assert library.names == ["Sample_Time000"], "the folder is the same entry, not a second one"
    assert sources(view, "Sample_Time000") == {"store-0": "data/0/", "live-1": "live/live-1/"}
    feed(library, range(8, 16))
    first = tiles[0].write_stack()
    library.end_stack()  # the time point is over, the time lapse is not
    look(library)
    look(library, SETTLE_S)
    assert [sorted(files) for _, files in landed(view)] == [sorted(first)]
    assert offered(view)["Sample_Time000"]["live"] is True, "the run goes on while the next time point is waited for"

    # The writer makes the next time point's folder before the camera's first frame:
    # it is listed, and the time point on screen stays until the microscope begins the new one.
    the_writer_makes(1)
    look(library)
    assert library.names == ["Sample_Time001", "Sample_Time000"]
    assert library.shown == ["Sample_Time000"] and view.layers == ["Sample_Time000"]
    library.begin_stack(a_time_point(tmp_path, 1))
    assert library.names == ["Sample_Time001", "Sample_Time000"], "it joins the entry its folder was listed under"
    assert library.shown == ["Sample_Time001"], "in place of the time point before"
    feed(library, range(0, 8))
    look(library)
    assert view.layers == ["Sample_Time001"]
    assert list(sources(view, "Sample_Time001")) == ["store-1", "live-2"]
    assert offered(view)["Sample_Time001"] == {
        "name": "Sample_Time001", "shown": True, "live": True, "removable": False, "tiles": 1,
        "note": "Tile 1 of 2 · 488", "empty": False,
    }
    held = tiles[1].write(0)
    look(library)
    assert status(view.url + "data/1/" + held[0]) == 404, "held back like any stack being acquired"
    assert follow(view)["await"]["store"] == "live/live-2"

    # An earlier time point the operator ticked on stays beside the ones that follow.
    library.show("Sample_Time000")
    assert library.shown == ["Sample_Time001", "Sample_Time000"]
    library.end_stack()
    library.begin_stack(a_time_point(tmp_path, 2))  # this time before its folder is on disk
    assert library.names == ["Sample_Time002", "Sample_Time001", "Sample_Time000"]
    assert library.shown == ["Sample_Time002", "Sample_Time000"]
    the_writer_makes(2)
    look(library)
    assert library.names == ["Sample_Time002", "Sample_Time001", "Sample_Time000"]
    assert library.shown == ["Sample_Time002", "Sample_Time000"]

    library.end_run()
    look(library, LIVE_S + 1)
    assert [entry["live"] for entry in offered(view).values()] == [False, False, False]
    assert all(not library.dataset(name).in_run for name in library.names)
    assert library.shown == ["Sample_Time002", "Sample_Time000"]


# -- a run the operator hid -------------------------------------------------------------------------------


def test_a_run_hidden_by_the_operator_stays_hidden_for_the_rest_of_it_and_is_shown_by_its_next_run(library, tmp_path):
    library.watch(tmp_path)
    view = library.viewer
    hidden = lambda: (
        library.shown == [] and view.layers == [] and previews(view) == [] and offered(view)["run"]["shown"] is False
    )
    library.begin_stack(a_stack(tmp_path, planes=16))
    feed(library, range(0, 8))
    assert library.shown == ["run"]
    library.show("run", False)
    assert hidden()
    # Its folder appears, the newest of the watched folder: it is not shown for that.
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=16, slab=8)
    look(library)
    assert hidden() and library.names == ["run"]
    feed(library, range(8, 16))
    tile.write_stack()
    library.end_stack()
    look(library)
    look(library, SETTLE_S)
    assert hidden() and landed(view) == []
    # The next channel, the next tile and the next time point of the same run.
    tile.create(timepoints=2)
    for about in (dict(channel="561"), dict(tile=1), dict(time_point=1), dict(time_point=1, channel="561")):
        library.begin_stack(a_stack(tmp_path, planes=16, **about))
        assert hidden(), about
        feed(library, range(0, 16))
        look(library)
        library.end_stack()
        look(library, LIVE_S + 1)  # a time lapse waits between its time points
        assert hidden(), about
        assert offered(view)["run"]["live"] is True, "hidden, and still running"
    library.end_run()
    look(library)
    assert hidden() and offered(view)["run"]["live"] is False

    # A new run of it is what a live view shows.
    library.begin_stack(a_stack(tmp_path, planes=16))
    assert library.shown == ["run"] and view.layers == ["run"]
    assert offered(view)["run"]["shown"] is True and offered(view)["run"]["live"] is True
    feed(library, range(0, 4))
    assert landed(view, "live/")[-1][0] == f"live/{previews(view)[-1]}", "and its planes are announced again"


def test_a_run_taken_off_or_left_out_of_a_view_of_another_stays_off_until_its_next_run(library, tmp_path):
    older = an_acquisition(tmp_path, "older")
    write_tile(older / TILE.format(0), origin_um=(0, 0, 0), seed=1)
    library.watch(tmp_path)
    library.begin_stack(a_stack(tmp_path))
    assert library.shown == ["run"]
    library.viewer._server.show_reported({"name": "older", "visible": True, "only": True})  # "only this one"
    assert library.shown == ["older"]
    library.begin_stack(a_stack(tmp_path, channel="561"))
    look(library)
    assert library.shown == ["older"], "the run left out of the view stays out through its stacks"
    library.show("run")
    assert library.shown == ["run", "older"], "until the operator ticks it on again"
    library.viewer._server.remove_reported({"name": "run"})  # the panel's remove button
    library.begin_stack(a_stack(tmp_path, tile=1))
    look(library)
    assert library.names == ["run", "older"] and library.shown == ["older"]
    library.end_run()
    look(library)
    library.begin_stack(a_stack(tmp_path))
    assert library.shown == ["run", "older"], "the next run is shown; what the operator ticked stays beside it"


def test_a_run_hidden_between_two_runs_is_shown_when_the_next_begins(library):
    library.begin_stack(a_stack(name="tiffs"))
    feed(library, range(20))
    library.end_run()
    library.show("tiffs", False)
    look(library)
    assert library.shown == []
    library.begin_stack(a_stack(name="tiffs", channel="561"))
    assert library.shown == ["tiffs"]
    assert len(previews(library.viewer, "tiffs")) == 2, "with what the run before left of it"


def test_a_time_lapse_hidden_at_one_time_point_stays_hidden_at_the_next(library, tmp_path):
    """With a folder per time point the run moves from one entry of the list to the
    next: the one before is over, and what the operator ticked off stays off."""
    library.watch(tmp_path)
    view = library.viewer
    library.begin_stack(a_time_point(tmp_path, 0))
    feed(library, range(0, 8))
    library.show("Sample_Time000", False)
    library.end_stack()
    look(library)
    library.begin_stack(a_time_point(tmp_path, 1))
    feed(library, range(0, 8))
    assert library.shown == [], "ticked off during the run: off for the rest of it"
    assert offered(view)["Sample_Time000"]["live"] is False, "the time point before is over"
    assert offered(view)["Sample_Time001"]["live"] is True
    library.end_run()
    look(library, LIVE_S + 1)
    # The next run is shown again.
    library.begin_stack(a_time_point(tmp_path, 2))
    assert library.shown == ["Sample_Time002"]


def test_a_run_shown_from_its_previews_counts_its_tiles_too(library):
    """A run saved as TIFF is shown from the camera's frames alone: the list says how
    many tiles it has all the same, as it does for a run on disk."""
    for tile in (0, 1):
        for channel in ("488", "561"):
            library.begin_stack(a_stack(name="tiffs", tile=tile, channel=channel))
            feed(library, range(20))
            library.end_stack()
    library.end_run()
    look(library, LIVE_S + 1)
    assert offered(library.viewer)["tiffs"]["tiles"] == 2
