"""new-case: #1024 `assets` MAF import from A101 archives, native acceptance through the AGR Lab runner.

  AGR_TEST_OUTPUT  NEW directory;  AGR_MAF_ZIPS  ';'-separated runner COPIES of the archives (job inputs).
A disposable library folder in OUT holds copies of the zips (one in a subfolder, like 3.1_ЮС). Steps: scan ->
MAX route import of every archive (extract into the project folder, merge, textures from that folder) ->
readback (names, layers, props, units: bbox vs sidecar mm within 1 mm, textures exist) -> re-run adds nothing ->
rollback by props -> FBX route of the first archive in a fresh scene (bbox vs the MAX route within 1 cm).
"""
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'))
import assets_max as amx  # noqa: E402

core = amx.core
LIB = 'maf'
summary = {'max_version': list(rt.maxVersion())[:3], 'checks': {}, 'errors': {}, 'seconds': {}}
zips = [Path(p) for p in os.environ['AGR_MAF_ZIPS'].split(';') if p]
lib = OUT / 'library'
for i, z in enumerate(zips):
    d = lib / ('sub' if i % 2 else '')
    d.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(z, d / z.name)
cache, project = OUT / 'cache', OUT / 'project'
settings = {'project_dir': str(project), 'cache_dir': str(cache), 'materials': 'reuse', 'source': 'max',
            'versions': ['high', 'low'], 'gap_m': 1.0, 'row_limit_m': 30.0}
state = {}


def check(name, fn):
    t0 = time.perf_counter()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['seconds'][name] = round(time.perf_counter() - t0, 2)


def reset():
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0


def size(bb):
    return [bb[1][i] - bb[0][i] for i in range(3)]


def step_scan():
    idx = core.scan_maf(str(lib), str(cache), lib=LIB)
    core.save_index(str(cache), idx)
    state['idx'] = idx
    assert len(idx['assets']) == len(zips) and not idx['report']['problems'], idx['report']
    return {a['name']: {'versions': sorted(a['versions']), 'sidecar': bool(a.get('meta')), 'path': a['source']['path']}
            for a in idx['assets']}


def step_max_route():
    reset()
    ids = [a['id'] for a in state['idx']['assets']]
    rep = amx.run_import(state['idx'], ids, settings, str(cache), scene_label='maf-native-A')
    assert rep['status'] == 'done', rep['errors']
    rb = amx.readback(LIB)
    state['rb'] = rb
    out = {}
    for a in state['idx']['assets']:
        rows = [r for r in rb if r['id'] == a['id']]
        assert sorted(r['version'] for r in rows) == sorted(a['versions']), (a['name'], rows)
        for r in rows:
            assert r['layer'] == 'ASSET_maf_' + r['version'], r
            assert r['sha256'] == core.sha256_file(str(lib / a['source']['path'])), r
            assert all(b['exists'] for b in r['bitmaps']), r['bitmaps']
            assert all(Path(b['file']).parent == project / 'assets' / LIB / a['name'] for b in r['bitmaps']), r
            geo = ((a.get('meta') or {}).get('geometry') or {}).get(r['version'])
            got = size(r['bbox_m'])
            row = {'name': r['name'], 'bbox_m': [round(x, 4) for x in got], 'bitmaps': len(r['bitmaps']),
                   'material': r['material']}
            if geo:
                want = [geo['bbox'][c] / 1000.0 for c in 'xyz']
                row['sidecar_m'] = want
                row['max_dev_mm'] = round(max(abs(x - y) for x, y in zip(got, want)) * 1000, 3)
                assert row['max_dev_mm'] <= 1.0, row
            out.setdefault(a['name'], []).append(row)
    n = len(rt.objects)
    rep2 = amx.run_import(state['idx'], ids, settings, str(cache), scene_label='maf-native-A')
    assert rep2['counts']['merged'] == 0 and len(rt.objects) == n
    rt.saveMaxFile(str(OUT / 'maf_import_max_route.max'), quiet=True)
    gone = amx.remove_imported(lib=LIB)
    assert len(gone) == n and len(rt.objects) == 0
    return {'report': {k: rep[k] for k in ('status', 'counts', 'textures', 'duration_s', 'extracted')},
            'rerun': rep2['counts'], 'objects': out}


def step_fbx_route():
    reset()
    a = state['idx']['assets'][0]
    s = dict(settings, source='fbx', project_dir=str(OUT / 'project_fbx'))
    rep = amx.run_import(state['idx'], [a['id']], s, str(cache), scene_label='maf-native-B')
    assert rep['status'] == 'done', rep['errors']
    rb = amx.readback(LIB)
    res = {}
    for r in rb:
        ref = [x for x in state['rb'] if x['id'] == r['id'] and x['version'] == r['version']][0]
        dev = max(abs(x - y) for x, y in zip(size(r['bbox_m']), size(ref['bbox_m'])))
        res[r['version']] = {'name': r['name'], 'bbox_m': [round(x, 4) for x in size(r['bbox_m'])],
                             'dev_vs_max_route_mm': round(dev * 1000, 2), 'bitmaps': r['bitmaps'][:3],
                             'material': r['material']}
        assert dev <= 0.01, res
    return {'counts': rep['counts'], 'extracted': rep.get('extracted'), 'versions': res}


check('scan', step_scan)
if 'idx' in state:
    check('max_route', step_max_route)
    if 'rb' in state:
        check('fbx_route', step_fbx_route)
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
if summary['errors']:
    raise RuntimeError('MAF native checks failed: ' + ', '.join(summary['errors']))
