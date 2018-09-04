'''
mesoSPIM Acquisition Manager Window
===================================
'''
import os
import sys

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi

''' mesoSPIM imports '''
from .utils.models import AcquisitionModel

from .utils.delegates import (ComboDelegate,
                        SliderDelegate,
                        MarkXPositionDelegate,
                        MarkYPositionDelegate,
                        MarkZPositionDelegate,
                        MarkFocusPositionDelegate,
                        ProgressBarDelegate,
                        ZstepSpinBoxDelegate,
                        SliderWithValueDelegate)

from .utils.widgets import MarkPositionWidget

from .utils.acquisition_wizards import TilingWizard

class MyStyle(QtWidgets.QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        '''
        Draw a line across the entire row rather than just the column
        we're hovering over.  
        '''
        if element == self.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
            option_new = QtWidgets.QStyleOption(option)
            option_new.rect.setLeft(0)
            if widget:
                option_new.rect.setRight(widget.width())
            option = option_new
        super().drawPrimitive(element, option, painter, widget)

class mesoSPIM_AcquisitionManagerWindow(QtWidgets.QWidget):

    model_changed = QtCore.pyqtSignal(AcquisitionModel)

    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent
        self.cfg = parent.cfg

        loadUi('gui/mesoSPIM_AcquisitionManagerWindow.ui', self)
        self.setWindowTitle('mesoSPIM Acquisition Manager')

        # self.moveUpButton.clicked.connect(self.move_selected_row_up)
        # self.moveDownButton.clicked.connect(self.move_selected_row_down)
        #
        # ''' Setting the model up '''
        # self.model = AcquisitionModel()
        #
        # self.table.setModel(self.model)
        # self.model.dataChanged.connect(self.update_model_data)
        #
        # ''' Table selection behavior '''
        # self.table.setSelectionBehavior(self.table.SelectRows)
        # self.table.setSelectionMode(self.table.ExtendedSelection)
        # self.table.setDragDropMode(self.table.InternalMove)
        # self.table.setDragDropOverwriteMode(False)
        # self.table.setDragEnabled(True)
        # self.table.setAcceptDrops(True)
        # self.table.setDropIndicatorShown(True)
        # self.table.setSortingEnabled(True)
        #
        # self.set_item_delegates()
        #
        # ''' Set our custom style - this draws the drop indicator across the whole row '''
        # self.table.setStyle(MyStyle())
        #
        # self.selection_model = self.table.selectionModel()
        # self.selection_mapper = QtWidgets.QDataWidgetMapper()
        #
        # self.update_persistent_editors()
