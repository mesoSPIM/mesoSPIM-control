import sys
import time
import pyqtgraph as pg
import numpy as np
import matplotlib
from PyQt5 import QtWidgets, QtCore
from PyQt5.uic import loadUi
from .utils.utility_functions import fit_window_to_screen
import logging
logger = logging.getLogger(__name__)


class mesoSPIM_ContrastWindow(QtWidgets.QWidget):

    def __init__(self, parent=None):
        '''Parent can be a mesoSPIM_MainWindow() object'''
        super().__init__()
        self.parent = parent
        self.active = True
        self._last_update = 0.0
        self.image_view = pg.ImageView()
        cmap = pg.colormap.get('jet', source='matplotlib')
        self.image_view.setColorMap(cmap)
        self.setWindowTitle("Contrast map")
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.image_view)
        self.resize(900, 900)
        fit_window_to_screen(self)
        self.show()

    def _contrast(self, roi):
        """Compute the contrast value, (max-min)/(max+min), from the image roi"""
        mini = np.percentile(roi, 1)
        maxi = np.percentile(roi, 99)
        denom = maxi + mini
        contrast = (maxi - mini) / denom if denom != 0 else 0.0
        return contrast

    @QtCore.pyqtSlot()
    def set_image(self):
        if not self.active or not self.parent.core.frame_queue_display:
            return
        now = time.monotonic()
        if now - self._last_update < 0.2:  # cap at 5 fps to keep GUI responsive
            return
        self._last_update = now
        image = self.parent.core.frame_queue_display[0]
        N_ROIs_H, N_ROIs_W = 8, 8
        roi_h = image.shape[0] // N_ROIs_H
        roi_w = image.shape[1] // N_ROIs_W
        contrast_map = np.zeros((N_ROIs_H, N_ROIs_W))
        for j in range(N_ROIs_H):
            for i in range(N_ROIs_W):
                roi = image[j * roi_h:(j + 1) * roi_h, i * roi_w:(i + 1) * roi_w]
                contrast_map[j, i] = self._contrast(roi)
        self.image_view.setImage(contrast_map, autoLevels=False, autoHistogramRange=False, autoRange=False)

    def closeEvent(self, event):
        """Override close event: window becomes hidden and inactive, but still exists and ready to pop up when called"""
        logger.info("Image contrast window closed")
        self.active = False
        event.accept() # let the window close


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = mesoSPIM_ContrastWindow()
    sys.exit(app.exec_())
