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

        self.parent = parent
        self.cfg = parent.cfg

        ''' parent is the window '''
        self.joystick = FarmSimulatorSidePanel()

        self.joystick.sig_button_pressed.connect(self.button_handler)
        self.joystick.sig_mode_changed.connect(self.mode_handler)
        self.joystick.sig_axis_moved.connect(self.axis_handler)

        ''' '''
        self.SliderChangeCount = 0

    @QtCore.pyqtSlot(int)
    def button_handler(self, button_id):
        ''' Debugging print statement '''
        print('Button pressed: ', button_id)

        ''' Laser switching buttons '''
        if button_id == 1:
            self.set_combobox_to_index(self.parent.LaserComboBox,0)
        if button_id == 2:
            self.set_combobox_to_index(self.parent.LaserComboBox,1)
        if button_id == 3:
            self.set_combobox_to_index(self.parent.LaserComboBox,2)
        if button_id == 6:
            self.set_combobox_to_index(self.parent.LaserComboBox,3)
        if button_id == 7:
            self.set_combobox_to_index(self.parent.LaserComboBox,4)
        if button_id == 8:
            self.set_combobox_to_index(self.parent.LaserComboBox,5)

        ''' Load & unload samples '''
        if button_id == 5:
            self.parent.sig_unload_sample.emit()
        if button_id == 10:
            self.parent.sig_load_sample.emit()

        ''' Filter & Zoom Increments & decrements '''
        if button_id == 11:
            self.increment_combobox(self.parent.FilterComboBox)
        if button_id == 12:
            self.decrement_combobox(self.parent.FilterComboBox)
        if button_id == 13:
            self.increment_combobox(self.parent.ZoomComboBox)
        if button_id == 14:
            self.decrement_combobox(self.parent.ZoomComboBox)

        ''' Live button '''
        if button_id == 21:
            current_state = self.parent.get_state_parameter('state')
            if current_state == 'live':
                self.parent.StopButton.clicked.emit(False)
            elif current_state == 'idle':
                self.parent.LiveButton.clicked.emit(False)

        ''' Increase & decrease laser intensity '''
        if button_id == 26:
            self.increase_slider(self.parent.LaserIntensitySlider, 2)

        if button_id == 27:
            self.decrease_slider(self.parent.LaserIntensitySlider, 2)

        ''' Stop movement button '''
        if button_id == 28:
            self.parent.sig_stop_movement.emit()

        if button_id == 29:
            pass

    def set_combobox_to_index(self, combobox, index):
        if index < combobox.count():
            combobox.setCurrentIndex(index)

    def increment_combobox(self, combobox):
        index = combobox.currentIndex()
        index += 1
        if index < combobox.count():
            combobox.setCurrentIndex(index)

    def decrement_combobox(self, combobox):
        index = combobox.currentIndex()
        index -= 1
        if index > -1:
            combobox.setCurrentIndex(index)

    def increase_slider(self, slider, event_devider=2):
        self.SliderChangeCount += 1
        ''' To avoid events coming too quickly,
        only every n-th event is causing a change if
        n = event_devider
        '''
        if self.SliderChangeCount % event_devider == 0:
            value = self.slider.value()
            value = value + 1

            if value != 100:
                slider.setValue(value)
            else:
                slider.setValue(100)

    def decrease_slider(self, slider, event_devider=2):
        ''' To avoid events coming too quickly,
        only every n-th event is causing a change if
        n = event_devider
        '''
        self.SliderChangeCount += 1

        if self.SliderChangeCount % event_devider == 0:
            value = self.slider.value()
            value = value - 1

            if value != 0:
                slider.setValue(value)
            else:
                slider.setValue(0)

    @QtCore.pyqtSlot(str)
    def mode_handler(self, str):
        print('New joystick mode: ', str)

    @QtCore.pyqtSlot(int, int)
    def axis_handler(self, axis_id, value):
        print('Axis: ', axis_id, ',Value: ', value)



    ### What needs to be done here
