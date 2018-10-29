from .Camera import Camera
import numpy as np

class EmulatedCamera(Camera):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.live_image_count = 0

    def set_state(self, requested_state):
        return
    def open(self):
        return
    def close(self):
        return
    def stop(self):
        return
    def set_camera_exposure_time(self, time):
        return
    def set_camera_line_interval(self, time):
        return
    def prepare_image_series(self, acq):
        return
    def add_images_to_series(self):
        for i in range(10):
            image = self.__create_demo_image(10.0)
            self.sig_camera_frame.emit(image)

    def end_image_series(self):
        return
    def snap_image(self):
        return
    def prepare_live(self):
        return

    def get_live_image(self):
        for i in range(10):
            self.sig_camera_frame.emit(np.random.rand(1024,1024))
            self.live_image_count += 1
            self.sig_camera_status.emit(str(self.live_image_count))

    def end_live(self):
        return