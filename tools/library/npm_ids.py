"""new-case: recover provisional NPM material IDs with the shared atlas segmenter.

IDs are layout labels, NOT approved library materials. Pixel boxes use top-left
origin; UVs use bottom-left origin. Ambiguous/straddling faces retain ID zero and
are reported, never assigned to a first/default cell. Synthetic fixtures in tests.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image
from shapely import STRtree, constrained_delaunay_triangles, get_coordinates
from shapely.geometry import Polygon, box, shape as geometry_shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from tools.library.maf_atlas_cells import colour_regions, segment


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


def _palette_shapes(rgb, bounds, tolerance):
    labels, swatches = colour_regions(rgb, bounds, tolerance=tolerance)
    x0, y0, _, _ = bounds
    for index, colour in enumerate(swatches, 1):
        mask = labels == index
        runs = []
        for y, row in enumerate(mask, y0):
            spans = np.flatnonzero(np.diff(np.r_[False, row, False]))
            runs.extend(box(x0 + lo, y, x0 + hi, y + 1) for lo, hi in spans.reshape(-1, 2))
        for shape in _polygons(unary_union(runs)):
            yield shape, colour


def _polygons(shape):
    if shape.is_empty:
        return
    if shape.geom_type == 'Polygon':
        yield shape
    elif hasattr(shape, 'geoms'):
        for child in shape.geoms:
            yield from _polygons(child)


def recover_regions(atlas_file, face_uvs, *, colour_tolerance=6, segmentation=None, cell_regions=None):
    """Return source-indexed UV triangle pieces or exact unresolved face indices.

    The facade segmenter retains its source UV evidence: supported cell-border
    crossers now get clipped, never centroid-assigned. Palette regions inside a
    mixed or majority-solid leaf may be nonrectangular or have holes. A partial
    intersection is not published when unclassified pixels cover source area.
    An automatic patterned label does not establish a material boundary;
    patterned pixels need an explicit layout to be assigned as one region.
    An explicit layout uses native top-left pixel coordinates, classifies cells
    as solid or patterned, and preserves internal texture motifs.
    """
    if type(colour_tolerance) is not int or not 0 < colour_tolerance < 128:
        raise ValueError('invalid RGB8 colour tolerance')
    if not isinstance(face_uvs, list) or not face_uvs:
        raise ValueError('no UV faces')
    with Image.open(atlas_file) as image:
        w, h = image.size
        rgb = np.asarray(image.convert('RGB'))
    faces = []
    for i, uv in enumerate(face_uvs):
        if not isinstance(uv, (list, tuple)) or len(uv) != 3 or any(
            not isinstance(p, (list, tuple)) or len(p) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in uv
        ):
            raise ValueError(f'face {i}: expected three finite UV pairs')
        poly = Polygon([(u * w, (1 - v) * h) for u, v in uv])
        if not poly.is_valid or poly.area <= 0:
            raise ValueError(f'face {i}: invalid UV triangle')
        faces.append(poly)
    opts = dict(segmentation or {})
    if cell_regions is not None:
        if opts:
            raise ValueError('cell layout and automatic segmentation are mutually exclusive')
        return _clip_cell_layout(faces, cell_regions, w, h)
    if {'profile', 'uv_bounds_px'} & opts.keys():
        raise ValueError('regions require internally measured facade UV bounds')
    atlas = segment(str(atlas_file), profile='facade', uv_bounds_px=[p.bounds for p in faces], **opts)
    return _clip_regions(rgb, faces, atlas, colour_tolerance)


def _clip_cell_layout(faces, regions, w, h):
    if not isinstance(regions, list) or not regions:
        raise ValueError('empty or invalid cell layout')
    shapes, table, keys = [], [], set()
    domain = box(0, 0, w, h)
    for i, row in enumerate(regions, 1):
        key = row.get('id') if isinstance(row, dict) else None
        if not isinstance(key, str) or not key.strip() or key in keys:
            raise ValueError(f'cell {i}: required unique cell key {key!r}')
        kind = row.get('kind')
        if kind not in ('solid', 'patterned'):
            raise ValueError(f'cell {key}: unmapped kind {kind!r}')
        try:
            geom = geometry_shape(row['geometry'])
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ValueError(f'cell {key}: invalid geometry') from exc
        if (geom.geom_type not in ('Polygon', 'MultiPolygon') or geom.is_empty or geom.has_z
                or not np.isfinite(get_coordinates(geom)).all() or not geom.is_valid
                or geom.area <= 0 or not domain.covers(geom)):
            raise ValueError(f'cell {key}: invalid or out-of-atlas polygon')
        keys.add(key)
        shapes.append(geom)
        table.append({'id': i, 'cell_key': key, 'kind': kind,
                      'bounds_px': list(geom.bounds), 'face_count': 0})
    tree = STRtree(shapes)
    for i, geom in enumerate(shapes):
        for j in tree.query(geom, predicate='intersects'):
            if j < i and geom.intersection(shapes[j]).area > 0:
                raise ValueError(f"cell {table[i]['cell_key']}: overlaps cell {table[j]['cell_key']}")
    pieces, residual = _clip_faces(faces, shapes, table, w, h, tree)
    return {'status': 'manual_required' if residual else 'ok', 'pieces': pieces,
            'residual': residual, 'table': table, 'atlas_size_px': [w, h], 'colour_tolerance': None}


def _clip_regions(rgb, faces, atlas, colour_tolerance):
    """Internal seam also used to replay hash-bound segmenter evidence offline."""
    w, h = atlas['size']
    shapes, table, cells, patterned = [], [], [], []
    for cell_id, cell in enumerate(atlas['cells'], 1):
        x, y, cw, ch = (cell[k] for k in ('x', 'y', 'w', 'h'))
        bounds = [x, y, x + cw, y + ch]
        kind = cell['kind']
        # The automatic patterned label cannot distinguish a texture motif from
        # a separate finish. Leave it unclassified rather than trust its box.
        if kind == 'patterned':
            patterned.append(box(*bounds))
        # Even a majority-solid leaf still needs native palette evidence.
        regions = _palette_shapes(rgb, bounds, colour_tolerance) if kind in ('mixed', 'solid') else ()
        covered = 0.
        for shape, colour in regions:
            shapes.append(shape)
            table.append({'id': len(shapes), 'cell': cell_id, 'kind': 'solid',
                          'color': colour, 'bounds_px': list(shape.bounds), 'face_count': 0})
            covered += shape.area
        cells.append({'cell': cell_id, 'bounds_px': bounds, 'kind': kind,
                      'unclassified_px2': cw * ch - covered})
    pieces, residual = _clip_faces(faces, shapes, table, w, h, STRtree(shapes),
                                   unresolved=STRtree(patterned) if patterned else None)
    return {'status': 'manual_required' if residual else 'ok', 'pieces': pieces,
            'residual': residual, 'table': table, 'cells': cells, 'atlas_size_px': [w, h],
            'colour_tolerance': colour_tolerance}


def _clip_faces(faces, shapes, table, w, h, tree, *, unresolved=None):
    pieces, residual = [], []
    for i, face in enumerate(faces):
        # A two-dimensional interior intersection is missing classification,
        # not overlay roundoff. Point and edge contact alone are harmless.
        if unresolved is not None and any(
            face.relate_pattern(unresolved.geometries[j], '2********')
            for j in unresolved.query(face)
        ):
            pieces.append([])
            residual.append(i)
            continue
        overlaps = []
        for j in sorted(tree.query(face, predicate='intersects')):
            shape = shapes[j]
            if shape.covers(face):
                overlaps = [(j, face)]
                break
            overlaps.extend((j, p) for p in _polygons(shape.intersection(face)) if p.area > 0)
        # GEOS overlay roundoff only, relative to the individual source face.
        if not overlaps or abs(math.fsum(p.area for _, p in overlaps) - face.area) > face.area * 1e-8:
            pieces.append([])
            residual.append(i)
            continue
        result = []
        for j, part in overlaps:
            triangles = ([part] if len(part.exterior.coords) == 4 and not part.interiors
                         else constrained_delaunay_triangles(part).geoms)
            if not triangles or abs(math.fsum(t.area for t in triangles) - part.area) > part.area * 1e-8:
                raise ValueError(f'face {i}: triangulation did not cover colour region {j + 1}')
            table[j]['face_count'] += 1
            for tri in triangles:
                ring = orient(tri, sign=1 if face.exterior.is_ccw else -1).exterior.coords
                result.append({'id': int(j + 1), 'uv': [[x / w, 1 - y / h] for x, y in list(ring)[:-1]]})
        pieces.append(result)
    return pieces, residual
