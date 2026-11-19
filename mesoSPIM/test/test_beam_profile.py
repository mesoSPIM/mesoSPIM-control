"""Beam profile analysis recovers a synthetic Gaussian beam; saturation and stack reading.
Run from mesoSPIM/: python -m pytest test/test_beam_profile.py -q"""
import numpy as np
from tifffile import imwrite

from src.utils.beam_profile_gui_qt import (analyse_beam, analyse_shape, measured_range, profile_widths,
                                           read_image, saturation, shape_report, GAUSS_SHAPE)


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


def sa_beam(sa=+1, k=150.0, alpha=0.05, H=400, W=2000, blur=3.0):
    """Ray model of a focused beam travelling towards -x (enters from the right), with spherical aberration:
    the ray through pupil height rho crosses the axis at x0 + sa * k * rho^2 (sa=+1: edge rays focus upstream)."""
    from scipy.ndimage import gaussian_filter1d
    rho = np.linspace(-1, 1, 6001)
    wgt = np.exp(-2 * rho ** 2 / 0.8 ** 2)
    xc = W / 2 + sa * k * rho ** 2
    img = np.zeros((H, W))
    for x in range(W):
        h = rho * alpha * (x - xc) + H / 2
        img[:, x] = np.histogram(h, bins=H, range=(0, H), weights=wgt)[0]
    return 100 + 1000 * gaussian_filter1d(img, blur, axis=0) / wgt.sum() * 50


def test_shape_gaussian_no_sa():
    img = synthetic_beam()
    res = analyse_beam(img, px_um=0.5, n=1.5)
    sh = analyse_shape(img, res, "right")
    ratios = [r[s]["ratio"] for r in sh["rows"] for s in ("up", "down") if r[s]]
    assert len(ratios) >= 4 and all(abs(q - GAUSS_SHAPE) < 0.05 for q in ratios)
    assert sh["sa_sign"] == 0


def test_shape_sa_sign():
    for sa in (+1, -1):
        img = sa_beam(sa)
        res = analyse_beam(img, px_um=1.0, n=1.5)
        sh = analyse_shape(img, res, "right")
        assert sh["sa_sign"] == sa, (sa, sh["asym"])
        assert analyse_shape(img, res, "left")["sa_sign"] == -sa      # direction flips the sign
        assert "POSITIVE" in "\n".join(shape_report(sh)) if sa > 0 else "NEGATIVE" in "\n".join(shape_report(sh))
    flat = analyse_shape(sa_beam(+1, k=0.0), analyse_beam(sa_beam(+1, k=0.0), 1.0), "right")
    assert flat["sa_sign"] == 0, flat["asym"]


def test_profile_widths():
    y = np.arange(201) - 100.
    fw, w13, c = profile_widths(np.exp(-2 * (y - 7) ** 2 / 20 ** 2))  # 1/e^2 radius 20: widths 23.5, 40; centre 107
    assert abs(fw - 23.55) < 0.3 and abs(w13 - 40) < 0.4 and abs(c - 107) < 0.1
    assert profile_widths(np.ones(50)) is None                       # never drops: level not reached


def test_two_sided_fit():
    img = synthetic_beam()                                  # no SA: both sides same NA, cones meet
    res = analyse_beam(img, px_um=0.5, n=1.5)
    sh = analyse_shape(img, res, "right")
    assert abs(sh["side_up"]["na"] - res["na_eff"]) < 0.003 and abs(sh["side_down"]["na"] - res["na_eff"]) < 0.003
    assert abs(sh["spread_um"]) < 5
    for sa in (+1, -1):                                     # SA of either sign: spread > 0 (a size, not a sign)
        img = sa_beam(sa)
        res = analyse_beam(img, px_um=1.0)
        assert analyse_shape(img, res, "right")["spread_um"] > 15
        assert analyse_shape(img, res, "left")["spread_um"] > 15
    assert "Focus spread" in "\n".join(shape_report(sh))
