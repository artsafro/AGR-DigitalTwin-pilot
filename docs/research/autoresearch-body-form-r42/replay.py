"""Standing 42 diagnostic replay. Uses the original evaluator; writes only a new output directory."""
import hashlib
import json
import os
import re
import runpy
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROTOCOL = Path('C:/x/t_563a40f7')
OLD = Path('C:/x/autoresearch-body-form-r40/evidence')
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
NATIVE = {'A': 'A', 'R': 'R', 'C_none': 'C_none', 'C_shift_opening': 'C_shift_opening', 'C_shift_wall': 'C_shift_wall'}
J_CASES = ['J1_missing_4259581', 'J2_extra_endwall', 'J3_stair_cut_basket', 'J4_stale_key']


def sha(path):
    with path.open('rb') as fd:
        return hashlib.file_digest(fd, 'sha256').hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def preflight():
    for root, digest in ((PROTOCOL, '867ee607a4f054c70ba05e1466fad639b4579756882d4f443b142a8df79e6488'),
                         (PROTOCOL / 'key', '723b11a951e4fa786e4725dc78613d8d3b797b4bc8dd3dc99c9286720491ac88'),
                         (OLD, 'e7f633b61d445e0e75cd5505c91a2a13b6f710f9191bd0b61ffb7cd11b522f2c')):
        manifest = root / 'SHA256SUMS.txt'
        require(sha(manifest) == digest, f'manifest drift: {manifest}')
        for line in manifest.read_text(encoding='utf-8').splitlines():
            expected, name = line.split(maxsplit=1)
            path = root / name.lstrip('*')
            require(sha(path) == expected, f'input drift: {path}')
    require(sha(BLENDER) == '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5', 'Blender drift')


def read(path):
    return json.loads(path.read_bytes())


def parity(raw, old):
    def normalize(doc):
        doc = json.loads(json.dumps(doc))
        doc.pop('fbx', None)
        doc.get('provenance', {}).pop('candidate_fbx', None)
        return doc
    return normalize(raw) == normalize(old)


def observe(detector, key, extract, report):
    items = report['items']
    annotation = set()
    mouth_counts = {'covered_both': 0, 'eligible_dependents': 0}
    if report['provenance']['key_hash_ok'] and report['provenance']['candidate_fbx_sha256']:
        box = key['box_xy_m']
        ring = {r['ring_index']: r['xy'] for r in key['contour_vertices_in_box']}
        for opening in key['openings']:
            prefix = f"opening:{opening['id']}"
            if items[prefix + ':present']['status'] != 'fail':
                continue
            a, u, _ = detector['frame'](ring, *opening['contour_segment'])
            lo, hi = opening['edge_s_m']
            cover = []
            for z in detector['OPENING_Z']:
                segments = [s for s in extract['sections'].get(z, [])
                            if any(detector['inbox'](p, box, 0.5) for p in s)]
                cover.append(any(l <= lo and hi <= h for l, h in detector['wall_intervals'](segments, a, u)))
            mouth_counts['covered_both'] += all(cover)
            for part in ('edges', 'reveal_depth', 'sill_head'):
                name = f'{prefix}:{part}'
                if items[name] == {'status': 'not_measured', 'basis': 'opening missing'}:
                    mouth_counts['eligible_dependents'] += 1
                    if all(cover):
                        annotation.add(name)
    weights = {'pass': 0, 'fail': 0, 'not_measured': 0, 'not_applicable': 0}
    for name, row in items.items():
        if row.get('score_group') == 'B' or (name.startswith('negative:') and name.endswith(':4259062')):
            continue
        weight = (3 if name.startswith('contour@') or name.endswith(':present') or name == 'openings:no_extra_in_box'
                  else 1 if name == 'scope:no_fills_stage1' else 2)
        weights[row['status']] += weight
    total = sum(weights.values()) - weights['not_applicable']
    excluded = 2 * len(annotation)
    full_schema = total == 66
    return {
        'raw_weights': weights,
        'raw_form_score_unchanged': 100 * weights['pass'] / total if full_schema else None,
        'baseline_unknown_pct': 100 * weights['not_measured'] / total if full_schema else None,
        'candidate_unknown_pct': 100 * (weights['not_measured'] - excluded) / (total - excluded) if full_schema else None,
        'excluded_original_weight_pct': 100 * excluded / total if full_schema else None,
        'baseline_changed_rows': 0,
        'candidate_changed_rows': len(annotation),
        'annotation_exercise': 'exercised' if annotation else 'not_exercised',
        **mouth_counts,
        'raw_groupA': report['summary_groupA'], 'raw_groupB': report['summary_groupB'],
        'raw_gap_counts': report['openings'],
        'candidate_fbx_sha256': report['provenance']['candidate_fbx_sha256'],
        'section_maxima_m_rounded': {name: float(m.group(1)) for name, row in items.items()
                                    if name.startswith('contour@') and (m := re.match(r'two-sided max ([0-9.]+) m', row['basis']))},
        'measured_depths_m_rounded': sorted(float(m.group(1)) for name, row in items.items()
                                           if name.endswith(':reveal_depth') and (m := re.match(r'depth ([0-9.]+) vs', row['basis']))),
    }


def main(out):
    out = out.resolve()
    out.mkdir(parents=True)
    preflight()
    started = time.monotonic()
    results = {'status': 'running', 'rows': {}}
    receipt = out / 'receipt.json'

    def save():
        results['wall_s'] = round(time.monotonic() - started, 3)
        receipt.write_bytes((json.dumps(results, indent=2) + '\n').encode())

    det = PROTOCOL / 'detector'
    key_file = PROTOCOL / 'key/heldout-key-v001.json'
    key_sums = PROTOCOL / 'key/SHA256SUMS.txt'
    key = read(key_file)
    detector = runpy.run_path(str(det / 'score_heldout.py'))
    temp = out / 'native-temp'
    temp.mkdir()
    env = dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    sources = {}
    for name in NATIVE:
        source = OLD / f'{name}.fbx'
        copied = out / source.name
        shutil.copyfile(source, copied)
        sources[name] = (copied, sha(source))
        require(sha(copied) == sources[name][1], f'copy drift: {name}')

    def child(args, label):
        with (out / f'{label}.log').open('wb') as log:
            subprocess.run([str(a) for a in args], check=True, env=env, cwd=out,
                           stdout=log, stderr=subprocess.STDOUT, timeout=max(0.1, 150 - (time.monotonic() - started)))

    def score(name, extract_path, archive, key_path=key_file, native_archive=None):
        destination = out / f'{name}.score.json'
        child([sys.executable, det / 'score_heldout.py', key_path, key_sums, extract_path, destination], f'{name}.score')
        raw = read(destination)
        extract = read(extract_path)
        row = observe(detector, key, extract, raw)
        row['raw_score_parity'] = None if archive is None else parity(raw, read(archive))
        row['native_extract_parity'] = None if native_archive is None else parity(extract, read(native_archive))
        results['rows'][name] = row
        save()

    def native(name, i):
        label = f'{name}-{i}'
        archive_label = label if name in ('A', 'R') else f'{name}-1'
        extract = out / f'{label}.extract.json'
        child([BLENDER, '--background', '--factory-startup', '--disable-autoexec', '--threads', '1',
               '--python-exit-code', '1', '--python', det / 'extract.py', '--', sources[name][0], extract,
               '16.85,17.8,18.2,19.8'], f'{label}.native')
        score(label, extract, OLD / f'{archive_label}.score.json', native_archive=OLD / f'{archive_label}.extract.json')

    try:
        native('C_none', 1)
        require(results['rows']['C_none-1']['raw_groupA']['pass'] == 29, 'clean detector self-check failed')
        score('J4_clean_preflight', out / 'C_none-1.extract.json', OLD / 'J4-on-C_none.score.json',
              PROTOCOL / 'controls/stale-key/heldout-key-v001.json')
        require(results['rows']['J4_clean_preflight']['raw_groupA']['pass'] == 0, 'stale detector self-check failed')
        pair_started = time.monotonic()
        native('A', 1)
        native('R', 1)
        pair_wall = time.monotonic() - pair_started
        results['first_pair_s'] = round(pair_wall, 3)
        if 4 * pair_wall > 150 - (time.monotonic() - started):
            results.update(status='budget_stop', hypothesis='inconclusive')
            return
        for i in (2, 3):
            native('A', i)
            native('R', i)
        for name in ('C_shift_opening', 'C_shift_wall'):
            native(name, 1)
        for name in J_CASES:
            stale = name == 'J4_stale_key'
            score(name, out / 'A-1.extract.json' if stale else PROTOCOL / f'controls/{name}.extract.json',
                  OLD / f'{name}-1.score.json', PROTOCOL / 'controls/stale-key/heldout-key-v001.json' if stale else key_file)
        masked = read(out / 'R-1.extract.json')
        results['offline_mask_removed_segments'] = len(masked['sections'].pop('17.8'))
        path = out / 'R-mask.extract.json'
        path.write_bytes(json.dumps(masked).encode())
        score('R-mask', path, None)
        rows = results['rows']
        pairs = [(rows[f'A-{i}'], rows[f'R-{i}']) for i in (1, 2, 3)]
        coverage_gap = [r['candidate_unknown_pct'] - a['candidate_unknown_pct'] for a, r in pairs]
        form_gap = [a['raw_form_score_unchanged'] - r['raw_form_score_unchanged'] for a, r in pairs]
        results.update(candidate_U_R=statistics.median(r['candidate_unknown_pct'] for _, r in pairs),
                       baseline_U_R=statistics.median(r['baseline_unknown_pct'] for _, r in pairs),
                       coverage_gap_pp=coverage_gap, coverage_spread_pp=max(coverage_gap) - min(coverage_gap),
                       form_gap_pp=form_gap, form_spread_pp=max(form_gap) - min(form_gap))
        results['qualification_checks'] = {
            'all_historical_parity': all(row['raw_score_parity'] is not False and row['native_extract_parity'] is not False
                                         for row in rows.values()),
            'pair_coverage_and_spread': results['candidate_U_R'] <= 10 and results['coverage_spread_pp'] <= .1 and
                                        all(a['candidate_unknown_pct'] == 0 and r['candidate_changed_rows'] > 0 for a, r in pairs),
            'form_bounds': statistics.median(form_gap) >= 5 and all(a['raw_form_score_unchanged'] >= 95 and
                                                                   r['raw_form_score_unchanged'] <= 90 for a, r in pairs),
            'clean_and_shifts': all(rows[name]['raw_gap_counts'] == {'TP': 6, 'FP_extra': 0, 'FN': 0, 'key_total': 6} and
                                    rows[name]['candidate_changed_rows'] == 0 and rows[name]['raw_groupA']['fail'] == fail
                                    for name, fail in (('C_none-1', 0), ('C_shift_opening-1', 1), ('C_shift_wall-1', 2))),
            'offline_controls': rows[J_CASES[0]]['raw_gap_counts']['FN'] == 1 and rows[J_CASES[0]]['candidate_changed_rows'] == 3 and
                                rows[J_CASES[1]]['raw_gap_counts']['FP_extra'] == 1 and rows[J_CASES[2]]['raw_groupB']['fail'] == 1 and
                                rows[J_CASES[3]]['raw_groupA']['pass'] == 0 and all(rows[j]['candidate_changed_rows'] == 0 for j in J_CASES[1:]),
            'offline_mask': results['offline_mask_removed_segments'] > 0 and rows['R-mask']['raw_gap_counts']['FN'] == 6 and
                            rows['R-mask']['candidate_changed_rows'] == 0 and rows['R-mask']['candidate_unknown_pct'] > 10,
        }
        results.update(status='complete', hypothesis='confirmed' if all(results['qualification_checks'].values()) else 'refuted')
    except subprocess.TimeoutExpired:
        results.update(status='budget_stop', hypothesis='inconclusive')
    except Exception as exc:
        results.update(status='error', hypothesis='inconclusive', error=str(exc))
        raise
    finally:
        try:
            preflight()
            for copied, digest in sources.values():
                require(sha(copied) == digest, f'copy drift: {copied}')
        except Exception as exc:
            results.update(status='input_drift', hypothesis='inconclusive', error=str(exc))
            raise
        finally:
            save()
            print(json.dumps({k: v for k, v in results.items() if k != 'rows'}))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
