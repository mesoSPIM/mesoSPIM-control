'''
mesoSPIM TileViewWindows
'''
import sys
import numpy as np
import logging
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QBrush, QPen
from PyQt5.QtCore import Qt
from PyQt5.uic import loadUi
#import pyqtgraph as pg
from .mesoSPIM_State import mesoSPIM_StateSingleton

logger = logging.getLogger(__name__)

class mesoSPIM_TileViewWindow(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent # the mesoSPIM_MainWindow() instance
        self.acquisition_manager_window = parent.acquisition_manager_window
        self.cfg = parent.cfg
        self.state = mesoSPIM_StateSingleton()

        '''Set up the UI'''
        if __name__ == '__main__':
            loadUi('../gui/mesoSPIM_Tile_Overview.ui', self)
        else:
            loadUi(self.parent.package_directory + '/gui/mesoSPIM_Tile_Overview.ui', self)
        self.setWindowTitle('mesoSPIM-Control: Tile View Window')

        ''' This is flipped to account for image rotation '''
        self.y_image_width = self.cfg.camera_parameters['x_pixels']
        self.x_image_width = self.cfg.camera_parameters['y_pixels']
        self.subsampling = self.cfg.startup['camera_display_live_subsampling']
        self.scene = QGraphicsScene()
        self.tile_overview.setScene(self.scene)
        self.show_tiles()
        # update the tiles every second
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.show_tiles)
        self.timer.start(1000)  # 1000 milliseconds = 1 second

    def show_tiles(self):
        self.scene.clear()
        self.pixel_size = self.cfg.pixelsize[self.state['zoom']]
        tile_size_x, tile_size_y = self.x_image_width * self.pixel_size, self.y_image_width * self.pixel_size
        scale_factor = 0.01
        # Optional: Set brush and pen to color the rectangle
        #brush = QBrush(Qt.green)
        pen_default = QPen(Qt.white);  pen_default.setWidth(2)
        pen_selected = QPen(Qt.yellow);  pen_selected.setWidth(2)
        #tile.setBrush(brush)
        acq_list = self.state['acq_list']
        selected_row = self.acquisition_manager_window.get_first_selected_row()
        start_points_xy_list = []
        for ind, acq in enumerate(acq_list):
            start_point_x, start_point_y = acq.get_startpoint()['x_abs'], acq.get_startpoint()['y_abs']
            if (start_point_x, start_point_y) not in start_points_xy_list: # remove duplicates
                start_points_xy_list.append((start_point_x, start_point_y))
                rect = QRectF(start_point_x*scale_factor, start_point_y*scale_factor, tile_size_x*scale_factor, tile_size_y*scale_factor)
                tile = QGraphicsRectItem(rect)
                if ind == selected_row:
                    tile.setPen(pen_selected)
                else:
                    tile.setPen(pen_default)
                self.scene.addItem(tile)

        # plot selected tile on top
        if selected_row is not None:
            acq = acq_list[selected_row]
            start_point_x, start_point_y = acq.get_startpoint()['x_abs'], acq.get_startpoint()['y_abs']
            rect = QRectF(start_point_x*scale_factor, start_point_y*scale_factor, tile_size_x*scale_factor, tile_size_y*scale_factor)
            tile = QGraphicsRectItem(rect)
            tile.setPen(pen_selected)
            self.scene.addItem(tile)
