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
    sig_scale_changed = QtCore.pyqtSignal(float)

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
        self.scale_factor = 0.01
        if 'flip_XYZFT_button_polarity' in self.cfg.ui_options.keys():
            self.x_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][0] else 1
            self.y_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][1] else 1
        else:
            logger.warning('flip_XYZFT_button_polarity key not found in config file. Assuming all buttons are positive.')

        self.scene = QGraphicsScene()
        self.tile_overview.setScene(self.scene)
        self.show_tiles()
        # update the tiles every second
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.show_tiles)
        self.timer.start(1000)  # 1000 milliseconds = 1 second

        self.doubleSpinBox_scale.valueChanged.connect(lambda: self.on_scale_changed(self.doubleSpinBox_scale.value()))

    def on_scale_changed(self, value=0.01):
        self.scale_factor = value
        self.show_tiles()

    def show_tiles(self):
        self.scene.clear()
        self.pixel_size = self.cfg.pixelsize[self.state['zoom']]
        self.tile_size_x, self.tile_size_y = self.x_image_width * self.pixel_size, self.y_image_width * self.pixel_size
        # Optional: Set brush and pen to color the rectangle
        #brush = QBrush(Qt.green)
        pen_default = QPen(Qt.white);  pen_default.setWidth(2)
        pen_selected = QPen(Qt.yellow);  pen_selected.setWidth(3)
        #tile.setBrush(brush)
        acq_list = self.state['acq_list']
        selected_row = self.acquisition_manager_window.get_first_selected_row()
        start_points_xy_list = []
        global_offset_x, global_offset_y = acq_list[0].get_startpoint()['x_abs'], acq_list[0].get_startpoint()['y_abs']
        for ind, acq in enumerate(acq_list):
            start_point_x, start_point_y = acq.get_startpoint()['x_abs'] - global_offset_x, acq.get_startpoint()['y_abs'] - global_offset_y
            if (start_point_x, start_point_y) not in start_points_xy_list: # remove duplicates
                start_points_xy_list.append((start_point_x, start_point_y))
                rect = QRectF(self.x_sign*start_point_x*self.scale_factor, self.y_sign*start_point_y*self.scale_factor, self.tile_size_x*self.scale_factor, self.tile_size_y*self.scale_factor)
                tile = QGraphicsRectItem(rect)
                tile.setPen(pen_default)
                self.scene.addItem(tile)

        # plot selected tile on top in yellow
        if selected_row is not None:
            acq = acq_list[selected_row]
            start_point_x, start_point_y = acq.get_startpoint()['x_abs'] - global_offset_x, acq.get_startpoint()['y_abs'] - global_offset_y
            rect = QRectF(self.x_sign*start_point_x*self.scale_factor, self.y_sign*start_point_y*self.scale_factor, self.tile_size_x*self.scale_factor, self.tile_size_y*self.scale_factor)
            tile = QGraphicsRectItem(rect)
            tile.setPen(pen_selected)
            label = QtWidgets.QGraphicsTextItem("Selected tile")
            label.setDefaultTextColor(Qt.yellow)
            label.setPos(rect.topLeft())
            self.scene.addItem(label)
            self.scene.addItem(tile)

        self.show_current_FOV(global_offset_x, global_offset_y)

    def show_current_FOV(self, global_offset_x, global_offset_y):
        start_point_x, start_point_y = self.state['position']['x_pos'] - global_offset_x, self.state['position']['y_pos'] - global_offset_y
        rect = QRectF(self.x_sign*start_point_x*self.scale_factor, self.y_sign*start_point_y*self.scale_factor, self.tile_size_x*self.scale_factor, self.tile_size_y*self.scale_factor)
        label = QtWidgets.QGraphicsTextItem("Current FOV")
        label.setDefaultTextColor(Qt.white)
        label.setPos(rect.topLeft())
        self.scene.addItem(label)

        pen_current_FOV = QPen(Qt.white);  pen_current_FOV.setWidth(2); pen_current_FOV.setStyle(Qt.DotLine)
        tile = QGraphicsRectItem(rect)
        tile.setPen(pen_current_FOV)
        self.scene.addItem(tile)
