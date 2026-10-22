"""new-case: AC06 Gate-1 colouring approval.

Safer reading of build_allowed: Artem approved colouring only. This card must
not authorize VPM/NPM construction, so build_allowed stays false for a later
card. Status is approved-gate1 and approved is true.
"""
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'jobs/TEC26-OKS/AC06/materials.json'
MARKDOWN = ROOT / 'jobs/TEC26-OKS/AC06/MATERIALS.md'

GATE1_QUOTE = """Принимаю
1. Sandwich panels: solid colour without joints (module not confirmed in drawings).
2. Roof: RAL 7004 grey (as KPP 7004), NOT 5015.
3. Mixed ID: parts may be painted differently (roof 7004, frame 7004, plinth/drop = wall colour) without geometry change - via UV/atlas regions or face-group split inside the same ID.
4. Panels RAL 5015 = KPP blue, doors/frames/porches RAL 7004 = KPP grey, glass as KPP; drop below ±0.000 = wall colour.
AC06 specifically: ID1 roof 7004; ID5 strips over entrances RAL 9016 (luminaires: colour only, no emission); ID6 ventilation 7004; ID9 window reveals 9016; ID11 interior box = KPP Interior.
Scope (Artem): only colouring; geometry, topology, UCX and multisub IDs stay exactly as in the source scene. Later cards build VPM (UDIM) / NPM (2048 atlas); do NOT build them here. Geometry checks are reported only, never fixed."""

# Previously proposed rows, now approved without a finish change.
KEPT = {
    2: ('Canopies and roof trims', '5015', 'metal'),
    3: ('Wall sandwich panels', '7047', 'solid'),
    4: ('Rainwater downpipes', '7004', 'metal'),
    7: ('Doors', '7004', 'metal'),
    8: ('Lightweight relief glazing frames', '9016', 'metal'),
    10: ('Plinth', '7004', 'solid'),
    12: ('Glazing', None, 'glass'),
}


class MaterialTableError(ValueError):
    def __init__(self, material_id, reason):
        self.material_id = material_id
        self.reason = reason
        if material_id is None:
            message = reason
        else:
            message = f'ID {material_id}: {reason}'
        super().__init__(message)


def load_packet():
    return json.loads(PACKET.read_text(encoding='utf-8'))


def validate_ac06_material_table(data):
    """Every material ID 1..12 is in the table once, approved, evidenced, finite area.

    Empty table, duplicate id, empty area and NaN area are errors. An approved
    row without evidence is an error. A RAL whose swatch is not the KPP colour
    for that same RAL is an error. The message names the material ID.
    """
    if data.get('status') != 'approved-gate1':
        raise MaterialTableError(None, 'status is not approved-gate1')
    if data.get('approved') is not True:
        raise MaterialTableError(None, 'approved is not true')
    # Colouring approval does not authorize this card to build VPM/NPM.
    if data.get('build_allowed') is not False:
        raise MaterialTableError(None, 'build_allowed must stay false until a later card')
    rows = data.get('materials')
    if not rows:
        raise MaterialTableError(None, 'empty material table')
    colours = data.get('kpp_colours') or {}
    seen = set()
    for row in rows:
        mid = row.get('id')
        if mid in seen:
            raise MaterialTableError(mid, 'duplicate material id')
        seen.add(mid)
        area = row.get('area_m2', None)
        if area is None or area == '':
            raise MaterialTableError(mid, 'empty area')
        try:
            area_value = float(area)
        except (TypeError, ValueError):
            raise MaterialTableError(mid, 'empty or NaN area')
        if not math.isfinite(area_value):
            raise MaterialTableError(mid, 'NaN area')
        if area_value <= 0:
            raise MaterialTableError(mid, 'empty area')
        finish = row.get('finish')
        if finish in (None, '', '?'):
            raise MaterialTableError(mid, 'unresolved finish')
        if row.get('map_type') in (None, '', '?'):
            raise MaterialTableError(mid, 'unmapped')
        if row.get('status') != 'approved':
            raise MaterialTableError(mid, 'not approved')
        if row.get('question'):
            raise MaterialTableError(mid, 'open question')
        if not row.get('evidence'):
            raise MaterialTableError(mid, 'approved without evidence')
        ral = row.get('ral')
        if ral is not None:
            expected = colours.get(ral, {}).get('rgb')
            if row.get('swatch_rgb') != expected:
                raise MaterialTableError(mid, f'RAL {ral} differs from KPP colour')
    missing = [i for i in range(1, 13) if i not in seen]
    if missing:
        raise MaterialTableError(missing[0], 'missing from table')
    extra = sorted(i for i in seen if i not in range(1, 13))
    if extra:
        raise MaterialTableError(extra[0], 'outside material ids 1..12')


def test_ac06_complete_measured_id_inventory():
    data = load_packet()
    rows = data['materials']
    assert [r['id'] for r in rows] == list(range(1, 13))
    assert [r['triangles'] for r in rows] == [362,1290,444,1576,48,300,204,1008,60,176,128,12]
    assert sum(r['triangles'] for r in rows) == 5608
    assert all(math.isfinite(r['area_m2']) and r['area_m2'] > 0 for r in rows)
    for row in rows:
        assert row['evidence'], f"ID {row['id']} approved without evidence"
    assert data['scene']['layer_actual'] == '006'
    assert len(data['scene']['collision_candidates']) == 21


def test_ac06_gate1_colouring_approved_build_stays_closed():
    data = load_packet()
    validate_ac06_material_table(data)
    assert data['status'] == 'approved-gate1'
    assert data['approved'] is True
    assert data['build_allowed'] is False
    assert 'later' in data['build_allowed_reason'].lower()
    assert data['gate1_approval']['date'] == '2026-10-22'
    assert data['gate1_approval']['decision'] == 'Принимаю'
    assert data['gate1_approval']['quote'] == GATE1_QUOTE
    rows = {r['id']: r for r in data['materials']}
    assert not any(r['finish'] in (None, '', '?') or r['map_type'] in (None, '', '?') for r in rows.values())
    assert all(r['status'] == 'approved' and not r['question'] for r in rows.values())
    assert rows[1]['finish'] == 'Roof sandwich panels and upper fascia'
    assert rows[1]['ral'] == '7004' and rows[1]['map_type'] == 'solid'
    assert rows[1]['swatch_rgb'] == data['kpp_colours']['7004']['rgb']
    assert rows[5]['finish'] == 'Strips over entrances'
    assert rows[5]['ral'] == '9016' and rows[5]['map_type'] == 'solid'
    assert rows[5]['emission'] is False
    assert rows[6]['finish'] == 'Ventilation assemblies'
    assert rows[6]['ral'] == '7004' and rows[6]['map_type'] == 'metal'
    assert rows[9]['finish'] == 'Window reveals'
    assert rows[9]['ral'] == '9016' and rows[9]['map_type'] == 'solid'
    assert rows[11]['finish'] == 'KPP Interior'
    assert rows[11]['ral'] is None and rows[11]['map_type'] == 'solid'
    assert rows[11]['swatch_rgb'] == rows[11]['kpp_colour']['rgb']
    assert len(rows[11]['kpp_colour']['sha256']) == 64
    for mid, (finish, ral, map_type) in KEPT.items():
        assert rows[mid]['finish'] == finish, f'ID {mid} finish changed'
        assert rows[mid]['ral'] == ral, f'ID {mid} RAL changed'
        assert rows[mid]['map_type'] == map_type, f'ID {mid} map type changed'
    rule = data['mixed_id_rule']
    assert rule['geometry_change'] is False
    assert rule['roof'] == '7004'
    assert rule['frame'] == '7004'
    assert rule['plinth_and_drop'] == 'wall colour'
    drop = rule['drop_below_pm_0_000']
    assert drop['takes'] == 'wall colour'
    assert drop['wall_id'] == 3 and drop['ral'] == '7047'
    assert drop['geometry_change'] is False
    assert 'KPP 7004' in data['contact_sheet_note']
    assert 'ID1' in data['contact_sheet_note'] or 'ID 1' in data['contact_sheet_note']
    text = MARKDOWN.read_text(encoding='utf-8')
    assert GATE1_QUOTE in text
    assert 'Gate-1 answers' in text
    assert 'Gate-1 questions for Artem' not in text
    assert 'KPP 7004' in text
    assert 'wall colour' in text


def test_ac06_unresolved_id_probe():
    """invariant: no ID left unresolved / every ID ends in the table.

    Brute-force probe over IDs 1..12: empty area, duplicate id and NaN area
    each raise MaterialTableError naming that ID. Synthetic inputs only.
    """
    data = load_packet()
    validate_ac06_material_table(data)
    passed = 0
    for mid in range(1, 13):
        for kind in ('empty', 'duplicate', 'nan'):
            bad = copy.deepcopy(data)
            rows = bad['materials']
            row = next(item for item in rows if item['id'] == mid)
            if kind == 'empty':
                row['area_m2'] = None
            elif kind == 'duplicate':
                rows.append(copy.deepcopy(row))
            else:
                row['area_m2'] = float('nan')
            try:
                validate_ac06_material_table(bad)
            except MaterialTableError as exc:
                assert exc.material_id == mid, f'ID {mid} {kind} named {exc.material_id}'
                passed += 1
            else:
                raise AssertionError(f'ID {mid} {kind} area input was accepted')
        stripped = copy.deepcopy(data)
        next(item for item in stripped['materials'] if item['id'] == mid)['evidence'] = []
        try:
            validate_ac06_material_table(stripped)
        except MaterialTableError as exc:
            assert exc.material_id == mid
            assert 'evidence' in exc.reason
        else:
            raise AssertionError(f'ID {mid} approved without evidence was accepted')
        ral = next(item for item in data['materials'] if item['id'] == mid)['ral']
        if ral is not None:
            shifted = copy.deepcopy(data)
            target = next(item for item in shifted['materials'] if item['id'] == mid)
            target['swatch_rgb'] = [0, 0, 0]
            try:
                validate_ac06_material_table(shifted)
            except MaterialTableError as exc:
                assert exc.material_id == mid
                assert 'differs from KPP colour' in exc.reason
            else:
                raise AssertionError(f'ID {mid} RAL {ral} mismatch was accepted')
    empty = copy.deepcopy(data)
    empty['materials'] = []
    try:
        validate_ac06_material_table(empty)
    except MaterialTableError as exc:
        assert exc.material_id is None
        assert 'empty' in exc.reason
    else:
        raise AssertionError('empty material table was accepted')
    assert passed == 36


def test_ac06_drawing_codes_are_own_building_not_kpp_inference():
    data = load_packet()
    assert data['building_name'] == 'Пункт редуцирования газа 1'
    assert {r['ral'] for r in data['drawing_finishes']} == {'5015', '7047', '7004', '9016'}
    assert all('136EBB' in r['locator'] for r in data['drawing_finishes'])
    assert data['pdf']['physical_pages'] == 1
    assert data['pdf']['printed_sheet'] == '2'
    assert all(r['status'] == 'approved' for r in data['materials'])


def test_ac06_kpp_colour_reuse_has_hashed_pixel_provenance():
    data = load_packet()
    assert set(data['kpp_colours']) == {'5015', '7047', '7004', '9016'}
    for ral, colour in data['kpp_colours'].items():
        assert colour['ral'] == ral
        assert len(colour['sha256']) == 64
        assert len(colour['rgb']) == 3
        assert all(type(v) is int and 0 <= v <= 255 for v in colour['rgb'])
        assert colour['method'] == 'most_frequent_rgb_pixel'
    for row in data['materials']:
        if row['ral'] is not None:
            assert row['swatch_rgb'] == data['kpp_colours'][row['ral']]['rgb'], (
                f"ID {row['id']} RAL {row['ral']} differs from KPP colour"
            )


def test_ac06_evidence_is_external_and_no_final_delivery_claim():
    data = load_packet()
    assert data['evidence_directory'] == 'G:/Мой диск/AGR-evidence/tec26-oks/AC06/evidence-v004'
    assert len(data['inputs']) >= 4
    assert all(len(r['sha256']) == 64 for r in data['inputs'])
    assert data['scene']['diagnostic_render_method'] == 'Blender 5.1.2 headless Cycles CPU; exact triangle readback; depth-correct shaded and ID pairs'
    assert (ROOT / 'jobs/TEC26-OKS/AC06/MATERIALS.md').is_file()
    assert data['build_allowed'] is False


class PanelJointError(ValueError):
    pass


def blue_ral5015_wall_panel_rows(data):
    """Approved IDs whose finish is a blue RAL 5015 sandwich wall panel.

    RAL 5015 metal canopies and trims stay out of this set unless the finish
    also says they are wall panels.
    """
    found = []
    for row in data.get('materials') or []:
        if row.get('status') != 'approved':
            continue
        if str(row.get('ral')) != '5015':
            continue
        finish = (row.get('finish') or '').lower()
        canopy_or_trim = ('canop' in finish) or ('trim' in finish)
        wall_panel = ('wall' in finish) and ('panel' in finish or 'sandwich' in finish)
        if canopy_or_trim and not wall_panel:
            continue
        if wall_panel or ('sandwich' in finish and 'panel' in finish):
            found.append(row)
    return found


def _count_or_step_closed(value, sheet_evidence, question):
    """A number needs sheet evidence. '?' needs a question. Anything else fails."""
    if value == '?':
        return isinstance(question, str) and bool(question.strip())
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if value <= 0:
        return False
    return bool(sheet_evidence)


def validate_panel_texture_rules(data):
    rules = data.get('panel_texture_rules')
    if not isinstance(rules, dict):
        raise PanelJointError('missing panel_texture_rules')
    if rules.get('joint_style') != 'vertical_ribs':
        raise PanelJointError('joint style is not vertical_ribs')
    if rules.get('vertical_only') is not True or rules.get('horizontal_joints') is not False:
        raise PanelJointError('joints are not vertical-only')
    if rules.get('below_zero') != 'plain' or rules.get('below_zero_joints') is not False:
        raise PanelJointError('below ±0.000 is not plain colour without joints')
    gate = data.get('gate1_approval') or {}
    if 'solid colour without joints' not in (gate.get('quote') or ''):
        raise PanelJointError('gate-1 item 1 quote was dropped')
    if not gate.get('superseded_by'):
        raise PanelJointError('gate-1 item 1 is not marked superseded_by')
    facades = rules.get('facades')
    if not isinstance(facades, list) or not facades:
        raise PanelJointError('missing per-facade count and step')
    for facade in facades:
        count = facade.get('vertical_ribs')
        step = facade.get('step')
        evidence = facade.get('sheet_evidence')
        question = facade.get('question')
        if not _count_or_step_closed(count, evidence, question):
            raise PanelJointError(f"facade {facade.get('label')} rib count fails closed")
        if not _count_or_step_closed(step, evidence, question):
            raise PanelJointError(f"facade {facade.get('label')} step fails closed")
    panel_ids = [row['id'] for row in blue_ral5015_wall_panel_rows(data)]
    if rules.get('switched_ids') != panel_ids:
        raise PanelJointError('switched_ids does not match blue RAL 5015 wall panels')
    for row in blue_ral5015_wall_panel_rows(data):
        if row.get('map_type') != 'joints':
            raise PanelJointError(f"ID {row.get('id')} map_type is not joints")
        joints = row.get('joints')
        if not isinstance(joints, dict):
            raise PanelJointError(f"ID {row.get('id')} missing joints")
        if joints.get('joint_style') != 'vertical_ribs':
            raise PanelJointError(f"ID {row.get('id')} joint style is not vertical_ribs")
        if joints.get('vertical_only') is not True or joints.get('horizontal_joints') is not False:
            raise PanelJointError(f"ID {row.get('id')} is not vertical-only")
        if joints.get('below_zero') != 'plain':
            raise PanelJointError(f"ID {row.get('id')} below zero is not plain")
        if not _count_or_step_closed(joints.get('vertical_ribs'), joints.get('sheet_evidence'), joints.get('question')):
            raise PanelJointError(f"ID {row.get('id')} rib count fails closed")
        if not _count_or_step_closed(joints.get('step'), joints.get('sheet_evidence'), joints.get('question')):
            raise PanelJointError(f"ID {row.get('id')} step fails closed")
    for row in data.get('materials') or []:
        finish = (row.get('finish') or '').lower()
        if str(row.get('ral')) == '5015' and 'canop' in finish and 'wall' not in finish:
            if row.get('map_type') != 'metal':
                raise PanelJointError(f"ID {row.get('id')} canopy/trim was switched off metal")


def test_ac06_panel_texture_rules_supersede_solid_without_joints():
    data = load_packet()
    validate_panel_texture_rules(data)
    rules = data['panel_texture_rules']
    assert rules['joint_style'] == 'vertical_ribs'
    assert rules['vertical_only'] is True
    assert rules['horizontal_joints'] is False
    assert rules['below_zero'] == 'plain'
    assert rules['below_zero_joints'] is False
    assert rules['texel_px_per_m'] == 1000
    assert rules['vpm_maps'] == ['diffuse', 'normal']
    assert rules['npm_joints_min_px'] == 1.5
    assert rules['doors_ral'] == '7004'
    assert rules['plinth_strip'] == 'grey'
    assert rules['frame_band']['tone'] == 'darker'
    assert rules['frame_band']['edges'] == ['top', 'bottom', 'corners']
    texture = rules['texture']
    assert texture['path'].replace('\\', '/').endswith(
        'user-textures/panel_RAL5015_vertical_joints_4096.png'
    )
    assert texture['width_px'] == 4096
    assert texture['mean_rgb'] == [34, 112, 177]
    assert texture['joint_px'] == 8
    assert texture['tiling_source'] is False
    assert texture['role'] == 'colour_noise_joint_look'
    assert [facade['label'] for facade in rules['facades']] == ['1-3', '3-1', 'А-Д', 'Д-А']
    for facade in rules['facades']:
        assert facade['vertical_ribs'] == '?'
        assert facade['step'] == '?'
        assert not facade.get('sheet_evidence')
        assert 'Цветовое решение' in facade['question']
        assert facade['label'] in facade['question']
        assert '0.20' in facade['question'] or '0.2' in facade['question']
    assert rules['switched_ids'] == []
    assert blue_ral5015_wall_panel_rows(data) == []
    assert rules.get('step_m', '?') == '?'
    assert rules.get('module_m', '?') == '?'
    rows = {row['id']: row for row in data['materials']}
    assert rows[2]['ral'] == '5015' and rows[2]['map_type'] == 'metal'
    assert rows[3]['ral'] == '7047' and rows[3]['map_type'] == 'solid'
    cut = rules['edge_cut']
    assert cut['record_only'] is True
    assert cut['quads_kept'] is True
    assert cut['unchanged'] == ['silhouette', 'normals', 'UCX', 'IDs']
    picture = rules['acceptance_picture']
    assert 'same scale' in picture['content'].lower()
    assert 'rib count' in picture['content'].lower()
    gate = data['gate1_approval']
    assert gate['quote'] == GATE1_QUOTE
    assert 'panel_texture_rules' in json.dumps(gate['superseded_by'])
    text = MARKDOWN.read_text(encoding='utf-8')
    assert 'Panel texture rules (supersede solid-without-joints)' in text
    assert GATE1_QUOTE in text
    assert data['build_allowed'] is False


def test_ac06_panel_count_step_fails_closed():
    """Numbers without sheet evidence, bare '?', and horizontal joints are rejected."""
    data = load_packet()
    validate_panel_texture_rules(data)

    def reject(mutate):
        bad = copy.deepcopy(data)
        mutate(bad)
        try:
            validate_panel_texture_rules(bad)
        except PanelJointError:
            return
        raise AssertionError('invalid panel joint packet was accepted')

    reject(lambda bad: bad.pop('panel_texture_rules'))
    reject(lambda bad: bad['gate1_approval'].pop('superseded_by'))
    reject(lambda bad: bad['panel_texture_rules'].update(horizontal_joints=True))
    reject(lambda bad: bad['panel_texture_rules'].update(below_zero='joints', below_zero_joints=True))
    reject(lambda bad: bad['panel_texture_rules']['facades'][0].update(
        vertical_ribs=30, step=0.20, sheet_evidence=None,
    ))
    reject(lambda bad: bad['panel_texture_rules']['facades'][0].update(
        vertical_ribs='?', step='?', question='',
    ))
    reject(lambda bad: bad['panel_texture_rules']['facades'][0].update(
        vertical_ribs=12, step=0.6, sheet_evidence='',
    ))

    def paint_id3_as_blue_wall(bad, **joints):
        row = next(item for item in bad['materials'] if item['id'] == 3)
        row['ral'] = '5015'
        row['finish'] = 'Wall sandwich panels'
        row['map_type'] = joints.pop('map_type', 'solid')
        if 'joints' in joints:
            row['joints'] = joints['joints']
        bad['panel_texture_rules']['switched_ids'] = [3]

    reject(lambda bad: paint_id3_as_blue_wall(bad))
    reject(lambda bad: paint_id3_as_blue_wall(bad, map_type='joints', joints={
        'joint_style': 'vertical_ribs',
        'vertical_only': True,
        'horizontal_joints': False,
        'below_zero': 'plain',
        'vertical_ribs': 30,
        'step': 0.20,
        'sheet_evidence': None,
        'question': 'invented',
    }))
    kept = copy.deepcopy(data)
    paint_id3_as_blue_wall(kept, map_type='joints', joints={
        'joint_style': 'vertical_ribs',
        'vertical_only': True,
        'horizontal_joints': False,
        'below_zero': 'plain',
        'vertical_ribs': '?',
        'step': '?',
        'sheet_evidence': None,
        'question': 'Rib count and step are not dimensioned on this AC06 facade sheet.',
    })
    validate_panel_texture_rules(kept)
