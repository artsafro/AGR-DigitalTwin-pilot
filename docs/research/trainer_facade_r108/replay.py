"""R108 observation only: a whole-family ablation of the pinned R107 selection."""
from pathlib import Path
from types import ModuleType, SimpleNamespace
import hashlib
import json
import math
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
R107 = '12708f1afc0cdd87a7d629419eeb40dfbfca1bb3'
PREFIX = 'Базовая стена Вентфасад 250 250 '
EPS = 1e-9


def blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def pinned_module(name, rev, path):
    code = blob(rev, path)
    module = ModuleType(name)
    module.__file__ = __file__  # reuse the runner's worktree root and invoking script hash
    exec(compile(code, f'{rev}:{path}', 'exec'), vars(module))
    return module


def prior_module():
    return pinned_module('r107', R107, 'docs/research/trainer_railing_r107/replay.py')


def select(prior, rows, scope, *, ablate):
    return prior.stated([r for r in rows if not (ablate and r[1].startswith(PREFIX))], scope)


def probe(driver, prior, reference, rows, box, built, key):
    tag = box['id']
    scope = prior.SCOPE[tag]
    inside = driver.contained(rows, box)
    before, after = (select(prior, inside, scope, ablate=x) for x in (False, True))
    if before is None or after is None:
        return {'status': 'inconclusive', 'eligible': False, 'reason': 'empty selection'}
    a_ids, b_ids = set(before['ids']), set(after['ids'])
    removed = [r for r in inside if r[0] in a_ids and r[1].startswith(PREFIX)]
    score = lambda sel: driver.bounds_step(driver.as_readback(sel), key)
    base, native = score(before), score(after)
    a, b = (s['max_corner_dev_m'] for s in (base, native))
    before_faces, after_faces = prior.faces(before), prior.faces(after)
    key_lo, key_hi = driver.box_of(key)
    ref = reference[tag]['S107_median_m']
    ordered = select(prior, list(reversed(inside)), scope, ablate=True)
    coverage = {'clean_removed_ids': sorted(a_ids - b_ids), 'order_changed_count': len(b_ids ^ set(ordered['ids'])),
                'native_trigger': 'exercised' if removed else 'not_exercised', 'witness': 'not_exercised'}
    picked = prior.pick_face(before, box)
    witness_ok = False
    if picked is not None:
        face, i = picked
        plain = prior.witness(before, scope, picked, 'SYNTHETIC facade')
        named = (plain[0], PREFIX + 'SYNTHETIC', *plain[2:])
        plain_after = select(prior, driver.contained([*inside, plain], box), scope, ablate=True)
        labelled_before = select(prior, driver.contained([*inside, named], box), scope, ablate=False)
        labelled_after = select(prior, driver.contained([*inside, named], box), scope, ablate=True)
        p_ids, lb_ids, la_ids = (set(s['ids']) for s in (plain_after, labelled_before, labelled_after))
        expected = list(after_faces)
        expected[i] = before_faces[i] + (0.5 if i >= 3 else -0.5)
        changed = prior.faces(plain_after)
        p_native = score(plain_after)
        witness_ok = (p_ids == b_ids | {-1} and lb_ids == a_ids | {-1} and labelled_after == after
                      and abs(changed[i] - after_faces[i]) > EPS
                      and all(math.isclose(x, y, abs_tol=EPS, rel_tol=0) for x, y in zip(changed, expected))
                      and p_native['status'] == 'fail')
        coverage.update(witness='exercised' if -1 in p_ids else 'not_exercised', witness_face=face,
                        plain_changed_count=len(p_ids ^ b_ids), labelled_baseline_changed_count=len(lb_ids ^ a_ids),
                        labelled_candidate_changed_count=len(la_ids ^ b_ids), plain_native=p_native,
                        plain_face_deltas_m=[x-y for x, y in zip(changed, after_faces)])
    controls = {'prior_parity': abs(a - ref) <= 1e-6 and base['status'] == ('pass' if tag == '63A' else 'fail'),
                'order': ordered == after, 'only_prefix': b_ids == a_ids - {r[0] for r in removed},
                'absent_band_refuses': all(select(prior, inside, None, ablate=x) is None for x in (False, True)),
                'witness': witness_ok}
    eligible = bool(removed) and all(controls.values()) and (tag != '63A' or abs(b-a) <= 0.05 + EPS)
    spans = [r[3][0] - r[2][0] for r in removed]
    xmax = lambda chosen, faces: sorted({r[1] for r in inside if r[0] in chosen and r[3][0] == faces[3]})
    return {'status': native['status'] if eligible else 'inconclusive', 'eligible': eligible,
            'baseline_native': base, 'native': native, 'direction_ok': after_faces[3] < before_faces[3] and b <= a + EPS,
            'baseline_face_deltas_m': [x-y for x, y in zip(before_faces, key_lo + key_hi)],
            'candidate_face_deltas_m': [x-y for x, y in zip(after_faces, key_lo + key_hi)],
            'baseline_xmax_names': xmax(a_ids, before_faces), 'candidate_xmax_names': xmax(b_ids, after_faces),
            'removed_x_span_range_m': [min(spans), max(spans)] if spans else None,
            'controls': controls, 'coverage': coverage}


def verdict(pairs, status):
    if status != 'complete' or len(pairs) != 3 or any(p['status'] != 'complete' for p in pairs):
        return 'inconclusive'
    if not all(p['63A']['eligible'] and p['63A']['native']['status'] == 'pass' and p['63B']['eligible'] for p in pairs):
        return 'inconclusive'
    if all(p['63B']['native']['status'] == 'pass' and p['63B']['direction_ok'] for p in pairs):
        return 'confirmed'
    if all(p['63B']['native']['status'] == 'fail' for p in pairs):
        return 'refuted'
    return 'inconclusive'


def main():
    commit = sys.argv[2]
    script = Path(__file__).resolve()
    path = script.relative_to(ROOT).as_posix()
    if len(commit) != 40 or blob(commit, path) != script.read_bytes().replace(b'\r\n', b'\n'):
        raise ValueError('use the full frozen variant commit with an exact replay blob')
    prior = prior_module()
    scope_hashes = {}
    for p in ('docs/trainer/ledger.json', 'docs/trainer/etalons.json', 'jobs/POLY63-B/REPORT.md'):
        raw = blob(prior.BASE, p)
        if raw != (ROOT / p).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError(f'scope/ledger provenance mismatch: {p}')
        scope_hashes[p] = hashlib.sha256(raw).hexdigest()
    reference = blob(R107, 'docs/research/trainer_railing_r107/receipt_r2.json')
    driver = pinned_module('r105', prior.PREVIOUS, prior.DRIVER)
    manifest = blob(prior.PREVIOUS, prior.MANIFEST)
    vars(driver).update(CONTRACT=SimpleNamespace(read_text=lambda *, encoding: manifest.decode(encoding)),
                        tower=lambda *args: probe(driver, prior, json.loads(reference)['summary'], *args), decide=verdict)
    driver.main()
    receipt = Path(sys.argv[1]) / 'receipt.json'
    report = json.loads(receipt.read_text(encoding='utf-8'))
    summary = {}
    for t in prior.SCOPE:
        pairs = [p[t] for p in report['results'] if 'native' in p.get(t, {})]
        if len(pairs) == 3:
            a, b = ([p[k]['max_corner_dev_m'] for p in pairs] for k in ('baseline_native', 'native'))
            gains = [x-y for x, y in zip(a,b)]
            summary[t] = {'S107_median_m': statistics.median(a), 'S108_median_m': statistics.median(b),
                          'paired_gain_range_m': [min(gains), max(gains)]}
    report.update(summary=summary, variant_commit=commit, scope_sha256=scope_hashes, r107_commit=R107,
                  r105_commit=prior.PREVIOUS, r107_reference_sha256=hashlib.sha256(reference).hexdigest(),
                  r105_manifest_sha256=hashlib.sha256(manifest).hexdigest())
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: report[k] for k in ('status', 'hypothesis', 'wall_s', 'summary')}))


if __name__ == '__main__':
    main()
