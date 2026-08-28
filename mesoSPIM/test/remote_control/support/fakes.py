"""Provide a thread-safe recording Core for TCP and MCP integration tests.

``RecordingCore``, ``FakeCfg``, and ``FakeState`` expose the production interfaces used by Remote
Control while keeping all state in memory. Concurrent HTTP workers and the test thread share one
lock-protected call log, so race tests can inspect exactly which Core methods were reached.
"""

from __future__ import annotations

import threading

from mesoSPIM.test.remote_control.support.fake_state import FakeState


class FakeCfg:
    """Configuration with an enforced range for every stage axis, including theta."""

    version = "test-1.0"
    filterdict = {"Empty": 0, "515LP": 1}
    zoomdict = {"1x": 1, "2x": 2}
    laserdict = {"488 nm": 0, "561 nm": 1}
    shutteroptions = ("Left", "Right", "Both")
    pixelsize = {"1x": 1.0, "2x": 0.5}
    binning_dict = {"1x1": (1, 1), "2x2": (2, 2)}
    camera_parameters = {"x_pixels": 2048, "y_pixels": 2048, "subsampling": [1, 2, 4]}
    stage_parameters = {
        "x_min": -25000,
        "x_max": 25000,
        "y_min": -50000,
        "y_max": 50000,
        "z_min": -25000,
        "z_max": 25000,
        "f_min": 0,
        "f_max": 98000,
        "theta_min": -999,
        "theta_max": 999,
        "stage_type": "DemoStage",
        "y_load_position": 1000,
        "y_unload_position": -1000,
        "x_center_position": 0,
        "z_center_position": 0,
    }

    def __init__(self):
        cls = type(self)
        self.filterdict = dict(cls.filterdict)
        self.zoomdict = dict(cls.zoomdict)
        self.laserdict = dict(cls.laserdict)
        self.pixelsize = dict(cls.pixelsize)
        self.binning_dict = dict(cls.binning_dict)
        self.camera_parameters = dict(cls.camera_parameters)
        self.camera_parameters["subsampling"] = list(cls.camera_parameters.get("subsampling", []))
        self.stage_parameters = dict(cls.stage_parameters)


class _Sig:
    """Record signal names and drive connected slots like a small bound Qt signal."""

    def __init__(self, core, name):
        self._core, self._name = core, name
        self._slots = []

    def connect(self, slot, *a, **k):
        self._slots.append(slot)

    def disconnect(self, slot=None):
        self._slots = [] if slot is None else [s for s in self._slots if s is not slot]

    def emit(self, *args):
        self._core._record(self._name, *args)
        for slot in list(self._slots):
            slot(*args)


class _SerialWorker:
    """serial_worker.move_relative logs under the BARE name "move_relative": Commands.py prefers it
    over Core.move_relative, so the wire matrix exercises that path and matches
    EXPECTED_CORE_CALL["move_relative"] == "move_relative"."""

    def __init__(self, core):
        self._core = core

    def move_relative(self, *args, **kwargs):
        self._core._record("move_relative", *args, **kwargs)
        moves = args[0]
        self._core._apply_move(moves, "_rel")

    def move_absolute(self, *args, **kwargs):
        self._core._record("move_absolute", *args, **kwargs)
        moves = args[0]
        self._core._apply_move(moves, "_abs")


class RecordingCore:
    """Production state contract; records every Core call/emit under a lock so the concurrent HTTP
    worker threads and the test thread share one inspectable log."""

    def __init__(self):
        self.cfg = FakeCfg()
        self._lock = threading.Lock()
        self._build()
        self.serial_worker = _SerialWorker(self)

    def _build(self):
        self.state = FakeState(
            state="idle",
            position={"x_pos": 24999.0, "y_pos": 0.0, "z_pos": 0.0, "f_pos": 1000.0, "theta_pos": 0.0},
            position_absolute={
                "x_pos": 24999.0,
                "y_pos": 0.0,
                "z_pos": 0.0,
                "f_pos": 1000.0,
                "theta_pos": 0.0,
            },
            shutterconfig="Left",
            ETL_cfg_file="etl.csv",
            acq_list=[{}],
        )
        self.timelapse_active = False
        self._remote_session = {"operation": None, "counter": 0}
        self._calls = []

    def reset(self):
        """Clear the log and REBUILD state AND the session, so a case never inherits the previous
        one's busy gate or its saved acquisition list."""
        with self._lock:
            self._build()

    def calls(self):
        with self._lock:
            return list(self._calls)

    def _record(self, name, *args, **kwargs):
        with self._lock:
            self._calls.append((name, args, kwargs))

    def _apply_move(self, moves, suffix):
        for key, value in moves.items():
            position_key = key.replace(suffix, "_pos")
            if suffix == "_abs":
                updated = float(value)
            else:
                updated = self.state["position"][position_key] + float(value)
            self.state["position"][position_key] = updated
            self.state["position_absolute"][position_key] = updated

    # --- movement / stage (record-only; the matrix's spot-ladder is gone) ---
    def move_absolute(self, *args, **kwargs):
        self._record("move_absolute", *args, **kwargs)
        self._apply_move(args[0], "_abs")

    def move_relative(self, *args, **kwargs):
        self._record("core_move_relative_fallback", *args, **kwargs)
        self._apply_move(args[0], "_rel")

    def zero_axes(self, *args, **kwargs):
        self._record("zero_axes", *args, **kwargs)

    def unzero_axes(self, *args, **kwargs):
        self._record("unzero_axes", *args, **kwargs)

    # --- settings (record-only) ---
    def state_request_handler(self, *args, **kwargs):
        self._record("state_request_handler", *args, **kwargs)

    def set_filter(self, *args, **kwargs):
        self._record("set_filter", *args, **kwargs)

    def set_zoom(self, *args, **kwargs):
        self._record("set_zoom", *args, **kwargs)

    def set_laser(self, *args, **kwargs):
        self._record("set_laser", *args, **kwargs)

    def set_intensity(self, *args, **kwargs):
        self._record("set_intensity", *args, **kwargs)

    def set_shutterconfig(self, *args, **kwargs):
        self._record("set_shutterconfig", *args, **kwargs)

    def open_shutters(self, *args, **kwargs):
        self._record("open_shutters", *args, **kwargs)

    def close_shutters(self, *args, **kwargs):
        self._record("close_shutters", *args, **kwargs)

    def set_state(self, *args, **kwargs):
        self._record("set_state", *args, **kwargs)
        if args:
            self.state["state"] = args[0]

    # --- activity (record-only) ---
    def start(self, *args, **kwargs):
        self._record("start", *args, **kwargs)
        # Production's synchronous start() returns only after it has left the run state. The
        # completion signal is deliberately omitted so transport tests can inspect the WAIT reply.
        self.state["state"] = "idle"

    def preview_acquisition(self, *args, **kwargs):
        self._record("preview_acquisition", *args, **kwargs)

    def stop(self, *args, **kwargs):
        self._record("stop", *args, **kwargs)
        self.state["state"] = "idle"

    def run_time_lapse(self, *args, **kwargs):
        self.timelapse_active = True
        self._record("run_time_lapse", *args, **kwargs)

    def stop_time_lapse(self, *args, **kwargs):
        self.timelapse_active = False
        self._record("stop_time_lapse", *args, **kwargs)

    # These reads record their Core call and return the value required by the command contract.
    def get_free_disk_space(self, *args, **kwargs):
        self._record("get_free_disk_space", *args, **kwargs)
        return 1_000_000

    def get_required_disk_space(self, *args, **kwargs):
        self._record("get_required_disk_space", *args, **kwargs)
        return 500_000

    def check_motion_limits(self, *args, **kwargs):
        self._record("check_motion_limits", *args, **kwargs)
        return []

    # --- signals: created lazily, recording under the bare name and driving connected slots ---
    def __getattr__(self, name):
        if name.startswith("sig_"):
            sig = _Sig(self, name)
            object.__setattr__(self, name, sig)
            return sig
        raise AttributeError(name)
