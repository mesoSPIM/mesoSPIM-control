"""
mesoSPIM Module for controlling a discrete zoom changer

Author: Fabian Voigt

#TODO
"""

import time

from PyQt5 import QtWidgets, QtCore, QtGui

class DemoZoom(QtCore.QObject):
    def __init__(self, zoomdict):
        super().__init__()
        self.zoomdict = zoomdict

    def set_zoom(self, zoom, wait_until_done=False):
        if zoom in self.zoomdict:
            print('Zoom set to: ', str(zoom))
            if wait_until_done:
                time.sleep(1)
   

class DynamixelZoom(QtCore.QObject):
    def __init__(self, zoomdict, COMport, identifier=2, baudrate=1000000):
        super().__init__()
        from .dynamixel import dynamixel_functions as dynamixel

        self.zoomdict = zoomdict
        self.dynamixel = dynamixel
        self.id = identifier
        self.devicename = COMport.encode('utf-8') # bad naming convention
        self.baudrate = baudrate

        self.addr_mx_torque_enable = 24
        self.addr_mx_goal_position = 30
        self.addr_mx_present_position = 36
        self.addr_mx_p_gain = 28
        self.addr_mx_torque_limit = 34
        self.addr_mx_moving_speed = 32

        ''' Specifies how much the goal position can be off (+/-) from the target '''
        self.goal_position_offset = 10
        ''' Specifies how long to sleep for the wait until done function'''
        self.sleeptime = 0.05
        self.timeout = 15

        # the dynamixel library uses integers instead of booleans for binary information
        self.torque_enable = 1
        self.torque_disable = 0

        self.port_num = dynamixel.portHandler(self.devicename)
        self.dynamixel.packetHandler()

    def set_zoom(self, zoom, wait_until_done=False):
        """Changes zoom after checking that the commanded value exists"""
        if zoom in self.zoomdict:
            self._move(self.zoomdict[zoom], wait_until_done)
            self.zoomvalue = zoom
        else:
            raise ValueError('Zoom designation not in the configuration')

    def _move(self, position, wait_until_done=False):
        # open port and set baud rate
        self.dynamixel.openPort(self.port_num)
        self.dynamixel.setBaudRate(self.port_num, self.baudrate)
        # Enable servo
        self.dynamixel.write1ByteTxRx(self.port_num, 1, self.id, self.addr_mx_torque_enable, self.torque_enable)
        # Write Moving Speed
        self.dynamixel.write2ByteTxRx(self.port_num, 1, self.id, self.addr_mx_moving_speed, 100)
        # Write Torque Limit
        self.dynamixel.write2ByteTxRx(self.port_num, 1, self.id, self.addr_mx_torque_limit, 200)
        # Write P Gain
        self.dynamixel.write1ByteTxRx(self.port_num, 1, self.id, self.addr_mx_p_gain, 44)
        # Write Goal Position
        self.dynamixel.write2ByteTxRx(self.port_num, 1, self.id, self.addr_mx_goal_position, position)
        # Check position

        ''' This works even though the positions returned during movement are just crap
        - they have 7 to 8 digits. Only when the motor stops, positions are accurate
        -
        '''
        if wait_until_done:
            start_time = time.time()
            upper_limit = position + self.goal_position_offset
            # print('Upper Limit: ', upper_limit)
            lower_limit = position - self.goal_position_offset
            # print('lower_limit: ', lower_limit)
            cur_position = self.dynamixel.read4ByteTxRx(self.port_num, 1, self.id, self.addr_mx_present_position)

            while (cur_position < lower_limit) or (cur_position > upper_limit):
                ''' Timeout '''
                if time.time()-start_time > self.timeout:
                    break
                time.sleep(0.05)
                cur_position = self.dynamixel.read4ByteTxRx(self.port_num, 1, self.id, self.addr_mx_present_position)
                # print(cur_position)

        self.dynamixel.closePort(self.port_num)

    def read_position(self):
        '''
        Returns position as an int between 0 and 4096

        Opens & closes the port
        '''
        self.dynamixel.openPort(self.port_num)
        self.dynamixel.setBaudRate(self.port_num, self.baudrate)
        cur_position = self.dynamixel.read4ByteTxRx(self.port_num, 1, self.id, self.addr_mx_present_position)

        self.dynamixel.closePort(self.port_num)

        return cur_position
