"""AiAssistentGUI logic, from source, using the QtWidgets stub in conftest.

The real QThread / worker hand-off is a real-PyQt concern (the smoke layer); here we test the
tab wiring, the transport-busy refusal, and the single-flight input lock in isolation.
"""
import types

from PyQt5 import QtCore, QtWidgets

from mesoSPIM.src import mesoSPIM_AiAssistent_GUI as gui_module
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

def _gui():
    return AiAssistentGUI(_FakeParent(_FakeCore(acceptor=object())))


def test_setup_row_prefills_the_default_provider():
    gui = _gui()
    assert gui.provider.currentText() == "Gemini"
    assert gui.model.text() == "gemini-3.5-flash-lite"
    assert gui.key.isVisible() and not gui.base_url.isVisible()
    assert gui.setup_status.text() == "not connected"


def test_choosing_a_local_provider_swaps_the_key_for_a_base_url():
    gui = _gui()
    gui.provider.setCurrentText("OpenAI-compatible server")
    gui.provider.currentTextChanged.emit("OpenAI-compatible server")
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
    assert gui.setup_status.text() == "ready"


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


# --- local mode: one model dropdown, the serving decided behind Connect ---

_SERVERS = []  # every _FakeServer built, so a test can inspect the ones the tab started


class _FakeServer:
    """A LocalModelServer stand-in: ready after `ready_after` polls, or dies with `error`."""

    def __init__(self, model_path, ready_after=2, error=None):
        self.model_path = model_path
        self.model = model_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        self.port = 4242
        self.base_url = "http://127.0.0.1:4242/v1"
        self.log_path = "/tmp/fake.log"
        self.polls = 0
        self.started = False
        self.stopped = False
        self._ready_after = ready_after
        self._error = error
        _SERVERS.append(self)

    def start(self):
        self.started = True

    def ready(self):
        self.polls += 1
        if self._error:
            raise RuntimeError(self._error)
        return self.polls >= self._ready_after

    def stop(self):
        self.stopped = True


def _local_gui(tmp_path, monkeypatch, server_factory=_FakeServer):
    (tmp_path / "qwen3.5-8b-q4.gguf").write_bytes(b"")
    (tmp_path / "gemma-4-12b-q4.gguf").write_bytes(b"")
    (tmp_path / "readme.txt").write_bytes(b"")
    core = _FakeCore(acceptor=object())
    core.cfg = types.SimpleNamespace(ai_assistant_models_folder=str(tmp_path))
    gui = AiAssistentGUI(_FakeParent(core))
    gui._worker = type("_Worker", (), {"configure": lambda self, endpoint: setattr(self, "endpoint", endpoint)})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    monkeypatch.setattr(gui_module, "LocalModelServer", server_factory)
    scheduled = []
    gui._single_shot = lambda ms, fn: scheduled.append(fn)   # the test drives the polls
    _SERVERS.clear()
    return gui, scheduled


def test_local_mode_lists_model_files_and_hides_the_key(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    assert gui.provider.isVisible() and not gui.local_model.isVisible()
    gui.local_radio.setChecked(True)
    assert gui.local_model.items() == ["gemma-4-12b-q4.gguf", "qwen3.5-8b-q4.gguf"]
    assert gui.local_model.isVisible() and gui.folder_button.isVisible()
    assert not gui.key.isVisible() and not gui.provider.isVisible() and not gui.model.isVisible()


def test_local_connect_starts_the_server_and_configures_when_ready(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    gui.local_radio.setChecked(True)
    gui.local_model.setCurrentText("qwen3.5-8b-q4.gguf")
    gui.on_connect()
    (server,) = _SERVERS
    assert server.started and server.model_path == str(tmp_path / "qwen3.5-8b-q4.gguf")
    assert gui.setup_status.text() == "starting…"
    assert gui._endpoint is None
    scheduled.pop()()                                          # first poll: still loading
    assert gui._endpoint is None and len(scheduled) == 1
    scheduled.pop()()                                          # second poll: ready
    endpoint = gui._worker.endpoint
    assert (endpoint.kind, endpoint.model, endpoint.base_url) == ("openai-compatible", "qwen3.5-8b-q4", server.base_url)
    assert endpoint.api_key == "" and not endpoint.needs_key
    assert gui.setup_status.text() == "ready on 127.0.0.1:4242"
    assert scheduled == []


def test_local_server_failure_is_reported_and_cleaned_up(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch,
                                server_factory=lambda path: _FakeServer(path, error="exited with code 3"))
    gui.local_radio.setChecked(True)
    gui.on_connect()
    scheduled.pop()()
    (server,) = _SERVERS
    assert server.stopped and gui._local_server is None
    assert gui.setup_status.text() == "not connected"
    assert "exited with code 3" in gui.output.toPlainText()


def test_switching_models_or_going_cloud_stops_the_previous_server(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    gui.local_radio.setChecked(True)
    gui.on_connect()
    first = _SERVERS[-1]
    gui.on_connect()                                           # a second Connect replaces the child
    assert first.stopped and len(_SERVERS) == 2
    gui.cloud_radio.setChecked(True)
    gui.key.setText("k")
    gui.on_connect()
    assert _SERVERS[-1].stopped and gui._local_server is None


def test_empty_models_folder_is_explained(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    for name in ("qwen3.5-8b-q4.gguf", "gemma-4-12b-q4.gguf"):
        (tmp_path / name).unlink()
    gui.local_radio.setChecked(True)
    assert gui.local_model.items() == [] and not gui.local_model.isEnabled()
    assert str(tmp_path) in gui.setup_status.text()
    gui.on_connect()
    assert "Put a model file" in gui.output.toPlainText()


def test_choosing_a_folder_rescans(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    other = tmp_path / "other"
    other.mkdir()
    (other / "phi.gguf").write_bytes(b"")
    gui.local_radio.setChecked(True)
    QtWidgets.QFileDialog.chosen = str(other)
    gui.on_choose_folder()
    QtWidgets.QFileDialog.chosen = ""
    assert gui._models_folder == str(other)
    assert gui.local_model.items() == ["phi.gguf"]


# --- the collapsible footer ---

def test_setup_starts_collapsed_with_an_inviting_summary():
    gui = _gui()
    assert not gui.expanded()
    assert gui.setup_toggle.text() == "Set up AI assistant"
    assert gui.setup_toggle.arrowType() == QtCore.Qt.RightArrow


def test_toggle_expands_and_collapses():
    gui = _gui()
    gui.setup_toggle.setChecked(True)
    assert gui.expanded() and gui.setup_toggle.arrowType() == QtCore.Qt.DownArrow
    gui.setup_toggle.setChecked(False)
    assert not gui.expanded()


def test_a_problem_opens_the_footer(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gui = _gui()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.input.setText("hello")
    gui.on_submit()                                            # nothing configured, no key
    assert gui.expanded()
    assert "Enter an API key" in gui.output.toPlainText()


def test_ready_folds_the_footer_and_keeps_the_label(monkeypatch):
    gui = _gui()
    gui._worker = type("_Worker", (), {"configure": lambda self, endpoint: None})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.setup_toggle.setChecked(True)
    gui.key.setText("g-key")
    gui.on_connect()
    assert not gui.expanded()
    assert gui.setup_toggle.text() == "Set up AI assistant"
    assert gui.setup_status.text() == "ready"


def test_local_status_moves_from_starting_to_ready(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    gui.local_radio.setChecked(True)
    gui.on_connect()
    assert gui.setup_status.text() == "starting…"
    scheduled.pop()(); scheduled.pop()()
    assert not gui.expanded()
    assert gui.setup_status.text() == "ready on 127.0.0.1:4242"
    assert gui.setup_toggle.text() == "Set up AI assistant"
