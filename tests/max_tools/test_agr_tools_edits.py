"""new-case: AGR Tools 0.8 base (#908): edit contract, EDITS_080 registry/dispatcher, UI/macro/icon/MCP wiring.

Plain pytest, no pymxs: the stub modules of branches A–D are empty, so every 0.8 tool answers not_implemented;
the full preview -> apply round trip is exercised with a fake glue module in place of a stub.
"""
import ast
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'
STUBS = ('geom', 'tex', 'names', 'udim', 'package')
OWNER = {'model.triangulate': 'geom', 'ucx.triangulate': 'geom', 'export.pivot_place': 'geom',
         'tex.format_fix': 'tex', 'tex.placeholders': 'tex', 'scene.missing_maps': 'tex',
         'qa.names_fix': 'names', 'ucx.rename': 'names', 'udim.ids_to_udims': 'udim',
         'qa.package': 'package', 'export.zip': 'package', 'export.ground_fbx': 'package',
         'export.geojson_write': 'package'}  # SPLIT.md: A geom, B tex, C names/udim, D package


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_t')
m = _load(PKG / 'ui_model.py', 'agr_tools_ui_model_edits')
icons = _load(ROOT / 'tools/max/agr_icons.py', 'agr_icons_edits')
builder = _load(ROOT / 'tools/max/build_agr_tools.py', 'agr_builder_edits')
suite = json.loads(SUITE.read_text(encoding='utf-8'))
ROWS_080 = {r['id']: r for r in suite['rows'] if r['version'] == '0.8'}


def runtime():
    return _load(PKG / 'runtime.py', 'agr_runtime_edits')


def _preview(tool='model.triangulate', state=None, **kw):
    state = state if state is not None else [{'handle': 5, 'name': 'Box', 'transform': [1.0] * 12, 'mesh': 'ab'}]
    kw.setdefault('objects', [ec.entry(5, 'Box')])
    kw.setdefault('done', ['Box'])
    return ec.report(tool, 'preview', state_hash=ec.fingerprint(state), **kw), state


# ---- edit_core: preview -> apply with hash check -----------------------------------------------------------
def test_preview_roundtrip_and_hash_covers_the_whole_report():
    p, state = _preview(skipped_=[ec.skipped('Sphere', 'not Editable_Poly')], extra={'actions': [{'n': 1}]})
    assert p['status'] == 'pass' and p['plan']['mode'] == 'preview' and len(p['plan']['hash']) == 64
    assert ec.check_preview('model.triangulate', p) is p
    assert ec.require_current(p, json.loads(json.dumps(state))) is p
    for path in (('objects', 0, 'name'), ('plan', 'done', 0), ('plan', 'actions', 0, 'n'), ('plan', 'state_hash'),
                 ('plan', 'skipped', 0, 'reason')):
        bad = json.loads(json.dumps(p))
        node = bad
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = node[path[-1]] + (1 if isinstance(node[path[-1]], int) else 'x')
        with pytest.raises(ec.StalePreview):
            ec.check_preview('model.triangulate', bad)


def test_preview_refused_for_other_tool_apply_report_stub_and_garbage():
    p, _ = _preview()
    with pytest.raises(ec.StalePreview, match='another tool'):
        ec.check_preview('ucx.triangulate', p)
    applied = ec.report('model.triangulate', 'apply', objects=[ec.entry(5, 'Box')], done=['Box'])
    for bad in (applied, ec.not_implemented('model.triangulate', 'preview'), None, [], 'preview', {}):
        with pytest.raises(ec.StalePreview):
            ec.check_preview('model.triangulate', bad)


def test_changed_scene_state_makes_the_preview_stale():
    p, state = _preview()
    moved = json.loads(json.dumps(state))
    moved[0]['transform'][3] = 1.001
    with pytest.raises(ec.StalePreview, match='scene changed'):
        ec.require_current(p, moved)


def test_report_lists_status_and_contract():
    r = ec.report('qa.names_fix', 'apply', objects=[ec.entry(3, 'a', [ec.finding('bad_name', [2, 2, 1], 'x')])])
    assert r['status'] == 'fail' and r['objects'][0]['findings'][0]['ids'] == [1, 2]
    assert set(r) == {'schema', 'tool', 'status', 'objects', 'plan'} and r['plan']['contract'] == '0.5.0'
    assert ec.report('qa.names_fix', 'apply', ambiguous=[{'item': 'a', 'candidates': ['b', 'c']}])['status'] == 'fail'
    with pytest.raises(ValueError, match='reason'):
        ec.skipped('a', '  ')
    claimed = dict(r, status='pass')
    with pytest.raises(ValueError, match='inconsistent'):
        ec.validate_report(claimed)
    with pytest.raises(ValueError):
        ec.report('x', 'commit')
    with pytest.raises(ValueError, match='state_hash'):
        ec.report('x', 'preview')
    with pytest.raises(ValueError, match='reserved'):
        ec.report('x', 'apply', extra={'done': []})
    with pytest.raises(ValueError):
        ec.report('x', 'apply', extra={'v': float('nan')})
    bad = json.loads(json.dumps(r))
    bad['plan']['skipped'] = [{'item': 'a'}]
    with pytest.raises(ValueError):
        ec.validate_report(bad)
    bad = json.loads(json.dumps(r))
    bad['plan']['hash'] = 'f' * 64
    with pytest.raises(ValueError, match='apply report'):
        ec.validate_report(bad)
    for dup in ([ec.entry(1, 'a'), ec.entry(1, 'b')], [ec.entry(0, 'a')], [{'handle': 1, 'name': 'a'}]):
        with pytest.raises(ValueError):
            ec.report('x', 'apply', objects=dup)


def test_not_implemented_report_is_empty_and_strict():
    r = ec.not_implemented('export.zip', 'apply')
    assert r['status'] == 'not_implemented' and r['objects'] == [] and r['plan']['issue'] == '#908'
    for k in ('done', 'skipped', 'ambiguous'):
        bad = json.loads(json.dumps(r))
        bad['plan'][k] = [{'item': 'a', 'reason': 'b'}]
        with pytest.raises(ValueError):
            ec.validate_report(bad)
    with pytest.raises(ValueError):
        ec.parse('{"a": 1, "a": 2}')
    with pytest.raises(ValueError):
        ec.parse('{"a": NaN}')


# ---- edit_core: never overwrite ------------------------------------------------------------------------
def test_new_path_refuses_or_versions_never_overwrites(tmp_path):
    free = tmp_path / 'SM_Addr_Ground.fbx'
    assert ec.new_path(free) == str(free)
    free.write_bytes(b'old')
    with pytest.raises(FileExistsError):
        ec.new_path(free)
    v2 = ec.new_path(free, version=True)
    assert Path(v2).name == 'SM_Addr_Ground_v002.fbx'
    (tmp_path / 'pack_v007.zip').write_bytes(b'x')
    (tmp_path / 'pack_v008.zip').write_bytes(b'x')
    assert Path(ec.new_path(tmp_path / 'pack_v007.zip', version=True)).name == 'pack_v009.zip'
    with pytest.raises(FileExistsError):
        ec.write_new(free, b'new')
    assert free.read_bytes() == b'old'
    ec.write_new(v2, b'new')
    assert Path(v2).read_bytes() == b'new'


# ---- runtime registry + dispatcher ---------------------------------------------------------------------
def test_registry_matches_the_13_plan_rows_of_version_08():
    rt = runtime()
    assert len(ROWS_080) == 13 and set(rt.EDITS_080) == set(ROWS_080)
    assert set(rt.READ_080) == {rid for rid, r in ROWS_080.items() if r['mode'] == 'read'}
    for rid, (core_file, fn) in rt.EDITS_080.items():
        assert core_file == OWNER[rid] + '_core.py' and (PKG / core_file).is_file()
        assert (PKG / core_file.replace('_core.py', '_max.py')).is_file()
        assert fn == rid.replace('.', '_')
    assert rt.VERSION == m.VERSION == '0.7.0'  # 0.8 stays unshipped until the release branch R


def _glue_functions(stem):
    tree = ast.parse((PKG / '{}_max.py'.format(stem)).read_text(encoding='utf-8'))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def _implemented(tool):
    """A branch A–D has filled the glue function of this tool (then its own tests own the behaviour)."""
    return tool.replace('.', '_') in _glue_functions(OWNER[tool])


def test_stub_modules_are_empty_and_load_without_pymxs():
    for stem in STUBS:
        for part in ('core', 'max'):
            tree = ast.parse((PKG / '{}_{}.py'.format(stem, part)).read_text(encoding='utf-8'))
            if not any(_implemented(t) for t, s in OWNER.items() if s == stem):  # still a stub of branch 0
                assert len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr), (stem, part)  # docstring only
            top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
            assert not any('pymxs' in ast.dump(n) for n in top), (stem, part)  # loads under plain pytest
    for name in ('edit_core.py', 'edit_max.py'):
        tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert not any('pymxs' in ast.dump(n) for n in top), name


@pytest.mark.parametrize('tool', sorted(ROWS_080))
def test_every_tool_answers_not_implemented_while_its_stub_is_empty(tool):
    if _implemented(tool):
        pytest.skip(tool + ' is implemented; covered by its branch tests')
    rt = runtime()
    r = rt.edits_080(tool, 'preview')
    assert r == rt._edit_core().not_implemented(tool, 'preview')
    assert rt.parse_report(json.dumps(r)) == r
    assert m.rows(r) == [m.Row(None, '—', tool, False, 'not_implemented', 'в работе (#908): модуль ещё пуст', ())]


def test_dispatcher_refusals():
    rt = runtime()
    p, _ = _preview()
    cases = [(('nope', 'preview'), 'unsupported edit tool'), ((['x'], 'preview'), 'unsupported edit tool'),
             (('model.triangulate', 'commit'), 'mode'), (('model.triangulate', 'apply'), 'needs the preview'),
             (('scene.missing_maps', 'apply', p), 'read-only'), (('qa.package', 'apply', p), 'read-only'),
             (('model.triangulate', 'preview', p), 'takes no preview')]
    for args, word in cases:
        with pytest.raises(ValueError, match=word):
            rt.edits_080(*args)
    with pytest.raises(ValueError, match='options belong'):
        rt.edits_080('model.triangulate', 'apply', p, options={'a': 1})
    with pytest.raises(ValueError):
        rt.edits_080('model.triangulate', 'preview', options=['a'])
    tampered = json.loads(json.dumps(p))
    tampered['plan']['done'] = ['Other']
    with pytest.raises(rt._edit_core().StalePreview):
        rt.edits_080('model.triangulate', 'apply', tampered)


def _fake_glue(rt, monkeypatch, fn):
    """Put a glue function where branch A will write it: geom_max.model_triangulate."""
    real = rt._load_core
    glue = types.ModuleType('fake_geom_max')
    glue.model_triangulate = fn

    def load(filename, module_name):
        return glue if filename == 'geom_max.py' else real(filename, module_name)
    monkeypatch.setattr(rt, '_load_core', load)


def test_preview_apply_round_trip_through_the_dispatcher(monkeypatch):
    rt = runtime()
    scene = {'state': [{'handle': 9, 'name': 'Wall', 'transform': [0.0] * 12, 'mesh': 'm1'}]}
    calls = []

    def model_triangulate(ctx, mode, nodes, preview):
        calls.append((mode, nodes, dict(ctx.options)))
        assert ctx.edit.MODES == ('preview', 'apply') and ctx.core.__name__.endswith('geom_core')
        if mode == 'preview':
            return ctx.edit.report('model.triangulate', 'preview', objects=[ctx.edit.entry(9, 'Wall')],
                                   done=['Wall'], state_hash=ctx.edit.fingerprint(scene['state']),
                                   extra={'options': ctx.options})
        ctx.edit.require_current(preview, scene['state'])
        return ctx.edit.report('model.triangulate', 'apply', objects=[ctx.edit.entry(9, 'Wall')],
                               done=['Wall_AGR_export_01'])
    _fake_glue(rt, monkeypatch, model_triangulate)
    p = rt.edits_080('model.triangulate', 'preview', options={'tol_m': 0.001})
    assert p['plan']['options'] == {'tol_m': 0.001}
    done = rt.edits_080('model.triangulate', 'apply', p)
    assert done['plan']['done'] == ['Wall_AGR_export_01'] and [c[0] for c in calls] == ['preview', 'apply']
    scene['state'][0]['mesh'] = 'm2'  # the scene changed after the preview
    with pytest.raises(rt._edit_core().StalePreview, match='scene changed'):
        rt.edits_080('model.triangulate', 'apply', p)


def test_dispatcher_rejects_glue_answers_for_another_tool_or_mode(monkeypatch):
    rt = runtime()
    _fake_glue(rt, monkeypatch, lambda ctx, mode, nodes, preview: ctx.edit.report(
        'ucx.triangulate', 'apply', done=['x']))
    with pytest.raises(ValueError, match='another tool/mode'):
        rt.edits_080('model.triangulate', 'preview')
    _fake_glue(rt, monkeypatch, lambda ctx, mode, nodes, preview: {'status': 'pass'})
    with pytest.raises(ValueError, match='incomplete'):
        rt.edits_080('model.triangulate', 'preview')


def test_two_press_ui_keeps_the_preview_per_selection(monkeypatch):
    rt = runtime()
    scene = {'sel': (1, 2), 'state': [1]}

    def model_triangulate(ctx, mode, nodes, preview):
        if mode == 'apply':
            ctx.edit.require_current(preview, scene['state'])
            return ctx.edit.report('model.triangulate', 'apply', done=['copy'])
        return ctx.edit.report('model.triangulate', 'preview', done=['x'],
                               state_hash=ctx.edit.fingerprint(scene['state']))
    _fake_glue(rt, monkeypatch, model_triangulate)
    monkeypatch.setattr(rt, '_selection_key', lambda: scene['sel'])
    assert rt.edit_ui('model.triangulate')['plan']['mode'] == 'preview'
    scene['sel'] = (1, 3)  # another selection: preview again, never apply the old one
    assert rt.edit_ui('model.triangulate')['plan']['mode'] == 'preview'
    assert rt.edit_ui('model.triangulate')['plan']['mode'] == 'apply'
    assert rt.edit_ui('model.triangulate')['plan']['mode'] == 'preview'  # the preview is used once
    # a read-only row whose glue is still empty (independent of branch B filling tex_max.py)
    loaded = rt._load_core
    monkeypatch.setattr(rt, '_load_core', lambda filename, module_name: types.ModuleType('empty_tex_max')
                        if filename == 'tex_max.py' else loaded(filename, module_name))
    assert rt.edit_ui('scene.missing_maps')['status'] == 'not_implemented'
    assert 'scene.missing_maps' not in rt._edits
    assert "elif tool in EDITS_080:\n        report = edit_ui(tool)" in (PKG / 'runtime.py').read_text(encoding='utf-8')


def test_panel_backend_routes_edit_tools_to_edits_080():
    src = (PKG / 'ui_max.py').read_text(encoding='utf-8')
    assert 'if tool in self.agr.EDITS_080:' in src and 'self.agr.edit_ui(tool)' in src


# ---- UI: section, actions, macros, menu, icons ---------------------------------------------------------
def test_each_08_row_has_one_action_with_macro_icon_and_menu_entry():
    acts = [a for a in m.ACTIONS if a.section == m.SECTIONS.index('Сдача (копии)')]
    assert len(acts) == 13 and {a.tool for a in acts} == set(ROWS_080)
    mcr, menu = m.macros_ms(), m.menu_ms()
    for a in acts:
        r = ROWS_080[a.tool]
        assert m.row_of(a.id) == a.tool and a.icon == r['icon'] and a.icon in icons.names()
        assert ' '.join(a.reqs) == r['reqs'] and a.macro.startswith('AGRTools') and not a.batch
        assert 'macroScript {} category:"AGR Tools"'.format(a.macro) in mcr
        assert "agr_tools_runtime.ui('{}')".format(a.tool) in mcr and '"{}`AGR Tools"'.format(a.macro) in menu
        assert icons.svg(a.icon, '#000000').startswith('<svg') and 'currentColor' not in icons.svg(a.icon, '#000')
    assert len({a.macro for a in m.ACTIONS}) == len(m.ACTIONS)
    assert sorted(r['icon'] for r in ROWS_080.values()) == sorted(
        ['missing', 'triangulate', 'pngfix', 'plug', 'ucxtri', 'ucxname', 'id2udim', 'namefix', 'package',
         'geojsonw', 'groundfbx', 'place', 'zip'])


def test_rail_keeps_08_actions_greyed_until_version_080():
    rail = m.rail(suite['blocks'], suite['rows'])
    done = {m.row_of(a.id) for _, d, _ in rail for a in d}
    planned = {r['id'] for _, _, p in rail for r in p}
    assert not done & set(ROWS_080) and set(ROWS_080) <= planned
    rail08 = m.rail(suite['blocks'], suite['rows'], '0.8.0')
    assert set(ROWS_080) <= {m.row_of(a.id) for _, d, _ in rail08 for a in d}


def test_builder_ships_the_edit_contract_and_every_stub():
    new = {'edit_core.py', 'edit_max.py'} | {'{}_{}.py'.format(s, p) for s in STUBS for p in ('core', 'max')}
    assert len(new) == 12 and new <= set(builder.FILES) and len(builder.FILES) == len(set(builder.FILES))
    install = (PKG / 'install.ms').read_text(encoding='utf-8-sig')
    for name in new:
        assert '"{}"'.format(name) in install


# ---- MCP -----------------------------------------------------------------------------------------------
def test_mcp_tools_map_one_to_one_and_apply_takes_only_the_preview():
    sys.path.insert(0, str(ROOT / 'src'))
    try:
        from agr_mcp import tools
        bridge = _load(ROOT / 'src/agr_mcp/max_side/max_bridge.py', 'agr_max_bridge_edits')
    finally:
        sys.path.pop(0)
    assert {row for _, row, _, _ in tools.EDITS_080} == set(ROWS_080)
    for name, row, _, kind in tools.EDITS_080:
        block, rest = row.split('.')
        assert name == 'agr_{}_{}'.format(block, rest) and bridge.EDITS_080[name] == row
        assert (kind == 'read') == (ROWS_080[row]['mode'] == 'read')
    assert set(bridge.EDITS_080) == {n for n, *_ in tools.EDITS_080} and set(bridge.EDITS_080) <= set(tools.PHASE0)
    cat = tools.catalog()
    p, _ = _preview()
    ok = [{'scene': 'live', 'mode': 'preview'}, {'scene': 'live', 'mode': 'preview', 'options': {'a': 1}},
          {'scene': 'live', 'mode': 'apply', 'preview': p, 'handles': [3]}]
    bad = [{'scene': 'live'}, {'scene': 'live', 'mode': 'apply'}, {'scene': 'live', 'mode': 'preview', 'preview': p},
           {'scene': 'live', 'mode': 'apply', 'preview': p, 'options': {}}, {'scene': 'live', 'mode': 'run'},
           {'scene': 'live', 'mode': 'preview', 'code': '1'}]
    for args in ok:
        jsonschema.validate(args, cat['agr_model_triangulate'].input)
    for args in bad:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(args, cat['agr_model_triangulate'].input)
    jsonschema.validate({'scene': 'live', 'handles': [1]}, cat['agr_qa_package'].input)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'scene': 'live', 'mode': 'apply'}, cat['agr_scene_missing_maps'].input)
    jsonschema.validate(ec.not_implemented('export.zip', 'preview'), cat['agr_export_zip'].result)


# ---- plan, changelog, native runners -------------------------------------------------------------------
def test_lab_verdict_wins_for_three_rows():
    for rid in ('model.triangulate', 'ucx.triangulate', 'export.ground_fbx'):
        r = ROWS_080[rid]
        assert r['verdict'] == 'take_fix' and r['verdict_note'].startswith('лаборатория #907')
    by = {}
    for r in suite['rows']:
        by[r['verdict']] = by.get(r['verdict'], 0) + 1
    assert suite['stats']['by_verdict'] == by


def test_changelog_has_08_in_work_with_four_non_empty_branch_subsections():
    text = (PKG / 'CHANGELOG.md').read_text(encoding='utf-8')
    head = text[text.index('## 0.8.0 (#908) — в работе'):text.index('## 0.7.0')]
    subs = re.split(r'^### ', head, flags=re.M)[1:]
    letters = [s.split(' ', 1)[0] for s in subs]
    assert letters == ['Основа', 'A', 'B', 'C', 'D']
    for s in subs:
        assert re.search(r'^- \S', s, re.M), s[:40]


def test_native_runners_derive_the_startup_file_from_the_installed_version():
    """Lab CI ace829fd: a literal AGRTools-0.6.0.ms kept the Max 2024 jobs red after the 0.7.0 build."""
    for name in ('run_agr_tools_native.py', 'run_agr_tools_checks_native.py'):
        src = (ROOT / 'tests/max_tools' / name).read_text(encoding='utf-8')
        assert not re.search(r'AGRTools-\d', src) and not re.search(r'AGR-Tools-\d', src), name
        assert "STARTUP = OUT / 'startup' / 'AGRTools-{}.ms'.format(agr.VERSION)" in src, name
    install = (PKG / 'install.ms').read_text(encoding='utf-8-sig')
    assert 'AGRTools-{}.ms'.format(runtime().VERSION) in install
