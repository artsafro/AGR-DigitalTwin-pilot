"""R105 evidence replay: key-free typical-storey band selector; does not build or modify a model."""
from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from dt_ai.core.blender_runner import run_blender  # noqa: E402
from tools.trainer.trainer import TOL, bounds_step  # noqa: E402  # type: ignore[import-not-found]

CONTRACT = ROOT / 'docs/research/autoresearch-trainer-storey-band-r105.md'
BASE = 'e1f3f168d7139b290871e5e49a0f3b84ff0ca668'
EV = Path('G:/Мой диск/AGR-evidence')
DUMP = 'tools/methods/body/revit_fbx_dump_blender.py'
READBACK = 'tools/blender/fbx_readback.py'
CODE = (DUMP, READBACK, 'tools/trainer/trainer.py', 'src/dt_ai/core/blender_runner.py',
        'src/twinqa/geometry/topology.py', 'src/twinqa/geometry/maf_surface.py',
        'adapters/max/agr_tools/udimtile_core.py')
MIN_ROWS, SIM, FLOOR = 20, 0.9, 'Перекрытие'
POSITIVE_MIN_M = 0.5
CAP_S, PAIR_S = 420, 140


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify(inputs):
    for path, expected in inputs.items():
        if digest(path) != expected:
            raise ValueError(f'hash mismatch: {path}')


def valid_box(lo, hi):
    return len(lo) == len(hi) == 3 and all(math.isfinite(a) and math.isfinite(b) and a <= b
                                           for a, b in zip(lo, hi))


def source_rows(doc):
    if doc.get('schema') != 'revit-fbx-dump/1':
        raise ValueError('unexpected source census schema')
    rows = []
    for i, obj in enumerate(doc['objects']):
        if not obj['verts']:
            continue
        x, y = zip(*obj['hull'])
        lo, hi = [min(x), min(y), obj['z'][0]], [max(x), max(y), obj['z'][1]]
        if not valid_box(lo, hi):
            raise ValueError(f'invalid source bounds at row {i}')
        rows.append((i, obj['name'], lo, hi))
    return rows


def contained(rows, box):
    return [r for r in rows if all(a <= b <= c <= d for a, b, c, d in zip(box['min'], r[2], r[3], box['max']))]


def signature(rows):
    return collections.Counter((round(r[2][0], 1), round(r[2][1], 1), round(r[3][0], 1), round(r[3][1], 1),
                                round(r[3][2] - r[2][2], 2)) for r in rows)


def jaccard(a, b):
    union = sum((a | b).values())
    return sum((a & b).values()) / union if union else 0.0


def select(rows):
    """S105, frozen: longest equal-pitch chain of identical storeys -> band Z; non-floor band rows -> XY."""
    by = collections.defaultdict(list)
    for r in rows:
        by[round(r[2][2], 2)].append(r)
    levels = sorted(z for z, rs in by.items() if len(rs) >= MIN_ROWS)
    sig = {z: signature(by[z]) for z in levels}
    have = set(levels)
    chains = []
    for i, z0 in enumerate(levels):
        for z1 in levels[i + 1:]:
            p = round(z1 - z0, 2)
            chain = [z0]
            while True:
                nxt = round(chain[-1] + p, 2)
                if nxt not in have or jaccard(sig[chain[-1]], sig[nxt]) < SIM:
                    break
                chain.append(nxt)
            if len(chain) >= 3:
                chains.append((p, chain))
    if not chains:
        return None
    best = max(len(c) for _, c in chains)
    top = [(p, c) for p, c in chains if len(c) == best]
    pitch = min(p for p, _ in top)
    top = [(p, c) for p, c in top if p == pitch]
    pitch, chain = max(top, key=lambda t: t[1][0])
    zlo, zhi = chain[0], round(chain[-1] + pitch, 2)
    band = [r for r in rows if zlo - 1e-6 <= r[2][2] < zhi - 1e-6 and not r[1].startswith(FLOOR)]
    if not band:
        return None
    lo = [min(r[2][0] for r in band), min(r[2][1] for r in band), zlo]
    hi = [max(r[3][0] for r in band), max(r[3][1] for r in band), zhi]
    return {'pitch_m': pitch, 'storeys': len(chain), 'levels': chain, 'n_longest_same_pitch': len(top),
            'band_rows': len(band), 'bounds_m': [lo, hi]}


def as_readback(sel):
    return {'readback_ok': True, 'meshes': [{'bounds_m': sel['bounds_m'], 'polygons': 0}]}


def box_of(doc):
    return ([min(m['bounds_m'][0][i] for m in doc['meshes']) for i in range(3)],
            [max(m['bounds_m'][1][i] for m in doc['meshes']) for i in range(3)])


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def positive_bound_ok(pos_native):
    """Frozen positive-witness bound: the injected +0.5 m row must score M105 >= 0.5 m."""
    dev = (pos_native or {}).get('max_corner_dev_m')
    return is_number(dev) and dev >= POSITIVE_MIN_M


def control_status(parity, pos_ok, neg_floor_ok, neg_out_ok, dev):
    """Any failed control or a missing/near-threshold deviation makes the tower inconclusive."""
    if not (parity and pos_ok and neg_floor_ok and neg_out_ok and is_number(dev)) \
            or abs(dev - TOL['bounds_m']) <= .0001:
        return 'inconclusive'
    return 'pass' if dev < TOL['bounds_m'] else 'fail'


def decide(results, stop):
    """Verdict: refuted/confirmed only on a complete series where every tower repeat has green controls."""
    if len(results) != 3 or stop != 'complete' or any(r.get('status') != 'complete' for r in results):
        return 'inconclusive'
    st = {t: [r[t]['status'] for r in results] for t in ('63A', '63B')}
    if any(s not in ('pass', 'fail') for v in st.values() for s in v):
        return 'inconclusive'
    if st['63B'] == ['fail'] * 3:
        return 'refuted'
    if st['63A'] == ['pass'] * 3 and st['63B'] == ['pass'] * 3:
        return 'confirmed'
    return 'inconclusive'


def tower(rows, box, built, key):
    inside = contained(rows, box)
    sel = select(inside)
    klo, khi = box_of(key)
    blo, bhi = box_of(built)
    record = {'contained_rows': len(inside), 'key_bounds_m': [klo, khi],
              'baseline_native': bounds_step(built, key),
              'baseline_signed_deltas_m': [b - k for b, k in zip(blo + bhi, klo + khi)]}
    if sel is None:
        return record | {'status': 'inconclusive', 'reason': 'no chain'}
    slo, shi = sel['bounds_m']
    native = bounds_step(as_readback(sel), key)
    record |= {'selection': sel, 'native': native, 'signed_deltas_m': [s - k for s, k in zip(slo + shi, klo + khi)]}
    # controls
    parity = select(list(reversed(inside))) == sel
    zlo = sel['levels'][0]
    wide = (-1, 'SYNTHETIC facade', [slo[0], slo[1], zlo], [shi[0] + .5, shi[1], zlo + 1])
    floor = (-2, FLOOR + ' SYNTHETIC', wide[2], wide[3])
    dx = box['max'][0] - box['min'][0] + 1
    outside = (-3, 'SYNTHETIC facade', [slo[0] + dx, slo[1], zlo], [shi[0] + .5 + dx, shi[1], zlo + 1])
    pos = select(contained([*rows, wide], box))
    neg_floor = select(contained([*rows, floor], box))
    neg_out = select(contained([*rows, outside], box))
    pos_ok = (bool(pos) and pos['levels'] == sel['levels'] and pos['band_rows'] == sel['band_rows'] + 1
              and abs(pos['bounds_m'][1][0] - shi[0] - .5) < 1e-9)
    same = lambda s: bool(s) and s['levels'] == sel['levels'] and s['bounds_m'] == sel['bounds_m'] \
        and s['band_rows'] == sel['band_rows']
    pos_native = bounds_step(as_readback(pos), key) if pos else None
    pos_ok = pos_ok and positive_bound_ok(pos_native)
    status = control_status(parity, pos_ok, same(neg_floor), neg_out == sel, native.get('max_corner_dev_m'))
    return record | {'status': status, 'order_parity': parity,
                     'injected': {'positive_xy_added': 1, 'positive_xy_pass': pos_ok,
                                  'positive_native': pos_native,
                                  'negative_floor_added': 1, 'negative_floor_unchanged': same(neg_floor),
                                  'negative_outside_added': 1, 'negative_outside_unchanged': neg_out == sel}}


def main():
    work = Path(sys.argv[1]).resolve()
    if not work.is_relative_to(ROOT):
        raise ValueError('output must be inside this worktree')
    work.mkdir()
    inputs = {Path(p) if p.startswith('C:/') else EV / p: h for p, h in
              re.findall(r'^\| `([^`]+)` \| `([0-9a-f]{64})` \|$', CONTRACT.read_text(encoding='utf-8'), re.M)}
    if len(inputs) != 8:
        raise ValueError('incomplete frozen manifest')
    source, boxes, key_a, key_b, reject_b, built_a, built_b, blender = inputs
    verify(inputs)
    signatures = {}
    for name in CODE:
        frozen = subprocess.check_output(['git', 'show', f'{BASE}:{name}'], cwd=ROOT)
        current = (ROOT / name).read_bytes().replace(b'\r\n', b'\n')
        if frozen != current:
            raise ValueError(f'code parity failed: {name}')
        signatures[name] = hashlib.sha256(frozen).hexdigest()
    box_map = {b['id']: b for b in json.loads(boxes.read_text(encoding='utf-8'))}
    results, series, stop = [], time.monotonic(), 'complete'
    for n in range(1, 4):
        start = time.monotonic()
        deadline = min(start + PAIR_S, series + CAP_S)
        folder = work / f'pair-{n}'
        folder.mkdir()

        def read(path, script, role):
            staged = folder / (role + '.fbx')
            shutil.copyfile(path, staged)
            verify({staged: inputs[path]})
            out = folder / (role + '.json')
            remaining = math.floor(deadline - time.monotonic())
            if remaining < 1:
                raise TimeoutError('pair budget exhausted before import')
            data = run_blender(ROOT / script, [staged, out], executable=blender, output_json=out,
                               log_path=folder / (role + '.log'), timeout=remaining, cwd=folder)
            verify({staged: inputs[path]})
            staged.unlink()
            return data

        try:
            ka = read(key_a, READBACK, 'accepted-a')
            kb = read(key_b, READBACK, 'accepted-b')
            rb = read(reject_b, READBACK, 'rejected-b')
            accepted, rejected = bounds_step(kb, kb), bounds_step(rb, kb)
            calib = {'accepted': accepted, 'rejected': rejected}
            if accepted['status'] != 'pass' or accepted['max_corner_dev_m'] != 0 or rejected['status'] != 'fail':
                results.append({'pair': n, 'status': 'calibration failed', 'calibration': calib,
                                'wall_s': time.monotonic() - start})
                stop = 'calibration failed'
                break
            ba = read(built_a, READBACK, 'baseline-a')
            bb = read(built_b, READBACK, 'baseline-b')
            dump = read(source, DUMP, 'source')
            if dump['sha256'] != inputs[source]:
                raise ValueError('source dump provenance mismatch')
            rows = source_rows(dump)
            pair = {'pair': n, 'status': 'complete', 'source_mesh_rows': len(dump['objects']),
                    'source_readable_rows': len(rows), 'calibration': calib,
                    '63A': tower(rows, box_map['63A'], ba, ka), '63B': tower(rows, box_map['63B'], bb, kb)}
            pair['wall_s'] = time.monotonic() - start
            results.append(pair)
            print(json.dumps({'pair': n, 'wall_s': pair['wall_s'],
                              **{t: [pair[t]['status'], pair[t].get('native')] for t in ('63A', '63B')}},
                             ensure_ascii=True), flush=True)
            if (n == 1 and pair['wall_s'] * 3 > CAP_S) or time.monotonic() > series + CAP_S:
                stop = 'budget stop'
                break
        except (ValueError, OSError, RuntimeError) as exc:
            stop = 'incomplete pair'
            results.append({'pair': n, 'status': stop, 'wall_s': time.monotonic() - start, 'error': str(exc)})
            break
    verify(inputs)
    verdict, summary = 'inconclusive', {}
    if len(results) == 3 and stop == 'complete':
        for t in ('63A', '63B'):
            devs = [r[t]['native']['max_corner_dev_m'] for r in results if 'native' in r[t]]
            if len(devs) == 3:
                summary[t] = {'m105_median_m': statistics.median(devs), 'm105_range_m': [min(devs), max(devs)],
                              'baseline_m': results[0][t]['baseline_native']['max_corner_dev_m']}
    verdict = decide(results, stop)
    receipt = {'results': results, 'summary': summary, 'hypothesis': verdict, 'status': stop,
               'wall_s': time.monotonic() - series, 'inputs': {p.as_posix(): h for p, h in inputs.items()},
               'code_sha256': signatures, 'replay_sha256_git_lf': hashlib.sha256(
                   Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()}
    (work / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                       newline='\n')
    print(json.dumps({'hypothesis': verdict, 'status': stop, 'summary': summary}, ensure_ascii=True))


if __name__ == '__main__':
    main()
