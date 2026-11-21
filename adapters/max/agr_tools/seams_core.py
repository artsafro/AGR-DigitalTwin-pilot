"""new-case: shared stdlib source-traced course-grid page assembly (#1510).

Extracted from course_grid_cut. Plain JSON data only, no pymxs or image libraries.
Explicit support footprints/placements remain caller inputs, never inferred cuts.
This returns candidates, not bitmap, native, visual or delivery certificates.
"""
from __future__ import annotations

import math


def calculate(config):
    """Build a mesh chart/fold or replay explicit source-support pages.

    course_panel stores physical [panel index, course index], before packing.
    Panel steps are a procedural grid, NOT inferred source bevel/cut authority.
    """
    required = {'schema', 'mode', 'course_height_m', 'panel_step_m', 'repeat_m',
                'texel_px_m', 'tile_px', 'tile_budget', 'data'}
    if not isinstance(config, dict) or set(config) != required or config['schema'] != 'brick-seams/1':
        raise ValueError(f'unsupported/partial brick-seams config; expected keys {sorted(required)}')
    for name in ('course_height_m', 'panel_step_m', 'repeat_m'):
        value = config[name]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be finite and positive')
    # Whole-repeat folding must preserve both course and panel phase.
    for name in ('course_height_m', 'panel_step_m'):
        ratio = config['repeat_m']/config[name]
        if not math.isfinite(ratio) or ratio < 1 or abs(ratio-round(ratio)) > 1e-9:
            raise ValueError(f'repeat_m must contain whole {name} periods')
    common = {k: config[k] for k in ('texel_px_m', 'tile_px', 'tile_budget')}
    data = config['data']
    if config['mode'] == 'pages':
        if not isinstance(data, dict) or set(data) != {'partitions', 'brick_fold', 'placements'}:
            raise ValueError('unmapped/partial pages data')
        plan = assemble_support_pages(**data, **common)
    elif config['mode'] == 'mesh':
        from tools.materials.course_grid_chart import build_chart
        from tools.materials.course_grid_fit import fold_chart
        if not isinstance(data, dict) or set(data) != {'rows', 'seam_edges', 'z0_m', 'border_px', 'udim_tile'}:
            raise ValueError('unmapped/partial mesh data')
        if type(common['tile_budget']) is not int or not 1 <= common['tile_budget'] <= 10:
            raise ValueError('unsupported tile_budget')
        tile = data['udim_tile']
        if type(tile) is not int or not 1001 <= tile < 1001+common['tile_budget']:
            raise ValueError('udim_tile exceeds explicit tile_budget')
        chart = build_chart(data['rows'], seam_edges=data['seam_edges'], repeat_m=config['repeat_m'],
                            texel_px_m=common['texel_px_m'], z0_m=data['z0_m'])
        if chart['conflicts']:
            raise ValueError(f'chart conflicts: {chart["conflicts"][:3]}')
        folded = fold_chart(chart['faces'], repeat_m=config['repeat_m'], texel_px_m=common['texel_px_m'],
                            tile_px=common['tile_px'], border_px=data['border_px'])
        if folded['unplaced']:
            raise ValueError(f'fold overflow: {folded["unplaced"]}')
        indexed = {(r['object'], r['face']): r for r in data['rows']}
        faces = []
        for f, c in zip(folded['faces'], chart['faces']):
            row = indexed[(f['object'], f['face'])]
            faces.append(dict(f, chart_m=c['chart_m'], xyz=row['xyz'], vertices=row['vertices'], tile=tile,
                              uv=[[p[0]+(tile-1001), p[1]] for p in f['uv']]))
        vertical = 0
        for edge in chart['continuous_edges']+chart['seams']:
            row = indexed[(edge['object'], edge['faces'][0])]
            a, b = [row['xyz'][row['vertices'].index(v)] for v in edge['vertices']]
            if a[:2] == b[:2] and a[2] != b[2]:
                vertical += 1
        plan = dict(passed=False, status='mesh_course_grid_candidate', faces=faces,
                    source_faces=len(faces), dropped_faces=[], unplaced=[], **common,
                    vertical_edges=vertical, max_course_residual=max(
                        (e['vertical_residual_px']/common['texel_px_m']/config['course_height_m']
                         for e in chart['continuous_edges']+chart['seams']), default=0))
    else:
        raise ValueError(f'unsupported mode {config["mode"]!r}')
    for face in plan['faces']:
        face['course_panel'] = [[p[0]/config['panel_step_m'], p[1]/config['course_height_m']]
                                for p in face['chart_m']]
        if any(not math.isfinite(x) for p in face['course_panel'] for x in p):
            raise ValueError('nonfinite course/panel coordinates')
    plan['pattern'] = {k: config[k] for k in ('repeat_m', 'course_height_m', 'panel_step_m')}
    plan['limitations'] = ['candidate only: no bitmap bake, native readback or visual acceptance',
                           'source panel supports must be explicit; procedural grid is not cut permission']
    return plan


def _points(value, dim, name):
    if not isinstance(value, list) or len(value) < 3 or any(
        not isinstance(p, list) or len(p) != dim or any(type(x) not in (int, float)
        or not math.isfinite(x) for x in p) for p in value):
        raise ValueError(f'invalid {name}')
    return value


def _simple_polygon(points):
    # Relative shoelace avoids cancellation at building-scale world coordinates.
    q = [[p[k]-points[0][k] for k in (0, 1)] for p in points]
    area = abs(sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(q, q[1:]+q[:1])))/2
    if not math.isfinite(area) or area <= 1e-12:
        return False
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on(a, b, p):
        return cross(a, b, p) == 0 and all(min(a[k], b[k]) <= p[k] <= max(a[k], b[k]) for k in (0, 1))
    edges = list(zip(q, q[1:]+q[:1]))
    for i, (a, b) in enumerate(edges):
        if a == b:
            return False
        for j, (c, d) in enumerate(edges[:i]):
            if i-j == 1 or (i == len(edges)-1 and j == 0):
                continue
            if (any((on(a, b, c), on(a, b, d), on(c, d, a), on(c, d, b)))
                    or cross(a, b, c)*cross(a, b, d) < 0 and cross(c, d, a)*cross(c, d, b) < 0):
                return False
    return True


def assemble_support_pages(partitions, brick_fold, placements, *, texel_px_m, tile_px, tile_budget):
    """Apply explicit approved pages, preserving source identity, XYZ and scale."""
    if type(tile_budget) is not int or not 1 <= tile_budget <= 10:
        raise ValueError('unsupported tile_budget')
    if type(tile_px) is not int or tile_px not in (2048, 4096):
        raise ValueError('unsupported tile_px')
    if type(texel_px_m) not in (int, float) or not math.isfinite(texel_px_m) or not 512 <= texel_px_m <= 1706:
        raise ValueError('illegal texel_px_m')
    def key(value, length):
        if (not isinstance(value, list) or len(value) != length or not isinstance(value[0], str)
                or not value[0] or any(type(v) is not int or v < 0 for v in value[1:])):
            raise ValueError(f'invalid source key {value}')
        return tuple(value)
    def vector(value):
        if not isinstance(value, list) or len(value) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in value):
            raise ValueError('invalid translation')
        return value
    def add(a, b):
        return [a[k]+b[k] for k in (0, 1)]
    if not isinstance(partitions, list) or not partitions:
        raise ValueError('empty partitions')
    seen = set(); pieces = []; patches = set()
    for row in partitions:
        if not isinstance(row, dict) or not row.get('pieces') or row.get('dropped_faces') != []:
            raise ValueError('partial partition')
        source = key(row.get('source'), 2)
        if source in seen:
            raise ValueError(f'duplicate source {source}')
        seen.add(source)
        piece_keys = set()
        for piece in row['pieces']:
            if piece.get('source') != row['source'] or type(piece.get('joint')) is not bool:
                raise ValueError(f'unmapped piece {source}')
            xy = _points(piece.get('chart_m'), 2, 'chart_m')
            xyz = _points(piece.get('xyz'), 3, 'xyz')
            if len(xy) != len(xyz) or not _simple_polygon(xy):
                raise ValueError(f'invalid piece {source}')
            cycle = tuple(tuple(p) for p in xyz)
            identity = min(c[i:]+c[:i] for c in (cycle, cycle[::-1]) for i in range(len(c)))
            if identity in piece_keys:
                raise ValueError(f'duplicate piece {source}')
            piece_keys.add(identity)
            if piece['joint']:
                patch = key(piece.get('patch'), 3)
                if patch[:2] != source:
                    raise ValueError(f'unmapped patch {patch}')
                patches.add(patch)
            pieces.append(piece)
    if (not isinstance(brick_fold, dict) or brick_fold.get('unplaced') != []
            or brick_fold.get('dropped_faces') != [] or not isinstance(brick_fold.get('faces'), list)):
        raise ValueError('incomplete brick fold')
    brick = [p for p in pieces if not p['joint']]
    folded = {}
    for record in brick_fold['faces']:
        i = record.get('face')
        if type(i) is not int or not 0 <= i < len(brick) or record.get('object') != brick[i]['source'][0] or i in folded:
            raise ValueError(f'unmapped/duplicate fold key {record.get("object")}/{i}')
        border = brick_fold.get('border_px', 0)
        if type(border) not in (int, float) or not math.isfinite(border) or border < 0:
            raise ValueError('invalid fold border')
        folded[i] = [x+border/texel_px_m for x in vector(record.get('translation_m'))]
    if set(folded) != set(range(len(brick))):
        raise ValueError('missing brick fold key')
    if not isinstance(placements, list):
        raise ValueError('partial placements')
    members = {}; groups = set()
    for placement in placements:
        group = key(placement.get('key'), 3)
        tile = placement.get('tile')
        if type(tile) is not int or not 1001 <= tile < 1001+tile_budget:
            raise ValueError(f'tile {tile} exceeds approved budget {tile_budget}')
        if group in groups or not placement.get('members'):
            raise ValueError(f'duplicate/empty placement {group}')
        groups.add(group); shift = vector(placement.get('translation_m'))
        for member in placement['members']:
            patch = key(member.get('key'), 3)
            if patch not in patches or patch in members:
                raise ValueError(f'unmapped/duplicate member {patch}')
            members[patch] = (tile, add(shift, vector(member.get('fold_shift_m'))))
    if set(members) != patches:
        raise ValueError(f'missing support members {sorted(patches-set(members))}')
    faces = []; i = 0
    for piece in pieces:
        if piece['joint']:
            tile, shift = members[tuple(piece['patch'])]
        else:
            tile, shift = 1001, folded[i]; i += 1
        local = [[(p[k]+shift[k])*texel_px_m/tile_px for k in (0, 1)] for p in piece['chart_m']]
        if any(not math.isfinite(v) or v < 0 or v > 1 for p in local for v in p):
            raise ValueError(f'cross-tile piece {piece["source"]}')
        uv = [[p[0]+(tile-1001), p[1]] for p in local]
        faces.append(dict(piece, object=piece['source'][0], tile=tile, translation_m=shift, uv=uv))
    return dict(passed=False, status='source_support_pages_candidate', faces=faces,
                source_faces=len(seen), support_members=len(members), tile_budget=tile_budget,
                texel_px_m=texel_px_m, tile_px=tile_px, unplaced=[], dropped_faces=[])
