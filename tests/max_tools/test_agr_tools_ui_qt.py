"""new-case: AGR Tools 0.6.0/0.7.0 Qt panel under pytest-qt with a fake backend (#808).

Runs outside 3ds Max (PySide6-Essentials + pytest-qt from the uv dev group, #897):
uv run pytest tests/max_tools/test_agr_tools_ui_qt.py
QT_QPA_PLATFORM=offscreen is set by tests/max_tools/conftest.py before any PySide6 import.
A missing Qt package FAILS this module when the rest of the dev group is installed; it is a skip
only without the dev group (tests/max_tools/_qt_guard.py). Exception: with pytest-qt installed and
PySide6 missing, the pytest-qt plugin aborts the whole session at startup (exit 4, "No module named
'PySide6'") before this guard runs; that is loud, not a skip. When the guard says 'ok' the imports
below are direct, so a broken install (for example a DLL error on Windows) fails instead of skipping.
"""
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_gspec = importlib.util.spec_from_file_location('agr_qt_guard_mod', Path(__file__).with_name('_qt_guard.py'))
_guard = importlib.util.module_from_spec(_gspec)
_gspec.loader.exec_module(_guard)
_status, _reason = _guard.qt_status(ROOT / 'pyproject.toml')
if _status == 'fail':
    pytest.fail('Qt panel tests: ' + _reason, pytrace=False)
if _status == 'ok':
    import PySide6  # noqa: F401  # a broken install must fail, not skip
    import pytestqt  # noqa: F401
else:
    pytest.importorskip('PySide6')
    pytest.importorskip('pytestqt')

PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, module):
    spec = importlib.util.spec_from_file_location(module, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


qt = _load('ui_qt.py', 'agr_tools_ui_qt')
model = _load('ui_model.py', 'agr_tools_ui_model')
roadmap = _load('roadmap.py', 'agr_tools_roadmap')
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'
ui = _load('ui_panel.py', 'agr_tools_ui_panel')
_ispec = importlib.util.spec_from_file_location('agr_icons_qt', ROOT / 'tools/max/agr_icons.py')
ICONS = importlib.util.module_from_spec(_ispec)
_ispec.loader.exec_module(ICONS)
QtCore, QtGui, QtWidgets = qt.QtCore, qt.QtGui, qt.QtWidgets


class FakeBackend:
    def __init__(self, n=1000, cancel_at=None):
        self.nodes = list(range(1, n + 1))
        self.cancel_at = cancel_at
        self.panel = None
        self.events = []
        self.selected = None
        self.settings = ''
        self.native_pct = []
        self.enabled_during_run = set()
        self.reports = {}

    def suite(self):
        return roadmap.load_file(SUITE)

    def last_reports(self):
        return dict(self.reports)

    def icon(self, name):
        icon = QtGui.QIcon()
        for s in (24, 30, 36, 48):
            pm = QtGui.QPixmap()
            pm.loadFromData(ICONS.png_bytes(ICONS.svg(name, ICONS.THEMES['Dark']), s), 'PNG')
            icon.addPixmap(pm)
        return icon

    def targets(self, scope_all):
        return list(self.nodes)

    def run_chunk(self, tool, chunk, on_item=None):
        if self.panel is not None:
            self.enabled_during_run |= {k for k, b in self.panel.buttons.items() if b.isEnabled()}
            self.panel.run('matid')  # re-entry through processEvents must be refused
        if on_item is not None:
            for _h in chunk:
                on_item()
        return {'schema': 1, 'tool': tool, 'status': 'pass',
                'objects': [{'handle': h, 'name': 'N%d' % h,
                             'findings': [] if h % 100 else [{'code': 'overlap_faces', 'ids': [1]}]}
                            for h in chunk]}

    def run_tool(self, tool, scope_all):
        self.events.append(('tool', tool, scope_all))
        if tool == 'export':
            raise ValueError('dry-run gate failed')
        rep = {'schema': 1, 'tool': tool, 'status': 'pass', 'objects': [{'handle': 5, 'name': 'A', 'findings': []}]}
        self.reports[tool] = rep
        return rep

    def select_failed(self, report):
        self.selected = [o['handle'] for o in report['objects'] if o['findings']]

    def select_row(self, row):
        self.selected = [row.handle]

    def progress_start(self, label):
        self.events.append(('start', label))

    def progress_update(self, pct):
        self.native_pct.append(pct)
        return not (self.cancel_at is not None and pct >= self.cancel_at)

    def progress_cancelled(self):
        return False

    def progress_end(self):
        self.events.append(('end',))

    def log(self, report):
        self.reports[report['tool']] = report

    def log_error(self, tool, exc):
        self.events.append(('error', tool, str(exc)))

    def save_path(self):
        return None

    def load_settings(self):
        return self.settings

    def save_settings(self, text):
        self.settings = text


@pytest.fixture
def main(qtbot):
    w = QtWidgets.QMainWindow()
    w.setCentralWidget(QtWidgets.QLabel('viewport'))
    w.resize(1400, 900)
    qtbot.addWidget(w)
    return w


def make(main, backend):
    panel = ui.AgrPanel(backend, main)
    backend.panel = panel
    ui.place(panel, main, model.parse_dock(backend.load_settings()))
    main.show()
    return panel


def test_layout_has_all_sections_and_actions(main):
    p = make(main, FakeBackend())
    assert p.objectName() == 'AgrToolsPanel' and isinstance(p, QtWidgets.QDockWidget)
    assert {s.header.text() for s in p.sections} == set(roadmap.STEP_RU)
    suite = roadmap.load_file(SUITE)
    shipped = [a for a in model.ACTIONS
               if roadmap.shipped(roadmap.row(suite, model.row_of(a.id))['version'], model.VERSION)]
    # release 1.0.0 (#1024 R): the 18 released 1.0 stage buttons of old rows are on their block pages too
    shipped_10 = [a for a in model.ACTIONS_100 if not a.wip and a.tool.partition('.')[0] == roadmap.row(
        suite, a.tool)['block']]
    assert len(shipped_10) == 18 and 'udim_udims_to_ids' in {a.id for a in shipped_10}
    shipped += shipped_10
    assert set(p.buttons) == {a.id for a in shipped}  # 0.8 actions stay greyed until VERSION 0.8.0 (#908)
    for a in shipped:
        b = p.buttons[a.id]
        assert b.toolTip().startswith(model.tooltip(a)) and 'Когда:' in b.toolTip()
        assert b.text() == a.label and not b.icon().isNull()
    assert main.dockWidgetArea(p) == QtCore.Qt.RightDockWidgetArea
    colours = {s.color.name() for s in p.sections}
    assert len(colours) == 10  # one accent per block


def test_batched_run_on_1000_objects_progress_and_buttons_disabled(main):
    be = FakeBackend(1000)
    p = make(main, be)
    report = p.run('xview')
    assert len(report['objects']) == 1000 and report['status'] == 'fail'
    assert be.enabled_during_run == set()  # every action button disabled while running
    assert be.native_pct[0] == 0 and be.native_pct[-1] == 100 and len(be.native_pct) == 41
    assert be.selected == list(range(100, 1001, 100))
    assert p.table.rowCount() == 1000 and p.summary.text().startswith('Ошибок 10 · ОК 990')
    assert all(b.isEnabled() for b in p.buttons.values()) and not p.cancel_btn.isEnabled()
    assert ('start', 'xView: перекрытия') in be.events and be.events[-1] == ('end',)


def test_native_cancel_stops_and_reports_partial(main):
    be = FakeBackend(1000, cancel_at=30)
    p = make(main, be)
    p.run('xview')
    assert 'Отменено' in p.summary.text()
    assert 0 < p.table.rowCount() < 1000
    assert all(b.isEnabled() for b in p.buttons.values()) and be.events[-1] == ('end',)


def test_panel_cancel_button(main, qtbot):
    be = FakeBackend(1000)
    p = make(main, be)
    orig = be.run_chunk

    def chunk(tool, c, on_item=None):
        if c[0] == 101:
            qtbot.mouseClick(p.cancel_btn, QtCore.Qt.LeftButton)
        return orig(tool, c, on_item=on_item)
    be.run_chunk = chunk
    p.run('matid')
    assert p.table.rowCount() == 126 and 'Отменено' in p.summary.text()  # 125 objects + the cancelled row
    assert p.row_data[-1].code == 'cancelled' and not p.row_data[-1].ok


def test_geojson_fail_shows_error_rows_and_red_summary(main):
    """#808 review P1: a failed GeoJSON report (objects == [], failures in plan.findings) must not read as success."""
    checks = _load('checks_core.py', 'agr_tools_checks_core_qt')
    be = FakeBackend()
    finding = {'name': 'crs', 'status': 'fail', 'observed': 'x', 'expected': 'y'}
    be.run_tool = lambda tool, scope_all: checks.geojson_report('C:/x/site.geojson', lambda path: [finding])
    p = make(main, be)
    report = p.run('geojson')
    assert report['status'] == 'fail' and report['objects'] == []
    assert p.table.rowCount() == 1
    assert p.table.item(0, 0).text() == 'site.geojson' and p.table.item(0, 2).text().startswith('crs')
    assert p.summary.text().startswith('Ошибок 1 · ОК 0')
    acc = p.accents()
    assert p.summary.palette().color(QtGui.QPalette.WindowText) == acc['error']
    assert p.table.item(0, 2).foreground().color() == acc['error']
    assert p.status.text() != 'Готово'


def test_single_call_tools_errors_and_scope(main):
    be = FakeBackend()
    p = make(main, be)
    p.scope.setCurrentIndex(1)
    p.run('cleanup_apply')
    assert ('tool', 'apply', True) in be.events
    p.run('export')
    assert ('error', 'export', 'dry-run gate failed') in be.events
    assert 'ValueError: dry-run gate failed' in p.summary.text()


def test_row_click_selects_object(main, qtbot):
    be = FakeBackend(50)
    p = make(main, be)
    p.run('xview')
    p._row_clicked(3, 0)
    assert be.selected == [p.row_data[3].handle]


def test_dock_position_is_remembered(main, qtbot):
    be = FakeBackend()
    p = make(main, be)
    main.removeDockWidget(p)
    main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, p)
    p.show()
    p.save_state()
    assert json.loads(be.settings)['area'] == 1
    p.close()
    p2 = make(main, be)
    assert main.dockWidgetArea(p2) == QtCore.Qt.LeftDockWidgetArea
    p2.setFloating(True)
    p2.save_state()
    assert json.loads(be.settings)['floating'] is True and json.loads(be.settings)['geometry']
    p3 = make(main, be)
    assert p3.isFloating()


@pytest.mark.parametrize('theme,window,base,text', [('Dark', '#444444', '#2e2e2e', '#dcdcdc'),
                                                    ('Light', '#d3d3d3', '#f0f0f0', '#202020')])
def test_accents_follow_the_palette(main, theme, window, base, text):
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor(window))
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor(base))
    pal.setColor(QtGui.QPalette.Text, QtGui.QColor(text))
    pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor(text))
    pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(text))
    QtWidgets.QApplication.instance().setPalette(pal)
    try:
        p = make(main, FakeBackend(30))
        p.run('xview')
        acc = p.accents()
        b = QtGui.QColor(base)
        for c in list(acc.values()) + [s.color for s in p.sections]:
            assert model.contrast((c.red(), c.green(), c.blue()), (b.red(), b.green(), b.blue())) >= 3
        out = os.environ.get('AGR_UI_SHOTS')
        if out:
            main.grab().save(str(Path(out) / 'offscreen_{}.png'.format(theme.lower())))
    finally:
        QtWidgets.QApplication.instance().setPalette(QtGui.QPalette())


def test_batched_progress_pumps_by_elapsed_time(main, monkeypatch):
    """Invariant: 25-object chunks must not be the event-loop cadence.

    Each object costs 0.06 s, so a count-based chunk of 25 blocks for 1.5 s.
    Pumps follow the clock and the max gap stays strictly under 0.1 s.
    """
    t = {'n': 0.0}
    marks = []

    def pumped(*_a, **_k):
        marks.append(t['n'])

    monkeypatch.setattr(QtWidgets.QApplication, 'processEvents', pumped)
    be = FakeBackend(50)
    orig = be.run_chunk

    def run_chunk(tool, chunk, on_item=None):
        for _h in chunk:
            t['n'] += 0.06
            if on_item is not None:
                on_item()
        return orig(tool, chunk)

    be.run_chunk = run_chunk
    kwargs = {}
    if 'clock' in inspect.signature(ui.AgrPanel.__init__).parameters:
        kwargs['clock'] = lambda: t['n']
    p = ui.AgrPanel(be, main, **kwargs)
    be.panel = p
    ui.place(p, main, model.parse_dock(be.load_settings()))
    main.show()
    p.run('xview')
    gaps = [b - a for a, b in zip(marks, marks[1:])]
    assert gaps, marks
    assert max(gaps) < 0.1, 'max_gap_s={:.3f} pumps={}'.format(max(gaps), len(marks))


def test_theme_switch_after_creation_recolours_sections(main):
    """Max can switch Dark/Light at runtime (colorMan.setColorTheme): accents must follow."""
    app = QtWidgets.QApplication.instance()
    p = make(main, FakeBackend(5))
    before = [s.color.name() for s in p.sections]
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor('#444444'))
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor('#2e2e2e'))
    pal.setColor(QtGui.QPalette.Text, QtGui.QColor('#dcdcdc'))
    app.setPalette(pal)
    try:
        QtWidgets.QApplication.processEvents()
        after = [s.color.name() for s in p.sections]
        assert after != before
        b = (46, 46, 46)
        for s in p.sections:
            assert model.contrast((s.color.red(), s.color.green(), s.color.blue()), b) >= 3
    finally:
        app.setPalette(QtGui.QPalette())


# ---- 0.7.0: tab rail + «Путь» (#860) -------------------------------------------------------------------
def test_rail_has_path_and_ten_blocks_in_order_with_planned_greyed(main):
    p = make(main, FakeBackend(5))
    suite = roadmap.load_file(SUITE)
    items = [p.rail.item(i).text() for i in range(p.rail.count())]
    assert items == ['Путь'] + ['{} {}'.format(b['number'], b['short_ru']) for b in suite['blocks']]
    assert p.pages.count() == 11 and p.rail.currentRow() == 0
    # block pages 0-9: rows whose id prefix is their block; the 15 new 1.0 rows (#1024) are stage buttons only
    planned = [r for r in suite['rows'] if r['id'].partition('.')[0] == r['block'] and (
        roadmap.vkey(r['version']) > roadmap.vkey(model.VERSION) or r.get('deferred') or r['fate'] == 'step')]
    # release 1.0.0 (#1024 R): 16 tail/obsolete rows (1.x) + 3 rows folded into a big button (fate step)
    assert set(p.planned) == {r['id'] for r in planned} and len(planned) == 19
    v10 = [r for r in planned if r['version'] == '1.0']
    assert not [r for r in v10 if r['fate'] == 'stage'] and len([r for r in v10 if r['fate'] == 'step']) == 3
    for r in planned:
        b = p.planned[r['id']]
        assert not b.isEnabled() and b.text().endswith(roadmap.planned_label(r))
    assert p.planned['tex.vpm_sets'].text().endswith('в кнопке vpm.build')
    assert p.planned['tex.browser'].text().endswith('в версии 1.x')
    stage_only = {r['id'] for r in suite['rows'] if r['id'].partition('.')[0] != r['block']}
    assert len(stage_only) == 15 and not stage_only & set(p.planned)
    assert not any(p.findChild(QtWidgets.QToolButton, 'agr_planned_' + rid) for rid in stage_only)
    assert stage_only <= {model.BY_ID[aid].tool for aid in p.stage_buttons}
    rail_colours = {p.rail.item(i).foreground().color().name() for i in range(1, 11)}
    assert len(rail_colours) == 10


def test_stage_rail_big_buttons_second_rows_wip_disabled(main, qtbot, monkeypatch):
    be = FakeBackend(5)
    p = make(main, be)
    suite = roadmap.load_file(SUITE)
    assert p.findChild(QtWidgets.QLabel, 'agr_stage_title').text() == '<b>{}</b>'.format(model.MENU_100)
    assert list(p.stages) == [s['id'] for s in suite['stages']]  # plan stage order, on the «Путь» page
    assert p.pages.widget(0).isAncestorOf(p.findChild(QtWidgets.QScrollArea, 'agr_stage_rail'))
    assert set(p.stage_buttons) == {a.id for a in model.ACTIONS_100} and len(p.stage_buttons) == 33
    for s in suite['stages']:
        big, status, small = p.stages[s['id']]
        a = model.BY_TOOL[s['big_button']]
        assert big is p.stage_buttons[a.id] and big.objectName() == 'agr_wip_' + a.tool
        assert big.text() == s['label_ru'] and big.toolButtonStyle() == QtCore.Qt.ToolButtonTextUnderIcon
        assert not big.icon().isNull() and status.text() == 'не начат'
        assert [b.objectName() for b in small] == ['agr_wip_' + rid for rid in s['rows'] if rid != s['big_button']]
        assert all(b.toolButtonStyle() == QtCore.Qt.ToolButtonIconOnly and b.iconSize().width() < big.iconSize().width()
                   for b in small)
        # second row sits under its big button, inside the same stage column
        col = p.findChild(QtWidgets.QWidget, 'agr_stage_{}'.format(s['id']))
        assert all(col.isAncestorOf(b) for b in [big] + small)
        assert all(b.geometry().top() > big.geometry().bottom() for b in small)
    stage_label = {s['big_button']: s['label_ru'] for s in suite['stages']}
    for aid, b in p.stage_buttons.items():  # release 1.0.0 (#1024 R): every stage button visible and enabled
        a = model.BY_ID[aid]
        assert b.isEnabled() and not a.wip and not b.isHidden()
        assert b.text() == stage_label.get(a.tool, a.label)
        assert b.toolTip().startswith(model.stage_tip(a.tool)) and 'Когда:' in b.toolTip() and not b.icon().isNull()
    p.run('census')  # after a run the stage buttons are enabled again
    assert all(b.isEnabled() for b in p.stage_buttons.values())
    # a wip stage button (a branch not merged at R) never runs and says so
    wip = model.BY_ID['npm_to_vpm']._replace(wip=True, tip=model.WIP_TIP)
    monkeypatch.setitem(model.BY_ID, 'npm_to_vpm', wip)
    before = list(be.events)
    assert p.run('npm_to_vpm') is None and be.events == before
    assert p.status.text() == 'НПМ → ВПМ: в работе, #1024'


def test_stage_status_comes_from_the_passport(main):
    be = FakeBackend(5)
    suite = roadmap.load_file(SUITE)
    stages = [{'id': s['id'], 'status': 'todo'} for s in suite['stages']]
    stages[1]['status'] = 'work'
    stages[9]['status'] = 'done'
    be.passport = lambda: {'stages': stages}
    p = make(main, be)
    assert p.stages[1][1].text() == 'в работе' and p.stages[9][1].text() == 'готов'
    assert p.stages[0][1].text() == 'не начат'
    stages[2]['status'] = 'lost'  # unreadable passport: said on every stage, never a guessed status
    p.refresh_path()
    assert {lab.text() for _, lab, _ in p.stages.values()} == {'паспорт: ошибка'}
    assert 'lost' in p.stages[0][1].toolTip()


def test_path_nodes_open_tabs_tooltips_and_cards(main, qtbot):
    p = make(main, FakeBackend(5))
    suite = roadmap.load_file(SUITE)
    assert list(p.nodes) == [b['id'] for b in suite['blocks']]
    qtbot.mouseClick(p.findChild(QtWidgets.QToolButton, 'agr_open_qa'), QtCore.Qt.LeftButton)
    assert p.rail.currentRow() == 8 and p.pages.currentIndex() == 8
    btn = p.findChild(QtWidgets.QToolButton, 'agr_path_qa.glass')
    assert btn.isEnabled() and 'NPM-2.7-2' in btn.toolTip() and 'Когда:' in btn.toolTip()
    shipped = p.findChild(QtWidgets.QToolButton, 'agr_path_light.check')
    assert shipped.isEnabled() and 'в версии' not in shipped.text()  # shipped in 0.9.0 (#979)
    released = p.findChild(QtWidgets.QToolButton, 'agr_path_light.export')
    assert released.isEnabled() and 'в версии' not in released.text()  # shipped in 1.0.0 (#1024 R)
    planned = p.findChild(QtWidgets.QToolButton, 'agr_path_tex.browser')  # a 1.x tail row
    assert not planned.isEnabled() and 'в версии 1.x' in planned.text()
    box = p.show_card('qa.glass')
    text = box.text()
    for part in ('Что делает:', 'Когда нужна:', 'Вход:', 'Результат:', 'Сцена: только чтение', 'Связанные кнопки:'):
        assert part in text, part
    box.close()


def test_live_status_and_next_step_follow_the_runs(main):
    be = FakeBackend(5)
    p = make(main, be)
    assert p.next_label.text() == 'Следующий шаг: 0 Сцена и источник: запустить проверки'
    assert p.nodes['scene'][1].text() == 'Статус: не запускалось'
    p.run('census')
    p.run('units')
    assert p.status_by_block['scene'] == 'ok' and p.nodes['scene'][1].text() == 'Статус: ок'
    assert p.next_label.text().startswith('Следующий шаг: 1 Моделирование')
    be.reports['xform'] = {'schema': 1, 'tool': 'xform', 'status': 'fail', 'objects': []}
    p.refresh_path()
    assert p.status_by_block['qa'] == 'errors' and p.nodes['qa'][1].text() == 'Статус: ошибки'
    out = os.environ.get('AGR_UI_SHOTS')
    if out:
        main.grab().save(str(Path(out) / 'offscreen_path_live.png'))
