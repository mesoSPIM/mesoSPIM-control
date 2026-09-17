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
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    gui._worker = type("_Worker", (), {"configure": lambda self, endpoint: None})()
    sent = _collect(gui.sig_run_turn)
    gui.input.setText("hello")
    gui.on_submit()
    assert sent == ["hello"]
    assert gui.input.isEnabled() is False               # single-flight: locked until the turn ends
    assert gui.input.text() == ""                       # the submitted text was cleared


# --- the setup row ---

def _gui(acceptor=object()):
    return AiAssistentGUI(_FakeParent(_FakeCore(acceptor=acceptor)))


def test_setup_row_prefills_the_default_provider():
    gui = _gui()
    assert gui.provider.currentText() == "Gemini"
    assert gui.model.text() == "gemini-3.5-flash-lite"
    assert gui.key.isVisible() and not gui.base_url.isVisible()
    assert gui.setup_status.text() == "not connected"


def test_choosing_a_local_provider_swaps_the_key_for_a_base_url():
    gui = _gui()
    gui.provider.setCurrentText("OpenAI-compatible (local)")
    gui.provider.currentTextChanged.emit("OpenAI-compatible (local)")
    assert gui.model.text() == "gemma4:31b"
    assert gui.base_url.text() == "http://localhost:11434/v1"
    assert gui.base_url.isVisible() and not gui.key.isVisible()


def test_connect_without_a_key_explains_and_does_not_start(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gui = _gui()
    configured = []
    gui._worker = type("_Worker", (), {"configure": lambda self, endpoint: configured.append(endpoint)})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.on_connect()
    assert configured == [] and gui._endpoint is None         # nothing configured
    assert "Enter an API key for Gemini" in gui.output.toPlainText()
    assert "GEMINI_API_KEY" in gui.output.toPlainText()


def test_connect_with_a_key_configures_the_worker(monkeypatch):
    gui = _gui()
    configured = []

    class _Worker:
        def configure(self, endpoint):
            configured.append(endpoint)

    gui._worker = _Worker()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.provider.setCurrentText("Anthropic")
    gui.provider.currentTextChanged.emit("Anthropic")
    gui.key.setText("sk-test")
    gui.on_connect()
    (endpoint,) = configured
    assert (endpoint.provider, endpoint.kind, endpoint.api_key) == ("Anthropic", "anthropic", "sk-test")
    assert gui.setup_status.text() == "ready: Anthropic, claude-sonnet-5"


def test_first_message_connects_with_the_typed_key(monkeypatch):
    gui = _gui()
    configured = []

    class _Worker:
        def configure(self, endpoint):
            configured.append(endpoint)

    gui._worker = _Worker()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.key.setText("g-key")
    sent = _collect(gui.sig_run_turn)
    gui.input.setText("hello")
    gui.on_submit()
    assert [e.api_key for e in configured] == ["g-key"]
    assert sent == ["hello"]
    assert gui.connect_button.isEnabled() is False           # setup is locked while the turn runs


def test_submit_without_key_or_environment_does_not_send(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gui = _gui()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    sent = _collect(gui.sig_run_turn)
    gui.input.setText("hello")
    gui.on_submit()
    assert sent == []
    assert gui.input.text() == "hello"                        # kept, so the operator can connect and resend
