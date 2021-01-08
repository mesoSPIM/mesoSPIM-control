'''
mesoSPIM CameraWindow

'''
import sys
import numpy as np

import logging
logger = logging.getLogger(__name__)

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi
import pyqtgraph as pg
from .mesoSPIM_State import mesoSPIM_StateSingleton

class mesoSPIM_CameraWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent
        self.cfg = parent.cfg
        self.state = mesoSPIM_StateSingleton()

        ''' Change the PyQtGraph-Options in White Mode'''
        pg.setConfigOptions(imageAxisOrder='row-major')
        if not self.cfg.ui_options['dark_mode']:
            pg.setConfigOptions(foreground='k')
            pg.setConfigOptions(background='w')
        else:
            '''Set background to #19232D'''
            background_color = pg.mkColor('#19232D')
            pg.setConfigOptions(background=background_color)
            pg.setConfigOptions(foreground='w')

        '''Set up the UI'''
        if __name__ == '__main__':
            loadUi('../gui/mesoSPIM_CameraWindow.ui', self)
        else:
            loadUi('gui/mesoSPIM_CameraWindow.ui', self)
        self.setWindowTitle('mesoSPIM-Control: Camera Window')

        ''' Set histogram Range '''
        self.graphicsView.setLevels(100,4000)

        self.imageItem = self.graphicsView.getImageItem()

        self.histogram = self.graphicsView.getHistogramWidget()
        self.histogram.setMinimumWidth(250)
        self.histogram.item.vb.setMaximumWidth(250)

        ''' This is flipped to account for image rotation '''
        self.y_image_width = self.cfg.camera_parameters['x_pixels']
        self.x_image_width = self.cfg.camera_parameters['y_pixels']

        ''' Initialize crosshairs '''
        self.crosspen = pg.mkPen({'color': "r", 'width': 1})
        self.vLine = pg.InfiniteLine(pos=self.x_image_width/2, angle=90, movable=False, pen=self.crosspen)
        self.hLine = pg.InfiniteLine(pos=self.y_image_width/2, angle=0, movable=False, pen=self.crosspen)
        self.graphicsView.addItem(self.vLine, ignoreBounds=True)
        self.graphicsView.addItem(self.hLine, ignoreBounds=True)

        # Create overlay ROIs
        self.roi_box = pg.RectROI((self.x_image_width//2 - 50, self.y_image_width//2 - 50), (100, 100))
        self.roi_box_w_text, self.roi_box_h_text = pg.TextItem(color='r'), pg.TextItem(color='r', angle=90)
        self.roi_list = [self.roi_box, self.roi_box_w_text, self.roi_box_h_text]

        # Set up CameraWindow signals
        self.adjustLevelsButton.clicked.connect(self.graphicsView.autoLevels)
        self.overlayCombo.currentTextChanged.connect(self.change_overlay)
        self.roi_box.sigRegionChangeFinished.connect(self.update_box_roi_labels)

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

    def px2um(self, px):
        '''Unit converter'''
        return px * self.cfg.pixelsize[self.state['zoom']]

    @QtCore.pyqtSlot(str)
    def change_overlay(self, overlay_name):
        ''''Changes the image overlay'''
        if overlay_name == 'Box roi':
            self.update_box_roi_labels()
            for item in self.roi_list:
                self.graphicsView.addItem(item)
        elif overlay_name == 'Overlay: none':
            for item in self.roi_list:
                self.graphicsView.removeItem(item)

    @QtCore.pyqtSlot()
    def update_box_roi_labels(self):
        w, h = self.roi_box.size()
        x, y = self.roi_box.pos()
        self.roi_box_w_text.setText(f"{int(self.px2um(w)):,} \u03BCm")
        self.roi_box_h_text.setText(f"{int(self.px2um(h)):,} \u03BCm")
        self.roi_box_w_text.setPos(x, y + h)
        self.roi_box_h_text.setPos(x, y + h)

    @QtCore.pyqtSlot(str)
    def display_status_message(self, string, time=0):
        '''
        Displays a message in the status bar for a time in ms

        If time=0, the message will stay.
        '''
        if time == 0:
            self.statusBar().showMessage(string)
        else:
            self.statusBar().showMessage(string, time)

    def draw_crosshairs(self):
        self.graphicsView.addItem(self.vLine, ignoreBounds=True)
        self.graphicsView.addItem(self.hLine, ignoreBounds=True)

    @QtCore.pyqtSlot(np.ndarray)
    def set_image(self, image):
        self.graphicsView.setImage(image, autoLevels=False, autoHistogramRange=False, autoRange=False)
        if image.shape[0] != self.y_image_width or image.shape[1] != self.x_image_width:
            self.x_image_width = image.shape[1]
            self.y_image_width = image.shape[0]
            self.vLine.setPos(self.x_image_width/2) # Stating a single value works for orthogonal lines
            self.hLine.setPos(self.y_image_width/2) # Stating a single value works for orthogonal lines
            self.graphicsView.addItem(self.vLine, ignoreBounds=True)
            self.graphicsView.addItem(self.hLine, ignoreBounds=True)
            ''' Debugging info
            
            logger.info('x_image_width: '+str(self.x_image_width))
            logger.info('y_image_width: '+str(self.y_image_width))
            logger.info('x_image_width/2: '+str(self.x_image_width/2))
            logger.info('y_image_width/2: '+str(self.y_image_width/2))
            '''
        else:
            self.draw_crosshairs()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    camera_window = mesoSPIM_CameraWindow()
    camera_window.show()

    sys.exit(app.exec_())
