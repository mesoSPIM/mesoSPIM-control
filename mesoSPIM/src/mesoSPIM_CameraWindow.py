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
pg.setConfigOptions(imageAxisOrder='row-major')
pg.setConfigOptions(foreground='k')
pg.setConfigOptions(background='w')

class mesoSPIM_CameraWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__()

        '''Set up the UI'''
        if __name__ == '__main__':
            loadUi('../gui/mesoSPIM_CameraWindow.ui', self)
        else:
            loadUi('gui/mesoSPIM_CameraWindow.ui', self)
        self.setWindowTitle('mesoSPIM-Control: Camera Window')

        self.parent = parent
        self.cfg = parent.cfg



        ''' Set histogram Range '''
        self.graphicsView.setLevels(100,4000)

        self.imageItem = self.graphicsView.getImageItem()

        self.histogram = self.graphicsView.getHistogramWidget()
        self.histogram.setMinimumWidth(250)
        self.histogram.item.vb.setMaximumWidth(250)

        ''' This is flipped to account for image rotation '''
        self.y_image_width = self.cfg.camera_parameters['x_pixels']
        self.x_image_width = self.cfg.camera_parameters['y_pixels']
        ''' Debugging info

        logger.info('x_image_width: '+str(self.x_image_width))
        logger.info('y_image_width: '+str(self.y_image_width))
        logger.info('x_image_width/2: '+str(self.x_image_width/2))
        logger.info('y_image_width/2: '+str(self.y_image_width/2))
        '''

        ''' Initialize crosshairs '''
        self.crosspen = pg.mkPen({'color': "r", 'width': 1})
        self.vLine = pg.InfiniteLine(pos=self.x_image_width/2, angle=90, movable=False, pen=self.crosspen)
        self.hLine = pg.InfiniteLine(pos=self.y_image_width/2, angle=0, movable=False, pen=self.crosspen)
        self.graphicsView.addItem(self.vLine, ignoreBounds=True)
        self.graphicsView.addItem(self.hLine, ignoreBounds=True)
        # print(self.vLine.getXPos())
        # print(self.hLine.getYPos())

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))


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