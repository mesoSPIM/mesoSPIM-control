'''
mesoSPIM Stage classes
======================
'''
import time

from PyQt5 import QtCore

from pipython import GCSDevice, pitools

from .mesoSPIM_State import mesoSPIM_StateSingleton

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
    sig_status_message = QtCore.pyqtSignal(str,int)

    def __init__(self, parent = None):
        super().__init__()
        self.parent = parent
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        ''' The movement signals are emitted by the mesoSPIM_Core, which in turn
        instantiates the mesoSPIM_Serial thread.

        Therefore, the signals are emitted by the parent of the parent, which
        is slightly confusing and dirty.
        '''

        self.parent.sig_move_relative.connect(lambda dict: self.move_relative(dict))
        self.parent.sig_move_relative_and_wait_until_done.connect(lambda dict: self.move_relative(dict, wait_until_done=True), type=3)
        self.parent.sig_move_absolute.connect(lambda dict: self.move_absolute(dict))
        self.parent.sig_move_absolute_and_wait_until_done.connect(lambda dict, time: self.move_absolute(dict, wait_until_done=True), type=3)
        self.parent.sig_stop_movement.connect(self.stop)
        self.parent.sig_zero_axes.connect(self.zero_axes)
        self.parent.sig_unzero_axes.connect(self.unzero_axes)
        self.parent.sig_load_sample.connect(self.load_sample)
        self.parent.sig_unload_sample.connect(self.unload_sample)

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

        '''
        Debugging code
        '''
        self.sig_status_message.connect(lambda string, time: print(string))

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

        self.state['position'] = self.int_position_dict

        self.sig_position.emit(self.int_position_dict)

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
            self.blockSignals(True)
            time.sleep(0.02)
            self.blockSignals(False)

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
            self.blockSignals(True)
            time.sleep(1)
            self.blockSignals(False)

    def stop(self):
        self.sig_status_message.emit('Stopped')

    def zero_axes(self, list):
        for axis in list:
            try:
                exec('self.int_'+axis+'_pos_offset = -self.'+axis+'_pos')
            except:
                print('Zeroing of axis: ', axis, 'failed')

    def unzero_axes(self, list):
        for axis in list:
            try:
                exec('self.int_'+axis+'_pos_offset = 0')
            except:
                print('Unzeroing of axis: ', axis, 'failed')

    def load_sample(self):
        self.y_pos = self.cfg.stage_parameters['y_load_position']

    def unload_sample(self):
        self.y_pos = self.cfg.stage_parameters['y_unload_position']

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

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
    '''

    def __init__(self, parent = None):
        super().__init__(parent)

        '''
        PI-specific code
        '''

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
        print('Referencing status 3: ', self.pidevice.qFRF(3))
        print('Referencing status 5: ', self.pidevice.qFRF(5))
        self.pidevice.FRF(5)
        print('M-406 Emergency referencing hack: Waiting for referencing move')
        self.block_till_controller_is_ready()
        print('M-406 Emergency referencing hack done')
        print('Again: Referencing status 3: ', self.pidevice.qFRF(3))
        print('Again: Referencing status 5: ', self.pidevice.qFRF(5))

        ''' Stage 5 close to good focus'''
        self.startfocus = self.cfg.stage_parameters['startfocus']
        self.pidevice.MOV(5,self.startfocus/1000)

    def __del__(self):
        try:
            '''Close the PI connection'''
            self.pidevice.unload()
            print('Stage disconnected')
        except:
            print('Error while disconnecting the PI stage')

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

        self.state['position'] = self.int_position_dict

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
            self.blockSignals(True)
            pitools.waitontarget(self.pidevice)
            self.blockSignals(False)

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
            self.blockSignals(True)
            pitools.waitontarget(self.pidevice)
            self.blockSignals(False)

    def stop(self):
        self.pidevice.STP(noraise=True)

    def load_sample(self):
        y_abs = self.cfg.stage_parameters['y_load_position']/1000
        self.pidevice.MOV({2 : y_abs})

    def unload_sample(self):
        y_abs = self.cfg.stage_parameters['y_unload_position']/1000
        self.pidevice.MOV({2 : y_abs})

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
