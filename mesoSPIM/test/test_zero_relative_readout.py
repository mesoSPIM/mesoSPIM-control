"""
ZERO buttons are display only: positions, stage moves and the acquisition table stay absolute,
a blue relative read-out (absolute - reference) appears under each zeroed axis.
Stub Core and main window (no hardware).
"""
import os
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtWidgets

from mesoSPIM.src.mesoSPIM_Core import mesoSPIM_Core
from mesoSPIM.src.mesoSPIM_MainWindow import mesoSPIM_MainWindow

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

AXES = ('x', 'y', 'z', 'f', 'theta')


def make_core(absolute):
    emitted = []
    core = types.SimpleNamespace(
        state={'position_absolute': {f'{a}_pos': v for a, v in absolute.items()}, 'position_reference': {}},
        sig_zero_axes=types.SimpleNamespace(emit=lambda l: emitted.append(('zero', l))),
        sig_unzero_axes=types.SimpleNamespace(emit=lambda l: emitted.append(('unzero', l))),
        emitted=emitted)
    for name in ('zero_axes', 'unzero_axes'):
        setattr(core, name, getattr(mesoSPIM_Core, name).__get__(core))
    return core


def test_zero_stores_reference_and_never_shifts_the_stage():
    core = make_core({'x': 1000.0, 'y': -250.0, 'z': 3000.0, 'f': 5000.0, 'theta': 0.0})
    core.zero_axes(['x', 'y'])
    assert core.state['position_reference'] == {'x': 1000.0, 'y': -250.0}
    core.state['position_absolute']['z_pos'] = 3500.0
    core.zero_axes(['z'])
    assert core.state['position_reference'] == {'x': 1000.0, 'y': -250.0, 'z': 3500.0}
    core.unzero_axes(['x', 'y'])
    assert core.state['position_reference'] == {'z': 3500.0}
    assert core.emitted == []  # stage offsets are never set: readback and moves stay absolute


def make_window(reference):
    container = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(container)
    win = types.SimpleNamespace(state={'position_reference': reference}, horizontalLayout_3=layout,
                                pos2str=lambda p: '%.1f' % p, _container=container)
    for name in ('X', 'Y', 'Z', 'Rotation', 'Focus'):
        edit = QtWidgets.QLineEdit(container)
        layout.addWidget(edit)
        setattr(win, f'{name}_Position_Indicator', edit)
    for name in ('xyZeroButton', 'zZeroButton', 'focusZeroButton', 'rotZeroButton'):
        button = QtWidgets.QPushButton(container)
        button.setCheckable(True)
        setattr(win, name, button)
    for name in ('create_relative_indicators', 'update_relative_indicators'):
        setattr(win, name, getattr(mesoSPIM_MainWindow, name).__get__(win))
    win.create_relative_indicators()
    container.show()
    return win


def test_relative_readout_only_for_zeroed_axes():
    win = make_window({'z': 3500.0})
    pos = {'x_pos': 10.0, 'y_pos': 20.0, 'z_pos': 3620.5, 'f_pos': 5000.0, 'theta_pos': 0.0}
    win.update_relative_indicators(pos)
    rel = win.relative_indicators
    assert rel['z'].isVisible() and rel['z'].text() == 'Δ 120.5 µm'
    assert not any(rel[a].isVisible() for a in ('x', 'y', 'f', 'theta'))
    # each relative read-out sits right under its absolute indicator, in the same column
    column = win.horizontalLayout_3.itemAt(2).layout()
    assert column.itemAt(0).widget() is win.Z_Position_Indicator and column.itemAt(1).widget() is rel['z']
    # unzero: read-out disappears
    win.state['position_reference'] = {}
    win.update_relative_indicators(pos)
    assert not rel['z'].isVisible()


def test_buttons_follow_a_remote_zero_but_a_click_is_not_undone():
    win = make_window({})
    pos = {f'{a}_pos': 0.0 for a in AXES}
    win.update_relative_indicators(pos)
    # a click checks the button before Core has stored the reference: the next update must not uncheck it
    win.xyZeroButton.setChecked(True)
    win.update_relative_indicators(pos)
    assert win.xyZeroButton.isChecked()
    # remote zero of F only: F button follows
    win.state['position_reference'] = {'x': 0.0, 'y': 0.0, 'f': 0.0}
    win.update_relative_indicators(pos)
    assert win.focusZeroButton.isChecked() and win.xyZeroButton.isChecked() and not win.zZeroButton.isChecked()
    # remote unzero of x and y: XY button follows
    win.state['position_reference'] = {'f': 0.0}
    win.update_relative_indicators(pos)
    assert not win.xyZeroButton.isChecked() and win.focusZeroButton.isChecked()
