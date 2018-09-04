''' Class that contains the main application window '''

import sys

from PyQt5 import QtWidgets, QtGui, QtCore, QtDesigner
from PyQt5.uic import loadUi

from .worker import WorkerObject
from .models import AcquisitionModel

from .delegates import (ComboDelegate,
                        SliderDelegate,
                        MarkXPositionDelegate,
                        MarkYPositionDelegate,
                        MarkZPositionDelegate,
                        MarkFocusPositionDelegate,
                        ProgressBarDelegate,
                        ZstepSpinBoxDelegate,
                        SliderWithValueDelegate)

from .widgets import MarkPositionWidget

from .config import config as cfg

from .devices.joysticks import joystick_handlers as jst

from .acquisition_wizards import MyWizard, TilingWizard

class MyStyle(QtWidgets.QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        '''
        Draw a line across the entire row rather than just the column
        we're hovering over.  This may not always work depending on global
        style - for instance I think it won't work on OSX.
        '''
        if element == self.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
            option_new = QtWidgets.QStyleOption(option)
            option_new.rect.setLeft(0)
            if widget:
                option_new.rect.setRight(widget.width())
            option = option_new
        super().drawPrimitive(element, option, painter, widget)

class Window(QtWidgets.QMainWindow):
    '''
    Main application window which instantiates a worker object and moves it
    to a thread.

    startButton
    addButton
    deleteButton
    moveUpButton
    moveDownButton
    saveButton
    loadButton

    textBox
    table

    rowProgressBar
    totalProgressBar

    --------------------
    Movement related:
    --------------------
    xPlusButton
    yPlusButton
    zPlusButton
    rotPlusButton

    xMinusButton
    yMinusButton
    zMinusButton
    rotMinusButton

    xyZeroButton
    zZeroButton
    focusZeroButton
    rotZeroButton



    xyzIncrementSpinbox
    rotIncrementSpinbox

    X_Position_Indicator
    Y_Position_Indicator
    Z_Position_Indicator
    Rotation_Position_Indicator
    Focus_Position_Indicator

    X_StartPositionIndicator
    Y_StartPositionIndicator
    Z_StartPositionIndicator
    '''

    sig_start = QtCore.pyqtSignal()
    sig_start_selected = QtCore.pyqtSignal(int)
    sig_stop = QtCore.pyqtSignal()
    add_row_signal = QtCore.pyqtSignal()
    delete_row = QtCore.pyqtSignal()

    set_zoom = QtCore.pyqtSignal(str)
    set_filter = QtCore.pyqtSignal(str)
    set_intensity = QtCore.pyqtSignal(int)
    set_laser_and_intensity = QtCore.pyqtSignal(str, int)

    move_rel = QtCore.pyqtSignal(dict)
    move_abs = QtCore.pyqtSignal(dict)

    zero_xy = QtCore.pyqtSignal()
    zero_z = QtCore.pyqtSignal()
    zero_focus = QtCore.pyqtSignal()
    zero_rot = QtCore.pyqtSignal()

    model_changed = QtCore.pyqtSignal(AcquisitionModel)

    def __init__(self):
        super(Window, self).__init__()

        ''' Set up the UI '''
        loadUi('gui/gui.ui', self)
        self.setWindowTitle('Threaded table-based sequencer with MVC')

        ''' Set up the basic slots '''
        self.startButton.clicked.connect(self.start)
        self.stopButton.clicked.connect(self.sig_stop.emit)
        self.selectedStartButton.clicked.connect(self.start_selected)

        self.moveUpButton.clicked.connect(self.move_selected_row_up)
        self.moveDownButton.clicked.connect(self.move_selected_row_down)

        ''' Set up the movement & zero buttons '''
        self.xPlusButton.pressed.connect(lambda: self.move_relative({'x_rel': self.xyzIncrementSpinbox.value()}))
        self.xMinusButton.pressed.connect(lambda: self.move_relative({'x_rel': -self.xyzIncrementSpinbox.value()}))
        self.yPlusButton.pressed.connect(lambda: self.move_relative({'y_rel': self.xyzIncrementSpinbox.value()}))
        self.yMinusButton.pressed.connect(lambda: self.move_relative({'y_rel': -self.xyzIncrementSpinbox.value()}))
        self.zPlusButton.pressed.connect(lambda: self.move_relative({'z_rel': self.xyzIncrementSpinbox.value()}))
        self.zMinusButton.pressed.connect(lambda: self.move_relative({'z_rel': -self.xyzIncrementSpinbox.value()}))
        self.focusPlusButton.pressed.connect(lambda: self.move_relative({'f_rel': self.xyzIncrementSpinbox.value()}))
        self.focusMinusButton.pressed.connect(lambda: self.move_relative({'f_rel': -self.xyzIncrementSpinbox.value()}))
        self.rotPlusButton.pressed.connect(lambda: self.move_relative({'theta_rel': self.rotIncrementSpinbox.value()}))
        self.rotMinusButton.pressed.connect(lambda: self.move_relative({'theta_rel': -self.rotIncrementSpinbox.value()}))

        self.xyZeroButton.pressed.connect(self.zero_xy.emit)
        self.zZeroButton.pressed.connect(self.zero_z.emit)
        self.rotZeroButton.pressed.connect(self.zero_rot.emit)
        self.focusZeroButton.pressed.connect(self.zero_focus.emit)

        self.joystick = jst.tableSequencer_JoystickHandler(self)
        # self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

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

        ''' go through all items and disable drops '''
        # setDropEnabled(False)
        # print(self.model.supportedDropActions())

        self.set_item_delegates()

        ''' Set our custom style - this draws the drop indicator across the whole row '''
        self.table.setStyle(MyStyle())

        self.selection_model = self.table.selectionModel()
        self.selection_mapper = QtWidgets.QDataWidgetMapper()
        #self.selection_mapper.setModel(self.selection_model)

        # self.selection_model.selectionChanged.connect(self.selection_changed)

        # self.mapper = QtWidgets.QDataWidgetMapper()
        # self.mapper.setModel(self.model)

        #self.mapper.setModel(self.selection_model)

        # self.mapper.addMapping(self.textBox, 2)
        # self.mapper.setCurrentIndex(0)

        self.update_persistent_editors()


        ''' Set the thread up '''
        self.my_thread = QtCore.QThread()
        self.my_worker = WorkerObject(self.model)
        self.my_worker.moveToThread(self.my_thread)
        ''' Connect GUI model change to worker thread '''
        self.model_changed.connect(self.my_worker.update_model_from_GUI)
        ''' Initialize the model in the worker thread '''
        self.update_model_data()
        ''' Connect worker model change to GUI model '''
        self.my_worker.model_changed.connect(self.update_model_from_worker)

        ''' '''
        self.add_row_signal.connect(self.my_worker.add_row)

        ''' Create the connections '''
        self.my_worker.progress.connect(self.update_progressbars)
        self.my_worker.statusMessage.connect(self.display_status_message)
        self.my_worker.finished.connect(self.enable_gui)
        self.my_worker.position.connect(self.update_position)

        self.my_worker.model.rowsInserted.connect(self.update_persistent_editors)
        self.my_worker.model.rowsRemoved.connect(self.update_persistent_editors)

        self.sig_start.connect(self.my_worker.start)
        self.sig_start_selected.connect(self.my_worker.start)
        self.sig_stop.connect(self.my_worker.stop)

        self.zero_xy.connect(self.my_worker.zero_xy)
        self.zero_z.connect(self.my_worker.zero_z)
        self.zero_rot.connect(self.my_worker.zero_rot)
        self.zero_focus.connect(self.my_worker.zero_focus)

        self.addButton.clicked.connect(self.add_row)
        self.deleteButton.clicked.connect(self.delete_row)
        self.copyButton.clicked.connect(self.copy_row)

        self.saveButton.clicked.connect(self.save_table)
        self.loadButton.clicked.connect(self.load_table)

        self.move_rel.connect(self.my_worker.move_relative)

        ''' Wizard Buttons '''
        self.myWizardButton.clicked.connect(self.run_my_wizard)
        self.tilingWizardButton.clicked.connect(self.run_tiling_wizard)

        ''' Start the thread '''
        self.my_thread.start()

    def __del__(self):
        '''Cleans the thread up after deletion, waits until the thread
        has truly finished its life.

        Uses "try" in case things crash before the thread was even started.
        '''
        try:
            self.my_thread.quit()
            self.my_thread.wait()
        except:
            pass

    def move_relative(self, dict):
        self.move_rel.emit(dict)

    def update_progressbars(self,dict):
        cur_acq = dict['current_acq']
        tot_acqs = dict['total_acqs']
        cur_image = dict['current_image_in_acq']
        images_in_acq = dict['images_in_acq']
        tot_images = dict['total_image_count']
        image_count = dict['image_counter']

        self.rowProgressBar.setValue(int((cur_image+1)/images_in_acq*100))
        self.totalProgressBar.setValue(int((image_count+1)/tot_images*100))

        self.rowProgressBar.setFormat('%p% (Image '+ str(cur_image+1) +\
                                        '/' + str(images_in_acq) + ')')
        self.totalProgressBar.setFormat('%p% (Acquisition '+ str(cur_acq+1) +\
                                        '/' + str(tot_acqs) +\
                                         ')' + ' (Image '+ str(image_count) +\
                                        '/' + str(tot_images) + ')')

    def update_position(self, dict):
        ''' Update the position indicators in the GUI '''

        self.X_Position_Indicator.setText(str(dict['x_pos']))
        self.Y_Position_Indicator.setText(str(dict['y_pos']))
        self.Z_Position_Indicator.setText(str(dict['z_pos']))
        self.Rotation_Position_Indicator.setText(str(dict['theta_pos']))
        self.Focus_Position_Indicator.setText(str(dict['f_pos']))

        self.model.position = dict

    def display_status_message(self, string, time=0):
        '''
        Displays a message in the status bar for a time in ms

        If time=0, the message will stay.
        '''

        if time == 0:
            self.statusBar().showMessage(string)
        else:
            self.statusBar().showMessage(string, time)

    def start(self):
        self.disable_gui()
        self.sig_start.emit()

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
                              'filter' : 'ComboDelegate(self,cfg.filter_options)',
                              'intensity' : 'SliderWithValueDelegate(self)',
                              'laser' : 'ComboDelegate(self,cfg.laser_options)',
                              'zoom' : 'ComboDelegate(self,cfg.zoom_options)',
                              'shutter' : 'ComboDelegate(self,cfg.shutter_options)',
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
        print('Model in GUI updated via Worker signal')
        self.model = model
        self.update_persistent_editors()

    def enable_gui(self):
        ''' Enables all GUI controls, disables stop button '''
        self.xyzGroupbox.setEnabled(True)
        self.focusGroupbox.setEnabled(True)
        self.positionGroupbox.setEnabled(True)
        self.rotGroupbox.setEnabled(True)
        self.table.setEnabled(True)
        self.tableControlButtons.setEnabled(True)
        self.generalControlButtons.setEnabled(True)
        self.stopButton.setEnabled(False)

    def disable_gui(self):
        ''' Disables all buttons and controls, enables stop button '''
        self.xyzGroupbox.setEnabled(False)
        self.focusGroupbox.setEnabled(False)
        self.positionGroupbox.setEnabled(False)
        self.rotGroupbox.setEnabled(False)
        self.table.setEnabled(False)
        self.tableControlButtons.setEnabled(False)
        self.generalControlButtons.setEnabled(False)
        self.stopButton.setEnabled(True)

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
