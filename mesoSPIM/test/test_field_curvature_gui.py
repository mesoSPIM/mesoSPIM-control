# To run the test:
# python -m pytest test/test_field_curvature_gui.py -q
"""
Regression tests for the field curvature analysis tool (src/utils/field_curvature_gui_qt.py).

Builds a synthetic z-stack of a square-wave (Ronchi-like) target whose modulation depth
follows a Gaussian along Z, with the Gaussian peak displaced parabolically across the
field (Y = array axis 1 / TIFF rows, X = array axis 2 / TIFF columns). The contrast
per ROI and the axial sag are then known analytically, so the
contrast table, the Z-profile of maximum contrast and the summary metrics can all be
checked against ground truth.
"""
import os
import tempfile
import unittest

import numpy as np
from tifffile import imwrite

from src.utils import field_curvature_gui_qt as fc

K = 2.3548200450309493  # FWHM = K * sigma, for a Gaussian

N_ROIS = 17          # odd, so the ROI grid has an exact center and exact edges at +/-1
ROI_PX = 32
N_Z = 41
Z_STEP_UM = 2.0
Z_CENTER_UM = 40.0   # axial position of best contrast at the center of the field
SAG_Y_UM = 12.0      # extra defocus at the two ends of axis 1 (Y, rows)
SAG_X_UM = 8.0       # extra defocus at the two ends of axis 2 (X, columns)
SIGMA_UM = 8.0
BASELINE = 1000.0
AMPLITUDE = 900.0    # contrast of a fully modulated ROI is AMPLITUDE / BASELINE = 0.9
FULL_CONTRAST = AMPLITUDE / BASELINE

FOV_X_MM, FOV_Y_MM = 2.5, 4.3  # arbitrary but distinct, to check the sag weighting


def make_grating_stack(saturate=False):
    """Square-wave target, Gaussian contrast along Z, parabolic field curvature."""
    n_px = N_ROIS * ROI_PX
    z_um = np.arange(N_Z) * Z_STEP_UM

    # Peak-contrast position per ROI: parabolic in both field coordinates.
    roi_index = np.arange(N_ROIS)
    normalized = (roi_index - N_ROIS // 2) / (N_ROIS // 2)
    z_peak_um = (Z_CENTER_UM
                 + SAG_Y_UM * normalized[:, None] ** 2
                 + SAG_X_UM * normalized[None, :] ** 2)

    # Modulation depth m(z, roi_y, roi_x), expanded to full-frame pixels.
    modulation = np.exp(-(z_um[:, None, None] - z_peak_um[None, :, :]) ** 2 / (2 * SIGMA_UM ** 2))
    modulation = np.repeat(np.repeat(modulation, ROI_PX, axis=1), ROI_PX, axis=2)

    # 50/50 duty cycle square wave, so the 1st/99th percentiles land on the two levels.
    square = np.where((np.arange(n_px) // 4) % 2 == 0, 1.0, -1.0)[None, :]
    square = np.broadcast_to(square, (n_px, n_px))

    stack = BASELINE + AMPLITUDE * modulation * square[None, :, :]
    if saturate:
        stack[0, :10, :10] = 65535.0
    return stack.astype(np.uint16)


def write_temp_stack(stack):
    path = os.path.join(tempfile.mkdtemp(), "grating.tif")
    imwrite(path, stack)
    return path


class TestContrastTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = write_temp_stack(make_grating_stack())
        cls.table, cls.n_saturated = fc.contrast_table_from_stack(cls.path, N_ROIS, N_ROIS)

    def test_table_shape_matches_roi_grid(self):
        self.assertEqual(self.table.shape, (N_Z, N_ROIS, N_ROIS))
        self.assertEqual(self.n_saturated, 0)

    def test_full_contrast_at_the_center_of_the_field(self):
        """Z_CENTER_UM falls exactly on plane 20, where the central ROI is in focus."""
        center = N_ROIS // 2
        self.assertAlmostEqual(self.table[20, center, center], FULL_CONTRAST, delta=0.01)

    def test_field_edges_are_defocused_in_the_central_plane(self):
        center = N_ROIS // 2
        self.assertLess(self.table[20, 0, center], self.table[20, center, center])
        self.assertLess(self.table[20, center, 0], self.table[20, center, center])

    def test_vectorised_table_matches_per_roi_loop(self):
        """The per-plane reshape must give exactly what a nested per-ROI loop gives."""
        from tifffile import imread
        plane = imread(self.path)[20]
        for i, j in [(0, 0), (N_ROIS // 2, N_ROIS // 2), (N_ROIS - 1, N_ROIS - 1)]:
            roi = plane[i * ROI_PX:(i + 1) * ROI_PX, j * ROI_PX:(j + 1) * ROI_PX]
            self.assertAlmostEqual(self.table[20, i, j], fc.contrast(roi), places=12)

    def test_z_profile_recovers_the_injected_sag(self):
        """Maximum-contrast position per ROI, in microns, within the 1 um upsampled grid."""
        profile = fc.z_profile_from_table(self.table, Z_STEP_UM)
        center = N_ROIS // 2
        self.assertAlmostEqual(profile[center, center], Z_CENTER_UM, delta=1.5)
        self.assertAlmostEqual(profile[0, center], Z_CENTER_UM + SAG_Y_UM, delta=1.5)
        self.assertAlmostEqual(profile[-1, center], Z_CENTER_UM + SAG_Y_UM, delta=1.5)
        self.assertAlmostEqual(profile[center, 0], Z_CENTER_UM + SAG_X_UM, delta=1.5)
        self.assertAlmostEqual(profile[center, -1], Z_CENTER_UM + SAG_X_UM, delta=1.5)

    def test_summary_metrics(self):
        metrics = fc.summary_metrics(self.table, Z_STEP_UM, FOV_X_MM, FOV_Y_MM)
        self.assertAlmostEqual(metrics['dof_um'], K * SIGMA_UM, delta=0.5)
        self.assertAlmostEqual(metrics['sag_x_um'], SAG_X_UM, delta=0.5)
        self.assertAlmostEqual(metrics['sag_y_um'], SAG_Y_UM, delta=0.5)
        expected_ave = (SAG_X_UM * FOV_X_MM + SAG_Y_UM * FOV_Y_MM) / (FOV_X_MM + FOV_Y_MM)
        self.assertAlmostEqual(metrics['ave_sag_um'], expected_ave, delta=0.5)
        self.assertAlmostEqual(metrics['z_best_um'], Z_CENTER_UM, delta=1.0)
        self.assertEqual(metrics['z_best_index'], 20)
        self.assertAlmostEqual(metrics['max_contrast'], FULL_CONTRAST, delta=0.01)


class TestEdgeCases(unittest.TestCase):
    def test_saturated_planes_are_counted(self):
        path = write_temp_stack(make_grating_stack(saturate=True))
        _, n_saturated = fc.contrast_table_from_stack(path, N_ROIS, N_ROIS)
        self.assertEqual(n_saturated, 1)

    def test_too_fine_roi_grid_raises(self):
        path = write_temp_stack(make_grating_stack())
        with self.assertRaises(ValueError):
            fc.contrast_table_from_stack(path, 500, 500)

    def test_single_plane_is_not_a_stack(self):
        path = write_temp_stack(make_grating_stack()[:1])
        with self.assertRaises(ValueError):
            fc.contrast_table_from_stack(path, N_ROIS, N_ROIS)

    def test_cancelling_the_progress_callback_aborts(self):
        path = write_temp_stack(make_grating_stack())
        with self.assertRaises(KeyboardInterrupt):
            fc.contrast_table_from_stack(path, N_ROIS, N_ROIS, lambda iz, n_z: iz < 3)

    def test_linear_trend_recovers_the_slope(self):
        slope = 3.5
        profile = 100.0 + slope * np.arange(10)
        detrended = profile - fc.linear_trend(profile)
        self.assertTrue(np.allclose(detrended, 100.0))


if __name__ == "__main__":
    unittest.main()
