"""
mesoSPIM Module for creating waveforms and analog output signals

Author: Fabian Voigt

#TODO
* Usage of amplitude is not consistent (peak-to-peak in single_pulse)
"""

#import nidaqmx
# from nidaqmx.constants import AcquisitionType, TaskMode
# from nidaqmx.constants import LineGrouping

from scipy import signal
import numpy as np

def single_pulse(
    samplerate=100000,  # in samples/second
    sweeptime=0.4,      # in seconds
    delay=10,           # in percent
    pulsewidth=1,       # in percent
    amplitude=0,        # in volts
    offset=0            # in volts
    ):

    '''
    Returns a numpy array with a single pulse

    Used for creating TTL pulses out of analog outputs and laser intensity
    pulses.

    Units:
    samplerate: Integer
    sweeptime:  Seconds
    delay:      Percent
    pulsewidth: Percent
    amplitude:  Volts
    offset:     Volts

    Examples:

    typical_TTL_pulse = single_pulse(samplerate, sweeptime, 10, 1, 5, 0)
    typical_laser_pulse = single_pulse(samplerate, sweeptime, 10, 80, 1.25, 0)
    '''

    # get an integer number of samples
    samples = int(np.floor(np.multiply(samplerate, sweeptime)))
    # create an array just containing the offset voltage:
    array = np.zeros((samples))+offset

    # convert pulsewidth and delay in % into number of samples
    pulsedelaysamples = int(samples * delay / 100)
    pulsesamples = int(samples * pulsewidth / 100)

    # modify the array
    array[pulsedelaysamples:pulsesamples+pulsedelaysamples] = amplitude
    return np.array(array)

def tunable_lens_ramp(
    samplerate = 100000,    # in samples/second
    sweeptime = 0.4,        # in seconds
    delay = 7.5,            # in percent
    rise = 85,              # in percent
    fall = 2.5,             # in percent
    amplitude = 0,          # in volts
    offset = 0              # in volts
    ):

    '''
    Returns a numpy array with a ETL ramp

    The waveform starts at offset and stays there for the delay period, then
    rises linearly to 2x amplitude (amplitude here refers to 1/2 peak-to-peak)
    and drops back down to the offset voltage during the fall period.

    Switching from a left to right ETL ramp is possible by exchanging the
    rise and fall periods.

    Units of parameters
    samplerate: Integer
    sweeptime:  Seconds
    delay:      Percent
    rise:       Percent
    fall:       Percent
    amplitude:  Volts
    offset:     Volts
    '''
    # get an integer number of samples
    samples = int(np.floor(np.multiply(samplerate, sweeptime)))
    # create an array just containing the negative amplitude voltage:
    array = np.zeros((samples))-amplitude + offset

    # convert rise, fall, and delay in % into number of samples
    delaysamples = int(samples * delay / 100)
    risesamples = int(samples * rise / 100)
    fallsamples = int(samples * fall / 100)

    risearray = np.arange(0,risesamples)
    risearray = amplitude * (2 * np.divide(risearray, risesamples) - 1) + offset

    fallarray = np.arange(0,fallsamples)
    fallarray = amplitude * (1-2*np.divide(fallarray, fallsamples)) + offset

    # rise phase
    array[delaysamples:delaysamples+risesamples] = risearray
    # fall phase
    array[delaysamples+risesamples:delaysamples+risesamples+fallsamples] = fallarray

    return np.array(array)

def sawtooth(
    samplerate = 100000,    # in samples/second
    sweeptime = 0.4,        # in seconds
    frequency = 10,         # in Hz
    amplitude = 0,          # in V
    offset = 0,             # in V
    dutycycle = 50,          # dutycycle in percent
    phase = np.pi/2,          # in rad
    ):
    '''
    Returns a numpy array with a sawtooth function

    Used for creating the galvo signal.

    Example:
    galvosignal =  sawtooth(100000, 0.4, 199, 3.67, 0, 50, np.pi)
    '''

    samples =  int(samplerate*sweeptime)
    dutycycle = dutycycle/100       # the signal.sawtooth width parameter has to be between 0 and 1
    t = np.linspace(0, sweeptime, samples)
    # Using the signal toolbox from scipy for the sawtooth:
    waveform = signal.sawtooth(2 * np.pi * frequency * t + phase, width=dutycycle)
    # Scale the waveform to a certain amplitude and apply an offset:
    waveform = amplitude * waveform + offset

    return waveform

def square(
    samplerate = 100000,    # in samples/second
    sweeptime = 0.4,        # in seconds
    frequency = 10,         # in Hz
    amplitude = 0,          # in V
    offset = 0,             # in V
    dutycycle = 50,         # dutycycle in percent
    phase = np.pi,          # in rad
    ):
    """
    Returns a numpy array with a rectangular waveform
    """

    samples =  int(samplerate*sweeptime)
    dutycycle = dutycycle/100       # the signal.square duty parameter has to be between 0 and 1
    t = np.linspace(0, sweeptime, samples)

    # Using the signal toolbox from scipy for the sawtooth:
    waveform = signal.square(2 * np.pi * frequency * t + phase, duty=dutycycle)
    # Scale the waveform to a certain amplitude and apply an offset:
    waveform = amplitude * waveform + offset

    return waveform
