"""new-case: Qt import shim for AGR Tools (#808). Max 2025/2026 ship PySide6, Max 2024 PySide2.

qtmax helpers are None outside 3ds Max so the panel also runs under pytest-qt.
"""
try:
    from PySide6 import QtCore, QtGui, QtWidgets  # noqa: F401
    BINDING = 'PySide6'
except ImportError:  # Max 2024: PySide2 / Python 3.10
    from PySide2 import QtCore, QtGui, QtWidgets  # noqa: F401
    BINDING = 'PySide2'

try:
    import qtmax as _qtmax
except ImportError:
    _qtmax = None


def max_main_window():
    """QMainWindow of Max (GetQMaxMainWindow); None outside Max."""
    if _qtmax is None:
        return None
    fn = getattr(_qtmax, 'GetQMaxMainWindow', None) or getattr(_qtmax, 'GetQMaxWindow', None)
    return fn() if fn else None


def disable_accelerators(widget):
    """Max shortcuts must not eat keys typed into the panel. Returns True when applied."""
    fn = getattr(_qtmax, 'DisableMaxAcceleratorsOnFocus', None) if _qtmax else None
    if fn is None:
        return False
    fn(widget, True)
    return True


def max_icon(name):
    """QIcon for 'AgrIcons/agr_x' through Max's theme-aware loader; None outside Max."""
    fn = getattr(_qtmax, 'LoadMaxMultiResIcon', None) if _qtmax else None
    return fn(name) if fn else None
