"""pytest bootstrap: install the AstrBot logger stub before test modules load."""

import sys
from pathlib import Path

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from _astrbot_runtime_stub import install  # noqa: E402

install()
