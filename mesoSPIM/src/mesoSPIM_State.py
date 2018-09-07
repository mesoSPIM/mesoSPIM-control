'''
mesoSPIM State class
'''
from PyQt5 import QtCore

class mesoSPIM_StateModel(QtCore.QObject):
    '''This class contains the microscope state

    Any access to this global state should only be done via signals sent by 
    the responsible class for actually causing that state change in hardware.

    '''
    sig_state_model_updated = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__()

        self.cfg = parent.cfg
        self.state = self.cfg.startup

    @QtCore.pyqtSlot(dict)
    def set_state(self, dict):
        for key, value in dict.items():
            if key in self.state.keys():
                self.state[key]=value
                self.sig_state_model_updated.emit()
            else:
                raise NameError('StateModel: Key not found: ')


    def get_state_parameter(self, key):
        if key in self.state.keys():
            return self.state[key]
        else:
            print('Key ', key, ' not in state dict')
