"""AC08 Gate-1 colour approval recorded from Artem 2026-10-22 («Принимаю»)."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / 'jobs/TEC26-OKS/AC08'

# KPP1 solid tiles, pixel-verified in the intake evidence (not a chart sample).
KPP_RGB_BY_RAL = {
    '5015': [34, 113, 179],  # Metal_RAL5015 tile 1013
    '7004': [150, 153, 146],  # Door_RAL7004 tile 1010
}

# Artem 2026-10-22 panel texture. Measured mean is not the approved flat wall colour.
ARTEM_PANEL_TEXTURE = Path('C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png')
ARTEM_PANEL_SHA256 = '2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece'
ARTEM_PANEL_MEAN_RGB = [34, 112, 177]
# Max |channel| distance from KPP Metal_RAL5015 (34,113,179) is 2 (B).
ARTEM_MEAN_KPP_TOLERANCE = 2

# Artem 2026-10-22, from the AC08 «Цветовое решение» sheet. Supersedes the 0.60 m step.
SHEET_STEP_M = 0.20
SHEET_STEP_PX_AT_1000 = 200
FACADE_RIBS = {'1-2': 30, 'A-B': 12, 'B-A': 12}
# Facade 2-1 is on the sheet and was not counted. Do not invent a rib count.
FACADE_2_1_QUESTION = (
    'Facade 2-1 («Фасад 2-1. Цветовое решение») is drawn on the colour sheet '
    'and this round does not count it. How many vertical ribs does facade 2-1 have, '
    'and is the step the same ~0.20 m as facade 1-2?'
)


def load():
    return json.loads((JOB / 'materials.json').read_text(encoding='utf-8'))


def gate_counts_as_approved(gate):
    """Fail closed: approved-gate1 counts only with a named author and a quote."""
    if not isinstance(gate, dict):
        return False
    if gate.get('stage') != 1 or gate.get('status') != 'approved-gate1':
        return False
    if gate.get('approved') is not True:
        return False
    author = gate.get('approved_by')
    quote = gate.get('quote')
    if not isinstance(author, str) or not author.strip():
        return False
    if not isinstance(quote, str) or not quote.strip():
        return False
    return True


def test_gate_approved_by_artem_quote():
    data = load()
    gate = data['gate']
    assert gate_counts_as_approved(gate)
    assert gate == {
        'stage': 1,
        'status': 'approved-gate1',
        'approved': True,
        'approved_by': 'Artem',
        'approved_on': '2026-10-22',
        'quote': 'Принимаю',
    }
    assert data['building_name'] == 'Контейнер низковольтных комплектных устройств (НКУ)'
    assert data['production_outputs'] == []


def test_gate_fail_closed_without_author_or_quote():
    gate = load()['gate']
    assert gate_counts_as_approved(gate)
    missing_author = dict(gate, approved_by='')
    missing_quote = dict(gate, quote='')
    absent_author = {k: v for k, v in gate.items() if k != 'approved_by'}
    absent_quote = {k: v for k, v in gate.items() if k != 'quote'}
    unapproved = dict(gate, approved=False)
    assert gate_counts_as_approved(missing_author) is False
    assert gate_counts_as_approved(missing_quote) is False
    assert gate_counts_as_approved(absent_author) is False
    assert gate_counts_as_approved(absent_quote) is False
    assert gate_counts_as_approved(unapproved) is False


@pytest.mark.parametrize('mid,triangles,faces,area', [
    (1, 254, 127, 60.50952526944401),
    (2, 30, 15, 35.3280560120449),
    (3, 64, 38, 1.6974531660811787),
])
def test_census_coverage(mid, triangles, faces, area):
    data = load()
    row = next(x for x in data['materials'] if x['id'] == mid)
    assert row['triangles'] == triangles
    assert row['poly_faces'] == faces
    assert row['area_m2'] == pytest.approx(area, abs=1e-10)
    assert row['evidence']
    assert all(x in data['evidence'] for x in row['evidence'])


def test_no_slot_or_face_silently_dropped():
    data = load()
    assert [x['id'] for x in data['materials']] == [1, 2, 3]
    assert data['scene']['unused_populated_ids'] == [4, 5]
    assert data['scene']['empty_ids'] == [6, 7, 8, 9, 10]
    assert sum(x['triangles'] for x in data['materials']) == 348
    assert sum(x['poly_faces'] for x in data['materials']) == 180
    assert data['scene']['mesh_handle'] == 172
    assert data['scene']['collision_handle'] == 343
    assert data['scene']['layer'] == '008'


def test_mixed_id1_split_by_region_keeps_aggregate():
    data = load()
    row = next(x for x in data['materials'] if x['id'] == 1)
    assert row['status'] == 'approved_mixed_id_split_by_region'
    assert row['map_type'] == 'solid'
    assert row['finish'] != '?'
    assert row['poly_faces'] == 127
    assert row['triangles'] == 254
    assert row['area_m2'] == pytest.approx(60.50952526944401, abs=1e-10)
    assert 'roof' in row['geometry_role'] and 'foundation' in row['geometry_role']
    parts = {p['role']: p for p in row['parts']}
    assert set(parts) == {'roof', 'frame', 'foundation_drop'}
    assert parts['roof']['ral'] == '7004'
    assert parts['roof']['kpp_tile'] == 1010
    assert parts['frame']['ral'] == '7004'
    assert parts['frame']['kpp_tile'] == 1010
    assert parts['foundation_drop']['ral'] == '5015'
    assert parts['foundation_drop']['kpp_tile'] == 1013
    for part in row['parts']:
        assert part['map_type'] == 'solid'
        assert part['poly_faces'] is None
        assert part['triangles'] is None
        assert part['area_m2'] is None
        assert 'scene-census.json' in part['area_reason']
    assert data['questions'] == [
        {'facade': '2-1', 'vertical_ribs': '?', 'question': FACADE_2_1_QUESTION}
    ]


def test_no_question_mark_finish_on_an_approved_id():
    data = load()
    approved = [
        row for row in data['materials']
        if str(row.get('status', '')).startswith('approved')
    ]
    assert len(approved) == 3
    for row in data['materials']:
        if row.get('finish') == '?':
            assert not str(row.get('status', '')).startswith('approved')
        if str(row.get('status', '')).startswith('approved'):
            assert row.get('finish') != '?'


def test_every_approved_id_or_part_rgb_matches_kpp_ral():
    data = load()
    checked = 0
    for row in data['materials']:
        if not str(row.get('status', '')).startswith('approved'):
            continue
        targets = row['parts'] if row.get('parts') else [row]
        for target in targets:
            assert target['rgb_srgb'] == KPP_RGB_BY_RAL[target['ral']]
            checked += 1
    # ID1 roof, ID1 frame, ID1 drop, ID2 panels, ID3 door.
    assert checked == 5


@pytest.mark.parametrize('mid,ral,rgb,tile', [
    (2, '5015', [34, 113, 179], 1013),
    (3, '7004', [150, 153, 146], 1010),
])
def test_approved_ids_reuse_exact_solid_kpp_pixels(mid, ral, rgb, tile):
    """Flat colour stays the verified KPP RGB. ID2 joints are separate from that flat."""
    data = load()
    row = next(x for x in data['materials'] if x['id'] == mid)
    assert row['ral'] == ral and row['rgb_srgb'] == rgb
    assert row['kpp_tile'] == tile
    assert row['status'] == 'approved'
    assert row['map_type'] == ('joints' if mid == 2 else 'solid')
    assert len(row['kpp_sha256']) == 64


def _finish_targets(data):
    for row in data['materials']:
        yield row
        yield from row.get('parts') or []


def _id2_joints(data):
    row = next(x for x in data['materials'] if x['id'] == 2)
    assert row['map_type'] == 'joints'
    return row, row['joints']


def test_id2_vertical_joints_only_module_matches_texel():
    """Layout step is 0.20 m (200 px at 1000 px/m). The texture pitch is not that step."""
    data = load()
    row, joints = _id2_joints(data)
    assert joints['joint_orientation'] == 'vertical_only'
    assert joints['vertical_only'] is True
    assert joints['horizontal_joints'] is False
    assert joints['pattern'] == 'vertical_only'
    assert joints.get('source_udim') != 1007
    assert joints.get('source_finish') != 'Cassette_RAL5015'
    assert '1007' not in json.dumps(joints)
    source = joints['source']
    assert source['path'].replace('\\', '/').endswith(
        'user-textures/panel_RAL5015_vertical_joints_4096.png'
    )
    assert source['sha256'] == ARTEM_PANEL_SHA256
    assert source['width_px'] == 4096 and source['height_px'] == 4096
    assert source['mean_rgb'] == ARTEM_PANEL_MEAN_RGB
    assert source['joint_pitch_px'] == 600
    assert source['joint_width_px'] == 8
    assert source['vertical_joint_count'] == 7
    assert source['joint_centres_px'] == [270 + 600 * i for i in range(7)]
    assert source['joint_centres_px'][0] == 270
    assert source['joint_centres_px'][-1] == 3870
    assert source['width_px'] % source['joint_pitch_px'] != 0
    assert joints['seamless_wrap'] is False
    assert joints['module_m'] == pytest.approx(SHEET_STEP_M)
    assert joints['step_m'] == pytest.approx(SHEET_STEP_M)
    assert joints['texel_px_per_m'] == 1000
    assert joints['step_px'] == SHEET_STEP_PX_AT_1000
    assert joints['step_px'] / joints['texel_px_per_m'] == pytest.approx(joints['step_m'])
    # File pitch (600 px / 0.60 m) is the drawn joint in the texture, not the facade step.
    assert source['joint_pitch_px'] != joints['step_px']
    assert source['joint_pitch_px'] / joints['texel_px_per_m'] != pytest.approx(joints['step_m'])
    assert (
        source['joint_width_px'] * 1000 / joints['texel_px_per_m']
        == pytest.approx(joints['joint_width_mm'])
    )
    assert joints['joint_width_mm'] == 8
    assert joints['phase_symmetric'] is True
    assert joints['phase_anchor'] == 'panel_field_symmetric'
    assert joints['phase_anchor'] != 'panel_start_edge'
    assert joints['spacing'] == 'even_over_panel_field'
    assert joints['below_ground_plain'] is True
    assert joints['vpm_maps'] == ['diffuse', 'normal']
    assert joints['npm_joints_min_px'] == 1.5
    history = joints['superseded_0_60_m']
    assert history['module_m'] == pytest.approx(0.60)
    assert history['phase_anchor'] == 'panel_start_edge'
    assert history['cut_at'] == 'joint_positions_only'
    assert 'edge loop' in history['cut_policy'].lower()
    assert 'ring' in history['cut_policy'].lower()
    cutting = joints['cutting']
    assert cutting['new_cuts_for_0_20_m_step'] is False
    assert cutting['method'] == 'edge_loop_or_ring'
    assert '4k' in cutting['when'].lower()
    assert cutting['quads_kept'] is True
    assert cutting['listed_in_build_report'] is True
    assert cutting['unchanged'] == ['silhouette', 'normals', 'UCX', 'IDs']
    assert row['rgb_srgb'] == KPP_RGB_BY_RAL['5015']
    summary = data['panel_joints']
    assert summary['joints'] is True
    assert summary['map_type'] == 'joints'
    assert summary['vertical_only'] is True
    assert summary['joint_orientation'] == 'vertical_only'
    assert summary['horizontal_joints'] is False
    assert summary['module_m'] == pytest.approx(SHEET_STEP_M)
    assert summary['step_m'] == pytest.approx(SHEET_STEP_M)
    assert summary['texel_px_per_m'] == 1000
    assert summary['phase_anchor'] == 'panel_field_symmetric'
    assert summary['below_zero_joints'] is False
    assert summary['superseded_0_60_m']['module_m'] == pytest.approx(0.60)
    assert summary.get('source_udim') != 1007
    assert summary['source_sha256'] == ARTEM_PANEL_SHA256
    assert '1007' in summary['superseded']
    assert 'not the panel source' in summary['superseded'].lower()
    assert 'all TEC26' in summary['applies_to']


def test_per_facade_rib_counts_from_the_colour_sheet():
    """Known counts are positive ints. Facade 2-1 stays '?' with the question."""
    _, joints = _id2_joints(load())
    assert joints['horizontal_joints'] is False
    assert joints['vertical_only'] is True
    facades = joints['facades']
    assert set(facades) == {'1-2', 'A-B', 'B-A', '2-1'}
    for name, count in FACADE_RIBS.items():
        assert facades[name]['vertical_ribs'] == count
        assert isinstance(facades[name]['vertical_ribs'], int)
        assert facades[name]['vertical_ribs'] > 0
        assert facades[name]['step_m'] == pytest.approx(SHEET_STEP_M)
    open_side = facades['2-1']
    assert open_side['vertical_ribs'] == '?'
    assert open_side['question'] == FACADE_2_1_QUESTION
    assert load()['questions'] == [
        {'facade': '2-1', 'vertical_ribs': '?', 'question': FACADE_2_1_QUESTION}
    ]


def test_count_times_step_fits_panel_field_width():
    """count * step stays inside the mesh plan extent of that facade (non-negative slack)."""
    _, joints = _id2_joints(load())
    step = joints['step_m']
    assert step > 0
    census = json.loads((JOB / 'scene-census.json').read_text(encoding='utf-8'))
    mesh = next(obj for obj in census['objects'] if obj['handle'] == 172)
    (xmin, ymin, _), (xmax, ymax, _) = mesh['bbox_native']
    long_m = xmax - xmin
    short_m = ymax - ymin
    width_by_facade = {'1-2': long_m, '2-1': long_m, 'A-B': short_m, 'B-A': short_m}
    assert long_m > short_m > 0
    for name, facade in joints['facades'].items():
        width = width_by_facade[name]
        assert width > 0
        count = facade['vertical_ribs']
        if count == '?':
            continue
        assert isinstance(count, int) and count > 0
        slack = width - count * step
        assert slack >= 0


def test_texture_role_is_joint_look_not_tiling_source():
    _, joints = _id2_joints(load())
    source = joints['source']
    assert source['role'] == 'colour_noise_joint_look'
    assert source['role'] != 'tiling source'
    assert 'tiling' not in source['role'].lower()
    assert source['tiling_source'] is False
    summary = load()['panel_joints']
    assert summary['source_role'] == 'colour_noise_joint_look'
    assert summary['source_role'] != 'tiling source'


def test_frame_band_and_plinth_strip_follow_the_sheet():
    _, joints = _id2_joints(load())
    band = joints['frame_band']
    assert band['tone'] == 'darker'
    assert band['edges'] == ['top', 'bottom', 'corners']
    assert band['outlines'] == 'panel field'
    plinth = joints['plinth_strip']
    assert plinth['colour'] == 'grey'
    assert plinth['ral'] == '7004'
    assert plinth['rgb_srgb'] == KPP_RGB_BY_RAL['7004']
    assert plinth['basis'] == 'per-sheet'
    door = next(x for x in load()['materials'] if x['id'] == 3)
    assert door['ral'] == '7004'
    assert door['rgb_srgb'] == KPP_RGB_BY_RAL['7004']
    assert door['map_type'] == 'solid'


def test_acceptance_picture_required_before_asking_artem():
    data = load()
    picture = data['acceptance_picture']
    assert picture['required'] is True
    assert 'build card' in picture['when'].lower()
    assert 'before asking artem' in picture['when'].lower()
    content = picture['content'].lower()
    assert 'each facade' in content
    assert 'same scale' in content
    assert 'rib count' in content
    assert 'sheet' in content
    ref = picture['reference'].replace('\\', '/')
    assert ref.endswith('user-refs/AC08_facades_colour_from_artem.jpg')
    md = (JOB / 'MATERIALS.md').read_text(encoding='utf-8').lower()
    assert 'acceptance picture' in md
    assert 'same scale' in md
    assert 'rib count' in md


def test_below_ground_drop_has_no_joints():
    data = load()
    row = next(x for x in data['materials'] if x['id'] == 1)
    parts = {p['role']: p for p in row['parts']}
    drop = parts['foundation_drop']
    assert drop['map_type'] == 'solid'
    assert drop.get('joints') in (None, False)
    assert drop['ral'] == '5015'
    assert drop['rgb_srgb'] == KPP_RGB_BY_RAL['5015']
    assert data['panel_joints']['below_zero_joints'] is False
    assert parts['roof']['map_type'] == 'solid'
    assert parts['frame']['map_type'] == 'solid'
    door = next(x for x in data['materials'] if x['id'] == 3)
    assert door['map_type'] == 'solid'
    assert door.get('joints') in (None, False)


def test_no_finish_claims_joints_without_the_artem_file():
    data = load()
    claimed = []
    for target in _finish_targets(data):
        claims = target.get('map_type') == 'joints' or isinstance(target.get('joints'), dict)
        if not claims:
            continue
        claimed.append(target)
        joints = target['joints']
        assert joints['joint_orientation'] == 'vertical_only'
        assert joints['horizontal_joints'] is False
        source = joints['source']
        assert source['path'].endswith('panel_RAL5015_vertical_joints_4096.png')
        assert source['sha256'] == ARTEM_PANEL_SHA256
        assert len(source['sha256']) == 64
    assert [t.get('id') for t in claimed] == [2]


def test_artem_mean_stays_inside_kpp_flat_tolerance():
    """Texture mean (34,112,177) vs KPP flat (34,113,179). ID1 drop keeps the wall colour."""
    data = load()
    row = next(x for x in data['materials'] if x['id'] == 2)
    mean = row['joints']['source']['mean_rgb']
    wall = KPP_RGB_BY_RAL['5015']
    assert mean == ARTEM_PANEL_MEAN_RGB
    assert row['rgb_srgb'] == wall
    assert max(abs(a - b) for a, b in zip(mean, wall)) <= ARTEM_MEAN_KPP_TOLERANCE
    drop = next(
        p for p in next(x for x in data['materials'] if x['id'] == 1)['parts']
        if p['role'] == 'foundation_drop'
    )
    assert drop['rgb_srgb'] == wall
    assert drop['ral'] == '5015'
    assert drop['map_type'] == 'solid'


def test_panel_source_sha256_matches_file_when_present():
    data = load()
    recorded = next(x for x in data['materials'] if x['id'] == 2)['joints']['source']['sha256']
    assert recorded == ARTEM_PANEL_SHA256
    assert data['panel_joints']['source_sha256'] == recorded
    if not ARTEM_PANEL_TEXTURE.is_file():
        pytest.skip('Artem panel texture is not on this machine')
    import hashlib
    digest = hashlib.sha256(ARTEM_PANEL_TEXTURE.read_bytes()).hexdigest()
    assert recorded == digest


def test_panel_joints_solid_and_no_glass_id():
    data = load()
    glass = data['glass']
    assert glass['observed'] is False
    assert glass['id'] is None
    assert glass['rule'] == 'as KPP'
    scope = data['scope']
    assert scope['colouring_only'] is True
    assert scope['builds_in_this_card'] is False
    assert '559' in scope['build_note']


def test_materials_md_records_approval_and_separate_build():
    text = (JOB / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'approved-gate1' in text
    assert 'Принимаю' in text
    assert 'STOP' not in text
    assert 'awaiting Artem' not in text
    lowered = text.lower()
    assert 'separate card' in lowered
    assert 'builds nothing' in lowered or 'builds nothing' in text
    # Original Gate-1 answer stays on record; the same-day instruction replaces it.
    assert 'solid colour, no joints' in lowered
    assert 'Не вижу швов на панелях' in text
    assert 'ниже ±0.000 без швов' in text
    assert 'Панели неверные, должны быть вертикальные швы только' in text
    assert 'panel_RAL5015_vertical_joints_4096.png' in text
    assert 'vertical joints only' in lowered
    assert 'no horizontal joints' in lowered
    assert '0.60' in text
    assert '0.20' in text
    assert '1000 px/m' in text
    assert 'edge loop' in lowered
    assert 'all tec26' in lowered
    assert '30' in text and '12' in text
    assert FACADE_2_1_QUESTION in text
    assert 'symmetric' in lowered
    assert 'frame band' in lowered
    assert 'plinth' in lowered
    assert 'per-sheet' in lowered
    assert 'not a tiling source' in lowered
    assert '4k tile' in lowered
    assert 'acceptance picture' in lowered
    # Cassette tile 1007 stays only as the superseded rule.
    assert 'T_Kpp_1_Diffuse_1.1007' in text
    assert 'superseded' in lowered
    assert 'not the panel source' in lowered
    assert lowered.count('no joints') == 1


def test_manifest_cites_files_and_untrusted_recovery():
    data = load()
    assert data['drawing']['sha256'] == 'cb90ed375df4fd708b7a69c6d018600347953245f0f6bde396f394bee3e1fa52'
    assert data['drawing']['recovery_fixes'] == 2
    assert data['drawing']['native_plot_verified'] is False
    assert len(data['evidence_files']) >= 8
    assert all(len(x['sha256']) == 64 and x['bytes'] > 0 for x in data['evidence_files'])
    assert data['contact_sheet'].endswith('/contact-sheet.png')
    assert (JOB / 'MATERIALS.md').is_file()
