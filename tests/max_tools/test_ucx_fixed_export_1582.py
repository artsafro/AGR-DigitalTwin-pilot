"""new-case: #1582 pack.deliver exports the ucx.gap copies fixed on layer AGR_export instead of the originals.

Synthetic scene descriptions only (no pymxs, no real object). ucx10_max writes the fixed pieces as copies
`<original>_AGR_gap_NN` on layer AGR_export; deliver_max dropped that layer, so the archive got the OLD UCX.
"""
import copy
import importlib.util
import json
import random
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
sys.path.insert(0, str(ROOT / 'src'))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dc = _load(PKG / 'deliver_core.py', 'agr_tools_deliver_core_1582')
gc = _load(PKG / 'ucx10_core.py', 'agr_tools_ucx10_core_1582')

A = 'SM_TestAddr_Main'
LAYER = 'AGR_export'


def m(h, name):
    return {'handle': h, 'name': name}


def c(h, name, layer=LAYER):
    return {'handle': h, 'name': name, 'layer': layer}


def scene():
    """Family Main_001/002 fixed by ucx.gap (both pieces copied); family Ground untouched."""
    model = [m(1, A), m(2, 'UCX_' + A + '_001'), m(3, 'UCX_' + A + '_002'), m(4, 'UCX_SM_TestAddr_Ground_001')]
    copies = [c(10, 'UCX_' + A + '_001_AGR_gap_001'), c(11, 'UCX_' + A + '_002_AGR_gap_001')]
    return model, copies


# ==== core: the selection =========================================================================================
def test_fixed_copy_replaces_the_original_in_the_export_list():
    model, copies = scene()
    sel = dc.ucx_export_selection(model, copies)
    assert [(r['handle'], r['name'], r['origin']) for r in sel['nodes']] == [
        (1, A, 'original'), (10, 'UCX_' + A + '_001', LAYER), (11, 'UCX_' + A + '_002', LAYER),
        (4, 'UCX_SM_TestAddr_Ground_001', 'original')]
    assert {2, 3}.isdisjoint(r['handle'] for r in sel['nodes'])          # originals skipped, never exported


def test_originals_untouched_and_inputs_not_mutated():
    model, copies = scene()
    before = copy.deepcopy((model, copies))
    dc.ucx_export_selection(model, copies)
    assert (model, copies) == before


def test_family_without_a_copy_keeps_the_original():
    model, _ = scene()
    sel = dc.ucx_export_selection(model, [])
    assert [(r['handle'], r['origin']) for r in sel['nodes']] == [(1, 'original'), (2, 'original'), (3, 'original'),
                                                                 (4, 'original')]
    assert dc.ucx_export_report(sel)['replaced'] == []


def test_report_lists_the_replacements_and_the_ignored_copies():
    model, copies = scene()
    copies += [c(12, 'UCX_Gone_01_AGR_gap_001'), c(13, 'UCX_' + A + '_001_AGR_export_001')]
    rep = dc.ucx_export_report(dc.ucx_export_selection(model, copies))
    assert rep['from_layer'] == LAYER
    assert rep['replaced'] == [
        {'name': 'UCX_' + A + '_001', 'copy': 'UCX_' + A + '_001_AGR_gap_001', 'copy_handle': 10, 'original_handle': 2},
        {'name': 'UCX_' + A + '_002', 'copy': 'UCX_' + A + '_002_AGR_gap_001', 'copy_handle': 11, 'original_handle': 3}]
    assert rep['kept'] == ['UCX_SM_TestAddr_Ground_001']
    assert [(i['handle'], i['reason'].split(':')[0]) for i in rep['ignored']] == [
        (12, 'original not in the export model'), (13, 'not a ucx.gap copy')]
    json.dumps(rep, allow_nan=False)


def test_two_copies_of_one_original_is_a_named_error():
    model, copies = scene()
    copies.append(c(14, 'UCX_' + A + '_001_AGR_gap_002'))
    with pytest.raises(ValueError, match='UCX_SM_TestAddr_Main_001_AGR_gap_001.*UCX_SM_TestAddr_Main_001_AGR_gap_002'):
        dc.ucx_export_selection(model, copies)


def test_partly_copied_family_is_a_named_error():
    """Mixing a moved piece with an old neighbour would ship the collision the gap tool removed."""
    model, copies = scene()
    with pytest.raises(ValueError, match='UCX_SM_TestAddr_Main_002'):
        dc.ucx_export_selection(model, copies[:1])


@pytest.mark.parametrize('model, copies, word', [
    ([], [], 'empty export model'),
    ([m(True, 'UCX_A_01')], [], 'handle'),
    ([m(0, 'UCX_A_01')], [], 'handle'),
    ([m(1, '')], [], 'name'),
    ([{'handle': 1}], [], 'name'),
    ([m(1, 'UCX_A_01')], [c(1, 'UCX_A_01_AGR_gap_001')], 'duplicate handle'),
    ([m(1, 'UCX_A_01')], [c(2, 'UCX_A_01_AGR_gap_001', layer='0')], 'layer'),
    ([m(1, 'UCX_A_01')], [{'handle': 2, 'name': 'UCX_A_01_AGR_gap_001'}], 'layer'),
    ([m(1, 'UCX_A_01'), m(2, 'UCX_A_01')], [c(3, 'UCX_A_01_AGR_gap_001')], 'two originals'),
    ([m(1, 'UCX_A_01')], [c(2, 'SM_A_AGR_gap_001')], 'not a UCX'),
])
def test_fail_closed_inputs(model, copies, word):
    with pytest.raises(ValueError, match=word):
        dc.ucx_export_selection(model, copies)


def test_family_rule_matches_the_gap_tool():
    assert dc.UCX_PIECE.pattern == gc.UCX_NAME.pattern


# ==== the validators still see exactly one UCX per name ==========================================================
def test_package_validator_sees_one_ucx_per_name():
    from twinqa.naming import mesh_name_findings
    model, copies = scene()
    model = model[:3]                     # VPM OKS: every UCX is UCX_SM_<Address>_Main_NNN, i.e. ONE family
    names = [r['name'] for r in dc.ucx_export_selection(model, copies)['nodes']]
    rows = {f.name: f.status for f in mesh_name_findings(names, 'vpm', 'oks', 'SM_TestAddr', 64, 'synthetic')}
    assert rows['UCX names'] == 'pass' and rows['mesh names'] == 'pass'
    # the old behaviour (copies exported by their own name next to the originals) is what V012 rejects
    old = [r['name'] for r in model] + [r['name'] for r in copies]
    rows = {f.name: f.status for f in mesh_name_findings(old, 'vpm', 'oks', 'SM_TestAddr', 64, 'synthetic')}
    assert rows['UCX names'] == 'fail'


def test_probe_random_scenes_one_ucx_per_name_and_every_input_accounted():
    rnd = random.Random(1582)
    for _ in range(300):
        model, copies, h = [m(1, A)], [], 2
        fams = rnd.randint(0, 4)
        for f in range(fams):
            pieces = rnd.randint(1, 4)
            fixed = rnd.random() < 0.5
            for p in range(1, pieces + 1):
                name = 'UCX_SM_X{}_Main_{:03d}'.format(f, p)
                model.append(m(h, name))
                h += 1
                if fixed:
                    copies.append(c(h, name + '_AGR_gap_001'))
                    h += 1
        for _k in range(rnd.randint(0, 2)):                                   # orphans and other tools' copies
            copies.append(c(h, rnd.choice(['UCX_Gone_01_AGR_gap_001', 'UCX_SM_X0_Main_001_AGR_export_001'])))
            h += 1
        rnd.shuffle(copies)
        sel = dc.ucx_export_selection(model, copies)
        names = [r['name'] for r in sel['nodes']]
        assert sorted(names) == sorted(r['name'] for r in model)              # exactly one per original name
        rep = dc.ucx_export_report(sel)
        used = {r['handle'] for r in sel['nodes']}
        dropped = {r['handle'] for r in model} - used
        assert dropped == {x['original_handle'] for x in rep['replaced']}    # every skipped original is reported
        assert {x['handle'] for x in copies} == {x['copy_handle'] for x in rep['replaced']} | {
            x['handle'] for x in rep['ignored']}                              # every copy used or ignored with reason


def test_cli_fresh_process(tmp_path):
    model, copies = scene()
    src = tmp_path / 'scene.json'
    src.write_text(json.dumps({'model': model, 'copies': copies}), encoding='utf-8')
    out = subprocess.run([sys.executable, str(PKG / 'deliver_core.py'), 'ucx-export', str(src)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert [r['copy_handle'] for r in json.loads(out.stdout)['replaced']] == [10, 11]
    src.write_text(json.dumps({'model': model, 'copies': copies[:1]}), encoding='utf-8')
    out = subprocess.run([sys.executable, str(PKG / 'deliver_core.py'), 'ucx-export', str(src)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 2 and 'UCX_SM_TestAddr_Main_002' in out.stderr and out.stdout == ''


# ==== runtime: the copy is exported under the original's name =====================================================
class Node:
    def __init__(self, h, name, layer='0'):
        self.h, self.name, self.layer = h, name, types.SimpleNamespace(name=layer)


def _runtime(monkeypatch):
    rt_mod = _load(PKG / 'runtime.py', 'agr_runtime_1582')
    return rt_mod


def test_export_scene_uses_the_original_name_for_the_copy(monkeypatch):
    mod = _runtime(monkeypatch)
    fake = types.SimpleNamespace(getHandleByAnim=lambda n: n.h)
    monkeypatch.setattr(mod, '_rt', lambda: fake)
    monkeypatch.setattr(mod, 'master_topology', lambda nodes: {'status': 'pass'})
    monkeypatch.setattr(mod, '_tri_mesh', lambda n: ([[0, 0, 0]], [[0, 0, 0]], [1]))
    monkeypatch.setattr(mod, '_hygiene_dump', lambda n: {'n': n.h})
    monkeypatch.setattr(mod, '_repair_blocks', lambda dumps: True)
    nodes = [Node(1, A), Node(10, 'UCX_' + A + '_001_AGR_gap_001', LAYER)]
    scene_ = mod._export_scene(nodes, names={10: 'UCX_' + A + '_001'})
    assert [o['name'] for o in scene_['objects']] == [A]
    assert [(p['name'], p['handle']) for p in scene_['ucx']] == [('UCX_' + A + '_001', 10)]
    with pytest.raises(ValueError, match='names'):
        mod._export_scene(nodes, names={99: 'UCX_X_01'})                    # a name for a node not exported


def test_write_fbx_exports_the_copy_under_the_original_name_and_restores_the_original(monkeypatch, tmp_path):
    mod = _runtime(monkeypatch)
    orig = Node(2, 'UCX_' + A + '_001')
    render, fixed = Node(1, A), Node(10, 'UCX_' + A + '_001_AGR_gap_001', LAYER)
    scene_nodes = [render, orig, fixed]
    seen = {}
    params = {}

    def export_file(path, *a, **k):
        seen['selected'] = [n.name for n in fake.selection]
        seen['scene'] = sorted(n.name for n in scene_nodes)
        Path(path).write_bytes(b'fbx')
        return True

    def copy_node(n):
        d = Node(100 + n.h, n.name, n.layer.name)
        scene_nodes.append(d)
        return d

    fake = types.SimpleNamespace(
        pluginManager=types.SimpleNamespace(loadClass=lambda cls: None), FbxExporter=object(), FBXEXP=object(),
        FBXExporterSetParam=lambda k, v: params.__setitem__(k, v),
        FBXExporterGetParam=lambda k: params[k], getHandleByAnim=lambda n: n.h, copy=copy_node,
        setUserPropBuffer=lambda n, b: None, getUserPropBuffer=lambda n: '', Name=lambda s: s,
        exportFile=export_file, delete=lambda ns: [scene_nodes.remove(n) for n in ns],
        objects=scene_nodes, selection=[])
    fake.select = lambda ns: fake.__setattr__('selection', list(ns))
    monkeypatch.setattr(mod, '_rt', lambda: fake)
    monkeypatch.setattr(mod, 'snapshot', lambda nodes: [(n.h, n.name) for n in nodes])
    monkeypatch.setattr(mod, '_delivery_props', lambda b: b)
    target = tmp_path / 'SM_TestAddr.fbx'
    mod._write_max_fbx([render, fixed], target, names={10: 'UCX_' + A + '_001'})
    assert seen['selected'] == [A, 'UCX_' + A + '_001']                      # the fixed geometry, original name
    assert seen['scene'].count('UCX_' + A + '_001') == 1                      # original parked during export
    assert orig.name == 'UCX_' + A + '_001' and fixed.name == 'UCX_' + A + '_001_AGR_gap_001'
    assert sorted(n.h for n in scene_nodes) == [1, 2, 10]                     # temp copies deleted
    assert target.read_bytes() == b'fbx'


# ==== deliver glue: export.checked gets the substituted set, deliver.json records it ==============================
def _glue(monkeypatch, tmp_path):
    dm = _load(PKG / 'deliver_max.py', 'agr_tools_deliver_max_1582')
    model = [Node(1, A), Node(2, 'UCX_' + A + '_001'), Node(3, 'UCX_' + A + '_002'),
             Node(4, 'UCX_SM_TestAddr_Ground_001')]
    copies = [Node(10, 'UCX_' + A + '_001_AGR_gap_001', LAYER), Node(11, 'UCX_' + A + '_002_AGR_gap_001', LAYER)]
    monkeypatch.setattr(dm, '_handle', lambda n: n.h)
    monkeypatch.setattr(dm, '_model_nodes', lambda nodes: list(model))
    monkeypatch.setattr(dm, '_gap_copies', lambda: list(copies))
    monkeypatch.setattr(dm, '_passport', lambda ctx, opts: (None, None))
    calls = []

    def rep(status='pass', plan=None):
        return {'status': status, 'objects': [], 'plan': plan or {}}

    def export_preview(nodes=None, target=None, names=None):
        calls.append(('preview', [n.h for n in nodes], names))
        return rep()

    def export_commit(nodes=None, preview=None, target=None, names=None):
        calls.append(('commit', [n.h for n in nodes], names))
        Path(target).write_bytes(b'fbx')
        return rep()

    def edits_080(tool, mode, preview=None, options=None):
        return rep(plan={'run_folder': options['folder'] if options else None})

    agr = types.SimpleNamespace(checks_050=lambda *a, **k: rep(), checks_070=lambda *a, **k: rep(),
                                edits_090=lambda *a, **k: rep(), edits_100=lambda *a, **k: rep(),
                                export_preview=export_preview, export_commit=export_commit, edits_080=edits_080)
    edit = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_1582')
    emax = types.SimpleNamespace(snapshot=lambda ns: [(n.h, n.name) for n in ns], keep_selection=_null)
    skip = {'light.export': 'нет света', 'qa.omk_te': 'нет', 'ucx.gap': 'нет', 'qa.sintez': 'нет',
            'light.check': 'нет'}
    ctx = types.SimpleNamespace(core=dc, agr=agr, edit=edit, emax=emax,
                                options={'folder': str(tmp_path), 'stem': 'SM_TestAddr', 'skip': skip})
    return dm, ctx, calls, copies


class _null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_deliver_exports_the_fixed_copies_and_records_them(monkeypatch, tmp_path):
    dm, ctx, calls, _ = _glue(monkeypatch, tmp_path)
    names = {10: 'UCX_' + A + '_001', 11: 'UCX_' + A + '_002'}
    pre = dm._pack_deliver(ctx, 'preview', None, None)
    assert ('preview', [1, 10, 11, 4], names) in calls
    assert [x['copy_handle'] for x in pre['plan']['ucx_export']['replaced']] == [10, 11]
    out = dm._pack_deliver(ctx, 'apply', None, pre)
    assert ('commit', [1, 10, 11, 4], names) in calls
    body = json.loads((Path(out['plan']['run_folder']) / dc.REPORT).read_text(encoding='utf-8'))
    assert [x['name'] for x in body['ucx_export']['replaced']] == ['UCX_' + A + '_001', 'UCX_' + A + '_002']
    assert body['ucx_export']['kept'] == ['UCX_SM_TestAddr_Ground_001']


@pytest.mark.parametrize('copy_offset', [1.01, 0.99, float('nan'), float('inf')])
def test_deliver_ucx_previews_judge_export_geometry_without_skips(monkeypatch, tmp_path, copy_offset):
    """#1584: real gap glue must not expand the export selection back to the originals."""
    dm, ctx, calls, copies = _glue(monkeypatch, tmp_path)
    ctx.options.pop('skip')
    gap_max = _load(PKG / 'ucx10_max.py', 'agr_ucx10_max_1584')
    uc = _load(PKG / 'ucx_core.py', 'agr_ucx_core_1584')
    model = dm._model_nodes(None)
    every = model + copies
    geometry = {}
    for n, x in zip(every, [20, 0, 0.99, 40, 0, 1.01]):
        geometry[n.h] = uc._convex_hull([[xx, y, z] for xx in (x, x + 1) for y in (0, 1) for z in (0, 1)])
        n.inode = types.SimpleNamespace(handle=n.h)
    geometry[11] = ([(x + copy_offset - 1.01, y, z) for x, y, z in geometry[11][0]], geometry[11][1])
    rt = types.SimpleNamespace(objects=every, isValidNode=lambda n: n in every,
                               canConvertTo=lambda *a: True, TriMeshGeometry=object(),
                               units=types.SimpleNamespace(SystemType='meters', SystemScale=1))
    monkeypatch.setattr(gap_max, '_rt', lambda: rt)
    host = types.SimpleNamespace(m_per_unit=lambda: 1., refs=lambda ns: ns,
                                 mesh=lambda n: dict(zip(('verts', 'faces'), geometry[n.h])))
    seen = []

    def edits(tool, mode, preview=None, nodes=None, options=None, **kw):
        if tool != 'ucx.gap':
            plan = {'target': str(Path(options['folder']) / 'SM_TestAddr_Light.fbx')} if options and tool == 'light.export' else {}
            if mode == 'apply' and tool == 'light.export':
                plan = preview['plan']
                Path(plan['target']).write_bytes(b'synthetic light fbx')
            return {'status': 'pass', 'objects': [], 'plan': plan}
        gctx = types.SimpleNamespace(core=gc, edit=ctx.edit, emax=ctx.emax, host=host, options=options or {})
        result = gap_max.ucx_gap(gctx, mode, nodes, preview)
        seen.append(result)
        return result

    def checks(tool, nodes=None, select=False, **kw):
        if tool in ('ucx_audit', 'preflight'):
            selected = kw.get('ucx_export', {}).get('nodes', nodes)
            assert [n.h for n in selected] == [1, 10, 11, 4]
        return {'status': 'pass', 'objects': [], 'plan': {}}

    ctx.agr.edits_100 = edits
    ctx.agr.checks_070 = checks
    # Establish that the originals really have findings, rather than faking their verdict.
    original = edits('ucx.gap', 'preview', nodes=model)
    assert original['status'] == 'fail'
    pre = dm.pack_deliver(ctx, 'preview', None, None)
    if copy_offset != 1.01:
        assert pre['status'] == 'fail'
        assert {r['id']: r['status'] for r in pre['plan']['steps']}['ucx.gap'] in ('fail', 'error')
        out = dm.pack_deliver(ctx, 'apply', None, pre)
        assert out['status'] == 'fail' and not any(c[0] == 'commit' for c in calls)
        return
    assert pre['status'] == 'pass', pre['plan']['blockers']
    assert seen[-1]['status'] == 'pass'
    assert {o['handle'] for o in seen[-1]['objects']} == {10, 11, 4}
    with pytest.raises(ValueError, match='read-only'):
        edits('ucx.gap', 'apply', preview=seen[-1])
    out = dm.pack_deliver(ctx, 'apply', None, pre)
    assert out['status'] == 'pass'
    assert ('commit', [1, 10, 11, 4], {10: 'UCX_' + A + '_001', 11: 'UCX_' + A + '_002'}) in calls
    body = json.loads((Path(out['plan']['run_folder']) / dc.REPORT).read_text(encoding='utf-8'))
    assert body['options']['skip'] == {}
    assert all(r['status'] == 'pass' for r in body['steps'] if r['id'] in ('ucx.audit', 'ucx.gap'))
    assert [n.name for n in copies] == ['UCX_' + A + '_001_AGR_gap_001', 'UCX_' + A + '_002_AGR_gap_001']


@pytest.mark.parametrize('case', ['empty', 'partial', 'unknown', 'null', 'duplicate', 'unsupported'])
def test_delivery_gap_rejects_invalid_exact_scope(monkeypatch, case):
    gm = _load(PKG / 'ucx10_max.py', 'agr_ucx10_max_scope_1584')
    ec = _load(PKG / 'edit_core.py', 'agr_edit_scope_1584')
    node = Node(10, 'UCX_' + A + '_001_AGR_gap_001', LAYER)
    node.inode = types.SimpleNamespace(handle=node.h)
    rows = [node]
    names = {'10': 'UCX_' + A + '_001'}
    if case == 'empty':
        rows, names = [], {}
    elif case == 'partial':
        names = {}
    elif case == 'unknown':
        names['99'] = 'UCX_Missing_001'
    elif case == 'null':
        names = None
    elif case == 'duplicate':
        rows *= 2
    else:
        names['10'] = 'not_a_ucx_piece'
    monkeypatch.setattr(gm, '_rt', lambda: types.SimpleNamespace())
    host = types.SimpleNamespace(m_per_unit=lambda: 1., refs=lambda ns: ns,
                                 mesh=lambda n: {'verts': [], 'faces': []})
    ctx = types.SimpleNamespace(core=gc, edit=ec, host=host, emax=None,
                                options={'delivery_names': names})
    with pytest.raises(ValueError, match='delivery|duplicate'):
        gm.ucx_gap(ctx, 'preview', rows, None)


def test_deliver_preview_is_stale_when_a_fixed_copy_changes(monkeypatch, tmp_path):
    dm, ctx, _calls, copies = _glue(monkeypatch, tmp_path)
    pre = dm._pack_deliver(ctx, 'preview', None, None)
    copies[0].name = 'UCX_' + A + '_001_AGR_gap_002'
    with pytest.raises(Exception, match='(?i)stale|changed'):
        dm._pack_deliver(ctx, 'apply', None, pre)


def test_deliver_ambiguous_copies_block_export_checked(monkeypatch, tmp_path):
    dm, ctx, calls, copies = _glue(monkeypatch, tmp_path)
    del copies[1]                                                             # family half fixed
    pre = dm._pack_deliver(ctx, 'preview', None, None)
    step = {r['id']: r for r in pre['plan']['steps']}['export.checked']
    assert step['status'] == 'error' and 'UCX_SM_TestAddr_Main_002' in step['error']
    assert pre['status'] == 'fail' and not [c for c in calls if c[0] == 'preview']
    assert 'error' in pre['plan']['ucx_export']
