'''
Code modified from https://github.com/AndreEbel/PyZWOEFW
Modifications by @nvladimus
Note that methods here are CamelCase for legacy reasons, unlike the rest of mesoSPIM API.
License: GPL-3
'''
import ctypes as c
import sys
from ctypes.util import find_library
from time import sleep
# Returned error codes, as defined in EFW_filter.h:
# typedef enum _EFW_ERROR_CODE{
#     EFW_SUCCESS = 0,
#     EFW_ERROR_INVALID_INDEX,   // 1
#     EFW_ERROR_INVALID_ID,      // 2
#     EFW_ERROR_INVALID_VALUE,   // 3
#     EFW_ERROR_REMOVED,         // 4, failed to find the wheel, maybe it has been removed
#     EFW_ERROR_MOVING,          // 5, filter wheel is moving
#     EFW_ERROR_ERROR_STATE,     // 6, filter wheel is in error state
#     EFW_ERROR_GENERAL_ERROR,   // 7, other error
#     EFW_ERROR_NOT_SUPPORTED,   // 8
#     EFW_ERROR_CLOSED,          // 9, device not opened
#     EFW_ERROR_END = -1
# }EFW_ERROR_CODE;
EFW_SUCCESS = 0
EFW_ERROR_INVALID_INDEX = 1
EFW_ERROR_INVALID_ID = 2
EFW_ERROR_INVALID_VALUE = 3
EFW_ERROR_REMOVED = 4
EFW_ERROR_MOVING = 5
EFW_ERROR_ERROR_STATE = 6
EFW_ERROR_GENERAL_ERROR = 7
EFW_ERROR_NOT_SUPPORTED = 8
EFW_ERROR_CLOSED = 9
EFW_ERROR_END = -1

class EFW_Error(Exception):
    """
    Exception class for errors returned from the :mod:`zwoasi` module.
    """
    def __init__(self, message):
        Exception.__init__(self, message)


class EFW_IOError(EFW_Error):
    """
    Exception class for all errors returned from the EFW SDK library.
    """
    def __init__(self, message, error_code=None):
        EFW_Error.__init__(self, message)
        self.error_code = error_code

# Mapping of error numbers to exceptions. Zero is used for success
efw_error_messages = {
    EFW_ERROR_INVALID_INDEX: 'Invalid index',
    EFW_ERROR_INVALID_ID: 'Invalid ID',
    EFW_ERROR_INVALID_VALUE: 'Invalid value',
    EFW_ERROR_REMOVED: 'EFW removed',
    EFW_ERROR_MOVING: 'Moving',
    EFW_ERROR_ERROR_STATE: 'EFW in error state',
    EFW_ERROR_GENERAL_ERROR: 'General error',
    EFW_ERROR_NOT_SUPPORTED: 'Not supported',
    EFW_ERROR_CLOSED: 'EFW closed (device not opened)',
    EFW_ERROR_END: 'End',
    }


def _check(r, verbose=False):
    """Raise EFW_IOError if the SDK return code `r` signals an error."""
    if r == EFW_SUCCESS:
        return
    if verbose:
        print(r)
    raise EFW_IOError(efw_error_messages.get(r, f'Unknown EFW error code {r}'), r)


# Filter wheel information
class _EFW_INFO(c.Structure):
    _fields_ = [
        ('ID', c.c_short),
        ('Name', c.c_char * 64),
        ('slotNum', c.c_int)
        ]
    
    def get_dict(self):
        r = {}
        for k, _ in self._fields_:
            v = getattr(self, k)
            if sys.version_info[0] >= 3 and isinstance(v, bytes):
                v = v.decode()
            r[k] = v
        return r


def init(library_file): 
    if not library_file:
        library_file = find_library('EFW_filter')
        if not library_file:
            raise EFW_Error('EFW SDK library not found')

    efwlib = c.cdll.LoadLibrary(library_file)

    efwlib.EFWGetNum.argtypes = []
    efwlib.EFWGetNum.restype = c.c_int

    efwlib.EFWGetID.argtypes = [c.c_int, c.POINTER(c.c_short)]
    efwlib.EFWGetID.restype = c.c_int

    efwlib.EFWGetProperty.argtypes = [c.c_short, c.POINTER(_EFW_INFO)]
    efwlib.EFWGetProperty.restype = c.c_int

    efwlib.EFWOpen.argtypes = [c.c_short]
    efwlib.EFWOpen.restype = c.c_int

    efwlib.EFWGetPosition.argtypes = [c.c_short, c.POINTER(c.c_int)]
    efwlib.EFWGetPosition.restype = c.c_int

    efwlib.EFWSetPosition.argtypes = [c.c_short, c.c_int]
    efwlib.EFWSetPosition.restype = c.c_int

    efwlib.EFWSetDirection.argtypes = [c.c_short, c.c_bool]
    efwlib.EFWSetDirection.restype = c.c_int

    efwlib.EFWGetDirection.argtypes = [c.c_short, c.c_bool]
    efwlib.EFWGetDirection.restype = c.c_int

    efwlib.EFWClose.argtypes = [c.c_short]
    efwlib.EFWClose.restype = c.c_int

    efwlib.EFWGetProductIDs.argtypes = [c.POINTER(c.c_int)]
    efwlib.EFWGetProductIDs.restype = c.c_int

    efwlib.EFWCalibrate.argtypes = [c.c_short]
    efwlib.EFWCalibrate.restype = c.c_int

    return efwlib


class EFW(object):
    def __init__(self, library_file=None, verbose=True): #ok
        self.verbose = verbose
        self.dll = init(library_file)
        # Per-instance state: these must not be shared between EFW objects,
        # otherwise a second instance inherits stale IDs and slot counts.
        self.IDs = []
        self.slotNums = {}
        self.FiltersNames = {}
        self.FiltersSlots = {}
        self.calibrated = {}

        self.Num = self.GetNum() #get number of wheels
        self.IDs = [self.GetID(n) for n in range(self.Num)] #get ids of wheels
        #open wheels and get slots number
        for ID in self.IDs:
            self.Open(ID)
            self.slotNums[ID] = (self.GetProperty(ID)['slotNum'])
            self.calibrated[ID] = False
            self.SetPosition(ID, 0)
            #self.SetDirection(ID, True)

    def GetNum(self): #ok
        return self.dll.EFWGetNum()

    def GetID(self, num): #ok
        ID = c.c_short()
        _check(self.dll.EFWGetID(num, ID), self.verbose)
        return ID.value

    def Open(self, ID): #ok
        _check(self.dll.EFWOpen(ID), self.verbose)

    def GetProperty(self, ID): #works once wheel is open
        props = _EFW_INFO()
        _check(self.dll.EFWGetProperty(ID, props), self.verbose)
        return props.get_dict()

    def GetPosition(self, ID): #ok
        slot = c.c_int()
        _check(self.dll.EFWGetPosition(ID, slot), self.verbose)
        return slot.value

    def SetPosition(self, ID, slot, wait_until_done=True):
        _check(self.dll.EFWSetPosition(ID, slot), self.verbose)
        if wait_until_done:
            inPosition = False
            while not inPosition:
                sleep(0.25)
                pos = self.GetPosition(ID)#.value
                if pos == slot:
                    inPosition = True
    
    def SetDirection(self, ID, direction): #ok
        _check(self.dll.EFWSetDirection(ID, direction), self.verbose)

    def Calibrate(self, ID): #ok
        #return to slot 0
        self.SetPosition(ID, 0)
        pos_ref = self.GetPosition(ID)
        _check(self.dll.EFWCalibrate(ID), self.verbose)
        # wait until calibration is over
        sleep(25)
        self.calibrated[ID] = True

    def Close(self, ID):
        """Park the wheel at slot 0 and release the device handle.

        Closing is idempotent: the SDK is global, so a wheel may already have
        been closed by another handle on the same device. Parking is
        best-effort, and an already-closed device is not an error.
        """
        try:
            self.SetPosition(ID, 0)
        except EFW_IOError as e:
            if e.error_code == EFW_ERROR_CLOSED:
                return  # already closed by someone else, nothing to release
            if self.verbose:
                print(f'EFW {ID}: could not park at slot 0 before closing: {e}')
        r = self.dll.EFWClose(ID)
        if r != EFW_ERROR_CLOSED:
            _check(r, self.verbose)

    def SetFiltersNames(self, ID, FiltersNames): 
        if len(FiltersNames) == self.slotNums[ID]:
            self.FiltersNames[ID] = FiltersNames
            self.FiltersSlots[ID] = {v: k for k, v in self.FiltersNames[ID].items()}


