"""What the Data viewer shows, without the window: the library of acquisitions.

:class:`Library` holds the list the panel shows -- the acquisitions of the
folder the microscope writes into, and whatever the operator opened from disk --
and keeps a viewer in line with that list and with the disk: a new acquisition
is shown in place of the last, a new tile becomes a source, files that land in
a tile are named to the page, a tile that gained a time point is read again on
its own (``watch.py``). Python only, on a clock the tests move by hand.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from mesoSPIM.src.mesospim_viewer import Acquisitions, NotAStore, NotSupported
from mesoSPIM.src.mesospim_viewer.demo import write_tile
from mesoSPIM.src.mesospim_viewer.watch import ASLEEP_S, AWAKE_S, DOZING_S, LIVE_S, RECENT_S, free_name, plain_name
from mesoSPIM.src.mesospim_viewer.window import refusal

from .stores import Slabs, an_acquisition, land, one_store_per_channel, take_chunks, write_store
from .tools import events, follow, landed, offered, sources, status

TILE = "Mag1_Tile{}_Sh0_Rot0.ome.zarr"


def a_run(root, name: str, tiles: int = 1, seed: int = 1):
    """An acquisition of whole tiles side by side, written a moment after whatever is there."""
    time.sleep(0.05)  # acquisitions are told apart by when their folder appeared
    acquisition = an_acquisition(root, name)
    for tile in range(tiles):
        write_tile(acquisition / TILE.format(tile), origin_um=(0, 0, tile * 144), seed=seed + tile)
    return acquisition


# -- the folder the microscope writes into ------------------------------------------------


def test_acquisitions_are_listed_newest_first_and_tiles_are_not_mistaken_for_them(tmp_path):
    older = a_run(tmp_path, "run_a")
    newer = a_run(tmp_path, "run_b", tiles=0)
    # a bare tile store beside them is not an acquisition
    write_tile(tmp_path / "loose_tile.ome.zarr", origin_um=(0, 0, 0), seed=2)
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "half_made.ome.zarr").mkdir()  # no zarr group yet: looked at again next time
    listed = Acquisitions(tmp_path).list()
    assert [a.path for a in listed] == [newer, older]
    assert [a.name for a in listed] == ["run_b", "run_a"]
    assert Acquisitions(tmp_path).newest().path == newer
    assert Acquisitions(tmp_path / "missing").list() == [] and Acquisitions(tmp_path / "missing").newest() is None


def test_watching_a_folder_lists_its_acquisitions_newest_first_and_shows_the_newest(library, tmp_path):
    a_run(tmp_path, "run_a")
    a_run(tmp_path, "run_b", tiles=2)
    library.watch(tmp_path)
    view = library.viewer
    assert library.root == tmp_path
    assert library.names == ["run_b", "run_a"] and library.shown == ["run_b"]
    assert view.layers == ["run_b"] and len(view.stores("run_b")) == 2
    assert [layer["name"] for layer in view.scene["layers"]] == ["run_b · 488", "run_b · 561"]
    assert list(offered(view)) == ["run_b", "run_a"]
    assert view._server.scene.camera == {"fit": True}, "the view frames what is shown"
    assert landed(view) == [], "what was on disk already is simply read"


def test_a_new_acquisition_is_shown_in_place_of_the_one_shown_for_being_newest(library, tmp_path):
    a_run(tmp_path, "run_a")
    library.watch(tmp_path)
    assert library.shown == ["run_a"]
    library.clock.tick()
    library.poll()
    assert library.shown == ["run_a"]
    a_run(tmp_path, "run_b")
    library.clock.tick()
    library.poll()
    assert library.names == ["run_b", "run_a"] and library.shown == ["run_b"]
    assert library.viewer.layers == ["run_b"]
    assert library.dataset("run_a").tiles == {}, "and the old one is no longer looked at"


def test_an_acquisition_the_operator_ticked_stays_when_a_new_one_starts(library, tmp_path):
    a_run(tmp_path, "run_a")
    a_run(tmp_path, "run_b")
    library.watch(tmp_path)
    library.show("run_a")
    assert library.shown == ["run_b", "run_a"]
    a_run(tmp_path, "run_c")
    library.clock.tick()
    library.poll()
    assert library.names == ["run_c", "run_b", "run_a"]
    assert library.shown == ["run_c", "run_a"], "run_b was only shown for being the newest"
    assert library.viewer.layers == ["run_a", "run_c"]


def test_ticking_the_newest_itself_keeps_it_too(library, tmp_path):
    a_run(tmp_path, "run_a")
    library.watch(tmp_path)
    library.show("run_a")  # shown already: now it is the operator's choice
    a_run(tmp_path, "run_b")
    library.clock.tick()
    library.poll()
    assert library.shown == ["run_b", "run_a"]


def test_an_acquisition_hidden_by_the_operator_is_not_shown_again_by_the_next_look(library, tmp_path):
    a_run(tmp_path, "run_a")
    library.watch(tmp_path)
    library.show("run_a", False)
    for _ in range(3):
        library.clock.tick()
        library.poll()
    assert library.shown == [] and library.viewer.layers == []
    assert offered(library.viewer)["run_a"]["shown"] is False


def test_watching_starts_empty_and_can_be_stopped_or_moved(library, tmp_path):
    library.watch(tmp_path / "not_there_yet")
    assert library.names == [] and offered(library.viewer) == {}
    (tmp_path / "day1").mkdir()
    (tmp_path / "day2").mkdir()
    a_run(tmp_path / "day1", "run_a")
    a_run(tmp_path / "day2", "run_b")
    library.watch(tmp_path / "day1")
    assert library.shown == ["run_a"]
    library.watch(tmp_path / "day2")
    assert library.names == ["run_b", "run_a"] and library.shown == ["run_b"]
    library.watch(None)
    assert library.root is None
    a_run(tmp_path / "day2", "run_c")
    library.clock.tick()
    library.poll()
    assert library.names == ["run_b", "run_a"], "nothing is followed any more"


# -- what is shown is kept up to date with the disk ---------------------------------------------


def test_a_tile_that_lands_later_is_added_as_one_more_source(library, tmp_path):
    acquisition = a_run(tmp_path, "run")
    library.watch(tmp_path)
    view = library.viewer
    before = sources(view, "run")
    assert before == {"store-0": "data/0/"} and offered(view)["run"]["tiles"] == 1
    write_tile(acquisition / TILE.format(1), origin_um=(0, 0, 144), seed=2)
    # a folder still being created is looked at again later, not shown half-made
    (acquisition / TILE.format(2)).mkdir()
    library.clock.tick()
    library.poll()
    assert sources(view, "run") == {"store-0": "data/0/", "store-1": "data/1/"}
    assert [store.path.name for store in view.stores("run")] == [TILE.format(0), TILE.format(1)]
    assert offered(view)["run"]["tiles"] == 2
    write_tile(acquisition / TILE.format(2), origin_um=(0, 144, 0), seed=3)
    library.clock.tick()
    library.poll()
    assert list(sources(view, "run")) == ["store-0", "store-1", "store-2"]
    assert landed(view) == [], "a whole tile is read as it is: nothing of it is news"


def test_a_look_that_finds_nothing_new_tells_the_page_nothing(library, tmp_path):
    a_run(tmp_path, "run", tiles=2)
    library.watch(tmp_path)
    scene = library.viewer._server.scene
    version, sequence, follows = scene.version, scene.sequence, scene.follow["count"]
    for _ in range(5):
        library.clock.tick()
        library.poll()
    assert (scene.version, scene.sequence, scene.follow["count"]) == (version, sequence, follows)


def test_files_landing_in_a_tile_that_is_shown_are_named_to_the_page_once_each(library, tmp_path):
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=24, slab=8)
    tile.write(0)  # on disk before anyone looks
    library.watch(tmp_path)
    view = library.viewer
    before = view.state["layers"]
    assert landed(view) == []
    named = []
    for write in (
        lambda: tile.write(1),
        lambda: tile.write(2, only=2),  # a slab half written when the look comes...
        lambda: tile.write(2, skip=2),  # ...and the rest of it a second later
        lambda: tile.write(0, c=1) + tile.write(1, c=1),
        lambda: [],
    ):
        files = write()
        library.clock.tick()
        library.poll()
        said = landed(view)[len(named):]
        assert [store for store, _ in said] == (["data/0"] if files else [])
        assert sorted(file for _, listed in said for file in listed) == sorted(files)
        named += said
    everything = [file for _, files in named for file in files]
    assert len(everything) == len(set(everything)) == 16, "each file once"
    assert sources(view, "run") == {"store-0": "data/0/"}, "at the address it always had"
    assert view.state["layers"] == before, "and nothing about the layers has changed"


def test_a_tile_that_gains_a_time_point_is_read_again_alone(library, tmp_path):
    acquisition = an_acquisition(tmp_path, "run")
    growing = Slabs(acquisition / TILE.format(0))
    growing.write_stack()
    write_tile(acquisition / TILE.format(1), origin_um=(0, 0, 64), seed=2)
    library.watch(tmp_path)
    view = library.viewer
    assert sources(view, "run") == {"store-0": "data/0/", "store-1": "data/1/"}
    growing.create(timepoints=2)  # the writer grows the arrays first; the chunks land after
    library.clock.tick()
    library.poll()
    assert sources(view, "run") == {"store-0": "data/0.1/", "store-1": "data/1/"}
    assert [store.shape[0] for store in view.stores("run")] == [2, 1]
    files = growing.write(0, t=1)
    library.clock.tick()
    library.poll()
    assert landed(view) == [("data/0", files)], "named by the store, whatever address it is read at"
    assert status(view.url + "data/0.1/" + files[0]) == 200
    growing.create(timepoints=3)
    library.clock.tick()
    library.poll()
    assert sources(view, "run") == {"store-0": "data/0.2/", "store-1": "data/1/"}


def test_a_tile_that_has_just_appeared_is_looked_at_again_the_next_second(library, tmp_path):
    """The writer makes a tile's arrays when the stack starts and its first files
    land a slab later: the tile is shown at once, empty, and its first slab must
    reach the page with the next look, not a quarter of a minute later."""
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0))
    library.watch(tmp_path)
    assert offered(library.viewer)["run"]["empty"] is True
    files = tile.write(0)
    library.clock.tick()
    library.poll()
    assert landed(library.viewer) == [("data/0", files)]


def test_a_tile_gone_quiet_is_looked_at_seldom_but_then_all_of_it(library, tmp_path):
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0))
    tile.write(0)
    library.watch(tmp_path)
    view = library.viewer
    library.clock.tick(AWAKE_S + 1)
    library.poll()  # nothing landed for two minutes: from now on it dozes
    files = tile.write(1)
    library.clock.tick(DOZING_S - 2)
    library.poll()
    assert landed(view) == [], "not looked at every second any more"
    library.clock.tick(3)
    library.poll()
    assert landed(view) == [("data/0", files)]
    # Awake again: the next files are seen with the next look.
    more = tile.write(2)
    library.clock.tick()
    library.poll()
    assert landed(view)[1:] == [("data/0", more)]


def test_a_dataset_opened_from_disk_is_hardly_looked_at_once_it_is_quiet(library, tmp_path):
    tile = Slabs(tmp_path / "old.ome.zarr")
    tile.write(0)
    long_ago = time.time() - 2 * RECENT_S
    for found in [tile.path, *tile.path.rglob("*")]:
        os.utime(found, (long_ago, long_ago))
    library.open(tile.path)
    library.clock.tick(AWAKE_S + 1)
    library.poll()
    files = tile.write(1)
    library.clock.tick(DOZING_S + 5)
    library.poll()
    assert landed(library.viewer) == []
    library.clock.tick(ASLEEP_S)
    library.poll()
    assert landed(library.viewer) == [("data/0", files)]


# -- the list the panel shows -------------------------------------------------------------------


def test_the_offered_list_says_what_the_panel_needs_about_each_acquisition(library, tmp_path):
    a_run(tmp_path, "run_a", tiles=2)
    time.sleep(0.05)
    tile = Slabs(an_acquisition(tmp_path, "run_b") / TILE.format(0))
    library.watch(tmp_path)
    view = library.viewer
    keys = ("name", "shown", "live", "paused", "removable", "tiles", "note", "empty")
    about = lambda name: {key: offered(view)[name][key] for key in keys}  # positions and channels: tested below
    assert list(offered(view)) == ["run_b", "run_a"]
    assert about("run_b") == {
        "name": "run_b", "shown": True, "live": False, "paused": False, "removable": True, "tiles": 1, "note": "", "empty": True,
    }
    assert about("run_a") == {
        "name": "run_a", "shown": False, "live": False, "paused": False, "removable": True, "tiles": None, "note": "",
        "empty": False,
    }
    tile.write(0)
    library.clock.tick(DOZING_S)
    library.poll()
    assert about("run_b") == {
        "name": "run_b", "shown": True, "live": True, "paused": False, "removable": True, "tiles": 1, "note": "", "empty": False,
    }
    library.show("run_a")
    assert offered(view)["run_a"]["shown"] is True and offered(view)["run_a"]["tiles"] == 2
    assert offered(view)["run_a"]["live"] is False, "it was whole when it was first looked at"
    library.clock.tick(LIVE_S + 1)
    library.poll()
    assert offered(view)["run_b"]["live"] is False, "nothing has landed for a while"


def test_a_run_saved_as_one_store_per_channel_counts_its_tiles_by_place(library, tmp_path):
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition)
    library.watch(tmp_path)
    assert len(library.viewer.stores("run")) == 4
    assert offered(library.viewer)["run"]["tiles"] == 2


def test_any_acquisition_but_the_run_being_acquired_can_be_taken_off_the_list(library, tmp_path):
    a_run(tmp_path / "data", "run_a")
    opened = a_run(tmp_path / "elsewhere", "run_b")
    library.watch(tmp_path / "data")
    library.open(opened)
    view = library.viewer
    assert {name: entry["removable"] for name, entry in offered(view).items()} == {"run_a": True, "run_b": True}
    assert view._server.scene.ui.get("removable") is True, "the panel is told that removals are heard"
    assert library.remove("run_b") is True
    assert library.names == ["run_a"] and view.layers == ["run_a"] and list(offered(view)) == ["run_a"]
    assert library.remove("run_a") is True
    assert library.names == [] and view.layers == [] and offered(view) == {}
    assert library.remove("nothing such") is False


def test_the_panels_clicks_reach_the_library_through_the_server(library, tmp_path):
    a_run(tmp_path, "run_a")
    a_run(tmp_path, "run_b")
    library.watch(tmp_path)
    opened = a_run(tmp_path / "elsewhere", "run_c")
    library.open(opened)
    server = library.viewer._server
    assert library.shown == ["run_b", "run_c"]
    server.show_reported({"name": "run_a", "visible": True})
    assert library.shown == ["run_b", "run_a", "run_c"]
    server.show_reported({"name": "run_b", "visible": False})
    assert library.shown == ["run_a", "run_c"]
    server.show_reported({"name": "run_b", "visible": True, "only": True})
    assert library.shown == ["run_b"]
    server.remove_reported({"name": "run_c"})
    assert library.names == ["run_b", "run_a"]


def test_showing_one_alone_takes_the_others_off(library, tmp_path):
    a_run(tmp_path, "run_a")
    a_run(tmp_path, "run_b")
    a_run(tmp_path, "run_c")
    library.watch(tmp_path)
    library.show("run_a")
    library.show("run_b")
    assert library.shown == ["run_c", "run_b", "run_a"]
    library.show("run_a", only=True)
    assert library.shown == ["run_a"] and library.viewer.layers == ["run_a"]
    assert [entry["shown"] for entry in offered(library.viewer).values()] == [False, False, True]
    library.show("run_b", visible=False, only=True)
    assert library.shown == ["run_b"], "asked for alone, it is shown"
    library.show("run_b", False)
    assert library.shown == [] and library.viewer.layers == []
    library.show("nothing such")
    assert library.shown == []


def test_a_dataset_shown_again_is_read_from_disk_as_it_is_now(library, tmp_path):
    acquisition = a_run(tmp_path, "run")
    library.watch(tmp_path)
    library.show("run", False)
    write_tile(acquisition / TILE.format(1), origin_um=(0, 0, 144), seed=2)
    library.show("run")
    assert len(library.viewer.stores("run")) == 2
    assert list(sources(library.viewer, "run")) == ["store-0", "store-1"], "the first tile under the name it had"


# -- opening from disk ------------------------------------------------------------------------------


def test_a_tile_an_acquisition_or_a_folder_of_acquisitions_can_be_opened(library, tmp_path):
    older = a_run(tmp_path / "session", "run_a", tiles=2)
    a_run(tmp_path / "session", "run_b")
    loose = write_tile(tmp_path / "loose" / "single.ome.zarr", origin_um=(0, 500, 0), seed=4, timepoints=3)
    view = library.viewer

    # One tile store on its own, named without its suffix.
    assert library.open(loose) == ["single"]
    assert view.layers == ["single"] and view.stores("single")[0].shape[0] == 3
    assert library.dataset("single").single and library.dataset("single").opened

    # One acquisition: all its tiles in one layer named after it, beside what is shown.
    assert library.open(older) == ["run_a"]
    assert library.shown == ["single", "run_a"]
    assert [store.path.name for store in view.stores("run_a")] == [TILE.format(0), TILE.format(1)]
    # Each tile placed by its own metadata: the viewer shifts none of them.
    assert [store.translation[-3:] for store in view.stores("run_a")] == [(0, 0, 0), (0, 0, 144)]
    assert all("transform" not in source for source in view.scene["layers"][-1]["source"])

    # A data folder: every acquisition is listed, oldest first, and the newest is shown.
    assert library.open(tmp_path / "session") == ["run_a", "run_b"]
    assert library.names == ["single", "run_a", "run_b"]
    assert library.shown == ["single", "run_a", "run_b"]
    assert all(entry["removable"] for entry in offered(view).values())


def test_a_folder_of_acquisitions_opened_from_disk_shows_its_newest_and_follows_nothing(library, tmp_path):
    a_run(tmp_path, "run_a")
    a_run(tmp_path, "run_b")
    assert library.open(tmp_path) == ["run_a", "run_b"]
    assert library.shown == ["run_b"] and library.root is None
    a_run(tmp_path, "run_c")
    library.clock.tick()
    library.poll()
    assert library.names == ["run_a", "run_b"], "an acquisition appearing later is not picked up"
    assert library.open(tmp_path) == ["run_a", "run_b", "run_c"], "until the folder is opened again"
    assert library.shown == ["run_b", "run_c"]


def test_a_folder_that_holds_tiles_directly_opens_as_one_acquisition(library, tmp_path):
    folder = tmp_path / "plain_folder"
    write_tile(folder / "a.ome.zarr", origin_um=(0, 0, 0), seed=1)
    write_tile(folder / "b.ome.zarr", origin_um=(0, 0, 144), seed=2)
    assert library.open(folder) == ["plain_folder"]
    assert len(library.viewer.stores("plain_folder")) == 2


def test_opening_what_is_listed_already_just_shows_it(library, tmp_path):
    run = a_run(tmp_path, "run_a")
    library.watch(tmp_path)
    library.show("run_a", False)
    assert library.open(run) == ["run_a"]
    assert library.names == ["run_a"] and library.shown == ["run_a"]
    assert library.dataset("run_a").opened is False, "still the watched folder's own"
    assert library.open(run) == ["run_a"] and library.viewer.layers == ["run_a"]


def test_two_acquisitions_of_one_name_are_two_entries(library, tmp_path):
    first = a_run(tmp_path / "day1", "run")
    again = a_run(tmp_path / "day2", "run")
    third = a_run(tmp_path / "day3", "run")
    assert library.open(first) == ["run"]
    assert library.open(again) == ["run (2)"]
    assert library.open(third) == ["run (3)"]
    view = library.viewer
    assert view.layers == ["run", "run (2)", "run (3)"]
    assert view.stores("run")[0].path.parent == first and view.stores("run (2)")[0].path.parent == again
    assert [spec["name"] for spec in view.scene["layers"]][:4] == ["run · 488", "run · 561", "run (2) · 488", "run (2) · 561"]
    # Taken off and opened again, it comes back under the name that is free.
    library.remove("run (2)")
    assert library.open(again) == ["run (2)"]
    assert free_name(["a", "a (2)"], "a") == "a (3)" and free_name([], "a") == "a"
    assert plain_name(first) == "run" and plain_name(tmp_path) == tmp_path.name


def test_a_watched_acquisition_is_numbered_when_its_name_is_taken_by_an_opened_one(library, tmp_path):
    opened = a_run(tmp_path / "day1", "run_a")
    library.open(opened)
    watched = a_run(tmp_path / "session", "run_a")
    library.watch(tmp_path / "session")
    assert library.names == ["run_a (2)", "run_a"], "the watched folder's first, then what was opened"
    assert library.viewer.stores("run_a (2)")[0].path.parent == watched
    assert library.viewer.stores("run_a")[0].path.parent == opened


def test_what_cannot_be_opened_says_why_in_one_sentence(library, tmp_path):
    a_run(tmp_path, "run_a")
    library.watch(tmp_path)

    def refused(path, kind=NotAStore):
        with pytest.raises(kind) as caught:
            library.open(path)
        return refusal(path, caught.value)

    (tmp_path / "notes").mkdir()
    with pytest.raises(NotAStore, match="not a dataset the viewer can open"):
        library.open(tmp_path / "notes")
    assert refused(tmp_path / "notes") == "notes isn't an OME-Zarr folder the viewer can open."
    assert refused(tmp_path / "never_there") == "never_there isn't an OME-Zarr folder the viewer can open."
    broken = tmp_path / "broken.ome.zarr"
    broken.mkdir()
    (broken / ".zattrs").write_text("{not json")
    assert refused(broken) == "broken.ome.zarr can't be shown: its metadata could not be read."
    newer_format = write_tile(tmp_path / "other" / "newer.ome.zarr", origin_um=(0, 0, 0), seed=8)
    attrs = json.loads((newer_format / ".zattrs").read_text())
    attrs["multiscales"][0]["version"] = "0.6"
    (newer_format / ".zattrs").write_text(json.dumps(attrs))
    assert refused(newer_format, NotSupported) == (
        "newer.ome.zarr can't be shown: it is OME-NGFF 0.6, which the viewer does not read yet."
    )
    # Beside others it is not taken for an acquisition, and its folder says the same.
    assert Acquisitions(tmp_path / "other").list() == []
    assert refused(tmp_path / "other", NotSupported).startswith("other can't be shown: it is OME-NGFF 0.6")
    # An acquisition whose tiles cannot be read says why its tiles could not.
    odd = an_acquisition(tmp_path / "odd", "run_x")
    attrs["multiscales"][0]["version"] = "0.4"
    attrs["multiscales"][0]["axes"][1]["type"] = "space"
    tile = write_tile(odd / TILE.format(0), origin_um=(0, 0, 0), seed=9)
    (tile / ".zattrs").write_text(json.dumps(attrs))
    assert refused(odd, NotSupported) == "run_x.ome.zarr can't be shown: its axis c is not of type channel."
    assert refusal(tmp_path / "gone", OSError("no such folder")) == (
        "gone isn't an OME-Zarr folder the viewer can open."
    )
    # What was shown is left alone.
    assert library.names == ["run_a"] and library.viewer.layers == ["run_a"]


# -- stores of other layouts ----------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["0.4", "0.5"])
def test_one_store_per_channel_becomes_one_row_per_channel(library, tmp_path, version):
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition, version=version)
    assert library.open(acquisition) == ["run"]
    layers = library.viewer.scene["layers"]
    assert [layer["name"] for layer in layers] == ["run · 488", "run · 561"]
    for layer in layers:
        assert len(layer["source"]) == 2, "each channel reads only its own two tiles"
        assert "localPosition" not in layer
    assert [layer["shaderControls"]["color"] for layer in layers] == ["#00ff66", "#ff33ff"]


def test_without_channel_metadata_the_stores_are_shown_as_one_channel(library, tmp_path):
    # The channel is taken from inside the store only, never from its name: a store
    # that does not say which channel it holds cannot be told apart from the others.
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition, omero=False)
    library.open(acquisition)
    layers = library.viewer.scene["layers"]
    assert len(layers) == 1 and len(layers[0]["source"]) == 4


def test_a_single_store_without_channel_axis_opens_on_its_own(library, tmp_path):
    assert library.open(write_store(tmp_path / "zyx.ome.zarr", axes="zyx", version="0.5")) == ["zyx"]
    assert [layer["name"] for layer in library.viewer.scene["layers"]] == ["zyx · 488"]


# -- the contrast, and where a live view looks ---------------------------------------------------------


def test_a_dataset_that_is_not_being_written_gets_its_contrast_once_from_its_data(library, tmp_path):
    store = write_store(tmp_path / "plain.ome.zarr")  # no window in its metadata
    library.open(store)
    view = library.viewer
    first = [layer["shaderControls"]["contrast"]["range"] for layer in view.scene["layers"]]
    assert all(low == 400 for low, _ in first)
    assert [layer["_auto"] for layer in view.scene["layers"]] == [False, False]


def test_a_store_opened_empty_is_measured_when_it_is_first_seen_to_hold_data(library, tmp_path):
    store = write_store(tmp_path / "plain.ome.zarr")
    taken = take_chunks(store)
    library.open(store)
    view = library.viewer
    assert all("contrast" not in layer["shaderControls"] for layer in view.scene["layers"])
    assert [layer["_auto"] for layer in view.scene["layers"]] == [True, True]
    assert offered(view)["plain"]["empty"] is True
    land(taken)
    library.clock.tick(ASLEEP_S)
    library.poll()
    assert offered(view)["plain"]["empty"] is False


def test_the_contrast_of_an_acquisition_being_written_is_left_to_the_page(library, tmp_path):
    tile = write_tile(an_acquisition(tmp_path, "run") / TILE.format(0), origin_um=(0, 0, 0), seed=1)
    late = take_chunks(tile, lambda chunk: chunk.parent.name == "0" and int(chunk.name.split(".")[2]) >= 12)
    library.watch(tmp_path)
    view = library.viewer
    auto = lambda: [layer["_auto"] for layer in view.scene["layers"]]
    assert auto() == [False, False], "the store names its window, and nothing says it is being written"
    land(late)
    library.clock.tick()
    library.poll()
    assert offered(view)["run"]["live"] is True
    assert auto() == [True, True], "while it is written nobody knows its brightness"
    library.clock.tick(LIVE_S + 1)
    library.poll()
    assert offered(view)["run"]["live"] is False
    assert auto() == [False, False]


def test_a_live_view_is_pointed_at_the_newest_complete_plane_on_disk(library, tmp_path):
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=24, slab=8, origin_um=(100.0, 0.0, 0.0))
    tile.write(0)
    library.watch(tmp_path)
    view = library.viewer
    assert follow(view) == {}, "nothing has landed while watched: nothing is running"
    tile.write(1)
    library.clock.tick()
    library.poll()
    assert follow(view) == {"z": 100.0 + 15 * 5.0, "t": 0.0}, "the sixteenth plane, in micrometres"
    tile.write(2, only=1)
    library.clock.tick()
    library.poll()
    assert follow(view)["z"] == 175.0, "a slab half written is not a plane to look at"
    tile.write(2, skip=1)
    library.clock.tick()
    library.poll()
    assert follow(view) == {"z": 100.0 + 23 * 5.0, "t": 0.0}
    tile.write(0, c=1)
    library.clock.tick()
    library.poll()
    assert follow(view)["z"] == 100.0 + 7 * 5.0, "the next channel starts again at the top"
    library.clock.tick(LIVE_S + 1)
    library.poll()
    assert follow(view) == {}, "the run is over: nothing to follow"


def test_the_time_point_being_written_is_followed_too(library, tmp_path):
    tile = Slabs(an_acquisition(tmp_path, "run") / TILE.format(0), planes=16, slab=8)
    tile.write_stack()
    library.watch(tmp_path)
    tile.create(timepoints=2)
    library.clock.tick()
    library.poll()
    tile.write(0, t=1)
    library.clock.tick()
    library.poll()
    assert follow(library.viewer) == {"z": 35.0, "t": 1.0}
    assert events(library.viewer)[-1]["store"] == "data/0"


# -- each acquisition's positions, for the panel to list and go to ---------------------------


def test_an_acquisition_offers_its_positions_with_their_place_and_its_channels(library, tmp_path):
    a_run(tmp_path, "run", tiles=2)  # two tiles of 160 x 160 um and 24 planes of 5 um, 144 um apart
    library.watch(tmp_path)
    entry = offered(library.viewer)["run"]
    assert entry["channels"] == ["488", "561"]
    assert entry["positions"] == [
        {"name": "Tile 1", "um": {"x": [0.0, 160.0], "y": [0.0, 160.0], "z": [0.0, 120.0]}},
        {"name": "Tile 2", "um": {"x": [144.0, 304.0], "y": [0.0, 160.0], "z": [0.0, 120.0]}},
    ]


def test_an_acquisition_not_shown_offers_its_positions_by_name(library, tmp_path):
    a_run(tmp_path, "run_a", tiles=2)
    a_run(tmp_path, "run_b")
    library.watch(tmp_path)
    entry = offered(library.viewer)["run_a"]
    assert entry["shown"] is False
    assert [position["name"] for position in entry["positions"]] == ["Tile 1", "Tile 2"]
    assert entry["channels"] == ["488", "561"], "read from its first tile, without showing it"


def test_a_run_of_the_watched_folder_taken_off_the_list_stays_off(library, tmp_path):
    a_run(tmp_path, "run_a")
    a_run(tmp_path, "run_b")
    library.watch(tmp_path)
    assert offered(library.viewer)["run_a"]["removable"] is True
    assert library.remove("run_a") is True
    library.clock.tick(5)
    library.poll()
    assert library.names == ["run_b"], "the next look at the folder does not bring it back"
    a_run(tmp_path, "run_c")
    library.clock.tick(5)
    library.poll()
    assert library.names == ["run_c", "run_b"], "a new one still comes in"
