'''
Contains Image Processing Wizard Class: Sets online processing options

'''

from PyQt5 import QtWidgets, QtGui, QtCore

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtProperty

from ..mesoSPIM_State import mesoSPIM_StateSingleton

class ImageProcessingWizard(QtWidgets.QWizard):
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
  
        self.setWindowTitle('Image Processing Wizard')

        self.addPage(ImageProcessingWizardWelcomePage(self))
        self.addPage(ImageProcessingWizardSetOptionsPage(self))
        self.addPage(ImageProcessingWizardCheckResultsPage(self))
        
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
            self.set_processing_options()
        else:
            print('Wizard provided return code: ', r)

        super().done(r)

    def set_processing_options(self):
        row_count = self.parent.model.rowCount()
        processing_column = self.parent.model.getColumnByName('Processing')
         
        for row in range(0, row_count):
            index = self.parent.model.createIndex(row, processing_column)
            if self.field('maxProjEnabled'):
                self.parent.model.setData(index, 'MAX')
            else:
                self.parent.model.setData(index,  '')

class ImageProcessingWizardWelcomePage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Welcome to the image processing wizard!")
        self.setSubTitle("This wizard allows you to set image processing flags!")
    
class ImageProcessingWizardSetOptionsPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle("Select processing options")
        #self.setSubTitle("Select the processing options:")

        self.maxProjectionCheckBox = QtWidgets.QCheckBox('Post-stack MAX projection (adds time)', self)
        
        self.registerField('maxProjEnabled',self.maxProjectionCheckBox)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.maxProjectionCheckBox, 0, 0)
        self.setLayout(self.layout)

    def validatePage(self):
        '''Further validation operations can be introduced here'''
        return super().validatePage()

class ImageProcessingWizardCheckResultsPage(QtWidgets.QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setTitle('Options have been set')
        


        
    