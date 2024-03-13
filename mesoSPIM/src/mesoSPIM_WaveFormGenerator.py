'''
mesoSPIM Waveform Generator - Creates and allows control of waveform generation.
'''
import os
import numpy as np
import csv
import time

import logging
logger = logging.getLogger(__name__)

'''National Instruments Imports'''
import nidaqmx
from nidaqmx.constants import AcquisitionType, TaskMode
from nidaqmx.constants import LineGrouping, DigitalWidthUnits
from nidaqmx.types import CtrTime

'''mesoSPIM imports'''
from .mesoSPIM_State import mesoSPIM_StateSingleton
from .utils.waveforms import single_pulse, tunable_lens_ramp, sawtooth, square

from PyQt5 import QtCore

class mesoSPIM_WaveFormGenerator(QtCore.QObject):
    '''This class contains the microscope state

    Any access to this global state should only be done via signals sent by
    the responsible class for actually causing that state change in hardware.

    '''
    sig_update_gui_from_state = QtCore.pyqtSignal(bool) # -> mesoSPIM_Core.sig_update_gui_from_state -> MainWindow.enable_gui_updates_from_state

    def __init__(self, parent):
        super().__init__()
        self.cfg = parent.cfg
        self.parent = parent # mesoSPIM_Core object
        self.state = mesoSPIM_StateSingleton()
        self.parent.sig_save_etl_config.connect(self.save_etl_parameters_to_csv)
        cfg_file = self.parent.read_config_parameter('ETL_cfg_file', self.cfg.startup)
        self.state['ETL_cfg_file'] = cfg_file
        self.update_etl_parameters_from_csv(cfg_file, self.state['laser'], self.state['zoom'])
        self.state['galvo_l_amplitude'] = self.parent.read_config_parameter('galvo_l_amplitude', self.cfg.startup)
        self.state['galvo_r_amplitude'] = self.parent.read_config_parameter('galvo_r_amplitude', self.cfg.startup)
        self.state['galvo_l_frequency'] = self.parent.read_config_parameter('galvo_l_frequency', self.cfg.startup)
        self.state['galvo_r_frequency'] = self.parent.read_config_parameter('galvo_r_frequency', self.cfg.startup)
        self.state['galvo_l_offset'] = self.parent.read_config_parameter('galvo_l_offset', self.cfg.startup)
        self.state['galvo_r_offset'] = self.parent.read_config_parameter('galvo_r_offset', self.cfg.startup)
        self.state['max_laser_voltage'] = self.parent.read_config_parameter('max_laser_voltage', self.cfg.startup)
        self.config_check()

    def config_check(self):
        '''Check config file for old/wrong/deprecated pieces'''
        if hasattr(self.cfg, 'laser_designation'):
            print("INFO: Config file: The 'laser_designation' dictionary is obsolete, you can remove it.")
        if hasattr(self.cfg, 'galvo_etl_designation'):
            print("INFO: Config file: The 'galvo_etl_designation' dictionary is obsolete, you can remove it.")
        laser_task_line_start = int(self.cfg.acquisition_hardware['laser_task_line'].split(':')[0][-1])
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

    def rescale_galvo_amplitude_by_zoom(self, zoom: float):
        if self.state['galvo_amp_scale_w_zoom'] is True:
            galvo_l_amplitude_ini = self.parent.read_config_parameter('galvo_l_amplitude', self.cfg.startup)
            galvo_r_amplitude_ini = self.parent.read_config_parameter('galvo_r_amplitude', self.cfg.startup)
            zoom_ini = float(self.parent.read_config_parameter('zoom', self.cfg.startup)[:-1])
            self.state['galvo_l_amplitude'] = galvo_l_amplitude_ini * zoom_ini / zoom
            self.state['galvo_r_amplitude'] = galvo_r_amplitude_ini * zoom_ini / zoom
            logger.info(f"Galvo amplitudes rescaled by {zoom_ini / zoom}")
        else:
            logger.debug('No rescaling of galvo amplitude')

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(), dict.values()):
            self.sig_update_gui_from_state.emit(True) # Notify GUI about the change
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
                       'galvo_r_amplitude',
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
                self.create_waveforms()
            elif key == 'zoom':
                self.state[key] = value
                self.rescale_galvo_amplitude_by_zoom(float(value[:-1])) # truncate and convert string eg '1.2x' -> 1.2
                self.create_waveforms()
            elif key == 'ETL_cfg_file':
                self.state[key] = value
                self.update_etl_parameters_from_csv(value, self.state['laser'], self.state['zoom'])
            elif key == 'set_etls_according_to_zoom':
                self.update_etl_parameters_from_zoom(value)
            elif key == 'set_etls_according_to_laser':
                self.update_etl_parameters_from_laser(value)
            elif key == 'state':
                if value == 'live':
                    logger.debug('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))
            self.sig_update_gui_from_state.emit(False) # Stop updating GUI about the change

    def calculate_samples(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate', 'sweeptime'])
        self.samples = int(samplerate*sweeptime)

    def create_waveforms(self):
        logger.info("waveforms updated")
        self.calculate_samples()
        self.create_etl_waveforms()
        self.create_galvo_waveforms()
        '''Bundle everything'''
        self.bundle_galvo_and_etl_waveforms()
        self.create_laser_waveforms()

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

        galvo_r_frequency, galvo_r_amplitude, galvo_r_offset, galvo_r_duty_cycle, galvo_r_phase =\
        self.state.get_parameter_list(['galvo_r_frequency', 'galvo_r_amplitude', 'galvo_r_offset',
        'galvo_r_duty_cycle', 'galvo_r_phase'])

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
        self.sig_update_gui_from_state.emit(True)
        full_path = os.path.join(self.parent.package_directory, cfg_path)
        with open(full_path) as file:
            reader = csv.DictReader(file, delimiter=';')
            match_found = False
            for row in reader:
                if row['Wavelength'] == laser and row['Zoom'] == zoom:
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

                    '''  Now the GUI needs to be updated '''
                    # time.sleep(0.2) # possible freezing here
                    logger.info(f'Parameters set from csv: {parameter_dict}')
                    self.state.set_parameters(parameter_dict)

        if match_found:
            '''Update waveforms with the new parameters'''
            self.create_waveforms()
        else:
            err_message = f"Laser {laser} - zoom {zoom} combination not found in ETL file. Update the file:\n{cfg_path}"
            print("Error: " + err_message)
            logger.error(err_message)
        self.sig_update_gui_from_state.emit(False)

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
        self.state.get_parameter_list(['ETL_cfg_file', 'laser', 'zoom',
        'etl_l_offset', 'etl_l_amplitude', 'etl_r_offset','etl_r_amplitude'])

        '''Temporary filepath'''
        etl_cfg_file = os.path.join(self.parent.package_directory, etl_cfg_file)
        tmp_etl_cfg_file = etl_cfg_file+'_tmp'
        with open(etl_cfg_file,'r') as input_file, open(tmp_etl_cfg_file,'w') as outputfile:
            reader = csv.DictReader(input_file,delimiter=';')
            #print('created reader')
            fieldnames = ['Objective',
                          'Wavelength',
                          'Zoom',
                          'ETL-Left-Offset',
                          'ETL-Left-Amp',
                          'ETL-Right-Offset',
                          'ETL-Right-Amp']

            writer = csv.DictWriter(outputfile,fieldnames=fieldnames,dialect='excel',delimiter=';')
            writer.writeheader()
            for row in reader:
                if row['Wavelength'] == laser and row['Zoom'] == zoom:
                        writer.writerow({'Objective' : '1x',
                                         'Wavelength' : laser,
                                         'Zoom' : zoom,
                                         'ETL-Left-Offset' : etl_l_offset,
                                         'ETL-Left-Amp' : etl_l_amplitude,
                                         'ETL-Right-Offset' : etl_r_offset,
                                         'ETL-Right-Amp' : etl_r_amplitude,
                                         })
                else:
                    writer.writerow(row)
            writer.writerows(reader)
        os.remove(etl_cfg_file)
        os.rename(tmp_etl_cfg_file, etl_cfg_file)

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
        if self.cfg.stage_parameters['stage_type'] in {'TigerASI'}:
            self.stage_trigger_task = nidaqmx.Task()

        # Check if 1 or 2 DAQ cards are used for AO waveform generation
        self.ao_cards = 1 if ah['galvo_etl_task_line'].split('/')[-2] == ah['laser_task_line'].split('/')[-2] else 2
        logger.info(f"Using {self.ao_cards} DAQmx card(s) for AO waveform generation.")

        if self.ao_cards == 1:
            # These AO tasks than must be bundled into one task if a single DAQmx card is used (e.g. PXI-6733)
            self.galvo_etl_laser_task = nidaqmx.Task()
        else:
            self.galvo_etl_task = nidaqmx.Task()
            self.laser_task = nidaqmx.Task()

        '''Housekeeping: Setting up the DO master trigger task'''
        self.master_trigger_task.do_channels.add_do_chan(ah['master_trigger_out_line'],
                                                         line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        #self.master_trigger_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement

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
        #self.camera_trigger_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement

        '''Housekeeping: Setting up the counter task for the stage TTL trigger for certain stages'''
        if self.cfg.stage_parameters['stage_type'] in {'TigerASI'}:
            assert hasattr(self.cfg, 'asi_parameters'), "Config file with stage 'TigerASI' must contain 'asi_parameters' dictionary"
            trig_line = self.parent.read_config_parameter('stage_trigger_out_line', self.cfg.asi_parameters)
            trig_source = self.parent.read_config_parameter('stage_trigger_source', self.cfg.asi_parameters)
            stage_trigger_pulse_percent = self.parent.read_config_parameter('stage_trigger_pulse_%', self.cfg.asi_parameters)
            stage_delay_percent = self.parent.read_config_parameter('stage_trigger_delay_%', self.cfg.asi_parameters)
            stage_high_time = stage_trigger_pulse_percent * 0.01 * sweeptime
            stage_delay = stage_delay_percent * 0.01 * sweeptime
            self.stage_trigger_task.co_channels.add_co_pulse_chan_time(trig_line, high_time=stage_high_time, initial_delay=stage_delay)
            self.stage_trigger_task.triggers.start_trigger.cfg_dig_edge_start_trig(trig_source)
            #self.stage_trigger_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement

        '''Housekeeping: Setting up the AO task for the Galvo and setting the trigger input'''
        if self.ao_cards == 2: # default mesoSPIM v5 configuration
            self.galvo_etl_task.ao_channels.add_ao_voltage_chan(ah['galvo_etl_task_line'], min_val=-5, max_val=5)
            msg = "Galvo and ETL AO task voltage range is set to -5V to 5V. Check if this is safe for your hardware."
            logger.warning(msg)
            self.galvo_etl_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                       sample_mode=AcquisitionType.FINITE,
                                                       samps_per_chan=samples)
            self.galvo_etl_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['galvo_etl_task_trigger_source'])
            #self.galvo_etl_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement

            '''Housekeeping: Setting up the AO task for the ETL and lasers and setting the trigger input'''
            self.laser_task.ao_channels.add_ao_voltage_chan(ah['laser_task_line'],
                                                            min_val=-self.state['max_laser_voltage'],
                                                            max_val=self.state['max_laser_voltage'])
            msg = f"Laser AO task voltage range is set {-self.state['max_laser_voltage']}V to {self.state['max_laser_voltage']}V. Check if this is safe for your hardware."
            logger.warning(msg)
            self.laser_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                        sample_mode=AcquisitionType.FINITE,
                                                        samps_per_chan=samples)
            self.laser_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['laser_task_trigger_source'])
            #self.laser_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement

        else: # Benchtop single-card PXI NI-6733 or cDAQ NI-9264 configuration
            self.galvo_etl_laser_task.ao_channels.add_ao_voltage_chan(ah['galvo_etl_task_line'] + ',' + ah['laser_task_line'],
                                                                      min_val=-5, max_val=5)
            msg = "Galvo-ETL-Laser AO task voltage range is set to -5V to 5V. Check if this is correct for your hardware."
            logger.warning(msg)
            self.galvo_etl_laser_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                       sample_mode=AcquisitionType.FINITE,
                                                       samps_per_chan=samples)
            self.galvo_etl_laser_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['galvo_etl_task_trigger_source'])
            #self.galvo_etl_laser_task.control(TaskMode.TASK_RESERVE) # cDAQ requirement

    def write_waveforms_to_tasks(self):
        """Write the waveforms to the slave tasks"""
        if self.ao_cards == 2:
            self.galvo_etl_task.write(self.galvo_and_etl_waveforms)
            self.laser_task.write(self.laser_waveforms)
        else:
            self.galvo_etl_laser_task.write(np.vstack((self.galvo_and_etl_waveforms, self.laser_waveforms)))

    def start_tasks(self):
        """Starts the tasks for camera triggering and analog outputs

        If the tasks are configured to be triggered, they won't output any
        signals until run_tasks() is called.
        """
        self.camera_trigger_task.start()
        if self.cfg.stage_parameters['stage_type'] in {'TigerASI'}:
            self.stage_trigger_task.start()
        if self.ao_cards == 2:
            self.galvo_etl_task.start()
            self.laser_task.start()
        else:
            self.galvo_etl_laser_task.start()

    def run_tasks(self):
        """Runs the tasks for triggering, analog and counter outputs

        Firstly, the master trigger triggers all other task via a shared trigger
        line (PFI line as given in the config file).

        For this to work, all analog output and counter tasks have to be started so
        that they are waiting for the trigger signal.

        Warning: `master_trigger_task` does not have explicit sample rate, because some cards like NI-6733 do not support this for DO lines.
        So the master pulse duration varies depening on the device. Can be as short as small as 1 micro-second!
        """
        self.master_trigger_task.write([False, True, True, True, True, True, False], auto_start=True)

        '''Wait until everything is done - this is effectively a sleep function.'''
        if self.ao_cards == 2:
            self.galvo_etl_task.wait_until_done()
            self.laser_task.wait_until_done()
        else:
            self.galvo_etl_laser_task.wait_until_done()
        self.camera_trigger_task.wait_until_done()
        if self.cfg.stage_parameters['stage_type'] in {'TigerASI'}:
            self.stage_trigger_task.wait_until_done()

    def stop_tasks(self):
        """Stops the tasks for triggering, analog and counter outputs"""
        if self.ao_cards == 2:
            self.galvo_etl_task.stop()
            self.laser_task.stop()
        else:
            self.galvo_etl_laser_task.stop()
        self.camera_trigger_task.stop()
        if self.cfg.stage_parameters['stage_type'] in {'TigerASI'}:
            self.stage_trigger_task.stop()
        self.master_trigger_task.stop()

    def close_tasks(self):
        """Closes the tasks for triggering, analog and counter outputs.
        Tasks should only be closed are they are stopped.
        """
        if self.ao_cards == 2:
            self.galvo_etl_task.close()
            self.laser_task.close()
        else:
            self.galvo_etl_laser_task.close()
        self.camera_trigger_task.close()
        if self.cfg.stage_parameters['stage_type'] in {'TigerASI'}:
            self.stage_trigger_task.close()
        self.master_trigger_task.close()


class mesoSPIM_DemoWaveFormGenerator(mesoSPIM_WaveFormGenerator):
    """Demo subclass of mesoSPIM_WaveFormGenerator class
    """

    def __init__(self, parent):
        super().__init__(parent)

    def create_tasks(self):
        """"Demo version of the actual DAQmx-based function."""
        self.calculate_samples()
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        camera_pulse_percent, camera_delay_percent = self.state.get_parameter_list(['camera_pulse_%','camera_delay_%'])
        self.camera_high_time = camera_pulse_percent*0.01*sweeptime
        self.camera_delay = camera_delay_percent*0.01*sweeptime

    def write_waveforms_to_tasks(self):
        """Demo: write the waveforms to the slave tasks """
        pass

    def start_tasks(self):
        """Demo: starts the tasks for camera triggering and analog outputs. """
        pass

    def run_tasks(self):
        """Demo: runs the tasks for triggering, analog and counter outputs. """
        time.sleep(self.state['sweeptime'])

    def stop_tasks(self):
        """"Demo: stop tasks"""
        pass

    def close_tasks(self):
        """Demo: closes the tasks for triggering, analog and counter outputs. """
        pass
