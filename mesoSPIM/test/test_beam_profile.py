"""Beam profile analysis recovers a synthetic Gaussian beam; saturation and stack reading.
Run from mesoSPIM/: python -m pytest test/test_beam_profile.py -q"""
import numpy as np
from tifffile import imwrite

from src.utils.beam_profile_gui_qt import analyse_beam, measured_range, read_image, saturation


def synthetic_beam(w0=3.0, theta=0.04, H=200, W=2000, noise=0.5, tilt_deg=0.0):
    x = np.arange(W)[None, :] - W / 2
    y = np.arange(H)[:, None] - H / 2
    t = np.radians(tilt_deg)
    u, v = x * np.cos(t) + y * np.sin(t), -x * np.sin(t) + y * np.cos(t)   # along / across the beam
    w = w0 * np.sqrt(1 + (u * theta / w0) ** 2)
    img = 3000 * np.sqrt(2 / np.pi) / w * np.exp(-2 * v ** 2 / w ** 2)   # power conserved along the beam
    return 100 + img + np.random.default_rng(0).normal(0, noise, img.shape)


def test_recovers_beam():
    res = analyse_beam(synthetic_beam(), px_um=0.5, n=1.5)
    assert abs(res["theta_rad"] - 0.04) < 0.002
    assert abs(res["na_eff"] - 1.5 * np.sin(0.04)) < 0.004
    assert abs(res["waist_fwhm_um"] - 1.1774 * 3 * 0.5) < 0.1     # 1.77 um
    assert abs(res["two_zR_um"] - 75) < 0.1 * 75                  # 2zR = 150 px = 75 um
    assert res["power_cv"] < 0.05 and res["waist_in_image"] and res["length_in_image"]
    assert abs(res["meas_length_um"] - res["two_zR_um"]) < 0.1 * 75 and not res["meas_length_at_edge"]


def test_saturation():
    img = np.full((50, 50), 300, np.uint16)
    assert not saturation(img)[0]
    img[20:22, 10:20] = 4095                                         # 12-bit full scale plateau
    assert saturation(img)[0]
    img[0, 0] = 65535
    assert saturation(img)[0]


def test_read_stack(tmp_path):
    stack = np.stack([np.full((30, 40), v, np.uint16) for v in range(20)])
    stack[3, 5, 5] = 65535
    path = tmp_path / "stack.tif"
    imwrite(path, stack)
    mean, mx, n, px = read_image(path)
    assert mean.shape == (30, 40) and n == 10 and abs(mean.mean() - 9.5) < 1e-9   # central 10 frames: 5..14
    assert mx.max() == 14 and px is None                                            # frame 3 not read


def test_measured_range_asymmetric():
    xs = np.arange(0, 100, 10.)
    fw = np.array([20, 16, 12, 8, 4, 5, 6, 7, 8, 9.])     # min 4 at x=40, threshold 4*sqrt2 = 5.657
    x0, x1, edge = measured_range(xs, fw, 4)
    assert abs(x0 - (30 + 10 * (8 - 5.657) / 4)) < 0.01   # crossing between 8 (x=30) and 4 (x=40)
    assert abs(x1 - (50 + 10 * (5.657 - 5) / 1)) < 0.01   # crossing between 5 (x=50) and 6 (x=60)
    assert not edge
    assert measured_range(xs, np.full(10, 4.), 0) == (0., 90., True)


def test_speck_rejected():
    img = synthetic_beam()
    img[100:106, 101:109] += 5000            # dust / hot pixel on the wide part of the beam (FWHM ~ 4x waist there)
    res = analyse_beam(img, px_um=0.5, n=1.5)
    assert len(res["outlier_x_um"]) >= 1
    assert abs(res["min_x_um"] - 500) < 30                            # min at the true waist (x = 1000 px)
    assert abs(res["min_fwhm_um"] - 1.1774 * 3 * 0.5) < 0.2
    assert abs(res["meas_length_um"] - 75) < 0.15 * 75


def test_tilted_beam():
    # 15 deg: uncorrected, theta would read 1/cos^2 = 7% high and lengths 3.5% short
    res = analyse_beam(synthetic_beam(w0=6.0, H=800, tilt_deg=15), px_um=0.5, n=1.5)
    assert abs(res["tilt_deg"] - 15) < 0.2
    assert abs(res["theta_rad"] - 0.04) < 0.001
    assert abs(res["waist_fwhm_um"] - 1.1774 * 6 * 0.5) < 0.06 * 3.53   # some smear: beam shifts 2.7 px per bin
    assert abs(res["two_zR_um"] - 150) < 0.1 * 150                         # 2zR = 2 w0/theta = 300 px = 150 um
