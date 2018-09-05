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
from .devices.filter_wheels.ludlcontrol import LudlFilterwheel
from .devices.zoom.mesoSPIM_Zoom import Dynamixel_Zoom
# from .mesoSPIM_State import mesoSPIM_State

class mesoSPIM_Serial(QtCore.QObject):
    '''This class handles mesoSPIM serial connections'''
    sig_finished = QtCore.pyqtSignal()

    sig_state_updated = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent
        self.cfg = parent.cfg

        ''' Handling of state changing requests '''
        self.parent.sig_state_request.connect(lambda dict: self.state_request_handler(dict, wait_until_done=False))
        self.parent.sig_state_request_and_wait_until_done.connect(lambda dict: self.state_request_handler(dict, wait_until_done=True), type=3)

        ''' Attaching the filterwheel '''
        if self.cfg.filterwheel_parameters['filterwheel_type'] == 'Ludl':
            self.filterwheel = LudlFilterwheel(self.cfg.filterwheel_parameters['COMport'],self.cfg.filterdict)

        ''' Attaching the zoom '''
        if self.cfg.zoom_parameters['zoom_type'] == 'Dynamixel':
            self.zoom = Dynamixel_Zoom(self.cfg.zoomdict,self.cfg.zoom_parameters['COMport'],self.cfg.zoom_parameters['servo_id'])


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


    def set_state_parameter(self, key, value):
        '''
        Sets the state of the parent (in most cases, mesoSPIM_MainWindow)

        In order to do this, a QMutexLocker has to be acquired

        Args:
            key (str): State dict key
            value (str, float, int): Value to set
        '''
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                self.parent.state[key]=value
            else:
                print('Set state parameters failed: Key ', key, 'not in state dictionary!')
        self.sig_state_updated.emit()

    def set_filter(self, filter, wait_until_done=False):
        if wait_until_done:
            self.filterwheel.set_filter(filter, wait_until_done=True)
        else:
            self.filterwheel.set_filter(filter, wait_until_done=False)
        self.set_state_parameter('filter',filter)

    def set_zoom(self, zoom, wait_until_done=False):
        if wait_until_done:
            self.zoom.set_zoom(zoom, wait_until_done=True)
        else:
            self.zoom.set_zoom(zoom, wait_until_done=False)
        self.set_state_parameter('zoom',zoom)
