"""Environment for a child 3ds Max / 3dsmaxbatch / dcc_batch process (#1024 1.0.1).

A parent (pytest, a driver script) may carry Qt variables for its own PySide6 use, e.g.
QT_QPA_PLATFORM=offscreen. Max brings its own Qt: inheriting them gives
"3dsmax: no Qt platform plugin could be initialized". Standard library only.
"""
from __future__ import annotations

import os

MAX_UNSAFE_ENV = ("QT_QPA_PLATFORM", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_API")


def max_child_env(base=None):
    """Copy the environment without parent Qt or virtualenv activation.

    Max's Python startup honors VIRTUAL_ENV and prepends its site-packages.
    A uv/pytest venv can therefore inject incompatible PySide6/Shiboken into
    Max 2026's Python 3.11 even when all QT_* settings were removed (#1089).
    Keep PATH and unrelated settings unchanged; never alter the user install.
    """
    unsafe = {key.casefold() for key in (*MAX_UNSAFE_ENV, "VIRTUAL_ENV")}
    return {key: value for key, value in (os.environ if base is None else base).items()
            if key.casefold() not in unsafe}
