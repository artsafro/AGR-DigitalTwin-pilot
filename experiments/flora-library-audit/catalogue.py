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


def percentile90(values):
    values = sorted(values)
    return values[math.ceil(.9 * len(values)) - 1] if values else None


def parse_label(text):
    """Keep raw text; Hnnn is an explicit unverified cm convention."""
    s = text.casefold().replace(',', '.')
    kind = 'other'
    for candidate, tokens in [('hedge', ('hedge', 'изгород')), ('bush', ('bush', 'куст')), ('tree', ('tree', 'дерев'))]:
        if any(t in s for t in tokens):
            kind = candidate
            break
    prof = profiles(text)
    for token, value in [('npm', 'NPM'), ('нпм', 'NPM'), ('vpm', 'VPM'), ('впм', 'VPM')]:
        if token in s and value not in prof:
            prof.append(value)
    def dimension(pattern):
        match = re.search(pattern + r'\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|см|m|м)?', s)
        if not match:
            return None
        number = float(match[1])
        return number / 100 if match[2] in ('cm', 'см') else number
    h = dimension(r'(?:height|высота|\bh\b)')
    shorthand = re.findall(r'\bh(\d+(?:\.\d+)?)\b', s)
    return {'raw': text, 'type': kind, 'profiles': sorted(prof), 'height_m': h,
            'width_m': dimension(r'(?:width|crown|диаметр|ширина|крона|\bd\b)'),
            'height_tokens_m_if_cm': [float(v) / 100 for v in shorthand],
            'height_token_units_verified': False}


def row_pair(label, meshes, plane, max_distance, row_band=.5):
    """Try a rightward row first, otherwise bounded nearest; retain <=20% ties.

    XZ library card labels lie below their own pivot, so the row band rejects
    neighbouring display rows and falls back to nearest XZ when appropriate.
    Project XY schedule may label multiple columns: all meshes on its nearest Y
    row remain candidates, regardless of different rightward column distances.
    """
    vertical = 2 if plane == 'xz' else 1
    axes = (0, vertical)
    p = label['position']
    row = [m for m in meshes if abs(m['position'][vertical] - p[vertical]) <= row_band and m['position'][0] > p[0] + .001]
    if plane == 'xz':
        row = [m for m in row if math.dist([p[i] for i in axes], [m['position'][i] for i in axes]) <= max_distance]
    candidates = row or meshes
    # The project has two intended high/low columns; row distance, not X distance,
    # is bounded here. Retain both and report the association as ambiguous.
    row_schedule = plane == 'y' and bool(row)
    ranked = [(abs(m['position'][vertical] - p[vertical]) if row_schedule else math.dist([p[i] for i in axes], [m['position'][i] for i in axes]), m['handle']) for m in candidates]
    if not ranked or min(d for d, _ in ranked) > max_distance:
        return {'handles': [], 'method': 'no_mesh_within_threshold', 'distances': []}
    best = min(d for d, _ in ranked)
    selected = sorted((d, h) for d, h in ranked if d <= max(best * 1.2, best + 1e-4) and d <= max_distance)
    return {'handles': sorted(h for _, h in selected), 'method': 'row_right' if row else 'nearest_fallback',
            'distances': [{'handle': h, 'distance': d} for d, h in selected]}


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
    if not s:
        return 'empty'
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
        association = {'handles': [], 'method': 'category_heading', 'distances': []}
        if label['class'] == 'TextPlus' and label['name'] in ('Tree', 'Bush'):
            ids, status = [], 'category_heading'
        else:
            association = row_pair(label, plants, 'y' if project else 'xz', 10 if project else 3, row_band=10 if project else .5)
            ids = association['handles']
            label_role = 'schedule_row' if project else text_role(label['text'])
            status = 'ambiguous' if len(ids) > 1 else ('paired' if ids else ('unpaired' if label_role in ('note', 'empty') else 'ambiguous'))
        links.append({'handle': label['handle'], 'name': label['name'], 'text': label['text'],
                      'bbox': label.get('bbox'), 'parsed': parse_label(label['text']), 'association': association,
                      'ambiguity_reasons': ['distances_within_20pct'] if len(ids) > 1 else (['no_mesh_within_threshold'] if not ids and status != 'category_heading' else []),
                      'class': label['class'], 'hidden': label['hidden'], 'position': label['position'],
                      'role': 'schedule_row' if project else text_role(label['text']),
                      'candidate_handles': ids, 'status': status})
    # Duplicate Text/TextPlus copies of the same caption are corroboration;
    # different captions of the same role competing for a node are ambiguous.
    for plant in plants:
        assigned = [l for l in links if plant['handle'] in l['candidate_handles']]
        for role_name in ('species', 'profile', 'triangle_count'):
            group = [l for l in assigned if l['role'] == role_name]
            if len({l['text'].strip().casefold() for l in group}) > 1:
                for label in group:
                    label['status'] = 'ambiguous'
                    label['ambiguity_reasons'].append('competing_' + role_name + '_labels')
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
        if nominal is not None and abs(dims[2] / nominal - 1) > .1:
            findings.append('measured_height_outside_10pct_of_node_token')
        if nominal is not None and abs(dims[2] / nominal - 1) > .2:
            findings.append('measured_height_outside_20pct_of_node_token')
        entry_id = ('project' if project else 'library') + f'-{index:03d}'
        archive = ROOT / 'out/verified-v004'
        export_receipt = archive / (entry_id + '.json')
        readback_receipt = archive / (entry_id + '-readback.json')
        artifact_status = 'not_produced'
        if export_receipt.exists():
            artifact_status = 'produced_unverified'
        if readback_receipt.exists():
            checked = json.loads(readback_receipt.read_text(encoding='utf-8'))
            artifact_status = 'readback_equal' if checked['equal'] else 'readback_mismatch'
        entries.append({'id': entry_id, 'source_name': plant['name'], 'source_handle': plant['handle'],
                        'species_labels': names, 'type': kind, 'type_basis': 'display_heading_region' if not project else 'object_name',
                        'profile_raw': raw_profile, 'profile_candidates': sorted({p for r in raw_profile for p in profiles(r)}),
                        'variant_raw': variants, 'hidden': plant['hidden'], 'triangles': plant['triangles'],
                        'vertices': plant['vertices'], 'uv_vertices': plant['uv_vertices'],
                        'bbox_m': [[v / source['unit_in_m'] for v in corner] for corner in plant['bbox']],
                        'dimensions_m': dims, 'labelled_triangles': labelled_tris,
                        'labelled_dimensions': {'raw_height_tokens_m_if_cm': heights, 'height_from_node_name_m_if_cm': nominal,
                                               'unit_assumption': 'H values interpreted as cm, not a verified text unit',
                                               'schedule_height_deviations_pct_if_cm': [(dims[2] / h - 1) * 100 for h in heights if h],
                                               'height_deviation_from_name_mm': (dims[2] - nominal) * 1000 if nominal is not None else None,
                                               'library_dimension_text': None},
                        'material': material,
                        'atlas_use': {'bitmap_users_in_scene': {b['filename']: bitmap_users[b['filename']] for b in (material or {}).get('bitmaps', [])},
                                      'status': 'reference_sharing_only_uv_islands_and_texture_pixels_not_audited'},
                        'findings': findings,
                        'planned_file': 'out/assets-v003/' + entry_id + '.fbx',
                        'planned_preview': 'out/verified-v004/' + entry_id + '.svg',
                        'file': 'out/assets-v003/' + entry_id + '.fbx' if export_receipt.exists() else None,
                        'preview': 'out/verified-v004/' + entry_id + '.svg' if export_receipt.exists() else None,
                        'artifact_status': artifact_status,
                        'preview_kind': 'untextured_front_wireframe_not_appearance_approval',
                        'delivery_passed': False})
    return {'source': {k: v for k, v in source.items() if k != 'objects'}, 'counts': dict(Counter(role(o, project) for o in objects)),
            'labels': links, 'entries': entries,
            'excluded_nodes': [{'name': o['name'], 'class': o['class'], 'role': role(o, project),
                                'triangles': o.get('triangles'), 'position': o['position'], 'bbox': o.get('bbox'),
                                'material_name': (o.get('material') or {}).get('name')} for o in objects if role(o, project) not in ('label', 'plant')]}


def budgets(scenes):
    rows = []
    for kind in ['tree', 'bush', 'hedge', 'climber', 'unclassified']:
        for profile in ['NPM', 'VPM', 'unknown']:
            selected = [e for s in scenes for e in s['entries'] if e['type'] == kind and (profile in e['profile_candidates'] if profile != 'unknown' else not e['profile_candidates'])]
            values = sorted(e['triangles'] for e in selected)
            rows.append({'type': kind, 'profile': profile, 'n': len(values), 'min': min(values) if values else None,
                         'median': statistics.median(values) if values else None, 'p90': percentile90(values), 'max': max(values) if values else None,
                         'proposed_review_above': math.ceil(max(values) / 100) * 100 if values else None,
                         'status': 'observed_ceiling_review_only_not_regulatory_limit' if values else 'no_samples_no_budget'})
    return rows


def species_keys(entry):
    keys = set()
    for raw in entry['species_labels']:
        # A library multiline caption is one name including its cultivar. A
        # project row separates species after each Hnnn token, not each newline.
        chunks = re.split(r'\bh\d+(?:[.,]\d+)?\b', raw, flags=re.I) if entry['id'].startswith('project') else [raw]
        for line in chunks:
            value = re.sub(r'\([^)]*\)', '', line.casefold().replace('ё', 'е'))
            value = re.sub(r'\bh\d+(?:[.,]\d+)?\b', '', value)
            value = re.sub(r'[^a-zа-я0-9]+', ' ', value).strip()
            if value:
                keys.add(value)
    return keys


def compare_libraries(library, project):
    library_names = set().union(*(species_keys(e) for e in library))
    project_names = set().union(*(species_keys(e) for e in project))
    rows = []
    for entry in project:
        by_name = [e['id'] for e in library if species_keys(entry) & species_keys(e)]
        dims = sorted(entry['dimensions_m'][:2]) + entry['dimensions_m'][2:]
        by_geometry = []
        for other in library:
            ref = sorted(other['dimensions_m'][:2]) + other['dimensions_m'][2:]
            if entry['triangles'] == other['triangles'] and all(abs(a-b) <= .2 * max(abs(b), .001) for a, b in zip(dims, ref)):
                by_geometry.append(other['id'])
        rows.append({'project_id': entry['id'], 'normalized_species_names': sorted(species_keys(entry)),
                     'library_name_candidates': by_name, 'dimension_and_triangle_candidates': by_geometry,
                     'status': 'candidate_only_not_botanical_identity'})
    return {'normalization': 'casefold, yo/e, remove parenthetical Latin and H tokens; exact remaining name',
            'dimension_tolerance': .2, 'triangle_tolerance': 0,
            'shared_species_names': sorted(library_names & project_names),
            'library_only_species_names': sorted(library_names - project_names),
            'project_only_species_names': sorted(project_names - library_names), 'entries': rows,
            'exact_mesh_name_matches': sorted({e['source_name'] for e in library} & {e['source_name'] for e in project}),
            'note': 'Candidates, not approved substitutions. Multiline rows and unlabelled meshes remain unresolved.'}


def portable(value):
    """Redact user-root references, keep paths relative to the authorized card root."""
    if isinstance(value, str):
        normalized = value.replace('\\', '/')
        root = str(ROOT).replace('\\', '/')
        if normalized.startswith(root + '/'):
            return normalized[len(root) + 1:]
        return normalized.replace('C:/Users/artsafro/', '<USER>/')
    if isinstance(value, list):
        return [portable(v) for v in value]
    if isinstance(value, dict):
        return {portable(k): portable(v) for k, v in value.items()}
    return value


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
        for plane in (['xy', 'xz', 'bounded_row'] if index == 0 else ['xy', 'y', 'bounded_row']):
            durations = []
            for _ in range(3):
                start = time.perf_counter()
                pairs = []
                for label in result['labels']:
                    if plane == 'bounded_row':
                        association = row_pair(label, meshes, 'y' if index else 'xz',
                                               10 if index else 3, row_band=10 if index else .5)
                        pairs.append([] if label['status'] == 'category_heading' else association['handles'])
                    else:
                        pairs.append(pair(label, meshes, plane))
                durations.append(time.perf_counter() - start)
            by_handle = {o['handle']: o for o in meshes}
            tris = [(l, ids) for l, ids in zip(result['labels'], pairs) if l['role'] == 'triangle_count']
            comparison.append({'scene': name, 'plane': plane, 'median_seconds': statistics.median(durations),
                               'unique_labels': sum(len(p) == 1 for p in pairs), 'ambiguous_labels': sum(len(p) > 1 for p in pairs),
                               'triangle_labels': len(tris), 'unique_triangle_concordance': sum(len(ids) == 1 and by_handle[ids[0]]['triangles'] == int(re.search(r'\d+', l['text'])[0]) for l, ids in tris)})
    result = {'schema': 'flora-audit-v1', 'application': 'headless 3ds Max 2026', 'delivery_passed': False,
              'sources': json.loads((ROOT / 'sources-verified.json').read_text()), 'scenes': scenes,
              'proposed_budgets': budgets(scenes[:1]), 'project_statistics': budgets(scenes[1:]), 'pairing_comparison': comparison,
              'artifact_root': 'C:/x/t_366e8d9d',
              'project_vs_library': compare_libraries(scenes[0]['entries'], scenes[1]['entries'])}
    result = portable(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'entries': [len(s['entries']) for s in scenes], 'labels': [len(s['labels']) for s in scenes], 'comparison': comparison}, indent=2))


if __name__ == '__main__':
    main()
