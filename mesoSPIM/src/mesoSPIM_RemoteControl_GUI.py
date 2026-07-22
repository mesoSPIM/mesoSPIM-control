"""Provide the operator-facing controls for mesoSPIM Remote Control.

The GUI lets the operator choose TCP or MCP, enter the host, port, and password, and explicitly
start or stop the selected transport. It displays the result reported by Core and never marks a
server as running before binding succeeds. Only one transport can run in a session, and neither is
started automatically when mesoSPIM opens.

The class also supplies the small, thread-safe bridge needed to keep a remotely installed
acquisition list synchronized with the visible mesoSPIM table. Network protocols, validation, and
hardware calls deliberately live in the other Remote Control modules. MainWindow only constructs
this widget and calls ``shutdown`` during application exit.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

from PyQt5 import QtCore, QtWidgets

from . import mesoSPIM_RemoteControl_Config as config


class RemoteControlGUI(QtWidgets.QWidget):
    """Self-contained Remote Control GUI.

    Start is queued to Core so the transport is created on its owning thread. Stop blocks until Core
    has unbound it. The acquisition-list bridge blocks in the opposite direction just long enough to
    reset the GUI model on its owning thread. MainWindow keeps only a handle and calls shutdown().
    """

    # Signal arguments are mode, host, port, and password.
    sig_start_remote_control = QtCore.pyqtSignal(str, str, int, str)
    sig_stop_remote_control = QtCore.pyqtSignal()
    sig_install_acquisition_list = QtCore.pyqtSignal(object, object)

    def __init__(self, parent):
        super().__init__(parent.TabWidget)

        # Use MainWindow as the modal-dialog parent so warnings remain centred on the application.
        self.main_window = parent
        self.core = parent.core
        self.running = False
        self.mode = config.DEFAULT_MODE
        self.host = config.DEFAULT_HOST
        self.port = config.DEFAULT_TCP_PORT
        self.token = config.DEFAULT_TOKEN
        self.setObjectName("RemoteControlTabWidget")
        self._build_ui()
        try:
            separate_threads = self.core.thread() is not self.thread()
        except AttributeError:
            # Small Qt-free test doubles do not expose a thread-affinity API.
            separate_threads = False

        blocking = QtCore.Qt.BlockingQueuedConnection if separate_threads else QtCore.Qt.DirectConnection
        self.sig_start_remote_control.connect(self.core.start_remote_control, type=QtCore.Qt.QueuedConnection)
        self.sig_stop_remote_control.connect(self.core.stop_remote_control, type=blocking)
        self.sig_install_acquisition_list.connect(self.install_acquisition_list, type=blocking)
        # Commands run on Core's thread. Publishing this bound signal avoids adding acquisition-table
        # plumbing to Core/MainWindow while still performing the Qt model reset on the GUI thread.
        self.core._remote_control_acquisition_list_signal = self.sig_install_acquisition_list
        self.core.sig_remote_control_started.connect(self.on_started)
        index = parent.TabWidget.indexOf(parent.TimelapseTabWidget)
        if index >= 0:
            parent.TabWidget.insertTab(index + 1, self, "Remote Control")
        else:
            parent.TabWidget.addTab(self, "Remote Control")
        self.refresh()

    def _build_ui(self):
        """Build the tab the way MainWindow builds its tabs: a titled group box, a form of inputs,
        a Start/Stop button row. Object names are kept stable so a .ui or a test can find them."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        group = QtWidgets.QGroupBox("Setup remote control", self)
        group.setObjectName("RemoteControlSetupGroupBox")
        font = group.font()
        font.setPointSize(12)
        group.setFont(font)
        form = QtWidgets.QFormLayout(group)
        form.setContentsMargins(10, 30, 10, 10)
        form.setSpacing(8)

        self.RemoteControlModeComboBox = QtWidgets.QComboBox(group)
        self.RemoteControlModeComboBox.addItems(list(config.TRANSPORT_MODES))
        self.RemoteControlModeComboBox.setCurrentText(self.mode)
        self.RemoteControlHostLineEdit = QtWidgets.QLineEdit(self.host, group)
        self.RemoteControlPortLineEdit = QtWidgets.QLineEdit(str(self.port), group)
        self.RemoteControlTokenLineEdit = QtWidgets.QLineEdit(self.token, group)
        # The password is a credential, not a caption, so keep it masked on screen.
        self.RemoteControlTokenLineEdit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.RemoteControlStatusLabel = QtWidgets.QLabel(group)
        for widget in self._inputs():
            widget.setFont(font)
        self.RemoteControlStatusLabel.setFont(font)

        def form_label(text):
            label = QtWidgets.QLabel(text, group)
            label.setFont(font)
            return label

        form.addRow(form_label("Protocol"), self.RemoteControlModeComboBox)
        form.addRow(form_label("Host"), self.RemoteControlHostLineEdit)
        form.addRow(form_label("Port"), self.RemoteControlPortLineEdit)
        form.addRow(form_label("Password"), self.RemoteControlTokenLineEdit)
        form.addRow(form_label("Status"), self.RemoteControlStatusLabel)

        self.RemoteControlStartButton = QtWidgets.QPushButton("Start", group)
        self.RemoteControlStopButton = QtWidgets.QPushButton("Stop", group)
        self.RemoteControlStartButton.setFont(font)
        self.RemoteControlStopButton.setFont(font)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.RemoteControlStartButton)
        buttons.addWidget(self.RemoteControlStopButton)
        form.addRow(buttons)
        layout.addWidget(group)
        layout.addStretch(1)

        self.RemoteControlStartButton.clicked.connect(self.start)
        self.RemoteControlStopButton.clicked.connect(self.stop)
        self.RemoteControlModeComboBox.currentTextChanged.connect(self.on_mode_changed)

    def _inputs(self):
        return (
            self.RemoteControlModeComboBox,
            self.RemoteControlHostLineEdit,
            self.RemoteControlPortLineEdit,
            self.RemoteControlTokenLineEdit,
        )

    def start(self):
        """Validate the operator's inputs and ask Core to bind the one transport they chose. Core
        reports the outcome back through on_started(); the tab shows 'running' only if it succeeds."""
        try:
            port = int(self.RemoteControlPortLineEdit.text())
        except ValueError:
            self._warn("Port must be a number.")
            return
        if not 1 <= port <= 65535:
            self._warn("Port must be between 1 and 65535.")
            return
        host = self.RemoteControlHostLineEdit.text().strip() or config.DEFAULT_HOST
        token = self.RemoteControlTokenLineEdit.text().strip()
        if not token:
            self._warn("Password is required.")
            return
        self.host, self.port, self.token = host, port, token
        self.mode = self.RemoteControlModeComboBox.currentText()
        self.sig_start_remote_control.emit(self.mode, host, port, token)

    def stop(self):
        self.sig_stop_remote_control.emit()
        self.running = False
        self.refresh()

    def shutdown(self):
        """Tell Core to stop during application exit, including an in-flight start request."""
        self.sig_stop_remote_control.emit()
        self.running = False

    @QtCore.pyqtSlot(object, object)
    def install_acquisition_list(self, acquisitions, selected_row):
        """Replace the GUI table with the list already installed in Core, on the GUI thread."""
        manager = self.main_window.acquisition_manager_window
        row = manager.get_first_selected_row() if selected_row is None else selected_row
        manager.model.setTable(acquisitions)
        manager.update_acquisition_time_prediction()
        manager.update_acquisition_size_prediction()
        if row is not None and 0 <= row < len(acquisitions):
            manager.set_selected_row(row)

    def on_started(self, ok, message):
        """Core's queued report of a start attempt. On failure the transport did NOT bind, so the
        tab must not show 'running' -- warn with the reason (bad port, self-test failed) instead."""
        self.running = ok
        if not ok:
            self._warn(f"Could not start the server: {message}")
        self.refresh()

    def on_mode_changed(self, _mode):
        self.update_mode_note()
        self.refresh()

    def update_mode_note(self):
        """Swap in the other protocol's default port, but never override a port the operator typed."""
        text = self.RemoteControlPortLineEdit.text()
        if self.RemoteControlModeComboBox.currentText() == "MCP":
            if text == str(config.DEFAULT_TCP_PORT):
                self.RemoteControlPortLineEdit.setText(str(config.DEFAULT_MCP_PORT))
        elif text == str(config.DEFAULT_MCP_PORT):
            self.RemoteControlPortLineEdit.setText(str(config.DEFAULT_TCP_PORT))

    def refresh(self):
        if self.running:
            self.RemoteControlStatusLabel.setText(f"{self.mode} running on {self.host}:{self.port}")
        else:
            self.RemoteControlStatusLabel.setText("stopped")
        self.RemoteControlStartButton.setEnabled(not self.running)
        self.RemoteControlStopButton.setEnabled(self.running)
        for widget in self._inputs():
            widget.setEnabled(not self.running)

    def _warn(self, message):
        QtWidgets.QMessageBox.warning(self.main_window, "Remote Control", message)
