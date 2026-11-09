"""new-case: AGR Tools 1.1 parameter form of the stage buttons (params_core.py, runtime.edit_ui options, macros).

Defects of 1.0.1 this file pins (CHANGELOG 1.0.0 «Известные ограничения», «Панель»):
P1 the panel passed a 1.0 button only the selection: atlas.facade_strip (period_by_id), tex.dilate / tex.plug_colour
   (files), export.place_by_passport (fbx), agent.request (task), agent.accept (request) refused in the release smoke
   with no way to give the parameter from the panel;
P2 a press without the parameter reached the glue and refused with an internal message; 1.1 refuses before the glue
   with `needs_params: <tool>: ...` naming the form fields (never silently);
P3 the held preview of edit_ui was applied by the next press on the same selection even when the parameters
   changed; 1.1 applies only with the same selection AND options;
P4 the macros of these rows pressed without options; 1.1 opens the panel form (runtime.form_ui).
Plain pytest, no pymxs (the Qt form is in test_agr_tools_110_panel.py).
"""
import importlib.util
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pc = _load(PKG / 'params_core.py', 'agr_tools_params_core_110p')
model = _load(PKG / 'ui_model.py', 'agr_tools_ui_model_110p')
NEED_10 = ('atlas.facade_strip', 'tex.dilate', 'tex.plug_colour', 'export.place_by_passport', 'agent.request',
           'agent.accept')  # the six rows CHANGELOG 1.0.0 names


def _set_literal(path, start):
    text = (PKG / path).read_text(encoding='utf-8')
    m = re.search(re.escape(start) + r'\s*(\{[^}]*\})', text)
    assert m, (path, start)
    return set(eval(m.group(1)))  # noqa: S307 - a literal set of option names in our own file


def glue_keys(tool):
    """Option names the glue of `tool` reads, from its own tables (never from params_core)."""
    if tool.startswith('handoff.'):
        hc = _load(PKG / 'handoff_core.py', 'agr_tools_handoff_core_110p')
        return set({'handoff.export': hc.EXPORT_OPTIONS, 'handoff.import': hc.IMPORT_OPTIONS,
                    'handoff.verify': hc.VERIFY_OPTIONS, 'handoff.restore_materials': hc.RESTORE_OPTIONS}[tool])
    if tool == 'agent.request':
        ab = _load(PKG / 'agentbridge_core.py', 'agr_tools_agentbridge_core_110p')
        return set(ab.options({'task': 'x'}))
    if tool == 'agent.accept':
        return _set_literal('agentbridge_max.py', "unknown = set(opt) -")
    if tool == 'export.place_by_passport':
        return _set_literal('placegeo_core.py', "unknown = set(o) -")
    if tool == 'tex.dilate':
        return _set_literal('dilate_core.py', 'known =')
    if tool == 'tex.plug_colour':
        text = (PKG / 'plugcolour_max.py').read_text(encoding='utf-8')
        return {k for k in ('paths', 'folder') if "ctx.options.get('{}')".format(k) in text}
    if tool == 'atlas.facade_strip':
        fa = _load(PKG / 'facadeatlas_core.py', 'agr_tools_facadeatlas_core_110p')
        return set(fa.OPTION_KEYS)
    raise KeyError(tool)


def test_p1_every_named_row_has_a_form_with_the_glue_option_names():
    assert set(NEED_10) <= set(pc.TOOLS)
    assert tuple(pc.TOOLS) == model.FORM_100
    for tool in pc.TOOLS:
        keys = {f.key for f in pc.fields(tool)}
        assert keys <= glue_keys(tool), (tool, keys - glue_keys(tool))
        for alts in pc.REQUIRED[tool]:
            assert set(alts) <= keys, tool
        assert all(f.kind in pc.KINDS and f.label for f in pc.fields(tool))


def test_p1_defaults_from_the_passport_bundles_requests_and_the_last_run():
    ctx = {'passport_path': 'C:/jobs/KPP1/passport.json', 'passport': {'project_id': 'KPP1'},
           'bundles': ['C:/jobs/KPP1/handoff/001', 'C:/jobs/KPP1/handoff/002'],
           'requests': ['C:/jobs/KPP1/agent/a/request.json', 'C:/jobs/KPP1/agent/b/request.json']}
    assert pc.defaults('handoff.export', ctx)['job_dir'] == 'C:/jobs/KPP1'
    assert pc.defaults('handoff.import', ctx)['bundle'] == 'C:/jobs/KPP1/handoff/002'
    assert pc.defaults('agent.accept', ctx)['request'] == 'C:/jobs/KPP1/agent/b/request.json'
    assert pc.defaults('agent.request', ctx)['job_dir'] == 'C:/jobs/KPP1'
    assert pc.defaults('export.place_by_passport', ctx)['passport'] == 'C:/jobs/KPP1/passport.json'
    assert pc.defaults('handoff.restore_materials', ctx)['reuse'] == 'scene'
    assert pc.defaults('agent.request', dict(ctx, last={'task': 'again'}))['task'] == 'again'
    empty = pc.defaults('handoff.import', {})
    assert empty['bundle'] == '' and pc.missing('handoff.import', pc.parse('handoff.import', empty))


def test_p1_parse_types_and_errors_name_the_field():
    assert pc.parse('tex.dilate', {'files': 'a.png; b.png\nc.png', 'folder': '', 'out': ' C:/o ', 'profile': 'npm'}) \
        == {'files': ['a.png', 'b.png', 'c.png'], 'out': 'C:/o', 'profile': 'npm'}
    assert pc.parse('atlas.facade_strip', {'period_by_id': '{"3": [3.6, 3.0]}'}) == {'period_by_id': {'3': [3.6, 3.0]}}
    assert pc.parse('export.place_by_passport', {'fbx': 'x.fbx', 'accept_precision_loss': False}) == {'fbx': 'x.fbx'}
    for tool, values, word in (('atlas.facade_strip', {'period_by_id': '{3:'}, 'не JSON'),
                               ('atlas.facade_strip', {'period_by_id': '[1]'}, 'объект JSON'),
                               ('tex.dilate', {'profile': 'xx'}, 'одно из'),
                               ('agent.request', {'nope': 1}, 'unknown')):
        with pytest.raises(ValueError, match=word):
            pc.parse(tool, values)
    assert pc.missing('tex.dilate', {'folder': 'C:/maps'}) == []
    assert pc.missing('tex.dilate', {}) == ['Карты PNG или Папка карт']
    assert pc.missing('qa.xview', {}) == []  # a row without a form needs nothing
    assert pc.needs_params_text('agent.request', {}).startswith('needs_params: agent.request: ')


def test_p1_scan_project_orders_bundles_by_number_and_requests_by_time(tmp_path):
    for seq in ('002', '001', 'tmp'):
        (tmp_path / 'handoff' / seq).mkdir(parents=True)
    for req, t in (('zzz', 1), ('aaa', 2)):
        d = tmp_path / 'agent' / req
        d.mkdir(parents=True)
        (d / 'request.json').write_text('{}', encoding='utf-8')
        os.utime(d / 'request.json', (t * 1e6, t * 1e6))
    got = pc.scan_project(str(tmp_path))
    assert [Path(p).name for p in got['bundles']] == ['001', '002']
    assert [Path(p).parent.name for p in got['requests']] == ['zzz', 'aaa']
    assert pc.scan_project(str(tmp_path / 'none')) == {'bundles': [], 'requests': []}


# ---- runtime.edit_ui -------------------------------------------------------------------------------------------
def _runtime(monkeypatch, calls):
    rt = _load(PKG / 'runtime.py', 'agr_runtime_110p')
    ec = rt._edit_core()
    monkeypatch.setattr(rt, '_selection_key', lambda: (1,))

    def fake(tool, mode, preview=None, nodes=None, options=None, actor='panel'):
        calls.append((tool, mode, options))
        return ec.report(tool, mode, objects=[ec.entry(5, 'Box')], done=['Box'],
                         state_hash=ec.fingerprint((1,)) if mode == 'preview' else None)
    monkeypatch.setattr(rt, 'edits_100', fake)
    return rt


def test_p2_press_without_required_options_is_refused_naming_the_fields(monkeypatch):
    calls = []
    rt = _runtime(monkeypatch, calls)
    for tool in NEED_10 + ('handoff.import',):
        with pytest.raises(ValueError, match='^needs_params: ' + re.escape(tool)):
            rt.edit_ui(tool)
    assert calls == []  # refused before the glue
    rt.edit_ui('body.roof')  # a row without a form still presses with the selection only
    assert calls == [('body.roof', 'preview', None)]


def test_p3_held_preview_is_applied_only_with_the_same_options(monkeypatch):
    calls = []
    rt = _runtime(monkeypatch, calls)
    a, b = {'task': 'mark openings'}, {'task': 'other'}
    assert rt.edit_ui('agent.request', options=a)['plan']['mode'] == 'preview'
    assert rt.edit_ui('agent.request', options=b)['plan']['mode'] == 'preview'  # changed options: a new preview
    assert rt.edit_ui('agent.request', options=b)['plan']['mode'] == 'apply'
    assert calls[0] == ('agent.request', 'preview', a) and calls[1] == ('agent.request', 'preview', b)
    assert calls[2][:2] == ('agent.request', 'apply') and calls[2][2] is None  # apply takes only the preview


def test_p4_form_rows_macro_opens_the_form_and_form_ui_refuses_other_rows(monkeypatch):
    mcr = model.macros_ms()
    for tool in model.FORM_100:
        assert "agr_tools_runtime.form_ui('{}')".format(tool) in mcr
        assert "agr_tools_runtime.edit_ui('{}')".format(tool) not in mcr
    assert "agr_tools_runtime.edit_ui('body.roof')" in mcr
    rt = _load(PKG / 'runtime.py', 'agr_runtime_110p4')
    with pytest.raises(ValueError, match='no parameter form'):
        rt.form_ui('body.roof')
    opened = []
    monkeypatch.setattr(rt, 'panel', lambda: type('P', (), {'open_form': lambda self, t: opened.append(t)})())
    rt.form_ui('tex.dilate')
    assert opened == ['tex.dilate']


def test_agent_dock_is_a_macro_and_a_menu_entry_and_calls_branch_u(monkeypatch):
    mcr, menu = model.macros_ms(), model.menu_ms()
    assert 'macroScript {} '.format(model.DOCK_MACRO) in mcr
    assert '(on execute do python.Execute "agr_tools_runtime.agent_dock()")' in mcr
    assert model.stable_id(model.DOCK_MACRO) in menu
    icons = _load(ROOT / 'tools/max/agr_icons.py', 'agr_icons_110p')
    assert model.DOCK_ICON in icons.names()
    rt = _load(PKG / 'runtime.py', 'agr_runtime_110pd')
    seen = []
    real = rt._load_core

    class Bridge:
        @staticmethod
        def agent_dock(profile='modeller'):
            seen.append(profile)
            return 'dock'
    monkeypatch.setattr(rt, '_load_core', lambda name, key: Bridge if name == 'agentbridge_max.py' else real(name, key))
    assert rt.agent_dock() == 'dock' and seen == ['modeller']
    src = (PKG / 'agentbridge_max.py').read_text(encoding='utf-8')
    assert "def agent_dock(repo=None, profile='modeller'" in src
