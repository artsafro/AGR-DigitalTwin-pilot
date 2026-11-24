"""Measure collateral gap loss with the existing #48 observer; no mesh writes."""
import hashlib
import json
from pathlib import Path
import runpy
import statistics
import subprocess
import sys
import time

PIN = '903a6501eca965bb4cce4bb0fc410031bdd05562:docs/research/autoresearch-body-form-r48/probe.py'
CONTRACT = 'a2a770b7a7fc2cb36fc9e7319f7b24fd8405f1c5'
CAP = 240
TARGET = '4259581'
FACET = [24, 25]
NEIGHBOR = (3.20, 3.70)
EXPECTED = {('A', False): ((6, 1, 0), (6, 1, 0)),
            ('A', True): ((5, 2, 1), (5, 1, 0)),
            ('R', False): ((0, 1, 6), (0, 1, 6)),
            ('R', True): ((0, 2, 6), (0, 1, 5))}


def subtract(section, det, a, u, lo, hi):
    out, removed, added = [], 0, 0
    tol = det['TOL']
    local = det['local']
    for seg in section:
        p, q = seg
        (s, d), (e, f) = local(p, a, u), local(q, a, u)
        length = ((q[0] - p[0])**2 + (q[1] - p[1])**2)**0.5
        if (length < 1e-6 or abs(e - s) / length < tol['parallel_cos'] or
                max(abs(d), abs(f)) >= tol['wall_line_search_m'] or
                max(s, e) <= lo or min(s, e) >= hi):
            out.append(seg)
            continue
        removed += 1
        if s > e:
            p, q, s, e = q, p, e, s

        def at(t):
            return [p[k] + (t-s)/(e-s)*(q[k]-p[k]) for k in (0, 1)]

        if s < lo:
            out.append([p, at(lo)])
            added += 1
        if e > hi:
            out.append([at(hi), q])
            added += 1
    return out, {'removed': removed, 'added': added}


def dump(path, data):
    path.write_bytes((json.dumps(data, indent=2) + '\n').encode())


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def triple(counts):
    return tuple(counts[k] for k in ('TP', 'FP_extra', 'FN'))


def main(out):
    start = time.monotonic()
    out = out.resolve()
    out.mkdir(parents=True)
    res = dict(contract=CONTRACT, driver_sha256=sha(Path(__file__)), rows={},
               status='running', hypothesis='inconclusive')

    def save():
        res['wall_s'] = round(time.monotonic() - start, 3)
        dump(out / 'receipt.json', res)

    def child(args, log):
        with (out / log).open('wb') as fd:
            subprocess.run([sys.executable, *map(str, args)], check=True, stdout=fd,
                           stderr=subprocess.STDOUT, timeout=max(.001, CAP-(time.monotonic()-start)))

    try:
        driver = out / 'r48.py'
        driver.write_bytes(subprocess.check_output(['git', 'show', PIN]))
        res['observer_sha256'] = sha(driver)
        obs = runpy.run_path(str(driver))
        baseline = out / 'r48'
        child([driver, baseline], 'r48.log')
        prev = read(baseline / 'receipt.json')
        res['prior'] = {k: prev[k] for k in ('status', 'hypothesis', 'wall_s', 'native_first_pair_s')}
        res['prior_receipt_sha256'] = sha(baseline / 'receipt.json')
        if prev['status'] == 'budget_stop':
            res['status'] = 'budget_stop'
            return
        if prev['status'] != 'complete' or prev['hypothesis'] != 'confirmed':
            raise RuntimeError('prior qualification failed')
        res['clean'] = {k: v for k, v in prev['controls'].items() if k.startswith(('A-', 'R-'))}
        res['controls'] = prev['control_bounds']
        res['clean_margin_pp'] = prev['clean_margin_pp']
        res['clean_margin_spread_pp'] = prev['clean_margin_spread_pp']
        native = baseline / 'prior/baseline'
        ref = runpy.run_path(str(baseline / 'prior/r42.py'))
        protocol = ref['PROTOCOL']
        scorer = protocol / 'detector/score_heldout.py'
        keyfile = protocol / 'key/heldout-key-v001.json'
        key = read(keyfile)
        det = runpy.run_path(str(scorer))
        ring = {v['ring_index']: v['xy'] for v in key['contour_vertices_in_box']}
        opening, = (o for o in key['openings'] if o['id'] == TARGET and o['contour_segment'] == FACET)
        lo, hi = opening['edge_s_m']
        a, u, _ = det['frame'](ring, *FACET)
        low, high = det['OPENING_Z']
        losses = []
        for i in range(1, 4):
            for mixed in (True, False):
                tick = time.monotonic()
                pair = []
                for variant in ('A', 'R'):
                    label = f'{variant}-{i}'
                    state = f'{label}.{"mixed" if mixed else "neighbor"}'
                    source = native / f'{label}.extract.json'
                    clean = read(native / f'{label}.score.json')
                    ext = read(source)
                    changes = {}
                    for z in (low, high):
                        ext['sections'][z], changes[z] = subtract(ext['sections'][z], det, a, u, *NEIGHBOR)
                    if mixed and variant == 'A':
                        witness = read(baseline / 'prior' / f'{label}.one_110.extract.json')
                        original_low = read(source)['sections'][low]
                        assert witness['sections'][low][:-1] == original_low
                        ext['sections'][low].append(witness['sections'][low][-1])
                        changes['target'] = {low: {'added': 1, 'removed': 0}}
                    elif mixed:
                        ext['sections'][high], target_change = subtract(ext['sections'][high], det, a, u, lo, hi)
                        changes['target'] = {high: target_change}
                    restored = dict(ext, sections=dict(ext['sections']))
                    orig = read(source)
                    for z in (low, high):
                        restored['sections'][z] = orig['sections'][z]
                    assert restored == orig
                    ip, rp = (out / f'{state}.{kind}.json' for kind in ('extract', 'score'))
                    dump(ip, ext)
                    child([scorer, keyfile, protocol / 'key/SHA256SUMS.txt', ip, rp], f'{state}.log')
                    raw_sha = sha(rp)
                    raw = read(rp)
                    diag, conflicts, exercise = obs['observe'](det, key, ext, raw)
                    assert raw_sha == sha(rp) and raw['provenance'] == clean['provenance']
                    extras = raw['extra_openings']
                    removed = {c['extra_index'] for c in conflicts}
                    remaining = [x for idx, x in enumerate(extras) if idx not in removed]
                    identity = [x for x in extras if x['ring_seg'] == FACET and
                                max(abs(a-b) for a, b in zip(x['gap_m'], NEIGHBOR, strict=True)) <= .003]
                    permitted = {'openings:no_extra_in_box'}
                    if mixed:
                        permitted |= {f'opening:{TARGET}:{s}' for s in ('present', 'edges', 'sill_head', 'reveal_depth')}
                    diffs = [k for k in clean['items'].keys() | raw['items'].keys()
                             if clean['items'].get(k) != raw['items'].get(k)]
                    expected_raw, expected_diag = EXPECTED[variant, mixed]
                    raw_ok = (triple(raw['openings']) == expected_raw and len(identity) == 1 and
                              set(diffs) <= permitted and all(any(changes[z].values()) for z in (low, high)) and
                              (not mixed or any(next(iter(changes['target'].values())).values())))
                    diagnostic_ok = (triple(diag) == expected_diag and len(conflicts) == int(mixed) and
                                     (not mixed or conflicts[0]['opening_id'] == TARGET))
                    loss = int(identity[0] not in remaining) if raw_ok else None
                    res['rows'][state] = dict(raw=triple(raw['openings']), diagnostic=triple(diag),
                                               raw_extras=extras, remaining_extras=remaining, conflicts=conflicts,
                                               exercise=exercise, changed_count=len(conflicts), changes=changes,
                                               scorer_diffs=sorted(diffs), raw_ok=raw_ok, diagnostic_ok=diagnostic_ok,
                                               loss=loss, native_extract_sha256=sha(source),
                                               injected_extract_sha256=sha(ip), score_sha256=raw_sha)
                    pair.append(loss)
                if mixed:
                    losses.append(sum(pair) if None not in pair else None)
                if 'first_pair_s' not in res:
                    elapsed = time.monotonic() - tick
                    res.update(first_pair_s=round(elapsed, 3), remaining_estimate_s=round(1.5*elapsed*5, 3))
                    if time.monotonic()-start + res['remaining_estimate_s'] > CAP:
                        res['status'] = 'budget_stop'
                        return
                save()
        ref['preflight']()
        for variant in ('A', 'R'):
            assert sha(native / f'{variant}.fbx') == res['clean'][f'{variant}-1']['fbx_sha256']
        if time.monotonic()-start > CAP:
            res['status'] = 'budget_stop'
            return
        res.update(status='complete', losses=losses, L50=None, spread=None)
        if all(row['raw_ok'] for row in res['rows'].values()):
            res.update(L50=statistics.median(losses), spread=max(losses)-min(losses))
            if res['L50'] == res['spread'] == 0 and all(row['diagnostic_ok'] for row in res['rows'].values()):
                res['hypothesis'] = 'confirmed'
            elif min(losses) > 0 or any(all(not res['rows'][f'{v}-{i}.{s}']['diagnostic_ok']
                                            for i in range(1, 4)) for v in ('A', 'R') for s in ('mixed', 'neighbor')):
                res['hypothesis'] = 'refuted'
    except subprocess.TimeoutExpired:
        res['status'] = 'budget_stop'
    except Exception as exc:
        res.update(status='error', error=str(exc))
        raise
    finally:
        save()
        print({k: v for k, v in res.items() if k not in ('rows', 'clean', 'controls')})


if __name__ == '__main__':
    main(Path(sys.argv[1]))
