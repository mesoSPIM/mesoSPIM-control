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
# Returned error code
# _EFW_ERROR_CODE = {EFW_SUCCESS = 0,
#                     EFW_ERROR_INVALID_INDEX,
#                     EFW_ERROR_INVALID_ID,
#                     EFW_ERROR_INVALID_VALUE,
#                     EFW_ERROR_CLOSED, #not opened
#                     EFW_ERROR_REMOVED, #failed to find the filter wheel, maybe the filter wheel has been removed
#                     EFW_ERROR_MOVING,#filter wheel is moving
#                     EFW_ERROR_GENERAL_ERROR,#other error
#                     EFW_ERROR_CLOSED,
#                     EFW_ERROR_END = -1
#                     }

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
efw_errors = [None,
              EFW_IOError('Invalid index', 1),
              EFW_IOError('Invalid ID', 2),
              EFW_IOError('Invalid value', 3),
              EFW_IOError('EFW closed', 4),
              EFW_IOError('EFW removed', 5),
              EFW_IOError('Moving', 6),
              EFW_IOError('General error', 7),
              EFW_IOError('Closed', 8),
              EFW_IOError('End', 9)
              ]


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
    IDs = []
    slotNums = {}
    FiltersNames = {}
    FiltersSlots = {}
    calibrated = False

    def __init__(self, library_file=None, verbose=True): #ok
        self.verbose = verbose
        self.dll = init(library_file)

        self.Num = self.GetNum() #get number of wheels
        self.IDs = [self.GetID(n) for n in range(self.Num)] #get ids of wheels
        #open wheels and get slots number
        for ID in self.IDs: 
            self.Open(ID)
            self.slotNums[ID] = (self.GetProperty(ID)['slotNum'])
            self.SetPosition(ID, 0)
            #self.SetDirection(ID, True)

    def GetNum(self): #ok
        return self.dll.EFWGetNum()

    def GetID(self, num): #ok
        ID = c.c_short()
        r = self.dll.EFWGetID(num, ID)
        if r:
            if self.verbose: 
                print(r)
            raise efw_errors[r]
        return ID.value

    def Open(self, ID): #ok
        r = self.dll.EFWOpen(ID)
        if r:
            if self.verbose: 
                print(r)
            raise efw_errors[r]
    
    def GetProperty(self, ID): #works once wheel is open
        props = _EFW_INFO()
        r = self.dll.EFWGetProperty(ID, props)
        if r:
            if self.verbose: 
                print(r)
            raise efw_errors[r]
        return props.get_dict()

    def GetPosition(self, ID): #ok
        slot = c.c_int()
        r = self.dll.EFWGetPosition(ID, slot)
        if r:
            if self.verbose: 
                print(r)
            raise efw_errors[r]
        return slot.value

    def SetPosition(self, ID, slot, wait_until_done=True):
        r = self.dll.EFWSetPosition(ID, slot)
        if r:
            if self.verbose:
                print(r)
            raise efw_errors[r]
        if wait_until_done:
            inPosition = False
            while not inPosition:
                sleep(0.25)
                pos = self.GetPosition(ID)#.value
                if pos == slot:
                    inPosition = True
    
    def SetDirection(self, ID, direction): #ok
        r = self.dll.EFWSetDirection(ID, direction)
        if r:
            if self.verbose: 
                print(r)
            raise efw_errors[r]
   
    def Calibrate(self, ID): #ok
        #return to slot 0 
        self.SetPosition(ID, 0)
        pos_ref = self.GetPosition(ID)
        r = self.dll.EFWCalibrate(ID)
        if r:
            if self.verbose: 
                print(r)
            raise efw_errors[r]
        # wait until calibration is over
        sleep(25)

    def Close(self, ID): #ok// not always ok 
        #return to slot 0 
        self.SetPosition(ID, 0)
        self.GetPosition(ID)
        r = self.dll.EFWClose(ID)
        if r:
            if self.verbose: 
                print(r)
            raise efw_errors[r]
    
    def SetFiltersNames(self, ID, FiltersNames): 
        if len(FiltersNames) == self.slotNums[ID]:
            self.FiltersNames[ID] = FiltersNames
            self.FiltersSlots[ID] = {v: k for k, v in self.FiltersNames[ID].items()}


