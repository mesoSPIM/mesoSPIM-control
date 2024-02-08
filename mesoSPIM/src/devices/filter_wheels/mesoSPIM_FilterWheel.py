'''
mesoSPIM Filterwheel classes
Authors: Fabian Voigt, Nikita Vladimirov
'''
import time
import serial
import io
import os
from PyQt5 import QtWidgets, QtCore, QtGui
import logging
logger = logging.getLogger(__name__)
from mesoSPIM.src.devices.servos.dynamixel.dynamixel import Dynamixel
from mesoSPIM.src.devices.filter_wheels.ZWO_EFW import pyzwoefw
from mesoSPIM.src.mesoSPIM_State import mesoSPIM_StateSingleton

state = mesoSPIM_StateSingleton()

class mesoSPIM_DemoFilterWheel(QtCore.QObject):
    def __init__(self, filterdict):
        super().__init__()
        self.filterdict = filterdict

    def _check_if_filter_in_filterdict(self, filter):
        '''
        Checks if the filter designation (string) given as argument
        exists in the filterdict
        '''
        if filter in self.filterdict:
            return True
        else:
            raise ValueError('Filter designation not in the configuration')

    def set_filter(self, filter, wait_until_done=False):
        if self._check_if_filter_in_filterdict(filter) is True:
            if wait_until_done:
                time.sleep(1)


class ZwoFilterWheel(QtCore.QObject):
    '''Astronomy filter wheels from https://astronomy-imaging-camera.com'''
    def __init__(self, filterdict):
        dll_path = os.path.join(state['package_directory'], 'src', 'devices', 'filter_wheels', 'ZWO_EFW', 'lib', 'Win64', 'EFW_filter.dll')
        self.device = pyzwoefw.EFW(dll_path)
        logger.info(f"Number of ZWO EFW filter wheels connected: {self.device.GetNum()}")
        self.n_slots = self.device.GetProperty(self.device.IDs[0])['slotNum']
        assert len(filterdict) <= self.n_slots, f"The length of filter dictionary {filterdict} exceeds " \
                                                f"the number of physical filter wheel slots ({self.n_slots}). " \
                                                f"\nChange the filter dictionary in config file."
        self.filterdict = filterdict

    def set_filter(self, filter, wait_until_done=False):
        if filter in self.filterdict:
            self.device.SetPosition(self.device.IDs[0], self.filterdict[filter], wait_until_done)
            self.filter = filter
            if wait_until_done:
                time.sleep(1)
        else:
            raise ValueError(f'Filter {filter} not found in the configuration file, please update config file')

    def __del__(self):
        if self.device is not None:
            self.device.Close(self.device.IDs[0])
        else:
            pass

class DynamixelFilterWheel(Dynamixel):
    def __init__(self, filterdict, COMport, identifier=1, baudrate=115200):
        super().__init__(COMport, identifier, baudrate)
        self.filterdict = filterdict
        self.filter = None

    def set_filter(self, filter, wait_until_done=False):
        """Changes filter after checking that the commanded value exists"""
        if filter in self.filterdict:
            self._move(self.filterdict[filter], wait_until_done)
            self.filter = filter
        else:
            raise ValueError(f'Filter {filter} not found in the configuration file, please update config file')


class LudlFilterWheel(QtCore.QObject):
    """ Class to control a 10-position Ludl filterwheel

    Needs a dictionary which combines filter designations and position IDs
    in the form:

    filters = {'405-488-647-Tripleblock' : 0,
           '405-488-561-640-Quadrupleblock': 1,
           '464 482-35': 2,
           '508 520-35': 3,
           '515LP':4,
           '529 542-27':5,
           '561LP':6,
           '594LP':7,
           'Empty':8,}

    If there are tuples instead of integers as values, the
    filterwheel is assumed to be a double wheel.

    I.e.: '508 520-35': (2,3)
    """

    def __init__(self, COMport, filterdict, baudrate=9600):
        super().__init__()

        self.COMport = COMport
        self.baudrate = baudrate
        self.filterdict = filterdict
        self.double_wheel = False
        self.ser = None
        self.sio = None
        self._connect()
        ''' Delay in s for the wait until done function '''
        self.wait_until_done_delay = 0.5

        """
        If the first entry of the filterdict has a tuple
        as value, it is assumed that it is a double-filterwheel
        to change the serial commands accordingly.

        TODO: This doesn't check that the tuple has length 2.
        """
        self.first_item_in_filterdict = list(self.filterdict.keys())[0]

        if type(self.filterdict[self.first_item_in_filterdict]) is tuple:
            self.double_wheel = True

    def _connect(self):
        """"Note: Only one connection should be done per session. Connecting frequently is error-prone,
         because COM port can be scanned by another program (e.g. laser control) and thus be permission-denied at random
          times."""
        try:
            self.ser = serial.Serial(self.COMport,
                                     self.baudrate,
                                     parity=serial.PARITY_NONE,
                                     timeout=0, write_timeout=0,
                                     xonxoff=False,
                                     stopbits=serial.STOPBITS_TWO)
            self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
        except serial.SerialException as e:
            logger.error(f"Serial connection to Ludl filter wheel failed: {e}")

    def _check_if_filter_in_filterdict(self, filter):
        '''
        Checks if the filter designation (string) given as argument
        exists in the filterdict
        '''
        if filter in self.filterdict:
            return True
        else:
            raise ValueError('Filter designation not in the configuration')

    def set_filter(self, filter, wait_until_done=False):
        '''
        Moves filter using the pyserial command set.
        No checks are done whether the movement is completed or
        finished in time.
        '''
        if self._check_if_filter_in_filterdict(filter) is True:
            """
            Check for double or single wheel
            TODO: A bit of repeating code in here. Might be better to
            spin the create and send commands off.
            """
            if self.double_wheel is False:
                """ Single wheel code """
                # Get the filter position from the filterdict:
                self.filternumber = self.filterdict[filter]
                # Rotat is the Ludl high-level command for moving a filter wheel
                self.ser.flush()
                self.ludlstring = 'Rotat S M ' + str(self.filternumber) + '\n'
                self.sio.write(str(self.ludlstring))
                self.sio.flush()

                if wait_until_done:
                    ''' Wait a certain number of seconds. This is a hack

                    Testing with :
                    self.sio.write(str('Rdstat S'))
                    self.sio.flush()
                    print('First:', self.sio.readline(10))
                    time.sleep(0.1)
                    self.sio.write(str('Rdstat S'))
                    self.sio.flush()
                    print('Second: ', self.sio.readline(10))

                    yielded very unstable results, sometimes ":N -3", sometimes
                    ":A" - and blocking & crashing the connection
                    '''
                    time.sleep(self.wait_until_done_delay)

            else:
                """ Double wheel code """
                # Get the filter position tuple from the filterdict:
                self.filternumber = self.filterdict[filter]
                """ Write command for the primary wheel """
                self.ludlstring0 = 'Rotat S M ' + str(self.filternumber[0]) + '\n'
                self.sio.write(str(self.ludlstring0))
                """ Write command for the auxillary wheel """
                self.ludlstring1 = 'Rotat S A ' + str(self.filternumber[1]) + '\n'
                self.sio.write(str(self.ludlstring1))
                self.sio.flush()

                if wait_until_done:
                    time.sleep(self.wait_until_done_delay)
        else:
            logger.error(f'Filter {filter} not found in configuration.')

    def __del__(self):
        self.sio.flush()
        self.ser.close()


class SutterLambda10BFilterWheel:
    def __init__(self, comport, filterdict, baudrate=9600, read_on_init=True):
        super().__init__()
        self.COMport = comport
        self.baudrate = baudrate
        self.filterdict = filterdict
        self.double_wheel = False

        ''' Delay in s for the wait until done function '''
        self.wait_until_done_delay = 0.5

        self.first_item_in_filterdict = list(self.filterdict.keys())[0]
        if type(self.filterdict[self.first_item_in_filterdict]) is tuple:
            self.double_wheel = True

        # Open Serial Port
        try:
            self.serial = serial.Serial(self.COMport, self.baudrate, timeout=.25)
        except serial.SerialException:
            raise UserWarning('Could not open the serial port to the Sutter Lambda 10-B.')

        # Place Controller Into Online Mode
        self.serial.write(bytes.fromhex('ee'))

        # Check to see if the initialization sequence has finished.
        if read_on_init:
            self.read(2)  # class 'bytes'
            self.init_finished = True
            logger.info('Done initializing filter wheel')
        else:
            self.init_finished = False
        self.filternumber = 0

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def _check_if_filter_in_filterdict(self, filterposition):
        # Checks if the filter designation (string) given as argument exists in the filterdict
        if filterposition in self.filterdict:
            return True
        else:
            raise ValueError('Filter designation not in the configuration')

    def set_filter(self, filterposition=0, speed=0, wait_until_done=False):
        # Confirm that the filter is present in the filter dictionary
        if self._check_if_filter_in_filterdict(filterposition) is True:

            # Confirm that you are only operating in a single filter wheel configuration.
            if self.double_wheel is False:

                # Identify the Filter Number from the Filter Dictionary
                self.wheel_position = self.filterdict[filterposition]

                # Make sure you are moving it to a reasonable filter position, at a reasonable speed.
                assert self.wheel_position in range(10)
                assert speed in range(8)

                # If previously we did not confirm that the initialization was complete, check now.
                if not self.init_finished:
                    self.read(2)
                    self.init_finished = True
                    logger.info('Done initializing filter wheel.')

                # Filter Wheel Command Byte Encoding = wheel + (speed*16) + position = command byte
                outputcommand = self.wheel_position + 16 * speed
                outputcommand = outputcommand.to_bytes(1, 'little')

                # Send out Command
                self.serial.write(outputcommand)
                if wait_until_done:
                    time.sleep(self.wait_until_done_delay)

                # Read up to 2 bytes
                self.read(2)

            else:
                raise UserWarning("Sutter Operates only in a Single Filter Wheel Configuration.")

    def read(self, num_bytes):
        for i in range(100):
            num_waiting = self.serial.inWaiting()
            if num_waiting == num_bytes:
                break
            time.sleep(0.02)
        else:
            raise UserWarning("The serial port to the Sutter Lambda 10-B is on, but it isn't responding as expected.")
        return self.serial.read(num_bytes)

    def close(self):
        self.set_filter()
        self.serial.close()
