"""Read-only standing #48 observer over the pinned #44 replay."""
import contextlib
import hashlib
import json
from pathlib import Path
import runpy
import statistics
import subprocess
import sys
import time

PIN = '3a843a21a5abfdd8835fba8e862b91f282e99ffa:docs/research/autoresearch-body-form-r44/'
CONTRACT = '86a36bb3'
CAP = 240


def blob(name):
    return subprocess.check_output(['git', 'show', PIN + name])


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def observe(det, key, extract, raw):
    counts = raw['openings']
    if not isinstance(counts, dict):
        return counts, [], 'not_measured'
    heights = det['OPENING_Z']
    box = key['box_xy_m']
    sections = [[s for s in extract['sections'].get(z, ()) if
                 any(det['inbox'](p, box, 0.5) for p in s)] for z in heights]
    if not all(sections):
        return counts, [], 'not_measured'
    ring = {v['ring_index']: v['xy'] for v in key['contour_vertices_in_box']}
    extras = raw['extra_openings']
    proposals = []
    for opening in key['openings']:
        oid = opening['id']
        if raw['items'][f'opening:{oid}:present']['status'] != 'fail':
            continue
        i, j = opening['contour_segment']
        a, u, _ = det['frame'](ring, i, j)
        lo, hi = opening['edge_s_m']
        mid = (lo + hi) / 2
        intervals = [det['wall_intervals'](s, a, u) for s in sections]
        found = [[g for g in det['gaps'](iv, lo - 0.6, hi + 0.6) if
                  g[0] < mid < g[1]] for iv in intervals]
        for side in (0, 1):
            other = 1 - side
            if len(found[side]) != 1 or found[other] or not any(
                    l <= lo and hi <= r for l, r in intervals[other]):
                continue
            gap, = found[side]
            if max(abs(gap[0] - lo), abs(gap[1] - hi)) > det['TOL']['opening_edge_m']:
                continue
            extra_index = None
            if side == 1:
                target = {'ring_seg': [i, j], 'gap_m': [round(x, 3) for x in gap]}
                matches = [idx for idx, extra in enumerate(extras) if extra == target]
                if len(matches) != 1:
                    continue
                extra_index, = matches
            proposals.append({'opening_id': oid, 'gap_z': heights[side], 'extra_index': extra_index})
    taken = [x['extra_index'] for x in proposals if x['extra_index'] is not None]
    conflicts = [x for x in proposals if x['extra_index'] is None or taken.count(x['extra_index']) == 1]
    diagnostic = dict(counts, FN=counts['FN'] - len(conflicts),
                      FP_extra=counts['FP_extra'] - sum(x['extra_index'] is not None for x in conflicts))
    return diagnostic, conflicts, 'exercised' if conflicts else 'not_exercised'


def main(out):
    start = time.monotonic()
    out = out.resolve()
    out.mkdir(parents=True)
    res = {'status': 'running', 'hypothesis': 'inconclusive', 'contract': CONTRACT,
           'candidate_sha256': sha(Path(__file__)), 'controls': {}, 'matrix': {}}

    def save():
        res['wall_s'] = round(time.monotonic() - start, 3)
        (out / 'receipt.json').write_bytes((json.dumps(res, indent=2) + '\n').encode())

    try:
        driver = out / 'r44.py'
        driver.write_bytes(blob('probe.py'))
        res['r44_sha256'] = sha(driver)
        prior = runpy.run_path(str(driver))
        states = prior['STATES']
        states['one_hi_110'] = (.110, ('18.2',))
        base = out / 'prior'
        with (out / 'r44.log').open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log):
            prior['main'](base)
        live = read(base / 'receipt.json')
        res['prior_wall_s'] = live['wall_s']
        res['native_first_pair_s'] = live['baseline_first_pair_s']
        if live['status'] == 'budget_stop' or time.monotonic() - start > CAP:
            res['status'] = 'budget_stop'
            return
        archived = json.loads(blob('receipt.json'))
        excluded = {'extract_sha256', 'native_extract_sha256', 'raw_score_sha256'}

        def canonical(row):
            return {k: v for k, v in row.items() if k not in excluded}

        parity = (live['clean_rows'] == archived['clean_rows'] and all(
            canonical(live['rows'][name]) == canonical(row) for name, row in archived['rows'].items()))
        res['prior_parity'] = parity
        require(live['status'] == 'complete' and parity, 'prior baseline replay failed')
        res['clean_margin_pp'] = live['form_gap_pp']
        res['clean_margin_spread_pp'] = live['form_spread_pp']
        ref = runpy.run_path(str(base / 'r42.py'))
        protocol = ref['PROTOCOL']
        key = read(protocol / 'key/heldout-key-v001.json')
        det = runpy.run_path(str(protocol / 'detector/score_heldout.py'))
        native = base / 'baseline'
        native_rows = read(native / 'receipt.json')['rows']

        def run(extract_path, report_path, source, injected):
            report_sha = sha(report_path)
            raw = read(report_path)
            diagnostic, conflicts, exercise = observe(det, key, read(extract_path), raw)
            require(sha(report_path) == report_sha, 'raw report changed')
            require(raw['openings'] == source['raw_gap_counts'], 'raw gap parity failed')
            return {'extract_sha256': sha(extract_path), 'raw_score_sha256': report_sha,
                    'fbx_sha256': raw['provenance']['candidate_fbx_sha256'],
                    'raw': raw['openings'], 'diagnostic': diagnostic, 'conflicts': conflicts,
                    'changed_count': len(conflicts), 'exercise': exercise, 'segments_added_by_z': injected,
                    'raw_form_score': source['raw_form_score_unchanged'],
                    'raw_unknown_pct': source['baseline_unknown_pct'],
                    'raw_outline_sections_m': source['section_maxima_m_rounded'],
                    'raw_measured_depths_m': source['measured_depths_m_rounded']}

        for name, source in native_rows.items():
            if name.startswith(('J1_', 'J2_', 'J3_')):
                path = protocol / 'controls' / f'{name}.extract.json'
            elif name == 'J4_stale_key':
                path = native / 'A-1.extract.json'
            elif name == 'J4_clean_preflight':
                path = native / 'C_none-1.extract.json'
            else:
                path = native / f'{name}.extract.json'
            res['controls'][name] = run(path, native / f'{name}.score.json', source, {})

        def tuple_counts(d):
            return d['TP'], d['FP_extra'], d['FN']

        tests = {}
        for name, row in res['controls'].items():
            tests[name] = row['diagnostic'] == row['raw'] and not row['conflicts']
            if name.startswith('J2_'):
                tests[name] &= row['raw']['FP_extra'] == 1
            if name.startswith('J1_'):
                tests[name] &= row['raw']['FN'] == 1
            if name.startswith('A-'):
                tests[name] &= tuple_counts(row['raw']) == (6, 0, 0)
            if name.startswith('R-') and name != 'R-mask':
                tests[name] &= tuple_counts(row['raw']) == (0, 0, 6)
            if name.startswith('J4_') or name == 'R-mask':
                tests[name] &= row['exercise'] == 'not_measured'
        res['control_bounds'] = tests
        # For planted rows use the canonical #44 trace metrics, not a second scorer.
        for state in states:
            for i in (1, 2, 3):
                tick = time.monotonic()
                for variant in ('A', 'R'):
                    name = f'{variant}-{i}.{state}'
                    source = live['rows'][name]
                    row = run(base / f'{name}.extract.json', base / f'{name}.score.json', source,
                              source['segments_added_by_z'])
                    res['matrix'][name] = row
                    expected = {'one_110': (5, 1, 1), 'one_hi_110': (5, 0, 1),
                                'both_130': (6, 0, 0)}.get(state, (5, 0, 1))
                    conflict = variant == 'A' and state in ('one_110', 'one_hi_110')
                    tests[name] = (tuple_counts(row['raw']) == (expected if variant == 'A' else (0, 0, 6)) and
                                   tuple_counts(row['diagnostic']) == ((5, 0, 0) if conflict else tuple_counts(row['raw'])) and
                                   row['changed_count'] == int(conflict) and
                                   (not conflict or row['conflicts'][0]['opening_id'] == prior['OPENING']))
                save()
                elapsed = time.monotonic() - tick
                if 'diagnostic_first_pair_s' not in res:
                    res['diagnostic_first_pair_s'] = round(elapsed, 4)
                    res['remaining_estimate_s'] = round(1.5 * elapsed * (3 * len(states) - 1), 4)
                    if time.monotonic() - start + res['remaining_estimate_s'] > CAP:
                        res['status'] = 'budget_stop'
                        return
                if time.monotonic() - start > CAP:
                    res['status'] = 'budget_stop'
                    return
        ref['preflight']()
        for variant in ('A', 'R'):
            require(sha(native / f'{variant}.fbx') == native_rows[f'{variant}-1']['candidate_fbx_sha256'], 'FBX drift')
        primary = [res['matrix'][f'A-{i}.one_110'] for i in (1, 2, 3)]
        old = [min(row['raw']['FN'], row['raw']['FP_extra']) for row in primary]
        new = [min(row['diagnostic']['FN'], row['diagnostic']['FP_extra']) for row in primary]
        spread = max(new) - min(new)
        confirmed = (all(tests.values()) and old == [1, 1, 1] and new == [0, 0, 0] and
                     min(res['clean_margin_pp']) >= 5 and res['clean_margin_spread_pp'] <= 0.1)
        res.update(status='complete', hypothesis='confirmed' if confirmed else 'refuted',
                   D_baseline=statistics.median(old), D=statistics.median(new), D_spread=spread,
                   D_raw_rows=old, D_diagnostic_rows=new)
    except Exception as exc:
        res.update(status='error', error=str(exc))
        raise
    finally:
        save()
        print({k: v for k, v in res.items() if k not in ('controls', 'matrix', 'control_bounds')})


if __name__ == '__main__':
    main(Path(sys.argv[1]))
