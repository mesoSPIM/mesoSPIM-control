'''
Serial thread for the mesoSPIM project
======================================

This thread handles all connections with serial devices such as stages,
filter wheels, zoom systems etc.
'''

import numpy as np
import time

'''PyQt5 Imports'''
from PyQt5 import QtWidgets, QtCore, QtGui

''' Import mesoSPIM modules '''
from .mesoSPIM_State import mesoSPIM_StateSingleton

from .devices.filter_wheels.ludlcontrol import LudlFilterwheel
from .devices.zoom.mesoSPIM_Zoom import Dynamixel_Zoom
from .mesoSPIM_Stages import mesoSPIM_PIstage, mesoSPIM_DemoStage
# from .mesoSPIM_State import mesoSPIM_State

class mesoSPIM_Serial(QtCore.QObject):
    '''This class handles mesoSPIM serial connections'''
    sig_finished = QtCore.pyqtSignal()

    sig_state_request = QtCore.pyqtSignal(dict)
    
    sig_position = QtCore.pyqtSignal(dict)

    sig_zero_axes = QtCore.pyqtSignal(list)
    sig_unzero_axes = QtCore.pyqtSignal(list)
    sig_stop_movement = QtCore.pyqtSignal()
    sig_load_sample = QtCore.pyqtSignal()
    sig_unload_sample = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        ''' Handling of state changing requests '''
        self.parent.sig_state_request.connect(lambda dict: self.state_request_handler(dict, wait_until_done=False))
        self.parent.sig_state_request_and_wait_until_done.connect(lambda dict: self.state_request_handler(dict, wait_until_done=True), type=3)

        ''' Attaching the filterwheel '''
        if self.cfg.filterwheel_parameters['filterwheel_type'] == 'Ludl':
            self.filterwheel = LudlFilterwheel(self.cfg.filterwheel_parameters['COMport'],self.cfg.filterdict)

        ''' Attaching the zoom '''
        if self.cfg.zoom_parameters['zoom_type'] == 'Dynamixel':
            self.zoom = Dynamixel_Zoom(self.cfg.zoomdict,self.cfg.zoom_parameters['COMport'],self.cfg.zoom_parameters['servo_id'])

        ''' Attaching the stage '''
        if self.cfg.stage_parameters['stage_type'] == 'PI':
            self.stage = mesoSPIM_PIstage(self)
            self.stage.sig_position.connect(lambda dict: self.sig_position.emit({'position': dict}))
        elif self.cfg.stage_parameters['stage_type'] == 'DemoStage':
            self.stage = mesoSPIM_DemoStage(self)
            self.stage.sig_position.connect(lambda dict: self.sig_position.emit({'position': dict}))

        ''' Wiring signals through to child objects '''
        self.parent.sig_move_relative.connect(lambda dict: self.move_relative(dict))
        self.parent.sig_move_relative_and_wait_until_done.connect(lambda dict: self.move_relative(dict, wait_until_done=True), type=3)

        self.parent.sig_move_absolute.connect(lambda dict: self.move_absolute(dict))
        self.parent.sig_move_absolute_and_wait_until_done.connect(lambda dict: self.move_absolute(dict, wait_until_done=True), type=3)

        self.parent.sig_zero_axes.connect(lambda list: self.sig_zero_axes.emit(list))
        self.parent.sig_unzero_axes.connect(lambda list: self.sig_unzero_axes.emit(list))
        self.parent.sig_stop_movement.connect(lambda: self.sig_stop_movement.emit())
        self.parent.sig_load_sample.connect(self.sig_load_sample.emit)
        self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit)

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict, wait_until_done=False):
        for key, value in zip(dict.keys(),dict.values()):
            print('Serial thread: state request: Key: ', key, ' Value: ', value)
            '''
            Here, the request handling is done with lots if 'ifs'
            '''
            print('Key: ', key, ' Value: ', value)
            if key == 'filter':
                if wait_until_done:
                    self.set_filter(value, wait_until_done)
                else:
                    self.set_filter(value)
            if key == 'zoom':
                if wait_until_done:
                    self.set_zoom(value, wait_until_done)
                else:
                    self.set_zoom(value)

    def move_relative(self, dict, wait_until_done=False):
        if wait_until_done:
            self.stage.move_relative(dict, wait_until_done=True)
        else:
            self.stage.move_relative(dict)

    def move_absolute(self, dict, wait_until_done=False):
        if wait_until_done:
            self.stage.move_absolute(dict, wait_until_done=True)
        else:
            self.stage.move_absolute(dict)

    def set_filter(self, filter, wait_until_done=False):
        if wait_until_done:
            self.filterwheel.set_filter(filter, wait_until_done=True)
        else:
            self.filterwheel.set_filter(filter, wait_until_done=False)
        self.state['filter'] = filter

    def set_zoom(self, zoom, wait_until_done=False):
        if wait_until_done:
            self.zoom.set_zoom(zoom, wait_until_done=True)
        else:
            self.zoom.set_zoom(zoom, wait_until_done=False)
        self.state['zoom'] = zoom
        self.state['pixelsize'] = self.cfg.pixelsize[zoom]