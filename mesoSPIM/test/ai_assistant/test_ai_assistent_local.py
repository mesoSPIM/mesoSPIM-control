"""Local model serving: the folder scan and the llama.cpp server child, with a stand-in server
process so no model runtime is needed."""
import os
import sys
import time
import types

import pytest

from mesoSPIM.src import mesoSPIM_AiAssistent_Config as config
from mesoSPIM.src.mesoSPIM_AiAssistent_Local import (LocalModelServer, list_models, models_folder, projector_for,
                                                     server_command)


def test_models_folder_prefers_the_microscope_config():
    cfg = types.SimpleNamespace(**{config.MODELS_FOLDER_CONFIG_KEY: "/data/models"})
    assert models_folder(cfg) == "/data/models"
    assert models_folder(types.SimpleNamespace()).endswith(os.path.join("mesoSPIM", "models"))
    assert models_folder(None).endswith(os.path.join("mesoSPIM", "models"))


def test_list_models_shows_only_model_files_sorted(tmp_path):
    for name in ("b-model.gguf", "A-Model.GGUF", "notes.txt", "weights.bin", "b-model-mmproj-f16.gguf"):
        (tmp_path / name).write_bytes(b"")
    assert list_models(str(tmp_path)) == ["A-Model.GGUF", "b-model.gguf"]   # a projector is not a model
    assert list_models(str(tmp_path / "missing")) == []


def test_server_command_names_the_missing_runtime(monkeypatch):
    monkeypatch.setitem(sys.modules, "llama_cpp", None)          # import fails as if not installed
    with pytest.raises(RuntimeError, match=r'pip install "llama-cpp-python\[server\]"'):
        server_command("/models/x.gguf", 1234)


def test_server_command_serves_the_file_on_loopback(monkeypatch):
    monkeypatch.setitem(sys.modules, "llama_cpp", types.ModuleType("llama_cpp"))
    argv = server_command("/models/qwen-8b.gguf", 4321)
    assert argv[:3] == [sys.executable, "-m", "llama_cpp.server"]
    assert argv[argv.index("--model") + 1] == "/models/qwen-8b.gguf"
    assert argv[argv.index("--model_alias") + 1] == "qwen-8b"
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert argv[argv.index("--port") + 1] == "4321"
    assert "--clip_model_path" not in argv
    with_eyes = server_command("/models/qwen-8b.gguf", 4321, projector="/models/mmproj-qwen-8b.gguf")
    assert with_eyes[with_eyes.index("--clip_model_path") + 1] == "/models/mmproj-qwen-8b.gguf"
    from mesoSPIM.src import mesoSPIM_AiAssistent_Config as config
    assert argv[argv.index("--n_ctx") + 1] == str(config.LOCAL_CONTEXT_TOKENS) == "32768"   # not llama.cpp's 2,048
    narrow = server_command("/models/qwen-8b.gguf", 4321, context_tokens=8192)
    assert narrow[narrow.index("--n_ctx") + 1] == "8192"
    assert argv[argv.index("--n_batch") + 1] == "2048" and argv[argv.index("--flash_attn") + 1] == "true"


def test_projector_for_wants_the_models_family_in_the_name(tmp_path):
    assert projector_for(str(tmp_path / "missing"), "gemma-4-12b-q4.gguf") is None
    assert projector_for(str(tmp_path), "gemma-4-12b-q4.gguf") is None                 # nothing there
    (tmp_path / "mmproj-qwen3.5-8b-f16.gguf").write_bytes(b"")
    assert projector_for(str(tmp_path), "gemma-4-12b-q4.gguf") is None                 # another family, even alone
    (tmp_path / "gemma-4-12b-mmproj-f16.gguf").write_bytes(b"")
    (tmp_path / "mmproj-gemma-4-27b-f16.gguf").write_bytes(b"")
    assert projector_for(str(tmp_path), "gemma-4-12b-q4.gguf") == str(tmp_path / "gemma-4-12b-mmproj-f16.gguf")
    assert projector_for(str(tmp_path), "gemma-4-27b-q8.gguf") == str(tmp_path / "mmproj-gemma-4-27b-f16.gguf")
    assert projector_for(str(tmp_path), "qwen3.5-8b-q4.gguf") == str(tmp_path / "mmproj-qwen3.5-8b-f16.gguf")
    assert projector_for(str(tmp_path), "phi-4-q4.gguf") is None


_FAKE_SERVER = """
import sys, json
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": [{"id": "fake"}]}).encode()
        self.send_response(int(sys.argv[2]) if len(sys.argv) > 2 else 200)
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
"""


def _fake_command(model_path, port, projector=None, context_tokens=None):
    return [sys.executable, "-c", _FAKE_SERVER, str(port)]


def _wait(server, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.ready():
            return True
        time.sleep(0.05)
    return False


def test_server_starts_becomes_ready_and_stops(tmp_path, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")        # a lab proxy must not catch a loopback probe
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    model = tmp_path / "tiny-model.gguf"
    model.write_bytes(b"")
    server = LocalModelServer(str(model), command=_fake_command)
    assert server.model == "tiny-model"
    assert server.base_url == f"http://127.0.0.1:{server.port}/v1"
    assert server.ready() is False                                # not started yet
    server.start()
    try:
        assert _wait(server), "the stand-in server never answered"
        assert os.path.isfile(server.log_path)
    finally:
        server.stop()
    assert server.ready() is False                                # stopped: nothing to talk to
    server.stop()                                                 # idempotent


def test_server_still_loading_is_not_ready(tmp_path):
    """llama.cpp answers 503 while the model loads; that is not ready."""
    server = LocalModelServer(str(tmp_path / "m.gguf"),
                              command=lambda p, port, projector, context_tokens=None: [sys.executable, "-c", _FAKE_SERVER, str(port), "503"])
    server.start()
    try:
        import http.client
        deadline = time.monotonic() + 10
        status = None
        while time.monotonic() < deadline and status != 503:       # wait for the stand-in to answer
            try:
                probe = http.client.HTTPConnection("127.0.0.1", server.port, timeout=0.5)
                probe.request("GET", "/v1/models")
                status = probe.getresponse().status
                probe.close()
            except OSError:
                time.sleep(0.05)
        assert status == 503, "the stand-in never answered"
        assert server.ready() is False                             # answering is not ready
    finally:
        server.stop()


def test_server_that_dies_is_reported_with_its_log(tmp_path):
    server = LocalModelServer(str(tmp_path / "m.gguf"),
                              command=lambda p, port, projector, context_tokens=None: [sys.executable, "-c", "import sys; sys.exit(3)"])
    server.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            server.ready()
        except RuntimeError as error:
            assert "exited with code 3" in str(error) and server.log_path in str(error)
            break
        time.sleep(0.05)
    else:
        pytest.fail("the exit was never reported")
    server.stop()


def test_start_raises_before_spawning_when_the_runtime_is_missing(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    server = LocalModelServer(str(tmp_path / "m.gguf"))
    with pytest.raises(RuntimeError, match="llama-cpp-python"):
        server.start()
    assert server.ready() is False and server.log_path is None
