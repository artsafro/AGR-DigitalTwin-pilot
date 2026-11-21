"""new-case: #1024 `assets` (Flora) native acceptance in locked batch Max through the AGR Lab runner.

Inputs come from the job, never from this repository (customer library, not committed):
  AGR_TEST_OUTPUT   NEW directory for results
  AGR_FLORA_MAX     the runner's COPY of the library .max (job `inputs`, in the run's work dir)
  AGR_FLORA_TEX     the library TextureFlora folder (only read: PNGs are copied into the project folder)
  AGR_FLORA_ORIG    optional: original library .max, hashed before/after to prove it was not touched
  AGR_ASSET_IDS     comma list of species bases to import (5)
Steps: disposable library mirror (copy of the .max) -> scan -> index -> cached rescan -> import with a decoy scene
material (policy reuse) -> readback (names, layers, props, materials, textures, scale, pivots, layout) -> re-run
adds nothing -> undo -> fresh scene with policy copy -> journal lines. The scene is saved only into OUT.
"""
import hashlib
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
PKG = Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'
sys.path.insert(0, str(PKG))
import assets_max as amx  # noqa: E402

core = amx.core
summary = {'max_version': list(rt.maxVersion())[:3], 'checks': {}, 'errors': {}, 'seconds': {}}
BASES = [b.strip() for b in os.environ['AGR_ASSET_IDS'].split(',') if b.strip()]
LIB = 'flora'
IDS = [LIB + ':' + b for b in BASES]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(name, fn):
    t0 = time.perf_counter()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['seconds'][name] = round(time.perf_counter() - t0, 2)


def reset():
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0


orig = os.environ.get('AGR_FLORA_ORIG')
orig_sha_before = sha(orig) if orig and os.path.isfile(orig) else None
mirror = OUT / 'library'
(mirror / 'PreviewFlora').mkdir(parents=True)
shutil.copyfile(os.environ['AGR_FLORA_MAX'], mirror / Path(os.environ['AGR_FLORA_MAX']).name)
cache = OUT / 'cache'
project = OUT / 'project'
settings = {'project_dir': str(project), 'cache_dir': str(cache), 'materials': 'reuse', 'textures': 'project',
            'versions': ['high', 'low'], 'gap_m': 1.0, 'row_limit_m': 20.0}
state = {}


def step_scan():
    t0 = time.perf_counter()
    idx = amx.scan_flora(str(mirror), str(cache), lib=LIB)
    t1 = time.perf_counter()
    again = amx.scan_flora(str(mirror), str(cache), lib=LIB)
    t2 = time.perf_counter()
    state['idx'] = idx
    by = {r['id']: r for r in idx['assets']}
    assert all(i in by for i in IDS), [i for i in IDS if i not in by]
    assert again['assets'] == idx['assets']
    return {'species': len(idx['assets']), 'report': {k: v for k, v in idx['report'].items()
                                                      if k != 'preview_match'},
            'sha256': idx['sources'][next(iter(idx['sources']))]['sha256'],
            'scan_s': round(t1 - t0, 2), 'cached_rescan_s': round(t2 - t1, 2),
            'selected': {i: {'versions': by[i]['versions'], 'warnings': by[i]['warnings']} for i in IDS}}


def decoy_material():
    """Scene material named like the library material of the 4th asset (policy reuse must keep it). Built outside
    any undo record (pilot 0.8: in 3dsmaxbatch the pymxs records of one ExecuteFile collapse into one step)."""
    import pymxs
    with pymxs.undo(False):
        b = rt.Box(length=0.5, width=0.5, height=0.5, pos=rt.Point3(-5, -5, 0))
        b.name = 'decoy_box'
        m = rt.StandardMaterial(name=BASES[3] + '_high')
        b.material = m
    return int(rt.getHandleByAnim(m))


def bbox_overlap(a, b):
    return all(a[0][i] < b[1][i] - 1e-6 and b[0][i] < a[1][i] - 1e-6 for i in (0, 1))


def step_import_reuse():
    reset()
    decoy = decoy_material()
    n0 = len(rt.objects)
    rep = amx.run_import(state['idx'], IDS, settings, str(cache), scene_label='assets-native-A',
                         texture_dirs=[os.environ['AGR_FLORA_TEX']])
    rb = amx.readback(LIB)
    state['rb_a'] = rb
    assert rep['status'] == 'done', rep['errors']
    names = sorted(r['name'] for r in rb)
    expect = sorted(b + '_' + v for b in BASES for v in ('high', 'low'))
    assert names == expect, names
    for r in rb:
        assert r['layer'] == 'ASSET_flora_' + r['version'], r
        assert r['id'] == LIB + ':' + r['name'].rsplit('_', 1)[0]
        assert r['sha256'] == state['idx']['assets'][0]['source']['sha256']
        assert r['scale'] == [1.0, 1.0, 1.0]
        assert abs(r['pivot_m'][2]) < 1e-6, r
        for bm in r['bitmaps']:
            assert bm['exists'] and Path(bm['file']).parent == project / 'assets' / LIB / 'textures', bm
    reuse = [r for r in rb if r['name'] == BASES[3] + '_high'][0]
    assert reuse['material_handle'] == decoy, 'policy reuse must keep the scene material'
    boxes = [(r['name'], r['bbox_m']) for r in rb]
    overl = [(a[0], b[0]) for i, a in enumerate(boxes) for b in boxes[i + 1:] if bbox_overlap(a[1], b[1])]
    assert not overl, overl
    lo_x = min(r['bbox_m'][0][0] for r in rb)
    lo_y = min(r['bbox_m'][0][1] for r in rb)
    assert abs(lo_x) < 1e-4 and abs(lo_y) < 1e-4, (lo_x, lo_y)
    n_after = len(rt.objects)
    rt.saveMaxFile(str(OUT / 'assets_import_reuse.max'), quiet=True)
    rep2 = amx.run_import(state['idx'], IDS, settings, str(cache), scene_label='assets-native-A',
                          texture_dirs=[os.environ['AGR_FLORA_TEX']])
    assert rep2['counts']['merged'] == 0 and rep2['counts']['skipped'] == 10, rep2['counts']
    assert len(rt.objects) == n_after, 're-run adds nothing'
    gone = amx.remove_imported(lib=LIB)
    assert sorted(gone) == expect and len(rt.objects) == n0, 'rollback by props'
    mats = sorted({r['material'] for r in rb})
    return {'report': {k: rep[k] for k in ('status', 'counts', 'textures', 'duration_s', 'plan_sha256')},
            'rerun_counts': rep2['counts'], 'objects_before': n0, 'objects_after': n_after,
            'removed_by_props': len(gone), 'materials': mats, 'decoy_kept': True,
            'readback': rb, 'moves': rep['moves']}


def step_undo():
    """One import, then ONE 'max undo' (measured, not asserted: batch collapses records; GUI check is separate)."""
    reset()
    import pymxs
    with pymxs.undo(False):
        rt.Box(name='keep_box', length=1, width=1, height=1)
    n0 = len(rt.objects)
    rep = amx.run_import(state['idx'], IDS[:2], settings, str(cache), scene_label='assets-native-U',
                         texture_dirs=[os.environ['AGR_FLORA_TEX']])
    n1 = len(rt.objects)
    try:
        rt.execute('max undo')
        err = None
    except Exception as exc:  # noqa: BLE001 - the measurement is the outcome
        err = str(exc)[:400]
    n2 = len(rt.objects)
    return {'merged': rep['counts']['merged'], 'objects_before': n0, 'after_import': n1, 'after_one_undo': n2,
            'undo_error': err, 'undo_removed_import': n2 == n0 and err is None}


def step_import_copy():
    reset()
    decoy = decoy_material()
    s = dict(settings, materials='copy', textures='library')
    rep = amx.run_import(state['idx'], IDS[3:4], s, str(cache), scene_label='assets-native-B',
                         texture_dirs=[os.environ['AGR_FLORA_TEX']])
    rb = amx.readback(LIB)
    hi = [r for r in rb if r['version'] == 'high'][0]
    assert rep['status'] == 'done', rep['errors']
    assert hi['material_handle'] != decoy and hi['material'] == BASES[3] + '_high_copy', hi['material']
    for r in rb:
        for bm in r['bitmaps']:
            assert bm['exists'] and Path(bm['file']).parent == Path(os.environ['AGR_FLORA_TEX']), bm
    return {'material_high': hi['material'], 'bitmaps': hi['bitmaps'], 'counts': rep['counts']}


def step_journal():
    out = {}
    for label in ('assets-native-A', 'assets-native-B'):
        p = core.journal_path(label, os.environ['LOCALAPPDATA'])
        lines = [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines()]
        out[label] = [(x['tool'], x['mode'], x['status'], x['counts']) for x in lines]
    assert len(out['assets-native-A']) == 2 and len(out['assets-native-B']) == 1
    return out


def step_window():
    """The browser window inside Max (PySide2 in 2024): real index, selection, settings, grab to PNG in OUT."""
    import assets_ui
    from ui_qt import QtWidgets, BINDING
    app = QtWidgets.QApplication.instance()
    be = assets_ui.MaxBackend()
    s = dict(settings, libraries={'flora': str(mirror)}, selection=IDS)
    w = assets_ui.AssetsWindow(be, settings=s)
    w.resize(1280, 800)
    w.show()
    for _ in range(40):
        app.processEvents()
        time.sleep(0.05)
    w.search.setText('t1')
    app.processEvents()
    rows = w.model.rowCount()
    sel = w.sel.count()
    w.grab().save(str(OUT / 'window_max2024.png'))
    w.close()
    saved = assets_ui.load_settings()
    assert sel == len(IDS) and rows > 0 and saved['selection'] == IDS
    return {'binding': BINDING, 'rows_after_search_t1': rows, 'selected': sel, 'status': w.status.text(),
            'png': (OUT / 'window_max2024.png').stat().st_size}


check('scan', step_scan)
if 'idx' in state:
    check('import_reuse', step_import_reuse)
    check('import_copy', step_import_copy)
    check('journal', step_journal)
    check('window', step_window)
    check('undo', step_undo)
summary['original_sha256'] = {'before': orig_sha_before,
                              'after': sha(orig) if orig_sha_before else None}
if orig_sha_before:
    summary['original_unchanged'] = summary['original_sha256']['before'] == summary['original_sha256']['after']
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
if summary['errors'] or summary.get('original_unchanged') is False:
    raise RuntimeError('assets native checks failed: ' + ', '.join(summary['errors']))
