"""Vatutino Ground v015 `texel_ready` exception [D193]: freeze and check the enumerated offender list.

Pattern: n/a | new-case: enumerated, master-bound waiver list for one invariant on one delivery (#371).

D193 allows the v015 paired-fan candidate to ship with `texel_ready` (#346) offenders, but only the
faces on the frozen list and never more than the frozen per-slot counts. The list is bound to the
exact master file (SHA-256 of its bytes): a different master is an error, never a silent re-freeze.

    freeze <master.json> <profile> <out.json>   write the list (refuses an existing output / alias)
    check  <master.json> <profile> <frozen.json> exit 0 only when every live offender is listed

Every other `texel_ready` failure class stays a failure: an offender not on the list, a count above
the cap, an unknown slot, an empty or non-finite master, a slot with 0 faces, a profile mismatch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

from dt_ai.ops.inv_texel import PolyMesh, texel_report

DECISION = 'D193'
PROFILES = {'npm': 'NPM-Ground', 'vpm': 'VPM-Ground'}
_TAG = re.compile(r'^(?P<slot>[A-Za-z0-9_]+)#(?P<index>\d+): ')


class TexelExceptionError(ValueError):
    """Input that the exception cannot judge (fail closed, never a pass)."""


def _load_master(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    d = json.loads(raw)
    for key in ('verts', 'faces', 'mat', 'slots'):
        if key not in d:
            raise TexelExceptionError(f'master {path}: missing key {key!r}')
    if not d['faces']:
        raise TexelExceptionError(f'master {path}: no faces')
    if len(d['mat']) != len(d['faces']):
        raise TexelExceptionError(f'master {path}: mat/faces length mismatch')
    v = np.asarray(d['verts'], dtype=float)
    if v.ndim != 2 or v.shape[1] != 3 or not np.isfinite(v).all():
        raise TexelExceptionError(f'master {path}: vertices must be finite XYZ')
    for mi in d['mat']:
        if isinstance(mi, bool) or not isinstance(mi, int) or not 0 <= mi < len(d['slots']):
            raise TexelExceptionError(f'master {path}: material index {mi!r} names no slot')
    return raw, d


def offenders(path: Path, profile: str) -> tuple[str, dict[str, list[int]], dict[str, int]]:
    """Return ``(master_sha256, {slot: sorted face indices within the slot}, {slot: faces})``."""
    if profile not in PROFILES:
        raise TexelExceptionError(f'unsupported profile {profile!r}; expected one of {sorted(PROFILES)}')
    raw, d = _load_master(path)
    v = np.asarray(d['verts'], dtype=float)
    out: dict[str, list[int]] = {}
    counts: dict[str, int] = {}
    for slot in d['slots']:
        selected = [f for f, mi in zip(d['faces'], d['mat']) if d['slots'][mi] == slot]
        counts[slot] = len(selected)
        if not selected:
            raise TexelExceptionError(f'slot {slot!r} has 0 faces')
        rep = texel_report({slot: PolyMesh(v, tuple(map(tuple, selected)))}, PROFILES[profile])[slot]
        idx = []
        for text in rep.offenders:
            m = _TAG.match(text)
            if not m or m['slot'] != slot:
                raise TexelExceptionError(f'unparsed texel offender {text!r}')
            idx.append(int(m['index']))
        if len(set(idx)) != len(idx):
            raise TexelExceptionError(f'slot {slot!r}: duplicate offender rows')
        out[slot] = sorted(idx)
    return hashlib.sha256(raw).hexdigest(), out, counts


def freeze(master: Path, profile: str, out: Path) -> dict:
    if out.exists():
        raise TexelExceptionError(f'refuse to overwrite {out}')
    if out.resolve() == master.resolve():
        raise TexelExceptionError('output path resolves to the master')
    sha, rows, counts = offenders(master, profile)
    record = {'decision': DECISION, 'invariant': 'texel_ready', 'profile': profile,
              'master_sha256': sha, 'scope': 'Vatutino Ground v015 only; listed faces only',
              'total': sum(map(len, rows.values())),
              'slots': {s: {'faces': counts[s], 'cap': len(i), 'offenders': i} for s, i in rows.items()}}
    out.write_text(json.dumps(record, indent=0, separators=(',', ':')) + '\n', encoding='utf-8')
    return record


def check(master: Path, profile: str, frozen_path: Path) -> dict:
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    if frozen.get('decision') != DECISION or frozen.get('invariant') != 'texel_ready':
        raise TexelExceptionError('frozen list is not a D193 texel_ready record')
    if frozen.get('profile') != profile:
        raise TexelExceptionError(f"frozen list is for {frozen.get('profile')!r}, not {profile!r}")
    sha, rows, _ = offenders(master, profile)
    if sha != frozen.get('master_sha256'):
        raise TexelExceptionError('master differs from the frozen master; a new list needs a new decision')
    unknown = sorted(set(rows) ^ set(frozen['slots']))
    if unknown:
        raise TexelExceptionError(f'slot set differs from the frozen list: {unknown}')
    unlisted, over_cap = {}, {}
    for slot, live in rows.items():
        allowed = frozen['slots'][slot]
        extra = sorted(set(live) - set(allowed['offenders']))
        if extra:
            unlisted[slot] = extra[:20]
        if len(live) > allowed['cap'] or allowed['cap'] != len(allowed['offenders']):
            over_cap[slot] = [len(live), allowed['cap']]
    total = sum(map(len, rows.values()))
    passed = not unlisted and not over_cap and total <= frozen['total']
    return {'decision': DECISION, 'profile': profile, 'passed': passed, 'offenders': total,
            'cap': frozen['total'], 'unlisted': unlisted, 'over_cap': over_cap,
            'per_slot': {s: len(i) for s, i in rows.items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument('action', choices=('freeze', 'check'))
    ap.add_argument('master', type=Path)
    ap.add_argument('profile')
    ap.add_argument('path', type=Path)
    a = ap.parse_args(argv)
    try:
        if a.action == 'freeze':
            r = freeze(a.master, a.profile, a.path)
            print(json.dumps({'frozen': r['total'], 'master_sha256': r['master_sha256']}))
            return 0
        r = check(a.master, a.profile, a.path)
        print(json.dumps(r))
        return 0 if r['passed'] else 1
    except (TexelExceptionError, OSError, json.JSONDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
