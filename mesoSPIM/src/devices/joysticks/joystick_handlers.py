'''
Contains the joystick handlers

Because the signals emitted can only be processed when a QEventLoop is running, you
need something with an eventloop (e.g. a QApplication) even for testing.
'''
from PyQt5 import QtCore

from .logitech import FarmSimulatorSidePanel

class mesoSPIM_JoystickHandler(QtCore.QObject):

    def __init__(self, parent = None):
        super().__init__()
        # QtCore.QObject.__init__(self)

        ''' parent is the window '''
        self.joystick = FarmSimulatorSidePanel()

        self.joystick.button_pressed.connect(self.button_handler)
        self.joystick.mode_changed.connect(self.mode_handler)
        self.joystick.axis_moved.connect(self.axis_handler)

    @QtCore.pyqtSlot(int)
    def button_handler(self, button_id):
        print('Button pressed: ', button_id)

    @QtCore.pyqtSlot(str)
    def mode_handler(self, str):
        print('New joystick mode: ', str)

    @QtCore.pyqtSlot(int, int)
    def axis_handler(self, axis_id, value):
        print('Axis: ', axis_id, ',Value: ', value)

    ### What needs to be done here
