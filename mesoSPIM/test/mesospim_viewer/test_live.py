"""The stack being acquired, kept in memory as a small zarr store.

A :class:`PreviewStack` takes the camera's frames as they come, thinned out
across and in depth, and answers the page's requests for a zarr v2 store whose
planes exist the moment they arrived (``live.py``). Python and numpy only.
"""

from __future__ import annotations

import json

import numpy as np

from mesoSPIM.src.mesospim_viewer import PreviewStack, Stack
from mesoSPIM.src.mesospim_viewer.live import MAX_ACROSS, MAX_PLANES, thin, thinning


def a_stack(**about) -> Stack:
    described = dict(
        acquisition="run",
        channel="488",
        channels=("488", "561"),
        planes=10,
        frame=(32, 32),
        voxel_um=(5.0, 1.0, 1.0),
        origin_um=(100.0, 200.0, 300.0),
    )
    return Stack(**{**described, **about})


def a_frame(value: int, shape=(32, 32)) -> np.ndarray:
    """A frame on a ground of ``value`` with a bright square, so that it has a contrast."""
    frame = np.full(shape, value, np.uint16)
    frame[: shape[0] // 4, : shape[1] // 4] = value + 2000
    return frame


def planes_held(preview: PreviewStack) -> list[int]:
    """The ground value of every plane of the preview: 0 where none has arrived."""
    return [int(plane[-1, -1]) for plane in preview.data]


# -- thinning out ---------------------------------------------------------------------


def test_a_frame_is_thinned_to_at_most_512_across():
    assert thinning((2048, 2048)) == 4 and thinning((2304, 2048)) == 5
    assert thinning((512, 512)) == 1 and thinning((100, 60)) == 1
    assert thinning((64, 40), max_across=16) == 4
    frame = np.arange(2048 * 2048, dtype=np.uint16).reshape(2048, 2048)
    thinned = thin(frame)
    assert thinned.shape == (512, 512) and thinned.dtype == np.uint16
    assert thinned[1, 1] == frame[4, 4]
    frame[4, 4] = 7
    assert thinned[1, 1] != 7, "a copy of its own: the camera may reuse the frame's memory"
    assert thin(np.zeros((30, 50), np.uint16), max_across=10).shape == (6, 10)


def test_a_preview_keeps_every_few_pixels_and_every_few_planes():
    preview = PreviewStack(a_stack(planes=20, frame=(40, 64)), max_across=16, max_planes=8)
    assert (preview.step, preview.every) == (4, 3)
    assert preview.shape == (7, 10, 16) == preview.data.shape
    assert preview.data.dtype == np.dtype("<u2") and preview.bytes == 7 * 10 * 16 * 2
    small = PreviewStack(a_stack(planes=10, frame=(32, 32)))
    assert (small.step, small.every, small.shape) == (1, 1, (10, 32, 32))


def test_a_stack_of_any_size_fits_the_previews_budget():
    big = PreviewStack(a_stack(planes=3000, frame=(2048, 2048)))
    assert big.step == 4 and big.every == 12
    assert big.shape == (250, 512, 512)
    assert big.shape[0] <= MAX_PLANES and max(big.shape[1:]) <= MAX_ACROSS
    assert big.bytes <= MAX_PLANES * MAX_ACROSS * MAX_ACROSS * 2


def test_a_stack_says_which_of_the_runs_channels_it_is():
    assert a_stack(channel="561").channel_index == 1
    assert a_stack(channel="640").channel_index == 0, "a channel the run does not list"
    assert a_stack().folder is None and a_stack().store is None and a_stack().time_point == 0


# -- filling --------------------------------------------------------------------------------


def test_a_whole_frame_is_thinned_and_a_thinned_one_is_taken_as_it_is():
    preview = PreviewStack(a_stack(frame=(64, 64)), max_across=16)
    whole = np.arange(64 * 64, dtype=np.uint16).reshape(64, 64)
    assert preview.add(0, whole) == ["0/0/0/0/0/0"]
    assert np.array_equal(preview.data[0], whole[::4, ::4])
    assert preview.add(1, thin(whole + 1, 16)) == ["0/0/0/1/0/0"]
    assert np.array_equal(preview.data[1], (whole + 1)[::4, ::4])
    assert preview.add(2, np.zeros((7, 9), np.uint16)) == [], "a frame of another size is passed over"
    assert preview.add(-1, whole) == []
    assert preview.top == 1 and preview.plane == 1


def test_the_chunk_files_are_named_for_the_stacks_channel():
    preview = PreviewStack(a_stack(channel="561"))
    assert preview.chunk_file(3) == "0/0/1/3/0/0"
    assert preview.add(0, a_frame(500)) == ["0/0/1/0/0/0"]


def test_planes_the_microscope_passed_over_are_filled_with_the_next_frame():
    preview = PreviewStack(a_stack(planes=10))
    assert preview.add(0, a_frame(500)) == ["0/0/0/0/0/0"]
    # The microscope hands on every other frame, or fewer when it is busy.
    assert preview.add(4, a_frame(900)) == [f"0/0/0/{z}/0/0" for z in (1, 2, 3, 4)]
    assert planes_held(preview) == [500, 900, 900, 900, 900, 0, 0, 0, 0, 0], "never a hole"
    assert preview.top == 4 and preview.plane == 4


def test_a_preview_that_thins_in_depth_keeps_the_first_frame_of_each_plane():
    preview = PreviewStack(a_stack(planes=12), max_planes=4)  # every third plane
    assert preview.every == 3 and preview.shape[0] == 4
    assert preview.add(0, a_frame(500)) == ["0/0/0/0/0/0"]
    assert preview.add(1, a_frame(600)) == [], "a plane that is on screen is not drawn again"
    assert preview.add(5, a_frame(700)) == ["0/0/0/1/0/0"]
    assert preview.add(11, a_frame(800)) == ["0/0/0/2/0/0", "0/0/0/3/0/0"]
    assert planes_held(preview) == [500, 700, 800, 800]
    assert preview.add(400, a_frame(900)) == [], "a plane past the end falls on the last, which is there"
    assert preview.plane == 400 and preview.top == 3


def test_an_earlier_plane_arriving_late_does_not_take_the_stack_back():
    preview = PreviewStack(a_stack(planes=10))
    preview.add(5, a_frame(500))
    assert preview.add(2, a_frame(900)) == [], "what is on screen stays"
    assert preview.top == 5 and preview.plane == 5
    assert planes_held(preview)[:6] == [500] * 6


def test_finishing_fills_a_short_tail_with_the_newest_plane():
    preview = PreviewStack(a_stack(planes=40))
    assert preview.finish() == [], "nothing arrived, nothing to fill with"
    for z in range(0, 37, 2):
        preview.add(z, a_frame(500 + z))
    assert preview.top == 36
    assert preview.finish() == [f"0/0/0/{z}/0/0" for z in (37, 38, 39)], "up to a tenth of the stack"
    assert planes_held(preview)[36:] == [536, 536, 536, 536]
    assert preview.top == 39
    assert preview.finish() == [], "already whole"


def test_finishing_leaves_a_stack_that_was_stopped_half_way_as_far_as_it_got():
    preview = PreviewStack(a_stack(planes=20))
    for z in range(10):
        preview.add(z, a_frame(500))
    assert preview.finish() == []
    assert preview.top == 9 and planes_held(preview)[10:] == [0] * 10
    # Two planes are always a short tail, however shallow the stack.
    shallow = PreviewStack(a_stack(planes=5))
    shallow.add(2, a_frame(500))
    assert shallow.finish() == ["0/0/0/3/0/0", "0/0/0/4/0/0"]
    stopped = PreviewStack(a_stack(planes=5))
    stopped.add(1, a_frame(500))
    assert stopped.finish() == []


# -- where it is, and how bright ----------------------------------------------------------------


def test_the_newest_plane_is_where_the_preview_has_got_to_in_micrometres():
    preview = PreviewStack(a_stack(planes=12, voxel_um=(5.0, 1.0, 1.0)), max_planes=4)
    assert preview.newest_um is None
    preview.add(0, a_frame(500))
    assert preview.newest_um == 100.0, "the stack's origin"
    preview.add(7, a_frame(500))
    assert preview.newest_um == 100.0 + 2 * 3 * 5.0, "the third plane of the preview stands for planes 6 to 8"


def test_the_first_frame_sets_the_previews_contrast():
    preview = PreviewStack(a_stack(colour="#00ff66"))
    assert preview.window is None and preview.channel().window is None
    preview.add(0, np.full((32, 32), 500, np.uint16))
    assert preview.window is None, "a flat frame says nothing"
    preview.add(1, a_frame(500))
    low, high = preview.window
    assert low == 500 and 2500 <= high <= 2800
    preview.add(2, a_frame(9000))
    assert preview.window == (low, high), "set once"
    channel = preview.channel()
    assert (channel.label, channel.color, channel.window) == ("488", "#00ff66", (low, high))


# -- being read by the page ----------------------------------------------------------------------


def test_the_preview_describes_itself_as_a_tczyx_store_where_the_stack_is():
    stack = a_stack(planes=20, frame=(40, 64), voxel_um=(5.0, 1.5, 1.5), time_point=2)
    preview = PreviewStack(stack, max_across=16, max_planes=8)
    assert json.loads(preview.read(".zgroup")) == {"zarr_format": 2}
    array = json.loads(preview.read("0/.zarray"))
    assert array["shape"] == [1, 2, 7, 10, 16], "as many channels as the run has"
    assert array["chunks"] == [1, 1, 1, 10, 16], "one file to a plane"
    assert array["dtype"] == "<u2" and array["compressor"] is None and array["dimension_separator"] == "/"
    (multiscale,) = json.loads(preview.read(".zattrs"))["multiscales"]
    assert multiscale["version"] == "0.4"
    assert [axis["name"] for axis in multiscale["axes"]] == ["t", "c", "z", "y", "x"]
    scale, translation = multiscale["datasets"][0]["coordinateTransformations"]
    assert scale == {"type": "scale", "scale": [1.0, 1.0, 15.0, 6.0, 6.0]}, "the voxels kept, in micrometres"
    assert translation == {"type": "translation", "translation": [2.0, 0.0, 100.0, 200.0, 300.0]}


def test_the_viewers_own_reader_reads_the_previews_description(tmp_path):
    from mesoSPIM.src.mesospim_viewer import read_store

    preview = PreviewStack(a_stack(planes=20, frame=(40, 64)), max_across=16, max_planes=8)
    for name in (".zgroup", ".zattrs", "0/.zarray"):
        target = tmp_path / "preview.ome.zarr" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(preview.read(name))
    store = read_store(tmp_path / "preview.ome.zarr")
    assert store.shape == (1, 2, 7, 10, 16) and store.scale == (1.0, 1.0, 15.0, 4.0, 4.0)
    assert store.translation == (0.0, 0.0, 100.0, 200.0, 300.0)


def test_a_plane_can_be_read_once_it_has_arrived_and_not_before():
    preview = PreviewStack(a_stack(channel="561"))
    assert preview.read("0/0/1/0/0/0") is None
    frame = a_frame(500)
    preview.add(0, frame)
    assert preview.read("0/0/1/0/0/0") == frame.astype("<u2").tobytes()
    assert preview.read("0/0/1/1/0/0") is None, "the next plane has not arrived"
    preview.add(3, a_frame(900))
    assert preview.read("0/0/1/2/0/0") == a_frame(900).astype("<u2").tobytes(), "filled forward"
    assert preview.read("0/0/1/9/0/0") is None


def test_only_the_stacks_own_chunks_are_files_of_the_preview():
    preview = PreviewStack(a_stack(channel="561"))
    preview.add(9, a_frame(500))
    for path in ("0/0/0/0/0/0", "0/1/1/0/0/0", "0/0/1/0/1/0", "0/0/1/0/0/1", "1/0/1/0/0/0", "0/0/1/0/0",
                 "0/0/1/x/0/0", "", "zarr.json", "0/zarr.json", ".zmetadata"):
        assert preview.read(path) is None, path
    assert preview.read(preview.chunk_file(9)) is not None
