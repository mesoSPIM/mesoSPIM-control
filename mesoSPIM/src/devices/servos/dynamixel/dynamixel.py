"""
General-purpose Dynamixel servo class to control e.g. mesoSPIM zoom or filter wheel
Authors: Fabian Voigt, Nikita Vladimirov
"""


import time
from PyQt5 import QtCore
from . import dynamixel_functions as dynamixel_func
import numpy as np
import logging

logger = logging.getLogger(__name__)
PROTOCOL_VERSION = 1


class Dynamixel(QtCore.QObject):
    def __init__(self, COMport, identifier=1, baudrate=115200):
        super().__init__()
        self.dynamixel = dynamixel_func
        self.id = identifier
        self.devicename = COMport.encode('utf-8') # bad naming convention
        self.baudrate = baudrate

        self.addr_mx_mult_turn_offset = 20
        self.addr_mx_torque_enable = 24
        self.addr_mx_goal_position = 30
        self.addr_mx_present_position = 36
        self.addr_mx_p_gain = 28
        self.addr_mx_torque_limit = 34
        self.addr_mx_moving_speed = 32

        ''' Specifies how much the goal position can be off (+/-) from the target '''
        self.goal_position_offset = 10
        self.multiturn_offset = 0
        self.moving_speed = 400
        ''' Specifies how long to sleep for the wait until done function'''
        self.sleeptime = 0.05
        self.timeout = 5

        # the dynamixel library uses integers instead of booleans for binary information
        self.torque_enable = 1
        self.torque_disable = 0
        self._connect()

    def _connect(self):
        try:
            logger.info(f"Connecting to serial port {self.devicename}")
            self.port_num = self.dynamixel.portHandler(self.devicename)
            self.dynamixel.packetHandler()
            self.dynamixel.openPort(self.port_num)
            self.dynamixel.setBaudRate(self.port_num, self.baudrate)
            self.multiturn_offset = self.dynamixel.read2ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_mult_turn_offset)
            self.multiturn_offset = self.normalize_position(self.multiturn_offset)
            logger.info(f"Dynamixel multi-turn offset: {self.multiturn_offset}")
        except Exception as e:
            logger.error(f"Failed to open serial port: {e}")

    def _move(self, position, wait_until_done=False):
        # Enable servo
        self.dynamixel.write1ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_torque_enable, self.torque_enable)
        # Write Moving Speed
        self.dynamixel.write2ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_moving_speed, self.moving_speed)
        # Write Torque Limit
        self.dynamixel.write2ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_torque_limit, 200)
        # Write P Gain
        self.dynamixel.write1ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_p_gain, 44)
        # Write Goal Position
        self.dynamixel.write2ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_goal_position, position)
        # Check position

        ''' This works even though the positions returned during movement are just crap
        - they have 7 to 8 digits. Only when the motor stops, positions are accurate
        -
        '''
        if wait_until_done:
            logger.info(f"Dynamixel (wait_until_done=True) goal positon {position}")
            start_time = time.time()
            upper_limit = position + self.goal_position_offset
            # print('Upper Limit: ', upper_limit)
            lower_limit = position - self.goal_position_offset
            # print('lower_limit: ', lower_limit)
            cur_position = np.int16(self.dynamixel.read2ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_present_position))
            cur_position = self.offset_position(self.normalize_position(cur_position))

            while (cur_position < lower_limit) or (cur_position > upper_limit):
                ''' Timeout '''
                if time.time() - start_time > self.timeout:
                    logger.error("Dynamixel zoom servo: timeout")
                    break
                time.sleep(self.sleeptime)
                cur_position = self.dynamixel.read2ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_present_position)
                cur_position = self.offset_position(self.normalize_position(cur_position))
                logger.info(f"Dynamixel normalized current position {cur_position}")

    def read_position(self):
        '''
        Returns position as an int between 0 and 4096
        '''
        cur_position = self.dynamixel.read4ByteTxRx(self.port_num, PROTOCOL_VERSION, self.id, self.addr_mx_present_position)
        return cur_position

    def normalize_position(self, pos):
        '''Negative numbers representation'''
        if pos >= 65535 // 2:
            cur_position = pos - 65535
        else:
            cur_position = pos
        return cur_position

    def offset_position(self, pos):
        '''Taking into account encoder offset for multi-turn mode.
        The encoder offset can be user-defined eg in Dynamixel Wizard software'''
        if self.multiturn_offset != 0:
            cur_position = pos - self.multiturn_offset
        else:
            cur_position = pos
        return cur_position

    def __del__(self):
        self.dynamixel.closePort(self.port_num)
