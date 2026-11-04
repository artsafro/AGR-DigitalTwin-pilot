"""new-case: AGR Tools 0.6.0 native UI checks in an interactive, EMPTY 3ds Max session (#808).

Started by run_agr_tools_ui_native.ps-free driver: `3dsmax.exe -silent -U PythonHost <this file>` with
AGR_UI_OUT=<new dir>. The AGR-Tools.bundle must already be installed (driver does it). All scene
data is synthetic (1000 generated boxes). Log lines: PASS/FAIL/INFO/SKIP/ERROR. Ends with quitMax.
"""
import json
import os
import time
import traceback
from pathlib import Path

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_UI_OUT'])
LOG = OUT / 'native_log.txt'
MENU_ID = '0b5898ec-a68d-43ff-a95f-b60edcdd8b43'
results = []


def log(status, key, detail=''):
    line = '{} {} {}'.format(status, key, detail).rstrip()
    results.append(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print('AGR_UI', line)


def step(key, fn):
    try:
        fn()
    except Exception as exc:  # the check did not reach its assertion
        log('ERROR', key, '{}: {}'.format(type(exc).__name__, exc).replace('\n', ' ')[:400])
        with open(OUT / 'tracebacks.txt', 'a', encoding='utf-8') as f:
            f.write(key + '\n' + traceback.format_exc() + '\n')


def check(key, ok, detail=''):
    log('PASS' if ok else 'FAIL', key, detail)


try:
    from PySide6 import QtCore, QtWidgets  # noqa: E402
except ImportError:  # Max 2024
    from PySide2 import QtCore, QtWidgets  # noqa: E402
import qtmax  # noqa: E402

app = QtWidgets.QApplication.instance()
main = qtmax.GetQMaxMainWindow()
state = {}


def pump(seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.02)


def find_panel():
    for w in main.findChildren(QtWidgets.QDockWidget):
        if w.objectName() == 'AgrToolsPanel':
            return w
    return None


def s_env():
    log('INFO', 'max', str(list(rt.maxVersion())))
    import sys
    binding = QtCore.__name__.split('.')[0]
    log('INFO', 'python', sys.version.split()[0] + ' ' + binding + ' ' + __import__(binding).__version__)
    check('empty_scene', not rt.maxFileName and len(rt.objects) == 0, 'objects={}'.format(len(rt.objects)))
    if rt.maxFileName or len(rt.objects):
        raise SystemExit('scene not empty')
    check('bundle_loaded', bool(rt.execute('AGRToolsRegistered == true')),
          str(rt.execute('AGRToolsRoot as string')))
    state['theme0'] = str(rt.colorMan.getColorTheme())


def s_globals():
    documented = {'agrtoolsroot', 'agrtoolsregistered', 'agrtoolsdialog', 'agrtoolsregistermenus'}
    names = [str(n) for n in rt.globalVars.gather()]
    ours = sorted({n.lower() for n in names if n.lower().startswith('agrtools')})
    check('globals_only_documented', set(ours) <= documented, 'AGRTools* globals: {}'.format(ours))
    other = sorted({n.lower() for n in names if 'agr' in n.lower()} - set(ours))
    log('INFO', 'other_agr_named_globals_not_ours', str(other))
    before = len(rt.globalVars.gather())
    rt.fileIn(str(rt.AGRToolsRoot) + 'startup.ms')
    after = len(rt.globalVars.gather())
    check('globals_reload_zero_new', after == before, 'before={} after={}'.format(before, after))


def s_menu():
    if rt.maxVersion()[0] < 27000:
        log('SKIP', 'menu', 'Max < 2025 has no CuiMenuManager; macros/toolbar only (menu.ms is a no-op)')
        return
    mgr = rt.maxOps.GetICuiMenuMgr()
    menu = mgr.GetMenuById(MENU_ID)
    check('menu_present_after_start', menu is not None and menu != rt.undefined)
    cur = str(mgr.GetCurrentConfiguration())
    default = str(mgr.GetDefaultConfiguration())
    log('INFO', 'menu_config', 'current={} default={}'.format(cur, default))
    ok = mgr.LoadConfiguration(default)
    menu2 = mgr.GetMenuById(MENU_ID)
    check('menu_survives_preset_change', bool(ok) and menu2 is not None and menu2 != rt.undefined,
          'LoadConfiguration(default)={}'.format(ok))
    mgr.LoadConfiguration(cur)
    menu3 = mgr.GetMenuById(MENU_ID)
    check('menu_present_after_restore', menu3 is not None and menu3 != rt.undefined)
    bar = main.menuBar()
    titles = [a.text().replace('&', '') for a in bar.actions()]
    check('menu_in_main_bar', 'AGR Tools' in titles, str(titles))


def s_icons():
    theme = str(rt.colorMan.getColorTheme())
    log('INFO', 'color_theme', theme + ' icon folder ' + str(rt.colorMan.getIconFolder()))
    for name in ('tools', 'xview', 'ucx_apply', 'geojson'):
        icon = qtmax.LoadMaxMultiResIcon('AgrIcons/agr_' + name)
        sizes = [s.width() for s in icon.availableSizes()]
        check('icon_resolves_{}_{}'.format(theme, name), not icon.isNull() and bool(sizes), 'sizes={}'.format(sizes))
    path = rt.execute('(local p = ""; colorMan.resolveIconFolder "AgrIcons/agr_xview_24.png" &p; p)')
    log('INFO', 'icon_resolved_path', str(path))


def s_panel_open():
    rt.macros.run('AGR Tools', 'AGRToolsOpen')
    pump(1.5)
    p = find_panel()
    state['panel'] = p
    check('panel_opened_by_macro', p is not None)
    check('panel_parent_is_max_main', p.parent() is main and isinstance(main, QtWidgets.QMainWindow))
    check('panel_docked', not p.isFloating() and main.dockWidgetArea(p) != QtCore.Qt.NoDockWidgetArea,
          'area={}'.format(main.dockWidgetArea(p)))
    check('accelerators_disabled', bool(p.accelerators_disabled))
    check('all_17_actions', len(p.buttons) == 17)
    be = p.backend
    srcs = {k: v for k, v in be.icon_source.items()}
    check('panel_icons_from_max_loader', all(v == 'max' for v in srcs.values()), str(srcs))


def s_dock_memory():
    p = state['panel']
    expect = os.environ.get('AGR_UI_EXPECT_AREA')
    if expect:  # written by the previous Max session (driver seeds nothing; phase 1 saved it)
        check('dock_position_from_previous_session', int(main.dockWidgetArea(p)) == int(expect),
              'area={} expected={}'.format(main.dockWidgetArea(p), expect))
    main.removeDockWidget(p)
    main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, p)
    p.show()
    pump(0.5)
    p.close()  # WA_DeleteOnClose: saves state, deletes the widget
    app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    pump(1.0)
    saved = str(rt.getINISetting(rt.getMAXIniFile(), 'AGRTools', 'dock'))
    log('INFO', 'dock_ini_after_close', saved)
    check('closed_panel_deleted', find_panel() is None)
    rt.macros.run('AGR Tools', 'AGRToolsOpen')
    pump(1.0)
    panels = [w for w in main.findChildren(QtWidgets.QDockWidget) if w.objectName() == 'AgrToolsPanel']
    p2 = panels[0] if panels else None
    state['panel'] = p2
    check('single_panel_after_reopen', len(panels) == 1, 'count={}'.format(len(panels)))
    check('dock_position_restored', p2 is not None and main.dockWidgetArea(p2) == QtCore.Qt.LeftDockWidgetArea,
          'area={}'.format(main.dockWidgetArea(p2) if p2 else None))
    keep = os.environ.get('AGR_UI_LEAVE_AREA')
    if keep:  # leave the panel where the next session must find it
        main.removeDockWidget(p2)
        main.addDockWidget(QtCore.Qt.DockWidgetArea(int(keep)), p2)
        p2.show()
        pump(0.5)
        p2.save_state()


def s_shot(name):
    def run():
        pump(1.0)
        main.grab().save(str(OUT / ('max_' + name + '.png')))
        state['panel'].grab().save(str(OUT / ('panel_' + name + '.png')))
        log('INFO', 'screenshot', name)
    return run


def s_boxes():
    rt.disableSceneRedraw()
    try:
        for i in range(1000):
            b = rt.Box(length=1, width=1, height=1, pos=rt.Point3((i % 40) * 2, (i // 40) * 2, 0))
            b.name = 'SM_Synthetic_{:04d}_Main'.format(i)
    finally:
        rt.enableSceneRedraw()
    rt.select(rt.objects)
    check('boxes_1000', len(rt.objects) == 1000)


def _timed_run(key, cancel_after=None):
    p = state['panel']
    ticks = []
    timer = QtCore.QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start()
    disabled = []
    probe = QtCore.QTimer()
    probe.setInterval(200)
    probe.timeout.connect(lambda: disabled.append(not p.buttons['matid'].isEnabled()))
    probe.start()
    if cancel_after:
        QtCore.QTimer.singleShot(int(cancel_after * 1000), p.cancel_btn.click)
    t0 = time.perf_counter()
    report = p.run('xview')
    dt = time.perf_counter() - t0
    timer.stop()
    probe.stop()
    gaps = [b - a for a, b in zip(ticks, ticks[1:])] or [dt]
    return p, report, dt, max(gaps), len(ticks), disabled


def s_progress():
    p, report, dt, gap, n, disabled = _timed_run('full')
    objs = len((report or {}).get('objects') or [])
    check('progress_1000_complete', objs == 1000 and p.bar.value() == 100,
          'objects={} seconds={:.1f} status={}'.format(objs, dt, (report or {}).get('status')))
    check('ui_responsive_during_run', gap < 0.5 and n > 5, 'max_gap_s={:.3f} ticks={}'.format(gap, n))
    check('buttons_disabled_while_running', bool(disabled) and all(disabled), 'samples={}'.format(len(disabled)))
    check('buttons_enabled_after', all(b.isEnabled() for b in p.buttons.values()) and not p.cancel_btn.isEnabled())
    state['full_seconds'] = dt


def s_cancel():
    rt.select(rt.objects)
    p, report, dt, gap, n, _ = _timed_run('cancel', cancel_after=min(3.0, state.get('full_seconds', 10) / 3))
    objs = len((report or {}).get('objects') or [])
    check('cancel_stops_early', 'Отменено' in p.summary.text() and objs < 1000,
          'objects={} seconds={:.1f} summary={}'.format(objs, dt, p.summary.text()))
    check('ui_responsive_during_cancel_run', gap < 0.5, 'max_gap_s={:.3f}'.format(gap))


def s_row_click():
    p = state['panel']
    p.run('xview') if p.report is None else None
    if not p.row_data:
        log('SKIP', 'row_click', 'no rows')
        return
    p._row_clicked(0, 0)
    sel = [str(o.name) for o in rt.selection]
    check('row_click_selects_object', sel == [p.row_data[0].name], str(sel[:3]))


def finish():
    p = state.get('panel')
    if p is not None:
        p.save_state()
        main.removeDockWidget(p)
        p.setParent(None)
        p.deleteLater()
        pump(0.5)
    summary = {'pass': sum(r.startswith('PASS') for r in results), 'fail': sum(r.startswith('FAIL') for r in results),
               'error': sum(r.startswith('ERROR') for r in results)}
    log('INFO', 'summary', json.dumps(summary))
    log('INFO', 'AGR_UI_DONE')
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.quitMax(rt.name('noPrompt'))


STEPS = [('env', lambda: s_env()), ('globals', lambda: s_globals()), ('menu', lambda: s_menu()),
         ('icons', lambda: s_icons()), ('panel_open', lambda: s_panel_open()),
         ('dock_memory', lambda: s_dock_memory()), ('boxes', lambda: s_boxes()),
         ('progress', lambda: s_progress()), ('row_click', lambda: s_row_click()),
         ('shot', lambda: s_shot(str(rt.colorMan.getColorTheme()))()), ('cancel', lambda: s_cancel())]


def selected_steps(spec):
    """AGR_UI_STEPS: unset -> every step; '' or 'none' -> no step (quit baseline, #868); else a comma list."""
    if spec is None:
        return [k for k, _ in STEPS]
    names = [n.strip() for n in spec.split(',') if n.strip() and n.strip() != 'none']
    unknown = sorted(set(names) - {k for k, _ in STEPS})
    if unknown:
        raise SystemExit('unknown AGR_UI_STEPS: ' + ', '.join(unknown))
    return names


def main_run():
    try:
        chosen = selected_steps(os.environ.get('AGR_UI_STEPS'))
    except SystemExit as exc:  # still quit Max, the driver must not wait for its timeout
        log('ERROR', 'steps', str(exc))
        chosen = []
    log('INFO', 'steps', ','.join(chosen) or 'none')
    for key, fn in STEPS:
        if key in chosen:
            step(key, fn)
    finish()


QtCore.QTimer.singleShot(8000, main_run)
log('INFO', 'scheduled')
