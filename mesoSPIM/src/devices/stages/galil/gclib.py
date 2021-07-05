"""
Python wrapper for Galil gclib.
Contact softwaresupport@galil.com with questions, comments, and suggestions.
"""
###############################################################################
# ctypes import, for pulling in all dll/so/dylib calls. 
# Part of implementation, don't use directly.
###############################################################################
import platform #for distinguishing 'Windows', 'Linux', 'Darwin'
from ctypes import *

if platform.system() == 'Windows':
    if '64 bit' in platform.python_compiler():
        _gclib_path = r'C:\Program Files (x86)\Galil\gclib\dll\x64\gclib.dll'
        _gclibo_path = r'C:\Program Files (x86)\Galil\gclib\dll\x64\gclibo.dll'
        _gclib = WinDLL(_gclib_path)
        _gclibo = WinDLL(_gclibo_path)
    else:
        _gclib_path = r'C:\Program Files (x86)\Galil\gclib\dll\x86\gclib.dll'
        _gclibo_path = r'C:\Program Files (x86)\Galil\gclib\dll\x86\gclibo.dll'
        _gclib = WinDLL(_gclib_path)
        _gclibo = WinDLL(_gclibo_path)
        #Reassign symbol name, Python doesn't like @ in function names
        #gclib calls
        setattr(_gclib, 'GArrayDownload', getattr(_gclib, '_GArrayDownload@20'))
        setattr(_gclib, 'GArrayUpload', getattr(_gclib, '_GArrayUpload@28'))
        setattr(_gclib, 'GClose', getattr(_gclib, '_GClose@4'))
        setattr(_gclib, 'GCommand', getattr(_gclib, '_GCommand@20'))
        setattr(_gclib, 'GFirmwareDownload', getattr(_gclib, '_GFirmwareDownload@8'))
        setattr(_gclib, 'GInterrupt', getattr(_gclib, '_GInterrupt@8'))
        setattr(_gclib, 'GMessage', getattr(_gclib, '_GMessage@12'))
        setattr(_gclib, 'GOpen', getattr(_gclib, '_GOpen@8'))
        setattr(_gclib, 'GProgramDownload', getattr(_gclib, '_GProgramDownload@12'))
        setattr(_gclib, 'GProgramUpload', getattr(_gclib, '_GProgramUpload@12'))
        #gclibo calls (open source component/convenience functions)
        setattr(_gclibo, 'GAddresses', getattr(_gclibo, '_GAddresses@8'))
        setattr(_gclibo, 'GArrayDownloadFile', getattr(_gclibo, '_GArrayDownloadFile@8'))
        setattr(_gclibo, 'GArrayUploadFile', getattr(_gclibo, '_GArrayUploadFile@12'))
        setattr(_gclibo, 'GAssign', getattr(_gclibo, '_GAssign@8'))
        setattr(_gclibo, 'GError', getattr(_gclibo, '_GError@12'))
        setattr(_gclibo, 'GInfo', getattr(_gclibo, '_GInfo@12'))
        setattr(_gclibo, 'GIpRequests', getattr(_gclibo, '_GIpRequests@8'))
        setattr(_gclibo, 'GMotionComplete', getattr(_gclibo, '_GMotionComplete@8'))
        setattr(_gclibo, 'GProgramDownloadFile', getattr(_gclibo, '_GProgramDownloadFile@12'))
        setattr(_gclibo, 'GSleep', getattr(_gclibo, '_GSleep@4'))
        setattr(_gclibo, 'GProgramUploadFile', getattr(_gclibo, '_GProgramUploadFile@8'))
        setattr(_gclibo, 'GTimeout', getattr(_gclibo, '_GTimeout@8'))
        setattr(_gclibo, 'GVersion', getattr(_gclibo, '_GVersion@8'))
        setattr(_gclibo, 'GSetupDownloadFile', getattr(_gclibo, '_GSetupDownloadFile@20'))

elif platform.system() == 'Linux':
    cdll.LoadLibrary("libgclib.so.0")
    _gclib = CDLL("libgclib.so.0")
    cdll.LoadLibrary("libgclibo.so.0")
    _gclibo = CDLL("libgclibo.so.0")

elif platform.system() == 'Darwin': #OSX
    _gclib_path = '/Applications/gclib/dylib/gclib.0.dylib'
    _gclibo_path = '/Applications/gclib/dylib/gclibo.0.dylib'
    cdll.LoadLibrary(_gclib_path)
    _gclib = CDLL(_gclib_path)
    cdll.LoadLibrary(_gclibo_path)
    _gclibo = CDLL(_gclibo_path)
    
    

# Python "typedefs"
_GReturn = c_int #type for a return code
_GCon = c_void_p #type for a Galil connection handle
_GCon_ptr = POINTER(_GCon) #used for argtypes declaration
_GSize = c_ulong #type for a Galil size variable
_GSize_ptr = POINTER(_GSize) #used for argtypes declaration
_GCStringIn = c_char_p #char*. In C it's const.
_GCStringOut = c_char_p #char*
_GOption = c_int #type for option variables, e.g.    GArrayDownload 
_GStatus = c_ubyte #type for interrupt status bytes
_GStatus_ptr = POINTER(_GStatus) #used for argtypes declaration

#Define arguments and result type (if not C int type)
#gclib calls
_gclib.GArrayDownload.argtypes = [_GCon, _GCStringIn, _GOption, _GOption, _GCStringIn]
_gclib.GArrayUpload.argtypes = [_GCon, _GCStringIn, _GOption, _GOption, _GOption, _GCStringOut, _GSize]
_gclib.GClose.argtypes = [_GCon]
_gclib.GCommand.argtypes = [_GCon, _GCStringIn, _GCStringOut, _GSize, _GSize_ptr]
_gclib.GFirmwareDownload.argtypes = [_GCon, _GCStringIn]
_gclib.GInterrupt.argtypes = [_GCon, _GStatus_ptr]
_gclib.GMessage.argtypes = [_GCon, _GCStringOut, _GSize]
_gclib.GOpen.argtypes = [_GCStringIn, _GCon_ptr]
_gclib.GProgramDownload.argtypes = [_GCon, _GCStringIn, _GCStringIn]
_gclib.GProgramUpload.argtypes = [_GCon, _GCStringOut, _GSize]
#gclibo calls (open source component/convenience functions)
_gclibo.GAddresses.argtypes = [_GCStringOut, _GSize]
_gclibo.GArrayDownloadFile.argtypes = [_GCon, _GCStringIn]
_gclibo.GArrayUploadFile.argtypes = [_GCon, _GCStringIn, _GCStringIn]
_gclibo.GAssign.argtypes = [_GCStringIn, _GCStringIn]
_gclibo.GError.argtypes = [_GReturn, _GCStringOut, _GSize]
_gclibo.GError.restype    = None
_gclibo.GError.argtypes = [_GCon, _GCStringOut, _GSize]
_gclibo.GIpRequests.argtypes = [_GCStringOut, _GSize]
_gclibo.GMotionComplete.argtypes = [_GCon, _GCStringIn]
_gclibo.GProgramDownloadFile.argtypes = [_GCon, _GCStringIn, _GCStringIn]
_gclibo.GSleep.argtypes = [c_uint]
_gclibo.GSleep.restype    = None
_gclibo.GProgramUploadFile.argtypes = [_GCon, _GCStringIn]
_gclibo.GTimeout.argtypes = [_GCon, c_int]
_gclibo.GVersion.argtypes = [_GCStringOut, _GSize]
_gclibo.GSetupDownloadFile.argtypes = [_GCon, _GCStringIn, _GOption, _GCStringOut, _GSize]

#Set up some constants
_enc = "ASCII" #byte encoding for going between python strings and c strings.
_buf_size = 500000 #size of response buffer. Big enough to fit entire 4000 program via UL/LS, or 24000 elements of array data.
_error_buf = create_string_buffer(128)    #buffer for retrieving error code descriptions.
    
def _rc(return_code):
    """Checks return codes from gclib and raises a python error if result is exceptional."""
    if return_code != 0:
        _gclibo.GError(return_code, _error_buf, 128) #Get the library's error description
        raise GclibError(str(_error_buf.value.decode(_enc)))
    return 

class GclibError(Exception):
    """Error class for non-zero gclib return codes."""
    pass 
 
class py:
    """Represents a single Python connection to a Galil Controller or PLC."""
    
    def __init__(self):
        """Constructor for the Connection class. Initializes gclib's handle and read buffer."""
        self._gcon = _GCon(0) #handle to connection
        self._buf = create_string_buffer(_buf_size)
        self._timeout = 5000
        return        
    
    def __del__(self):
        """Destructor for the Connection class. Ensures close gets called to release Galil resource (Sockets, Kernel Driver, Com Port, etc)."""
        self.GClose()
        return
    
    def _cc(self):
        """Checks if connection is established, throws error if not."""
        if self._gcon.value == None:
            _rc(-1201) #G_CONNECTION_NOT_ESTABLISHED
    
    def GOpen(self, address):
        """
        Opens a connection a galil controller.
        See the gclib docs for address string formatting.
        See Link GOpen() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_aef4aec8a85630eed029b7a46aea7db54.html#aef4aec8a85630eed029b7a46aea7db54>
        """
        c_address = _GCStringIn(address.encode(_enc))
        _rc(_gclib.GOpen(c_address, byref(self._gcon)))
        return
        
     
    def GClose(self):
        """
        Closes a connection to a Galil Controller. 
        See Link GClose() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_a24a437bcde9637b0db4b94176563a052.html#a24a437bcde9637b0db4b94176563a052>
        """
        if self._gcon.value != None:
            _rc(_gclib.GClose(self._gcon))
            self._gcon = _GCon(0)
        return
        
        
    def GCommand(self, command):
        """
        Performs a command-and-response transaction on the connection. 
        Trims the response.
        See Link GCommand() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_a5ac031e76efc965affdd73a1bec084a8.html#a5ac031e76efc965affdd73a1bec084a8>
        """
        self._cc()
        c_command = _GCStringIn(command.encode(_enc))
        _rc(_gclib.GCommand(self._gcon, c_command, self._buf, _buf_size, None))
        response = str(self._buf.value.decode(_enc))
        return response[:-3].strip() # trim trailing /r/n: and leading space

        
    def GSleep(self, val):
        """
        Provides a blocking sleep call which can be useful for timing-based chores.
        See Link GSleep() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_adf81cb901627dd83408ca1f686e05cac.html#adf81cb901627dd83408ca1f686e05cac>
        """
        _gclibo.GSleep(val)
        return 
        
        
    def GVersion(self):
        """
        Provides the gclib version number. Please include the output of this function on all support cases.
        See Link GVersion() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a1784b39416b77af20efc98a05f8ce475.html#a1784b39416b77af20efc98a05f8ce475>
        """
        _rc(_gclibo.GVersion(self._buf, _buf_size))
        return "py." + str(self._buf.value.decode(_enc))
        
        
    def GInfo(self):
        """
        Provides a useful connection string. Please include the output of this function on all support cases.
        See Link GInfo() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a08abfcff8a1a85a01987859473167518.html#a08abfcff8a1a85a01987859473167518>
        """
        _rc(_gclibo.GInfo(self._gcon, self._buf, _buf_size))
        return str(self._buf.value.decode(_enc))
        
        
    def GIpRequests(self):
        """
        Provides a dictionary of all Galil controllers requesting IP addresses via BOOT-P or DHCP. 
        
        Returns a dictionary mapping 'model-serial' --> 'mac address'
        e.g. {'DMC4000-783': '00:50:4c:20:03:0f', 'DMC4103-9998': '00:50:4c:38:27:0e'}
        
        Linux/OS X users must be root to use GIpRequests() and have UDP access to bind and listen on port 67.
        See Link GIpRequests() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a0afb4c82642a4ef86f997c39a5518952.html#a0afb4c82642a4ef86f997c39a5518952>
        """
        _rc(_gclibo.GIpRequests(self._buf, _buf_size)) #get the c string from gclib
        ip_req_dict = {}
        for line in str(self._buf.value.decode(_enc)).splitlines():
            line = line.replace(' ', '') #trim spaces throughout
            if (line == ""): continue
            fields = line.split(',')
            #fields go [model, serial number, mac]
            ip_req_dict[fields[0] + '-' + fields[1]] = fields[2] # e.g. DMC4000-783 maps to its MAC addr.
        return ip_req_dict
    
    
    def GAssign(self, ip, mac):
        """
        Assigns IP address over the Ethernet to a controller at a given MAC address.
        Linux/OS X users must be root to use GAssign() and have UDP access to send on port 68.
        See Link GAssign() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a80e87e876408dea6e1c5e29da2de143f.html#a80e87e876408dea6e1c5e29da2de143f>
        """
        c_ip = _GCStringIn(ip.encode(_enc))
        c_mac = _GCStringIn(mac.encode(_enc))
        _rc(_gclibo.GAssign(c_ip, c_mac))
        return
        
        
    def GAddresses(self):
        """
        Provides a dictionary of all available connection addresses. 
        
        Returns a dictionary mapping 'address' -> 'revision reports', where possible
        e.g. {}
        
        See Link GAddresses() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8c_ae92a1b09a2f340fc7720ea2074f4526c.html#ae92a1b09a2f340fc7720ea2074f4526c>
        """
        _rc(_gclibo.GAddresses(self._buf, _buf_size))
        addr_dict = {}
        for line in str(self._buf.value.decode(_enc)).splitlines():
            print("LINE ")
            fields = line.split(',')
            if len(fields) >= 2:
                addr_dict[fields[0]] = fields[1]
            else:
                addr_dict[fields[0]] = ''
                
        return addr_dict
 
        
    def GProgramDownload(self, program, preprocessor=""):
        """
        Downloads a program to the controller's program buffer.
        See the gclib docs for preprocessor options.
        See Link GProgramDownload() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_acafe19b2dd0537ff458e3c8afe3acfeb.html#acafe19b2dd0537ff458e3c8afe3acfeb>
        """
        self._cc()
        c_prog = _GCStringIn(program.encode(_enc))
        c_pre = _GCStringIn(preprocessor.encode(_enc))
        _rc(_gclib.GProgramDownload(self._gcon, c_prog, c_pre))
        return
     
    
    def GProgramUpload(self):    
        """
        Uploads a program from the controller's program buffer. 
        See Link GProgramUpload() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_a80a653ce387a2bd16bde2793c6de77e9.html#a80a653ce387a2bd16bde2793c6de77e9>
        """
        self._cc()
        _rc(_gclib.GProgramUpload(self._gcon, self._buf, _buf_size))
        return str(self._buf.value.decode(_enc))
        
        
    def GProgramDownloadFile(self, file_path, preprocessor=""):
        """
        Program download from file. 
        See the gclib docs for preprocessor options.
        See Link GProgramDownloadFile() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a8e44e2e321df9e7b8c538bf2d640633f.html#a8e44e2e321df9e7b8c538bf2d640633f>
        """
        self._cc()
        c_path = _GCStringIn(file_path.encode(_enc))
        c_pre = _GCStringIn(preprocessor.encode(_enc))
        _rc(_gclibo.GProgramDownloadFile(self._gcon, c_path, c_pre))
        return        
        
    def GProgramUploadFile(self, file_path):
        """
        Program upload to file. 
        See Link GProgramUploadFile() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a38c5565afc11762fa19d37fbaa3c9aa3.html#a38c5565afc11762fa19d37fbaa3c9aa3>
        """
        self._cc()
        c_path = _GCStringIn(file_path.encode(_enc))
        _rc(_gclibo.GProgramUploadFile(self._gcon, c_path))
        return
        
    def GArrayDownload(self, name, first, last, array_data):
        """
        Downloads array data to a pre-dimensioned array in the controller's array table. 
        array_data should be a list of values (e.g. int or float)
        See Link GArrayDownload() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_a6ea5ae6d167675e4c27ccfaf2f240f8a.html#a6ea5ae6d167675e4c27ccfaf2f240f8a>
        """
        self._cc()
        c_name = _GCStringIn(name.encode(_enc))
        array_string = ""
        for val in array_data:
            array_string += str(val) + ","
        c_data = _GCStringIn(array_string[:-1].encode(_enc)) #trim trailing command
        _rc(_gclib.GArrayDownload(self._gcon, c_name, first, last, c_data))
        return
        
        
    def GArrayUploadFile(self, file_path, names = []):
        """
        Uploads the entire controller array table or a subset and saves the data as a csv file specified by file_path.
        names is optional and should be a list of array names on the controller.
        See Link GArrayUploadFile() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a2271aa7eff5d1aaf7fc1eb3a472e3f4c.html#a2271aa7eff5d1aaf7fc1eb3a472e3f4c>
        """
        self._cc()
        c_path = _GCStringIn(file_path.encode(_enc))
        names_string = ''
        c_names = _GCStringIn(''.encode(_enc)) #in case empty list provided
        for name in names:
            names_string += name + ' '
        
        c_names = _GCStringIn(names_string[:-1].encode(_enc)) #trim trailing space
        _rc(_gclibo.GArrayUploadFile(self._gcon, c_path, c_names))
        return
            
            
    def GArrayDownloadFile(self, file_path):
        """
        Downloads a csv file containing array data at file_path.
        See Link GArrayDownloadFile() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a14b448ab8c7e6cf495865af301be398e.html#a14b448ab8c7e6cf495865af301be398e>
        """
        self._cc()
        c_path = _GCStringIn(file_path.encode(_enc))
        _rc(_gclibo.GArrayDownloadFile(self._gcon, c_path))
        return        
    
    
    def GArrayUpload(self, name, first, last):
        """
        Uploads array data from the controller's array table. 
        See Link GArrayUpload() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_af215806ec26ba06ed3f174ebeeafa7a7.html#af215806ec26ba06ed3f174ebeeafa7a7>
        """
        self._cc()
        c_name = _GCStringIn(name.encode(_enc))
        _rc(_gclib.GArrayUpload(self._gcon, c_name, first, last, 1, self._buf, _buf_size)) #1 is comma delimiter
        string_list = str(self._buf.value.decode(_enc)).split(',')
        float_list = []
        for s in string_list:
            float_list.append(float(s))
        return float_list
    
    
    def GTimeout(self, timeout):
        """
        Set the library timeout. Set to -1 to use the intitial library timeout, as specified in GOpen.
        See Link GTimeout() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a179aa2d1b8e2227944cc06a7ceaf5640.html#a179aa2d1b8e2227944cc06a7ceaf5640>
        """
        self._cc()
        _rc(_gclibo.GTimeout(self._gcon, timeout))
        self._timeout = timeout
        return
        
    
    @property
    def timeout(self):
        """
        Convenience property read access to timeout value. If -1, gclib uses the initial library timeout, as specified in GOpen.
        See Link GTimeout() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a179aa2d1b8e2227944cc06a7ceaf5640.html#a179aa2d1b8e2227944cc06a7ceaf5640>
        """
        return self._timeout
        
    @timeout.setter
    def timeout(self, timeout):
        """
        Convenience property write access to timeout value. Set to -1 to use the initial library timeout, as specified in GOpen.
        See Link GTimeout() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a179aa2d1b8e2227944cc06a7ceaf5640.html#a179aa2d1b8e2227944cc06a7ceaf5640>
        """
        self.GTimeout(timeout)
        return

        
    def GFirmwareDownload(self, file_path):
        """
        Upgrade firmware. 
        See Link GFirmwareDownload() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_a1878a2285ff17897fa4fb20182ba6fdf.html#a1878a2285ff17897fa4fb20182ba6fdf>
        """
        self._cc()
        c_path = _GCStringIn(file_path.encode(_enc))
        _rc(_gclib.GFirmwareDownload(self._gcon, c_path))
        return


    def GMessage(self):
        """
        Provides access to unsolicited messages from the controller. 
        See Link GMessage() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclib_8h_aabc5eaa09ddeca55ab8ee048b916cbcd.html#aabc5eaa09ddeca55ab8ee048b916cbcd>
        """
        self._cc()
        _rc(_gclib.GMessage(self._gcon, self._buf, _buf_size))
        return str(self._buf.value.decode(_enc))
     
     
    def GMotionComplete(self, axes):
        """
        Blocking call that returns once all axes specified have completed their motion. 
        See Link GMotionComplete() <http://www.galil.com/sw/pub/all/doc/gclib/html/gclibo_8h_a19c220879442987970706444197f397a.html#a19c220879442987970706444197f397a>
        """
        self._cc()
        c_axes = _GCStringIn(axes.encode(_enc))
        _rc(_gclibo.GMotionComplete(self._gcon, c_axes))
        return

    def GInterrupt(self):
        """   
        Provides access to PCI and UDP interrupts from the controller.
        See Link GInterrupt() <http://galil.com/sw/pub/all/doc/gclib/html/gclib_8h_a5bcf802404a96343e7593d247b67f132.html#a5bcf802404a96343e7593d247b67f132>
        """
        self._cc()
        status = _GStatus(0)
        _rc(_gclib.GInterrupt(self._gcon, byref(status)))
        return status.value
    
    def GSetupDownloadFile(self, file_path, options):
        """
    Downloads specified sectors from a Galil compressed backup (gcb) file to a controller.
    
    Returns a dictionary with the controller information stored in the gcb file.
    If options is specified as 0, an additional "options" key will be in the dictionary indicating the info sectors available in the gcb
    """
        self._cc()
        c_path = _GCStringIn(file_path.encode(_enc))

        rc = _gclibo.GSetupDownloadFile(self._gcon, c_path, options, self._buf, _buf_size)
        if (options != 0):
            _rc(rc)

        info_dict = {}
        for line in str(self._buf.value.decode(_enc)).split("\"\n"):
            fields = line.split(',',1)

            if (fields[0] == ""): continue
            elif len(fields) >= 2:
                info_dict[fields[0].strip("\"\'")] = fields[1].strip("\"\'")
            else:
                info_dict[fields[0].strip("\"\'")] = ''

        if (options == 0):
            info_dict["options"] = rc

        return info_dict