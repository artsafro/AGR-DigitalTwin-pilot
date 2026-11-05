"""new-case: AGR Tools 0.9 `export.batch` (#979, branch D): batch_core over the real export.checked core.

The groups are exported through export_core.dry_run / commit (the gates and readback of `export.checked`,
AGR Tools 0.4.0) with an injected FBX writer and reader, as runtime.export_preview / export_commit do in Max.
Source model: `export.checked` pressed once per FBX (one target, one run): an existing target is refused
(`existing_target`), and a group whose gates fail raises in commit, so a hand loop over the groups stops there.
Acceptance (#979 §16): 3 groups - clean, dirty geometry, already existing file -> FBX + readback for the clean
one, fail at the gates for the dirty one, a new file version for the third; one report.
"""
import ast
import importlib.util
import json
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


ec = sys.modules.get('agr_tools_edit_core') or _load(PKG / 'edit_core.py', 'agr_tools_edit_core')
bc = _load(PKG / 'batch_core.py', 'agr_tools_batch_core_t')
xc = _load(PKG / 'export_core.py', 'agr_tools_export_batch_t')


# ---- export_core scene fixtures (same shape as runtime._export_scene) --------------------------------------
def hygiene(name, props='MapChannel:1 = UV\r\n', channels=(1,)):
    return {'name': name, 'custom_attributes': {'base': [], 'node': [], 'modifiers': [], 'materials': []},
            'user_props': props, 'map_channels': list(channels)}


def triangle(name, handle, z=0.0):
    xyz = [(0.0, 0.0, z), (1.0, 0.0, z), (0.0, 1.0, z)]
    return {'name': name, 'handle': handle, 'material': 'brick', 'material_ids': [1],
            'vertices': [list(p) for p in xyz], 'faces': [[0, 1, 2]], 'hygiene': hygiene(name), 'slot_gaps': [],
            'texel': {'profile': 'VPM', 'materials': [{'name': 'brick', 'map_px': 1024}],
                      'faces': [{'id': '1', 'mesh': name, 'material': 'brick', 'xyz': xyz,
                                 'uv': [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]}]}}


def stacked(name, handle):
    obj = triangle(name, handle)
    obj['vertices'] = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                       [0.0, 0.0, 0.002], [1.0, 0.0, 0.002], [0.0, 1.0, 0.002]]
    obj['faces'] = [[0, 1, 2], [3, 4, 5]]
    obj['material_ids'] = [1, 1]
    obj['texel']['faces'].append({'id': '2', 'mesh': name, 'material': 'brick',
                                  'xyz': [(0.0, 0.0, 0.002), (1.0, 0.0, 0.002), (0.0, 1.0, 0.002)],
                                  'uv': [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]})
    return obj


class World:
    """A scene of export_core objects keyed by handle, with AGR_EXPORT_PATH per node."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.objs, self.paths, self.writes = {}, {}, []

    def add(self, obj, path):
        self.objs[obj['handle']] = obj
        self.paths[obj['handle']] = path
        return obj['handle']

    def rows(self):
        return [{'handle': h, 'name': o['name'], 'path': self.paths[h]} for h, o in self.objs.items()]

    def scene(self, g):
        return {'objects': [self.objs[m['handle']] for m in g['members']], 'ucx': [], 'units': 'm', 'axis': 'Z-up'}

    def dry_run(self, g):
        return xc.dry_run(self.scene(g), g['target'], None)

    def commit(self, g, preview):
        def writer(path, _plan):
            Path(path).write_bytes(b'FBX ' + str(path).encode())
            self.writes.append(str(path))

        def reader(_data):
            p = preview['plan']
            return {'object_count': p['object_count'], 'triangle_count': p['triangle_count'],
                    'material_count': p['material_count'], 'unit_scale_factor': p['unit_scale_factor'],
                    'axis': p['axis'], 'error': None, 'object_names': list(p['object_names'])}
        return xc.commit(self.scene(g), g['target'], None, preview, writer=writer, readback_fn=reader)


NOT_IMPL = ec.not_implemented('qa.procedural_objects', 'preview', '#979')
qc = _load(PKG / 'qa9_core.py', 'agr_tools_qa9_core_batch_t')  # the real answer of branch C (#1000)
CLASSES = qc.load_classes(str(PKG / 'data' / 'procedural_classes.json'))


def proc_report(offenders=(), others=()):
    """The real qa.procedural_objects preview (qa9_core.procedural_scan + procedural_report): offenders are
    Forest_Pro nodes, others plain Editable_Poly nodes."""
    rows = [{'handle': h, 'name': n, 'cls': 'Forest_Pro', 'superclass': 'GeometryClass', 'hidden': False,
             'frozen': False} for h, n in offenders]
    rows += [{'handle': h, 'name': n, 'cls': 'Editable_Poly', 'superclass': 'GeometryClass', 'hidden': False,
              'frozen': False} for h, n in others]
    hits, products = qc.procedural_scan(rows, CLASSES, {'forest_pro'})
    return qc.procedural_report(ec, rows, hits, products, 'scene')


CLEAN = proc_report(others=[(1, 'SM_Clean_Main'), (2, 'SM_Clean_Main_2'), (3, 'SM_Dirty_Main'), (4, 'SM_Old_Main')])


def preview(world, proc=CLEAN):
    groups, skipped, procedural = bc.plan_batch(ec, world.rows(), proc, world.dry_run)
    state = ec.fingerprint(bc.batch_state(ec, groups, skipped, procedural))
    return bc.batch_report(ec, 'preview', groups, skipped, procedural, state), (groups, skipped, procedural)


def apply(world, prev, proc=CLEAN):
    groups, skipped, procedural = bc.plan_batch(ec, world.rows(), proc, world.dry_run)
    ec.check_preview('export.batch', prev)
    ec.require_current(prev, bc.batch_state(ec, groups, skipped, procedural))
    bc.apply_batch(groups, world.commit)
    return bc.batch_report(ec, 'apply', groups, skipped, procedural)


def codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


@pytest.fixture
def three(tmp_path):
    w = World(tmp_path)
    out = tmp_path / 'export'
    out.mkdir()
    w.add(triangle('SM_Clean_Main', 1), str(out / 'clean.fbx'))
    w.add(triangle('SM_Clean_Main_2', 2, z=5.0), str(out / 'clean.fbx'))
    w.add(stacked('SM_Dirty_Main', 3), str(out / 'dirty.fbx'))
    w.add(triangle('SM_Old_Main', 4), str(out / 'old.fbx'))
    (out / 'old.fbx').write_bytes(b'previous delivery')
    return w, out


# ---- source model ----------------------------------------------------------------------------------------
def checked_loop(world, groups):
    """export.checked pressed per FBX in a loop: target as written; commit raises on a failed gate."""
    written = []
    for g in groups:
        g = dict(g, target=g['requested'])
        rep = world.dry_run(g)
        if rep['status'] != 'pass':
            raise ValueError('gate failed: ' + str(rep['plan']['stopped']))
        written.append(world.commit(g, rep)['plan']['target'])
    return written


def test_red_a_loop_of_export_checked_stops_at_the_first_bad_group_and_refuses_the_old_file(three):
    w, out = three
    groups, _ = bc.group_nodes(w.rows())
    old = next(g for g in groups if g['requested'].endswith('old.fbx'))
    rep = w.dry_run(dict(old, target=old['requested']))
    assert rep['plan']['stopped'] == 'path' and 'existing_target' in json.dumps(rep)  # RED: no new version
    with pytest.raises(ValueError, match='gate failed'):
        checked_loop(w, groups)  # RED: clean.fbx first, then dirty.fbx stops the loop: old.fbx never runs
    assert not (out / 'old_v002.fbx').exists()


# ---- acceptance -----------------------------------------------------------------------------------------
def test_three_groups_one_report_preview_then_apply(three):
    w, out = three
    prev, _ = preview(w)
    assert prev['tool'] == 'export.batch' and prev['plan']['mode'] == 'preview' and prev['status'] == 'fail'
    rows = {Path(r['requested']).name: r for r in prev['plan']['groups']}
    assert rows['clean.fbx']['status'] == 'pass' and rows['clean.fbx']['nodes'] == ['SM_Clean_Main', 'SM_Clean_Main_2']
    assert rows['dirty.fbx']['status'] == 'fail' and rows['dirty.fbx']['stopped'] == 'xview'
    assert rows['old.fbx']['status'] == 'pass' and rows['old.fbx']['versioned']
    assert Path(rows['old.fbx']['target']).name == 'old_v002.fbx'
    assert codes(prev) == {'SM_Clean_Main': [], 'SM_Clean_Main_2': [], 'SM_Dirty_Main': ['overlap_faces', 'overlap_vertices'],
                           'SM_Old_Main': []}
    assert [Path(d['item']).name for d in prev['plan']['done']] == ['clean.fbx', 'old_v002.fbx']
    assert [Path(s['item']).name for s in prev['plan']['skipped']] == ['dirty.fbx']
    assert sorted(p.name for p in out.iterdir()) == ['old.fbx']  # preview writes nothing

    rep = apply(w, prev)
    assert rep['plan']['mode'] == 'apply' and rep['status'] == 'fail'  # one group failed -> the batch fails
    done = {Path(d['item']).name: d for d in rep['plan']['done']}
    assert set(done) == {'clean.fbx', 'old_v002.fbx'}
    assert done['clean.fbx']['readback']['object_count'] == 2 and done['old_v002.fbx']['readback']['object_count'] == 1
    assert (out / 'old.fbx').read_bytes() == b'previous delivery'  # never overwritten
    assert sorted(p.name for p in out.iterdir()) == ['clean.fbx', 'clean.report.json', 'old.fbx', 'old_v002.fbx',
                                                     'old_v002.report.json']
    assert ec.validate_report(rep) is rep


def test_a_group_that_raises_does_not_stop_the_others(three):
    w, out = three
    real = w.dry_run

    def flaky(g):
        if g['requested'].endswith('clean.fbx'):
            raise RuntimeError('snapshotAsMesh failed')
        return real(g)

    groups, skipped, procedural = bc.plan_batch(ec, w.rows(), CLEAN, flaky)
    rep = bc.batch_report(ec, 'preview', groups, skipped, procedural, 's')
    assert codes(rep)['SM_Clean_Main'] == ['export_error'] and codes(rep)['SM_Old_Main'] == []
    assert [Path(d['item']).name for d in rep['plan']['done']] == ['old_v002.fbx']


def test_apply_error_in_one_group_is_recorded_and_the_rest_written(three):
    w, out = three
    prev, _ = preview(w)
    real = w.commit

    def bad(g, rep):
        if g['target'].endswith('clean.fbx'):
            raise RuntimeError('FBX export failed')
        return real(g, rep)
    w.commit = bad
    rep = apply(w, prev)
    assert codes(rep)['SM_Clean_Main'] == ['export_error'] and (out / 'old_v002.fbx').is_file()
    assert not (out / 'clean.fbx').exists()


def test_stale_preview_is_refused_and_writes_nothing(three):
    w, out = three
    prev, _ = preview(w)
    (out / 'old_v002.fbx').write_bytes(b'someone else')  # the planned version appeared after the preview
    with pytest.raises(ec.StalePreview):
        apply(w, prev)
    assert sorted(p.name for p in out.iterdir()) == ['old.fbx', 'old_v002.fbx']


def test_version_skips_the_report_and_partial_files_and_planned_targets(tmp_path):
    out = tmp_path
    (out / 'a.report.json').write_text('{}', encoding='utf-8')
    (out / 'a_v002.fbx.partial').write_bytes(b'')
    assert bc.plan_target(ec, str(out / 'a.fbx')) == (str(out / 'a_v003.fbx'), True)
    w = World(tmp_path)
    (out / 'b.fbx').write_bytes(b'x')
    w.add(triangle('SM_B_Main', 1), str(out / 'b.fbx'))
    w.add(triangle('SM_C_Main', 2), str(out / 'b_v002.fbx'))  # asks for the name b.fbx would version to
    prev, _ = preview(w)
    assert sorted(Path(r['target']).name for r in prev['plan']['groups']) == ['b_v002.fbx', 'b_v003.fbx']


# ---- procedural objects (branch C) ------------------------------------------------------------------------
def test_with_the_real_answer_of_c_a_procedural_object_blocks_only_its_group(three):
    """Replaces the not_implemented refusal test of #990: branch C is in main (#1000). A Forest_Pro node in the
    old.fbx group blocks that group; the clean groups go through the gates and are written with readback."""
    w, out = three
    proc = proc_report([(4, 'SM_Old_Main')], [(1, 'SM_Clean_Main'), (2, 'SM_Clean_Main_2'), (3, 'SM_Dirty_Main')])
    assert proc['plan']['blocking'] == [4]  # the stable list of qa9_core.procedural_report
    prev, _ = preview(w, proc)
    rows = {Path(r['requested']).name: r['status'] for r in prev['plan']['groups']}
    assert rows == {'clean.fbx': 'pass', 'dirty.fbx': 'fail', 'old.fbx': 'blocked'}
    assert codes(prev)['SM_Old_Main'] == ['procedural_object'] and prev['plan']['procedural']['state'] == 'checked'
    old = next(o for o in prev['objects'] if o['name'] == 'SM_Old_Main')
    assert 'proc_object Forest_Pro' in old['findings'][0]['detail']
    rep = apply(w, prev, proc)
    done = {Path(d['item']).name: d for d in rep['plan']['done']}
    assert set(done) == {'clean.fbx'} and done['clean.fbx']['readback']['object_count'] == 2
    assert not (out / 'old_v002.fbx').exists() and (out / 'old.fbx').read_bytes() == b'previous delivery'


def test_with_the_real_answer_of_c_and_no_procedural_object_every_clean_group_is_written(three):
    w, out = three
    prev, _ = preview(w, CLEAN)
    assert CLEAN['status'] == 'pass' and CLEAN['plan']['blocking'] == []
    assert not any(r['status'] == 'blocked' for r in prev['plan']['groups'])
    rep = apply(w, prev, CLEAN)
    assert sorted(Path(d['item']).name for d in rep['plan']['done']) == ['clean.fbx', 'old_v002.fbx']


def test_a_missing_plugin_placeholder_blocks_its_group(three):
    w, _ = three
    rows = [{'handle': 1, 'name': 'SM_Clean_Main', 'cls': 'Missing_Geom', 'superclass': 'GeometryClass',
             'hidden': True, 'frozen': False}]
    hits, products = qc.procedural_scan(rows, CLASSES, set())
    proc = qc.procedural_report(ec, rows, hits, products, 'scene')
    prev, _ = preview(w, proc)
    rows = {Path(r['requested']).name: r['status'] for r in prev['plan']['groups']}
    assert rows['clean.fbx'] == 'blocked' and rows['old.fbx'] == 'pass'


def test_unknown_procedural_state_still_blocks_everything():
    """Fail closed stays in the core: a not_implemented answer, an error or another tool's answer."""
    assert bc.procedural_state(NOT_IMPL)[0] == 'not_implemented'
    state, offenders, detail = bc.procedural_state(RuntimeError('class table unreadable'))
    assert state == 'error' and 'unreadable' in detail
    assert bc.procedural_state({'tool': 'qa.normals'})[0] == 'error'
    groups, _ = bc.group_nodes([{'handle': 1, 'name': 'A', 'path': 'C:/x/a.fbx'}])
    assert bc.judge(groups, 'not_implemented', {}, 'x')[0]['blocked']


def test_glue_gets_the_list_only_through_runtime_edits_090():
    src = (PKG / 'batch_max.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    imported = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    assert not any('qa9' in name for name in imported) and 'qa9' not in src.replace('qa9_*', '')
    assert 'agr.edits_090(core.PROCEDURAL' in src
    assert 'agr.export_preview(' in src and 'agr.export_commit(' in src  # the export.checked path as it is


# ---- grouping and empty input ---------------------------------------------------------------------------
def test_grouping_and_skipped_nodes_have_reasons(tmp_path):
    rows = [{'handle': 1, 'name': 'A', 'path': 'C:/x/A.fbx'}, {'handle': 2, 'name': 'B', 'path': 'c:\\X\\a.FBX'},
            {'handle': 3, 'name': 'C', 'path': None}, {'handle': 4, 'name': 'D', 'path': 'rel/d.fbx'},
            {'handle': 5, 'name': 'E', 'path': 'C:/x/e.obj'}]
    groups, skipped = bc.group_nodes(rows)
    assert [[m['name'] for m in g['members']] for g in groups] == [['A', 'B']]
    assert [s[1] for s in skipped] == ['C', 'D', 'E'] and all(s[2] for s in skipped)
    rep = bc.batch_report(ec, 'preview', [], skipped, {'state': 'checked', 'offenders': {}}, 's')
    assert codes(rep) == {'C': [], 'D': ['export_path_invalid'], 'E': ['export_path_invalid']}  # no key: no defect
    with pytest.raises(ValueError, match='empty batch'):
        bc.plan_batch(ec, rows[2:], CLEAN, lambda g: None)


def test_options_are_refused():
    assert bc.batch_options(None) == {}
    with pytest.raises(ValueError):
        bc.batch_options({'overwrite': True})
