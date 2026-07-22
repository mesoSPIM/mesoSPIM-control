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

from PyQt5 import QtCore, QtGui, QtWidgets

from .mesoSPIM_AiAssistent import AssistantWorker

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
        if not self._ensure_worker():
            self._blocks.append(self._note_block("Stop the Remote Control transport to use the AI Assistant."))
            self._render()
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
            self._worker.interrupt()
            self._thread.quit()
            self._thread.wait(3000)
            self._call_on_core("stop_ai_assistant")
