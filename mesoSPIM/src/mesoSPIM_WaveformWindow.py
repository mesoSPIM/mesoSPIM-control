'''
Waveform viewer: the output waveforms of one sweep on a common time axis (Waveforms tab, "Show waveforms").

Shows what the waveform generator currently holds: galvo L/R, ETL L/R and the active laser's AO
waveforms, plus the camera trigger and (ASI / mixed stages) stage trigger TTL pulses, which are
counter pulses on the DAQ and drawn here from their delay and pulse length. Read-only: nothing
is sent to the hardware. Refreshed twice a second while the window is open, so parameter
changes on the Waveforms and ETL tabs show up immediately.
'''
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore

from .utils.waveforms import single_pulse
from .utils.utility_functions import fit_window_to_screen

import logging
logger = logging.getLogger(__name__)

TTL_VOLTS = 5.0
REFRESH_MS = 500
COLORS = {'left': (80, 160, 255), 'right': (255, 140, 60), 'laser': (90, 220, 90),
          'camera': (230, 230, 230), 'stage': (220, 120, 220)}


def _uses_stage_trigger(cfg):
    stage_type = str(getattr(cfg, 'stage_parameters', {}).get('stage_type', '')).lower()
    return 'asi' in stage_type or stage_type == 'mixed'


def waveform_traces(waveformer, state, cfg):
    """The waveforms of one sweep, as plot rows on a common time axis.

    Args:
        waveformer: mesoSPIM_WaveFormGenerator (or anything with its *_waveform attributes).
        state: the mesoSPIM state (dict-like: samplerate, sweeptime, laser, camera_*_%).
        cfg: the config module (asi_parameters and stage_parameters for the stage trigger).

    Returns:
        (t_ms, rows): t_ms is the time axis in ms (0 .. sweeptime); rows is a list of
        (title, unit, [(label, color, y), ...]), one per plot, each y as long as t_ms.
    """
    samplerate, sweeptime = state['samplerate'], state['sweeptime']
    n = len(waveformer.galvo_l_waveform)
    t_ms = np.arange(n) / samplerate * 1000.0

    def fit(y):  # all traces on the same samples, even if one was just being recreated
        y = np.asarray(y, dtype=float)
        return y[:n] if len(y) >= n else np.pad(y, (0, n - len(y)), mode='edge')

    def ttl(delay_percent, pulse_percent):
        return fit(single_pulse(samplerate=samplerate, sweeptime=sweeptime, delay=delay_percent,
                                pulsewidth=pulse_percent, amplitude=TTL_VOLTS, offset=0))

    rows = [
        ('Galvos', 'V', [('Galvo L', COLORS['left'], fit(waveformer.galvo_l_waveform)),
                         ('Galvo R', COLORS['right'], fit(waveformer.galvo_r_waveform))]),
        ('ETLs', 'V', [('ETL L', COLORS['left'], fit(waveformer.etl_l_waveform)),
                       ('ETL R', COLORS['right'], fit(waveformer.etl_r_waveform))]),
        ('Laser', 'V', [(f"Laser {state['laser']}", COLORS['laser'], fit(waveformer.laser_template_waveform))]),
        ('Camera trigger', 'TTL', [('Camera', COLORS['camera'], ttl(state['camera_delay_%'], state['camera_pulse_%']))]),
    ]
    asi = getattr(cfg, 'asi_parameters', None)
    if _uses_stage_trigger(cfg) and isinstance(asi, dict) and \
            'stage_trigger_delay_%' in asi and 'stage_trigger_pulse_%' in asi:
        rows.append(('Stage trigger', 'TTL',
                     [('Stage', COLORS['stage'], ttl(asi['stage_trigger_delay_%'], asi['stage_trigger_pulse_%']))]))
    return t_ms, rows


class mesoSPIM_WaveformWindow(QtWidgets.QWidget):
    '''One plot per output, stacked, with linked time axes (zooming one zooms all).'''

    def __init__(self, parent):
        '''parent: mesoSPIM_MainWindow'''
        super().__init__()
        self.parent = parent
        self.setWindowTitle('Waveforms (one sweep)')
        layout = QtWidgets.QVBoxLayout(self)
        self.info = QtWidgets.QLabel(self)
        layout.addWidget(self.info)
        self.plots_widget = pg.GraphicsLayoutWidget(self)
        layout.addWidget(self.plots_widget, 1)
        self._row_titles = None
        self._sweeptime = None
        self.plots, self.curves = [], []
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.resize(900, 900)
        fit_window_to_screen(self)
        self.refresh()

    def _build(self, rows):
        self.plots_widget.clear()
        self.plots, self.curves = [], []
        for index, (title, unit, traces) in enumerate(rows):
            plot = self.plots_widget.addPlot(row=index, col=0)
            plot.setLabel('left', title, units=None if unit == 'TTL' else unit)
            plot.getAxis('left').enableAutoSIPrefix(False)  # always V, not mV for a weak laser
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.addLegend(offset=(-10, 5))
            if self.plots:
                plot.setXLink(self.plots[0])
            if index == len(rows) - 1:
                plot.setLabel('bottom', 'Time', units='ms')
            else:
                plot.getAxis('bottom').setStyle(showValues=False)
            self.plots.append(plot)
            self.curves.append([plot.plot(name=label, pen=pg.mkPen(color, width=2)) for label, color, _ in traces])
        self._row_titles = [(title, tuple(label for label, _, _ in traces)) for title, _, traces in rows]
        self._sweeptime = None  # new plots: set the time range on this refresh

    @QtCore.pyqtSlot()
    def refresh(self):
        state = self.parent.state
        try:
            t_ms, rows = waveform_traces(self.parent.core.waveformer, state, self.parent.cfg)
        except AttributeError as error:  # waveforms not created yet
            self.info.setText(f'No waveforms yet ({error})')
            return
        titles = [(title, tuple(label for label, _, _ in traces)) for title, _, traces in rows]
        if titles != self._row_titles:   # laser changed, or first draw
            self._build(rows)
        for curves, (_, _, traces) in zip(self.curves, rows):
            for curve, (_, _, y) in zip(curves, traces):
                curve.setData(t_ms, y)
        if state['sweeptime'] != self._sweeptime:   # one sweep wide; kept while the user zooms
            self._sweeptime = state['sweeptime']
            self.plots[0].setXRange(0, self._sweeptime * 1000.0, padding=0.01)
        self.info.setText(f"Sweep time {state['sweeptime'] * 1000:.1f} ms, sample rate {state['samplerate']:.0f} Hz, "
                          f"{len(t_ms)} samples. Shutter: {state['shutterconfig']}, laser: {state['laser']}, "
                          f"intensity {state['intensity']} %. Read-only view of the current waveforms.")

    def showEvent(self, event):
        self._sweeptime = None  # reopened: back to one full sweep
        self.refresh()
        self.timer.start(REFRESH_MS)
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)
