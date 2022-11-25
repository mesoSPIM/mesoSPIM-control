# To run the test:
# python -m test.test_serial
import unittest
import src.devices.filter_wheels.ludlcontrol as ludl
import src.devices.zoom.mesoSPIM_Zoom as zoomlib

"""
Filterwheel settings from config file
"""
filterwheel_parameters = {'filterwheel_type' : 'Ludl',
                          'COMport' : 'COM6'}
filterdict = {'Empty' : 0,
              '405/50' : 1,
              '480/40' : 2,
              '525/50' : 3,
              '535/30' : 4,
              '590/50' : 5,
              '585/40' : 6,
              '405/488/561/640 m' : 7,
              }

'''
Zoom configuration from config file
'''
zoom_parameters = {'zoom_type' : 'Dynamixel',
                   'servo_id' :  1,
                   'COMport' : 'COM10',
                   'baudrate' : 1000000}

zoomdict = {'0.63x' : 3423,
            '0.8x' : 3071,
            '1x' : 2707,
            '1.25x' : 2389,
            '1.6x' : 2047,
            '2x' : 1706,
            '2.5x' : 1354,
            '3.2x' : 967,
            '4x' : 637,
            '5x' : 318,
            '6.3x' : 0}

class TestFilterWheel(unittest.TestCase):
    def setUp(self) -> None:
        """"This will be called for EVERY test method of the class."""
        if filterwheel_parameters['filterwheel_type'] == 'Ludl':
            self.fwheel = ludl.LudlFilterwheel(filterwheel_parameters['COMport'], filterdict)
        else:
            raise ValueError('Only Ludl filterwheel test is currently implemented')

    def test_multiple_filter_pos(self):
        n_cycles = 3
        for i_cycle in range(n_cycles):
            print(f"cycle {i_cycle}/{n_cycles}")
            for filter in filterdict.keys():
                self.fwheel.set_filter(filter, wait_until_done=True)
                print(f"filter {filter}")

    # def tearDown(self) -> None:
    #     """"Tidies up after EACH test method execution."""

class TestZoomServo(unittest.TestCase):
    def setUp(self) -> None:
        """"This will be called for EVERY test method of the class."""
        if zoom_parameters['zoom_type'] == 'Dynamixel':
            self.zoom = zoomlib.DynamixelZoom(zoomdict, zoom_parameters['COMport'],
                                              zoom_parameters['servo_id'], zoom_parameters['baudrate'])
        else:
            raise ValueError('Only Dynamixel zoom servo test is currently implemented')

    def test_multiple_zoom_pos(self):
        n_cycles = 3
        for i_cycle in range(n_cycles):
            print(f"cycle {i_cycle}/{n_cycles}")
            for zoomratio in zoomdict.keys():
                self.zoom.set_zoom(zoomratio, wait_until_done=True)
                print(f"zoom {zoomratio}")


if __name__ == '__main__':
    unittest.main()
