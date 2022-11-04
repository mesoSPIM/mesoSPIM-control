import sys
import pyqtgraph as pg
import numpy as np
import matplotlib
from PyQt5 import QtWidgets, QtCore
from PyQt5.uic import loadUi
import logging
logger = logging.getLogger(__name__)


class mesoSPIM_ContrastWindow(QtWidgets.QWidget):

    def __init__(self, parent=None):
        '''Parent can be a mesoSPIM_MainWindow() object'''
        super().__init__()
        self.parent = parent
        self.active = True
        self.image_view = pg.ImageView()
        cmap = pg.colormap.get('jet', source='matplotlib')
        self.image_view.setColorMap(cmap)
        self.setWindowTitle("Contrast map")
        layout = pg.QtGui.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.image_view)
        self.resize(900, 900)
        self.show()

    def _contrast(self, roi):
        """Compute the contrast value, (max-min)/(max+min), from the image roi"""
        mini = np.percentile(roi, 1)
        maxi = np.percentile(roi, 99)
        contrast = (maxi - mini) / (maxi + mini)
        return contrast

    @QtCore.pyqtSlot(np.ndarray)
    def set_image(self, image):
        if self.active: # do updates only if widget window is active (visible), to minimize overhead.
            roi_h = roi_w = 128 # px, roi size
            N_ROIs_H, N_ROIs_W = int(np.ceil(image.shape[0] / roi_h)), int(np.ceil(image.shape[1] / roi_w))
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
