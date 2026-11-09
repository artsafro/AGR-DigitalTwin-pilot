"""Environment for a child 3ds Max / 3dsmaxbatch / dcc_batch process (#1024 1.0.1).

A parent (pytest, a driver script) may carry Qt variables for its own PySide6 use, e.g.
QT_QPA_PLATFORM=offscreen. Max brings its own Qt: inheriting them gives
"3dsmax: no Qt platform plugin could be initialized". Standard library only.
"""
from __future__ import annotations

import os

MAX_UNSAFE_ENV = ("QT_QPA_PLATFORM", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_API")


def max_child_env(base=None):
    """Copy of `base` (default os.environ) without the Qt variables a child Max must not inherit."""
    env = dict(os.environ if base is None else base)
    for key in MAX_UNSAFE_ENV:
        env.pop(key, None)
    return env
