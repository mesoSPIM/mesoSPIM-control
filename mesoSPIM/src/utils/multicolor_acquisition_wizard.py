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

    num_of_pages = 11
    (welcome, zeroing, boundingbox, generalparameters, checktiling, channel1, 
    channel2, channel3, multiplexpage, folderpage, finished) = range(num_of_pages)

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
        self.LoopOrder = [0,1,2]
        self.illumination = 0
        
        self.setWindowTitle('Tiling Wizard')

        self.setPage(0, TilingWelcomePage(self))
        self.setPage(1, ZeroingXYStagePage(self))
        self.setPage(2, DefineBoundingBoxPage(self))
        self.setPage(3, DefineGeneralParametersPage(self))
        self.setPage(4, CheckTilingPage(self))
        self.setPage(5, FirstChannelPage(self))
        self.setPage(6, SecondChannelPage(self))
        self.setPage(7, ThirdChannelPage(self))
        self.setPage(8, MultiplexPage(self))
        self.setPage(9, DefineFolderPage(self))
        self.setPage(10, FinishedTilingPage(self))

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
                'loop_order': self.LoopOrder,
                'illumination': self.illumination,
                'image_size': self.image_size
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

        '''
            06.02.2020 This part was changed by Tzu-Lun Ohn
            The xOffset and yOffset were replaced to overlap to adapt to the habit of Ertürk's lab
            Todo:
            checked the overlap in LaVision: whether it is overlap on both side or one side
        '''
        self.xOverlapSpinBoxLabel = QtWidgets.QLabel('X Overlap')
        self.xOverlapSpinBox = QtWidgets.QSpinBox(self)
        self.xOverlapSpinBox.setSuffix(' %')
        self.xOverlapSpinBox.setMinimum(0)
        self.xOverlapSpinBox.setMaximum(99)
        self.xOverlapSpinBox.setValue(10)

        self.yOverlapSpinBoxLabel = QtWidgets.QLabel('Y Overlap')
        self.yOverlapSpinBox = QtWidgets.QSpinBox(self)
        self.yOverlapSpinBox.setSuffix(' %')
        self.yOverlapSpinBox.setMinimum(0)
        self.yOverlapSpinBox.setMaximum(99)
        self.yOverlapSpinBox.setValue(10)

        Illumination_methods = {'left': 0, 'right': 1,'interleaved' : 2, 'automatic determination' : 3} 

        self.shutterLabel = QtWidgets.QLabel('Illumination method')
        self.shutterComboBox = QtWidgets.QComboBox(self)
        self.shutterComboBox.addItems(Illumination_methods.keys())

        self.channelLabel = QtWidgets.QLabel('# Channels')
        self.channelSpinBox = QtWidgets.QSpinBox(self)
        self.channelSpinBox.setMinimum(1)
        self.channelSpinBox.setMaximum(3)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.zoomLabel, 0, 0)
        self.layout.addWidget(self.zoomComboBox, 0, 1)
        self.layout.addWidget(self.shutterLabel, 1, 0)
        self.layout.addWidget(self.shutterComboBox, 1, 1)
        self.layout.addWidget(self.xOverlapSpinBoxLabel, 2, 0)
        self.layout.addWidget(self.xOverlapSpinBox, 2, 1)
        self.layout.addWidget(self.yOverlapSpinBoxLabel, 3, 0)
        self.layout.addWidget(self.yOverlapSpinBox, 3, 1)
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
        self.parent.image_size = self.image_sizer()
        self.parent.x_offset = round(self.parent.image_size[0] - self.xOverlapSpinBox.value()*self.parent.image_size[0]/100)
        self.parent.y_offset = round(self.parent.image_size[1] - self.yOverlapSpinBox.value()*self.parent.image_size[1]/100)
        self.parent.shutterconfig = self.shutterComboBox.currentText()
        self.parent.channelcount = self.channelSpinBox.value()
        self.parent.illumination = self. shutterComboBox.currentIndex()
        

    def initializePage(self):
        self.update_page_from_state()

    def update_page_from_state(self):
        self.zoomComboBox.setCurrentText(self.parent.state['zoom'])
        self.shutterComboBox.setCurrentText(self.parent.state['shutterconfig'])

    def image_sizer(self):
        cfg = self.parent.cfg
        zoom_str = self.parent.zoom  
        ints = zoom_str.find('.')
        decimals = zoom_str.find('x')
    
        # This part is used to get the number of zoom from the string
        if ints == -1:
            zoom = int(zoom_str[0:decimals])
        else:
            zoom = int(zoom_str[0:ints])+int(zoom_str[ints+1:decimals])*10**(ints-decimals+1)

        camera_pixel_size_x = cfg.camera_parameters['x_pixel_size_in_microns']
        camera_pixel_size_y = cfg.camera_parameters['y_pixel_size_in_microns']
        camera_pixel_number_x = cfg.camera_parameters['x_pixels']
        camera_pixel_number_y = cfg.camera_parameters['y_pixels']
        chip_size_x = camera_pixel_size_x * camera_pixel_number_x
        chip_size_y = camera_pixel_size_y * camera_pixel_number_y
        image_size = [chip_size_x/zoom, chip_size_y/zoom]
    
        return image_size

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
            return self.parent.multiplexpage
        else: 
            return self.parent.channel2 

class SecondChannelPage(GenericChannelPage):
    def __init__(self, parent=None):
        super().__init__(parent, 1)

    def nextId(self):
        if self.parent.channelcount == 2:
            return self.parent.multiplexpage
        else: 
            return self.parent.channel3 

class ThirdChannelPage(GenericChannelPage):
    def __init__(self, parent=None):
        super().__init__(parent, 2)

    def nextId(self):
        return self.parent.multiplexpage

class MultiplexPage(QtWidgets.QWizardPage):
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setTitle("Multiplex choice")
        self.setSubTitle("Please choose your looping order in the following drop-down menu")

        self.current_ComboBox = {'please select' : 0, 'x move' : 1,'y move' : 2,'fluorescence channel' : 3}
        
        self.MultiplexComboBox1 = QtWidgets.QComboBox()
        self.MultiplexComboBox1.addItems(self.current_ComboBox.keys())      
        self.MultiplexComboBox1.setCurrentIndex(0) 

        self.MultiplexComboBox2 = QtWidgets.QComboBox()        
        self.MultiplexComboBox2.addItems(self.current_ComboBox.keys())
        self.MultiplexComboBox2.setCurrentIndex(0) 
        
        self.MultiplexComboBox3 = QtWidgets.QComboBox()        
        self.MultiplexComboBox3.addItems(self.current_ComboBox.keys())
        self.MultiplexComboBox3.setCurrentIndex(0)
        
        self.MultiplexComboBox2.setDisabled(True) 
        self.MultiplexComboBox3.setDisabled(True)

        self.MultiplexComboBox1.currentIndexChanged.connect(lambda:self.update_dynamic_options(1))
        self.MultiplexComboBox2.currentIndexChanged.connect(lambda:self.update_dynamic_options(2))
        self.MultiplexComboBox3.currentIndexChanged.connect(lambda:self.update_dynamic_options(3))

        self.Box1_Label = QtWidgets.QLabel('First iteration choice:')
        self.Box1_Labe2 = QtWidgets.QLabel('Second iteration choice:')
        self.Box1_Labe3 = QtWidgets.QLabel('Third iteration choice:')
        self.UpdateButton = QtWidgets.QPushButton()
        self.UpdateButton.setText("set iteration order")
        self.UpdateButton.toggled.connect(self.update_Loop_Choice)
        self.UpdateButton.setCheckable(True)
        self.UpdateButton.setChecked(False)
        self.UpdateButton.setDisabled(True)
        self.registerField('LoopOrder*',self.UpdateButton)
        
        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.MultiplexComboBox1,0,1,1,2)
        self.layout.addWidget(self.MultiplexComboBox2,2,1,1,2)
        self.layout.addWidget(self.MultiplexComboBox3,4,1,1,2)
        self.layout.addWidget(self.Box1_Label,0,0)
        self.layout.addWidget(self.Box1_Labe2,2,0)
        self.layout.addWidget(self.Box1_Labe3,4,0)
        self.layout.addWidget(self.UpdateButton,6,2,1,2)
        self.setLayout(self.layout)                 

    def update_Loop_Choice(self):
        Options = {'x move' : 0,'y move' : 1,'fluorescence channel' : 2}
        Opt_1 = self.MultiplexComboBox1.currentText()
        Opt_2 = self.MultiplexComboBox2.currentText()
        Opt_3 = self.MultiplexComboBox3.currentText()
        k1 = Options[Opt_1]
        k2 = Options[Opt_2]
        k3 = Options[Opt_3]
        self.parent.LoopOrder = [k1,k2,k3]
    
    @QtCore.pyqtSlot()
    def update_dynamic_options(self,ComboBoxNr):    
        
        Iteration_options = {'please select' : 0, 'x move' : 1,'y move' : 2,'fluorescence channel' : 3}

        if ComboBoxNr == 1:
            Options_ComboBox = Iteration_options
            textStr = self.MultiplexComboBox1.currentText()
        elif ComboBoxNr == 2:
            Options_ComboBox = self.current_ComboBox
            textStr = self.MultiplexComboBox2.currentText()
        elif ComboBoxNr == 3:
            textStr = self.MultiplexComboBox3.currentText()

        if textStr == 'x move' and ComboBoxNr != 3:
            del Options_ComboBox['x move']   
        elif textStr == 'y move' and ComboBoxNr != 3:
            del Options_ComboBox['y move']   
        elif textStr == 'fluorescence channel' and ComboBoxNr != 3:
            del Options_ComboBox['fluorescence channel']
        elif textStr == "refresh options":
            self.MultiplexComboBox1.setDisabled(False)
            self.MultiplexComboBox1.blockSignals(True)
            self.MultiplexComboBox1.clear()
            self.MultiplexComboBox1.addItems(Iteration_options)
            self.MultiplexComboBox1.blockSignals(False)
            self.MultiplexComboBox3.setDisabled(True)
            self.UpdateButton.setDisabled(True) 

        if ComboBoxNr == 1:
            self.MultiplexComboBox2.blockSignals(True)
            self.MultiplexComboBox2.clear()
            self.MultiplexComboBox2.addItems(Options_ComboBox.keys())
            self.MultiplexComboBox2.blockSignals(False)
            self.current_ComboBox = Options_ComboBox
            self.MultiplexComboBox1.setDisabled(True)
            self.MultiplexComboBox2.setDisabled(False)
        elif ComboBoxNr == 2:
            self.MultiplexComboBox3.blockSignals(True)
            self.MultiplexComboBox3.clear()
            del(Options_ComboBox['please select'])
            self.MultiplexComboBox3.addItems(Options_ComboBox.keys())
            self.MultiplexComboBox3.addItems({"refresh options" : 4})
            #self.current_ComboBox = Options_ComboBox
            self.MultiplexComboBox3.blockSignals(False)
            self.MultiplexComboBox2.setDisabled(True)
            self.MultiplexComboBox3.setDisabled(False)
            self.UpdateButton.setDisabled(False)


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
    wizard = MulticolorTilingWizard()
    sys.exit(app.exec_())
