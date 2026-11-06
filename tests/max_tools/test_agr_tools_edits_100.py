"""new-case: AGR Tools 1.0 base (#1024, branch 0): plan stages, EDITS_100 registry/dispatcher, stub modules and their
cross-branch signatures, contract_core (roles, markers, ObjRef), K1/K4 schemas, the journal hook, UI/macro/icon
wiring of the 33 wip buttons and the polygon base 1.0.

Plain pytest, no pymxs: the stub modules of branches F..U are empty, so every 1.0 tool answers not_implemented.
Once a branch fills its glue function, that tool's stub checks skip and the branch's own tests own the behaviour.
"""
import ast
import copy
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'
# SPLIT.md (#1024, redaction 2): owner branch of every 1.0 button
OWNER = {'project.passport': 'F', 'source.intake': 'F', 'scene.source_class': 'F', 'scene.small_parts': 'F',
         'body.prepare': 'G', 'model.attach_by_material': 'G', 'model.move_apart': 'G',
         'model.grid_cleanup': 'H', 'model.glass_planes': 'H', 'win.generate': 'J', 'win.place': 'J',
         'body.capsules': 'K', 'body.roof': 'K', 'mat.table': 'L', 'mat.tiles': 'L', 'tex.plug_colour': 'L',
         'vpm.build': 'M', 'udim.rescale': 'M', 'udim.distortion': 'M', 'tex.dilate': 'N', 'udim.plugs': 'N',
         'npm.build': 'P', 'atlas.facade_strip': 'P', 'npm.to_vpm': 'Q', 'udim.udims_to_ids': 'Q',
         'pack.deliver': 'S', 'ucx.gap': 'S', 'light.export': 'S', 'ucx.stairs': 'T', 'qa.omk_te': 'T',
         'export.place_by_passport': 'T', 'agent.request': 'U', 'agent.accept': 'U'}
NEW_15 = ('project.passport', 'source.intake', 'body.prepare', 'win.place', 'win.generate', 'body.capsules',
          'body.roof', 'mat.table', 'mat.tiles', 'vpm.build', 'npm.build', 'npm.to_vpm', 'pack.deliver',
          'agent.request', 'agent.accept')
NEW_ICONS = ('passport', 'intake', 'body', 'winplace', 'wingen', 'capsule', 'roof', 'mattable', 'mattiles', 'vpm',
             'npm', 'npm2vpm', 'deliver', 'agentreq', 'agentok')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_100')
rm = _load(PKG / 'roadmap.py', 'agr_tools_roadmap_100')
cc = _load(PKG / 'contract_core.py', 'agr_tools_contract_core_100')
jc = _load(PKG / 'journal_core.py', 'agr_tools_journal_core_100')
TEXT = SUITE.read_text(encoding='utf-8')
suite = rm.load(TEXT)
ORDER = rm.stage_buttons(suite)
ROWS = {r['id']: r for r in suite['rows']}


def runtime():
    return _load(PKG / 'runtime.py', 'agr_runtime_100')


def _functions(name):
    tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def _implemented(rt, tool):
    core, fn = rt.EDITS_100[tool]
    return fn in _functions(rt.glue_file(core, rt.GLUE_100))


def _broken(mutate):
    s = json.loads(TEXT)
    mutate(s)
    return json.dumps(s, ensure_ascii=False)


# ---- plan --------------------------------------------------------------------------------------------------
def test_stages_cover_the_33_buttons_in_station_order():
    assert len(ORDER) == 33 and len(set(ORDER)) == 33 and set(ORDER) == set(OWNER)
    assert [s['id'] for s in suite['stages']] == list(range(10)) + ['agent']
    v10 = next(v for v in suite['versions'] if v['version'] == '1.0')
    assert v10['rows'] == ORDER and v10['status'] == 'done' and v10['issue'] == '#1024'
    assert sorted(v10['steps']) == ['atlas.unatlas', 'model.window_placer', 'tex.vpm_sets']
    # release 1.0.0 (#1024 R): branch Q (stage 8) was not merged; its rows and step are deferred to 1.1, and the
    # panel keeps exactly its two buttons wip
    deferred = {rid for rid, r in ROWS.items() if r.get('deferred')}
    assert deferred == set(v10['deferred']) == {'npm.to_vpm', 'udim.udims_to_ids', 'atlas.unatlas'}
    assert all(ROWS[rid]['deferred'] == '1.1' and ROWS[rid]['stage'] == 8 for rid in deferred)
    assert set(_load(PKG / 'ui_model.py', 'agr_tools_ui_model_100').WIP_100) == deferred & set(ORDER)
    for rid in ORDER:
        assert ROWS[rid]['version'] == '1.0' and ROWS[rid]['fate'] == 'stage' and ROWS[rid]['mcp'] == 'yes'
    for rid in NEW_15:
        assert ROWS[rid]['verdict'] == 'new' and ROWS[rid]['stage'] is not None
    assert {s['big_button'] for s in suite['stages']} <= set(NEW_15)


def test_layout_of_the_35_old_rows_follows_the_1024_table():
    fates = {r['id']: r['fate'] for r in suite['rows'] if r['fate']}
    assert sorted(k for k, v in fates.items() if v == 'obsolete') == ['tex.multimat', 'udim.unwrap_tiles',
                                                                       'udim.viewer']
    tail = sorted(k for k, v in fates.items() if v == 'tail')
    assert tail == sorted(['model.ground_border', 'model.ground_slice', 'model.ground_surface', 'ucx.ground',
                           'place.maf_generator', 'model.three_pt_align', 'tex.browser', 'place.scatter',
                           'place.tree_cards', 'light.place', 'model.pipe_lo', 'export.library_zip',
                           'qa.names_library'])
    assert {ROWS[k]['step_of'] for k in ('model.window_placer', 'tex.vpm_sets', 'atlas.unatlas')} == \
        {'win.place', 'vpm.build', 'npm.to_vpm'}
    old = {r['id'] for r in suite['rows'] if r['fate']} - set(NEW_15) - {'export.library_zip', 'qa.names_library'}
    assert len(old) == 35  # the 35 rows of 1.0 / 1.x before #1024: 18 stage + 3 step + 11 tail + 3 obsolete
    for r in suite['rows']:
        if r['version'] not in ('1.0', '1.x'):
            assert r['stage'] is None and r['fate'] is None, r['id']


@pytest.mark.parametrize('mutate,word', [
    (lambda s: s.pop('stages'), 'stages'),
    (lambda s: s['stages'].reverse(), 'stages'),
    (lambda s: s['rows'][0].pop('fate'), 'stage/fate'),
    (lambda s: [r.update(stage=11) for r in s['rows'] if r['id'] == 'ucx.gap'], 'unknown stage'),
    (lambda s: [r.update(fate='later') for r in s['rows'] if r['id'] == 'ucx.gap'], 'unknown fate'),
    (lambda s: [r.update(fate='tail') for r in s['rows'] if r['id'] == 'ucx.gap'], 'does not fit'),
    (lambda s: [r.update(stage=3, fate='stage') for r in s['rows'] if r['id'] == 'qa.xview'], 'needs version 1.0'),
    (lambda s: [r.update(mode='agent') for r in s['rows'] if r['id'] == 'ucx.gap'], 'mode agent'),
    (lambda s: [r.pop('step_of') for r in s['rows'] if r['id'] == 'tex.vpm_sets'], 'step_of'),
    (lambda s: s['stages'][9]['rows'].remove('ucx.gap'), 'cover'),
    (lambda s: s['stages'][9].update(big_button='qa.xview'), 'big button'),
    (lambda s: s['stages'][9]['checks'].append('vpm.build'), 'released row'),
    (lambda s: [r.update(stage=None, fate=None) for r in s['rows'] if r['id'] == 'project.passport'],
     'prefix|no fate|cover'),
    (lambda s: next(v for v in s['versions'] if v['version'] == '1.0')['rows'].reverse(), 'versions\\[1.0\\]'),
])
def test_roadmap_rejects_broken_stages(mutate, word):
    with pytest.raises(ValueError, match=word):
        rm.load(_broken(mutate))


def test_block_pages_stay_without_the_stage_only_rows():
    for b in suite['blocks']:
        ids = [r['id'] for r in rm.block_rows(suite, b['id'])]
        assert all(i.partition('.')[0] == b['id'] for i in ids), b['id']
    assert not any(i.startswith(p + '.') for p in rm.STAGE_PREFIXES
                   for b in suite['blocks'] for i in [r['id'] for r in rm.block_rows(suite, b['id'])])


def test_geoagr_lines_of_1024_are_pinned_and_checked_when_the_source_is_here():
    src = Path('C:/agr/GeoAGR-private/versions/13.64/GeoAGR.ms')
    assert {56719, 56942, 57117, 45538, 5236, 20050, 31390, 31473, 33785} <= set(rm.GEOAGR_LINES_1024)
    if not src.is_file():
        pytest.skip('GeoAGR-private not on this machine')
    lines = src.read_bytes().decode('cp1251', 'replace').splitlines()
    for name, line in rm.GEOAGR_BUTTONS.items():
        assert 'on ' + name + ' ' in lines[line - 1] and ('pressed' in lines[line - 1] or
                                                          'rightclick' in lines[line - 1]), (name, line)
    probes = {56719: 'getPolyBorders', 56942: 'getBorderAlignmentData', 20050: 'fit_all_to_udim',
              31390: 'wrap_island_to_first_udim', 31473: 'process_and_align_island_universal',
              33785: 'clearUndoBuffer', 16071: 'uvDistortionViewer', 57117: 'bestWin', 45538: 'random'}
    for line, word in probes.items():
        assert word in lines[line - 1], (line, word)


# ---- registry and dispatcher ------------------------------------------------------------------------------
def test_registry_is_the_33_buttons_with_one_glue_each():
    rt = runtime()
    assert list(rt.EDITS_100) == ORDER
    assert set(rt.READ_100) == {k for k in ORDER if ROWS[k]['mode'] in ('read', 'select')}
    assert set(rt.AGENT_100) == {k for k in ORDER if ROWS[k]['mode'] == 'agent'}
    builder = _load(ROOT / 'tools/max/build_agr_tools.py', 'agr_builder_100')
    for tool, (core, fn) in rt.EDITS_100.items():
        glue = rt.glue_file(core, rt.GLUE_100)
        assert core in builder.FILES and glue in builder.FILES, tool
        assert (PKG / core).is_file() and (PKG / glue).is_file(), tool
        assert fn == tool.replace('.', '_'), tool
    for name in ('contract_core.py', 'journal_core.py', 'host_max.py', 'openings_core.py', 'uvlayout_core.py',
                 'vpmmaps_core.py'):
        assert name in builder.FILES
    install = (PKG / 'install.ms').read_text(encoding='utf-8-sig')
    for name in builder.FILES:
        if name.endswith('.py'):
            assert '"{}"'.format(name) in install, name


def test_stub_docstrings_name_the_owner_branch():
    rt = runtime()
    for tool, (core, _) in rt.EDITS_100.items():
        if core == 'light_core.py':
            continue  # 0.9 module of branch D; light_export arrives with branch S
        for name in (core, rt.glue_file(core, rt.GLUE_100)):
            doc = ast.get_docstring(ast.parse((PKG / name).read_text(encoding='utf-8')))
            assert 'owned by branch {}'.format(OWNER[tool]) in doc and '#1024' in doc, name


@pytest.mark.parametrize('tool', list(OWNER))
def test_every_stub_answers_not_implemented(tool):
    rt = runtime()
    if _implemented(rt, tool):
        pytest.skip(tool + ' is implemented; covered by its branch tests')
    r = rt.edits_100(tool, 'preview')
    assert r == ec.not_implemented(tool, 'preview', '#1024') and r['plan']['issue'] == '#1024'
    assert rt.parse_report(json.dumps(r)) == r
    if tool not in rt.READ_100:
        p = ec.report(tool, 'preview', objects=[ec.entry(5, 'Box')], done=['Box'], state_hash=ec.fingerprint((1,)))
        assert rt.edits_100(tool, 'apply', p) == ec.not_implemented(tool, 'apply', '#1024')


def _stub_roof_glue(rt, monkeypatch):
    """`body.roof` is the sample stub row of the dispatcher / journal checks: its glue (branch K) is replaced by an
    empty module, so these checks keep testing the base whatever a branch implements."""
    real = rt._load_core

    def fake(name, key):
        return type(sys)('fake_empty_roof_max') if name == 'roof_max.py' else real(name, key)
    monkeypatch.setattr(rt, '_load_core', fake)


def test_dispatcher_refusals_and_apply_only_from_the_panel(monkeypatch):
    rt = runtime()
    _stub_roof_glue(rt, monkeypatch)
    p = ec.report('body.roof', 'preview', objects=[ec.entry(5, 'Box')], done=['Box'], state_hash=ec.fingerprint((1,)))
    for args, word in ((('nope', 'preview'), 'unsupported edit tool'), (('place.replace', 'preview'), 'unsupported'),
                       (('body.roof', 'commit'), 'mode'), (('body.roof', 'apply'), 'needs the preview'),
                       (('qa.omk_te', 'apply', p), 'read-only')):
        with pytest.raises(ValueError, match=word):
            rt.edits_100(*args)
    for actor in ('mcp', 'agent'):
        with pytest.raises(ValueError, match='^needs_human'):
            rt.edits_100('body.roof', 'apply', p, actor=actor)
        assert rt.edits_100('body.roof', 'preview', actor=actor)['status'] == 'not_implemented'
    with pytest.raises(ValueError, match='actor'):
        rt.edits_100('body.roof', 'preview', actor='robot')
    for fn in (rt.edits_080, rt.edits_090, rt.edits_100):
        assert inspect.signature(fn).parameters['actor'].default == 'panel'


def test_dispatch_path_with_a_fake_glue_gets_the_host_adapter(monkeypatch):
    rt = runtime()
    seen = {}

    def body_roof(ctx, mode, nodes, preview):
        seen['host'] = type(ctx.host).__name__
        seen['core'] = ctx.core.__name__
        return ec.report('body.roof', 'preview', objects=[ec.entry(5, 'Box')], done=['Box'],
                         state_hash=ec.fingerprint((2,)))
    real = rt._load_core

    def fake(name, key):
        mod = real(name, key)
        if name == 'roof_max.py':
            mod = type(mod)('fake_roof_max')
            mod.body_roof = body_roof
        return mod
    monkeypatch.setattr(rt, '_load_core', fake)
    r = rt.edits_100('body.roof', 'preview')
    assert r['status'] == 'pass' and seen == {'host': 'MaxHost', 'core': 'agr_tools_roof_core'}


# ---- cross-branch signatures (SPLIT.md:53-60) --------------------------------------------------------------
@pytest.mark.parametrize('module,fn,params', [
    ('openings_core.py', 'find_openings', ['mesh', 'options']),
    ('windowgen_core.py', 'build_type', ['entry', 'standard', 'options']),
    ('matlib_core.py', 'load_library', ['path']),
    ('matlib_core.py', 'renumber_dense', ['used_ids', 'start']),
    ('uvlayout_core.py', 'layout_seamless', ['islands', 'grid_zero_m', 'module_m', 'texel_px_per_m', 'tile_px',
                                             'options']),
    ('vpmmaps_core.py', 'build_maps', ['udim_table', 'library', 'out_dir', 'options']),
    ('atlas_core.py', 'correspondence_table', ['atlas_report']),
])
def test_cross_branch_signatures_are_fixed(module, fn, params):
    mod = _load(PKG / module, 'agr_sig_' + module[:-3])
    f = getattr(mod, fn)
    assert list(inspect.signature(f).parameters) == params
    if fn == 'renumber_dense':
        assert inspect.signature(f).parameters['start'].default == 1001  # per mesh from 1001 (owner V9 06.11)
    src = inspect.getsource(f)
    if 'raise NotImplementedError' in src:
        with pytest.raises(NotImplementedError, match='#1024'):
            f(*[None] * sum(p.default is inspect.Parameter.empty for p in inspect.signature(f).parameters.values()))


# ---- contract core ------------------------------------------------------------------------------------------
def test_roles_markers_and_names():
    assert cc.ROLES == ('body', 'opening', 'window', 'glass', 'capsule', 'roof', 'parapet', 'equipment', 'decor',
                        'helper')
    assert cc.role_layer('glass') == 'GLASS_' and cc.opening_name(7) == 'OPEN_007' and cc.opening_number('OPEN_012') == 12
    assert cc.level_name('roof') == 'LEVEL_roof' and cc.body_name('Brick', 3) == 'BODY_Brick_003'
    assert cc.agent_layer('req-12') == 'AGENT_req-12'
    for bad in (lambda: cc.check_role('wall'), lambda: cc.opening_name(0), lambda: cc.opening_name(1000),
                lambda: cc.opening_number('OPEN_000'), lambda: cc.opening_number('OPEN_7'),
                lambda: cc.level_name('1 st'), lambda: cc.body_name('Brick wall', 1), lambda: cc.agent_layer('a b'),
                lambda: cc.check_window_type(7)):
        with pytest.raises(ValueError):
            bad()


def test_agr_opening_json_round_trip_and_rejects():
    text = cc.dump_opening(1.2, 1.5, 0.9, 0.25, 'BODY_Brick_001', False)
    assert cc.parse_opening(text) == {'w': 1.2, 'h': 1.5, 'sill': 0.9, 'depth': 0.25, 'wall': 'BODY_Brick_001',
                                      'corner': False}
    good = json.loads(text)
    for k, v in (('w', 0), ('h', -1), ('sill', -0.1), ('depth', float('nan')), ('corner', 'no'), ('wall', ''),
                 ('w', True)):
        bad = dict(good, **{k: v})
        with pytest.raises(ValueError):
            cc.parse_opening(json.dumps(bad))
    with pytest.raises(ValueError):
        cc.parse_opening(json.dumps(dict(good, extra=1)))
    with pytest.raises(ValueError):
        cc.parse_opening('{')


def test_obj_ref_is_host_neutral_and_strict():
    ref = cc.obj_ref('max', 'C:/x.max', 42, 'BODY_Brick_001')
    assert cc.check_ref(dict(ref)) == ref
    for bad in (('maya', 'd', 1, 'n'), ('max', '', 1, 'n'), ('max', 'd', 0, 'n'), ('max', 'd', True, 'n'),
                ('max', 'd', 1.5, 'n')):
        with pytest.raises(ValueError):
            cc.obj_ref(*bad)
    with pytest.raises(ValueError):
        cc.check_ref(dict(ref, node=object()))


def test_host_adapter_interface_and_max_adapter_never_decode_units():
    abstract = {'doc', 'm_per_unit', 'refs', 'resolve', 'selection', 'mesh', 'get_prop', 'set_prop', 'undo'}
    for name in abstract:
        with pytest.raises(NotImplementedError):
            getattr(cc.HostAdapter(), name)(*([None] * (len(inspect.signature(getattr(cc.HostAdapter, name))
                                                            .parameters) - 1)))
    host = _load(PKG / 'host_max.py', 'agr_host_max_100')
    assert abstract <= set(dir(host.MaxHost))
    code = (PKG / 'host_max.py').read_text(encoding='utf-8')
    assert 'decodeValue(' not in code and 'units.SystemScale' in code
    for name in [p.name for p in PKG.glob('*_core.py')]:
        tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
        imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
            {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert 'pymxs' not in imports, name  # cores never take host objects


# ---- schemas K1 / K4 ----------------------------------------------------------------------------------------
def _passport():
    return {'schema': 1, 'project_id': 'KPP1', 'source': {'path': 'src.fbx', 'level': 'B', 'class': 'fbx_cm'},
            'normalization': {'units': 'm', 'up_axis': 'Z', 'scale': 0.01, 'origin_m': [2345678.0, 0.0, 0.0]},
            'stages': [{'id': i, 'status': 'todo'} for i in range(10)] + [{'id': 'agent', 'status': 'todo'}],
            'parts': [{'name': 'BODY_Brick_001', 'role': 'body', 'levels': ['LEVEL_1']}],
            'openings': [{'marker': 'OPEN_001', 'window_type': 'WT-07'}],
            'materials': [{'library_id': 12, 'udim': 1001, 'mesh': 'SM_KPP1_Main'}],
            'journal': {'path': 'jobs/KPP1/journal.jsonl'}, 'agent_requests': [], 'questions': []}


def test_project_passport_schema_accepts_a_passport_and_rejects_broken_ones():
    schema = json.loads((ROOT / 'schemas/ProjectPassport.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(_passport(), schema)
    for mutate in (lambda p: p.pop('stages'), lambda p: p['stages'].pop(), lambda p: p['source'].update(level='D'),
                   lambda p: p['normalization'].update(units='cm'), lambda p: p['parts'][0].update(role='wall'),
                   lambda p: p['openings'][0].update(marker='OPEN_1'),
                   lambda p: p['materials'][0].update(library_id=1005), lambda p: p.update(extra=1)):
        bad = copy.deepcopy(_passport())
        mutate(bad)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
    roles = schema['properties']['parts']['items']['properties']['role']['enum']
    assert tuple(roles) == cc.ROLES


def test_agent_request_schema_layer_and_ops():
    schema = json.loads((ROOT / 'schemas/AgentRequest.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    req = {'schema': 1, 'request_id': 'r1', 'project_id': 'KPP1', 'stage': 2, 'task': 'mark openings',
           'passport_excerpt': {}, 'journal_tail': [],
           'objects': [{'ref': cc.obj_ref('max', 'C:/x.max', 3, 'BODY_Brick_001'), 'role': 'body'}],
           'snapshot': {'fbx': 'snap.fbx', 'sha256': '0' * 64}, 'allowed_ops': ['mark_opening'],
           'invariants': ['objects outside AGENT_r1 unchanged'], 'result_layer': 'AGENT_r1'}
    jsonschema.validate(req, schema)
    for k, v in (('result_layer', 'BODY_r1'), ('allowed_ops', ['exec_unsafe']), ('allowed_ops', []),
                 ('stage', 10)):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(dict(req, **{k: v}), schema)


# ---- journal hook ----------------------------------------------------------------------------------------
def test_one_call_one_journal_line_with_actor(tmp_path, monkeypatch):
    monkeypatch.setenv('AGR_JOURNAL_DIR', str(tmp_path))
    rt = runtime()
    # the journal hook is under test, not the buttons: once a branch implements body.roof / udim.distortion their
    # glue needs Max, so the dispatcher answers like a stub here (#1024 branch M found this)
    real = rt._dispatch_edit
    monkeypatch.setattr(rt, '_dispatch_edit', lambda table, read, glue, issue, tool, mode, *a: (
        rt._edit_core().not_implemented(tool, mode, issue) if tool in table else real(table, read, glue, issue,
                                                                                         tool, mode, *a)))
    rt.edits_100('body.roof', 'preview')
    rt.edits_100('udim.distortion', 'preview', actor='mcp')
    with pytest.raises(ValueError):
        rt.edits_100('nope', 'preview', actor='agent')
    lines = [json.loads(x) for x in (tmp_path / 'untitled.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [x['tool'] for x in lines][0] == 'body.roof' and lines[0]['status'] == 'not_implemented'
    assert lines[0]['actor'] == 'panel' and set(jc.FIELDS) <= set(lines[0])
    assert lines[-1]['tool'] == 'nope' and lines[-1]['status'] == 'error' and lines[-1]['actor'] == 'agent'
    assert len(lines) == 3 and lines[1]['actor'] == 'mcp' and lines[1]['tool'] == 'udim.distortion'


def test_journal_write_failure_never_hides_the_tool_result(tmp_path, monkeypatch, capsys):
    blocker = tmp_path / 'file'
    blocker.write_text('x')
    monkeypatch.setenv('AGR_JOURNAL_DIR', str(blocker / 'sub'))
    rt = runtime()
    _stub_roof_glue(rt, monkeypatch)
    assert rt.edits_100('body.roof', 'preview')['status'] == 'not_implemented'
    assert 'journal line not written' in capsys.readouterr().out


def test_journal_core_record_and_path(tmp_path):
    rec = jc.record('body.roof', 'preview', 'pass', {'objects': 1}, 'ab', 0.5, 'mcp', 'C:/s.max')
    p = jc.append(rec, 'C:/s.max', folder=str(tmp_path))
    assert Path(p).name == jc.scene_key('C:/s.max') + '.jsonl' and len(jc.scene_key('C:/s.max')) == 40
    assert jc.tail('C:/s.max', folder=str(tmp_path)) == [rec]
    with pytest.raises(ValueError):
        jc.record('x', 'preview', 'pass', actor='robot')
    with pytest.raises(ValueError):
        jc.append({'tool': 'x'}, folder=str(tmp_path))


def test_refused_apply_by_mcp_is_journaled_too(tmp_path, monkeypatch):
    """Native job 20261106-040337-75e4eea7: needs_human was raised before the journal hook (60 lines of 114)."""
    monkeypatch.setenv('AGR_JOURNAL_DIR', str(tmp_path))
    rt = runtime()
    p = ec.report('body.roof', 'preview', objects=[ec.entry(5, 'Box')], done=['Box'], state_hash=ec.fingerprint((1,)))
    with pytest.raises(ValueError, match='^needs_human'):
        rt.edits_100('body.roof', 'apply', p, actor='mcp')
    line, = [json.loads(x) for x in (tmp_path / 'untitled.jsonl').read_text(encoding='utf-8').splitlines()]
    assert (line['tool'], line['mode'], line['status'], line['actor']) == ('body.roof', 'apply', 'error', 'mcp')


def test_max_host_is_a_host_adapter_with_roles():
    """Native job 20261106-040337-75e4eea7: MaxHost had no role()/set_role()."""
    host = _load(PKG / 'host_max.py', 'agr_host_max_100b')
    assert issubclass(host.MaxHost, host._core().HostAdapter)
    assert callable(host.MaxHost.role) and callable(host.MaxHost.set_role)
