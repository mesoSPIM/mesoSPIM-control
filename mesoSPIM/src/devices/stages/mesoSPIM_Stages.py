'''
mesoSPIM Stage classes
======================
'''

from PyQt5 import QtCore

class mesoSPIM_Stage(QtCore.QObject):
    '''

    It is expected that the parent class has the following signals:
        sig_move_relative = pyqtSignal(dict)
        sig_move_relative_and_wait_until_done = pyqtSignal(dict)
        sig_move_absolute = pyqtSignal(dict)
        sig_move_absolute_and_wait_until_done = pyqtSignal(dict)
        sig_stop_movement = pyqtSignal()

    Also contains a QTimer that regularily sends position updates, e.g
    during the execution of movements.
    '''

    sig_position = QtCore.pyqtSignal(dict)

    def __init__(self, parent = None):
        super().__init__()
        self.parent = parent
        self.cfg = parent.cfg

        self.parent.sig_move_relative.connect(self.sig_move_relative)
        self.parent.sig_move_relative_and_wait_until_done.connect(self.move_relative)

        self.pos_timer = QtCore.QTimer(self)
        self.pos_timer.timeout.connect(self.report_position)
        self.pos_timer.start(50)

    def set_state_parameter(self, key, value):
        '''
        Sets the state of the parent (in most cases, mesoSPIM_MainWindow)

        In order to do this, a QMutexLocker from the parent has to be acquired

        Args:
            key (str): State dict key
            value (str, float, int): Value to set
        '''
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                self.parent.state[key]=value
                self.sig_state_updated.emit()
            else:
                print('Set state parameters failed: Key ', key, 'not in state dictionary!')

    def move_relative(self, dict, wait_until_done=False):
        '''
        Executes a relative movement.

        Args:
            dict (dict): Movement dictionary in the form: {'x_rel':230,'y_rel':0,'z_rel':0,'f_rel':0,'theta_rel':0}


        '''

    def move_absolute(self):
        pass

    def report_position(self):
        pass

class mesoSPIM_DemoStage(mesoSPIM_Stage):
    def __init__(self, config, parent = None):
        super().__init__(config, parent)

class mesoSPIM_PIStage(mesoSPIM_Stage):
    def __init__(self, config, parent = None):
        super().__init__(config, parent)
