'''
Contains Acquisition Wizard Classes:

Widgets that take user input and create acquisition lists

'''
import numpy as np
import pprint

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty

# from .config import config as cfg
from .acquisition_builder import TilingAcquisitionListBuilder

from ..mesoSPIM_State import mesoSPIM_StateSingleton

class TilingWizard(QtWidgets.QWizard):
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
        self.f_start = 0
        self.f_end = 0
        self.x_offset = 0
        self.y_offset = 0
        self.zoom = '1x'
        self.x_fov = 1
        self.y_fov = 1
        self.laser = ''
        self.intensity = 0
        self.filter = ''
        self.shutterconfig = ''
        self.theta_pos = 0
        self.f_pos = 0
        self.x_image_count = 1
        self.y_image_count = 1
        self.folder = ''
        self.delta_x = 0.0
        self.delta_y = 0.0
        self.etl_l_offset = 0.0
        self.etl_l_amplitude = 0.0
        self.etl_r_offset = 0.0
        self.etl_r_amplitude = 0.0

        self.acquisition_time = 0

        self.setWindowTitle('Tiling Wizard')

        self.addPage(TilingWelcomePage(self))
        self.addPage(ZeroingXYStagePage(self))
        self.addPage(DefineXYPositionPage(self))
        # self.addPage(DefineXYStartPositionPage(self))
        # self.addPage(DefineXYEndPositionPage(self))
        self.addPage(DefineZPositionPage(self))
        self.addPage(OtherAcquisitionParametersPage(self))
        self.addPage(DefineFolderPage(self))
        self.addPage(CheckTilingPage(self))
        self.addPage(FinishedTilingPage(self))

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
            self.update_model(self.parent.model, self.acq_list)
            ''' Update state with this new list '''
            # self.parent.update_persistent_editors()
            self.wizard_done.emit()
        else:
            print('Wizard provided return code: ', r)

        super().done(r)

    def update_model(self, model, table):
        # if self.field('appendToTable'):
        #     current_acq_list = self.state['acq_list'] 
        #     new_acq_list = current_acq_list.append(table)
        #     model.setTable(new_acq_list)
        #     self.state['acq_list']=new_acq_list
        # else:
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
                'f_start' : self.f_start,
                'f_end' : self.f_end,
                'x_offset' : self.x_offset,
                'y_offset' : self.y_offset,
                'x_fov' : self.x_fov,
                'y_fov' : self.y_fov,
                'x_image_count' : self.x_image_count,
                'y_image_count' : self.y_image_count,
                'zoom' : self.zoom,
                'laser' : self.laser,
                'intensity' : self.intensity,
                'filter' : self.filter,
                'shutterconfig' : self.shutterconfig,
                'folder' : self.folder,
                'etl_l_offset' : self.etl_l_offset,
                'etl_l_amplitude' : self.etl_l_amplitude,
                'etl_r_offset' : self.etl_r_offset,
                'etl_r_amplitude' : self.etl_r_amplitude,
                }

    def update_acquisition_list(self):
        self.update_image_counts()
        self.update_fov()

        ''' If the ETL amplitude is set, update the acq list accordingly'''
        if self.field('ETLCheckBox'):
            self.etl_l_offset = self.state['etl_l_offset'] 
            self.etl_l_amplitude = self.state['etl_l_amplitude']
            self.etl_r_offset = self.state['etl_r_offset'] 
            self.etl_r_amplitude = self.state['etl_r_amplitude'] 

        ''' Use the current rotation angle '''
        self.theta_pos = self.state['position']['theta_pos']

        dict = self.get_dict()
        self.acq_list = TilingAcquisitionListBuilder(dict).get_acquisition_list()
        self.acquisition_time = self.acq_list.get_acquisition_time()

        # pprint.pprint(self.acq_list)

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

        # self.button = QtWidgets.QPushButton(self)
        # self.button.setText('Zero XY stages')
        # self.button.setCheckable(True)

        # self.registerField('stages_zeroed*',
        #                     self.button,
        #                     )

        # try:
        #     '''
        #     Pretty dirty approach, reaching up through the hierarchy:

        #     The first level parent is the QWizard
        #     The second level parent is the Window - which can send zeroing signals
        #     The third level is the mesoSPIM MainWindow
        #     '''
        #     self.button.toggled.connect(lambda: self.parent.parent.parent.sig_zero_axes.emit(['x','y']))
        # except:
        #     print('Zeroing connection failed')

class DefineXYPositionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define the corners of the tiling acquisition")
        self.setSubTitle("Move XY stages to the starting corner position")

        self.button0 = QtWidgets.QPushButton(self)
        self.button0.setText('Set XY Start Corner')
        self.button0.setCheckable(True)
        self.button0.toggled.connect(self.get_xy_start_position)

        self.button1 = QtWidgets.QPushButton(self)
        self.button1.setText('Set XY End Corner')
        self.button1.setCheckable(True)
        self.button1.toggled.connect(self.get_xy_end_position)

        self.registerField('xy_start_position*',
                            self.button0,
                            )
        self.registerField('xy_end_position*',
                            self.button1,
                            )

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.button0, 0, 0)
        self.layout.addWidget(self.button1, 1, 1)
        self.setLayout(self.layout)

    def get_xy_start_position(self):
        self.parent.x_start = self.parent.state['position']['x_pos']
        self.parent.y_start = self.parent.state['position']['y_pos']
        
    def get_xy_end_position(self):
        self.parent.x_end = self.parent.state['position']['x_pos']
        self.parent.y_end = self.parent.state['position']['y_pos']

class DefineZPositionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define start & end Z position")
        self.setSubTitle("Move Z stages to the start & end position")

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

        self.StartFocusButton = QtWidgets.QPushButton(self)
        self.StartFocusButton.setText('Set start focus')
        self.StartFocusButton.setCheckable(True)
        self.StartFocusButton.toggled.connect(self.update_start_focus_position)

        self.EndFocusButton = QtWidgets.QPushButton(self)
        self.EndFocusButton.setText('Set end focus')
        self.EndFocusButton.setCheckable(True)
        self.EndFocusButton.toggled.connect(self.update_end_focus_position)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.ZStartButton, 0, 0)
        self.layout.addWidget(self.ZEndButton, 0, 1)
        self.layout.addWidget(self.ZSpinBoxLabel, 2, 0)
        self.layout.addWidget(self.ZStepSpinBox, 2, 1)
        self.layout.addWidget(self.StartFocusButton, 3, 0)
        self.layout.addWidget(self.EndFocusButton, 4, 0)
        self.setLayout(self.layout)

        self.registerField('z_start_position*',
                            self.ZStartButton,
                            )

        self.registerField('z_end_position*',
                            self.ZEndButton,
                            )

        self.registerField('start_focus_position*',
                            self.StartFocusButton,
                            )

        self.registerField('end_focus_position*',
                            self.EndFocusButton,
                            )

    def update_z_start_position(self):
        self.parent.z_start = self.parent.state['position']['z_pos']
    
    def update_z_end_position(self):
        self.parent.z_end = self.parent.state['position']['z_pos']

    def update_z_step(self):
        self.parent.z_step = self.ZStepSpinBox.value()

    def update_start_focus_position(self):
        self.parent.f_start = self.parent.state['position']['f_pos']

    def update_end_focus_position(self):
        self.parent.f_end = self.parent.state['position']['f_pos']

class OtherAcquisitionParametersPage(QtWidgets.QWizardPage):
    '''

    TODO: Needs a button: Take current parameters from Live or so
    '''

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define other parameters")

        self.zoomLabel = QtWidgets.QLabel('Zoom')
        self.zoomComboBox = QtWidgets.QComboBox(self)
        self.zoomComboBox.addItems(self.parent.cfg.zoomdict.keys())
       
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

        self.shutterLabel = QtWidgets.QLabel('Shutter')
        self.shutterComboBox = QtWidgets.QComboBox(self)
        self.shutterComboBox.addItems(self.parent.cfg.shutteroptions)

        self.xOffsetSpinBoxLabel = QtWidgets.QLabel('X Offset')
        self.xOffsetSpinBox = QtWidgets.QSpinBox(self)
        self.xOffsetSpinBox.setSuffix(' μm')
        self.xOffsetSpinBox.setMinimum(1)
        self.xOffsetSpinBox.setMaximum(20000)
        self.xOffsetSpinBox.setValue(500)

        self.yOffsetSpinBoxLabel = QtWidgets.QLabel('Y Offset')
        self.yOffsetSpinBox = QtWidgets.QSpinBox(self)
        self.yOffsetSpinBox.setSuffix(' μm')
        self.yOffsetSpinBox.setMinimum(1)
        self.yOffsetSpinBox.setMaximum(20000)
        self.yOffsetSpinBox.setValue(500)

        self.ETLCheckBoxLabel = QtWidgets.QLabel('ETL')
        self.ETLCheckBox = QtWidgets.QCheckBox('Copy current ETL parameters', self)
        self.ETLCheckBox.setChecked(True)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.zoomLabel, 0, 0)
        self.layout.addWidget(self.zoomComboBox, 0, 1)
        self.layout.addWidget(self.laserLabel, 1, 0)
        self.layout.addWidget(self.laserComboBox, 1, 1)
        self.layout.addWidget(self.intensityLabel, 2, 0)
        self.layout.addWidget(self.intensitySlider, 2, 1)
        self.layout.addWidget(self.filterLabel, 3, 0)
        self.layout.addWidget(self.filterComboBox, 3, 1)
        self.layout.addWidget(self.shutterLabel, 4, 0)
        self.layout.addWidget(self.shutterComboBox, 4, 1)
        self.layout.addWidget(self.xOffsetSpinBoxLabel, 5, 0)
        self.layout.addWidget(self.xOffsetSpinBox, 5, 1)
        self.layout.addWidget(self.yOffsetSpinBoxLabel, 6, 0)
        self.layout.addWidget(self.yOffsetSpinBox, 6, 1)
        self.layout.addWidget(self.ETLCheckBoxLabel, 7, 0)
        self.layout.addWidget(self.ETLCheckBox, 7, 1)

        self.registerField('ETLCheckBox', self.ETLCheckBox)

        self.setLayout(self.layout)

        self.update_page_from_state()

    def validatePage(self):
        ''' The done function should update all the parent parameters '''
        self.update_other_acquisition_parameters()
        return True

    def update_other_acquisition_parameters(self):
        ''' Here, all the Tiling parameters are filled in the parent (TilingWizard)

        This method should be called when the "Next" Button is pressed
        '''
        self.parent.zoom = self.zoomComboBox.currentText()
        # self.parent.x_fov = self.parent.cfg.fov_options[self.zoomComboBox.currentIndex()]
        # self.parent.y_fov = self.parent.cfg.fov_options[self.zoomComboBox.currentIndex()]
        self.parent.x_offset = self.xOffsetSpinBox.value()
        self.parent.y_offset = self.yOffsetSpinBox.value()
        self.parent.laser = self.laserComboBox.currentText()
        self.parent.intensity = self.intensitySlider.value()
        self.parent.filter = self.filterComboBox.currentText()
        self.parent.shutterconfig = self.shutterComboBox.currentText()

    def initializePage(self):
        self.update_page_from_state()

    def update_page_from_state(self):
        self.zoomComboBox.setCurrentText(self.parent.state['zoom'])
        self.laserComboBox.setCurrentText(self.parent.state['laser'])
        self.intensitySlider.setValue(self.parent.state['intensity'])
        self.filterComboBox.setCurrentText(self.parent.state['filter'])
        self.shutterComboBox.setCurrentText(self.parent.state['shutterconfig'])

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

class CheckTilingPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Check Tiling Page")
        self.setSubTitle("Here are your parameters")

        # self.timeLabel = QtWidgets.QLabel('Acquisition Time:')
        # self.acqTime = QtWidgets.QLineEdit(self)
        # self.acqTime.setReadOnly(True)

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
        # self.layout.addWidget(self.timeLabel, 0, 0)
        # self.layout.addWidget(self.acqTime, 0, 1)
        self.layout.addWidget(self.xFOVLabel, 1, 0)
        self.layout.addWidget(self.xFOVs, 1, 1)
        self.layout.addWidget(self.yFOVLabel, 2, 0)
        self.layout.addWidget(self.yFOVs, 2, 1)
        self.layout.addWidget(self.Button, 3, 1)
        self.setLayout(self.layout)

        self.registerField('finalCheck*',self.Button)

    def initializePage(self):
        ''' Here, the acquisition list is created for further checking'''
        self.parent.update_acquisition_list()
        self.xFOVs.setText(str(self.parent.x_image_count))
        self.yFOVs.setText(str(self.parent.y_image_count))

class FinishedTilingPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Finished!")
        self.setSubTitle("Attention: This will overwrite the Acquisition Table. Click 'Finished' to continue. To rename the files, use the filename wizard.")

    def validatePage(self):
        print('Update parent table')
        return True


if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    wizard = MyWizard()
    sys.exit(app.exec_())
