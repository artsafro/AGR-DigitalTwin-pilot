"""new-case: #1024 branch H native run of model.grid_cleanup and model.glass_planes in locked batch Max 2024 on
DISPOSABLE synthetic scenes, plus the branch's rows of the live polygon (stations 1.0.7 and 1.0.11).

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then through runtime.edits_100 (the panel path):
* grid cleanup on the 12 x 9 m facade (triangulated, 2 T-junctions, a loop, noise, a UV seam, MatID/SG band):
  preview changes nothing; apply makes ONE copy on AGR_export, the original mesh hash is unchanged, the copy has
  0 T-vertices, 0 triangles, 2 UV islands, SG {1,2}, MatID {1,2}, the 24 opening corners in place; one `max undo`
  removes the copy; selection restored; 0 hidden objects added; no new MAXScript globals;
* weld mode welds only the selected crack points; without a selection it is skipped; no map channel 1 is skipped;
* a centimetre scene gives the same counts as the metre scene (thresholds in metres);
* glass planes on the #1024 row 2 pieces: faces after the rule, the copy carries agr_role=glass, MatIDs and UV kept;
* actor mcp cannot apply (needs_human); an empty selection is an error;
* polygon: builds polygon_all from polygon_core.load_catalog(), presses the two buttons (preview), compares with
  test-polygon/expected and writes the rows.
Nothing is saved except the polygon scene copy under OUT.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import traceback

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'
sys.path.insert(0, str(ROOT / 'test-polygon' / 'stations'))
import H_build as hb  # noqa: E402


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2500:]


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    sys.modules.pop('runtime', None)
    import runtime as agr
    return agr


agr = install()
emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
gcore = agr._load_core('gridclean_core.py', 'agr_tools_gridclean_core')
gmax = agr._load_core('gridclean_max.py', 'agr_tools_gridclean_max')
glcore = agr._load_core('glass_core.py', 'agr_tools_glass_core')
summary['runtime_version'] = agr.VERSION


def gather_globals():
    return {str(x) for x in rt.globalVars.gather()}


GLOBALS0 = None


def reset(units='meters'):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(units)
    rt.units.SystemScale = 1.0


def build(name, mesh, pos=(0, 0, 0)):
    n = hb.build_poly(rt, name, mesh)
    n.pos = rt.Point3(*pos)
    return n


def hidden_count():
    return sum(1 for o in rt.objects if o.isHidden)


def world_points(node):
    k = float(agr._load_core('host_max.py', 'agr_tools_host_max').MaxHost().m_per_unit())
    mesh, _, _ = gmax.read_poly(node, k)
    return mesh


def copies_of(name, suffix):
    return [o for o in rt.objects if str(o.name).startswith(name + suffix)]


def grid_apply():
    global GLOBALS0
    reset()
    GLOBALS0 = gather_globals()
    n = build('SM_GridH_Dirty_Main', hb.facade())
    rt.select(n)
    sel_before = [str(o.name) for o in rt.selection]
    hash0 = emax.snapshot([n])
    objs0, hidden0 = len(list(rt.objects)), hidden_count()
    pre = agr.edits_100('model.grid_cleanup', 'preview')
    assert pre['status'] == 'fail' and pre['plan']['mode'] == 'preview', pre['status']
    codes = sorted(f['code'] for o in pre['objects'] for f in o['findings'])
    assert codes == ['t_junction', 'triangles'], codes
    assert emax.snapshot([n]) == hash0 and len(list(rt.objects)) == objs0, 'preview changed the scene'
    rep = agr.edits_100('model.grid_cleanup', 'apply', pre)
    assert rep['status'] == 'pass', json.dumps(rep)[:1500]
    assert emax.snapshot([n]) == hash0, 'the original changed'
    cs = copies_of('SM_GridH_Dirty_Main', '_AGR_grid_')
    assert len(cs) == 1, [str(c.name) for c in cs]
    c = cs[0]
    assert str(c.layer.name) == 'AGR_export'
    assert len(list(rt.objects)) == objs0 + 1 and hidden_count() == hidden0, 'hidden or extra objects'
    m = world_points(c)
    st = gcore.stats(m)
    assert st['t_vertices'] == 0 and st['tris'] == 0, st
    assert (st['uv_islands'], st['sgs'], st['mat_ids']) == (2, [1, 2], [1, 2]), st
    corners = hb.opening_corners()
    missing = [p for p in corners if not any(math.dist(p, q) < 1e-6 for q in m['verts'])]
    assert not missing, missing[:4]
    assert [str(o.name) for o in rt.selection] == sel_before, 'selection not restored'
    rt.execute('max undo')  # ONE undo removes the whole run
    assert not copies_of('SM_GridH_Dirty_Main', '_AGR_grid_') and len(list(rt.objects)) == objs0, 'one undo'
    return {'preview_codes': codes, 'apply_done': rep['plan']['done'], 'copy': str(c.name), 'stats': st,
            'counts': pre['plan']['rows'][0]['counts'], 'objects_before_after': [objs0, objs0 + 1],
            'hidden_added': 0, 'undo_removes_copy': True}


def grid_weld_and_skips():
    reset()
    n = build('SM_GridH_Weld_Main', hb.facade_weld())
    sel = [i + 1 for i, p in enumerate(hb.facade_weld()['verts']) if p[0] > 11.9 and p[2] < 1.01]
    rt.polyop.setVertSelection(n, rt.execute('#{' + ','.join(str(i) for i in sel) + '}'))
    rt.select(n)
    opts = {'modes': ['tjunctions'], 't_mode': 'weld', 'weld_m': 0.001}
    pre = agr.edits_100('model.grid_cleanup', 'preview', options=opts)
    row = pre['plan']['rows'][0]
    assert row['counts']['welded'] == 2, row
    rep = agr.edits_100('model.grid_cleanup', 'apply', pre)
    assert rep['status'] == 'pass', json.dumps(rep)[:1500]
    c = copies_of('SM_GridH_Weld_Main', '_AGR_grid_')[0]
    m_c, m_o = world_points(c), world_points(n)
    away = [p for p in m_o['verts'] if p[0] < 11.9]
    moved = [p for p in away if not any(math.dist(p, q) < 1e-6 for q in m_c['verts'])]
    assert not moved, moved[:3]
    assert len(m_c['verts']) == len(m_o['verts']) - 2
    # no selection -> skipped, nothing welded
    rt.polyop.setVertSelection(n, rt.execute('#{}'))
    rt.select(n)
    pre2 = agr.edits_100('model.grid_cleanup', 'preview', options=opts)
    assert not pre2['objects'] and 'selection' in pre2['plan']['skipped'][0]['reason'], pre2['plan']
    # no map channel 1 -> skipped, not an error
    u = build('SM_GridH_NoUV_Main', hb.facade(uv=False), (20, 0, 0))
    rt.select(u)
    pre3 = agr.edits_100('model.grid_cleanup', 'preview')
    assert not pre3['objects'] and 'channel 1' in pre3['plan']['skipped'][0]['reason'], pre3['plan']
    # empty selection -> error, never the whole scene
    rt.clearSelection()
    try:
        agr.edits_100('model.grid_cleanup', 'preview')
        raise AssertionError('empty selection accepted')
    except ValueError as exc:
        empty = str(exc)
    # actor mcp cannot apply
    rt.select(n)
    pre4 = agr.edits_100('model.grid_cleanup', 'preview', actor='mcp')
    try:
        agr.edits_100('model.grid_cleanup', 'apply', pre4, actor='mcp')
        raise AssertionError('mcp apply accepted')
    except ValueError as exc:
        assert str(exc).startswith('needs_human'), exc
    return {'welded': row['counts']['welded'], 'unselected_moved': 0, 'no_selection': pre2['plan']['skipped'],
            'no_uv': pre3['plan']['skipped'], 'empty_selection_error': empty[:120], 'mcp_apply': 'needs_human'}


def grid_cm_scene():
    reset('meters')
    n = build('SM_GridH_M_Main', hb.facade())
    rt.select(n)
    ref = agr.edits_100('model.grid_cleanup', 'preview')['plan']['rows'][0]
    reset('centimeters')
    n = build('SM_GridH_Cm_Main', hb.facade(scale=100.0))
    rt.select(n)
    pre = agr.edits_100('model.grid_cleanup', 'preview')
    got = pre['plan']['rows'][0]
    assert abs(pre['plan']['m_per_unit'] - 0.01) < 1e-12
    assert (got['counts'], got['faces'], got['tris'], got['t_vertices']) == \
        (ref['counts'], ref['faces'], ref['tris'], ref['t_vertices']), (got, ref)
    rep = agr.edits_100('model.grid_cleanup', 'apply', pre)
    assert rep['status'] == 'pass', json.dumps(rep)[:1500]
    reset('meters')
    return {'metres': ref['counts'], 'centimetres': got['counts'], 'equal': True}


GLASS = {'flat_12': 1, 'bend_30': 2, 'corner_sliver': 2, 'corner_stick': 2, 'frame_5cm': 1, 'double_film': 1,
         'package_f100': 1, 'single': 1}


def glass_all():
    reset()
    out = {}
    nodes = []
    for i, kind in enumerate(GLASS):
        nodes.append(build('SM_GlassH_{}_MainGlass'.format(kind), hb.glass(kind), (i * 5.0, 30.0, 0)))
    hashes = emax.snapshot(nodes)
    rt.select(nodes)
    pre = agr.edits_100('model.glass_planes', 'preview')
    assert not pre['plan']['ambiguous'], pre['plan']['ambiguous']
    rep = agr.edits_100('model.glass_planes', 'apply', pre)
    assert rep['status'] == 'pass', json.dumps(rep)[:2000]
    assert emax.snapshot(nodes) == hashes, 'an original changed'
    for kind, want in GLASS.items():
        name = 'SM_GlassH_{}_MainGlass'.format(kind)
        c, = copies_of(name, '_AGR_glass_')
        m = world_points(c)
        sizes = sorted({len(f['v']) for f in m['faces']})
        assert len(m['faces']) == want and sizes == [4], (kind, len(m['faces']), sizes)
        assert str(rt.getUserProp(c, 'agr_role')) == 'glass', kind
        assert m['uv'] and {f['mat'] for f in m['faces']} == {1}, kind
        out[kind] = {'faces': len(m['faces']), 'points': len(m['verts']), 'udim': glcore.udim_tiles(m)}
    row = {r['name']: r for r in pre['plan']['rows']}
    out['package_from_frame_m'] = row['SM_GlassH_package_f100_MainGlass']['glass_from_frame_m']
    rt.select(nodes[list(GLASS).index('package_f100')])  # package_f100 with place: frame -> 80 mm behind the frame face
    pre2 = agr.edits_100('model.glass_planes', 'preview', options={'place': 'frame'})
    out['package_place_frame_m'] = pre2['plan']['rows'][0]['glass_from_frame_m']
    assert out['package_place_frame_m'] == [0.08], out['package_place_frame_m']
    rt.select(nodes[list(GLASS).index('single')])  # single quad: nothing to do (PASS)
    pre3 = agr.edits_100('model.glass_planes', 'preview')
    assert pre3['status'] == 'pass', pre3
    return out


def no_new_globals():
    new = sorted(gather_globals() - GLOBALS0)
    assert not new, new[:20]
    return {'new_globals': 0}


def polygon_rows():
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as core
    cat = OUT / 'catalog.json'
    cat.write_text(json.dumps(core.load_catalog(), ensure_ascii=False), encoding='utf-8')
    os.environ['AGR_POLYGON_CATALOG'] = str(cat)
    import build_scene
    build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    rows, mism = [], []
    for button in ('model.grid_cleanup', 'model.glass_planes'):
        doc = core.load_expected(button)
        assert doc['shipped'], button
        names = [o['name'] for o in doc['objects'] if o['scene'] == 'polygon_all']
        rt.select([rt.getNodeByName(x) for x in names])
        try:
            report = agr.edits_100(doc['tool'], 'preview', None, list(rt.selection), doc.get('options'))
        except Exception as exc:  # noqa: BLE001
            report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
        bad = core.compare_report(doc['objects'], report)
        mism += bad
        got = {o['name']: sorted({f['code'] for f in o['findings']}) for o in report.get('objects', [])}
        for o in doc['objects']:
            codes = got.get(o['name'])
            rows.append({'station': doc['station'], 'button': button, 'name': o['name'], 'expect': o['expect'],
                         'codes': o['codes'], 'got': None if codes is None else ('fail' if codes else 'pass'),
                         'got_codes': codes})
    (OUT / 'polygon_rows.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
    assert not mism, mism
    return {'rows': rows, 'mismatches': 0}


check('grid_apply_m', grid_apply)
check('grid_weld_skips', grid_weld_and_skips)
check('grid_cm_scene', grid_cm_scene)
check('glass_planes', glass_all)
check('no_new_globals', no_new_globals)
check('polygon_rows', polygon_rows)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('GRID_GLASS_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native grid/glass failed: see summary.json'
