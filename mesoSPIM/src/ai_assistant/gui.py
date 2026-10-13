"""The 'AI Assistant' tab and window.

The tab is shaped like the Remote Control tab: one Setup AI assistant box (Preferences, Language
model, Vision model), a status line, and Connect and Disconnect. Connect applies the boxes, takes
the session and opens the assistant window; Disconnect, or closing that window, cancels a running
turn, closes it and hands the session back, so the Remote Control transports can start. The two
are mutually exclusive.

The window is the chat, styled like a coding-agent chat: your question bold on its own panel, the
answer plain under the commands it ran when Show tool calls is on. Images stay out of the chat: a
frame goes to the vision model only. Enter submits; the input disables during a turn
(single-flight); Cancel prompt stops the assistant, Stop microscope stops the instrument.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import dataclasses
import html as _htmllib
import re
import os

from PyQt5 import QtCore, QtGui, QtWidgets

from . import config
from . import skills as skill_files
from ..remote_control import config as rc_config
from .assistant import AssistantWorker, Endpoint, offered_commands

CLOUD_MODE = "Cloud AI"
SAME_AS_LANGUAGE = "Same as language model"
NO_COMMANDS_SENT = "no command was sent to the microscope in this turn"
PAIR_GAP = 14                   # px before an inner label, more than the 8 between it and its field
_ORPHANED_THREADS = []          # worker threads still in a model call at exit; kept so Qt never destroys a running one

_BUBBLE = "#2b3b47"      # the operator's own turns only — the answers stay on the tab background
_DIM = "#9aa7b0"         # tool-call and note text


def _md_to_html(markdown):
    """Render Markdown to an HTML body fragment (the model's bold/lists/etc.) via Qt's own parser."""
    doc = QtGui.QTextDocument()
    doc.setMarkdown(markdown)
    html = doc.toHtml()
    lower = html.lower()
    body, close = lower.find("<body"), lower.rfind("</body>")
    if body == -1 or close == -1:
        return _htmllib.escape(markdown)
    return _chat_sized(html[html.find(">", body) + 1:close].strip())


def _chat_sized(html):
    """Qt's Markdown sets inline code, which is how a model writes a file path, in a fixed point
    size smaller than the chat; drop the size and keep the fixed-width face."""
    return re.sub(r"\s*font-size:\s*[\d.]+pt;", "", html)


class _Input(QtWidgets.QPlainTextEdit):
    """A two-line message box. Enter sends; Shift+Enter starts a new line. Offers the QLineEdit
    names the tab uses (text, setText, returnPressed) so the rest of the tab does not care."""

    returnPressed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        palette = self.palette()
        palette.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor("white"))   # "Ask the microscope…" reads
        self.setPalette(palette)

    def text(self):
        return self.toPlainText()

    def setText(self, text):
        self.setPlainText(text)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and not event.modifiers() & QtCore.Qt.ShiftModifier:
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)


def _field_label(text, parent, font, gap=PAIR_GAP):
    """A field's label: right against its field, with room before it so each label-and-field
    pair reads as one."""
    widget = QtWidgets.QLabel(parent)
    widget.setText(text)
    widget.setFont(font)
    widget.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    widget.setContentsMargins(gap, 0, 0, 0)
    return widget


def _describe(endpoint):
    return f"{endpoint.provider}, {endpoint.model}"


class ModelPicker(QtWidgets.QGroupBox):
    """A titled box that names one model. A Type dropdown (Cloud AI, and for the vision box "Same
    as language model") decides the fields after it: provider and model, then the API key and,
    for an OpenAI-style server, its base URL."""

    def __init__(self, title, font, parent, same_as=None):
        super().__init__(title, parent)
        self.setFont(font)
        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(10)

        self.mode = QtWidgets.QComboBox(self)
        self.mode.addItems(([same_as] if same_as else []) + [CLOUD_MODE])
        self.provider = QtWidgets.QComboBox(self)
        self.provider.addItems(list(config.PROVIDERS))
        self.provider.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)  # as wide as its names
        self.model = QtWidgets.QLineEdit("", self)
        self.model.setMinimumWidth(120)                           # grows with the window
        self.key = QtWidgets.QLineEdit("", self)
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.key.setMinimumWidth(100)
        self.base_url = QtWidgets.QLineEdit("", self)
        self.base_url.setMinimumWidth(160)                        # grows with the window
        # An OpenAI-style server says nothing about what its model can do: the operator says
        # whether it accepts images. Unticked, look hands the model the numbers only.
        self.sees = QtWidgets.QCheckBox("Can see images", self)
        self.sees.setToolTip("Tick when the model behind this server accepts images; look then shows it "
                             "the frame. Unticked, look gives it the frame's numbers only.")
        for widget in (self.mode, self.provider, self.model, self.key, self.base_url, self.sees):
            widget.setFont(font)
        self.type_label = _field_label("Type", self, font, gap=0)
        self.provider_label = _field_label("Provider", self, font)
        self.model_label = _field_label("Model", self, font)
        self.key_label = _field_label("API key", self, font)
        self.base_url_label = _field_label("Base URL", self, font)

        # Line one: the type and the provider. Line two: the model. Line three: the key, or the base
        # URL with the key on the line below it (_on_provider_changed), so an OpenAI-style server is
        # no wider than any other provider. Columns 5 and 7 take the leftover width, so the model,
        # the URL and the key all grow with the window.
        grid = self.grid
        grid.addWidget(self.type_label, 0, 0)
        grid.addWidget(self.mode, 0, 1)
        grid.addWidget(self.provider_label, 0, 2)
        grid.addWidget(self.provider, 0, 3)
        grid.addWidget(self.model_label, 1, 2)
        grid.addWidget(self.model, 1, 3, 1, 6)
        grid.addWidget(self.base_url_label, 2, 2)
        grid.addWidget(self.base_url, 2, 3, 1, 6)
        grid.addWidget(self.sees, 4, 3, 1, 6)
        grid.setColumnStretch(5, 1)
        grid.setColumnStretch(7, 1)

        self.provider.setCurrentText(config.DEFAULT_PROVIDER)
        self.mode.setCurrentText(same_as or CLOUD_MODE)
        self.mode.currentTextChanged.connect(self._on_mode_changed)
        self.provider.currentTextChanged.connect(self._on_provider_changed)
        self._on_provider_changed(config.DEFAULT_PROVIDER)     # prefills, then shows the mode's fields

    @property
    def same(self):
        """True when this box defers to the language model (the vision box's first choice)."""
        return self.mode.currentText() != CLOUD_MODE

    def _on_mode_changed(self, *_):
        """Show the fields for the type chosen."""
        cloud = not self.same
        server = cloud and config.PROVIDERS[self.provider.currentText()]["kind"] == "openai-compatible"
        for widget in (self.provider_label, self.provider, self.model_label, self.model,
                       self.key_label, self.key):
            widget.setVisible(cloud)
        for widget in (self.base_url_label, self.base_url, self.sees):
            widget.setVisible(server)

    def _on_provider_changed(self, name):
        """Prefill the preset. An OpenAI-style server also shows its base URL, and its key is
        optional: Ollama wants none, a gateway or a hosted API wants one."""
        preset = config.PROVIDERS[name]
        self.model.setText(preset["model"])
        self.base_url.setText(preset.get("base_url", ""))
        key_env = preset.get("key_env")
        in_env = bool(key_env and os.environ.get(key_env))
        if preset["kind"] == "openai-compatible":
            placeholder = "optional"
        else:
            placeholder = f"using {key_env} from the environment" if in_env else f"{name} API key"
        self.key.setPlaceholderText(placeholder)
        # The key takes the whole third line, or the fourth, under the base URL.
        self.grid.removeWidget(self.key_label)
        self.grid.removeWidget(self.key)
        if preset["kind"] == "openai-compatible":
            self.grid.addWidget(self.key_label, 3, 2)
            self.grid.addWidget(self.key, 3, 3, 1, 6)
        else:
            self.grid.addWidget(self.key_label, 2, 2)
            self.grid.addWidget(self.key, 2, 3, 1, 6)
        self._on_mode_changed()

    def cloud_endpoint(self):
        server = config.PROVIDERS[self.provider.currentText()]["kind"] == "openai-compatible"
        return Endpoint.from_preset(self.provider.currentText(), self.model.text(), self.key.text(),
                                    self.base_url.text(), vision=self.sees.isChecked() if server else None)


class AssistantWindow(QtWidgets.QWidget):
    """The chat, in a window of its own: the transcript, the input line with Stop microscope
    beside it, and under them Cancel prompt, Clear context and Show tool calls. It exists while
    the assistant is connected: Connect in the tab opens it, Disconnect closes it, and closing it
    disconnects. The tab owns the session and the turn; this window is what it shows."""

    def __init__(self, tab, font):
        super().__init__(tab.main_window, QtCore.Qt.Window)
        self.tab = tab
        self.setObjectName("AiAssistantWindow")
        self.setWindowTitle("mesoSPIM AI Assistant")
        self.setStyleSheet("QPushButton { padding: 3px 9px; }"
                           "QPushButton#AiAssistantStopButton { color: #ff4d4d; font-weight: bold; }")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.output = QtWidgets.QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setObjectName("AiAssistantOutput")
        self.output.setFont(font)
        self.output.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)          # wrap; no horizontal bar
        self.output.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)   # scrollbar from the start
        layout.addWidget(self.output, 1)

        self.status = QtWidgets.QLabel("", self)
        self.status.setObjectName("AiAssistantStatus")
        self.status.setFont(font)
        self.status.setVisible(False)                             # shown only while a turn runs
        layout.addWidget(self.status)

        # The token meter: what the last request of the session cost in input tokens. The history
        # is append-only, so it grows with every turn; past the model's warning it says so, and
        # past its ceiling no turn starts until Clear context.
        self.meter = QtWidgets.QLabel("", self)
        self.meter.setObjectName("AiAssistantMeter")
        self.meter.setFont(font)
        layout.addWidget(self.meter)

        self.input = _Input(self)
        self.input.setPlaceholderText("Ask the microscope…")
        self.input.setObjectName("AiAssistantInput")
        self.input.setFont(font)
        self.input.returnPressed.connect(tab.on_submit)
        self.interrupt = QtWidgets.QPushButton("Cancel prompt", self)
        self.interrupt.setFont(font)
        self.interrupt.clicked.connect(tab.on_interrupt)      # always clickable; a no-op between turns
        self.stop_button = QtWidgets.QPushButton("Stop microscope", self)
        self.stop_button.setObjectName("AiAssistantStopButton")
        self.stop_button.setFont(font)
        self.stop_button.clicked.connect(tab.on_stop_microscope)   # always enabled: the emergency stop
        self.clear_button = QtWidgets.QPushButton("Clear context", self)
        self.clear_button.setFont(font)
        self.clear_button.clicked.connect(tab.on_clear_all)
        self.show_tool_calls = QtWidgets.QCheckBox("Show tool calls", self)
        self.show_tool_calls.setFont(font)
        self.show_tool_calls.setChecked(config.SHOW_TOOL_CALLS)
        self.show_tool_calls.toggled.connect(lambda _checked: tab._render())
        # The two-line input, which Enter sends, with Stop microscope to its right, as tall as it;
        # under them the other controls on one line.
        two_rows = 2 * self.interrupt.sizeHint().height() + 6
        self.input.setFixedHeight(two_rows)
        self.stop_button.setFixedHeight(two_rows)
        entry = QtWidgets.QHBoxLayout()
        entry.addWidget(self.input, 1)
        entry.addWidget(self.stop_button)
        layout.addLayout(entry)
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(6)
        for widget in (self.interrupt, self.clear_button, self.show_tool_calls):
            buttons.addWidget(widget)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.resize(760, 880)                     # room for an answer of some lines above the input
        self.hide()

    def closeEvent(self, event):
        """The window's own close button: the operator is done with the assistant."""
        event.accept()
        self.tab.on_window_closed()


class AiAssistantGUI(QtWidgets.QWidget):
    """The tab: setup and the session, shaped like the Remote Control tab. One Setup AI assistant
    box (Language model, Vision model, Preferences), a status line, and Connect and Disconnect;
    the chat is in the AssistantWindow, which Connect opens."""

    sig_run_turn = QtCore.pyqtSignal(str)
    sig_check_run = QtCore.pyqtSignal()      # is the run the assistant started still under way?

    def __init__(self, parent):
        super().__init__(parent.TabWidget)
        self.main_window = parent
        self.core = parent.core
        self.setObjectName("AiAssistantTabWidget")
        self._worker = None
        self._thread = None
        self._state = "idle"                    # idle or ready; the status line shows it
        self._endpoints = {}                    # "language" and, when it is its own, "vision"
        self._running = False                   # a turn is in flight
        self._run_turn_slot = None
        self._blocks = []                       # oldest first: HTML, or a finished answer's turn dict
        self._active = None                     # the running turn: {"tools", "reply", "error"}
        self._tokens = 0                        # the input tokens of the session's last request
        # The done notice: while a run the assistant started is under way, the worker is asked every
        # DONE_CHECK_MS whether it has ended. It never runs a turn.
        self._done_check = QtCore.QTimer(self)
        self._done_check.setInterval(config.DONE_CHECK_MS)
        self._done_check.timeout.connect(self.sig_check_run.emit)
        self._build_ui()
        index = parent.TabWidget.indexOf(parent.remote_control)   # RemoteControlGUI instance
        if index >= 0:
            parent.TabWidget.insertTab(index + 1, self, "AI Assistant")
        else:
            parent.TabWidget.addTab(self, "AI Assistant")

    def _call_on_core(self, method):
        """Invoke a Core slot on the Core thread (affinity matters — the Acceptor must be
        built there). Blocks until it returns."""
        try:
            same = self.core.thread() is self.thread()
        except AttributeError:                                     # Qt-free test doubles
            same = True
        conn = QtCore.Qt.DirectConnection if same else QtCore.Qt.BlockingQueuedConnection
        QtCore.QMetaObject.invokeMethod(self.core, method, conn)

    def _ensure_worker(self):
        """Acquire the Acceptor (built by Core, on the Core thread) and start the worker, on
        first use. Returns False if a TCP/MCP transport is active (mutually exclusive)."""
        if self._worker is not None:
            return True
        self._call_on_core("start_ai_assistant")
        acceptor = getattr(self.core, "_assistant_acceptor", None)
        if acceptor is None:
            return False
        self._thread = QtCore.QThread(self)
        self._worker = AssistantWorker(acceptor)
        self._worker.moveToThread(self._thread)
        self._run_turn_slot = self._worker.run_turn
        self.sig_run_turn.connect(self._run_turn_slot, QtCore.Qt.QueuedConnection)
        self.sig_check_run.connect(self._worker.check_run, QtCore.Qt.QueuedConnection)
        self._worker.sig_run_ended.connect(self._on_run_ended)
        self._worker.sig_usage.connect(self._on_usage)
        self._worker.sig_reply.connect(self._on_reply)
        self._worker.sig_tool.connect(self._on_tool)
        self._worker.sig_served.connect(self._on_served)
        self._worker.sig_error.connect(self._on_error)
        self._worker.sig_done.connect(self._on_done)
        self._apply_options()
        self._thread.start()
        return True

    def _apply_options(self, *_):
        if self._worker is not None:
            self._worker.look_image_bin = int(self.frame_bin.currentText())
            self._worker.focus_metric = self.focus_metric.currentData()
            self._worker.axes = self.axes()

    def axes(self):
        """What a positive move on x, y and z does to the sample in the image, as chosen."""
        return {axis: combo.currentText() for axis, combo in self.axis_boxes.items()}

    def _build_ui(self):
        # Only the padding: qdarkstyle's buttons hug their text, its labels carry 7 px a side that
        # the setup grids do not want, and every other property cascades.
        self.setStyleSheet("QPushButton { padding: 3px 9px; }"
                           "QGroupBox QLabel { padding: 0px; }")
        font = self.font()
        font.setPointSize(12)                                     # match Remote Control
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        group = QtWidgets.QGroupBox("Setup AI assistant", self)
        group.setFont(font)
        column = QtWidgets.QVBoxLayout(group)
        column.setContentsMargins(12, 12, 12, 12)
        column.setSpacing(8)
        column.addWidget(self._build_setup(group, font))

        # The status line: what the session is doing, and what a failed Connect needs.
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(_field_label("Status", group, font, gap=0))
        self.status_label = QtWidgets.QLabel(group)
        self.status_label.setObjectName("AiAssistantStatusLabel")
        self.status_label.setFont(font)
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label, 1)
        column.addLayout(status_row)

        self.connect_button = QtWidgets.QPushButton("Connect", group)
        self.connect_button.setFont(font)
        self.connect_button.clicked.connect(self.on_connect)
        self.disconnect_button = QtWidgets.QPushButton("Disconnect", group)
        self.disconnect_button.setFont(font)
        self.disconnect_button.clicked.connect(self.on_disconnect)
        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addWidget(self.connect_button)
        buttons.addWidget(self.disconnect_button)
        buttons.addStretch(1)
        column.addLayout(buttons)
        layout.addWidget(group)
        layout.addStretch(1)
        self.chat_window = AssistantWindow(self, font)
        self._set_connect_state("idle")

    def _build_setup(self, parent, font):
        """Three titled boxes, in the order they are decided: the Language model, the Vision model,
        then Preferences on one line. Connect applies them."""
        setup = QtWidgets.QWidget(parent)
        column = QtWidgets.QVBoxLayout(setup)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        preferences = QtWidgets.QGroupBox("Preferences", setup)
        preferences.setFont(font)
        options = QtWidgets.QGridLayout(preferences)
        options.setContentsMargins(12, 12, 12, 12)
        options.setHorizontalSpacing(8)
        options.setVerticalSpacing(10)
        cfg = getattr(self.core, "cfg", None)
        self.frame_bin = QtWidgets.QComboBox(preferences)
        self.frame_bin.addItems([str(factor) for factor in rc_config.FRAME_BINS])
        self.frame_bin.setCurrentText(str(config.LOOK_BIN))
        self.focus_metric = QtWidgets.QComboBox(preferences)
        self.focus_metric.addItem("Laplacian", "laplacian")
        self.focus_metric.addItem("DCT-Shannon (Auto-Focus)", "dct_shannon")
        self.focus_metric.setCurrentIndex(self.focus_metric.findData(config.FOCUS_METRIC))
        for widget in (self.frame_bin, self.focus_metric):
            widget.setFont(font)

        # The bin and the focus metric on one line, the leftover width after them.
        image_label = _field_label("Bin image", preferences, font, gap=0)
        focus_label = _field_label("Focus metric", preferences, font)
        options.addWidget(image_label, 0, 0)
        options.addWidget(self.frame_bin, 0, 1)
        options.addWidget(focus_label, 0, 2)
        options.addWidget(self.focus_metric, 0, 3)
        options.setColumnStretch(4, 1)

        # The coordinate system as the operator sees it: one row per axis, what a positive move
        # does to the sample in the image. "Move it up" then has one meaning for the model.
        axes_box = QtWidgets.QGroupBox("Coordinate system", setup)
        axes_box.setFont(font)
        axes_grid = QtWidgets.QGridLayout(axes_box)
        axes_grid.setContentsMargins(12, 12, 12, 12)
        axes_grid.setHorizontalSpacing(8)
        axes_grid.setVerticalSpacing(10)
        configured_axes = getattr(cfg, config.AXES_CONFIG_KEY, None) or {}
        self.axis_boxes = {}
        for row, axis in enumerate(("x", "y", "z")):
            label = _field_label(f"{axis}+ moves the sample", axes_box, font, gap=0)
            combo = QtWidgets.QComboBox(axes_box)
            combo.addItems(list(config.AXIS_CHOICES[axis]))
            start = configured_axes.get(axis) if isinstance(configured_axes, dict) else None
            combo.setCurrentText(start if start in config.AXIS_CHOICES[axis] else config.DEFAULT_AXES[axis])
            combo.setFont(font)
            axes_grid.addWidget(label, row, 0)
            axes_grid.addWidget(combo, row, 1)
            self.axis_boxes[axis] = combo
        axes_grid.setColumnStretch(2, 1)

        self.language = ModelPicker("Language model", font, setup)
        self.vision = ModelPicker("Vision model", font, setup, same_as=SAME_AS_LANGUAGE)
        column.addWidget(self.language)
        column.addWidget(self.vision)
        column.addWidget(preferences)
        column.addWidget(axes_box)

        # The boxes share their first columns, each as wide as its widest occupant, so Type sits
        # under Bin image, the dropdowns under each other, Provider under Focus metric.
        pickers = (self.language, self.vision)

        def widest(*widgets):
            return max(widget.sizeHint().width() for widget in widgets)

        widths = (
            widest(image_label, *(p.type_label for p in pickers)),
            widest(self.frame_bin, *(p.mode for p in pickers)),   # "Same as language model" sets it
            widest(focus_label, *(w for p in pickers for w in (p.provider_label, p.base_url_label, p.key_label))),
        )
        for grid in (options, self.language.grid, self.vision.grid):
            for index, width in enumerate(widths):
                grid.setColumnMinimumWidth(index, width)
        self.frame_bin.currentTextChanged.connect(self._apply_options)
        self.focus_metric.currentIndexChanged.connect(self._apply_options)
        for combo in self.axis_boxes.values():
            combo.currentTextChanged.connect(self._apply_options)
        return setup

    # --- the session ---
    def _set_connect_state(self, state, detail=""):
        """idle: Connect is the one button that works and the window is closed. ready: connected,
        the window open and titled with what answers."""
        self._state = state
        text = {"idle": "disconnected", "ready": f"connected: {detail}"}[state]
        self.status_label.setText(text)
        self.connect_button.setEnabled(state == "idle")
        self.disconnect_button.setEnabled(state != "idle")
        self._set_setup_enabled(state == "idle")
        if state == "ready":
            self.chat_window.setWindowTitle(f"mesoSPIM AI Assistant — {detail}")
            self.chat_window.show()
            self.chat_window.raise_()
            self.chat_window.activateWindow()
        else:
            self._done_check.stop()
            self.chat_window.hide()

    def _set_setup_enabled(self, enabled):
        """The setup is applied by Connect and read only after it: Disconnect first to change it."""
        for widget in (self.language, self.vision, self.frame_bin, self.focus_metric, *self.axis_boxes.values()):
            widget.setEnabled(enabled)

    # --- connecting ---
    def on_connect(self):
        if self._state == "idle":
            self._connect()

    def on_disconnect(self):
        """Hand the session back so the Remote Control tab can start a transport, without
        restarting mesoSPIM: a running turn is cancelled, the window closes, and the next Connect
        starts fresh: the transcript and the model's memory of it are cleared, so what is on screen
        is what the model knows. A run the assistant started carries on, and the main window's
        STOP ends it."""
        if self._state == "idle":
            return
        self._release_session()
        if self._running:
            self._set_running(False)
        self._blocks, self._active = [], None
        self._show_tokens(0)
        self._render()
        self._set_connect_state("idle")

    def on_window_closed(self):
        """The window's ×: the same as Disconnect."""
        self.on_disconnect()

    def _release_session(self):
        """Stop the worker, joining with a bound so the GUI never hangs on an in-flight model call,
        and release the Core-owned Acceptor."""
        self._endpoints = {}
        self._done_check.stop()
        if self._worker is None:
            return
        self._worker.interrupt()
        if self._run_turn_slot is not None:
            self.sig_run_turn.disconnect(self._run_turn_slot)
            self.sig_check_run.disconnect(self._worker.check_run)
            self._run_turn_slot = None
        self._thread.quit()
        if not self._thread.wait(3000):         # still inside a model call: let it be, never qFatal
            self._thread.setParent(None)
            _ORPHANED_THREADS.append(self._thread)
        self._call_on_core("stop_ai_assistant")
        self._worker, self._thread = None, None

    def _connect(self):
        """Apply the three boxes. Returns True when the assistant can take a message now; False
        after a note that says what to fix."""
        if not self._ensure_worker():
            self._note(getattr(self.core, "_assistant_refusal", None)
                       or "Stop the Remote Control transport to use the AI Assistant.")
            return False
        plan = self._plan()
        if plan is None:
            return False
        self._endpoints = {role: endpoint for role, endpoint in plan.items() if endpoint is not None}
        self._use()
        return True

    def _plan(self):
        """What each box asks for, by role: an Endpoint, or None when the vision model is the
        language model. None altogether after a note that says what to fix."""
        plan = {}
        for role, picker in (("language", self.language), ("vision", self.vision)):
            if picker.same:
                plan[role] = None
            else:
                endpoint = picker.cloud_endpoint()
                if endpoint.needs_key and not endpoint.api_key:
                    key_env = config.PROVIDERS[endpoint.provider].get("key_env")
                    if role == "language":
                        self._note(f"Enter an API key for {endpoint.provider}, or set {key_env} before starting mesoSPIM.")
                        return None
                    self._note(f"Vision model {endpoint.provider} needs an API key, or {key_env} in the environment; "
                               "the language model will read frames if it can.")
                    endpoint = None
                if role == "vision" and endpoint is not None:
                    endpoint = dataclasses.replace(endpoint, vision=True)   # chosen to see, so it may
                plan[role] = endpoint
        return plan

    def _use(self):
        """Hand the endpoints to the worker; the status line says which, and the window opens."""
        language, vision = self._endpoints["language"], self._endpoints.get("vision")
        interval = float(getattr(getattr(self.core, "cfg", None), config.REQUEST_INTERVAL_CONFIG_KEY, 0) or 0)
        if interval > 0:                        # the microscope config spaces the requests, for a tight host limit
            language = dataclasses.replace(language, request_interval_s=interval)
            vision = dataclasses.replace(vision, request_interval_s=interval) if vision else None
        self._load_skills()
        self._worker.configure(language, vision)
        detail = _describe(language) + (f"; vision: {_describe(vision)}" if vision else "")
        if interval > 0:
            detail += f"; {interval:g} s between requests"
        if vision is None and not language.vision:
            detail += "; no vision: look gives the numbers only"   # the box above says how to change that
        self._set_connect_state("ready", detail)

    def _load_skills(self):
        """The microscope's skills, from the folder next to its config; the transcript says which were
        found and why a file was left out, so a lab sees at connect what the assistant will use."""
        found, problems = skill_files.load(skill_files.folder_of(getattr(self.core, "cfg", None)))
        offered = [cmd.name for cmd in offered_commands()] + ["look", "ask_eyes", "calibrate"]
        self._worker.skills = found
        lines = problems + skill_files.unknown_tools(found, offered)
        if found:
            lines.insert(0, "Skills: " + ", ".join(found))
        for line in lines:
            self._blocks.append(self._note_block(line))

    def _note(self, text):
        """What a Connect needs: on the status line, where the setup is, and in the transcript,
        where it stays readable once connected (a vision model without its key, say)."""
        self.status_label.setText(text)
        self._blocks.append(self._note_block(text))
        self._render()

    # --- transcript rendering ---
    def _user_block(self, text):
        """The question, bold on its own lighter panel. Only the operator's turns are panelled, so
        the transcript reads as the microscope answering into your log rather than as two
        symmetrical speakers — which is also what makes the 'You' label unnecessary."""
        return ('<table width="100%" cellspacing="0" cellpadding="8" style="margin:14px 0 2px 0;">'
                f'<tr><td style="background-color:{_BUBBLE};">'
                f'<b>{_htmllib.escape(text)}</b></td></tr></table>')

    def _assistant_block(self, active):
        """The answer, unbolded and unpanelled, under the commands it ran. The left margin lines it
        up with the question text inside the panel above rather than with the panel's edge. Nothing
        is emitted until the first tool call or the reply arrives — the status line already says the
        turn is running."""
        parts = []
        for name, args in active["tools"] if self.chat_window.show_tool_calls.isChecked() else ():
            parts.append(f'<div style="color:{_DIM};">&#8250; {_htmllib.escape(name)}'
                         f'({_htmllib.escape(args)})</div>')
        if active.get("served"):
            parts.append(f'<div style="color:#e0c080;"><b>&#9888;</b> {_htmllib.escape(active["served"])}</div>')
        if active["error"] is not None:
            parts.append(f'<div style="color:#e08a8a;"><b>&#9888; error</b> — '
                         f'{_htmllib.escape(active["error"])}</div>')
        elif active["reply"] is not None:
            if not active["tools"] and self.chat_window.show_tool_calls.isChecked():
                # A small model will write "I have closed the shutters" having called nothing. The
                # tab cannot judge the sentence, but it knows what it sent: said with the tool calls.
                parts.append(f'<div style="color:{_DIM};">&#8250; {_htmllib.escape(NO_COMMANDS_SENT)}</div>')
            parts.append(_md_to_html(active["reply"]))
        # Qt drops a bottom margin before the next question's table: an empty line keeps the air.
        return f'<div style="margin:12px 0 0 8px;">{"".join(parts)}</div><p style="margin:0;">&nbsp;</p>'

    def _note_block(self, text):
        return f'<div style="color:{_DIM};margin:3px 0;"><i>{_htmllib.escape(text)}</i></div>'

    def _render(self):
        output = self.chat_window.output
        blocks = [self._assistant_block(b) if isinstance(b, dict) else b for b in self._blocks]
        if self._active is not None:
            blocks.append(self._assistant_block(self._active))
        output.setHtml("".join(blocks))
        cursor = output.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)               # collapse to the end: nothing selected
        output.setTextCursor(cursor)
        output.ensureCursorVisible()                             # scroll to the newest line

    # --- input / turn lifecycle ---
    def on_submit(self):
        text = self.chat_window.input.text().strip()
        if not text or not self.chat_window.input.isEnabled() or self._state != "ready":
            return
        if self._tokens >= self._ceiling()[1]:                # the session is as large as the model takes
            self._blocks.append(self._note_block(config.CONTEXT_FULL))
            self._render()
            return
        self.chat_window.input.clear()
        self._submit(text)

    def _submit(self, text):
        """One turn: the operator's message."""
        self._blocks.append(self._user_block(text))
        self._active = {"tools": [], "reply": None, "error": None}
        self._set_running(True)
        self._render()
        self.sig_run_turn.emit(text)

    # --- the token meter ---
    def _ceiling(self):
        """The language model's (warning, ceiling) in input tokens; none for an unknown server."""
        language = self._endpoints.get("language")
        preset = config.PROVIDERS.get(language.provider, {}) if language is not None else {}
        return preset.get("context_warn_tokens", float("inf")), preset.get("context_max_tokens", float("inf"))

    def _on_usage(self, tokens):
        if tokens:                              # a provider that counted nothing keeps the last count
            self._show_tokens(tokens)

    def _show_tokens(self, tokens):
        """The meter: the last request's input tokens, a warning past the model's, and the stop."""
        self._tokens = tokens
        warn, ceiling = self._ceiling()
        text = f"{tokens:,} tokens per request" if tokens else ""
        if tokens >= ceiling:
            text += f" · {config.CONTEXT_FULL}"
        elif tokens >= warn:
            text += f" · {config.CONTEXT_LARGE}"
        self.chat_window.meter.setText(text)

    # --- the done notice ---
    def _on_run_ended(self, text):
        """The run the assistant started has ended: one grey line, no model turn."""
        self._done_check.stop()
        self._blocks.append(self._note_block(text))
        self._render()

    def on_interrupt(self):
        if not self._running:
            return                                  # nothing is running
        if self._worker is not None:
            self._worker.interrupt()
        self._blocks.append(self._note_block("[cancelled]"))
        self._render()

    def on_stop_microscope(self):
        """The emergency stop, exactly as the main window's Stop button does it and just as fast:
        from the GUI thread, the same queued signals to Core (state idle aborts the running mode,
        the time lapse is cancelled) plus the stage stop, with no assistant thread or dispatcher
        in between. The assistant is cancelled too."""
        if self._worker is not None:
            self._worker.interrupt()
        self.main_window.stop_acquisition_and_timelapse()
        self.main_window.sig_stop_movement.emit()
        self._blocks.append(self._note_block("[stop microscope]"))
        self._render()

    def on_clear_all(self):
        """Clear the transcript and the model's memory of it; the models stay connected."""
        if self._running:
            return                                  # not while a turn runs
        self._blocks = []
        self._active = None
        if self._worker is not None:
            self._worker.reset()
        self._show_tokens(0)
        self._render()

    def _set_running(self, running):
        self._running = running
        window = self.chat_window
        window.input.setEnabled(not running)
        window.clear_button.setEnabled(not running)   # the memory is cleared between turns
        window.status.setText("mesoSPIM is working…" if running else "")
        window.status.setVisible(running)
        if not running:
            window.input.setFocus()

    def _on_reply(self, text):
        if self._active is not None:
            self._active["reply"] = text
            self._render()

    def _on_tool(self, name, args):
        if self._active is not None:
            self._active["tools"].append((name, args))
            self._render()
        if name in config.RUNS_ON_ITS_OWN:
            self._done_check.start()            # the worker says when it is under way, and when it ends

    def _on_served(self, text):
        if self._active is not None:
            self._active["served"] = text
            self._render()

    def _on_error(self, message):
        if self._active is not None:
            self._active["error"] = message
            self._render()

    def _on_done(self):
        if self._active is not None:
            self._blocks.append(self._active)   # kept as the turn, so Show tool calls reaches it
            self._active = None
        self._set_running(False)
        self._render()

    def shutdown(self):
        """Called by MainWindow on app exit: release the session as Disconnect does. The
        instrument is the main window's to stop."""
        self._release_session()
        self.chat_window.hide()
