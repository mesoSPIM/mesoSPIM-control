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

        self.moveUpButton.clicked.connect(self.move_selected_row_up)
        self.moveDownButton.clicked.connect(self.move_selected_row_down)

        ''' Setting the model up '''
        self.model = AcquisitionModel()

        self.table.setModel(self.model)
        self.model.dataChanged.connect(self.update_model_data)

        ''' Table selection behavior '''
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.ExtendedSelection)
        self.table.setDragDropMode(self.table.InternalMove)
        self.table.setDragDropOverwriteMode(False)
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setSortingEnabled(True)

        self.set_item_delegates()

        ''' Set our custom style - this draws the drop indicator across the whole row '''
        self.table.setStyle(MyStyle())

        self.selection_model = self.table.selectionModel()
        self.selection_mapper = QtWidgets.QDataWidgetMapper()

        self.update_persistent_editors()

        self.addButton.clicked.connect(self.add_row)
        self.deleteButton.clicked.connect(self.delete_row)
        self.copyButton.clicked.connect(self.copy_row)

        self.saveButton.clicked.connect(self.save_table)
        self.loadButton.clicked.connect(self.load_table)

    def display_status_message(self, string, time=0):
        '''
        Displays a message in the status bar for a time in ms

        If time=0, the message will stay.
        '''

        if time == 0:
            self.statusBar().showMessage(string)
        else:
            self.statusBar().showMessage(string, time)

    def get_first_selected_row(self):
        ''' Little helper method to provide the first row out of a selection range '''
        try:
            indices = self.selection_model.selectedIndexes()
            rows = self.selection_model.selectedRows()
            row = indices[0].row()
        except:
            row = None

        return row

    def set_selected_row(self, row):
        ''' Little helper method to allow setting the selected row '''
        index = self.model.createIndex(row,0)
        # self.selection_model.clearCurrentIndex()
        self.selection_model.select(index,QtCore.QItemSelectionModel.ClearAndSelect)

    def start_selected(self):
        ''' Get the selected row and run this (single) row only

        Indices is a list of selected QModelIndex objects, we're only interested
        in the first.
        '''
        self.disable_gui()
        row = self.get_first_selected_row()
        if row is not None:
            self.sig_start_selected.emit(row)
        else:
            print('No row selected!')

    def add_row(self):
        self.model.insertRows(self.model.rowCount(),1)
        self.update_model_data()
        self.update_persistent_editors()

    def delete_row(self):
        ''' Deletes the selected row '''
        if self.model.rowCount() > 1:
            row = self.get_first_selected_row()
            if row is not None:
                self.model.removeRows(row,1)
            else:
                print('No row selected!')
        else:
            self.display_status_message("Can't delete last row!", 2)
        self.update_model_data()
        self.update_persistent_editors()

    def copy_row(self):
        row = self.get_first_selected_row()
        if row is not None:
            self.model.copyRow(row)
        else:
            print('No row selected!')

    def move_selected_row_up(self):
        row = self.get_first_selected_row()
        if row is not None:
            if row > 0:
                self.model.moveRow(QtCore.QModelIndex(),row,QtCore.QModelIndex(),row-1)
                self.set_selected_row(row-1)
        else:
            print('No row selected!')

    def move_selected_row_down(self):
        row = self.get_first_selected_row()
        if row is not None:
            if row < self.model.rowCount():
                self.model.moveRow(QtCore.QModelIndex(),row,QtCore.QModelIndex(),row+1)
                self.set_selected_row(row+1)
        else:
            print('No row selected!')

    def set_item_delegates(self):
        ''' Several columns should have certain delegates

        If I decide to move colums, the delegates should move with them

        Here, I need the configuration to provide the options for the
        delegates.
        '''
        self.delegate_dict = {'x_pos' :  'MarkXPositionDelegate(self)',
                              'y_pos' : 'MarkYPositionDelegate(self)',
                              'z_start' : 'MarkZPositionDelegate(self)',
                              'z_end' : 'MarkZPositionDelegate(self)',
                              'z_step' : 'ZstepSpinBoxDelegate(self)',
                              'f_pos' : 'MarkFocusPositionDelegate(self)',
                              'filter' : 'ComboDelegate(self,[key for key in self.cfg.filterdict.keys()])',
                              'intensity' : 'SliderWithValueDelegate(self)',
                              'laser' : 'ComboDelegate(self,[key for key in self.cfg.laserdict.keys()])',
                              'zoom' : 'ComboDelegate(self,[key for key in self.cfg.zoomdict.keys()])',
                              'shutter' : 'ComboDelegate(self,[key for key in self.cfg.shutteroptions])',
                              }

        self.persistent_editor_column_indices=[]
        ''' Go through the dictionary keys of the

        self.model._table[0].

        find the index of a certain key and set the delegate accordingly

        '''
        for key in self.delegate_dict :
            column_index = self.model._table[0].keys().index(key)
            ''' As some of the delegates expect options, a hack using exec was used: '''
            string_to_execute = 'self.table.setItemDelegateForColumn(column_index,'+self.delegate_dict[key]+')'
            delegate_object = exec(self.delegate_dict[key])

            self.persistent_editor_column_indices.append(column_index)
            exec(string_to_execute)

    def update_persistent_editors(self):
        '''
        Go through all the rows and all necessary columns and
        open persistent editors.
        '''

        for row in range(0, self.model.rowCount()):
            for column in self.persistent_editor_column_indices:
                self.table.openPersistentEditor(self.model.index(row, column))

    def update_model_data(self):
        print('Model in GUI thread updated, sending signal')
        self.model_changed.emit(self.model)

    @QtCore.pyqtSlot(AcquisitionModel)
    def update_model_from_worker(self, model):
        print('Model in the Aquisition Manager updated via signal')
        self.model = model
        self.update_persistent_editors()

    def enable_gui(self):
        ''' Enables all GUI controls, disables stop button '''
        self.table.setEnabled(True)
        self.tableControlButtons.setEnabled(True)
        self.generalControlButtons.setEnabled(True)

    def disable_gui(self):
        ''' Disables all buttons and controls, enables stop button '''
        self.table.setEnabled(False)
        self.tableControlButtons.setEnabled(False)
        self.generalControlButtons.setEnabled(False)

    def save_table(self):
        path , _ = QtWidgets.QFileDialog.getSaveFileName(None,'Save Table')
        if path:
            self.model.saveModel(path)

    def load_table(self):
        path , _ = QtWidgets.QFileDialog.getOpenFileName(None,'Load Table')
        if path:
            self.model.loadModel(path)
            self.update_persistent_editors()

    def run_my_wizard(self):
        wizard = MyWizard(self)

        #print('Name: ', name, 'Email: ', email)

    def run_tiling_wizard(self):
        wizard = TilingWizard(self)
