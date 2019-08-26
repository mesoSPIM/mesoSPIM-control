'''
Logitech Joystick Classes

pywinusb.hid spawns another thread for joystick event handling which might cause
problems.

Because the signals emitted can only be processed when a QEventLoop is running,
you need something with an eventloop (e.g. a QApplication) even for testing.
'''
from PyQt5 import QtCore

class FarmSimulatorSidePanel(QtCore.QObject):
    '''


    The joystick is set up using the pyqinusb package by using an HidDeviceFilter
    for the side panel values.

    Axis numbers are 0-indexed as per Python convention, i.e. the 6 axes are
    designated "0" to "5".

    Signals:
        sig_button_pressed = QtCore.pyqtSignal(int) # <-- allows handling of buttons
        sig_axis_moved = QtCore.pyqtSignal(int, int) # <-- axis, value
        sig_mode_changed = QtCore.pyqtSignal(str) # <-- Modal switching (XY/ZF mode)
        sig_start_timer =  QtCore.pyqtSignal(int) # <-- timer id, value to emit
        sig_stop_timer = QtCore.pyqtSignal(int) # <-- timer id

    Attributes:
        mode (str): Joysticks can have different modes (e.g. whether analog axes 0-2
                    or 3-5 are selected). This is represented in this attribute.

    '''
    sig_button_pressed = QtCore.pyqtSignal(int) # <-- allows handling of buttons
    sig_axis_moved = QtCore.pyqtSignal(int, int) # <-- axis, value
    sig_mode_changed = QtCore.pyqtSignal(str) # <-- Modal switching (XY/ZF mode)
    sig_start_timer =  QtCore.pyqtSignal(int) # <-- timer id, value to emit
    sig_stop_timer = QtCore.pyqtSignal(int) # <-- timer id

    def __init__(self):
        super().__init__()

        import pywinusb.hid as hid

        self.hid_filter = hid.HidDeviceFilter(vendor_id = 0x0738, product_id = 0x2218)
        self.hid_device = self.hid_filter.get_devices()
        self.joystick = self.hid_device[0]

        self.joystick.open()
        self.joystick.set_raw_data_handler(self.farm_panel_handler)

        self.mode = 'undefined'
        self.sig_mode_changed.emit(self.mode)

        self.sig_start_timer.connect(self.start_axis_timer)
        self.sig_stop_timer.connect(self.stop_axis_timer)

        '''
        One problem with the joystick is that it stops sending packages when the
        maximum tip/tilt is reached. To circumvent the motion to be stopped,
        a QTimer is used to periodically trigger movement in the same direction.

        joystick_timer_start/stop are helper methods.
        '''
        self.timeout_interval = 10
        self.axis0_timer = QtCore.QTimer(self)
        self.axis1_timer = QtCore.QTimer(self)
        self.axis2_timer = QtCore.QTimer(self)
        self.axis3_timer = QtCore.QTimer(self)
        self.axis4_timer = QtCore.QTimer(self)
        self.axis5_timer = QtCore.QTimer(self)

        self.axis0_value = 0
        self.axis1_value = 0
        self.axis2_value = 0
        self.axis3_value = 0
        self.axis4_value = 0
        self.axis5_value = 0

        self.axis0_timer.timeout.connect(lambda: self.sig_axis_moved.emit(0, self.axis0_value))
        self.axis1_timer.timeout.connect(lambda: self.sig_axis_moved.emit(1, self.axis1_value))
        self.axis2_timer.timeout.connect(lambda: self.sig_axis_moved.emit(2, self.axis2_value))
        self.axis3_timer.timeout.connect(lambda: self.sig_axis_moved.emit(3, self.axis3_value))
        self.axis4_timer.timeout.connect(lambda: self.sig_axis_moved.emit(4, self.axis4_value))
        self.axis5_timer.timeout.connect(lambda: self.sig_axis_moved.emit(5, self.axis5_value))

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
        '''
        Get the binary representation of x.

        Args:
            x (int): Data
            n (int): Minimum number of digits. If x needs less digits in binary, the rest
            is filled with zeros.

        Returns
        -------
        str
        '''
        return format(x, 'b').zfill(n)

    def farm_panel_handler(self, data):
        '''Buttons 1 to 8'''
        self.group_1to8 = data[1]

        self.group_1to8_string = self.get_bin(self.group_1to8,8)
        '''Catch only events which are different from Off-events'''
        if self.group_1to8_string != '00000000':
            button = 8 - self.group_1to8_string.find('1')
            self.sig_button_pressed.emit(button)

        self.group_9to16 = data[2]
        self.group_9to16_string = self.get_bin(self.group_9to16,8)
        '''Catch only events which are different from Off-events'''
        if self.group_9to16_string != '00000000':
            button = 16 - self.group_9to16_string.find('1')
            self.sig_button_pressed.emit(button)

        self.group_17to24 = data[3]
        self.group_17to24_string = self.get_bin(self.group_17to24,8)
        '''Catch only events which are different from Off-events'''
        if self.group_17to24_string != '00000000':
            button = 24 - self.group_17to24_string.find('1')
            self.sig_button_pressed.emit(button)

        self.group_25to29 = data[4]
        self.group_25to29_string = self.get_bin(self.group_25to29,8)
        '''Catch only events which are different from Off-events'''
        if self.group_25to29_string != '00000000':
            index = self.group_25to29_string.find('1')
            if index == 0:
                '''
                29 is the mode changing button, so the corresponding
                signal should be emitted as well:
                '''
                print('self mode: ', self.mode)
                if self.mode == '012':
                    self.mode = '345'
                    self.sig_mode_changed.emit(self.mode)
                elif self.mode == '345':
                    self.mode = '012'
                    self.sig_mode_changed.emit(self.mode)

                self.sig_button_pressed.emit(29)
            elif index == 4:
                self.sig_button_pressed.emit(28)
            else:
                button = 32-index
                self.sig_button_pressed.emit(button)

        '''Joystick handling:

        Stop the joystick timer - a QTimer can be stopped even though it was never
        started. This allows every new arriving HID package to stop the
        persistent sending of messages.
        '''
        self.handle_axis_value_changes(0,'012',5,data)
        self.handle_axis_value_changes(1,'012',6,data)
        self.handle_axis_value_changes(2,'012',7,data)
        self.handle_axis_value_changes(3,'345',8,data)
        self.handle_axis_value_changes(4,'345',9,data)
        self.handle_axis_value_changes(5,'345',10,data)

    def handle_axis_value_changes(self, axis_id, axis_group, data_group, data):
        value = data[data_group]
        if value != 128:
            if self.mode != axis_group:
                self.mode = axis_group
                self.sig_mode_changed.emit(axis_group)

            if value-128 == -128 or value-128 == 127:
                ''' Assign a certain axis the min or max value '''
                exec('self.axis'+str(axis_id)+'_value = value')
                ''' Start timers. Because this is executed from
                another thread, a signal has to be used here.'''
                self.sig_start_timer.emit(axis_id)
                self.sig_axis_moved.emit(axis_id, value)
            else:
                self.sig_stop_timer.emit(axis_id)
                self.sig_axis_moved.emit(axis_id, value)
