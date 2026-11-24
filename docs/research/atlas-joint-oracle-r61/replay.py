"""Standing #61: AC08 NPM joint count/phase against the slide-49 contract (OBSERVE).

Renders exactly as #58 (pinned code/specs/ZIPs), reads the v010 VPM back for the oracle frame, runs the unchanged
compare_facades.py on both revisions, reproduces its NPM rows in-process (parity) and scores in-memory probes.
"""
import importlib
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
R58_REV = 'd45e1ea44471de876f577b63a403f1be43c118ec'
ORACLE_REV = '543652498f34756feef1a729a364c569b3dc8663'      # v010 spec, sheet and checker code
SLIDE = Path('G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-pilot-v010/slide49.png')
SLIDE_SHA = '256f32da2a04141fc6b62b46ed9710c1830c5ffd3f48f2bac578719c0208a8fd'
CODE = ('jobs/TEC26-OKS/scripts/compare_facades.py', 'jobs/TEC26-OKS/scripts/joint_count.py',
        'jobs/TEC26-OKS/scripts/finish_map.py', 'jobs/TEC26-OKS/scripts/qa_readback.py',
        'jobs/KPP1/scripts/vpm_textures.json')
VIEW = {'+y': 'north', '-y': 'south', '+x': 'east', '-x': 'west'}
FRACS = (0.2, 0.95)
SHIFT, SMALL = 20, 2


def git(*args):
    return subprocess.check_output(['git', *args])


def load_r58(out):
    """The #58 driver from its pinned commit (stage/render inputs, sha, Blender pins); never edited here."""
    path = out / 'r58_replay.py'
    path.write_bytes(git('show', f'{R58_REV}:docs/research/atlas-drift-r58/replay.py'))
    spec = importlib.util.spec_from_file_location('r58', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def je(rows):
    if any('missing' not in r for r in rows.values()):
        raise ValueError(f'row without panel samples: {rows}')      # coverage failure -> inconclusive
    return sum(len(r['missing']) + len(r['extra']) for r in rows.values())


def oracle_rows(jc, img, view, key, lo, hi, zlo, zhi, ribs):
    """compare_facades lines 166-172, verbatim arguments."""
    axis = 1 if key in ('+x', '-x') else 0
    rows, ys = {}, []
    c = np.asarray(view['center'], float)
    W, H = view['res']
    scale = view['ortho_scale'] / W
    for frac in FRACS:
        z = zlo + frac * (zhi - zlo)
        ys.append(int(round(H / 2 - (z - c[2]) / scale - 0.5)))
        s, lum = jc.render_row(img, view, axis, z, lo, hi)
        rows[f'z={z:.3f}'] = jc.count_joints(s, lum, lo, hi, ribs, tol=0.01, dark=0.85)
    return rows, ys


def shift_rows(img, ys, px):
    out = img.copy()
    for y in ys:
        out[y, px:, :3] = img[y, :-px, :3]
    return out


def outside_rows(img, ys):
    out = img.copy()
    keep = np.zeros(img.shape[0], bool)
    keep[ys] = True
    out[~keep, :, :3] = 17
    return out


def changed(a, b):
    return int(np.any(a[..., :3] != b[..., :3], axis=2).sum())


def score_version(code, cf, jc, spec, sheet, readback, renders, out):
    """Unchanged compare_facades.main, then in-process parity and probes on its NPM rows."""
    with (out.parent / f'{out.name}.log').open('w', encoding='utf-8') as log:
        done = subprocess.run([sys.executable, str(code / CODE[0]), str(spec), str(sheet), str(renders),
                               str(readback), str(out)], stdout=log, stderr=subprocess.STDOUT)
    rep = json.loads((out / 'compare.json').read_text(encoding='utf-8'))
    sp, sh = (json.loads(Path(p).read_text(encoding='utf-8')) for p in (spec, sheet))
    meta = json.loads((renders / 'renders.json').read_text(encoding='utf-8'))
    vrb = json.loads(Path(readback).read_text(encoding='utf-8'))
    vmain = next(o for o in vrb['objects'] if not o['name'].startswith('UCX_'))
    V = np.asarray(vmain['vertices'], float)
    uvs = [np.asarray(u, float) for u in vmain['face_uvs']]
    res = {'compare_exit': done.returncode, 'facades': {}, 'JE': 0, 'JE_vpm': 0,
           'probes': {k: {'JE': 0, 'changed_px': {}} for k in ('shift20', 'shift2', 'outside')}}
    for name, fc in sp['facades'].items():
        key = fc['normal']
        ud = sp['finishes'][fc['finish']]['udim']
        keep = lambda t, ud=ud: int(1001 + np.floor(uvs[t].mean(0)[0]) + 10 * np.floor(uvs[t].mean(0)[1])) == ud  # noqa
        tris = jc.facade_triangles(V, vmain['faces'], keep, key)
        lo, hi, zlo, zhi = jc.field_extent(V, vmain['faces'], tris, key)
        view = meta['npm']['views'][VIEW[key]]
        img = np.asarray(Image.open(renders / view['png']).convert('RGB'))
        rows, ys = oracle_rows(jc, img, view, key, lo, hi, zlo, zhi, fc['ribs'])
        got = rep['facades'][name]
        if json.loads(json.dumps(rows)) != got['npm_render_rows']:
            raise ValueError(f'parity failure {out.name} {name}')
        f = {'contract_joints': fc['ribs'] - 1, 'slide_joints': got['slide_joints'],
             'npm_joints': got['npm_render_joints'], 'vpm_joints': got['vpm_render_joints'], 'match': got['match'],
             'JE': je(got['npm_render_rows']), 'JE_vpm': je(got['vpm_render_rows']), 'rows_y': ys,
             'npm_rows': {z: {k: r.get(k) for k in ('joints_found', 'joints_expected', 'missing', 'extra',
                                                     'hidden_by_other_finish', 'max_position_error_m',
                                                     'first_joint_from_field_m')}
                          for z, r in got['npm_render_rows'].items()}}
        found = [r.get('found_m', []) for r in got['npm_render_rows'].values()]
        f['npm_found_pitch_m'] = [round(float(np.median(np.diff(x))), 4) if len(x) > 1 else None for x in found]
        for probe, mod in (('shift20', shift_rows(img, ys, SHIFT)), ('shift2', shift_rows(img, ys, SMALL)),
                           ('outside', outside_rows(img, ys))):
            prow, _ = oracle_rows(jc, mod, view, key, lo, hi, zlo, zhi, fc['ribs'])
            res['probes'][probe]['JE'] += je(prow)
            res['probes'][probe]['changed_px'][name] = changed(img, mod)
        res['JE'] += f['JE']
        res['JE_vpm'] += f['JE_vpm']
        res['facades'][name] = f
    for p in res['probes'].values():
        p['delta'] = p['JE'] - res['JE']
        p['exercised'] = all(v > 0 for v in p['changed_px'].values())
    return res


def run(out):
    out.mkdir(parents=True)
    r58 = load_r58(out)
    start = time.monotonic()
    receipt = {'rounds': [], 'attempts': [], 'cameras': {}, 'status': 'running', 'hypothesis': 'inconclusive'}
    originals = {r58.DRIVE / f'559-tec26-oks-ac08-pilot-{v}' / name: digest
                 for v in r58.ZIPS for name, digest in zip(r58.FILES, r58.ZIPS[v], strict=True)}

    def check_originals():
        return all(r58.sha(p) == d for p, d in originals.items())

    def blender(argv, log, tmp):
        with log.open('wb') as fh:
            done = subprocess.run(argv, env=os.environ | {k: str(tmp) for k in ('TEMP', 'TMP', 'TMPDIR')} |
                                  {'PX_PER_M': '400'}, stdout=fh, stderr=subprocess.STDOUT,
                                  timeout=max(1, 420 - (time.monotonic() - start)))
        done.check_returncode()

    try:
        if not check_originals() or r58.sha(SLIDE) != SLIDE_SHA:
            raise ValueError('input preflight mismatch')
        version = subprocess.check_output([str(r58.BLENDER), '--version'], text=True)
        if 'Blender 5.1.2' not in version or 'ec6e62d40fa9' not in version:
            raise ValueError('Blender build mismatch')
        receipt.update(blender=version.splitlines()[0] + ' ec6e62d40fa9', blender_exe_sha256=r58.sha(r58.BLENDER),
                       reducer_sha256=r58.sha(Path(__file__)), r58_driver_sha256=r58.sha(out / 'r58_replay.py'),
                       archives={str(p): h for p, h in originals.items()}, slide_sha256=SLIDE_SHA, code={})
        code = out / 'code'
        for rel in CODE:
            (code / rel).parent.mkdir(parents=True, exist_ok=True)
            (code / rel).write_bytes(git('show', f'{ORACLE_REV}:{rel}'))
            receipt['code'][f'{ORACLE_REV}:{rel}'] = r58.sha(code / rel)
        for name in ('render_facades.py', 'vpm_uv.py'):
            (out / name).write_bytes(git('show', f'{r58.RENDER_REV}:jobs/TEC26-OKS/scripts/{name}'))
            receipt['code'][f'{r58.RENDER_REV}:{name}'] = r58.sha(out / name)
        oracle = out / 'oracle'
        oracle.mkdir()
        shutil.copyfile(SLIDE, oracle / 'slide49.png')
        spec = json.loads(git('show', f'{ORACLE_REV}:jobs/TEC26-OKS/AC08/vpm_textures.json'))
        spec['presentation']['image'] = str(oracle / 'slide49.png').replace('\\', '/')
        (oracle / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
        (oracle / 'sheet-facades.json').write_bytes(git('show', f'{ORACLE_REV}:jobs/TEC26-OKS/AC08/sheet-facades.json'))
        receipt['oracle'] = {p.name: r58.sha(p) for p in sorted(oracle.iterdir())}
        sys.path.insert(0, str(code / 'jobs/TEC26-OKS/scripts'))
        cf, jc = importlib.import_module('compare_facades'), importlib.import_module('joint_count')
        for i in range(1, 4):
            begin = time.monotonic()
            rnd = {'round': i}
            folders = {}
            for v in r58.SPECS:
                folder = out / f'r{i}-{v}'
                inputs, tmp = folder / 'inputs', folder / 'temp'
                folder.mkdir()
                tmp.mkdir()
                hashes = r58.stage(inputs, v)
                case = dict(round=i, version=v, step='render', inputs=hashes, status='started')
                receipt['attempts'].append(case)
                t0 = time.monotonic()
                blender([str(r58.BLENDER), '--background', '--factory-startup', '--disable-autoexec', '--threads', '1',
                         '--python-exit-code', '1', '--python', str(out / 'render_facades.py'), '--',
                         str(inputs / 'spec.json'), str(inputs / 'SM_Nku_1.fbx'), str(inputs),
                         str(inputs / '0000_Nku_1_01.fbx'), str(folder / 'renders')], folder / 'blender.log', tmp)
                case.update(status='rendered', wall_seconds=time.monotonic() - t0)
                if {p.name: r58.sha(p) for p in inputs.iterdir()} != hashes:
                    raise ValueError('staged operand parity failure')
                meta = json.loads((folder / 'renders' / 'renders.json').read_bytes())
                for view in r58.VIEWS:
                    for prof in ('vpm', 'npm'):
                        cam = json.loads(json.dumps([meta[prof]['bbox'], {
                            k: x for k, x in meta[prof]['views'][view].items() if k != 'png'}]))
                        if receipt['cameras'].setdefault(view, cam) != cam:
                            raise ValueError(f'camera mismatch {view} {v} {prof}')
                folders[v] = folder
            rb_dir = out / f'r{i}-readback'
            rb_dir.mkdir()
            shutil.copyfile(folders['v010'] / 'inputs' / 'SM_Nku_1.fbx', rb_dir / 'SM_Nku_1.fbx')
            t0 = time.monotonic()
            blender([str(r58.BLENDER), '--background', '--factory-startup', '--disable-autoexec',
                     '--python-exit-code', '1', '--python', str(code / CODE[3]), '--',
                     str(rb_dir / 'SM_Nku_1.fbx'), str(rb_dir / 'vpm.readback.json')], rb_dir / 'blender.log', rb_dir)
            rnd['readback_seconds'] = time.monotonic() - t0
            rnd['readback_sha256'] = r58.sha(rb_dir / 'vpm.readback.json')
            for v, folder in folders.items():
                rnd[v] = score_version(code, cf, jc, oracle / 'spec.json', oracle / 'sheet-facades.json',
                                       rb_dir / 'vpm.readback.json', folder / 'renders', folder / 'compare')
            rnd['delta'] = rnd['v007']['JE'] - rnd['v010']['JE']
            rnd['wall_seconds'] = time.monotonic() - begin
            receipt['rounds'].append(rnd)
            print({'round': i, 'JE_v007': rnd['v007']['JE'], 'JE_v010': rnd['v010']['JE'],
                   'wall': round(rnd['wall_seconds'], 3)}, flush=True)
            if i == 1 and (rnd['wall_seconds'] > 120 or 420 - (time.monotonic() - start) < 2 * rnd['wall_seconds'] + 15):
                receipt['status'] = 'budget_stop'
                break
        if len(receipt['rounds']) == 3:
            ds = [r['delta'] for r in receipt['rounds']]
            median, spread = statistics.median(ds), max(ds) - min(ds)
            v010 = receipt['rounds']
            controls = dict(
                accepted_clean=all(r['v010']['JE'] == 0 for r in v010),
                slide_contract=all(f['slide_joints'] == f['contract_joints']
                                   for r in v010 for f in r['v010']['facades'].values()),
                shift20_v010=all(r['v010']['probes']['shift20']['delta'] >= 8 for r in v010),
                shift2_v010=all(r['v010']['probes']['shift2']['delta'] == 0 for r in v010),
                outside_both=all(r[v]['probes']['outside']['delta'] == 0 for r in v010 for v in r58.SPECS),
                exercised=all(p['exercised'] for r in v010 for v in r58.SPECS for p in r[v]['probes'].values()))
            receipt.update(status='completed', median_delta=median, paired_spread=spread, controls=controls)
            if min(ds) <= 0:
                receipt['hypothesis'] = 'refuted'
            elif spread == 0 and median >= 1 and all(controls.values()):
                receipt['hypothesis'] = 'confirmed'
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as err:
        receipt.update(status='timeout' if isinstance(err, subprocess.TimeoutExpired) else 'refused',
                       error=f'{type(err).__name__}: {err}')
    finally:
        receipt['originals_match_after'] = check_originals()
        receipt['wall_seconds'] = time.monotonic() - start
        if not receipt['originals_match_after']:
            receipt.update(status='input_parity_failure', hypothesis='inconclusive')
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print({k: v for k, v in receipt.items() if k in ('status', 'hypothesis', 'median_delta', 'paired_spread',
                                                          'controls', 'error', 'wall_seconds')})
    return 0 if receipt['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(run(Path(sys.argv[1]).resolve()))
