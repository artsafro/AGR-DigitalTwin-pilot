"""R107 paired diagnostic: S106 stated band vs S107 (same, railings dropped), reusing the pinned R105 runner."""
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
FLOOR, RAIL = 'Перекрытие', 'Ограждение'
FACES = ('xmin', 'ymin', 'zmin', 'xmax', 'ymax', 'zmax')
ORDER, HEADROOM_M, STEP_M = ('xmax', 'xmin', 'ymax', 'ymin'), 0.60, 0.50


def stated(rows, scope, drop_rails=True):
    """S106 selector; with drop_rails it is S107 (names starting with the railing prefix are not envelope)."""
    if scope is None:
        return None
    lo, hi = scope
    selected = [r for r in rows if lo - 1e-6 <= r[2][2] < hi - 1e-6 and not r[1].startswith(FLOOR)
                and not (drop_rails and r[1].startswith(RAIL))]
    if not selected:
        return None
    return {'ids': sorted(r[0] for r in selected), 'bounds_m': [
        [min(r[2][i] for r in selected) for i in range(2)] + [lo],
        [max(r[3][i] for r in selected) for i in range(2)] + [hi],
    ]}


def faces(selection):
    return selection['bounds_m'][0] + selection['bounds_m'][1]


def pick_face(selection, box):
    """First face in the frozen order whose outward headroom to the tower box is >= HEADROOM_M."""
    f = faces(selection)
    for name in ORDER:
        i = FACES.index(name)
        room = box['max'][i - 3] - f[i] if i >= 3 else f[i] - box['min'][i]
        if room >= HEADROOM_M:
            return name, i
    return None


def witness(selection, scope, face, name):
    (lo_x, lo_y, _), (hi_x, hi_y, _) = selection['bounds_m']
    low, high = [lo_x, lo_y], [hi_x, hi_y]
    _, i = face
    if i >= 3:
        high[i - 3] += STEP_M
    else:
        low[i] -= STEP_M
    z = sum(scope) / 2
    return (-1, name, [*low, z], [*high, z + .1])


def extremum_names(rows, selection):
    chosen = [r for r in rows if r[0] in set(selection['ids'])]
    f = faces(selection)
    out = {}
    for name, i in (('xmin', 0), ('ymin', 1), ('xmax', 3), ('ymax', 4)):
        side = 2 if i < 3 else 3
        out[name] = sorted({r[1] for r in chosen if r[side][i % 3] == f[i]})[:3]
    return out


def probe(runner, rows, box, built, key):
    tag = box['id']
    scope = SCOPE[tag]
    inside = runner.contained(rows, box)
    s106 = stated(inside, scope, drop_rails=False)
    s107 = stated(inside, scope)
    if s106 is None or s107 is None:
        return {'status': 'inconclusive', 'reason': 'missing S106 or S107 geometry'}

    def score(selection):
        return runner.bounds_step(runner.as_readback(selection), key)

    klo, khi = runner.box_of(key)
    ids, ids106 = set(s107['ids']), set(s106['ids'])
    removed = sorted(ids106 - ids)
    removed_names = {r[1] for r in inside if r[0] in set(removed)}
    ordered = stated(list(reversed(inside)), scope)
    shifted = stated(inside, tuple(z + .25 for z in scope))
    face = pick_face(s107, box)
    native, baseline = score(s107), score(s106)
    cov = {'order_changed_ids': len(set(ordered['ids']) ^ ids) if ordered else None,
           'rail_removed_ids': len(removed), 'rail_rule': 'exercised' if removed else 'not_exercised',
           'witness_face': face[0] if face else None,
           'headroom_m': {n: (box['max'][FACES.index(n) - 3] - faces(s107)[FACES.index(n)]) if FACES.index(n) >= 3
                          else (faces(s107)[FACES.index(n)] - box['min'][FACES.index(n)]) for n in ORDER}}
    wide_ok = relabel_ok = False
    if face:
        extra = witness(s107, scope, face, 'SYNTHETIC facade')
        wider = stated(runner.contained([*rows, extra], box), scope)
        rail = (-1, RAIL + ' SYNTHETIC', extra[2], extra[3])
        relabel = stated(runner.contained([*rows, rail], box), scope)
        expect = [0.0] * 6
        expect[face[1]] = STEP_M if face[1] >= 3 else -STEP_M
        if wider:
            deltas = [a - b for a, b in zip(faces(wider), faces(s107))]
            wide_native = score(wider)
            added, lost = sorted(set(wider['ids']) - ids), sorted(ids - set(wider['ids']))
            wide_ok = (added == [-1] and not lost and all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(deltas, expect))
                       and wide_native['status'] == 'fail' and wide_native['max_corner_dev_m'] >= .4)
            cov.update(wide_added_ids=added, wide_removed_ids=lost, wide_deltas_m=deltas, wide_native=wide_native)
        relabel_ok = relabel == s107
        cov['relabel_changed_ids_vs_clean'] = len(set(relabel['ids']) ^ ids) if relabel else None
    shift_native = score(shifted) if shifted else {}
    z_deltas = [faces(shifted)[i] - faces(s107)[i] for i in (2, 5)] if shifted else []
    cov.update(shift_z_deltas_m=z_deltas, shift_changed_ids=len(set(shifted['ids']) ^ ids) if shifted else None,
               shift_native=shift_native)
    ok = {
        'S106_parity': baseline['status'] == ('pass' if tag == '63A' else 'fail'),
        'row_order': ordered == s107,
        'rail_rule_fires': bool(removed) and ids <= ids106 and all(n.startswith(RAIL) for n in removed_names),
        'witness': wide_ok,
        'rail_relabel': relabel_ok,
        'shift': len(z_deltas) == 2 and all(math.isclose(d, .25, abs_tol=1e-9) for d in z_deltas)
        and shift_native.get('status') == 'fail' and shift_native.get('max_corner_dev_m', -1) >= .24,
        'absent_scope_refuses': stated(inside, None) is None,
    }
    return {
        'status': native['status'] if all(ok.values()) else 'inconclusive',
        'native': native, 'baseline_native': baseline, 'submitted_native': runner.bounds_step(built, key),
        'selected_rows': len(ids), 's106_rows': len(ids106), 'bounds_m': s107['bounds_m'],
        's106_bounds_m': s106['bounds_m'], 'signed_face_deltas_m': [a - b for a, b in zip(faces(s107), klo + khi)],
        'extremum_names': extremum_names(inside, s107), 'removed_name_prefixes': sorted({n[:40] for n in removed_names})[:10],
        'controls': ok, 'coverage': cov,
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
    if git_blob(commit, script.relative_to(ROOT).as_posix()) != script.read_bytes().replace(b'\r\n', b'\n'):
        raise ValueError('variant differs from frozen Git blob')
    scope_hashes = {}
    for path in ('docs/trainer/ledger.json', 'docs/trainer/etalons.json', 'jobs/POLY63-B/REPORT.md'):
        frozen = git_blob(BASE, path)
        if frozen != (ROOT / path).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError(f'scope/ledger provenance mismatch: {path}')
        scope_hashes[path] = hashlib.sha256(frozen).hexdigest()
    previous, manifest = git_blob(PREVIOUS, DRIVER), git_blob(PREVIOUS, MANIFEST)
    driver = ModuleType('r105_native_replay')
    driver.__file__ = str(script)  # R105 resolves ROOT and hashes the invoking replay from this layout.
    exec(compile(previous, f'{PREVIOUS}:{DRIVER}', 'exec'), driver.__dict__)
    vars(driver).update(CONTRACT=SimpleNamespace(read_text=lambda *, encoding: manifest.decode(encoding)),
                        tower=lambda *args: probe(driver, *args), decide=verdict)
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
        summary[tag] = {'S106_median_m': statistics.median(before), 'S107_median_m': statistics.median(after),
                        'paired_gain_range_m': [min(gains), max(gains)]}
    report.update(summary=summary, variant_commit=commit, known_scope_m=SCOPE, scope_blob_sha256=scope_hashes,
                  previous_commit=PREVIOUS, previous_driver_sha256=hashlib.sha256(previous).hexdigest(),
                  previous_manifest_sha256=hashlib.sha256(manifest).hexdigest())
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'summary': summary, 'status': report['status'], 'hypothesis': report['hypothesis']}))


if __name__ == '__main__':
    main()
