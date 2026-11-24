"""OBSERVE-only hook on unmodified standing #54 replay (fresh Blender imports)."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

R54 = 'cc470a6d6e01a5a861f4c00b1145caec727a7d00'
R55 = 'bf779a32d30f4c01e0653e0682fc51a949deaf63'
TARGETS = {'G22_C_none': '4259581', 'v007': '194b464', 'v006': '194b464'}


def git(*args):
    return subprocess.check_output(['git', *args])


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def fetch(out, rev, round_no, filename):
    path = out / f'r{round_no}' / filename
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(git('show', f'{rev}:docs/research/autoresearch-body-form-r{round_no}/{filename}'))
    return path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def measure(S, key, ex, overlay, clean, describe, catalogue, fixture, rep):
    opening, = [o for o in key['openings'] if o['id'].endswith(TARGETS[fixture])]
    pid = 'opening:' + opening['id']
    datum = clean[pid]
    a, u, _ = S.frame({p['ring_index']: p['xy'] for p in key['contour_vertices_in_box']},
                      *opening['contour_segment'])
    lo, hi = opening['edge_s_m']
    mid = (lo + hi) / 2
    gaps = {}
    for z in S.OPENING_Z:
        section = [(p, q) for p, q in ex['sections'][z]
                   if S.inbox(p, key['box_xy_m'], .5) or S.inbox(q, key['box_xy_m'], .5)]
        found = [g for g in S.gaps(S.wall_intervals(section, a, u), lo - .6, hi + .6)
                 if lo - .6 < g[0] < mid < g[1] < hi + .6]
        if len(found) == 1:
            gaps[z] = found[0]

    row = dict(fixture=fixture, rep=rep, target=pid, key_edges=(lo, hi), gaps=gaps, clean=datum)
    if datum['depth'] is None or len(gaps) != len(S.OPENING_Z):
        return row | {'probes': {}, 'state': 'not_exercised'}
    sign = math.copysign(1, S.local(overlay['openings'][pid]['rim']['c'], a, u)[1] - datum['line'])

    def xy(t, d):
        return [a[0] + t*u[0] + d*u[1], a[1] + t*u[1] - d*u[0]]

    probes = {}
    for name, (offset, sides, pullback, kind) in catalogue.PROBES.items():
        d = datum['line'] + offset*sign
        in_band = abs(d) < S.TOL['wall_line_search_m']
        trial = copy.deepcopy(ex)
        added, distances = {}, {}
        for z, (left, right) in gaps.items():
            spans = ([(left-.30, right+.30)] if kind == 'rail' else
                     [(left-pullback-catalogue.LEN, left-pullback)] +
                     ([(right+pullback, right+pullback+catalogue.LEN)] if sides == 'both' else []))
            distances[z] = ([0., 0.] if kind == 'rail' and spans[0][0] < left < right < spans[0][1]
                            else [abs(spans[0][1]-left)] +
                            ([abs(spans[-1][0]-right)] if sides == 'both' else []))
            trial['sections'][z].extend([[xy(s, d), xy(t, d)] for s, t in spans])
            added[z] = len(spans)
        touches = all(all(x <= S.TOL['opening_edge_m'] for x in vals) for vals in distances.values())
        eligible = (not in_band and touches if name == 'rear_out' else
                    in_band and not touches if name == 'near_miss' else in_band and touches)
        results = describe(S, key, trial, overlay, None)
        v = results[pid]
        delta = None if v['depth'] is None else v['depth'] - datum['depth']
        count_delta = {z: [x-y for x, y in zip(v['counts'][z], datum['counts'][z])] for z in gaps}
        expected = {z: ([-x for x in datum['counts'][z]] if kind == 'rail' else
                        [0, 0] if name in ('rear_out', 'near_miss') else
                        [1, 0] if sides == 'left' else [1, 1]) for z in gaps}
        positive = name not in ('rear_out', 'near_miss')
        response_observed = any(any(vals) for vals in count_delta.values())
        state = ('exercised' if positive else 'negative_control') if eligible and (
            not positive or response_observed) else 'not_exercised'
        off_target = [k for k, c in clean.items() if k != pid and (
            results[k]['status'] != c['status'] or (c['depth'] is not None and
            (results[k]['depth'] is None or abs(results[k]['depth']-c['depth']) > .001)))]
        probes[name] = dict(state=state, eligible=eligible, in_band=in_band, edge_distances_m=distances,
                            added=added, count_delta=count_delta, expected_counts=expected, depth=v['depth'],
                            delta=delta, status=v['status'], off_target=off_target,
                            false_depth=eligible and delta is not None and abs(delta) > S.TOL['reveal_depth_m'],
                            as_expected=count_delta == expected and catalogue.expected(name, v, delta))
    return row | {'probes': probes, 'state': 'clean_measured'}


def main(out):
    out = out.resolve()
    out.mkdir(parents=True)
    sys.dont_write_bytecode = True
    replay = load('standing54', fetch(out, R54, 54, 'replay.py'))
    fetch(out, R54, 54, 'pins.json')
    catalogue = load('standing55', fetch(out, R55, 55, 'replay.py'))
    describe, perturb = replay.describe, replay.perturb
    rows = {k: [] for k in TARGETS}

    def observe(S, key, ex, overlay, clean, fixture):
        series = rows[fixture]
        series.append(measure(S, key, ex, overlay, clean, describe, catalogue, fixture, len(series)+1))

    def described(S, key, ex, overlay, reference):
        res = describe(S, key, ex, overlay, reference)
        fixture = Path(ex['fbx']).stem
        if reference is not None and fixture in ('v007', 'v006'):
            observe(S, key, ex, overlay, res, fixture)
        return res

    def perturbed(S, key, ex, overlay, target, mode, clean):
        if mode == 'face' and Path(ex['fbx']).stem == 'G22_C_none':
            observe(S, key, ex, overlay, clean, 'G22_C_none')
        return perturb(S, key, ex, overlay, target, mode, clean)

    replay.describe, replay.perturb = described, perturbed
    rc = None
    try:
        replay.main(out / 'fresh')
    except Exception as exc:
        rc = repr(exc)
    raw = out / 'fresh' / 'receipt.json'
    base = json.loads(raw.read_text(encoding='utf-8'))
    trials = [(row['rep'], p) for series in rows.values() for row in series for p in row['probes'].values()]
    f_counts = [sum(p['false_depth'] for rep, p in trials if rep == r) for r in range(1, 4)]
    spread = {}
    for k, series in rows.items():
        for name in catalogue.PROBES:
            probes = [row['probes'][name] for row in series if name in row['probes']]
            values = [p['depth'] for p in probes if p['depth'] is not None]
            spread[f'{k}:{name}'] = dict(statuses=sorted({p['status'] for p in probes}),
                                         depth_m=max(values)-min(values) if values else None)
    stable = all(len(v['statuses']) == 1 and (v['depth_m'] or 0) <= .001 for v in spread.values())
    calibrated = (rc is None and base['status'] == 'complete' and base['hypothesis'] == 'confirmed'
                  and base.get('all_guards') and base.get('postflight'))
    verdict = 'inconclusive'
    if calibrated and len(trials) == 63:
        if any(p['false_depth'] or (p['state'] != 'not_exercised' and (
            not p['as_expected'] or p['off_target'])) for _, p in trials) or not stable:
            verdict = 'refuted'
        elif all(p['state'] != 'not_exercised' for _, p in trials):
            verdict = 'confirmed'
    receipt = dict(head=git('rev-parse', 'HEAD').decode().strip(), runner_sha256=sha(Path(__file__)),
                   run_status=base['status'], wall_s=base['wall_s'], timed_pair_s=base.get('timed_pair_s'),
                   raw_receipt=str(raw), raw_sha256=sha(raw), error=rc, calibration=base.get('calibration'),
                   calibrated=calibrated, hypothesis=verdict, rows=rows, spread=spread,
                   trials=len(trials), not_exercised=sum(p['state'] == 'not_exercised' for _, p in trials),
                   F56_counts=f_counts if calibrated and len(trials) == 63 else None,
                   F56=statistics.median(f_counts) if calibrated and len(trials) == 63 else None)
    (out / 'receipt56.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print({k: receipt[k] for k in ('run_status', 'wall_s', 'timed_pair_s', 'calibrated', 'hypothesis',
                                   'trials', 'not_exercised', 'F56_counts', 'error')})


if __name__ == '__main__':
    main(Path(sys.argv[1]))
