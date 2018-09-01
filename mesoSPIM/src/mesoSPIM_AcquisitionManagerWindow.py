'''
mesoSPIM Acquisition Manager Window

'''
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi

class mesoSPIM_AcquisitionManagerWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent

        loadUi('gui/mesoSPIM_AcquisitionManagerWindow.ui', self)
        self.setWindowTitle('mesoSPIM Acquisition Manager')
