'''
Contains Focus Tracking Wizard Class: autogenerates start end end foci from reference / anchor positions

'''

from PyQt5 import QtWidgets, QtGui, QtCore

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty

from ..mesoSPIM_State import mesoSPIM_StateSingleton

class FocusTrackingWizard(QtWidgets.QWizard):
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

        self.f_1 = 0
        self.f_2 = 0
        self.z_1 = 0
        self.z_2 = 0
        
        self.setWindowTitle('Foucs Tracking Wizard')

        self.addPage(FocusTrackingWizardWelcomePage(self))
        self.addPage(FocusTrackingWizardSetReferencePointsPage(self))
        self.addPage(FocusTrackingWizardCheckResultsPage(self))
        
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
            # print('Laser selected: ', self.field('Laser'))
            self.update_focus_positions_in_model()
        else:
            print('Wizard provided return code: ', r)

        super().done(r)

    def calculate_f_pos(self, z_1, z_2, f_1, f_2, z):
        if z_2 == z_1:
            ''' Avoid division by zero '''
            return 0
        else:
            return (f_2-f_1)/(z_2-z_1)*(z-z_1)+f_1

    def convert_string_to_list(self, inputstring):
        outputlist = []
        for substring in inputstring.split(','):
            newlist = substring.split('-')
            if len(newlist) == 1:
                output_values = [int(newlist[0])]
            else:
                output_values = [i for i in range(int(newlist[0]), int(newlist[1])+1, 1)]
            outputlist.extend(output_values)
        return outputlist       

    
    def update_focus_positions_in_model(self):
        row_count = self.parent.model.rowCount()
        z_start_column =  self.parent.model.getColumnByName('Z_start')
        z_end_column = self.parent.model.getColumnByName('Z_end')
        f_start_column = self.parent.model.getColumnByName('F_start')
        f_end_column = self.parent.model.getColumnByName('F_end')
        filter_column = self.parent.model.getColumnByName('Filter')
        laser_column = self.parent.model.getColumnByName('Laser')

        if self.field('RowEnabled'):
            row_list = self.convert_string_to_list(self.field('RowString'))

        for row in range(0, row_count):
            z_start = self.parent.model.getZStartPosition(row)
            z_end = self.parent.model.getZEndPosition(row)

            f_start = self.calculate_f_pos(self.z_1, self.z_2, self.f_1, self.f_2, z_start)
            f_end = self.calculate_f_pos(self.z_1, self.z_2, self.f_1, self.f_2, z_end)

            f_start_index = self.parent.model.createIndex(row, f_start_column)
            f_end_index = self.parent.model.createIndex(row, f_end_column)

            if self.field('LaserEnabled'):
                print('Laser is enabled')
                if self.field('Laser') == 'All laser lines':
                    print('All laser lines')
                    self.parent.model.setData(f_start_index, f_start)
                    self.parent.model.setData(f_end_index, f_end)
                else: 
                    print('Laserfield: ', self.field('Laser'))
                    print('Laser in row: ', self.parent.model.getLaser(row))
                    if self.field('Laser') == self.parent.model.getLaser(row):
                        self.parent.model.setData(f_start_index, f_start)
                        self.parent.model.setData(f_end_index, f_end)

            elif self.field('FilterEnabled'):
                if self.field('Filter') == 'All filters':
                    self.parent.model.setData(f_start_index, f_start)
                    self.parent.model.setData(f_end_index, f_end)
                else:
                    if self.field('Filter') == self.parent.model.getFilter(row):
                        self.parent.model.setData(f_start_index, f_start)
                        self.parent.model.setData(f_end_index, f_end)

            elif self.field('RowEnabled'):
                if row in row_list:
                    self.parent.model.setData(f_start_index, f_start)
                    self.parent.model.setData(f_end_index, f_end)
            

class FocusTrackingWizardWelcomePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Welcome to the focus tracking wizard!")
        self.setSubTitle("This wizard allows you to set the correct focus start and end points by focusing manually at two reference points inside the sample. ATTENTION: In the last step, you can apply the focus range to selected channels and lasers!")
    
class FocusTrackingWizardSetReferencePointsPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Reference point definition")
        self.setSubTitle("Between z_start and z_end, focus the microscope at two different z-positions inside the sample.")

        self.button0 = QtWidgets.QPushButton(self)
        self.button0.setText('Set first reference point')
        self.button0.setCheckable(True)
        self.button0.toggled.connect(self.get_first_reference_point)

        self.button1 = QtWidgets.QPushButton(self)
        self.button1.setText('Set second reference point')
        self.button1.setCheckable(True)
        self.button1.toggled.connect(self.get_second_reference_point)

        self.registerField('set_first_refpoint*',
                            self.button0,
                            )
        self.registerField('set_second_refpoint*',
                            self.button1,
                            )

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.button0, 0, 0)
        self.layout.addWidget(self.button1, 0, 1)
        self.setLayout(self.layout)

    def get_first_reference_point(self):
        self.parent.f_1 = self.parent.state['position']['f_pos']
        self.parent.z_1 = self.parent.state['position']['z_pos']
        
    def get_second_reference_point(self):
        self.parent.f_2 = self.parent.state['position']['f_pos']
        self.parent.z_2 = self.parent.state['position']['z_pos']

    def validatePage(self):
        '''Further validation operations can be introduced here'''
        return super().validatePage()

class FocusTrackingWizardCheckResultsPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle('To which acquisitions should the focus settings be applied?')

        self.laserCheckBox = QtWidgets.QCheckBox('Rows with laser set to: ', self)
        self.laserComboBox = QtWidgets.QComboBox(self)
        self.laserComboBox.addItem('All laser lines')
        self.laserComboBox.addItems(self.parent.cfg.laserdict.keys())

        self.filterCheckBox = QtWidgets.QCheckBox('Rows with filter set to:', self)
        self.filterComboBox = QtWidgets.QComboBox(self)
        self.filterComboBox.addItem('All filters')
        self.filterComboBox.addItems(self.parent.cfg.filterdict.keys())

        self.rowCheckBox = QtWidgets.QCheckBox('Specific rows (e.g. 0-2,5-7,10,13):',self)
        self.rowLineEdit = QtWidgets.QLineEdit(self)
        
        self.registerField('LaserEnabled',self.laserCheckBox)
        self.registerField('FilterEnabled', self.filterCheckBox)
        self.registerField('RowEnabled', self.rowCheckBox)
        self.registerField('Laser',self.laserComboBox, 'currentText', self.laserComboBox.currentTextChanged)
        self.registerField('Filter', self.filterComboBox, 'currentText', self.filterComboBox.currentTextChanged)
        self.registerField('RowString', self.rowLineEdit)

        self.laserCheckBox.clicked.connect(lambda boolean: self.laserComboBox.setEnabled(boolean))
        self.laserCheckBox.clicked.connect(lambda boolean: self.filterCheckBox.setChecked(not boolean))
        self.laserCheckBox.clicked.connect(lambda boolean: self.filterComboBox.setEnabled(not boolean))
        self.laserCheckBox.clicked.connect(lambda boolean: self.rowLineEdit.setEnabled(not boolean))
        self.laserCheckBox.clicked.connect(lambda boolean: self.rowCheckBox.setChecked(not boolean))
        
        self.filterCheckBox.clicked.connect(lambda boolean: self.filterComboBox.setEnabled(boolean))
        self.filterCheckBox.clicked.connect(lambda boolean: self.laserCheckBox.setChecked(not boolean))
        self.filterCheckBox.clicked.connect(lambda boolean: self.laserComboBox.setEnabled(not boolean))
        self.filterCheckBox.clicked.connect(lambda boolean: self.rowLineEdit.setEnabled(not boolean))
        self.filterCheckBox.clicked.connect(lambda boolean: self.rowCheckBox.setChecked(not boolean))
        
        self.rowCheckBox.clicked.connect(lambda boolean: self.rowLineEdit.setEnabled(boolean))
        self.rowCheckBox.clicked.connect(lambda boolean: self.laserComboBox.setEnabled(not boolean))
        self.rowCheckBox.clicked.connect(lambda boolean: self.filterComboBox.setEnabled(not boolean))
        self.rowCheckBox.clicked.connect(lambda boolean: self.laserCheckBox.setChecked(not boolean))
        self.rowCheckBox.clicked.connect(lambda boolean: self.filterCheckBox.setChecked(not boolean))

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.laserCheckBox, 0, 0)
        self.layout.addWidget(self.laserComboBox, 0, 1)
        self.layout.addWidget(self.filterCheckBox, 1, 0)
        self.layout.addWidget(self.filterComboBox, 1, 1)
        self.layout.addWidget(self.rowCheckBox, 2, 0)
        self.layout.addWidget(self.rowLineEdit, 2, 1)
        self.setLayout(self.layout)

    def initializePage(self):
        self.laserComboBox.setCurrentText(self.parent.state['laser'])
        self.filterComboBox.setCurrentText(self.parent.state['filter'])

        self.laserCheckBox.setChecked(True)
        self.filterComboBox.setEnabled(False)
        self.rowLineEdit.setEnabled(False)






        
    