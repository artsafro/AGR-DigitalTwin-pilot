"""new-case: AGR Tools 1.1 parameter form and «Claude-док» in the Qt panel (pytest-qt, offscreen, fake backend).

Defects of 1.0.1 (CHANGELOG 1.0.0 «Известные ограничения», «Панель» and «Агент»):
F1 a stage button that needs a parameter ran with the selection only and the row refused; 1.1 opens a compact form
   filled with the defaults (passport, last run) and runs nothing until «Выполнить»;
F2 «Выполнить» with an empty required field or a bad value runs nothing and names the field (never silent);
F3 the values of the form go to the backend as the row options; the next press of the row reuses the last values;
F4 the agent dock (agentbridge_max.agent_dock) had no button in the panel.
The fake backend and the helpers come from test_agr_tools_ui_qt.py (same Qt guard).
"""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location('agr_ui_qt_tests_110', Path(__file__).with_name('test_agr_tools_ui_qt.py'))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
QtWidgets, model, ui = base.QtWidgets, base.model, base.ui


class FormBackend(base.FakeBackend):
    def __init__(self):
        super().__init__()
        self.docked = 0
        self.calls = []

    def run_tool(self, tool, scope_all, options=None):
        self.calls.append((tool, options))
        return super().run_tool(tool, scope_all)

    def form_context(self, tool):
        return {'passport_path': 'C:/jobs/KPP1/passport.json', 'passport': {'project_id': 'KPP1'},
                'bundles': ['C:/jobs/KPP1/handoff/001'], 'requests': []}

    def agent_dock(self):
        self.docked += 1


@pytest.fixture
def main(qtbot):
    w = QtWidgets.QMainWindow()
    w.setCentralWidget(QtWidgets.QLabel('viewport'))
    w.resize(1400, 900)
    qtbot.addWidget(w)
    return w


def _w(p, key):
    return p.form_widgets[key][1]


def test_f1_form_row_opens_its_form_with_defaults_and_runs_nothing(main):
    b = FormBackend()
    p = base.make(main, b)
    a = model.BY_TOOL['handoff.import']
    assert p.run(a.id) is None and b.calls == []
    assert p.form_box.isVisible() and p.form_tool == 'handoff.import'
    assert _w(p, 'bundle').text() == 'C:/jobs/KPP1/handoff/001'
    assert 'handoff.import' in p.form_box.title()
    p.stage_buttons[model.BY_TOOL['handoff.export'].id].click()  # the stage button itself opens the form
    assert p.form_tool == 'handoff.export' and _w(p, 'job_dir').text() == 'C:/jobs/KPP1' and b.calls == []


def test_f2_empty_required_or_bad_value_names_the_field(main):
    b = FormBackend()
    p = base.make(main, b)
    p.run(model.BY_TOOL['agent.request'].id)
    assert 'Задача агенту' in p.form_hint.text()
    p.form_run.click()
    assert b.calls == [] and 'Задача агенту' in p.status.text()
    p.run(model.BY_TOOL['atlas.facade_strip'].id)
    _w(p, 'period_by_id').setText('{3:')
    p.form_run.click()
    assert b.calls == [] and 'не JSON' in p.form_hint.text()


def test_f3_values_go_to_the_backend_and_are_kept_for_the_next_press(main):
    b = FormBackend()
    p = base.make(main, b)
    a = model.BY_TOOL['agent.request']
    p.run(a.id)
    _w(p, 'task').setText('mark the openings')
    p.form_run.click()
    assert b.calls == [('agent.request', {'task': 'mark the openings', 'job_dir': 'C:/jobs/KPP1'})]
    p.form_run.click()  # the second «Выполнить» with the same values: the runtime applies the held preview
    assert b.calls[-1] == b.calls[0] and len(b.calls) == 2
    p.close_form()
    p.run(a.id)
    assert _w(p, 'task').text() == 'mark the openings'
    r = model.BY_TOOL['handoff.restore_materials']
    p.run(r.id)
    _w(p, 'reuse').setCurrentIndex(1)
    p.form_run.click()
    assert b.calls[-1] == ('handoff.restore_materials', {'bundle': 'C:/jobs/KPP1/handoff/001', 'reuse': 'never'})
    p.run(model.BY_TOOL['body.roof'].id)  # a row without a form runs at once, without options
    assert b.calls[-1] == ('body.roof', None)


def test_f4_claude_dock_button(main):
    b = FormBackend()
    p = base.make(main, b)
    assert p.dock_btn.text() == model.DOCK_LABEL and p.dock_btn.isEnabled()
    p.dock_btn.click()
    assert b.docked == 1 and model.DOCK_LABEL in p.status.text()

    class Broken(FormBackend):
        def agent_dock(self):
            raise RuntimeError('no claude.exe')
    b2 = Broken()
    p2 = base.make(main, b2)
    p2.dock_btn.click()
    assert 'no claude.exe' in p2.status.text() and b2.events[-1][:2] == ('error', 'agent.dock')
    old = base.make(main, base.FakeBackend())  # a backend without agent_dock: the button is disabled
    assert not old.dock_btn.isEnabled()
