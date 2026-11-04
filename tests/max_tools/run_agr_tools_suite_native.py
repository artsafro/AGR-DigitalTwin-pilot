"""#860 native smoke (headless 3dsmaxbatch): AGR Tools 0.7.0 checks on a DISPOSABLE synthetic scene.

Loads runtime.py from the extracted MZP (AGR_860_PKG), builds a new scene in memory (never saved), runs the
12 checks and writes one JSON per check + summary.json to AGR_860_OUT. Synthetic data, not a real object.
"""
import importlib.util
import json
import os
import sys
import traceback

from pymxs import runtime as rt

PKG = os.environ['AGR_860_PKG']
OUT = os.environ['AGR_860_OUT']
os.makedirs(OUT, exist_ok=True)
summary = {'max_version': list(rt.maxVersion())[:3], 'pkg': PKG, 'checks': {}, 'errors': {}}


def load_runtime():
    spec = importlib.util.spec_from_file_location('agr_tools_runtime', os.path.join(PKG, 'runtime.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['agr_tools_runtime'] = mod
    spec.loader.exec_module(mod)
    return mod


def box(name, pos, size=(10, 10, 10), fbx=None, zero=0.0, mat=None):
    b = rt.Box(name=name, length=size[0], width=size[1], height=size[2], pos=rt.Point3(*pos))
    props = []
    if fbx:
        props.append('AGR_EXPORT_PATH=' + fbx)
    if zero is not None:
        props.append('AGR_ZERO_M=' + repr(zero))
    rt.setUserPropBuffer(b, '\r\n'.join(props))
    b.material = mat if mat is not None else rt.Standardmaterial(name='M_Addr_001_Main_1')
    return b


try:
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0
    rt.fileInGamma = 1.0
    rt.fileOutGamma = 1.0
    agr = load_runtime()
    summary['runtime_version'] = agr.VERSION
    oks = 'C:/x/ev_860/out/0101_Addr_01.fbx'
    ground = 'C:/x/ev_860/out/0101_Addr_Ground.fbx'
    box('SM_Addr_001_Main', (0, 0, -2), fbx=oks)                                   # clean: drop 2 m
    bad = box('SM_Addr_002_Main', (20, 0, -0.5), fbx=oks, mat=rt.RaytraceMaterial(name='M_raytrace'))
    bad.scale = rt.Point3(2, 2, 2)                                               # drop 0.5 m, scale, class
    glass_mat = rt.Standardmaterial(name='M_Addr_001_MainGlass_1', opacity=50)
    box('SM_Addr_001_MainGlass', (40, 0, -2), size=(5, 5, 5), fbx=oks, mat=glass_mat)  # D2/D3: clean glass
    box('SM_Addr_Ground', (0, 40, -3), size=(30, 30, 2), fbx=ground)
    ucx = box('UCX_SM_Addr_001_Main_001', (0, 0, -2), size=(9, 9, 9), fbx=oks, zero=None)
    ucx.material = None
    cam = rt.FreeCamera(name='Camera_Leftover')
    rt.setUserPropBuffer(cam, 'AGR_EXPORT_PATH=' + oks)
    rt.select(rt.objects)
    for tool in agr.CHECKS_070:
        try:
            rep = agr.checks_070(tool, None, False)
            agr.parse_report(json.dumps(rep, allow_nan=False))
            with open(os.path.join(OUT, tool + '.json'), 'w', encoding='utf-8') as f:
                json.dump(rep, f, ensure_ascii=False, indent=1)
            codes = sorted({fd['code'] for o in rep['objects'] for fd in o['findings']}
                           | {fd['name'] for fd in (rep['plan'].get('findings') or []) if fd['status'] != 'pass'})
            summary['checks'][tool] = {'status': rep['status'], 'objects': len(rep['objects']), 'codes': codes}
        except Exception as exc:  # noqa: BLE001 - recorded, the smoke continues
            summary['errors'][tool] = traceback.format_exc()[-1500:]
    # the panel model in the real Max Python: rail + «Путь» from the shipped JSON
    try:
        agr._load_core('ui_model.py', 'agr_tools_ui_model')
        roadmap = agr._load_core('roadmap.py', 'agr_tools_roadmap')
        suite = roadmap.load_file(agr.suite_path())
        reports = {agr._load_core('ui_model.py', 'agr_tools_ui_model').row_of(t): json.load(
            open(os.path.join(OUT, t + '.json'), encoding='utf-8')) for t in agr.CHECKS_070
            if os.path.isfile(os.path.join(OUT, t + '.json'))}
        status = roadmap.live_status(suite, reports, agr.VERSION)
        summary['path_status'] = status
        summary['next_step'] = roadmap.next_step(suite, status)[0]
        summary['suite_path'] = agr.suite_path()
    except Exception:  # noqa: BLE001
        summary['errors']['roadmap'] = traceback.format_exc()[-1500:]
    summary['scene_saved'] = bool(str(rt.maxFileName))
    # Qt panel inside this Max's own Python/Qt (batch: no main window, the dock floats; grab renders it)
    try:
        import types
        from pathlib import Path
        agr._load_core('ui_qt.py', 'agr_tools_ui_qt')
        ui_panel = agr._load_core('ui_panel.py', 'agr_tools_ui_panel')
        ui_max = agr._load_core('ui_max.py', 'agr_tools_ui_max')
        qt = sys.modules['agr_tools_ui_qt']
        app = qt.QtWidgets.QApplication.instance()
        summary['qt_app'] = app is not None
        os.environ['LOCALAPPDATA'] = os.path.join(OUT, 'localappdata')  # report memory of this smoke only
        for t in agr.CHECKS_070:
            if os.path.isfile(os.path.join(OUT, t + '.json')):
                agr.remember(json.load(open(os.path.join(OUT, t + '.json'), encoding='utf-8')))
        icon_root = str(Path(PKG) / 'icons')
        # the theme is Max's own (MaxStartUI.clrx; the driver switches it), never a palette forced here
        win = app.palette().color(qt.QtGui.QPalette.Window)
        theme = sys.modules['agr_tools_ui_model'].theme_name((win.red(), win.green(), win.blue())).lower()
        summary['theme'] = theme
        shots = []
        for _ in (0,):
            backend = ui_max.MaxBackend(types.SimpleNamespace(**vars(agr)), icon_root)
            panel = ui_panel.AgrPanel(backend, None)
            panel.refresh_path()
            panel.resize(720, 1100)
            for page, name in ((0, 'path'), (8, 'qa')):
                panel.rail.setCurrentRow(page)
                app.processEvents()
                f = os.path.join(OUT, 'max{}_{}_{}.png'.format(summary['max_version'][0] // 1000 + 1998, theme, name))
                panel.grab().save(f)
                shots.append(f)
            summary['next_step_label_' + theme] = panel.next_label.text()
            panel.deleteLater()
        summary['shots'] = shots
    except Exception:  # noqa: BLE001
        summary['errors']['qt_panel'] = traceback.format_exc()[-1500:]
except Exception:  # noqa: BLE001
    summary['errors']['setup'] = traceback.format_exc()[-2000:]
with open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)
print('AGR_860_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
