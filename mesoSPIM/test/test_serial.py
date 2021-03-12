# To run the test:
# python -m test.test_serial
import unittest
import src.devices.filterwheels as fw

# Copy these from your config file
filterwheel_parameters = {'filterwheel_type' : 'Ludl',
                          'COMport' : 'COM6'}

filterdict = {'Empty-Alignment' : 0,
              '405/50' : 1,
              '480/40' : 2,
              '525/50' : 3,
              '535/30' : 4,
              '590/50' : 5,
              '585/40' : 6,
              '405/488/561/640 m' : 7,
              }

class TestFilterWheel(unittest.TestCase):
    def setUp(self) -> None:
        """"This will automatically call for EVERY single test method below."""
        if filterwheel_parameters['filterwheel_type'] == 'Ludl':
            self.fwheel = fw.LudlFilterwheel(filterwheel_parameters['COMport'], filterdict)
        else:
            raise ValueError('Only Ludl filterwheel test is currently implemented')

    def test_multiple_positions(self):
        for i_cycle in range(1):
            for filter in filterdict.keys():
                self.fwheel.set_filter(filter)

    # def tearDown(self) -> None:
    #     """"Tidies up after EACH test method execution."""


if __name__ == '__main__':
    unittest.main()
