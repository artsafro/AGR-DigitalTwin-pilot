"""Replay the pinned #19 sink on 63C and attribute the lost R6 signal (OBSERVE)."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AR19 = '987f418a237e5931d695c278bcca177c789de3da'
AR21 = 'd802aa8c0e72b7c73e560a049c0f3cd0f8c545b6'
H19 = 'docs/research/autoresearch-body-mesh-r3-localize-harness/localize.py'
H21 = 'docs/research/autoresearch-body-mesh-convex-quad-harness/replay.py'
PAIR = ('63C-v002', '63C-v001')


def pinned(rev, path, sha):
    raw = subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f'pinned blob mismatch: {rev}:{path}')
    return raw.decode('utf-8')


def replace_once(code, old, new):
    if code.count(old) != 1:
        raise ValueError(f'expected one splice anchor: {old!r}')
    return code.replace(old, new, 1)


def bounds(points):
    return [(min(axis), max(axis)) for axis in zip(*points, strict=True)]


def diagnose(entries, angles, classify, flat, exempt):
    total, removed, retained, patches, faces = [], [], [], [], []
    for e in entries:
        for i in e['bad']:
            area = e['areas'][i]
            total.append(area)
            corner = angles(e['pts'][i])
            if exempt(e['normals'][i][2], flat, corner):
                removed.append(area)
            else:
                retained.append({'element': e['name'], 'face': i, 'area_m2': area, 'corners_deg': corner})
        if e['local'] > 0:
            e['angles'] = lambda pts: [round(x, 3) for x in angles(pts)]
            summary = classify(e, 0.5 * e['local'])
            for p in summary['top_patches']:
                i = p['seed']
                p.update(element=e['name'], vertex_count=len(e['pts'][i]), bounds_m=bounds(e['pts'][i]))
                patches.append(p)
        for i, pts in enumerate(e['pts']):
            if abs(e['normals'][i][2]) >= flat:
                faces.append((e['name'], i, bounds(pts), len(pts)))
    area = math.fsum(total)
    excluded = math.fsum(removed)
    return {'seed_count': len(total), 'seed_area_m2': area, 'excluded_count': len(removed),
            'excluded_area_m2': excluded, 'excluded_pct': 100 * excluded / area if area else None,
            'survivors': retained, 'top_patches': sorted(patches, key=lambda p: -p['local'])[:10]}, faces


def nearby(plane, faces):
    return [{'element': name, 'face': i, 'bounds_m': box, 'vertex_count': degree}
            for name, i, box, degree in faces if plane[2][1] - plane[2][0] <= 0.001
            and all(abs(z - plane[2][0]) <= 0.001 for z in box[2])
            and all(min(hi, b) > max(lo, a) for (lo, hi), (a, b) in zip(plane[:2], box[:2], strict=True))]


def main(cache, out):
    h19 = pinned(AR19, H19, 'e84c7bef192e1aa3f7a9a3295869d26a4d8e961bc6d976514e6f730340f160d7')
    r6: dict[str, Any] = {'__name__': 'ar21', '__file__': __file__}
    exec(compile(pinned(AR21, H21, 'eb3ef3f6d2f104a8e9f32266816f57196ecf91d63134df3ebe215e12f0eeb12d'), H21, 'exec'), r6)
    r6['witness']()
    h19 = replace_once(h19, "inputs, pairs = suite['INPUTS'], suite['PAIRS']", "inputs = {k: suite['INPUTS'][k] for k in _PAIR}")
    h19 = replace_once(h19, "    for key in inputs:\n        objects", "    for key in inputs:\n        snapshots = []\n        objects")
    h19 = replace_once(h19, "        sink.clear()\n        c = var3s['score'](objects, **args)",
                       "        for _ in range(3):\n            sink.clear()\n            c = var3s['score'](objects, **args)\n"
                       "            if c != b[0]:\n                raise ValueError(f'non-neutral sink: {key}')\n"
                       "            snapshots.append(_diagnose(sink, var3s_angles, classify, COS1, _exempt))\n"
                       "        _snapshots[key] = snapshots")
    # Reuse Step A, stop before the 63B-specific decision and candidate loop.
    boundary = '    v007 = loc['
    if h19.count(boundary) != 1:
        raise ValueError('missing unique #19 Step A boundary')
    h19 = h19.split(boundary, 1)[0] + '    return ledger, local_rows, r3s\n'
    snapshots = {}
    scope = {'__name__': 'ar22', '__file__': __file__, '_PAIR': PAIR,
             '_diagnose': diagnose, '_exempt': r6['exempt'], '_snapshots': snapshots}
    exec(compile(h19, H19, 'exec'), scope)
    ledger, scores, sink = scope['main'](cache, out)
    for key, runs in snapshots.items():
        if runs != [runs[0]] * 3:
            raise ValueError(f'nonrepeatable localization: {key}')
    acc, rej = (snapshots[key][0][0] for key in PAIR)
    values = [run[0]['excluded_pct'] for run in snapshots[PAIR[1]]]
    median = statistics.median(values) if None not in values else None
    accepted_faces = snapshots[PAIR[0]][0][1]
    near = nearby(rej['top_patches'][0]['bounds_m'], accepted_faces) if rej['top_patches'] else []
    receipt = {'ar19_revision': AR19, 'ar21_revision': AR21, 'inputs': ledger, 'scores': scores,
               'replay_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'r3_sink_sha256': hashlib.sha256(sink.encode()).hexdigest(),
               'spliced_harness_sha256': hashlib.sha256(h19.encode()).hexdigest(),
               'accepted': acc, 'rejected': rej, 'excluded_pct_runs': values, 'median_pct': median,
               'spread_pp': max(values) - min(values) if median is not None else None,
               'accepted_near_top_rejected_seed': near, 'keep': False,
               'clean': ['hashes', 'R0/R3 #17 parity', 'neutral sink and repeatability', 'clean/reset', 'R6 predicate witness'],
               'injected': ['skew #19 witness'], 'not_measured': ['native readback', 'design attribution', 'full calibration',
               'independent holdouts', 'body builders', 'delivery QA']}
    with out.open('x', encoding='utf-8', newline='\n') as fp:
        json.dump(receipt, fp, indent=2, allow_nan=False)
        fp.write('\n')
    print(f'R6 excluded seed area: {median}%; accepted nearby faces: {len(near)}; keep: false')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    main(args.cache, args.out)
