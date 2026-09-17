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


class _Signal:
    """A bound signal stand-in: connect stores slots, emit calls them."""

    def __init__(self):
        self._slots = []

    def connect(self, slot, *_a, **_k):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _FakeParent:
    """MainWindow as the tab sees it, including the Stop button's method and the stage stop."""

    def __init__(self, core):
        self.TabWidget = _FakeTabWidget()
        self.remote_control = object()
        self.TabWidget.addTab(self.remote_control, "Remote Control")
        self.core = core
        self.stops = 0
        self.sig_stop_movement = _Signal()

    def stop_acquisition_and_timelapse(self):
        self.stops += 1


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
    gui._worker = type("_Worker", (), {"configure": lambda self, endpoint, vision=None, profile=None: None})()
    sent = _collect(gui.sig_run_turn)
    gui.input.setText("hello")
    gui.on_submit()
    assert sent == ["hello"]
    assert gui.input.isEnabled() is False               # single-flight: locked until the turn ends
    assert gui.send_button.isEnabled() is False         # and so is the mouse's way in
    assert gui.input.text() == ""                       # the submitted text was cleared


# --- the setup row ---

def _gui():
    return AiAssistentGUI(_FakeParent(_FakeCore(acceptor=object())))


def test_setup_row_prefills_the_default_provider():
    gui = _gui()
    assert gui.language.provider.currentText() == "Gemini"
    assert gui.language.model.text() == "gemini-3.5-flash-lite"
    assert gui.language.key.isVisible() and not gui.language.base_url.isVisible()
    assert gui.connect_button.text() == "Connect"


def test_an_openai_style_server_adds_a_base_url_and_keeps_an_optional_key():
    gui = _gui()
    gui.language.provider.setCurrentText("OpenAI-style")
    gui.language.provider.currentTextChanged.emit("OpenAI-style")
    assert gui.language.model.text() == "gemma4:31b"
    assert gui.language.base_url.text() == "http://localhost:11434/v1"
    assert gui.language.base_url.isVisible() and gui.language.key.isVisible()
    assert gui.language.key.placeholderText() == "optional"


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
        def configure(self, endpoint, vision=None, profile=None):
            configured.append(endpoint)

    gui._worker = _Worker()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.language.provider.setCurrentText("Anthropic")
    gui.language.provider.currentTextChanged.emit("Anthropic")
    gui.language.key.setText("sk-test")
    gui.on_connect()
    (endpoint,) = configured
    assert (endpoint.provider, endpoint.kind, endpoint.api_key) == ("Anthropic", "anthropic", "sk-test")
    assert gui.connect_button.text() == "Connected"


def test_openai_style_connects_without_a_key_and_passes_one_through(monkeypatch):
    gui = _gui()
    configured = []

    class _Worker:
        def configure(self, endpoint, vision=None, profile=None):
            configured.append(endpoint)

    gui._worker = _Worker()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.language.provider.setCurrentText("OpenAI-style")
    gui.language.provider.currentTextChanged.emit("OpenAI-style")
    gui.language.base_url.setText("http://box:8000/v1")
    gui.on_connect()                                       # an Ollama-like server: no key
    gui.language.key.setText("gw-token")
    gui.on_connect()                                       # a gateway: the token goes through
    without, with_key = configured
    assert (without.kind, without.base_url, without.api_key) == ("openai-compatible", "http://box:8000/v1", "")
    assert with_key.api_key == "gw-token"
    assert gui.connect_button.text() == "Connected"


def test_first_message_connects_with_the_typed_key(monkeypatch):
    gui = _gui()
    configured = []

    class _Worker:
        def configure(self, endpoint, vision=None, profile=None):
            configured.append(endpoint)

    gui._worker = _Worker()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.language.key.setText("g-key")
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

    def __init__(self, model_path, ready_after=2, error=None, projector=None):
        self.model_path = model_path
        self.projector = projector
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
    gui._worker = type("_Worker", (), {"configure": lambda self, endpoint, vision=None, profile=None: setattr(self, "endpoint", endpoint)})()
    monkeypatch.setenv("GEMINI_API_KEY", "g")                      # the default cloud language model connects
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    monkeypatch.setattr(gui_module, "LocalModelServer", server_factory)
    scheduled = []
    gui._single_shot = lambda ms, fn: scheduled.append(fn)   # the test drives the polls
    _SERVERS.clear()
    return gui, scheduled


def _choose_mode(gui, mode, picker=None):
    picker = picker or gui.language
    picker.mode.setCurrentText(mode)
    picker.mode.currentTextChanged.emit(mode)


def _choose_provider(picker, name):
    picker.provider.setCurrentText(name)
    picker.provider.currentTextChanged.emit(name)


def test_local_mode_lists_model_files_and_swaps_the_cloud_fields(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    assert gui.language.provider.isVisible() and not gui.language.local_model.isVisible()
    _choose_mode(gui, "Local AI")
    assert gui.language.local_model.items() == ["gemma-4-12b-q4.gguf", "qwen3.5-8b-q4.gguf"]
    assert gui.language.local_model.isVisible() and gui.language.folder_button.isVisible()
    assert not gui.language.key.isVisible() and not gui.language.provider.isVisible() and not gui.language.model.isVisible()
    _choose_mode(gui, "Cloud AI")
    assert gui.language.provider.isVisible() and not gui.language.local_model.isVisible()


def test_local_connect_starts_the_server_and_configures_when_ready(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    _choose_mode(gui, "Local AI")
    gui.language.local_model.setCurrentText("qwen3.5-8b-q4.gguf")
    gui.on_connect()
    (server,) = _SERVERS
    assert server.started and server.model_path == str(tmp_path / "qwen3.5-8b-q4.gguf")
    assert gui.connect_button.text() == "Starting…"
    assert gui._endpoint is None
    scheduled.pop()()                                          # first poll: still loading
    assert gui._endpoint is None and len(scheduled) == 1
    scheduled.pop()()                                          # second poll: ready
    endpoint = gui._worker.endpoint
    assert (endpoint.kind, endpoint.model, endpoint.base_url) == ("openai-compatible", "qwen3.5-8b-q4", server.base_url)
    assert endpoint.api_key == "" and not endpoint.needs_key
    assert gui.connect_button.text() == "Connected"
    assert scheduled == []


def test_local_server_failure_is_reported_and_cleaned_up(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch,
                                server_factory=lambda path, projector=None: _FakeServer(path, error="exited with code 3"))
    _choose_mode(gui, "Local AI")
    gui.on_connect()
    scheduled.pop()()
    (server,) = _SERVERS
    assert server.stopped and gui._servers == {}
    assert gui.connect_button.text() == "Connect"
    assert "exited with code 3" in gui.output.toPlainText()


def test_switching_models_or_going_cloud_stops_the_previous_server(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    _choose_mode(gui, "Local AI")
    gui.on_connect()
    first = _SERVERS[-1]
    gui.on_connect()                                           # a second Connect replaces the child
    assert first.stopped and len(_SERVERS) == 2
    _choose_mode(gui, "Cloud AI")
    gui.language.key.setText("k")
    gui.on_connect()
    assert _SERVERS[-1].stopped and gui._servers == {}


def test_empty_models_folder_is_explained(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    for name in ("qwen3.5-8b-q4.gguf", "gemma-4-12b-q4.gguf"):
        (tmp_path / name).unlink()
    _choose_mode(gui, "Local AI")
    assert gui.language.local_model.items() == [] and not gui.language.local_model.isEnabled()
    gui.on_connect()
    assert "Put a model file" in gui.output.toPlainText()


def test_choosing_a_folder_rescans(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    other = tmp_path / "other"
    other.mkdir()
    (other / "phi.gguf").write_bytes(b"")
    _choose_mode(gui, "Local AI")
    QtWidgets.QFileDialog.chosen = str(other)
    gui.on_choose_folder()
    QtWidgets.QFileDialog.chosen = ""
    assert gui._models_folder == str(other)
    assert gui.language.local_model.items() == ["phi.gguf"]


# --- the collapsible footer ---

def test_setup_starts_collapsed_with_an_inviting_summary():
    gui = _gui()
    assert not gui.setup_group.isVisible()
    assert gui.setup_toggle.text() == "Set up AI assistant"
    assert gui.setup_toggle.arrowType() == QtCore.Qt.RightArrow


def test_toggle_expands_and_collapses():
    gui = _gui()
    gui.setup_toggle.setChecked(True)
    assert gui.setup_group.isVisible() and gui.setup_toggle.arrowType() == QtCore.Qt.DownArrow
    gui.setup_toggle.setChecked(False)
    assert not gui.setup_group.isVisible()


def test_a_problem_opens_the_footer(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gui = _gui()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.input.setText("hello")
    gui.on_submit()                                            # nothing configured, no key
    assert gui.setup_group.isVisible()
    assert "Enter an API key" in gui.output.toPlainText()


def test_ready_folds_the_footer_and_keeps_the_label(monkeypatch):
    gui = _gui()
    gui._worker = type("_Worker", (), {"configure": lambda self, endpoint, vision=None, profile=None: None})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.setup_toggle.setChecked(True)
    gui.language.key.setText("g-key")
    gui.on_connect()
    assert not gui.setup_group.isVisible()
    assert gui.setup_toggle.text() == "Set up AI assistant"
    assert gui.connect_button.text() == "Connected"


def test_local_status_moves_from_starting_to_ready(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    _choose_mode(gui, "Local AI")
    gui.on_connect()
    assert gui.connect_button.text() == "Starting…"
    scheduled.pop()(); scheduled.pop()()
    assert not gui.setup_group.isVisible()
    assert gui.connect_button.text() == "Connected"
    assert gui.setup_toggle.text() == "Set up AI assistant"


def test_frames_from_look_are_shown_in_the_turn(monkeypatch):
    gui = _gui()
    gui._active = {"tools": [("look", "{}")], "reply": None, "error": None}
    gui._on_frame("QUJD")
    assert '<img src="data:image/png;base64,QUJD"' in gui.output.toPlainText()
    gui._on_done()
    assert '<img src="data:image/png;base64,QUJD"' in gui.output.toPlainText()   # kept in the finished block


# --- the Run / Cancel bar ---

def test_confirmation_bar_is_hidden_until_asked_and_answers_the_gate():
    gui = _gui()
    answers = []
    gui._worker = type("_W", (), {"gate": type("_G", (), {"answer": lambda self, ok: answers.append(ok)})()})()
    assert not gui.confirm_run.isVisible()
    gui._on_confirm("run_acquisition_list", "{}")
    assert gui.confirm_run.isVisible() and "run_acquisition_list" in gui.confirm_label.text()
    gui._answer_confirmation(True)
    assert answers == [True] and not gui.confirm_run.isVisible()
    assert "[confirmed run_acquisition_list]" in gui.output.toPlainText()
    gui._on_confirm("unload_sample", "{}")
    gui._answer_confirmation(False)
    assert answers == [True, False]
    assert "[cancelled unload_sample]" in gui.output.toPlainText()


def test_new_conversation_clears_the_transcript_and_the_worker_between_turns():
    gui = _gui()
    resets = []
    gui._worker = type("_W", (), {"reset": lambda self: resets.append(True)})()
    gui._blocks.append(gui._user_block("old question"))
    gui._render()
    assert "old question" in gui.output.toPlainText()
    gui.on_new_conversation()
    assert resets == [True] and gui._blocks == [] and "old question" not in gui.output.toPlainText()
    gui._set_running(True)
    gui.on_new_conversation()                                       # ignored while a turn runs
    assert resets == [True] and not gui.new_button.isEnabled()


def test_options_row_sets_the_worker_at_once():
    gui = _gui()
    gui._worker = type("_W", (), {"max_history_turns": 20, "look_image_size": 1024})()
    gui._apply_options()                                            # what _ensure_worker does on start
    assert gui._worker.max_history_turns == 20 and gui._worker.look_image_size == 1024
    gui.history_turns.setValue(5)
    gui.frame_size.setValue(512)
    assert gui._worker.max_history_turns == 5 and gui._worker.look_image_size == 512


def test_vision_box_defers_to_the_language_model_by_default(monkeypatch):
    gui = _gui()
    configured = []
    gui._worker = type("_W", (), {"configure": lambda self, endpoint, vision=None, profile=None: configured.append(vision)})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    assert gui.vision.mode.currentText() == "Same as language model" and gui.vision.same
    assert not gui.vision.provider.isVisible() and not gui.vision.local_model.isVisible()
    gui.language.key.setText("k")
    gui.on_connect()
    assert configured == [None]


def test_cloud_vision_model_reaches_the_worker_able_to_see(monkeypatch):
    gui = _gui()
    configured = []
    gui._worker = type("_W", (), {"configure": lambda self, endpoint, vision=None, profile=None: configured.append((endpoint, vision))})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    _choose_provider(gui.language, "Anthropic")
    gui.language.key.setText("sk")
    _choose_mode(gui, "Cloud AI", gui.vision)
    _choose_provider(gui.vision, "OpenAI-style")               # a vLLM with eyes: the preset alone says no
    gui.vision.base_url.setText("http://eyes:8000/v1")
    gui.on_connect()
    (endpoint, vision), = configured
    assert endpoint.provider == "Anthropic"
    assert (vision.kind, vision.base_url, vision.vision) == ("openai-compatible", "http://eyes:8000/v1", True)
    assert "vision:" in gui.connect_button.toolTip()


def test_vision_model_without_a_key_falls_back_with_a_note(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gui = _gui()
    configured = []
    gui._worker = type("_W", (), {"configure": lambda self, endpoint, vision=None, profile=None: configured.append(vision)})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.language.key.setText("k")
    _choose_mode(gui, "Cloud AI", gui.vision)
    _choose_provider(gui.vision, "OpenAI")
    gui.on_connect()
    assert configured == [None]
    assert "OPENAI_API_KEY" in gui.output.toPlainText()


def test_local_vision_model_is_served_with_its_projector(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    (tmp_path / "mmproj-gemma-4-12b-f16.gguf").write_bytes(b"")
    gui.language.key.setText("k")
    _choose_mode(gui, "Local AI", gui.vision)
    assert gui.vision.local_model.items() == ["gemma-4-12b-q4.gguf", "qwen3.5-8b-q4.gguf"]  # not the projector
    gui.vision.local_model.setCurrentText("gemma-4-12b-q4.gguf")
    gui.on_connect()
    (server,) = _SERVERS
    assert server.projector == str(tmp_path / "mmproj-gemma-4-12b-f16.gguf")
    assert gui.connect_button.text() == "Starting…"
    scheduled.pop()(); scheduled.pop()()
    vision = gui._endpoints["vision"]
    assert (vision.provider, vision.model, vision.base_url, vision.vision) == ("Local", "gemma-4-12b-q4", server.base_url, True)
    assert gui._worker.endpoint.provider == "Gemini"           # the language model stayed cloud
    assert gui.connect_button.text() == "Connected"


def test_local_language_model_sees_when_its_projector_is_beside_it(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    (tmp_path / "mmproj-qwen3.5-8b-f16.gguf").write_bytes(b"")
    _choose_mode(gui, "Local AI")
    gui.language.local_model.setCurrentText("qwen3.5-8b-q4.gguf")
    gui.on_connect()                                           # vision stays "Same as language model"
    (server,) = _SERVERS
    assert server.projector == str(tmp_path / "mmproj-qwen3.5-8b-f16.gguf")
    scheduled.pop()(); scheduled.pop()()
    assert gui._worker.endpoint.vision is True and "vision" not in gui._endpoints


def test_the_same_file_in_both_boxes_is_served_once(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    (tmp_path / "mmproj-gemma-4-12b-f16.gguf").write_bytes(b"")
    _choose_mode(gui, "Local AI")
    gui.language.local_model.setCurrentText("gemma-4-12b-q4.gguf")
    _choose_mode(gui, "Local AI", gui.vision)
    gui.vision.local_model.setCurrentText("gemma-4-12b-q4.gguf")
    gui.on_connect()
    (server,) = _SERVERS                                       # one child for both roles
    assert gui._servers["language"] is gui._servers["vision"] is server
    scheduled.pop()(); scheduled.pop()()
    assert gui._endpoints["language"].base_url == gui._endpoints["vision"].base_url == server.base_url
    assert gui.connect_button.text() == "Connected"


def test_a_second_connect_while_loading_leaves_one_live_poll(tmp_path, monkeypatch):
    gui, scheduled = _local_gui(tmp_path, monkeypatch)
    _choose_mode(gui, "Local AI")
    gui.on_connect()
    stale = scheduled.pop()
    gui.on_connect()                                           # replaces the child before it answered
    assert _SERVERS[0].stopped and len(scheduled) == 1
    stale()                                                    # the old chain finds its servers gone
    assert len(scheduled) == 1 and gui._endpoint is None
    scheduled.pop()(); scheduled.pop()()
    assert gui.connect_button.text() == "Connected" and scheduled == []


def test_local_vision_model_without_a_projector_is_refused(tmp_path, monkeypatch):
    gui, _ = _local_gui(tmp_path, monkeypatch)
    gui.language.key.setText("k")
    _choose_mode(gui, "Local AI", gui.vision)
    gui.on_connect()
    assert _SERVERS == [] and gui.connect_button.text() == "Connect"
    assert "projector file" in gui.output.toPlainText()


def test_stop_microscope_now_goes_the_main_windows_way_and_cancels_the_assistant():
    gui = _gui()
    window = gui.main_window
    halted = _collect(window.sig_stop_movement)
    assert gui.stop_button.isEnabled()
    gui.on_stop_microscope()                                        # before any assistant: still stops
    assert window.stops == 1 and len(halted) == 1
    cancelled = []
    gui._worker = type("_W", (), {"interrupt": lambda self: cancelled.append(True)})()
    gui._set_running(True)
    assert gui.stop_button.isEnabled()
    gui.on_stop_microscope()
    assert window.stops == 2 and len(halted) == 2 and cancelled == [True]
    assert "[stop microscope now]" in gui.output.toPlainText()


def test_cancel_request_is_always_clickable_and_idle_between_turns():
    gui = _gui()
    assert gui.interrupt.isEnabled()
    gui.on_interrupt()                                              # idle: nothing happens
    assert "[cancelled]" not in gui.output.toPlainText()
    interrupted = []
    gui._worker = type("_W", (), {"interrupt": lambda self: interrupted.append(True)})()
    gui._set_running(True)
    assert gui.interrupt.isEnabled()
    gui.on_interrupt()
    assert interrupted == [True] and "[cancelled]" in gui.output.toPlainText()


def test_tools_choice_defaults_to_regular_reaches_the_worker_and_follows_the_config(monkeypatch):
    gui = _gui()
    assert gui.tools_profile.currentText() == "Regular"
    configured, switched = [], []
    gui._worker = type("_W", (), {"configure": lambda self, endpoint, vision=None, profile=None: configured.append(profile),
                                  "set_profile": lambda self, profile: switched.append(profile)})()
    monkeypatch.setattr(gui, "_ensure_worker", lambda: True)
    gui.language.key.setText("k")
    gui.on_connect()
    assert configured == ["Regular"]
    gui.tools_profile.setCurrentText("Full")
    gui.tools_profile.currentTextChanged.emit("Full")
    assert switched == ["Full"]
    core = _FakeCore(acceptor=object())
    core.cfg = types.SimpleNamespace(ai_assistant_tools="Full")
    assert AiAssistentGUI(_FakeParent(core)).tools_profile.currentText() == "Full"
