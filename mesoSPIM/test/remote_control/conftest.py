"""Install the small PyQt5 substitute used by hardware-free implementation tests.

The substitute keeps ``QTimer.singleShot`` synchronous. Deferred command bodies therefore run in
the test call, while individual tests emit terminal signals explicitly when they need to inspect an
operation before completion.
"""

from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def _install_fake_pyqt5():
    if "PyQt5" in sys.modules:
        return

    qtcore = types.ModuleType("PyQt5.QtCore")

    class QObject:
        def __init__(self, parent=None):
            self._parent = parent

        def thread(self):
            return _MAIN_THREAD

    class _Signal:
        """A stand-in bound signal: connect stores slots, emit calls them synchronously."""

        def __init__(self):
            self._slots = []

        def connect(self, slot, *a, **k):
            self._slots.append(slot)

        def disconnect(self, slot=None):
            self._slots = [] if slot is None else [s for s in self._slots if s is not slot]

        def emit(self, *args):
            for slot in list(self._slots):
                slot(*args)

    def pyqtSignal(*_a, **_k):
        # A descriptor: each instance gets its own _Signal.
        class _Descriptor:
            def __set_name__(self, owner, name):
                self._name = "_sig_" + name

            def __get__(self, obj, owner=None):
                if obj is None:
                    return self
                if not hasattr(obj, self._name):
                    setattr(obj, self._name, _Signal())
                return getattr(obj, self._name)

        return _Descriptor()

    def pyqtSlot(*_a, **_k):
        return lambda fn: fn

    class _Thread:
        pass

    _MAIN_THREAD = _Thread()

    class QThread:
        @staticmethod
        def currentThread():
            return _MAIN_THREAD

    class QTimer:
        @staticmethod
        def singleShot(_msec, fn):
            fn()  # immediate: drive deferred WAIT bodies in-test

    class _Qt:
        QueuedConnection = 0
        DirectConnection = 1

    qtcore.QObject = QObject
    qtcore.pyqtSignal = pyqtSignal
    qtcore.pyqtSlot = pyqtSlot
    qtcore.QThread = QThread
    qtcore.QTimer = QTimer
    qtcore.Qt = _Qt

    qtnetwork = types.ModuleType("PyQt5.QtNetwork")
    qtnetwork.QTcpServer = object  # only touched at runtime, never in unit tests
    qtnetwork.QHostAddress = object

    # Provide only the widgets needed to construct RemoteControlGUI in test_gui.
    qtwidgets = types.ModuleType("PyQt5.QtWidgets")

    class _Font:
        def setPointSize(self, _size):
            pass

    class QWidget:
        def __init__(self, parent=None):
            self._parent = parent
            self._enabled = True

        def setObjectName(self, _name):
            pass

        def setFont(self, _font):
            pass

        def setEnabled(self, enabled):
            self._enabled = bool(enabled)

        def isEnabled(self):
            return self._enabled

        def font(self):
            return _Font()

    class QComboBox(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._items = []
            self._current = ""
            self.currentTextChanged = _Signal()

        def addItems(self, items):
            self._items.extend(items)

        def setCurrentText(self, text):
            self._current = text

        def currentText(self):
            return self._current

    class QLineEdit(QWidget):
        Normal = 0
        Password = 2  # matches QtWidgets.QLineEdit.Password

        def __init__(self, text="", parent=None):
            super().__init__(parent)
            self._text = text
            self._echo = QLineEdit.Normal

        def text(self):
            return self._text

        def setText(self, text):
            self._text = text

        def setEchoMode(self, mode):
            self._echo = mode

        def echoMode(self):
            return self._echo

    class QLabel(QWidget):
        def __init__(self, *_args, **_kwargs):
            super().__init__()
            self._text = ""

        def setText(self, text):
            self._text = text

        def text(self):
            return self._text

    class QPushButton(QWidget):
        def __init__(self, *_args, **_kwargs):
            super().__init__()
            self.clicked = _Signal()

    class _Layout:
        def __init__(self, *_args, **_kwargs):
            pass

        def addWidget(self, *_a, **_k):
            pass

        def addRow(self, *_a, **_k):
            pass

        def addStretch(self, *_a, **_k):
            pass

        def setContentsMargins(self, *_a, **_k):
            pass

        def setSpacing(self, *_a, **_k):
            pass

    class QVBoxLayout(_Layout):
        pass

    class QFormLayout(_Layout):
        pass

    class QHBoxLayout(_Layout):
        pass

    class QGroupBox(QWidget):
        def __init__(self, *_args, **_kwargs):
            super().__init__()

    class QMessageBox:
        warnings = []  # recording, so a test can assert a warn fired

        @staticmethod
        def warning(parent, title, message):
            QMessageBox.warnings.append((parent, title, message))

    for _name, _obj in (
        ("QWidget", QWidget),
        ("QComboBox", QComboBox),
        ("QLineEdit", QLineEdit),
        ("QLabel", QLabel),
        ("QPushButton", QPushButton),
        ("QVBoxLayout", QVBoxLayout),
        ("QFormLayout", QFormLayout),
        ("QHBoxLayout", QHBoxLayout),
        ("QGroupBox", QGroupBox),
        ("QMessageBox", QMessageBox),
    ):
        setattr(qtwidgets, _name, _obj)

    pyqt5 = types.ModuleType("PyQt5")
    pyqt5.QtCore = qtcore
    pyqt5.QtNetwork = qtnetwork
    pyqt5.QtWidgets = qtwidgets
    sys.modules["PyQt5"] = pyqt5
    sys.modules["PyQt5.QtCore"] = qtcore
    sys.modules["PyQt5.QtNetwork"] = qtnetwork
    sys.modules["PyQt5.QtWidgets"] = qtwidgets


_install_fake_pyqt5()


def pytest_configure(config):
    """Register the explicit operator-gated live-test markers."""
    config.addinivalue_line("markers", "live_valid: safe live movement and restoration")
    config.addinivalue_line("markers", "live_demo_all: complete DemoStage command sweep")
    config.addinivalue_line("markers", "live_real_all: complete real-hardware command sweep")
    config.addinivalue_line("markers", "live_adversarial: bounded live hostile-input and race tests")
