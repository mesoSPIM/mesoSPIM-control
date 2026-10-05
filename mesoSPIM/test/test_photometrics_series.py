"""
Photometrics image-series draining, against a fake PyVCAM camera (no camera or PVCAM needed).

Regression for the 2026-10-01 continuous-mode hang: poll_frame() waited forever for a frame
that never came, so the camera thread never closed the series and the writer never finished.
"""
import collections
import types
import numpy as np
from PyQt5 import QtCore

from mesoSPIM.src.mesoSPIM_Camera import mesoSPIM_PhotometricsCamera, mesoSPIM_Camera


class FakePVCam:
    def __init__(self, n_buffered=0):
        self.buffer = collections.deque()
        self.counter = 0
        self.started_with = None
        self.timeouts = []
        for _ in range(n_buffered):
            self.capture()

    def capture(self):
        self.counter += 1
        self.buffer.append(self.counter)

    fail_above = None  # frames; mimic a start_live() that rejects large buffers

    def start_live(self, buffer_frame_count=16):  # PyVCAM 2.1.6: no reset_frame_counter
        if self.fail_above is not None and buffer_frame_count > self.fail_above:
            raise RuntimeError('pl_exp_setup_cont failed')
        self.started_with = buffer_frame_count

    def poll_frame(self, timeout_ms=-1, oldestFrame=True, copyData=True):
        self.timeouts.append(timeout_ms)
        if not self.buffer:
            raise RuntimeError('Frame timeout')  # what PyVCAM does when timeout_ms expires
        n = self.buffer.popleft()
        return {'pixel_data': np.full((4, 4), n, np.uint16)}, 12.0, n  # PyVCAM stamps each frame at capture


def make_camera(fake, **camera_parameters):
    cam = mesoSPIM_PhotometricsCamera.__new__(mesoSPIM_PhotometricsCamera)
    cam.pvcam = fake
    cam.camera_exposure_time = 0.01
    cam.x_pixels, cam.y_pixels = 2960, 5056  # Iris 15: 29.9 MB per frame
    cam.cfg = types.SimpleNamespace(camera_parameters=camera_parameters)
    return cam


def test_times_out_instead_of_blocking_forever():
    fake = FakePVCam(n_buffered=0)
    cam = make_camera(fake)
    cam.initialize_image_series()
    assert cam.get_images_in_series() == []
    assert fake.timeouts == [cam.SERIES_POLL_TIMEOUT_MS]


def test_drains_the_whole_backlog_in_one_call():
    fake = FakePVCam(n_buffered=5)
    cam = make_camera(fake)
    cam.initialize_image_series()
    images = cam.get_images_in_series()
    assert [int(i[0, 0]) for i in images] == [1, 2, 3, 4, 5]  # oldest first, none skipped
    assert fake.timeouts[0] == cam.SERIES_POLL_TIMEOUT_MS and set(fake.timeouts[1:]) == {1}
    assert cam.max_frame_count == 5


def test_frame_count_is_per_series_when_pyvcam_never_resets_it():
    fake = FakePVCam(n_buffered=0)
    fake.counter = 100  # frames from earlier stacks: PyVCAM < 2.2 keeps counting
    for _ in range(3):
        fake.capture()
    cam = make_camera(fake)
    cam.initialize_image_series()
    cam.get_images_in_series()
    assert cam.max_frame_count == 3


def test_one_call_is_bounded():
    fake = FakePVCam(n_buffered=40)
    cam = make_camera(fake)
    cam.initialize_image_series()
    assert len(cam.get_images_in_series()) == cam.SERIES_MAX_FRAMES_PER_CALL


def test_circular_buffer_size_comes_from_the_config():
    fake = FakePVCam()
    make_camera(fake).initialize_image_series()
    assert fake.started_with == 16
    make_camera(fake, series_buffer_frames=64).initialize_image_series()
    assert fake.started_with == 64


def test_circular_buffer_is_capped_below_2_GiB():
    fake = FakePVCam()
    make_camera(fake, series_buffer_frames=100).initialize_image_series()  # 3 GB failed on the rig
    assert fake.started_with == 71 and 71 * 2960 * 5056 * 2 < 2**31


def test_falls_back_to_16_frames_if_the_buffer_is_refused():
    fake = FakePVCam()
    fake.fail_above = 32
    make_camera(fake, series_buffer_frames=64).initialize_image_series()
    assert fake.started_with == 16


class _Sig:
    def __init__(self):
        self.n = 0

    def emit(self, *a):
        self.n += 1


def make_worker(images_per_call):
    w = mesoSPIM_Camera.__new__(mesoSPIM_Camera)
    QtCore.QObject.__init__(w)  # skip __init__: it needs a full Core parent
    calls = iter(images_per_call)
    w.camera = types.SimpleNamespace(get_images_in_series=lambda: next(calls))
    w.stopflag, w.cur_image, w.max_frame = False, 0, 5
    w.processor_chain = types.SimpleNamespace(is_enabled=False)
    w.frame_queue, w.frame_queue_display = collections.deque(), collections.deque(maxlen=1)
    w.camera_display_temporal_subsampling = 2
    w.sig_camera_frame, w.sig_write_images = _Sig(), _Sig()
    return w


def test_worker_ignores_an_empty_drain_and_never_overfills():
    img = lambda: np.zeros((4, 4), np.uint16)
    w = make_worker([[], [img(), img(), img()], [img(), img(), img()]])
    add = mesoSPIM_Camera.add_images_to_series.__wrapped__.__wrapped__ if hasattr(
        mesoSPIM_Camera.add_images_to_series, '__wrapped__') else mesoSPIM_Camera.add_images_to_series
    for _ in range(3):
        add(w, None, None)
    assert w.cur_image == 5 and len(w.frame_queue) == 5   # 3 + 2: capped at max_frame
    assert w.sig_write_images.n == 2                       # the empty drain wrote nothing


def test_identity_conversion_of_uint16_is_free_and_exact():
    from mesoSPIM.src.plugins.utils import count_domain_to_uint16
    img = np.random.default_rng(0).integers(0, 65536, (64, 64), dtype=np.uint16)
    assert count_domain_to_uint16(img) is img  # no 53 ms float round trip per camera frame
    ints = np.array([-5, 0, 70000, 300], dtype=np.int32)
    assert count_domain_to_uint16(ints).tolist() == [0, 0, 65535, 300]
    floats = np.array([np.nan, -1.0, 2.6, 1e9])
    assert count_domain_to_uint16(floats).tolist() == [0, 0, 3, 65535]


def test_drain_counter_advances_even_when_the_drain_fails():
    w = make_worker([])  # get_images_in_series raises StopIteration: a failing camera call
    w.drain_requests_done = 0
    try:
        mesoSPIM_Camera.add_images_to_series(w, None, None)
    except Exception:
        pass
    assert w.drain_requests_done == 1  # the Core must never wait on a request that died
