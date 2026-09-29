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
from mesoSPIM.src.mesoSPIM_MainWindow import mesoSPIM_MainWindow

# Module level, and kept alive: a QApplication that gets garbage collected takes the
# interpreter down with it.
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

FILTERS = ['Empty', '515LP', '561LP']
ZOOMS = ['1x', '2x', '4x Olympus']
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
