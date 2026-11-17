"""new-case: recover provisional NPM material IDs with the shared atlas segmenter.

IDs are layout labels, NOT approved library materials. Pixel boxes use top-left
origin; UVs use bottom-left origin. Ambiguous/straddling faces retain ID zero and
are reported, never assigned to a first/default cell. Synthetic fixtures in tests.
"""
from __future__ import annotations

import math
from pathlib import Path

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from tools.library.maf_atlas_cells import segment


def recover(atlas_file, face_uvs, *, tolerance_px=.5, segmentation=None):
    """Return IDs, per-cell union coverage and complete manual face accounting."""
    if isinstance(tolerance_px, bool) or not math.isfinite(tolerance_px) or tolerance_px < 0:
        raise ValueError('tolerance_px must be finite and nonnegative')
    if not isinstance(face_uvs, list) or not face_uvs:
        raise ValueError('no UV faces')
    options = dict(segmentation or {})
    if options.get('profile') == 'facade':
        from PIL import Image
        with Image.open(atlas_file) as image:
            width, height = image.size
        # Bounds are conservative source-UV coverage witnesses; final polygons
        # still undergo exact containment and union accounting below.
        try:
            options['uv_bounds_px'] = [[min(p[0]*width for p in uv),
                min((1-p[1])*height for p in uv), max(p[0]*width for p in uv),
                max((1-p[1])*height for p in uv)] for uv in face_uvs]
        except (TypeError, IndexError, ValueError) as exc:
            raise ValueError('invalid facade UV faces') from exc
    atlas = segment(str(atlas_file), **options)
    w, h = atlas['size']
    table, shapes = [], []
    for i, c in enumerate(atlas['cells'], 1):
        bounds = [c['x'], c['y'], c['x'] + c['w'], c['y'] + c['h']]
        table.append({'id': i, 'cell_box_px': bounds, 'face_count': 0,
                      'atlas_file': str(Path(atlas_file).resolve()), 'kind': c['kind'],
                      'color': c['color']})
        shapes.append(box(*bounds))
    assigned, straddling, unassigned, ambiguous = [], [], [], []
    polygons = [[] for _ in table]
    for f, uv in enumerate(face_uvs):
        if not isinstance(uv, list) or len(uv) < 3 or any(
                not isinstance(p, (list, tuple)) or len(p) != 2 or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in p) for p in uv):
            raise ValueError(f'face {f}: missing/invalid/nonfinite UV')
        pts = [(u * w, (1-v) * h) for u, v in uv]
        poly = Polygon(pts)
        if not poly.is_valid or poly.area <= 0:
            raise ValueError(f'face {f}: degenerate/invalid UV polygon')
        # Match the arithmetic UV centroid, as used by npm2vpm_core._row_of.
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        hit = [i for i, row in enumerate(table) if row['kind'] != 'mixed' and
               row['cell_box_px'][0]-tolerance_px <= cx <= row['cell_box_px'][2]+tolerance_px and
               row['cell_box_px'][1]-tolerance_px <= cy <= row['cell_box_px'][3]+tolerance_px]
        assigned.append(0)
        if len(hit) > 1:
            ambiguous.append(f)
        elif not hit:
            unassigned.append(f)
        else:
            i = hit[0]
            x0, y0, x1, y1 = table[i]['cell_box_px']
            excess = max(0., max(max(x0-x, x-x1, y0-y, y-y1) for x, y in pts))
            # Equality at the tolerance cap is unresolved, not proof of containment.
            # Exact cell-border points (excess == 0) remain valid, including tol=0.
            if ((excess > 0 and excess >= tolerance_px) or
                    not shapes[i].buffer(tolerance_px, join_style=2).covers(poly)):
                straddling.append(f)
            else:
                assigned[-1] = i+1
                table[i]['face_count'] += 1
                polygons[i].append(poly)
    for row, ps, shape in zip(table, polygons, shapes):
        union = unary_union(ps)
        row['uv_union_area_px2'] = union.area
        row['uv_coverage_fraction'] = union.intersection(shape).area / shape.area
        row['uv_islands'] = len(union.geoms) if union.geom_type == 'MultiPolygon' else int(not union.is_empty)
    manual = [r['id'] for r in table if r['kind'] == 'mixed']
    return {'status': 'manual_required' if straddling or unassigned or ambiguous or manual else 'ok',
            'atlas_file': str(Path(atlas_file).resolve()), 'atlas_size_px': [w, h], 'table': table,
            'mat_ids': assigned, 'straddling': straddling, 'unassigned': unassigned,
            'ambiguous': ambiguous, 'non_rectangular_regions': manual,
            'empty_cells': [r['id'] for r in table if not r['face_count']], 'tolerance_px': tolerance_px}
