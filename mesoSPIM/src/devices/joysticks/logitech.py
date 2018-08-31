'''
Logitech Joystick Classes

pywinusb.hid spawns another thread for joystick event handling which might cause
problems.

Because the signals emitted can only be processed when a QEventLoop is running,
you need something with an eventloop (e.g. a QApplication) even for testing.
'''
from PyQt5 import QtCore

import pywinusb.hid as hid

class FarmSimulatorSidePanel(QtCore.QObject):
    button_pressed = QtCore.pyqtSignal(int) # <-- allows handling of buttons
    axis_moved = QtCore.pyqtSignal(int, int) # <-- axis, value
    mode_changed = QtCore.pyqtSignal(str) # <-- Modal switching (XY/ZF mode)

    start_timer =  QtCore.pyqtSignal(int) # <-- timer id, value to emit
    stop_timer = QtCore.pyqtSignal(int) # <-- timer id

    def __init__(self):
        super().__init__()
        '''
        Setting up the joystick using an HID filter for the side panel values
        '''
        self.hid_filter = hid.HidDeviceFilter(vendor_id = 0x0738, product_id = 0x2218)
        self.hid_device = self.hid_filter.get_devices()
        self.joystick = self.hid_device[0]

        self.joystick.open()
        self.joystick.set_raw_data_handler(self.farm_panel_handler)

        self.mode = 'undefined'
        self.mode_changed.emit(self.mode)

        self.start_timer.connect(self.start_axis_timer)
        self.stop_timer.connect(self.stop_axis_timer)

        '''
        One problem with the joystick is that it stops sending packages when the
        maximum tip/tilt is reached. To circumvent the motion to be stopped,
        a QTimer is used to periodically trigger movement in the same direction.

        joystick_timer_start/stop are helper methods.
        '''
        self.timeout_interval = 25
        self.axis1_timer = QtCore.QTimer(self)
        self.axis2_timer = QtCore.QTimer(self)
        self.axis3_timer = QtCore.QTimer(self)
        self.axis4_timer = QtCore.QTimer(self)
        self.axis5_timer = QtCore.QTimer(self)
        self.axis6_timer = QtCore.QTimer(self)

        self.axis1_value = 0
        self.axis2_value = 0
        self.axis3_value = 0
        self.axis4_value = 0
        self.axis5_value = 0
        self.axis6_value = 0

        self.axis1_timer.timeout.connect(lambda: self.axis_moved.emit(1, self.axis1_value))
        self.axis2_timer.timeout.connect(lambda: self.axis_moved.emit(2, self.axis2_value))
        self.axis3_timer.timeout.connect(lambda: self.axis_moved.emit(3, self.axis3_value))
        self.axis4_timer.timeout.connect(lambda: self.axis_moved.emit(4, self.axis4_value))
        self.axis5_timer.timeout.connect(lambda: self.axis_moved.emit(5, self.axis5_value))
        self.axis6_timer.timeout.connect(lambda: self.axis_moved.emit(6, self.axis6_value))

    def start_axis_timer(self, axis):
        value = exec('self.axis'+str(axis)+'_value')
        exec('self.axis'+str(axis)+'_timer.start(self.timeout_interval)')

    def stop_axis_timer(self, axis):
        exec('self.axis'+str(axis)+'_timer.stop()')

    def __del__(self):
        try:
            self.joystick.close()
        except:
            print('Closing HID device failed')

    def sample_handler(self, data):
        print("Raw data: {0}".format(data))
        print(data[1])

    def get_bin(self, x, n=0):
        """
        Get the binary representation of x.

        Parameters
        ----------
        x : int
        n : int
            Minimum number of digits. If x needs less digits in binary, the rest
            is filled with zeros.

        Returns
        -------
        str
        """
        return format(x, 'b').zfill(n)

    def farm_panel_handler(self, data):
        '''Buttons 1 to 8'''
        self.group_1to8 = data[1]

        self.group_1to8_string = self.get_bin(self.group_1to8,8)
        '''Catch only events which are different from Off-events'''
        if self.group_1to8_string != '00000000':
            button = 8 - self.group_1to8_string.find('1')
            self.button_pressed.emit(button)

        self.group_9to16 = data[2]
        self.group_9to16_string = self.get_bin(self.group_9to16,8)
        '''Catch only events which are different from Off-events'''
        if self.group_9to16_string != '00000000':
            button = 16 - self.group_9to16_string.find('1')
            self.button_pressed.emit(button)

        self.group_17to24 = data[3]
        self.group_17to24_string = self.get_bin(self.group_17to24,8)
        '''Catch only events which are different from Off-events'''
        if self.group_17to24_string != '00000000':
            button = 24 - self.group_17to24_string.find('1')
            self.button_pressed.emit(button)

        self.group_25to29 = data[4]
        self.group_25to29_string = self.get_bin(self.group_25to29,8)
        '''Catch only events which are different from Off-events'''
        if self.group_25to29_string != '00000000':
            index = self.group_25to29_string.find('1')
            if index == 0:
                self.button_pressed.emit(29)
            elif index == 4:
                self.button_pressed.emit(28)
            else:
                button = 32-index
                self.button_pressed.emit(button)

        '''Joystick handling:

        Stop the joystick timer - a QTimer can be stopped even though it was never
        started. This allows every new arriving HID package to stop the
        persistent sending of messages.
        '''
        self.handle_axis_value_changes(1,'123',5,data)
        self.handle_axis_value_changes(2,'123',6,data)
        self.handle_axis_value_changes(3,'123',7,data)
        self.handle_axis_value_changes(4,'456',8,data)
        self.handle_axis_value_changes(5,'456',9,data)
        self.handle_axis_value_changes(6,'456',10,data)

    def handle_axis_value_changes(self, axis_id, axis_group, data_group, data):
        value = data[data_group]
        if value != 128:
            if self.mode != axis_group:
                self.mode_changed.emit(axis_group)

            if value-128 == -128 or value-128 == 127:
                ''' Assign a certain axis the min or max value '''
                exec('self.axis'+str(axis_id)+'_value = value')
                ''' Start timers. Because this is executed from
                another thread, a signal has to be used here.'''
                self.start_timer.emit(axis_id)
                self.axis_moved.emit(axis_id, value)
            else:
                self.stop_timer.emit(axis_id)
                self.axis_moved.emit(axis_id, value)
