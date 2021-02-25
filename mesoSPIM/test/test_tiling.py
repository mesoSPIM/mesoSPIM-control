# python -m test.test_h5
import unittest
from src.utils.multicolor_acquisition_wizard import MulticolorTilingWizard
from PyQt5 import QtCore, QtGui, QtWidgets
import sys

app = QtWidgets.QApplication(sys.argv)

class TestTilingWizard(unittest.TestCase):
    def setUp(self) -> None:
        """"This will automatically call for EVERY single test method below."""
        self.wiz = MulticolorTilingWizard()

    def test_image_counts(self):
        self.wiz.x_start = 0
        self.wiz.y_start = 0
        self.wiz.x_end = 30 # small delta_x
        self.wiz.y_end = 30 # small delta_y
        self.wiz.x_offset = self.wiz.y_offset = 60 # say, FOV=300, and default 20% overlap is used
        self.wiz.update_image_counts()
        self.assertEqual(self.wiz.x_image_count, 2, f"Image count along X is {self.wiz.x_image_count}, must be 2")
        self.assertEqual(self.wiz.y_image_count, 2, f"Image count along Y is {self.wiz.y_image_count}, must be 2")

    # def tearDown(self) -> None:
    #     """"Tidies up after EACH test method execution."""

if __name__ == '__main__':
    unittest.main()