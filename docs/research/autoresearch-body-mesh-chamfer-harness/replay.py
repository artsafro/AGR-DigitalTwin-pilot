"""Replay standing #19 with one offline chamfer candidate (OBSERVE only)."""
import argparse
import hashlib
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
REV = '987f418a237e5931d695c278bcca177c789de3da'
HARNESS = 'docs/research/autoresearch-body-mesh-r3-localize-harness/localize.py'
SHA = 'e84c7bef192e1aa3f7a9a3295869d26a4d8e961bc6d976514e6f730340f160d7'


def exempt(normal_z, flat_cos, corners):
    return (abs(normal_z) >= flat_cos and len(corners) == 4
            and all(min(abs(angle - target) for target in (45.0, 90.0, 135.0)) <= 1.0
                    for angle in corners))


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'expected exactly one anchor: {old!r}')
    return text.replace(old, new, 1)


def witness():
    flat = math.cos(math.radians(1.0))
    expected = {
        'aligned_quad': (1.0, [45.5, 45.5, 134.5, 134.5], True),
        'inclusive_limits': (-flat, [44.0, 46.0, 134.0, 136.0], True),
        'beyond_limit': (1.0, [43.99, 46.01, 135.0, 135.0], False),
        'triangle': (1.0, [45.0, 45.0, 90.0], False),
        'degenerate_quad': (1.0, [45.0, 45.0, 90.0, 180.0], False),
        'vertical_quad': (0.0, [45.0, 45.0, 135.0, 135.0], False),
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
    print('chamfer policy witness:', checks, flush=True)
    if args.witness:
        return
    if args.cache is None or args.out is None or args.out.exists():
        parser.error('pass the cache and a new receipt path')
    raw = subprocess.check_output(['git', 'show', f'{REV}:{HARNESS}'], cwd=ROOT)
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError('prior harness SHA-256 mismatch')
    harness = raw.decode('utf-8').replace('R4', 'R5').replace('r4', 'r5')
    harness = replace_once(harness, 'if abs(normals[fi][2]) < flat_cos:',
                           'if not _AR20_EXEMPT(normals[fi][2], flat_cos, ang):')
    harness = replace_once(harness, "scope = {'_AR19_SINK':",
                           "scope = {'_AR20_EXEMPT': _AR20_EXEMPT, '_AR19_SINK':")
    harness = replace_once(harness, "    with out.open('x'",
                           "    receipt.update(_AR20_PROVENANCE)\n    with out.open('x'")
    provenance = {'prior_harness_revision': REV, 'prior_harness_sha256': SHA,
                  'replay_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'chamfer_policy_witness': checks, 'metric': 'worst accepted-minus-rejected margin'}
    scope = {'__file__': __file__, '__name__': 'ar20_replay', '_AR20_EXEMPT': exempt,
             '_AR20_PROVENANCE': provenance}
    exec(compile(harness, f'{REV}:{HARNESS}', 'exec'), scope)
    scope['main'](args.cache, args.out)


if __name__ == '__main__':
    main()
