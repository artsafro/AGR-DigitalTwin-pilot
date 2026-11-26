"""R104 evidence replay; does not build or modify a model."""
from __future__ import annotations

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
from dt_ai.core.blender_runner import run_blender  # noqa: E402
from tools.trainer.trainer import TOL, bounds_step  # noqa: E402  # type: ignore[import-not-found]

CONTRACT = ROOT / 'docs/research/autoresearch-trainer-revit-bounds-r104.md'
BASE = '1140d9b417462ac4190e791b8c66b6970415d4ad'
EV = Path('G:/Мой диск/AGR-evidence')
DUMP = 'tools/methods/body/revit_fbx_dump_blender.py'
READBACK = 'tools/blender/fbx_readback.py'
CODE = (DUMP, READBACK, 'tools/trainer/trainer.py', 'src/dt_ai/core/blender_runner.py',
        'src/twinqa/geometry/topology.py', 'src/twinqa/geometry/maf_surface.py',
        'adapters/max/agr_tools/udimtile_core.py')


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify(inputs):
    for path, expected in inputs.items():
        if digest(path) != expected:
            raise ValueError(f'hash mismatch: {path}')


def bounds(doc):
    if not doc.get('readback_ok') or not doc.get('meshes'):
        raise ValueError('native readback did not return meshes')
    boxes = [m['bounds_m'] for m in doc['meshes']]
    if not all(valid_box(lo, hi) for lo, hi in boxes):
        raise ValueError('invalid native bounds')
    return [min(b[0][i] for b in boxes) for i in range(3)], [max(b[1][i] for b in boxes) for i in range(3)]


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


def nearest(rows, box, top):
    chosen = [r for r in rows if all(a <= b <= c <= d for a, b, c, d in
                                    zip(box['min'], r[2], r[3], box['max']))]
    item = min(chosen, default=None, key=lambda r: (abs(r[3][2] - top), r[0]))
    return {'selected': len(chosen), 'nearest': item, 'delta_m': abs(item[3][2] - top) if item else None}


def comparison(rows, box, built, key):
    key_lo, key_hi = bounds(key)
    built_lo, built_hi = bounds(built)
    center = [(a + b) / 2 for a, b in zip(key_lo, key_hi)]
    faces = [b - k for b, k in zip(built_lo + built_hi, key_lo + key_hi)]
    record = {'key_bounds_m': [key_lo, key_hi], 'built_bounds_m': [built_lo, built_hi],
              'native_bounds': bounds_step(built, key), 'signed_deltas_m': faces, 'baseline_top_m': abs(faces[-1])}
    if not all(box['min'][i] <= center[i] <= box['max'][i] for i in (0, 1)):
        return record | {'status': 'inconclusive', 'reason': 'key XY centroid outside tower box'}
    top = key_hi[2]
    clean = nearest(rows, box, top)
    parity = clean == nearest(reversed(rows), box, top)
    mid = [(a + b) / 2 for a, b in zip(box['min'], box['max'])]
    inside = (-1, 'SYNTHETIC', mid[:2] + [top - .01], mid[:2] + [top])
    x = box['max'][0] + 1
    outside = (-1, 'SYNTHETIC', [x] + inside[2][1:], [x] + inside[3][1:])
    added = nearest([*rows, inside], box, top)
    excluded = nearest([*rows, outside], box, top)
    positive = added['selected'] == clean['selected'] + 1 and added['delta_m'] == 0
    negative = excluded == clean
    delta = clean['delta_m']
    status = 'inconclusive'
    if positive and negative and parity and delta is not None and abs(delta - TOL['bounds_m']) > .0001:
        status = 'reachable' if delta < TOL['bounds_m'] else 'unreachable'
    return record | {'status': status, 'clean': clean, 'order_parity': parity,
                     'paired_gain_m': None if delta is None else abs(faces[-1]) - delta,
                     'injected': {'inside_added': 1, 'inside_selected_change': added['selected'] - clean['selected'],
                                  'inside_delta_m': added['delta_m'], 'inside_pass': positive,
                                  'outside_added': 1, 'outside_selected_change': excluded['selected'] - clean['selected'],
                                  'outside_delta_m': excluded['delta_m'], 'outside_pass': negative}}


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
    results = []
    series = time.monotonic()
    stop = 'complete'
    for n in range(1, 4):
        start = time.monotonic()
        deadline = min(start + 120, series + 360)
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
            data = run_blender(ROOT / script, [staged, out], executable=blender,
                               output_json=out, log_path=folder / (role + '.log'),
                               timeout=remaining, cwd=folder)
            verify({staged: inputs[path]})
            return data

        try:
            ka = read(key_a, READBACK, 'accepted-a')
            kb = read(key_b, READBACK, 'accepted-b')
            rb = read(reject_b, READBACK, 'rejected-b')
            accepted, rejected = bounds_step(kb, kb), bounds_step(rb, kb)
            if accepted['status'] != 'pass' or accepted['max_corner_dev_m'] != 0 or rejected['status'] != 'fail':
                results.append({'pair': n, 'status': 'calibration failed', 'wall_s': time.monotonic() - start,
                                'calibration': {'accepted': accepted, 'rejected': rejected}})
                stop = 'calibration failed'
                break
            ba = read(built_a, READBACK, 'baseline-a')
            bb = read(built_b, READBACK, 'baseline-b')
            dump = read(source, DUMP, 'source')
            if dump['sha256'] != inputs[source]:
                raise ValueError('source dump provenance mismatch')
            rows = source_rows(dump)
            pair = {'pair': n, 'status': 'complete', 'source_mesh_rows': len(dump['objects']),
                    'source_readable_rows': len(rows), 'calibration': {'accepted': accepted, 'rejected': rejected},
                    '63A': comparison(rows, box_map['63A'], ba, ka),
                    '63B': comparison(rows, box_map['63B'], bb, kb)}
            pair['wall_s'] = time.monotonic() - start
            results.append(pair)
            print(json.dumps(pair, ensure_ascii=True), flush=True)
            if (n == 1 and pair['wall_s'] * 3 > 360) or time.monotonic() > series + 360:
                stop = 'budget stop'
                break
        except (ValueError, OSError, RuntimeError) as exc:
            stop = 'incomplete pair'
            results.append({'pair': n, 'status': stop, 'wall_s': time.monotonic() - start, 'error': str(exc)})
            break
    verify(inputs)
    verdict, summary = 'inconclusive', {}
    if len(results) == 3 and stop == 'complete':
        for tower in ('63A', '63B'):
            gains = [r[tower]['paired_gain_m'] for r in results if 'paired_gain_m' in r[tower]]
            if len(gains) == 3 and all(g is not None for g in gains):
                summary[tower] = {'gain_median_m': statistics.median(gains), 'gain_range_m': [min(gains), max(gains)]}
        if any(all(r[t]['status'] == 'unreachable' for r in results) for t in ('63A', '63B')):
            verdict = 'refuted'
        elif all(r[t]['status'] == 'reachable' for t in ('63A', '63B') for r in results):
            verdict = 'confirmed'
    receipt = {'results': results, 'summary': summary, 'hypothesis': verdict, 'status': stop,
               'wall_s': time.monotonic() - series, 'inputs': {p.as_posix(): h for p, h in inputs.items()},
               'code_sha256': signatures, 'replay_sha256_git_lf': hashlib.sha256(
                   Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()}
    (work / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'hypothesis': verdict, 'status': stop, 'summary': summary}, ensure_ascii=True))


if __name__ == '__main__':
    main()
