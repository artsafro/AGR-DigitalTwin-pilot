"""Apply evidence-only parallel segments; reuse the pinned standing #42 evaluator."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import statistics
import subprocess
import sys
import time

PIN = 'e63634826fa9c39897602634965e3347929ccf3f:docs/research/autoresearch-body-form-r42/'
STATES = {
    'one_110': (.110, ('17.8',)),
    'both_060': (.060, ('17.8', '18.2')),
    'both_110': (.110, ('17.8', '18.2')),
    'both_n110': (-.110, ('17.8', '18.2')),
    'both_130': (.130, ('17.8', '18.2')),
}
OPENING = '4259581'
PREFIX = f'opening:{OPENING}:'


def blob(name):
    return subprocess.check_output(['git', 'show', PIN + name])


def dump(path, data):
    path.write_bytes((json.dumps(data, indent=2) + '\n').encode())


def main(out):
    started = time.monotonic()
    deadline = started + 240
    out = out.resolve()
    out.mkdir(parents=True)
    result = {'status': 'running', 'hypothesis': 'inconclusive', 'rows': {}}
    driver = blob('replay.py')
    result['r42_driver_sha256'] = hashlib.sha256(driver).hexdigest()
    result['probe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    baseline = out / 'baseline'

    def save():
        result['wall_s'] = round(time.monotonic() - started, 3)
        dump(out / 'receipt.json', result)

    def child(args, log, env=None):
        with log.open('wb') as fd:
            subprocess.run([str(a) for a in args], check=True, cwd=out, env=env, stdout=fd,
                           stderr=subprocess.STDOUT, timeout=max(.001, deadline - time.monotonic()))

    try:
        local_driver = out / 'r42.py'
        local_driver.write_bytes(driver)
        child([sys.executable, local_driver, baseline], out / 'r42.log')
        ref = runpy.run_path(str(local_driver))
        read, require = ref['read'], ref['require']
        clean = read(baseline / 'receipt.json')
        result['baseline_wall_s'] = clean['wall_s']
        result['baseline_first_pair_s'] = clean.get('first_pair_s')
        result['baseline_status'] = clean['status']
        if clean['status'] == 'budget_stop':
            result['status'] = 'budget_stop'
            return
        historic = json.loads(blob('receipt.json'))
        result['baseline_checks'] = clean['qualification_checks']
        result['baseline_parity'] = clean['rows'] == historic['rows']
        require(result['baseline_parity'] and all(result['baseline_checks'].values()), 'R42 baseline differs')
        protocol = ref['PROTOCOL']
        score = protocol / 'detector/score_heldout.py'
        keyfile = protocol / 'key/heldout-key-v001.json'
        sums = protocol / 'key/SHA256SUMS.txt'
        det = runpy.run_path(str(score))
        key = read(keyfile)
        opening, = (o for o in key['openings'] if o['id'] == OPENING)
        require(opening['contour_segment'] == [24, 25], 'wrong source facet')
        ring = {v['ring_index']: v['xy'] for v in key['contour_vertices_in_box']}
        a, u, _ = det['frame'](ring, 24, 25)
        lo, hi = opening['edge_s_m']
        n = (u[1], -u[0])
        tmp = out / 'probe-temp'
        tmp.mkdir()
        env = dict(os.environ, TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp))
        result['clean_rows'] = {label: row for label, row in clean['rows'].items() if label.startswith(('A-', 'R-'))}
        result['form_gap_pp'] = clean['form_gap_pp']
        result['form_spread_pp'] = clean['form_spread_pp']
        result['baseline_receipt_sha256'] = ref['sha'](baseline / 'receipt.json')
        result['offsets_m'] = {k: v[0] for k, v in STATES.items()}
        for i in (1, 2, 3):
            for state, (offset, heights) in STATES.items():
                pair_start = time.monotonic()
                for variant in ('A', 'R'):
                    label = f'{variant}-{i}'
                    stem = f'{label}.{state}'
                    original = baseline / f'{label}.extract.json'
                    baseline_items = read(baseline / f'{label}.score.json')['items']
                    extract = read(original)
                    segment = [[a[j] + t*u[j] + offset*n[j] for j in (0, 1)] for t in (lo-.010, hi+.010)]
                    for z in heights:
                        extract['sections'][z].append(segment)
                    changed = {z: len(segments) - len(read(original)['sections'][z])
                               for z, segments in extract['sections'].items()}
                    for z in heights:
                        require(extract['sections'][z].pop() == segment, 'not the inserted segment')
                    require(extract == read(original), 'non-local injection')
                    for z in heights:
                        extract['sections'][z].append(segment)
                    inputfile = out / f'{stem}.extract.json'
                    outfile = out / f'{stem}.score.json'
                    dump(inputfile, extract)
                    child([sys.executable, score, keyfile, sums, inputfile, outfile], out / f'{stem}.log', env)
                    report = read(outfile)
                    observed = ref['observe'](det, key, extract, report)
                    items = report['items']
                    diffs = sorted(k for k in items.keys() | baseline_items.keys() if items.get(k) != baseline_items.get(k))
                    result['rows'][stem] = {
                        'extract_sha256': ref['sha'](inputfile), 'native_extract_sha256': ref['sha'](original),
                        'raw_score_sha256': ref['sha'](outfile), 'segments_added_by_z': changed,
                        'raw_changed_items': diffs, 'target_presence': items[PREFIX + 'present']['status'],
                        'target_dependents': {key.removeprefix(PREFIX): value['status'] for key, value in items.items()
                                              if key.startswith(PREFIX) and key != PREFIX + 'present'},
                        **observed,
                    }
                    save()
                if i == 1 and state == next(iter(STATES)):
                    elapsed = time.monotonic() - pair_start
                    result['first_probe_pair_s'] = round(elapsed, 3)
                    result['remaining_probe_estimate_s'] = round(1.5 * elapsed * (3 * len(STATES) - 1), 3)
                    if result['remaining_probe_estimate_s'] > deadline - time.monotonic():
                        result['status'] = 'budget_stop'
                        return
        matrix = result['rows']
        a_counts = {s: [matrix[f'A-{i}.{s}']['candidate_changed_rows'] for i in (1, 2, 3)] for s in STATES}
        result['F'] = max(map(statistics.median, a_counts.values()))
        result['A_counts_by_state'] = a_counts
        result['A_spread_by_state'] = {s: max(counts) - min(counts) for s, counts in a_counts.items()}
        bounds = True
        trigger = False
        for s in STATES:
            for i in (1, 2, 3):
                ar, rr = (matrix[f'{v}-{i}.{s}'] for v in ('A', 'R'))
                trigger |= ar['target_presence'] == 'fail'
                bounds &= (all(k.startswith(PREFIX) for k in ar['raw_changed_items']) and not rr['raw_changed_items']
                           and ar['raw_gap_counts']['FN'] <= 1 and ar['raw_gap_counts']['FP_extra'] == 0
                           and ar['candidate_changed_rows'] in (0, 3) and rr['candidate_changed_rows'] == 18
                           and ar['raw_form_score_unchanged'] > rr['raw_form_score_unchanged']
                           and (s != 'both_130' or not ar['raw_changed_items']))
        ref['preflight']()
        for label, row in result['clean_rows'].items():
            require(ref['sha'](baseline / f'{label[0]}.fbx') == row['candidate_fbx_sha256'], 'staged FBX drift')
        result['bounds_ok'] = bounds
        result['raw_presence_trigger_exercised'] = trigger
        result['status'] = 'complete'
        if bounds and trigger:
            result['hypothesis'] = 'refuted' if result['F'] > 0 else 'confirmed'
    except subprocess.TimeoutExpired:
        result['status'] = 'budget_stop'
    except Exception as exc:
        result.update(status='error', error=str(exc))
        raise
    finally:
        save()


if __name__ == '__main__':
    main(Path(sys.argv[1]))
