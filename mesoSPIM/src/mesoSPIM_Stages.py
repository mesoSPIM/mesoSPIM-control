'''
mesoSPIM Stage classes
======================
'''
import time

import logging
logger = logging.getLogger(__name__)

from PyQt5 import QtCore
from .mesoSPIM_State import mesoSPIM_StateSingleton

# from .mesoSPIM_State import mesoSPIM_StateSingleton

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
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
    '''

    sig_position = QtCore.pyqtSignal(dict)
    sig_status_message = QtCore.pyqtSignal(str,int)

    def __init__(self, parent = None):
        super().__init__()
        self.parent = parent
        self.cfg = parent.cfg

        #self.state = mesoSPIM_StateSingleton()

        ''' The movement signals are emitted by the mesoSPIM_Core, which in turn
        instantiates the mesoSPIM_Serial thread.

        Therefore, the signals are emitted by the parent of the parent, which
        is slightly confusing and dirty.
        '''

        self.parent.sig_stop_movement.connect(self.stop)
        self.parent.sig_zero_axes.connect(self.zero_axes)
        self.parent.sig_unzero_axes.connect(self.unzero_axes)
        self.parent.sig_load_sample.connect(self.load_sample)
        self.parent.sig_unload_sample.connect(self.unload_sample)
        self.parent.sig_mark_rotation_position.connect(self.mark_rotation_position)

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(20)

        '''Initial setting of all positions

        self.x_pos, self.y_pos etc are the true axis positions, no matter whether
        the stages are zeroed or not.
        '''
        self.x_pos = 0
        self.y_pos = 0
        self.z_pos = 0
        self.f_pos = 0
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
        self.x_rot_position = self.cfg.stage_parameters['x_rot_position']
        self.y_rot_position = self.cfg.stage_parameters['y_rot_position']
        self.z_rot_position = self.cfg.stage_parameters['z_rot_position']
        '''
        Debugging code
        '''
        # self.sig_status_message.connect(lambda string, time: print(string))

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

    def create_position_dict(self):
        self.position_dict = {'x_pos': self.x_pos,
                              'y_pos': self.y_pos,
                              'z_pos': self.z_pos,
                              'f_pos': self.f_pos,
                              'theta_pos': self.theta_pos,
                              }

    def create_internal_position_dict(self):
        self.int_position_dict = {'x_pos': self.int_x_pos,
                                  'y_pos': self.int_y_pos,
                                  'z_pos': self.int_z_pos,
                                  'f_pos': self.int_f_pos,
                                  'theta_pos': self.int_theta_pos,
                                  }

    def report_position(self):
        self.create_position_dict()

        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        # self.state['position'] = self.int_position_dict

        self.sig_position.emit(self.int_position_dict)

    # @QtCore.pyqtSlot(dict)
    def move_relative(self, dict, wait_until_done=False):
        ''' Move relative method '''
        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                self.x_pos = self.x_pos + x_rel
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                self.y_pos = self.y_pos + y_rel
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                self.z_pos = self.z_pos + z_rel
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)

        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.theta_pos = self.theta_pos + theta_rel
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                self.f_pos = self.f_pos + f_rel
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        if wait_until_done == True:
            time.sleep(0.02)

    # @QtCore.pyqtSlot(dict)
    def move_absolute(self, dict, wait_until_done=False):
        ''' Move absolute method '''

        if 'x_abs' in dict:
            x_abs = dict['x_abs']
            x_abs = x_abs - self.int_x_pos_offset
            if self.x_min < x_abs and self.x_max > x_abs:
                self.x_pos = x_abs
            else:
                self.sig_status_message.emit('Absolute movement stopped: X Motion limit would be reached!',1000)

        if 'y_abs' in dict:
            y_abs = dict['y_abs']
            y_abs = y_abs - self.int_y_pos_offset
            if self.y_min < y_abs and self.y_max > y_abs:
                self.y_pos = y_abs
            else:
                self.sig_status_message.emit('Absolute movement stopped: Y Motion limit would be reached!',1000)

        if 'z_abs' in dict:
            z_abs = dict['z_abs']
            z_abs = z_abs - self.int_z_pos_offset
            if self.z_min < z_abs and self.z_max > z_abs:
                self.z_pos = z_abs
            else:
                self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!',1000)

        if 'f_abs' in dict:
            f_abs = dict['f_abs']
            f_abs = f_abs - self.int_f_pos_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                self.f_pos = f_abs
            else:
                self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!',1000)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                self.theta_pos = theta_abs
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)

        if wait_until_done == True:
            time.sleep(3)

    @QtCore.pyqtSlot()
    def stop(self):
        self.sig_status_message.emit('Stopped',0)

    def zero_axes(self, list):
        for axis in list:
            try:
                exec('self.int_'+axis+'_pos_offset = -self.'+axis+'_pos')
            except:
                logger.info('Zeroing of axis: ', axis, 'failed')

    def unzero_axes(self, list):
        for axis in list:
            try:
                exec('self.int_'+axis+'_pos_offset = 0')
            except:
                logger.info('Unzeroing of axis: ', axis, 'failed')

    def load_sample(self):
        self.y_pos = self.cfg.stage_parameters['y_load_position']

    def unload_sample(self):
        self.y_pos = self.cfg.stage_parameters['y_unload_position']

    def mark_rotation_position(self):
        ''' Take the current position and mark it as rotation location '''
        self.x_rot_position = self.x_pos
        self.y_rot_position = self.y_pos
        self.z_rot_position = self.z_pos
        logger.info('Marking new rotation position (absolute coordinates): X: ', self.x_pos, ' Y: ', self.y_pos, ' Z: ', self.z_pos)

    def go_to_rotation_position(self, wait_until_done=False):
        ''' Move to the proper rotation position 
        
        Not implemented in the default
        '''
        print('Going to rotation position: NOT IMPLEMENTED / DEMO MODE')
        logger.info('Going to rotation position: NOT IMPLEMENTED / DEMO MODE')

class mesoSPIM_DemoStage(mesoSPIM_Stage):
    def __init__(self, parent = None):
        super().__init__(parent)

class mesoSPIM_PIstage(mesoSPIM_Stage):
    '''

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        '''
        PI-specific code
        '''
        from pipython import GCSDevice, pitools

        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters

        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = self.cfg.pi_parameters['stages']
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

        ''' Stage 5 referencing hack '''
        # print('Referencing status 3: ', self.pidevice.qFRF(3))
        # print('Referencing status 5: ', self.pidevice.qFRF(5))
        self.pidevice.FRF(5)
        logger.info('mesoSPIM_Stages: M-406 Emergency referencing hack: Waiting for referencing move')
        self.block_till_controller_is_ready()
        logger.info('mesoSPIM_Stages: M-406 Emergency referencing hack done')
        # print('Again: Referencing status 3: ', self.pidevice.qFRF(3))
        # print('Again: Referencing status 5: ', self.pidevice.qFRF(5))

        ''' Stage 5 close to good focus'''
        self.startfocus = self.cfg.stage_parameters['startfocus']
        self.pidevice.MOV(5,self.startfocus/1000)

    def __del__(self):
        try:
            '''Close the PI connection'''
            self.pidevice.unload()
            logger.info('Stage disconnected')
        except:
            logger.info('Error while disconnecting the PI stage')

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)

        self.x_pos = round(positions['1']*1000,2)
        self.y_pos = round(positions['2']*1000,2)
        self.z_pos = round(positions['3']*1000,2)
        self.f_pos = round(positions['5']*1000,2)
        self.theta_pos = positions['4']

        self.create_position_dict()

        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        # self.state['position'] = self.int_position_dict

        self.sig_position.emit(self.int_position_dict)

    def move_relative(self, dict, wait_until_done=False):
        ''' PI move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                x_rel = x_rel/1000
                self.pidevice.MVR({1 : x_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                y_rel = y_rel/1000
                self.pidevice.MVR({2 : y_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                z_rel = z_rel/1000
                self.pidevice.MVR({3 : z_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)

        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({4 : theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                f_rel = f_rel/1000
                self.pidevice.MVR({5 : f_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice)

    def move_absolute(self, dict, wait_until_done=False):
        '''
        PI move absolute method

        Lots of implementation details in here, should be replaced by a facade

        TODO: Also lots of repeating code.
        TODO: DRY principle violated
        '''

        if 'x_abs' in dict:
            x_abs = dict['x_abs']
            x_abs = x_abs - self.int_x_pos_offset
            if self.x_min < x_abs and self.x_max > x_abs:
                ''' Conversion to mm and command emission'''
                x_abs= x_abs/1000
                self.pidevice.MOV({1 : x_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: X Motion limit would be reached!',1000)

        if 'y_abs' in dict:
            y_abs = dict['y_abs']
            y_abs = y_abs - self.int_y_pos_offset
            if self.y_min < y_abs and self.y_max > y_abs:
                ''' Conversion to mm and command emission'''
                y_abs= y_abs/1000
                self.pidevice.MOV({2 : y_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Y Motion limit would be reached!',1000)

        if 'z_abs' in dict:
            z_abs = dict['z_abs']
            z_abs = z_abs - self.int_z_pos_offset
            if self.z_min < z_abs and self.z_max > z_abs:
                ''' Conversion to mm and command emission'''
                z_abs= z_abs/1000
                self.pidevice.MOV({3 : z_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!',1000)

        if 'f_abs' in dict:
            f_abs = dict['f_abs']
            f_abs = f_abs - self.int_f_pos_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                ''' Conversion to mm and command emission'''
                f_abs= f_abs/1000
                self.pidevice.MOV({5 : f_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!',1000)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({4 : theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice)

    def stop(self):
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        y_abs = self.cfg.stage_parameters['y_load_position']/1000
        self.pidevice.MOV({2 : y_abs})

    def unload_sample(self):
        y_abs = self.cfg.stage_parameters['y_unload_position']/1000
        self.pidevice.MOV({2 : y_abs})

    def go_to_rotation_position(self, wait_until_done=False):
        x_abs = self.x_rot_position/1000
        y_abs = self.y_rot_position/1000
        z_abs = self.z_rot_position/1000

        self.pidevice.MOV({1 : x_abs, 2 : y_abs, 3 : z_abs})

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice)

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

class mesoSPIM_PI_xyzf_Stages(mesoSPIM_Stage):
    '''
    Expects following microscope configuration:
        Sample XYZ movement: Physik Instrumente stage with three L-509-type stages and individual C-663 controller.
        F movement: Physik Instrumente C-663 controller and custom stage with stepper motor
        Rotation: not implemented

        All stage controller are of same type and the samle stages work with reference setting.
        Focus stage has reference mode set to off.
            
    Note:
        configs as declared in mesoSPIM_ISP_config.py:
        stage_parameters = {'stage_type' : 'PI_xyz',
                            ...
                            }
        pi_parameters = {'stage_x' : ('L-509.20SD00'),
                         'serialnum_x' : ('**********'),
                         'stage_y' : ('L-509.40SD00'),
                         'serialnum_y' : ('**********'),
                         'stage_z' : ('L-509.20SD00'),
                         'serialnum_z' : ('**********'),
                         'controllername' : ('C-663'),
                         'refmode' : ('FRF'),
                         'stage_f' : ('MESOSPIM_FOCUS'),
                         'serialnum_f' : ('0021550121')                 
                         }
    '''
    
    def __init__(self, parent = None):
        super().__init__(parent)

        # get PI connection tools
        from pipython import GCSDevice, pitools
        self.pitools = pitools

        # get configs
        self.pi = self.cfg.pi_parameters

        print("Connecting stage drive...")

        # Setting up the PI xyzf stages, explicitly set referencing status and get position
        # run stage startup for x axis
        self.pidevice_x = GCSDevice(self.pi['controllername'])
        self.pidevice_x.ConnectUSB(serialnum=self.pi['serialnum_x'])
        pitools.startup(self.pidevice_x, stages=self.pi['stage_x'], refmodes=self.pi['refmode'])
        self.pidevice_x.FRF(1)
        self.wait_for_controller(self.pidevice_x)
        print("x stage ready")

        # run stage startup for y axis
        self.pidevice_y = GCSDevice(self.pi['controllername'])
        self.pidevice_y.ConnectUSB(serialnum=self.pi['serialnum_y'])
        pitools.startup(self.pidevice_y, stages=self.pi['stage_y'], refmodes=self.pi['refmode'])
        self.pidevice_y.FRF(1)
        self.wait_for_controller(self.pidevice_y)
        print("y stage ready")

        # run stage startup for z axis
        self.pidevice_z = GCSDevice(self.pi['controllername'])
        self.pidevice_z.ConnectUSB(serialnum=self.pi['serialnum_z'])
        pitools.startup(self.pidevice_z, stages=self.pi['stage_z'], refmodes=self.pi['refmode'])
        self.pidevice_z.FRF(1)
        self.wait_for_controller(self.pidevice_z)
        print("z stage ready")

        # run stage startup for focus (stage has no reference!)
        self.pidevice_f = GCSDevice(self.pi['controllername'])
        self.pidevice_f.ConnectUSB(serialnum=self.pi['serialnum_f'])
        pitools.startup(self.pidevice_f, stages=self.pi['stage_f'])
        self.pidevice_f.RON({1: 0}) # set reference mode
        #print('referencing mode: {}'.format(self.pidevice_f.qRON()))
        
        # activate servo
        self.pidevice_f.SVO(self.pidevice_f.axes, [True] * len(self.pidevice_f.axes))
        #print('servo state: {}'.format(self.pidevice_f.qSVO()))

        # set/get actual position as home position
        # assumes that starting position is within reasonable distance from optimal focus
        self.pidevice_f.POS({1: 0.0})
        self.pidevice_f.DFH(1)
        # simply report home and actual position (should match)
        #print('home position: {}, actual position: {}'.format(self.pidevice_f.qDFH(), self.pidevice_f.qPOS()))
        self.wait_for_controller(self.pidevice_f)
        print("f stage ready")

        logger.info('mesoSPIM_Stages: C-663-type controller started')


    def wait_for_controller(self, controller):
        # function used during stage setup
        blockflag = True
        while blockflag:
            if controller.IsControllerReady():
                blockflag = False
            else:
                time.sleep(0.1)


    def __del__(self):
        try:
            '''Close the PI connection'''
            self.pidevice_x.unload()
            self.pidevice_y.unload()
            self.pidevice_z.unload()
            self.pidevice_f.unload()
            logger.info('Stages disconnected')
        except:
            logger.info('Error while disconnecting the PI stage')
    
    
    def report_position(self):
        position_x = self.pidevice_x.qPOS(1)[1]  # query single axis
        position_y = self.pidevice_y.qPOS(1)[1]  # query single axis
        position_z = self.pidevice_z.qPOS(1)[1]  # query single axis
        position_f = self.pidevice_f.qPOS(1)[1]  # query single axis
        # print('current position of x axis {} is {:.5f}'.format(1, position_x))
        # print('current position of y axis {} is {:.5f}'.format(1, position_y))
        # print('current position of z axis {} is {:.5f}'.format(1, position_z))        
        # print('current position of f stage {} is {:.5f}'.format(1, position_f))        
        positions = {'1': position_x,
                     '2': position_y,
                     '3': position_z,
                     '4': 0,
                     '5': position_f}
        
        self.x_pos = round(positions['1']*1000,2)
        self.y_pos = round(positions['2']*1000,2)
        self.z_pos = round(positions['3']*1000,2)
        self.f_pos = round(positions['5']*1000,2)
        self.theta_pos = positions['4']

        self.create_position_dict()

        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)


    def move_relative(self, dict, wait_until_done=False):
        ''' PI move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        
        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                x_rel = x_rel/1000
                self.pidevice_x.MVR({1 : x_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                y_rel = y_rel/1000
                self.pidevice_y.MVR({1 : y_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                z_rel = z_rel/1000
                self.pidevice_z.MVR({1 : z_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                f_rel = f_rel/1000
                self.pidevice_f.MVR({1 : f_rel})
                self.pitools.waitontarget(self.pidevice_f) #  not really sure
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        """
        # Currently not implemented for this microscope configuration
        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({4 : theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)
        """

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice_x)
            self.pitools.waitontarget(self.pidevice_y)
            self.pitools.waitontarget(self.pidevice_z)
            self.pitools.waitontarget(self.pidevice_f)


    def move_absolute(self, dict, wait_until_done=False):
        '''
        PI move absolute method

        Lots of implementation details in here, should be replaced by a facade

        TODO: Also lots of repeating code.
        TODO: DRY principle violated
        '''

        if 'x_abs' in dict:
            x_abs = dict['x_abs']
            x_abs = x_abs - self.int_x_pos_offset
            if self.x_min < x_abs and self.x_max > x_abs:
                ''' Conversion to mm and command emission'''
                x_abs= x_abs/1000
                self.pidevice_x.MOV({1 : x_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: X Motion limit would be reached!',1000)

        if 'y_abs' in dict:
            y_abs = dict['y_abs']
            y_abs = y_abs - self.int_y_pos_offset
            if self.y_min < y_abs and self.y_max > y_abs:
                ''' Conversion to mm and command emission'''
                y_abs= y_abs/1000
                self.pidevice_y.MOV({1 : y_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Y Motion limit would be reached!',1000)

        if 'z_abs' in dict:
            z_abs = dict['z_abs']
            z_abs = z_abs - self.int_z_pos_offset
            if self.z_min < z_abs and self.z_max > z_abs:
                ''' Conversion to mm and command emission'''
                z_abs= z_abs/1000
                self.pidevice_z.MOV({1 : z_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!',1000)

        if 'f_abs' in dict:
            f_abs = dict['f_abs']
            f_abs = f_abs - self.int_f_pos_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                ''' Conversion to mm and command emission'''
                f_abs= f_abs/1000
                self.pidevice_f.MOV({1 : f_abs})
                self.pitools.waitontarget(self.pidevice_f) #  not really sure
            else:
                self.sig_status_message.emit('Absolute movement stopped: f Motion limit would be reached!',1000)

        """
        # currently not implemented for this microscope configuration
        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({4 : theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)
        """

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice_x)
            self.pitools.waitontarget(self.pidevice_y)
            self.pitools.waitontarget(self.pidevice_z)
            self.pitools.waitontarget(self.pidevice_f)


    def stop(self):
        self.pidevice_x.STP(noraise=True)
        self.pidevice_y.STP(noraise=True)
        self.pidevice_z.STP(noraise=True)
        self.pidevice_f.STP(noraise=True)


    def load_sample(self):
        y_abs = self.cfg.stage_parameters['y_load_position']/1000
        self.pidevice_y.MOV({1 : y_abs})


    def unload_sample(self):
        y_abs = self.cfg.stage_parameters['y_unload_position']/1000
        self.pidevice_y.MOV({1 : y_abs})


    '''
    # currently not implemented for this microscope configuration
    def go_to_rotation_position(self, wait_until_done=False):
        x_abs = self.x_rot_position/1000
        y_abs = self.y_rot_position/1000
        z_abs = self.z_rot_position/1000

        self.pidevice.MOV({1 : x_abs, 2 : y_abs, 3 : z_abs})

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice)
    '''

class mesoSPIM_GalilStages(mesoSPIM_Stage):
    '''

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.

    Todo: Rotation handling not implemented!
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        '''
        Galil-specific code
        '''
        from src.devices.stages.galil.galilcontrol import StageControlGalil

        self.x_encodercounts_per_um = self.cfg.xyz_galil_parameters['x_encodercounts_per_um']
        self.y_encodercounts_per_um = self.cfg.xyz_galil_parameters['y_encodercounts_per_um']
        self.z_encodercounts_per_um = self.cfg.xyz_galil_parameters['z_encodercounts_per_um']
        self.f_encodercounts_per_um = self.cfg.f_galil_parameters['z_encodercounts_per_um']

        ''' Setting up the Galil stages '''
        self.xyz_stage = StageControlGalil(COMport = self.cfg.xyz_galil_parameters['COMport'],
                                            x_encodercounts_per_um = self.x_encodercounts_per_um,
                                            y_encodercounts_per_um = self.y_encodercounts_per_um,
                                            z_encodercounts_per_um = self.z_encodercounts_per_um)

        self.f_stage = StageControlGalil(COMport = self.cfg.f_galil_parameters['COMport'],
                                        x_encodercounts_per_um = 0,
                                        y_encodercounts_per_um = 0,
                                        z_encodercounts_per_um = self.f_encodercounts_per_um)
        '''
        print('Galil: ', self.xyz_stage.read_position('x'))
        print('Galil: ', self.xyz_stage.read_position('y'))
        print('Galil: ', self.xyz_stage.read_position('z'))
        '''

    def __del__(self):
        try:
            '''Close the Galil connection'''
            self.xyz_stage.close_stage()
            self.f_stage.close_stage()
            logger.info('Galil stages disconnected')
        except:
            logger.info('Error while disconnecting the Galil stage')

    def report_position(self):
        self.x_pos = self.xyz_stage.read_position('x')
        self.y_pos = self.xyz_stage.read_position('y')
        self.z_pos = self.xyz_stage.read_position('z')
        self.f_pos = self.f_stage.read_position('z')
        self.theta_pos = 0

        self.create_position_dict()

        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)

    def move_relative(self, dict, wait_until_done=False):
        ''' Galil move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                self.xyz_stage.move_relative(xrel = int(x_rel))
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                self.xyz_stage.move_relative(yrel = int(y_rel))
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                self.xyz_stage.move_relative(zrel = int(z_rel))
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)

        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
               print('No rotation stage attached')
            else:
               self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                self.f_stage.move_relative(zrel = f_rel)
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        if wait_until_done == True:
            pass


    def move_absolute(self, dict, wait_until_done=False):
        '''
        Galil move absolute method

        Lots of implementation details in here, should be replaced by a facade

        '''
        #print(dict)

        # if ('x_abs', 'y_abs', 'z_abs', 'f_abs') in dict:
        x_abs = dict['x_abs']
        x_abs = x_abs - self.int_x_pos_offset
        y_abs = dict['y_abs']
        y_abs = y_abs - self.int_y_pos_offset
        z_abs = dict['z_abs']
        z_abs = z_abs - self.int_z_pos_offset
        f_abs = dict['f_abs']
        f_abs = f_abs - self.int_f_pos_offset

        self.xyz_stage.move_absolute(xabs=x_abs, yabs=y_abs, zabs=z_abs)
        self.f_stage.move_absolute(zabs=f_abs)

        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')

    # def stop(self):
    #     # self.pidevice.STP(noraise=True)

    # def load_sample(self):
    #     y_abs = self.cfg.stage_parameters['y_load_position']/1000
    #     # self.pidevice.MOV({2 : y_abs})

    # def unload_sample(self):
    #     y_abs = self.cfg.stage_parameters['y_unload_position']/1000
    #     # self.pidevice.MOV({2 : y_abs})

class mesoSPIM_PI_f_rot_and_Galil_xyz_Stages(mesoSPIM_Stage):
    '''

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.

    Todo: Rotation handling not implemented!
    Todo: Rotation axes are hardcoded! (M-605: #5, M-061.PD: #6)
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        #self.state = mesoSPIM_StateSingleton()

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)
        '''
        Galil-specific code
        '''
        from src.devices.stages.galil.galilcontrol import StageControlGalil

        self.x_encodercounts_per_um = self.cfg.xyz_galil_parameters['x_encodercounts_per_um']
        self.y_encodercounts_per_um = self.cfg.xyz_galil_parameters['y_encodercounts_per_um']
        self.z_encodercounts_per_um = self.cfg.xyz_galil_parameters['z_encodercounts_per_um']

        ''' Setting up the Galil stages '''
        self.xyz_stage = StageControlGalil(self.cfg.xyz_galil_parameters['port'],[self.x_encodercounts_per_um,
                                                self.y_encodercounts_per_um,self.z_encodercounts_per_um])
        '''
        self.f_stage = StageControlGalil(COMport = self.cfg.f_galil_parameters['COMport'],
                                        x_encodercounts_per_um = 0,
                                        y_encodercounts_per_um = 0,
                                        z_encodercounts_per_um = self.f_encodercounts_per_um)
        '''
        
        '''
        print('Galil: ', self.xyz_stage.read_position('x'))
        print('Galil: ', self.xyz_stage.read_position('y'))
        print('Galil: ', self.xyz_stage.read_position('z'))
        '''

        ''' PI-specific code '''
        from pipython import GCSDevice, pitools

        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters

        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = self.cfg.pi_parameters['stages']
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

        ''' Stage 5 referencing hack '''
        # print('Referencing status 3: ', self.pidevice.qFRF(3))
        # print('Referencing status 5: ', self.pidevice.qFRF(5))
        self.pidevice.FRF(5)
        print('M-406 Emergency referencing hack: Waiting for referencing move')
        logger.info('M-406 Emergency referencing hack: Waiting for referencing move')
        self.block_till_controller_is_ready()
        print('M-406 Emergency referencing hack done')
        logger.info('M-406 Emergency referencing hack done')
        # print('Again: Referencing status 3: ', self.pidevice.qFRF(3))
        # print('Again: Referencing status 5: ', self.pidevice.qFRF(5))

        ''' Stage 5 close to good focus'''
        self.startfocus = self.cfg.stage_parameters['startfocus']
        self.pidevice.MOV(5,self.startfocus/1000)

    def __del__(self):
        try:
            '''Close the Galil connection'''
            self.xyz_stage.close()
            self.f_stage.close_stage()
            logger.info('Galil stages disconnected')
        except:
            logger.info('Error while disconnecting the Galil stages')

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)

        '''
        Ugly workaround to deal with non-responding stage 
        position reports: Do not update positions in 
        exceptional circumstances. 
        '''
        self.x_pos, self.y_pos, self.z_pos  = self.xyz_stage.read_position()
        self.f_pos = round(positions['5']*1000,2)
        self.theta_pos = positions['6']

        self.create_position_dict()

        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)
        #print(self.int_position_dict)

    def move_relative(self, dict, wait_until_done=False):
        ''' Galil move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        xyz_motion_dict = {}

        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                xyz_motion_dict.update({1:int(x_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                xyz_motion_dict.update({2:int(y_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                xyz_motion_dict.update({3:int(z_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)
        
        if xyz_motion_dict != {}:
            self.xyz_stage.move_relative(xyz_motion_dict)

        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({6 : theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                f_rel = f_rel/1000
                self.pidevice.MVR({5 : f_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)


    def move_absolute(self, dict, wait_until_done=False):
        '''
        Galil move absolute method

        Lots of implementation details in here, should be replaced by a facade

        '''
        xyz_motion_dict = {}

        if 'x_abs' or 'y_abs' or 'z_abs' in dict:
            if 'x_abs' in dict:
                x_abs = dict['x_abs']
                x_abs = x_abs - self.int_x_pos_offset
                xyz_motion_dict.update({1:x_abs})

            if 'y_abs' in dict:
                y_abs = dict['y_abs']
                y_abs = y_abs - self.int_y_pos_offset
                xyz_motion_dict.update({2:y_abs})
                        
            if 'z_abs' in dict:
                z_abs = dict['z_abs']
                z_abs = z_abs - self.int_z_pos_offset
                xyz_motion_dict.update({3:z_abs})
        
        if xyz_motion_dict != {}:
            self.xyz_stage.move_absolute(xyz_motion_dict)
        
        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')
        
        if 'f_abs' in dict:
            f_abs = dict['f_abs']
            f_abs = f_abs - self.int_f_pos_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                ''' Conversion to mm and command emission'''
                f_abs= f_abs/1000
                self.pidevice.MOV({5 : f_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!',1000)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({6 : theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice)

    def stop(self):
        self.xyz_stage.stop(restart_programs=True)
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        self.xyz_stage.move_absolute({1:self.int_x_pos, 2:self.cfg.stage_parameters['y_load_position'], 3:self.int_z_pos})

    def unload_sample(self):
        self.xyz_stage.move_absolute({1:self.int_x_pos, 2:self.cfg.stage_parameters['y_unload_position'], 3:self.int_z_pos})
        
    def go_to_rotation_position(self, wait_until_done=False):
        self.xyz_stage.move_absolute({1:self.x_rot_position, 2:self.y_rot_position, 3:self.z_rot_position})
        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')

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
        self.xyz_stage.execute_program()

class mesoSPIM_PI_rot_and_Galil_xyzf_Stages(mesoSPIM_Stage):
    '''
    Expects following microscope configuration:
    
    Sample XYZ movement: Galil controller with 3 axes 
    F movement: Second Galil controller with a single axis 
    Rotation: PI C-863 mercury controller

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
   
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        #self.state = mesoSPIM_StateSingleton()

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)
        '''
        Galil-specific code
        '''
        from src.devices.stages.galil.galilcontrol import StageControlGalil

        self.x_encodercounts_per_um = self.cfg.xyz_galil_parameters['x_encodercounts_per_um']
        self.y_encodercounts_per_um = self.cfg.xyz_galil_parameters['y_encodercounts_per_um']
        self.z_encodercounts_per_um = self.cfg.xyz_galil_parameters['z_encodercounts_per_um']
        self.f_encodercounts_per_um = self.cfg.f_galil_parameters['f_encodercounts_per_um']

        ''' Setting up the Galil stages: XYZ '''
        self.xyz_stage = StageControlGalil(self.cfg.xyz_galil_parameters['port'],[self.x_encodercounts_per_um,
                                                self.y_encodercounts_per_um,self.z_encodercounts_per_um])

        ''' Setting up the Galil stages: F with two dummy axes.'''
        self.f_stage = StageControlGalil(self.cfg.f_galil_parameters['port'],[self.x_encodercounts_per_um,
                                                self.y_encodercounts_per_um,self.f_encodercounts_per_um])
        '''
        self.f_stage = StageControlGalil(COMport = self.cfg.f_galil_parameters['COMport'],
                                        x_encodercounts_per_um = 0,
                                        y_encodercounts_per_um = 0,
                                        z_encodercounts_per_um = self.f_encodercounts_per_um)
        '''
        
        '''
        print('Galil: ', self.xyz_stage.read_position('x'))
        print('Galil: ', self.xyz_stage.read_position('y'))
        print('Galil: ', self.xyz_stage.read_position('z'))
        '''

        ''' PI-specific code '''
        from pipython import GCSDevice, pitools

        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters

        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = self.cfg.pi_parameters['stages']
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

        self.pidevice.FRF(1)
        print('M-061 Emergency referencing hack: Waiting for referencing move')
        logger.info('M-061 Emergency referencing hack: Waiting for referencing move')
        self.block_till_controller_is_ready()
        print('M-061 Emergency referencing hack done')
        logger.info('M-061 Emergency referencing hack done')
       
        ''' Stage 5 close to good focus'''
        self.startfocus = self.cfg.stage_parameters['startfocus']
        self.f_stage.move_absolute({3: self.startfocus})
        #self.pidevice.MOV(5,self.startfocus/1000)

    def __del__(self):
        try:
            '''Close the Galil connection'''
            self.xyz_stage.close()
            self.f_stage.close_stage()
            logger.info('Galil stages disconnected')
        except:
            logger.info('Error while disconnecting the Galil stages')

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)

        '''
        Ugly workaround to deal with non-responding stage 
        position reports: Do not update positions in 
        exceptional circumstances. 
        '''
        try:
            self.x_pos, self.y_pos, self.z_pos  = self.xyz_stage.read_position()
            _ , _ , self.f_pos = self.f_stage.read_position()
        except:
            logger.info('Error while unpacking Galil stage position values')
            
            self.create_position_dict()
            
        self.theta_pos = positions['1']
        
        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)
        #print(self.int_position_dict)

    def move_relative(self, dict, wait_until_done=False):
        ''' Galil move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        xyz_motion_dict = {}

        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                xyz_motion_dict.update({1:int(x_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                xyz_motion_dict.update({2:int(y_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                xyz_motion_dict.update({3:int(z_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)
        
        if xyz_motion_dict != {}:
            self.xyz_stage.move_relative(xyz_motion_dict)

        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({1 : theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                self.f_stage.move_relative({3:int(f_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.f_stage.wait_until_done('Z')
            self.xyz_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)


    def move_absolute(self, dict, wait_until_done=False):
        '''
        Galil move absolute method

        Lots of implementation details in here, should be replaced by a facade

        '''
        xyz_motion_dict = {}

        if 'x_abs' or 'y_abs' or 'z_abs' in dict:
            if 'x_abs' in dict:
                x_abs = dict['x_abs']
                x_abs = x_abs - self.int_x_pos_offset
                xyz_motion_dict.update({1:x_abs})

            if 'y_abs' in dict:
                y_abs = dict['y_abs']
                y_abs = y_abs - self.int_y_pos_offset
                xyz_motion_dict.update({2:y_abs})
                        
            if 'z_abs' in dict:
                z_abs = dict['z_abs']
                z_abs = z_abs - self.int_z_pos_offset
                xyz_motion_dict.update({3:z_abs})
        
        if xyz_motion_dict != {}:
            self.xyz_stage.move_absolute(xyz_motion_dict)
        
        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')
        
        if 'f_abs' in dict:
            f_abs = dict['f_abs']
            f_abs = f_abs - self.int_f_pos_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                ''' Conversion to mm and command emission'''
                self.f_stage.move_absolute({3:int(f_abs)})
            else:
                self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!',1000)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({1 : theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice)

    def stop(self):
        self.f_stage.stop(restart_programs=True)
        self.xyz_stage.stop(restart_programs=True)
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        self.move_absolute({'y_abs':self.cfg.stage_parameters['y_load_position']})

    def unload_sample(self):
        self.move_absolute({'y_abs':self.cfg.stage_parameters['y_unload_position']})
        
    def go_to_rotation_position(self, wait_until_done=False):
        self.move_absolute({'x_abs':self.x_rot_position, 'y_abs':self.y_rot_position, 'z_abs':self.z_rot_position})
        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')

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
        self.f_stage.execute_program()
        self.xyz_stage.execute_program()

class mesoSPIM_PI_rotz_and_Galil_xyf_Stages(mesoSPIM_Stage):
    '''
    Expects following microscope configuration:
    
    Sample XYF movement: Galil controller with 3 axes 
    Z-Movement and Rotation: PI C-884 mercury controller

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
   
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        #self.state = mesoSPIM_StateSingleton()

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)
        '''
        Galil-specific code
        '''
        from src.devices.stages.galil.galilcontrol import StageControlGalil

        self.x_encodercounts_per_um = self.cfg.xyf_galil_parameters['x_encodercounts_per_um']
        self.y_encodercounts_per_um = self.cfg.xyf_galil_parameters['y_encodercounts_per_um']
        self.f_encodercounts_per_um = self.cfg.xyf_galil_parameters['f_encodercounts_per_um']

        ''' Setting up the Galil stages: XYZ '''
        self.xyf_stage = StageControlGalil(self.cfg.xyf_galil_parameters['port'],[self.x_encodercounts_per_um,
                                                self.y_encodercounts_per_um,self.f_encodercounts_per_um])

        ''' PI-specific code '''
        from pipython import GCSDevice, pitools

        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters

        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = self.cfg.pi_parameters['stages']
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
       
        ''' Stage 5 close to good focus'''
        self.startfocus = self.cfg.stage_parameters['startfocus']
        self.xyf_stage.move_absolute({3: self.startfocus})

    def __del__(self):
        try:
            '''Close the Galil connection'''
            self.xyf_stage.close()
            logger.info('Galil stages disconnected')
        except:
            logger.info('Error while disconnecting the Galil stages')

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)

        '''
        Ugly workaround to deal with non-responding stage 
        position reports: Do not update positions in 
        exceptional circumstances. 
        '''
        try:
            self.x_pos, self.y_pos, self.f_pos  = self.xyf_stage.read_position()
        except:
            logger.info('Error while unpacking Galil stage position values')
            
        self.create_position_dict()

        self.z_pos = round(positions['2']*1000,2)
        self.theta_pos = positions['1']
        
        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)
        #print(self.int_position_dict)

    def move_relative(self, dict, wait_until_done=False):
        ''' Galil move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        xyf_motion_dict = {}

        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                xyf_motion_dict.update({1:int(x_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                xyf_motion_dict.update({2:int(y_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                z_rel = z_rel/1000
                self.pidevice.MVR({2 : z_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)
        
        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({1 : theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                xyf_motion_dict.update({3:int(f_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)

        if xyf_motion_dict != {}:
            self.xyf_stage.move_relative(xyf_motion_dict)

        if wait_until_done == True:
            self.xyf_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)


    def move_absolute(self, dict, wait_until_done=False):
        '''
        Galil move absolute method

        Lots of implementation details in here, should be replaced by a facade

        '''
        xyf_motion_dict = {}

        if 'x_abs' or 'y_abs' or 'f_abs' in dict:
            if 'x_abs' in dict:
                x_abs = dict['x_abs']
                x_abs = x_abs - self.int_x_pos_offset
                xyf_motion_dict.update({1:x_abs})

            if 'y_abs' in dict:
                y_abs = dict['y_abs']
                y_abs = y_abs - self.int_y_pos_offset
                xyf_motion_dict.update({2:y_abs})
                        
            if 'f_abs' in dict:
                f_abs = dict['f_abs']
                f_abs = f_abs - self.int_f_pos_offset
                xyf_motion_dict.update({3:f_abs})
        
        if xyf_motion_dict != {}:
            self.xyf_stage.move_absolute(xyf_motion_dict)
        
        if wait_until_done == True:
            self.xyf_stage.wait_until_done('XYZ')
        
        if 'z_abs' in dict:
            z_abs = dict['z_abs']
            z_abs = z_abs - self.int_z_pos_offset
            if self.z_min < z_abs and self.z_max > z_abs:
                ''' Conversion to mm and command emission'''
                z_abs= z_abs/1000
                self.pidevice.MOV({2 : z_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!',1000)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({1 : theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.xyf_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)

    def stop(self):
        self.xyf_stage.stop(restart_programs=True)
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        self.xyf_stage.move_absolute({2:self.cfg.stage_parameters['y_load_position']})
        
    def unload_sample(self):
        self.xyf_stage.move_absolute({2:self.cfg.stage_parameters['y_unload_position']})
        
    def go_to_rotation_position(self, wait_until_done=False):
        ''' This has to be done in absolute coordinates of the stages to avoid problems with the 
        internal position offset (when the stage is zeroed). '''
        xy_motion_dict = {1:self.x_rot_position, 2: self.y_rot_position}
        self.xyf_stage.move_absolute(xy_motion_dict)
        self.pidevice.MOV({2 : self.z_rot_position/1000})
        
        if wait_until_done == True:
            self.xyf_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)
    
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

### Up for deletion --> also in mesoSPIM serial
class mesoSPIM_PI_rot_and_Galil_xyzf_Stages(mesoSPIM_Stage):
    '''
    Expects following microscope configuration:
    
    Sample XYZ movement: Galil controller with 3 axes 
    F movement: Second Galil controller with a single axis 
    Rotation: PI C-863 mercury controller

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
   
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        #self.state = mesoSPIM_StateSingleton()

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)
        '''
        Galil-specific code
        '''
        from src.devices.stages.galil.galilcontrol import StageControlGalil

        self.x_encodercounts_per_um = self.cfg.xyz_galil_parameters['x_encodercounts_per_um']
        self.y_encodercounts_per_um = self.cfg.xyz_galil_parameters['y_encodercounts_per_um']
        self.z_encodercounts_per_um = self.cfg.xyz_galil_parameters['z_encodercounts_per_um']
        self.f_encodercounts_per_um = self.cfg.f_galil_parameters['f_encodercounts_per_um']

        ''' Setting up the Galil stages: XYZ '''
        self.xyz_stage = StageControlGalil(self.cfg.xyz_galil_parameters['port'],[self.x_encodercounts_per_um,
                                                self.y_encodercounts_per_um,self.z_encodercounts_per_um])

        ''' Setting up the Galil stages: F with two dummy axes.'''
        self.f_stage = StageControlGalil(self.cfg.f_galil_parameters['port'],[self.x_encodercounts_per_um,
                                                self.y_encodercounts_per_um,self.f_encodercounts_per_um])
        '''
        self.f_stage = StageControlGalil(COMport = self.cfg.f_galil_parameters['COMport'],
                                        x_encodercounts_per_um = 0,
                                        y_encodercounts_per_um = 0,
                                        z_encodercounts_per_um = self.f_encodercounts_per_um)
        '''
        
        '''
        print('Galil: ', self.xyz_stage.read_position('x'))
        print('Galil: ', self.xyz_stage.read_position('y'))
        print('Galil: ', self.xyz_stage.read_position('z'))
        '''

        ''' PI-specific code '''
        from pipython import GCSDevice, pitools

        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters

        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = self.cfg.pi_parameters['stages']
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

        self.pidevice.FRF(1)
        print('M-061 Emergency referencing hack: Waiting for referencing move')
        logger.info('M-061 Emergency referencing hack: Waiting for referencing move')
        self.block_till_controller_is_ready()
        print('M-061 Emergency referencing hack done')
        logger.info('M-061 Emergency referencing hack done')
       
        ''' Stage 5 close to good focus'''
        self.startfocus = self.cfg.stage_parameters['startfocus']
        self.f_stage.move_absolute({3: self.startfocus})
        #self.pidevice.MOV(5,self.startfocus/1000)

    def __del__(self):
        try:
            '''Close the Galil connection'''
            self.xyz_stage.close()
            self.f_stage.close_stage()
            logger.info('Galil stages disconnected')
        except:
            logger.info('Error while disconnecting the Galil stages')

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)

        '''
        Ugly workaround to deal with non-responding stage 
        position reports: Do not update positions in 
        exceptional circumstances. 
        '''
        try:
            self.x_pos, self.y_pos, self.z_pos  = self.xyz_stage.read_position()
            _ , _ , self.f_pos = self.f_stage.read_position()
        except:
            logger.info('Error while unpacking Galil stage position values')
            
            self.create_position_dict()
            
        self.theta_pos = positions['1']
        
        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)
        #print(self.int_position_dict)

    def move_relative(self, dict, wait_until_done=False):
        ''' Galil move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        xyz_motion_dict = {}

        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                xyz_motion_dict.update({1:int(x_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                xyz_motion_dict.update({2:int(y_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                xyz_motion_dict.update({3:int(z_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)
        
        if xyz_motion_dict != {}:
            self.xyz_stage.move_relative(xyz_motion_dict)

        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({1 : theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                self.f_stage.move_relative({3:int(f_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.f_stage.wait_until_done('Z')
            self.xyz_stage.wait_until_done('XYZ')
            self.pitools.waitontarget(self.pidevice)


    def move_absolute(self, dict, wait_until_done=False):
        '''
        Galil move absolute method

        Lots of implementation details in here, should be replaced by a facade

        '''
        xyz_motion_dict = {}

        if 'x_abs' or 'y_abs' or 'z_abs' in dict:
            if 'x_abs' in dict:
                x_abs = dict['x_abs']
                x_abs = x_abs - self.int_x_pos_offset
                xyz_motion_dict.update({1:x_abs})

            if 'y_abs' in dict:
                y_abs = dict['y_abs']
                y_abs = y_abs - self.int_y_pos_offset
                xyz_motion_dict.update({2:y_abs})
                        
            if 'z_abs' in dict:
                z_abs = dict['z_abs']
                z_abs = z_abs - self.int_z_pos_offset
                xyz_motion_dict.update({3:z_abs})
        
        if xyz_motion_dict != {}:
            self.xyz_stage.move_absolute(xyz_motion_dict)
        
        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')
        
        if 'f_abs' in dict:
            f_abs = dict['f_abs']
            f_abs = f_abs - self.int_f_pos_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                ''' Conversion to mm and command emission'''
                self.f_stage.move_absolute({3:int(f_abs)})
            else:
                self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!',1000)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({1 : theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.pitools.waitontarget(self.pidevice)

    def stop(self):
        self.f_stage.stop(restart_programs=True)
        self.xyz_stage.stop(restart_programs=True)
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        self.move_absolute({'y_abs':self.cfg.stage_parameters['y_load_position']})

    def unload_sample(self):
        self.move_absolute({'y_abs':self.cfg.stage_parameters['y_unload_position']})
        
    def go_to_rotation_position(self, wait_until_done=False):
        self.move_absolute({'x_abs':self.x_rot_position, 'y_abs':self.y_rot_position, 'z_abs':self.z_rot_position})
        if wait_until_done == True:
            self.xyz_stage.wait_until_done('XYZ')

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
        self.f_stage.execute_program()
        self.xyz_stage.execute_program()

class mesoSPIM_PI_rotzf_and_Galil_xy_Stages(mesoSPIM_Stage):
    '''
    Expects following microscope configuration:
    
    Sample XY movement: Galil controller with 2 axes 
    Z-Movement, F-Movement and Rotation: PI C-884 mercury controller

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_zero = pyqtSignal(list)
        sig_unzero = pyqtSignal(list)
        sig_stop_movement = pyqtSignal()
        sig_mark_rotation_position = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
   
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)
        '''
        Galil-specific code
        '''
        from src.devices.stages.galil.galilcontrol import StageControlGalil

        self.x_encodercounts_per_um = self.cfg.xy_galil_parameters['x_encodercounts_per_um']
        self.y_encodercounts_per_um = self.cfg.xy_galil_parameters['y_encodercounts_per_um']

        ''' Setting up the Galil stages: XYZ '''
        self.xy_stage = StageControlGalil(self.cfg.xy_galil_parameters['port'],[self.x_encodercounts_per_um,
                                                self.y_encodercounts_per_um])

        ''' PI-specific code '''
        from pipython import GCSDevice, pitools

        self.pitools = pitools

        ''' Setting up the PI stages '''
        self.pi = self.cfg.pi_parameters

        self.controllername = self.cfg.pi_parameters['controllername']
        self.pi_stages = self.cfg.pi_parameters['stages']
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
        
        print('M-406 Emergency referencing hack: Waiting for referencing move')
        logger.info('M-406 Emergency referencing hack: Waiting for referencing move')
        self.pidevice.FRF(2)
        print('M-406 Emergency referencing hack done')
        logger.info('M-406 Emergency referencing hack done')

        print('M-605.2DD Emergency referencing hack: Waiting for referencing move')
        logger.info('M-605.2DD  Emergency referencing hack: Waiting for referencing move')
        self.pidevice.FRF(3)
        print('M-605.2DD Emergency referencing hack done')
        logger.info('M-605.2DD Emergency referencing hack done')

        self.block_till_controller_is_ready()

        ''' Stage 3 close to good focus'''
        self.startfocus = self.cfg.stage_parameters['startfocus']
        self.pidevice.MOV(3,self.startfocus/1000)

    def __del__(self):
        try:
            '''Close the Galil connection'''
            self.xy_stage.close()
            logger.info('Galil stages disconnected')
        except:
            logger.info('Error while disconnecting the Galil stages')

    def report_position(self):
        positions = self.pidevice.qPOS(self.pidevice.axes)

        '''
        Ugly workaround to deal with non-responding stage 
        position reports: Do not update positions in 
        exceptional circumstances. 
        '''
        try:
            self.x_pos, self.y_pos  = self.xy_stage.read_position()
        except:
            logger.info('Error while unpacking Galil stage position values')
            
        
        self.f_pos = round(positions['3']*1000,2)
        self.z_pos = round(positions['2']*1000,2)
        self.theta_pos = positions['1']

        self.create_position_dict()
        
        self.int_x_pos = self.x_pos + self.int_x_pos_offset
        self.int_y_pos = self.y_pos + self.int_y_pos_offset
        self.int_z_pos = self.z_pos + self.int_z_pos_offset
        self.int_f_pos = self.f_pos + self.int_f_pos_offset
        self.int_theta_pos = self.theta_pos + self.int_theta_pos_offset

        self.create_internal_position_dict()

        self.sig_position.emit(self.int_position_dict)
        #print(self.int_position_dict)

    def move_relative(self, dict, wait_until_done=False):
        ''' Galil move relative method

        Lots of implementation details in here, should be replaced by a facade
        '''
        xy_motion_dict = {}

        if 'x_rel' in dict:
            x_rel = dict['x_rel']
            if self.x_min < self.x_pos + x_rel and self.x_max > self.x_pos + x_rel:
                xy_motion_dict.update({1:int(x_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: X Motion limit would be reached!',1000)

        if 'y_rel' in dict:
            y_rel = dict['y_rel']
            if self.y_min < self.y_pos + y_rel and self.y_max > self.y_pos + y_rel:
                xy_motion_dict.update({2:int(y_rel)})
            else:
                self.sig_status_message.emit('Relative movement stopped: Y Motion limit would be reached!',1000)

        if 'z_rel' in dict:
            z_rel = dict['z_rel']
            if self.z_min < self.z_pos + z_rel and self.z_max > self.z_pos + z_rel:
                z_rel = z_rel/1000
                self.pidevice.MVR({2 : z_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: z Motion limit would be reached!',1000)
        
        if 'theta_rel' in dict:
            theta_rel = dict['theta_rel']
            if self.theta_min < self.theta_pos + theta_rel and self.theta_max > self.theta_pos + theta_rel:
                self.pidevice.MVR({1 : theta_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: theta Motion limit would be reached!',1000)

        if 'f_rel' in dict:
            f_rel = dict['f_rel']
            if self.f_min < self.f_pos + f_rel and self.f_max > self.f_pos + f_rel:
                f_rel = f_rel/1000
                self.pidevice.MVR({3 : f_rel})
            else:
                self.sig_status_message.emit('Relative movement stopped: f Motion limit would be reached!',1000)

        if xy_motion_dict != {}:
            self.xy_stage.move_relative(xy_motion_dict)

        if wait_until_done == True:
            self.xy_stage.wait_until_done('XY')
            self.pitools.waitontarget(self.pidevice)


    def move_absolute(self, dict, wait_until_done=False):
        '''
        Galil move absolute method

        Lots of implementation details in here, should be replaced by a facade

        '''
        xy_motion_dict = {}

        if 'x_abs' or 'y_abs'in dict:
            if 'x_abs' in dict:
                x_abs = dict['x_abs']
                x_abs = x_abs - self.int_x_pos_offset
                xy_motion_dict.update({1:x_abs})

            if 'y_abs' in dict:
                y_abs = dict['y_abs']
                y_abs = y_abs - self.int_y_pos_offset
                xy_motion_dict.update({2:y_abs})
                        
        if xy_motion_dict != {}:
            self.xy_stage.move_absolute(xy_motion_dict)
        
        if wait_until_done == True:
            self.xy_stage.wait_until_done('XYZ')

        if 'f_abs' in dict:
            f_abs = dict['f_abs']
            f_abs = f_abs - self.int_f_pos_offset
            if self.f_min < f_abs and self.f_max > f_abs:
                ''' Conversion to mm and command emission'''
                f_abs= f_abs/1000
                self.pidevice.MOV({3 : f_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: F Motion limit would be reached!',1000)
        
        if 'z_abs' in dict:
            z_abs = dict['z_abs']
            z_abs = z_abs - self.int_z_pos_offset
            if self.z_min < z_abs and self.z_max > z_abs:
                ''' Conversion to mm and command emission'''
                z_abs= z_abs/1000
                self.pidevice.MOV({2 : z_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Z Motion limit would be reached!',1000)

        if 'theta_abs' in dict:
            theta_abs = dict['theta_abs']
            theta_abs = theta_abs - self.int_theta_pos_offset
            if self.theta_min < theta_abs and self.theta_max > theta_abs:
                ''' No Conversion to mm !!!! and command emission'''
                self.pidevice.MOV({1 : theta_abs})
            else:
                self.sig_status_message.emit('Absolute movement stopped: Theta Motion limit would be reached!',1000)

        if wait_until_done == True:
            self.xy_stage.wait_until_done('XY')
            self.pitools.waitontarget(self.pidevice)

    def stop(self):
        self.xy_stage.stop(restart_programs=True)
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        self.xy_stage.move_absolute({2:self.cfg.stage_parameters['y_load_position']})
        
    def unload_sample(self):
        self.xy_stage.move_absolute({2:self.cfg.stage_parameters['y_unload_position']})
        
    def go_to_rotation_position(self, wait_until_done=False):
        ''' This has to be done in absolute coordinates of the stages to avoid problems with the 
        internal position offset (when the stage is zeroed). '''
        xy_motion_dict = {1:self.x_rot_position, 2: self.y_rot_position}
        self.xy_stage.move_absolute(xy_motion_dict)
        self.pidevice.MOV({2 : self.z_rot_position/1000})
        
        if wait_until_done == True:
            self.xy_stage.wait_until_done('XY')
            self.pitools.waitontarget(self.pidevice)
    
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
        self.xy_stage.execute_program()