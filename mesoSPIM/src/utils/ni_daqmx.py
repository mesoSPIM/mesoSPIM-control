'''
ni_daqmx.py
========================================

Optional-import shim for NI-DAQmx. Modules that talk to NI cards import the
package through here, so a missing installation does not break startup: the NI
classes raise a readable error when instantiated, and Demo mode is unaffected.

The package and the driver install separately. `pip install nidaqmx` gives only
the Python wrapper, so both are checked.
'''

import logging

logger = logging.getLogger(__name__)

try:
    import nidaqmx
    import nidaqmx.system  # the driver check below needs this submodule, do not rely on Task pulling it in
    from nidaqmx.constants import AcquisitionType, LineGrouping, TaskMode
    NIDAQMX_AVAILABLE = True
except ImportError as error:
    nidaqmx = None
    AcquisitionType = LineGrouping = TaskMode = None
    NIDAQMX_AVAILABLE = False
    logger.info(f"The 'nidaqmx' package is not available ({error}). "
                f"NI hardware cannot be used, demo mode is unaffected.")

'''The driver cannot appear while the application is running, so a successful check is cached.'''
_driver_checked = False


def require_nidaqmx(device):
    """Raise if a config file asks for NI hardware that this machine cannot drive.

    Checks the `nidaqmx` package and the NI-DAQmx driver it wraps, which are
    installed separately and can each be missing on their own.

    Args:
        device (str): what the caller was setting up, used in the error message.

    Raises:
        ImportError: if the package is not installed, or if it is installed but
            the NI-DAQmx driver it needs is not present.
    """
    if not NIDAQMX_AVAILABLE:
        raise ImportError(f"{device} requires the 'nidaqmx' package, which is not installed. "
                          f"Install it with 'pip install nidaqmx' together with the NI-DAQmx driver, "
                          f"or select the 'Demo' options in the configuration file.")
    _require_driver(device)


def _require_driver(device):
    """Raise if the `nidaqmx` package is installed but the NI-DAQmx driver is not.

    Reading the driver version is the cheapest call that makes `nidaqmx` load the
    DAQmx library, which it otherwise defers until the first task is created.
    """
    global _driver_checked
    if _driver_checked:
        return
    try:
        version = nidaqmx.system.System.local().driver_version
    except Exception as error:
        '''nidaqmx raises DaqNotFoundError for this on Windows, but the failure mode of
        loading the library differs between platforms and package versions, so anything
        that goes wrong here is reported as the missing driver it almost certainly is.'''
        raise ImportError(f"{device} requires the NI-DAQmx driver, which could not be loaded ({error}). "
                          f"The 'nidaqmx' package is installed, but it is only a wrapper: install the "
                          f"NI-DAQmx driver from National Instruments as well, or select the 'Demo' "
                          f"options in the configuration file.") from error
    _driver_checked = True
    logger.info(f"NI-DAQmx driver version {version.major_version}.{version.minor_version}."
                f"{version.update_version} found.")
