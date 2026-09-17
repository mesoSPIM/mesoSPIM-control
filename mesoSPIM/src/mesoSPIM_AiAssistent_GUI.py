"""The 'AI Assistant' tab: a chat transcript styled like a coding-agent chat.

The transcript is plain on the tab's own background — no bubbles and no speaker labels, so weight
alone separates the voices: your question is bold, the answer is not. Each answer streams the
commands it runs above it, then the final Markdown. Enter submits; the input disables during a turn
(single-flight); Cancel request stops the assistant, Stop microscope stops the instrument. The Acceptor is acquired lazily on first use —
until then the Remote Control transports stay usable, and the two are mutually exclusive.

The endpoint setup sits under the input box as a collapsible footer: one line ("Set up AI
assistant") that expands to the setup rows. It opens itself when something needs the operator
(nothing configured, a missing key, a server that failed) and folds back once the assistant is
ready, so a first-time user sees a chat, not a configuration form.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import html as _htmllib
import os
import time

from PyQt5 import QtCore, QtGui, QtWidgets

from . import mesoSPIM_AiAssistent_Config as config
from .mesoSPIM_AiAssistent import AssistantWorker, Endpoint, vision_endpoint_for
from .mesoSPIM_AiAssistent_Local import LocalModelServer, list_models, models_folder

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
    return html[html.find(">", body) + 1:close].strip()


class _Input(QtWidgets.QPlainTextEdit):
    """A two-line message box. Enter sends; Shift+Enter starts a new line. Offers the QLineEdit
    names the tab uses (text, setText, returnPressed) so the rest of the tab does not care."""

    returnPressed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

    def text(self):
        return self.toPlainText()

    def setText(self, text):
        self.setPlainText(text)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and not event.modifiers() & QtCore.Qt.ShiftModifier:
            self.returnPressed.emit()
            return
        super().keyPressEvent(event)


class AiAssistentGUI(QtWidgets.QWidget):
    sig_run_turn = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent.TabWidget)
        self.main_window = parent
        self.core = parent.core
        self.setObjectName("AiAssistentTabWidget")
        self._worker = None
        self._endpoint = None                   # set by Connect, or by the first message
        self._local_server = None               # the child process serving a local model
        self._models_folder = models_folder(getattr(self.core, "cfg", None))
        self._single_shot = QtCore.QTimer.singleShot   # injectable for tests
        self._blocks = []                       # finalized message HTML, oldest first
        self._active = None                     # the running turn: {"tools", "reply", "error"}
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
        self.sig_run_turn.connect(self._worker.run_turn, QtCore.Qt.QueuedConnection)
        self._worker.sig_reply.connect(self._on_reply)
        self._worker.sig_tool.connect(self._on_tool)
        self._worker.sig_frame.connect(self._on_frame)
        self._worker.sig_confirm.connect(self._on_confirm)
        self._worker.sig_error.connect(self._on_error)
        self._worker.sig_done.connect(self._on_done)
        self._apply_options()
        self._thread.start()
        return True

    def _apply_profile(self, *_):
        if self._worker is not None:
            self._worker.set_profile(self.tools_profile.currentText())

    def _apply_options(self, *_):
        if self._worker is not None:
            self._worker.max_history_turns = self.history_turns.value()
            self._worker.look_image_size = self.frame_size.value()

    def _build_ui(self):
        # Only the padding: qdarkstyle's buttons hug their text, and every other property cascades.
        self.setStyleSheet("QPushButton, QToolButton { padding: 3px 12px; }"
                           "QPushButton#AiAssistentStopButton { color: #ff4d4d; font-weight: bold; }")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        font = self.font()
        font.setPointSize(12)                                     # match Remote Control

        self.output = QtWidgets.QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setObjectName("AiAssistentOutput")
        self.output.setFont(font)
        self.output.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)          # wrap; no horizontal bar
        self.output.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)   # scrollbar from the start
        layout.addWidget(self.output, 1)

        self.status = QtWidgets.QLabel("", self)
        self.status.setObjectName("AiAssistentStatus")
        self.status.setFont(font)
        self.status.setVisible(False)                             # shown only while a turn runs
        layout.addWidget(self.status)

        # The confirm-first bar: hidden until the assistant wants to run a command the operator
        # must approve; Run or Cancel answers the worker's gate.
        confirm = QtWidgets.QHBoxLayout()
        self.confirm_label = QtWidgets.QLabel(self)
        self.confirm_label.setFont(font)
        self.confirm_run = QtWidgets.QPushButton("Run", self)
        self.confirm_cancel = QtWidgets.QPushButton("Cancel", self)
        for widget in (self.confirm_run, self.confirm_cancel):
            widget.setFont(font)
        self.confirm_run.clicked.connect(lambda: self._answer_confirmation(True))
        self.confirm_cancel.clicked.connect(lambda: self._answer_confirmation(False))
        confirm.addWidget(self.confirm_label, 1)
        confirm.addWidget(self.confirm_run)
        confirm.addWidget(self.confirm_cancel)
        layout.addLayout(confirm)
        self._show_confirmation(False)

        row = QtWidgets.QHBoxLayout()
        self.input = _Input(self)
        self.input.setPlaceholderText("Ask the microscope…")
        self.input.setObjectName("AiAssistentInput")
        self.input.setFont(font)
        self.input.returnPressed.connect(self.on_submit)
        self.interrupt = QtWidgets.QPushButton("Cancel request", self)
        self.interrupt.setFont(font)
        self.interrupt.clicked.connect(self.on_interrupt)   # always clickable; a no-op between turns
        self.stop_button = QtWidgets.QPushButton("Stop microscope now", self)
        self.stop_button.setObjectName("AiAssistentStopButton")
        self.stop_button.setFont(font)
        self.stop_button.clicked.connect(self.on_stop_microscope)   # always enabled: the emergency stop
        self.new_button = QtWidgets.QPushButton("New session", self)
        self.new_button.setFont(font)
        self.new_button.clicked.connect(self.on_new_conversation)
        # Right of the two-line input: Cancel request and New session side by side, the emergency
        # stop underneath them, spanning both; the input is as tall as the two button rows.
        buttons = QtWidgets.QGridLayout()
        buttons.setHorizontalSpacing(6)
        buttons.setVerticalSpacing(6)
        buttons.addWidget(self.interrupt, 0, 0)
        buttons.addWidget(self.new_button, 0, 1)
        buttons.addWidget(self.stop_button, 1, 0, 1, 2)
        row.addWidget(self.input, 1)
        row.addLayout(buttons)
        self.input.setFixedHeight(2 * self.interrupt.sizeHint().height() + 6)
        layout.addLayout(row)
        layout.addSpacing(24)

        self.setup_toggle = QtWidgets.QToolButton(self)
        self.setup_toggle.setObjectName("AiAssistentSetupToggle")
        self.setup_toggle.setFont(font)
        self.setup_toggle.setCheckable(True)
        self.setup_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.setup_toggle.setAutoRaise(True)
        self.setup_toggle.setText("Set up AI assistant")
        self.setup_toggle.toggled.connect(self._set_expanded)
        layout.addWidget(self.setup_toggle)
        self.setup_group = self._build_setup(font)
        layout.addWidget(self.setup_group)
        self._set_expanded(False)

    def _build_setup(self, font):
        """The endpoint rows, styled like the Remote Control tab's setup group. Cloud: provider,
        model and API key. Local: one model dropdown filled from the models folder; how the file
        is served is decided behind Connect."""
        group = QtWidgets.QGroupBox(self)
        group.setObjectName("AiAssistentSetupGroupBox")
        group.setFont(font)
        rows = QtWidgets.QVBoxLayout(group)
        rows.setContentsMargins(10, 10, 10, 10)
        rows.setSpacing(8)

        def label(text):
            widget = QtWidgets.QLabel(group)
            widget.setText(text)
            widget.setFont(font)
            return widget

        self.cloud_radio = QtWidgets.QRadioButton("Cloud AI", group)
        self.local_radio = QtWidgets.QRadioButton("Local AI", group)
        self.provider = QtWidgets.QComboBox(group)
        self.provider.addItems(list(config.PROVIDERS))
        self.history_turns = QtWidgets.QSpinBox(group)
        self.history_turns.setRange(1, 200)
        self.history_turns.setValue(config.MAX_HISTORY_TURNS)
        self.history_turns.setSuffix(" turns")
        self.frame_size = QtWidgets.QSpinBox(group)
        self.frame_size.setRange(256, 4096)
        self.frame_size.setValue(config.LOOK_IMAGE_SIZE)
        self.frame_size.setSuffix(" px")
        self.vision_provider = QtWidgets.QComboBox(group)
        self.vision_provider.addItems([config.SAME_AS_MODEL] + [n for n, p in config.PROVIDERS.items() if p.get("vision")])
        self.tools_profile = QtWidgets.QComboBox(group)
        self.tools_profile.addItems(list(config.TOOL_PROFILES))
        cfg = getattr(self.core, "cfg", None)
        start = getattr(cfg, config.TOOLS_CONFIG_KEY, None)
        self.tools_profile.setCurrentText(start if start in config.TOOL_PROFILES else config.DEFAULT_TOOL_PROFILE)
        self.model = QtWidgets.QLineEdit("", group)
        self.local_model = QtWidgets.QComboBox(group)
        self.key = QtWidgets.QLineEdit("", group)
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.base_url = QtWidgets.QLineEdit("", group)
        self.folder_button = QtWidgets.QPushButton("Models folder…", group)
        self.connect_button = QtWidgets.QPushButton("Connect", group)
        self.setup_status = QtWidgets.QLabel(group)
        self.setup_status.setText("not connected")
        self.setup_status.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self._provider_label = label("Provider")
        self._model_label = label("Model")
        self._local_model_label = label("Model")
        self._key_label = label("API key")
        self._base_url_label = label("Base URL")
        for widget in (self.cloud_radio, self.local_radio, self.provider, self.model, self.local_model,
                       self.key, self.base_url, self.folder_button, self.connect_button, self.setup_status,
                       self.history_turns, self.vision_provider, self.frame_size, self.tools_profile):
            widget.setFont(font)

        # The mode on its own line, then a grid: columns 0 label | 1 field | 2 label | 3 field.
        # Row 0 is the model, row 1 the credential (or, in local mode, the folder button) and
        # Connect with its status.
        mode = QtWidgets.QHBoxLayout()
        mode.addWidget(self.cloud_radio)
        mode.addSpacing(16)
        mode.addWidget(self.local_radio)
        mode.addStretch(1)
        rows.addLayout(mode)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.addWidget(self._provider_label, 0, 0)
        grid.addWidget(self.provider, 0, 1)
        grid.addWidget(self._model_label, 0, 2)
        grid.addWidget(self.model, 0, 3)
        grid.addWidget(self._local_model_label, 0, 0)
        grid.addWidget(self.local_model, 0, 1, 1, 3)
        grid.addWidget(self.folder_button, 1, 0, 1, 2, QtCore.Qt.AlignLeft)
        grid.addWidget(self._key_label, 1, 0)
        grid.addWidget(self.key, 1, 1)
        grid.addWidget(self._base_url_label, 1, 0)
        grid.addWidget(self.base_url, 1, 1)
        connect = QtWidgets.QHBoxLayout()
        connect.addWidget(self.connect_button)
        connect.addWidget(self.setup_status, 1)
        grid.addLayout(connect, 1, 2, 1, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 2)
        rows.addLayout(grid)

        # Operator preferences, applied at once.
        options = QtWidgets.QHBoxLayout()
        options.addWidget(label("Tool set"))
        options.addWidget(self.tools_profile)
        options.addSpacing(12)
        options.addWidget(label("Memory"))
        options.addWidget(self.history_turns)
        options.addSpacing(12)
        options.addWidget(label("Vision model"))
        options.addWidget(self.vision_provider)
        options.addSpacing(12)
        options.addWidget(label("Frame"))
        options.addWidget(self.frame_size)
        options.addStretch(1)
        rows.addLayout(options)
        self.tools_profile.currentTextChanged.connect(self._apply_profile)
        self.history_turns.valueChanged.connect(self._apply_options)
        self.frame_size.valueChanged.connect(self._apply_options)

        self.cloud_radio.toggled.connect(self._on_mode_changed)
        self.local_radio.toggled.connect(self._on_mode_changed)
        self.provider.currentTextChanged.connect(self._on_provider_changed)
        self.folder_button.clicked.connect(self.on_choose_folder)
        self.connect_button.clicked.connect(self.on_connect)
        self.provider.setCurrentText(config.DEFAULT_PROVIDER)
        self._on_provider_changed(config.DEFAULT_PROVIDER)
        self.cloud_radio.setChecked(True)
        self._on_mode_changed()
        return group

    # --- the footer ---
    def _set_expanded(self, expanded):
        self.setup_group.setVisible(bool(expanded))
        self.setup_toggle.setChecked(bool(expanded))
        self.setup_toggle.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)

    # --- setup row state ---
    def _local_mode(self):
        return self.local_radio.isChecked()

    def _on_mode_changed(self, *_):
        local = self._local_mode()
        for widget in (self._provider_label, self.provider, self.model, self._model_label):
            widget.setVisible(not local)
        for widget in (self.local_model, self.folder_button, self._local_model_label):
            widget.setVisible(local)
        if local:
            for widget in (self._key_label, self.key, self._base_url_label, self.base_url):
                widget.setVisible(False)
            self._scan_models()
        else:
            self._on_provider_changed(self.provider.currentText())

    def _on_provider_changed(self, name):
        """Prefill the preset and show the field the provider needs: a key, or a base URL."""
        preset = config.PROVIDERS[name]
        server = preset["kind"] == "openai-compatible"
        self.model.setText(preset["model"])
        self.base_url.setText(preset.get("base_url", ""))
        key_env = preset.get("key_env")
        in_env = bool(key_env and os.environ.get(key_env))
        self.key.setPlaceholderText(f"using {key_env} from the environment" if in_env else f"{name} API key")
        if self._local_mode():
            return
        for widget in (self._key_label, self.key):
            widget.setVisible(not server)
        for widget in (self._base_url_label, self.base_url):
            widget.setVisible(server)

    def _scan_models(self):
        """Fill the local dropdown from the models folder; say so when it holds nothing."""
        current = self.local_model.currentText()
        names = list_models(self._models_folder)
        self.local_model.clear()
        self.local_model.addItems(names)
        if current in names:
            self.local_model.setCurrentText(current)
        self.local_model.setEnabled(bool(names))
        if not names and self._endpoint is None:
            self.setup_status.setText(f"no {'/'.join(config.MODEL_SUFFIXES)} files in {self._models_folder}")

    def on_choose_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Models folder", self._models_folder)
        if path:
            self._models_folder = path
            self._scan_models()

    # --- connecting ---
    def on_connect(self):
        self._connect()

    def _connect(self):
        """Apply the setup row. Returns True when the assistant can take a message now. A local
        model returns False while its server is still loading; the status shows the progress."""
        if not self._ensure_worker():
            self._note("Stop the Remote Control transport to use the AI Assistant.")
            return False
        return self._connect_local() if self._local_mode() else self._connect_cloud()

    def _connect_cloud(self):
        endpoint = Endpoint.from_preset(
            self.provider.currentText(), self.model.text(), self.key.text(), self.base_url.text()
        )
        if endpoint.needs_key and not endpoint.api_key:
            key_env = config.PROVIDERS[endpoint.provider].get("key_env")
            self._note(f"Enter an API key for {endpoint.provider}, or set {key_env} before starting mesoSPIM.")
            return False
        self._stop_local_server()
        self._use(endpoint)
        return True

    def _connect_local(self):
        name = self.local_model.currentText()
        if not name:
            self._note(f"Put a model file ({', '.join(config.MODEL_SUFFIXES)}) in {self._models_folder} first.")
            return False
        self._stop_local_server()
        server = LocalModelServer(os.path.join(self._models_folder, name))
        try:
            server.start()
        except (RuntimeError, OSError) as error:  # missing runtime, or the child could not spawn
            self._note(str(error))
            return False
        self._local_server = server
        self._endpoint = None
        self._started_at = time.monotonic()
        self.setup_status.setText("starting…")
        self._single_shot(config.LOCAL_SERVER_POLL_MS, self._poll_local_server)
        return False

    def _poll_local_server(self):
        server = self._local_server
        if server is None:
            return
        try:
            ready = server.ready()
        except RuntimeError as error:  # the child exited
            self._local_failed(str(error))
            return
        if ready:
            self._use(Endpoint(provider="Local", kind="openai-compatible", model=server.model, base_url=server.base_url),
                      status=f"ready on 127.0.0.1:{server.port}")
        elif time.monotonic() - self._started_at > config.LOCAL_SERVER_TIMEOUT_S:
            self._local_failed(f"{server.model} did not answer within {config.LOCAL_SERVER_TIMEOUT_S} s; see {server.log_path}")
        else:
            self._single_shot(config.LOCAL_SERVER_POLL_MS, self._poll_local_server)

    def _local_failed(self, message):
        self._stop_local_server()
        self._endpoint = None
        self.setup_status.setText("not connected")
        self._note(message)

    def _use(self, endpoint, status=None):
        self._worker.configure(endpoint, self._vision_endpoint(), self.tools_profile.currentText())
        self._endpoint = endpoint
        self.setup_status.setText(status or "ready")
        self._set_expanded(False)

    def _vision_endpoint(self):
        """The dedicated frame reader chosen in the options row, or None for the main model."""
        chosen = self.vision_provider.currentText()
        reader = vision_endpoint_for(chosen)
        if chosen != config.SAME_AS_MODEL and reader is None:
            key_env = config.PROVIDERS[chosen].get("key_env")
            self._note(f"Vision model {chosen} needs {key_env} in the environment; the main model will read frames if it can.")
        return reader

    def _stop_local_server(self):
        server, self._local_server = self._local_server, None
        if server is not None:
            server.stop()

    def _note(self, text):
        """A note in the transcript about the setup; the footer opens so the fix is in view."""
        self._blocks.append(self._note_block(text))
        self._render()
        self._set_expanded(True)

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
        for name, args in active["tools"]:
            parts.append(f'<div style="color:{_DIM};">&#8250; {_htmllib.escape(name)}'
                         f'({_htmllib.escape(args)})</div>')
        for png in active.get("frames", ()):
            # what the vision model was shown, so the operator sees it too
            parts.append(f'<div><img src="data:image/png;base64,{png}" width="320"></div>')
        if active["error"] is not None:
            parts.append(f'<div style="color:#e08a8a;"><b>&#9888; error</b> — '
                         f'{_htmllib.escape(active["error"])}</div>')
        elif active["reply"] is not None:
            parts.append(_md_to_html(active["reply"]))
        return f'<div style="margin:2px 0 16px 8px;">{"".join(parts)}</div>'

    def _note_block(self, text):
        return f'<div style="color:{_DIM};margin:3px 0;"><i>{_htmllib.escape(text)}</i></div>'

    def _render(self):
        blocks = list(self._blocks)
        if self._active is not None:
            blocks.append(self._assistant_block(self._active))
        self.output.setHtml("".join(blocks))
        cursor = self.output.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)               # collapse to the end: nothing selected
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()                        # scroll to the newest line

    # --- input / turn lifecycle ---
    def on_submit(self):
        text = self.input.text().strip()
        if not text or not self.input.isEnabled():
            return
        if self._endpoint is None and not self._connect():   # a first message connects as typed
            return
        self.input.clear()
        self._blocks.append(self._user_block(text))
        self._active = {"tools": [], "reply": None, "error": None}   # mesoSPIM header appears at once
        self._set_running(True)
        self._render()
        self.sig_run_turn.emit(text)

    def on_interrupt(self):
        if self.input.isEnabled():
            return                                  # nothing is running
        if self._worker is not None:
            self._worker.interrupt()
        self._show_confirmation(False)
        self._blocks.append(self._note_block("[cancelled]"))
        self._render()

    def on_stop_microscope(self):
        """The emergency stop, exactly as the main window's Stop button does it and just as fast:
        from the GUI thread, the same queued signals to Core (state idle aborts the running mode,
        the time lapse is cancelled) plus the stage stop, with no assistant thread or dispatcher
        in between. Works before the assistant has ever connected. The assistant is cancelled too."""
        if self._worker is not None:
            self._worker.interrupt()
        self.main_window.stop_acquisition_and_timelapse()
        self.main_window.sig_stop_movement.emit()
        self._show_confirmation(False)
        self._blocks.append(self._note_block("[stop microscope now]"))
        self._render()

    def on_new_conversation(self):
        """New session: clear the transcript and the model's memory of it; the endpoint stays."""
        if not self.input.isEnabled():
            return                                  # not while a turn runs
        self._blocks = []
        self._active = None
        if self._worker is not None:
            self._worker.reset()
        self._render()

    # --- confirm-first commands ---
    def _show_confirmation(self, visible):
        for widget in (self.confirm_label, self.confirm_run, self.confirm_cancel):
            widget.setVisible(visible)

    def _on_confirm(self, name, args):
        self._pending_confirmation = name
        self.confirm_label.setText(f"The assistant wants to run {name} {args}. Run it?")
        self._show_confirmation(True)

    def _answer_confirmation(self, allowed):
        name = getattr(self, "_pending_confirmation", None)
        self._show_confirmation(False)
        if self._worker is not None:
            self._worker.gate.answer(allowed)
        verdict = "confirmed" if allowed else "cancelled"
        self._blocks.append(self._note_block(f"[{verdict} {name}]"))
        self._render()

    def _set_running(self, running):
        self.input.setEnabled(not running)
        for widget in (self.cloud_radio, self.local_radio, self.provider, self.model, self.local_model,
                       self.key, self.base_url, self.folder_button, self.connect_button, self.new_button,
                       self.vision_provider, self.tools_profile):
            widget.setEnabled(not running)      # the endpoint and tool set change only between turns
        if running:
            self._set_expanded(False)
        self.status.setText("mesoSPIM is working…" if running else "")
        self.status.setVisible(running)
        if not running:
            self.input.setFocus()

    def _on_reply(self, text):
        if self._active is not None:
            self._active["reply"] = text
            self._render()

    def _on_tool(self, name, args):
        if self._active is not None:
            self._active["tools"].append((name, args))
            self._render()

    def _on_frame(self, png):
        if self._active is not None:
            self._active.setdefault("frames", []).append(png)
            self._render()

    def _on_error(self, message):
        if self._active is not None:
            self._active["error"] = message
            self._render()

    def _on_done(self):
        if self._active is not None:
            self._blocks.append(self._assistant_block(self._active))
            self._active = None
        self._set_running(False)
        self._render()

    def shutdown(self):
        """Called by MainWindow on app exit: stop the assistant, join with a bound so the GUI
        never hangs on an in-flight model call, release the Core-owned Acceptor, and stop a
        local model server. The instrument is the main window's to stop."""
        self._stop_local_server()
        if self._worker is not None:
            self._worker.interrupt()
            self._thread.quit()
            self._thread.wait(3000)
            self._call_on_core("stop_ai_assistant")
