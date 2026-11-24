"""OBSERVE only. See ../autoresearch-body-form-r55.md for the frozen contract.

Runs standing #54's replay unchanged (fetched from Git at REV54) and attaches independent
decoy-segment probes to its `face` perturbation on the two accepted witnesses.
"""
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import subprocess as sp
import sys

REV54 = 'cc470a6d6e01a5a861f4c00b1145caec727a7d00'
SRC54 = 'docs/research/autoresearch-body-form-r54'
SHA54 = 'f1d1d5c5256a3d2d78ba6a74f5e7876f856058d8dbabc7a44d57112f0a0401f3'
LEN, BAND = .60, .12
# name: (offset from clean flank line toward the rim, sides, pull-back from gap edge, kind)
PROBES = {
    'rear_in': (+.05, 'both', 0., 'flank'),
    'front_in': (-.05, 'both', 0., 'flank'),
    'one_side': (+.05, 'left', 0., 'flank'),
    'rear_out': (+.20, 'both', 0., 'flank'),
    'near_miss': (+.05, 'both', .06, 'flank'),
    'tiny': (+.01, 'both', 0., 'flank'),
    'rail': (-.08, 'span', 0., 'rail'),
}


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def expected(name, v, diff):
    if name in ('rear_in', 'front_in', 'one_side'):
        return v['status'] == 'noncoplanar' and v['depth'] is None
    if name in ('rear_out', 'near_miss'):
        return v['status'] == 'measured' and abs(diff) <= .001
    if name == 'tiny':
        return v['status'] == 'measured' and .001 < abs(diff) <= .010
    return v['status'] == 'flank_missing' and v['depth'] is None


def probes(r54, S, key, ex, overlay, target, clean):
    o, = [o for o in key['openings'] if o['id'].endswith(target)]
    pid = 'opening:' + o['id']
    ring = {v['ring_index']: v['xy'] for v in key['contour_vertices_in_box']}
    a, u, _ = S.frame(ring, *o['contour_segment'])
    lo, hi = o['edge_s_m']
    line = clean[pid]['line']
    s = math.copysign(1., S.local(overlay['openings'][pid]['rim']['c'], a, u)[1] - line)

    def pt(t, d):
        return [a[0] + t*u[0] + d*u[1], a[1] + t*u[1] - d*u[0]]

    out = {}
    for name, (off, sides, back, kind) in PROBES.items():
        d = line + off*s
        if kind == 'rail':
            segs = [[pt(lo - .30, d), pt(hi + .30, d)]]
        else:
            segs = [[pt(lo - back - LEN, d), pt(lo - back, d)]]
            if sides == 'both':
                segs.append([pt(hi + back, d), pt(hi + back + LEN, d)])
        trial = copy.deepcopy(ex)
        for z in S.OPENING_Z:
            trial['sections'][z].extend(segs)
        res = r54.describe(S, key, trial, overlay, None)
        v = res[pid]
        diff = None if v['depth'] is None else v['depth'] - clean[pid]['depth']
        inband = abs(d) < BAND
        exercised = len(segs) > 0 and (not inband if name == 'rear_out' else inband if kind == 'flank' and not back else True)
        off_target = [p for p in res if p != pid and (res[p]['status'] != clean[p]['status'] or (
            res[p]['depth'] is not None and abs(res[p]['depth'] - clean[p]['depth']) > .001))]
        out[name] = dict(decoy_d=d, decoy_in_band=inband, added_per_slice=len(segs), exercised=exercised,
                         status=v['status'], depth=v['depth'], clean_depth=clean[pid]['depth'], delta=diff,
                         flank_counts=v['counts'], flank_spread=v['flank_spread'], off_target=off_target,
                         false_depth=v['status'] == 'measured' and abs(diff) > S.TOL['reveal_depth_m'],
                         as_expected=expected(name, v, diff))
    return dict(target=pid, clean_line=line, rim_sign=s, probes=out)


def main(out):
    out = out.resolve()
    src = out / 'r54src'
    src.mkdir(parents=True)
    for name in ('replay.py', 'pins.json'):
        (src / name).write_bytes(sp.run(['git', 'show', f'{REV54}:{SRC54}/{name}'], check=True,
                                        capture_output=True).stdout)
    assert sha(src / 'replay.py') == SHA54, 'r54 replay drift'
    sys.path.insert(0, str(src))
    sys.dont_write_bytecode = True
    r54 = importlib.import_module('replay')
    orig = r54.perturb

    def hooked(S, key, ex, overlay, target, mode, clean):
        res = orig(S, key, ex, overlay, target, mode, clean)
        if mode == 'face':
            res['decoys'] = probes(r54, S, key, ex, overlay, target, clean)
        return res

    r54.perturb = hooked
    receipt = {'rev54': REV54, 'r54_replay_sha256': SHA54, 'script_sha256': sha(Path(__file__)),
               'hypothesis': 'inconclusive'}
    try:
        r54.main(out / 'run')
    except Exception as exc:  # r54 already wrote its own receipt; keep ours
        receipt['error'] = repr(exc)
    raw = out / 'run' / 'receipt.json'
    base = json.loads(raw.read_text(encoding='utf-8'))
    receipt |= {'raw_receipt': str(raw), 'raw_sha256': sha(raw), 'r54_status': base['status'],
                'r54_hypothesis': base['hypothesis'], 'r54_all_guards': base.get('all_guards'),
                'r54_primary_m': base.get('primary_m'), 'wall_s': base.get('wall_s'),
                'postflight': base.get('postflight'), 'calibration': base.get('calibration')}
    trials = []
    for k in ('G22_C_none', 'v007'):
        for rep, row in enumerate(base['runs'].get(k, []), 1):
            for name, p in row.get('injected', {}).get('face', {}).get('decoys', {}).get('probes', {}).items():
                trials.append(dict(fixture=k, rep=rep, probe=name, **p))
    receipt['trials'] = trials
    n = len(trials)
    receipt['F55'] = sum(t['false_depth'] for t in trials)
    receipt['n_trials'] = n
    receipt['exercised'] = sum(t['exercised'] for t in trials)
    receipt['as_expected'] = sum(t['as_expected'] for t in trials)
    receipt['off_target'] = sum(bool(t['off_target']) for t in trials)
    receipt['fail_closed_losses'] = {p: sum(t['probe'] == p and t['depth'] is None for t in trials) for p in PROBES}
    spread = {}
    for k in ('G22_C_none', 'v007'):
        for p in PROBES:
            xs = [t for t in trials if t['fixture'] == k and t['probe'] == p]
            ds = [t['depth'] for t in xs if t['depth'] is not None]
            spread[f'{k}:{p}'] = dict(statuses=sorted({t['status'] for t in xs}),
                                      depth_spread=max(ds) - min(ds) if ds else None)
    receipt['spread'] = spread
    stable = all(len(v['statuses']) == 1 and (v['depth_spread'] or 0) <= .001 for v in spread.values())
    calibrated = base['status'] == 'complete' and base['hypothesis'] == 'confirmed' and base.get('all_guards')
    if calibrated and n == 42:
        if receipt['F55'] or receipt['as_expected'] < receipt['exercised']:
            receipt['hypothesis'] = 'refuted'
        elif receipt['exercised'] == n and receipt['as_expected'] == n and not receipt['off_target'] and stable:
            receipt['hypothesis'] = 'confirmed'
    (out / 'receipt55.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print({k: v for k, v in receipt.items() if k not in ('trials', 'calibration', 'spread')})
    print(json.dumps(spread))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
