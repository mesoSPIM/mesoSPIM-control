'''
Serial thread for the mesoSPIM project
======================================

This thread handles all connections with serial devices such as stages,
filter wheels, zoom systems etc.
'''

import numpy as np
import time

import logging
logger = logging.getLogger(__name__)

'''PyQt5 Imports'''
from PyQt5 import QtWidgets, QtCore, QtGui

''' Import mesoSPIM modules '''
from .mesoSPIM_State import mesoSPIM_StateSingleton

#from .devices.filter_wheels.ludlcontrol import LudlFilterwheel
#from .devices.filter_wheels.mesoSPIM_FilterWheel import mesoSPIM_DemoFilterWheel
#from .devices.zoom.mesoSPIM_Zoom import DynamixelZoom, DemoZoom
#from .mesoSPIM_Stages import mesoSPIM_PIstage, mesoSPIM_DemoStage, mesoSPIM_GalilStages
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
    sig_mark_rotation_position = QtCore.pyqtSignal()
    
    def __init__(self, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        ''' Handling of state changing requests '''
        self.parent.sig_state_request.connect(self.report_thread_id)
        self.parent.sig_state_request.connect(lambda dict: self.state_request_handler(dict, wait_until_done=False))

        # self.parent.sig_state_request_and_wait_until_done.connect(lambda dict: self.state_request_handler(dict, wait_until_done=True), type=3)

        # ''' Attaching the filterwheel '''
        # if self.cfg.filterwheel_parameters['filterwheel_type'] == 'Ludl':
        #     self.filterwheel = LudlFilterwheel(self.cfg.filterwheel_parameters['COMport'],self.cfg.filterdict)
        # elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'DemoFilterWheel':
        #     self.filterwheel = mesoSPIM_DemoFilterWheel(self.cfg.filterdict)

        # ''' Attaching the zoom '''
        # if self.cfg.zoom_parameters['zoom_type'] == 'Dynamixel':
        #     self.zoom = DynamixelZoom(self.cfg.zoomdict,self.cfg.zoom_parameters['COMport'],self.cfg.zoom_parameters['servo_id'])
        # elif self.cfg.zoom_parameters['zoom_type'] == 'DemoZoom':
        #     self.zoom = DemoZoom(self.cfg.zoomdict)

        # ''' Attaching the stage '''
        # if self.cfg.stage_parameters['stage_type'] == 'PI':
        #     self.stage = mesoSPIM_PIstage(self)
        #     self.stage.sig_position.connect(lambda dict: self.sig_position.emit({'position': dict}))
        # elif self.cfg.stage_parameters['stage_type'] == 'GalilStage':
        #     self.stage = mesoSPIM_GalilStages(self)
        #     self.stage.sig_position.connect(lambda dict: self.sig_position.emit({'position': dict}))
        # elif self.cfg.stage_parameters['stage_type'] == 'DemoStage':
        #     self.stage = mesoSPIM_DemoStage(self)
        #     self.stage.sig_position.connect(lambda dict: self.sig_position.emit({'position': dict}))

        ''' Wiring signals through to child objects '''
        # self.parent.sig_move_relative.connect(lambda dict: self.move_relative(dict))
        # self.parent.sig_move_relative_and_wait_until_done.connect(lambda dict: self.move_relative(dict, wait_until_done=True), type=3)

        # self.parent.sig_move_absolute.connect(lambda dict: self.move_absolute(dict))
        # self.parent.sig_move_absolute_and_wait_until_done.connect(lambda dict: self.move_absolute(dict, wait_until_done=True), type=3)

        # self.parent.sig_zero_axes.connect(lambda list: self.sig_zero_axes.emit(list))
        # self.parent.sig_unzero_axes.connect(lambda list: self.sig_unzero_axes.emit(list))
        # self.parent.sig_stop_movement.connect(lambda: self.sig_stop_movement.emit())
        # self.parent.sig_load_sample.connect(self.sig_load_sample.emit)
        # self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit)

        # self.parent.sig_mark_rotation_position.connect(self.sig_mark_rotation_position.emit)
        self.parent.sig_go_to_rotation_position.connect(self.go_to_rotation_position)
        # self.parent.sig_go_to_rotation_position_and_wait_until_done.connect(lambda: self.go_to_rotation_position(wait_until_done=True), type=3)

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

    @QtCore.pyqtSlot(dict)
    def report_thread_id(self):
        logger.info('Demo Serial Thread ID: '+str(int(QtCore.QThread.currentThreadId())))

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict, wait_until_done=False):
        logger.info('Demo Serial Thread ID from request handler: '+str(int(QtCore.QThread.currentThreadId())))
        for key, value in zip(dict.keys(),dict.values()):
            # print('Serial thread: state request: Key: ', key, ' Value: ', value)
            '''
            Here, the request handling is done with lots if 'ifs'
            '''
            # print('Key: ', key, ' Value: ', value)
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
            # Log Thread ID during Live: just debugging code
            if key == 'state':
                if value == 'live':
                    logger.info('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))

    @QtCore.pyqtSlot(dict)
    def move_relative(self, dict, wait_until_done=False):
        logger.info('Thread ID during relative movement: '+str(int(QtCore.QThread.currentThreadId())))

        # logger.info('Thread ID during move rel: '+str(int(QtCore.QThread.currentThreadId())))
        # if wait_until_done:
        #     self.stage.move_relative(dict, wait_until_done=True)
        # else:
        #     self.stage.move_relative(dict)

    @QtCore.pyqtSlot(dict)
    def move_absolute(self, dict, wait_until_done=False):
        pass
        # if wait_until_done:
        #     self.stage.move_absolute(dict, wait_until_done=True)
        # else:
        #     self.stage.move_absolute(dict)

    @QtCore.pyqtSlot()
    def go_to_rotation_position(self, wait_until_done=False):
        logger.info('Thread ID during going to rotation position: '+str(int(QtCore.QThread.currentThreadId())))
        
        # if wait_until_done:
        #     self.stage.go_to_rotation_position(wait_until_done=True)
        # else:
        #     self.stage.go_to_rotation_position()

    @QtCore.pyqtSlot(str)
    def set_filter(self, filter, wait_until_done=False):
        logger.info('Thread ID during set filter: '+str(int(QtCore.QThread.currentThreadId())))
        # if wait_until_done:
        #     self.filterwheel.set_filter(filter, wait_until_done=True)
        # else:
        #     self.filterwheel.set_filter(filter, wait_until_done=False)
        self.state['filter'] = filter

    @QtCore.pyqtSlot(str)
    def set_zoom(self, zoom, wait_until_done=False):
        logger.info('Thread ID during set zoom: '+str(int(QtCore.QThread.currentThreadId())))
        # if wait_until_done:
        #     self.zoom.set_zoom(zoom, wait_until_done=True)
        # else:
        #     self.zoom.set_zoom(zoom, wait_until_done=False)
        self.state['zoom'] = zoom
        self.state['pixelsize'] = self.cfg.pixelsize[zoom]