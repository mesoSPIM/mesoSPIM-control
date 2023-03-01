from PyQt5 import QtWidgets, QtGui, QtCore, QtDesigner


class MarkPositionWidget(QtWidgets.QWidget):
    """ Pushbutton plus position indicator """
    pressed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.button = QtWidgets.QToolButton()
        self.button.setText("M")

        font = QtGui.QFont()
        font.setPointSize(12)
        self.button.setFont(font)
        self.button.setMaximumWidth(30)

        self.lineEdit = QtWidgets.QLineEdit()
        self.lineEdit.setFont(font)

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.lineEdit)
        self.layout.addWidget(self.button)
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)
        self.setAutoFillBackground(True)

        self.button.clicked.connect(lambda: self.pressed.emit())


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

        font = QtGui.QFont()
        font.setPointSize(14)
        self.slider.setFont(font)

    def setText(self, value):
        self.label.setText(str(value) + '%')

    def setValue(self, value):
        self.slider.setValue(value)
        
    def value(self):
        return self.slider.value()
