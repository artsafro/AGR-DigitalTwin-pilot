"""new-case: #1024 textures of imported A101 assets, native acceptance through the AGR Lab runner (Max 2024).

  AGR_TEST_OUTPUT NEW dir; AGR_TEST_PACKAGE built MZP (for the existing atlas buttons);
  AGR_FLORA_MAX runner copy of the Flora library .max; AGR_FLORA_TEX textures folder (read only);
  AGR_FLORA_IDS comma list of species bases; AGR_MAF_ZIPS ';' list of runner copies of MAF archives.
Steps on one disposable scene (saved only into OUT):
  import Flora + MAF (High + Low) -> NPM: atlas.flora on the Flora Low objects, atlas.groundel profile npm on the
  MAF Low objects (preview -> apply, existing buttons) -> VPM: project folder already holds T_ADDR_*_1.1001..1003
  (the building); Flora sets go to the next free UDIMs, MAF after them; maps copied under VPM names, placeholders,
  UVs moved by whole tiles, read back; packed 4K plan with tile_limit 1 (plan only).
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
os.environ['AGR_NO_PROMPT'] = '1'
PKG = Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'
sys.path.insert(0, str(PKG))
import assets_max as amx  # noqa: E402

core = amx.core
summary = {'max_version': list(rt.maxVersion())[:3], 'checks': {}, 'errors': {}, 'seconds': {}}
ADDR = 'ADDR'


def check(name, fn):
    t0 = time.perf_counter()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['seconds'][name] = round(time.perf_counter() - t0, 2)


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(os.environ['AGR_TEST_PACKAGE'])
    sys.path.insert(0, str(OUT / 'installed'))
    import runtime as agr
    return agr


pkg_sha = hashlib.sha256(Path(os.environ['AGR_TEST_PACKAGE']).read_bytes()).hexdigest()
agr = install()
summary['package_sha256'] = pkg_sha
rt.resetMaxFile(rt.Name('noPrompt'))
rt.units.SystemType = rt.Name('meters')
rt.units.SystemScale = 1.0
project = OUT / 'project'
cache = OUT / 'cache'
state = {}


def step_import():
    flib = OUT / 'flora_lib'
    (flib / 'PreviewFlora').mkdir(parents=True)
    shutil.copyfile(os.environ['AGR_FLORA_MAX'], flib / Path(os.environ['AGR_FLORA_MAX']).name)
    fidx = amx.scan_flora(str(flib), str(cache), lib='flora')
    mlib = OUT / 'maf_lib'
    mlib.mkdir()
    for z in [p for p in os.environ['AGR_MAF_ZIPS'].split(';') if p]:
        shutil.copyfile(z, mlib / Path(z).name)
    midx = core.scan_maf(str(mlib), str(cache), lib='maf')
    s = {'project_dir': str(project), 'cache_dir': str(cache), 'versions': ['high', 'low'], 'row_limit_m': 25.0}
    ids = ['flora:' + b.strip() for b in os.environ['AGR_FLORA_IDS'].split(',') if b.strip()]
    r1 = amx.run_import(fidx, ids, s, str(cache), scene_label='tex', texture_dirs=[os.environ['AGR_FLORA_TEX']])
    r2 = amx.run_import(midx, [a['id'] for a in midx['assets']], dict(s, gap_m=2.0), str(cache), scene_label='tex')
    for g in rt.objects:  # MAF block next to the Flora block
        if str(rt.getUserProp(g, core.PROP_LIB)) == 'maf':
            g.pos = g.pos + rt.Point3(0, 20, 0)
    assert r1['status'] == r2['status'] == 'done', (r1['errors'], r2['errors'])
    return {'flora': r1['counts'], 'maf': r2['counts']}


def low(lib):
    return [o for o in rt.objects if str(rt.getUserProp(o, core.PROP_LIB)) == lib and
            str(rt.getUserProp(o, core.PROP_VER)) == 'low']


def step_npm_flora():
    nodes = low('flora')
    rep = agr.edits_090('atlas.flora', 'preview', None, nodes, {'out_dir': str(OUT / 'npm_flora')})
    res = {'status': rep['status'], 'report': {k: v for k, v in rep.items() if k != 'plan'},
           'atlas': {k: v for k, v in (rep.get('plan') or {}).get('atlas', {}).items() if k != 'cells'}}
    if rep['status'] == 'pass':
        out = agr.edits_090('atlas.flora', 'apply', rep, nodes)
        res['written'] = out['plan'].get('written')
        res['done'] = [{k: r.get(k) for k in ('source', 'faces', 'faces_in_tile')} for r in out['plan']['done']]
    return res


def step_npm_maf():
    nodes = low('maf')
    rep = agr.edits_090('atlas.groundel', 'preview', None, nodes,
                        {'profile': 'npm', 'size': 2048, 'out_dir': str(OUT / 'npm_maf')})
    res = {'status': rep['status'], 'report': {k: v for k, v in rep.items() if k != 'plan'},
           'atlas': {k: v for k, v in (rep.get('plan') or {}).get('atlas', {}).items() if k != 'cells'}}
    if rep['status'] == 'pass':
        out = agr.edits_090('atlas.groundel', 'apply', rep, nodes)
        res['written'] = out['plan'].get('written')
    return res


def step_vpm():
    folder = project / 'textures' / 'vpm'
    folder.mkdir(parents=True)
    for i, role in enumerate(('Diffuse', 'ERM', 'Normal')):
        for u in (1001, 1002, 1003):
            amx.write_flat_png(str(folder / 'T_{}_{}_1.{}.png'.format(ADDR, role, u)), (90, 90, 90), 16)
    packed = amx.vpm_udims('flora', 'flora', ADDR, str(project), mode='preview', tile_limit=1)
    pf = amx.vpm_udims('flora', 'flora', ADDR, str(project), mode='apply')
    assert pf['applied'] and [t[1] for t in pf['tiles']] == [1004, 1005, 1006, 1007, 1008], pf['tiles']
    pm = amx.vpm_udims('maf', 'maf', ADDR, str(project), mode='apply')
    assert pm['applied'] and [t[1] for t in pm['tiles']] == [1009, 1010], pm['tiles']
    for p in (pf, pm):
        for b in p['readback']:
            assert b['inside_tile'] and b['maps_exist'] and b['maps_udim'] == [b['udim']], b
    rt.saveMaxFile(str(OUT / 'assets_textures.max'), quiet=True)
    files = sorted(os.listdir(folder))
    return {'packed_plan': {k: packed[k] for k in ('mode', 'texel_px_per_m', 'tiles', 'fill')},
            'packed_rows': [{k: r[k] for k in ('material', 'udim', 'x', 'y', 'w', 'h')} for r in packed['rows']],
            'flora': {'tiles': pf['tiles'], 'readback': pf['readback'],
                      'rows': [{'material': r['material'], 'udim': r['udim'], 'copy': [c['stem'] for c in r['copy']],
                                'placeholders': [c['stem'] for c in r['placeholders']]} for r in pf['rows']]},
            'maf': {'tiles': pm['tiles'], 'readback': pm['readback'],
                    'rows': [{'material': r['material'], 'udim': r['udim'], 'copy': [c['stem'] for c in r['copy']],
                              'placeholders': [c['stem'] for c in r['placeholders']]} for r in pm['rows']]},
            'files': files}


check('import', step_import)
if 'import' in summary['checks']:
    check('npm_flora', step_npm_flora)
    check('npm_maf', step_npm_maf)
    check('vpm', step_vpm)
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
if summary['errors']:
    raise RuntimeError('textures native checks failed: ' + ', '.join(summary['errors']))
