"""
mesoSPIM Module for controlling a discrete zoom changer

Authors: Fabian Voigt, Nikita Vladimirov
"""

import time
import logging
from PyQt5 import QtCore
from .devices.servos.dynamixel.dynamixel import Dynamixel
import serial
logger = logging.getLogger(__name__)

class DemoZoom(QtCore.QObject):
    def __init__(self, zoomdict):
        super().__init__()
        self.zoomdict = zoomdict

    def set_zoom(self, zoom, wait_until_done=True):
        if zoom in self.zoomdict:
            if wait_until_done:
                time.sleep(0.1)
   

class DynamixelZoom(Dynamixel):
    def __init__(self, zoomdict, COMport, identifier=1, baudrate=115200):
        super().__init__(COMport, identifier, baudrate)
        self.zoomdict = zoomdict

    def set_zoom(self, zoom, wait_until_done=True):
        """Changes zoom after checking that the commanded value exists"""
        if zoom in self.zoomdict:
            self._move(self.zoomdict[zoom], wait_until_done)
            self.zoomvalue = zoom
        else:
            raise ValueError('Zoom designation not in the configuration')


class MitutoyoZoom(QtCore.QObject):
    def __init__(self, zoomdict, COMport, baudrate=9600):
        super().__init__()
        self.port = COMport
        self.baudrate = baudrate
        self.zoomdict = zoomdict
        try:
            self.revolver_connection = serial.Serial(self.port, self.baudrate, parity=serial.PARITY_EVEN, timeout=5,
                                                stopbits=serial.STOPBITS_ONE)
            self._initialize()
        except Exception as error:
            msg = f"Serial connection to Mitutoyo revolver failed, error: {error}"
            logger.error(msg)
            print(msg)

    def _initialize(self):
        response = self._send_command(b'RRDSTU\r')
        if response[:9] != 'ROK000001':
            msg = f"Error in Mitutoyo revolver initialization, response: {response} \nIf response is empty, check if the revolver is connected."
            logger.error(msg)
            print(msg)
        else:
            logger.info("Mitutoyo revolver initialized")

    def _send_command(self, command: bytes):
        try:
            self._reset_buffers()
            self.revolver_connection.write(command)
            message = self.revolver_connection.readline().decode("ascii")
            logger.debug(f"Serial received: {message} ")
            return message
        except Exception as error:
            logger.error(f"Serial exception of the Mitutoyo revolver: command {command.decode('ascii')}, error: {error}")

    def _reset_buffers(self):
        if self.revolver_connection is not None:
            self.revolver_connection.reset_input_buffer()
            self.revolver_connection.reset_output_buffer()
        else:
            logger.error("Serial port not initialized")

    def set_zoom(self, zoom, wait_until_done=True):
        if zoom in self.zoomdict:
            position = self.zoomdict[zoom]
            assert position in ('A', 'B', 'C', 'D', 'E'), "Revolver position must be one of ('A', 'B', 'C', 'D', 'E')"
            command = 'RWRMV' + position + '\r'
            message = self._send_command(command.encode('ascii'))
            if message != 'ROK\r\n':
                msg = f"Error in Mitutoyo revolver command, response:{message}."
                logger.error(msg)
                print(msg)
            if wait_until_done:
                time.sleep(1) #  wait for the revolver to move
        else:
            return ValueError(f"Zoom {zoom} not in 'zoomdict', check your config file")

    def __del__(self):
        if self.revolver_connection is not None:
            self.revolver_connection.close()
        else:
            pass