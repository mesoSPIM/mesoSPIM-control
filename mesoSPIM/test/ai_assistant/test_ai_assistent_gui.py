"""AiAssistentGUI logic, from source, using the QtWidgets stub in conftest.

The real QThread / worker hand-off is a real-PyQt concern (the smoke layer); here we test the
tab wiring, the transport-busy refusal, and the single-flight input lock in isolation.
"""
from mesoSPIM.src.mesoSPIM_AiAssistent_GUI import AiAssistentGUI


class _FakeTabWidget:
    def __init__(self):
        self._tabs = []

    def indexOf(self, widget):
        return self._tabs.index(widget) if widget in self._tabs else -1

    def addTab(self, widget, _label):
        self._tabs.append(widget)

    def insertTab(self, index, widget, _label):
        self._tabs.insert(index, widget)


class _FakeCore:
    """Records the assistant slots MainWindow would invoke and hands back an acceptor (or not)."""

    def __init__(self, acceptor):
        self._acceptor = acceptor
        self._assistant_acceptor = None
        self.calls = []

    def start_ai_assistant(self):
        self.calls.append("start_ai_assistant")
        self._assistant_acceptor = self._acceptor      # None simulates a busy transport

    def stop_ai_assistant(self):
        self.calls.append("stop_ai_assistant")
        self._assistant_acceptor = None


class _FakeParent:
    def __init__(self, core):
        self.TabWidget = _FakeTabWidget()
        self.remote_control = object()
        self.TabWidget.addTab(self.remote_control, "Remote Control")
        self.core = core


def _collect(signal):
    got = []
    signal.connect(lambda *a: got.append(a[0] if len(a) == 1 else a))
    return got


def test_tab_inserts_after_remote_control():
    gui = AiAssistentGUI(_FakeParent(_FakeCore(acceptor=object())))
    tabs = gui.main_window.TabWidget
    assert tabs.indexOf(gui) == tabs.indexOf(gui.main_window.remote_control) + 1


def test_submit_refused_when_transport_busy():
    core = _FakeCore(acceptor=None)                     # start_ai_assistant leaves _assistant_acceptor None
    gui = AiAssistentGUI(_FakeParent(core))
    sent = _collect(gui.sig_run_turn)
    gui.input.setText("hi")
    gui.on_submit()
    assert core.calls == ["start_ai_assistant"]         # Core was asked, on its own thread
    assert sent == []                                   # nothing dispatched
    assert gui.input.isEnabled() is True                # input stays usable
    assert "Stop the Remote Control transport" in gui.output.toPlainText()


def test_submit_single_flight_disables_input(monkeypatch):
    gui = AiAssistentGUI(_FakeParent(_FakeCore(acceptor=object())))
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)   # pretend ready; no real thread
    sent = _collect(gui.sig_run_turn)
    gui.input.setText("hello")
    gui.on_submit()
    assert sent == ["hello"]
    assert gui.input.isEnabled() is False               # single-flight: locked until the turn ends
    assert gui.input.text() == ""                       # the submitted text was cleared
