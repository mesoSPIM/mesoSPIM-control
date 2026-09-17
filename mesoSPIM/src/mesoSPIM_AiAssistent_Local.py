"""Serve a local model file for the AI Assistant, without an external runtime.

A ``.gguf`` file chosen in the tab is served by llama.cpp's OpenAI-compatible server (the
``llama_cpp.server`` module of the ``llama-cpp-python`` package) as a child process bound to
loopback. The assistant then talks to it through the same OpenAI-compatible endpoint it uses for
any other server, so nothing in the agent depends on the runtime. The child lives while that
endpoint is in use: switching models or closing the tab stops it.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import os
import socket
import subprocess
import sys
import tempfile
import urllib.request

from . import mesoSPIM_AiAssistent_Config as config


def models_folder(cfg):
    """The operator's models folder: the microscope config's ``ai_assistant_models_folder`` when
    set, else ``~/mesoSPIM/models``."""
    configured = getattr(cfg, config.MODELS_FOLDER_CONFIG_KEY, None)
    return configured or os.path.join(os.path.expanduser("~"), "mesoSPIM", "models")


def list_models(folder):
    """Model files in the folder by name; a missing folder lists nothing."""
    if not os.path.isdir(folder):
        return []
    return sorted(name for name in os.listdir(folder) if name.lower().endswith(config.MODEL_SUFFIXES))


def server_command(model_path, port):
    """The child process serving ``model_path`` on ``port``. Raises with the install hint when the
    runtime is missing, so the tab can say what to do instead of failing later."""
    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        raise RuntimeError("llama-cpp-python is not installed: pip install llama-cpp-python")
    return [
        sys.executable, "-m", "llama_cpp.server",
        "--model", model_path,
        "--model_alias", model_name(model_path),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--n_gpu_layers", "-1",  # offload everything the GPU can take; CPU-only builds ignore it
    ]


def model_name(model_path):
    return os.path.splitext(os.path.basename(model_path))[0]


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class LocalModelServer:
    """One server child for one model file. ``start()`` returns at once; poll ``ready()`` until the
    model has loaded (a large file takes tens of seconds), then use ``base_url`` and ``model``."""

    def __init__(self, model_path, command=server_command):
        self.model_path = model_path
        self.model = model_name(model_path)
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}/v1"
        self.log_path = None
        self._command = command
        self._process = None

    def start(self):
        argv = self._command(self.model_path, self.port)  # raises before anything is spawned
        handle, self.log_path = tempfile.mkstemp(prefix="mesospim-model-server-", suffix=".log")
        with os.fdopen(handle, "wb") as log:  # the child inherits the descriptor; ours can close
            self._process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)

    def ready(self):
        """True once the server answers. Raises when the child has already exited."""
        if self._process is None:
            return False
        if self._process.poll() is not None:
            raise RuntimeError(
                f"the model server exited with code {self._process.returncode}; see {self.log_path}"
            )
        try:
            with urllib.request.urlopen(self.base_url + "/models", timeout=0.5):
                return True
        except OSError:
            return False

    def stop(self):
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
