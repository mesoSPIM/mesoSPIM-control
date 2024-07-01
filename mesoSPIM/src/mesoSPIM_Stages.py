'''
mesoSPIM Stage classes
======================
'''
import time
import logging
from PyQt5 import QtCore
from .mesoSPIM_State import mesoSPIM_StateSingleton
logger = logging.getLogger(__name__)


class mesoSPIM_Stage(QtCore.QObject):
    '''
    DemoStage for a mesoSPIM microscope

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
    '''

    sig_position = QtCore.pyqtSignal(dict)
    sig_status_message = QtCore.pyqtSignal(str)
    sig_pause = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        ''' The movement signals are emitted by the mesoSPIM_Core, which in turn
        instantiates the mesoSPIM_Serial object, both (must be) running in the same Core thread.

        Therefore, the signals are emitted by the parent of the parent, which
        is slightly confusing and dirty.
        '''
        self.parent.sig_stop_movement.connect(self.stop)
        self.parent.sig_zero_axes.connect(self.zero_axes)
        self.parent.sig_unzero_axes.connect(self.unzero_axes)
        self.parent.sig_load_sample.connect(self.load_sample)
        self.parent.sig_unload_sample.connect(self.unload_sample)
        self.parent.sig_center_sample.connect(self.center_sample)

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)

        '''Initial setting of all positions

        self.x_pos, self.y_pos etc are the true axis positions, no matter whether
        the stages are zeroed or not.
        '''
        self.x_pos = 0
        self.y_pos = 0
        self.z_pos = 0
        self.f_pos = 2500 # for testing purposes
        self.theta_pos = 0

        '''Internal (software) positions'''
        self.int_x_pos = 0
        self.int_y_pos = 0
        self.int_z_pos = 0
        self.int_f_pos = 0
        self.int_theta_pos = 0

        '''Create offsets

        It should be:

        int_x_pos = x_pos + int_x_pos_offset
        self.int_x_pos = self.x_pos + self.int_x_pos_offset

        OR

        x_pos = int_x_pos - int_x_pos_offset
        self.x_pos = self.int_x_pos - self.int_x_pos_offset

        '''
        self.int_x_pos_offset = 0
        self.int_y_pos_offset = 0
        self.int_z_pos_offset = 0
        self.int_f_pos_offset = 0
        self.int_theta_pos_offset = 0

        '''
        Setting movement limits: currently hardcoded

        Open question: Should these be in mm or microns?
        Answer: Microns for now....
        '''
        self.x_max = self.cfg.stage_parameters['x_max']
        self.x_min = self.cfg.stage_parameters['x_min']
        self.y_max = self.cfg.stage_parameters['y_max']
        self.y_min = self.cfg.stage_parameters['y_min']
        self.z_max = self.cfg.stage_parameters['z_max']
        self.z_min = self.cfg.stage_parameters['z_min']
        self.f_max = self.cfg.stage_parameters['f_max']
        self.f_min = self.cfg.stage_parameters['f_min']
        self.theta_max = self.cfg.stage_parameters['theta_max']
        self.theta_min = self.cfg.stage_parameters['theta_min']
        for deprecated_param in ('x_rot_position', 'y_rot_position', 'z_rot_position'):
            if deprecated_param in self.cfg.stage_parameters.keys():
                print(f"INFO: '{deprecated_param}' in 'stage_parameters' dictionary is deprecated and ignored. "
                      f"Update your config file to suppress these messages.")

    def create_position_dict(self):
        self.position_dict = {'x_pos': self.x_pos,
                              'y_pos': self.y_pos,
                              'z_pos': self.z_pos,
                              'f_pos': self.f_pos,
                              'theta_pos': self.theta_pos,
                              }
        self.state['position_absolute'] = self.position_dict

    def create_internal_position_dict(self):
        self.int_position_dict = {'x_pos': self.int_x_pos,
                                  'y_pos': self.int_y_pos,
                                  'z_pos': self.int_z_pos,
                                  'f_pos': self.int_f_pos,
                                  'theta_pos': self.int_theta_pos,
                                  }

    @QtCore.pyqtSlot()
    def report_position(self):
        self.create_position_dict()

        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()
        self.state['position'] = self.int_position_dict
        self.sig_position.emit(self.int_position_dict)

    @QtCore.pyqtSlot(dict)
    def move_relative(self, sdict, wait_until_done=False):
        if 'x_rel' in sdict:
            self.x_pos = self.x_pos + sdict['x_rel']
            print(f"INFO: x_pos = {self.x_pos}")

        if 'y_rel' in sdict:
            self.y_pos = self.y_pos + sdict['y_rel']
            print(f"INFO: y_pos = {self.y_pos}")

        if 'z_rel' in sdict:
            self.z_pos = self.z_pos + sdict['z_rel']
            print(f"INFO: z_pos = {self.z_pos}")

        if 'theta_rel' in sdict:
            self.theta_pos = self.theta_pos + sdict['theta_rel']
            print(f"INFO: theta_pos = {self.theta_pos}")

        if 'f_rel' in sdict:
            self.f_pos = self.f_pos + sdict['f_rel']
            print(f"INFO: f_pos = {self.f_pos}")

        if wait_until_done is True:
            self.state['moving_to_target'] = True
            time.sleep(0.1)
            self.report_position()
            self.state['moving_to_target'] = False

    @QtCore.pyqtSlot(dict)
    def move_absolute(self, dict, wait_until_done=False, use_internal_position=True):
        if use_internal_position is True:
            x_offset = self.int_x_pos_offset
            y_offset = self.int_y_pos_offset
            z_offset = self.int_z_pos_offset
            f_offset = self.int_f_pos_offset
            theta_offset = self.int_theta_pos_offset
        else:
            x_offset = 0
            y_offset = 0
            z_offset = 0
            f_offset = 0
            theta_offset = 0
        if 'x_abs' in dict:
            x_abs = dict['x_abs'] - x_offset
            self.x_pos = x_abs
            print(f"INFO: x_pos = {self.x_pos}")

        if 'y_abs' in dict:
            y_abs = dict['y_abs'] - y_offset
            self.y_pos = y_abs
            print(f"INFO: y_pos = {self.y_pos}")

        if 'z_abs' in dict:
            z_abs = dict['z_abs'] - z_offset
            self.z_pos = z_abs
            print(f"INFO: z_pos = {self.z_pos}")

        if 'f_abs' in dict:
            f_abs = dict['f_abs'] - f_offset
            self.f_pos = f_abs
            if self.f_min < f_abs < self.f_max:
                logger.debug('Moving to f_abs: %s' % f_abs)
                time.sleep(0.2)
            else:
                msg = f' f_abs={f_abs} absolute movement stopped: F motion limits ({self.f_min},{self.f_max}) would be reached!'
                self.sig_status_message.emit(msg)
                logger.debug(msg)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs'] - theta_offset
            self.theta_pos = theta_abs
            print(f"INFO: theta_pos = {self.theta_pos}")

        if wait_until_done is True:
            self.state['moving_to_target'] = True
            time.sleep(1)
            self.report_position()
            self.state['moving_to_target'] = False
            msg = 'Demo stage move (wait_until_done is True) complete'
            print(msg); logger.debug(msg)

    @QtCore.pyqtSlot()
    def stop(self):
        self.sig_status_message.emit('Stopped')

    def zero_axes(self, list):
        for axis in list:
            try:
                exec('self.int_' + axis + '_pos_offset = -self.' + axis + '_pos') # update the position offset
            except:
                logger.info('Zeroing of axis: ', axis, 'failed')

    def unzero_axes(self, list):
        for axis in list:
            try:
                exec('self.int_' + axis + '_pos_offset = 0') # zero the position offset
            except:
                logger.info('Unzeroing of axis: ', axis, 'failed')

    def load_sample(self):
        self.y_pos = self.cfg.stage_parameters['y_load_position']

    def unload_sample(self):
        self.y_pos = self.cfg.stage_parameters['y_unload_position']    
        
    def center_sample(self):
        if 'x_center_position' in self.cfg.stage_parameters.keys():
            self.x_center = self.cfg.stage_parameters['x_center_position']
            self.move_absolute({'x_abs': self.x_center}, wait_until_done=False, use_internal_position=False)
        else:
            self.x_center = self.x_pos
            msg = 'Centering X position not defined in config file'
            logger.info(msg); print(msg)
        if 'z_center_position' in self.cfg.stage_parameters.keys():
            self.z_center = self.cfg.stage_parameters['z_center_position']
            self.move_absolute({'z_abs': self.z_center}, wait_until_done=False, use_internal_position=False)
        else:
            self.z_center = self.z_pos
            msg = 'Centering Z position not defined in config file'
            logger.info(msg); print(msg)


class mesoSPIM_DemoStage(mesoSPIM_Stage):
    def __init__(self, parent=None):
        super().__init__(parent)


class mesoSPIM_PI_1toN(mesoSPIM_Stage):
    '''
    Configuration with 1 controller connected to N stages, (e.g. C-884, default mesoSPIM V5 setup).

    Note:
    configs as declared in mesoSPIM_config.py:
        stage_parameters = {'stage_type' : 'PI_1controllerNstages',
                            ...
                            }
    pi_parameters = {'controllername' : 'C-884',
                    'stages' : ('L-509.20DG10','L-509.40DG10','L-509.20DG10','M-060.DG','M-406.4PD','NOSTAGE'),
                    'refmode' : ('FRF',),
                    'serialnum' : ('118075764'),
                    }
    '''

    def __init__(self, parent=None):
        super().__init__(parent)
        from pipython import GCSDevice, pitools
        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters
        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = list(self.cfg.pi_parameters['stages'])
        self.refmode = self.cfg.pi_parameters['refmode']
        self.serialnum = self.cfg.pi_parameters['serialnum']
        self.pidevice = GCSDevice(self.controllername)
        self.pidevice.ConnectUSB(serialnum=self.serialnum)

        ''' PI startup '''
        ''' with refmode enabled: pretty dangerous
        pitools.startup(self.pidevice, stages=self.pi_stages, refmode=self.refmode)
        '''
        pitools.startup(self.pidevice, stages=self.pi_stages)

        ''' Report reference status of all stages '''
        for ii in range(1, len(self.pi_stages) + 1):
            tStage = self.pi_stages[ii - 1]
            if tStage == 'NOSTAGE':
                continue

            tState = self.pidevice.qFRF(ii)
            if tState[ii]:
                msg = 'referenced'
            else:
                msg = '*UNREFERENCED*'

            logger.info("Axis %d (%s) reference status: %s" % (ii, tStage, msg))

        self.report_position()
        ''' Stage 5 referencing hack '''
        # self.pidevice.FRF(5)
        # logger.info('M-406 Emergency referencing hack: Waiting for referencing move')
        # self.block_till_controller_is_ready()
        # logger.info('M-406 Emergency referencing hack done')

    def __del__(self):
        try:
            self.pidevice.unload()
        except:
            pass

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)
        self.x_pos = round(positions['1'] * 1000, 2)
        self.y_pos = round(positions['2'] * 1000, 2)
        self.z_pos = round(positions['3'] * 1000, 2)
        self.f_pos = round(positions['5'] * 1000, 2)
        self.theta_pos = positions['4']

        self.create_position_dict()

        # relative positions, with the offset
        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()
        self.state['position'] = self.int_position_dict
        self.sig_position.emit(self.int_position_dict)

    @QtCore.pyqtSlot(dict)
    def move_relative(self, sdict, wait_until_done=False):
        ''' PI move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        if 'x_rel' in sdict:
            x_rel = sdict['x_rel'] / 1000
            self.pidevice.MVR({1: x_rel})

        if 'y_rel' in sdict:
            y_rel = sdict['y_rel'] / 1000
            self.pidevice.MVR({2: y_rel})

        if 'z_rel' in sdict:
            z_rel = sdict['z_rel'] / 1000
            self.pidevice.MVR({3: z_rel})

        if 'theta_rel' in sdict:
            theta_rel = sdict['theta_rel']
            self.pidevice.MVR({4: theta_rel})

        if 'f_rel' in sdict:
            f_rel = sdict['f_rel'] / 1000
            self.pidevice.MVR({5: f_rel})

        if wait_until_done:
            self.state['moving_to_target'] = True
            self.pitools.waitontarget(self.pidevice)
            self.report_position()
            self.state['moving_to_target'] = False

    @QtCore.pyqtSlot(dict)
    def move_absolute(self, sdict, wait_until_done=False, use_internal_position=True):
        '''
        Lots of implementation details in here, should be replaced by a facade

        TODO: Also lots of repeating code.
        TODO: DRY principle violated
        '''
        if use_internal_position is True:
            x_offset = self.int_x_pos_offset
            y_offset = self.int_y_pos_offset
            z_offset = self.int_z_pos_offset
            f_offset = self.int_f_pos_offset
            theta_offset = self.int_theta_pos_offset
        else:
            x_offset = 0
            y_offset = 0
            z_offset = 0
            f_offset = 0
            theta_offset = 0
        if 'x_abs' in sdict:
            x_abs = sdict['x_abs'] - x_offset
            if self.x_min < x_abs < self.x_max:
                ''' Conversion to mm and command emission'''
                x_abs = x_abs / 1000
                self.pidevice.MOV({1: x_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: X Motion limit would be reached!')

        if 'y_abs' in sdict:
            y_abs = sdict['y_abs'] - y_offset
            if self.y_min < y_abs < self.y_max:
                ''' Conversion to mm and command emission'''
                y_abs = y_abs / 1000
                self.pidevice.MOV({2: y_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Y Motion limit would be reached!')

        if 'z_abs' in sdict:
            z_abs = sdict['z_abs'] - z_offset
            if self.z_min < z_abs < self.z_max:
                ''' Conversion to mm and command emission'''
                z_abs = z_abs / 1000
                self.pidevice.MOV({3: z_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!')

        if 'f_abs' in sdict:
            f_abs = sdict['f_abs'] - f_offset
            if self.f_min < f_abs < self.f_max:
                logger.debug('Moving to f_abs: %s' % f_abs)
                ''' Conversion to mm and command emission'''
                f_abs_mm = f_abs / 1000
                self.pidevice.MOV({5: f_abs_mm})
            else:
                msg = f' f_abs={f_abs} absolute movement stopped: F motion limits ({self.f_min},{self.f_max}) would be reached!'
                self.sig_status_message.emit(msg)
                logger.debug(msg)

        if 'theta_abs' in sdict:
            theta_abs = sdict['theta_abs'] - theta_offset
            if self.theta_min < theta_abs < self.theta_max:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({4: theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!')

        if wait_until_done:
            self.state['moving_to_target'] = True
            logger.debug('Waiting for target (wait_until_done=True)')
            self.pitools.waitontarget(self.pidevice)
            logger.debug('Target reached (wait_until_done=True)')
            self.report_position()
            self.state['moving_to_target'] = False

    @QtCore.pyqtSlot()
    def stop(self):
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        y_abs = self.cfg.stage_parameters['y_load_position'] / 1000
        self.pidevice.MOV({2: y_abs})

    def unload_sample(self):
        y_abs = self.cfg.stage_parameters['y_unload_position'] / 1000
        self.pidevice.MOV({2: y_abs})

    def block_till_controller_is_ready(self):
        '''
        Blocks further execution (especially during referencing moves)
        till the PI controller returns ready
        '''
        blockflag = True
        while blockflag:
            if self.pidevice.IsControllerReady():
                blockflag = False
            else:
                time.sleep(0.1)


class mesoSPIM_PI_NtoN(mesoSPIM_Stage):
    '''
    Expects following microscope configuration:
        Sample XYZ movement: Physik Instrumente stage with three L-509-type stepper motor stages and individual C-663 controller.
        F movement: Physik Instrumente C-663 controller and custom stage with stepper motor
        Rotation: not implemented

        All stage controller are of same type and the sample stages work with reference setting.
        Focus stage has reference mode set to off.
            
    Note:
        configs as declared in mesoSPIM_config.py:
        stage_parameters = {'stage_type' : 'PI_NcontrollersNstages',
                            ...
                            }
        pi_parameters = {'axes_names': ('x', 'y', 'z', 'theta', 'f'),
                        'stages': ('L-509.20SD00', 'L-509.40SD00', 'L-509.20SD00', None, 'MESOSPIM_FOCUS'),
                        'controllername': ('C-663', 'C-663', 'C-663', None, 'C-663'),
                        'serialnum': ('**********', '**********', '**********', None, '**********'),
                        'refmode': ('FRF', 'FRF', 'FRF', None, 'RON')
                        }
        make sure that reference points are not in conflict with general microscope setup
        and will not hurt optics under referencing at startup
    '''

    def __init__(self, parent=None):
        super().__init__(parent)
        from pipython import GCSDevice, pitools
        self.pitools = pitools
        self.pi = self.cfg.pi_parameters
        print("Connecting stage drive...")

        # Setting up the stages with separate PI controller.
        # Explicitly set referencing status and get position

        # gather stage devices in VirtualStages class
        class VirtualStages:
            pass

        assert len(self.pi['axes_names']) == len(self.pi['stages']) == len(self.pi['controllername']) \
               == len(self.pi['serialnum']) == len(self.pi['refmode']), \
            "Config file, pi_parameters dictionary: numbers of axes_names, stages, controllername, serialnum, refmode must match "
        self.pi_stages = VirtualStages()
        for axis_name, stage, controller, serialnum, refmode in zip(self.pi['axes_names'], self.pi['stages'],
                                                                    self.pi['controllername'], self.pi['serialnum'],
                                                                    self.pi['refmode']):
            # run stage startup procedure for each axis
            if stage:
                print(f'starting stage {stage}')
                pidevice_ = GCSDevice(controller)
                pidevice_.ConnectUSB(serialnum=serialnum)
                if refmode is None:
                    pitools.startup(pidevice_, stages=stage)
                elif refmode == 'FRF':
                    pitools.startup(pidevice_, stages=stage, refmodes=refmode)
                    pidevice_.FRF(1)
                elif refmode == 'RON':
                    pitools.startup(pidevice_, stages=stage)
                    pidevice_.RON({1: 0})  # set reference mode
                    # activate servo
                    pidevice_.SVO(pidevice_.axes, [True] * len(pidevice_.axes))
                    # print('servo state: {}'.format(pidevice_.qSVO()))
                    # set/get actual position as home position
                    # assumes that starting position is within reasonable distance from optimal focus
                    pidevice_.POS({1: 0.0})
                    pidevice_.DFH(1)
                else:
                    raise ValueError(f"refmode {refmode} is not supported, PI stage {stage} initialization failed")
                print(f'stage {stage} started')
                print('axis {}, referencing mode: {}'.format(axis_name, pidevice_.qRON()))
                self.wait_for_controller(pidevice_)
                print('axis {}, stage {} ready'.format(axis_name, stage))
                setattr(self.pi_stages, ('pidevice_' + axis_name), pidevice_)
            else:
                setattr(self.pi_stages, axis_name, None)

        logger.info('mesoSPIM_PI_NtoN: started')


    def wait_for_controller(self, controller):
        # function used during stage setup
        blockflag = True
        while blockflag:
            if controller.IsControllerReady():
                blockflag = False
            else:
                time.sleep(0.1)


    def __del__(self):
        '''Close the PI connection'''
        try:
            [(getattr(self.pi_stages, ('pidevice_' + axis_name))).unload() for axis_name in self.pi['axes_names'] if
             (hasattr(self.pi_stages, ('pidevice_' + axis_name)))]
        except:
            pass


    def report_position(self):
        '''report stage position'''
        for axis_name in self.pi['axes_names']:
            pidevice_name = 'pidevice_' + str(axis_name)
            if hasattr(self.pi_stages, pidevice_name):
                try:
                    if axis_name is None:
                        pos = 0
                    elif axis_name == 'theta':
                        pos = (getattr(self.pi_stages, pidevice_name)).qPOS(1)[1]
                    else:
                        pos = round((getattr(self.pi_stages, pidevice_name)).qPOS(1)[1] * 1000, 2)
                except:
                    print(f"Failed to report_position for axis_name {axis_name}, pidevice_name {pidevice_name}.")
            else:
                pos = 0

            setattr(self, (axis_name + '_pos'), pos)
            int_pos = pos + getattr(self, ('int_' + axis_name + '_pos_offset'))
            setattr(self, ('int_' + axis_name + '_pos'), int_pos)

        self.create_position_dict()
        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)


    def move_relative(self, move_dict, wait_until_done=False):
        ''' PI move relative method '''        
        for axis_move in move_dict.keys():        
            axis_name = axis_move.split('_')[0]
            move_value = move_dict[axis_move]        
        
            if (hasattr(self.pi_stages, ('pidevice_' + axis_name))):
                if (getattr(self, (axis_name + '_min')) < getattr(self, (axis_name + '_pos')) + move_value) and \
                    (getattr(self, (axis_name + '_max')) > getattr(self, (axis_name + '_pos')) + move_value):
                    if not axis_name=='theta':
                        move_value = move_value/1000
                    (getattr(self.pi_stages, ('pidevice_' + axis_name))).MVR({1 : move_value})
                else:
                    self.sig_status_message.emit('Relative movement stopped: {} Motion limit would be reached!'.format(axis_name))
                if (axis_name == 'f') or (wait_until_done == True):
                    self.pitools.waitontarget(getattr(self.pi_stages, ('pidevice_' + axis_name)))  # focus may be slower than expected


    def move_absolute(self, move_dict, wait_until_done=False, use_internal_position=True):
        if use_internal_position is True:
            x_offset = self.int_x_pos_offset
            y_offset = self.int_y_pos_offset
            z_offset = self.int_z_pos_offset
            f_offset = self.int_f_pos_offset
            theta_offset = self.int_theta_pos_offset
        else:
            x_offset = 0
            y_offset = 0
            z_offset = 0
            f_offset = 0
            theta_offset = 0
        for axis_move in move_dict.keys():
            axis_name = axis_move.split('_')[0]
            move_value = move_dict[axis_move] - locals()[axis_name + '_offset']
            
            if (hasattr(self.pi_stages, ('pidevice_' + axis_name))):
                if (getattr(self, (axis_name + '_min')) < move_value) and \
                        (getattr(self, (axis_name + '_max')) > move_value):
                    if not axis_name == 'theta':
                        move_value = move_value / 1000
                    (getattr(self.pi_stages, ('pidevice_' + axis_name))).MOV({1: move_value})
                else:
                    self.sig_status_message.emit(
                        'Absolute movement stopped: {} Motion limit would be reached!'.format(axis_name))
                if (axis_name == 'f') or (wait_until_done == True):
                    self.pitools.waitontarget(getattr(self.pi_stages, ('pidevice_' + axis_name)))  # focus may be slower than expected


    def stop(self):
        '''stop stage movement'''
        [(getattr(self.pi_stages, ('pidevice_' + axis_name))).STP(noraise=True) for axis_name in self.pi['axes_names']
         if (hasattr(self.pi_stages, ('pidevice_' + axis_name)))]


    def load_sample(self):
        '''bring sample to imaging position'''
        axis_name = 'y'
        y_abs = self.cfg.stage_parameters['y_load_position'] / 1000
        (getattr(self.pi_stages, ('pidevice_' + axis_name))).MOV({1: y_abs})


    def unload_sample(self):
        '''lift sample to sample handling position'''
        axis_name = 'y'
        y_abs = self.cfg.stage_parameters['y_unload_position'] / 1000
        (getattr(self.pi_stages, ('pidevice_' + axis_name))).MOV({1: y_abs})


# class mesoSPIM_GalilStages(mesoSPIM_Stage):
#     '''

#     It is expected that the parent class has the following signals:
#         sig_move_relative = pyqtSignal(dict)
#         sig_move_relative_and_wait_until_done = pyqtSignal(dict)
#         sig_move_absolute = pyqtSignal(dict)
#         sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
#         sig_zero = pyqtSignal(list)
#         sig_unzero = pyqtSignal(list)
#         sig_stop_movement = pyqtSignal()

#     Also contains a QTimer that regularily sends position updates, e.g
#     during the execution of movements.

#     Todo: Rotation handling not implemented!
#     '''

#     def __init__(self, parent=None):
#         super().__init__(parent)

#         '''
#         Galil-specific code
#         '''
#         from .devices.stages.galil.galilcontrol import StageControlGalil

#         self.x_encodercounts_per_um = self.cfg.xyz_galil_parameters['x_encodercounts_per_um']
#         self.y_encodercounts_per_um = self.cfg.xyz_galil_parameters['y_encodercounts_per_um']
#         self.z_encodercounts_per_um = self.cfg.xyz_galil_parameters['z_encodercounts_per_um']
#         self.f_encodercounts_per_um = self.cfg.f_galil_parameters['z_encodercounts_per_um']

#         ''' Setting up the Galil stages '''
#         self.xyz_stage = StageControlGalil(COMport=self.cfg.xyz_galil_parameters['COMport'],
#                                            x_encodercounts_per_um=self.x_encodercounts_per_um,
#                                            y_encodercounts_per_um=self.y_encodercounts_per_um,
#                                            z_encodercounts_per_um=self.z_encodercounts_per_um)

#         self.f_stage = StageControlGalil(COMport=self.cfg.f_galil_parameters['COMport'],
#                                          x_encodercounts_per_um=0,
#                                          y_encodercounts_per_um=0,
#                                          z_encodercounts_per_um=self.f_encodercounts_per_um)
#         '''
#         print('Galil: ', self.xyz_stage.read_position('x'))
#         print('Galil: ', self.xyz_stage.read_position('y'))
#         print('Galil: ', self.xyz_stage.read_position('z'))
#         '''

#     def __del__(self):
#         try:
#             '''Close the Galil connection'''
#             self.xyz_stage.close_stage()
#             self.f_stage.close_stage()
#         except:
#             pass

#     def report_position(self):
#         self.x_pos = self.xyz_stage.read_position('x')
#         self.y_pos = self.xyz_stage.read_position('y')
#         self.z_pos = self.xyz_stage.read_position('z')
#         self.f_pos = self.f_stage.read_position('z')
#         self.theta_pos = 0

#         self.create_position_dict()

#         self.int_x_pos = self.x_pos + self.int_x_pos_offset
#         self.int_y_pos = self.y_pos + self.int_y_pos_offset
#         self.int_z_pos = self.z_pos + self.int_z_pos_offset
#         self.int_f_pos = self.f_pos + self.int_f_pos_offset
#         self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

#         self.create_internal_position_dict()

#         self.sig_position.emit(self.int_position_dict)

#     def move_relative(self, sdict, wait_until_done=False):
#         ''' Galil move relative method

#         Lots of implementation details in here, should be replaced by a facade
#         '''
#         if 'x_rel' in sdict:
#             x_rel = sdict['x_rel']
#             if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
#                 self.xyz_stage.move_relative(xrel=int(x_rel))
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!')

#         if 'y_rel' in sdict:
#             y_rel = sdict['y_rel']
#             if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
#                 self.xyz_stage.move_relative(yrel=int(y_rel))
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!')

#         if 'z_rel' in sdict:
#             z_rel = sdict['z_rel']
#             if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
#                 self.xyz_stage.move_relative(zrel=int(z_rel))
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')

#         if 'theta_rel' in sdict:
#             theta_rel = sdict['theta_rel']
#             if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
#                 print('No rotation stage attached')
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!')

#         if 'f_rel' in sdict:
#             f_rel = sdict['f_rel']
#             if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
#                 self.f_stage.move_relative(zrel=f_rel)
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!')

#         if wait_until_done == True:
#             pass

#     def move_absolute(self, dict, wait_until_done=False):
#         '''
#         Galil move absolute method

#         Lots of implementation details in here, should be replaced by a facade

#         '''
#         # print(dict)

#         # if ('x_abs', 'y_abs', 'z_abs', 'f_abs') in dict:
#         x_abs = dict['x_abs']
#         x_abs = x_abs - self.int_x_pos_offset
#         y_abs = dict['y_abs']
#         y_abs = y_abs - self.int_y_pos_offset
#         z_abs = dict['z_abs']
#         z_abs = z_abs - self.int_z_pos_offset
#         f_abs = dict['f_abs']
#         f_abs = f_abs - self.int_f_pos_offset

#         self.xyz_stage.move_absolute(xabs=x_abs, yabs=y_abs, zabs=z_abs)
#         self.f_stage.move_absolute(zabs=f_abs)

#         if wait_until_done == True:
#             self.xyz_stage.wait_until_done('XYZ')

#     # def stop(self):
#     #     # self.pidevice.STP(noraise=True)

#     # def load_sample(self):
#     #     y_abs = self.cfg.stage_parameters['y_load_position']/1000
#     #     # self.pidevice.MOV({2 : y_abs})

#     # def unload_sample(self):
#     #     y_abs = self.cfg.stage_parameters['y_unload_position']/1000
#     #     # self.pidevice.MOV({2 : y_abs})


# class mesoSPIM_PI_f_rot_and_Galil_xyz_Stages(mesoSPIM_Stage):
#     '''
#     Deprecated?
#     Todo: Rotation handling not implemented!
#     Todo: Rotation axes are hardcoded! (M-605: #5, M-061.PD: #6)
#     '''

#     def __init__(self, parent=None):
#         super().__init__(parent)

#         self.state = mesoSPIM_StateSingleton()

#         self.pos_timer = QtCore.QTimer(self)
#         self.pos_timer.timeout.connect(self.report_position)
#         self.pos_timer.start(50)
#         '''
#         Galil-specific code
#         '''
#         from .devices.stages.galil.galilcontrol import StageControlGalil

#         self.x_encodercounts_per_um = self.cfg.xyz_galil_parameters['x_encodercounts_per_um']
#         self.y_encodercounts_per_um = self.cfg.xyz_galil_parameters['y_encodercounts_per_um']
#         self.z_encodercounts_per_um = self.cfg.xyz_galil_parameters['z_encodercounts_per_um']

#         ''' Setting up the Galil stages '''
#         self.xyz_stage = StageControlGalil(self.cfg.xyz_galil_parameters['port'], [self.x_encodercounts_per_um,
#                                                                                    self.y_encodercounts_per_um,
#                                                                                    self.z_encodercounts_per_um])


#         ''' PI-specific code '''
#         from pipython import GCSDevice, pitools

#         self.pitools = pitools

#         ''' Setting up the PI stages '''
#         self.pi = self.cfg.pi_parameters

#         self.controllername = self.cfg.pi_parameters['controllername']
#         self.pi_stages = list(self.cfg.pi_parameters['stages'])
#         # ('M-112K033','L-406.40DG10','M-112K033','M-116.DG','M-406.4PD','NOSTAGE')
#         self.refmode = self.cfg.pi_parameters['refmode']
#         # self.serialnum = ('118015439')  # Wyss Geneva
#         self.serialnum = self.cfg.pi_parameters['serialnum']  # UZH Irchel H45

#         self.pidevice = GCSDevice(self.controllername)
#         self.pidevice.ConnectUSB(serialnum=self.serialnum)

#         ''' PI startup '''

#         ''' with refmode enabled: pretty dangerous
#         pitools.startup(self.pidevice, stages=self.pi_stages, refmode=self.refmode)
#         '''
#         pitools.startup(self.pidevice, stages=self.pi_stages)

#         ''' Setting PI velocities '''
#         self.pidevice.VEL(self.cfg.pi_parameters['velocity'])

#         ''' Stage 5 referencing hack '''
#         # print('Referencing status 3: ', self.pidevice.qFRF(3))
#         # print('Referencing status 5: ', self.pidevice.qFRF(5))
#         self.pidevice.FRF(5)
#         print('M-406 Emergency referencing hack: Waiting for referencing move')
#         logger.info('M-406 Emergency referencing hack: Waiting for referencing move')
#         self.block_till_controller_is_ready()
#         print('M-406 Emergency referencing hack done')
#         logger.info('M-406 Emergency referencing hack done')
#         # print('Again: Referencing status 3: ', self.pidevice.qFRF(3))
#         # print('Again: Referencing status 5: ', self.pidevice.qFRF(5))

#     def __del__(self):
#         try:
#             '''Close the Galil connection'''
#             self.xyz_stage.close()
#             self.f_stage.close_stage()
#         except:
#             pass

#     def report_position(self):
#         positions = self.pidevice.qPOS(self.pidevice.axes)

#         '''
#         Ugly workaround to deal with non-responding stage 
#         position reports: Do not update positions in 
#         exceptional circumstances. 
#         '''
#         self.x_pos, self.y_pos, self.z_pos = self.xyz_stage.read_position()
#         self.f_pos = round(positions['5'] * 1000, 2)
#         self.theta_pos = positions['6']

#         self.create_position_dict()

#         self.int_x_pos = self.x_pos + self.int_x_pos_offset
#         self.int_y_pos = self.y_pos + self.int_y_pos_offset
#         self.int_z_pos = self.z_pos + self.int_z_pos_offset
#         self.int_f_pos = self.f_pos + self.int_f_pos_offset
#         self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

#         self.create_internal_position_dict()
#         self.state['position'] = self.int_position_dict
#         self.sig_position.emit(self.int_position_dict)
#         # print(self.int_position_dict)

#     def move_relative(self, sdict, wait_until_done=False):
#         ''' Galil move relative method

#         Lots of implementation details in here, should be replaced by a facade
#         '''
#         xyz_motion_dict = {}

#         if 'x_rel' in sdict:
#             x_rel = sdict['x_rel']
#             if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
#                 xyz_motion_dict.update({1: int(x_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!')

#         if 'y_rel' in sdict:
#             y_rel = sdict['y_rel']
#             if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
#                 xyz_motion_dict.update({2: int(y_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!')

#         if 'z_rel' in sdict:
#             z_rel = sdict['z_rel']
#             if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
#                 xyz_motion_dict.update({3: int(z_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')

#         if xyz_motion_dict != {}:
#             self.xyz_stage.move_relative(xyz_motion_dict)

#         if 'theta_rel' in sdict:
#             theta_rel = sdict['theta_rel']
#             if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
#                 self.pidevice.MVR({6: theta_rel})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!')

#         if 'f_rel' in sdict:
#             f_rel = sdict['f_rel']
#             if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
#                 f_rel = f_rel / 1000
#                 self.pidevice.MVR({5: f_rel})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!')

#         if wait_until_done == True:
#             self.xyz_stage.wait_until_done('XYZ')
#             self.pitools.waitontarget(self.pidevice)

#     def move_absolute(self, dict, wait_until_done=False):
#         '''
#         Galil move absolute method

#         Lots of implementation details in here, should be replaced by a facade

#         '''
#         xyz_motion_dict = {}

#         if 'x_abs' or 'y_abs' or 'z_abs' in dict:
#             if 'x_abs' in dict:
#                 x_abs = dict['x_abs']
#                 x_abs = x_abs - self.int_x_pos_offset
#                 xyz_motion_dict.update({1: x_abs})

#             if 'y_abs' in dict:
#                 y_abs = dict['y_abs']
#                 y_abs = y_abs - self.int_y_pos_offset
#                 xyz_motion_dict.update({2: y_abs})

#             if 'z_abs' in dict:
#                 z_abs = dict['z_abs']
#                 z_abs = z_abs - self.int_z_pos_offset
#                 xyz_motion_dict.update({3: z_abs})

#         if xyz_motion_dict != {}:
#             self.xyz_stage.move_absolute(xyz_motion_dict)

#         if wait_until_done == True:
#             self.xyz_stage.wait_until_done('XYZ')

#         if 'f_abs' in dict:
#             f_abs = dict['f_abs']
#             f_abs = f_abs - self.int_f_pos_offset
#             if self.f_min < f_abs and self.f_max > f_abs:
#                 ''' Conversion to mm and command emission'''
#                 f_abs = f_abs / 1000
#                 self.pidevice.MOV({5: f_abs})
#             else:
#                 self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!')

#         if 'theta_abs' in dict:
#             theta_abs = dict['theta_abs']
#             theta_abs = theta_abs - self.int_theta_pos_offset
#             if self.theta_min < theta_abs and self.theta_max > theta_abs:
#                 ''' No Conversion to mm !!!! and command emission'''
#                 self.pidevice.MOV({6: theta_abs})
#             else:
#                 self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!')

#         if wait_until_done == True:
#             self.pitools.waitontarget(self.pidevice)

#     def stop(self):
#         self.xyz_stage.stop(restart_programs=True)
#         self.pidevice.STP(noraise=True)

#     def load_sample(self):
#         self.xyz_stage.move_absolute(
#             {1: self.int_x_pos, 2: self.cfg.stage_parameters['y_load_position'], 3: self.int_z_pos})

#     def unload_sample(self):
#         self.xyz_stage.move_absolute(
#             {1: self.int_x_pos, 2: self.cfg.stage_parameters['y_unload_position'], 3: self.int_z_pos})

#     def block_till_controller_is_ready(self):
#         '''
#         Blocks further execution (especially during referencing moves)
#         till the PI controller returns ready
#         '''
#         blockflag = True
#         while blockflag:
#             if self.pidevice.IsControllerReady():
#                 blockflag = False
#             else:
#                 time.sleep(0.1)

#     def execute_program(self):
#         '''Executes program stored on the Galil controller'''
#         self.xyz_stage.execute_program()


# class mesoSPIM_PI_rot_and_Galil_xyzf_Stages(mesoSPIM_Stage):
#     '''
#     Expects following microscope configuration:
    
#     Sample XYZ movement: Galil controller with 3 axes 
#     F movement: Second Galil controller with a single axis 
#     Rotation: PI C-863 mercury controller

#     It is expected that the parent class has the following signals:
#         sig_move_relative = pyqtSignal(dict)
#         sig_move_relative_and_wait_until_done = pyqtSignal(dict)
#         sig_move_absolute = pyqtSignal(dict)
#         sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
#         sig_zero = pyqtSignal(list)
#         sig_unzero = pyqtSignal(list)
#         sig_stop_movement = pyqtSignal()

#     Also contains a QTimer that regularily sends position updates, e.g
#     during the execution of movements.
   
#     '''

#     def __init__(self, parent=None):
#         super().__init__(parent)

#         self.state = mesoSPIM_StateSingleton()

#         self.pos_timer = QtCore.QTimer(self)
#         self.pos_timer.timeout.connect(self.report_position)
#         self.pos_timer.start(50)
#         '''
#         Galil-specific code
#         '''
#         from .devices.stages.galil.galilcontrol import StageControlGalil

#         self.x_encodercounts_per_um = self.cfg.xyz_galil_parameters['x_encodercounts_per_um']
#         self.y_encodercounts_per_um = self.cfg.xyz_galil_parameters['y_encodercounts_per_um']
#         self.z_encodercounts_per_um = self.cfg.xyz_galil_parameters['z_encodercounts_per_um']
#         self.f_encodercounts_per_um = self.cfg.f_galil_parameters['f_encodercounts_per_um']

#         ''' Setting up the Galil stages: XYZ '''
#         self.xyz_stage = StageControlGalil(self.cfg.xyz_galil_parameters['port'], [self.x_encodercounts_per_um,
#                                                                                    self.y_encodercounts_per_um,
#                                                                                    self.z_encodercounts_per_um])

#         ''' Setting up the Galil stages: F with two dummy axes.'''
#         self.f_stage = StageControlGalil(self.cfg.f_galil_parameters['port'], [self.x_encodercounts_per_um,
#                                                                                self.y_encodercounts_per_um,
#                                                                                self.f_encodercounts_per_um])
#         '''
#         self.f_stage = StageControlGalil(COMport = self.cfg.f_galil_parameters['COMport'],
#                                         x_encodercounts_per_um = 0,
#                                         y_encodercounts_per_um = 0,
#                                         z_encodercounts_per_um = self.f_encodercounts_per_um)
#         '''

#         '''
#         print('Galil: ', self.xyz_stage.read_position('x'))
#         print('Galil: ', self.xyz_stage.read_position('y'))
#         print('Galil: ', self.xyz_stage.read_position('z'))
#         '''

#         ''' PI-specific code '''
#         from pipython import GCSDevice, pitools

#         self.pitools = pitools

#         ''' Setting up the PI stages '''
#         self.pi = self.cfg.pi_parameters

#         self.controllername = self.cfg.pi_parameters['controllername']
#         self.pi_stages = self.cfg.pi_parameters['stages']
#         # ('M-112K033','L-406.40DG10','M-112K033','M-116.DG','M-406.4PD','NOSTAGE')
#         self.refmode = self.cfg.pi_parameters['refmode']
#         # self.serialnum = ('118015439')  # Wyss Geneva
#         self.serialnum = self.cfg.pi_parameters['serialnum']  # UZH Irchel H45

#         self.pidevice = GCSDevice(self.controllername)
#         self.pidevice.ConnectUSB(serialnum=self.serialnum)

#         ''' PI startup '''

#         ''' with refmode enabled: pretty dangerous
#         pitools.startup(self.pidevice, stages=self.pi_stages, refmode=self.refmode)
#         '''
#         pitools.startup(self.pidevice, stages=self.pi_stages)

#         ''' Setting PI velocities '''
#         self.pidevice.VEL(self.cfg.pi_parameters['velocity'])

#         self.pidevice.FRF(1)
#         print('M-061 Emergency referencing hack: Waiting for referencing move')
#         logger.info('M-061 Emergency referencing hack: Waiting for referencing move')
#         self.block_till_controller_is_ready()
#         print('M-061 Emergency referencing hack done')
#         logger.info('M-061 Emergency referencing hack done')

#     def __del__(self):
#         try:
#             '''Close the Galil connection'''
#             self.xyz_stage.close()
#             self.f_stage.close_stage()
#         except:
#             pass

#     def report_position(self):
#         positions = self.pidevice.qPOS(self.pidevice.axes)

#         '''
#         Ugly workaround to deal with non-responding stage 
#         position reports: Do not update positions in 
#         exceptional circumstances. 
#         '''
#         try:
#             self.x_pos, self.y_pos, self.z_pos = self.xyz_stage.read_position()
#             _, _, self.f_pos = self.f_stage.read_position()
#         except:
#             logger.info('Error while unpacking Galil stage position values')

#         self.theta_pos = positions['1']
#         self.create_position_dict()

#         self.int_x_pos = self.x_pos + self.int_x_pos_offset
#         self.int_y_pos = self.y_pos + self.int_y_pos_offset
#         self.int_z_pos = self.z_pos + self.int_z_pos_offset
#         self.int_f_pos = self.f_pos + self.int_f_pos_offset
#         self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

#         self.create_internal_position_dict()

#         self.sig_position.emit(self.int_position_dict)
#         # print(self.int_position_dict)

#     def move_relative(self, sdict, wait_until_done=False):
#         ''' Galil move relative method

#         Lots of implementation details in here, should be replaced by a facade
#         '''
#         xyz_motion_dict = {}

#         if 'x_rel' in sdict:
#             x_rel = sdict['x_rel']
#             if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
#                 xyz_motion_dict.update({1: int(x_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!')

#         if 'y_rel' in sdict:
#             y_rel = sdict['y_rel']
#             if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
#                 xyz_motion_dict.update({2: int(y_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!')

#         if 'z_rel' in sdict:
#             z_rel = sdict['z_rel']
#             if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
#                 xyz_motion_dict.update({3: int(z_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')

#         if xyz_motion_dict != {}:
#             self.xyz_stage.move_relative(xyz_motion_dict)

#         if 'theta_rel' in sdict:
#             theta_rel = sdict['theta_rel']
#             if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
#                 self.pidevice.MVR({1: theta_rel})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!')

#         if 'f_rel' in sdict:
#             f_rel = sdict['f_rel']
#             if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
#                 self.f_stage.move_relative({3: int(f_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!')

#         if wait_until_done == True:
#             self.f_stage.wait_until_done('Z')
#             self.xyz_stage.wait_until_done('XYZ')
#             self.pitools.waitontarget(self.pidevice)

#     def move_absolute(self, dict, wait_until_done=False):
#         '''
#         Galil move absolute method

#         Lots of implementation details in here, should be replaced by a facade

#         '''
#         xyz_motion_dict = {}

#         if 'x_abs' or 'y_abs' or 'z_abs' in dict:
#             if 'x_abs' in dict:
#                 x_abs = dict['x_abs']
#                 x_abs = x_abs - self.int_x_pos_offset
#                 xyz_motion_dict.update({1: x_abs})

#             if 'y_abs' in dict:
#                 y_abs = dict['y_abs']
#                 y_abs = y_abs - self.int_y_pos_offset
#                 xyz_motion_dict.update({2: y_abs})

#             if 'z_abs' in dict:
#                 z_abs = dict['z_abs']
#                 z_abs = z_abs - self.int_z_pos_offset
#                 xyz_motion_dict.update({3: z_abs})

#         if xyz_motion_dict != {}:
#             self.xyz_stage.move_absolute(xyz_motion_dict)

#         if wait_until_done == True:
#             self.xyz_stage.wait_until_done('XYZ')

#         if 'f_abs' in dict:
#             f_abs = dict['f_abs']
#             f_abs = f_abs - self.int_f_pos_offset
#             if self.f_min < f_abs and self.f_max > f_abs:
#                 ''' Conversion to mm and command emission'''
#                 self.f_stage.move_absolute({3: int(f_abs)})
#             else:
#                 self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!')

#         if 'theta_abs' in dict:
#             theta_abs = dict['theta_abs']
#             theta_abs = theta_abs - self.int_theta_pos_offset
#             if self.theta_min < theta_abs and self.theta_max > theta_abs:
#                 ''' No Conversion to mm !!!! and command emission'''
#                 self.pidevice.MOV({1: theta_abs})
#             else:
#                 self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!')

#         if wait_until_done == True:
#             self.pitools.waitontarget(self.pidevice)

#     def stop(self):
#         self.f_stage.stop(restart_programs=True)
#         self.xyz_stage.stop(restart_programs=True)
#         self.pidevice.STP(noraise=True)

#     def load_sample(self):
#         self.move_absolute({'y_abs': self.cfg.stage_parameters['y_load_position']})

#     def unload_sample(self):
#         self.move_absolute({'y_abs': self.cfg.stage_parameters['y_unload_position']})

#     def block_till_controller_is_ready(self):
#         '''
#         Blocks further execution (especially during referencing moves)
#         till the PI controller returns ready
#         '''
#         blockflag = True
#         while blockflag:
#             if self.pidevice.IsControllerReady():
#                 blockflag = False
#             else:
#                 time.sleep(0.1)

#     def execute_program(self):
#         '''Executes program stored on the Galil controller'''
#         self.f_stage.execute_program()
#         self.xyz_stage.execute_program()


class mesoSPIM_PI_rotz_and_Galil_xyf_Stages(mesoSPIM_Stage):
    '''
    Deprecated?
    Expects following microscope configuration:

    Sample XYF movement: Galil controller with 3 axes
    Z-Movement and Rotation: PI C-884 mercury controller
    '''

    def __init__(self, parent=None):
        super().__init__(parent)

        self.state = mesoSPIM_StateSingleton()

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)
        '''
        Galil-specific code
        '''
        from .devices.stages.galil.galilcontrol import StageControlGalil

        self.x_encodercounts_per_um = self.cfg.xyf_galil_parameters['x_encodercounts_per_um']
        self.y_encodercounts_per_um = self.cfg.xyf_galil_parameters['y_encodercounts_per_um']
        self.f_encodercounts_per_um = self.cfg.xyf_galil_parameters['f_encodercounts_per_um']

        ''' Setting up the Galil stages: XYZ '''
        self.xyf_stage = StageControlGalil(self.cfg.xyf_galil_parameters['port'], [self.x_encodercounts_per_um,
                                                                                   self.y_encodercounts_per_um,
                                                                                   self.f_encodercounts_per_um])

        ''' PI-specific code '''
        from pipython import GCSDevice, pitools

        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters

        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = list(self.cfg.pi_parameters['stages'])
        # ('M-112K033','L-406.40DG10','M-112K033','M-116.DG','M-406.4PD','NOSTAGE')
        self.refmode = self.cfg.pi_parameters['refmode']
        # self.serialnum = ('118015439')  # Wyss Geneva
        self.serialnum = self.cfg.pi_parameters['serialnum']  # UZH Irchel H45

        self.pidevice = GCSDevice(self.controllername)
        self.pidevice.ConnectUSB(serialnum=self.serialnum)

        ''' PI startup '''

        ''' with refmode enabled: pretty dangerous
        pitools.startup(self.pidevice, stages=self.pi_stages, refmode=self.refmode)
        '''
        pitools.startup(self.pidevice, stages=self.pi_stages)

        ''' Setting PI velocities '''
        self.pidevice.VEL(self.cfg.pi_parameters['velocity'])

        ''' Reference movements '''
        print('M-406 Emergency referencing hack: Waiting for referencing move')
        logger.info('M-406 Emergency referencing hack: Waiting for referencing move')
        self.pidevice.FRF(2)
        print('M-406 Emergency referencing hack done')
        logger.info('M-406 Emergency referencing hack done')

    def __del__(self):
        try:
            '''Close the Galil connection'''
            self.xyf_stage.close()
        except:
            pass

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)

        '''
        Ugly workaround to deal with non-responding stage 
        position reports: Do not update positions in 
        exceptional circumstances. 
        '''
        try:
            self.x_pos, self.y_pos, self.f_pos = self.xyf_stage.read_position()
        except:
            logger.info('Error while unpacking Galil stage position values')

        self.z_pos = round(positions['2'] * 1000, 2)
        self.theta_pos = positions['1']
        self.create_position_dict()

        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)
        # print(self.int_position_dict)

    def move_relative(self, sdict, wait_until_done=False):
        ''' Galil move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        xyf_motion_dict = {}

        if 'x_rel' in sdict:
            x_rel = sdict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                xyf_motion_dict.update({1: int(x_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!')

        if 'y_rel' in sdict:
            y_rel = sdict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                xyf_motion_dict.update({2: int(y_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!')

        if 'z_rel' in sdict:
            z_rel = sdict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                z_rel = z_rel / 1000
                self.pidevice.MVR({2: z_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')

        if 'theta_rel' in sdict:
            theta_rel = sdict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({1: theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!')

        if 'f_rel' in sdict:
            f_rel = sdict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                xyf_motion_dict.update({3: int(f_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')

        if xyf_motion_dict != {}:
            self.xyf_stage.move_relative(xyf_motion_dict)

        if wait_until_done == True:
            self.xyf_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)

    def move_absolute(self, dict, wait_until_done=False, use_internal_position=True):
        '''
        Galil move absolute method

        Lots of implementation details in here, should be replaced by a facade

        '''
        if use_internal_position is True:
            x_offset = self.int_x_pos_offset
            y_offset = self.int_y_pos_offset
            z_offset = self.int_z_pos_offset
            f_offset = self.int_f_pos_offset
            theta_offset = self.int_theta_pos_offset
        else:
            x_offset = 0
            y_offset = 0
            z_offset = 0
            f_offset = 0
            theta_offset = 0

        xyf_motion_dict = {}

        if 'x_abs' or 'y_abs' or 'f_abs' in dict:
            if 'x_abs' in dict:
                x_abs = dict['x_abs'] - x_offset
                xyf_motion_dict.update({1: x_abs})

            if 'y_abs' in dict:
                y_abs = dict['y_abs'] - y_offset
                xyf_motion_dict.update({2: y_abs})

            if 'f_abs' in dict:
                f_abs = dict['f_abs'] - f_offset
                xyf_motion_dict.update({3: f_abs})

        if xyf_motion_dict != {}:
            self.xyf_stage.move_absolute(xyf_motion_dict)

        if wait_until_done == True:
            self.xyf_stage.wait_until_done('XYZ')

        if 'z_abs' in dict:
            z_abs = dict['z_abs'] - z_offset
            if self.z_min < z_abs and self.z_max > z_abs:
                ''' Conversion to mm and command emission'''
                z_abs = z_abs / 1000
                self.pidevice.MOV({2: z_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!')

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs'] - theta_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({1: theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!')

        if wait_until_done == True:
            self.xyf_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)

    def stop(self):
        self.xyf_stage.stop(restart_programs=True)
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        self.xyf_stage.move_absolute({2: self.cfg.stage_parameters['y_load_position']})

    def unload_sample(self):
        self.xyf_stage.move_absolute({2: self.cfg.stage_parameters['y_unload_position']})

    def block_till_controller_is_ready(self):
        '''
        Blocks further execution (especially during referencing moves)
        till the PI controller returns ready
        '''
        blockflag = True
        while blockflag:
            if self.pidevice.IsControllerReady():
                blockflag = False
            else:
                time.sleep(0.1)

    def execute_program(self):
        '''Executes program stored on the Galil controller'''
        self.xyf_stage.execute_program()


# class mesoSPIM_PI_rotzf_and_Galil_xy_Stages(mesoSPIM_Stage):
#     '''
#     Deprecated?
#     Expects following microscope configuration:
    
#     Sample XY movement: Galil controller with 2 axes 
#     Z-Movement, F-Movement and Rotation: PI C-884 mercury controller
#     '''

#     def __init__(self, parent=None):
#         super().__init__(parent)

#         self.pos_timer = QtCore.QTimer(self)
#         self.pos_timer.timeout.connect(self.report_position)
#         self.pos_timer.start(50)
#         '''
#         Galil-specific code
#         '''
#         from .devices.stages.galil.galilcontrol import StageControlGalil

#         self.x_encodercounts_per_um = self.cfg.xy_galil_parameters['x_encodercounts_per_um']
#         self.y_encodercounts_per_um = self.cfg.xy_galil_parameters['y_encodercounts_per_um']

#         ''' Setting up the Galil stages: XYZ '''
#         self.xy_stage = StageControlGalil(self.cfg.xy_galil_parameters['port'], [self.x_encodercounts_per_um,
#                                                                                  self.y_encodercounts_per_um])

#         ''' PI-specific code '''
#         from pipython import GCSDevice, pitools

#         self.pitools = pitools

#         ''' Setting up the PI stages '''
#         self.pi = self.cfg.pi_parameters

#         self.controllername = self.cfg.pi_parameters['controllername']
#         self.pi_stages = list(self.cfg.pi_parameters['stages'])
#         # ('M-112K033','L-406.40DG10','M-112K033','M-116.DG','M-406.4PD','NOSTAGE')
#         self.refmode = self.cfg.pi_parameters['refmode']
#         self.serialnum = self.cfg.pi_parameters['serialnum']

#         self.pidevice = GCSDevice(self.controllername)
#         self.pidevice.ConnectUSB(serialnum=self.serialnum)

#         ''' PI startup '''

#         ''' with refmode enabled: pretty dangerous
#         pitools.startup(self.pidevice, stages=self.pi_stages, refmode=self.refmode)
#         '''
#         pitools.startup(self.pidevice, stages=self.pi_stages)

#         ''' Setting PI velocities '''
#         self.pidevice.VEL(self.cfg.pi_parameters['velocity'])

#         print('M-406 Emergency referencing hack: Waiting for referencing move')
#         logger.info('M-406 Emergency referencing hack: Waiting for referencing move')
#         self.pidevice.FRF(2)
#         print('M-406 Emergency referencing hack done')
#         logger.info('M-406 Emergency referencing hack done')

#         print('M-605.2DD Emergency referencing hack: Waiting for referencing move')
#         logger.info('M-605.2DD  Emergency referencing hack: Waiting for referencing move')
#         self.pidevice.FRF(3)
#         print('M-605.2DD Emergency referencing hack done')
#         logger.info('M-605.2DD Emergency referencing hack done')

#         self.block_till_controller_is_ready()

#     def __del__(self):
#         try:
#             '''Close the Galil connection'''
#             self.xy_stage.close()
#         except:
#             pass

#     def report_position(self):
#         positions = self.pidevice.qPOS(self.pidevice.axes)

#         '''
#         Ugly workaround to deal with non-responding stage 
#         position reports: Do not update positions in 
#         exceptional circumstances. 
#         '''
#         try:
#             self.x_pos, self.y_pos = self.xy_stage.read_position()
#         except:
#             logger.info('Error while unpacking Galil stage position values')

#         self.f_pos = round(positions['3'] * 1000, 2)
#         self.z_pos = round(positions['2'] * 1000, 2)
#         self.theta_pos = positions['1']

#         self.create_position_dict()

#         self.int_x_pos = self.x_pos + self.int_x_pos_offset
#         self.int_y_pos = self.y_pos + self.int_y_pos_offset
#         self.int_z_pos = self.z_pos + self.int_z_pos_offset
#         self.int_f_pos = self.f_pos + self.int_f_pos_offset
#         self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

#         self.create_internal_position_dict()

#         self.sig_position.emit(self.int_position_dict)
#         # print(self.int_position_dict)

#     def move_relative(self, sdict, wait_until_done=False):
#         ''' Galil move relative method

#         Lots of implementation details in here, should be replaced by a facade
#         '''
#         xy_motion_dict = {}

#         if 'x_rel' in sdict:
#             x_rel = sdict['x_rel']
#             if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
#                 xy_motion_dict.update({1: int(x_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!')

#         if 'y_rel' in sdict:
#             y_rel = sdict['y_rel']
#             if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
#                 xy_motion_dict.update({2: int(y_rel)})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!')

#         if 'z_rel' in sdict:
#             z_rel = sdict['z_rel']
#             if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
#                 z_rel = z_rel / 1000
#                 self.pidevice.MVR({2: z_rel})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')

#         if 'theta_rel' in sdict:
#             theta_rel = sdict['theta_rel']
#             if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
#                 self.pidevice.MVR({1: theta_rel})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!')

#         if 'f_rel' in sdict:
#             f_rel = sdict['f_rel']
#             if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
#                 f_rel = f_rel / 1000
#                 self.pidevice.MVR({3: f_rel})
#             else:
#                 self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!')

#         if xy_motion_dict != {}:
#             self.xy_stage.move_relative(xy_motion_dict)

#         if wait_until_done == True:
#             self.xy_stage.wait_until_done('XY')
#             self.pitools.waitontarget(self.pidevice)

#     def move_absolute(self, dict, wait_until_done=False):
#         '''
#         Galil move absolute method

#         Lots of implementation details in here, should be replaced by a facade

#         '''
#         xy_motion_dict = {}

#         if 'x_abs' or 'y_abs' in dict:
#             if 'x_abs' in dict:
#                 x_abs = dict['x_abs']
#                 x_abs = x_abs - self.int_x_pos_offset
#                 xy_motion_dict.update({1: x_abs})

#             if 'y_abs' in dict:
#                 y_abs = dict['y_abs']
#                 y_abs = y_abs - self.int_y_pos_offset
#                 xy_motion_dict.update({2: y_abs})

#         if xy_motion_dict != {}:
#             self.xy_stage.move_absolute(xy_motion_dict)

#         if wait_until_done == True:
#             self.xy_stage.wait_until_done('XYZ')

#         if 'f_abs' in dict:
#             f_abs = dict['f_abs']
#             f_abs = f_abs - self.int_f_pos_offset
#             if self.f_min < f_abs and self.f_max > f_abs:
#                 ''' Conversion to mm and command emission'''
#                 f_abs = f_abs / 1000
#                 self.pidevice.MOV({3: f_abs})
#             else:
#                 self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!')

#         if 'z_abs' in dict:
#             z_abs = dict['z_abs']
#             z_abs = z_abs - self.int_z_pos_offset
#             if self.z_min < z_abs and self.z_max > z_abs:
#                 ''' Conversion to mm and command emission'''
#                 z_abs = z_abs / 1000
#                 self.pidevice.MOV({2: z_abs})
#             else:
#                 self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!')

#         if 'theta_abs' in dict:
#             theta_abs = dict['theta_abs']
#             theta_abs = theta_abs - self.int_theta_pos_offset
#             if self.theta_min < theta_abs and self.theta_max > theta_abs:
#                 ''' No Conversion to mm !!!! and command emission'''
#                 self.pidevice.MOV({1: theta_abs})
#             else:
#                 self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!')

#         if wait_until_done == True:
#             self.xy_stage.wait_until_done('XY')
#             self.pitools.waitontarget(self.pidevice)

#     def stop(self):
#         self.xy_stage.stop(restart_programs=True)
#         self.pidevice.STP(noraise=True)

#     def load_sample(self):
#         self.xy_stage.move_absolute({2: self.cfg.stage_parameters['y_load_position']})

#     def unload_sample(self):
#         self.xy_stage.move_absolute({2: self.cfg.stage_parameters['y_unload_position']})

#     def block_till_controller_is_ready(self):
#         '''
#         Blocks further execution (especially during referencing moves)
#         till the PI controller returns ready
#         '''
#         blockflag = True
#         while blockflag:
#             if self.pidevice.IsControllerReady():
#                 blockflag = False
#             else:
#                 time.sleep(0.1)

#     def execute_program(self):
#         '''Executes program stored on the Galil controller'''
#         self.xy_stage.execute_program()


class mesoSPIM_ASI_Tiger_Stage(mesoSPIM_Stage):
    '''
    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
    '''
    sig_pause = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.state = mesoSPIM_StateSingleton()
        from .devices.stages.asi.asicontrol import StageControlASITiger
        
        ''' Setting up the ASI stages '''
        self.asi_parameters = self.cfg.asi_parameters
        self.mesoSPIM2ASIdict = self.asi_parameters['stage_assignment'] # converts mesoSPIM stage to ASI stage designation
        # self.ASI2mesoSPIMdict = {self.mesoSPIM2ASIdict[item] : item for item in self.mesoSPIM2ASIdict} # converts ASI stage designation to mesoSPIM

        self.ttl_cards = self.asi_parameters['ttl_cards']
        self.asi_stages = StageControlASITiger(self.asi_parameters)
        self.asi_stages.sig_pause.connect(self.pause)

        assert hasattr(self.cfg, 'asi_parameters'), "Config file with stage 'TigerASI' must have 'asi_parameters' dict."
        self.ttl_motion_enabled_during_acq = self.cfg.asi_parameters['ttl_motion_enabled']
        self.ttl_motion_currently_enabled = False
        self.set_speed_from_config()
        self.pos_timer.setInterval(250)
        logger.info('ASI stages initialized')
        
    def __del__(self):
        try:
            self.asi_stages.close()
        except:
            pass

    def set_speed_from_config(self):
        if hasattr(self.cfg, 'asi_parameters') and 'speed' in self.cfg.asi_parameters.keys():
            command = 'S'
            for axis, speed in self.cfg.asi_parameters['speed'].items():
                if self.asi_stages.axis_in_config_check(axis):
                    command += ' ' + axis + '=' + str(speed)
                else:
                    logger.error(f'Axis {axis} not in the axes list, check config file for ASI stages')
            command += '\r'
            self.asi_stages._send_command(command.encode('ascii'))
        else:
            print("INFO: 'speed' not found in config file, 'asi_parameters' dictionary, using default values.")

    @QtCore.pyqtSlot(bool)
    def pause(self, boolean):
        state = self.state['state']
        if state == 'run_selected_acquisition' or state == 'run_acquisition_list':
            self.sig_pause.emit(boolean)

    @QtCore.pyqtSlot(dict)
    def log_slice(self, dictionary):
        slice = dictionary['current_image_in_acq']
        self.asi_stages.current_z_slice = slice

    def report_position(self):
        position_dict = self.asi_stages.read_position()
        if position_dict is not None:
            self.x_pos = position_dict[self.mesoSPIM2ASIdict['x']]
            self.y_pos = position_dict[self.mesoSPIM2ASIdict['y']]
            self.z_pos = position_dict[self.mesoSPIM2ASIdict['z']]
            self.f_pos = position_dict[self.mesoSPIM2ASIdict['f']]
            self.theta_pos = position_dict[self.mesoSPIM2ASIdict['theta']]

            self.create_position_dict()

            self.int_x_pos = self.x_pos + self.int_x_pos_offset
            self.int_y_pos = self.y_pos + self.int_y_pos_offset
            self.int_z_pos = self.z_pos + self.int_z_pos_offset
            self.int_f_pos = self.f_pos + self.int_f_pos_offset
            self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

            self.create_internal_position_dict()
            self.sig_position.emit(self.int_position_dict)

    def move_relative(self, sdict, wait_until_done=False):
        ''' ASI move relative method
        Lots of implementation details in here, should be replaced by a facade
        '''
        motion_dict = {}
        if not self.ttl_motion_currently_enabled:
            if 'x_rel' in sdict:
                x_rel = sdict['x_rel']
                if self.x_min < self.x_pos + x_rel < self.x_max:
                    motion_dict.update({self.mesoSPIM2ASIdict['x'] : round(x_rel, 1)})
                else:
                    self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!')

            if 'y_rel' in sdict:
                y_rel = sdict['y_rel']
                if self.y_min < self.y_pos + y_rel < self.y_max:
                    motion_dict.update({self.mesoSPIM2ASIdict['y'] : round(y_rel, 1)})
                else:
                    self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!')

            if 'z_rel' in sdict:
                z_rel = sdict['z_rel']
                if self.z_min < self.z_pos + z_rel < self.z_max:
                    motion_dict.update({self.mesoSPIM2ASIdict['z'] : round(z_rel, 1)})
                else:
                    self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')
            
            if 'theta_rel' in sdict:
                theta_rel = sdict['theta_rel']
                if self.theta_min < self.theta_pos + theta_rel < self.theta_max:
                    ''' 1° equals 1000 cts'''
                    motion_dict.update({self.mesoSPIM2ASIdict['theta'] : int(theta_rel)})
                else:
                    self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!')

            if 'f_rel' in sdict:
                f_rel = sdict['f_rel']
                if self.f_min < self.f_pos + f_rel < self.f_max:
                    motion_dict.update({self.mesoSPIM2ASIdict['f'] : round(f_rel, 1)})
                else:
                    self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!')

            if motion_dict != {}:
                self.asi_stages.move_relative(motion_dict)

            if wait_until_done:
                self.asi_stages.wait_until_done()
    
    def move_absolute(self, dict, wait_until_done=False, use_internal_position=True):
        '''
        ASI move absolute method

        Lots of implementation details in here, should be replaced by a facade
        '''
        if use_internal_position is True:
            x_offset = self.int_x_pos_offset
            y_offset = self.int_y_pos_offset
            z_offset = self.int_z_pos_offset
            f_offset = self.int_f_pos_offset
            theta_offset = self.int_theta_pos_offset
        else:
            x_offset = 0
            y_offset = 0
            z_offset = 0
            f_offset = 0
            theta_offset = 0
        motion_dict = {}
        if 'x_abs' in dict:
            x_abs = dict['x_abs'] - x_offset
            if self.x_min < x_abs < self.x_max:
                motion_dict.update({self.mesoSPIM2ASIdict['x'] : round(x_abs, 1)})
            else:
                logger.error(f"The x-move is outside of min-max range, check your config file, 'x_min' and 'x_max'.")

        if 'y_abs' in dict:
            y_abs = dict['y_abs'] - y_offset
            if self.y_min < y_abs < self.y_max:
                motion_dict.update({self.mesoSPIM2ASIdict['y'] : round(y_abs, 1)})
            else:
                logger.error(f"The y-move is outside of min-max range, check your config file, 'y_min' and 'y_max'.")
                    
        if 'z_abs' in dict:
            z_abs = dict['z_abs'] - z_offset
            if self.z_min < z_abs < self.z_max:
                motion_dict.update({self.mesoSPIM2ASIdict['z'] : round(z_abs, 1)})
            else:
                logger.error(f"The z-move is outside of min-max range, check your config file, 'z_min' and 'z_max'.")

        if 'f_abs' in dict:
            f_abs = dict['f_abs'] - f_offset
            if self.f_min < f_abs < self.f_max:
                motion_dict.update({self.mesoSPIM2ASIdict['f'] : round(f_abs, 1)})
            else:
                logger.error(f"The f-move is outside of min-max range, check your config file, 'f_min' and 'f_max'.")

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs'] - theta_offset
            if self.theta_min < theta_abs < self.theta_max:
                ''' 1° equals 1000 cts'''
                motion_dict.update({self.mesoSPIM2ASIdict['theta'] : int(theta_abs)})
            else:
                logger.error(f"The theta-move is outside of min-max range, check your config file, 'theta_min' and 'theta_max'.")

        if motion_dict:
            self.asi_stages.move_absolute(motion_dict)
        
        if wait_until_done is True:
            self.asi_stages.wait_until_done()
        
    def stop(self):
        self.asi_stages.stop()

    def load_sample(self):
        y_abs = self.cfg.stage_parameters['y_load_position']
        self.move_absolute({'y_abs':round(y_abs)})

    def unload_sample(self):
        y_abs = self.cfg.stage_parameters['y_unload_position']
        self.move_absolute({'y_abs':round(y_abs)})

    def enable_ttl_motion(self, boolean):
        if self.ttl_motion_enabled_during_acq:
            self.asi_stages.enable_ttl_mode(self.ttl_cards, boolean)
            self.ttl_motion_currently_enabled = boolean
            logger.info('TTL Motion currently enabled: '+str(boolean))
            self.state['ttl_movement_enabled_during_acq'] = boolean
        

class mesoSPIM_ASI_MS2000_Stage(mesoSPIM_Stage):
    '''

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.

    This implements an ASI MS2000 controller for a setup with the following configuration
    * ASI X Stage is equivalent to the mesoSPIM z-stage (moved during stacks direction)
    * ASI Y Stage is equivalent to the mesoSPIM y-stage  
    * ASI Z-Stage is equivalent to the mesoSPIM f-stage (focus)

    '''
    sig_pause = QtCore.pyqtSignal(bool)

    def __init__(self, parent = None):
        super().__init__(parent)

        self.state = mesoSPIM_StateSingleton()
        '''
        ASI-specific code
        '''
        from devices.stages.asi.asicontrol import StageControlASITiger
        
        ''' Setting up the ASI stages '''
        self.asi_parameters = self.cfg.asi_parameters
        self.mesoSPIM2ASIdict = self.asi_parameters['stage_assignment'] # converts mesoSPIM stage to ASI stage designation
        # self.ASI2mesoSPIMdict = {self.mesoSPIM2ASIdict[item] : item for item in self.mesoSPIM2ASIdict} # converts ASI stage designation to mesoSPIM

        self.asi_stages = StageControlASITiger(self.asi_parameters)
        self.asi_stages.sig_pause.connect(self.pause)
        self.pos_timer.setInterval(100)

        logger.info('mesoSPIM_Stages: ASI stages initialized')

    def __del__(self):
        try:
            '''Close the ASI connection'''
            self.asi_stages.close()
        except:
            pass

    @QtCore.pyqtSlot(bool)
    def pause(self,boolean):
        state = self.state['state']
        if state == 'run_selected_acquisition' or state == 'run_acquisition_list':
            self.sig_pause.emit(boolean)

    @QtCore.pyqtSlot(dict)
    def log_slice(self, dictionary):
        slice = dictionary['current_image_in_acq']
        self.asi_stages.current_z_slice = slice

    def report_position(self):
        position_dict = self.asi_stages.read_position()
        if position_dict is not None:
            self.y_pos = position_dict[self.mesoSPIM2ASIdict['y']]
            self.z_pos = position_dict[self.mesoSPIM2ASIdict['z']]
            self.f_pos = position_dict[self.mesoSPIM2ASIdict['f']]
            
            self.create_position_dict()

            self.int_y_pos = self.y_pos + self.int_y_pos_offset
            self.int_z_pos = self.z_pos + self.int_z_pos_offset
            self.int_f_pos = self.f_pos + self.int_f_pos_offset

            self.create_internal_position_dict()

            self.sig_position.emit(self.int_position_dict)


    def move_relative(self, sdict, wait_until_done=False):
        ''' ASI move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''

        '''
        Report position 

        '''
        #self.adapt_position_polling_interval_to_state()

        motion_dict = {}

        if 'y_rel' in sdict:
            y_rel = sdict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                motion_dict.update({self.mesoSPIM2ASIdict['y'] : round(y_rel, 1)})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!')

        if 'z_rel' in sdict:
            z_rel = sdict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                motion_dict.update({self.mesoSPIM2ASIdict['z'] : round(z_rel, 1)})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!')
        
        if 'f_rel' in sdict:
            f_rel = sdict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                motion_dict.update({self.mesoSPIM2ASIdict['f'] : round(f_rel, 1)})
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!')

        if motion_dict != {}:
            self.asi_stages.move_relative(motion_dict)

        if wait_until_done is True:
            self.asi_stages.wait_until_done()
    
    def move_absolute(self, dict, wait_until_done=False, use_internal_position=True):
        '''
        ASI move absolute method

        Lots of implementation details in here, should be replaced by a facade
        '''
        if use_internal_position is True:
            x_offset = self.int_x_pos_offset
            y_offset = self.int_y_pos_offset
            z_offset = self.int_z_pos_offset
            f_offset = self.int_f_pos_offset
            theta_offset = self.int_theta_pos_offset
        else:
            x_offset = 0
            y_offset = 0
            z_offset = 0
            f_offset = 0
            theta_offset = 0

        motion_dict = {}

        if 'y_abs' in dict:
            y_abs = dict['y_abs'] - y_offset
            if self.y_min < y_abs and self.y_max > y_abs:
                motion_dict.update({self.mesoSPIM2ASIdict['y'] : round(y_abs, 1)})
                    
        if 'z_abs' in dict:
            z_abs = dict['z_abs'] - z_offset
            if self.z_min < z_abs and self.z_max > z_abs:
                motion_dict.update({self.mesoSPIM2ASIdict['z'] : round(z_abs, 1)})

        if 'f_abs' in dict:
            f_abs = dict['f_abs'] - f_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                motion_dict.update({self.mesoSPIM2ASIdict['f'] : round(f_abs, 1)})

        if motion_dict != {}:
            self.asi_stages.move_absolute(motion_dict)
        
        if wait_until_done is True:
            self.asi_stages.wait_until_done()
        
    def stop(self):
        self.asi_stages.stop()

    def load_sample(self):
        message = 'ASI MS-2000 Stage: Sample loading not implemented!'
        print(message)
        logger.info(message)

    def unload_sample(self):
        message = 'ASI MS-2000 Stage: Sample unloading not implemented!'
        print(message)
        logger.info(message)
