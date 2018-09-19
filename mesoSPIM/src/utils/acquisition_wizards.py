'''
Contains Acquisition Wizard Classes:

Widgets that take user input and create acquisition lists

'''
import numpy as np
import pprint

from PyQt5 import QtWidgets, QtGui, QtCore

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
        self.laser = ''
        self.intensity = 0
        self.filter = ''
        self.shutter = ''
        self.theta_pos = 0
        self.f_pos = 0
        self.x_image_count = 1
        self.y_image_count = 1

        self.acquisition_time = 0

        self.setWindowTitle('Tiling Wizard')

        self.addPage(TilingWelcomePage(self))
        self.addPage(ZeroingXYStagePage(self))
        self.addPage(DefineXYPositionPage(self))
        # self.addPage(DefineXYStartPositionPage(self))
        # self.addPage(DefineXYEndPositionPage(self))
        self.addPage(DefineZPositionPage(self))
        self.addPage(OtherAcquisitionParametersPage(self))
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
            self.print_dict()
            self.update_model(self.parent.model, self.acq_list)
            self.parent.update_persistent_editors()
            self.wizard_done.emit()
        else:
            print('Wizard provided return code: ', r)

        super().done(r)

    def update_model(self, model, table):
        model.setTable(table)

    def update_image_counts(self):
        ''' This needs some FOV information'''
        delta_x = abs(self.x_end - self.x_start)
        delta_y = abs(self.y_end - self.y_start)

        self.x_image_count = int(np.rint(delta_x/self.x_offset))
        self.y_image_count = int(np.rint(delta_y/self.y_offset))

    def update_fov(self):
        zoom = self.zoom
        index = self.parent.cfg.zoom_options.index(zoom)
        self.x_fov = self.parent.cfg.zoom_options[index]
        self.y_fov = self.parent.cfg.zoom_options[index]

    def get_dict(self):
        return {'x_start' : self.x_start,
                'x_end' : self.x_end,
                'y_start' : self.y_start,
                'y_end' : self.y_end,
                'z_start' : self.z_start,
                'z_end' : self.z_end,
                'z_step' : self.z_step,
                'theta_pos' : self.theta_pos,
                'f_pos' : self.f_pos,
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
                'shutter' : self.shutter,
                }

    def update_acquisition_list(self):
        self.update_image_counts()
        self.update_fov()
        dict = self.get_dict()
        self.acq_list = TilingAcquisitionListBuilder(dict).get_acquisition_list()
        self.acquisition_time = self.acq_list.get_acquisition_time()

        pprint.pprint(self.acq_list)

    def print_dict(self):
        pprint.pprint(self.get_dict())


class TilingWelcomePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle("Welcome to the tiling wizard")
        self.setSubTitle("This wizard will guide you through the steps of \
        creating a tiling acquisition.")

class ZeroingXYStagePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle("Zero stage positions")
        self.setSubTitle("To aid in relative positioning, the stages have to be zeroed in XY")

        self.button = QtWidgets.QPushButton(self)
        self.button.setText('Zero XY stages')
        self.button.setCheckable(True)

        self.registerField('stages_zeroed*',
                            self.button,
                            )

        try:
            '''
            The first level parent is the QWizard
            The second level parent is the Window - which can send zeroing signals
            '''
            self.button.toggled.connect(parent.parent.zero_xy.emit)
        except:
            print('Zeroing connection failed')

class DefineXYPositionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define top left XY Position")
        self.setSubTitle("Move XY stages to the top left position")

        self.button0 = QtWidgets.QPushButton(self)
        self.button0.setText('Set XY (top left) startpoint')
        self.button0.setCheckable(True)
        self.button0.toggled.connect(self.get_xy_start_position)

        self.button1 = QtWidgets.QPushButton(self)
        self.button1.setText('Set XY (bottom right) endpoint')
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
        ''' parent.parent.model is the model
        TODO: Has to be reimplemented

        This is risky in case the API breaks. Here, submodules need
        information about parent's parents - not that great.
        '''
        pass
        # self.parent.x_start = self.parent.parent.model.position['x_pos']
        # self.parent.y_start = self.parent.parent.model.position['y_pos']

    def get_xy_end_position(self):
        ''' parent.parent.model is the model

        This is risky in case the API breaks. Here, submodules need
        information about parent's parents - not that great.
        '''
        pass
        # self.parent.x_end = self.parent.parent.model.position['x_pos']
        # self.parent.y_end = self.parent.parent.model.position['y_pos']

class DefineXYStartPositionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define top left XY Position")
        self.setSubTitle("Move XY stages to the top left position")

        self.button = QtWidgets.QPushButton(self)
        self.button.setText('Set XY (top left) startpoint')
        self.button.setCheckable(True)
        self.button.toggled.connect(self.get_xy_start_position)

        self.registerField('xy_start_position*',
                            self.button,
                            )

    def get_xy_start_position(self):
        ''' parent.parent.model is the model
        TODO: Has to be reimplemented

        This is risky in case the API breaks. Here, submodules need
        information about parent's parents - not that great.
        '''
        pass
        # self.parent.x_start = self.parent.parent.model.position['x_pos']
        # self.parent.y_start = self.parent.parent.model.position['y_pos']

class DefineXYEndPositionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define top left XY Position")
        self.setSubTitle("Move XY stages to the bottom right position")

        self.button = QtWidgets.QPushButton(self)
        self.button.setText('Set XY (bottom right) endpoint')
        self.button.setCheckable(True)
        self.button.toggled.connect(self.get_xy_end_position)

        self.registerField('xy_end_position*',
                            self.button,
                            )

    def get_xy_end_position(self):
        ''' parent.parent.model is the model

        This is risky in case the API breaks. Here, submodules need
        information about parent's parents - not that great.
        '''
        pass
        # self.parent.x_end = self.parent.parent.model.position['x_pos']
        # self.parent.y_end = self.parent.parent.model.position['y_pos']

class DefineZPositionPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define start & end Z position")
        self.setSubTitle("Move Z stages to the start & end position")

        self.z_start_button = QtWidgets.QPushButton(self)
        self.z_start_button.setText('Set Z start')
        self.z_start_button.setCheckable(True)
        self.z_start_button.toggled.connect(self.update_z_start_position)

        self.z_end_button = QtWidgets.QPushButton(self)
        self.z_end_button.setText('Set Z end')
        self.z_end_button.setCheckable(True)
        self.z_end_button.toggled.connect(self.update_z_end_position)

        self.z_spinbox_label = QtWidgets.QLabel('Z stepsize')

        self.z_step_spinbox = QtWidgets.QSpinBox(self)
        self.z_step_spinbox.setValue(1)
        self.z_step_spinbox.setMinimum(1)
        self.z_step_spinbox.setMaximum(1000)
        self.z_step_spinbox.valueChanged.connect(self.update_z_step)

        self.focus_button = QtWidgets.QPushButton(self)
        self.focus_button.setText('Set Focus')
        self.focus_button.setCheckable(True)
        self.focus_button.toggled.connect(self.update_focus_position)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.z_start_button, 0, 0)
        self.layout.addWidget(self.z_end_button, 0, 1)
        self.layout.addWidget(self.z_spinbox_label, 2, 0)
        self.layout.addWidget(self.z_step_spinbox, 2, 1)
        self.layout.addWidget(self.focus_button, 3, 0)
        self.setLayout(self.layout)

        self.registerField('z_start_position*',
                            self.z_start_button,
                            )

        self.registerField('z_end_position*',
                            self.z_end_button,
                            )

        self.registerField('focus_position*',
                            self.focus_button,
                            )

    def update_z_start_position(self):
        ''' parent.parent.model is the model

        This is risky in case the API breaks. Here, submodules need
        information about parent's parents - not that great.
        '''
        pass
        # self.parent.z_start = self.parent.parent.model.position['z_pos']

    def update_z_end_position(self):
        ''' parent.parent.model is the model

        This is risky in case the API breaks. Here, submodules need
        information about parent's parents - not that great.
        '''
        pass
        # self.parent.z_end = self.parent.parent.model.position['z_pos']

    def update_z_step(self):
        pass
        # self.parent.z_step = self.z_step_spinbox.value()

    def update_focus_position(self):
        pass
        # self.parent.f_pos = self.parent.parent.model.position['f_pos']

class OtherAcquisitionParametersPage(QtWidgets.QWizardPage):
    '''

    TODO: Needs a button: Take current parameters from Live or so
    '''

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Define other parameters")
        self.setSubTitle("Set zoom, shutter, laser, intensity")

        self.zoomLabel = QtWidgets.QLabel('Zoom')
        self.zoomComboBox = QtWidgets.QComboBox(self)
        self.zoomComboBox.addItems(sefl.parent.cfg.zoom_options)

        self.laserLabel = QtWidgets.QLabel('Laser')
        self.laserComboBox = QtWidgets.QComboBox(self)
        self.laserComboBox.addItems(sefl.parent.cfg.laser_options)

        self.intensityLabel = QtWidgets.QLabel('Intensity')
        self.intensitySlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.intensitySlider.setMinimum(0)
        self.intensitySlider.setMaximum(100)

        self.filterLabel = QtWidgets.QLabel('Filter')
        self.filterComboBox = QtWidgets.QComboBox(self)
        self.filterComboBox.addItems(sefl.parent.cfg.filter_options)

        self.shutterLabel = QtWidgets.QLabel('Shutter')
        self.shutterComboBox = QtWidgets.QComboBox(self)
        self.shutterComboBox.addItems(sefl.parent.cfg.shutter_options)

        self.xyOffsetSpinBoxLabel = QtWidgets.QLabel('XY Offset')
        self.xyOffsetSpinBox = QtWidgets.QSpinBox(self)
        self.xyOffsetSpinBox.setValue(100)
        self.xyOffsetSpinBox.setSuffix(' μm')
        self.xyOffsetSpinBox.setMinimum(1)
        self.xyOffsetSpinBox.setMaximum(20000)

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
        self.layout.addWidget(self.xyOffsetSpinBoxLabel, 5, 0)
        self.layout.addWidget(self.xyOffsetSpinBox, 5, 1)
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
        self.parent.x_fov = self.parent.cfg.fov_options[self.zoomComboBox.currentIndex()]
        self.parent.y_fov = self.parent.cfg.fov_options[self.zoomComboBox.currentIndex()]
        self.parent.x_offset = self.xyOffsetSpinBox.value()
        self.parent.y_offset = self.xyOffsetSpinBox.value()
        self.parent.laser = self.laserComboBox.currentText()
        self.parent.intensity = self.intensitySlider.value()
        self.parent.filter = self.filterComboBox.currentText()
        self.parent.shutter = self.shutterComboBox.currentText()

class CheckTilingPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Check Tiling Page")
        self.setSubTitle("Here are your parameters")

        self.timeLabel = QtWidgets.QLabel('Acquisition Time:')
        self.acqTime = QtWidgets.QLineEdit(self)
        self.acqTime.setReadOnly(True)

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
        self.layout.addWidget(self.timeLabel, 0, 0)
        self.layout.addWidget(self.acqTime, 0, 1)
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
        self.acqTime.setText(str(round(self.parent.acquisition_time,2))+' s')
        self.xFOVs.setText(str(self.parent.x_image_count))
        self.yFOVs.setText(str(self.parent.y_image_count))

class FinishedTilingPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Finished!")
        self.setSubTitle("Attention: This will overwrite the \
        Acquisition Table. Click 'Finished' to continue.")

    def validatePage(self):
        print('Update parent table')
        return True


if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    wizard = MyWizard()
    sys.exit(app.exec_())
