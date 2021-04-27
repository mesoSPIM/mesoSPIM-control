'''
Contains Nonlinear Filename Wizard Class: autogenerates Filenames
'''

from PyQt5 import QtWidgets, QtGui, QtCore

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty

from ..mesoSPIM_State import mesoSPIM_StateSingleton

import logging
logger = logging.getLogger(__name__)

class FilenameWizard(QtWidgets.QWizard):
    '''
    Wizard to run

    The parent is the Window class of the microscope
    '''
    wizard_done = QtCore.pyqtSignal()

    num_of_pages = 4
    (welcome, raw, single_hdf5, finished) = range(num_of_pages)

    def __init__(self, parent=None):
        super().__init__(parent)

        ''' By an instance variable, callbacks to window signals can be handed
        through '''
        self.parent = parent
        self.state = mesoSPIM_StateSingleton()

        self.setWindowTitle('Filename Wizard')

        self.setPage(0, FilenameWizardWelcomePage(self))
        self.setPage(1, FilenameWizardRawSelectionPage(self))
        self.setPage(2, FilenameWizardSingleHDF5SelectionPage(self))
        self.setPage(3, FilenameWizardCheckResultsPage(self))
        
        self.show()

    def done(self, r):
        ''' Reimplementation of the done function

        if r == 0: canceled
        if r == 1: finished properly
        '''
        if r == 0:
            logger.info('Filename Wizard was canceled')
        if r == 1:
            logger.info('Filename Wizard was closed properly')
            self.update_filenames_in_model()
        else:
            logger.info('Filename Wizard provided return code: ', r)

        super().done(r)

    def replace_spaces_with_underscores(self, string):
        return string.replace(' ','_')

    def replace_dots_with_underscores(self, string):
        return string.replace('.','_')

    def generate_filename_list(self, suffix, increment_number=True):
        '''
        Go through the model, entry for entry and populate the filenames
        '''
        row_count = self.parent.model.rowCount()
        filename_column = self.parent.model.getFilenameColumn()

        num_string = '000000'
        
        start_number = 0

        start_number_string = str(start_number)

        self.filename_list = []

        for row in range(0, row_count):
            filename = ''

            if self.field('DescriptionRaw'):
                descriptionstring = self.field('DescriptionRaw')
                filename += self.replace_spaces_with_underscores(descriptionstring)
                filename += '_'

            if self.field('DescriptionHDF5'):
                descriptionstring = self.field('DescriptionHDF5')
                filename += self.replace_spaces_with_underscores(descriptionstring)
                filename += '_'

            if self.field('xyPosition'):
                '''Round to nearest integer '''
                x_position_string = str(int(round(self.parent.model.getXPosition(row))))
                y_position_string = str(int(round(self.parent.model.getYPosition(row))))

                filename += 'X' + x_position_string + '_' + 'Y' + y_position_string + '_'

            if self.field('rotationPosition'):
                rot_position_string = str(int(round(self.parent.model.getRotationPosition(row))))
                filename += 'rot_' + rot_position_string + '_'

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

            file_suffix = num_string[:-len(start_number_string)]+start_number_string + '.' + suffix

            if increment_number:
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
        self.setSubTitle("How would you like to save your data?")

        self.raw_string = 'Individual Raw Files: ~.raw'
        self.single_hdf5_string = 'Single HDF5-File: ~.h5'

        self.SaveAsComboBoxLabel = QtWidgets.QLabel('Save as:')
        self.SaveAsComboBox = QtWidgets.QComboBox()
        self.SaveAsComboBox.addItems([self.raw_string, self.single_hdf5_string])
        self.SaveAsComboBox.setCurrentIndex(0)

        self.registerField('SaveAs', self.SaveAsComboBox, 'currentIndex')
        
        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.SaveAsComboBoxLabel, 0, 0)
        self.layout.addWidget(self.SaveAsComboBox, 0, 1)
        self.setLayout(self.layout)
    
    def nextId(self):
        if self.SaveAsComboBox.currentText() == self.raw_string: # is .raw
            return self.parent.raw 
        elif self.SaveAsComboBox.currentText() == self.single_hdf5_string: # is .h5 
            return self.parent.single_hdf5

class FilenameWizardRawSelectionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Autogenerate raw filenames")
        self.setSubTitle("Which properties would you like to use?")

        self.DescriptionCheckBox = QtWidgets.QCheckBox('Description: ',self)
        self.DescriptionLineEdit = QtWidgets.QLineEdit(self) 

        self.DescriptionCheckBox.toggled.connect(lambda boolean: self.DescriptionLineEdit.setEnabled(boolean))

        self.xyPositionCheckBox = QtWidgets.QCheckBox('XY Position')
        self.RotationPositionCheckBox = QtWidgets.QCheckBox('Rotation angle')

        self.LaserCheckBox = QtWidgets.QCheckBox('Laser', self)
        self.FilterCheckBox = QtWidgets.QCheckBox('Filter', self)
        self.ZoomCheckBox = QtWidgets.QCheckBox('Zoom', self)
        self.ShutterCheckBox = QtWidgets.QCheckBox('Shutterconfig', self)

        self.registerField('DescriptionRaw', self.DescriptionLineEdit)
        self.registerField('xyPosition', self.xyPositionCheckBox)
        self.registerField('rotationPosition', self.RotationPositionCheckBox)
        self.registerField('Laser',self.LaserCheckBox)
        self.registerField('Filter', self.FilterCheckBox)
        self.registerField('Zoom', self.ZoomCheckBox)
        self.registerField('Shutterconfig', self.ShutterCheckBox)
        
        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.DescriptionCheckBox, 0, 0)
        self.layout.addWidget(self.DescriptionLineEdit, 0, 1)
        self.layout.addWidget(self.xyPositionCheckBox, 1, 0)
        self.layout.addWidget(self.RotationPositionCheckBox, 2, 0)
        self.layout.addWidget(self.LaserCheckBox, 3, 0)
        self.layout.addWidget(self.FilterCheckBox, 4, 0)
        self.layout.addWidget(self.ZoomCheckBox, 5, 0)
        self.layout.addWidget(self.ShutterCheckBox, 6, 0)
        self.setLayout(self.layout)

    def validatePage(self):
        self.parent.generate_filename_list('raw')
        return super().validatePage()

    def nextId(self):
        return self.parent.finished

class FilenameWizardSingleHDF5SelectionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Autogenerate hdf5 filename")
        self.setSubTitle("This replaces all filenames with a single hdf5 file. \n Which properties would you like to use?")

        self.DescriptionCheckBox = QtWidgets.QCheckBox('Description: ',self)
        self.DescriptionLineEdit = QtWidgets.QLineEdit(self) 
        self.DescriptionCheckBox.toggled.connect(lambda boolean: self.DescriptionLineEdit.setEnabled(boolean))

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.DescriptionCheckBox, 0, 0)
        self.layout.addWidget(self.DescriptionLineEdit, 0, 1)
        self.setLayout(self.layout)

        self.registerField('DescriptionHDF5', self.DescriptionLineEdit)

    def validatePage(self):
        self.parent.generate_filename_list('h5', increment_number=False)
        return super().validatePage()

    def nextId(self):
        return self.parent.finished

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

