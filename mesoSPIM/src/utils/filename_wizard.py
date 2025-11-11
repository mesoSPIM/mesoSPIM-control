'''
Contains Nonlinear Filename Wizard Class: autogenerates Filenames
'''

from PyQt5 import QtCore, QtWidgets

from .utility_functions import replace_with_underscores
#from ..mesoSPIM_State import mesoSPIM_StateSingleton
from ..plugins.utils import get_image_writer_plugins, get_image_writer_from_name
from pprint import pprint as print

import logging
logger = logging.getLogger(__name__)


class FilenameWizard(QtWidgets.QWizard):
    wizard_done = QtCore.pyqtSignal()

    Writers = get_image_writer_plugins()

    num_of_pages = 2 + len(Writers)

    def __init__(self, parent=None):
        '''Parent is object of class mesoSPIM_AcquisitionManagerWindow()'''
        super().__init__(parent)

        ''' By an instance variable, callbacks to window signals can be handed
        through '''
        self.parent = parent
        self.cfg = self.parent.cfg
        self.state = self.parent.state # the mesoSPIM_StateSingleton() instance
        self.selected_writer = None

        # Set Writer ID #s for use in UI Wizard
        # Enable option to have a favorite writer at the top of the list
        first_writer = None
        if hasattr(self.cfg,'plugins'):
            first_writer = self.cfg.plugins.get('first_image_writer', None) # Get name of writer from config
            first_writer = get_image_writer_from_name(first_writer) # Get writer details
        if first_writer:
            self.Writers = [x for x in self.Writers if x['name'] != first_writer['name']]
            self.Writers = [first_writer] + self.Writers
        for id, writer in enumerate(self.Writers):
            writer['id'] = id+1

        self.setWindowTitle('Filename Wizard')
        self.setPage(0, FilenameWizardWelcomePage(self))
        for writer in self.Writers:
            self.setPage(writer.get('id'), self.build_selection_page(self, writer))
        self.setPage(self.num_of_pages-1, FilenameWizardCheckResultsPage(self))
        self.setStyleSheet(''' font-size: 16px; ''')
        self.show()

    def build_selection_page(self, parent, writer):
        class SelectionPage(AbstractSelectionPage):
            def __init__(self, parent=None, writer=None):
                super().__init__(parent)
                self.parent = parent
                self.setTitle(writer.get('file_names').WindowTitle)
                self.setSubTitle(
                    writer.get('file_names').WindowSubTitle
                )
                self.registerField(writer.get('file_names').WindowDescription, self.DescriptionLineEdit)
        return SelectionPage(parent, writer)

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
            logger.info(f'Filename Wizard provided return code: {r}')

        super().done(r)

    def generate_filename_list(self, increment_number=True):
        '''
        Go through the model, entry for entry and populate the filenames
        Use attributes from self.selected_writer to control naming
        mesoSPIM/src/plugins/ImageWriterApi.py:FileNaming

        Each writer is formated by:
        mesoSPIM/src/plugins/utils.py:get_writer_plugins()
        '''
        if self.selected_writer.get('file_names').SingleFileFormat:
            row_count = 1
        else:
            row_count = self.parent.model.rowCount()
        num_string = '000000'
        start_number = 0
        start_number_string = str(start_number)
        self.filename_list = []
        for row in range(0, row_count):
            filename = ''

            # Add custom description
            WindowDescription = self.selected_writer.get('file_names').WindowDescription
            if self.field(WindowDescription):
                filename += replace_with_underscores(self.field(WindowDescription)) + '_'

            # Add Magnification
            if self.selected_writer.get('file_names').IncludeMag:
                filename += f'Mag{self.parent.model.getZoom(row)}_'

            # Add Tile
            if self.selected_writer.get('file_names').IncludeTile:
                filename += f'Tile{self.parent.model.getTileIndex(row)}_'

            # Add Channel(s)
            if self.selected_writer.get('file_names').IncludeChannel:
                if self.selected_writer.get('file_names').SingleFileFormat \
                        and self.selected_writer.get('file_names').IncludeAllChannelsInSingleFileFormat:
                    laser_list = self.parent.model.getLaserList()
                    for laser in laser_list:
                        filename += 'Ch' + laser[:-3] + '_'
                else:
                    filename += f'Ch{self.parent.model.getLaser(row)[:-3]}_'

            # Add Shutter
            if self.selected_writer.get('file_names').IncludeShutter:
                if self.parent.model.getNShutterConfigs() > 1:
                    shutter_id = 0 if self.parent.model.getShutterconfig(row) == 'Left' else 1
                else:
                    shutter_id = 0
                filename += f'Sh{shutter_id}_'

            # Add Rotation/Angle
            if self.selected_writer.get('file_names').IncludeRotation:
                if self.parent.model.getNAngles() > 1:
                    angle = int(self.parent.model.getRotationPosition(row))
                else:
                    angle = 0
                filename += f'Rot{angle}_'

            # Add Suffix
            if self.selected_writer.get('file_names').IncludeSuffix:
                filename += f'{self.selected_writer.get('file_names').IncludeSuffix}'

            # Trim trailing _
            if filename.endswith('_'):
                filename = filename[:-1]

            # Add File Extension
            extension = self.selected_writer['file_extensions'][0]
            if extension.startswith('.'):
                extension = extension[1:]
            filename += '.' + extension

            self.filename_list.append(filename)

        if self.selected_writer.get('file_names').SingleFileFormat:
            self.filename_list *= self.parent.model.rowCount()

            # if self.file_format == 'raw':
            #     if self.field('DescriptionRaw'):
            #         filename += replace_with_underscores(self.field('DescriptionRaw')) + '_'
            #
            #     if self.field('xyPosition'):
            #         '''Round to nearest integer '''
            #         x_position_string = str(int(round(self.parent.model.getXPosition(row))))
            #         y_position_string = str(int(round(self.parent.model.getYPosition(row))))
            #         filename += 'X' + x_position_string + '_' + 'Y' + y_position_string + '_'
            #
            #     if self.field('rotationPosition'):
            #         rot_position_string = str(int(round(self.parent.model.getRotationPosition(row))))
            #         filename += 'rot_' + rot_position_string + '_'
            #
            #     if self.field('Laser'):
            #         filename += replace_with_underscores(self.parent.model.getLaser(row)) + '_'
            #
            #     if self.field('Filter'):
            #         filename += replace_with_underscores(self.parent.model.getFilter(row)) + '_'
            #
            #     # if self.field('Zoom'):
            #     #     filename += replace_with_underscores(self.parent.model.getZoom(row)) + '_'
            #
            #     if self.field('Shutterconfig'):
            #         filename += self.parent.model.getShutterconfig(row) + '_'
            #
            #     file_suffix = num_string[:-len(start_number_string)] + start_number_string + '.' + self.file_format
            #
            #     if increment_number:
            #         start_number += 1
            #         start_number_string = str(start_number)
            #
            # elif self.file_format in {'tiff', 'btf'}:
            #     if self.field('DescriptionTIFF'):
            #         filename += replace_with_underscores(self.field('DescriptionTIFF')) + '_'
            #
            #     if self.field('DescriptionBigTIFF'):
            #         filename += replace_with_underscores(self.field('DescriptionBigTIFF')) + '_'
            #
            #     if self.parent.model.getNShutterConfigs() > 1:
            #         shutter_id = 0 if self.parent.model.getShutterconfig(row) == 'Left' else 1
            #     else:
            #         shutter_id = 0
            #
            #     if self.parent.model.getNAngles() > 1:
            #         angle = int(self.parent.model.getRotationPosition(row))
            #     else:
            #         angle = 0
            #
            #     filename += f'Mag{self.parent.model.getZoom(row)}_Tile{self.parent.model.getTileIndex(row)}_Ch{self.parent.model.getLaser(row)[:-3]}_Sh{shutter_id}_Rot{angle}'
            #
            #     file_suffix = '.' + self.file_format
            #
            # elif self.file_format == 'h5':
            #     if self.field('DescriptionHDF5'):
            #         filename += replace_with_underscores(self.field('DescriptionHDF5')) + '_'
            #     filename += f'Mag{self.parent.model.getZoom(0)}'
            #     laser_list = self.parent.model.getLaserList()
            #     for laser in laser_list:
            #         filename += '_ch' + laser[:-3]
            #     file_suffix = '_bdv.' + self.file_format
            #
            # else:
            #     raise ValueError(f"file suffix invalid: {self.file_format}")
            #
            # filename += file_suffix
            # self.filename_list.append(filename)
            
    def update_filenames_in_model(self):
        '''Updates both filenames and selected ImageWriterPlugin'''
        row_count = self.parent.model.rowCount()
        filename_column = self.parent.model.getFilenameColumn()
        image_writer_plugin_column = self.parent.model.getImageWriterPluginColumn()
        for row in range(0, row_count):
            filename = self.filename_list[row]
            # Update Filename
            index = self.parent.model.createIndex(row, filename_column)
            self.parent.model.setData(index, filename)
            # Update Selected ImageWriterPlugin
            index = self.parent.model.createIndex(row, image_writer_plugin_column)
            self.parent.model.setData(index, self.selected_writer.get('name'))


class FilenameWizardWelcomePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.Writers = parent.Writers

        self.setStyleSheet(''' font-size: 16px; ''')
        self.setTitle("Autogenerate filenames")
        self.setSubTitle("How would you like to save your data?")

        self.SaveAsComboBoxLabel = QtWidgets.QLabel('Save as:')
        self.SaveAsComboBox = QtWidgets.QComboBox()
        self.SaveAsComboBox.addItems([writer.get('file_names').FormatSelectionOption for writer in self.Writers])
        self.SaveAsComboBox.setCurrentIndex(0)

        self.registerField('SaveAs', self.SaveAsComboBox, 'currentIndex')
        
        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.SaveAsComboBoxLabel, 0, 0)
        self.layout.addWidget(self.SaveAsComboBox, 0, 1)
        self.setLayout(self.layout)
    
    def nextId(self):
        for writer in self.Writers:
            if self.SaveAsComboBox.currentText() == writer.get('file_names').FormatSelectionOption:
                self.parent.selected_writer = writer
                return writer.get('id')


class AbstractSelectionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setStyleSheet(''' font-size: 16px; ''')
        self.DescriptionCheckBox = QtWidgets.QCheckBox('Description: ', self)
        self.DescriptionCheckBox.setChecked(True)
        self.DescriptionLineEdit = QtWidgets.QLineEdit(self)
        self.DescriptionCheckBox.toggled.connect(lambda boolean: self.DescriptionLineEdit.setEnabled(boolean))
        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.DescriptionCheckBox, 0, 0)
        self.layout.addWidget(self.DescriptionLineEdit, 0, 1)
        self.setLayout(self.layout)

    def validatePage(self):
        self.parent.generate_filename_list()
        return super().validatePage()

    def nextId(self):
        return self.parent.num_of_pages - 1 # Last page 'finished'


class FilenameWizardRawSelectionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setStyleSheet(''' font-size: 16px; ''')
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
        return self.parent.num_of_pages - 1 # Last page 'finished'


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
        file_list = self.parent.filename_list

        for f in file_list:
            self.mystring += f
            self.mystring += '\n'
        self.TextEdit.setPlainText(self.mystring)        

    def cleanupPage(self):
        self.mystring = ''

