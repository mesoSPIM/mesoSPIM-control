"""
The Main Window's combo boxes (filter, zoom, shutter, laser, binning, subsampling) and the state
requests they send to Core.

A box changes for two reasons: someone wants a new value (the operator, or the joystick, which sets
the box from code), or update_gui_from_state shows the state Core already has. Only the first is a
request. Echoing the second made Core redo its own change: every zoom change Core made itself was
run twice, with a second trip of the focus to the objective exchange position; and a laser Core set
without touching the ETL (an acquisition row, with its own ETL values) came back as a laser request
that reloaded the ETL values from the file over the row's.

Run from the mesoSPIM/ directory:  python -m pytest test/test_combobox_state_requests.py -q

Needs PyQt5 but no hardware: the boxes run offscreen.
"""
import os
import sys
import types
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtTest import QTest

from mesoSPIM.src.devices.joysticks.mesoSPIM_JoystickHandlers import mesoSPIM_JoystickHandler
from mesoSPIM.src.mesoSPIM_Core import mesoSPIM_Core
from mesoSPIM.src.mesoSPIM_MainWindow import mesoSPIM_MainWindow

# Module level, and kept alive: a QApplication that gets garbage collected takes the
# interpreter down with it.
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

FILTERS = ['Empty', '515LP', '561LP']
ZOOMS = ['1x', '2x', '4x Olympus']
SHUTTERS = ['Left', 'Right', 'Both', 'Interleaved']
SUBSAMPLING = ['1', '2', '4']


class Core(QtCore.QObject):
    """Core's side: it takes a state request in its own turn of the event loop, and its
    sig_update_gui_from_state refreshes the GUI."""
    sig_update_gui_from_state = QtCore.pyqtSignal()

    def __init__(self, window):
        super().__init__()
        self.window = window

    def state_request_handler(self, request):
        self.window.state.update(request)


class Window(QtCore.QObject):
    """What the combo boxes and the GUI refresh use of the Main Window, with the Main Window's own
    code for both: its state, its startup config, the signal that carries state requests to Core."""
    sig_state_request = QtCore.pyqtSignal(dict)
    showing_state = mesoSPIM_MainWindow.showing_state
    request_state_from_combobox = mesoSPIM_MainWindow.request_state_from_combobox
    update_widget_from_state = mesoSPIM_MainWindow.update_widget_from_state

    def __init__(self, startup):
        super().__init__()
        self.cfg = types.SimpleNamespace(startup=dict(startup))
        self.state = dict(startup, selected_row=0)
        self.acquisition_manager_window = types.SimpleNamespace(set_selected_row=lambda _row: None)
        self.widget_to_state_parameter_assignment = []
        self.requests = []
        self.sig_state_request.connect(self.requests.append)
        self.core = Core(self)
        self.sig_state_request.connect(self.core.state_request_handler, type=QtCore.Qt.QueuedConnection)
        self.core.sig_update_gui_from_state.connect(lambda: mesoSPIM_MainWindow.update_gui_from_state(self))


def connected_box(window, options, state_parameter, int_conversion=False):
    box = QtWidgets.QComboBox()
    mesoSPIM_MainWindow.connect_combobox_to_state_parameter(window, box, options, state_parameter,
                                                            int_conversion=int_conversion)
    return box


def settled(window):
    app.processEvents()
    return window.requests


def show_state(window, box, state_parameter):
    """The GUI refresh (update_gui_from_state) for one box, through the Main Window's own code."""
    window.widget_to_state_parameter_assignment = [(box, state_parameter, 1)]
    mesoSPIM_MainWindow.update_gui_from_state(window)


@pytest.fixture
def zoom():
    window = Window({'zoom': '2x'})
    box = connected_box(window, ZOOMS, 'zoom')
    window.requests.clear()
    return window, box


def test_a_box_asks_core_once_at_startup_for_the_configured_value():
    window = Window({'zoom': '2x', 'camera_display_live_subsampling': 2})
    zoom_box = connected_box(window, ZOOMS, 'zoom')
    subsampling_box = connected_box(window, SUBSAMPLING, 'camera_display_live_subsampling', int_conversion=True)
    assert settled(window) == [{'zoom': '2x'}, {'camera_display_live_subsampling': 2}]
    assert (zoom_box.currentText(), subsampling_box.currentText()) == ('2x', '2')


def test_showing_the_state_core_changed_asks_core_for_nothing(zoom):
    window, box = zoom
    window.state['zoom'] = '4x Olympus'          # Core changed the zoom (a remote command, an acquisition row)
    show_state(window, box, 'zoom')
    assert box.currentText() == '4x Olympus'
    assert settled(window) == []


def test_other_listeners_on_a_box_still_hear_the_refresh(zoom):
    window, box = zoom
    heard = []
    box.currentTextChanged.connect(heard.append)  # as the shutter box's ETL controls listen
    window.state['zoom'] = '1x'
    show_state(window, box, 'zoom')
    assert heard == ['1x']


def test_an_operator_choosing_a_zoom_asks_core_once(zoom):
    window, box = zoom
    box.show()
    QTest.keyClick(box, QtCore.Qt.Key_Down)      # 2x -> 4x Olympus
    assert settled(window) == [{'zoom': '4x Olympus'}]


def test_the_joystick_stepping_the_box_asks_core(zoom):
    window, box = zoom
    mesoSPIM_JoystickHandler.decrement_combobox(None, box)   # 2x -> 1x, set from code
    assert settled(window) == [{'zoom': '1x'}]


def test_a_change_and_back_before_core_catches_up_asks_for_both():
    """Core writes the new filter into the state only once the wheel has moved. Stepping to 515LP and
    back to Empty before then must still send both, or the wheel ends on 515LP under a box that
    shows Empty."""
    window = Window({'filter': 'Empty'})
    box = connected_box(window, FILTERS, 'filter')
    window.requests.clear()
    box.setCurrentText('515LP')
    box.setCurrentText('Empty')                  # the state still says Empty
    assert settled(window) == [{'filter': '515LP'}, {'filter': 'Empty'}]


def test_a_subsampling_box_asks_with_an_integer():
    window = Window({'camera_display_live_subsampling': 2})
    box = connected_box(window, SUBSAMPLING, 'camera_display_live_subsampling', int_conversion=True)
    window.requests.clear()
    box.setCurrentText('4')
    assert settled(window) == [{'camera_display_live_subsampling': 4}]


def test_a_refresh_older_than_the_request_does_not_leave_the_box_wrong():
    """A refresh Core sent before it took the request (after a zoom change, the ETL update's) can
    arrive after the operator chose 515LP. It shows Empty and asks for nothing; the wheel still goes
    to 515LP, so the box must come back to 515LP rather than name a filter that is not in."""
    window = Window({'filter': 'Empty'})
    box = connected_box(window, FILTERS, 'filter')
    window.widget_to_state_parameter_assignment = [(box, 'filter', 1)]
    app.processEvents()
    window.requests.clear()
    box.setCurrentText('515LP')                  # the operator
    show_state(window, box, 'filter')            # the older refresh: Core has not taken 515LP yet
    assert box.currentText() == 'Empty'
    assert settled(window) == [{'filter': '515LP'}]
    assert window.state['filter'] == '515LP' and box.currentText() == '515LP'


class SettingCore(QtCore.QObject):
    """Core setting a value itself (a remote command, an acquisition row), with Core's own setters.
    Its state requests are applied at once, as by the serial worker and the waveformer, which live
    in Core's thread; its refresh reaches the window queued, as across threads."""
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_update_gui_from_state = QtCore.pyqtSignal()
    sig_update_gui_from_shutter_state = QtCore.pyqtSignal()
    set_filter = mesoSPIM_Core.set_filter
    set_shutterconfig = mesoSPIM_Core.set_shutterconfig

    def __init__(self, window):
        super().__init__()
        self.sig_state_request.connect(window.state.update)
        self.sig_update_gui_from_state.connect(lambda: mesoSPIM_MainWindow.update_gui_from_state(window),
                                               type=QtCore.Qt.QueuedConnection)

    def send_status_message_to_gui(self, _message):
        pass


@pytest.mark.parametrize('setter, state_parameter, options, before, after', [
    ('set_filter', 'filter', FILTERS, 'Empty', '561LP'),
    ('set_shutterconfig', 'shutterconfig', SHUTTERS, 'Right', 'Left'),
])
def test_a_value_core_sets_itself_reaches_the_box(setter, state_parameter, options, before, after):
    """A filter or shutter set by a remote command changed Core's state but not the box: the shutter
    box went on naming the other light sheet, with that side's ETL controls enabled. The box must
    follow, and showing it must ask Core for nothing."""
    window = Window({state_parameter: before})
    box = connected_box(window, options, state_parameter)
    window.widget_to_state_parameter_assignment = [(box, state_parameter, 1)]
    app.processEvents()
    window.requests.clear()
    getattr(SettingCore(window), setter)(after)
    assert settled(window) == []
    assert window.state[state_parameter] == after and box.currentText() == after


class RemoteCore(QtCore.QObject):
    """Core taking a Remote Control setter (the AI Assistant's, TCP's or MCP's): Core's own handler
    and setters, then the Remote Control's refresh of the window. The waveformer's keys are applied
    at once, as it lives in Core's thread; the camera's later, as its worker lives on its own thread.
    The refresh reaches the window queued, as across threads."""
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_update_gui_from_state = QtCore.pyqtSignal()
    state_request_handler = mesoSPIM_Core.state_request_handler
    set_intensity = mesoSPIM_Core.set_intensity
    set_camera_exposure_time = mesoSPIM_Core.set_camera_exposure_time
    set_filter = set_zoom = set_laser = set_shutterconfig = set_state = set_camera_line_interval = None   # in the handler's table, not called

    def __init__(self, window):
        super().__init__()
        self.state = window.state
        self.sig_state_request.connect(self.apply)
        self.sig_update_gui_from_state.connect(lambda: mesoSPIM_MainWindow.update_gui_from_state(window),
                                               type=QtCore.Qt.QueuedConnection)

    def apply(self, request):
        for key, value in request.items():
            if key.startswith('camera_'):
                QtCore.QTimer.singleShot(200, lambda key=key, value=value: self.state.update({key: value}))
            else:
                self.state[key] = value


class RemoteWindow(Window):
    """The Main Window's spin boxes, slider and check box, with its own code for them."""
    connect_spinbox_to_state_parameter = mesoSPIM_MainWindow.connect_spinbox_to_state_parameter
    spinbox_to_state_parameter = mesoSPIM_MainWindow.spinbox_to_state_parameter
    slow_down_spinbox = mesoSPIM_MainWindow.slow_down_spinbox
    set_laser_intensity = mesoSPIM_MainWindow.set_laser_intensity
    scale_galvo_amp_w_zoom = mesoSPIM_MainWindow.scale_galvo_amp_w_zoom

    def __init__(self, startup):
        super().__init__(startup)
        self.core = RemoteCore(self)
        self.CameraExposureTimeSpinBox = QtWidgets.QDoubleSpinBox(maximum=10000, decimals=1)
        self.LeftETLOffsetSpinBox = QtWidgets.QDoubleSpinBox(minimum=-5, maximum=5, decimals=3)
        self.GalvoFrequencySpinBox = QtWidgets.QDoubleSpinBox(maximum=1000, decimals=2)
        self.LaserIntensitySlider = QtWidgets.QSlider(maximum=100)
        self.LaserIntensitySpinBox = QtWidgets.QSpinBox(maximum=100)
        self.checkBoxScaleWZoom = QtWidgets.QCheckBox()
        self.BinningComboBox = connected_box(self, ['1x1', '2x2'], 'camera_binning')
        self.LiveSubSamplingComboBox = connected_box(self, SUBSAMPLING, 'camera_display_live_subsampling',
                                                     int_conversion=True)
        self.widget_to_state_parameter_assignment = [
            (self.CameraExposureTimeSpinBox, 'camera_exposure_time', 1000),
            (self.LeftETLOffsetSpinBox, 'etl_l_offset', 1),
            (self.GalvoFrequencySpinBox, 'galvo_l_frequency', 1),
            (self.LaserIntensitySlider, 'intensity', 1),
            (self.LaserIntensitySpinBox, 'intensity', 1),
            (self.checkBoxScaleWZoom, 'galvo_amp_scale_w_zoom', 1),
            (self.BinningComboBox, 'camera_binning', 1),
            (self.LiveSubSamplingComboBox, 'camera_display_live_subsampling', 1),
        ]
        for widget, state_parameter, conversion_factor in self.widget_to_state_parameter_assignment[:3]:
            self.connect_spinbox_to_state_parameter(widget, state_parameter, conversion_factor)
        self.LaserIntensitySlider.valueChanged.connect(self.set_laser_intensity)
        self.LaserIntensitySpinBox.valueChanged.connect(self.set_laser_intensity)
        self.checkBoxScaleWZoom.stateChanged.connect(self.scale_galvo_amp_w_zoom)
        mesoSPIM_MainWindow.update_gui_from_state(self)
        app.processEvents()
        self.requests.clear()


def shows(window, condition):
    """Pump the event loop until the widget shows the value, within the refresh's own cap."""
    from mesoSPIM.src.remote_control import config
    deadline = QtCore.QDeadlineTimer(int((config.READ_BACK_S + 1) * 1000))
    while not condition() and not deadline.hasExpired():
        app.processEvents()
        QTest.qWait(10)
    app.processEvents()
    return condition()


@pytest.fixture
def remote():
    return RemoteWindow({'intensity': 10, 'camera_exposure_time': 0.02, 'camera_binning': '1x1',
                         'camera_display_live_subsampling': 2, 'etl_l_offset': 1.0, 'galvo_l_frequency': 99.9,
                         'galvo_amp_scale_w_zoom': False})


def test_a_camera_setting_made_remotely_reaches_the_widgets_once_the_camera_wrote_it(remote):
    """A remote set_camera changed Core's state, late (the camera worker's thread), and the window
    showed nothing of it. The widgets must follow, and showing the values must ask Core for nothing."""
    from mesoSPIM.src.remote_control import commands
    commands._run_state_settings(remote.core, {'settings': {'camera_exposure_time': 0.05, 'camera_binning': '2x2',
                                                            'camera_display_live_subsampling': 4}})
    assert shows(remote, lambda: remote.CameraExposureTimeSpinBox.value() == 50.0)
    assert (remote.BinningComboBox.currentText(), remote.LiveSubSamplingComboBox.currentText()) == ('2x2', '4')
    assert remote.requests == []


def test_a_remote_intensity_reaches_the_slider_and_the_box(remote):
    from mesoSPIM.src.remote_control import commands
    commands._run_set_intensity(remote.core, {'intensity': 30, 'wait': False})
    assert shows(remote, lambda: remote.LaserIntensitySlider.value() == remote.LaserIntensitySpinBox.value() == 30)
    assert remote.requests == []


@pytest.mark.parametrize('setting, widget_name, shown', [
    ({'etl_l_offset': 1.25}, 'LeftETLOffsetSpinBox', 1.25),                     # set_etl
    ({'galvo_l_frequency': 100.5}, 'GalvoFrequencySpinBox', 100.5),             # set_galvo
])
def test_a_remote_waveform_setting_reaches_its_spin_box(remote, setting, widget_name, shown):
    from mesoSPIM.src.remote_control import commands
    commands._run_state_settings(remote.core, {'settings': setting})
    assert shows(remote, lambda: getattr(remote, widget_name).value() == shown)
    assert remote.requests == []


def test_scale_with_zoom_set_remotely_reaches_the_check_box(remote):
    """Core forwards galvo_amp_scale_w_zoom and nobody applied it: a remote set_state of it was a
    silent no-op. The Remote Control writes it; the check box follows."""
    from mesoSPIM.src.remote_control import commands
    commands._run_state_settings(remote.core, {'settings': {'galvo_amp_scale_w_zoom': True}})
    assert shows(remote, lambda: remote.checkBoxScaleWZoom.isChecked())
    assert remote.state['galvo_amp_scale_w_zoom'] is True and remote.requests == []


def test_a_refresh_does_not_send_a_rounded_value_back():
    """A spin box's setValue fires valueChanged, and that sent the box's rounded value back to Core as
    a request: an exposure of 12.3 ms shown by a box with no decimals came back as 12 ms."""
    window = RemoteWindow({'intensity': 10, 'camera_exposure_time': 0.0123, 'camera_binning': '1x1',
                           'camera_display_live_subsampling': 2, 'etl_l_offset': 1.0, 'galvo_l_frequency': 99.9,
                           'galvo_amp_scale_w_zoom': False})
    window.CameraExposureTimeSpinBox.setDecimals(0)
    window.requests.clear()
    mesoSPIM_MainWindow.update_gui_from_state(window)
    assert window.CameraExposureTimeSpinBox.value() == 12
    assert settled(window) == [] and window.state['camera_exposure_time'] == 0.0123
    window.CameraExposureTimeSpinBox.setValue(20)                     # the operator
    assert settled(window) == [{'camera_exposure_time': 0.02}]
