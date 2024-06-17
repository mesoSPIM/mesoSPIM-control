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
        self.setWindowTitle('mesoSPIM-Control: Tile Overview Window')

        ''' This is flipped to account for image rotation '''
        self.y_image_width = self.cfg.camera_parameters['x_pixels']
        self.x_image_width = self.cfg.camera_parameters['y_pixels']
        self.subsampling = self.cfg.startup['camera_display_live_subsampling']
        self.scale_factor = 0.01
        if 'flip_XYZFT_button_polarity' in self.cfg.ui_options.keys():
            self.x_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][0] else 1
            self.y_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][1] else 1
        else:
            self.x_sign = self.y_sign = 1
            msg = "'flip_XYZFT_button_polarity' key not found in config file. Assuming all buttons are positive."; logger.warning(msg); print(msg)

        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-300, -400, 600, 800)
        self.tile_overview.setScene(self.scene)
        self.show_tiles()
        # update the tiles every second
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.show_tiles)
        self.timer.start(500)  # milliseconds

        self.doubleSpinBox_scale.valueChanged.connect(lambda: self.on_scale_changed(self.doubleSpinBox_scale.value()))

    def on_scale_changed(self, value=0.01):
        self.scale_factor = value
        self.show_tiles()

    def show_tiles(self):
        self.scene.clear()
        self.pixel_size = self.cfg.pixelsize[self.state['zoom']]
        self.tile_size_x, self.tile_size_y = self.x_image_width * self.pixel_size, self.y_image_width * self.pixel_size
        self.fov_scene_offset_x = self.tile_size_x / 2 * self.scale_factor # offset of the FOV in the scene coordinates
        self.fov_scene_offset_y = self.tile_size_y / 2 * self.scale_factor
        self.show_current_FOV()
        global_offset_x, global_offset_y = self.state['position']['x_pos'], self.state['position']['y_pos'] # offset of the FOV in global (stage) coordinates
        # Optional: Set brush and pen to color the rectangle
        #brush = QBrush(Qt.green)
        pen_default = QPen(Qt.white);  pen_default.setWidth(2)
        pen_selected = QPen(Qt.yellow);  pen_selected.setWidth(3)
        #tile.setBrush(brush)
        acq_list = self.state['acq_list']
        selected_row = self.acquisition_manager_window.get_first_selected_row()
        start_points_xy_list = []
        for ind, acq in enumerate(acq_list):
            start_point_x, start_point_y = acq.get_startpoint()['x_abs'] - global_offset_x, acq.get_startpoint()['y_abs'] - global_offset_y
            if (start_point_x, start_point_y) not in start_points_xy_list: # remove duplicates
                start_points_xy_list.append((start_point_x, start_point_y))
                rect = QRectF(self.x_sign*start_point_x*self.scale_factor - self.fov_scene_offset_x, 
                              self.y_sign*start_point_y*self.scale_factor - self.fov_scene_offset_y, 
                              self.tile_size_x*self.scale_factor, 
                              self.tile_size_y*self.scale_factor)
                tile = QGraphicsRectItem(rect)
                tile.setPen(pen_default)
                label = QtWidgets.QGraphicsTextItem("tile")
                label.setDefaultTextColor(Qt.white)
                label.setPos(rect.topLeft())
                self.scene.addItem(tile)
                self.scene.addItem(label)

        # plot selected tile on top in yellow
        if selected_row is not None:
            acq = acq_list[selected_row]
            start_point_x, start_point_y = acq.get_startpoint()['x_abs'] - global_offset_x, acq.get_startpoint()['y_abs'] - global_offset_y
            rect = QRectF(self.x_sign*start_point_x*self.scale_factor - self.fov_scene_offset_x, 
                          self.y_sign*start_point_y*self.scale_factor - self.fov_scene_offset_y, 
                          self.tile_size_x*self.scale_factor, 
                          self.tile_size_y*self.scale_factor)
            tile = QGraphicsRectItem(rect)
            tile.setPen(pen_selected)
            label = QtWidgets.QGraphicsTextItem("Selected")
            label.setDefaultTextColor(Qt.yellow)
            label.setPos(rect.center().x() - label.boundingRect().width() / 2, rect.center().y() - label.boundingRect().height() / 2 - rect.height() / 4)
            self.scene.addItem(label)
            self.scene.addItem(tile)

    def show_current_FOV(self):
        """Show the current FOV in the center of the scene"""	
        start_point_x, start_point_y = -self.fov_scene_offset_x, -self.fov_scene_offset_y
        rect = QRectF(start_point_x, start_point_y, self.tile_size_x*self.scale_factor, self.tile_size_y*self.scale_factor)
        label = QtWidgets.QGraphicsTextItem("FOV")
        label.setDefaultTextColor(Qt.white)
        label.setPos(rect.center().x() - label.boundingRect().width() / 2, rect.center().y() - label.boundingRect().height() / 2)

        pen_current_FOV = QPen(Qt.white);  pen_current_FOV.setWidth(2); pen_current_FOV.setStyle(Qt.DotLine)
        brush = QBrush(Qt.gray)
        tile = QGraphicsRectItem(rect)
        tile.setBrush(brush)
        tile.setPen(pen_current_FOV)
        self.scene.addItem(tile)
        self.scene.addItem(label)
