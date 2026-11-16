"""Beam profile analysis recovers a synthetic Gaussian beam; saturation and stack reading.
Run from mesoSPIM/: python -m pytest test/test_beam_profile.py -q"""
import numpy as np
from tifffile import imwrite

from src.utils.beam_profile_gui_qt import analyse_beam, read_image, saturation


def synthetic_beam(w0=3.0, theta=0.04, H=200, W=2000, noise=0.5):
    x = np.arange(W)[None, :]
    y = np.arange(H)[:, None] - H / 2
    w = w0 * np.sqrt(1 + ((x - W / 2) * theta / w0) ** 2)
    img = 3000 * np.sqrt(2 / np.pi) / w * np.exp(-2 * y ** 2 / w ** 2)   # power conserved along x
    return 100 + img + np.random.default_rng(0).normal(0, noise, img.shape)


def test_recovers_beam():
    res = analyse_beam(synthetic_beam(), px_um=0.5, n=1.5)
    assert abs(res["theta_rad"] - 0.04) < 0.002
    assert abs(res["na_eff"] - 1.5 * np.sin(0.04)) < 0.004
    assert abs(res["waist_fwhm_um"] - 1.1774 * 3 * 0.5) < 0.1     # 1.77 um
    assert abs(res["two_zR_um"] - 75) < 0.1 * 75                  # 2zR = 150 px = 75 um
    assert res["power_cv"] < 0.05 and res["waist_in_image"] and res["length_in_image"]


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
