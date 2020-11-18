"""
mesoSPIM Module for controlling Sutter Lambda Filter Wheels

Author: Kevin Dean,
Basically 100% stolen from Andrew York's GitHub Account :)
"""

import serial
import time


class Lambda10B:
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
            print('Done initializing filter wheel')
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
                    print('Done initializing filter wheel.')

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
