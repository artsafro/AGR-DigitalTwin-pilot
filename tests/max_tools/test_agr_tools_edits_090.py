"""new-case: AGR Tools 0.9 base (#979, branch 0): EDITS_090 registry/dispatcher, stubs, UI/macro/icon/MCP wiring,
cleanup options, the polygon bases 0.8/0.9 with the station-fragment hook, and the strict roadmap.load().

Plain pytest, no pymxs: the stub modules of branches A–D are empty, so every 0.9 tool answers not_implemented;
the dispatch path is exercised with a fake glue module in place of a stub. Once a branch fills its glue function,
that tool's not_implemented check skips and the branch's own tests own the behaviour.
"""
import ast
import copy
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
GEOAGR_MS = Path('C:/agr/GeoAGR-private/versions/13.64/GeoAGR.ms')  # private; the citation test skips without it
# SPLIT.md (#979) «Ветка 0»: glue module of every 0.9 row and the branch that owns it
GLUE = {'tex.erm_normal_check': ('texqa_max.py', 'B'), 'tex.finish_map': ('finish_max.py', 'B'),
        'udim.matid_unwrap': ('uvtile_max.py', 'B'), 'udim.slots': ('uvtile_max.py', 'B'),
        'atlas.flora': ('flora_atlas_max.py', 'B'), 'atlas.groundel': ('flora_atlas_max.py', 'B'),
        'place.flora_repair': ('place_max.py', 'A'), 'place.maf_checks': ('place_max.py', 'A'),
        'place.replace': ('place_max.py', 'A'), 'place.schedule': ('place_max.py', 'A'),
        'place.drop_to_ground': ('place_max.py', 'A'), 'qa.address': ('qa9_max.py', 'C'),
        'qa.facade_compare': ('facade_max.py', 'C'), 'qa.normals': ('qa9_max.py', 'C'),
        'qa.sintez': ('qa9_max.py', 'C'), 'qa.procedural_objects': ('qa9_max.py', 'C'),
        'export.batch': ('batch_max.py', 'D'), 'scene.maps_usage': ('mapsuse_max.py', 'D'),
        'light.check': ('light_max.py', 'D')}
STUB_FILES = ('place_core.py', 'place_max.py', 'texqa_core.py', 'texqa_max.py', 'finish_core.py', 'finish_max.py',
              'uvtile_core.py', 'uvtile_max.py', 'flora_atlas_max.py', 'qa9_core.py', 'qa9_max.py', 'facade_core.py',
              'facade_max.py', 'batch_core.py', 'batch_max.py', 'mapsuse_core.py', 'mapsuse_max.py',
              'light_core.py', 'light_max.py')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_090')
m = _load(PKG / 'ui_model.py', 'agr_tools_ui_model_090')
rm = _load(PKG / 'roadmap.py', 'agr_tools_roadmap_090')
icons = _load(ROOT / 'tools/max/agr_icons.py', 'agr_icons_090')
builder = _load(ROOT / 'tools/max/build_agr_tools.py', 'agr_builder_090')
xc = _load(PKG / 'export_core.py', 'agr_tools_export_090')
suite = json.loads(SUITE.read_text(encoding='utf-8'))
ROWS_090 = {r['id']: r for r in suite['rows'] if r['version'] == '0.9'}
ORDER_090 = next(v['rows'] for v in suite['versions'] if v['version'] == '0.9')


def runtime():
    return _load(PKG / 'runtime.py', 'agr_runtime_090')


def _glue_functions(glue):
    tree = ast.parse((PKG / glue).read_text(encoding='utf-8'))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def _implemented(tool):
    rt = runtime()
    return rt.EDITS_090[tool][1] in _glue_functions(GLUE[tool][0])


# ---- registry ----------------------------------------------------------------------------------------------
def test_registry_is_the_19_rows_of_version_09():
    rt = runtime()
    assert len(ROWS_090) == 19 and list(rt.EDITS_090) == ORDER_090  # plan order
    for tool, (core, fn) in rt.EDITS_090.items():
        assert fn == tool.replace('.', '_') and core.endswith('_core.py') and (PKG / core).is_file(), tool
        glue = rt.glue_file(core, rt.GLUE_090)
        assert glue == GLUE[tool][0] and (PKG / glue).is_file(), tool
    assert not set(rt.EDITS_090) & set(rt.EDITS_080)
    assert rt.GLUE_090 == {'atlas_core.py': 'flora_atlas_max.py'}


def test_read_090_and_select_090_are_the_plan_modes():
    rt = runtime()
    assert set(rt.READ_090) == {t for t, r in ROWS_090.items() if r['mode'] in ('read', 'select')}
    assert len(rt.READ_090) == 10
    assert rt.SELECT_090 == tuple(t for t, r in ROWS_090.items() if r['mode'] == 'select') == ('light.check',)
    editing = set(rt.EDITS_090) - set(rt.READ_090)
    assert {ROWS_090[t]['mode'] for t in editing} == {'copy', 'undo', 'file'}


def test_stub_modules_are_docstrings_and_load_without_pymxs():
    for name in STUB_FILES:
        src = (PKG / name).read_text(encoding='utf-8')
        tree = ast.parse(src)
        owner = {GLUE[t][1] for t in GLUE if GLUE[t][0] == name or name.replace('_core', '_max') == GLUE[t][0]}
        if not any(_implemented(t) for t in GLUE if GLUE[t][0] in (name, name.replace('_core', '_max'))):
            assert len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr), name  # docstring only
            assert '#979' in src and any('branch ' + o in src for o in owner), name
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert not any('pymxs' in ast.dump(n) for n in top), name


def test_data_files_have_an_owner_and_ship_in_the_package():
    data = json.loads((PKG / 'data/procedural_classes.json').read_text(encoding='utf-8'))
    assert data['owner'] == 'C' and data['issue'] == '#979' and isinstance(data['classes'], list)
    prov = (PKG / 'data/streets/PROVENANCE.md').read_text(encoding='utf-8')
    assert 'Владелец: ветка **C**' in prov
    files = builder.data_files()
    assert {'data/procedural_classes.json', 'data/streets/PROVENANCE.md'} <= set(files)
    assert all(f.count('/') <= 2 for f in files)


def test_data_files_refuse_deep_nesting(tmp_path):
    (tmp_path / 'data/a/b').mkdir(parents=True)
    (tmp_path / 'data/a/b/x.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='deeper'):
        builder.data_files(tmp_path)


# ---- dispatcher --------------------------------------------------------------------------------------------
@pytest.mark.parametrize('tool', ORDER_090)
def test_every_stub_answers_not_implemented(tool):
    if _implemented(tool):
        pytest.skip(tool + ' is implemented; covered by its branch tests')
    rt = runtime()
    r = rt.edits_090(tool, 'preview')
    assert r == ec.not_implemented(tool, 'preview', '#979') and r['plan']['issue'] == '#979'
    assert rt.parse_report(json.dumps(r)) == r
    assert m.rows(r) == [m.Row(None, '—', tool, False, 'not_implemented', 'в работе (#979): модуль ещё пуст', ())]
    if tool not in rt.READ_090:
        assert rt.edits_090(tool, 'apply', _preview(tool)) == ec.not_implemented(tool, 'apply', '#979')


def _preview(tool, state=(1,)):
    return ec.report(tool, 'preview', objects=[ec.entry(5, 'Box')], done=['Box'], state_hash=ec.fingerprint(state))


def test_dispatcher_refusals():
    rt = runtime()
    p = _preview('place.replace')
    cases = [(('nope', 'preview'), 'unsupported edit tool'), (('model.triangulate', 'preview'), 'unsupported edit'),
             (('place.replace', 'commit'), 'mode'), (('place.replace', 'apply'), 'needs the preview'),
             (('light.check', 'apply', _preview('light.check')), 'read-only'),
             (('qa.normals', 'apply', _preview('qa.normals')), 'read-only'),
             (('place.replace', 'preview', p), 'takes no preview')]
    for args, word in cases:
        with pytest.raises(ValueError, match=word):
            rt.edits_090(*args)
    with pytest.raises(ValueError, match='options belong'):
        rt.edits_090('place.replace', 'apply', p, options={'a': 1})
    with pytest.raises(ValueError):
        rt.edits_090('place.replace', 'preview', options=['a'])
    with pytest.raises(rt._edit_core().StalePreview):
        rt.edits_090('place.replace', 'apply', _preview('place.schedule'))
    with pytest.raises(rt._edit_core().StalePreview):
        rt.edits_090('place.replace', 'apply', ec.not_implemented('place.replace', 'preview', '#979'))
    with pytest.raises(ValueError, match='issue'):
        ec.not_implemented('place.replace', 'preview', '979')
    assert ec.not_implemented('model.triangulate', 'preview')['plan']['issue'] == '#908'  # 0.8 default unchanged


def _fake_glue(rt, monkeypatch, glue_file, name, fn):
    real = rt._load_core
    glue = types.ModuleType('fake_' + glue_file)
    setattr(glue, name, fn)
    monkeypatch.setattr(rt, '_load_core', lambda f, mod: glue if f == glue_file else real(f, mod))


def test_preview_apply_round_trip_and_ctx(monkeypatch):
    rt = runtime()
    scene = {'state': [{'handle': 9, 'name': 'Bench', 'mesh': 'm1'}]}
    calls = []

    def place_replace(ctx, mode, nodes, preview):
        calls.append((mode, nodes, dict(ctx.options), ctx.core.__name__))
        if mode == 'preview':
            return ctx.edit.report('place.replace', 'preview', objects=[ctx.edit.entry(9, 'Bench')], done=['Bench'],
                                   state_hash=ctx.edit.fingerprint(scene['state']), extra={'options': ctx.options})
        ctx.edit.require_current(preview, scene['state'])
        return ctx.edit.report('place.replace', 'apply', objects=[ctx.edit.entry(9, 'Bench')], done=['Bench'])
    _fake_glue(rt, monkeypatch, 'place_max.py', 'place_replace', place_replace)
    p = rt.edits_090('place.replace', 'preview', options={'mask': 'SM_*'})
    assert p['plan']['options'] == {'mask': 'SM_*'} and calls[0][3] == 'agr_tools_place_core'
    assert rt.edits_090('place.replace', 'apply', p)['plan']['mode'] == 'apply'
    scene['state'][0]['mesh'] = 'm2'
    with pytest.raises(rt._edit_core().StalePreview, match='scene changed'):
        rt.edits_090('place.replace', 'apply', p)


def test_atlas_rows_use_the_flora_atlas_glue(monkeypatch):
    rt = runtime()
    seen = []

    def atlas_groundel(ctx, mode, nodes, preview):
        seen.append(ctx.core.__name__)
        return ctx.edit.report('atlas.groundel', 'preview', done=['x'], state_hash='h')
    _fake_glue(rt, monkeypatch, 'flora_atlas_max.py', 'atlas_groundel', atlas_groundel)
    assert rt.edits_090('atlas.groundel', 'preview')['status'] == 'pass' and seen == ['agr_tools_atlas_core']


def test_dispatcher_rejects_glue_answers_for_another_tool_or_mode(monkeypatch):
    rt = runtime()
    _fake_glue(rt, monkeypatch, 'qa9_max.py', 'qa_normals',
               lambda ctx, mode, nodes, preview: ctx.edit.report('qa.sintez', 'preview', state_hash='h'))
    with pytest.raises(ValueError, match='another tool/mode'):
        rt.edits_090('qa.normals', 'preview')
    _fake_glue(rt, monkeypatch, 'qa9_max.py', 'qa_normals', lambda ctx, mode, nodes, preview: {'status': 'pass'})
    with pytest.raises(ValueError, match='incomplete'):
        rt.edits_090('qa.normals', 'preview')


def test_select_row_selects_offenders_in_the_ui_glue_not_in_the_core(monkeypatch):
    rt = runtime()
    report = ec.report('light.check', 'preview', state_hash='h', objects=[
        ec.entry(11, 'Omni_far', [ec.finding('omni_distance', detail='3.2 m < 5 m')]), ec.entry(12, 'Spot_ok')])
    _fake_glue(rt, monkeypatch, 'light_max.py', 'light_check', lambda ctx, mode, nodes, preview: report)
    monkeypatch.setattr(rt, '_selection_key', lambda: (1,))
    picked = []
    monkeypatch.setattr(rt, 'select_offenders', lambda r: picked.append(rt.offender_handles(r)))
    assert rt.edit_ui('light.check') == report and picked == [[11]]
    assert rt.edit_ui('light.check') == report and picked == [[11], [11]]  # read row: always a preview, no apply
    assert 'light.check' not in rt._edits
    assert rt.edit_ui('light.check', select=False) == report and len(picked) == 2  # the panel selects itself
    src = (PKG / 'runtime.py').read_text(encoding='utf-8')
    body = src[src.index('def select_offenders'):src.index('\ndef ', src.index('def select_offenders') + 1)]
    assert 'pymxs.undo(True' in body and 'getAnimByHandle' in body  # one undo record; report handles are anims


def test_fake_pymxs_select_offenders_is_one_undo_record(monkeypatch):
    rt = runtime()
    log = []

    class Undo:
        def __init__(self, on, label):
            log.append(('undo', on, label))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            log.append(('end',))
            return False
    nodes = {11: 'omni', 12: 'spot'}
    fake_rt = types.SimpleNamespace(getAnimByHandle=nodes.get, isValidNode=lambda n: n is not None,
                                    select=lambda ns: log.append(('select', list(ns))))
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(undo=Undo, runtime=fake_rt))
    monkeypatch.setattr(rt, '_rt', lambda: fake_rt)
    r = {'objects': [{'handle': 11, 'findings': [1]}, {'handle': 12, 'findings': []}, {'handle': 99, 'findings': [1]}]}
    assert rt.select_offenders(r) == 1
    assert log == [('undo', True, 'AGR Tools: выделить нарушителей'), ('select', ['omni']), ('end',)]
    log.clear()
    assert rt.select_offenders({'objects': [{'handle': 12, 'findings': []}]}) == 0 and log == []  # selection kept


def test_ui_routes_every_090_tool_to_edit_ui():
    src = (PKG / 'runtime.py').read_text(encoding='utf-8')
    assert "elif tool in EDITS_080 or tool in EDITS_090:\n        report = edit_ui(tool)" in src


# ---- panel backend (fake pymxs, as test_agr_tools_ui_backend.py) ------------------------------------------
class _Node:
    def __init__(self, handle):
        self.handle, self.valid = handle, True


class _Rt:
    def __init__(self, nodes, geometry):
        self.objects, self.geometry, self.selection = list(nodes), list(geometry), []

    def select(self, x):
        self.selection = list(x) if isinstance(x, (list, tuple)) else [x]

    def clearSelection(self):
        self.selection = []

    def isValidNode(self, n):
        return n is not None and n.valid


@pytest.fixture
def backend(monkeypatch):
    model = _load(PKG / 'ui_model.py', 'agr_tools_ui_model')
    monkeypatch.setitem(sys.modules, 'agr_tools_ui_model', model)
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=None))
    qt = types.ModuleType('agr_tools_ui_qt')
    qt.QtGui = qt.QtWidgets = None
    qt.max_icon = qt.max_main_window = lambda *a: None
    monkeypatch.setitem(sys.modules, 'agr_tools_ui_qt', qt)
    mod = _load(PKG / 'ui_max.py', 'agr_tools_ui_max_090')

    def make(nodes, geometry):
        rt = _Rt(nodes, geometry)
        mod.rt = rt
        log = []
        report = {'tool': 'light.check', 'status': 'fail', 'objects': [{'handle': 2, 'findings': [{'code': 'x'}]}]}

        def edit_ui(tool, select=True):
            log.append(('edit_ui', tool, select, list(rt.selection)))
            return dict(report, tool=tool)
        agr = types.SimpleNamespace(CHECKS_070=(), EDITS_080={}, EDITS_090={'light.check': 1, 'place.replace': 1},
                                    SELECT_090=('light.check',), edit_ui=edit_ui, remember=lambda r: None,
                                    select_offenders=lambda r: log.append(('select_offenders', list(rt.selection))))
        be = mod.MaxBackend(agr, '')
        be.log = lambda r: None
        return be, rt, log
    return make


def test_backend_scope_all_selects_offenders_after_restoring_the_user_selection(backend):
    a, b, light = _Node(1), _Node(2), _Node(3)
    be, rt, log = backend([a, b, light], geometry=[a, b])
    rt.selection = [a]
    be.run_tool('light.check', True)
    assert log[0] == ('edit_ui', 'light.check', False, [a, b, light])  # 0.9 rows see every object (lights)
    assert log[1] == ('select_offenders', [a]) and rt.selection == [a]  # Ctrl+Z goes back to the user's [a]
    log.clear()
    be.run_tool('light.check', False)
    assert log == [('edit_ui', 'light.check', False, [a]), ('select_offenders', [a])]
    log.clear()
    be.run_tool('place.replace', False)  # not a select row: nothing selected by the backend
    assert [x[0] for x in log] == ['edit_ui']


# ---- UI: actions, sections, macros, menu, icons ------------------------------------------------------------
def test_each_09_row_has_one_action_in_the_section_of_its_mode():
    acts = [a for a in m.ACTIONS if a.tool in ROWS_090]
    assert [a.tool for a in acts] == ORDER_090 and len(acts) == 19
    assert m.SECTIONS[6:] == ('Проверить и выделить', 'Исправить — копии / undo / новые файлы')
    mcr, menu = m.macros_ms(), m.menu_ms()
    for a in acts:
        r = ROWS_090[a.tool]
        assert a.section == (6 if r['mode'] in ('read', 'select') else 7), a.tool
        assert m.row_of(a.id) == a.tool and a.icon == r['icon'] and a.icon in icons.names(), a.tool
        assert ' '.join(a.reqs) == r['reqs'] and a.macro.startswith('AGRTools') and not a.batch, a.tool
        assert a.label and a.tip and ('только чтение' in a.tip) == (r['mode'] in ('read', 'select')), a.tool
        assert 'macroScript {} category:"AGR Tools"'.format(a.macro) in mcr
        assert "agr_tools_runtime.ui('{}')".format(a.tool) in mcr and '"{}`AGR Tools"'.format(a.macro) in menu
        assert icons.svg(a.icon, '#000000').startswith('<svg') and 'currentColor' not in icons.svg(a.icon, '#000')
    assert len({a.macro for a in m.ACTIONS}) == len({a.id for a in m.ACTIONS}) == len(m.ACTIONS) == 61
    assert sorted(r['icon'] for r in ROWS_090.values()) == sorted(
        ['ermn', 'finish', 'mafuv', 'slots', 'flora', 'groundel', 'florafix', 'mafcheck', 'replace', 'schedule',
         'ground', 'address', 'compare', 'normals', 'sintez', 'batch', 'mapsuse', 'lightcheck', 'procobj'])


def test_committed_macro_and_menu_files_are_generated():
    for name, text in (('agr_tools.mcr', m.macros_ms()), ('menu.ms', m.menu_ms())):
        raw = (PKG / name).read_bytes().replace(b'\r\n', b'\n')
        assert raw == b'\xef\xbb\xbf' + text.encode('utf-8'), name


def test_icons_are_new_and_distinct():
    bodies = {n: icons.icon_body(n) for n in icons.names()}
    for name in (r['icon'] for r in ROWS_090.values()):
        assert sum(1 for b in bodies.values() if b == bodies[name]) == 1, name
        assert re.fullmatch(r'[a-z]+', name)
    assert len(icons.names()) == 100  # +32 icons of the 1.0 rows (#1024 branch 0)


def test_rail_shows_09_actions_from_version_090_and_greys_them_before():
    rail08 = m.rail(suite['blocks'], suite['rows'], '0.8.1')  # what the branches A-E3 shipped on
    done = {m.row_of(a.id) for _, d, _ in rail08 for a in d}
    assert not done & set(ROWS_090)
    assert m.VERSION == runtime().VERSION == '0.9.0'  # release branch R (#979)
    rail = m.rail(suite['blocks'], suite['rows'])
    assert set(ROWS_090) <= {m.row_of(a.id) for _, d, _ in rail for a in d}
    assert all(rm.shipped(r['version'], m.VERSION) for r in ROWS_090.values())


def test_section_accents_stay_distinct_and_away_from_status_hues():
    import colorsys
    for base, text in (((43, 43, 43), (220, 220, 220)), ((240, 240, 240), (20, 20, 20))):
        secs = [m.section_accent(i, base, text) for i in range(len(m.SECTIONS))]
        assert len(set(secs)) == len(m.SECTIONS) == len(m.SECTION_HUES) == 8
        for c in secs:
            assert m.contrast(c, base) >= 3.0
            h = colorsys.rgb_to_hls(*(v / 255 for v in c))[0] * 360
            assert min(m.hue_gap(h, s) for s in m.STATUS_HUES_DEG) >= 25


# ---- builder ---------------------------------------------------------------------------------------------
def test_builder_ships_every_stub_and_install_requires_them():
    assert set(STUB_FILES) <= set(builder.FILES) and len(builder.FILES) == len(set(builder.FILES))
    install = (PKG / 'install.ms').read_text(encoding='utf-8-sig')
    for name in STUB_FILES:
        assert '"{}"'.format(name) in install
    assert 'agr_tools/data/' in install and 'getDirectories (dataSrc + "*")' in install
    assert 'if icons.count < {} do'.format(len(icons.names()) * len(icons.SIZES)) in install


# ---- cleanup options -------------------------------------------------------------------------------------
def test_cleanup_options_are_opt_in_and_validated():
    assert xc.CLEANUP_OPTIONS == ('channels', 'keys')
    assert xc.cleanup_options() == xc.cleanup_options({}) == {'channels': False, 'keys': False}
    assert xc.cleanup_options({'keys': True}) == {'channels': False, 'keys': True}
    for bad in ([], 'x', {'delete': True}, {'channels': 1}, {'keys': None}):
        with pytest.raises(ValueError):
            xc.cleanup_options(bad)
    actions = [{'action': 'delete_map_channels', 'channels': [2, 3]}, {'action': 'clear_user_defined_lines'}]
    assert xc._cleanup_channels(actions) == xc._cleanup_channels(actions, {'channels': True, 'keys': True}) == [2, 3]
    with pytest.raises(ValueError):
        xc._cleanup_channels(actions, {'nope': True})


def test_runtime_cleanup_passes_options_from_preview_to_apply():
    src = (PKG / 'runtime.py').read_text(encoding='utf-8')
    assert 'def cleanup_preview(nodes=None, options=None):' in src
    assert "opts = export.cleanup_options(options)" in src
    assert "export._cleanup_channels(item['actions'], opts)" in src
    assert "current = cleanup_preview(nodes, preview.get('options'))" in src
    assert "after = cleanup_preview(copies, current['options'])['report']" in src


# ---- MCP -----------------------------------------------------------------------------------------------
def test_mcp_has_19_preview_only_tools():
    sys.path.insert(0, str(ROOT / 'src'))
    try:
        from agr_mcp import tools
        bridge = _load(ROOT / 'src/agr_mcp/max_side/max_bridge.py', 'agr_max_bridge_090')
    finally:
        sys.path.pop(0)
    assert [row for _, row, _, _ in tools.EDITS_090] == ORDER_090
    for name, row, _, mode in tools.EDITS_090:
        block, rest = row.split('.')
        assert name == 'agr_{}_{}'.format(block, rest) and bridge.EDITS_090[name] == row
        assert mode == ROWS_090[row]['mode']
    assert set(bridge.EDITS_090) == {n for n, *_ in tools.EDITS_090} and set(bridge.EDITS_090) <= set(tools.PHASE0)
    assert bridge.RUNTIME_090 == runtime().VERSION
    cat = tools.catalog()
    for name, *_ in tools.EDITS_090:
        spec = cat[name]
        assert spec.read_only and not spec.destructive
        jsonschema.validate({'scene': 'live'}, spec.input)
        jsonschema.validate({'scene': 'live', 'mode': 'preview', 'handles': [3], 'options': {'a': 1}}, spec.input)
        for bad in ({'scene': 'live', 'mode': 'apply'}, {'scene': 'live', 'preview': {}}, {'mode': 'preview'},
                    {'scene': 'live', 'code': '1'}):
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(bad, spec.input)
        jsonschema.validate(ec.not_implemented(ROWS_090[spec.name.split('_', 1)[1].replace('_', '.', 1)]['id'],
                                               'preview', '#979'), spec.result)
    with pytest.raises(ValueError, match='only mode=preview'):
        bridge.run('agr_place_replace', '', {'scene': 'live', 'mode': 'apply', 'preview': {}})


# ---- changelog ---------------------------------------------------------------------------------------------
def test_changelog_has_one_released_09_section_naming_all_19_rows():
    """Release branch R (#979): the branch subsections (0, A-D, E1-E3) are merged into one `0.9.0 (#979)` section."""
    text = (PKG / 'CHANGELOG.md').read_text(encoding='utf-8')
    # 1.0 (#1024): the section '## 1.0.0 (#1024) — в работе' sits above; the released 0.9.0 section stays clean
    assert 'в работе' not in text[text.index('## 0.9.0 (#979)'):text.index('## 0.8.1')] and text.count('## 0.9.0') == 1
    head = text[text.index('## 0.9.0 (#979)\n'):text.index('## 0.8.1')]
    assert not re.search(r'^### (?:[ABCD]|E[123]) ', head, re.M) and '(ветка 0)' not in head
    subs = re.split(r'^### ', head, flags=re.M)[1:]
    assert [s.splitlines()[0] for s in subs] == [
        'Контракт и регистрация', 'Замены и МАФ', 'Текстуры, UDIM, атласы', 'Проверки', 'Экспорт, карты, свет',
        'Доработки 0.8: текстуры и имена', 'Доработки 0.8: геометрия и UDIM', 'Доработки 0.1–0.8: пакет и предсдача',
        'Релиз']
    for s in subs:
        assert re.search(r'^- \S', s, re.M), s[:40]
    for rid in ROWS_090:
        assert '`{}`'.format(rid) in head, rid
    assert 'пока пишет PNG через Max' not in head  # atlas.npm moved to the npm profile in R


# ---- polygon: bases 0.8 / 0.9 and the station fragments ---------------------------------------------------
def _poly():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import test_polygon_support as support
    return sys.modules['agr_polygon_core'], support


def test_polygon_has_32_new_stations_each_with_expected_and_reason():
    core, support = _poly()
    # #1024 branch 0: base 1.0 follows 0.9 and the tour ends there
    assert core.TOUR_LAST == '1.0' and [b['version'] for b in core.bases()][-3:] == ['0.8', '0.9', '1.0']
    new = [s for s in core.stations() if s['version'] in ('0.8', '0.9')]
    assert len(new) == 32
    assert [s['id'] for s in new] == ['0.8.{}'.format(i) for i in range(1, 14)] + [
        '0.9.{}'.format(i) for i in range(1, 20)]
    assert set(core.OWNER) == {s['button'] for s in new} and set(core.OWNER.values()) == set(core.BRANCHES)
    for s in new:
        doc = support.load_expected(s['button'])
        assert doc['station'] == s['id'] and doc['base'] == s['version'] and s['branch'] == core.OWNER[s['button']]
        passes = [o for o in doc['objects'] if o['expect'] == 'pass']
        fails = [o for o in doc['objects'] if o['expect'] == 'fail']
        if not (passes and fails):
            # stations/README.md: at least one PASS and one FAIL, else a non-empty reason. A station a branch has
            # not filled keeps the base text; a filled fragment station may give its own reason (#979).
            frag = core.load_fragments().get(s['button'])
            if frag and frag['expected']:
                assert doc['reason'].strip(), s['button']
            else:
                assert doc['reason'] == 'станция в работе, #979, ветка ' + core.OWNER[s['button']], s['button']
    cat = support.load_catalog()
    labels = {o['name'] for o in cat['objects'] if o['name'].startswith('_label_0_8_') or
              o['name'].startswith('_label_0_9_')}
    assert labels == {'_label_' + s['id'].replace('.', '_') for s in new}
    names = {o['name'] for o in cat['objects']}
    assert {'_base_0_8', '_base_0_9', '_cam_База 0.8', '_cam_База 0.9'} <= names


def _fragment(**station):
    st = {'button': 'place.replace', 'objects': [
        {'name': 'SM_Frag_Ok_Main', 'role': 'Main', 'mat_name': 'M_Polygon_001_Main_1'},
        {'name': 'SM_Frag_Bad_Main', 'role': 'Main', 'size': [1, 1, 1], 'extra': {'reference': 'SM_Bench'}}],
          'expected': [{'name': 'SM_Frag_Ok_Main', 'scene': 'polygon_all', 'expect': 'pass', 'codes': []},
                       {'name': 'SM_Frag_Bad_Main', 'scene': 'polygon_all', 'expect': 'fail',
                        'codes': ['no_reference']}]}
    st.update(station)
    return {'schema': 1, 'branch': 'A', 'issue': '#979', 'stations': [st]}


def test_station_fragment_hook_adds_objects_without_touching_older_buttons(tmp_path, monkeypatch):
    core, support = _poly()
    empty = tmp_path / 'none'
    empty.mkdir()
    monkeypatch.setattr(core, 'STATIONS_DIR', empty)  # the committed branch fragments stay out of this test
    before = core.predict_all()
    (tmp_path / 'A.json').write_text(json.dumps(_fragment(), ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(core, 'STATIONS_DIR', tmp_path)
    docs = core.predict_all()
    for button, doc in docs.items():
        if button != 'place.replace':
            assert doc == before[button], button  # 0.1-0.7 predictions never see a fragment object
    doc = docs['place.replace']
    assert doc['shipped'] is True and doc['tool'] == 'place.replace' and doc['reason'] == ''
    assert [o['expect'] for o in doc['objects']] == ['pass', 'fail'] and doc['station'] == '0.9.9'
    cat = core.load_catalog(docs)
    frag = {o['name']: o for o in cat['objects'] if o.get('fragment') == 'A'}
    assert set(frag) == {'SM_Frag_Ok_Main', 'SM_Frag_Bad_Main'}
    assert all(o['station'] == '0.9.9' and o['base'] == '0.9' and o['layer'] == '0' for o in frag.values())
    assert frag['SM_Frag_Bad_Main']['extra'] == {'reference': 'SM_Bench'}
    assert 'place.replace=no_reference' in frag['SM_Frag_Bad_Main']['AGR_TEST']
    rect = next(o for o in cat['objects'] if o['name'] == '_base_0_9')
    for o in frag.values():
        assert abs(o['pos'][0] - rect['pos'][0]) <= rect['size'][0] / 2 and \
            abs(o['pos'][1] - rect['pos'][1]) <= rect['size'][1] / 2
    committed = json.loads((core.POLY / 'catalog.json').read_text(encoding='utf-8'))
    assert [o for o in committed['objects'] if not core.fragment_part(o)] == \
        [o for o in cat['objects'] if not core.fragment_part(o)]  # bases 0.1-0.7 unchanged


@pytest.mark.parametrize('mutate,word', [
    (lambda d: d['stations'][0].update(button='qa.normals'), 'not owned'),
    (lambda d: d.update(branch='B'), 'branch A'),
    (lambda d: d['stations'][0]['objects'][0].update(name='SM_Polygon_001_Main'), 'collides'),
    (lambda d: d['stations'][0]['objects'][0].update(scene='frag_b_x'), 'scene'),
    (lambda d: d['stations'][0]['objects'][0].update(wat=1), 'object keys'),
    (lambda d: d['stations'][0].update(homes=['SM_Frag_Ok_Main']), 'every polygon_all object'),
    (lambda d: d['stations'][0]['expected'][0].update(expect='ok'), 'expected row'),
    (lambda d: d['stations'][0]['objects'][0].update(builder='B_build'), 'builder'),
    (lambda d: d['stations'].append(copy.deepcopy(d['stations'][0])), 'duplicate'),
])
def test_station_fragment_is_validated(tmp_path, monkeypatch, mutate, word):
    core, _ = _poly()
    doc = _fragment()
    mutate(doc)
    (tmp_path / 'A.json').write_text(json.dumps(doc), encoding='utf-8')
    monkeypatch.setattr(core, 'STATIONS_DIR', tmp_path)
    with pytest.raises(RuntimeError, match=word):
        core.load_catalog()


def test_unknown_fragment_file_and_branch_writer(tmp_path, monkeypatch):
    core, _ = _poly()
    (tmp_path / 'Z.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(core, 'STATIONS_DIR', tmp_path)
    with pytest.raises(RuntimeError, match='unknown station fragment'):
        core.load_fragments()
    (tmp_path / 'Z.json').unlink()
    (tmp_path / 'A.json').write_text(json.dumps(_fragment()), encoding='utf-8')
    out = tmp_path / 'expected'
    out.mkdir()
    monkeypatch.setattr(core, 'EXPECTED', out)
    assert core.write_branch('A') == sorted(b for b, o in core.OWNER.items() if o == 'A')
    assert sorted(p.stem for p in out.glob('*.json')) == sorted(b for b, o in core.OWNER.items() if o == 'A')
    assert json.loads((out / 'place.replace.json').read_text(encoding='utf-8'))['shipped'] is True
    with pytest.raises(SystemExit):
        core.write_branch('Z')  # Q is a branch of #1024 since branch 0 of 1.0


def test_committed_fragments_are_branch_fragments():
    core, _ = _poly()  # branches A-E3 of #979 and F-U of #1024 commit stations/<branch>.json (+ <branch>_build.py)
    assert {p.stem for p in core.STATIONS_DIR.glob('*.json')} <= set(core.ALL_BRANCHES)
    assert (core.STATIONS_DIR / 'README.md').is_file()


# ---- roadmap.load: 8 of 8 broken plans are rejected (SYNTHESIS §4, T09 R3) ---------------------------------
def _mutations():
    def first(d, **kw):
        d['rows'][0].update(kw)

    def units_line(d):
        r = next(r for r in d['rows'] if r['id'] == 'scene.units')
        r['source'] = r['source'].replace('GeoAGR.ms:12547', 'GeoAGR.ms:12000')
    return [
        ('verdict typo', lambda d: first(d, verdict='tak'), 'verdict'),
        ('priority P4', lambda d: first(d, priority='P4'), 'priority'),
        ('mcp maybe', lambda d: first(d, mcp='maybe'), 'mcp'),
        ('id prefix != block', lambda d: first(d, id='model.units_x'), 'prefix'),
        ('unknown requirement', lambda d: first(d, reqs='NPM-9.9-9'), 'requirement'),
        ('version not in roadmap', lambda d: first(d, version='0.65'), 'versions'),
        ('empty does_ru', lambda d: first(d, does_ru=''), 'empty does_ru'),
        ('wrong GeoAGR line', units_line, 'GeoAGR.ms:12000'),
    ]


def test_roadmap_load_accepts_the_plan():
    assert len(rm.load(SUITE.read_text(encoding='utf-8'))['rows']) == len(suite['rows'])


@pytest.mark.parametrize('name,mutate,word', _mutations(), ids=[x[0] for x in _mutations()])
def test_roadmap_load_rejects_each_of_8_broken_plans(name, mutate, word):
    d = copy.deepcopy(suite)
    mutate(d)
    with pytest.raises(ValueError, match=re.escape(word)):
        rm.load(json.dumps(d, ensure_ascii=False))


def test_roadmap_load_more_gaps():
    for mutate, word in (
            (lambda d: d.pop('versions'), 'versions missing'),
            (lambda d: d['versions'][-1]['rows'].append('qa.ghost'), 'do not exist'),
            (lambda d: d['versions'][-1]['rows'].remove(d['versions'][-1]['rows'][0]), 'missing from versions'),
            (lambda d: d['rows'][0].update(source=d['rows'][0]['source'] + '; btn_new_one GeoAGR.ms:5'), 'btn_new_one'),
            (lambda d: d['rows'][0].update(reqs='NPM-2.1-1.b,VPM-2.4-2'), 'malformed'),
            (lambda d: d['rows'][0].update(icon=' '), 'empty icon')):
        d = copy.deepcopy(suite)
        mutate(d)
        with pytest.raises(ValueError, match=word):
            rm.load(json.dumps(d, ensure_ascii=False))
    reqs = {q for r in suite['rows'] for q in r['reqs'].split() if q != '-'}
    rm.load(SUITE.read_text(encoding='utf-8'), requirements=reqs)
    with pytest.raises(ValueError, match='unknown requirement'):
        rm.load(SUITE.read_text(encoding='utf-8'), requirements=reqs - {'VPM-2.15-2'})


def test_roadmap_checks_the_short_geoagr_citation_form_and_pins_every_cited_button():
    """Release R (#979): `btn_x :123` after a GeoAGR.ms citation was not checked at all (RED on 0.8.x: a wrong line
    or an unpinned button passed). Every button the plan cites, in either form, is pinned."""
    cited = {n for r in suite['rows'] for n, _ in rm.GEOAGR_CITE_RE.findall(r['source'])}
    assert cited == set(rm.GEOAGR_BUTTONS)
    for rid, old, new, word in (('scene.units', 'btn_set_alpha :12554', 'btn_set_alpha :12555', '12555'),
                                ('qa.address', 'btn_Streets_List :42460', 'btn_Streets_Lst :42460', 'btn_Streets_Lst'),
                                ('qa.normals', 'btn_View_Normals GeoAGR.ms:47595', 'btn_View_Normals GeoAGR.ms:47594',
                                 '47594')):
        d = copy.deepcopy(suite)
        r = next(x for x in d['rows'] if x['id'] == rid)
        assert old in r['source'], rid
        r['source'] = r['source'].replace(old, new)
        with pytest.raises(ValueError, match=word):
            rm.load(json.dumps(d, ensure_ascii=False))


@pytest.mark.skipif(not GEOAGR_MS.is_file(), reason='GeoAGR-private GeoAGR.ms is not on this machine')
def test_pinned_geoagr_citations_match_geoagr_ms():
    lines = GEOAGR_MS.read_text(encoding='utf-8', errors='replace').splitlines()
    for name, line in rm.GEOAGR_BUTTONS.items():
        assert name in lines[line - 1], (name, line)
