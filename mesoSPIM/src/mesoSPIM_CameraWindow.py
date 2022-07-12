'''
mesoSPIM CameraWindow
'''
import sys
import numpy as np
from mesoSPIM.src.utils.optimization import shannon_dct

import logging
logger = logging.getLogger(__name__)

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi
import pyqtgraph as pg
from mesoSPIM.src.mesoSPIM_State import mesoSPIM_StateSingleton

class mesoSPIM_CameraWindow(QtWidgets.QWidget):
    sig_update_roi = QtCore.pyqtSignal(tuple)
    sig_update_status = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent # the mesoSPIM_MainWindow() instance
        self.cfg = parent.cfg
        self.state = mesoSPIM_StateSingleton()

        pg.setConfigOptions(imageAxisOrder='row-major')
        if (hasattr(self.cfg, 'ui_options') and self.cfg.ui_options['dark_mode']) or\
                (hasattr(self.cfg, 'dark_mode') and self.cfg.dark_mode):
            pg.setConfigOptions(background=pg.mkColor('#19232D'))  # To avoid pitch black bg for the image view
        else:
            pg.setConfigOptions(background="w")

        '''Set up the UI'''
        if __name__ == '__main__':
            loadUi('../gui/mesoSPIM_CameraWindow.ui', self)
        else:
            loadUi('gui/mesoSPIM_CameraWindow.ui', self)
        self.setWindowTitle('mesoSPIM-Control: Camera Window')

        self.status_label.setText("Status: OK")

        ''' Set histogram Range '''
        self.image_view.setLevels(100, 3000)
        self.imageItem = self.image_view.getImageItem()
        self.histogram = self.image_view.getHistogramWidget()
        self.histogram.setMinimumWidth(100)
        self.histogram.item.vb.setMaximumWidth(100)

        ''' This is flipped to account for image rotation '''
        self.y_image_width = self.cfg.camera_parameters['x_pixels']
        self.x_image_width = self.cfg.camera_parameters['y_pixels']
        self.subsampling = self.cfg.startup['camera_display_live_subsampling']

        ''' Initialize crosshairs '''
        self.crosspen = pg.mkPen({'color': "r", 'width': 1})
        self.vLine = pg.InfiniteLine(pos=self.x_image_width/2, angle=90, movable=False, pen=self.crosspen)
        self.hLine = pg.InfiniteLine(pos=self.y_image_width/2, angle=0, movable=False, pen=self.crosspen)
        self.image_view.addItem(self.vLine, ignoreBounds=True)
        self.image_view.addItem(self.hLine, ignoreBounds=True)

        # Create overlay ROIs
        self.overlay = None  # None, 'box'
        w, h = self.x_image_width//self.subsampling, self.y_image_width//self.subsampling
        self.roi_box = pg.RectROI((0, 0), (w, h), sideScalers=True)
        self.roi_drawn = False

        # Set up internal CameraWindow signals
        self.adjustLevelsButton.clicked.connect(self.adjust_levels)
        self.overlayCombo.currentTextChanged.connect(self.change_overlay)
        self.roi_box.sigRegionChangeFinished.connect(self.update_status)
        self.sig_update_status.connect(self.update_status)

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

    def adjust_levels(self, pct_low=25, pct_hi=99.99):
        ''''Adjust histogram levels'''
        img = self.image_view.getImageItem().image
        self.image_view.setLevels(min=np.percentile(img, pct_low), max=np.percentile(img, pct_hi))

    def px2um(self, px, scale=1):
        '''Unit converter'''
        return scale * px * self.cfg.pixelsize[self.state['zoom']]

    @QtCore.pyqtSlot(str)
    def change_overlay(self, overlay_name):
        w, h = self.get_image_shape()
        if overlay_name == 'Box roi':
            self.set_roi('box', (w//2 - 50, h//2 - 50, 100, 100))
        elif overlay_name == 'Overlay: none':
            self.set_roi(None, (0, 0, w, h))

    def get_roi(self):
        im_item = self.image_view.getImageItem()
        if self.overlay == 'box' and self.roi_drawn:
            roi = self.roi_box.getArrayRegion(im_item.image, im_item)
            x, y = self.roi_box.pos()
            w, h = self.roi_box.size()
            self.sig_update_roi.emit((x, y, w, h))
        else:
            roi = im_item.image
            w, h = im_item.image.shape
            self.sig_update_roi.emit((0, 0, w, h))
        return roi

    def set_roi(self, mode='box', x_y_w_h=(0, 0, 100, 100)):
        assert mode in ('box', None), f"Mode must be in ('box', None), received {mode} instead"
        self.overlay = mode
        x, y, w, h = x_y_w_h
        self.roi_box.setPos((x, y))
        self.roi_box.setSize((w, h))
        if self.overlay is None and self.roi_drawn:
            self.image_view.removeItem(self.roi_box)
            self.roi_drawn = False
        elif self.overlay == 'box' and not self.roi_drawn:
            self.image_view.addItem(self.roi_box)
            self.roi_drawn = True
        self.sig_update_status.emit()

    def get_image_shape(self):
        return self.image_view.getImageItem().image.shape

    @QtCore.pyqtSlot()
    def update_status(self):
        roi = self.get_roi()
        if self.overlay == 'box':
            w, h = self.roi_box.size()
            self.status_label.setText(f"ROI: w {int(self.px2um(w, self.subsampling)):,} \u03BCm, "
                                      f"h {int(self.px2um(h, self.subsampling)):,} \u03BCm, "
                                      f"sharpness {np.round(1e4 * shannon_dct(roi)):.0f}")
        else:
            self.status_label.setText(f"Image dimensions: {roi.shape}")

    def draw_crosshairs(self):
        self.image_view.addItem(self.vLine, ignoreBounds=True)
        self.image_view.addItem(self.hLine, ignoreBounds=True)

    @QtCore.pyqtSlot(np.ndarray)
    def set_image(self, image):
        self.image_view.setImage(image, autoLevels=False, autoHistogramRange=False, autoRange=False)
        # update roi size if subsampling has changed interactively:
        if self.overlay == 'box' and self.subsampling != self.state['camera_display_live_subsampling']:
            subsampling_ratio = self.subsampling / self.state['camera_display_live_subsampling']
            self.subsampling = self.state['camera_display_live_subsampling']
            x, y = self.roi_box.pos()
            w, h = self.roi_box.size()
            self.roi_box.setPos((x * subsampling_ratio, y * subsampling_ratio))
            self.roi_box.setSize((w * subsampling_ratio, h * subsampling_ratio))
        self.update_status()

        h, w = image.shape[-2], image.shape[-1]  # works for both 2D and 3/4D loaded TIFF files.
        if h != self.y_image_width or w != self.x_image_width:
            self.x_image_width, self.y_image_width = w, h
            self.vLine.setPos(self.x_image_width/2.), self.hLine.setPos(self.y_image_width/2.)
        self.draw_crosshairs()

