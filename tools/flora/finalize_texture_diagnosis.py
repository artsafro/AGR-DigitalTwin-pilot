"""Finalize #369 repair recommendations, never asset acceptance.

Pattern: n/a | new-case: control-calibrated source-defect/limitation routing.
User decision: t_49156f66, 2026-10-20 20:27. Keep raw failures; calibrate on
valid controls instead of requiring all authored originals to pass D155.
Consumes frozen offline evidence only. Does not render, edit maps or run DCC.
"""
import argparse
from collections import Counter
import hashlib
import html
import json
import math
from pathlib import Path

from compare_sprite_diagnostics import npm_star_check, SOURCE_TAGS
from diagnose_texture import guard_outputs

CONTROLS = ('Tilia_cordata_VPM', 'Crataegus_mollis_VPM', 'Spiraea_japonica_NPM')
CLEAN_STATUSES = (None, 'pass', 'passed')
ROLES = {'foliage', 'trunk', 'star_plane'}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def clean(island):
    return (island.get('pass') is True and island.get('role') in ROLES
            and island.get('status') in CLEAN_STATUSES
            and island.get('policy_applicable') is not False and finite(island.get('score')))


def control_clean(island):
    """Independently recheck the measured control numbers, not just a pass flag.

    These controls fit the original bbox/island NPM target; this does not certify
    every margin case of the later NPM clarification.
    """
    if not clean(island):
        return False
    score = island['score']
    if island['role'] == 'trunk':
        return island.get('metric') == 'bark_containment' and .95 <= score <= 1
    if island['role'] == 'star_plane':
        clipped = island.get('clipped_opaque_px_tolerance_1')
        return .8 <= score <= .95 and type(clipped) is int and clipped == 0
    neighbours = island.get('neighbour_opaque_px')
    return .8 <= score <= 1 and (score <= .95 or type(neighbours) is int and neighbours == 0)


def source_issue(island):
    limitation = (not finite(island.get('score')) or island.get('role') not in ROLES
                  or island.get('status') not in CLEAN_STATUSES or island.get('policy_applicable') is False)
    result = {key: island.get(key) for key in ('island', 'faces', 'role', 'status', 'error',
              'policy_applicable', 'sprite_bbox', 'clipped_opaque_px_tolerance_1', 'neighbour_opaque_px')}
    result.update(kind='measurement_limitation' if limitation else 'source_geometric_defect',
                  score=island['score'] if finite(island.get('score')) else None,
                  raw_pass=island.get('pass'))
    return result


def validate_rows(rows):
    if not isinstance(rows, list) or len(rows) != 201:
        raise ValueError('201 complete measured records required')
    by = {}
    for row in rows:
        name, tag = row.get('object'), row.get('tag')
        if not isinstance(name, str) or tag not in (*SOURCE_TAGS, 'ours', 'light') or (name, tag) in by:
            raise ValueError(f'duplicate or unsupported record {name}/{tag}')
        if row.get('profile') not in ('NPM', 'VPM') or not name.endswith('_'+row['profile']):
            raise ValueError(f'unsupported profile {name}')
        triangles = row.get('triangles')
        islands = row.get('islands')
        if type(triangles) is not int or triangles <= 0 or not isinstance(islands, list) or not islands:
            raise ValueError(f'empty geometry ledger {name}/{tag}')
        faces = [f for island in islands for f in island.get('faces', [])]
        if any(type(f) is not int for f in faces) or sorted(faces) != list(range(triangles)):
            raise ValueError(f'inexact face ledger {name}/{tag}')
        ids = [i.get('island') for i in islands]
        if any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
            raise ValueError(f'duplicate island {name}/{tag}')
        by[name, tag] = row
    source = [r for r in rows if r['tag'] in SOURCE_TAGS]
    source_names = {r['object'] for r in source}
    if (len(source) != 99 or len(source_names) != 99
            or {n for n, t in by if t == 'ours'} != source_names
            or sum(t == 'light' for n, t in by) != 3
            or not {n for n, t in by if t == 'light'} <= source_names):
        raise ValueError('99 unique source/library pairs and 3 matching light records required')
    return by, source


def finalize(rows, source_records):
    """Issue repair *recommendations*, retaining all raw defects and limitations."""
    by, source = validate_rows(rows)
    source_by = {r['object']: r for r in source}
    controls = []
    for name in CONTROLS:
        row = source_by.get(name)
        if row is None or not all(control_clean(i) for i in row['islands']):
            raise ValueError(f'control calibration failed: {name}')
        controls.append({'object': name, 'charts': len(row['islands']), 'passed': True})
    routes = []
    for row in sorted(source, key=lambda r: r['object']):
        name = row['object']
        issues = [source_issue(i) for i in row['islands'] if not clean(i)]
        star = npm_star_check(source_records.get(name)) if row['profile'] == 'NPM' else None
        if row['profile'] == 'NPM':
            route = ('remap_star_to_whole_plant_image' if star['is_star']
                     else 'rebuild_whole_plant_star_and_uv')
        elif any(i['kind'] == 'measurement_limitation' for i in issues):
            route = 'resolve_source_atlas_region_then_restore_or_bake'
        elif issues:
            route = 'repair_source_uv_then_restore_or_bake_atlas'
        else:
            route = 'restore_or_bake_original_atlas'
        routes.append({'object': name, 'profile': row['profile'], 'source_tag': row['tag'],
                       'route': route, 'source_issues': issues, 'star': star,
                       'source_raw_clean': not issues,
                       'source_chart_count': len(row['islands']),
                       'library_failed_charts': sum(not clean(i) for i in by[name, 'ours']['islands']),
                       'light_failed_charts': (sum(not clean(i) for i in by[name, 'light']['islands'])
                                               if (name, 'light') in by else None),
                       'requires_visual_validation_after_repair': True})
    limited = sum(bool(r['source_issues']) for r in routes)
    return {'decision': 'Artem, t_49156f66, 2026-10-20 20:27',
            'control_calibration': 'passed', 'controls': controls,
            'raw_all_originals_gate': 'failed' if limited else 'not_failed',
            'source_limited_objects': limited, 'route_count': len(routes),
            'route_counts': dict(Counter(r['route'] for r in routes)),
            'asset_accepted': False, 'semantic_masks_certified': False,
            'scope': 'final diagnostic repair recommendations, not validated fixes or asset passes',
            'routes': routes}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'duplicate JSON key {key}')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def run(metrics_path, inventory_path, provenance_path, output):
    inputs = [Path(p) for p in (metrics_path, inventory_path, provenance_path)]
    output = Path(output)
    guard_outputs(inputs, [output, output/'routes.json', output/'index.html'])
    snapshots = [p.read_bytes() for p in inputs]
    metrics, inventory, provenance = [read_json(data) for data in snapshots]
    if (sha(snapshots[0]) != provenance['outputs']['metrics.json']
            or sha(snapshots[1]) != provenance['inventory_sha256']):
        raise ValueError('stale or changed metrics/inventory provenance')
    from compare_sprite_diagnostics import split_records
    source, ours, light = split_records(inventory)
    records = {key: record for _, key, record in source}
    rows = metrics['records']
    by, _ = validate_rows(rows)
    for tag, name, record in [*source, *(('ours', n, r) for n, r in ours),
                               *(('light', n, r) for n, r in light)]:
        if by[name, tag]['triangles'] != record['triangles']:
            raise ValueError(f'stale geometry ledger {name}/{tag}')
    result = finalize(rows, records)
    result['provenance'] = {str(p): sha(data) for p, data in zip(inputs, snapshots)}
    # Reject concurrent input rewrites before the first output. This is offline evidence,
    # not a transaction/locking protocol for mutable production assets.
    if any(p.read_bytes() != data for p, data in zip(inputs, snapshots)):
        raise ValueError('input changed during finalization')
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    table = ''.join('<tr><td>'+html.escape(r['object'])+'</td><td>'+html.escape(r['route'])+
                    '</td><td>'+str(len(r['source_issues']))+'</td></tr>' for r in result['routes'])
    page = ('<!doctype html><meta charset="utf-8"><h1>#369: диагностические маршруты</h1>'
            '<p>Контроли пройдены; исходные дефекты сохранены. Ассеты НЕ приняты и не исправлены.</p>'
            '<p><a href="../geometry-diagnostics-v005/index.html">Шесть просмотренных листов, UV и маски</a> '
            '<a href="routes.json">Все маршруты и исходные ограничения (JSON)</a></p>'
            '<table><tr><th>Object</th><th>Repair recommendation</th><th>Source issues</th></tr>'+table+'</table>')
    output.mkdir(parents=True, exist_ok=False)
    for name, content in (('routes.json', payload), ('index.html', page)):
        with (output/name).open('x', encoding='utf-8') as stream:
            stream.write(content)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('metrics', 'inventory', 'provenance', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    result = run(args.metrics, args.inventory, args.provenance, args.output)
    print(json.dumps({key: result[key] for key in ('route_count', 'route_counts', 'source_limited_objects',
                                                 'control_calibration', 'asset_accepted')}))


if __name__ == '__main__':
    main()
