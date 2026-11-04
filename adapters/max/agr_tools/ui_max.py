"""new-case: 3ds Max backend of the AGR Tools 0.6.0 panel (#808): pymxs + runtime.py actions.

The panel never calls pymxs itself; everything scene-related is here. Native progress uses
progressStart / progressUpdate / getProgressCancel / progressEnd next to the panel bar.
"""
import json
import traceback

from pymxs import runtime as rt

import agr_tools_ui_model as model
from agr_tools_ui_qt import QtGui, QtWidgets, max_icon, max_main_window

INI_SECTION = 'AGRTools'
INI_KEY = 'dock'


class MaxBackend:
    def __init__(self, agr, icon_root):
        self.agr = agr            # namespace over runtime.py globals
        self.icon_root = icon_root  # <root>/icons/{Dark,Light}/AgrIcons for MZP installs
        self.icon_source = {}

    # ---- icons --------------------------------------------------------------------------
    def icon(self, name):
        ref = model.ICON_PREFIX + name
        icon = max_icon(ref)
        if icon is not None and not icon.isNull() and icon.availableSizes():
            self.icon_source[name] = 'max'
            return icon
        app = QtWidgets.QApplication.instance()
        window = app.palette().color(QtGui.QPalette.Window) if app else None
        theme = model.theme_name((window.red(), window.green(), window.blue())) if window else 'Dark'
        icon = QtGui.QIcon()
        for size in (24, 30, 36, 48):
            path = '{}/{}/AgrIcons/agr_{}_{}.png'.format(self.icon_root, theme, name, size)
            if rt.doesFileExist(path):
                icon.addFile(path)
        self.icon_source[name] = 'file' if not icon.isNull() else 'missing'
        return icon

    # ---- scene --------------------------------------------------------------------------
    def targets(self, scope_all):
        return self.agr._targets(list(rt.geometry) if scope_all else None)

    def run_chunk(self, tool, chunk):
        fn = {'xview': self.agr.xview, 'matid': self.agr.matid}[tool]
        return fn(chunk)

    def run_tool(self, tool, scope_all):
        if scope_all:
            rt.select(rt.geometry)
        return self.agr.ui(tool)

    def _node(self, handle):
        """Report handles are anim handles (getHandleByAnim), not node handles."""
        if handle is None:
            return None
        n = rt.getAnimByHandle(int(handle))
        return n if n is not None and rt.isValidNode(n) else None

    def select_failed(self, report):
        nodes = [self._node(o.get('handle')) for o in report.get('objects') or [] if o.get('findings')]
        rt.select([n for n in nodes if n is not None])

    def select_row(self, row):
        n = self._node(row.handle)
        if n is None:
            rt.clearSelection()
            return False
        rt.select(n)
        return True

    # ---- progress -----------------------------------------------------------------------
    def progress_start(self, label):
        rt.progressStart('AGR Tools: ' + label)

    def progress_update(self, pct):
        return bool(rt.progressUpdate(pct))

    def progress_cancelled(self):
        return bool(rt.getProgressCancel())

    def progress_end(self):
        rt.progressEnd()

    # ---- log / files --------------------------------------------------------------------
    def log(self, report):
        print(json.dumps(report, ensure_ascii=True, allow_nan=False))

    def log_error(self, tool, exc):
        print('AGR_TOOLS_ERROR tool={} {}'.format(tool, ''.join(traceback.format_exception_only(type(exc), exc)).strip()))

    def save_path(self):
        p = rt.getSaveFileName(caption='AGR Tools report', types='JSON (*.json)|*.json|')
        return None if p is None or p == rt.undefined else str(p)

    def load_settings(self):
        return str(rt.getINISetting(rt.getMAXIniFile(), INI_SECTION, INI_KEY) or '')

    def save_settings(self, text):
        rt.setINISetting(rt.getMAXIniFile(), INI_SECTION, INI_KEY, text)


def create(agr, ui, icon_root):
    backend = MaxBackend(agr, icon_root)
    main = max_main_window()
    panel = ui.AgrPanel(backend, main)
    state = model.parse_dock(backend.load_settings())
    ui.place(panel, main, state)
    panel.show()
    panel.raise_()
    return panel
