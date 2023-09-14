'''
Contains Multicolor Acquisition Wizard Classes:

Widgets that take user input and create acquisition lists

'''
import numpy as np
import pprint
from functools import partial

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty

from .multicolor_acquisition_builder import MulticolorTilingAcquisitionListBuilder
from .filename_wizard import FilenameWizard
from ..mesoSPIM_State import mesoSPIM_StateSingleton


class MulticolorTilingWizard(QtWidgets.QWizard):
    '''
    Wizard to run

    The parent is the Window class of the microscope
    '''
    wizard_done = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        ''' Parent is object of class mesoSPIM_AcquisitionManagerWindow()'''
        super().__init__(parent)

        ''' By an instance variable, callbacks to window signals can be handed through '''
        self.parent = parent
        self.cfg = parent.cfg if parent else None
        self.state = mesoSPIM_StateSingleton()

        ''' Instance variables '''
        self.x_start = self.x_end = self.y_start = self.y_end = self.z_start = self.z_end = 0
        self.z_step = 5
        self.x_offset = self.y_offset = 0
        self.zoom = '1x'
        self.x_pixels = self.cfg.camera_parameters['x_pixels'] if self.cfg else 2048
        self.y_pixels = self.cfg.camera_parameters['y_pixels'] if self.cfg else 2048
        self.x_fov = self.y_fov = 1
        self.channels = []
        self.channelcount = 0
        self.shutterconfig = ''
        self.theta_pos = 0
        self.x_image_count = self.y_image_count = 1
        self.folder = ''
        self.delta_x = self.delta_y = 0.0
        self.shutter_seq = False
        
        self.setWindowTitle('Tiling Wizard')

        self.channel1, self.channel2, self.channel3, self.channel4, self.channel5, self.folderpage = 4, 5, 6, 7, 8, 9
        self.setPage(0, TilingWelcomePage(self))
        self.setPage(1, DefineBoundingBoxPage(self))
        self.setPage(2, DefineGeneralParametersPage(self))
        self.setPage(3, CheckTilingPage(self))
        self.setPage(self.channel1, FirstChannelPage(self))
        self.setPage(self.channel2, SecondChannelPage(self))
        self.setPage(self.channel3, ThirdChannelPage(self))
        self.setPage(self.channel4, FourthChannelPage(self))
        self.setPage(self.channel5, FifthChannelPage(self))
        self.setPage(self.folderpage, DefineFolderPage(self))
        self.setPage(10, FinishedTilingPage(self))
        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        self.setStyleSheet(''' font-size: 20px; ''')
        self.show()

        self.button(QtWidgets.QWizard.BackButton).clicked.connect(self.go_back)

    def go_back(self):
        '''Amend previously created channel settings'''
        if self.currentId() in (self.channel1, self.channel2, self.channel3):
            ch = self.channels.pop()
            # print(f"DEBUG: removed channel {ch}")

    def done(self, r):
        ''' Reimplementation of the done function

        if r == 0: canceled
        if r == 1: finished properly
        '''
        if r == 0:
            print("Wizard was canceled")
        if r == 1:
            print('Wizard was closed properly')
            # self.print_dict()
            self.update_acquisition_list()
            if self.parent:
                self.update_model(self.parent.model, self.acq_list)
            ''' Update state with this new list '''
            # self.parent.update_persistent_editors()
            self.wizard_done.emit()
            FilenameWizard(self.parent)
        else:
            print('Wizard provided return code: ', r)

        super().done(r)

    def update_model(self, model, acq_list):
        model.setTable(acq_list)
        self.state['acq_list'] = acq_list

    def update_image_counts(self):
        self.delta_x = abs(self.x_end - self.x_start)
        self.delta_y = abs(self.y_end - self.y_start)

        ''' Using the ceiling function to always create at least 1 image '''
        self.x_image_count = int(np.ceil(self.delta_x / self.x_offset)) + 1
        self.y_image_count = int(np.ceil(self.delta_y / self.y_offset)) + 1

    def get_dict(self):
        return {'x_start' : self.x_start,
                'x_end' : self.x_end,
                'y_start' : self.y_start,
                'y_end' : self.y_end,
                'z_start' : self.z_start,
                'z_end' : self.z_end,
                'z_step' : self.z_step,
                'theta_pos' : self.theta_pos,
                'x_offset' : self.x_offset,
                'y_offset' : self.y_offset,
                'x_fov' : self.x_fov,
                'y_fov' : self.y_fov,
                'x_image_count' : self.x_image_count,
                'y_image_count' : self.y_image_count,
                'zoom' : self.zoom,
                'shutterconfig' : self.shutterconfig,
                'shutter_seq': self.shutter_seq,
                'folder' : self.folder,
                'channels' : self.channels,
                }

    def update_acquisition_list(self):
        self.update_image_counts()
        self.theta_pos = self.state['position']['theta_pos']

        dict = self.get_dict()
        self.acq_list = MulticolorTilingAcquisitionListBuilder(dict).get_acquisition_list()

    def print_dict(self):
        pprint.pprint(self.get_dict())


class TilingWelcomePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to the tiling wizard")
        self.setSubTitle("This wizard will guide you through the steps of creating a tiling acquisition.")


class DefineBoundingBoxPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define the bounding box of the tiling acquisition")
        self.setSubTitle("Move the sample in XYZ and define bounding box by corners OR walls by pressing the buttons below. ")

        self.button_xy_start = QtWidgets.QPushButton(self)
        self.button_xy_start.setText('Set XY Start Corner')
        self.button_xy_start.setCheckable(True)
        self.button_xy_start.clicked.connect(partial(self.get_edge_position, key='xy-start'))

        self.button_x_start = QtWidgets.QPushButton(self)
        self.button_x_start.setText('Set X start')
        self.button_x_start.setCheckable(True)
        self.button_x_start.clicked.connect(partial(self.get_edge_position, key='x-start'))

        self.button_x_end = QtWidgets.QPushButton(self)
        self.button_x_end.setText('Set X end')
        self.button_x_end.setCheckable(True)
        self.button_x_end.clicked.connect(partial(self.get_edge_position, key='x-end'))

        self.button_y_start = QtWidgets.QPushButton(self)
        self.button_y_start.setText('Set Y start')
        self.button_y_start.setCheckable(True)
        self.button_y_start.clicked.connect(partial(self.get_edge_position, key='y-start'))

        self.button_y_end = QtWidgets.QPushButton(self)
        self.button_y_end.setText('Set Y end')
        self.button_y_end.setCheckable(True)
        self.button_y_end.clicked.connect(partial(self.get_edge_position, key='y-end'))

        self.button_xy_end = QtWidgets.QPushButton(self)
        self.button_xy_end.setText('Set XY End Corner')
        self.button_xy_end.setCheckable(True)
        self.button_xy_end.clicked.connect(partial(self.get_edge_position, key='xy-end'))

        self.ZStartButton = QtWidgets.QPushButton(self)
        self.ZStartButton.setText('Set Z start')
        self.ZStartButton.setCheckable(True)
        self.ZStartButton.clicked.connect(partial(self.get_edge_position, key='z-start'))

        self.ZEndButton = QtWidgets.QPushButton(self)
        self.ZEndButton.setText('Set Z end')
        self.ZEndButton.setCheckable(True)
        self.ZEndButton.clicked.connect(partial(self.get_edge_position, key='z-end'))

        self.ZSpinBoxLabel = QtWidgets.QLabel('Z stepsize')
        self.ZStepSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.ZStepSpinBox.setValue(5)
        self.ZStepSpinBox.setDecimals(1)
        self.ZStepSpinBox.setMinimum(0.1)
        self.ZStepSpinBox.setMaximum(1000)
        self.ZStepSpinBox.valueChanged.connect(self.update_z_step)

        self.registerField('xy_start_position*', self.button_xy_start)
        self.registerField('xy_end_position*', self.button_xy_end)
        self.registerField('z_end_position*', self.ZEndButton)
        self.update_z_step()

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.button_xy_start, 0, 0)
        self.layout.addWidget(self.button_y_start, 0, 1)
        self.layout.addWidget(self.button_x_start, 1, 0)
        self.layout.addWidget(self.button_x_end, 1, 2)
        self.layout.addWidget(self.button_y_end, 2, 1)
        self.layout.addWidget(self.button_xy_end, 2, 2)
        self.layout.addWidget(self.ZStartButton, 3, 0)
        self.layout.addWidget(self.ZEndButton, 3, 2)
        self.layout.addWidget(self.ZSpinBoxLabel, 4, 0)
        self.layout.addWidget(self.ZStepSpinBox, 4, 2)
        self.setLayout(self.layout)

    def get_edge_position(self, key):
        valid_keys = ('x-start', 'x-end', 'y-start', 'y-end', 'z-start', 'z-end', 'xy-start', 'xy-end')
        assert key in valid_keys, f"Position key {key} is invalid"
        if key == 'x-start':
            self.parent.x_start = self.parent.state['position']['x_pos']
            if self.button_y_start.isChecked():
                self.button_xy_start.setChecked(True)
        elif key == 'x-end':
            self.parent.x_end = self.parent.state['position']['x_pos']
            if self.button_y_end.isChecked():
                self.button_xy_end.setChecked(True)
        elif key == 'y-start':
            self.parent.y_start = self.parent.state['position']['y_pos']
            if self.button_x_start.isChecked():
                self.button_xy_start.setChecked(True)
        elif key == 'y-end':
            self.parent.y_end = self.parent.state['position']['y_pos']
            if self.button_x_end.isChecked():
                self.button_xy_end.setChecked(True)
        elif key == 'z-start':
            self.parent.z_start = self.parent.state['position']['z_pos']
        elif key == 'z-end':
            self.parent.z_end = self.parent.state['position']['z_pos']
        elif key == 'xy-start':
            self.parent.x_start = self.parent.state['position']['x_pos']
            self.parent.y_start = self.parent.state['position']['y_pos']
            self.button_x_start.setChecked(True)
            self.button_y_start.setChecked(True)
        elif key == 'xy-end':
            self.parent.x_end = self.parent.state['position']['x_pos']
            self.parent.y_end = self.parent.state['position']['y_pos']
            self.button_x_end.setChecked(True)
            self.button_y_end.setChecked(True)

    def update_z_step(self):
        self.parent.z_step = self.ZStepSpinBox.value()


class DefineGeneralParametersPage(QtWidgets.QWizardPage):
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        N_CHANNELS = 5
        self.setTitle("Define other parameters")
        self.channelLabel = QtWidgets.QLabel('# Channels')
        self.channelSpinBox = QtWidgets.QSpinBox(self)
        self.channelSpinBox.setMinimum(1)
        self.channelSpinBox.setMaximum(N_CHANNELS)

        self.zoomLabel = QtWidgets.QLabel('Zoom')
        self.zoomComboBox = QtWidgets.QComboBox(self)
        if self.parent.cfg:
            self.zoomComboBox.addItems(self.parent.cfg.zoomdict.keys())
        self.zoomComboBox.currentIndexChanged.connect(self.update_fov_size)

        self.shutterLabel = QtWidgets.QLabel('Shutter')
        self.shutterComboBox = QtWidgets.QComboBox(self)
        if self.parent.cfg:
            self.shutterComboBox.addItems(self.parent.cfg.shutteroptions)

        self.shutterSequenceLabel = QtWidgets.QLabel('Left, then Right?')
        self.shutterSeqCheckBox = QtWidgets.QCheckBox(self)
        self.shutterSeqCheckBox.setChecked(False)
        self.shutterSeqCheckBox.clicked.connect(self.update_shutt_seq)

        self.fovSizeLabel = QtWidgets.QLabel('FOV Size X ⨉ Y:')
        self.fovSizeLineEdit = QtWidgets.QLineEdit(self)
        self.fovSizeLineEdit.setReadOnly(True)
        
        self.overlapPercentageCheckBox = QtWidgets.QCheckBox('Overlap %', self)
        self.overlapLabel = QtWidgets.QLabel('Overlap in %')
        self.overlapPercentageSpinBox = QtWidgets.QSpinBox(self)
        self.overlapPercentageSpinBox.setSuffix(' %')
        self.overlapPercentageSpinBox.setMinimum(1)
        self.overlapPercentageSpinBox.setMaximum(50)
        self.overlapPercentageSpinBox.setValue(10)
        self.overlapPercentageSpinBox.valueChanged.connect(self.update_x_and_y_offset)

        self.manualOverlapCheckBox = QtWidgets.QCheckBox('Set Offset Manually', self)

        self.xOffsetSpinBoxLabel = QtWidgets.QLabel('X Offset')
        self.xOffsetSpinBox = QtWidgets.QSpinBox(self)
        self.xOffsetSpinBox.setSuffix(' μm')
        self.xOffsetSpinBox.setMinimum(1)
        self.xOffsetSpinBox.setMaximum(30000)
        self.xOffsetSpinBox.setValue(500)
        
        self.yOffsetSpinBoxLabel = QtWidgets.QLabel('Y Offset')
        self.yOffsetSpinBox = QtWidgets.QSpinBox(self)
        self.yOffsetSpinBox.setSuffix(' μm')
        self.yOffsetSpinBox.setMinimum(1)
        self.yOffsetSpinBox.setMaximum(30000)
        self.yOffsetSpinBox.setValue(500)

        self.overlapPercentageCheckBox.clicked.connect(lambda boolean: self.overlapPercentageSpinBox.setEnabled(boolean))
        self.overlapPercentageCheckBox.clicked.connect(self.update_x_and_y_offset)
        self.overlapPercentageCheckBox.clicked.connect(lambda boolean: self.xOffsetSpinBox.setEnabled(not boolean))
        self.overlapPercentageCheckBox.clicked.connect(lambda boolean: self.yOffsetSpinBox.setEnabled(not boolean))
        self.overlapPercentageCheckBox.clicked.connect(lambda boolean: self.manualOverlapCheckBox.setChecked(not boolean))

        self.manualOverlapCheckBox.clicked.connect(lambda boolean: self.overlapPercentageSpinBox.setEnabled(not boolean))
        self.manualOverlapCheckBox.clicked.connect(lambda boolean: self.xOffsetSpinBox.setEnabled(boolean))
        self.manualOverlapCheckBox.clicked.connect(lambda boolean: self.yOffsetSpinBox.setEnabled(boolean))
        self.manualOverlapCheckBox.clicked.connect(lambda boolean: self.overlapPercentageCheckBox.setChecked(not boolean))

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.channelLabel, 0, 0)
        self.layout.addWidget(self.channelSpinBox, 0, 1)
        self.layout.addWidget(self.zoomLabel, 1, 0)
        self.layout.addWidget(self.zoomComboBox, 1, 1)
        self.layout.addWidget(self.shutterLabel, 2, 0)
        self.layout.addWidget(self.shutterComboBox, 2, 1)
        self.layout.addWidget(self.shutterSequenceLabel, 2, 2)
        self.layout.addWidget(self.shutterSeqCheckBox, 2, 3)
        self.layout.addWidget(self.fovSizeLabel, 3, 0)
        self.layout.addWidget(self.fovSizeLineEdit, 3, 1)
        self.layout.addWidget(self.overlapPercentageCheckBox, 4, 0)
        self.layout.addWidget(self.overlapLabel, 5, 0)
        self.layout.addWidget(self.overlapPercentageSpinBox, 5, 1)
        self.layout.addWidget(self.manualOverlapCheckBox, 6, 0)
        self.layout.addWidget(self.xOffsetSpinBoxLabel, 7, 0)
        self.layout.addWidget(self.xOffsetSpinBox, 7, 1)
        self.layout.addWidget(self.yOffsetSpinBoxLabel, 8, 0)
        self.layout.addWidget(self.yOffsetSpinBox, 8, 1)
        self.setLayout(self.layout)

    def validatePage(self):
        ''' The done function should update all the parent parameters '''
        self.update_other_acquisition_parameters()
        return True

    @QtCore.pyqtSlot()
    def update_fov_size(self):
        ''' Should be invoked whenever the zoom selection is changed '''
        new_zoom = self.zoomComboBox.currentText()
        pixelsize_in_um = self.parent.cfg.pixelsize[new_zoom] if self.parent.cfg else 6.5
        ''' X and Y are interchanged here to account for the camera rotation by 90°'''
        new_x_fov_in_um = int(self.parent.y_pixels * pixelsize_in_um)
        new_y_fov_in_um = int(self.parent.x_pixels * pixelsize_in_um)
        self.parent.x_fov = new_x_fov_in_um
        self.parent.y_fov = new_y_fov_in_um

        self.fovSizeLineEdit.setText(str(new_x_fov_in_um)+' ⨉ '+str(new_y_fov_in_um) + ' μm²')

        ''' If the zoom changes, the offset calculation should be redone'''
        if self.overlapPercentageCheckBox.isChecked():
            self.update_x_and_y_offset()

    @QtCore.pyqtSlot()
    def update_x_and_y_offset(self):
        new_offset_percentage = self.overlapPercentageSpinBox.value()
        x_offset = int(self.parent.x_fov * (1-new_offset_percentage / 100))
        y_offset = int(self.parent.y_fov * (1-new_offset_percentage / 100))
        self.xOffsetSpinBox.setValue(x_offset)
        self.yOffsetSpinBox.setValue(y_offset)

    @QtCore.pyqtSlot()
    def update_shutt_seq(self):
        self.parent.shutter_seq = self.shutterSeqCheckBox.checkState()
        if self.shutterSeqCheckBox.checkState():
            self.shutterComboBox.setEnabled(False)
        else:
            self.shutterComboBox.setEnabled(True)

    def update_other_acquisition_parameters(self):
        ''' Here, all the Tiling parameters are filled in the parent (TilingWizard)
        This method should be called when the "Next" Button is pressed
        '''
        self.parent.zoom = self.zoomComboBox.currentText()
        self.parent.x_offset = self.xOffsetSpinBox.value()
        self.parent.y_offset = self.yOffsetSpinBox.value()
        self.parent.shutterconfig = self.shutterComboBox.currentText()
        self.parent.channelcount = self.channelSpinBox.value()

    def initializePage(self):
        self.update_page_from_state()
        self.update_fov_size()
        self.update_x_and_y_offset()
        self.overlapPercentageCheckBox.setChecked(True)
        self.xOffsetSpinBox.setEnabled(False)
        self.yOffsetSpinBox.setEnabled(False)
        
    def update_page_from_state(self):
        self.zoomComboBox.setCurrentText(self.parent.state['zoom'])
        self.shutterComboBox.setCurrentText(self.parent.state['shutterconfig'])


class CheckTilingPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Check Tiling Page")
        self.setSubTitle("Here are your parameters")

        self.xFOVLabel = QtWidgets.QLabel('X FOVs:')
        self.xFOVs = QtWidgets.QLineEdit(self)
        self.xFOVs.setReadOnly(True)

        self.yFOVLabel = QtWidgets.QLabel('Y FOVs:')
        self.yFOVs = QtWidgets.QLineEdit(self)
        self.yFOVs.setReadOnly(True)

        self.x_start_end_label = QtWidgets.QLabel('X start, end:')
        self.x_start = QtWidgets.QLineEdit(self)
        self.x_start.setReadOnly(True)
        self.x_end = QtWidgets.QLineEdit(self)
        self.x_end.setReadOnly(True)

        self.y_start_end_label = QtWidgets.QLabel('Y start, end:')
        self.y_start = QtWidgets.QLineEdit(self)
        self.y_start.setReadOnly(True)
        self.y_end = QtWidgets.QLineEdit(self)
        self.y_end.setReadOnly(True)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.xFOVLabel, 0, 0)
        self.layout.addWidget(self.xFOVs, 0, 1)
        self.layout.addWidget(self.x_start_end_label, 1, 0)
        self.layout.addWidget(self.x_start, 1, 1)
        self.layout.addWidget(self.x_end, 1, 2)

        self.layout.addWidget(self.yFOVLabel, 2, 0)
        self.layout.addWidget(self.yFOVs, 2, 1)
        self.layout.addWidget(self.y_start_end_label, 3, 0)
        self.layout.addWidget(self.y_start, 3, 1)
        self.layout.addWidget(self.y_end, 3, 2)

        self.setLayout(self.layout)

    def initializePage(self):
        ''' Here, the acquisition list is created for further checking'''
        self.parent.update_image_counts()
        self.xFOVs.setText(str(self.parent.x_image_count))
        self.yFOVs.setText(str(self.parent.y_image_count))
        self.x_start.setText(str(round(self.parent.x_start)))
        self.y_start.setText(str(round(self.parent.y_start)))
        self.x_end.setText(str(round(self.parent.x_end)))
        self.y_end.setText(str(round(self.parent.y_end)))


class GenericChannelPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None, channel_id=0):
        super().__init__(parent)
        self.parent = parent

        self.channel_id = channel_id
        self.id_string = str(self.channel_id+1)
        self.setTitle("Configure channel #"+self.id_string)

        self.f_start = self.f_end = 0

        self.copyCurrentStateLabel = QtWidgets.QLabel('Copy state:')

        self.copyCurrentStateButton = QtWidgets.QPushButton(self)
        self.copyCurrentStateButton.setText('Copy current laser, intensity and filter')
        self.copyCurrentStateButton.clicked.connect(self.update_page_from_state)

        self.laserLabel = QtWidgets.QLabel('Laser')
        self.laserComboBox = QtWidgets.QComboBox(self)
        if self.parent.cfg:
            self.laserComboBox.addItems(self.parent.cfg.laserdict.keys())

        self.intensityLabel = QtWidgets.QLabel('Intensity')
        self.intensitySlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.intensitySlider.setMinimum(0)
        self.intensitySlider.setMaximum(100)

        self.filterLabel = QtWidgets.QLabel('Filter')
        self.filterComboBox = QtWidgets.QComboBox(self)
        if self.parent.cfg:
            self.filterComboBox.addItems(self.parent.cfg.filterdict.keys())

        self.ETLCheckBoxLabel = QtWidgets.QLabel('ETL')
        self.ETLCheckBox = QtWidgets.QCheckBox('Copy current ETL parameters', self)
        self.ETLCheckBox.setChecked(True)

        self.StartFocusLabel = QtWidgets.QLabel('Start focus')
        self.StartFocusButton = QtWidgets.QPushButton(self)
        self.StartFocusButton.setText('Set start focus')
        self.StartFocusButton.setCheckable(True)
        self.StartFocusButton.toggled.connect(self.update_start_focus_position)

        self.EndFocusLabel = QtWidgets.QLabel('End focus')
        self.EndFocusButton = QtWidgets.QPushButton(self)
        self.EndFocusButton.setText('Set end focus')
        self.EndFocusButton.setCheckable(True)
        self.EndFocusButton.toggled.connect(self.update_end_focus_position)

        self.GoToZStartButton = QtWidgets.QPushButton(self)
        self.GoToZStartButton.setText('Go to Z start')
        self.GoToZStartButton.clicked.connect(lambda: self.go_to_z_position(self.parent.z_start))

        self.GoToZEndButton = QtWidgets.QPushButton(self)
        self.GoToZEndButton.setText('Go to Z end')
        self.GoToZEndButton.clicked.connect(lambda: self.go_to_z_position(self.parent.z_end))

        self.registerField('start_focus_position' + str(self.channel_id) + '*', self.StartFocusButton)

        self.registerField('end_focus_position' + str(self.channel_id) + '*', self.EndFocusButton)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.copyCurrentStateLabel, 0, 0, 1, 1)
        self.layout.addWidget(self.copyCurrentStateButton, 0, 1, 1, 2)
        self.layout.addWidget(self.laserLabel, 1, 0, 1, 1)
        self.layout.addWidget(self.laserComboBox, 1, 1, 1, 2)
        self.layout.addWidget(self.intensityLabel, 2, 0, 1, 1)
        self.layout.addWidget(self.intensitySlider, 2, 1, 1, 2)
        self.layout.addWidget(self.filterLabel, 3, 0, 1, 1)
        self.layout.addWidget(self.filterComboBox, 3, 1, 1, 2)
        self.layout.addWidget(self.ETLCheckBoxLabel, 4, 0, 1, 1)
        self.layout.addWidget(self.ETLCheckBox, 4, 1, 1, 2)
        self.layout.addWidget(self.StartFocusLabel, 5, 0, 1, 1)
        self.layout.addWidget(self.StartFocusButton, 5, 1, 1, 1)
        self.layout.addWidget(self.GoToZStartButton, 5, 2, 1, 1)
        self.layout.addWidget(self.EndFocusLabel, 6, 0, 1, 1)
        self.layout.addWidget(self.EndFocusButton, 6, 1, 1, 1)
        self.layout.addWidget(self.GoToZEndButton, 6, 2, 1, 1)
        self.setLayout(self.layout)

    def initializePage(self):
        self.update_page_from_state()

    def update_page_from_state(self):
        self.laserComboBox.setCurrentText(self.parent.state['laser'])
        self.intensitySlider.setValue(self.parent.state['intensity'])
        self.filterComboBox.setCurrentText(self.parent.state['filter'])

    def update_start_focus_position(self):
        self.f_start = self.parent.state['position']['f_pos']

    def update_end_focus_position(self):
        self.f_end = self.parent.state['position']['f_pos']

    def go_to_z_position(self, z):
        self.parent.parent.parent.sig_move_absolute.emit({'z_abs':z})

    def validatePage(self):
        selectedIntensity = self.intensitySlider.value()
        selectedLaser = self.laserComboBox.currentText()
        selectedFilter = self.filterComboBox.currentText()
        f_start = self.f_start
        f_end = self.f_end

        if self.ETLCheckBox.isChecked():
            etl_l_offset = self.parent.state['etl_l_offset'] 
            etl_l_amplitude = self.parent.state['etl_l_amplitude']
            etl_r_offset = self.parent.state['etl_r_offset'] 
            etl_r_amplitude = self.parent.state['etl_r_amplitude']
        else: 
            etl_l_offset = etl_l_amplitude = etl_r_offset = etl_r_amplitude = 0

        self.parent.channels.append({'laser':selectedLaser, 
                                    'intensity':selectedIntensity,
                                    'filter':selectedFilter,
                                    'f_start':f_start,
                                    'f_end':f_end,
                                    'etl_l_offset':etl_l_offset,
                                    'etl_l_amplitude':etl_l_amplitude,
                                    'etl_r_offset':etl_r_offset,
                                    'etl_r_amplitude':etl_r_amplitude})

        return True


class FirstChannelPage(GenericChannelPage):
    def __init__(self, parent=None):
        super().__init__(parent, 0)

    def nextId(self):
        if self.parent.channelcount == 1:
            return self.parent.folderpage
        else: 
            return self.parent.channel2 


class SecondChannelPage(GenericChannelPage):
    def __init__(self, parent=None):
        super().__init__(parent, 1)

    def nextId(self):
        if self.parent.channelcount == 2:
            return self.parent.folderpage
        else: 
            return self.parent.channel3 


class ThirdChannelPage(GenericChannelPage):
    def __init__(self, parent=None):
        super().__init__(parent, 2)

    def nextId(self):
        if self.parent.channelcount == 3:
            return self.parent.folderpage
        else:
            return self.parent.channel4


class FourthChannelPage(GenericChannelPage):
    def __init__(self, parent=None):
        super().__init__(parent, 3)

    def nextId(self):
        if self.parent.channelcount == 4:
            return self.parent.folderpage
        else:
            return self.parent.channel5


class FifthChannelPage(GenericChannelPage):
    def __init__(self, parent=None):
        super().__init__(parent, 4)

    def nextId(self):
        return self.parent.folderpage


class DefineFolderPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Select folder")
        self.setSubTitle("Please select the folder in which the data should be saved.")

        self.Button = QtWidgets.QPushButton('Select Folder')
        self.Button.setCheckable(True)
        self.Button.setChecked(False)
        self.Button.toggled.connect(self.choose_folder)

        self.TextEdit = QtWidgets.QLineEdit(self)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.Button, 0, 0)
        self.layout.addWidget(self.TextEdit, 1, 0)
        self.setLayout(self.layout)

    def choose_folder(self):
        ''' File dialog for choosing the save folder '''
        path = QtWidgets.QFileDialog.getExistingDirectory(self.parent, 'Select Folder')
        if path:
            self.parent.folder = path
            self.TextEdit.setText(path)


class FinishedTilingPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Finished!")
        self.setSubTitle("Attention: This will overwrite the Acquisition Table. "
                         "File name wizard will start next.")

    def validatePage(self):
        return True
