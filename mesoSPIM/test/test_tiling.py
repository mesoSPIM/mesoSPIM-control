# To run the test:
# python -m test.test_tiling
import unittest
from src.utils.multicolor_acquisition_wizard import MulticolorTilingWizard
from PyQt5 import QtWidgets
import sys

class TestTilingWizard(unittest.TestCase):
    def setUp(self) -> None:
        """"This will automatically call for EVERY single test method below."""
        self.wiz = MulticolorTilingWizard()

    def test_image_counts(self):
        # assuming FOV = 1000, overlap 20%
        xy_start_fixtures = [(0, 0), (-100, -100), (0, 0), (0, -350), (4500, 4700)]
        xy_end_fixtures = [(200, 200), (100, 100), (10000, 7900), (0, 350), (-3000, -5800)]
        xy_offset_fixtures = [(800, 800), (800, 800), (800, 800), (752, 752), (2948, 2948)]
        xy_counts_correct_answers = [(2, 2), (2, 2), (14, 11), (1, 2), (4, 5)]
        for i in range(len(xy_start_fixtures)):
            self.wiz.x_start, self.wiz.y_start = xy_start_fixtures[i]
            self.wiz.x_end, self.wiz.y_end = xy_end_fixtures[i]
            self.wiz.x_offset, self.wiz.y_offset = xy_offset_fixtures[i]
            self.wiz.update_image_counts()
            self.assertEqual((self.wiz.x_image_count, self.wiz.y_image_count), xy_counts_correct_answers[i],
                             f"Image count [{i}] {self.wiz.x_image_count, self.wiz.y_image_count} is incorrect," \
                             f" must be {xy_counts_correct_answers[i]}")

    # def tearDown(self) -> None:
    #     """"Tidies up after EACH test method execution."""

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    unittest.main()
