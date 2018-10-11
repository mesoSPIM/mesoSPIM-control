'''
Contains Filename Wizard Class: autogenerates Filenames

'''

from PyQt5 import QtWidgets, QtGui, QtCore

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty

# from .config import config as cfg
# from .acquisition_builder import TilingAcquisitionListBuilder

from ..mesoSPIM_State import mesoSPIM_StateSingleton

class FilenameWizard(QtWidgets.QWizard):
    '''
    Wizard to run

    The parent is the Window class of the microscope
    '''
    wizard_done = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        ''' By an instance variable, callbacks to window signals can be handed
        through '''
        self.parent = parent
        self.state = mesoSPIM_StateSingleton()

        self.setWindowTitle('Filename Wizard')

        self.addPage(FilenameWizardWelcomePage(self))
        self.addPage(FilenameWizardCheckResultsPage(self))
        
        self.show()

    def done(self, r):
        ''' Reimplementation of the done function

        if r == 0: canceled
        if r == 1: finished properly
        '''
        if r == 0:
            print("Wizard was canceled")
        if r == 1:
            print('Wizard was closed properly')
            print('Laser selected: ', self.field('Laser'))
            print('Filter selected: ', self.field('Filter'))
            print('Zoom selected: ', self.field('Zoom'))
            print('Shutter selected: ', self.field('Shutterconfig'))
            self.update_filenames_in_model()
        else:
            print('Wizard provided return code: ', r)

        super().done(r)

    def replace_spaces_with_underscores(self, string):
        return string.replace(' ','_')

    def replace_dots_with_underscores(self, string):
        return string.replace('.','_')

    def generate_filename_list(self):
        '''
        Go through the model, entry for entry and populate the filenames
        '''
        row_count = self.parent.model.rowCount()
        filename_column = self.parent.model.getFilenameColumn()

        print('Row count: ', row_count)
        print('Filename column: ', filename_column)

        num_string = '000000'
        if self.field('StartNumber'):
            start_number = self.field('StartNumberValue')
        else: 
            start_number = 0

        start_number_string = str(start_number)

        self.filename_list = []

        for row in range(0, row_count):
            filename = ''
            if self.field('Laser'):
                laserstring = self.parent.model.getLaser(row)
                filename += self.replace_spaces_with_underscores(laserstring)
                filename += '_'
            
            if self.field('Filter'):
                filterstring = self.parent.model.getFilter(row)
                filename += self.replace_spaces_with_underscores(filterstring)
                filename += '_'
            
            if self.field('Zoom'):
                zoomstring = self.parent.model.getZoom(row)
                filename += self.replace_dots_with_underscores(zoomstring)
                filename += '_'

            if self.field('Shutterconfig'):
                shutterstring = self.parent.model.getShutterconfig(row)
                filename += shutterstring
                filename += '_'

            file_suffix = num_string[:-len(start_number_string)]+start_number_string + '.raw'

            start_number += 1
            start_number_string = str(start_number)
            
            filename += file_suffix
            
            self.filename_list.append(filename)
            
    def update_filenames_in_model(self):
        row_count = self.parent.model.rowCount()
        filename_column = self.parent.model.getFilenameColumn()

        for row in range(0, row_count):
            filename =  self.filename_list[row]
            index = self.parent.model.createIndex(row, filename_column)
            self.parent.model.setData(index, filename)

class FilenameWizardWelcomePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Autogenerate filenames")
        self.setSubTitle("Which properties would you like to use?")

        self.LaserCheckBox = QtWidgets.QCheckBox('Laser', self)
        self.FilterCheckBox = QtWidgets.QCheckBox('Filter', self)
        self.ZoomCheckBox = QtWidgets.QCheckBox('Zoom', self)
        self.ShutterCheckBox = QtWidgets.QCheckBox('Shutterconfig', self)
        self.StartNumberCheckBox = QtWidgets.QCheckBox('Start Number: ', self)

        self.StartNumberSpinBox = QtWidgets.QSpinBox(self)
        self.StartNumberSpinBox.setEnabled(False)
        self.StartNumberSpinBox.setValue(0)
        self.StartNumberSpinBox.setSingleStep(1)
        self.StartNumberSpinBox.setMinimum(0)
        self.StartNumberSpinBox.setMaximum(999999)

        self.StartNumberCheckBox.toggled.connect(lambda boolean: self.StartNumberSpinBox.setEnabled(boolean))

        self.registerField('Laser',self.LaserCheckBox)
        self.registerField('Filter', self.FilterCheckBox)
        self.registerField('Zoom', self.ZoomCheckBox)
        self.registerField('Shutterconfig', self.ShutterCheckBox)
        self.registerField('StartNumber', self.StartNumberCheckBox)
        self.registerField('StartNumberValue', self.StartNumberSpinBox)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.LaserCheckBox, 0, 0)
        self.layout.addWidget(self.FilterCheckBox, 1, 0)
        self.layout.addWidget(self.ZoomCheckBox, 2, 0)
        self.layout.addWidget(self.ShutterCheckBox, 3, 0)
        self.layout.addWidget(self.StartNumberCheckBox, 4, 0)
        self.layout.addWidget(self.StartNumberSpinBox, 4, 1)
        self.setLayout(self.layout)

    def validatePage(self):
        self.parent.generate_filename_list()
        return super().validatePage()

class FilenameWizardCheckResultsPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle('Check results')
        self.setSubTitle('Please check if the following filenames are ok:')

        self.TextEdit = QtWidgets.QPlainTextEdit(self)
        self.TextEdit.setReadOnly(True)

        self.mystring = ''        
        self.TextEdit.setPlainText(self.mystring)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.TextEdit, 0, 0, 1, 1)
        self.setLayout(self.layout)

    def initializePage(self):
        for i in self.parent.filename_list:
            self.mystring += str(i)
            self.mystring += '\n'
        self.TextEdit.setPlainText(self.mystring)        

    def cleanupPage(self):
        self.mystring = ''
