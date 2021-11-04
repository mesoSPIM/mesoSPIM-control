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
    wizard_done = QtCore.pyqtSignal()

    num_of_pages = 5
    (welcome, raw, tiff, single_hdf5, finished) = range(num_of_pages)

    def __init__(self, parent=None):
        '''Parent is object of class mesoSPIM_AcquisitionManagerWindow()'''
        super().__init__(parent)

        ''' By an instance variable, callbacks to window signals can be handed
        through '''
        self.parent = parent
        self.state = mesoSPIM_StateSingleton()
        self.file_format = None  # 'raw', 'h5', or 'tiff'
        self.setWindowTitle('Filename Wizard')
        self.setPage(0, FilenameWizardWelcomePage(self))
        self.setPage(1, FilenameWizardRawSelectionPage(self))
        self.setPage(2, FilenameWizardTiffSelectionPage(self))
        self.setPage(3, FilenameWizardSingleHDF5SelectionPage(self))
        self.setPage(4, FilenameWizardCheckResultsPage(self))
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

    def generate_filename_list(self, increment_number=True):
        '''
        Go through the model, entry for entry and populate the filenames
        '''
        row_count = self.parent.model.rowCount()
        num_string = '000000'
        start_number = 0
        start_number_string = str(start_number)
        self.filename_list = []
        for row in range(0, row_count):
            filename = ''
            if self.file_format == 'raw':
                if self.field('DescriptionRaw'):
                    filename += self.replace_spaces_with_underscores(self.field('DescriptionRaw')) + '_'

                if self.field('xyPosition'):
                    '''Round to nearest integer '''
                    x_position_string = str(int(round(self.parent.model.getXPosition(row))))
                    y_position_string = str(int(round(self.parent.model.getYPosition(row))))
                    filename += 'X' + x_position_string + '_' + 'Y' + y_position_string + '_'

                if self.field('rotationPosition'):
                    rot_position_string = str(int(round(self.parent.model.getRotationPosition(row))))
                    filename += 'rot_' + rot_position_string + '_'

                if self.field('Laser'):
                    filename += self.replace_spaces_with_underscores(self.parent.model.getLaser(row)) + '_'

                if self.field('Filter'):
                    filename += self.replace_spaces_with_underscores(self.parent.model.getFilter(row)) + '_'

                if self.field('Zoom'):
                    filename += self.replace_dots_with_underscores(self.parent.model.getZoom(row)) + '_'

                if self.field('Shutterconfig'):
                    filename += self.parent.model.getShutterconfig(row) + '_'

                file_suffix = num_string[:-len(start_number_string)] + start_number_string + '.' + self.file_format

                if increment_number:
                    start_number += 1
                    start_number_string = str(start_number)

            elif self.file_format == 'tiff':
                if self.field('DescriptionTIFF'):
                    filename += self.replace_spaces_with_underscores(self.field('DescriptionTIFF')) + '_'

                if self.parent.model.getNShutterConfigs() > 1:
                    shutter_id = 0 if self.parent.model.getShutterconfig(row) == 'Left' else 1
                else:
                    shutter_id = 0
                filename += f'Tile{self.parent.model.getTileIndex(row)}_Ch{self.parent.model.getLaser(row)[:-3]}_Sh{shutter_id}'

                file_suffix = '.' + self.file_format

            elif self.file_format == 'h5':
                if self.field('DescriptionHDF5'):
                    filename += self.replace_spaces_with_underscores(self.field('DescriptionHDF5')) + '_'
                file_suffix = 'bdv.' + self.file_format

            else:
                raise ValueError(f"file suffix invalid: {self.file_format}")

            filename += file_suffix
            self.filename_list.append(filename)
            
    def update_filenames_in_model(self):
        row_count = self.parent.model.rowCount()
        filename_column = self.parent.model.getFilenameColumn()
        for row in range(0, row_count):
            filename = self.filename_list[row]
            index = self.parent.model.createIndex(row, filename_column)
            self.parent.model.setData(index, filename)


class FilenameWizardWelcomePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Autogenerate filenames")
        self.setSubTitle("How would you like to save your data?")

        self.raw_string = 'Individual Raw Files: ~.raw'
        self.tiff_string = 'ImageJ TIFF files: ~.tiff'
        self.single_hdf5_string = 'BigDataViewer HDF5 file: ~.h5'

        self.SaveAsComboBoxLabel = QtWidgets.QLabel('Save as:')
        self.SaveAsComboBox = QtWidgets.QComboBox()
        self.SaveAsComboBox.addItems([self.raw_string, self.tiff_string, self.single_hdf5_string])
        self.SaveAsComboBox.setCurrentIndex(2)

        self.registerField('SaveAs', self.SaveAsComboBox, 'currentIndex')
        
        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.SaveAsComboBoxLabel, 0, 0)
        self.layout.addWidget(self.SaveAsComboBox, 0, 1)
        self.setLayout(self.layout)
    
    def nextId(self):
        if self.SaveAsComboBox.currentText() == self.raw_string:
            self.parent.file_format = 'raw'
            return self.parent.raw
        elif self.SaveAsComboBox.currentText() == self.tiff_string:
            self.parent.file_format = 'tiff'
            return self.parent.tiff
        elif self.SaveAsComboBox.currentText() == self.single_hdf5_string:
            self.parent.file_format = 'h5'
            return self.parent.single_hdf5


class FilenameWizardTiffSelectionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setTitle("Autogenerate TIFF filenames")
        self.setSubTitle("Names will be compatible with BigStitcher auto-loader format:\n {Description}_Tile{}_Ch{}_Sh{}.tiff")

        self.DescriptionCheckBox = QtWidgets.QCheckBox('Description: ', self)
        self.DescriptionCheckBox.setChecked(True)
        self.DescriptionLineEdit = QtWidgets.QLineEdit(self)
        self.DescriptionCheckBox.toggled.connect(lambda boolean: self.DescriptionLineEdit.setEnabled(boolean))

        self.registerField('DescriptionTIFF', self.DescriptionLineEdit)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.DescriptionCheckBox, 0, 0)
        self.layout.addWidget(self.DescriptionLineEdit, 0, 1)
        self.setLayout(self.layout)

    def validatePage(self):
        self.parent.generate_filename_list()
        return super().validatePage()

    def nextId(self):
        return self.parent.finished


class FilenameWizardRawSelectionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Autogenerate RAW filenames")
        self.setSubTitle("Which properties would you like to use?")

        self.DescriptionCheckBox = QtWidgets.QCheckBox('Description: ', self)
        self.DescriptionCheckBox.setChecked(True)
        self.DescriptionLineEdit = QtWidgets.QLineEdit(self)
        self.DescriptionCheckBox.toggled.connect(lambda boolean: self.DescriptionLineEdit.setEnabled(boolean))

        self.xyPositionCheckBox = QtWidgets.QCheckBox('XY Position')
        self.RotationPositionCheckBox = QtWidgets.QCheckBox('Rotation angle')

        self.LaserCheckBox = QtWidgets.QCheckBox('Laser', self)
        self.LaserCheckBox.setChecked(True)
        self.FilterCheckBox = QtWidgets.QCheckBox('Filter', self)
        # self.FilterCheckBox.setChecked(True)
        self.ZoomCheckBox = QtWidgets.QCheckBox('Zoom', self)
        self.ZoomCheckBox.setChecked(True)
        self.ShutterCheckBox = QtWidgets.QCheckBox('Shutterconfig', self)
        self.ShutterCheckBox.setChecked(True)

        self.registerField('DescriptionRaw', self.DescriptionLineEdit)
        self.registerField('xyPosition', self.xyPositionCheckBox)
        self.registerField('rotationPosition', self.RotationPositionCheckBox)
        self.registerField('Laser', self.LaserCheckBox)
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
        self.parent.generate_filename_list()
        return super().validatePage()

    def nextId(self):
        return self.parent.finished


class FilenameWizardSingleHDF5SelectionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Autogenerate hdf5 filename")
        self.setSubTitle("This puts all raw data into a single hdf5 file, accompanied by two metadata files.")

        self.DescriptionCheckBox = QtWidgets.QCheckBox('Description: ', self)
        self.DescriptionCheckBox.setChecked(True)
        self.DescriptionLineEdit = QtWidgets.QLineEdit(self) 
        self.DescriptionCheckBox.toggled.connect(lambda boolean: self.DescriptionLineEdit.setEnabled(boolean))

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.DescriptionCheckBox, 0, 0)
        self.layout.addWidget(self.DescriptionLineEdit, 0, 1)
        self.setLayout(self.layout)
        self.registerField('DescriptionHDF5', self.DescriptionLineEdit)

    def validatePage(self):
        self.parent.generate_filename_list(increment_number=False)
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
        if self.parent.file_format in ('raw', 'tiff'):
            file_list = self.parent.filename_list
        elif self.parent.file_format == 'h5':
            file_list = [self.parent.filename_list[0]]
        else:
            raise ValueError(f"file_format must be in ('raw', 'tiff', 'h5'), received {self.parent.file_format}")

        for f in file_list:
            self.mystring += f
            self.mystring += '\n'
        self.TextEdit.setPlainText(self.mystring)        

    def cleanupPage(self):
        self.mystring = ''

