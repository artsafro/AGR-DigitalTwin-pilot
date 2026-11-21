"""Replay standing #19 with one offline convex-quad candidate R6 (standing #21, OBSERVE only)."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
REV = '987f418a237e5931d695c278bcca177c789de3da'
HARNESS = 'docs/research/autoresearch-body-mesh-r3-localize-harness/localize.py'
SHA = 'e84c7bef192e1aa3f7a9a3295869d26a4d8e961bc6d976514e6f730340f160d7'
AR20 = 'e26aa9c1'
R20 = 'docs/research/autoresearch-body-mesh-chamfer-harness/r20.json'
R20_SHA = 'ab9ac3034ac2777aa05d7ddbe445ab706248f2596887ded7b78c90ff4009ca15'


def exempt(normal_z, flat_cos, corners):
    """R6: horizontal, non-degenerate, convex planar quad."""
    return (abs(normal_z) >= flat_cos and len(corners) == 4
            and all(1.0 < angle < 179.0 for angle in corners)
            and abs(math.fsum(corners) - 360.0) <= 1.0)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'expected exactly one anchor: {old!r}')
    return text.replace(old, new, 1)


def witness():
    flat = math.cos(math.radians(1.0))
    expected = {
        'chamfer_quad': (1.0, [45.5, 45.5, 134.5, 134.5], True),
        'v007_survivor': (1.0, [121.59, 56.65, 60.15, 121.6], True),
        'rectangle_down': (-1.0, [90.0, 90.0, 90.0, 90.0], True),
        'triangle': (1.0, [45.0, 45.0, 90.0], False),
        'corner_180': (1.0, [71.8, 180.0, 72.7, 35.5], False),
        'corner_0': (1.0, [0.0, 90.0, 90.0, 180.0], False),
        'concave_quad': (1.0, [30.0, 30.0, 60.0, 60.0], False),
        'vertical_quad': (0.0, [90.0, 90.0, 90.0, 90.0], False),
        'pentagon': (1.0, [108.0] * 5, False),
    }
    for name, (nz, angles, verdict) in expected.items():
        if exempt(nz, flat, angles) != verdict:
            raise AssertionError(name)
    return {name: verdict for name, (_, _, verdict) in expected.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--witness', action='store_true')
    parser.add_argument('cache', type=Path, nargs='?')
    parser.add_argument('out', type=Path, nargs='?')
    args = parser.parse_args()
    checks = witness()
    print('convex-quad policy witness:', checks, flush=True)
    if args.witness:
        return
    if args.cache is None or args.out is None or args.out.exists():
        parser.error('pass the cache and a new receipt path')
    raw = subprocess.check_output(['git', 'show', f'{REV}:{HARNESS}'], cwd=ROOT)
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError('prior harness SHA-256 mismatch')
    r20_raw = subprocess.check_output(['git', 'show', f'{AR20}:{R20}'], cwd=ROOT)
    if hashlib.sha256(r20_raw).hexdigest() != R20_SHA:
        raise ValueError('#20 receipt SHA-256 mismatch')
    harness = raw.decode('utf-8').replace('R4', 'R6').replace('r4', 'r6')
    harness = replace_once(harness, 'if abs(normals[fi][2]) < flat_cos:',
                           'if not _AR21_EXEMPT(normals[fi][2], flat_cos, ang):')
    harness = replace_once(harness, "scope = {'_AR19_SINK':",
                           "scope = {'_AR21_EXEMPT': _AR21_EXEMPT, '_AR19_SINK':")
    harness = replace_once(harness, "    with out.open('x'",
                           "    receipt.update(_AR21_PROVENANCE)\n    with out.open('x'")
    provenance = {'prior_harness_revision': REV, 'prior_harness_sha256': SHA,
                  'replay_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'r20_receipt_sha256': R20_SHA, 'harness_spliced_sha256': hashlib.sha256(harness.encode()).hexdigest(),
                  'convex_quad_policy_witness': checks, 'metric': 'worst accepted-minus-rejected margin'}
    scope = {'__file__': __file__, '__name__': 'ar21_replay', '_AR21_EXEMPT': exempt,
             '_AR21_PROVENANCE': provenance}
    exec(compile(harness, f'{REV}:{HARNESS}', 'exec'), scope)
    scope['main'](args.cache, args.out)
    # Clean check: R0 rows equal #20's R0 rows at both shifts.
    got = json.loads(args.out.read_text(encoding='utf-8'))['step_b']['runs']
    prior = json.loads(r20_raw)['step_b']['runs']
    same = all(got[s][k]['R0'] == prior[s][k]['R0'] for s in prior for k in prior[s])
    print('R0 rows equal #20 receipt:', same)
    if not same:
        raise ValueError('R0 rows differ from #20 receipt')


if __name__ == '__main__':
    main()
