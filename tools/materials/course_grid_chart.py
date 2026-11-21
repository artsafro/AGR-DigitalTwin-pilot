"""new-case: explicit source-edge, fixed-scale course-grid chart adapter.

Reuse uvlayout_core normals and facadeatlas_core frames. Return metre charts and
complete source-edge diagnostics, not packed UVs or a delivery certificate.
No geometry edits, inferred seam permissions, vertex correction or scale search.
"""
from __future__ import annotations

from collections import defaultdict
import math

from adapters.max.agr_tools.facadeatlas_core import frame
from adapters.max.agr_tools.uvlayout_core import tri_normal
from tools.materials.course_grid_audit import audit_corners


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')


def build_chart(rows, *, seam_edges, repeat_m, texel_px_m, z0_m, tolerance_px=0.1):
    """Project each planar face rigidly, propagate translation at complete edges.

    `seam_edges` is an explicit list of {object, vertices:[a,b], faces:[a,b],
    mode:horizontal_phase|all_phase}. horizontal_phase preserves vertical courses;
    all_phase is only for caller-authorized thin returns. Indices are source IDs.
    Every other shared edge is measured at both endpoints; conflicts are reported,
    never silently converted into seams. Partial/vertex contacts need further QA.
    """
    for name, value in [('repeat_m', repeat_m), ('texel_px_m', texel_px_m), ('tolerance_px', tolerance_px)]:
        _positive(value, name)
    if isinstance(z0_m, bool) or not isinstance(z0_m, (int, float)) or not math.isfinite(z0_m):
        raise ValueError('z0_m must be finite')
    audit_corners(rows, anisotropy_limit=1.02)
    if not isinstance(seam_edges, list):
        raise ValueError('seam_edges must be an explicit list')
    by_key = {(r['object'], r['face']): r for r in rows}
    raw, edge_users = {}, defaultdict(list)
    for key, r in sorted(by_key.items()):
        n, _ = tri_normal(r['xyz'], [0, 1, 2])
        h = math.hypot(n[0], n[1])
        if h > 0.01:
            t = (-n[1]/h, n[0]/h, 0.0)
            v = (-n[2]*t[1], n[2]*t[0], h)
        else:
            t, _v, n = frame(r['xyz'])
            v = (n[1]*t[2]-n[2]*t[1], n[2]*t[0]-n[0]*t[2], n[0]*t[1]-n[1]*t[0])
        raw[key] = [[_dot(p, t), _dot((p[0], p[1], p[2]-z0_m), v)] for p in r['xyz']]
        for j, a in enumerate(r['vertices']):
            b = r['vertices'][(j+1) % len(r['vertices'])]
            edge_users[(key[0], tuple(sorted((a, b))))].append(key)
    if any(len(users) > 2 for users in edge_users.values()):
        e = next(e for e, users in edge_users.items() if len(users) > 2)
        raise ValueError(f'nonmanifold source edge {e}')
    seams = {}
    for s in seam_edges:
        if not isinstance(s, dict) or set(s) != {'object', 'vertices', 'faces', 'mode'}:
            raise ValueError(f'unsupported seam entry {s!r}')
        obj, ids, fs, mode = s['object'], s['vertices'], s['faces'], s['mode']
        if not isinstance(obj, str) or not obj or any(
            not isinstance(xs, list) or len(xs) != 2 or len(set(xs)) != 2 or
            any(type(x) is not int or x < 0 for x in xs) for xs in [ids, fs]
        ) or mode not in ['horizontal_phase', 'all_phase']:
            raise ValueError(f'invalid seam entry {s!r}')
        edge = (obj, tuple(sorted(ids)))
        if edge in seams:
            raise ValueError(f'duplicate seam {edge}')
        if set(edge_users.get(edge, [])) != {(obj, f) for f in fs}:
            raise ValueError(f'unmapped seam edge/faces {s!r}')
        seams[edge] = s
    adj = defaultdict(list)
    for edge, users in sorted(edge_users.items()):
        if len(users) != 2 or edge in seams:
            continue
        a, b = users
        vi = edge[1][0]
        ia, ib = by_key[a]['vertices'].index(vi), by_key[b]['vertices'].index(vi)
        delta = [raw[a][ia][k]-raw[b][ib][k] for k in range(2)]
        adj[a].append((b, delta))
        adj[b].append((a, [-d for d in delta]))
    offsets, component = {}, {}
    for root in sorted(by_key):
        if root in offsets:
            continue
        # Common global metre anchor; do not snap vertices to raster or face edges.
        offsets[root] = [0.0, 0.0]
        queue = [root]
        for a in queue:
            component[a] = list(root)
            for b, delta in adj[a]:
                if b not in offsets:
                    offsets[b] = [offsets[a][k]+delta[k] for k in range(2)]
                    queue.append(b)
    chart = {key: [[p[k]+offsets[key][k] for k in range(2)] for p in points]
             for key, points in raw.items()}
    samples, breaks = [], []
    for edge, users in sorted(edge_users.items()):
        if len(users) != 2:
            continue
        a, b = users
        diffs = []
        for vi in edge[1]:
            pa = chart[a][by_key[a]['vertices'].index(vi)]
            pb = chart[b][by_key[b]['vertices'].index(vi)]
            diffs.append([abs((pa[k]-pb[k]+repeat_m/2) % repeat_m-repeat_m/2)*texel_px_m for k in range(2)])
        u, v = [max(p[k] for p in diffs) for k in range(2)]
        record = {'object': edge[0], 'vertices': list(edge[1]), 'faces': [a[1], b[1]],
                  'horizontal_residual_px': u, 'vertical_residual_px': v}
        if edge in seams:
            record['mode'] = seams[edge]['mode']
            breaks.append(record)
        else:
            samples.append(record)
    conflicts = [s for s in samples if max(s['horizontal_residual_px'], s['vertical_residual_px']) > tolerance_px]
    conflicts += [s for s in breaks if s['mode'] == 'horizontal_phase' and s['vertical_residual_px'] > tolerance_px]
    return {'status': 'chart_conflict' if conflicts else 'chart_constructed', 'passed': False,
            'faces': [{'object': k[0], 'face': k[1], 'chart_m': chart[k], 'component': component[k]}
                      for k in sorted(by_key)], 'dropped_faces': [],
            'seams': breaks, 'continuous_edges': samples, 'conflicts': conflicts,
            'max_continuous_residual_px': max((max(s['horizontal_residual_px'], s['vertical_residual_px']) for s in samples), default=0.0),
            'repeat_m': repeat_m, 'texel_px_m': texel_px_m, 'z0_m': z0_m,
            'limitations': ['complete source edges only; no partial-edge or vertex-only certificate',
                            'no panel masks, bitmap equivalence, packing or exported UV QA']}
