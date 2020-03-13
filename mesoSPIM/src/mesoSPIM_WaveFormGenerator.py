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
    sig_update_gui_from_state = QtCore.pyqtSignal(bool)

    def __init__(self, parent):
        super().__init__()

        self.cfg = parent.cfg
        self.parent = parent

        self.state = mesoSPIM_StateSingleton()
        self.parent.sig_save_etl_config.connect(self.save_etl_parameters_to_csv)

        cfg_file = self.cfg.startup['ETL_cfg_file']
        self.state['ETL_cfg_file'] = cfg_file
        self.update_etl_parameters_from_csv(cfg_file, self.state['laser'], self.state['zoom'])

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

        self.state['galvo_l_amplitude'] = self.cfg.startup['galvo_l_amplitude']
        self.state['galvo_r_amplitude'] = self.cfg.startup['galvo_r_amplitude']
        self.state['galvo_l_frequency'] = self.cfg.startup['galvo_l_frequency']
        self.state['galvo_r_frequency'] = self.cfg.startup['galvo_r_frequency']
        self.state['galvo_l_offset'] = self.cfg.startup['galvo_l_offset']
        self.state['galvo_r_offset'] = self.cfg.startup['galvo_r_offset']

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(),dict.values()):
            # print('Waveform Generator: State request: Key: ', key, ' Value: ', value)
            '''
            The request handling is done
            '''
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
                       'camera_delay_%',
                       'camera_pulse_%'):
                ''' Notify GUI about the change '''
                #self.sig_update_gui_from_state.emit(True)
                self.state[key] = value
                #self.sig_update_gui_from_state.emit(False)
                self.create_waveforms()
                # print('Waveform change')
            elif key in ('ETL_cfg_file'):
                self.state[key] = value
                self.update_etl_parameters_from_csv(value, self.state['laser'], self.state['zoom'])
                # print('ETL CFG File changed')
            elif key in ('set_etls_according_to_zoom'):
                self.update_etl_parameters_from_zoom(value)
                #print('zoom change')
            elif key in ('set_etls_according_to_laser'):
                self.state['laser'] = value
                self.create_waveforms()
                self.update_etl_parameters_from_laser(value)
                #print('laser change')
            elif key in ('laser'):
                self.state['laser'] = value
                self.create_waveforms()
                
            # Log Thread ID during Live: just debugging code
            elif key == 'state':
                if value == 'live':
                    logger.info('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))

    def calculate_samples(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        self.samples = int(samplerate*sweeptime)

    def create_waveforms(self):
        self.calculate_samples()
        self.create_etl_waveforms()
        self.create_galvo_waveforms()
        '''Bundle everything'''
        self.bundle_galvo_and_etl_waveforms()
        self.create_laser_waveforms()

    def create_etl_waveforms(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        etl_l_delay, etl_l_ramp_rising, etl_l_ramp_falling, etl_l_amplitude, etl_l_offset =\
        self.state.get_parameter_list(['etl_l_delay_%','etl_l_ramp_rising_%','etl_l_ramp_falling_%',
        'etl_l_amplitude','etl_l_offset'])
        etl_r_delay, etl_r_ramp_rising, etl_r_ramp_falling, etl_r_amplitude, etl_r_offset =\
        self.state.get_parameter_list(['etl_r_delay_%','etl_r_ramp_rising_%','etl_r_ramp_falling_%',
        'etl_r_amplitude','etl_r_offset'])


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

        ''' Attention: Right Galvo gets the left frequency for now '''

        self.galvo_r_waveform = sawtooth(samplerate = samplerate,
                                         sweeptime = sweeptime,
                                         frequency = galvo_l_frequency,
                                         amplitude = galvo_r_amplitude,
                                         offset = galvo_r_offset,
                                         dutycycle = galvo_r_duty_cycle,
                                         phase = galvo_r_phase)

    def create_laser_waveforms(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])

        laser_l_delay, laser_l_pulse, max_laser_voltage, intensity = \
        self.state.get_parameter_list(['laser_l_delay_%','laser_l_pulse_%',
        'max_laser_voltage','intensity'])

        '''Create zero waveforms for the lasers'''
        self.zero_waveform = np.zeros((self.samples))

        '''Update the laser intensity waveform'''
        '''This could be improved: create a list with as many zero arrays as analog out lines for ETL and Lasers'''
        self.laser_waveform_list = [self.zero_waveform for i in self.cfg.laser_designation]

        ''' Conversion from % to V of the intensity:'''
        laser_voltage = max_laser_voltage * intensity / 100

        self.laser_template_waveform = single_pulse(samplerate = samplerate,
                                                    sweeptime = sweeptime,
                                                    delay = laser_l_delay,
                                                    pulsewidth = laser_l_pulse,
                                                    amplitude = laser_voltage,
                                                    offset = 0)

        '''The key: replace the waveform in the waveform list with this new template'''
        current_laser_index = self.cfg.laser_designation[self.state['laser']]
        self.laser_waveform_list[current_laser_index] = self.laser_template_waveform
        self.laser_waveforms = np.stack(self.laser_waveform_list)

    def bundle_galvo_and_etl_waveforms(self):
        ''' Stacks the Galvo and ETL waveforms into a numpy array adequate for
        the NI cards.

        In here, the assignment of output channels of the Galvo / ETL card to the
        corresponding output channel is hardcoded: This could be improved.
        '''
        self.galvo_and_etl_waveforms = np.stack((self.galvo_l_waveform,
                                                 self.galvo_r_waveform,
                                                 self.etl_l_waveform,
                                                 self.etl_r_waveform))

    def update_etl_parameters_from_zoom(self, zoom):
        ''' Little helper method: Because the mesoSPIM core is not handling
        the serial Zoom connection. '''
        laser = self.state['laser']
        etl_cfg_file = self.state['ETL_cfg_file']
        self.update_etl_parameters_from_csv(etl_cfg_file, laser, zoom)

    def update_etl_parameters_from_laser(self, laser):
        ''' Little helper method: Because laser changes need an ETL parameter update '''
        zoom = self.state['zoom']
        etl_cfg_file = self.state['ETL_cfg_file']
        self.update_etl_parameters_from_csv(etl_cfg_file, laser, zoom)

    def update_etl_parameters_from_csv(self, cfg_path, laser, zoom):
        ''' Updates the internal ETL left/right offsets and amplitudes from the
        values in the ETL csv files

        The .csv file needs to contain the follwing columns:

        Wavelength
        Zoom
        ETL-Left-Offset
        ETL-Left-Amp
        ETL-Right-Offset
        ETL-Right-Amp


        '''
        # print('Updating ETL parameters from file:', cfg_path)

        self.sig_update_gui_from_state.emit(True)
        with open(cfg_path) as file:
            reader = csv.DictReader(file,delimiter=';')
            #print('opened csv')
            for row in reader:
                if row['Wavelength'] == laser and row['Zoom'] == zoom:

                    ''' Some diagnostic tracing statements

                    # print(row)
                    # print('updating parameters')
                    # print(self.etl_l['amplitude'])

                    '''

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
                    # print('Parameters set from csv')
                    self.state.set_parameters(parameter_dict)

        '''Update waveforms with the new parameters'''

        self.create_waveforms()
        self.sig_update_gui_from_state.emit(False)

    @QtCore.pyqtSlot()
    def save_etl_parameters_to_csv(self):
        ''' Saves the current ETL left/right offsets and amplitudes from the
        values to the ETL csv files

        The .csv file needs to contain the following columns:

        Wavelength
        Zoom
        ETL-Left-Offset
        ETL-Left-Amp
        ETL-Right-Offset
        ETL-Right-Amp

        Creates a temporary cfg file with the ending _tmp

        '''

        etl_cfg_file, laser, zoom, etl_l_offset, etl_l_amplitude, etl_r_offset, etl_r_amplitude = \
        self.state.get_parameter_list(['ETL_cfg_file', 'laser', 'zoom',
        'etl_l_offset', 'etl_l_amplitude', 'etl_r_offset','etl_r_amplitude'])

        '''Temporary filepath'''
        tmp_etl_cfg_file = etl_cfg_file+'_tmp'

        # print('saving current ETL parameters')

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
            #print('created writer')

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
        '''Creates a total of four tasks for the mesoSPIM:

        These are:
        - the master trigger task, a digital out task that only provides a trigger pulse for the others
        - the camera trigger task, a counter task that triggers the camera in lightsheet mode
        - the galvo task (analog out) that controls the left & right galvos for creation of
          the light-sheet and shadow avoidance
        - the ETL & Laser task (analog out) that controls all the laser intensities (Laser should only
          be on when the camera is acquiring) and the left/right ETL waveforms
        '''
        ah = self.cfg.acquisition_hardware

        self.calculate_samples()
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        samples = self.samples
        camera_pulse_percent, camera_delay_percent = self.state.get_parameter_list(['camera_pulse_%','camera_delay_%'])

        self.master_trigger_task = nidaqmx.Task()
        self.camera_trigger_task = nidaqmx.Task()
        self.galvo_etl_task = nidaqmx.Task()
        self.laser_task = nidaqmx.Task()

        '''Housekeeping: Setting up the DO master trigger task'''
        self.master_trigger_task.do_channels.add_do_chan(ah['master_trigger_out_line'],
                                                         line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)

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

        '''Housekeeping: Setting up the AO task for the Galvo and setting the trigger input'''
        self.galvo_etl_task.ao_channels.add_ao_voltage_chan(ah['galvo_etl_task_line'])
        self.galvo_etl_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                   sample_mode=AcquisitionType.FINITE,
                                                   samps_per_chan=samples)
        self.galvo_etl_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['galvo_etl_task_trigger_source'])

        '''Housekeeping: Setting up the AO task for the ETL and lasers and setting the trigger input'''
        self.laser_task.ao_channels.add_ao_voltage_chan(ah['laser_task_line'])
        self.laser_task.timing.cfg_samp_clk_timing(rate=samplerate,
                                                    sample_mode=AcquisitionType.FINITE,
                                                    samps_per_chan=samples)
        self.laser_task.triggers.start_trigger.cfg_dig_edge_start_trig(ah['laser_task_trigger_source'])

    def write_waveforms_to_tasks(self):
        '''Write the waveforms to the slave tasks'''
        self.galvo_etl_task.write(self.galvo_and_etl_waveforms)
        self.laser_task.write(self.laser_waveforms)

    def start_tasks(self):
        '''Starts the tasks for camera triggering and analog outputs

        If the tasks are configured to be triggered, they won't output any
        signals until run_tasks() is called.
        '''
        self.camera_trigger_task.start()
        self.galvo_etl_task.start()
        self.laser_task.start()

    def run_tasks(self):
        '''Runs the tasks for triggering, analog and counter outputs

        Firstly, the master trigger triggers all other task via a shared trigger
        line (PFI line as given in the config file).

        For this to work, all analog output and counter tasks have to be started so
        that they are waiting for the trigger signal.
        '''
        self.master_trigger_task.write([False, True, True, True, False], auto_start=True)

        '''Wait until everything is done - this is effectively a sleep function.'''
        self.galvo_etl_task.wait_until_done()
        self.laser_task.wait_until_done()
        self.camera_trigger_task.wait_until_done()

    def stop_tasks(self):
        '''Stops the tasks for triggering, analog and counter outputs'''
        self.galvo_etl_task.stop()
        self.laser_task.stop()
        self.camera_trigger_task.stop()
        self.master_trigger_task.stop()

    def close_tasks(self):
        '''Closes the tasks for triggering, analog and counter outputs.

        Tasks should only be closed are they are stopped.
        '''
        self.galvo_etl_task.close()
        self.laser_task.close()
        self.camera_trigger_task.close()
        self.master_trigger_task.close()

class mesoSPIM_DemoWaveFormGenerator(QtCore.QObject):
    '''This class contains the microscope state

    Any access to this global state should only be done via signals sent by
    the responsible class for actually causing that state change in hardware.

    '''
    sig_update_gui_from_state = QtCore.pyqtSignal(bool)

    def __init__(self, parent):
        super().__init__()

        self.cfg = parent.cfg
        self.parent = parent

        self.state = mesoSPIM_StateSingleton()
        self.parent.sig_save_etl_config.connect(self.save_etl_parameters_to_csv)

        cfg_file = self.cfg.startup['ETL_cfg_file']
        self.state['ETL_cfg_file'] = cfg_file
        self.update_etl_parameters_from_csv(cfg_file, self.state['laser'], self.state['zoom'])

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

        self.state['galvo_l_amplitude'] = self.cfg.startup['galvo_l_amplitude']
        self.state['galvo_r_amplitude'] = self.cfg.startup['galvo_r_amplitude']
        self.state['galvo_l_frequency'] = self.cfg.startup['galvo_l_frequency']
        self.state['galvo_r_frequency'] = self.cfg.startup['galvo_r_frequency']
        self.state['galvo_l_offset'] = self.cfg.startup['galvo_l_offset']
        self.state['galvo_r_offset'] = self.cfg.startup['galvo_r_offset']

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(),dict.values()):
            # print('Waveform Generator: State request: Key: ', key, ' Value: ', value)
            '''
            The request handling is done
            '''
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
                       'camera_delay_%',
                       'camera_pulse_%'):
                ''' Notify GUI about the change '''
                #self.sig_update_gui_from_state.emit(True)
                self.state[key] = value
                #self.sig_update_gui_from_state.emit(False)
                self.create_waveforms()
                # print('Waveform change')
            elif key in ('ETL_cfg_file'):
                self.state[key] = value
                self.update_etl_parameters_from_csv(value, self.state['laser'], self.state['zoom'])
                # print('ETL CFG File changed')
            elif key in ('zoom'):
                self.update_etl_parameters_from_zoom(value)
                #print('zoom change')
            elif key in ('laser'):
                self.state[key] = value
                self.create_waveforms()
                self.update_etl_parameters_from_laser(value)
                #print('laser change')

            # Log Thread ID during Live: just debugging code
            elif key == 'state':
                if value == 'live':
                    logger.info('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))

    def calculate_samples(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        self.samples = int(samplerate*sweeptime)

    def create_waveforms(self):
        self.calculate_samples()
        self.create_etl_waveforms()
        self.create_galvo_waveforms()
        '''Bundle everything'''
        self.bundle_galvo_and_etl_waveforms()
        self.create_laser_waveforms()

    def create_etl_waveforms(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        etl_l_delay, etl_l_ramp_rising, etl_l_ramp_falling, etl_l_amplitude, etl_l_offset =\
        self.state.get_parameter_list(['etl_l_delay_%','etl_l_ramp_rising_%','etl_l_ramp_falling_%',
        'etl_l_amplitude','etl_l_offset'])
        etl_r_delay, etl_r_ramp_rising, etl_r_ramp_falling, etl_r_amplitude, etl_r_offset =\
        self.state.get_parameter_list(['etl_r_delay_%','etl_r_ramp_rising_%','etl_r_ramp_falling_%',
        'etl_r_amplitude','etl_r_offset'])


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

        ''' Attention: Right Galvo gets the left frequency for now '''

        self.galvo_r_waveform = sawtooth(samplerate = samplerate,
                                         sweeptime = sweeptime,
                                         frequency = galvo_l_frequency,
                                         amplitude = galvo_r_amplitude,
                                         offset = galvo_r_offset,
                                         dutycycle = galvo_r_duty_cycle,
                                         phase = galvo_r_phase)

    def create_laser_waveforms(self):
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])

        laser_l_delay, laser_l_pulse, max_laser_voltage, intensity = \
        self.state.get_parameter_list(['laser_l_delay_%','laser_l_pulse_%',
        'max_laser_voltage','intensity'])

        '''Create zero waveforms for the lasers'''
        self.zero_waveform = np.zeros((self.samples))

        '''Update the laser intensity waveform'''
        '''This could be improved: create a list with as many zero arrays as analog out lines for ETL and Lasers'''
        self.laser_waveform_list = [self.zero_waveform for i in self.cfg.laser_designation]

        ''' Conversion from % to V of the intensity:'''
        laser_voltage = max_laser_voltage * intensity / 100

        self.laser_template_waveform = single_pulse(samplerate = samplerate,
                                                    sweeptime = sweeptime,
                                                    delay = laser_l_delay,
                                                    pulsewidth = laser_l_pulse,
                                                    amplitude = laser_voltage,
                                                    offset = 0)

        '''The key: replace the waveform in the waveform list with this new template'''
        current_laser_index = self.cfg.laser_designation[self.state['laser']]
        self.laser_waveform_list[current_laser_index] = self.laser_template_waveform
        self.laser_waveforms = np.stack(self.laser_waveform_list)

    def bundle_galvo_and_etl_waveforms(self):
        ''' Stacks the Galvo and ETL waveforms into a numpy array adequate for
        the NI cards.

        In here, the assignment of output channels of the Galvo / ETL card to the
        corresponding output channel is hardcoded: This could be improved.
        '''
        self.galvo_and_etl_waveforms = np.stack((self.galvo_l_waveform,
                                                 self.galvo_r_waveform,
                                                 self.etl_l_waveform,
                                                 self.etl_r_waveform))

    def update_etl_parameters_from_zoom(self, zoom):
        ''' Little helper method: Because the mesoSPIM core is not handling
        the serial Zoom connection. '''
        laser = self.state['laser']
        etl_cfg_file = self.state['ETL_cfg_file']
        self.update_etl_parameters_from_csv(etl_cfg_file, laser, zoom)

    def update_etl_parameters_from_laser(self, laser):
        ''' Little helper method: Because laser changes need an ETL parameter update '''
        zoom = self.state['zoom']
        etl_cfg_file = self.state['ETL_cfg_file']
        self.update_etl_parameters_from_csv(etl_cfg_file, laser, zoom)

    def update_etl_parameters_from_csv(self, cfg_path, laser, zoom):
        ''' Updates the internal ETL left/right offsets and amplitudes from the
        values in the ETL csv files

        The .csv file needs to contain the follwing columns:

        Wavelength
        Zoom
        ETL-Left-Offset
        ETL-Left-Amp
        ETL-Right-Offset
        ETL-Right-Amp


        '''
        # print('Updating ETL parameters from file:', cfg_path)

        with open(cfg_path) as file:
            reader = csv.DictReader(file,delimiter=';')
            #print('opened csv')
            for row in reader:
                if row['Wavelength'] == laser and row['Zoom'] == zoom:

                    ''' Some diagnostic tracing statements

                    # print(row)
                    # print('updating parameters')
                    # print(self.etl_l['amplitude'])

                    '''

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
                    self.sig_update_gui_from_state.emit(True)
                    self.state.set_parameters(parameter_dict)
                    self.sig_update_gui_from_state.emit(False)

        '''Update waveforms with the new parameters'''

        self.create_waveforms()

    @QtCore.pyqtSlot()
    def save_etl_parameters_to_csv(self):
        ''' Saves the current ETL left/right offsets and amplitudes from the
        values to the ETL csv files

        The .csv file needs to contain the following columns:

        Wavelength
        Zoom
        ETL-Left-Offset
        ETL-Left-Amp
        ETL-Right-Offset
        ETL-Right-Amp

        Creates a temporary cfg file with the ending _tmp

        '''

        etl_cfg_file, laser, zoom, etl_l_offset, etl_l_amplitude, etl_r_offset, etl_r_amplitude = \
        self.state.get_parameter_list(['ETL_cfg_file', 'laser', 'zoom',
        'etl_l_offset', 'etl_l_amplitude', 'etl_r_offset','etl_r_amplitude'])

        '''Temporary filepath'''
        tmp_etl_cfg_file = etl_cfg_file+'_tmp'

        # print('saving current ETL parameters')

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
            #print('created writer')

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

        self.calculate_samples()
        samplerate, sweeptime = self.state.get_parameter_list(['samplerate','sweeptime'])
        samples = self.samples
        camera_pulse_percent, camera_delay_percent = self.state.get_parameter_list(['camera_pulse_%','camera_delay_%'])

        self.camera_high_time = camera_pulse_percent*0.01*sweeptime
        self.camera_delay = camera_delay_percent*0.01*sweeptime

    def write_waveforms_to_tasks(self):
        '''Write the waveforms to the slave tasks'''
        pass

    def start_tasks(self):
        '''Starts the tasks for camera triggering and analog outputs

        If the tasks are configured to be triggered, they won't output any
        signals until run_tasks() is called.
        '''
        pass

    def run_tasks(self):
        '''Runs the tasks for triggering, analog and counter outputs

        Firstly, the master trigger triggers all other task via a shared trigger
        line (PFI line as given in the config file).

        For this to work, all analog output and counter tasks have to be started so
        that they are waiting for the trigger signal.
        '''
        time.sleep(self.state['sweeptime'])

    def stop_tasks(self):
        pass

    def close_tasks(self):
        '''Closes the tasks for triggering, analog and counter outputs.

        Tasks should only be closed are they are stopped.
        '''
        pass
