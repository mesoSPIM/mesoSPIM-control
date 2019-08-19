"""
mesoSPIM Module for controlling Galil-Stages (by Steinmayer-Mechatronik/Feinmess)

Author: Fabian Voigt

#TODO
"""
import copy
import time
import traceback

from PyQt5 import QtWidgets, QtCore, QtGui

import gclib

import logging
logger = logging.getLogger(__name__)

class StageControlGalil(QtCore.QObject):
    '''
    Class to control a Galil mechanical stage controller
    
    Inherits from QtCore.QObject so it can be moved to a QThread.
    
    Note:
        The encodercounts should be specfified such that: Position in um = encoderposition * encodercounts
        or Position in degrees = encoderposition * encodercounts
        
    Args:
        port (str): Either a COMport designation ("COM42") or a IP address "192.168.1.42"
        encodercounts (list of int): Conversion factor from unit of interest
            
    Examples:
        my_stage = StageControlGalil('COM19', [2,2,2])
        my_stage2 = StageControlGalil('192.168.1.45', [2,2,2])
    
    Todo
        * correct tracking of the internal and external absolute positions: Do everything via the Galil controller
        * is it truly a good idea to set the stage to zero for each new instantiation?
    
    '''

    def __init__(self,port,encodercounts = [2,2,2]):
        super().__init__()
        
        self.port = port
        self.encodercounts = encodercounts
        '''The number of '''
        self.num_axes = len(encodercounts)
        
        self.g = gclib.py()
        
        '''Opens connection to the stage controller'''
        if port[0:3] == 'COM':
            self.port = port
            self.baudrate = '19200'
            self.timeout = '60000'
            self.connectionstring = self.COMport + ' --baud ' + self.baudrate + ' --subscribe ALL --timeout ' + self.timeout
            self.g.GOpen(self.connectionstring)
        else:
            '''Assumes Ethernet connection'''
            self.connectionstring = self.port + ' --direct'
            self.g.GOpen(self.connectionstring)
        
        '''To address the stages for commands, the list of axes designations needs 
        to be truncated.'''
        _axisstring = 'ABCDEFGH'
        self._axistring = _axisstring[0:self.num_axes]  
        
        '''Create an default position list with the right length'''
        self.positions = [0 for i in range(self.num_axes)]
        self.read_position()
        
        self.initflag = True
        self.unit = 'micron'
        self.speed = 5000
        self.slow_speed = 5000
        self.fast_speed = 20000
        self.set_speed(self.slow_speed)
        '''
        self.read_position('x')
        self.read_position('y')
        self.read_position('z')
        '''
        self.initflag = False

    def close(self):
        '''Closes connection to the stage'''
        self.g.GClose()

    def controller_info(self):
        '''Returns COM port/IP adress, DMC version and serial number of the controller'''
        return self.g.GInfo()
    
    def _send_command(self, command):
        '''Sends a command to the controller
        
        Try-except block included to catch errors - this is dangerous - no checking of success 
        
        Args:
            command (str): Command string to be sent
            
        Returns:
            answer (str): Answer by the controller
        '''
        try:
            return self.g.GCommand(command)
        except Exception as error:
            logger.exception(error)
            
    def stop(self, restart_programs=False):
        '''Stops movement on all axes by sending ST to the controller
        
        After ST, also program execution stops -- using the restart_programs 
        flag, they can be restarted this is risky, here it 
        is assumed that any program runs only the handcontroller and does 
        not induce any movement.
        '''
        self._send_command('ST')
        if restart_programs == True:
            self.execute_program()
    
    def execute_program(self):
        self._send_command('XQ')
            
    def wait_until_done(self, axis):
        '''Requires X,Y,Z or A,B,C etc..'''
        self.g.GMotionComplete(axis.upper())
        
    def read_position(self):
        '''Reports position from the stages 
        
        Notes:
            Updates internal position list self.positions as well.
        
        Returns:
            positions (list): list of positions 
        
        '''
        position = self._send_command('RP')
        position_list = position.split(',')
        try:
            position_list = [int(float(i)) for i in position_list]
            self.positions = [item[0]/item[1] for item in zip(position_list,self.encodercounts)]
        except Exception as error:
            logger.exception(error)

        return self.positions
    
    def move_relative(self, motion_dict):
        '''Command for relative motion 
        
        Args:
            motion_dict (dict): Dictionary in the form {1: 4000, 2:-234}, in general {axis_id:requested_position} 
                                with axis_id (int) and requested_position (int).
        Returns:
            Carries out motion
        '''
        
        ''' Set speed according to requested distance unless it has been set before '''
        if any(abs(distance)>250 for distance in motion_dict.values()):
            if self.speed != self.slow_speed:
                self.set_speed(self.slow_speed)
        else:
            if self.speed != self.fast_speed:
                self.set_speed(self.fast_speed)
                
        ''' Convert um to encodercounts '''
        command_list = self._convert_dict_to_sorted_list(motion_dict, self.num_axes)
        encoder_command_list = [i[0]*i[1] for i in zip(command_list, self.encodercounts)]
                
        ''' Create command string and initiate movement 
        
        Zero padding is important here as the non-commanded axes should stay where they are,
        otherwise previous relative motion commands are retained and possibly excuted 
        again after the 'BG' command ist sent.
        '''                
        command_string = self._convert_sorted_list_to_galil_string(encoder_command_list, zero_padding=True)
        self._send_command('PR'+command_string)
        self._send_command('BG')         
    
    def move_absolute(self, motion_dict):
        ''' Command for absolute motion 
        
        Args:
            motion_dict (dict): Dictionary in the form {1: 4000, 2:-234}, in general {axis_id:requested_position} 
                                with axis_id (int) and requested_position (int).
        
        '''
        
        ''' Set speed according to requested distance unless it has been set before '''
        current_positions = self.read_position()
        requested_positions = self._convert_dict_to_sorted_list(motion_dict, self.num_axes)
        ''' Set requested positions to current value to make the list difference zero
        Otherwise, the distances are not detected correctly
        '''
        requested_positions = [pos[0] if pos[0] != 0 else pos[1] for pos in zip(requested_positions,current_positions)]
        position_differences = self._list_difference(requested_positions,current_positions)    
        if any(abs(distance)>250 for distance in position_differences):
            if self.speed != self.slow_speed:
                self.set_speed(self.slow_speed)
        else:
            if self.speed != self.fast_speed:
                self.set_speed(self.fast_speed)
                
        ''' Convert um to encodercounts '''
        command_list = self._convert_dict_to_sorted_list(motion_dict, self.num_axes)
        encoder_command_list = [i[0]*i[1] for i in zip(command_list, self.encodercounts)]
                
        ''' Carry out motion 
        
        Removing zero padding is important here as the non-commanded axes should stay where they are,
        otherwise they move to position 0.
        '''
        command_string = self._convert_sorted_list_to_galil_string(encoder_command_list, zero_padding=False)
        self._send_command('PA'+command_string)
        self._send_command('BG')         
    
    def set_speed(self, speed):
        '''Sets speed for all axes to the requested value 
        
        Args:
            speed (int): speed value 
        
        '''
        list_axes = [i+1 for i in range(self.num_axes)]
        command_dict = {i : speed for i in list_axes}
        command_string = self._convert_dict_to_galil_string(command_dict, self.num_axes)
        self._send_command('SP'+command_string)
        self.speed = speed
        
    def get_speed(self):
        return self.speed
    
    def _convert_dict_to_galil_string(self, command_dict, length, zero_padding=False):
        '''Converts a dict of the form {1: 4000, 3:-234} into a string '4000,,-234'
        which can be combined with a command ('RP4000,,-234') and sent to the stage controller.

        Args:
            command_dict (dict): Command dictionary in the form {key (int): command value (int)}
            length (int): Length of output items
            zero_padding (bool): Indicates whether the values between commas should be filled with zeros

        Returns:
            galil_string (str): String with values between separating commas
        '''
        keylist = list(command_dict.keys())
        keylist.sort()

        galil_string = ''

        for i in range(length):
            if i+1 in keylist:
                galil_string += str(command_dict[i+1])
                galil_string += ','
            else:
                if zero_padding == True:
                    galil_string += '0'
                galil_string += ','
        return galil_string    
        
    def _convert_sorted_list_to_galil_string(self, command_list, zero_padding=True):
        '''Converts a list of the form [80,123,-53] into a string '80,123,-53'
        which can be combined with a command ('RP80,123,-53') and sent to the stage controller.
        
        Notes:
            If zero_padding is set to False, zeros are removed from the output: [80,0,-53] --> '80,,-53'

        Args:
            command_list (list): Command list in the form [80,123,-53]
            length (int): Length of output items
            zero_padding (bool): Indicates whether the values between commas should be filled with zeros

        Returns:
            galil_string (str): String with values between separating commas
        '''
        galil_string = ''
        for i in range(len(command_list)):
            if command_list[i] == 0 and zero_padding == False:
                galil_string += ','
            else:
                galil_string += str(command_list[i])
                galil_string += ','
            
        return galil_string

    def _convert_dict_to_sorted_list(self, input_dict, length):
        '''Converts an input dictionary into a zero-padded list of a certain length
        
        Args:
            input_dict (dict): Input dictionary in the form {key (int): value (int)} .
            length (int): Number of elements required in the output list.
        Returns:
            List with n = length sorted elements which are sorted
        '''
        keylist = list(input_dict.keys())
        keylist.sort()
        return [input_dict[i+1] if i+1 in keylist else 0 for i in range(length)]
    
    def _list_difference(self, list1, list2):
        '''Returns the element-wise difference of two lists of the same length
        
        Args:
            list1 (list): First list of values
            list2 (list): Second list of values
        '''
        return [i[0]-i[1] for i in zip(list1, list2)]
