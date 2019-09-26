from PyQt5 import QtWidgets, QtGui, QtCore

from .widgets import MarkPositionWidget, SliderWithValue

class ComboDelegate(QtWidgets.QItemDelegate):
    '''
    A delegate that places a fully functioning QComboBox in every
    cell of the column to which it's applied

    TODO: Provide list for entries during __init__
    '''
    def __init__(self, parent, option_list=[]):
        super().__init__(parent)
        self.option_list = option_list

    def createEditor(self, parent, option, index):
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(self.option_list)
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        # self.connect(combo, QtCore.SIGNAL("currentIndexChanged(int)"), self, QtCore.SLOT("currentIndexChanged()"))
        return combo

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        ''' The editor needs to know the config of the filters'''

        current_item = index.model().data(index, role=QtCore.Qt.EditRole)
        current_index = self.option_list.index(current_item)

        editor.setCurrentIndex(current_index)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        # model.setData(index, editor.currentIndex())
        model.setData(index, editor.currentText())

    def currentIndexChanged(self):
        self.commitData.emit(self.sender())

class SliderDelegate(QtWidgets.QStyledItemDelegate):
    ''' A slider delegate '''
    def __init__(self, parent):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        slider = QtWidgets.QSlider(parent)
        slider.setOrientation(QtCore.Qt.Horizontal)
        slider.setTracking(False)
        slider.setAutoFillBackground(True)
        slider.valueChanged.connect(lambda: self.commitData.emit(self.sender()))
        return slider

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setValue(int(index.model().data(index, role=QtCore.Qt.EditRole)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())

class SliderWithValueDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        slider = SliderWithValue(parent)
        slider.valueChanged.connect(lambda: self.commitData.emit(self.sender()))
        slider.setValue(int(index.model().data(index, role=QtCore.Qt.EditRole)))
        slider.setText(index.model().data(index, role=QtCore.Qt.EditRole))
        return slider

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setValue(int(index.model().data(index, role=QtCore.Qt.EditRole)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())

class ProgressBarDelegate(QtWidgets.QStyledItemDelegate):
    ''' A progress bar as a delegate

    Of course, it does not have an editing function, instead it only serves
    to display data

    TODO: How to set value properly?
    '''

    def __init__(self, parent):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        progressbar = QtWidgets.QProgressBar(parent)
        progressbar.setOrientation(QtCore.Qt.Horizontal)
        progressbar.setAutoFillBackground(True)
        # progressbar.valueChanged.connect(lambda: self.commitData.emit(self.sender()))
        return progressbar

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setValue(int(index.model().data(index, role=QtCore.Qt.EditRole)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())

class ETLSpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    ''' Delegate with Spinbox, very fine steps'''
    def __init__(self, parent):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        spinbox = QtWidgets.QDoubleSpinBox(parent)
        spinbox.setDecimals(3)
        spinbox.setSingleStep(0.001)
        spinbox.setMinimum(-5.0)
        spinbox.setMaximum(5.0)
        spinbox.setSuffix(' V')
        spinbox.valueChanged.connect(lambda: self.commitData.emit(self.sender()))
        spinbox.setAutoFillBackground(True)
        return spinbox

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setValue(index.model().data(index, role=QtCore.Qt.EditRole))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())

class RotationSpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    ''' Delegate with Spinbox, very fine steps'''
    def __init__(self, parent):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        spinbox = QtWidgets.QDoubleSpinBox(parent)
        spinbox.setDecimals(1)
        spinbox.setSingleStep(1)
        spinbox.setMinimum(-360.0)
        spinbox.setMaximum(360.0)
        spinbox.setSuffix('°')
        spinbox.valueChanged.connect(lambda: self.commitData.emit(self.sender()))
        spinbox.setAutoFillBackground(True)
        return spinbox

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setValue(index.model().data(index, role=QtCore.Qt.EditRole))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())        

class ZstepSpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    ''' Delegate with Spinbox, Minimum value is 0 (no negative step sizes)'''
    def __init__(self, parent):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        spinbox = QtWidgets.QSpinBox(parent)
        spinbox.setMinimum(1)
        spinbox.setMaximum(1000)
        spinbox.valueChanged.connect(lambda: self.commitData.emit(self.sender()))
        spinbox.setAutoFillBackground(True)
        return spinbox

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setValue(int(index.model().data(index, role=QtCore.Qt.EditRole)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())


class MarkPositionDelegate(QtWidgets.QStyledItemDelegate):
    ''' Delegate with a Mark button

    Upon hitting the mark button, it should take the current value
    from e.g. the coordinates and put them into the model
    set it into

    There is only a single delegate per row instantiated.
    '''
    def __init__(self, parent):
        super().__init__(parent)

        self.model = parent.model

    def createEditor(self, parent, option, index):
        marker = MarkPositionWidget(parent)
        marker.pressed.connect(lambda: self.commitData.emit(self.sender()))
        marker.lineEdit.editingFinished.connect(lambda: self.set_model_data_from_focus_change(marker, index))
        return marker

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.lineEdit.setText(str(index.model().data(index, role=QtCore.Qt.EditRole)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        ''' Sets the data in the model in two ways:
        * When the Button is pressed, it should use the model position
        * If the lineEdit has a value change, it should use this

        Important: This functionality has to be inheritable
        '''

        ''' By testing, I found out that editing the lineEdit
        leads to self.sender() == None (print(self.sender()))
        --> self.sender() is of NoneType

        This means that I can differentiate whether an edit action
        was caused by the button press or editing the lineEdit
        '''
       
        if self.sender() is None:
            # print(self.sender())
            self.set_model_data_from_lineedit(editor, model, index)
        else:
            self.set_model_data_from_button(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def set_model_data_from_button(self, editor, model, index):
        pos = 0 # replace by model.position['x_pos'] after inheriting
        pos = round(pos, 2)
        model.setData(index, pos)
        editor.lineEdit.setText(str(pos))

    def set_model_data_from_lineedit(self, editor, model, index):
        try:
            model.setData(index, float(editor.lineEdit.text()))
        except:
            model.setData(index, 0.0)

    def set_model_data_from_focus_change(self, editor, index):
        try:
            self.model.setData(index, float(editor.lineEdit.text()))
        except:
            self.model.setData(index, 0.0)

class MarkXPositionDelegate(MarkPositionDelegate):
    def __init__(self, parent):
        super().__init__(parent)

    def set_model_data_from_button(self, editor, model, index):
        pos = model.state['position']['x_pos']
        pos = round(pos, 2)
        model.setData(index, pos)
        editor.lineEdit.setText(str(pos))

class MarkYPositionDelegate(MarkPositionDelegate):
    def __init__(self, parent):
        super().__init__(parent)

    def set_model_data_from_button(self, editor, model, index):
        pos = model.state['position']['y_pos']
        pos = round(pos, 2)
        model.setData(index, pos)
        editor.lineEdit.setText(str(pos))

class MarkZPositionDelegate(MarkPositionDelegate):
    def __init__(self, parent):
        super().__init__(parent)

    def set_model_data_from_button(self, editor, model, index):
        pos = model.state['position']['z_pos']
        pos = round(pos, 2)
        model.setData(index, pos)
        editor.lineEdit.setText(str(pos))

class MarkFocusPositionDelegate(MarkPositionDelegate):
    def __init__(self, parent):
        super().__init__(parent)

    def set_model_data_from_button(self, editor, model, index):
        pos = model.state['position']['f_pos']
        pos = round(pos, 2)
        model.setData(index, pos)
        editor.lineEdit.setText(str(pos))

class MarkRotationPositionDelegate(MarkPositionDelegate):
    def __init__(self, parent):
        super().__init__(parent)

    def set_model_data_from_button(self, editor, model, index):
        pos = model.state['position']['theta_pos']
        pos = round(pos, 2)
        model.setData(index, pos)
        editor.lineEdit.setText(str(pos))

class ChooseFolderDelegate(QtWidgets.QItemDelegate):
    '''
    A delegate that has a button, in turn opening a set folder dialog 
    and displaying the folder name.

    '''
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.folder = ''

    def createEditor(self, parent, option, index):
        button = QtWidgets.QPushButton(parent)
        button.setText('...')
        button.clicked.connect(self.choose_folder_dialog)
        return button
    
    def choose_folder_dialog(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self.parent, 'Select Folder')
        if path:
            self.folder = path
            self.commitData.emit(self.sender())

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        editor.setText(str(index.model().data(index, role=QtCore.Qt.EditRole)))
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, self.folder)
