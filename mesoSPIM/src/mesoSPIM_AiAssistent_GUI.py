"""The 'AI Assistant' tab: a chat transcript styled like a coding-agent chat.

The transcript is plain on the tab's own background — no bubbles and no speaker labels, so weight
alone separates the voices: your question is bold, the answer is not. Each answer streams the
commands it runs above it, then the final Markdown. Enter submits; the input disables during a turn
(single-flight); Interrupt halts a runaway agent. The Acceptor is acquired lazily on first use —
until then the Remote Control transports stay usable, and the two are mutually exclusive.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import html as _htmllib
import os

from PyQt5 import QtCore, QtGui, QtWidgets

from . import mesoSPIM_AiAssistent_Config as config
from .mesoSPIM_AiAssistent import AssistantWorker, Endpoint

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


class AiAssistentGUI(QtWidgets.QWidget):
    sig_run_turn = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent.TabWidget)
        self.main_window = parent
        self.core = parent.core
        self.setObjectName("AiAssistentTabWidget")
        self._worker = None
        self._endpoint = None   # set by Connect; a first message connects with the current fields
        self._blocks = []       # finalized message HTML, oldest first
        self._active = None     # in-progress mesoSPIM turn: {"tools": [...], "reply": str, "error": str}
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
        self._worker.sig_error.connect(self._on_error)
        self._worker.sig_done.connect(self._on_done)
        self._thread.start()
        return True

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        font = self.font()
        font.setPointSize(12)                                     # match Remote Control

        layout.addWidget(self._build_setup(font))

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
        layout.addWidget(self.status)

        row = QtWidgets.QHBoxLayout()
        self.input = QtWidgets.QLineEdit(self)
        self.input.setPlaceholderText("Ask the microscope…")
        self.input.setObjectName("AiAssistentInput")
        self.input.setFont(font)
        self.input.returnPressed.connect(self.on_submit)
        self.interrupt = QtWidgets.QPushButton("Interrupt", self)
        self.interrupt.setFont(font)
        self.interrupt.setEnabled(False)
        self.interrupt.clicked.connect(self.on_interrupt)
        row.addWidget(self.input, 1)
        row.addWidget(self.interrupt)
        layout.addLayout(row)

    def _build_setup(self, font):
        """The endpoint row, styled like the Remote Control tab's setup group: provider and model on
        one line, the key (or base URL for a local server) with Connect and a status on the next."""
        group = QtWidgets.QGroupBox("Assistant setup", self)
        group.setObjectName("AiAssistentSetupGroupBox")
        group.setFont(font)
        rows = QtWidgets.QVBoxLayout(group)
        rows.setContentsMargins(10, 30, 10, 10)
        rows.setSpacing(8)

        self.provider = QtWidgets.QComboBox(group)
        self.provider.addItems(list(config.PROVIDERS))
        self.model = QtWidgets.QLineEdit("", group)
        self.key = QtWidgets.QLineEdit("", group)
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)        # a credential, never a caption
        self.base_url = QtWidgets.QLineEdit("", group)
        self.connect_button = QtWidgets.QPushButton("Connect", group)
        self.setup_status = QtWidgets.QLabel(group)
        self.setup_status.setText("not connected")
        self._key_label = QtWidgets.QLabel("API key", group)
        self._base_url_label = QtWidgets.QLabel("Base URL", group)
        for widget in (self.provider, self.model, self.key, self.base_url, self.connect_button,
                       self.setup_status, self._key_label, self._base_url_label):
            widget.setFont(font)

        first = QtWidgets.QHBoxLayout()
        provider_label = QtWidgets.QLabel("Provider", group)
        model_label = QtWidgets.QLabel("Model", group)
        provider_label.setFont(font)
        model_label.setFont(font)
        first.addWidget(provider_label)
        first.addWidget(self.provider, 1)
        first.addWidget(model_label)
        first.addWidget(self.model, 2)
        second = QtWidgets.QHBoxLayout()
        second.addWidget(self._key_label)
        second.addWidget(self.key, 2)
        second.addWidget(self._base_url_label)
        second.addWidget(self.base_url, 2)
        second.addWidget(self.connect_button)
        second.addWidget(self.setup_status, 1)
        rows.addLayout(first)
        rows.addLayout(second)

        self.provider.currentTextChanged.connect(self._on_provider_changed)
        self.connect_button.clicked.connect(self.on_connect)
        self.provider.setCurrentText(config.DEFAULT_PROVIDER)
        self._on_provider_changed(config.DEFAULT_PROVIDER)
        return group

    def _on_provider_changed(self, name):
        """Prefill the preset and show the field the provider needs: a key, or a base URL."""
        preset = config.PROVIDERS[name]
        local = preset["kind"] == "openai-compatible"
        self.model.setText(preset["model"])
        self.base_url.setText(preset.get("base_url", ""))
        key_env = preset.get("key_env")
        in_env = bool(key_env and os.environ.get(key_env))
        self.key.setPlaceholderText(f"using {key_env} from the environment" if in_env else f"{name} API key")
        for widget in (self._key_label, self.key):
            widget.setVisible(not local)
        for widget in (self._base_url_label, self.base_url):
            widget.setVisible(local)

    def on_connect(self):
        if self._connect():
            self._render()

    def _connect(self):
        """Apply the setup row: build the endpoint, acquire the Acceptor, hand the endpoint to the
        worker for its next turn. Returns False (with a note in the transcript) when it cannot."""
        endpoint = Endpoint.from_preset(
            self.provider.currentText(), self.model.text(), self.key.text(), self.base_url.text()
        )
        if not self._ensure_worker():
            self._note("Stop the Remote Control transport to use the AI Assistant.")
            return False
        if endpoint.needs_key and not endpoint.api_key:
            key_env = config.PROVIDERS[endpoint.provider].get("key_env")
            self._note(f"Enter an API key for {endpoint.provider}, or set {key_env} before starting mesoSPIM.")
            return False
        self._worker.configure(endpoint)
        self._endpoint = endpoint
        self.setup_status.setText(f"ready: {endpoint.describe()}")
        return True

    def _note(self, text):
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
        for name, args in active["tools"]:
            parts.append(f'<div style="color:{_DIM};">&#8250; {_htmllib.escape(name)}'
                         f'({_htmllib.escape(args)})</div>')
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
        if self._worker is not None:
            self._worker.interrupt()
        self._blocks.append(self._note_block("[interrupted]"))
        self._render()

    def _set_running(self, running):
        self.input.setEnabled(not running)
        self.interrupt.setEnabled(running)
        for widget in (self.provider, self.model, self.key, self.base_url, self.connect_button):
            widget.setEnabled(not running)                        # the endpoint changes only between turns
        self.status.setText("mesoSPIM is working…" if running else "")
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
        """Called by MainWindow on app exit: stop the agent, join with a bound so the GUI
        never hangs on an in-flight model call, and release the Core-owned Acceptor."""
        if self._worker is not None:
            stopper = self._worker.interrupt()
            self._thread.quit()
            self._thread.wait(3000)
            # The emergency stop is issued from a helper thread; give it a bounded chance to reach
            # Core before the acceptor is released (a closed acceptor refuses the dispatch).
            stopper.join(3.0)
            self._call_on_core("stop_ai_assistant")
