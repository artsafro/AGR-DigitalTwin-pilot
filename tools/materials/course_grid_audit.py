"""new-case: source-bound closed corner-link audit before course-grid packing.

Reuse uvlayout_core geometry; never unwrap, cut, scale, or certify a delivery.
A closed disk fan of any valence with angle defect needs a seam or distortion.
For anisotropy k, each angle can change at most 2*asin((k-1)/(k+1)).
This necessary condition is not a complete feasibility or packing solver.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib

import json
import math
from pathlib import Path

from adapters.max.agr_tools.facadeatlas_core import frame
from adapters.max.agr_tools.uvlayout_core import tri_normal


def audit_corners(rows, *, anisotropy_limit):
    """Audit plain source-face rows; retain every face, never infer seam permission.

    Keys: object (str), face (0-based int), vertices (unique source indices),
    xyz (metres in corresponding order). Additional intake fields are retained
    by the caller. Analyse connected closed disk links, including reflex angles.
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
    for (obj, vi), faces in sorted(incident.items()):
        if len(faces) < 3:
            continue
        faces = sorted(faces, key=lambda r: r['face'])
        neighbors = []
        for r in faces:
            j = r['vertices'].index(vi)
            neighbors.append({r['vertices'][j-1], r['vertices'][(j+1) % len(r['vertices'])]})
        # A closed disk link is one connected cycle, regardless of valence.
        # Trihedral corners subdivided into 4+ polygons retain the same defect.
        radial_counts = defaultdict(int)
        for ns in neighbors:
            for n in ns:
                radial_counts[n] += 1
        if any(n != 2 for n in radial_counts.values()):
            continue
        adjacent = {i: {j for j in range(len(faces)) if j != i and neighbors[i] & neighbors[j]}
                    for i in range(len(faces))}
        if any(len(ns) != 2 for ns in adjacent.values()):
            continue
        visited, queue = {0}, [0]
        for i in queue:
            for j in adjacent[i] - visited:
                visited.add(j)
                queue.append(j)
        if len(visited) != len(faces):
            continue
        angle_budget = len(faces) * math.degrees(2 * math.asin((k - 1) / (k + 1)))
        angles, lengths = [], []
        for r in faces:
            j = r['vertices'].index(vi)
            p = r['xyz'][j]
            a = [x-y for x, y in zip(r['xyz'][j-1], p)]
            b = [x-y for x, y in zip(r['xyz'][(j+1) % len(r['xyz'])], p)]
            la, lb = math.hypot(*a), math.hypot(*b)
            angle = math.degrees(math.acos(max(-1, min(1, sum(x*y for x, y in zip(a,b))/(la*lb)))))
            fr = frame(r['xyz'])
            if fr is None:
                raise ValueError(f'{obj, r["face"]}: unsupported zero polygon normal')
            n = fr[2]
            cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
            if sum(x*y for x,y in zip(cross,n)) > 0:
                angle = 360-angle  # reflex polygon corner, not the smaller angle
            angles.append(angle)
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
            'limitations': ['closed disk links only; no open/nonmanifold fan certificate', 'not a course phase/panel mask/packing certificate',
                            'no seam exceptions have been approved by this tool']}


def audit_vertical_cycles(rows, *, repeat_m, texel_px_m, phase_tolerance_px=0.1):
    """Necessary phase-closure check of fixed-scale horizontal wall charts.

    Each complete shared vertical source edge constrains the two U offsets.
    Circulation on a closed loop must be an integer *full appearance* repeat.
    A spanning forest exposes fundamental cycles; it neither chooses seams nor
    solves variable-scale charts. No welding, geometry edits, UV writes or pass
    certificates. Vertex-only and partial-edge contacts are not analysed.
    """
    for name, value in [('repeat_m', repeat_m), ('texel_px_m', texel_px_m),
                        ('phase_tolerance_px', phase_tolerance_px)]:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be finite and positive')
    # Reuse the source-face validator; corner permission is deliberately not inferred.
    audit_corners(rows, anisotropy_limit=1.02)
    by_key = {(r['object'], r['face']): r for r in rows}
    tangents, edges = {}, defaultdict(list)
    for key, r in sorted(by_key.items()):
        n, _area = tri_normal(r['xyz'], [0, 1, 2])
        if abs(n[2]) > 0.01:
            continue
        h = math.hypot(n[0], n[1])
        tangents[key] = (-n[1]/h, n[0]/h, 0.0)
        for j, p in enumerate(r['xyz']):
            k = (j+1) % len(r['xyz'])
            q = r['xyz'][k]
            if math.hypot(p[0]-q[0], p[1]-q[1]) > 1e-4 or abs(p[2]-q[2]) < 0.02:
                continue
            edge = (r['object'], tuple(sorted((r['vertices'][j], r['vertices'][k]))))
            midpoint = tuple((a+b)/2 for a,b in zip(p,q))
            edges[edge].append((key, midpoint))
    adj, constraints = defaultdict(list), []
    dot = lambda a,b: sum(x*y for x,y in zip(a,b))
    for edge, users in sorted(edges.items()):
        if len(users) > 2:
            raise ValueError(f'nonmanifold vertical source edge {edge}')
        if len(users) != 2:
            continue
        (a, p), (b, q) = users
        d = dot(p, tangents[a])-dot(q, tangents[b])
        adj[a].append((b,d,edge,p))
        adj[b].append((a,-d,edge,q))
        constraints.append((a,b,d,edge))
    offset, parent, tree_edges = {}, {}, set()
    for root in sorted(tangents):
        if root in offset:
            continue
        offset[root], parent[root] = 0.0, None
        queue = [root]
        for a in queue:
            for b,d,edge,_p in adj[a]:
                if b not in offset:
                    offset[b], parent[b] = offset[a]+d, a
                    tree_edges.add(edge)
                    queue.append(b)
    cycles = []
    for a,b,d,edge in constraints:
        if edge in tree_edges:
            continue
        chain_a, chain_b = [a], [b]
        while parent[chain_a[-1]] is not None:
            chain_a.append(parent[chain_a[-1]])
        while chain_b[-1] not in chain_a:
            chain_b.append(parent[chain_b[-1]])
        ancestor = chain_b[-1]
        chain = chain_a[:chain_a.index(ancestor)+1] + list(reversed(chain_b[:-1]))
        mids, seam_edges = [], []
        for j, f in enumerate(chain):
            neighbor = chain[(j+1) % len(chain)]
            candidates = [item for item in adj[f] if item[0] == neighbor]
            if len(candidates) != 1:
                raise ValueError(f'ambiguous source adjacency {f}, {neighbor}')
            _nb,_delta,e,p = candidates[0]
            mids.append(p)
            seam_edges.append({'object': e[0], 'vertices': list(e[1]),
                               'faces': [f[1], neighbor[1]], 'midpoint_m': list(p)})
        circulation = offset[a]+d-offset[b]
        repeats = round(circulation/repeat_m)
        residual = abs(circulation-repeats*repeat_m)*texel_px_m
        travel = sum(abs(dot(tuple(x-y for x,y in zip(mids[j], mids[j-1])), tangents[f]))
                     for j,f in enumerate(chain))
        cycles.append({'object': a[0], 'faces': [f[1] for f in chain], 'edges': seam_edges,
                       'circulation_m': circulation, 'travel_m': travel,
                       'nearest_repeat_count': repeats, 'wrapped_residual_px': residual,
                       'requires_seam_at_frozen_scale': residual > phase_tolerance_px})
    return {'status': 'needs_seam_policy' if any(c['requires_seam_at_frozen_scale'] for c in cycles) else 'incomplete',
            'passed': False, 'repeat_m': repeat_m, 'texel_px_m': texel_px_m,
            'phase_tolerance_px': phase_tolerance_px, 'cycles': cycles,
            'input_faces': len(rows), 'vertical_faces': len(tangents),
            'unanalysed_faces': [list(k) for k in sorted(set(by_key)-set(tangents))],
            'shared_vertical_edges': len(constraints),
            'limitations': ['necessary condition only; fixed scale and horizontal outward U',
                            'source vertex indices only; no welding or partial-edge matching',
                            'complete vertical edges only; nonvertical faces not analysed',
                            'no bitmap symmetry inference, seam authorization or tile capacity verdict']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='source face readback JSON array, metres')
    parser.add_argument('report', type=Path, help='new report path (never overwritten)')
    parser.add_argument('--material-id', type=int, required=True)
    parser.add_argument('--anisotropy-limit', type=float, default=1.02)
    parser.add_argument('--repeat-m', type=float, help='also audit vertical rings at this full appearance repeat')
    parser.add_argument('--texel-px-m', type=float, default=512.0)
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
        if args.repeat_m is not None:
            report['vertical_cycles'] = audit_vertical_cycles(
                target, repeat_m=args.repeat_m, texel_px_m=args.texel_px_m)
            if report['vertical_cycles']['status'] == 'needs_seam_policy':
                report['status'] = 'needs_seam_policy'
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
