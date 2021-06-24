# Utilitues for image-based optimization (ETL, auto-focus, etc)
# by @nvladimus

from scipy.fftpack import dct
import numpy as np

def _otf_radius(img, psf_radius_px):
    """Maximum number of spatial frequencies in the image"""
    assert len(img.shape) == 2, "Image must be 2D array"
    assert psf_radius_px > 0, "PSF radius must be positive"
    w = min(img.shape)
    psf_radius_px = np.ceil(psf_radius_px)  # clip all PSF radii below 1 px to 1.
    return w/psf_radius_px

def _normL2(x):
    """L2 norm of n-dimensional array"""
    return np.sqrt(np.sum(x.flatten() ** 2))

def _abslog2(x):
    x_abs = abs(x)
    res = np.zeros(x_abs.shape)
    res[x_abs > 0] = np.log2(x_abs[x_abs > 0].astype(np.float64))
    return res

def _shannon(spectrum_2d, otf_radius=100):
    """Normalized shannon entropy of an image spectrum, bound by OTF support radius."""
    h, w = spectrum_2d.shape
    y, x = np.ogrid[:h, :w]
    support = (x + y < otf_radius)
    norm = _normL2(spectrum_2d[support])
    if norm != 0:
        terms = spectrum_2d[support].flatten() / norm
        entropy = -2 / otf_radius**2 * np.sum(abs(terms) * _abslog2(terms))
    else:
        entropy = 0
    return entropy

def _dct_2d(img, cutoff=100):
    cutoff = int(cutoff)
    assert len(img.shape) == 2, 'dct_2d(img): image must be 2D'
    return dct(dct(img.astype(np.float64).T, norm='ortho', n=cutoff).T, norm='ortho', n=cutoff)

def shannon_DCT(img, psf_radius_px=1):
    """Shannon entropy of discreet cosine transform, for 2D images."""
    cutoff = _otf_radius(img, psf_radius_px)
    return _shannon(_dct_2d(img, cutoff), cutoff)

