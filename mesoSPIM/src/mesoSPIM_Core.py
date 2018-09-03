'''
Core for the mesoSPIM project
=============================
'''

import numpy as np
import time
from scipy import signal
import csv
import traceback

'''PyQt5 Imports'''
from PyQt5 import QtWidgets, QtCore, QtGui

'''National Instruments Imports'''
# import nidaqmx
# from nidaqmx.constants import AcquisitionType, TaskMode
# from nidaqmx.constants import LineGrouping, DigitalWidthUnits
# from nidaqmx.types import CtrTime

''' Import mesoSPIM modules '''
from .mesoSPIM_State import mesoSPIM_State

class mesoSPIM_Core(QtCore.QObject):
    '''This class is the pacemaker of a mesoSPIM'''
    sig_finished = QtCore.pyqtSignal()

    sig_state_updated = QtCore.pyqtSignal()

    def __init__(self, config, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent

        ''' The signal-slot switchboard '''
        self.parent.sig_live.connect(lambda: self.set_filter('515LP'))
        self.parent.sig_state_request.connect(self.state_request_handler)

        self.parent.sig_execute_script.connect(self.execute_script)

        # ''' Set the Camera thread up '''
        # self.camera_thread = QtCore.QThread()
        # self.camera_worker = mesoSPIM_Camera()
        # self.camera_worker.moveToThread(self.camera_thread)
        #
        # ''' Set the serial thread up '''
        # self.serial_thread = QtCore.QThread()
        # self.serial_worker = mesoSPIM_Serial(config)
        # self.serial_worker.moveToThread(self.serial_thread)

        # self.camera_thread.start()
        # self.serial_thread.start()

        self.set_state_parameter('state','idle')

    def __del__(self):
        '''Cleans the threads up after deletion, waits until the threads
        have truly finished their life.

        Make sure to keep this up to date with the number of threads
        '''
        # try:
        #     self.camera_thread.quit()
        #     self.serial_thread.quit()
        #
        #     self.camera_thread.wait()
        #     self.serial_thread.wait()
        # except:
        #     pass


    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(),dict.values()):
            print('State request: Key: ', key, ' Value: ', value)
            '''
            The request handling is done with exec() to write fewer lines of
            code.
            '''
            if key in ('filter','zoom','laser','intensity','shutterconfig'):
                exec('self.set_'+key+'(value)')


    def set_state_parameter(self, key, value):
        '''
        Sets the state of the parent (in most cases, mesoSPIM_MainWindow)

        In order to do this, a QMutexLocker has to be acquired

        Args:
            key (str): State dict key
            value (str, float, int): Value to set
        '''
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                self.parent.state[key]=value
                self.sig_state_updated.emit()
            else:
                print('Set state parameters failed: Key ', key, 'not in state dictionary!')

    def set_state_parameters(self, dict):
        '''
        Sets a whole dict of state parameters:

        Args:
            dict (dict):
        '''
        with QtCore.QMutexLocker(self.parent.state_mutex):
            for key, value in dict:
                if key in self.parent.state:
                    self.parent.state[key]=value
                    self.sig_state_updated.emit()
                else:
                    print('Set state parameters failed: Key ', key, 'not in state dictionary!')

    def get_state_parameter(self, key):
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                return self.parent.state[key]
            else:
                print('Getting state parameters failed: Key ', key, 'not in state dictionary!')

    def set_filter(self, filter):
        print('Setting filter')
        self.set_state_parameter('filter',filter)
        print('Filter set')

    def set_zoom(self, zoom):
        print('Setting zoom')
        self.set_state_parameter('zoom',zoom)
        print('Zoom set')

    def set_laser(self, laser):
        print('Setting laser')
        self.set_state_parameter('laser',laser)
        print('Laser set')

    def set_shutterconfig(self, shutterconfig):
        print('Setting shutterconfig')
        self.set_state_parameter('shutterconfig',shutterconfig)
        print('Shutterconfig set')

    def set_intensity(self, intensity):
        print('Setting intensity')
        self.set_state_parameter('intensity',intensity)
        print('Intensity set')

    def live(self):
        pass

    @QtCore.pyqtSlot(str)
    def execute_script(self, script):
        self.set_state_parameter('state','running_script')
        try:
            exec(script)
        except:
            traceback.print_exc()
        self.sig_finished.emit()
        self.set_state_parameter('state','idle')
