# To run the test:
# python -m test.test_psf_gui
"""
Regression tests for the Bead PSF Analysis tool (src/utils/psf_gui_qt.py).

Builds synthetic Gaussian "bead" stacks with a known ground-truth FWHM,
samples them at a chosen voxel size, and checks that bead detection and
per-bead Gaussian fitting recover the correct FWHM and bead count.
"""
import unittest

import numpy as np

from src.utils import psf_gui_qt as psf

K = 2.3548200450309493  # FWHM = K * sigma, for a Gaussian


def make_bead_volume(shape, center, sigma_ax_px, sigma_lat_px, amplitude=5000.0, baseline=300.0):
    zz, yy, xx = np.meshgrid(
        np.arange(shape[0]), np.arange(shape[1]), np.arange(shape[2]), indexing="ij"
    )
    r2 = (
        (zz - center[0]) ** 2 / (2 * sigma_ax_px ** 2)
        + (yy - center[1]) ** 2 / (2 * sigma_lat_px ** 2)
        + (xx - center[2]) ** 2 / (2 * sigma_lat_px ** 2)
    )
    return (baseline + amplitude * np.exp(-r2)).astype(np.float32)


class TestBeadDetectionAndFitting(unittest.TestCase):
    """1 x 1 x 2 um (lateral x lateral x axial) FWHM bead, sampled at 0.5 x 0.5 x 1 um voxels."""

    FWHM_LAT_UM = 1.0
    FWHM_AX_UM = 2.0
    PX_LAT_UM = 0.5
    PX_AX_UM = 1.0

    def setUp(self):
        self.sigma_lat_px = (self.FWHM_LAT_UM / K) / self.PX_LAT_UM
        self.sigma_ax_px = (self.FWHM_AX_UM / K) / self.PX_AX_UM
        self.options = {
            "pxPerUmAx": 1.0 / self.PX_AX_UM,
            "pxPerUmLat": 1.0 / self.PX_LAT_UM,
            "windowUm": [6.0, 6.0, 6.0],
            "thresh": 300.0 + 5000.0 * 0.2,
        }

    def test_single_bead_noiseless_fwhm_recovered(self):
        im = make_bead_volume((25, 60, 60), (12, 30, 30), self.sigma_ax_px, self.sigma_lat_px)
        psf_list, beads, maxima, centers, smoothed = psf.compute(im, self.options)

        self.assertEqual(len(centers), 1, "expected exactly one detected bead")
        _, latFit, axFit = psf_list[0]
        self.assertIsNotNone(latFit)
        self.assertIsNotNone(axFit)
        self.assertAlmostEqual(latFit[3], self.FWHM_LAT_UM, delta=0.01)
        self.assertAlmostEqual(axFit[3], self.FWHM_AX_UM, delta=0.01)

    def test_single_bead_with_noise_fwhm_within_tolerance(self):
        im = make_bead_volume((25, 60, 60), (12, 30, 30), self.sigma_ax_px, self.sigma_lat_px)
        rng = np.random.default_rng(0)
        im_noisy = rng.poisson(im).astype(np.float32) + rng.normal(0, 5, size=im.shape)

        psf_list, beads, maxima, centers, smoothed = psf.compute(im_noisy.astype(np.float32), self.options)

        self.assertEqual(len(centers), 1, "expected exactly one detected bead")
        _, latFit, axFit = psf_list[0]
        self.assertIsNotNone(latFit)
        self.assertIsNotNone(axFit)
        # noise adds a few percent of error; keep a generous tolerance
        self.assertAlmostEqual(latFit[3], self.FWHM_LAT_UM, delta=0.05)
        self.assertAlmostEqual(axFit[3], self.FWHM_AX_UM, delta=0.1)

    def test_two_well_separated_beads_both_detected(self):
        shape = (25, 60, 100)
        center_a = (12, 30, 30)
        center_b = (12, 30, 70)  # 20 um apart in X, well beyond the min-distance setting
        im = np.full(shape, 300.0, dtype=np.float64)
        for c in (center_a, center_b):
            im = im + 5000.0 * np.exp(
                -(
                    (np.arange(shape[0])[:, None, None] - c[0]) ** 2 / (2 * self.sigma_ax_px ** 2)
                    + (np.arange(shape[1])[None, :, None] - c[1]) ** 2 / (2 * self.sigma_lat_px ** 2)
                    + (np.arange(shape[2])[None, None, :] - c[2]) ** 2 / (2 * self.sigma_lat_px ** 2)
                )
            )
        psf_list, beads, maxima, centers, smoothed = psf.compute(im.astype(np.float32), self.options)
        self.assertEqual(len(centers), 2, "two well-separated beads should both be detected")


class TestElongatedBeadRegression(unittest.TestCase):
    """Regression test: a bead elongated in Z (e.g. out-of-focus or oversized) used to
    be detected as 0 beads, because peak_local_max found several noisy local maxima
    along its length and keepBeads()'s crowding filter discarded all of them instead
    of keeping the brightest one."""

    def test_close_candidates_collapse_to_brightest(self):
        """keepBeads() must keep only the brightest peak among several mutually-close
        candidates (e.g. multiple noisy local maxima on one elongated bead), instead
        of discarding all of them. Geometry taken from a real bead stack that used
        to be detected as 0 beads: 8 candidates all within ~2 um of each other."""
        shape = (25, 140, 140)
        im = np.full(shape, 300.0, dtype=np.float32)
        close_centers = np.array([
            [12, 65, 70], [5, 64, 71], [12, 57, 69], [5, 57, 69],
            [13, 63, 63], [13, 51, 68], [5, 51, 67], [5, 56, 60],
        ])
        brightest_idx = 4
        for i, c in enumerate(close_centers):
            im[c[0], c[1], c[2]] = 9000.0 if i == brightest_idx else 5000.0

        options = {
            "pxPerUmAx": 1.0,
            "pxPerUmLat": 1.0 / 0.2125,
            "windowUm": [15.0, 15.0, 15.0],
            "thresh": 700,
        }
        window = [15, 71, 71]
        kept = psf.keepBeads(im, window, close_centers, options)

        self.assertEqual(len(kept), 1, "mutually-close candidates must collapse to one")
        np.testing.assert_array_equal(kept[0], close_centers[brightest_idx])

    def test_zero_beads_found_does_not_raise(self):
        """compute() must not raise when no bead clears the intensity threshold."""
        im = np.full((20, 40, 40), 300.0, dtype=np.float32)
        options = {
            "pxPerUmAx": 1.0,
            "pxPerUmLat": 1.0 / 0.5,
            "windowUm": [6.0, 6.0, 6.0],
            "thresh": 10000.0,  # far above the flat background
        }
        psf_list, beads, maxima, centers, smoothed = psf.compute(im, options)
        self.assertEqual(len(centers), 0)
        self.assertEqual(psf_list, [])

    def test_bead_touching_z_edge_is_excluded(self):
        """A bead close enough to the Z-stack boundary that its fitting window
        cannot fit with room to spare must be excluded, rather than analyzed with
        a window that silently touches the edge (whose profile then has no
        guarantee of having decayed back to baseline)."""
        shape = (25, 80, 80)
        z_window = 20  # half-window = 10
        options = {
            "pxPerUmAx": 1.0,
            "pxPerUmLat": 1.0,
            "windowUm": [float(z_window), 15.0, 15.0],
            "thresh": 700,
        }
        window = [z_window, 15, 15]

        # z=10: 10 - window//2(=10) == 0, exactly touching the low edge -> excluded
        im_touching = np.full(shape, 300.0, dtype=np.float32)
        im_touching[10, 40, 40] = 9000.0
        kept_touching = psf.keepBeads(im_touching, window, np.array([[10, 40, 40]]), options)
        self.assertEqual(len(kept_touching), 0, "bead with zero Z margin must be excluded")

        # z=11: one plane of margin to spare -> kept
        im_clear = np.full(shape, 300.0, dtype=np.float32)
        im_clear[11, 40, 40] = 9000.0
        kept_clear = psf.keepBeads(im_clear, window, np.array([[11, 40, 40]]), options)
        self.assertEqual(len(kept_clear), 1, "bead with nonzero Z margin should be kept")

    def test_saturated_bead_is_excluded(self):
        """A bead with a saturated pixel (e.g. the max value of the original
        uint16 file) anywhere in its fitting window must be excluded when
        saturationValue is set, but kept when it isn't (unset/None)."""
        shape = (25, 80, 100)
        options = {
            "pxPerUmAx": 1.0,
            "pxPerUmLat": 1.0,
            "windowUm": [10.0, 10.0, 10.0],
            "thresh": 700,
            "saturationValue": 65535,
        }
        centers = np.array([[12, 40, 30], [12, 40, 70]])

        im = np.full(shape, 300.0, dtype=np.float32)
        im[12, 40, 30] = 5000.0    # clean bead
        im[12, 40, 70] = 65535.0  # saturated bead

        kept = psf.keepBeads(im, [10, 10, 10], centers, options)
        self.assertEqual(len(kept), 1, "saturated bead must be excluded")
        np.testing.assert_array_equal(kept[0], centers[0])

        options_no_filter = dict(options, saturationValue=None)
        kept_unfiltered = psf.keepBeads(im, [10, 10, 10], centers, options_no_filter)
        self.assertEqual(len(kept_unfiltered), 2, "both beads kept when saturationValue is None")


class TestFitBounds(unittest.TestCase):
    """Regression test: curve_fit's Gaussian sigma used to be unbounded, so a bead
    with a weak/noisy profile could occasionally converge on a degenerate, very
    broad "fit" (or a negative sigma), producing a FWHM of hundreds/thousands of
    um in a stack only ~100 um deep. This wildly inflated the std of FWHM across
    beads (not robust to outliers) while the median stayed reasonable."""

    def test_noisy_weak_profiles_never_exceed_bounded_fwhm(self):
        rng = np.random.default_rng(42)
        n = 30  # matches the default 30 um Z fit window at 1 um/px
        x = np.arange(n)
        max_allowed_fwhm = K * n  # curve_fit's sigma is bounded to (0, n)

        checked_any = False
        for _ in range(100):
            amp = rng.uniform(0.1, 0.3)  # weak signal, comparable to noise below
            true_sigma = rng.uniform(2, 4)
            peak = amp * np.exp(-(x - 15) ** 2 / (2 * true_sigma ** 2))
            background = 0.3 + rng.normal(0, 0.05) + rng.normal(0, 1) * 0.003 * x
            noise = rng.normal(0, 0.25, n)
            yRaw = peak + background + noise

            _, _, _, fwhm = psf.fit(yRaw, scale=1.0)
            if fwhm is not None:
                checked_any = True
                self.assertLessEqual(
                    abs(fwhm), max_allowed_fwhm,
                    "FWHM must stay within the fitting window's bounded extent"
                )

        self.assertTrue(checked_any, "expected at least one successful fit in this batch")


if __name__ == "__main__":
    unittest.main()
