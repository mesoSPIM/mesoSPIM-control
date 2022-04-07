"""
mesoSPIM Module for controlling a discrete zoom changer

Authors: Fabian Voigt, Nikita Vladimirov
"""

import time
from PyQt5 import QtCore
from .devices.servos.dynamixel.dynamixel import Dynamixel


class DemoZoom(QtCore.QObject):
    def __init__(self, zoomdict):
        super().__init__()
        self.zoomdict = zoomdict

    def set_zoom(self, zoom, wait_until_done=False):
        if zoom in self.zoomdict:
            print('Zoom set to: ', str(zoom))
            if wait_until_done:
                time.sleep(1)
   

class DynamixelZoom(Dynamixel):
    def __init__(self, zoomdict, COMport, identifier=1, baudrate=1000000):
        super().__init__(COMport, identifier, baudrate)
        self.zoomdict = zoomdict

    def set_zoom(self, zoom, wait_until_done=False):
        """Changes zoom after checking that the commanded value exists"""
        if zoom in self.zoomdict:
            self._move(self.zoomdict[zoom], wait_until_done)
            self.zoomvalue = zoom
        else:
            raise ValueError('Zoom designation not in the configuration')
