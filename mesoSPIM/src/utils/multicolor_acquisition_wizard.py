'''
Contains Multicolor Acquisition Wizard Classes:

Widgets that take user input and create acquisition lists

'''
import numpy as np
import pprint

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty

from .multicolor_acquisition_builder import MulticolorTilingAcquisitionListBuilder

from ..mesoSPIM_State import mesoSPIM_StateSingleton

class MulticolorTilingWizard(QtWidgets.QWizard):
    '''
    Wizard to run

    The parent is the Window class of the microscope
    '''
    wizard_done = QtCore.pyqtSignal()

    num_of_pages = 10
    (welcome, zeroing, boundingbox, generalparameters, checktiling, channel1, 
    channel2, channel3, folderpage, finished) = range(num_of_pages)

    def __init__(self, parent=None):
        super().__init__(parent)

        ''' By an instance variable, callbacks to window signals can be handed
        through '''
        self.parent = parent
        self.cfg = parent.cfg
        self.state = mesoSPIM_StateSingleton()

        ''' Instance variables '''
        self.x_start = 0
        self.x_end = 0
        self.y_start = 0
        self.y_end = 0
        self.z_start = 0
        self.z_end = 0
        self.z_step = 1
        self.x_offset = 0
        self.y_offset = 0
        self.zoom = '1x'
        self.x_fov = 1
        self.y_fov = 1
        self.channels = []
        self.channelcount = 0
        self.shutterconfig = ''
        self.theta_pos = 0
        self.x_image_count = 1
        self.y_image_count = 1
        self.folder = ''
        self.delta_x = 0.0
        self.delta_y = 0.0
        
        self.setWindowTitle('Tiling Wizard')

        self.setPage(0, TilingWelcomePage(self))
        self.setPage(1, ZeroingXYStagePage(self))
        self.setPage(2, DefineBoundingBoxPage(self))
        self.setPage(3, DefineGeneralParametersPage(self))
        self.setPage(4, CheckTilingPage(self))
        self.setPage(5, FirstChannelPage(self))
        self.setPage(6, SecondChannelPage(self))
        self.setPage(7, ThirdChannelPage(self))
        self.setPage(8, DefineFolderPage(self))
        self.setPage(9, FinishedTilingPage(self))

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
            # self.print_dict()
            self.update_acquisition_list()
            self.update_model(self.parent.model, self.acq_list)
            ''' Update state with this new list '''
            # self.parent.update_persistent_editors()
            self.wizard_done.emit()
        else:
            print('Wizard provided return code: ', r)

        super().done(r)

    def update_model(self, model, table):
        model.setTable(table)
        self.state['acq_list']=self.acq_list

    def update_image_counts(self):
        ''' 
        TODO: This needs some FOV information
        '''
        self.delta_x = abs(self.x_end - self.x_start)
        self.delta_y = abs(self.y_end - self.y_start)

        ''' Using the ceiling function to always create at least 1 image '''
        self.x_image_count = int(np.ceil(self.delta_x/self.x_offset))
        self.y_image_count = int(np.ceil(self.delta_y/self.y_offset))

        ''' Create at least 1 image even if delta_x or delta_y is 0 '''
        if self.x_image_count == 0:
            self.x_image_count = 1
        if self.y_image_count == 0:
            self.y_image_count = 1

        ''' The first FOV is centered on the starting location -
            therefore, add another image count to fully contain the end position
            if necessary
        '''
        if self.delta_x % self.x_offset > self.x_offset/2:
            self.x_image_count = self.x_image_count + 1
        
        if self.delta_y % self.y_offset > self.y_offset/2:
            self.y_image_count = self.y_image_count + 1

      
    def update_fov(self):
        pass
        # zoom = self.zoom
        # index = self.parent.cfg.zoom_options.index(zoom)
        # self.x_fov = self.parent.cfg.zoom_options[index]
        # self.y_fov = self.parent.cfg.zoom_options[index]

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
                'folder' : self.folder,
                'channels' : self.channels,
                }

    def update_acquisition_list(self):
        self.update_image_counts()
        self.update_fov()

        ''' Use the current rotation angle '''
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

class ZeroingXYStagePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Zero stage positions")
        self.setSubTitle("To aid in relative positioning, it is recommended to zero the XY stages.")

class DefineBoundingBoxPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define the bounding box of the tiling acquisition")
        self.setSubTitle("Move XY stages to the starting corner position")

        self.button0 = QtWidgets.QPushButton(self)
        self.button0.setText('Set XY Start Corner')
        self.button0.setCheckable(True)
        self.button0.toggled.connect(self.get_xy_start_position)

        self.button1 = QtWidgets.QPushButton(self)
        self.button1.setText('Set XY End Corner')
        self.button1.setCheckable(True)
        self.button1.toggled.connect(self.get_xy_end_position)

        self.ZStartButton = QtWidgets.QPushButton(self)
        self.ZStartButton.setText('Set Z start')
        self.ZStartButton.setCheckable(True)
        self.ZStartButton.toggled.connect(self.update_z_start_position)

        self.ZEndButton = QtWidgets.QPushButton(self)
        self.ZEndButton.setText('Set Z end')
        self.ZEndButton.setCheckable(True)
        self.ZEndButton.toggled.connect(self.update_z_end_position)

        self.ZSpinBoxLabel = QtWidgets.QLabel('Z stepsize')

        self.ZStepSpinBox = QtWidgets.QSpinBox(self)
        self.ZStepSpinBox.setValue(1)
        self.ZStepSpinBox.setMinimum(1)
        self.ZStepSpinBox.setMaximum(1000)
        self.ZStepSpinBox.valueChanged.connect(self.update_z_step)

        self.registerField('xy_start_position*',
                            self.button0,
                            )
        self.registerField('xy_end_position*',
                            self.button1,
                            )

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.button0, 0, 0)
        self.layout.addWidget(self.button1, 1, 1)
        self.layout.addWidget(self.ZStartButton, 2, 0)
        self.layout.addWidget(self.ZEndButton, 2, 1)
        self.layout.addWidget(self.ZSpinBoxLabel, 3, 0)
        self.layout.addWidget(self.ZStepSpinBox, 3, 1)
        self.setLayout(self.layout)

    def get_xy_start_position(self):
        self.parent.x_start = self.parent.state['position']['x_pos']
        self.parent.y_start = self.parent.state['position']['y_pos']
        
    def get_xy_end_position(self):
        self.parent.x_end = self.parent.state['position']['x_pos']
        self.parent.y_end = self.parent.state['position']['y_pos']    

    def update_z_start_position(self):
        self.parent.z_start = self.parent.state['position']['z_pos']
    
    def update_z_end_position(self):
        self.parent.z_end = self.parent.state['position']['z_pos']

    def update_z_step(self):
        self.parent.z_step = self.ZStepSpinBox.value()

class DefineGeneralParametersPage(QtWidgets.QWizardPage):
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define other parameters")

        self.zoomLabel = QtWidgets.QLabel('Zoom')
        self.zoomComboBox = QtWidgets.QComboBox(self)
        self.zoomComboBox.addItems(self.parent.cfg.zoomdict.keys())

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

        self.shutterLabel = QtWidgets.QLabel('Shutter')
        self.shutterComboBox = QtWidgets.QComboBox(self)
        self.shutterComboBox.addItems(self.parent.cfg.shutteroptions)

        self.channelLabel = QtWidgets.QLabel('# Channels')
        self.channelSpinBox = QtWidgets.QSpinBox(self)
        self.channelSpinBox.setMinimum(1)
        self.channelSpinBox.setMaximum(3)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.zoomLabel, 0, 0)
        self.layout.addWidget(self.zoomComboBox, 0, 1)
        self.layout.addWidget(self.shutterLabel, 1, 0)
        self.layout.addWidget(self.shutterComboBox, 1, 1)
        self.layout.addWidget(self.xOffsetSpinBoxLabel, 2, 0)
        self.layout.addWidget(self.xOffsetSpinBox, 2, 1)
        self.layout.addWidget(self.yOffsetSpinBoxLabel, 3, 0)
        self.layout.addWidget(self.yOffsetSpinBox, 3, 1)
        self.layout.addWidget(self.channelLabel, 4, 0)
        self.layout.addWidget(self.channelSpinBox, 4, 1)
        self.setLayout(self.layout)

    def validatePage(self):
        ''' The done function should update all the parent parameters '''
        self.update_other_acquisition_parameters()
        return True

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

        self.Button = QtWidgets.QPushButton('Values are ok?')
        self.Button.setCheckable(True)
        self.Button.setChecked(False)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.xFOVLabel, 1, 0)
        self.layout.addWidget(self.xFOVs, 1, 1)
        self.layout.addWidget(self.yFOVLabel, 2, 0)
        self.layout.addWidget(self.yFOVs, 2, 1)
        self.layout.addWidget(self.Button, 3, 1)
        self.setLayout(self.layout)

        self.registerField('finalCheck*',self.Button)

    def initializePage(self):
        ''' Here, the acquisition list is created for further checking'''
        self.parent.update_image_counts()
        self.xFOVs.setText(str(self.parent.x_image_count))
        self.yFOVs.setText(str(self.parent.y_image_count))

class GenericChannelPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None, channel_id=0):
        super().__init__(parent)
        self.parent = parent

        self.channel_id = channel_id
        self.id_string = str(self.channel_id+1)
        self.setTitle("Configure channel #"+self.id_string)

        self.f_start = 0
        self.f_end = 0

        self.copyCurrentStateLabel = QtWidgets.QLabel('Copy state:')

        self.copyCurrentStateButton = QtWidgets.QPushButton(self)
        self.copyCurrentStateButton.setText('Copy current laser, intensity and filter')
        self.copyCurrentStateButton.clicked.connect(self.update_page_from_state)

        self.laserLabel = QtWidgets.QLabel('Laser')
        self.laserComboBox = QtWidgets.QComboBox(self)
        self.laserComboBox.addItems(self.parent.cfg.laserdict.keys())

        self.intensityLabel = QtWidgets.QLabel('Intensity')
        self.intensitySlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.intensitySlider.setMinimum(0)
        self.intensitySlider.setMaximum(100)

        self.filterLabel = QtWidgets.QLabel('Filter')
        self.filterComboBox = QtWidgets.QComboBox(self)
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

        self.registerField('start_focus_position'+str(self.channel_id)+'*',
                            self.StartFocusButton,
                            )

        self.registerField('end_focus_position'+str(self.channel_id)+'*',
                            self.EndFocusButton,
                            )

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
        #try:
        #except:
        #    print('Move absolute is not possible!')

    def validatePage(self):
        selectedIntensity =  self.intensitySlider.value()
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
            etl_l_offset = 0
            etl_l_amplitude = 0
            etl_r_offset = 0
            etl_r_amplitude = 0

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
        self.setSubTitle("Attention: This will overwrite the Acquisition Table. Click 'Finished' to continue. To rename the files, use the filename wizard.")

    def validatePage(self):
        return True

if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    wizard = MyWizard()
    sys.exit(app.exec_())
