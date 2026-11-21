"""new-case: #1513 AC08 (TEC26-OKS, Контейнер НКУ) through AGR Tools stages 0..9 in an owned batch Max 2026, plus a
native D221 two-glass-ID readback on an EXPLICITLY SYNTHETIC fixture (AC08 has no glass:
jobs/TEC26-OKS/AC08/materials.json glass.observed=false).

Derived from tests/max_tools/run_agr_tools_kpp1_e2e_native.py (#1024): same press()/receipt machinery, but the source
is the REAL AC08 geometry: a scratch copy of G:/Мой диск/AGR-assets/tec26/ac08/source/AC08_source_geomfinal.fbx
(env AC08_FBX; node `АС.08` + `Colizii_044`). Nothing is built or repaired by the harness. Face ids of the source are
local (1/2/3); the harness maps ONLY the evidenced ones to library ids (2 -> 11 panel_ribbed_ral5015, 3 -> 2
paint_ral7004: jobs/TEC26-OKS/AC08/materials.json + PILOT_REPORT v010 legend) and puts the unresolved mixed id 1
(roof + frame + skirt, materials.json status unresolved_mixed_id, awaiting Artem) on the sentinel 999 that is NOT in
the library, so every library-dependent button must name it (no default, no first entry). An unmapped source id is an
error naming it.

Env: AGR_TEST_OUTPUT (a NEW directory), AGR_TEST_PACKAGE (the built MZP, installed into OUT), AGR_TOOLS_REPO, AC08_FBX,
AGR_PYTHON. A refusal / failure of a button is RECORDED, never hidden; non-zero exit only on harness errors.
Writes OUT/summary.json, OUT/table.md, OUT/d221.json, OUT/readback.json and scenes under OUT/scenes.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

from pymxs import runtime as rt

ROOT = Path(os.environ.get('AGR_TOOLS_REPO') or Path(__file__).resolve().parents[2])
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
os.environ['AGR_TOOLS_REPO'] = str(ROOT)
REPORTS = OUT / 'reports'
REPORTS.mkdir()
summary = {'case': 'AC08 AGR Tools stages 0-9 (#1513)', 'model': 'REAL AC08 (TEC26-OKS) AC08_source_geomfinal.fbx',
           'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'stages': [], 'harness_errors': [], 'harness_steps': []}
assert not rt.maxFileName, 'only an empty batch document is allowed'


FBX = Path(os.environ['AC08_FBX'])
ADDRESS = 'Nku_1'   # the address of the AC08 v010 package (SM_Nku_1.zip); qa.names: digits after '_'
STEM = 'SM_' + ADDRESS
ID_MAP = {1: 999, 2: 11, 3: 2}   # source face id -> library id; 999 = unresolved (NOT in the library)
# DIAGNOSTIC ONLY (never an acceptance run): AC08_ID1_DIAG=<library id> replaces the sentinel of source id 1 to show
# whether a later refusal depends on the unresolved material; the run is labelled diagnostic in summary/table.
DIAG_ID1 = os.environ.get('AC08_ID1_DIAG')
if DIAG_ID1:
    ID_MAP[1] = int(DIAG_ID1)
    summary['diagnostic'] = 'DIAGNOSTIC: source id 1 -> library {} (not a decision, not acceptance)'.format(DIAG_ID1)
ID_UNRESOLVED = 999
GLASS_IDS = []                   # AC08: no glazing evidenced (materials.json glass.observed=false)
LEVELS = []                      # filled from the source: L1 = 0.0 (+-0.000), roof = top of the body


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


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
summary['runtime_version'] = agr.VERSION
assert agr.VERSION == os.environ.get('AGR_EXPECT_VERSION', '1.1.0'), agr.VERSION
NC = agr._load_core('npm_core.py', 'agr_tools_npm_core_ac08')
roadmap = agr._load_core('roadmap.py', 'agr_tools_roadmap_ac08')

SUITE = roadmap.load_file(str(OUT / 'installed' / 'agr-tools-suite.json'))
STAGE_ROWS = {s['id']: list(s['rows']) for s in SUITE['stages']}

# library copy (K5: read from a copy): <copy>/library/materials + <copy>/tools/materials/ral_classic.json
LIBCOPY = OUT / 'libcopy'
shutil.copytree(ROOT / 'library' / 'materials', LIBCOPY / 'library' / 'materials')
(LIBCOPY / 'tools' / 'materials').mkdir(parents=True)
shutil.copy2(ROOT / 'tools' / 'materials' / 'ral_classic.json', LIBCOPY / 'tools' / 'materials' / 'ral_classic.json')
LIB = str(LIBCOPY / 'library' / 'materials' / 'materials.json')
S = {}   # pipeline state: nodes and paths handed from stage to stage


# ---- helpers ---------------------------------------------------------------------------------------------------
def valid(nodes):
    out, seen = [], set()
    for n in nodes or ():
        if n is not None and rt.isValidNode(n):
            h = int(rt.getHandleByAnim(n))
            if h not in seen:
                seen.add(h)
                out.append(n)
    return out


def names(nodes):
    return [str(n.name) for n in valid(nodes)]


def tris(n):
    try:
        if rt.superClassOf(n) != rt.GeometryClass or not rt.canConvertTo(n, rt.TriMeshGeometry):
            return None
        m = rt.snapshotAsMesh(n)
    except Exception:  # noqa: BLE001 - targets, helpers
        return None
    try:
        return int(m.numfaces)
    finally:
        rt.delete(m)


def census():
    vis = tot = 0
    by = {}
    for n in list(rt.objects):
        c = tris(n)
        if c is None:
            continue
        h = int(rt.getHandleByAnim(n))
        by[h] = c
        tot += c
        if not bool(n.isHidden):
            vis += c
    return vis, tot, by


def first_line(exc):
    return '{}: {}'.format(type(exc).__name__, (str(exc).splitlines() or [''])[0][:300])


def classify(exc):
    return 'refused' if isinstance(exc, (ValueError, FileExistsError, PermissionError)) else 'error'


def codes_of(rep):
    out = {}
    for o in (rep or {}).get('objects') or ():
        for f in o.get('findings') or ():
            out[f.get('code')] = out.get(f.get('code'), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def report_status(rep):
    s = rep.get('status')
    plan = rep.get('plan') if isinstance(rep.get('plan'), dict) else {}
    amb = plan.get('ambiguous') or []
    if s == 'not_implemented':
        return 'not_implemented'
    if s == 'pass':
        return 'ambiguous' if amb else 'done'
    if s == 'fail':
        return 'ambiguous' if amb else 'findings'
    return 'error'


PLAN_KEYS = ('counts', 'copies', 'out_dir', 'out', 'written', 'results', 'objects_in', 'objects_out', 'moved',
             'found', 'slabs', 'capsules', 'drafts', 'rejected', 'run_folder', 'blockers', 'stage_entry', 'stem',
             'target', 'readback', 'renumber', 'steps', 'classes', 'source', 'normalization', 'action', 'sha256',
             'table', 'files', 'summary', 'agent_requests', 'udim_table', 'notes', 'passport', 'manifest', 'rows')


def brief(rep):
    plan = rep.get('plan') if isinstance(rep.get('plan'), dict) else {}
    out = {'status': report_status(rep), 'report_status': rep.get('status'), 'objects': len(rep.get('objects') or ()),
           'codes': codes_of(rep), 'done': len(plan.get('done') or ()), 'skipped': len(plan.get('skipped') or ()),
           'ambiguous': [str(a)[:240] for a in (plan.get('ambiguous') or ())[:4]],
           'skipped_first': [str(a)[:200] for a in (plan.get('skipped') or ())[:3]],
           'done_first': [str(a)[:160] for a in (plan.get('done') or ())[:4]]}
    extract = {}
    for k in PLAN_KEYS:
        if k in plan:
            text = json.dumps(plan[k], ensure_ascii=False, default=str)
            extract[k] = plan[k] if len(text) <= 1200 else text[:1200] + ' ...'
    out['plan'] = extract
    return out


_dump_n = [0]


def dump(tool, mode, rep):
    _dump_n[0] += 1
    p = REPORTS / '{:03d}_{}_{}.json'.format(_dump_n[0], tool.replace('.', '_'), mode)
    try:
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    except Exception as exc:  # noqa: BLE001 - evidence only
        p.write_text(json.dumps({'unserialisable': first_line(exc)}), encoding='utf-8')
    return p.name


def press(st, tool, nodes=None, options=None, apply=True, why=None, label=None, api='100'):
    """preview -> apply of one button (actor panel; 1.0 rows, or a released 0.8 row with api='080'); every
    outcome is a row of the stage."""
    edits = {'100': agr.edits_100, '080': agr.edits_080}[api]
    read = {'100': agr.READ_100, '080': agr.READ_080}[api]
    row = {'tool': label or tool, 'nodes': names(nodes) if nodes is not None else None,
           'options': sorted(options) if options else []}
    t0 = time.perf_counter()
    nodes = valid(nodes) if nodes is not None else None
    if nodes:
        rt.select(nodes)
    pre = app = None
    try:
        pre = edits(tool, 'preview', None, nodes, options)
        row['preview'] = brief(pre)
        row['preview']['file'] = dump(tool, 'preview', pre)
    except Exception as exc:  # noqa: BLE001 - a refusal is the evidence
        row['preview'] = {'status': classify(exc), 'error': first_line(exc)}
    if pre is None:
        row['status'] = row['preview']['status']
    elif tool in read:
        row['apply'] = {'status': 'n/a', 'reason': 'read row: preview only'}
        row['status'] = row['preview']['status']
    elif pre.get('status') == 'not_implemented':
        row['status'] = 'not_implemented'
    elif not apply:
        row['apply'] = {'status': 'skipped', 'reason': why or ''}
        row['status'] = row['preview']['status']
        row['note'] = 'apply не нажат: ' + (why or '')
    else:
        if nodes:
            rt.select(nodes)
        try:
            app = edits(tool, 'apply', pre, nodes)
            row['apply'] = brief(app)
            row['apply']['file'] = dump(tool, 'apply', app)
            row['status'] = row['apply']['status']
        except Exception as exc:  # noqa: BLE001
            row['apply'] = {'status': classify(exc), 'error': first_line(exc)}
            row['status'] = row['apply']['status']
    row['seconds'] = round(time.perf_counter() - t0, 2)
    st['buttons'].append(row)
    print('AC08_E2E', st['id'], row['tool'], row['status'], row['seconds'], 's')
    return pre, app


def names_of_materials(node):
    m = node.material
    if m is None:
        return []
    out = [str(m.name)]
    try:
        out += [str(x.name) for x in m.materialList if x is not None]
    except Exception:  # noqa: BLE001 - not a Multi/Sub
        pass
    return out


def harness_step(st, text):
    st.setdefault('harness_steps', []).append(text)
    summary['harness_steps'].append('этап {}: {}'.format(st['id'], text))


def run_stage(sid, title, fn):
    st = {'id': sid, 'title': title, 'rows': STAGE_ROWS.get(sid, []), 'big': (STAGE_ROWS.get(sid) or [None])[0],
          'buttons': [], 'notes': []}
    _v, _t, before = census()
    t0 = time.perf_counter()
    try:
        fn(st)
    except Exception:  # noqa: BLE001 - a harness error: recorded, the run fails at the end
        tb = traceback.format_exc()[-3000:]
        st['harness_error'] = tb
        summary['harness_errors'].append('stage {}: {}'.format(sid, tb.splitlines()[-1][:300]))
    st['seconds'] = round(time.perf_counter() - t0, 2)
    vis, tot, after = census()
    st['tris_visible'], st['tris_total'] = vis, tot
    new = [h for h in after if h not in before]
    st['new_geometry_nodes'] = len(new)
    st['tris_new'] = sum(after[h] for h in new)
    big = next((b for b in st['buttons'] if b['tool'] == st['big']), None)
    st['status'] = 'harness_error' if 'harness_error' in st else (big['status'] if big else 'skipped')
    summary['stages'].append(st)
    write_outputs()


def fill_multi(mm, subs, ids):
    rt.execute('(fn f mm subs ids = (for i = 1 to subs.count do (mm.materialList[i] = subs[i]; '
               'mm.materialIDList[i] = ids[i]); ok); f)')(mm, subs, ids)




def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def node_facts(n):
    """Independent facts of one node: topology, material ids, UV channel 1 tiles per material id, transform."""
    import math
    m = rt.snapshotAsMesh(n)
    try:
        nf, nv = int(m.numfaces), int(m.numverts)
        ids = {}
        for f in range(1, nf + 1):
            i = int(rt.getFaceMatID(m, f))
            ids[i] = ids.get(i, 0) + 1
        uv = None
        if rt.meshop.getMapSupport(m, 1):
            us, vs, tiles, bad = [], [], {}, 0
            for f in range(1, nf + 1):
                face = rt.meshop.getMapFace(m, 1, f)
                pts = [rt.meshop.getMapVert(m, 1, int(face[k])) for k in range(3)]
                cu = sum(float(p.x) for p in pts) / 3.0
                cv = sum(float(p.y) for p in pts) / 3.0
                if not (math.isfinite(cu) and math.isfinite(cv)):
                    bad += 1
                    continue
                t = 1001 + int(math.floor(cu)) + 10 * int(math.floor(cv))
                key = '{}:{}'.format(int(rt.getFaceMatID(m, f)), t)
                tiles[key] = tiles.get(key, 0) + 1
                for p in pts:
                    us.append(float(p.x))
                    vs.append(float(p.y))
            uv = {'map_verts': int(rt.meshop.getNumMapVerts(m, 1)), 'u': [min(us), max(us)] if us else None,
                  'v': [min(vs), max(vs)] if vs else None, 'matid_tile_faces': tiles, 'nonfinite_faces': bad}
    finally:
        rt.delete(m)
    return {'name': str(n.name), 'class': str(rt.classOf(n)), 'faces_tri': nf, 'verts': nv, 'mat_ids': ids, 'uv1': uv,
            'pos': [round(float(c), 5) for c in (n.pos.x, n.pos.y, n.pos.z)],
            'rotation_quat': [round(float(c), 6) for c in (n.rotation.x, n.rotation.y, n.rotation.z, n.rotation.w)],
            'scale': [round(float(c), 6) for c in (n.scale.x, n.scale.y, n.scale.z)],
            'bbox_m': [[round(float(c), 4) for c in (n.min.x, n.min.y, n.min.z)],
                       [round(float(c), 4) for c in (n.max.x, n.max.y, n.max.z)]],
            'material': str(n.material.name) if n.material is not None else None, 'id_sub_names': sub_names(n, ids)}


def sub_names(n, ids):
    """{face id: sub-material name} of a Multi/Sub (FBX import renumbers ids; the sub name carries the source id)."""
    m = n.material
    if m is None or rt.classOf(m) != rt.MultiMaterial:
        return None
    out = {}
    lst, idl = list(m.materialList), list(m.materialIDList)
    for i in ids:
        sub = next((lst[k] for k in range(len(idl)) if int(idl[k]) == i), None)
        out[i] = str(sub.name) if sub is not None else None
    return out


def build_source():
    """Import the scratch copy of the real AC08 FBX into the empty metre scene; map face ids (ID_MAP)."""
    import pymxs
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0
    summary['source_fbx'] = {'path': str(FBX), 'sha256': sha(FBX), 'bytes': FBX.stat().st_size}
    before = set(int(rt.getHandleByAnim(n)) for n in rt.objects)
    rt.FBXImporterSetParam('ScaleConversion', False)
    ok = rt.importFile(str(FBX), rt.name('noPrompt'), using=rt.FBXIMP)
    assert ok, 'FBX import failed: ' + str(FBX)
    nodes = [n for n in rt.objects if int(rt.getHandleByAnim(n)) not in before and tris(n) is not None]
    summary['source_import'] = [node_facts(n) for n in nodes]
    body = [n for n in nodes if not str(n.name).lower().startswith(('colizii', 'ucx'))]
    coll = [n for n in nodes if n not in body]
    assert len(body) == 1, 'expected ONE AC08 body node, got {}'.format(names(body))
    b = body[0]
    rt.convertToPoly(b)
    seen = {}
    with pymxs.undo(False):
        for f in range(1, int(rt.polyop.getNumFaces(b)) + 1):
            i = int(rt.polyop.getFaceMatID(b, f))
            if i not in ID_MAP:
                raise ValueError('unmapped source face id {} on {} (no default)'.format(i, b.name))
            rt.polyop.setFaceMatID(b, f, ID_MAP[i])
            seen[i] = seen.get(i, 0) + 1
    summary['id_map'] = {'map': {str(k): v for k, v in ID_MAP.items()}, 'faces_by_source_id': seen,
                         'unresolved_sentinel': ID_UNRESOLVED,
                         'note': 'id 1 = roof+frame+skirt, unresolved_mixed_id (materials.json): sentinel 999, not a guess'}
    LEVELS[:] = [{'name': 'L1', 'z_m': 0.0}, {'name': 'roof', 'z_m': round(float(b.max.z), 4)}]
    for c in coll:
        c.isHidden = True
    S['src'] = [b]
    S['facade'] = S['parapet'] = b
    summary['source'] = {'body': str(b.name), 'collision_hidden': names(coll), 'levels': list(LEVELS),
                         'tris': tris(b), 'scene_units': 'm'}
    scene = OUT / 'scenes' / 'AC08_stage_input.max'
    scene.parent.mkdir(parents=True, exist_ok=True)
    assert rt.saveMaxFile(str(scene), quiet=True), scene
    summary['scene'] = str(scene)
    summary['scene_input_sha256'] = sha(scene)



def box_uv(node):
    rt.addModifier(node, rt.Uvwmap(maptype=4))
    rt.collapseStack(node)

# ---- stages -------------------------------------------------------------------------------------------------------

def stage0(st):
    root = OUT / 'proj'
    pre, app = press(st, 'project.passport', None, {'root': str(root), 'project_id': 'TEC26-OKS',
                                                     'title': 'ТЭЦ-26 ОКС, АС.08 Контейнер НКУ (AC08)'})
    pp = root / 'jobs' / 'TEC26-OKS' / 'passport.json'
    S['passport'] = str(pp) if pp.is_file() else None
    st['notes'].append('паспорт: ' + (S['passport'] or 'не записан'))
    pre, app = press(st, 'source.intake', S['src'], {'source_path': str(FBX)})
    if app is not None:
        cmap = {}
        for nm in app['plan'].get('readback', {}).get('copies', []):
            c = rt.getNodeByName(nm)
            if c is not None:
                cmap[str(rt.getUserProp(c, 'agr_intake_source'))] = c
        b = cmap.get(str(S['facade'].name))
        if b is not None:
            S['facade'] = S['parapet'] = b
            for n in S['src']:
                n.isHidden = True
            harness_step(st, 'исходник скрыт после source.intake; дальше работает копия ' + str(b.name))
        st['notes'].append('readback копий: ' + json.dumps(app['plan'].get('readback', {}).get('size_m')))
        origin = (app['plan'].get('normalization') or {}).get('origin_m')
        if origin:
            # the source +-0.000 is z=0 of the FBX; source.intake moved the copy by -origin_m
            S['zero_m'] = round(-float(origin[2]), 4)
            LEVELS[:] = [dict(lv, z_m=round(lv['z_m'] - float(origin[2]), 4)) for lv in LEVELS]
            summary['source']['levels_after_intake'] = list(LEVELS)
            summary['source']['zero_m_after_intake'] = S['zero_m']
            harness_step(st, 'source.intake сдвинул копию на -origin_m {}: +-0.000 = {} м, уровни {}'.format(
                origin, S['zero_m'], LEVELS))
    else:
        st['notes'].append('source.intake не применён: дальше работает импортированный исходник')
    press(st, 'scene.source_class', [S['facade']])


def bodies():
    return valid([S.get('facade'), S.get('parapet')])


def stage1(st):
    press(st, 'body.prepare', bodies(), {'levels': LEVELS})
    before = bodies()
    pre, app = press(st, 'model.attach_by_material', before, None)
    if app is not None:
        res = valid([rt.getNodeByName(x['name']) for x in app['plan'].get('results') or ()])
        if len(res) == 1:
            S['facade'] = S['parapet'] = res[0]
            st['notes'].append('attach: фасад и парапет стали одним телом ' + str(res[0].name))
        elif res:
            S['parapet'] = max(res, key=lambda n: float(n.min.z))
            S['facade'] = min(res, key=lambda n: float(n.min.z))
            st['notes'].append('attach (split): {} тел - {}'.format(len(res), names(res)))
    press(st, 'model.move_apart', bodies(), None)
    press(st, 'model.grid_cleanup', [S['facade']], None)
    press(st, 'scene.small_parts', bodies() + valid(S.get('bolts')), None)


def by_prefix(prefix, geometry=None):
    out = []
    for n in list(rt.objects):
        if str(n.name).startswith(prefix):
            if geometry is True and tris(n) is None:
                continue
            out.append(n)
    return sorted(out, key=lambda n: str(n.name))


def stage2(st):
    press(st, 'win.place', [S['facade']], {'drafts_dir': str(OUT / 'win_drafts')})
    wins = [n for n in by_prefix('WIN_') if not str(n.name).startswith('WINLIB_')]
    per = {}
    for w in wins:
        t = str(rt.getUserProp(w, 'agr_window_type'))
        per[t] = per.get(t, 0) + 1
    st['windows'] = {'placed': len(wins), 'by_type': per, 'markers': len(by_prefix('OPEN_')),
                     'glass': len(by_prefix('GLASS_', True)), 'masters': len(by_prefix('WINLIB_'))}
    markers = [n for n in by_prefix('OPEN_') if rt.getUserProp(n, 'agr_window_type') is not None]
    if markers:
        press(st, 'win.generate', markers, {'out': str(OUT / 'win_generate')})
    else:
        st['buttons'].append({'tool': 'win.generate', 'status': 'skipped', 'seconds': 0.0,
                              'note': 'нет маркеров OPEN_ с agr_window_type после win.place'})
    glass = by_prefix('GLASS_', True)
    if glass:
        press(st, 'model.glass_planes', glass, None)
    else:
        st['buttons'].append({'tool': 'model.glass_planes', 'status': 'skipped', 'seconds': 0.0,
                              'note': 'нет объектов GLASS_ после win.place'})


def stage3(st):
    press(st, 'body.capsules', [S['facade']], None)
    st['capsules'] = len(by_prefix('CAPSULE_', True))


def stage4(st):
    pre, app = press(st, 'body.roof', [S['parapet']], None)
    if app is not None:
        slabs = valid([rt.getAnimByHandle(int(s['handle'])) for s in app['plan'].get('slabs') or ()])
        S['slab'] = slabs[0] if slabs else None
        st['notes'].append('плита: {}'.format(names(slabs)))
        if slabs:
            st['roof_z_m'] = [round(float(slabs[0].min.z), 4), round(float(slabs[0].max.z), 4)]


def model_set():
    return valid([S.get('facade'), S.get('parapet'), S.get('slab')])


def stage5(st):
    press(st, 'mat.table', model_set(), {'library': LIB})
    press(st, 'mat.tiles', model_set(), {'out_dir': str(OUT / 'tiles'), 'library': LIB})
    if (OUT / 'tiles').is_dir():
        press(st, 'tex.plug_colour', None, {'folder': str(OUT / 'tiles')})
    else:
        st['buttons'].append({'tool': 'tex.plug_colour', 'status': 'skipped', 'seconds': 0.0,
                              'note': 'нет папки карт mat.tiles: на модели нет растровых заглушек'})


def stage6(st):
    parts = model_set()
    if len(parts) > 1:
        pre, app = press(st, 'model.attach_by_material', parts, None,
                         label='model.attach_by_material (подготовка ВПМ: один Main)')
        res = valid([rt.getNodeByName(x['name']) for x in (app or {}).get('plan', {}).get('results') or ()])
        if res:
            parts = res
    S['main'] = parts[0] if len(parts) == 1 else max(parts, key=lambda n: tris(n) or 0)
    if len(parts) > 1:
        st['notes'].append('в ВПМ идёт только {}: тела не слились в один Main ({})'.format(S['main'].name,
                                                                                       names(parts)))
    pre, app = press(st, 'vpm.build', [S['main']], {'glass_ids': GLASS_IDS, 'out_dir': str(OUT / 'vpm'),
                                                    'library_path': LIB, 'address': ADDRESS,
                                                    'map_dir': str(OUT / 'tiles')})
    if app is None:
        # run 20261106-071804-147131cc: with library_path the apply refuses (step 6, maps); the build itself is
        # pressed again without the maps so the later stages work on a real VPM copy (recorded as its own row)
        pre, app = press(st, 'vpm.build', [S['main']], {'glass_ids': GLASS_IDS, 'out_dir': str(OUT / 'vpm_nomaps')},
                         label='vpm.build (повтор без library_path: шаг 6 карт выключен)')
        if app is not None:
            st['notes'].append('vpm.build с library_path отказал; ВПМ собран повтором без карт D+ERM+N')
    S['vpm_copies'], S['vpm_body'], S['vpm_table'], S['vpm_dmaps'] = [], None, None, []
    if app is not None:
        copies = valid([rt.getNodeByName(c) for c in app['plan'].get('copies') or ()])
        S['vpm_copies'] = copies
        body = [c for c in copies if '_glass_' not in str(c.name)]
        S['vpm_body'] = body[0] if body else None
        for f in app['plan'].get('files') or ():
            if f.get('kind') == 'udim_table':
                S['vpm_table'] = f['path']
            elif f.get('kind') == 'map_D' or 'diffuse' in str(f.get('kind', '')).lower():
                S['vpm_dmaps'].append(f['path'])
        st['vpm'] = {'copies': names(copies), 'maps': len(app['plan'].get('files') or ()) - 1,
                     'diffuse_maps': len(S['vpm_dmaps']), 'out_dir': app['plan'].get('out_dir'),
                     'tris': {str(c.name): tris(c) for c in copies}, 'source_tris': tris(S['main']),
                     'udim': [{k: r.get(k) for k in ('object', 'part', 'tiles', 'udim_table')}
                              for r in app['plan'].get('done') or ()][:4]}
    vb = valid([S.get('vpm_body')])
    if not vb:
        st['notes'].append('нет копии ВПМ: малые кнопки этапа 6 нажаты на рабочем теле')
        vb = [S['main']]
    press(st, 'udim.rescale', vb, None, apply=False,
          why='тексель уже задан vpm.build (шаг 2); apply сделал бы лишнюю копию')
    press(st, 'udim.distortion', vb, None)
    if S['vpm_dmaps']:
        press(st, 'tex.dilate', None, {'files': S['vpm_dmaps'], 'out': str(OUT / 'dilate')})
        st['notes'].append('tex.dilate: карты vpm.build заливают весь тайл (сплошной цвет или бесшовная маска) - '
                           'фона для расширения нет, находка dilate_no_mask ожидаема')
    else:
        st['buttons'].append({'tool': 'tex.dilate', 'status': 'skipped', 'seconds': 0.0,
                              'note': 'vpm.build не записал диффузы (шаг 6 карт): нечего расширять'})
    # udim.plugs: only the placeholder materials (library recipe `solid`) get a plug island; the tile of each id is
    # the dense tile of the copy (agr_udim_table written by vpm.build, 1.0.1)
    lib = agr._load_core('matlib_core.py', 'agr_tools_matlib_core_kpp1').load_library(LIB)
    table = {}
    try:
        table = json.loads(str(rt.getUserProp(vb[0], 'agr_udim_table') or '{}'))
    except ValueError:
        pass
    def kind(rec):
        r = (rec or {}).get('recipe')
        return r.get('kind') if isinstance(r, dict) else r
    solid = sorted(int(k) for k in table if kind(lib['by_id'].get(int(k))) == 'solid')
    st['plug_ids'] = {'udim_table': table, 'solid': solid}
    if solid:
        pre, app = press(st, 'udim.plugs', vb, {'matids': solid})
        plugged = valid([rt.getNodeByName(c) for c in (app or {}).get('plan', {}).get('copies') or ()])
        if plugged:
            S['vpm_plugged'] = plugged[0]
            st['notes'].append('udim.plugs: копия с заглушками {} (id {})'.format(plugged[0].name, solid))
    else:
        st['buttons'].append({'tool': 'udim.plugs', 'status': 'skipped', 'seconds': 0.0,
                              'note': 'на копии ВПМ нет id с рецептом solid (заглушки не нужны): {}'.format(table)})


def stage7(st):
    copies = valid(S.get('vpm_copies'))
    if not copies:
        copies = valid([S.get('main')])
        st['notes'].append('нет копий ВПМ: npm.build нажат на рабочем теле')
    opts = {'out_dir': str(OUT / 'npm'), 'name': STEM + '_001_Main', 'glass_ids': GLASS_IDS}
    if S.get('vpm_table'):
        table = json.loads(Path(S['vpm_table']).read_text(encoding='ascii'))
        opts['udim_table'] = NC.udim_table_of(table, names(copies))
    pre, app = press(st, 'npm.build', copies, opts)
    if app is not None:
        S['npm'] = valid([rt.getNodeByName(c) for c in app['plan'].get('copies') or ()])
        rows = []
        for f in app['plan'].get('files') or ():
            if f.get('kind') == 'table':
                S['npm_table_path'] = f['path']
                try:
                    rows = json.loads(Path(f['path']).read_text(encoding='ascii'))['table']
                except Exception as exc:  # noqa: BLE001
                    st['notes'].append('npm_table.json не прочитан: ' + first_line(exc))
            if f.get('kind') == 'diffuse':
                st['npm_atlas_px'] = f.get('size')
        kinds = {}
        for r in rows:
            kinds[r.get('kind')] = kinds.get(r.get('kind'), 0) + 1
        st['npm_table_kinds'] = kinds
        st['npm_tris'] = {str(n.name): tris(n) for n in S['npm']}
        st['npm_row_sample'] = [{k: r.get(k) for k in ('library_id', 'kind', 'udim', 'udim_source', 'color', 'material')}
                                for r in rows[:3]]
    # strip period of the AC08 ribbed panels: ~0.20 m (D169, 30/12 ribs per field)
    press(st, 'atlas.facade_strip', valid([S.get('vpm_body')]) or valid([S.get('main')]),
          {'out_dir': str(OUT / 'facade_strip'), 'period_by_id': {'11': [0.2, 0.2]}})


def stage8(st):
    """Stage 8 (branch Q #1085, released in 1.0.0): the NPM of stage 7 back to a VPM by the npm.build table, then
    UDIM -> ID (read) on the copies it made."""
    opts = {'table': S['npm_table_path']} if S.get('npm_table_path') else None
    if opts is None:
        st['notes'].append('нет npm_table.json от npm.build: npm.to_vpm без таблицы (регионы атласа)')
    pre, app = press(st, 'npm.to_vpm', valid(S.get('npm')) or valid([S.get('vpm_body')]), opts)
    copies = []
    for c in ((app or {}).get('plan', {}).get('copies') or ()):   # [[{copy, part, ...}]] per source object
        for x in (c if isinstance(c, list) else [c]):
            copies.append(x.get('copy') if isinstance(x, dict) else x)
    back = valid([rt.getNodeByName(c) for c in copies if c]) if app else []
    if back:
        st['notes'].append('ВПМ из НПМ: ' + ', '.join(names(back)))
    press(st, 'udim.udims_to_ids', back or valid([S.get('vpm_body')]) or valid([S.get('main')]), None)


def stage9(st):
    work = (valid([S.get('vpm_plugged')]) or valid([S.get('vpm_body')]) or valid([S.get('main')]))[0]
    target = STEM + '_Main'
    # qa.names_fix (0.8) names a copy by the ROLE token of the working name (V7): the vpm.build copy is called
    # <source>_VPM_NNN (no role token), so the artist gives it a working name ending in _Main first
    old = str(work.name)
    work.name = ADDRESS + '_VPM_Main'
    harness_step(st, 'рабочее имя копии ВПМ {} -> {} (токен роли Main для qa.names_fix: vpm.build называет копию '
                     '<источник>_VPM_NNN)'.format(old, work.name))
    press(st, 'qa.names_fix', [work], {'model': 'vpm', 'address': ADDRESS}, api='080')
    named = valid([rt.getNodeByName(target)])
    main = named[0] if named else work
    if not named:
        main.name = target
        harness_step(st, 'qa.names_fix не дал {}: ручное переименование {} -> {}'.format(target, work.name, target))
    else:
        work.isHidden = True
        harness_step(st, 'рабочая копия ВПМ {} скрыта: сдаётся копия qa.names_fix {}'.format(work.name, target))
    S['deliver_main'] = main
    st['materials'] = names_of_materials(main)
    # UCX: the 0.8 builder (runtime.ucx_preview / ucx_apply) - pack.deliver has no ucx.build step
    ucx_row = {'tool': 'ucx (0.8 runtime.ucx_preview/ucx_apply)', 'nodes': [str(main.name)]}
    t0 = time.perf_counter()
    created = []
    try:
        up = agr.ucx_preview([main])
        ucx_row['preview'] = {'status': report_status(up['report']), 'codes': codes_of(up['report'])}
        created, _rep = agr.ucx_apply([main], up)
        created = valid(created)
        ucx_row['status'] = 'done'
        ucx_row['created'] = names(created)[:12]
    except Exception as exc:  # noqa: BLE001
        ucx_row['status'] = classify(exc)
        ucx_row['error'] = first_line(exc)
    ucx_row['seconds'] = round(time.perf_counter() - t0, 2)
    st['buttons'].append(ucx_row)
    ucx = [n for n in created if str(n.name).upper().startswith('UCX_')]
    st['ucx_pieces'] = len(ucx)
    if ucx:
        # 0.8 ucx.rename: the builder names pieces after its export copy (UCX_<name>_AGR_ucx__NN), the VPM mask is
        # UCX_SM_<Address>_Main_NNN (1.0.1: ucx.rename reads the builder pieces)
        press(st, 'ucx.rename', ucx, None, api='080')
        import re
        mask = re.compile(r'^UCX_' + re.escape(STEM) + r'_Main_\d{3}$')
        if not all(mask.match(str(n.name)) for n in valid(ucx)):
            old = names(ucx)
            for i, n in enumerate(sorted(valid(ucx), key=lambda n: str(n.name)), 1):
                n.name = 'UCX_{}_Main_{:03d}'.format(STEM, i)
            harness_step(st, 'ручное переименование {} UCX {}.. -> UCX_{}_Main_NNN (ucx.rename их не '
                             'переименовал)'.format(len(old), old[0], STEM))
    S['ucx'] = ucx
    st['ucx_names_first'] = names(ucx)[:3]
    if ucx:
        press(st, 'ucx.gap', ucx, None)
        press(st, 'ucx.stairs', ucx, None)
    else:
        for t in ('ucx.gap', 'ucx.stairs'):
            st['buttons'].append({'tool': t, 'status': 'skipped', 'seconds': 0.0, 'note': 'нет UCX'})
    lp, la = press(st, 'light.export', None, {'folder': str(OUT / 'light')})
    light_ok = la is not None and la.get('status') == 'pass'
    press(st, 'qa.omk_te', [main], None)
    model = valid([main] + ucx)
    common = {'stem': STEM}
    if S.get('passport'):
        common['passport'] = S['passport']
    # artist inputs that no 1.0 button sets (project data, not geometry): the FBX path of the delivery
    # (AGR_EXPORT_PATH, read by every 0.5-0.9 check), the +-0.000 of the building (AGR_ZERO_M, no default) and the
    # delivered nodes on layer 0 (qa.scene_hygiene; vpm.build / qa.names_fix make copies on their own layers)
    fbx_path = str(OUT / 'deliver_B' / (STEM + '.fbx')).replace(chr(92), '/')
    for n in model:
        rt.setUserProp(n, 'AGR_EXPORT_PATH', fbx_path)
    zero = '{:.4f}'.format(S.get('zero_m', 0.0))
    rt.setUserProp(main, 'AGR_ZERO_M', zero)
    layer0 = rt.LayerManager.getLayer(0)
    moved = [str(n.name) for n in model if str(n.layer.name) != '0']
    for n in model:
        layer0.addNode(n)
    harness_step(st, 'вход художника: AGR_EXPORT_PATH={} на {} узлах, AGR_ZERO_M={} на {} (+-0.000 исходника после сдвига '
                     'source.intake; ни одна кнопка 1.0 их не задаёт)'.format(fbx_path, len(model), zero, main.name))
    harness_step(st, 'вход художника: {} узлов перенесены на слой «0» (qa.scene_hygiene hyg_layer)'.format(len(moved)))
    # A: honest full run, nothing skipped
    rt.select(model)
    (OUT / 'deliver_A').mkdir()
    pa, aa = press(st, 'pack.deliver', model, dict(common, folder=str(OUT / 'deliver_A')),
                   label='pack.deliver')
    # B: the steps without an input of this synthetic model skipped with the reason (never a pass)
    # diagnostic (not a button): the gates of export.checked on the model, to name the cleanup finding
    try:
        ep = agr.export_preview(nodes=model, target=fbx_path)
        plan = ep.get('plan') or {}
        st['export_checked_diag'] = {'status': ep.get('status'), 'gates': plan.get('gates'),
                                     'dropped': (plan.get('dropped') or [])[:5], 'stopped': plan.get('stopped'),
                                     'first_findings': [(o.get('name'), [(f.get('code'), str(f.get('detail'))[:300])
                                                                         for f in (o.get('findings') or ())[:3]])
                                                        for o in (ep.get('objects') or ())[:2]]}
    except Exception as exc:  # noqa: BLE001
        st['export_checked_diag'] = {'error': first_line(exc)}
    skip = {'qa.sintez': 'SINTEZ AGR Checker (Blender-расширение) в этом прогоне не запускается: отчёта нет',
            'qa.omk_te': 'нет таблицы ОМК ТЭ объекта AC08 (options.table)'}
    pre_a = (aa or pa or {}).get('plan', {}).get('steps') or ()
    if any(r.get('id') == 'qa.preflight' and r.get('status') != 'pass' for r in pre_a):
        skip['qa.preflight'] = 'находки qa.preflight - в прогоне A (см. его шаги)'
    if not light_ok:
        skip['light.export'] = 'light.export не дал файла (в сцене AC08 нет источников света)'
        skip['light.check'] = 'в сцене AC08 нет источников света: пустой набор - ошибка light.check'
    rt.select(model)
    (OUT / 'deliver_B').mkdir()
    pb, ab = press(st, 'pack.deliver', model, dict(common, folder=str(OUT / 'deliver_B'), skip=skip),
                   label='pack.deliver (B: skip {})'.format(', '.join(sorted(skip))))
    S['deliver'] = {'A': aa, 'B': ab}
    fbx = None
    for rep in (ab, aa):
        if rep and rep.get('plan', {}).get('run_folder'):
            cand = Path(rep['plan']['run_folder']) / (STEM + '.fbx')
            if cand.is_file():
                fbx = str(cand)
                break
    po = {'passport': S['passport']} if S.get('passport') else {}
    if fbx:
        po['fbx'] = fbx
    press(st, 'export.place_by_passport', [main], po or None)
    st['deliver'] = {}
    for key, rep in (('A', aa), ('B', ab)):
        if rep is None:
            continue
        plan = rep.get('plan', {})
        st['notes'].append('{}: этап 9 {}; шаги {}'.format(key, (plan.get('stage_entry') or {}).get('status'), ', '.join(
            '{}={}'.format(r['id'], r['status']) for r in plan.get('steps') or ())))
        st['deliver'][key] = {'status': rep.get('status'), 'stage_entry': plan.get('stage_entry'),
                              'blockers': [str(b)[:300] for b in plan.get('blockers') or ()],
                              'steps': {r['id']: r['status'] for r in plan.get('steps') or ()},
                              'run_folder': plan.get('run_folder'),
                              'files': sorted(str(p.relative_to(plan['run_folder'])) for p in
                                              Path(plan['run_folder']).rglob('*')) if plan.get('run_folder') else []}




def final_checks():
    """qa.package on the archive of the delivery (if one was written) and qa.sintez (0.9 row)."""
    out = {}
    zips = []
    for key in ('B', 'A'):
        rep = (S.get('deliver') or {}).get(key)
        if rep and rep.get('plan', {}).get('run_folder'):
            zips = sorted(str(p) for p in Path(rep['plan']['run_folder']).rglob('*.zip'))
            if zips:
                out['package_from'] = key
                break
    pkg_file = None
    if zips:
        t0 = time.perf_counter()
        try:
            rep = agr.edits_080('qa.package', 'preview', options={'path': str(Path(zips[0]).parent)})
            pkg_file = OUT / 'qa_package_report.json'
            pkg_file.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
            out['qa_package'] = dict(brief(rep), zips=[Path(z).name for z in zips], file=pkg_file.name)
        except Exception as exc:  # noqa: BLE001
            out['qa_package'] = {'status': classify(exc), 'error': first_line(exc), 'zips': [Path(z).name for z in zips]}
        out['qa_package']['seconds'] = round(time.perf_counter() - t0, 2)
    else:
        out['qa_package'] = {'status': 'skipped', 'reason': 'pack.deliver не записал архив (этап 9 blocked)'}
    # qa.sintez: the real SINTEZ AGR Checker is a Blender extension (third party, not run here)
    try:
        rep = agr.edits_090('qa.sintez', 'preview', None, None, None)
        out['qa_sintez'] = dict(brief(rep), note='без отчёта SINTEZ')
    except Exception as exc:  # noqa: BLE001
        out['qa_sintez'] = {'status': classify(exc), 'error': first_line(exc)}
    out['qa_sintez_real'] = {'status': 'not_run', 'reason': 'SINTEZ AGR Checker is a Blender extension; not run in this Max job'}
    summary['final'] = out



# ---- outputs -----------------------------------------------------------------------------------------------------
STATUS_RU = {'done': 'done', 'findings': 'findings', 'ambiguous': 'ambiguous', 'refused': 'refused', 'error': 'error',
             'skipped': 'skipped', 'not_implemented': 'not_implemented', 'harness_error': 'HARNESS ERROR', 'n/a': 'n/a'}


def short(b):
    for part in ('apply', 'preview'):
        x = b.get(part) or {}
        if x.get('error'):
            return x['error'][:160]
        if x.get('ambiguous'):
            return 'ambiguous: ' + x['ambiguous'][0][:150]
        if x.get('codes'):
            return 'codes: ' + ', '.join('{} x{}'.format(k, v) for k, v in list(x['codes'].items())[:4])
    return b.get('note', '')[:160]


def write_outputs():
    lines = ['# AC08 (TEC26-OKS) через этапы 0–9 — AGR Tools {} (Max {})'.format(
        summary.get('runtime_version'), '.'.join(str(x) for x in summary['max_version'])), '',
        '**Модель: РЕАЛЬНАЯ AC08** `{}` sha256 `{}`; карта id {}.'.format(
            (summary.get('source_fbx') or {}).get('path'), (summary.get('source_fbx') or {}).get('sha256'),
            json.dumps((summary.get('id_map') or {}).get('map'))), '',
        '**{}**'.format(summary['diagnostic']) if summary.get('diagnostic') else '', '',
        '| Этап | Кнопки (статус) | Время, с | Треугольники: видимые / всего / новые | Статус этапа | Коротко |',
        '|---|---|---:|---|---|---|']
    for st in summary['stages']:
        btn = '; '.join('{} {} ({} с)'.format(b['tool'], STATUS_RU.get(b['status'], b['status']), b.get('seconds'))
                        for b in st['buttons'])
        big = next((b for b in st['buttons'] if b['tool'] == st['big']), None)
        why = short(big) if big else ''
        if st.get('harness_error'):
            why = 'harness: ' + st['harness_error'].strip().splitlines()[-1][:160]
        notes = ' '.join(st.get('notes') or ())[:300]
        cell = (why + (' — ' + notes if notes else '')).replace('|', '/')
        lines.append('| {} {} | {} | {} | {} / {} / {} | {} | {} |'.format(
            st['id'], st['title'], btn.replace('|', '/'), st['seconds'], st['tris_visible'], st['tris_total'],
            st['tris_new'], STATUS_RU.get(st['status'], st['status']), cell))
    fin = summary.get('final') or {}
    if fin:
        lines += ['', '## SINTEZ и qa.package', '']
        for key in ('qa_package', 'qa_sintez', 'qa_sintez_fixture'):
            x = fin.get(key)
            if x:
                lines.append('- `{}`: {} — {}'.format(key, x.get('status'), (x.get('error') or x.get('reason') or
                                                                            x.get('note') or json.dumps(
                                                                                x.get('codes'), ensure_ascii=False))
                                                      [:300]))
    if summary['harness_steps']:
        lines += ['', '## Шаги стенда (не кнопки)', ''] + ['- ' + s for s in summary['harness_steps']]
    lines += ['', 'Всего: {} с; журнал: {} строк.'.format(summary.get('total_seconds'), summary.get('journal_lines'))]
    (OUT / 'table.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')



# ---- D221 on an EXPLICITLY SYNTHETIC fixture (AC08 has no glass) ----------------------------------------------------
GLASS_A, GLASS_B = 39, 48     # 39 = library glass_01; 48 = second glass id of the fixture (as test_agr_tools_vpm_layout)
BODY_IDS = (11, 2)


def fbx_readback(path):
    """Independent readback: reset, import the written FBX alone, read every node."""
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0
    rt.FBXImporterSetParam('ScaleConversion', False)
    ok = rt.importFile(str(path), rt.name('noPrompt'), using=rt.FBXIMP)
    out = {'path': str(path), 'import_ok': bool(ok), 'nodes': []}
    for n in rt.objects:
        if tris(n) is not None:
            out['nodes'].append(node_facts(n))
    return out


def d221_fixture():
    import pymxs
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0
    st = {'id': 'D221', 'buttons': []}
    with pymxs.undo(False):
        b = rt.Box(name='SYNTH_D221_Body', length=3.0, width=6.0, height=4.0, lengthsegs=4, widthsegs=4, heightsegs=4)
        rt.convertToPoly(b)
        nf = int(rt.polyop.getNumFaces(b))
        cycle = [BODY_IDS[0], BODY_IDS[1], GLASS_A, GLASS_B]
        for f in range(1, nf + 1):
            rt.polyop.setFaceMatID(b, f, cycle[(f - 1) % 4])
        box_uv(b)
    res = {'fixture': 'SYNTHETIC (not AC08): Box 6 x 3 x 4 m, 4 segments, face ids cycle 11/2/39/48',
           'glass_ids': [GLASS_A, GLASS_B], 'body_ids': list(BODY_IDS), 'source': node_facts(b)}
    pre, app = press(st, 'vpm.build', [b], {'glass_ids': [GLASS_A, GLASS_B], 'out_dir': str(OUT / 'd221_vpm'),
                                             'library_path': LIB, 'address': 'Synth_1'},
                     label='vpm.build (SYNTHETIC D221, library_path)')
    if app is None:
        pre, app = press(st, 'vpm.build', [b], {'glass_ids': [GLASS_A, GLASS_B], 'out_dir': str(OUT / 'd221_vpm_nolib'),
                                                 'address': 'Synth_1'},
                         label='vpm.build (SYNTHETIC D221, без library_path)')
    res['buttons'] = st['buttons']
    if app is not None:
        copies = valid([rt.getNodeByName(c) for c in app['plan'].get('copies') or ()])
        res['copies'] = []
        for c in copies:
            f = node_facts(c)
            try:
                f['agr_udim_table'] = json.loads(str(rt.getUserProp(c, 'agr_udim_table') or 'null'))
            except ValueError:
                f['agr_udim_table'] = str(rt.getUserProp(c, 'agr_udim_table'))
            res['copies'].append(f)
        res['plan_files'] = app['plan'].get('files')
        outdir = Path(app['plan'].get('out_dir') or (OUT / 'd221_vpm'))
        files = sorted(str(p.relative_to(outdir)).replace(chr(92), '/') for p in outdir.rglob('*')
                       if p.is_file()) if outdir.is_dir() else []
        res['out_dir'] = str(outdir)
        res['out_files'] = files
        res['glass_maps'] = [f for f in files if 'glass' in f.lower()
                             and f.lower().endswith(('.png', '.tga', '.jpg', '.exr', '.tif', '.tiff'))]
        scene = OUT / 'scenes' / 'D221_synthetic_vpm.max'
        res['scene_saved'] = bool(rt.saveMaxFile(str(scene), quiet=True))
        fbx = OUT / 'd221_export' / 'SYNTH_D221_vpm.fbx'
        fbx.parent.mkdir(parents=True, exist_ok=True)
        # FBX keeps per-face materials, not Max ids: give the copies a Multi/Sub whose sub names carry the id
        # (harness step on the copies only), so the readback can map the renumbered ids back by name
        ids = sorted({int(k) for c in res['copies'] for k in c['mat_ids']})
        mm = rt.MultiMaterial(numsubs=len(ids))
        mm.name = 'SYNTH_D221_IDS'
        fill_multi(mm, [rt.StandardMaterial(name='ID_{:03d}'.format(i)) for i in ids], ids)
        for c in copies:
            c.material = mm
        res['export_material'] = {'name': 'SYNTH_D221_IDS', 'subs': ['ID_{:03d}'.format(i) for i in ids]}
        rt.select(copies)
        res['export_ok'] = bool(rt.exportFile(str(fbx), rt.name('noPrompt'), selectedOnly=True, using=rt.FBXEXP))
        res['export'] = {'path': str(fbx), 'sha256': sha(fbx) if fbx.is_file() else None}
        if fbx.is_file():
            res['readback'] = fbx_readback(fbx)
    summary['d221'] = {k: res.get(k) for k in ('fixture', 'glass_maps', 'export_ok')}
    (OUT / 'd221.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding='utf-8')



T0 = time.perf_counter()
try:
    build_source()
except Exception:  # noqa: BLE001
    summary['harness_errors'].append('build_source: ' + traceback.format_exc()[-1500:])
if not summary['harness_errors']:
    for sid, title, fn in ((0, 'Паспорт', stage0), (1, 'Бадик', stage1), (2, 'Окна', stage2), (3, 'Капсулы', stage3),
                           (4, 'Крыша', stage4), (5, 'Материалы', stage5), (6, 'ВПМ', stage6), (7, 'НПМ', stage7),
                           (8, 'НПМ→ВПМ', stage8), (9, 'Сдача', stage9)):
        run_stage(sid, title, fn)
    try:
        final_checks()
    except Exception:  # noqa: BLE001
        summary['harness_errors'].append('final_checks: ' + traceback.format_exc()[-1500:])
summary['total_seconds'] = round(time.perf_counter() - T0, 2)
jl = 0
for p in (OUT / 'journal').glob('*.jsonl'):
    jl += len(p.read_text(encoding='utf-8').splitlines())
summary['journal_lines'] = jl
try:
    final = OUT / 'scenes' / 'AC08_stages_final.max'
    summary['final_scene_saved'] = bool(rt.saveMaxFile(str(final), quiet=True))
    summary['final_scene_sha256'] = sha(final)
except Exception as exc:  # noqa: BLE001 - evidence only
    summary['final_scene_saved'] = first_line(exc)
# independent readback of every FBX written by stage 9 (fresh import into a reset scene)
rb = {}
try:
    for key in ('A', 'B'):
        rep = (S.get('deliver') or {}).get(key)
        rf = (rep or {}).get('plan', {}).get('run_folder')
        if rf:
            for p in sorted(Path(rf).rglob('*.fbx')):
                rb['{}:{}'.format(key, p.name)] = dict(fbx_readback(p), sha256=sha(p))
except Exception:  # noqa: BLE001
    summary['harness_errors'].append('fbx readback: ' + traceback.format_exc()[-1500:])
if not rb and valid([S.get('deliver_main')]):
    # no delivery FBX (stage 9 blocked): a HARNESS export of the stage-9 working nodes, labelled as such, only to
    # read the produced geometry back independently; it is NOT a delivery and not a pack.deliver output
    try:
        model = valid([S['deliver_main']] + list(S.get('ucx') or ()))
        diag = OUT / 'readback_export' / (STEM + '_HARNESS_NOT_DELIVERY.fbx')
        diag.parent.mkdir(parents=True, exist_ok=True)
        rt.select(model)
        ok = bool(rt.exportFile(str(diag), rt.name('noPrompt'), selectedOnly=True, using=rt.FBXEXP))
        summary['harness_readback_export'] = {'nodes': names(model), 'ok': ok, 'path': str(diag),
                                              'facts_before_export': [node_facts(n) for n in model]}
        if diag.is_file():
            rb['HARNESS:' + diag.name] = dict(fbx_readback(diag), sha256=sha(diag),
                                              note='harness export, NOT a delivery (stage 9 blocked)')
    except Exception:  # noqa: BLE001
        summary['harness_errors'].append('harness readback export: ' + traceback.format_exc()[-1500:])
(OUT / 'readback.json').write_text(json.dumps(rb, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
summary['readback_fbx'] = sorted(rb)
try:
    d221_fixture()
except Exception:  # noqa: BLE001
    summary['harness_errors'].append('d221: ' + traceback.format_exc()[-1500:])
write_outputs()
print('AC08_E2E stages', [(s['id'], s['status']) for s in summary['stages']], 'harness_errors', summary['harness_errors'])
assert not summary['harness_errors'], 'AC08 harness failed: see summary.json'

