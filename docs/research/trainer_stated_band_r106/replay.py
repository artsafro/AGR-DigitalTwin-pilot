"""R106 paired diagnostic: reuse the pinned R105 native import/readback runner."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
PREVIOUS = '95ae5adb1bf907e927b994296c51ad321edd18b7'
BASE = '7762dcfe2e78219155461bb633faaca2015e259b'
DRIVER = 'docs/research/trainer_storey_band_r105/replay.py'
MANIFEST = 'docs/research/autoresearch-trainer-storey-band-r105.md'
SCOPE = {'63A': (10.15, 47.95), '63B': (4.65, 51.90)}


def stated(rows, scope, floor):
    if scope is None:
        return None
    lo, hi = scope
    selected = [r for r in rows if lo - 1e-6 <= r[2][2] < hi - 1e-6 and not r[1].startswith(floor)]
    if not selected:
        return None
    return {'ids': sorted(r[0] for r in selected), 'bounds_m': [
        [min(r[2][i] for r in selected) for i in range(2)] + [lo],
        [max(r[3][i] for r in selected) for i in range(2)] + [hi],
    ]}


def probe(runner, rows, box, built, key):
    tag = box['id']
    scope = SCOPE[tag]
    inside = runner.contained(rows, box)
    inferred = runner.select(inside)
    selected = stated(inside, scope, runner.FLOOR)
    if inferred is None or selected is None:
        return {'status': 'inconclusive', 'reason': 'missing inferred or stated geometry'}

    def score(selection):
        return runner.bounds_step(runner.as_readback(selection), key)

    def faces(selection):
        return selection['bounds_m'][0] + selection['bounds_m'][1]

    klo, khi = runner.box_of(key)
    low, high = selected['bounds_m']
    ids = set(selected['ids'])
    ordered = stated(list(reversed(inside)), scope, runner.FLOOR)
    shifted = stated(inside, tuple(z + .25 for z in scope), runner.FLOOR)
    z = sum(scope) / 2
    extra = (-1, 'SYNTHETIC facade', [low[0], low[1], z], [high[0] + .5, high[1], z + .1])
    wider = stated(runner.contained([*rows, extra], box), scope, runner.FLOOR)
    floor = (-1, runner.FLOOR + ' SYNTHETIC', extra[2], extra[3])
    excluded = stated(runner.contained([*rows, floor], box), scope, runner.FLOOR)
    native, baseline = score(selected), score(inferred)
    shift_native, wide_native = score(shifted) if shifted else {}, score(wider) if wider else {}
    z_deltas = [faces(shifted)[i] - faces(selected)[i] for i in (2, 5)] if shifted else []
    shift_changed = len(set(shifted['ids']) ^ ids) if shifted else None
    wide_added = sorted(set(wider['ids']) - ids) if wider else []
    wide_removed = sorted(ids - set(wider['ids'])) if wider else []
    wide_deltas = [a - b for a, b in zip(faces(wider), faces(selected))] if wider else []
    floor_removed = sorted(set(wider['ids']) - set(excluded['ids'])) if wider and excluded else []
    ok = {
        'S105_parity': baseline['status'] == ('pass' if tag == '63A' else 'fail'),
        'row_order': ordered == selected,
        'shift': len(z_deltas) == 2 and all(math.isclose(d, .25, abs_tol=1e-9) for d in z_deltas)
        and shift_native.get('status') == 'fail' and shift_native.get('max_corner_dev_m', -1) >= .24,
        'wide': wide_added == [-1] and not wide_removed and len(wide_deltas) == 6
        and all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(wide_deltas, [0, 0, 0, .5, 0, 0]))
        and wide_native.get('status') == 'fail' and wide_native.get('max_corner_dev_m', -1) >= .4,
        'floor': excluded == selected and floor_removed == [-1],
        'absent_scope_refuses': stated(inside, None, runner.FLOOR) is None,
    }
    return {
        'status': native['status'] if all(ok.values()) else 'inconclusive',
        'native': native, 'baseline_native': baseline, 'submitted_native': runner.bounds_step(built, key),
        'selected_rows': len(ids), 'bounds_m': selected['bounds_m'], 'inferred_bounds_m': inferred['bounds_m'],
        'signed_face_deltas_m': [a - b for a, b in zip(faces(selected), klo + khi)],
        'controls': ok,
        'coverage': {'order_changed_ids': len(set(ordered['ids']) ^ ids) if ordered else None,
                     'shift_z_deltas_m': z_deltas, 'shift_changed_ids': shift_changed,
                     'shift_xy_membership': 'exercised' if shift_changed else 'not_exercised',
                     'shift_native': shift_native, 'wide_added_ids': wide_added, 'wide_removed_ids': wide_removed,
                     'wide_deltas_m': wide_deltas, 'wide_native': wide_native, 'floor_removed_ids': floor_removed,
                     'floor_changed_ids_vs_clean': len(set(excluded['ids']) ^ ids) if excluded else None},
    }


def verdict(pairs, status):
    if status != 'complete' or len(pairs) != 3 or any(p['status'] != 'complete' for p in pairs):
        return 'inconclusive'
    if any(p['63A']['status'] != 'pass' for p in pairs):
        return 'inconclusive'
    outcomes = [p['63B']['status'] for p in pairs]
    return {('pass',) * 3: 'confirmed', ('fail',) * 3: 'refuted'}.get(tuple(outcomes), 'inconclusive')


def git_blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def main():
    commit = sys.argv[2]
    if len(commit) != 40 or subprocess.check_output(
            ['git', 'rev-parse', f'{commit}^{{commit}}'], cwd=ROOT, text=True).strip() != commit:
        raise ValueError('pass the full frozen variant commit')
    script = Path(__file__).resolve()
    tracked_script = script.relative_to(ROOT).as_posix()
    if git_blob(commit, tracked_script) != script.read_bytes().replace(b'\r\n', b'\n'):
        raise ValueError('variant differs from frozen Git blob')
    scope_hashes = {}
    for path in ('docs/trainer/ledger.json', 'docs/trainer/etalons.json', 'jobs/POLY63-B/REPORT.md'):
        frozen = git_blob(BASE, path)
        if frozen != (ROOT / path).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError(f'scope/ledger provenance mismatch: {path}')
        scope_hashes[path] = hashlib.sha256(frozen).hexdigest()
    previous = git_blob(PREVIOUS, DRIVER)
    manifest = git_blob(PREVIOUS, MANIFEST)
    driver = ModuleType('r105_native_replay')
    driver.__file__ = str(script)  # R105 resolves ROOT and hashes the invoking replay from this layout.
    exec(compile(previous, f'{PREVIOUS}:{DRIVER}', 'exec'), driver.__dict__)
    driver.CONTRACT = SimpleNamespace(read_text=lambda *, encoding: manifest.decode(encoding))
    driver.tower = lambda *args: probe(driver, *args)
    driver.decide = verdict
    driver.main()
    path = Path(sys.argv[1]) / 'receipt.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    summary = {}
    for tag in SCOPE:
        runs = [p[tag] for p in report['results'] if 'native' in p.get(tag, {})]
        if len(runs) != 3:
            continue
        before = [r['baseline_native']['max_corner_dev_m'] for r in runs]
        after = [r['native']['max_corner_dev_m'] for r in runs]
        gains = [a - b for a, b in zip(before, after)]
        summary[tag] = {'S105_median_m': statistics.median(before), 'S106_median_m': statistics.median(after),
                        'paired_gain_range_m': [min(gains), max(gains)]}
    report.update(summary=summary, variant_commit=commit, known_scope_m=SCOPE, scope_blob_sha256=scope_hashes,
                  previous_commit=PREVIOUS, previous_driver_sha256=hashlib.sha256(previous).hexdigest(),
                  previous_manifest_sha256=hashlib.sha256(manifest).hexdigest())
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'summary': summary, 'status': report['status'], 'hypothesis': report['hypothesis']}))


if __name__ == '__main__':
    main()
