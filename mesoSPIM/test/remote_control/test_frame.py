"""get_frame and get_snapshot: the readouts a client (or a model) decides from."""
import base64
import io

import numpy as np
import pytest

from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher
from mesoSPIM.src.mesoSPIM_RemoteControl_Frame import describe_frame, downsample, focus_measure, frame_stats
from mesoSPIM.test.remote_control.support.fakes import RecordingCore


def _frame():
    frame = np.full((300, 400), 100, dtype=np.uint16)
    frame[100:200, 250:350] = 3000
    frame[150, 300] = 65535  # one saturated pixel
    return frame


def test_stats_describe_exposure_and_signal_position():
    stats = frame_stats(_frame())
    assert stats["shape"] == [300, 400] and stats["dtype"] == "uint16" and stats["full_scale"] == 65535
    assert stats["background"] == 100 and stats["max"] == 65535
    assert 0 < stats["saturated_fraction"] < 0.001
    assert 0.05 < stats["bright_fraction"] < 0.12                # the 100x100 rectangle of 120000 px
    assert abs(stats["signal_centroid"]["row"] - 0.5) < 0.02
    assert abs(stats["signal_centroid"]["col"] - 0.75) < 0.02
    assert stats["focus_measure"] > 0


def test_flat_frame_has_no_centroid_and_zero_focus():
    stats = frame_stats(np.zeros((50, 50), dtype=np.uint16))
    assert stats["signal_centroid"] is None
    assert stats["focus_measure"] == 0.0 and stats["saturated_fraction"] == 0.0


def test_focus_measure_prefers_the_sharper_image():
    rng = np.random.default_rng(0)
    sharp = rng.integers(0, 4000, (200, 200)).astype(np.float32)
    blurred = np.kron(downsample(sharp, 100), np.ones((2, 2), dtype=np.float32))   # block mean = blur
    assert focus_measure(sharp) > focus_measure(blurred)


def test_png_is_bounded_and_stretched():
    document = describe_frame(_frame(), max_size=200)
    image = document["image"]
    assert image["format"] == "png" and max(image["width"], image["height"]) <= 200
    from PIL import Image
    decoded = np.asarray(Image.open(io.BytesIO(base64.b64decode(image["base64"]))))
    assert decoded.dtype == np.uint8 and decoded.max() == 255 and decoded.min() == 0


def test_numbers_only_when_asked():
    document = describe_frame(_frame(), include_image=False)
    assert document["available"] and "image" not in document and "stats" in document


def test_get_frame_reports_no_frame_before_a_snap():
    core = RecordingCore()
    assert dispatcher.run(core, "get_frame", {}) == {"available": False}


def test_get_frame_after_a_snap_over_the_dispatcher():
    core = RecordingCore()
    dispatcher.run(core, "snap", {})
    document = dispatcher.run(core, "get_frame", {"max_size": 64, "include_image": True})
    assert document["available"] and document["stats"]["shape"] == [64, 96]
    assert max(document["image"]["width"], document["image"]["height"]) <= 64
    with pytest.raises(dispatcher.ValidationError):
        dispatcher.run(core, "get_frame", {"max_size": 10})


def test_snapshot_is_one_compact_readout():
    core = RecordingCore()
    core.state["position"]["x_pos"] = 0.0
    core.state["position_absolute"]["x_pos"] = 24999.0            # x zeroed
    snapshot = dispatcher.run(core, "get_snapshot", {})
    assert snapshot["state"] == "idle" and snapshot["operation"] == {"status": "idle"}
    assert snapshot["zeroed_axes"] == ["x"]
    assert snapshot["position"]["x"] == 0.0 and snapshot["position_stage"]["x"] == 24999.0
    assert snapshot["limits"]["x"] == [-25000, 25000]
    assert snapshot["optics"]["laser"] == "488 nm" and snapshot["camera"]["pixels"] == [2048, 2048]
    assert snapshot["acquisition_list"]["rows"] == 1
    assert snapshot["disk"] == {"free_bytes": 1_000_000, "required_bytes": 500_000}
    assert snapshot["time_lapse"]["active"] is False
    assert snapshot["frame_available"] is False and snapshot["last_snap"] is None
    dispatcher.run(core, "snap", {})
    snapshot = dispatcher.run(core, "get_snapshot", {})
    assert snapshot["frame_available"] is True
    assert snapshot["last_snap"].endswith(".tif")
