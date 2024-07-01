'''
Serial thread for the mesoSPIM project
======================================

This thread handles all connections with serial devices such as stages,
filter wheels, zoom systems etc.
'''

import logging
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
''' Import mesoSPIM modules '''
from .mesoSPIM_State import mesoSPIM_StateSingleton
from .devices.filter_wheels.mesoSPIM_FilterWheel import mesoSPIM_DemoFilterWheel, DynamixelFilterWheel, LudlFilterWheel
from .devices.filter_wheels.mesoSPIM_FilterWheel import ZwoFilterWheel, SutterLambda10BFilterWheel
from .mesoSPIM_Zoom import DynamixelZoom, DemoZoom, MitutoyoZoom
from .mesoSPIM_Stages import mesoSPIM_PI_1toN, mesoSPIM_PI_NtoN, mesoSPIM_ASI_Tiger_Stage, mesoSPIM_ASI_MS2000_Stage, mesoSPIM_DemoStage, mesoSPIM_PI_rotz_and_Galil_xyf_Stages

logger = logging.getLogger(__name__)

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
    sig_center_sample = QtCore.pyqtSignal()
    sig_mark_rotation_position = QtCore.pyqtSignal()
    sig_status_message = QtCore.pyqtSignal(str)
    sig_pause = QtCore.pyqtSignal(bool)
    
    def __init__(self, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent
        self.cfg = parent.cfg
        self.state = mesoSPIM_StateSingleton()

        ''' Attaching the filterwheel '''
        if self.cfg.filterwheel_parameters['filterwheel_type'] == 'Ludl':
            self.filterwheel = LudlFilterWheel(self.cfg.filterwheel_parameters['COMport'],self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'Dynamixel':
            self.filterwheel = DynamixelFilterWheel(self.cfg.filterdict, self.cfg.filterwheel_parameters['COMport'],
                                                    self.cfg.filterwheel_parameters['servo_id'],
                                                    self.cfg.filterwheel_parameters['baudrate'])
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'Demo':
            self.filterwheel = mesoSPIM_DemoFilterWheel(self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'Sutter':
            self.filterwheel = SutterLambda10BFilterWheel(self.cfg.filterwheel_parameters['COMport'], self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'ZWO':
            self.filterwheel = ZwoFilterWheel(self.cfg.filterdict)
        else:
            raise ValueError(f"Filter wheel type unknown: {self.cfg.filterwheel_parameters['filterwheel_type']}")

        ''' Attaching the zoom '''
        if self.cfg.zoom_parameters['zoom_type'] == 'Dynamixel':
            self.zoom = DynamixelZoom(self.cfg.zoomdict, self.cfg.zoom_parameters['COMport'], self.cfg.zoom_parameters['servo_id'], self.cfg.zoom_parameters['baudrate'])
        elif self.cfg.zoom_parameters['zoom_type'] in ('Mitu', 'Mitutoyo'):
            self.zoom = MitutoyoZoom(self.cfg.zoomdict, self.cfg.zoom_parameters['COMport'], self.cfg.zoom_parameters['baudrate'])
        elif self.cfg.zoom_parameters['zoom_type'] in ('Demo', 'DemoZoom'):
            self.zoom = DemoZoom(self.cfg.zoomdict)
        else:
            raise ValueError(f"Zoom type unknown: {self.cfg.zoom_parameters['zoom_type']}")

        ''' Attaching the stage '''
        if self.cfg.stage_parameters['stage_type'] in {'PI', 'PI_1controllerNstages'}:
            self.stage = mesoSPIM_PI_1toN(self)
        elif self.cfg.stage_parameters['stage_type'] == 'PI_NcontrollersNstages':
            self.stage = mesoSPIM_PI_NtoN(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'GalilStage':
        #     self.stage = mesoSPIM_GalilStages(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'PI_rot_and_Galil_xyzf':
        #     self.stage = mesoSPIM_PI_rot_and_Galil_xyzf_Stages(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'PI_f_rot_and_Galil_xyz':
        #     self.stage = mesoSPIM_PI_f_rot_and_Galil_xyz_Stages(self)
        elif self.cfg.stage_parameters['stage_type'] == 'PI_rotz_and_Galil_xyf':
            self.stage = mesoSPIM_PI_rotz_and_Galil_xyf_Stages(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'PI_rotzf_and_Galil_xy':
        #     self.stage = mesoSPIM_PI_rotzf_and_Galil_xy_Stages(self)
        elif self.cfg.stage_parameters['stage_type'] == 'TigerASI':
            self.stage = mesoSPIM_ASI_Tiger_Stage(self)
            self.stage.sig_pause.connect(self.pause)
            self.parent.sig_progress.connect(self.stage.log_slice)
        elif self.cfg.stage_parameters['stage_type'] == 'MS2000ASI':
            self.stage = mesoSPIM_ASI_MS2000_Stage(self)
            self.stage.sig_pause.connect(self.pause)
            self.parent.sig_progress.connect(self.stage.log_slice)
        elif self.cfg.stage_parameters['stage_type'] == 'DemoStage':
            self.stage = mesoSPIM_DemoStage(self)
        else:
            raise ValueError(f"Stage type unknown: {self.cfg.stage_parameters['stage_type']}")
        try:
            self.stage.sig_status_message.connect(self.send_status_message)
            self.stage.sig_position.connect(self.report_position)
        except:
            print('Stage not initalized! Please check the config file')

        # self.parent.sig_move_absolute.connect(self.move_absolute)
        # self.parent.sig_move_absolute_and_wait_until_done.connect(lambda sdict: self.move_absolute(sdict, wait_until_done=True))
        # WARNING: do not use type=Qt.BlockingQueuedConnection for _wait_until_done signals, as this will cause a deadlock!
        # The mesoSPIM_Serial object is executed in the parent (Core) thread, and type=Qt.BlockingQueuedConnection can be used only between threads.
        # Using type=Qt.BlockingQueuedConnection withing the same thread will cause a deadlock.

        self.parent.sig_zero_axes.connect(self.sig_zero_axes.emit)
        self.parent.sig_unzero_axes.connect(self.sig_unzero_axes.emit)
        self.parent.sig_stop_movement.connect(self.sig_stop_movement.emit)
        self.parent.sig_load_sample.connect(self.sig_load_sample.emit)
        self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit)
        self.parent.sig_center_sample.connect(self.sig_center_sample.emit)

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, sdict, wait_until_done=False):
        for key, value in zip(sdict.keys(), sdict.values()):
            if key == 'filter':
                self.set_filter(value, wait_until_done)
            if key == 'zoom':
                self.set_zoom(value, wait_until_done)
            if key == 'stage_program':
                self.execute_stage_program()
            if key == 'ttl_movement_enabled_during_acq':
                self.enable_ttl_motion(value)
            logger.info(f'state change: {key}: {value}')

    @QtCore.pyqtSlot(str)
    def send_status_message(self, string):
        self.sig_status_message.emit(string)

    @QtCore.pyqtSlot(bool)
    def pause(self, boolean):
        self.sig_pause.emit(boolean)

    @QtCore.pyqtSlot(bool)
    def enable_ttl_motion(self, boolean):
        self.stage.enable_ttl_motion(boolean)

    def stage_limits_OK(self, sdict, safety_margin_n_moves=3):
        '''Safety margin is added to deal with delays in position reporting.'''
        for key in ('x_rel', 'y_rel', 'z_rel', 'theta_rel', 'f_rel'):
            if key in sdict:
                axis = key[:-4]
                condition = f"(self.stage.{axis}_min < self.stage.{axis}_pos + {safety_margin_n_moves} * sdict['{key}'] < self.stage.{axis}_max)"
                if not eval(condition):
                    self.send_status_message(f'Relative movement stopped: {axis} motion limit would be reached!')
                    return False
        self.send_status_message('')
        return True

    @QtCore.pyqtSlot(dict)
    def move_relative(self, sdict, wait_until_done=False):
        if self.stage_limits_OK(sdict):
            self.stage.move_relative(sdict, wait_until_done=wait_until_done)
        else:
            logger.info('Stage limits reached: motion stopped')

    @QtCore.pyqtSlot(dict)
    def move_absolute(self, sdict, wait_until_done=False, use_internal_position=True):
        self.stage.move_absolute(sdict, wait_until_done=wait_until_done, use_internal_position=use_internal_position)

    @QtCore.pyqtSlot(dict)
    def report_position(self, sdict):
        self.state['position'] = sdict
        self.sig_position.emit({'position': sdict})

    @QtCore.pyqtSlot()
    def go_to_rotation_position(self, wait_until_done=False):
        self.stage.go_to_rotation_position(wait_until_done=wait_until_done)

    @QtCore.pyqtSlot(str)
    def set_filter(self, sfilter, wait_until_done=False):
        self.filterwheel.set_filter(sfilter, wait_until_done=wait_until_done)
        self.state['filter'] = sfilter

    @QtCore.pyqtSlot(str)
    def set_zoom(self, zoom, wait_until_done=True):
        # logger.info('Thread ID during set zoom: '+str(int(QtCore.QThread.currentThreadId())))
        ''' Here, the state parameters are set before sending the value to the zoom --
        this is to avoid laggy update loops with the GUI.'''
        self.state['zoom'] = zoom
        self.state['pixelsize'] = self.cfg.pixelsize[zoom]
        self.zoom.set_zoom(zoom, wait_until_done=wait_until_done)

    def execute_stage_program(self):
        self.stage.execute_program()
