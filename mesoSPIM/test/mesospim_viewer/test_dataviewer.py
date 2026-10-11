"""What mesoSPIM-control tells the viewer about the stack it is about to acquire.

``mesoSPIM_DataViewer.py`` is all the control software holds of the viewer. Two
of its helpers are plain functions, tested here with stand-ins for the Core,
the acquisition and the acquisition list: which time point a file name of a
time lapse names, and the description of a stack (``describe_stack``) the
viewer's preview is placed by. ``Feed`` listens to the Core's signals; what it
makes of the end of a run is tested by calling it with a stand-in for itself.
No microscope, no window.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PyQt5", reason="mesoSPIM_DataViewer is part of the PyQt5 application")

from mesoSPIM.src.mesoSPIM_DataViewer import (  # noqa: E402
    Feed,
    acquisition_folder,
    close_window,
    describe_stack,
    time_point_of,
)
from mesoSPIM.src.mesospim_viewer import Stack  # noqa: E402


class Acquisition(dict):
    """One row of the acquisition list: read like a dictionary, and it knows its image count."""

    def get_image_count(self) -> int:
        return int(abs(self["z_end"] - self["z_start"]) / self["z_step"])


class AcquisitionList(list):
    def get_unique_attr_list(self, key: str) -> list[str]:
        seen = []
        for row in self:
            if row[key] not in seen:
                seen.append(row[key])
        return seen

    def get_tile_index(self, acq) -> int:
        places = []
        for row in self:
            place = (row["x_pos"], row["y_pos"])
            if place not in places:
                places.append(place)
        return places.index((acq["x_pos"], acq["y_pos"]))

    def get_n_tiles(self) -> int:
        return len({(row["x_pos"], row["y_pos"]) for row in self})


def a_row(filename: str, *, laser: str = "488 nm", x: float = 0.0, y: float = 0.0) -> Acquisition:
    return Acquisition(
        filename=filename, folder="/data/session", laser=laser, zoom="2x",
        x_pos=x, y_pos=y, z_start=100.0, z_end=1100.0, z_step=5.0,
    )


def a_core(writer=None) -> SimpleNamespace:
    """The Core as ``describe_stack`` reads it: the pixel size per zoom, and the open writer."""
    core = SimpleNamespace(cfg=SimpleNamespace(pixelsize={"1x": 6.55, "2x": 3.26}))
    if writer is not None:
        core.image_writer = SimpleNamespace(writer=writer)
    return core


def two_tiles_two_lasers(filename: str = "brain.ome.zarr") -> AcquisitionList:
    return AcquisitionList(
        [
            a_row(filename, laser="488 nm", x=0.0),
            a_row(filename, laser="561 nm", x=0.0),
            a_row(filename, laser="488 nm", x=1500.0),
            a_row(filename, laser="561 nm", x=1500.0),
        ]
    )


# -- the time point in a file name ---------------------------------------------------


def test_a_time_lapse_file_name_says_its_time_point():
    assert time_point_of("Sample.ome_Time003.zarr") == 3
    assert time_point_of("brain_Time012.ome.zarr") == 12
    assert time_point_of("brain_Time0.h5") == 0
    assert time_point_of("/data/run_Time007/brain_Time002.ome.zarr") == 2, "the file's own name, not its folder's"
    assert time_point_of("brain_Time001_Time004.ome.zarr") == 4, "the index appended last"


def test_a_file_name_without_a_time_index_is_the_first_time_point():
    assert time_point_of("brain.ome.zarr") == 0
    assert time_point_of("") == 0
    assert time_point_of("brain_Timeless.tif") == 0
    assert time_point_of("/data/run_Time007/brain.ome.zarr") == 0


# -- the description of a stack ---------------------------------------------------------


def test_a_stack_is_described_by_what_the_writers_save():
    rows = two_tiles_two_lasers()
    acq = rows[3]
    stack = describe_stack(a_core(), acq, rows, (2048, 2304))
    assert isinstance(stack, Stack)
    assert stack.acquisition == "brain"
    assert (stack.channel, stack.channels, stack.channel_index) == ("561", ("488", "561"), 1)
    assert stack.planes == 200 and stack.frame == (2048, 2304)
    assert stack.voxel_um == (5.0, 3.26, 3.26), "the z step and the pixel size of the zoom"
    assert stack.origin_um == (100.0, 0.0, 1500.0), "z start, then the stage's y and x"
    assert (stack.tile, stack.tiles) == ("Tile 2", 2)
    assert stack.time_point == 0


def test_a_run_saved_as_tiff_has_a_preview_and_no_place_on_disk():
    rows = AcquisitionList([a_row("brain_Mag2x_Tile0_Ch488.tiff"), a_row("brain_Mag2x_Tile1_Ch488.tiff", x=1500.0)])
    for core in (a_core(), a_core(SimpleNamespace(current_acquire_file_path="/data/session/brain.tiff"))):
        stack = describe_stack(core, rows[0], rows, (512, 512))
        assert stack.folder is None and stack.store is None
        assert stack.acquisition == "brain_Mag2x"  # what the files' names share
        assert stack.channels == ("488",)


def named(*filenames: str, folder: str = "/data/session", row: int = 0) -> str:
    """The name ``describe_stack`` gives a run saved as one file per stack with these names."""
    rows = AcquisitionList([a_row(filename, x=1500.0 * at) for at, filename in enumerate(filenames)])
    for found in rows:
        found["folder"] = folder
    return describe_stack(a_core(), rows[row], rows, (64, 64)).acquisition


def test_a_run_of_one_file_per_stack_is_named_by_the_whole_words_its_files_share():
    assert named("brain_Mag2x_Tile0_Ch488.tiff", "brain_Mag2x_Tile1_Ch488.tiff") == "brain_Mag2x"
    assert named("brain_Mag2x_Tile0_Ch488.tiff", "brain_Mag2x_Tile0_Ch561.tiff") == "brain_Mag2x_Tile0", (
        "not brain_Mag2x_Tile0_Ch: a word cut short is not shared"
    )
    assert named("brain_Tile1.tiff", "brain_Tile10.tiff") == "brain", "Tile1 is not a word of Tile10"
    assert named("brain_left.tif", "brain_lower.tif") == "brain"
    assert named("brain.tiff", "brain_again.tiff") == "brain", "one name whole, the other going on after a mark"
    assert named("brain-01 left.raw", "brain-01 right.raw") == "brain-01", "words end at a space, a dash or a dot too"
    assert named("brain.v2.tile0.btf", "brain.v2.tile1.btf") == "brain.v2"
    assert named("brain_Mag2x_Tile0.tiff", "brain_Mag2x_Tile1.tiff", "brain_Mag4x_Tile0.tiff") == "brain"
    # Every stack of the run says the same name, so they are shown as one acquisition.
    files = ("brain_Mag2x_Tile0_Ch488.tiff", "brain_Mag2x_Tile0_Ch561.tiff", "brain_Mag2x_Tile1_Ch488.tiff")
    assert {named(*files, row=row) for row in range(3)} == {"brain_Mag2x"}


def test_a_run_of_a_single_file_is_named_by_that_file():
    assert named("brain_Mag2x_Tile0_Ch488.tiff") == "brain_Mag2x_Tile0_Ch488"
    assert named("brain_Mag2x_Tile0_Ch488.tiff", "brain_Mag2x_Tile0_Ch488.tiff") == "brain_Mag2x_Tile0_Ch488", (
        "the same file named in two rows"
    )
    assert named("brain_.tiff") == "brain", "without a mark left hanging at its end"


def test_files_that_share_no_name_to_speak_of_are_named_by_their_folder():
    assert named("left.tiff", "right.tiff") == "session"
    assert named("a_Tile0.tiff", "b_Tile0.tiff") == "session"
    assert named("ab_Tile0.tiff", "ab_Tile1.tiff") == "session", "two letters are not a name"
    assert named("abc_Tile0.tiff", "abc_Tile1.tiff") == "abc", "three are"
    assert named("sample1.tiff", "sample2.tiff") == "session", "no whole word is shared"
    assert named("x.tiff") == "session"
    assert named("left.tiff", "right.tiff", folder="/data/session/") == "session"
    assert named("left.tiff", "right.tiff", folder="D:\\data\\session\\").endswith("session")
    assert named("left.tiff", "right.tiff", folder="") == "Acquisition", "and by a word when there is no folder either"


def test_the_time_index_of_a_time_lapse_is_no_part_of_the_shared_name():
    assert named("brain_Tile0_Time003.tiff", "brain_Tile1_Time003.tiff") == "brain"
    assert named("brain_Mag2x_Tile0_Time000.tiff", "brain_Mag2x_Tile1_Time000.tiff") == named(
        "brain_Mag2x_Tile0_Time007.tiff", "brain_Mag2x_Tile1_Time007.tiff"
    ) == "brain_Mag2x", "the same entry in the panel at every time point"


def test_an_ome_zarr_run_is_named_by_its_own_file_whatever_the_other_rows_are_called():
    rows = AcquisitionList([a_row("brain_left.ome.zarr"), a_row("brain_right.ome.zarr", x=1500.0)])
    writer = SimpleNamespace(current_acquire_file_path="/data/session/brain_right.ome.zarr/Tile0.ome.zarr")
    assert describe_stack(a_core(writer), rows[1], rows, (64, 64)).acquisition == "brain_right"


@pytest.mark.parametrize("suffix", [".ome.zarr", ".zarr", ".ome.tif", ".tiff", ".tif", ".h5", ".raw", ".btf"])
def test_the_acquisition_is_named_without_the_files_suffix(suffix):
    rows = AcquisitionList([a_row("brain" + suffix)])
    assert describe_stack(a_core(), rows[0], rows, (64, 64)).acquisition == "brain"


def test_the_one_store_per_tile_writer_names_the_tile_and_the_acquisitions_folder():
    rows = two_tiles_two_lasers("brain.ome.zarr")
    writer = SimpleNamespace(
        current_acquire_file_path="/data/session/brain.ome.zarr/Mag2x_Tile1_Sh0_Rot0.ome.zarr",
        acquisition_path="/data/session/brain.ome.zarr",
    )
    stack = describe_stack(a_core(writer), rows[2], rows, (2048, 2048))
    assert stack.store == Path("/data/session/brain.ome.zarr/Mag2x_Tile1_Sh0_Rot0.ome.zarr")
    assert stack.folder == Path("/data/session/brain.ome.zarr")
    assert (stack.acquisition, stack.time_point) == ("brain", 0)


def test_a_time_lapse_into_one_store_per_tile_is_one_acquisition_with_time_points():
    rows = two_tiles_two_lasers("brain_Time003.ome.zarr")
    writer = SimpleNamespace(
        current_acquire_file_path="/data/session/brain.ome.zarr/Mag2x_Tile0_Sh0_Rot0.ome.zarr",
        acquisition_path="/data/session/brain.ome.zarr",
    )
    stack = describe_stack(a_core(writer), rows[0], rows, (2048, 2048))
    assert stack.acquisition == "brain", "the same entry in the panel at every time point"
    assert stack.time_point == 3
    assert stack.folder == Path("/data/session/brain.ome.zarr")


def test_other_ome_zarr_writers_save_each_time_point_as_a_dataset_of_its_own():
    rows = two_tiles_two_lasers("brain_Time003.ome.zarr")
    writer = SimpleNamespace(current_acquire_file_path="/data/session/brain_Time003.ome.zarr/Tile0_Ch488.ome.zarr")
    stack = describe_stack(a_core(writer), rows[0], rows, (2048, 2048))
    assert stack.store == Path("/data/session/brain_Time003.ome.zarr/Tile0_Ch488.ome.zarr")
    assert stack.folder == Path("/data/session/brain_Time003.ome.zarr"), "the folder the store lies in"
    assert stack.time_point == 0, "its store holds this time point alone"


def test_a_time_lapse_saved_as_tiff_still_says_its_time_point():
    rows = AcquisitionList([a_row("brain_Time005.tiff")])
    stack = describe_stack(a_core(), rows[0], rows, (64, 64))
    assert (stack.acquisition, stack.time_point, stack.store) == ("brain", 5, None)


def test_a_laser_named_without_nm_is_taken_as_it_is():
    rows = AcquisitionList([a_row("brain.tiff", laser="488"), a_row("brain.tiff", laser="640 nm")])
    stack = describe_stack(a_core(), rows[1], rows, (64, 64))
    assert (stack.channel, stack.channels) == ("640", ("488", "640"))


def test_the_described_stack_is_one_the_library_takes(library, tmp_path):
    rows = two_tiles_two_lasers("brain.ome.zarr")
    writer = SimpleNamespace(
        current_acquire_file_path=str(tmp_path / "brain.ome.zarr" / "Mag2x_Tile0_Sh0_Rot0.ome.zarr"),
        acquisition_path=str(tmp_path / "brain.ome.zarr"),
    )
    library.watch(tmp_path)
    library.begin_stack(describe_stack(a_core(writer), rows[1], rows, (64, 64)))
    assert library.names == ["brain"] and library.shown == ["brain"]
    (entry,) = library.viewer._server.scene.acquisitions
    assert entry["note"] == "Tile 1 of 2 · 561" and entry["live"] is True
    assert library.viewer.scene["layers"][0]["localPosition"] == [1]


# -- where the acquisition list saves ------------------------------------------------------


def test_the_watched_folder_is_the_one_the_acquisition_list_saves_into():
    window = SimpleNamespace(state={"acq_list": two_tiles_two_lasers()})
    assert acquisition_folder(window) == "/data/session"
    assert acquisition_folder(SimpleNamespace(state={"acq_list": AcquisitionList()})) is None
    assert acquisition_folder(SimpleNamespace(state={})) is None
    assert acquisition_folder(SimpleNamespace(state={"acq_list": AcquisitionList([a_row("x") | {"folder": ""}])})) is None


# -- the end of a stack, of a time point, of a run ---------------------------------------------


class Window:
    """The Data viewer window as the feed sees it: it notes what it is told."""

    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self.told: list[str] = []

    def isVisible(self) -> bool:  # noqa: N802 -- Qt's name
        return self.visible

    def end_stack(self) -> None:
        self.told.append("end_stack")

    def end_run(self) -> None:
        self.told.append("end_run")

    def close(self) -> None:
        self.told.append("close")


def a_feed(window=None, time_point=None, **core) -> SimpleNamespace:
    """What ``Feed``'s methods read of the feed, without the signals it listens to.
    ``time_point`` is the time point of a time lapse the Core last announced."""
    feed = SimpleNamespace(
        main_window=SimpleNamespace(data_viewer_window=window),
        core=SimpleNamespace(**core),
        pending=("an acquisition", "its list"),
        running=True,
        time_point=time_point,
    )
    feed.window = lambda: Feed.window(feed)
    return feed


def finished(window=None, time_point=None, **core) -> list[str]:
    feed = a_feed(window, time_point, **core)
    Feed.on_finished(feed)
    assert feed.pending is None and feed.running is False, "whatever follows, no stack is running"
    return window.told if window is not None else []


def test_a_finished_run_ends_the_run():
    assert finished(Window()) == ["end_run"], "a Core that knows no time lapse"
    assert finished(Window(), timelapse_active=False, time_counter=0, timelapse_tpoints=0) == ["end_run"]
    # Left over from a time lapse that is no longer going on.
    assert finished(Window(), time_point=1, timelapse_active=False, timelapse_tpoints=5) == ["end_run"]


def test_a_finished_time_point_of_a_time_lapse_ends_the_stack_and_not_the_run():
    for at in (0, 1, 2, 3):
        told = finished(Window(), time_point=at, timelapse_active=True, timelapse_tpoints=5)
        assert told == ["end_stack"], at


def test_the_last_time_point_of_a_time_lapse_ends_the_run():
    assert finished(Window(), time_point=4, timelapse_active=True, timelapse_tpoints=5) == ["end_run"]
    assert finished(Window(), time_point=0, timelapse_active=True, timelapse_tpoints=1) == ["end_run"]
    assert finished(Window(), timelapse_active=True, timelapse_tpoints=5) == ["end_run"], "no time point was announced"
    assert finished(Window(), time_point=0, timelapse_active=True) == ["end_run"], "nothing says that more is to come"


def test_the_cores_own_counter_having_moved_on_does_not_end_the_run_early():
    # With no pause between the time points the Core has started the next one --
    # and counted it -- before the end of this one is heard.
    told = finished(Window(), time_point=3, timelapse_active=True, time_counter=5, timelapse_tpoints=5)
    assert told == ["end_stack"]


def test_a_whole_time_lapse_ends_its_run_once_at_its_last_time_point():
    window = Window()
    feed = a_feed(window, timelapse_active=True, timelapse_tpoints=3)
    for time_point in range(3):
        Feed.on_time_point(feed, time_point)  # the Core starts the time point...
        Feed.on_finished(feed)  # ...and says when it is acquired
    assert window.told == ["end_stack", "end_stack", "end_run"]


def test_with_no_window_open_the_end_of_a_run_is_passed_over():
    assert finished(None, time_point=1, timelapse_active=True, timelapse_tpoints=5) == []
    closed = Window(visible=False)
    assert finished(closed) == [] and finished(closed, time_point=1, timelapse_active=True, timelapse_tpoints=5) == []


def test_a_time_lapse_fed_to_the_library_stays_one_run_until_its_last_time_point(library):
    """The window passes the two calls on to the library: between two time points
    the run is still live, after the last it is over."""
    window = SimpleNamespace(
        isVisible=lambda: True, end_stack=library.end_stack, end_run=library.end_run
    )
    core = SimpleNamespace(timelapse_active=True, time_counter=0, timelapse_tpoints=2)
    feed = a_feed(window)
    feed.core = core
    rows = AcquisitionList([a_row("brain_Time000.tiff")])
    live = lambda: library.viewer._server.scene.acquisitions[0]["live"]
    for time_point in range(2):
        rows[0]["filename"] = f"brain_Time{time_point:03d}.tiff"
        Feed.on_time_point(feed, time_point)
        library.begin_stack(describe_stack(core_with_pixels(core), rows[0], rows, (64, 64)))
        assert library.names == ["brain"] and live() is True
        Feed.on_finished(feed)
        library.poll()
        assert library.dataset("brain").running is None
        assert live() is (time_point == 0), "live between the time points, over after the last"
    assert library.dataset("brain").in_run is False and library.dataset("brain").over is True


def core_with_pixels(core: SimpleNamespace) -> SimpleNamespace:
    core.cfg = a_core().cfg
    return core


# -- closing mesoSPIM ----------------------------------------------------------------------------


def test_closing_mesospim_closes_the_data_viewer_with_it():
    """A window of its own, the Data viewer left open would keep mesoSPIM running
    after File > Exit has closed every other window."""
    window = Window()
    close_window(SimpleNamespace(data_viewer_window=window))
    assert window.told == ["close"]


def test_closing_mesospim_with_no_data_viewer_open_is_fine():
    close_window(SimpleNamespace())
    close_window(SimpleNamespace(data_viewer_window=None))
