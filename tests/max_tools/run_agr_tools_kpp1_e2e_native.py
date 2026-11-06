"""new-case: #1024 R acceptance 1.0 «KPP1 сквозняком»: one native Max 2024 run drives a SYNTHETIC KPP1-like body
through the stage buttons 0..9 of AGR Tools 1.0.0 in order and records per stage the wall time, the triangles of the
scene after the stage, the status of every pressed button, and at the end qa.sintez / qa.package.

NOT the corpus: the KPP1 Revit/FBX (v005/v007) is not in the allowed folders, so the body is built here from the
KPP1 facts of jobs/KPP1 (scripts/build_kpp1.py docstring, object.json): plan 27.66 x 11.66 m, levels 0 / 3.9 / 7.7 /
8.65 (parapet top), parapet 0.555 m, finish bands RAL 7004 / 7047 / 5015, openings KPP1-W01..W03 (the sizes of
test-polygon/stations/J_build.KPP1). Facade shell: J_build.facade (closed loop, reveals 0.23 m); parapet:
K_build.parapet_mesh. The source is written in CENTIMETRE numbers into a metre scene (an FBX read 1:1), so
source.intake has real work; library ids of library/materials (a copy under OUT) are on the faces.

Run via the lab DCC runner (script_in_place). Env: AGR_TEST_OUTPUT (a NEW directory), AGR_TEST_PACKAGE (the built
MZP, installed into OUT: no user folders), AGR_TOOLS_REPO, AGR_PYTHON (validator of qa.package). Journal, LOCALAPPDATA,
passport root, library copy, every export folder: under OUT. Buttons are pressed through runtime.edits_100 (actor
panel): preview, then apply of that preview for editing rows. A refusal / failure of a button is RECORDED (status
refused / error / findings / ambiguous / not_implemented), never hidden; the script fails (non-zero) only on
harness errors. Writes OUT/summary.json and OUT/table.md (Markdown, Russian), the final scene OUT/scenes/*.max.
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
summary = {'case': 'KPP1 e2e 1.0.1 (#1024)', 'model': 'SYNTHETIC KPP1-like (not the corpus)',
           'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'stages': [], 'harness_errors': [], 'harness_steps': []}
assert not rt.maxFileName, 'only an empty batch document is allowed'

W, L = 27.66, 11.66             # outer facade plane (KPP1: x -0.33..27.33, y -0.33..11.33)
PARAPET_TOP, PARAPET_H, PARAPET_T = 8.65, 0.555, 0.3
ROOF_LEVEL = PARAPET_TOP - PARAPET_H   # 8.095: bottom of the inner parapet faces = contour A of body.roof
WALL_TOP = ROOF_LEVEL - 0.3            # 7.795: the parapet outer faces go down to level - 0.3 (K_build)
LEVELS = [{'name': 'L1', 'z_m': 0.0}, {'name': 'L2', 'z_m': 3.9}, {'name': 'roof', 'z_m': 7.7},
          {'name': 'parapet', 'z_m': PARAPET_TOP}]
CM = 100.0                              # the source numbers are centimetres
# library ids (library/materials/materials_v001.json)
ID_PLINTH, ID_7047, ID_5015, ID_9016, ID_ROOF, ID_FLASH, ID_GLASS = 16, 12, 9, 3, 29, 35, 39
ADDRESS = 'Kpp_1'  # the KPP1 address of jobs/KPP1/scripts/build_kpp1.py (qa.names: digits after '_')
STEM = 'SM_' + ADDRESS


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
assert agr.VERSION == os.environ.get('AGR_EXPECT_VERSION', '1.0.1'), agr.VERSION
JB = load(ROOT / 'test-polygon' / 'stations' / 'J_build.py', 'kpp1_e2e_J_build')
KB = load(ROOT / 'test-polygon' / 'stations' / 'K_build.py', 'kpp1_e2e_K_build')
NC = agr._load_core('npm_core.py', 'agr_tools_npm_core_kpp1')
roadmap = agr._load_core('roadmap.py', 'agr_tools_roadmap_kpp1')
SUITE = roadmap.load_file(str(OUT / 'installed' / 'agr-tools-suite.json'))
STAGE_ROWS = {s['id']: list(s['rows']) for s in SUITE['stages']}

# library copy (K5: read from a copy): <copy>/library/materials + <copy>/tools/materials/ral_classic.json
LIBCOPY = OUT / 'libcopy'
shutil.copytree(ROOT / 'library' / 'materials', LIBCOPY / 'library' / 'materials')
(LIBCOPY / 'tools' / 'materials').mkdir(parents=True)
shutil.copy2(ROOT / 'tools' / 'materials' / 'ral_classic.json', LIBCOPY / 'tools' / 'materials' / 'ral_classic.json')
LIB = str(LIBCOPY / 'library' / 'materials' / 'materials.json')
SINTEZ_FIXTURE = ROOT / 'tests' / 'max_tools' / 'fixtures_qa9' / 'sintez_hp_all_verified.json'
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
    print('KPP1_E2E', st['id'], row['tool'], row['status'], row['seconds'], 's')
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


# ---- the synthetic KPP1-like source ------------------------------------------------------------------------------
def kpp1_spec():
    holes = []

    def add(wall, u, t, floor):
        w, h = JB.KPP1[t]
        sill = 0.3 if t == 'KPP1-W02' else (0.9 if floor == 1 else 4.8)
        holes.append({'wall': wall, 'kind': 'rect', 'u': u, 'sill': sill, 'w': w, 'h': h, 'type': t})
    for u, t in ((2.0, 'KPP1-W01'), (6.0, 'KPP1-W03'), (10.0, 'KPP1-W01'), (14.0, 'KPP1-W02'), (18.0, 'KPP1-W01'),
                 (22.0, 'KPP1-W03')):
        add(0, u, t, 1)
    for u, t in ((2.0, 'KPP1-W01'), (6.0, 'KPP1-W03'), (10.0, 'KPP1-W01'), (18.0, 'KPP1-W01'), (22.0, 'KPP1-W03')):
        add(0, u, t, 2)
    for fl in (1, 2):
        for u in (2.0, 8.48):
            add(1, u, 'KPP1-W01', fl)
        for u in (3.0, 9.0, 15.0, 21.0):
            add(2, u, 'KPP1-W01', fl)
        add(3, 4.83, 'KPP1-W03', fl)
    return {'name': 'KPP1_Facade', 'points': [[0, 0], [W, 0], [W, L], [0, L], [0, 0]], 'height': WALL_TOP,
            'reveal': 0.23, 'holes': holes, 'corners': []}


def facade_ids(data):
    out = []
    for f, mid in zip(data['faces'], data['mat_ids']):
        if mid == 2:
            out.append(ID_9016)   # reveals / window surrounds RAL 9016
            continue
        z = sum(data['verts'][i][2] for i in f) / len(f)
        out.append(ID_PLINTH if z < 0.9 else ID_7047 if z < 2.7 else ID_5015 if z < 7.1 else ID_7047)
    return out


def parapet_ids(data):
    out = []
    for f in data['faces']:
        pts = [data['verts'][i] for i in f]
        n = JB._newell(pts)
        ln = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5 or 1.0
        if abs(n[2] / ln) > 0.7:
            out.append(ID_FLASH)
            continue
        cx = sum(p[0] for p in pts) / len(pts) - W / 2
        cy = sum(p[1] for p in pts) / len(pts) - L / 2
        out.append(ID_5015 if cx * n[0] + cy * n[1] > 0 else ID_ROOF)
    return out


def box_uv(node):
    rt.addModifier(node, rt.Uvwmap(maptype=4))
    rt.collapseStack(node)


def build_source():
    """KPP1-like source in a metre scene, numbers in centimetres (as an FBX in cm read 1:1)."""
    import pymxs
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0
    with pymxs.undo(False):
        subs, ids = [], [ID_PLINTH, ID_7047, ID_5015, ID_9016, ID_ROOF, ID_FLASH]
        for i in ids:
            subs.append(rt.StandardMaterial(name='KPP1_AR_{:02d}'.format(i)))
        mm = rt.MultiMaterial(numsubs=len(ids))
        mm.name = 'KPP1_AR'
        fill_multi(mm, subs, ids)
        spec = kpp1_spec()
        data = JB.facade(spec)
        data['mat_ids'] = facade_ids(data)
        cm = dict(data, verts=[[c * CM for c in v] for v in data['verts']])
        facade = JB.mesh_node(rt, cm, 'KPP1_Facade')
        facade.material = mm
        box_uv(facade)
        inner = [[PARAPET_T, PARAPET_T], [W - PARAPET_T, PARAPET_T], [W - PARAPET_T, L - PARAPET_T],
                 [PARAPET_T, L - PARAPET_T]]
        pdata = KB.parapet_mesh(inner, ROOF_LEVEL, PARAPET_H, PARAPET_T)
        pids = parapet_ids(pdata)
        parapet = KB.mesh_node(rt, 'KPP1_Parapet', {'verts': [[c * CM for c in v] for v in pdata['verts']],
                                                    'faces': pdata['faces']})
        for i, mid in enumerate(pids, 1):
            rt.polyop.setFaceMatID(parapet, i, mid)
        parapet.material = mm
        box_uv(parapet)
        bolts = []
        for i, (x, y) in enumerate(((1.0, -0.05), (9.0, -0.05), (17.0, -0.05), (25.0, -0.05))):
            b = rt.Box(name='Bolt_M12_{:02d}'.format(i + 1), length=2, width=2, height=6)
            b.pos = rt.Point3(x * CM, y * CM, 7.0 * CM)
            rt.convertToMesh(b)
            bolts.append(b)
        a = rt.Box(name='Уголок_50_01', length=5, width=5, height=10)
        a.pos = rt.Point3(5.0 * CM, -0.1 * CM, 7.2 * CM)
        rt.convertToMesh(a)
        bolts.append(a)
    S['src'] = [facade, parapet] + bolts
    S['facade'], S['parapet'], S['bolts'] = facade, parapet, bolts
    types = {}
    for h in spec['holes']:
        types[h['type']] = types.get(h['type'], 0) + 1
    summary['source'] = {'plan_m': [W, L], 'wall_top_m': WALL_TOP, 'roof_level_m': ROOF_LEVEL,
                         'parapet_top_m': PARAPET_TOP, 'parapet_h_m': PARAPET_H, 'levels': LEVELS,
                         'openings': len(spec['holes']), 'openings_by_type': types, 'units_of_numbers': 'cm',
                         'scene_units': 'm', 'tris': {str(n.name): tris(n) for n in S['src']},
                         'library_ids': {'plinth_RAL7004': ID_PLINTH, 'cassette_RAL7047': ID_7047,
                                         'panel_RAL5015': ID_5015, 'reveal_RAL9016': ID_9016,
                                         'parapet_inner_roof': ID_ROOF, 'flashing': ID_FLASH, 'glass': ID_GLASS}}
    scene = OUT / 'scenes' / 'KPP1_e2e.max'
    scene.parent.mkdir(parents=True, exist_ok=True)
    assert rt.saveMaxFile(str(scene), quiet=True), scene
    summary['scene'] = str(scene)


# ---- stages ------------------------------------------------------------------------------------------------------
def stage0(st):
    root = OUT / 'proj'
    pre, app = press(st, 'project.passport', None, {'root': str(root), 'project_id': 'KPP1',
                                                     'title': 'КПП-1 (синтетика KPP1-like, не корпус)'})
    pp = root / 'jobs' / 'KPP1' / 'passport.json'
    S['passport'] = str(pp) if pp.is_file() else None
    st['notes'].append('паспорт: ' + (S['passport'] or 'не записан'))
    pre, app = press(st, 'source.intake', S['src'], {'source_path': 'synthetic:KPP1-like (cm numbers, Z up)'})
    if app is not None:
        cmap = {}
        for nm in app['plan'].get('readback', {}).get('copies', []):
            c = rt.getNodeByName(nm)
            if c is not None:
                cmap[str(rt.getUserProp(c, 'agr_intake_source'))] = c
        S['facade'] = cmap.get('KPP1_Facade', S['facade'])
        S['parapet'] = cmap.get('KPP1_Parapet', S['parapet'])
        S['bolts'] = [cmap.get(str(b.name), b) for b in S['bolts']]
        for n in S['src']:
            n.isHidden = True
        harness_step(st, 'исходники (cm) скрыты после source.intake; дальше работают копии AGR_intake (метры)')
        st['notes'].append('readback копий: ' + json.dumps(app['plan'].get('readback', {}).get('size_m')))
    else:
        st['notes'].append('source.intake не применён: дальше работают ИСХОДНИКИ в числах cm (результаты в метрах '
                           'неверны в 100 раз)')
    press(st, 'scene.source_class', [S['facade'], S['parapet']])


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
    pre, app = press(st, 'vpm.build', [S['main']], {'glass_ids': [ID_GLASS], 'out_dir': str(OUT / 'vpm'),
                                                    'library_path': LIB, 'address': ADDRESS,
                                                    'map_dir': str(OUT / 'tiles')})
    if app is None:
        # run 20261106-071804-147131cc: with library_path the apply refuses (step 6, maps); the build itself is
        # pressed again without the maps so the later stages work on a real VPM copy (recorded as its own row)
        pre, app = press(st, 'vpm.build', [S['main']], {'glass_ids': [ID_GLASS], 'out_dir': str(OUT / 'vpm_nomaps')},
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
    opts = {'out_dir': str(OUT / 'npm'), 'name': STEM + '_001_Main', 'glass_ids': [ID_GLASS]}
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
    # strip periods of the textured KPP1 finishes from their library base maps (panel_v1200, panel_v600, 300x300)
    press(st, 'atlas.facade_strip', valid([S.get('vpm_body')]) or valid([S.get('main')]),
          {'out_dir': str(OUT / 'facade_strip'),
           'period_by_id': {str(ID_5015): [1.2, 1.2], str(ID_7047): [0.6, 0.6], str(ID_PLINTH): [0.3, 0.3]}})


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
    rt.setUserProp(main, 'AGR_ZERO_M', '0.0')
    layer0 = rt.LayerManager.getLayer(0)
    moved = [str(n.name) for n in model if str(n.layer.name) != '0']
    for n in model:
        layer0.addNode(n)
    harness_step(st, 'вход художника: AGR_EXPORT_PATH={} на {} узлах, AGR_ZERO_M=0.0 на {} (ни одна кнопка 1.0 их не '
                     'задаёт)'.format(fbx_path, len(model), main.name))
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
    skip = {'qa.sintez': 'нет отчёта SINTEZ AGR Checker для синтетики (Blender-расширение не запускается)',
            'qa.omk_te': 'нет таблицы ОМК ТЭ объекта KPP1 (options.table)'}
    pre_a = (aa or pa or {}).get('plan', {}).get('steps') or ()
    if any(r.get('id') == 'qa.preflight' and r.get('status') != 'pass' for r in pre_a):
        skip['qa.preflight'] = ('синтетика без Ground FBX и без опуска фасада на 1 м ниже +-0.000 '
                                '(fbx_ground_missing, perimeter_drop): находки qa.preflight - в прогоне A')
    if not light_ok:
        skip['light.export'] = 'в KPP1-like нет источников света: light.export не дал файла'
        skip['light.check'] = 'в KPP1-like нет источников света: пустой набор - ошибка light.check'
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
    try:
        opts = {'sintez': str(SINTEZ_FIXTURE)}
        if pkg_file:
            opts['package'] = str(pkg_file)
        rep = agr.edits_090('qa.sintez', 'preview', None, [S['deliver_main']] if S.get('deliver_main') else None, opts)
        plan = rep.get('plan') or {}
        out['qa_sintez_fixture'] = dict(brief(rep), fixture=SINTEZ_FIXTURE.name,
                                        counts={k: plan.get(k) for k in ('mismatch', 'unmatched', 'agree', 'rules')
                                                if k in plan},
                                        note='ЧУЖОЙ фикстурный отчёт SINTEZ (не KPP1): проверка только механики '
                                             'сравнения, это НЕ ошибки SINTEZ этой модели')
    except Exception as exc:  # noqa: BLE001
        out['qa_sintez_fixture'] = {'status': classify(exc), 'error': first_line(exc), 'fixture': SINTEZ_FIXTURE.name}
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
    lines = ['# KPP1 сквозняком через этапы 0–9 — AGR Tools {} (Max {})'.format(
        summary.get('runtime_version'), '.'.join(str(x) for x in summary['max_version'])), '',
        '**Модель: СИНТЕТИКА KPP1-like, не корпус** (план {} x {} м, отметки 0 / 3.9 / 7.7 / 8.65, парапет {} м, '
        'окна KPP1-W01..W03: {} проёмов; исходник в числах cm в метровой сцене).'.format(
            W, L, PARAPET_H, (summary.get('source') or {}).get('openings')), '',
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
    final = OUT / 'scenes' / 'KPP1_e2e_final.max'
    summary['final_scene_saved'] = bool(rt.saveMaxFile(str(final), quiet=True))
except Exception as exc:  # noqa: BLE001 - evidence only
    summary['final_scene_saved'] = first_line(exc)
write_outputs()
print('KPP1_E2E stages', [(s['id'], s['status']) for s in summary['stages']], 'harness_errors', summary['harness_errors'])
assert not summary['harness_errors'], 'KPP1 e2e harness failed: see summary.json'
