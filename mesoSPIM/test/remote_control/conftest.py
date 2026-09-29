"""Test bootstrap for the Remote Control live tests: the repository on the path and the markers."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

collect_ignore = ["test_real_pyqt_smoke.py", "test_real_pyqt_transport_smoke.py"]  # scripts for real PyQt; run.py pyqt runs them


def pytest_configure(config):
    """Register the explicit operator-gated live-test markers."""
    config.addinivalue_line("markers", "live_valid: safe live movement and restoration")
    config.addinivalue_line("markers", "live_demo_all: complete DemoStage command sweep")
    config.addinivalue_line("markers", "live_real_all: complete real-hardware command sweep")
