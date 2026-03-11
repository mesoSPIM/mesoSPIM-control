"""
mesoSPIM Module for controlling a discrete zoom changer
"""

import time
import logging
from PyQt5 import QtCore
from .devices.servos.dynamixel.dynamixel import Dynamixel
import serial
logger = logging.getLogger(__name__)

class DemoZoom(QtCore.QObject):
    '''Software-only zoom driver for use without physical hardware.

    All :meth:`set_zoom` calls validate the requested zoom string against
    ``zoomdict`` and optionally sleep 100 ms to simulate settling time.
    No serial or USB connections are opened.  Used for development and testing.
    '''
    def __init__(self, zoomdict):
        super().__init__()
        self.zoomdict = zoomdict

    def set_zoom(self, zoom, wait_until_done=True):
        """Simulate moving the zoom body to the named zoom position.

        Args:
            zoom (str): Zoom designation, e.g. ``'2x'``, that must be a key in
                ``self.zoomdict``.
            wait_until_done (bool): When ``True``, sleep 100 ms to simulate
                a mechanical settle delay.
        """
        if zoom in self.zoomdict:
            if wait_until_done:
                time.sleep(0.1)
   

class DynamixelZoom(Dynamixel):
    '''Zoom driver that controls a Dynamixel servo-driven zoom body.

    Inherits from :class:`mesoSPIM.src.devices.servos.dynamixel.dynamixel.Dynamixel`
    which handles low-level serial communication with the Dynamixel protocol.
    The ``zoomdict`` maps user-facing zoom strings (e.g. ``'2x'``) to the
    corresponding servo goal-position values.
    '''
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
    '''Zoom driver for a Mitutoyo motorised objective revolver.
    '''
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
        """Send the status query (``RRDSTU``) and confirm the revolver is ready."""
        response = self._send_command(b'RRDSTU\r')
        if response[:9] != 'ROK000001':
            msg = f"Error in Mitutoyo revolver initialization, response: {response} \nIf response is empty, check if the revolver is connected."
            logger.error(msg)
            print(msg)
        else:
            logger.info("Mitutoyo revolver initialized")

    def _send_command(self, command: bytes):
        """Write *command* to the serial port and return the decoded response line.

        Args:
            command (bytes): ASCII command terminated with ``\\r``.

        Returns:
            str: Decoded response string, or ``None`` on error.
        """
        try:
            self._reset_buffers()
            self.revolver_connection.write(command)
            message = self.revolver_connection.readline().decode("ascii")
            logger.debug(f"Serial received: {message} ")
            return message
        except Exception as error:
            logger.error(f"Serial exception of the Mitutoyo revolver: command {command.decode('ascii')}, error: {error}")

    def _reset_buffers(self):
        """Flush the serial input and output buffers before sending a command."""
        if self.revolver_connection is not None:
            self.revolver_connection.reset_input_buffer()
            self.revolver_connection.reset_output_buffer()
        else:
            logger.error("Serial port not initialized")

    def set_zoom(self, zoom, wait_until_done=True):
        """Move the revolver to the named objective position. 
        Communicates via RS-232 serial using the Mitutoyo ASCII protocol (``RWRMV<X>`` commands where ``X`` is one of ``A``–``E``).
        The ``zoomdict`` maps user-facing zoom strings to revolver positions  ``'A'`` through ``'E'``.

        Args:
            zoom (str): Zoom designation that must be a key in ``self.zoomdict``
                and whose value must be a letter in ``('A', 'B', 'C', 'D', 'E')``.
            wait_until_done (bool): When ``True``, wait 1 s for the revolver to
                complete its rotation before returning.
        """
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