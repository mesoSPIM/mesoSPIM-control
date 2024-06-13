'''
mesoSPIM Acquisition Manager Window
===================================
'''
import os
import sys
import time
import logging
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi

''' mesoSPIM imports '''
from .mesoSPIM_State import mesoSPIM_StateSingleton
from .utils.utility_functions import format_data_size
from .utils.models import AcquisitionModel

from .utils.delegates import (ComboDelegate,
                        SliderDelegate,
                        MarkXPositionDelegate,
                        MarkYPositionDelegate,
                        MarkZPositionDelegate,
                        MarkFocusPositionDelegate,
                        ProgressBarDelegate,
                        ZstepSpinBoxDelegate,
                        IntensitySpinBoxDelegate,
                        ChooseFolderDelegate,
                        ETLSpinBoxDelegate,
                        RotationSpinBoxDelegate)

from .utils.widgets import MarkPositionWidget

from .utils.multicolor_acquisition_wizard import MulticolorTilingWizard
from .utils.filename_wizard import FilenameWizard
from .utils.focus_tracking_wizard import FocusTrackingWizard
from .utils.image_processing_wizard import ImageProcessingWizard
from .utils.utility_functions import convert_seconds_to_string
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


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
    sig_warning = QtCore.pyqtSignal(str)
    sig_move_absolute = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__()

        self.parent = parent # mesoSPIM_MainWindow instance
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        loadUi(self.parent.package_directory + '/gui/mesoSPIM_AcquisitionManagerWindow.ui', self)
        self.setWindowTitle('mesoSPIM Acquisition Manager')

        self.MoveUpButton.clicked.connect(self.move_selected_row_up)
        self.MoveDownButton.clicked.connect(self.move_selected_row_down)

        ''' Parent Enable / Disable GUI'''
        self.parent.sig_enable_gui.connect(lambda boolean: self.setEnabled(boolean))

        self.statusBar = QtWidgets.QStatusBar()

        ''' Setting the model up '''
        self.model = AcquisitionModel()

        self.table.setModel(self.model) # self.table is a QTableView object
        self.model.dataChanged.connect(self.set_state)
        self.model.dataChanged.connect(self.update_acquisition_time_prediction)
        self.model.dataChanged.connect(self.update_acquisition_size_prediction)

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

        self.AddButton.clicked.connect(self.add_row)
        self.DeleteButton.clicked.connect(self.delete_row)
        self.CopyButton.clicked.connect(self.copy_row)

        self.SaveButton.clicked.connect(self.save_table)
        self.LoadButton.clicked.connect(self.load_table)

        self.MarkCurrentXYButton.clicked.connect(self.mark_current_xy_position)
        self.MarkCurrentFocusButton.clicked.connect(self.mark_current_focus)
        self.MarkCurrentRotationButton.clicked.connect(self.mark_current_rotation)
        self.MarkCurrentStateButton.clicked.connect(self.mark_current_state)
        self.MarkCurrentETLParametersButton.clicked.connect(self.mark_current_etl_parameters)
        self.MarkAllButton.clicked.connect(self.mark_all_current_parameters)
        self.PreviewSelectionButton.clicked.connect(self.preview_acquisition)

        self.TilingWizardButton.clicked.connect(self.run_tiling_wizard)
        self.FilenameWizardButton.clicked.connect(self.generate_filenames)
        self.FocusTrackingWizardButton.clicked.connect(self.run_focus_tracking_wizard)
        self.AutoIlliminationButton.clicked.connect(self.auto_illumination)
        self.ImageProcessingWizardButton.clicked.connect(self.run_image_processing_wizard)

        self.DeleteAllButton.clicked.connect(self.delete_all_rows)
        # self.SetRotationPointButton.clicked.connect(lambda bool: self.set_rotation_point() if bool is True else self.delete_rotation_point())
        self.SetFoldersButton.clicked.connect(self.set_folder_names)

        font = QtGui.QFont()
        font.setPointSize(14)
        self.table.horizontalHeader().setFont(font)
        self.table.verticalHeader().setFont(font)

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

        self.selection_model.selectionChanged.connect(self.selected_row_changed)

    def enable(self):
        self.setEnabled(True)

    def disable(self):
        self.setEnabled(False)

    def display_status_message(self, string, time=0):
        '''
        Displays a message in the status bar for a time in ms

        If time=0, the message will stay.
        '''

        if time == 0:
            self.statusBar.showMessage(string)
        else:
            self.statusBar.showMessage(string, time)

    def get_first_selected_row(self):
        ''' Little helper method to provide the first row out of a selection range '''
        try:
            indices = self.selection_model.selectedIndexes()
            #rows = self.selection_model.selectedRows()
            row = indices[0].row()
        except:
            row = None
        return row

    def get_selected_rows(self):
        ''' Little helper method to provide the selected rows '''
        try:
            indices = self.selection_model.selectedIndexes()
            rows = [index.row() for index in indices]
        except:
            rows = None
        return rows

    def set_selected_row(self, row):
        ''' Little helper method to allow setting the selected row '''
        index = self.model.createIndex(row,0)
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
            self.display_no_row_selected_warning()

    def selected_row_changed(self, new_selection, old_selection):
        if new_selection.indexes() != []:
            new_row = new_selection.indexes()[0].row()
            for column in self.persistent_editor_column_indices:
                self.table.openPersistentEditor(self.model.index(new_row, column))

        if old_selection.indexes() != []:
            old_row = old_selection.indexes()[0].row()
            for column in self.persistent_editor_column_indices:
                self.table.closePersistentEditor(self.model.index(old_row, column))   

    def add_row(self):
        self.model.insertRows(self.model.rowCount(),1)

    def delete_row(self):
        ''' Deletes the selected row '''
        if self.model.rowCount() > 1:
            row = self.get_first_selected_row()
            if row is not None:
                self.model.removeRows(row,1)
            else:
                self.display_no_row_selected_warning()
        else:
            self.display_warning("Can't delete last row!")

    def delete_all_rows(self):
        ''' 
        Displays a warning that this will delete the entire table
        and then proceeds to delete if the user clicks 'Yes'
        '''
        reply = QtWidgets.QMessageBox.warning(self,"mesoSPIM Warning",
                'Do you want to delete the table?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.model.deleteTable()

    def copy_row(self):
        row = self.get_first_selected_row()
        if row is not None:
            self.model.copyRow(row)
        else:
            self.display_no_row_selected_warning()

    def move_selected_row_up(self):
        row = self.get_first_selected_row()
        if row is not None:
            if row > 0:
                self.model.moveRow(QtCore.QModelIndex(),row,QtCore.QModelIndex(),row-1)
                self.set_selected_row(row-1)
        else:
            self.display_no_row_selected_warning()

    def move_selected_row_down(self):
        row = self.get_first_selected_row()
        if row is not None:
            if row < self.model.rowCount():
                self.model.moveRow(QtCore.QModelIndex(),row,QtCore.QModelIndex(),row+1)
                self.set_selected_row(row+1)
        else:
            self.display_no_row_selected_warning()

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
                              'rot' : 'RotationSpinBoxDelegate(self)',
                              'f_start' : 'MarkFocusPositionDelegate(self)',
                              'f_end' : 'MarkFocusPositionDelegate(self)',
                              'filter' : 'ComboDelegate(self,[key for key in self.cfg.filterdict.keys()])',
                              'intensity' : 'IntensitySpinBoxDelegate(self)',
                              'laser' : 'ComboDelegate(self,[key for key in self.cfg.laserdict.keys()])',
                              'zoom' : 'ComboDelegate(self,[key for key in self.cfg.zoomdict.keys()])',
                              'shutterconfig' : 'ComboDelegate(self,[key for key in self.cfg.shutteroptions])',
                              'folder' : 'ChooseFolderDelegate(self)',
                              'etl_l_offset' : 'ETLSpinBoxDelegate(self)',
                              'etl_l_amplitude' : 'ETLSpinBoxDelegate(self)',
                              'etl_r_offset' : 'ETLSpinBoxDelegate(self)',
                              'etl_r_amplitude' : 'ETLSpinBoxDelegate(self)',
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

    def update_acquisition_time_prediction(self):
        framerate = self.state['current_framerate']
        total_time = self.state['acq_list'].get_acquisition_time(framerate)
        self.state['predicted_acq_list_time'] = total_time
        time_string = convert_seconds_to_string(total_time)
        self.AcquisitionTimeLabel.setText(time_string)

    def update_acquisition_size_prediction(self):
        bytes_total = self.parent.core.get_required_disk_space(self.model.get_acquisition_list())
        self.PredictedSizeLabel.setText(format_data_size(bytes_total))

    def set_state(self):
        self.state['acq_list'] = self.model.get_acquisition_list()
        
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
        path , _ = QtWidgets.QFileDialog.getSaveFileName(None, 'Save Table', directory='./acq_table.bin')
        if path:
            self.model.saveModel(path)
        self.set_state()

    def load_table(self):
        path , _ = QtWidgets.QFileDialog.getOpenFileName(None, 'Load Table')
        if path:
            try:
                self.model.loadModel(path)
                self.set_state()
                self.update_acquisition_time_prediction()
                self.update_acquisition_size_prediction()
            except:
                err_message = 'Table cannot be loaded - incompatible file format (Probably created by a previous version of the mesoSPIM software)!'
                self.print(err_message)
                logger.error(err_message)

    def run_tiling_wizard(self):
        wizard = MulticolorTilingWizard(self)

    def run_focus_tracking_wizard(self):
        wizard = FocusTrackingWizard(self)

    def run_image_processing_wizard(self):
        wizard = ImageProcessingWizard(self)

    def mark_current_xy_position(self):
        row = self.get_first_selected_row()

        if row is not None:
            self.model.setDataFromState(row, 'x_pos')
            self.model.setDataFromState(row, 'y_pos')
        else:
            if self.model.rowCount() == 1:
                self.set_selected_row(0)
                self.mark_current_xy_position()
            else:
                self.display_no_row_selected_warning()

    def mark_current_state(self):
        row = self.get_first_selected_row()

        if row is not None:
            self.model.setDataFromState(row, 'filter')
            self.model.setDataFromState(row, 'zoom')
            self.model.setDataFromState(row, 'laser')
            self.model.setDataFromState(row, 'intensity')
            self.model.setDataFromState(row, 'shutterconfig')
        else:
            if self.model.rowCount() == 1:
                self.set_selected_row(0)
                self.mark_current_state()
            else:
                self.display_no_row_selected_warning()

    def mark_current_etl_parameters(self):
        row = self.get_first_selected_row()

        if row is not None:
            self.model.setDataFromState(row, 'etl_l_offset')
            self.model.setDataFromState(row, 'etl_l_amplitude')
            self.model.setDataFromState(row, 'etl_r_offset')
            self.model.setDataFromState(row, 'etl_r_amplitude')
        else:
            if self.model.rowCount() == 1:
                self.set_selected_row(0)
                self.mark_current_etl_parameters()
            else:
                self.display_no_row_selected_warning()

    def mark_current_focus(self):
        ''' Marks both foci start focus '''
        row = self.get_first_selected_row()

        if row is not None:
            f_pos = self.state['position']['f_pos']
            ''' Set f_start and f_end to the same values '''
            column_index0 = self.model._table[0].keys().index('f_start')
            index0 = self.model.createIndex(row, column_index0)
            column_index1 = self.model._table[0].keys().index('f_end')
            index1 = self.model.createIndex(row, column_index1)

            self.model.setData(index0, f_pos)
            self.model.setData(index1, f_pos)
        
        else:
            if self.model.rowCount() == 1:
                self.set_selected_row(0)
                self.mark_current_focus()
            else:
                self.display_no_row_selected_warning()
            
    def mark_current_rotation(self):
        row = self.get_first_selected_row()

        if row is not None:
            self.model.setDataFromState(row, 'rot')

        else:
            if self.model.rowCount() == 1:
                self.set_selected_row(0)
                self.mark_current_rotation()
            else:
                self.display_no_row_selected_warning()

    def mark_all_current_parameters(self):
        self.mark_current_xy_position()
        self.mark_current_rotation()
        self.mark_current_focus()
        self.mark_current_etl_parameters()
        self.mark_current_state()

    def preview_acquisition(self):
        row = self.get_first_selected_row()
        # print('selected row:', row)
        if row is not None:
            self.state['selected_row'] = row
            # Check if the z position should be updated
            if self.PreviewZCheckBox.checkState():
                # print('Checkbox checked')
                self.parent.sig_state_request.emit({'state':'preview_acquisition_with_z_update'})
            else:
                # print('Checkbox not checked')
                self.parent.sig_state_request.emit({'state':'preview_acquisition_without_z_update'})
        else: 
            if self.model.rowCount() == 1:
                self.set_selected_row(0)
                self.preview_acquisition() # recursive call of the same function
            else:    
                self.display_no_row_selected_warning()

    def set_folder_names(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self.parent, 'Select Folder')
        if path:
            column_index = self.model._table[0].keys().index('folder')
            for row in range(0, self.model.rowCount()):
                index = self.model.createIndex(row, column_index)
                self.model.setData(index, path)

    def generate_filenames(self):
        wizard = FilenameWizard(self)

    def display_no_row_selected_warning(self):
        self.display_warning('No row selected!')

    def display_warning(self, string):
        warning = QtWidgets.QMessageBox.warning(None,'Warning',
                string, QtWidgets.QMessageBox.Ok) 
    def display_information(self, string, fontsize=12):
        msg_box = QMessageBox(QtWidgets.QMessageBox.Information, 'Info', string)
        msg_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Information, 'Info', string)
        font = msg_box.font()
        font.setPointSize(fontsize)  
        msg_box.setFont(font)
        msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        return msg_box.exec_()

    def auto_illumination(self, margin_um=500):
        message = 'Illumination (Left/Right) will be changed based on x-positions of tiles on the grid.\n\n'
        message += f'Only tiles closest to the grid edges will be changed, within 500 µm from the "x_min" and "x_max" of the acquisition table.\n\n'
        message += 'The best illumination for tiles that are closer to the grid center is sample-dependent and must be selected manually.'
        message_box =  self.display_information(message,12)
        if message_box == QMessageBox.Cancel:
            return
        x_pos_list = []
        # collect all x positions
        for row in range(0,self.model.rowCount()):
            x_pos = self.model.getXPosition(row)
            x_pos_list.append(x_pos)
        # for edge positions, set the illumination based on them
        x_min = min(x_pos_list)
        x_max = max(x_pos_list)
        for row in range(0,self.model.rowCount()):
            x_pos = self.model.getXPosition(row)
            if x_pos <= x_min + margin_um:
                if 'flip_auto_LR_illumination' in self.cfg.ui_options.keys() and self.cfg.ui_options['flip_auto_LR_illumination']:
                    logger.info(f"Config parameter 'flip_auto_LR_illumination' = True. Illumination of tile {row} will be set to 'Right'.")
                    self.model.setShutterconfig(row, 'Right')
                else:
                    self.model.setShutterconfig(row, 'Left')
            elif x_pos >= x_max - margin_um:
                if 'flip_auto_LR_illumination' in self.cfg.ui_options.keys() and self.cfg.ui_options['flip_auto_LR_illumination']:
                    logger.info(f"Config parameter 'flip_auto_LR_illumination' = True. Illumination of tile {row} will be set to 'Left'.")
                    self.model.setShutterconfig(row, 'Left')
                else:
                    self.model.setShutterconfig(row, 'Right')
            else:
                pass

