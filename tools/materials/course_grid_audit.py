"""new-case: source-bound trihedral corner audit before course-grid packing.

Reuse uvlayout_core geometry; never unwrap, cut, scale, or certify a delivery.
A closed three-face fan with angle defect needs a chart seam or distortion.
For anisotropy k, each angle can change at most 2*asin((k-1)/(k+1)).
This necessary condition is not a complete feasibility or packing solver.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path

from adapters.max.agr_tools.uvlayout_core import tri_normal


def audit_corners(rows, *, anisotropy_limit):
    """Audit plain source-face rows; retain every face, never infer seam permission.

    Keys: object (str), face (0-based int), vertices (unique source indices),
    xyz (metres in corresponding order). Additional intake fields are retained
    by the caller. Only closed three-face fans are analysed by this first slice.
    """
    k = anisotropy_limit
    if isinstance(k, bool) or not isinstance(k, (float, int)) or not math.isfinite(k) or k < 1:
        raise ValueError('anisotropy_limit must be finite and >= 1')
    if not isinstance(rows, list) or not rows:
        raise ValueError('empty source-face rows')
    seen, coords, incident = set(), {}, defaultdict(list)
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get('object'), str) or not r['object']:
            raise ValueError('missing source object')
        obj, face = r['object'], r.get('face')
        if isinstance(face, bool) or not isinstance(face, int) or face < 0:
            raise ValueError(f'{obj}: invalid source face {face!r}')
        key = (obj, face)
        if key in seen:
            raise ValueError(f'duplicate source face {key}')
        seen.add(key)
        ids, xyz = r.get('vertices'), r.get('xyz')
        if not isinstance(ids, list) or not isinstance(xyz, list) or len(ids) < 3 or len(ids) != len(xyz):
            raise ValueError(f'{key}: partial vertices/xyz')
        if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in ids) or len(set(ids)) != len(ids):
            raise ValueError(f'{key}: invalid source vertex indices')
        for i, p in zip(ids, xyz):
            if not isinstance(p, list) or len(p) != 3 or any(
                isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in p
            ):
                raise ValueError(f'{key}: non-finite/partial xyz')
            vk = (obj, i)
            if vk in coords and p != coords[vk]:
                raise ValueError(f'{key}: inconsistent source vertex {i}')
            coords[vk] = p
            incident[vk].append(r)
        if tri_normal(xyz, [0, 1, 2])[0] is None:
            raise ValueError(f'{key}: degenerate face')
        for j, p in enumerate(xyz):
            if math.dist(p, xyz[(j+1) % len(xyz)]) == 0:
                raise ValueError(f'{key}: zero length edge')
    result = []
    angle_budget = 3 * math.degrees(2 * math.asin((k - 1) / (k + 1)))
    for (obj, vi), faces in sorted(incident.items()):
        if len(faces) != 3:
            continue
        faces = sorted(faces, key=lambda r: r['face'])
        neighbors = []
        for r in faces:
            j = r['vertices'].index(vi)
            neighbors.append({r['vertices'][j-1], r['vertices'][(j+1) % len(r['vertices'])]})
        if not all(len(a & b) == 1 for a, b in itertools.combinations(neighbors, 2)):
            continue
        if len(set.union(*neighbors)) != 3:
            continue
        angles, lengths = [], []
        for r in faces:
            j = r['vertices'].index(vi)
            p = r['xyz'][j]
            a = [x-y for x, y in zip(r['xyz'][j-1], p)]
            b = [x-y for x, y in zip(r['xyz'][(j+1) % len(r['xyz'])], p)]
            la, lb = math.hypot(*a), math.hypot(*b)
            angles.append(math.degrees(math.acos(max(-1, min(1, sum(x*y for x, y in zip(a,b))/(la*lb))))))
            lengths.extend([la, lb])
        defect = abs(360 - sum(angles))
        if defect > angle_budget:
            result.append({'object': obj, 'vertex': vi, 'faces': [r['face'] for r in faces],
                           'xyz': coords[(obj, vi)], 'angles_deg': angles, 'angle_sum_deg': sum(angles),
                           'defect_deg': defect, 'max_angle_change_deg': angle_budget,
                           'shortest_incident_edge_m': min(lengths)})
    return {'status': 'needs_seam_policy' if result else 'incomplete', 'passed': False,
            'face_count': len(rows), 'covered_faces': [[r['object'], r['face']] for r in rows],
            'dropped_faces': [], 'corners': result, 'anisotropy_limit': k,
            'limitations': ['three-face fans only', 'not a course phase/panel mask/packing certificate',
                            'no seam exceptions have been approved by this tool']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='source face readback JSON array, metres')
    parser.add_argument('report', type=Path, help='new report path (never overwritten)')
    parser.add_argument('--material-id', type=int, required=True)
    parser.add_argument('--anisotropy-limit', type=float, default=1.02)
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.report.resolve() or args.report.exists():
            raise ValueError('report aliases input or already exists')
        data = args.input.read_bytes()
        rows = json.loads(data)
        if not isinstance(rows, list) or not rows or args.material_id <= 0:
            raise ValueError('empty/unsupported source or material ID')
        if any(not isinstance(r, dict) or type(r.get('material_id')) is not int for r in rows):
            raise ValueError('unmapped material_id in source')
        target = [r for r in rows if r['material_id'] == args.material_id]
        report = audit_corners(target, anisotropy_limit=args.anisotropy_limit)
        report.update({'source_sha256': hashlib.sha256(data).hexdigest(), 'source': str(args.input.resolve()),
                       'material_id': args.material_id, 'input_faces': len(rows),
                       'protected_faces': [[r['object'], r['face']] for r in rows if r['material_id'] != args.material_id]})
        payload = json.dumps(report, indent=2, allow_nan=False) + '\n'
        if args.input.read_bytes() != data:
            raise ValueError('source changed during audit')
        # Exclusive write rejects hardlinks, junctions and a racing output creator;
        # no predictable temp file is created and no path is deleted.
        with args.report.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(payload)
        print(f"{report['status']}: {len(target)} faces; {len(report['corners'])} corner witnesses")
        return 1  # An audit never claims full pilot success, even without witnesses.
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'course-grid audit error: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
