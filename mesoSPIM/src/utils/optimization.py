'''
Utilities for fast image-based optimization (auto-focus, etc)
Auto-focus is based on Autopilot paper (Royer at al, Nat Biotechnol. 2016 Dec;34(12):1267-1278. doi: 10.1038/nbt.3708.)
author: Nikita Vladimirov, @nvladimus, 2021
License: GPL-3
'''

from scipy.fftpack import dct
import numpy as np
import scipy.optimize

def _otf_radius(img, psf_radius_px):
    """Maximum number of spatial frequencies in the image"""
    assert len(img.shape) == 2, "Image must be 2D array"
    assert psf_radius_px > 0, "PSF radius must be positive"
    w = min(img.shape)
    psf_radius_px = np.ceil(psf_radius_px)  # clip all PSF radii below 1 px to 1.
    return w / (2 * psf_radius_px)

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

def shannon_dct(img, psf_radius_px=1):
    """Shannon entropy of discreet cosine transform, for 2D images."""
    cutoff = _otf_radius(img, psf_radius_px)
    return _shannon(_dct_2d(img, cutoff), cutoff)

def gaussian_1d(x_arr, xo, sigma, amplitude=1, offset=0):
    """"Return 1D gaussian function as array"""
    g = offset + amplitude * np.exp(- ((x_arr - float(xo)) ** 2) / (2 * sigma ** 2))
    return g.ravel()

def _parabola_1d(x_arr, xcenter, amplitude=1, offset=0):
    """"Return 1D parabola function as array, with minus sign (e.g. reaching max at `xcenter`)"""
    g = offset - amplitude * (x_arr - float(xcenter)) ** 2
    return g.ravel()

def sigma2fwhm(sigma):
    """Convert gaussian std (sigma) to full-width half-maximum (FWHM)"""
    return 2.0 * sigma * np.sqrt(2 * np.log(2))

def _normalize_1d(arr, low_percentile=5.0):
    """Rescale the 1d array amplitude to [0,1] using percentile as a background value"""
    bg = np.percentile(arr, low_percentile)
    arr_normalized = np.clip((arr - bg) / (arr.max() - bg), 0, 1)
    return arr_normalized

def fit_gaussian_1d(f_arr, x_arr):
    """Fit measured values f_arr(x_arr) with a gaussian function.
    The true gaussian peak must lie withing the `x_arr` limits,
    so the measurements must 'clamp' the gaussian from left and right.

    Parameters:
    -----------
    f_arr: 1d-array
        Measured function values.
    x_arr: 1d-array
        Positions where the function was measured.

    Returns:
    --------
    (xcenter, sigma, f_amp, f_offset): tuple
        Parameters of gaussian fit: `f = f_offset + f_amp * np.exp(-((x_arr - xcenter)**2) / (2 * sigma ** 2))`
    """
    assert len(f_arr.shape) == len(x_arr.shape) == 1, f"Arrays must be 1d, got {f_arr.shape}, {x_arr.shape} instead"
    assert len(f_arr) >= 3, f"At least 3 points are needed for gaussian fit, received {len(f_arr)}."
    x_peak = x_arr[np.argmax(f_arr)]  # initial guess for gaussian peak position
    sigma_guess, amp_guess = x_arr.std(), f_arr.max()
    initial_guess = (x_peak, sigma_guess, amp_guess, amp_guess / 10)  # Parameters: xpos, sigma, amp, offset
    try:
        popt, pcov = scipy.optimize.curve_fit(gaussian_1d, (x_arr), f_arr,
                                              p0=initial_guess,
                                              bounds=((x_arr.min(), # min position of the peak
                                                       0.2 * sigma_guess,  # min sigma
                                                       0.5 * amp_guess, 0.001 * amp_guess),  # min amp, min offset
                                                      (x_arr.max(), # max position of the peak
                                                       20 * sigma_guess,  # max sigma
                                                       3 * amp_guess, 0.5 * amp_guess)))  # max amp, offset
    except RuntimeError as e:
        popt = initial_guess
        print(f"{e}")
    xcenter, sigma, f_amp, f_offset = popt
    return xcenter, sigma, f_amp, f_offset

def fit_parabola_1d(f_arr, x_arr):
    """Fit measured values f_arr(x_arr) with a parabola function f=a(x-x0)**2 + b.
    The true peak must lie withing the `x_arr` limits,
    so the measurements must 'clamp' the function from left and right.

    Parameters:
    -----------
    f_arr: 1d-array
        Measured function values.
    x_arr: 1d-array
        Positions where the function was measured.

    Returns:
    --------
    (xcenter, f_amp, f_offset): tuple
        Parameters of parabola fit: `f = f_offset + f_amp(x-xcenter)**2`
    """
    assert len(f_arr.shape) == len(x_arr.shape) == 1, f"Arrays must be 1d, got {f_arr.shape}, {x_arr.shape} instead"
    assert len(f_arr) >= 3, f"At least 3 points are needed for fit, received {len(f_arr)}."
    x_peak = x_arr[np.argmax(f_arr)]  # initial guess for peak position
    amp_guess, offset_guess = f_arr.max()/((x_arr.max() - x_arr.min()) / 2)**2, f_arr.max()
    initial_guess = (x_peak, amp_guess, offset_guess)  # Parameters: xpos, amp, offset
    try:
        popt, pcov = scipy.optimize.curve_fit(_parabola_1d, (x_arr), f_arr,
                                              p0=initial_guess,
                                              bounds=((x_arr.min(), # min position of the peak
                                                       0.001 * amp_guess, 0.001 * offset_guess),  # min amp, min offset
                                                      (x_arr.max(), # max position of the peak
                                                       1000 * amp_guess, 1000 * offset_guess)))  # max amp, offset
    except RuntimeError as e:
        popt = initial_guess
        print(f"{e}")
    xcenter,  f_amp, f_offset = popt
    return xcenter, f_amp, f_offset
