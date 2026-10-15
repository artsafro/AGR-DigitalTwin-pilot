"""New case: spatial labels on a real Max Flora display library (#189).

Standalone audit, not a delivery checker. Preserve ambiguous associations and raw
LP/HP tokens; inferred NPM/VPM candidates do not assert compliance. No binary I/O.
"""
import argparse
import json
import math
import re
import statistics
import time
from collections import Counter
from pathlib import Path

ROOT = Path('C:/x/t_366e8d9d')
SCENES = ['FLORA_Union_v1', 'FLORIO_2BT_2022']


def pair(label, meshes, plane, max_distance=math.inf, tolerance=1e-4):
    axes = {'xz': (0, 2), 'xy': (0, 1), 'y': (1,)}[plane]
    ranked = [(math.sqrt(sum((label['position'][i] - m['position'][i]) ** 2 for i in axes)), m['handle']) for m in meshes]
    if not ranked:
        return []
    best = min(d for d, _ in ranked)
    if best > max_distance:
        return []
    return sorted(h for d, h in ranked if d <= best + tolerance)


def dimensions(node, units_per_meter):
    return [(b - a) / units_per_meter for a, b in zip(*node['bbox'])]


def profiles(raw):
    token = raw.strip().upper()
    return {'LP': ['NPM'], 'HP': ['VPM'], 'LP -> HP': ['NPM', 'VPM']}.get(token, [])


def fresh_path(root, name):
    if not name or name in ('.', '..') or any(c in name for c in '/\\:'):
        raise ValueError('Flat output name required')
    target = Path(root) / name
    if target.exists():
        raise FileExistsError(target)
    return target


def role(o, project):
    if o['class'] in ('text', 'TextPlus'):
        return 'label'
    if not o.get('triangles'):
        return 'nonmesh'
    if project:
        return 'plant'
    if o['name'].startswith('Box'):
        return 'display_envelope_unverified'
    if o['class'] == 'Cylinder':
        return 'size_reference'
    if o['name'].startswith(('Капшо_', 'Кашпо_', 'MAF_')):
        return 'planter'
    return 'plant'


def text_role(text):
    s = text.strip()
    if re.fullmatch(r'\d+\s+Tris', s, re.I):
        return 'triangle_count'
    if profiles(s):
        return 'profile'
    if re.fullmatch(r'v\d+(\.\d+)?', s):
        return 'variant'
    if s in ('ППТ', '4K'):
        return 'note'
    return 'species'


def make_catalogue(source, project=False):
    objects = source['objects']
    assert len({o['name'] for o in objects}) == len(objects), 'Duplicate object names need explicit disambiguation'
    plants = [o for o in objects if role(o, project) == 'plant']
    labels = [dict(o, text=o.get('text', o.get('plain_text', ''))) for o in objects if role(o, project) == 'label']
    links = []
    # Library is a front-facing XZ grid. Project is a top XY display with labels
    # far to the left: Y-row distance, not Euclidean XY, preserves both profiles.
    for label in labels:
        if label['class'] == 'TextPlus' and label['name'] in ('Tree', 'Bush'):
            ids, status = [], 'category_heading'
        else:
            ids = pair(label, plants, 'y' if project else 'xz', max_distance=10 if project else 3)
            status = 'ambiguous' if len(ids) > 1 else ('paired' if ids else 'unpaired')
        links.append({'handle': label['handle'], 'name': label['name'], 'text': label['text'],
                      'class': label['class'], 'hidden': label['hidden'], 'position': label['position'],
                      'role': 'schedule_row' if project else text_role(label['text']),
                      'candidate_handles': ids, 'status': status})
    entries = []
    bitmap_users = Counter(filename for plant in plants for filename in {b['filename'] for b in (plant.get('material') or {}).get('bitmaps', [])})
    for index, plant in enumerate(sorted(plants, key=lambda o: o['name']), 1):
        assigned = [l for l in links if plant['handle'] in l['candidate_handles']]
        names = [l['text'].strip() for l in assigned if l['role'] in ('species', 'schedule_row')]
        raw_profile = [l['text'].strip() for l in assigned if l['role'] == 'profile']
        if project:
            raw_profile = ['LP' if '_low' in plant['name'] else 'HP']
        variants = [l['text'].strip() for l in assigned if l['role'] == 'variant']
        dims = dimensions(plant, source['unit_in_m'])
        labelled_tris = [int(re.search(r'\d+', l['text'])[0]) for l in assigned if l['role'] == 'triangle_count']
        heights = [int(h) / 100 for s in names for h in re.findall(r'\bH(\d+)\b', s)]
        # Project H tokens are retained as raw cm-convention candidates; multi-
        # species rows are not silently collapsed to a single species/height.
        name_h = re.search(r'_h(\d+)', plant['name'], re.I)
        nominal = int(name_h[1]) / 100 if name_h else None
        p = plant['position']
        if project:
            kind = 'tree' if any(t in plant['name'].lower() for t in ('klen', 'dub_', 'cheremuxa', 'elka')) else ('climber' if 'vinograd' in plant['name'] else 'bush')
        elif abs(p[1] - 10) < .25 and p[0] < -5:
            kind = 'tree'
        elif abs(p[1] - 10) < .25 and p[0] > 3:
            kind = 'bush'
        else:
            kind = 'unclassified'
        findings = []
        if not names:
            findings.append('no_species_label')
        if any(l['status'] == 'ambiguous' for l in assigned):
            findings.append('ambiguous_label_pair')
        if labelled_tris and plant['triangles'] not in labelled_tris:
            findings.append('labelled_triangle_mismatch')
        if not raw_profile:
            findings.append('profile_unlabelled')
        material = plant.get('material')
        if material and any(not b['exists'] for b in material['bitmaps']):
            findings.append('unresolved_bitmap_paths')
        if project and len(heights) > 1:
            findings.append('multiple_schedule_species_or_heights')
        if project and nominal is not None and heights and nominal not in heights:
            findings.append('node_height_token_not_in_schedule_row')
        if nominal is not None and abs(dims[2] / nominal - 1) > .2:
            findings.append('measured_height_outside_20pct_of_node_token')
        entry_id = ('project' if project else 'library') + f'-{index:03d}'
        entries.append({'id': entry_id, 'source_name': plant['name'], 'source_handle': plant['handle'],
                        'species_labels': names, 'type': kind, 'type_basis': 'display_heading_region' if not project else 'object_name',
                        'profile_raw': raw_profile, 'profile_candidates': sorted({p for r in raw_profile for p in profiles(r)}),
                        'variant_raw': variants, 'hidden': plant['hidden'], 'triangles': plant['triangles'],
                        'vertices': plant['vertices'], 'uv_vertices': plant['uv_vertices'],
                        'bbox_m': [[v / source['unit_in_m'] for v in corner] for corner in plant['bbox']],
                        'dimensions_m': dims, 'labelled_triangles': labelled_tris,
                        'labelled_dimensions': {'raw_height_tokens_m_if_cm': heights, 'height_from_node_name_m_if_cm': nominal,
                                               'unit_assumption': 'H values interpreted as cm, not a verified text unit',
                                               'height_deviation_from_name_mm': (dims[2] - nominal) * 1000 if nominal is not None else None,
                                               'library_dimension_text': None},
                        'material': material,
                        'atlas_use': {'bitmap_users_in_scene': {b['filename']: bitmap_users[b['filename']] for b in (material or {}).get('bitmaps', [])},
                                      'status': 'reference_sharing_only_uv_islands_and_texture_pixels_not_audited'},
                        'findings': findings,
                        'file': str(ROOT / 'assets-v001' / (entry_id + '.max')),
                        'preview': str(ROOT / 'assets-v001' / (entry_id + '.svg')),
                        'preview_kind': 'untextured_front_wireframe_not_appearance_approval',
                        'delivery_passed': False})
    return {'source': {k: v for k, v in source.items() if k != 'objects'}, 'counts': dict(Counter(role(o, project) for o in objects)),
            'labels': links, 'entries': entries,
            'excluded_nodes': [{'name': o['name'], 'class': o['class'], 'role': role(o, project), 'triangles': o.get('triangles')} for o in objects if role(o, project) not in ('label', 'plant')]}


def budgets(scenes):
    rows = []
    for kind in ['tree', 'bush', 'hedge', 'climber', 'unclassified']:
        for profile in ['NPM', 'VPM', 'unknown']:
            selected = [e for s in scenes for e in s['entries'] if e['type'] == kind and (profile in e['profile_candidates'] if profile != 'unknown' else not e['profile_candidates'])]
            values = sorted(e['triangles'] for e in selected)
            rows.append({'type': kind, 'profile': profile, 'n': len(values), 'min': min(values) if values else None,
                         'median': statistics.median(values) if values else None, 'max': max(values) if values else None,
                         'proposed_review_above': math.ceil(max(values) / 100) * 100 if values else None,
                         'status': 'observed_ceiling_review_only_not_regulatory_limit' if values else 'no_samples_no_budget'})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    scenes = []
    comparison = []
    for index, name in enumerate(SCENES):
        data = json.loads((ROOT / (name + '-detailed.json')).read_text(encoding='utf-8'))
        timings = []
        for _ in range(3):
            start = time.perf_counter()
            result = make_catalogue(data, project=bool(index))
            timings.append(time.perf_counter() - start)
        result['pairing_seconds'] = timings
        scenes.append(result)
        meshes = [o for o in data['objects'] if role(o, bool(index)) == 'plant']
        for plane in (['xy', 'xz'] if index == 0 else ['xy', 'y']):
            durations = []
            for _ in range(3):
                start = time.perf_counter()
                pairs = [pair(l, meshes, plane) for l in result['labels']]
                durations.append(time.perf_counter() - start)
            by_handle = {o['handle']: o for o in meshes}
            tris = [(l, ids) for l, ids in zip(result['labels'], pairs) if l['role'] == 'triangle_count']
            comparison.append({'scene': name, 'plane': plane, 'median_seconds': statistics.median(durations),
                               'unique_labels': sum(len(p) == 1 for p in pairs), 'ambiguous_labels': sum(len(p) > 1 for p in pairs),
                               'triangle_labels': len(tris), 'unique_triangle_concordance': sum(len(ids) == 1 and by_handle[ids[0]]['triangles'] == int(re.search(r'\d+', l['text'])[0]) for l, ids in tris)})
    result = {'schema': 'flora-audit-v1', 'application': 'headless 3ds Max 2026', 'delivery_passed': False,
              'sources': json.loads((ROOT / 'sources-verified.json').read_text()), 'scenes': scenes,
              'proposed_budgets': budgets(scenes[:1]), 'project_statistics': budgets(scenes[1:]), 'pairing_comparison': comparison,
              'project_vs_library': {'exact_name_matches': sorted({e['source_name'] for e in scenes[0]['entries']} & {e['source_name'] for e in scenes[1]['entries']}),
                                     'note': 'Distinct libraries. Triangle equality is not species equivalence; no automatic cross-library substitution.'}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'entries': [len(s['entries']) for s in scenes], 'labels': [len(s['labels']) for s in scenes], 'comparison': comparison}, indent=2))


if __name__ == '__main__':
    main()
