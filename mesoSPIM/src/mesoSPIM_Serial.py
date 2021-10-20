'''
Serial thread for the mesoSPIM project
======================================

This thread handles all connections with serial devices such as stages,
filter wheels, zoom systems etc.
'''

import logging
logger = logging.getLogger(__name__)
from PyQt5 import QtCore

''' Import mesoSPIM modules '''
from .mesoSPIM_State import mesoSPIM_StateSingleton

from .devices.filter_wheels.ludlcontrol import LudlFilterwheel
from .devices.filter_wheels.sutterLambdaControl import Lambda10B
from .devices.filter_wheels.mesoSPIM_FilterWheel import mesoSPIM_DemoFilterWheel
from .devices.zoom.mesoSPIM_Zoom import DynamixelZoom, DemoZoom
from .mesoSPIM_Stages import mesoSPIM_PI_1toN, mesoSPIM_PI_NtoN, mesoSPIM_DemoStage, mesoSPIM_GalilStages, mesoSPIM_PI_f_rot_and_Galil_xyz_Stages, mesoSPIM_PI_rot_and_Galil_xyzf_Stages, mesoSPIM_PI_rotz_and_Galil_xyf_Stages, mesoSPIM_PI_rotzf_and_Galil_xy_Stages


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
        self.parent.sig_state_request.connect(self.state_request_handler)
        self.parent.sig_state_request_and_wait_until_done.connect(lambda sdict: self.state_request_handler(sdict, wait_until_done=True), type=3)

        ''' Attaching the filterwheel '''
        if self.cfg.filterwheel_parameters['filterwheel_type'] == 'Ludl':
            self.filterwheel = LudlFilterwheel(self.cfg.filterwheel_parameters['COMport'], self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'DemoFilterWheel':
            self.filterwheel = mesoSPIM_DemoFilterWheel(self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'Sutter':
            self.filterwheel = Lambda10B(self.cfg.filterwheel_parameters['COMport'], self.cfg.filterdict)

        ''' Attaching the zoom '''
        if self.cfg.zoom_parameters['zoom_type'] == 'Dynamixel':
            self.zoom = DynamixelZoom(self.cfg.zoomdict, self.cfg.zoom_parameters['COMport'], self.cfg.zoom_parameters['servo_id'], self.cfg.zomm_parameters['baudrate'])
        elif self.cfg.zoom_parameters['zoom_type'] == 'DemoZoom':
            self.zoom = DemoZoom(self.cfg.zoomdict)

        ''' Attaching the stage '''
        if self.cfg.stage_parameters['stage_type'] in {'PI', 'PI_1controllerNstages'}:
            self.stage = mesoSPIM_PI_1toN(self)
        elif self.cfg.stage_parameters['stage_type'] == 'PI_NcontrollersNstages':
            self.stage = mesoSPIM_PI_NtoN(self)
            self.stage.sig_position.connect(lambda sdict: self.sig_position.emit({'position': sdict}))
        elif self.cfg.stage_parameters['stage_type'] == 'GalilStage':
            self.stage = mesoSPIM_GalilStages(self)
            self.stage.sig_position.connect(lambda sdict: self.sig_position.emit({'position': sdict}))
        elif self.cfg.stage_parameters['stage_type'] == 'PI_rot_and_Galil_xyzf':
            self.stage = mesoSPIM_PI_rot_and_Galil_xyzf_Stages(self)
            self.stage.sig_position.connect(lambda sdict: self.sig_position.emit({'position': sdict}))
        elif self.cfg.stage_parameters['stage_type'] == 'PI_f_rot_and_Galil_xyz':
            self.stage = mesoSPIM_PI_f_rot_and_Galil_xyz_Stages(self)
            self.stage.sig_position.connect(lambda sdict: self.sig_position.emit({'position': sdict}))
        elif self.cfg.stage_parameters['stage_type'] == 'PI_rotz_and_Galil_xyf':
            self.stage = mesoSPIM_PI_rotz_and_Galil_xyf_Stages(self)
            self.stage.sig_position.connect(lambda sdict: self.sig_position.emit({'position': sdict}))
        elif self.cfg.stage_parameters['stage_type'] == 'PI_rotzf_and_Galil_xy':
            self.stage = mesoSPIM_PI_rotzf_and_Galil_xy_Stages(self)
            self.stage.sig_position.connect(lambda sdict: self.sig_position.emit({'position': sdict}))
        elif self.cfg.stage_parameters['stage_type'] == 'DemoStage':
            self.stage = mesoSPIM_DemoStage(self)
        try:
            self.stage.sig_position.connect(self.report_position)
        except:
            print('Stage not initalized! Please check the configuratio file')

        ''' Wiring signals through to child objects '''
        self.parent.sig_move_relative.connect(self.move_relative)
        self.parent.sig_move_relative_and_wait_until_done.connect(lambda sdict: self.move_relative(sdict, wait_until_done=True), type=3)

        self.parent.sig_move_absolute.connect(self.move_absolute)
        self.parent.sig_move_absolute_and_wait_until_done.connect(lambda sdict: self.move_absolute(sdict, wait_until_done=True), type=3)

        self.parent.sig_zero_axes.connect(self.sig_zero_axes.emit)
        self.parent.sig_unzero_axes.connect(self.sig_unzero_axes.emit)
        self.parent.sig_stop_movement.connect(self.sig_stop_movement.emit)
        self.parent.sig_load_sample.connect(self.sig_load_sample.emit)
        self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit)

        self.parent.sig_mark_rotation_position.connect(self.sig_mark_rotation_position.emit)
        self.parent.sig_go_to_rotation_position.connect(self.go_to_rotation_position)
        self.parent.sig_go_to_rotation_position_and_wait_until_done.connect(lambda: self.go_to_rotation_position(wait_until_done=True), type=3)

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))


    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, sdict, wait_until_done=False):
        for key, value in zip(sdict.keys(), sdict.values()):
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
            if key == 'stage_program':
                self.execute_stage_program()
            # Log Thread ID during Live: just debugging code
            if key == 'state':
                if value == 'live':
                    logger.info('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))

    @QtCore.pyqtSlot(dict)
    def move_relative(self, sdict, wait_until_done=False):
        # logger.info('Thread ID during relative movement: '+str(int(QtCore.QThread.currentThreadId())))

        # logger.info('Thread ID during move rel: '+str(int(QtCore.QThread.currentThreadId())))
        if wait_until_done:
            self.stage.move_relative(sdict, wait_until_done=True)
        else:
            self.stage.move_relative(sdict)

    @QtCore.pyqtSlot(dict)
    def move_absolute(self, sdict, wait_until_done=False):
        if wait_until_done:
            self.stage.move_absolute(sdict, wait_until_done=True)
        else:
            self.stage.move_absolute(sdict)

    @QtCore.pyqtSlot(dict)
    def report_position(self, sdict):
        self.sig_position.emit({'position': sdict})

    @QtCore.pyqtSlot()
    def go_to_rotation_position(self, wait_until_done=False):
        if wait_until_done:
            self.stage.go_to_rotation_position(wait_until_done=True)
        else:
            self.stage.go_to_rotation_position()

    @QtCore.pyqtSlot(str)
    def set_filter(self, sfilter, wait_until_done=False):
        # logger.info('Thread ID during set filter: '+str(int(QtCore.QThread.currentThreadId())))
        if wait_until_done:
            self.filterwheel.set_filter(sfilter, wait_until_done=True)
        else:
            self.filterwheel.set_filter(sfilter, wait_until_done=False)
        self.state['filter'] = sfilter

    @QtCore.pyqtSlot(str)
    def set_zoom(self, zoom, wait_until_done=False):
        # logger.info('Thread ID during set zoom: '+str(int(QtCore.QThread.currentThreadId())))
        ''' Here, the state parameters are set before sending the value to the zoom --
        this is to avoid laggy update loops with the GUI.'''
        self.state['zoom'] = zoom
        self.state['pixelsize'] = self.cfg.pixelsize[zoom]
        if wait_until_done:
            self.zoom.set_zoom(zoom, wait_until_done=True)
        else:
            self.zoom.set_zoom(zoom, wait_until_done=False)

    def execute_stage_program(self):
        self.stage.execute_program()