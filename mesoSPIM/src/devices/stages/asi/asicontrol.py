"""
mesoSPIM Module for controlling ASI-Stages 

Author: Fabian Voigt
"""

import time
import traceback
import serial

from PyQt5 import QtWidgets, QtCore, QtGui

import logging
logger = logging.getLogger(__name__)


class StageControlASITiger(QtCore.QObject):
    sig_pause = QtCore.pyqtSignal(bool)

    '''
    Class to control a ASI Tiger mechanical stage controller
    
    Inherits from QtCore.QObject so it can be moved to a QThread.

    Note:
        This is a custom ASI stageset which contains the axis designations:
        X Y Z T V W 
    '''

    def __init__(self, asi_parameters):
        super().__init__()
        self.port = asi_parameters['COMport']
        self.baudrate = asi_parameters['baudrate']
        self.stage_assignment = asi_parameters['stage_assignment']
        self.axis_list = [self.stage_assignment[i] for i in self.stage_assignment.keys()]
        self.axes = ''.join(self.axis_list) # String containing all axes
        self.num_axes = len(self.axes) # The number of axes
        self.encoder_conversion = asi_parameters['encoder_conversion']
        
        self.position_dict = {axis : None for axis in self.axis_list} # create an empty position dict
                
        '''Open connection to the stage controller'''
        self.asi_connection = serial.Serial(self.port, self.baudrate, parity=serial.PARITY_NONE, timeout=5, xonxoff=False, stopbits=serial.STOPBITS_ONE)
        self.previous_command = ''
        self.current_z_slice = 0

    def close(self):
        '''Closes connection to the stage'''
        self.asi_connection.close()
    
    def _send_command(self, command: bytes):
        '''Sends a command to the controller
        Try-except block included to catch errors - this is dangerous - no checking of success
        Args:
            command (bytes): Command string to be sent. Needs to be in the form "b'W V?\r'" - has to be binary, do not forget the carriage return
            
        Returns:
            answer (str): Answer by the controller.
        '''
        try:
            ''' During acquisitions: send pause signal '''
            self.sig_pause.emit(True)
            start_time = time.time()
            self._reset_buffers()
            logger.debug(f"Serial sent: {command}")
            self.asi_connection.write(command)
            message = self.asi_connection.readline().decode("ascii")
            response_time = time.time() 
            ''' During acquistions: send unpause signal '''
            self.sig_pause.emit(False)
            logger.debug(f"Serial received: {message} ")
            ''' Logging of serial connections if response >30 ms (previously: 15 ms)'''
            delta_t = round(response_time - start_time, 6)
            if delta_t > 0.04:
                logger.info('Z-Slice (only valid during acq): ' + str(self.current_z_slice) + ' Response time, s (if >0.04): ' + str(delta_t))
            return message
        except Exception as error:
            logger.error(f"Serial exception of the ASI stage: command {command.decode('ascii')}, error: {error}")

    def _reset_buffers(self):
        if self.asi_connection is not None:
            self.asi_connection.reset_input_buffer()
            self.asi_connection.reset_output_buffer()
        else:
            logger.error("Serial port not initialized")

    def axis_in_config_check(self, axis):
        '''
        Checks if a axis string is in self.axes
        
        Returns:
            True if axis in config
        '''
        if axis in self.axes:
            return True 
        else:
            print('Axis: ', axis, ' not found in ASI stage config.')
            logger.info('Axis: ' + str(axis) + ' not found in ASI stage config.')
            return False
                  
    def stop(self):
        '''Stops movement on all axes by sending "halt" to the controller
        '''
        response = self._send_command(b'\\r')
        logger.info(f"ASI response to HALT command: {response}")
        
    def wait_until_done(self):
        '''Blocks if the stage is moving due to a serial command'''

        '''If the stage returns 'B'as the first letter, it is busy, if it returns 'N', it is done.
        Only if the stage returns 'N' twice, it is not busy.
        '''
        self.stage_busy = True
        while self.stage_busy is True:
            try: 
                message1 = self._send_command(b'/\r')[0]
                time.sleep(0.05)
                message2 = self._send_command(b'/\r')[0]
                time.sleep(0.05)
                if message1 == 'N' and message2 == 'N':
                    self.stage_busy = False
            except:
                logger.error('ASI stages: Wait until done failed')
        
    def read_position(self):
        '''Reports position from the stages
        Returns:
            positions (dictionary): list of positions 
        
        '''
        command_string = 'W ' + self.axes + '\r'
        position_string = self._send_command(command_string.encode('ascii'))
        # Create a list of the form "['7835', '-38704', '0', '0', '-367586']", first element is the ack ':A' and gets discarded
        if position_string is not None:
            try:
                position_list = position_string.split()[1:]
                ''' Only process position list if it contains all values'''
                if len(position_list) == self.num_axes:
                    try:
                        position_list = [int(value) for value in position_list]
                        endcoder_conversion_list = list(self.encoder_conversion.values())
                        position_dict = {self.axes[i]: position_list[i]/endcoder_conversion_list[i] for i in range(self.num_axes)}
                        if position_dict is not None:
                            self.position_dict = position_dict
                            return position_dict
                    except:
                        logger.info('Invalid position dict: ' + str(position_list))
                        # return last position dict
                        return self.position_dict
                else:
                    logger.error(f"Position list count {position_list} does not match the number of axes {self.num_axes}")
            except: 
                logger.error('Invalid position string: ' + str(position_string))
        else:
            logger.error("Position string is empty")

    def move_relative(self, motion_dict):
        '''Command for relative motion 
        
        Args:
            motion_dict (dict): Dictionary in the form {1: 4000, 2:-234}, in general {axis_id:requested_position} 
                                with axis_id (str) and requested_position (int) in um.
        Returns:
            Carries out motion
        '''
        command_string = 'R'
        for axis in motion_dict.keys():
            if self.axis_in_config_check(axis):
                command_string = command_string + ' ' + axis + '=' + str(motion_dict[axis]*self.encoder_conversion[axis])
        if command_string != 'R':
            command_string += '\r'
            self._send_command(command_string.encode('ascii'))
        
    def move_absolute(self, motion_dict):
        ''' Command for absolute motion 
        
        Args:
            motion_dict (dict): Dictionary in the form {1: 4000, 2:-234}, in general {axis_id:requested_position} 
                                with axis_id (str) and requested_position (int) in um.
        
        '''
        command_string = 'M'
        for axis in motion_dict.keys():
            if self.axis_in_config_check(axis):
                command_string = command_string + ' ' + axis + '=' + str(motion_dict[axis]*self.encoder_conversion[axis])
                
        if command_string != 'M':
            command_string += '\r'
            self._send_command(command_string.encode('ascii'))

    def enable_ttl_mode(self, card_ids, bool):
        ''' Enables or disables TTL mode of ASI controllers
        Args:
            card_ids (list): List of card IDs inside the controller (i.e. (2,3) for cards in slots 2 and 3) for 
                            which TTL triggering should be enabled or disabled. If None, the controller is assumed
                            not to have any card slots, i.e. an MS-2000 controller
            
            bool (boolean): True or False depending on whether TTL mode should be enabled or disabled.
        '''
        if card_ids is not None: # Tiger controller
            if bool is True: # Enable TTL mode for all cards
                for i in card_ids:
                    command_string = str(i) + ' TTL X=2 Y=2\r'
                    self._send_command(command_string.encode('ascii'))
                    logger.info('TTL enabled')
            else: # Disable TTL mode for all cards
                for i in card_ids:
                    command_string = str(i) + ' TTL X=0 Y=2\r'
                    self._send_command(command_string.encode('ascii'))
                    logger.info('TTL disabled')
        else: # MS-2000 controller
            if bool is True:
                self._send_command(b'TTL X=2 Y=2\r') # MS-2000 TTL mode should be enabled
                logger.info('TTL enabled')
            else:
                self._send_command(b'TTL X=0 Y=2\r') # MS-2000 TTL mode should be disabled
                logger.info('TTL disabled')
