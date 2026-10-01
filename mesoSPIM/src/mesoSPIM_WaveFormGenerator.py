'''
mesoSPIM Waveform Generator - Creates and allows control of waveform generation.
'''
import os
import numpy as np
import csv
import time

import logging
logger = logging.getLogger(__name__)

'''National Instruments Imports (optional: demo mode runs without them)'''
from .utils.ni_daqmx import nidaqmx, require_nidaqmx
from .utils.ni_daqmx import AcquisitionType, TaskMode, LineGrouping, RegenerationMode, Level, DaqError

'''mesoSPIM imports'''
from .utils.waveforms import single_pulse, tunable_lens_ramp, sawtooth, square, samples_per_sweep
from .utils.utility_functions import log_cpu_core, timed

from PyQt5 import QtCore

class mesoSPIM_WaveFormGenerator(QtCore.QObject):
    '''This class contains the microscope state

    Any access to this global state should only be done via signals sent by
    the responsible class for actually causing that state change in hardware.

    '''
    sig_update_gui_from_state = QtCore.pyqtSignal() # -> mesoSPIM_Core.sig_update_gui_from_state -> MainWindow.update_gui_from_state
    requires_nidaqmx = True # the Demo subclass below sets this to False

    def __init__(self, parent):
        super().__init__()
        if self.requires_nidaqmx:
            require_nidaqmx('NI waveform generation')
        self.cfg = parent.cfg
        self.parent = parent # mesoSPIM_Core object
        self.state = self.parent.state # mesoSPIM_StateSingleton object
        self.parent.sig_save_etl_config.connect(self.save_etl_parameters_to_csv)
        cfg_file = self.parent.read_config_parameter('ETL_cfg_file', self.cfg.startup)
        self.state['ETL_cfg_file'] = cfg_file
        self.update_etl_parameters_from_csv(cfg_file, self.state['laser'], self.state['zoom'])
        self.state['galvo_l_amplitude'] = self.parent.read_config_parameter('galvo_l_amplitude', self.cfg.startup)
        #self.state['galvo_r_amplitude'] = self.parent.read_config_parameter('galvo_r_amplitude', self.cfg.startup)
        self.state['galvo_l_frequency'] = self.parent.read_config_parameter('galvo_l_frequency', self.cfg.startup)
        self.state['galvo_r_frequency'] = self.parent.read_config_parameter('galvo_r_frequency', self.cfg.startup)
        self.state['galvo_l_offset'] = self.parent.read_config_parameter('galvo_l_offset', self.cfg.startup)
        self.state['galvo_r_offset'] = self.parent.read_config_parameter('galvo_r_offset', self.cfg.startup)
        self.state['max_laser_voltage'] = self.parent.read_config_parameter('max_laser_voltage', self.cfg.startup)
        self.MAX_GALVO_ETL_VOLT = 5
        self.config_check()

    def config_check(self):
        '''Check config file for old/wrong/deprecated pieces'''
        if hasattr(self.cfg, 'laser_designation'):
            print("INFO: Config file: The 'laser_designation' dictionary is obsolete, you can remove it.")
        if hasattr(self.cfg, 'galvo_etl_designation'):
            print("INFO: Config file: The 'galvo_etl_designation' dictionary is obsolete, you can remove it.")
        laser_task_line_start = int(self.cfg.acquisition_hardware['laser_task_line'].split(':')[0].split('ao')[-1])
        laser_task_line_end = int(self.cfg.acquisition_hardware['laser_task_line'].split(':')[1])
        if (laser_task_line_end - laser_task_line_start + 1) != len(self.cfg.laserdict):
            raise ValueError(f"Config file: number of AO lines in 'laser_task_line' "
                             f"({self.cfg.acquisition_hardware['laser_task_line']}) "
                             f"must be equal to num(lasers) in 'laserdict' ({len(self.cfg.laserdict)}). "
                             f"Check assignment of AO channels in 'laser_task_line'.")
        if self.state['max_laser_voltage'] > 10:
            self.state['max_laser_voltage'] = 10
            msg = f"Config parameter 'max_laser_voltage' ({self.state['max_laser_voltage']}) is > 10V, which can damage the hardware. Setting to 10V."
            print(msg); logger.warning(msg)
        elif self.state['max_laser_voltage'] > 5:
            msg = f"Config parameter 'max_laser_voltage' ({self.state['max_laser_voltage']}) is > 5V, which may damage the laser controller."
            print(msg); logger.warning(msg)
        
        logger.warning(f"Laser AO task voltage range is +/- {self.state['max_laser_voltage']}V. Check if this is safe for your hardware.")

        logger.warning("Galvo and ETL AO task voltage range is set to -5V to 5V. Check if this is safe for your hardware.")
        self.MAX_GALVO_ETL_VOLT = 5

    def rescale_galvo_amplitude_by_zoom(self, zoom: float):
        if self.state['galvo_amp_scale_w_zoom'] is True:
            galvo_l_amplitude_ini = self.parent.read_config_parameter('galvo_l_amplitude', self.cfg.startup)
            #galvo_r_amplitude_ini = self.parent.read_config_parameter('galvo_r_amplitude', self.cfg.startup)
            zoom_ini = float(self.parent.read_config_parameter('zoom', self.cfg.startup)[:-1])
            self.state['galvo_l_amplitude'] = galvo_l_amplitude_ini * zoom_ini / zoom
            #self.state['galvo_r_amplitude'] = galvo_r_amplitude_ini * zoom_ini / zoom
            logger.info(f"Galvo amplitudes rescaled by {zoom_ini / zoom}")
        else:
            logger.debug('No rescaling of galvo amplitude')

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(), dict.values()):
            logger.debug(f"state change: {key}: {value}")
            if key in ('samplerate',
                       'sweeptime',
                       'intensity',
                       'etl_l_delay_%',
                       'etl_l_ramp_rising_%',
                       'etl_l_ramp_falling_%',
                       'etl_l_amplitude',
                       'etl_l_offset',
                       'etl_r_delay_%',
                       'etl_r_ramp_rising_%',
                       'etl_r_ramp_falling_%',
                       'etl_r_amplitude',
                       'etl_r_offset',
                       'galvo_l_frequency',
                       'galvo_l_amplitude',
                       'galvo_l_offset',
                       'galvo_l_duty_cycle',
                       'galvo_l_phase',
                       'galvo_r_frequency',
                       #'galvo_r_amplitude',
                       'galvo_r_offset',
                       'galvo_r_duty_cycle',
                       'galvo_r_phase',
                       'laser_l_delay_%',
                       'laser_l_pulse_%',
                       'laser_l_max_amplitude',
                       'laser_r_delay_%',
                       'laser_r_pulse_%',
                       'laser_r_max_amplitude',
                       'laser',
                       'camera_delay_%',
                       'camera_pulse_%',
                       'shutterconfig',
                       ):
                self.state[key] = value
                self.create_waveforms() # no GUI update feeding back, one-way signal from the GUI to the hardware
            elif key == 'zoom':
                self.state[key] = value
                self.rescale_galvo_amplitude_by_zoom(float(value.split('x')[0])) # truncate and convert string eg '1.2x BlahBlah' -> 1.2
                self.create_waveforms()
            elif key == 'ETL_cfg_file':
                self.state[key] = value
                self.update_etl_parameters_from_csv(value, self.state['laser'], self.state['zoom']) # feeding back state change to the GUI
            elif key == 'set_etls_according_to_zoom':
                self.update_etl_parameters_from_zoom(value) # feeding back state change to the GUI
            elif key == 'set_etls_according_to_laser':
                self.update_etl_parameters_from_laser(value) # feeding back state change to the GUI
            else:
                pass

    def create_waveforms(self):
        logger.info("waveforms updated")
        self.calculate_samples()
        self.create_etl_waveforms()
        self.create_galvo_waveforms()
        '''Bundle everything'''
        self.bundle_galvo_and_etl_waveforms()
        self.create_laser_waveforms()
        #self.sig_update_gui_from_state.emit() # not necessary, and to minimize looping between state changes and GUI

    def calculate_samples(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate', 'sweeptime'])
        self.samples = samples_per_sweep(samplerate, sweeptime)

    def create_etl_waveforms(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate', 'sweeptime'])
        etl_l_delay, etl_l_ramp_rising, etl_l_ramp_falling, etl_l_amplitude, etl_l_offset = \
            self.state.get_parameter_list(['etl_l_delay_%', 'etl_l_ramp_rising_%', 'etl_l_ramp_falling_%', 'etl_l_amplitude','etl_l_offset'])
        etl_r_delay, etl_r_ramp_rising, etl_r_ramp_falling, etl_r_amplitude, etl_r_offset = \
            self.state.get_parameter_list(['etl_r_delay_%', 'etl_r_ramp_rising_%', 'etl_r_ramp_falling_%', 'etl_r_amplitude', 'etl_r_offset'])

        self.etl_l_waveform = tunable_lens_ramp(samplerate = samplerate,
                                                sweeptime = sweeptime,
                                                delay = etl_l_delay,
                                                rise = etl_l_ramp_rising,
                                                fall = etl_l_ramp_falling,
                                                amplitude = etl_l_amplitude,
                                                offset = etl_l_offset)

        self.etl_r_waveform = tunable_lens_ramp(samplerate = samplerate,
                                                sweeptime = sweeptime,
                                                delay = etl_r_delay,
                                                rise = etl_r_ramp_rising,
                                                fall = etl_r_ramp_falling,
                                                amplitude = etl_r_amplitude,
                                                offset = etl_r_offset)
        # freeze AO channel which is not in use, to reduce heating and increase ETL lifetime
        if self.state['shutterconfig'] == 'Left':
            self.etl_r_waveform[:] = etl_r_offset
            logger.debug("Right arm frozen")
        elif self.state['shutterconfig'] == 'Right':
            self.etl_l_waveform[:] = etl_l_offset
            logger.debug("Left arm frozen")
        else:
            pass

    def create_galvo_waveforms(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])

        galvo_l_frequency, galvo_l_amplitude, galvo_l_offset, galvo_l_duty_cycle, galvo_l_phase =\
        self.state.get_parameter_list(['galvo_l_frequency', 'galvo_l_amplitude', 'galvo_l_offset',
        'galvo_l_duty_cycle', 'galvo_l_phase'])

        galvo_r_frequency, galvo_r_offset, galvo_r_duty_cycle, galvo_r_phase =\
        self.state.get_parameter_list(['galvo_r_frequency', 'galvo_r_offset',  'galvo_r_duty_cycle', 'galvo_r_phase'])

        galvo_r_amplitude = galvo_l_amplitude # always use same amplitude for both galvos

        '''Create Galvo waveforms:'''
        self.galvo_l_waveform = sawtooth(samplerate = samplerate,
                                         sweeptime = sweeptime,
                                         frequency = galvo_l_frequency,
                                         amplitude = galvo_l_amplitude,
                                         offset = galvo_l_offset,
                                         dutycycle = galvo_l_duty_cycle,
                                         phase = galvo_l_phase)

        self.galvo_r_waveform = sawtooth(samplerate = samplerate,
                                         sweeptime = sweeptime,
                                         frequency = galvo_r_frequency,
                                         amplitude = galvo_r_amplitude,
                                         offset = galvo_r_offset,
                                         dutycycle = galvo_r_duty_cycle,
                                         phase = galvo_r_phase)

        # freeze AO channel which is not in use, to reduce heating and increase galvo lifetime
        if self.state['shutterconfig'] == 'Left':
            self.galvo_r_waveform[:] = galvo_r_offset
        elif self.state['shutterconfig'] == 'Right':
            self.galvo_l_waveform[:] = galvo_l_offset
        else:
            pass

    def create_laser_waveforms(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])

        laser_l_delay, laser_l_pulse, max_laser_voltage, intensity = \
        self.state.get_parameter_list(['laser_l_delay_%','laser_l_pulse_%', 'max_laser_voltage', 'intensity'])

        '''Create zero waveforms for the lasers'''
        self.zero_waveform = np.zeros((self.samples))

        '''Update the laser intensity waveform'''
        '''This could be improved: create a list with as many zero arrays as analog out lines for ETL and Lasers'''
        self.laser_waveform_list = [self.zero_waveform for i in self.cfg.laserdict]

        ''' Conversion from % to V of the intensity:'''
        laser_voltage = max_laser_voltage * intensity / 100

        self.laser_template_waveform = single_pulse(samplerate = samplerate,
                                                    sweeptime = sweeptime,
                                                    delay = laser_l_delay,
                                                    pulsewidth = laser_l_pulse,
                                                    amplitude = laser_voltage,
                                                    offset = 0)

        '''The key: replace the waveform in the waveform list with this new template'''
        assert sorted(list(self.cfg.laserdict.keys())) == list(self.cfg.laserdict.keys()), f"Error: laserdict keys in config file must be alphanumerically sorted: {self.cfg.laserdict.keys()}"
        current_laser_index = sorted(list(self.cfg.laserdict.keys())).index(self.state['laser'])
        self.laser_waveform_list[current_laser_index] = self.laser_template_waveform
        self.laser_waveforms = np.stack(self.laser_waveform_list)

    def bundle_galvo_and_etl_waveforms(self):
        """ Stacks the Galvo and ETL waveforms into a numpy array adequate for
        the NI cards.

        In here, the assignment of output channels of the Galvo / ETL card to the
        corresponding output channel is hardcoded: This could be improved.
        """
        self.galvo_and_etl_waveforms = np.stack((self.galvo_l_waveform,
                                                 self.galvo_r_waveform,
                                                 self.etl_l_waveform,
                                                 self.etl_r_waveform))

    def update_etl_parameters_from_zoom(self, zoom):
        """ Little helper method: Because the mesoSPIM core is not handling
        the serial Zoom connection. """
        laser = self.state['laser']
        etl_cfg_file = self.state['ETL_cfg_file']
        self.update_etl_parameters_from_csv(etl_cfg_file, laser, zoom)

    def update_etl_parameters_from_laser(self, laser):
        """ Little helper method: Because laser changes need an ETL parameter update """
        zoom = self.state['zoom']
        etl_cfg_file = os.path.join(self.parent.package_directory, self.state['ETL_cfg_file'])
        self.update_etl_parameters_from_csv(etl_cfg_file, laser, zoom)

    def update_etl_parameters_from_csv(self, cfg_path, laser, zoom):
        """ Updates the internal ETL left/right offsets and amplitudes from the
        values in the ETL csv files

        The .csv file needs to contain the follwing columns:

        Wavelength
        Zoom
        ETL-Left-Offset
        ETL-Left-Amp
        ETL-Right-Offset
        ETL-Right-Amp
        """
        zoom_clean = zoom.split('x')[0] + 'x' # cleanup the zoom string for backwards compatibility with existing ETL files
        full_path = os.path.join(self.parent.package_directory, cfg_path)
        with open(full_path) as file:
            reader = csv.DictReader(file, delimiter=';')
            match_found = False
            for row in reader:
                if row['Wavelength'] == laser and (row['Zoom'] == zoom_clean or row['Zoom'] == zoom):
                    match_found = True
                    # Some diagnostic tracing statements
                    # print(row)
                    ''' updating internal state '''
                    etl_l_offset = float(row['ETL-Left-Offset'])
                    etl_l_amplitude = float(row['ETL-Left-Amp'])
                    etl_r_offset = float(row['ETL-Right-Offset'])
                    etl_r_amplitude = float(row['ETL-Right-Amp'])

                    parameter_dict = {'etl_l_offset': etl_l_offset,
                                      'etl_l_amplitude' : etl_l_amplitude,
                                      'etl_r_offset' : etl_r_offset,
                                      'etl_r_amplitude' : etl_r_amplitude}

                    logger.info(f'Parameters set from csv: {parameter_dict}')
                    self.state.set_parameters(parameter_dict)

        if match_found:
            '''Update waveforms with the new parameters'''
            self.create_waveforms()
        else:
            err_message = f"Combination {laser} - {zoom} not found in ETL file. The file will be updated:\n{cfg_path}"
            self.parent.sig_warning.emit(err_message)
            self.save_etl_parameters_to_csv()
        self.sig_update_gui_from_state.emit()

    @QtCore.pyqtSlot()
    def save_etl_parameters_to_csv(self):
        """ Saves the current ETL left/right offsets and amplitudes from the
        values to the ETL csv files

        The .csv file needs to contain the following columns:

        Wavelength
        Zoom
        ETL-Left-Offset
        ETL-Left-Amp
        ETL-Right-Offset
        ETL-Right-Amp

        Creates a temporary cfg file with the ending _tmp
        """

        etl_cfg_file, laser, zoom, etl_l_offset, etl_l_amplitude, etl_r_offset, etl_r_amplitude = \
        self.state.get_parameter_list(['ETL_cfg_file', 'laser', 'zoom', 'etl_l_offset', 'etl_l_amplitude', 'etl_r_offset','etl_r_amplitude'])

        '''Temporary filepath'''
        etl_cfg_file = os.path.join(self.parent.package_directory, etl_cfg_file)
        tmp_etl_cfg_file = etl_cfg_file+'_tmp'
        with open(etl_cfg_file,'r') as input_file, open(tmp_etl_cfg_file,'w') as outputfile:
            reader = csv.DictReader(input_file, delimiter=';')
            fieldnames = ['Objective',
                          'Wavelength',
                          'Zoom',
                          'ETL-Left-Offset',
                          'ETL-Left-Amp',
                          'ETL-Right-Offset',
                          'ETL-Right-Amp']

            writer = csv.DictWriter(outputfile, fieldnames=fieldnames, dialect='excel', delimiter=';')
            writer.writeheader()
            match_found = False
            for row in reader:
                # update values if the laser and zoom are already in the file
                if row['Wavelength'] == laser and row['Zoom'] == zoom:
                        writer.writerow({'Objective' : '1x',
                                         'Wavelength' : laser,
                                         'Zoom' : zoom,
                                         'ETL-Left-Offset' : etl_l_offset,
                                         'ETL-Left-Amp' : etl_l_amplitude,
                                         'ETL-Right-Offset' : etl_r_offset,
                                         'ETL-Right-Amp' : etl_r_amplitude,
                                         })
                        match_found = True
                else:
                    # copy all other rows
                    writer.writerow(row)
            if not match_found:
                writer.writerow({'Objective' : '1x',
                                 'Wavelength' : laser,
                                 'Zoom' : zoom,
                                 'ETL-Left-Offset' : etl_l_offset,
                                 'ETL-Left-Amp' : etl_l_amplitude,
                                 'ETL-Right-Offset' : etl_r_offset,
                                 'ETL-Right-Amp' : etl_r_amplitude,
                                 })
        os.remove(etl_cfg_file)
        os.rename(tmp_etl_cfg_file, etl_cfg_file)

    @timed
    def create_tasks(self):
        """Creates a tasks for the mesoSPIM:

        These are:
        - the master trigger task, a digital out task that only provides a trigger pulse for the others
        - the camera trigger task, a counter task that triggers the camera in lightsheet mode
        - the stage trigger task, a counter task that provides a TTL trigger for stages that allow triggered movement (e.g. ASI stages)
        - the galvo and ETL task (analog out) that controls the left & right galvos for creation of
          the light-sheet and shadow avoidance
        - the aser task (analog out) that controls all the laser intensities (Laser should only
          be on when the camera is acquiring) and the left/right ETL waveforms.
          This task is bundled with galvo-ETL task if a single DAQmx card is used, because multifunction DAQmx devices
          can only run only 1 AO hardware-timed task at a time (https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z0000019KWYSA2&l=en-CH)
        """
        ah = self.cfg.acquisition_hardware

        self.calculate_samples()
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        samples = self.samples
        camera_pulse_percent, camera_delay_percent = self.state.get_parameter_list(['camera_pulse_%','camera_delay_%'])
        self.master_trigger_task = nidaqmx.Task()
        self.camera_trigger_task = nidaqmx.Task()
        if 'asi' in self.cfg.stage_parameters['stage_type'].lower() or self.cfg.stage_parameters['stage_type'].lower() == 'mixed':
            self.stage_trigger_task = nidaqmx.Task()

        # Check if 1 or 2 DAQ cards are used for AO waveform generation
        self.ao_cards = 1 if ah['galvo_etl_task_line'].split('/')[-2] == ah['laser_task_line'].split('/')[-2] else 2
        logger.info(f"Using {self.ao_cards} DAQmx card(s) for AO waveform generation.")

        # ADD THIS: Close existing task if it exists
        if self.ao_cards == 1:
            # These AO tasks than must be bundled into one task if a single DAQmx card is used (e.g. PXI-6733)
            self.galvo_etl_laser_task = nidaqmx.Task()
        else:
            self.galvo_etl_task = nidaqmx.Task()
            self.laser_task = nidaqmx.Task()

        '''Housekeeping: Setting up the DO master trigger task'''
        self.master_trigger_task.do_channels.add_do_chan(ah['master_trigger_out_line'],
                                                         line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        if self.cfg.waveformgeneration == 'cDAQ':
            self.master_trigger_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement
            logger.debug("cDAQ: master_trigger_task reserved.")

        '''Calculate camera high time and initial delay:
        Disadvantage: high time and delay can only be set after a task has been created
        '''
        self.camera_high_time = camera_pulse_percent*0.01*sweeptime
        self.camera_delay = camera_delay_percent*0.01*sweeptime

        '''Housekeeping: Setting up the counter task for the camera trigger'''
        self.camera_trigger_task.co_channels.add_co_pulse_chan_time(ah['camera_trigger_out_line'],
                                                                    high_time=self.camera_high_time,
                                                                    initial_delay=self.camera_delay)

        self.camera_trigger_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['camera_trigger_source'])
        if self.cfg.waveformgeneration == 'cDAQ':
            self.camera_trigger_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement
            logger.debug("cDAQ: camera_trigger_task reserved.")

        '''Housekeeping: Setting up the counter task for the stage TTL trigger for certain stages'''
        if 'asi' in self.cfg.stage_parameters['stage_type'].lower() or self.cfg.stage_parameters['stage_type'].lower() == 'mixed':
            assert hasattr(self.cfg, 'asi_parameters'), "Config file with an ASI stage must contain 'asi_parameters' dictionary"
            trig_line = self.parent.read_config_parameter('stage_trigger_out_line', self.cfg.asi_parameters)
            trig_source = self.parent.read_config_parameter('stage_trigger_source', self.cfg.asi_parameters)
            stage_trigger_pulse_percent = self.parent.read_config_parameter('stage_trigger_pulse_%', self.cfg.asi_parameters)
            stage_delay_percent = self.parent.read_config_parameter('stage_trigger_delay_%', self.cfg.asi_parameters)
            stage_high_time = stage_trigger_pulse_percent * 0.01 * sweeptime
            stage_delay = stage_delay_percent * 0.01 * sweeptime
            self.stage_trigger_task.co_channels.add_co_pulse_chan_time(trig_line, high_time=stage_high_time, initial_delay=stage_delay)
            self.stage_trigger_task.triggers.start_trigger.cfg_dig_edge_start_trig(trig_source)
            if self.cfg.waveformgeneration == 'cDAQ':
                self.stage_trigger_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement
                logger.debug("cDAQ: stage_trigger_task reserved.")

        '''Housekeeping: Setting up the AO task for the Galvo and setting the trigger input'''
        if self.ao_cards == 2: # default mesoSPIM v5 configuration
            self.galvo_etl_task.ao_channels.add_ao_voltage_chan(ah['galvo_etl_task_line'], min_val = -self.MAX_GALVO_ETL_VOLT, max_val = self.MAX_GALVO_ETL_VOLT)
            self.galvo_etl_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                       sample_mode=AcquisitionType.FINITE,
                                                       samps_per_chan=samples)
            self.galvo_etl_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['galvo_etl_task_trigger_source'])
            if self.cfg.waveformgeneration == 'cDAQ':
                self.galvo_etl_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement
                logger.debug("cDAQ: galvo_etl_task reserved.")

            '''Housekeeping: Setting up the AO task for the ETL and lasers and setting the trigger input'''
            self.laser_task.ao_channels.add_ao_voltage_chan(ah['laser_task_line'],
                                                            min_val=-self.state['max_laser_voltage'],
                                                            max_val=self.state['max_laser_voltage'])
            self.laser_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                        sample_mode=AcquisitionType.FINITE,
                                                        samps_per_chan=samples)
            self.laser_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['laser_task_trigger_source'])
            if self.cfg.waveformgeneration == 'cDAQ':
                self.laser_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement
                logger.debug("cDAQ: laser_task reserved.")

        else: # Benchtop single-card PXI NI-6733 or cDAQ NI-9264 configuration
            self.galvo_etl_laser_task.ao_channels.add_ao_voltage_chan(ah['galvo_etl_task_line'] + ',' + ah['laser_task_line'],
                                                                      min_val = -self.MAX_GALVO_ETL_VOLT, max_val = self.MAX_GALVO_ETL_VOLT)
            self.galvo_etl_laser_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                       sample_mode=AcquisitionType.FINITE,
                                                       samps_per_chan=samples)
            self.galvo_etl_laser_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['galvo_etl_task_trigger_source'])
            if self.cfg.waveformgeneration == 'cDAQ':
                self.galvo_etl_laser_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement
                logger.debug("cDAQ: galvo_etl_laser_task reserved.")

    @timed
    def write_waveforms_to_tasks(self):
        """Write the waveforms to the slave tasks"""
        if self.ao_cards == 2:
            self.galvo_etl_task.write(self.galvo_and_etl_waveforms)
            self.laser_task.write(self.laser_waveforms)
        else:
            logger.debug(f"Writing analog waveforms: self.galvo_and_etl_waveforms, min {self.galvo_and_etl_waveforms.min()}, max {self.galvo_and_etl_waveforms.max()}")
            logger.debug(f"Writing analog waveforms: self.laser_waveforms, min {self.laser_waveforms.min()}, max {self.laser_waveforms.max()}")
            self.galvo_etl_laser_task.write(np.vstack((self.galvo_and_etl_waveforms, self.laser_waveforms)))

    @timed
    def start_tasks(self):
        """Starts the tasks for camera triggering and analog outputs

        If the tasks are configured to be triggered, they won't output any
        signals until run_tasks() is called.
        """
        self.camera_trigger_task.start()
        if 'asi' in self.cfg.stage_parameters['stage_type'].lower() or self.cfg.stage_parameters['stage_type'].lower() == 'mixed':
            self.stage_trigger_task.start()
        if self.ao_cards == 2:
            self.galvo_etl_task.start()
            self.laser_task.start()
        else:
            self.galvo_etl_laser_task.start()

    @timed
    def run_tasks(self):
        """Runs the tasks for triggering, analog and counter outputs

        Firstly, the master trigger triggers all other task via a shared trigger
        line (PFI line as given in the config file).

        For this to work, all analog output and counter tasks have to be started so
        that they are waiting for the trigger signal.

        Warning: `master_trigger_task` does not have explicit sample rate, because some cards like NI-6733 do not support this for DO lines.
        So the master pulse duration varies depening on the device. Can be as short as small as 1 micro-second!
        """
        logger.debug("Starting master trigger")
        self.master_trigger_task.write([False, True, True, True, True, True, False], auto_start=True)
        logger.debug("Master trigger started")

        '''Wait until everything is done - this is effectively a sleep function.'''
        if self.ao_cards == 2:
            self.galvo_etl_task.wait_until_done()
            self.laser_task.wait_until_done() 
        else:
            self.galvo_etl_laser_task.wait_until_done()
        logger.debug("AO tasks wait_until_done() finished")
        self.camera_trigger_task.wait_until_done() 
        logger.debug("camera_trigger_task.wait_until_done() finished")
        if 'asi' in self.cfg.stage_parameters['stage_type'].lower() or self.cfg.stage_parameters['stage_type'].lower() == 'mixed':
            self.stage_trigger_task.wait_until_done()
            logger.debug("stage_trigger_task.wait_until_done() finished")

    @timed
    def stop_tasks(self):
        """Stops the tasks for triggering, analog and counter outputs"""
        logger.debug("Stopping task initiated")
        if self.ao_cards == 2:
            self.galvo_etl_task.stop()
            self.laser_task.stop()
        else:
            self.galvo_etl_laser_task.stop()
        self.camera_trigger_task.stop()
        if 'asi' in self.cfg.stage_parameters['stage_type'].lower() or self.cfg.stage_parameters['stage_type'].lower() == 'mixed':
            self.stage_trigger_task.stop()
        self.master_trigger_task.stop()
        logger.debug("All tasks stopped")

    @timed
    def close_tasks(self):
        """Closes the tasks for triggering, analog and counter outputs.
        Tasks should only be closed after they are stopped.
        """
        logger.debug("Closing tasks started")
        if self.ao_cards == 2:
            self.galvo_etl_task.close()
            self.laser_task.close()
        else:
            self.galvo_etl_laser_task.close()
        self.camera_trigger_task.close()
        if 'asi' in self.cfg.stage_parameters['stage_type'].lower() or self.cfg.stage_parameters['stage_type'].lower() == 'mixed':
            self.stage_trigger_task.close()
        self.master_trigger_task.close()
        logger.debug("All tasks closed")

    # ------------------------------------------------------------------
    # Continuous-regeneration mode (acquisition_hardware['waveform_mode'] = 'continuous')
    #
    # Instead of arming, triggering, waiting for and stopping the DAQ tasks once per
    # plane, the whole stack is configured once and launched by one master trigger:
    #   * the AO task runs CONTINUOUS with regeneration: the one-sweep buffer repeats;
    #   * the camera trigger is a FINITE counter pulse train of n_planes pulses;
    #   * the stage trigger is a FINITE pulse train of n_planes-1 TTL steps.
    # Planes stay orthogonal to z (step-and-shoot); only the per-plane software
    # overhead goes away. Works on the PXI-6733 and the cDAQ NI-9264, which support
    # regeneration but not native retriggering.
    #
    # The counters MUST share the AO waveform's period exactly, or the light-sheet
    # sweep slides against the camera's rolling shutter a little more on every plane
    # (the progressive right-edge blur seen on the first bench tests). So:
    #   1. preferred: the counters count ticks of the AO sample clock itself
    #      (period = samples ticks), which is drift-free by construction;
    #   2. fallback, if the device cannot route the AO sample clock to the counter:
    #      time-based pulses at the AO's actual (coerced) period, read back from the
    #      driver, and the launch is refused if the residual drift over the stack
    #      exceeds half a sample.
    # ------------------------------------------------------------------
    MAX_STACK_DRIFT_SAMPLES = 0.5

    def _uses_stage_trigger(self):
        stage_type = self.cfg.stage_parameters['stage_type'].lower()
        return 'asi' in stage_type or stage_type == 'mixed'

    def _reserve(self, task):
        '''Verify and reserve a task now, so coerced rates and routing errors are known before launch.

        Reserve, not commit: on cDAQ the NI 9401 refuses to commit one task while another
        task on the same module is committed (DAQmx -201133); every task has to be
        reserved before any of them is committed, which start_tasks() then does.
        '''
        task.control(TaskMode.TASK_RESERVE)

    _CONTINUOUS_TASK_ATTRS = ('master_trigger_task', 'galvo_etl_laser_task', 'galvo_etl_task', 'laser_task',
                              'camera_trigger_task', 'stage_trigger_task')

    @timed
    def create_tasks_continuous(self, n_planes):
        """Create the DAQ tasks for a whole stack launched by a single master trigger.

        On any failure every task created so far is closed again, so a half-built
        set never holds the device reserved for the next acquisition.

        Args:
            n_planes (int): Number of planes (camera frames) in the stack.
        """
        for attr in self._CONTINUOUS_TASK_ATTRS:
            setattr(self, attr, None)
        try:
            self._create_tasks_continuous(n_planes)
        except Exception:
            for attr in self._CONTINUOUS_TASK_ATTRS:
                task = getattr(self, attr, None)
                if task is not None:
                    try:
                        task.close()
                    except Exception:
                        pass
                    setattr(self, attr, None)
            raise

    def _create_tasks_continuous(self, n_planes):
        ah = self.cfg.acquisition_hardware
        self.calculate_samples()
        samplerate = self.state['samplerate']
        samples = self.samples
        n_planes = int(n_planes)
        for name in ('galvo_and_etl_waveforms', 'laser_waveforms'):
            length = getattr(self, name).shape[-1]
            if length != samples:
                raise RuntimeError(f"[continuous] {name} has {length} samples per sweep, expected {samples}; "
                                   f"the regenerated AO buffer would not match the trigger period.")

        self.ao_cards = 1 if ah['galvo_etl_task_line'].split('/')[-2] == ah['laser_task_line'].split('/')[-2] else 2
        logger.info(f"[continuous] {n_planes} planes, {samples} samples/sweep at {samplerate} S/s, "
                    f"{self.ao_cards} AO card(s).")

        self.master_trigger_task = nidaqmx.Task()
        self.master_trigger_task.do_channels.add_do_chan(ah['master_trigger_out_line'],
                                                         line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        if self.cfg.waveformgeneration == 'cDAQ':
            self.master_trigger_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement

        '''AO: CONTINUOUS with regeneration. The task that drives the galvos and ETLs is the timing reference.'''
        def make_ao_task(lines, vmax, trigger_source, clock_source=None):
            task = nidaqmx.Task()
            try:
                task.ao_channels.add_ao_voltage_chan(lines, min_val=-vmax, max_val=vmax)
                kwargs = dict(rate=samplerate, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=samples)
                if clock_source:
                    kwargs['source'] = clock_source
                task.timing.cfg_samp_clk_timing(**kwargs)
                task.out_stream.regen_mode = RegenerationMode.ALLOW_REGENERATION
                task.triggers.start_trigger.cfg_dig_edge_start_trig(trigger_source)
                self._reserve(task)
            except Exception:
                task.close()
                raise
            return task

        if self.ao_cards == 1:
            self.galvo_etl_laser_task = make_ao_task(ah['galvo_etl_task_line'] + ',' + ah['laser_task_line'],
                                                     self.MAX_GALVO_ETL_VOLT, ah['galvo_etl_task_trigger_source'])
            ref_task = self.galvo_etl_laser_task
        else:
            self.galvo_etl_task = make_ao_task(ah['galvo_etl_task_line'], self.MAX_GALVO_ETL_VOLT,
                                               ah['galvo_etl_task_trigger_source'])
            ref_task = self.galvo_etl_task
            # Lock the laser card to the galvo/ETL card's sample clock, otherwise two
            # independent oscillators drift apart over the stack as well.
            try:
                self.laser_task = make_ao_task(ah['laser_task_line'], self.state['max_laser_voltage'],
                                               ah['laser_task_trigger_source'],
                                               clock_source=ref_task.timing.samp_clk_term)
                logger.info(f"[continuous] laser AO clocked from {ref_task.timing.samp_clk_term}")
            except DaqError as e:
                logger.warning(f"[continuous] laser AO cannot use the galvo/ETL sample clock ({e}); "
                               f"using its own clock, so lasers may drift against the galvos over long stacks.")
                self.laser_task = make_ao_task(ah['laser_task_line'], self.state['max_laser_voltage'],
                                               ah['laser_task_trigger_source'])

        ao_rate = ref_task.timing.samp_clk_rate  # actual (coerced) rate, may differ from the requested one
        ao_clock = ref_task.timing.samp_clk_term
        self.continuous_plane_period = samples / ao_rate
        if abs(ao_rate - samplerate) > 1e-6 * samplerate:
            logger.warning(f"[continuous] AO sample clock coerced from {samplerate} to {ao_rate} S/s")

        '''Counters: camera (n_planes pulses) and stage (n_planes-1 steps).'''
        camera_pulse_percent, camera_delay_percent = self.state.get_parameter_list(['camera_pulse_%', 'camera_delay_%'])
        pulses = [('camera_trigger_task', ah['camera_trigger_out_line'], ah['camera_trigger_source'],
                   camera_delay_percent, camera_pulse_percent, n_planes)]
        if self._uses_stage_trigger():
            assert hasattr(self.cfg, 'asi_parameters'), "Config file with an ASI stage must contain 'asi_parameters' dictionary"
            read = lambda key: self.parent.read_config_parameter(key, self.cfg.asi_parameters)
            pulses.append(('stage_trigger_task', read('stage_trigger_out_line'), read('stage_trigger_source'),
                           read('stage_trigger_delay_%'), read('stage_trigger_pulse_%'), max(n_planes - 1, 1)))

        try:
            for attr, line, trig, delay_pct, pulse_pct, count in pulses:
                setattr(self, attr, self._make_tick_counter(line, ao_clock, samples, delay_pct, pulse_pct, count))
            self.continuous_timing_mode = 'ao_sample_clock_ticks'
            logger.info(f"[continuous] counters clocked from the AO sample clock {ao_clock}: "
                        f"period {samples} ticks = {self.continuous_plane_period * 1e3:.4f} ms, drift-free")
        except DaqError as e:
            logger.warning(f"[continuous] cannot clock the counters from {ao_clock} ({e}); "
                           f"falling back to time-based counter pulses matched to the AO period.")
            for attr, *_ in pulses:
                task = getattr(self, attr, None)
                if task is not None:
                    try:
                        task.close()
                    except Exception:
                        pass
                    setattr(self, attr, None)
            for attr, line, trig, delay_pct, pulse_pct, count in pulses:
                setattr(self, attr, self._make_time_counter(line, trig, ao_rate, samples, delay_pct, pulse_pct, count, n_planes))
            self.continuous_timing_mode = 'time_matched'

    def _make_tick_counter(self, line, ao_clock, samples, delay_pct, pulse_pct, count):
        '''Pulse train counting AO sample-clock ticks: rising edges at delay + k*samples.'''
        high = max(2, int(round(samples * pulse_pct * 0.01)))
        low = samples - high
        delay = max(2, int(round(samples * delay_pct * 0.01)))
        if low < 2:
            raise ValueError(f"[continuous] pulse of {pulse_pct}% leaves no low time in a {samples}-tick period")
        task = nidaqmx.Task()
        try:
            task.co_channels.add_co_pulse_chan_ticks(line, source_terminal=ao_clock, idle_state=Level.LOW,
                                                     initial_delay=delay, low_ticks=low, high_ticks=high)
            task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.FINITE, samps_per_chan=count)
            # No start trigger on purpose: the AO sample clock only ticks once the AO task
            # has been triggered, so an armed counter starts on exactly the first AO sample.
            # A digital start trigger would be sampled on this slow external source and
            # could miss the short master pulse.
            self._reserve(task)
        except Exception:
            task.close()
            raise
        return task

    def _make_time_counter(self, line, trigger_source, ao_rate, samples, delay_pct, pulse_pct, count, n_planes):
        '''Fallback: time-based pulse train at the AO's actual period, refused if it would drift.'''
        period = samples / ao_rate
        task = nidaqmx.Task()
        try:
            ch = task.co_channels.add_co_pulse_chan_freq(line, freq=1.0 / period,
                                                         duty_cycle=min(max(pulse_pct * 0.01, 1e-3), 0.999),
                                                         initial_delay=delay_pct * 0.01 * period)
            task.timing.cfg_implicit_timing(sample_mode=AcquisitionType.FINITE, samps_per_chan=count)
            task.triggers.start_trigger.cfg_dig_edge_start_trig(trigger_source)
            self._reserve(task)
            actual_period = 1.0 / ch.co_pulse_freq  # coerced to the counter timebase
        except Exception:
            task.close()
            raise
        drift_samples = abs(actual_period - period) * n_planes * ao_rate
        logger.info(f"[continuous] {line}: counter period {actual_period * 1e3:.6f} ms vs AO {period * 1e3:.6f} ms, "
                    f"drift over {n_planes} planes = {drift_samples:.3f} samples")
        if drift_samples > self.MAX_STACK_DRIFT_SAMPLES:
            task.close()
            raise RuntimeError(f"[continuous] {line} cannot match the AO period: the light sheet would drift "
                               f"{drift_samples:.1f} samples against the camera over {n_planes} planes. "
                               f"Choose a sweeptime that is a whole number of counter-timebase ticks, "
                               f"or use waveform_mode 'stepped'.")
        return task

    def launch_continuous(self):
        """Fire the single master trigger that launches the whole hardware-timed stack.

        Call after write_waveforms_to_tasks() and start_tasks(), and after the shutters
        are open and the laser is enabled, so the first plane is not dark.
        """
        logger.debug("[continuous] firing single master trigger for the whole stack")
        self.master_trigger_task.write([False, True, True, True, True, True, False], auto_start=True)

    def wait_for_stack_done(self, timeout=-1.0):
        """Block until the finite camera pulse train has emitted all its pulses."""
        self.camera_trigger_task.wait_until_done(timeout=timeout)

    def park_ao_outputs(self):
        """Hold every AO line at the last sample of its waveform after a continuous stack.

        Stopping a regenerating task leaves each line at whatever sample was playing,
        e.g. a laser modulation voltage mid-pulse. A stepped (finite) sweep always ends
        on its last sample -- lasers off, galvos and ETLs at the sweep end -- so park there.
        Call only after close_tasks(), when the AO lines are free.
        """
        ah = self.cfg.acquisition_hardware
        if self.ao_cards == 1:
            groups = [(ah['galvo_etl_task_line'] + ',' + ah['laser_task_line'], self.MAX_GALVO_ETL_VOLT,
                       np.vstack((self.galvo_and_etl_waveforms, self.laser_waveforms))[:, -1])]
        else:
            groups = [(ah['galvo_etl_task_line'], self.MAX_GALVO_ETL_VOLT, self.galvo_and_etl_waveforms[:, -1]),
                      (ah['laser_task_line'], self.state['max_laser_voltage'], self.laser_waveforms[:, -1])]
        for lines, vmax, values in groups:
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(lines, min_val=-vmax, max_val=vmax)
                task.write([float(v) for v in values], auto_start=True)
        logger.debug("[continuous] AO outputs parked at the sweep-end values")


class mesoSPIM_DemoWaveFormGenerator(mesoSPIM_WaveFormGenerator):
    """Demo subclass of mesoSPIM_WaveFormGenerator class

    Every method that touches a DAQmx task is overridden below, so this class
    runs without the `nidaqmx` package and without the NI-DAQmx driver.
    """
    requires_nidaqmx = False

    def __init__(self, parent):
        super().__init__(parent)

    def create_tasks(self):
        """"Demo version of the actual DAQmx-based function."""
        logger.debug("Demo: create tasks")
        self.calculate_samples()
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        camera_pulse_percent, camera_delay_percent = self.state.get_parameter_list(['camera_pulse_%','camera_delay_%'])
        self.camera_high_time = camera_pulse_percent*0.01*sweeptime
        self.camera_delay = camera_delay_percent*0.01*sweeptime

    def write_waveforms_to_tasks(self):
        """Demo: write the waveforms to the slave tasks """
        logger.debug("Demo: write waveforms to tasks")
        pass

    def start_tasks(self):
        """Demo: starts the tasks for camera triggering and analog outputs. """
        logger.debug("Demo: start tasks")
        pass

    def run_tasks(self):
        """Demo: runs the tasks for triggering, analog and counter outputs. """
        logger.debug("Demo: run tasks")
        time.sleep(self.state['sweeptime'])

    def stop_tasks(self):
        """"Demo: stop tasks"""
        logger.debug("Demo: stop tasks")
        pass

    def close_tasks(self):
        """Demo: closes the tasks for triggering, analog and counter outputs. """
        logger.debug("Demo: close tasks")
        pass

    def create_tasks_continuous(self, n_planes):
        """Demo: no DAQ tasks; keep the period bookkeeping the Core relies on."""
        logger.debug(f"Demo: create continuous tasks ({n_planes} planes)")
        self.calculate_samples()
        self.continuous_plane_period = self.samples / self.state['samplerate']
        self.continuous_timing_mode = 'demo'

    def launch_continuous(self):
        logger.debug("Demo: launch continuous")

    def wait_for_stack_done(self, timeout=-1.0):
        logger.debug("Demo: wait for stack done")

    def park_ao_outputs(self):
        logger.debug("Demo: park AO outputs")
