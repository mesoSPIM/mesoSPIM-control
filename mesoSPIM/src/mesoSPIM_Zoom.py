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

    def set_zoom(self, zoom, wait_until_done=False):
        if zoom in self.zoomdict:
            if wait_until_done:
                time.sleep(1)
   

class DynamixelZoom(Dynamixel):
    def __init__(self, zoomdict, COMport, identifier=1, baudrate=115200):
        super().__init__(COMport, identifier, baudrate)
        self.zoomdict = zoomdict

    def set_zoom(self, zoom, wait_until_done=False):
        """Changes zoom after checking that the commanded value exists"""
        if zoom in self.zoomdict:
            self._move(self.zoomdict[zoom], wait_until_done)
            self.zoomvalue = zoom
        else:
            raise ValueError('Zoom designation not in the configuration')


class MitutoyoZoom(QtCore.QObject):
    def __init__(self, zoomdict, COMport, baudrate=9600):
        super().__init__()
        self.port = self.COMport
        self.baudrate = baudrate
        self.zoomdict = zoomdict
        self.revolver_connection = serial.Serial(self.port, self.baudrate, parity=serial.PARITY_NONE, timeout=5,
                                            xonxoff=False, stopbits=serial.STOPBITS_ONE)

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

    def set_zoom(self, zoom, wait_until_done=False):
        if zoom in self.zoomdict:
            position = self.zoomdict[zoom]
            assert position in ('A', 'B', 'C', 'D', 'E'), "Revolver position must be one of ('A', 'B', 'C', 'D', 'E')"
            command = 'RWRMV' + position + '\r'
            message = self._send_command(command.encode('ascii'))
            if message != 'ROK\r':
                logger.error(f"Mitutoyo revolver response: {message}")
        else:
            return ValueError(f"Zoom {zoom} not in 'zoomdict', check your config file")