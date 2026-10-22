"""new-case: AC05 Gate-1 evidence inventory, not production-model acceptance."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / 'jobs/TEC26-OKS/AC05'
GEOMETRY_SHA = '22406a97eaf836e47cce92ef871a5cceea3357b3f936ea13ca2764791ac6e500'
ANSWER_DATE = '2026-10-22'
ANSWER_QUOTE = 'Принимаю'
ANSWER_LINES = (
    'Sandwich panels: solid colour without joints (module not confirmed in drawings).',
    'Roof: RAL 7004 grey (as KPP 7004), not 5015.',
    'Mixed ID: allowed to paint parts differently (roof 7004, frame 7004, plinth/perimeter drop = wall colour) WITHOUT changing geometry - via UV/atlas regions or splitting face groups inside the same ID.',
    'Panels RAL 5015 = KPP blue; doors/frames/porches RAL 7004 = KPP grey; glass as KPP; the drop below +-0.000 = wall colour.',
    'AC05 result: ID1-2 blue 5015 (roof part of ID1 -> 7004 per 2-3); ID3-4 metal 7004 including the gate infill.',
)
PANEL_MODULE = (
    'vertical joints only; rib count and step from each facade colour-solution sheet; '
    'no horizontal joints; drop below +-0.000 plain'
)
SUPERSEDING_DATE = '2026-10-22'
SUPERSEDING_QUOTES = (
    'Не вижу швов на панелях. В КПП есть текстура для VPM со швами... такой же тексель на наших домиках в VPM и NPM',
    'ниже ±0.000 без швов (под землёй не видно).',
    'Панели неверные, должны быть вертикальные швы только; текстуру пришлю; если не влезает, можно аккуратно порезать через loop или ring.',
    'всё равно говно, почему нельзя сделать как на презе — тут прям всё читается, и швы, и количество',
)
STEP_SUPERSEDES = '0.60'
PANEL_TEXTURE_SHA = '2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece'
TILE_M = 4096 / 1000
EXCEED_4K_POLYGONS = frozenset({
    239, 241, 259, 260, 261, 262, 271, 272, 285, 291, 327, 335, 336, 340, 633, 643,
})


def _load():
    path = JOB / 'materials.json'
    assert path.is_file(), 'AC05 Gate-1 materials evidence is missing'
    return json.loads(path.read_text(encoding='utf-8'))


def _triangle(vertices, corners):
    a, b, c = (vertices[k] for k in corners)
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    area = 0.5 * length
    unit_z = 0.0 if length == 0 else nz / length
    zs = (a[2], b[2], c[2])
    return area, unit_z, min(zs)


def _region_hits(region, unit_z, zmin):
    match = region['match']
    if match.get('complement_of') == 'roof':
        return False
    return unit_z > match['normal_z_gt'] and zmin > match['min_vertex_z_gt_m']


def _assign_id1(data):
    """Every ID1 triangle must hit exactly one declared region. Fail closed."""
    row = next(item for item in data['materials'] if item['id'] == 1)
    regions = row['regions']
    names = [region['region'] for region in regions]
    assert len(names) == len(set(names)) == 2
    assert set(names) == {'wall_drop', 'roof'}
    by_name = {region['region']: region for region in regions}
    roof_match = by_name['roof']['match']
    assert roof_match['normal_z_gt'] == 0.5
    assert roof_match['min_vertex_z_gt_m'] == 2.0
    assert by_name['wall_drop']['match'] == {'complement_of': 'roof'}
    geometry = json.loads(Path(data['scene']['geometry_buffer']['path']).read_text(encoding='utf-8'))
    assert data['scene']['geometry_buffer']['sha256'] == GEOMETRY_SHA
    vertices, triangles, material_ids = geometry['vertices'], geometry['triangles'], geometry['material_ids']
    assert len(triangles) == len(material_ids) == 1290
    assigned = {}
    areas = {'wall_drop': 0.0, 'roof': 0.0}
    for index, material_id in enumerate(material_ids):
        if material_id != 1:
            continue
        area, unit_z, zmin = _triangle(vertices, triangles[index])
        roof_hit = _region_hits(by_name['roof'], unit_z, zmin)
        wall_hit = not roof_hit
        hits = [name for name, hit in (('roof', roof_hit), ('wall_drop', wall_hit)) if hit]
        if len(hits) != 1:
            raise AssertionError(f'ID1 triangle {index} is unmapped or duplicated: {hits}')
        if zmin <= 0.0 and hits[0] != 'wall_drop':
            raise AssertionError(f'perimeter-drop triangle {index} is not wall-coloured')
        assigned[index] = hits[0]
        areas[hits[0]] += area
        pair = index - 1 if index % 2 else index + 1
        if pair in assigned and assigned[pair] != hits[0]:
            raise AssertionError(f'ID1 polygon pair {(min(index, pair), max(index, pair))} splits across regions')
        shared = set(triangles[index]) & set(triangles[pair])
        if len(shared) != 2:
            raise AssertionError(f'ID1 triangle {index} is not paired to a polygon')
    id1_indices = {index for index, material_id in enumerate(material_ids) if material_id == 1}
    if set(assigned) != id1_indices:
        missing = id1_indices - set(assigned)
        extra = set(assigned) - id1_indices
        raise AssertionError(f'missing={sorted(missing)[:8]} extra={sorted(extra)[:8]}')
    if len(assigned) != len(id1_indices):
        raise AssertionError('duplicate ID1 face assignment')
    return by_name, assigned, areas


def test_ac05_gate1_inventory_preserves_measured_ids_and_records_approval():
    data = _load()
    assert data['gate1']['status'] == 'approved-gate1'
    assert data['gate1']['approved'] is True
    assert data['gate1']['date'] == ANSWER_DATE
    assert data['gate1']['quote'] == ANSWER_QUOTE
    answer = data['gate1']['answer_verbatim']
    assert ANSWER_DATE in answer and ANSWER_QUOTE in answer
    for line in ANSWER_LINES:
        assert line in answer
    assert data['gate1']['questions'] == []
    assert data['gate1']['panel_module'] == PANEL_MODULE
    assert data['passed'] is False
    assert data['building_name'] == 'Блок-модуль пенного пожаротушения'
    assert data['scene']['layer'] == '005'
    assert data['scene']['mesh']['handle'] == 161
    assert [c['handle'] for c in data['scene']['collision_candidates']] == [344, 345]
    rows = data['materials']
    assert [r['id'] for r in rows] == list(range(1, 11))
    expected = {1: (127, 254, 82.98113025259933),
                2: (22, 44, 56.48439932962852),
                3: (476, 990, 6.699798207317762),
                4: (1, 2, 4.313754850037867)}
    for row in rows:
        if row['id'] in expected:
            assert row['status'] == 'approved-gate1'
            assert row['question_id'] is None
        else:
            assert row['finish'] == '?'
            assert row['status'] == 'unused'
            assert row['ral'] is None
        if row['id'] in expected:
            faces, triangles, area = expected[row['id']]
            assert row['poly_faces'] == faces
            assert row['triangles'] == triangles
            assert math.isfinite(row['area_m2'])
            assert math.isclose(row['area_m2'], area, abs_tol=1e-10)
        else:
            assert row['triangles'] == row['poly_faces'] == row['area_m2'] == 0
    by_id = {row['id']: row for row in rows}
    assert by_id[2]['ral'] == '5015' and by_id[2]['map_type'] == 'joints'
    assert by_id[2]['joints']['orientation'] == 'vertical'
    assert by_id[2]['joints']['horizontal_joints'] is False
    assert by_id[3]['ral'] == '7004' and by_id[3]['map_type'] == 'metal' and by_id[3]['joints'] is False
    assert by_id[4]['ral'] == '7004' and by_id[4]['map_type'] == 'metal' and by_id[4]['joints'] is False
    assert sum(r['triangles'] for r in rows) == 1290
    assert sum(r['poly_faces'] for r in rows) == 626
    assert {r['ral'] for r in data['drawing_finishes'] if r['ral']} == {'5015', '7004'}
    for finish in data['drawing_finishes']:
        assert finish['evidence']
    for source in data['sources']:
        assert len(source['sha256']) == 64
        int(source['sha256'], 16)
    assert data['evidence']['contact_sheet'].startswith('G:/Мой диск/AGR-evidence/tec26-oks/AC05/gate1-v007/')
    assert 'gate1-v006' in data['evidence']['supersedes']
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'not a delivery acceptance' in report
    assert '276D52' in report
    assert '-2.004332' in report
    assert ANSWER_QUOTE in report and ANSWER_DATE in report
    for line in ANSWER_LINES:
        assert line in report
    assert PANEL_MODULE in report
    assert 'approved-gate1' in report
    assert 'Gate 1 — STOP' not in report


def test_ac05_gate1_id1_regions_partition_every_face():
    data = _load()
    by_name, assigned, areas = _assign_id1(data)
    palette = {item['ral']: item['rgb'] for item in data['kpp_palette']}
    assert palette['7004'] == [150, 153, 146]
    assert palette['5015'] == [34, 113, 179]
    roof, wall = by_name['roof'], by_name['wall_drop']
    assert roof['ral'] == '7004'
    assert roof['rgb'] == palette['7004']
    assert roof['kpp_finish'] == 'Door_RAL7004'
    assert wall['ral'] == '5015'
    assert wall['rgb'] == palette['5015']
    assert wall['kpp_finish'] == 'Metal_RAL5015'
    assert roof['map_type'] == 'metal' and roof['joints'] is False
    above = wall['above_zero']
    assert above['map_type'] == 'joints'
    assert above['orientation'] == 'vertical'
    assert above['horizontal_joints'] is False
    assert wall['drop']['joints'] is False
    assert wall['drop']['map_type'] == 'solid'
    counts = {'roof': 0, 'wall_drop': 0}
    polys = {'roof': 0, 'wall_drop': 0}
    for index, name in assigned.items():
        counts[name] += 1
        if index % 2 == 0:
            polys[name] += 1
    for name in ('roof', 'wall_drop'):
        region = by_name[name]
        stored = region['triangle_indices']
        assert len(stored) == len(set(stored)), f'duplicate indices in {name}'
        assert set(stored) == {index for index, hit in assigned.items() if hit == name}
        assert region['triangles'] == counts[name] == len(stored)
        assert region['poly_faces'] == polys[name]
        assert math.isclose(region['area_m2'], areas[name], abs_tol=1e-12)
    assert counts['roof'] + counts['wall_drop'] == 254
    assert polys['roof'] + polys['wall_drop'] == 127
    assert math.isclose(areas['roof'] + areas['wall_drop'], 82.98113025259933, abs_tol=1e-12)
    assert counts['roof'] > 0 and counts['wall_drop'] > 0
    id1 = next(item for item in data['materials'] if item['id'] == 1)
    assert id1['status'] == 'approved-gate1'
    assert 'rule' in id1['classification']
    assert 'normal' in id1['classification']['rule'] and 'Z' in id1['classification']['rule']


def test_ac05_gate_images_and_required_perimeter_drop():
    data = _load()
    render = data['evidence'].get('native_render', {})
    assert render.get('application') == 'Blender 5.1.2'
    assert render.get('ucx_visible') is False
    assert render.get('zero_level_line_m') == 0.0
    assert len(render.get('paired_views', [])) == 2
    assert render.get('id1_roof_triangles') == next(
        region['triangles'] for region in data['materials'][0]['regions'] if region['region'] == 'roof')
    drop = data['scene'].get('perimeter_drop', {})
    assert drop.get('keep_in_both_profiles') is True
    assert drop.get('finish_policy') == 'adjacent facade; no new ID'
    walls = drop.get('walls', [])
    assert len(walls) == 4
    for wall in walls:
        assert wall['coverage_at_minus_1_m'] == 'complete'
        assert math.isfinite(wall['highest_bottom_z_m'])
        assert wall['highest_bottom_z_m'] <= -1.0


def _vertical_only(spec):
    assert spec['map_type'] == 'joints'
    assert spec['orientation'] == 'vertical'
    assert spec['horizontal_joints'] is False


def _panel_wall_faces(geometry):
    """Blue wall-region polygons: ID2, and ID1 triangles that are not the roof split.

    Width is the horizontal run of the polygon at 1000 px/m. A vertical face uses
    the tangent perpendicular to its horizontal normal. A horizontal face uses the
    longer plan dimension. The drop is the shell whose vertices stay at or below
    the 0.01 m gap under the first above-grade band.
    """
    vertices, triangles, material_ids = geometry['vertices'], geometry['triangles'], geometry['material_ids']
    groups = {}
    for index, material_id in enumerate(material_ids):
        if material_id in (1, 2):
            groups.setdefault(index // 2, []).append(index)
    faces = []
    for polygon, indices in sorted(groups.items()):
        assert len(indices) == 2
        assert material_ids[indices[0]] == material_ids[indices[1]]
        points, normals = [], []
        for index in indices:
            a, b, c = (vertices[k] for k in triangles[index])
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            points.extend((a, b, c))
            normals.append((nx / length, ny / length, nz / length))
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        zs = [point[2] for point in points]
        nx = sum(normal[0] for normal in normals) / 2
        ny = sum(normal[1] for normal in normals) / 2
        nz = sum(normal[2] for normal in normals) / 2
        zmin, zmax = min(zs), max(zs)
        material_id = material_ids[indices[0]]
        if material_id == 1 and nz > 0.5 and zmin > 2.0:
            continue
        if abs(nz) > 0.5 or math.hypot(nx, ny) < 1e-6:
            width = max(max(xs) - min(xs), max(ys) - min(ys))
        else:
            span = math.hypot(nx, ny)
            axis_x, axis_y = -ny / span, nx / span
            projections = [point[0] * axis_x + point[1] * axis_y for point in points]
            width = max(projections) - min(projections)
        faces.append({
            'polygon': polygon,
            'material_id': material_id,
            'width_m': width,
            'drop': zmax <= 0.01 and zmin < 0.0,
        })
    return faces


def test_ac05_superseding_decisions_quote_the_later_notes():
    data = _load()
    decisions = data['superseding_decisions']
    assert len(decisions) == 3
    assert [item['date'] for item in decisions] == [SUPERSEDING_DATE] * 3
    recorded = '\n'.join(item['quote'] for item in decisions)
    for quote in SUPERSEDING_QUOTES:
        assert quote in recorded
    assert 'solid colour without joints' in decisions[0]['supersedes']
    assert STEP_SUPERSEDES in decisions[2]['supersedes']
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'superseding_decisions' in report
    for quote in SUPERSEDING_QUOTES:
        assert quote in report
        assert SUPERSEDING_DATE in report


def test_ac05_blue_wall_joints_are_vertical_and_drop_has_none():
    data = _load()
    by_id = {row['id']: row for row in data['materials']}
    _vertical_only(by_id[2]['joints'] | {'map_type': by_id[2]['map_type']})
    wall = next(region for region in by_id[1]['regions'] if region['region'] == 'wall_drop')
    roof = next(region for region in by_id[1]['regions'] if region['region'] == 'roof')
    _vertical_only(wall['above_zero'])
    assert wall['drop']['region'] == 'perimeter_drop'
    assert wall['drop']['joints'] is False
    assert wall['drop']['map_type'] == 'solid'
    assert 'без швов' in wall['drop']['quote'] or 'without joints' in wall['drop']['rule']
    assert roof['map_type'] == 'metal' and roof['joints'] is False
    assert by_id[3]['joints'] is False and by_id[4]['joints'] is False
    rule = data['panel_rule']
    assert rule['orientation'] == 'vertical'
    assert rule['horizontal_joints'] is False
    assert rule['texel_px_per_m'] == 1000
    assert rule['udim_px'] == 4096
    assert rule.get('module_m') != 0.60
    assert rule.get('period_m') != 0.60
    assert rule['step_source'] == 'facade_colour_sheet'
    assert rule['source_tiled_raw'] is False
    assert rule['cuts_performed'] == []
    assert 'ring' in rule['cut_rule']
    assert 'plain' in rule['drop_rule']
    assert set(rule['wall_faces_exceeding_4k']) == EXCEED_4K_POLYGONS


def test_ac05_panel_texture_hash_matches_the_file():
    data = _load()
    texture = data['panel_texture']
    path = Path(texture['path'])
    assert path.as_posix().endswith('user-textures/panel_RAL5015_vertical_joints_4096.png')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == texture['sha256'] == PANEL_TEXTURE_SHA
    drive = Path(texture['drive_copy'])
    assert hashlib.sha256(drive.read_bytes()).hexdigest() == digest
    assert texture['width_px'] == texture['height_px'] == 4096
    assert texture['mean_rgb'] == [34, 112, 177]


def test_ac05_wall_face_widths_are_generated_for_every_face():
    data = _load()
    geometry = json.loads(Path(data['scene']['geometry_buffer']['path']).read_text(encoding='utf-8'))
    generated = _panel_wall_faces(geometry)
    recorded = data['panel_rule']['wall_faces']
    assert len(recorded) == len(generated)
    assert len({row['polygon'] for row in recorded}) == len(recorded)
    by_polygon = {row['polygon']: row for row in recorded}
    exceed = set()
    for face in generated:
        row = by_polygon[face['polygon']]
        assert row['material_id'] == face['material_id']
        assert math.isclose(row['width_m'], face['width_m'], abs_tol=1e-6)
        assert row['exceeds_4k_tile'] is (face['width_m'] > TILE_M)
        if face['drop']:
            assert row['joints'] is False
            assert row['role'] == 'perimeter_drop'
        else:
            assert row['joints'] == 'vertical'
            assert row['horizontal_joints'] is False
            assert row['role'] == 'wall'
        if row['exceeds_4k_tile']:
            exceed.add(face['polygon'])
    assert exceed == EXCEED_4K_POLYGONS
    assert data['panel_rule']['cuts_performed'] == []
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    for polygon in sorted(exceed):
        assert str(polygon) in report


def _consistent(count, step, width):
    return min(abs(count * step - width), abs((count - 1) * step - width)) < 0.002


def test_ac05_facade_ribs_come_from_the_colour_sheet_and_supersede_060():
    data = _load()
    assert data['facade_rib_source'] == 'found'
    searched = '\n'.join(data['facade_rib_files_searched'])
    assert 'AC.05_R1.dwg' in searched
    assert 'АС.pdf' in searched
    assert 'ТЭЦ26 на РР.pptx' in searched
    assert 'user-refs' in searched
    rule = data['panel_rule']
    assert rule['horizontal_joints'] is False
    facades = {item['id']: item for item in rule['facades']}
    assert set(facades) == {'1-2', '2-1', 'BA', 'AB'}
    for item in facades.values():
        assert item['horizontal_joints'] is False
        assert item['sheet']
        assert item['block_insert_handle']
    long_12, long_21 = facades['1-2'], facades['2-1']
    assert long_12['rib_count'] == long_21['rib_count'] == 44
    assert long_12['step_m'] == long_21['step_m'] == 0.2
    assert long_12['panel_field_width_m'] == long_21['panel_field_width_m'] == 8.8
    assert long_12['even_step'] is True and long_21['even_step'] is True
    assert _consistent(44, 0.2, 8.8)
    assert long_12['module_handles'] == ['278522', '27854D']
    assert long_21['module_handles'] == ['27A4C0', '27A495']
    short = facades['BA']
    assert short['rib_count'] == 13
    assert short['even_step'] is True
    assert _consistent(short['rib_count'], short['step_m'], short['panel_field_width_m'])
    gate = facades['AB']
    assert gate['even_step'] is False
    assert gate['panel_rib_count'] is None
    door = long_21['door']
    assert door['ral'] == '7004'
    assert door['hatch_handle'] == '27A4C1'
    assert door['rgb'] == [155, 155, 155]
    assert 1.0 < door['width_m'] < 1.2
    assert 2.0 < door['height_m'] < 2.4
    assert gate['gate']['hatch_handle'] == '27D28A'
    assert gate['gate']['rgb'] == [155, 155, 155]
    assert 'grey' in rule['plinth_rule']
    assert 'plain' in rule['drop_rule']
    report = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'facade_rib_source' in report
    assert '44' in report and '0.200' in report
    assert data['gate1']['questions'] == []


def test_ac05_gate1_v007_hashes_match_files():
    data = _load()
    text = (JOB / 'SHA256SUMS.txt').read_text(encoding='utf-8')
    assert 'superseded' in text.lower()
    assert 'gate1-v006' in text
    pinned = []
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        digest, path = line.split('  ', 1)
        assert 'gate1-v007' in path.replace('\\', '/')
        file_digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert file_digest == digest, path
        pinned.append(path.replace('\\', '/'))
    assert any(path.endswith('/contact-sheet.png') for path in pinned)
    sheet = data['evidence']['contact_sheet']
    assert hashlib.sha256(Path(sheet).read_bytes()).hexdigest() == data['evidence']['contact_sheet_sha256']
    assert sheet.replace('\\', '/') in pinned
    assert data['evidence']['native_render']['finish_views'] == 'colour-only'
