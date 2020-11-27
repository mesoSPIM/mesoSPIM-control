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

class StageControlASITango(QtCore.QObject):
    '''
    Class to control a ASI Tango mechanical stage controller
    
    Inherits from QtCore.QObject so it can be moved to a QThread.

    Note:
        This is a custom ASI stageset which contains the axis designations:
        X Y Z T V W 
        
        V and W are 

        Internally, the 
    '''

    def __init__(self, port, baudrate, stage_assigment):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.stage_assignment = stage_assigment
        self.axis_list = [self.stage_assignment[i] for i in self.stage_assignment.keys()]
        self.axes = ''.join(self.axis_list) # String containing all axes
        self.num_axes = len(self.axes) # The number of axes
        
        self.position_dict = {axis : None for axis in self.axis_list} # create an empty position dict
                
        '''Open connection to the stage controller'''
        self.asi_connection = serial.Serial(self.port, self.baudrate, parity=serial.PARITY_NONE, timeout=1
    , xonxoff=False, stopbits=serial.STOPBITS_ONE)

        self.previous_command = ''

    def close(self):
        '''Closes connection to the stage'''
        self.asi_connection.close()
    
    def _send_command(self, command, delay=0.01):
        '''Sends a command to the controller
        
        Try-except block included to catch errors - this is dangerous - no checking of success 
        
        Args:
            command (str): Command string to be sent. Needs to be in the form "b'W V?\r\n'" - has to be binary, do not forget the carriage return
            
        Returns:
            answer (str): Answer by the controller. Will be in binary format and needs to be decoded if necessary.
        '''
        try:
            # print(time.time(), ' ', command.decode('UTF-8'))
            start_time = time.time() 
            self.asi_connection.write(command)
            time.sleep(delay)
            message = self.asi_connection.readline()
            response_time = time.time() 
            ''' Logging of serial connections if response >15 ms'''
            delta_t = round(response_time - start_time, 6)
            if delta_t > 0.015:
                logger.info('Serial sent: ' + str(command) + ' Serial recv: ' + str(message) + ' Z-Position: ' + str(position) + ' Response time (>15 ms): ' + str(delta_t))
            return message
        except Exception as error:
            logger.info('Serial exception of the ASI stage: ' + str(error))
                        
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
                  
    def stop(self, restart_programs=False):
        '''Stops movement on all axes by sending "halt" to the controller
               
        '''
        self._send_command(b'\\r\n')
        
    def wait_until_done(self):
        '''Blocks if the stage is moving due to a serial command'''

        '''If the stage returns 'B'as the first letter, it is busy, if it returns 'N', it is done.
        Only if the stage returns 'N' twice, it is not busy.
        '''
        self.stage_busy = True
        while self.stage_busy is True:
            message1 = self._send_command(b'/\r\n').decode('UTF-8')[0]
            time.sleep(0.1)
            message2 = self._send_command(b'/\r\n').decode('UTF-8')[0]
            time.sleep(0.1)
            if message1 == 'N' and message2 == 'N':
                self.stage_busy = False
        
    def read_position(self):
        '''Reports position from the stages 
               
        Returns:
            positions (dictionary): list of positions 
        
        '''
        command_string = 'W ' + self.axes + '\r\n'
        position_string = self._send_command(command_string.encode('UTF-8'))
        # Create a list of the form "['7835', '-38704', '0', '0', '-367586']", first element is the ack ':A' and gets discarded
        if position_string is not None:
            position_list = position_string.decode('UTF-8').split()[1:]
            ''' Only process position list if it contains all values'''
            if len(position_list) == self.num_axes:
                # conversion to um: internal unit is 1/10 um
                try:
                    position_list = [int(value)/10 for value in position_list] 
                    position_dict = {self.axes[i] : position_list[i] for i in range(self.num_axes)}
                    if position_dict is not None:
                        self.position_dict = position_dict
                        return position_dict
                except:
                    logger.info('Invalid position dict: ' + str(position_list))
                    # return last position dict
                    return self.position_dict
        
            
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
                # Conversion um to 1/10 um for internal use requires *10
                # TODO: This has to be taken into account for rotations: 90° = 90000 cts, command 9000
                command_string = command_string + ' ' + axis + '=' + str(motion_dict[axis]*10) 
                
        if command_string != 'R':
            command_string += '\r\n'
            self._send_command(command_string.encode('UTF-8'))
        
    def move_absolute(self, motion_dict):
        ''' Command for absolute motion 
        
        Args:
            motion_dict (dict): Dictionary in the form {1: 4000, 2:-234}, in general {axis_id:requested_position} 
                                with axis_id (str) and requested_position (int) in um.
        
        '''
        command_string = 'M'
        for axis in motion_dict.keys():
            if self.axis_in_config_check(axis):
                # Conversion um to 1/10 um for internal use requires *10
                command_string = command_string + ' ' + axis + '=' + str(motion_dict[axis]*10) 
                
        if command_string != 'M':
            command_string += '\r\n'
            self._send_command(command_string.encode('UTF-8'))         