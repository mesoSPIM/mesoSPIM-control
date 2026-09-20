"""Serve a local model file for the AI Assistant, without an external runtime.

A ``.gguf`` file chosen in the tab is served by llama.cpp's OpenAI-compatible server (the
``llama_cpp.server`` module of the ``llama-cpp-python`` package) as a child process bound to
loopback. The assistant then talks to it through the same OpenAI-compatible endpoint it uses for
any other server, so nothing in the agent depends on the runtime. The child lives while that
endpoint is in use: connecting again or closing mesoSPIM stops it.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import atexit
import http.client
import os
import socket
import subprocess
import sys
import tempfile

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
    return sorted(
        name for name in os.listdir(folder)
        if name.lower().endswith(config.MODEL_SUFFIXES) and "mmproj" not in name.lower()  # a projector, not a model
    )


def projector_for(folder, model_name):
    """The projector file (``mmproj``) that lets a local model see: one in the folder whose name
    carries the model's family, the first two dash-separated parts of the file name ("gemma-4",
    "qwen3.5-8b"). Of several, the longest shared start with the model's name wins. None when none
    matches: a projector of another family makes the server fail or see nonsense."""
    if not os.path.isdir(folder):
        return None
    stem = model_name.lower().rsplit(".", 1)[0]
    family = "-".join(stem.split("-")[:2])
    candidates = [name for name in os.listdir(folder)
                  if name.lower().endswith(config.MODEL_SUFFIXES) and "mmproj" in name.lower()
                  and family in name.lower()]
    if not candidates:
        return None
    best = max(candidates, key=lambda name: len(os.path.commonprefix([stem, name.lower().replace("mmproj-", "")])))
    return os.path.join(folder, best)


def server_command(model_path, port, projector=None, context_tokens=None):
    """The child process serving ``model_path`` on ``port``, with its projector file when it is
    to see images and the context window it is to keep. Raises with the install hint when the
    runtime is missing, so the tab can say what to do instead of failing later."""
    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        raise RuntimeError("llama-cpp-python is not installed: pip install llama-cpp-python")
    argv = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", model_path,
        "--model_alias", model_name(model_path),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--n_gpu_layers", "-1",  # offload everything the GPU can take; CPU-only builds ignore it
        "--n_ctx", str(int(context_tokens or config.LOCAL_CONTEXT_TOKENS)),
    ]
    if projector:
        argv += ["--clip_model_path", projector]
    return argv


def model_name(model_path):
    return os.path.splitext(os.path.basename(model_path))[0]


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class LocalModelServer:
    """One server child for one model file. ``start()`` returns at once; poll ``ready()`` until the
    model has loaded (a large file takes tens of seconds), then use ``base_url`` and ``model``."""

    def __init__(self, model_path, command=server_command, projector=None, context_tokens=None):
        self.model_path = model_path
        self.projector = projector
        self.context_tokens = context_tokens
        self.model = model_name(model_path)
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}/v1"
        self.log_path = None
        self._command = command
        self._process = None

    def start(self):
        argv = self._command(self.model_path, self.port, self.projector, self.context_tokens)  # raises before anything is spawned
        handle, self.log_path = tempfile.mkstemp(prefix="mesospim-model-server-", suffix=".log")
        with os.fdopen(handle, "wb") as log:  # the child inherits the descriptor; ours can close
            try:
                self._process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)
            except OSError:
                os.unlink(self.log_path)
                raise
        atexit.register(self.stop)            # no orphaned child if mesoSPIM ends without shutdown()

    def ready(self):
        """True once the server answers. Raises when the child has already exited."""
        if self._process is None:
            return False
        if self._process.poll() is not None:
            raise RuntimeError(
                f"the model server exited with code {self._process.returncode}; see {self.log_path}"
            )
        # A direct connection: urllib would send a loopback probe through an HTTP proxy from the
        # environment. Short, since the poll runs on the GUI thread.
        probe = http.client.HTTPConnection("127.0.0.1", self.port, timeout=0.2)
        try:
            probe.request("GET", "/v1/models")
            response = probe.getresponse()
            response.read()
            return 200 <= response.status < 300         # 503 while loading is not ready
        except (OSError, http.client.HTTPException):  # not listening yet, or half-way up
            return False
        finally:
            probe.close()

    def stop(self):
        """Stop a running child and drop its log; a child that died on its own keeps the log,
        since the failure message names it."""
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if self.log_path and os.path.exists(self.log_path):
            os.unlink(self.log_path)
