'''
Serial thread for the mesoSPIM project
======================================

This thread handles all connections with serial devices such as stages,
filter wheels, zoom systems etc.
'''

import logging
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
''' Import mesoSPIM modules '''
from .devices.filter_wheels.mesoSPIM_FilterWheel import mesoSPIM_DemoFilterWheel, DynamixelFilterWheel, LudlFilterWheel
from .devices.filter_wheels.mesoSPIM_FilterWheel import ZwoFilterWheel, SutterLambda10BFilterWheel
from .mesoSPIM_Zoom import DynamixelZoom, DemoZoom, MitutoyoZoom
from .mesoSPIM_Stages import mesoSPIM_PI_1toN, mesoSPIM_PI_NtoN, mesoSPIM_ASI_Stages, mesoSPIM_DemoStage, mesoSPIM_PI_rotz_and_Galil_xyf_Stages, mesoSPIM_Mixed_Stages
from .plugins.FilterWheelApi import FilterWheel
from .plugins.utils import get_filter_wheel_plugins, get_filter_wheel_plugin_class_from_name
from .utils.utility_functions import log_cpu_core, timed
from .utils.config_loader import is_demo
from .utils.stage_limits import StageLimitGuard, limits_from_cfg, limit_guard_um

logger = logging.getLogger(__name__)

class mesoSPIM_Serial(QtCore.QObject):
    '''This class handles mesoSPIM serial connections.

    Acts as a facade over three hardware sub-systems:

    * **Stage** — one of several concrete :class:`mesoSPIM_Stage` subclasses
      (PI, ASI, Demo …) selected from the config file.
    * **Filter wheel** — one of the :class:`mesoSPIM_FilterWheel` implementations
      (Ludl, Dynamixel, Sutter, ZWO, Demo).
    * **Zoom** — one of the :class:`DynamixelZoom` / :class:`MitutoyoZoom` /
      :class:`DemoZoom` implementations.

    All three are instantiated in ``__init__`` based on config parameters.
    This object stays in the **Core thread** (see :class:`mesoSPIM_Core`);
    slot calls therefore run synchronously in that event loop.
    '''
    sig_finished = QtCore.pyqtSignal()
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_position = QtCore.pyqtSignal(dict)
    sig_zero_axes = QtCore.pyqtSignal(list)
    sig_unzero_axes = QtCore.pyqtSignal(list)
    sig_stop_movement = QtCore.pyqtSignal()
    sig_load_sample = QtCore.pyqtSignal()
    sig_unload_sample = QtCore.pyqtSignal()
    sig_center_sample = QtCore.pyqtSignal()
    sig_mark_rotation_position = QtCore.pyqtSignal()
    sig_status_message = QtCore.pyqtSignal(str)
    sig_move_refused = QtCore.pyqtSignal(str)  # a programmatic move was refused by the soft limits
    #sig_pause = QtCore.pyqtSignal(bool)
    
    def __init__(self, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent
        self.cfg = parent.cfg
        self.state = self.parent.state # the mesoSPIM_StateSingleton() instance
        self.stage_limits_warning = False
        # Soft limits for every stage type (utils/stage_limits.py), physical coordinates.
        self.limit_guard = StageLimitGuard(limits_from_cfg(self.cfg.stage_parameters),
                                           limit_guard_um(self.cfg.stage_parameters))

        ''' Attaching the filterwheel '''
        self._filterwheel_is_plugin = False
        if self.cfg.filterwheel_parameters['filterwheel_type'] == 'Ludl':
            self.filterwheel = LudlFilterWheel(self.cfg.filterwheel_parameters['COMport'],self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'Dynamixel':
            self.filterwheel = DynamixelFilterWheel(self.cfg.filterdict, self.cfg.filterwheel_parameters['COMport'],
                                                    self.cfg.filterwheel_parameters['servo_id'],
                                                    self.cfg.filterwheel_parameters['baudrate'])
        elif is_demo(self.cfg.filterwheel_parameters['filterwheel_type']):
            self.filterwheel = mesoSPIM_DemoFilterWheel(self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'Sutter':
            self.filterwheel = SutterLambda10BFilterWheel(self.cfg.filterwheel_parameters, self.cfg.filterdict)
        elif self.cfg.filterwheel_parameters['filterwheel_type'] == 'ZWO':
            self.filterwheel = ZwoFilterWheel(self.cfg.filterdict, self)
        else:
            filterwheel_type = self.cfg.filterwheel_parameters['filterwheel_type']
            plugin_class = get_filter_wheel_plugin_class_from_name(filterwheel_type)
            if plugin_class is None:
                built_in_types = {'Demo', 'Dynamixel', 'Ludl', 'Sutter', 'ZWO'}
                plugin_types = {plugin['name'] for plugin in get_filter_wheel_plugins()}
                available_types = ', '.join(sorted(built_in_types | plugin_types))
                raise ValueError(
                    f"Filter wheel type unknown: {filterwheel_type}. "
                    f"Available types: {available_types}"
                )
            logger.info(f"Initializing filter wheel plugin: {filterwheel_type}")
            filterwheel = plugin_class.create(
                self.cfg.filterwheel_parameters,
                self.cfg.filterdict,
            )
            if not isinstance(filterwheel, FilterWheel):
                close = getattr(filterwheel, 'close', None)
                if callable(close):
                    close()
                raise TypeError(
                    f"Filter wheel plugin {filterwheel_type} returned an invalid driver"
                )
            self.filterwheel = filterwheel
            self._filterwheel_is_plugin = True

        ''' Attaching the zoom '''
        if self.cfg.zoom_parameters['zoom_type'] == 'Dynamixel':
            self.zoom = DynamixelZoom(self.cfg.zoomdict, self.cfg.zoom_parameters['COMport'], self.cfg.zoom_parameters['servo_id'], self.cfg.zoom_parameters['baudrate'])
        elif self.cfg.zoom_parameters['zoom_type'] in ('Mitu', 'Mitutoyo'):
            self.zoom = MitutoyoZoom(self.cfg.zoomdict, self.cfg.zoom_parameters['COMport'], self.cfg.zoom_parameters['baudrate'])
        elif is_demo(self.cfg.zoom_parameters['zoom_type']):
            self.zoom = DemoZoom(self.cfg.zoomdict)
        else:
            raise ValueError(f"Zoom type unknown: {self.cfg.zoom_parameters['zoom_type']}")

        ''' Attaching the stage '''
        if self.cfg.stage_parameters['stage_type'] in {'PI', 'PI_1controllerNstages'}:
            self.stage = mesoSPIM_PI_1toN(self)
        elif self.cfg.stage_parameters['stage_type'] == 'PI_NcontrollersNstages':
            self.stage = mesoSPIM_PI_NtoN(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'GalilStage':
        #     self.stage = mesoSPIM_GalilStages(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'PI_rot_and_Galil_xyzf':
        #     self.stage = mesoSPIM_PI_rot_and_Galil_xyzf_Stages(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'PI_f_rot_and_Galil_xyz':
        #     self.stage = mesoSPIM_PI_f_rot_and_Galil_xyz_Stages(self)
        elif self.cfg.stage_parameters['stage_type'] == 'PI_rotz_and_Galil_xyf':
            self.stage = mesoSPIM_PI_rotz_and_Galil_xyf_Stages(self)
        # elif self.cfg.stage_parameters['stage_type'] == 'PI_rotzf_and_Galil_xy':
        #     self.stage = mesoSPIM_PI_rotzf_and_Galil_xy_Stages(self)
        elif 'asi' in self.cfg.stage_parameters['stage_type'].lower():
            self.stage = mesoSPIM_ASI_Stages(self)
            #self.stage.sig_pause.connect(self.pause)
            self.parent.sig_progress.connect(self.stage.log_slice)
        # elif self.cfg.stage_parameters['stage_type'] == 'MS2000ASI':
        #     self.stage = mesoSPIM_ASI_MS2000_Stage(self)
        #     #self.stage.sig_pause.connect(self.pause)
        #     self.parent.sig_progress.connect(self.stage.log_slice)
        elif self.cfg.stage_parameters['stage_type'].lower() == 'mixed':
            self.stage = mesoSPIM_Mixed_Stages(self)
            self.parent.sig_progress.connect(self.stage.log_slice)
        elif is_demo(self.cfg.stage_parameters['stage_type']):
            self.stage = mesoSPIM_DemoStage(self)
        else:
            raise ValueError(f"Stage type unknown: {self.cfg.stage_parameters['stage_type']}")
        try:
            self.stage.sig_status_message.connect(self.send_status_message)
            self.stage.sig_position.connect(self.report_position)
        except:
            print('Stage not initalized! Please check the config file')

        # self.parent.sig_move_absolute.connect(self.move_absolute)
        # self.parent.sig_move_absolute_and_wait_until_done.connect(lambda sdict: self.move_absolute(sdict, wait_until_done=True))
        # WARNING: do not use type=Qt.BlockingQueuedConnection for _wait_until_done signals, as this will cause a deadlock!
        # The mesoSPIM_Serial object is executed in the parent (Core) thread, and type=Qt.BlockingQueuedConnection can be used only between threads.
        # Using type=Qt.BlockingQueuedConnection withing the same thread will cause a deadlock.

        self.parent.sig_zero_axes.connect(self.sig_zero_axes.emit)
        self.parent.sig_unzero_axes.connect(self.sig_unzero_axes.emit)
        self.parent.sig_stop_movement.connect(self.sig_stop_movement.emit)
        self.parent.sig_load_sample.connect(self.sig_load_sample.emit)
        self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit)
        self.parent.sig_center_sample.connect(self.sig_center_sample.emit)
        # These moves bypass the guard (or stop a move): forget where the axes were heading.
        for signal in (self.parent.sig_stop_movement, self.parent.sig_load_sample,
                       self.parent.sig_unload_sample, self.parent.sig_center_sample):
            signal.connect(lambda *args: self.limit_guard.forget())

    def __del__(self):
        self.close()

    def close(self):
        """Release plugin filter-wheel resources during cleanup."""
        try:
            close = (
                getattr(self.filterwheel, 'close', None)
                if self._filterwheel_is_plugin
                else None
            )
            if callable(close):
                close()
        except Exception:
            logger.debug('Failed to close filter wheel during cleanup', exc_info=True)

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, sdict, wait_until_done=False):
        """Route state-change requests from Core to the appropriate hardware method.

        Recognised keys: ``'filter'``, ``'zoom'``, ``'stage_program'``,
        ``'ttl_movement_enabled_during_acq'``.

        Args:
            sdict (dict): Key/value pairs describing the desired state change.
            wait_until_done (bool): Passed down to ``set_filter`` / ``set_zoom``.
        """
        logger.debug(f'mesoSPIM_Serial state request: {sdict}')
        for key, value in zip(sdict.keys(), sdict.values()):
            if key == 'filter':
                self.set_filter(value, wait_until_done)
            if key == 'zoom':
                self.set_zoom(value, wait_until_done)
            if key == 'stage_program':
                self.execute_stage_program()
            if key == 'ttl_movement_enabled_during_acq':
                self.enable_ttl_motion(value)
            logger.info(f'state change: {key}: {value}')

    @QtCore.pyqtSlot(str)
    def send_status_message(self, string):
        """Re-emit a stage status message up to :class:`mesoSPIM_Core` / GUI.

        Args:
            string (str): Human-readable status string from the stage driver.
        """
        self.sig_status_message.emit(string)

#    @QtCore.pyqtSlot(bool)
#    def pause(self, boolean):
#        logger.debug(f'Pause signal received: {boolean}')
#        self.sig_pause.emit(boolean)

    @QtCore.pyqtSlot(bool)
    def enable_ttl_motion(self, boolean):
        """Enable or disable TTL-triggered motion on ASI stages during an acquisition.

        Args:
            boolean (bool): ``True`` to enable TTL motion, ``False`` to disable.
        """
        self.stage.enable_ttl_motion(boolean)

    def _limit_message(self, message, refused_programmatic=False):
        """Show a soft-limit message in the status bar and log it; a refused programmatic move
        (acquisition step, script) is also sent on sig_move_refused so Core can stop."""
        self.send_status_message(message)
        self.stage_limits_warning = True
        logger.warning(message)
        if refused_programmatic:
            self.sig_move_refused.emit(message)

    def _clear_limit_message(self):
        if self.stage_limits_warning:  # clear the previous soft-limit message
            self.send_status_message('')
            self.stage_limits_warning = False

    @log_cpu_core
    @QtCore.pyqtSlot(dict)
    def move_relative(self, sdict, wait_until_done=False, clamp=False):
        """Move one or more axes by a relative offset, within the soft limits.

        Each step is checked against where the axis is heading (utils/stage_limits.py), so
        fast repeated clicks can't add up past a limit.

        Args:
            sdict (dict): Axis → step mapping, e.g. ``{'z_rel': 50.0}`` (μm).
            wait_until_done (bool): Block until the stage controller confirms completion.
            clamp (bool): Button moves: a step that would cross a limit is shortened to stop
                just inside it. Otherwise (acquisition steps, scripts) the whole move is refused
                and sig_move_refused is emitted.

        Returns:
            bool: True if a move was sent to the stage.
        """
        logger.debug(f"mesoSPIM_Serial moving relative: {{{', '.join([f'{k!r}: {v:.3f}' if isinstance(v, (int, float)) else f'{k!r}: {v!r}' for k, v in sdict.items()])}}}")
        moves, targets, messages = {}, {}, []
        for key, step in sdict.items():
            if not key.endswith('_rel'):
                moves[key] = step
                continue
            axis = key[:-4]
            allowed, target, message = self.limit_guard.check_relative(
                axis, step, getattr(self.stage, axis + '_pos'), clamp=clamp)
            if message:
                messages.append(message)
            if allowed is None:
                if not clamp:  # programmatic: refuse the whole move
                    self._limit_message(message, refused_programmatic=True)
                    return False
                continue
            moves[key] = allowed
            if target is not None:
                targets[axis] = target
        if messages:
            self._limit_message(' '.join(messages))
        else:
            self._clear_limit_message()
        if not any(key.endswith('_rel') for key in moves):
            return False
        self.stage.move_relative(moves, wait_until_done=wait_until_done)
        for axis, target in targets.items():
            self.limit_guard.accept(axis, target)
        return True

    @timed
    @QtCore.pyqtSlot(dict)
    def move_absolute(self, sdict, wait_until_done=False, use_internal_position=True):
        """Move one or more axes to an absolute position.

        Args:
            sdict (dict): Axis → target mapping, e.g. ``{'x_abs': 1000.0}`` (μm).
            wait_until_done (bool): Block until the stage controller confirms completion.
            use_internal_position (bool): Apply the user-visible position offset stored
                in :class:`mesoSPIM_StateSingleton` when ``True``.

        Targets outside the soft limits are refused for every stage type (the whole move),
        with a status message, a WARNING and sig_move_refused.

        Returns:
            bool: True if the move was sent to the stage.
        """
        logger.debug(f"mesoSPIM_Serial moving absolute: {{{', '.join([f'{k!r}: {v:.3f}' if isinstance(v, (int, float)) else f'{k!r}: {v!r}' for k, v in sdict.items()])}}}")
        targets = {}
        for key, value in sdict.items():
            if not key.endswith('_abs'):
                continue
            axis = key[:-4]
            offset = getattr(self.stage, f'int_{axis}_pos_offset', 0) if use_internal_position else 0
            physical = value - offset
            message = self.limit_guard.check_absolute(axis, physical)
            if message:  # refuse the whole move: a partial absolute move ends somewhere unexpected
                self._limit_message(message, refused_programmatic=True)
                return False
            targets[axis] = physical
        self._clear_limit_message()
        self.stage.move_absolute(sdict, wait_until_done=wait_until_done, use_internal_position=use_internal_position)
        for axis, target in targets.items():
            self.limit_guard.accept(axis, target)
        return True

    @log_cpu_core
    @QtCore.pyqtSlot(dict)
    def report_position(self, sdict):
        """Receive a position update from the stage driver and broadcast it to the GUI.

        Writes the new position into :class:`mesoSPIM_StateSingleton` and emits
        ``sig_position`` so the main window can update the position readouts.

        Args:
            sdict (dict): Position dictionary, e.g.
                ``{'x_pos': 0.0, 'y_pos': 0.0, 'z_pos': 0.0, 'f_pos': 0.0, 'theta_pos': 0.0}``.
        """
        logger.debug(f"mesoSPIM_Serial reporting position: {{{', '.join([f'{k!r}: {v:.3f}' if isinstance(v, (int, float)) else f'{k!r}: {v!r}' for k, v in sdict.items()])}}}")
        self.state['position'] = sdict
        self.sig_position.emit({'position': sdict})

    @QtCore.pyqtSlot()
    def go_to_rotation_position(self, wait_until_done=False):
        """Move the rotation axis to the stored rotation/sample-exchange position.

        Args:
            wait_until_done (bool): Block until the rotation is complete.
        """
        logger.debug('Going to rotation position')
        self.stage.go_to_rotation_position(wait_until_done=wait_until_done)

    @QtCore.pyqtSlot(str)
    def set_filter(self, sfilter, wait_until_done=False):
        """Move the filter wheel to the named filter position and update state.

        Args:
            sfilter (str): Filter name as defined in ``cfg.filterdict``.
            wait_until_done (bool): Block until the wheel has settled.
        """
        logger.debug(f'Setting filter to {sfilter}')
        self.filterwheel.set_filter(sfilter, wait_until_done=wait_until_done)
        self.state['filter'] = sfilter

    @QtCore.pyqtSlot(str)
    def set_zoom(self, zoom, wait_until_done=True):
        """Move the zoom body to the named zoom position and update state.

        State is updated *before* the physical move to keep the GUI responsive.

        Args:
            zoom (str): Zoom designation, e.g. ``'2x'``, as defined in ``cfg.zoomdict``.
            wait_until_done (bool): Block until the zoom mechanism has settled.
        """
        ''' Here, the state parameters are set before sending the value to the zoom --
        this is to avoid laggy update loops with the GUI.'''
        self.state['zoom'] = zoom
        self.state['pixelsize'] = self.cfg.pixelsize[zoom]
        self.zoom.set_zoom(zoom, wait_until_done=wait_until_done)

    def execute_stage_program(self):
        """Trigger the pre-loaded Galil/ASI stage program for TTL-driven motion."""
        self.stage.execute_program()
