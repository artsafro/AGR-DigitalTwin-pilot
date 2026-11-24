"""Replay #44 with one scene-annotation candidate; no writes to the evaluator packet."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import statistics
import subprocess
import sys
import time

PIN = '3a843a21a5abfdd8835fba8e862b91f282e99ffa:docs/research/autoresearch-body-form-r44/'
CONTRACT = '9effae1be05aa41ea289ff82054966d643937afb'
HEIGHTS = ('17.8', '18.2')


def blob(name):
    return subprocess.check_output(['git', 'show', PIN + name])


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def comparable(row):
    return {k: v for k, v in row.items() if k not in ('extract_sha256', 'native_extract_sha256', 'raw_score_sha256')}


def evaluate(det, key, ref, extract, report):
    good_key = report['provenance']['key_hash_ok'] and report['provenance']['candidate_fbx_sha256']
    missing = [o['id'] for o in key['openings'] if good_key and
               report['items'][f"opening:{o['id']}:present"]['status'] == 'fail']
    steps = [(opening, z) for opening in missing for z in HEIGHTS]
    tol = det['TOL']['contour_max_dev_m']
    passes, discards = {}, {}

    def trace(use_datum):
        coverage = {}
        counts = []

        def intervals(segments, a, u):
            select = [s for s in segments if all(abs(det['local'](p, a, u)[1]) <= tol for p in s)] if use_datum else segments
            counts.append(len(segments) - len(select))
            iv = det['wall_intervals'](select, a, u)
            opening, z = steps[len(counts) - 1]
            spec = next(o for o in key['openings'] if o['id'] == opening)
            lo, hi = spec['edge_s_m']
            coverage.setdefault(opening, {})[z] = any(l <= lo and hi <= r for l, r in iv)
            return iv

        res = ref['observe'](dict(det, wall_intervals=intervals), key, extract, report)
        require(len(counts) == len(steps), 'annotation call order/shape drift')
        ids = {name for op, zs in coverage.items() if all(zs.values())
               for part in ('edges', 'reveal_depth', 'sill_head')
               if report['items'][name := f'opening:{op}:{part}'] ==
               {'status': 'not_measured', 'basis': 'opening missing'}}
        require(len(ids) == res['candidate_changed_rows'], 'annotation ID parity failed')
        return res, ids, sum(counts)

    old, passes['old'], _ = trace(False)
    new, passes['C1'], discards['C1'] = trace(True)
    return old, new, sorted(passes['old'] - passes['C1']), sorted(passes['C1'] - passes['old']), discards['C1']


def main(out):
    start = time.monotonic()
    out = out.resolve()
    out.mkdir(parents=True)
    result = {'status': 'running', 'hypothesis': 'inconclusive', 'contract': CONTRACT,
              'candidate_sha256': digest(Path(__file__)), 'rows': {}, 'controls': {}}

    def save():
        result['wall_s'] = round(time.monotonic() - start, 3)
        (out / 'receipt.json').write_bytes((json.dumps(result, indent=2) + '\n').encode())

    try:
        harness = out / 'r44.py'
        harness.write_bytes(blob('probe.py'))
        result['r44_sha256'] = digest(harness)
        prior = runpy.run_path(str(harness))
        states = prior['STATES']
        states['both_030'] = (.030, HEIGHTS)
        base = out / 'prior'
        with (out / 'r44.log').open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log):
            prior['main'](base)
        baseline = read(base / 'receipt.json')
        result['prior_wall_s'] = baseline['wall_s']
        result['native_pair_s'] = baseline.get('baseline_first_pair_s')
        result['prior_pair_s'] = baseline.get('first_probe_pair_s')
        if baseline['status'] == 'budget_stop':
            result['status'] = 'budget_stop'
            return
        archived = json.loads(blob('receipt.json'))
        result['baseline_parity'] = baseline['clean_rows'] == archived['clean_rows'] and all(
            comparable(baseline['rows'][name]) == comparable(row) for name, row in archived['rows'].items())
        require(baseline['status'] == 'complete' and result['baseline_parity'], '#44 historical parity failed')
        ref = runpy.run_path(str(base / 'r42.py'))
        native = base / 'baseline'
        det = runpy.run_path(str(ref['PROTOCOL'] / 'detector/score_heldout.py'))
        key = read(ref['PROTOCOL'] / 'key/heldout-key-v001.json')
        opening, = (o for o in key['openings'] if o['id'] == prior['OPENING'])
        ring = {v['ring_index']: v['xy'] for v in key['contour_vertices_in_box']}
        a, u, _ = det['frame'](ring, *opening['contour_segment'])
        scans = read(native / 'receipt.json')['rows']

        def one(extract_path, raw_path, trace):
            extract, report = read(extract_path), read(raw_path)
            raw_digest = digest(raw_path)
            old, new, removed, added, rejected = evaluate(det, key, ref, extract, report)
            require(all(old[field] == trace[field] for field in old), 'unfiltered annotation parity failed')
            require(digest(raw_path) == raw_digest, 'raw report changed')
            return extract, {
                'extract_sha256': digest(extract_path), 'raw_report_sha256': raw_digest,
                'variant_fbx_sha256': old['candidate_fbx_sha256'], 'raw_gap_counts': old['raw_gap_counts'],
                'outline_section_maxima_m': old['section_maxima_m_rounded'], 'raw_score': old['raw_form_score_unchanged'],
                'measured_depths_m': old['measured_depths_m_rounded'],
                'old_annotation': old['candidate_changed_rows'], 'C1_annotation': new['candidate_changed_rows'],
                'C1_unknown_pct': new['candidate_unknown_pct'], 'removed_ids': removed, 'added_ids': added,
                'segment_removals_in_annotation_calls': rejected,
                'annotation_exercise': new['annotation_exercise'],
            }

        original_bound = True
        for label, trace in scans.items():
            if label.startswith(('J1_', 'J2_', 'J3_')):
                spec = ref['PROTOCOL'] / 'controls' / f'{label}.extract.json'
            elif label == 'J4_stale_key':
                spec = native / 'A-1.extract.json'
            elif label == 'J4_clean_preflight':
                spec = native / 'C_none-1.extract.json'
            else:
                spec = native / f'{label}.extract.json'
            _, row = one(spec, native / f'{label}.score.json', trace)
            result['controls'][label] = row
            original_bound &= not row['removed_ids'] and not row['added_ids']

        exercise, raw_witness, r_bound = set(), set(), True
        a_counts, old_counts, gaps = {}, {}, {}
        for state, (_, heights) in states.items():
            a_counts[state], old_counts[state], gaps[state] = [], [], []
            for i in (1, 2, 3):
                tick = time.monotonic()
                scores = []
                for variant in ('A', 'R'):
                    name = f'{variant}-{i}.{state}'
                    trace = baseline['rows'][name]
                    extract, row = one(base / f'{name}.extract.json', base / f'{name}.score.json', trace)
                    treatment = {}
                    for z in heights:
                        s = extract['sections'][z][-1]
                        old_hit = bool(det['wall_intervals']([s], a, u))
                        new_hit = old_hit and all(abs(det['local'](p, a, u)[1]) <= det['TOL']['contour_max_dev_m'] for p in s)
                        treatment[z] = 'excluded' if old_hit and not new_hit else ('retained' if new_hit else 'not_exercised')
                    if 'excluded' in treatment.values():
                        exercise.add(variant)
                    row.update(segments_added_by_z=trace['segments_added_by_z'], inserted_segment_treatment=treatment)
                    result['rows'][name] = row
                    scores.append(row['raw_score'])
                    if variant == 'A':
                        a_counts[state].append(row['C1_annotation'])
                        old_counts[state].append(row['old_annotation'])
                        if row['old_annotation'] == 3 and trace['target_presence'] == 'fail':
                            raw_witness.add((state, i))
                    else:
                        r_bound &= row['C1_annotation'] == 18 and not row['removed_ids'] and not row['added_ids']
                gaps[state].append(scores[0] - scores[1])
                save()
                elapsed = time.monotonic() - tick
                if 'candidate_first_pair_s' not in result:
                    result['candidate_first_pair_s'] = round(elapsed, 4)
                    result['candidate_remaining_estimate_s'] = 1.5 * elapsed * (3 * len(states) - 1)
                    if time.monotonic() - start + result['candidate_remaining_estimate_s'] > 300:
                        result['status'] = 'budget_stop'
                        return
                if time.monotonic() - start > 300:
                    result['status'] = 'budget_stop'
                    return
        ref['preflight']()
        for variant in ('A', 'R'):
            require(digest(native / f'{variant}.fbx') == scans[f'{variant}-1']['candidate_fbx_sha256'], 'staged FBX drift')
        f = max(map(statistics.median, a_counts.values()))
        result.update(status='complete', F=f, F_baseline=max(map(statistics.median, old_counts.values())),
                      A_counts=a_counts, baseline_A_counts=old_counts, clean_gap_pp=baseline['form_gap_pp'],
                      pair_gaps_pp=gaps, clean_gap_spread_pp=baseline['form_spread_pp'],
                      exercised_variants=sorted(exercise), original_annotation_parity=original_bound,
                      injected_R_bound=r_bound, raw_positive_A_witnesses=len(raw_witness))
        if original_bound and exercise == {'A', 'R'} and raw_witness and all(min(g) >= 5 for g in gaps.values()):
            result['hypothesis'] = 'confirmed' if f == 0 and r_bound else 'refuted'
    except Exception as exc:
        result.update(status='error', error=str(exc))
        raise
    finally:
        save()
        print({k: v for k, v in result.items() if k not in ('rows', 'controls')})


if __name__ == '__main__':
    main(Path(sys.argv[1]))
