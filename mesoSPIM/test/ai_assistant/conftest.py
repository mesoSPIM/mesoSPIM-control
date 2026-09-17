"""Test bootstrap for the AI Assistant suite.

Reuses the Remote Control Qt-free substitute — importing that conftest installs it, and keeps
``QTimer.singleShot`` synchronous so deferred command bodies run in-test — then adds only what the
chat tab needs on top: a rich-text transcript widget, the QtGui pieces that render Markdown to
HTML, a cross-thread ``QMetaObject.invokeMethod``, and two ``Qt`` enums.

Extending here rather than editing ``test/remote_control/conftest.py`` keeps that file identical to
the reviewed Remote Control contribution, and makes the additions independent of which suite pytest
collects first.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from mesoSPIM.test.remote_control import conftest as _rc_conftest    # noqa: F401,E402 (installs it)

from PyQt5 import QtCore, QtWidgets                                  # noqa: E402 (the substitute)


class QTextEdit(QtWidgets.QWidget):
    """The AI Assistant transcript. Records the last rendered body so a test can assert on it."""

    WidgetWidth = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._markdown = ""

    def setReadOnly(self, _flag):
        pass

    def setLineWrapMode(self, _mode):
        pass

    def setVerticalScrollBarPolicy(self, _policy):
        pass

    def setMarkdown(self, text):
        self._markdown = text

    def setHtml(self, text):
        self._markdown = text

    def toPlainText(self):
        return self._markdown

    def textCursor(self):
        class _Cursor:
            def movePosition(self, _position):
                pass
        return _Cursor()

    def setTextCursor(self, _cursor):
        pass

    def ensureCursorVisible(self):
        pass


class QMetaObject:
    @staticmethod
    def invokeMethod(obj, member, _connection=0):
        """Every QObject shares one thread in-test, so a cross-thread invoke is just a call."""
        getattr(obj, member)()


class QTextDocument:
    def setMarkdown(self, markdown):
        self._markdown = markdown

    def toHtml(self):
        return "<body>" + getattr(self, "_markdown", "") + "</body>"


class QTextCursor:
    End = 0


QtWidgets.QTextEdit = QTextEdit
if not hasattr(QtCore, "QMetaObject"):
    QtCore.QMetaObject = QMetaObject
for _enum, _value in (("BlockingQueuedConnection", 3), ("ScrollBarAlwaysOn", 2),
                      ("QueuedConnection", 0), ("DirectConnection", 1)):
    if not hasattr(QtCore.Qt, _enum):
        setattr(QtCore.Qt, _enum, _value)
for _layout in (QtWidgets.QVBoxLayout, QtWidgets.QHBoxLayout, QtWidgets.QFormLayout):
    if not hasattr(_layout, "addLayout"):
        _layout.addLayout = lambda self, *a, **k: None
if not hasattr(QtWidgets.QLineEdit, "setPlaceholderText"):
    QtWidgets.QLineEdit.setPlaceholderText = lambda self, _text: None
if not hasattr(QtWidgets.QLineEdit, "clear"):
    QtWidgets.QLineEdit.clear = lambda self: self.setText("")
if not hasattr(QtWidgets.QWidget, "setVisible"):
    QtWidgets.QWidget.setVisible = lambda self, visible: setattr(self, "_visible", bool(visible))
    QtWidgets.QWidget.isVisible = lambda self: getattr(self, "_visible", True)


class _Signal:
    """A bound signal per widget instance: connect stores slots, emit calls them synchronously."""

    def __init__(self):
        self._slots = []

    def connect(self, slot, *_a, **_k):
        self._slots.append(slot)

    def disconnect(self, slot=None):
        self._slots = [] if slot is None else [s for s in self._slots if s is not slot]

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


def _lazy_signal(attribute):
    """The stub widgets have no metaclass machinery, so each signal is created on first access."""
    def getter(self):
        if not hasattr(self, attribute):
            setattr(self, attribute, _Signal())
        return getattr(self, attribute)
    return property(getter)


_RADIO_GROUPS = {}  # parent id -> radios, so setChecked(True) unchecks the siblings


class QRadioButton(QtWidgets.QWidget):
    """Two of these share one 'checked' choice in production; here each just holds its own flag
    and setChecked drives the `toggled` signal the tab listens to."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
        self._checked = False
        self.toggled = _Signal()
        _RADIO_GROUPS.setdefault(id(parent), []).append(self)

    def setChecked(self, checked):
        changed = self._checked != bool(checked)
        self._checked = bool(checked)
        if changed:
            self.toggled.emit(self._checked)
        if self._checked:
            for sibling in _RADIO_GROUPS.get(id(self._parent), []):
                if sibling is not self:
                    sibling.setChecked(False)


    def isChecked(self):
        return self._checked


class QToolButton(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._checked = False
        self._arrow = None
        self.clicked = _Signal()
        self.toggled = _Signal()

    def setCheckable(self, _flag):
        pass

    def setChecked(self, checked):
        changed = self._checked != bool(checked)
        self._checked = bool(checked)
        if changed:
            self.toggled.emit(self._checked)

    def isChecked(self):
        return self._checked

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def setArrowType(self, arrow):
        self._arrow = arrow

    def arrowType(self):
        return self._arrow

    def setToolButtonStyle(self, _style):
        pass

    def setAutoRaise(self, _flag):
        pass


class QGridLayout(QtWidgets.QVBoxLayout):
    def setHorizontalSpacing(self, _v):
        pass

    def setVerticalSpacing(self, _v):
        pass

    def setColumnStretch(self, _column, _stretch):
        pass

    def setColumnMinimumWidth(self, _column, _width):
        pass


class QFileDialog:
    chosen = ""  # a test sets the folder the dialog "returns"

    @staticmethod
    def getExistingDirectory(_parent, _title, _start):
        return QFileDialog.chosen


QtWidgets.QRadioButton = QRadioButton
QtWidgets.QToolButton = QToolButton
QtWidgets.QGridLayout = QGridLayout
if not hasattr(QtWidgets.QWidget, "setFocus"):
    QtWidgets.QWidget.setFocus = lambda self: None
if not hasattr(QtWidgets.QWidget, "setStyleSheet"):
    QtWidgets.QWidget.setStyleSheet = lambda self, _sheet: None
if not hasattr(QtWidgets.QWidget, "sizeHint"):
    QtWidgets.QWidget.sizeHint = lambda self: types.SimpleNamespace(width=lambda: 80, height=lambda: 24)
if not hasattr(QtWidgets.QWidget, "setSizePolicy"):
    QtWidgets.QWidget.setSizePolicy = lambda self, *_a: None
    QtWidgets.QSizePolicy = types.SimpleNamespace(Ignored=0, Preferred=1)
for _enum, _value in (("AlignLeft", 1),):
    if not hasattr(QtCore.Qt, _enum):
        setattr(QtCore.Qt, _enum, _value)
QtWidgets.QFileDialog = QFileDialog
for _enum, _value in (("RightArrow", 4), ("DownArrow", 2), ("ToolButtonTextBesideIcon", 2)):
    if not hasattr(QtCore.Qt, _enum):
        setattr(QtCore.Qt, _enum, _value)
if not hasattr(QtWidgets.QComboBox, "clear"):
    QtWidgets.QComboBox.clear = lambda self: (self._items.clear(), setattr(self, "_current", ""))
    QtWidgets.QComboBox.items = lambda self: list(self._items)
for _layout in (QtWidgets.QVBoxLayout, QtWidgets.QHBoxLayout, QtWidgets.QFormLayout):
    if not hasattr(_layout, "addSpacing"):
        _layout.addSpacing = lambda self, *a, **k: None

# Only returnPressed is missing: QPushButton already assigns `clicked` per instance in its own
# __init__, and a class-level property here would shadow that assignment and break it.
if not hasattr(QtWidgets.QLineEdit, "returnPressed"):
    QtWidgets.QLineEdit.returnPressed = _lazy_signal("_signal_returnPressed")

_qtgui = types.ModuleType("PyQt5.QtGui")
_qtgui.QTextDocument = QTextDocument
_qtgui.QTextCursor = QTextCursor
sys.modules["PyQt5.QtGui"] = _qtgui
sys.modules["PyQt5"].QtGui = _qtgui
