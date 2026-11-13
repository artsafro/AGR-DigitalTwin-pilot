"""Measure explicitly mapped rectangular facade openings from a millimetre DXF (F16).

Pattern: new-case: source-bound facade drawing opening schedule, not inferred cutter geometry.

CLI: uv run python tools/methods/body/facade_openings_from_dxf.py sheet.dxf map.json NEW.json
Start with plan_from_dxf.py census; review the sheet before mapping handles. Example map::

    {"facades": {"north": {"origin_mm": [1000, 1000], "direction": 1, "datum_m": 0.5}},
     "openings": [{"id": "W1", "kind": "window", "facade": "north", "handles": ["2F"]}],
     "drop": {"30": "dimension annotation"}}

origin_mm is the drawing's facade horizontal/height datum; direction is +1 or -1 for
sheet horizontal orientation; datum_m is the confirmed project height at origin_mm.y.
Every model-space handle must occur exactly once, in an opening or a reasoned drop.
An opening is a closed axis-aligned rectangular outline: LINE segments and/or closed
LWPOLYLINEs with zero bulge, default extrusion and zero elevation. Unsupported shapes,
units, nonfinite/degenerate coordinates and incomplete/duplicated outlines are errors,
not guessed bounding boxes. Exact rectangle boundaries are required (no snap tolerance).
Width/height, sill/head and horizontal sheet positions are metres, with source handles.
No wall depth, facade-to-plan placement, library type or architectural approval is inferred.
Only the selected outline is measured, not completeness of the architect's opening design.

The JSON is status=measured, never a delivery pass. Inputs are hashed before/after reading;
JSON duplicate keys are rejected. Output is exclusively created: existing files, aliases
and stale successes are refused without replacement. No fixed temp/partial file is used.
Hashes detect persistent changes during extraction, not a concurrent edit restored between
checks; callers must retain sole ownership of inputs through extraction/publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import ezdxf
from shapely.geometry import LineString, box
from shapely.ops import unary_union


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'{label}: expected keys {sorted(expected)}, got {value!r}')


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label}: expected finite number')
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key {key!r}')
        result[key] = value
    return result


def _segments(entity):
    handle, kind = entity.dxf.handle, entity.dxftype()
    if tuple(entity.dxf.get('extrusion', (0, 0, 1))) != (0, 0, 1):
        raise ValueError(f'handle {handle}: unsupported extrusion')
    if kind == 'LINE':
        points = [tuple(entity.dxf.start), tuple(entity.dxf.end)]
    elif kind == 'LWPOLYLINE':
        if not entity.closed or entity.dxf.elevation != 0 or any(p[4] != 0 for p in entity):
            raise ValueError(f'handle {handle}: open, elevated or curved polyline')
        points = [(p[0], p[1], 0) for p in entity]
        if points:
            points.append(points[0])
    else:
        raise ValueError(f'handle {handle}: unsupported {kind}')
    segments = []
    for point in points:
        for coord in point:
            _number(coord, f'handle {handle} coordinate')
        if point[2] != 0:
            raise ValueError(f'handle {handle}: nonzero Z')
    for a, b in zip(points, points[1:]):
        if a == b or (a[0] != b[0] and a[1] != b[1]):
            raise ValueError(f'handle {handle}: zero or diagonal edge')
        segments.append(LineString([a[:2], b[:2]]))
    if not segments:
        raise ValueError(f'handle {handle}: empty outline')
    return segments


def extract(source: Path, mapping: Path) -> dict:
    """Return measured dimensions and full entity accounting; no filesystem writes."""
    source, mapping = Path(source), Path(mapping)
    if source.suffix.lower() != '.dxf':
        raise ValueError('source must be .dxf')
    raw_source, raw_map = source.read_bytes(), mapping.read_bytes()
    config = json.loads(raw_map, object_pairs_hook=_pairs)
    _keys(config, {'facades', 'openings', 'drop'}, 'mapping')
    if not isinstance(config['facades'], dict) or not config['facades']:
        raise ValueError('facades must be a nonempty object')
    for name, frame in config['facades'].items():
        if not name:
            raise ValueError('empty facade name')
        _keys(frame, {'origin_mm', 'direction', 'datum_m'}, f'facade {name}')
        origin = frame['origin_mm']
        if not isinstance(origin, list) or len(origin) != 2:
            raise ValueError(f'facade {name}: origin_mm must have two coordinates')
        for value in [*origin, frame['datum_m'], frame['direction']]:
            _number(value, f'facade {name}')
        if frame['direction'] not in (-1, 1):
            raise ValueError(f'facade {name}: direction must be -1 or 1')
    if not isinstance(config['openings'], list) or not config['openings']:
        raise ValueError('openings must be a nonempty list')
    if not isinstance(config['drop'], dict):
        raise ValueError('drop must be an object')
    doc = ezdxf.readfile(source)
    if doc.units != 4:
        raise ValueError(f'expected millimetres ($INSUNITS 4), got {doc.units}')
    entities = {e.dxf.handle: e for e in doc.modelspace()}
    if not entities or len(entities) != len(doc.modelspace()):
        raise ValueError('empty drawing or duplicate entity handles')
    assigned, ids, rows = {}, set(), []
    for opening in config['openings']:
        _keys(opening, {'id', 'kind', 'facade', 'handles'}, 'opening')
        oid = opening['id']
        if not isinstance(oid, str) or not oid.strip() or oid in ids:
            raise ValueError(f'empty or duplicate opening id {oid!r}')
        ids.add(oid)
        if opening['kind'] not in ('window', 'door'):
            raise ValueError(f'opening {oid}: unknown kind {opening["kind"]!r}')
        facade = opening['facade']
        if not isinstance(facade, str) or facade not in config['facades']:
            raise ValueError(f'opening {oid}: unknown facade {facade!r}')
        handles = opening['handles']
        if not isinstance(handles, list) or not handles:
            raise ValueError(f'opening {oid}: handles must be a nonempty list')
        segments = []
        for handle in handles:
            if not isinstance(handle, str) or handle not in entities or handle in assigned:
                raise ValueError(f'opening {oid}: missing or duplicate handle {handle!r}')
            assigned[handle] = {'status': 'used', 'opening': oid}
            segments.extend(_segments(entities[handle]))
        outline = unary_union(segments)
        left, bottom, right, top = outline.bounds
        boundary = box(left, bottom, right, top).boundary
        if left >= right or bottom >= top or not outline.equals(boundary) or sum(s.length for s in segments) != outline.length:
            raise ValueError(f'opening {oid}: incomplete, duplicate or nonrectangular outline')
        frame = config['facades'][facade]
        ox, oy = frame['origin_mm']
        horizontal = sorted((v - ox) * .001 * frame['direction'] for v in (left, right))
        sill, head = [(v - oy) * .001 + frame['datum_m'] for v in (bottom, top)]
        values = [*horizontal, sill, head, (right-left)*.001, (top-bottom)*.001]
        if not all(math.isfinite(v) for v in values) or not (horizontal[0] < horizontal[1] and sill < head):
            raise ValueError(f'opening {oid}: unrepresentable dimensions or datum')
        rows.append(dict(id=oid, kind=opening['kind'], facade=facade, source_handles=handles,
                         **dict(zip(('left_m', 'right_m', 'sill_m', 'head_m', 'width_m', 'height_m'), values))))
    for handle, reason in config['drop'].items():
        if handle not in entities or handle in assigned:
            raise ValueError(f'missing or duplicate drop handle {handle!r}')
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f'handle {handle}: drop requires reason')
        assigned[handle] = {'status': 'dropped', 'reason': reason}
    missing = set(entities) - set(assigned)
    if missing:
        raise ValueError(f'unmapped handles: {sorted(missing)}')
    if source.read_bytes() != raw_source or mapping.read_bytes() != raw_map:
        raise ValueError('input changed during extraction')
    return {'status': 'measured', 'units': 'm', 'openings': rows,
            'source': {'path': str(source.resolve()), 'sha256': hashlib.sha256(raw_source).hexdigest()},
            'mapping': {'path': str(mapping.resolve()), 'sha256': hashlib.sha256(raw_map).hexdigest()},
            'entities': [{'handle': h, 'type': e.dxftype(), 'layer': e.dxf.layer, **assigned[h]}
                         for h, e in entities.items()]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'mapping', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    try:
        # Exclusive creation also rejects hardlink/symlink aliases and racing output writers.
        if args.output.exists() or args.output.is_symlink() or args.output.resolve() in (args.source.resolve(), args.mapping.resolve()):
            raise ValueError('output exists or aliases input; nothing written')
        result = extract(args.source, args.mapping)
        text = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        print(f'measured: {len(result["openings"])} openings; architectural review required')
        return 0
    except (ValueError, OSError, ezdxf.DXFError, TypeError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
