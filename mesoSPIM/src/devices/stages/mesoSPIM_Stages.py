from PyQt5 import QtCore

class mesoSPIM_Stage(QtCore.QObject):
    sig_position = QtCore.pyqtSignal(dict)

    def __init__(self, config, parent = None):
        super().__init__()
        self.cfg = config

    def move_relative(self):
        pass

    def move_absolute(self):
        pass

    def read_position(self):
        pass
