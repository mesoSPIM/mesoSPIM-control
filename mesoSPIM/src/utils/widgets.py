from PyQt5 import QtWidgets, QtGui, QtCore, QtDesigner

class MarkPositionWidget(QtWidgets.QWidget):
    """ Pushbutton plus position indicator """
    pressed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        #QtWidgets.QWidget.__init__(self, parent)
        super().__init__(parent)
        # QtDesigner.QPyDesignerCustomWidgetPlugin.__init__(self, parent)

        self.button = QtWidgets.QPushButton()
        self.button.setText("M")

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.button.sizePolicy().hasHeightForWidth())
        self.button.setSizePolicy(sizePolicy)
        self.button.setMinimumSize(QtCore.QSize(25, 0))

        self.lineEdit = QtWidgets.QLineEdit()
        # self.lineEdit.setReadOnly(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit.sizePolicy().hasHeightForWidth())
        self.lineEdit.setSizePolicy(sizePolicy)

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.button)
        self.layout.addWidget(self.lineEdit)
        ''' '''
        self.layout.setContentsMargins(0,0,0,0)

        self.button.clicked.connect(lambda: self.pressed.emit())

        self.setLayout(self.layout)
        self.setAutoFillBackground(True)

class SliderWithValue(QtWidgets.QWidget):
    ''' Slider with value to the left '''
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = QtWidgets.QLabel()
        self.label.setMinimumSize(QtCore.QSize(25, 0))

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)

        self.slider = QtWidgets.QSlider()
        self.slider.setOrientation(QtCore.Qt.Horizontal)
        self.slider.setTracking(False)
        self.slider.valueChanged.connect(self.setText)
        self.slider.valueChanged.connect(self.valueChanged.emit)

        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.slider.sizePolicy().hasHeightForWidth())
        self.slider.setSizePolicy(sizePolicy)

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.slider)
        self.layout.setContentsMargins(0,0,0,0)

        self.setLayout(self.layout)
        self.setAutoFillBackground(True)

    def setText(self, value):
        self.label.setText(str(value) + '%')

    def setValue(self, value):
        self.slider.setValue(value)
        
    def value(self):
        return self.slider.value()
