'''
mesoSPIM State class
'''
from PyQt5 import QtCore

class mesoSPIM_State(QtCore.QObject):
    '''This class contains the microscope state

    Here, we convert from a dictionary to a normal object

    Any access to this global state should be locked via mutexes

    TODO: Turn this into a singleton at some point, for now: Instantiate only once.
    '''
    def __init__(self, cfg):
        super().__init__()

        self.state = cfg.startup

    def set_state_parameter(self, key, value):
        self[key] = value

    def get_state_parameter(self, key):

        if key in self.state:
            return self[key]
        else:
            print('Key ', key, ' not in state dict')
