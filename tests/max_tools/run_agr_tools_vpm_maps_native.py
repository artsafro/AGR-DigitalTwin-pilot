"""new-case: #1024 branch N native run of tex.dilate, udim.plugs, vpmmaps and the bitmap enumerator in locked batch Max 2024.

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP,
AGR_TOOLS_REPO the worktree (for test-polygon/stations/N_build.py and expected/*.json). Installs the MZP into OUT (no user
folders touched) and runs on SYNTHETIC files under OUT/data and a disposable unsaved scene:
* dilate_files: RGBA island map -> padded copy in a NEW folder, source bytes unchanged, covered pixels identical, padding
  limited; second press refuses (dilate_exists); white map without alpha (mask=alpha) -> dilate_no_mask, no file;
* polygon_rows: the objects of stations 1.0.20 / 1.0.21 (stations/N.json, built by N_build.py) are pressed in preview through
  runtime.edits_100 and compared with expected/tex.dilate.json and expected/udim.plugs.json (PASS and FAIL rows);
* plugs_apply: copy in layer AGR_export with the 0.05 island in the centre of tile 1003, source mesh hash unchanged, a
  SECOND apply on the same source works (GridUVLayout22 runPlugs refused it);
* vpmmaps: build_maps in the real Max Python: 12 files, repeated plan gives the same hashes;
* enumerator: Multi/Sub (ID 1, 2) with bitmaps -> rows with matid, role and UDIM.
Nothing is saved; the scene is never written.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import time
import traceback
import zlib

from pymxs import runtime as rt

REPO = Path(os.environ['AGR_TOOLS_REPO'])
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
DATA = OUT / 'data'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}, 'seconds': {}, 'polygon_rows': []}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    t = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['seconds'][name] = round(time.time() - t, 2)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
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
tex = agr._load_core('tex_core.py', 'agr_tools_tex_core')
nbuild = load(REPO / 'test-polygon/stations/N_build.py', 'n_build')


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def edits(tool, mode, **kw):
    return agr.edits_100(tool, mode, **kw)


def codes_of(report, name):
    for o in report['objects']:
        if o['name'] == name:
            return sorted({f['code'] for f in o['findings']})
    return None


# ---- tex.dilate on files -------------------------------------------------------------------------------
def dilate_files():
    maps = DATA / 'maps'
    maps.mkdir(parents=True)
    ok = maps / 'T_NNat_Diffuse_1.1001.png'
    ok.write_bytes(nbuild.png('rgba_island'))
    white = maps / 'T_NNatW_Diffuse_1.1001.png'
    white.write_bytes(nbuild.png('rgb_white_island'))
    before = (md5(ok), md5(white))
    out = DATA / 'padded'
    pv = edits('tex.dilate', 'preview', options={'files': [str(ok), str(white)], 'out': str(out), 'mask': 'alpha',
                                                  'padding': 4})
    res = {'preview_status': pv['status'], 'done': len(pv['plan']['done']), 'skipped': len(pv['plan']['skipped'])}
    assert not out.exists(), 'preview wrote files'
    assert res['done'] == 1 and res['skipped'] == 1, res
    ap = edits('tex.dilate', 'apply', preview=pv)
    written = sorted(p.name for p in out.glob('*.png'))
    assert written == ['T_NNat_Diffuse_1.1001.png'], written
    assert before == (md5(ok), md5(white)), 'source changed'
    img = tex.decode_png((out / written[0]).read_bytes())[0]
    src = tex.decode_png(ok.read_bytes())[0]
    covered = all(src.px[4 * i + 3] == 0 or tuple(src.px[4 * i:4 * i + 3]) == tuple(img.px[img.n * i:img.n * i + 3])
                  for i in range(src.w * src.h))
    assert covered, 'covered pixels changed'
    pad_px = 32 * 12 + 11                                   # next to the island
    assert tuple(img.px[img.n * pad_px:img.n * pad_px + 3]) == (200, 40, 40) and tuple(img.px[0:3]) == (0, 0, 0)
    pv2 = edits('tex.dilate', 'preview', options={'files': [str(ok)], 'out': str(out), 'mask': 'alpha', 'padding': 4})
    refused = [s['reason'] for s in pv2['plan']['skipped']]
    assert refused and 'not overwritten' in refused[0], refused
    res.update(written=written, second_press=refused[0][:60], white_codes=codes_of(pv, white.name))
    assert res['white_codes'] == ['dilate_no_mask'], res
    return res


# ---- polygon rows (stations 1.0.20 / 1.0.21) -----------------------------------------------------------
def station_objects():
    frag = json.loads((REPO / 'test-polygon/stations/N.json').read_text(encoding='utf-8'))
    nodes = {}
    for si, st in enumerate(frag['stations']):
        for oi, spec in enumerate(st['objects']):
            obj = dict(spec, pos=[10.0 * oi, 10.0 * si, 0.0], texture_dir=str(DATA / 'tex'), size=[2, 2, 2])
            nodes[spec['name']] = nbuild.make(obj, rt)
    return frag, nodes


def polygon_rows():
    frag, nodes = station_objects()
    rows = []
    for st in frag['stations']:
        for exp in st['expected']:
            node = nodes[exp['name']]
            rep = edits(st['button'], 'preview', nodes=[node], options=st.get('options'))
            codes = codes_of(rep, exp['name'])
            status = 'pass' if not codes else 'fail'
            row = {'button': st['button'], 'name': exp['name'], 'expect': exp['expect'], 'codes_expected': exp['codes'],
                   'status': status, 'codes': codes, 'report_status': rep['status']}
            row['match'] = status == exp['expect'] and codes == sorted(exp['codes'])
            rows.append(row)
    summary['polygon_rows'] = rows
    assert all(r['match'] for r in rows), rows
    return rows


# ---- udim.plugs apply -----------------------------------------------------------------------------------
def plugs_apply():
    node = rt.Box(name='SM_NPlugNat_Main', length=2, width=2, height=2)
    rt.convertToPoly(node)
    rt.polyop.setFaceMatID(node, rt.execute('#all'), 3)
    before = agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot([node])
    results = []
    for run in (1, 2):                                       # the second run on the same source must work
        pv = edits('udim.plugs', 'preview', nodes=[node])
        assert pv['status'] == 'pass', pv['objects']
        ap = edits('udim.plugs', 'apply', preview=pv, nodes=[node])
        copies = ap['plan']['copies']
        copy = rt.getNodeByName(copies[0])
        po = rt.polyop
        uv = [[(float(po.getMapVert(copy, 1, int(i)).x), float(po.getMapVert(copy, 1, int(i)).y))
               for i in po.getMapFace(copy, 1, f)] for f in range(1, int(po.getNumFaces(copy)) + 1)]
        core = agr._load_core('udimplug_core.py', 'agr_tools_udimplug_core')
        assert core.plug_check(uv, 1003), 'readback of the plug island differs'
        assert str(copy.layer.name) == 'AGR_export'
        results.append({'run': run, 'copy': copies[0], 'faces': len(uv)})
    after = agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot([node])
    assert before == after, 'source changed'
    return results


# ---- vpmmaps -------------------------------------------------------------------------------------------
def vpmmaps():
    vm = agr._load_core('vpmmaps_core.py', 'agr_tools_vpmmaps_core')
    lib = {i: {'library_id': i, 'key': 'k%d' % i, 'rgb_srgb': [30 * i % 256, 90, 120], 'roughness': 77, 'metallic': 255 if i == 7 else 0,
               'emissive': 0, 'recipe': 'solid'} for i in (3, 7, 12, 31)}
    table = {'SM_NatAddr_Main': {3: 1001, 7: 1002, 12: 1003, 31: 1004}, 'SM_NatAddr_MainGlass': {31: 1001}}
    plan = vm.plan_maps(table, lib, str(DATA / 'maps_out'), {'slot': {'SM_NatAddr_MainGlass': 2}})
    again = vm.plan_maps(table, lib, str(DATA / 'maps_out'), {'slot': {'SM_NatAddr_MainGlass': 2}})
    assert [m['sha256'] for m in plan['maps']] == [m['sha256'] for m in again['maps']]
    built = vm.build_maps(table, lib, str(DATA / 'maps_out'), {'slot': {'SM_NatAddr_MainGlass': 2}})
    assert len(built['maps']) == 15 and not built['skipped'], built['skipped']
    files = sorted(p.name for p in (DATA / 'maps_out').glob('*.png'))
    repeat = vm.build_maps(table, lib, str(DATA / 'maps_out'), {'slot': {'SM_NatAddr_MainGlass': 2}})
    assert repeat['maps'] == [] and len(repeat['skipped']) == 15
    return {'files': len(files), 'first': files[0], 'glass_1001': 'T_NatAddr_Diffuse_2.1001.png' in files}


# ---- bitmap enumerator ------------------------------------------------------------------------------------
def enumerator():
    box = rt.Box(name='SM_NEnum_Main')
    multi = rt.Multimaterial(numsubs=2)
    multi.name = 'M_NEnum'
    for i, nm in ((1, 'T_E_Diffuse_1.1001.png'), (2, 'T_E_Diffuse_1.1002.png')):
        m = rt.Standardmaterial()
        m.name = 'M_NEnum_%d' % i
        rt.setSubMtl(multi, i, m)
        p = str(DATA / 'enum' / nm).replace('\\', '/')
        (DATA / 'enum').mkdir(parents=True, exist_ok=True)
        (DATA / 'enum' / nm).write_bytes(nbuild.png('rgba_island'))
        m.diffuseMap = rt.Bitmaptexture(fileName=p)
    box.material = multi
    tm = agr._load_core('tex_max.py', 'agr_tools_tex_max')
    rows = tm.scene_bitmaps(tex, [box])[0]['rows']
    got = sorted((r['matid'], r['udim'], r['role']) for r in rows)
    assert got == [(1, 1001, 'diffuse'), (2, 1002, 'diffuse')], got
    return got


for name, fn in (('dilate_files', dilate_files), ('polygon_rows', polygon_rows), ('plugs_apply', plugs_apply),
                 ('vpmmaps', vpmmaps), ('enumerator', enumerator)):
    check(name, fn)

(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
print(json.dumps({'errors': list(summary['errors']), 'checks': list(summary['checks'])}))
if summary['errors']:
    for k, v in summary['errors'].items():
        print('ERROR', k, v)
    sys.exit(1)
