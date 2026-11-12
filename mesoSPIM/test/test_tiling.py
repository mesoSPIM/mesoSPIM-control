"""
Tile counts of the Tiling Wizard.

Run from the mesoSPIM/ directory:  python -m pytest test/test_tiling.py -q

update_image_counts() only does arithmetic on the wizard's start, end and offset values, so it is
called on a plain object: building the wizard needs a running Qt application and a parent window
with the microscope state.
"""
import unittest
from types import SimpleNamespace

from src.utils.multicolor_acquisition_wizard import MulticolorTilingWizard


class TestTilingWizard(unittest.TestCase):
    def test_image_counts(self):
        # assuming FOV = 1000, overlap 20%
        xy_start_fixtures = [(0, 0), (-100, -100), (0, 0), (0, -350), (4500, 4700)]
        xy_end_fixtures = [(200, 200), (100, 100), (10000, 7900), (0, 350), (-3000, -5800)]
        xy_offset_fixtures = [(800, 800), (800, 800), (800, 800), (752, 752), (2948, 2948)]
        xy_counts_correct_answers = [(2, 2), (2, 2), (14, 11), (1, 2), (4, 5)]
        for i in range(len(xy_start_fixtures)):
            wiz = SimpleNamespace()
            wiz.x_start, wiz.y_start = xy_start_fixtures[i]
            wiz.x_end, wiz.y_end = xy_end_fixtures[i]
            wiz.x_offset, wiz.y_offset = xy_offset_fixtures[i]
            MulticolorTilingWizard.update_image_counts(wiz)
            self.assertEqual((wiz.x_image_count, wiz.y_image_count), xy_counts_correct_answers[i],
                             f"Image count [{i}] {wiz.x_image_count, wiz.y_image_count} is incorrect,"
                             f" must be {xy_counts_correct_answers[i]}")


if __name__ == '__main__':
    unittest.main()
