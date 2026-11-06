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

    def run_chunk(self, tool, chunk, on_item=None):
        fn = {'xview': self.agr.xview, 'matid': self.agr.matid}[tool]
        return fn(chunk, on_item=on_item)

    def run_tool(self, tool, scope_all):
        if not scope_all:
            return self._run_tool(tool)
        # runtime.ui reads rt.selection, so "вся сцена" selects the scope for the call and then puts the
        # user's selection back, also on error; nodes deleted by the tool are dropped (#861).
        keep = list(rt.selection)
        # 0.7 checks and 0.9 rows (lights, scatters, maps) see every object, the rest only geometry
        rt.select(rt.objects if tool in self.agr.CHECKS_070 or tool in self.agr.EDITS_090 else rt.geometry)
        report = None
        try:
            report = self._run_tool(tool, select=False)
            return report
        finally:
            alive = [n for n in keep if rt.isValidNode(n)]
            if alive:
                rt.select(alive)
            else:
                rt.clearSelection()
            self._select_offenders(tool, report)  # after the user's selection is back, so Ctrl+Z returns to it

    def _run_tool(self, tool, select=True):
        if tool in getattr(self.agr, 'EDITS_100', ()):
            # 1.0 stage buttons (#1024): runtime.ui has no 1.0 branch, a press goes to edit_ui (preview -> apply,
            # actor panel). The panel never calls this while the button is wip.
            report = self.agr.edit_ui(tool, select=False)
            self.log(report)
            return report
        if tool in self.agr.EDITS_080 or tool in self.agr.EDITS_090:
            # 0.8 (#908) / 0.9 (#979): preview -> apply through runtime.edits_080 / edits_090; a `select` row
            # (SELECT_090) selects its offenders here, never in the core
            report = self.agr.edit_ui(tool, select=False)
            self.log(report)
            if select:
                self._select_offenders(tool, report)
            return report
        return self.agr.ui(tool)

    def _select_offenders(self, tool, report):
        """`select` rows (light.check): offenders become the selection as ONE undo record (Ctrl+Z restores)."""
        if (isinstance(report, dict) and tool in self.agr.SELECT_090
                and report.get('status') not in (None, 'not_implemented')):
            self.agr.select_offenders(report)

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
        # Finding ids index the node's poly copy; they match the node itself only for a plain Editable_Poly
        # (no modifiers). Otherwise, or for an unknown id type, the object stays the selection (#861).
        if rt.classOf(n.baseObject) != rt.Editable_Poly or len(n.modifiers):
            return 'object'
        sel = model.component_selection(row, int(rt.polyop.getNumVerts(n)), int(rt.polyop.getNumFaces(n)))
        if sel is None:
            return 'object'
        kind, ids = sel
        rt.setCommandPanelTaskMode(rt.Name('modify'))
        if kind == 'vertex':
            rt.polyop.setVertSelection(n, ids)
            rt.subObjectLevel = 1
        else:
            rt.polyop.setFaceSelection(n, ids)
            rt.subObjectLevel = 4
        rt.redrawViews()
        return kind

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
        self.agr.remember(report)

    # ---- «Путь» (0.7.0) -----------------------------------------------------------------
    def suite(self):
        import agr_tools_roadmap as roadmap
        return roadmap.load_file(self.agr.suite_path())

    def last_reports(self):
        return self.agr.last_reports()

    def passport(self):
        """Project passport dict (K1) for the stage statuses of the 1.0 stage rail (#1024). The reader is branch F
        (passport_core); until it ships there is no passport and every stage shows «не начат»."""
        return None

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
