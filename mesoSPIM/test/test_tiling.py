# To run the test:
# $ python -m test.test_h5
import unittest
from src.utils.multicolor_acquisition_wizard import MulticolorTilingWizard
from PyQt5 import QtWidgets
import sys

TEST_MANUALLY = False # set True to manually test the GUI, False to run unittests

class TestTilingWizard(unittest.TestCase):
    def setUp(self) -> None:
        """"This will automatically call for EVERY single test method below."""
        self.wiz = MulticolorTilingWizard()

    def test_image_counts(self):
        # assuming FOV = 1000, overlap 20%
        xy_start_cases = [(0, 0), (-100, -100), (0, 0)]
        xy_end_cases = [(200, 200), (100, 100), (10000, 7900)]
        xy_offset_cases = [(800, 800), (800, 800), (800, 800)]
        xy_counts_correct_answers = [(2, 2), (2, 2), (13, 11)]
        for i in range(len(xy_start_cases)):
            self.wiz.x_start, self.wiz.y_start = xy_start_cases[i]
            self.wiz.x_end, self.wiz.y_end = xy_end_cases[i]
            self.wiz.x_offset, self.wiz.y_offset = xy_offset_cases[i]
            self.wiz.update_image_counts()
            self.assertEqual((self.wiz.x_image_count, self.wiz.y_image_count), xy_counts_correct_answers[i],
                             f"Image count [{i}] {self.wiz.x_image_count, self.wiz.y_image_count} is incorrect," \
                             f" must be {xy_counts_correct_answers[i]}")

    # def tearDown(self) -> None:
    #     """"Tidies up after EACH test method execution."""

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    if not TEST_MANUALLY:
        unittest.main()
    else:
        wizard_window = MulticolorTilingWizard()
        wizard_window.show()
        sys.exit(wizard_window.exec_())