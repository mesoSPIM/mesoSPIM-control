"""
Photometrics image-series draining, against a fake PyVCAM camera (no camera or PVCAM needed).

Regression for the 2026-10-01 continuous-mode hang: poll_frame() waited forever for a frame
that never came, so the camera thread never closed the series and the writer never finished.
"""
import collections
import types
import numpy as np

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

    def start_live(self, buffer_frame_count=16, reset_frame_counter=False):
        self.started_with = buffer_frame_count

    def poll_frame(self, timeout_ms=-1, oldestFrame=True, copyData=True):
        self.timeouts.append(timeout_ms)
        if not self.buffer:
            raise RuntimeError('Frame timeout')  # what PyVCAM does when timeout_ms expires
        n = self.buffer.popleft()
        return {'pixel_data': np.full((4, 4), n, np.uint16)}, 12.0, self.counter


def make_camera(fake, **camera_parameters):
    cam = mesoSPIM_PhotometricsCamera.__new__(mesoSPIM_PhotometricsCamera)
    cam.pvcam = fake
    cam.camera_exposure_time = 0.01
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


def test_one_call_is_bounded():
    fake = FakePVCam(n_buffered=40)
    cam = make_camera(fake)
    cam.initialize_image_series()
    assert len(cam.get_images_in_series()) == cam.SERIES_MAX_FRAMES_PER_CALL


def test_circular_buffer_size_comes_from_the_config():
    fake = FakePVCam()
    make_camera(fake).initialize_image_series()
    assert fake.started_with == 16
    make_camera(fake, series_buffer_frames=100).initialize_image_series()
    assert fake.started_with == 100


class _Sig:
    def __init__(self):
        self.n = 0

    def emit(self, *a):
        self.n += 1


def make_worker(images_per_call):
    w = mesoSPIM_Camera.__new__(mesoSPIM_Camera)
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
