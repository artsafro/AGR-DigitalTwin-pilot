"""new-case: AC04 Gate-1 paint may be approved while delivery stays unpassed.

RAL5015 panels are vertical joints only. Gate-1 point 1 (solid, no joints) is superseded.
"""
import hashlib
import json
import math
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'jobs/TEC26-OKS/AC04'

ALLOWED_GATE_STATUS = ('awaiting_artem', 'approved-gate1')
# KPP tiles already pinned in this building's material evidence (sRGB bytes).
KPP_RALS = {
    'RAL5015': [34, 113, 179],
    'RAL7004': [150, 153, 146],
    'RAL1021': [238, 201, 0],
}
KPP_GREY_SHA = '765b8504bfb70793698a541cfd88cf839a0c5bbf6cb3cb3b76cb52bacd382969'
QUOTE_MARKS = (
    'Sandwich panels: solid colour without joints',
    'Roof: RAL 7004 grey (as KPP 7004), not 5015.',
    'WITHOUT changing geometry',
    'small frames of ID4 = RAL 7004',
)
# Provisioned publication input. Default unit tests must not read this file.
# Marker panel_texture requires this path and PANEL_TEXTURE_SHA.
PANEL_TEXTURE = 'C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png'
PANEL_TEXTURE_SHA = '2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece'
# In-memory stand-in for validator mutation tests. synthetic=True; not publication evidence.
SYNTHETIC_PANEL_BYTES = b'synthetic-ac04-panel-joints-v1'
SYNTHETIC_PANEL_SHA = hashlib.sha256(SYNTHETIC_PANEL_BYTES).hexdigest()
SYNTHETIC_PANEL_PATH = 'synthetic://ac04/panel_RAL5015_vertical_joints'
PANEL_QUOTE = (
    'Панели неверные, должны быть вертикальные швы только; текстуру пришлю; '
    'если не влезает, можно аккуратно порезать через loop или ring'
)
BELOW_GRADE_QUOTE = 'ниже ±0.000 без швов (под землёй не видно)'
POSITIVE_FINITE_KEYS = ('joint_width_mm', 'texel_px_per_m')
WIDTH_TOLERANCE = 0.02
SHEET_FACADES = (
    'Фасад А-В. Цветовое решение',
    'Фасад 1-2. Цветовое решение',
    'Фасад В-А. Цветовое решение',
    'Фасад 2-1. Цветовое решение',
)
# KPP 5015 versus the whole-texture mean. Joints darken the mean; 2 sRGB units
# covers the measured gap (max abs channel delta about 1.57).
COLOUR_TOLERANCE_MAX_ABS = 2.0


def load():
    return json.loads((ROOT / 'materials.json').read_text(encoding='utf-8'))


def _id_label(material):
    return f"ID {material.get('id')}"


def validate_gate1(doc):
    """Fail closed: unknown gate status, a material with no finish, or a RAL outside KPP/JSON."""
    status = doc.get('gate_1_status')
    if status not in ALLOWED_GATE_STATUS:
        raise ValueError(
            f'gate_1_status {status!r} is not allowed; '
            f'allowed values are {ALLOWED_GATE_STATUS[0]} and {ALLOWED_GATE_STATUS[1]}'
        )
    for material in doc['materials']:
        label = _id_label(material)
        finish = material.get('finish')
        if not isinstance(finish, str) or not finish.strip() or finish.strip() == '?':
            raise ValueError(f'{label} has no finish')
        _require_known_ral(label, material.get('ral'), allow_null=True)
        for region in material.get('regions') or []:
            part = region.get('part', '?')
            _require_known_ral(f'{label} region {part}', region.get('ral'), allow_null=False)


def _require_known_ral(label, ral, allow_null):
    if ral is None and allow_null:
        return
    if ral not in KPP_RALS:
        raise ValueError(f'{label} RAL {ral!r} not found in KPP/JSON')


def _walk_finish_nodes(doc):
    """Yield (label, node, is_ral5015_panel) for each material and ID1 region."""
    for material in doc['materials']:
        label = _id_label(material)
        yield label, material, material.get('id') == 2
        for region in material.get('regions') or []:
            part = region.get('part', '?')
            is_panel = material.get('id') == 1 and part == 'wall panels'
            yield f'{label} region {part}', region, is_panel


def _positive_finite(label, spec, key):
    value = spec.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{label} {key} must be a positive finite number, got {value!r}')


def _facade_name(facade):
    name = facade.get('facade')
    if not isinstance(name, str) or not name.strip():
        return '?'
    return name


def _require_resolved_facade(label, facade):
    """A counted facade has an integer rib count and a positive step.

    When the panel-field width is recorded, count times step stays strictly inside 2%.
    A ratio of exactly 2% is an error.
    """
    name = _facade_name(facade)
    count = facade.get('rib_count')
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(
            f'{label} facade {name} rib_count must be an integer >= 1, got {count!r}'
        )
    step = facade.get('step_m')
    if isinstance(step, bool) or not isinstance(step, (int, float)) or not math.isfinite(step) or step <= 0:
        raise ValueError(
            f'{label} facade {name} step_m must be a positive finite number, got {step!r}'
        )
    width = facade.get('field_width_m')
    if width is None:
        return
    if isinstance(width, bool) or not isinstance(width, (int, float)) or not math.isfinite(width) or width <= 0:
        raise ValueError(
            f'{label} facade {name} field_width_m must be a positive finite number, got {width!r}'
        )
    ratio = abs(count * float(step) - float(width)) / float(width)
    if not math.isfinite(ratio) or ratio >= WIDTH_TOLERANCE:
        raise ValueError(
            f'{label} facade {name} rib_count * step_m is not strictly within 2% of the panel-field width'
        )


def _require_per_facade(label, spec):
    if 'module_m' in spec:
        raise ValueError(
            f'{label} module_m is not the panel step; per_facade is required and 0.60 is not a fallback'
        )
    facades = spec.get('per_facade')
    if not isinstance(facades, list) or len(facades) == 0:
        raise ValueError(f'{label} per_facade must be a non-empty list')
    for facade in facades:
        if not isinstance(facade, dict):
            raise ValueError(f'{label} per_facade entry must be an object')
        name = _facade_name(facade)
        if facade.get('status') == 'unresolved':
            question = facade.get('question')
            if not isinstance(question, str) or not question.strip():
                raise ValueError(f'{label} facade {name} is unresolved without a question')
            continue
        _require_resolved_facade(label, facade)


def unresolved_facade_report(doc):
    """Names of facades whose rib count is not settled. Does not change gate status."""
    names = []
    for _label, node, is_panel in _walk_finish_nodes(doc):
        if not is_panel:
            continue
        spec = node.get('joint_spec') or {}
        for facade in spec.get('per_facade') or []:
            if isinstance(facade, dict) and facade.get('status') == 'unresolved':
                name = _facade_name(facade)
                if name not in names:
                    names.append(name)
    return names


def validate_panel_joints(doc, read_bytes=None):
    """RAL5015 panels are vertical joints only; every other finish stays free of panel joints.

    The joint step is per facade from the colour sheet. A fixed module_m is not a fallback.
    An unresolved facade must carry a question. It does not by itself revoke gate approval;
    unresolved_facade_report lists it.
    Fail closed: a horizontal orientation, a bad rib count (the error names the facade),
    a non-positive step, a count whose field-width ratio is 2% or more,
    a below-grade value other than plain, empty or unsupported texture bytes,
    or a texture SHA256 that does not match the file.
    read_bytes defaults to Path(path).read_bytes(). Unit tests pass an in-memory reader.
    """
    if read_bytes is None:
        def read_bytes(path):
            return Path(path).read_bytes()
    for label, node, is_panel in _walk_finish_nodes(doc):
        if not is_panel:
            if node.get('map_type') == 'vertical_joints' or 'joint_spec' in node:
                raise ValueError(f'{label} must not carry panel joints')
            continue
        if node.get('map_type') != 'vertical_joints':
            raise ValueError(
                f'{label} map_type must be vertical_joints, got {node.get("map_type")!r}'
            )
        spec = node.get('joint_spec')
        if not isinstance(spec, dict):
            raise ValueError(f'{label} joint_spec is missing')
        orientation = spec.get('orientation')
        if orientation != 'vertical_only':
            raise ValueError(
                f'{label} joint_spec orientation must equal vertical_only; '
                f'horizontal joints are not allowed, got {orientation!r}'
            )
        for key in POSITIVE_FINITE_KEYS:
            _positive_finite(label, spec, key)
        _require_per_facade(label, spec)
        below = spec.get('below_grade')
        if below != 'plain_no_joints':
            raise ValueError(
                f'{label} below_grade must be plain (plain_no_joints), got {below!r}'
            )
        source = spec.get('source_texture')
        if not isinstance(source, dict):
            raise ValueError(f'{label} source_texture is missing')
        recorded = source.get('sha256')
        path = source.get('path')
        if not isinstance(path, str) or not path:
            raise ValueError(f'{label} source_texture path is missing')
        raw = read_bytes(path)
        if isinstance(raw, str) or not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
            raise ValueError(f'{label} source_texture bytes are missing or unsupported')
        actual = hashlib.sha256(bytes(raw)).hexdigest()
        if recorded != actual:
            raise ValueError(
                f'{label} source_texture sha256 mismatch: recorded {recorded!r} != file {actual}'
            )
    report = doc.get('joint_report', {}).get('unresolved_facades')
    expected = unresolved_facade_report(doc)
    if report != expected:
        raise ValueError(
            f'joint_report.unresolved_facades {report!r} does not list unresolved facades {expected!r}'
        )


def _panel_nodes(doc):
    return [node for _label, node, is_panel in _walk_finish_nodes(doc) if is_panel]


def _read_synthetic_panel(path):
    if path != SYNTHETIC_PANEL_PATH:
        raise FileNotFoundError(path)
    return SYNTHETIC_PANEL_BYTES


def _use_synthetic_panel(doc, sha=None):
    """Point panel source_texture at the in-memory synthetic payload.

    synthetic=True marks the bytes as not publication evidence.
    """
    recorded = SYNTHETIC_PANEL_SHA if sha is None else sha
    for node in _panel_nodes(doc):
        spec = node.get('joint_spec')
        if not isinstance(spec, dict):
            continue
        source = spec.get('source_texture')
        if not isinstance(source, dict):
            continue
        source['path'] = SYNTHETIC_PANEL_PATH
        source['sha256'] = recorded
        source['synthetic'] = True
    return doc


def _validate_unit(doc, sha=None):
    return validate_panel_joints(_use_synthetic_panel(doc, sha=sha), read_bytes=_read_synthetic_panel)


def _measure_panel_texture(path):
    import numpy as np
    from PIL import Image

    raw = Path(path).read_bytes()
    image = np.asarray(Image.open(BytesIO(raw)))
    if image.shape != (4096, 4096, 3):
        raise AssertionError(f'expected 4096x4096 RGB, got {image.shape}')
    mean = image.reshape(-1, 3).astype(np.float64).mean(axis=0)
    column = image.astype(np.float64).mean(axis=2).mean(axis=0)
    dark = column < 60
    runs = []
    index = 0
    while index < len(dark):
        if dark[index]:
            end = index
            while end < len(dark) and dark[end]:
                end += 1
            runs.append((index, end - index))
            index = end
        else:
            index += 1
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'mean': mean, 'runs': runs}


def test_ac04_gate1_approved_delivery_still_open():
    d = load()
    validate_gate1(d)
    assert d['gate_1_status'] == 'approved-gate1'
    assert d['delivery_passed'] is False
    approval = d['approval']
    assert approval['date'] == '2026-10-22'
    assert approval['source'] == 'orchestrator relay of Artem'
    for mark in QUOTE_MARKS:
        assert mark in approval['quote']
    statement = approval['geometry_untouched']
    assert 'Geometry, topology, UCX and multisub IDs stay exactly as in the source scene' in statement
    md = (ROOT / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'approved-gate1' in md
    assert '150' in md and '120' in md


def test_ac04_questions_closed():
    d = load()
    by_id = {q['id']: q for q in d['questions']}
    for qid in ('Q1', 'Q3', 'Q4'):
        assert by_id[qid]['status'] == 'closed'
        assert by_id[qid]['answer'].strip()
        assert by_id[qid].get('open') is not True
    assert 'solid colour without joints' not in by_id['Q4']['answer']
    assert 'joint_spec' in by_id['Q4']['answer']
    assert '0.60' not in by_id['Q4']['answer']
    assert 'per_facade' in by_id['Q4']['answer']
    assert not any(q['id'] == 'Q2' for q in d['questions'])


def test_ac04_id1_regions_and_grey_roof():
    d = load()
    by_id = {m['id']: m for m in d['materials']}
    id1 = by_id[1]
    id4 = by_id[4]
    regions = {r['part']: r for r in id1['regions']}
    assert set(regions) == {'roof', 'frame/carcass', 'wall panels', 'below-grade drop/plinth'}
    assert regions['roof']['ral'] == 'RAL7004'
    assert regions['roof']['rgb_srgb'] == KPP_RALS['RAL7004']
    assert regions['roof']['kpp_reference']['sha256'] == KPP_GREY_SHA
    assert regions['frame/carcass']['ral'] == 'RAL7004'
    assert regions['frame/carcass']['kpp_reference']['sha256'] == KPP_GREY_SHA
    assert regions['wall panels']['ral'] == 'RAL5015'
    assert regions['wall panels']['map_type'] == 'vertical_joints'
    assert regions['below-grade drop/plinth']['ral'] == 'RAL5015'
    assert regions['below-grade drop/plinth']['map_type'] == 'solid'
    assert 'joint_spec' not in regions['below-grade drop/plinth']
    assert regions['roof']['map_type'] == 'solid' and 'joint_spec' not in regions['roof']
    assert regions['frame/carcass']['map_type'] == 'solid' and 'joint_spec' not in regions['frame/carcass']
    for region in id1['regions']:
        assert region['faces'] == 'unresolved'
        assert region['need'].strip()
    assert id4['ral'] == 'RAL7004'
    assert id4['rgb_srgb'] == KPP_RALS['RAL7004']
    assert id4['kpp_reference']['sha256'] == KPP_GREY_SHA
    assert by_id[2]['ral'] == 'RAL5015' and by_id[2]['map_type'] == 'vertical_joints'
    assert 'joint_spec' not in by_id[4] and 'joint_spec' not in by_id[5]
    assert by_id[4]['map_type'] == 'metal' and by_id[5]['map_type'] == 'metal'
    assert by_id[3]['map_type'] == 'glass'
    assert by_id[5]['ral'] == 'RAL1021'


def test_fail_closed_missing_finish_names_id():
    d = load()
    d['materials'][1]['finish'] = ''
    with pytest.raises(ValueError, match=r'ID 2'):
        validate_gate1(d)


def test_fail_closed_unknown_ral_names_id():
    d = load()
    d['materials'][4]['ral'] = 'RAL9999'
    with pytest.raises(ValueError, match=r'ID 5'):
        validate_gate1(d)


def test_fail_closed_status_outside_two_allowed_values():
    d = load()
    d['gate_1_status'] = 'published'
    with pytest.raises(ValueError, match='published'):
        validate_gate1(d)


def test_ac04_all_ids_and_slots_accounted():
    d = load()
    assert [m['id'] for m in d['materials']] == [1, 2, 3, 4, 5]
    assert d['scene']['empty_slots'] == [6, 7, 8, 9, 10]
    assert sum(m['triangles'] for m in d['materials']) == 5006
    assert sum(m['poly_faces'] for m in d['materials']) == 2552
    assert all(math.isfinite(m['area_m2']) and m['area_m2'] > 0 for m in d['materials'])
    assert len(d['scene']['collision_handles']) == 17


def test_ac04_finish_evidence_and_unknowns():
    d = load()
    for m in d['materials']:
        assert m['evidence'] and m['geometry_evidence']
        if m['finish'] == '?':
            assert m['question_ids']
    assert d['materials'][2]['map_type'] == 'glass'
    assert d['materials'][2]['glass']['npm_opacity'] == 0.5


def test_ac04_depth_render_and_perimeter_drop():
    d = load()
    assert d['rendering']['renderer'] == 'BLENDER_WORKBENCH'
    assert d['rendering']['depth_correct'] is True
    assert d['rendering']['ucx_visible'] is False
    assert d['rendering']['datum_z_m'] == 0
    assert d['rendering']['plain_shaded_companion'] is True
    assert d['perimeter_drop']['material_id'] == 1
    assert not any(q['id'] == 'Q2' for q in d['questions'])
    drop = json.loads((ROOT / 'perimeter-drop.json').read_text())
    assert drop['walls_verified'] == 4 and drop['walls_failed'] == 0
    assert all(w['verified'] and w['minimum_z_m'] <= -1 for w in drop['walls'])
    assert all(len(w['below_minus_1_continuous_spans_m']) == 1 for w in drop['walls'])


def test_ac04_kpp_colours_exact():
    d = load()
    for m in d['materials']:
        if m['ral']:
            assert m['rgb_srgb'] == KPP_RALS[m['ral']]
            assert len(m['kpp_reference']['sha256']) == 64
        for region in m.get('regions') or []:
            if region.get('ral'):
                assert region['rgb_srgb'] == KPP_RALS[region['ral']]
                assert region['kpp_reference']['sha256']


def test_ac04_manifest_and_source_provenance():
    d = load()
    assert len(d['base_sha']) == 40
    assert d['scene']['layer'] == '004'
    for s in d['sources']:
        assert len(s['sha256']) == 64
    manifest = json.loads((ROOT / 'evidence.json').read_text(encoding='utf-8'))
    names = [e['filename'] for e in manifest['files']]
    assert len(names) == len(set(names))
    assert {'contact-sheet.png', 'iso.png', 'reverse.png', 'roof.png'} <= set(names)
    assert all(len(e['sha256']) == 64 and e['bytes'] > 0 for e in manifest['files'])


def test_ac04_ral5015_vertical_joints_spec():
    """JSON and MATERIALS.md only. Does not read the provisioned panel texture."""
    d = load()
    validate_gate1(d)
    panels = _panel_nodes(d)
    assert len(panels) == 2
    for panel in panels:
        spec = panel['joint_spec']
        assert spec['orientation'] == 'vertical_only'
        assert 'module_m' not in spec
        assert '0.60' not in spec.get('layout', '')
        assert spec['joint_width_mm'] == 8
        assert spec['texel_px_per_m'] == 1000
        assert spec['phase_origin'] == 'symmetric in the panel field'
        assert spec['below_grade'] == 'plain_no_joints'
        assert spec['npm_min_joint_px'] == 1.5
        assert spec['source_texture']['role'] == 'colour_noise_one_joint_profile'
        assert spec['source_texture']['tiling_source'] is False
        names = [entry['facade'] for entry in spec['per_facade']]
        assert names == list(SHEET_FACADES)
        assert spec['source_texture']['path'] == PANEL_TEXTURE
        assert spec['source_texture']['sha256'] == PANEL_TEXTURE_SHA
        assert spec['supersedes']['replaced'] == (
            'Sandwich panels: solid colour without joints (module not confirmed by the drawings).'
        )
        assert spec['supersedes']['quote'] == PANEL_QUOTE
        assert spec['supersedes']['below_grade_quote'] == BELOW_GRADE_QUOTE
        assert spec['measured']['mean_rgb_rounded'] == [34, 112, 177]
        assert spec['measured']['width_px'] == 4096 and spec['measured']['height_px'] == 4096
        assert spec['measured']['joint_count'] == 7
        assert spec['measured']['joint_width_px'] == 8
        assert spec['measured']['joint_period_px'] == 600
        assert spec['colour_tolerance_max_abs'] == COLOUR_TOLERANCE_MAX_ABS
        assert spec['colour_reference_role'] == 'kpp_colour_only'
    md = (ROOT / 'MATERIALS.md').read_text(encoding='utf-8')
    assert PANEL_QUOTE in md and BELOW_GRADE_QUOTE in md
    assert 'vertical_joints' in md
    assert 'approved-gate1' in md


@pytest.mark.panel_texture
def test_ac04_ral5015_panel_texture_publication_evidence():
    """Publication evidence for the RAL5015 vertical-joint texture.

    Required provisioned input, not a unit fixture and not a skip:
    path C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png
    sha256 2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece.
    A missing file fails this check.
    """
    import numpy as np

    if PANEL_TEXTURE != 'C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png':
        raise AssertionError('provisioned path contract drifted')
    if PANEL_TEXTURE_SHA != '2c255edc5f7a56fc8aca3038d0e0235327128ac6ae3c8c63e0be31a1f6386ece':
        raise AssertionError('provisioned sha256 contract drifted')
    if not Path(PANEL_TEXTURE).is_file():
        raise FileNotFoundError(
            f'required provisioned panel texture is missing: {PANEL_TEXTURE} sha256 {PANEL_TEXTURE_SHA}'
        )
    d = load()
    validate_panel_joints(d)
    measured = _measure_panel_texture(PANEL_TEXTURE)
    assert measured['sha256'] == PANEL_TEXTURE_SHA
    assert measured['runs'] == [(266, 8), (866, 8), (1466, 8), (2066, 8), (2666, 8), (3266, 8), (3866, 8)]
    assert all(measured['runs'][i + 1][0] - measured['runs'][i][0] == 600 for i in range(6))
    mean = measured['mean']
    assert [int(round(channel)) for channel in mean] == [34, 112, 177]
    kpp = np.array(KPP_RALS['RAL5015'], dtype=np.float64)
    delta = mean - kpp
    assert float(np.max(np.abs(delta))) <= COLOUR_TOLERANCE_MAX_ABS
    for panel in _panel_nodes(d):
        spec = panel['joint_spec']
        assert np.allclose(spec['measured']['mean_rgb'], mean, atol=1e-6)
        assert np.allclose(spec['colour_delta_vs_kpp'], delta, atol=1e-6)


def test_horizontal_joints_not_allowed():
    """Invariant: panel joint orientation is vertical_only. Probe rejects horizontal values."""
    orientations = ('horizontal', 'horizontal_only', 'both', None)
    caught = 0
    for orientation in orientations:
        doc = load()
        for node in _panel_nodes(doc):
            spec = node.get('joint_spec')
            if isinstance(spec, dict):
                spec['orientation'] = orientation
        with pytest.raises(ValueError, match='vertical_only'):
            _validate_unit(doc)
        caught += 1
    assert caught == len(orientations)


def test_panel_joint_texel_positive_finite():
    """Invariant: joint_width_mm and texel_px_per_m are positive finite. Probe: 0/NaN/inf."""
    bad_values = (0, float('nan'), float('inf'), float('-inf'))
    caught = 0
    for key in POSITIVE_FINITE_KEYS:
        for bad in bad_values:
            doc = load()
            for node in _panel_nodes(doc):
                spec = node.get('joint_spec')
                if isinstance(spec, dict):
                    spec[key] = bad
            with pytest.raises(ValueError, match=rf'\b{key}\b'):
                _validate_unit(doc)
            caught += 1
    assert caught == len(POSITIVE_FINITE_KEYS) * len(bad_values)


def test_per_facade_rib_count_rejects_bad_values_by_name():
    """Invariant: a resolved rib_count is an integer >= 1. Probe: 0/NaN/negative/float, error names the facade."""
    target = SHEET_FACADES[0]
    bad_values = (0, float('nan'), -3, 1.5)
    caught = 0
    for bad in bad_values:
        doc = load()
        for node in _panel_nodes(doc):
            for facade in node['joint_spec']['per_facade']:
                if facade['facade'] == target:
                    facade.pop('status', None)
                    facade.pop('question', None)
                    facade['rib_count'] = bad
                    facade['step_m'] = 1.0
        with pytest.raises(ValueError, match=target):
            _validate_unit(doc)
        caught += 1
    assert caught == len(bad_values)


def _settle_target_facade(doc, target, **fields):
    for node in _panel_nodes(doc):
        for facade in node['joint_spec']['per_facade']:
            if facade['facade'] == target:
                facade.pop('status', None)
                facade.pop('question', None)
                facade.update(fields)
        node['joint_spec']['per_facade'] = [
            facade for facade in node['joint_spec']['per_facade'] if facade.get('status') != 'unresolved'
        ]
    doc['joint_report'] = {'unresolved_facades': unresolved_facade_report(doc)}
    return doc


def test_per_facade_step_and_width_and_no_module_fallback():
    """Invariant: step is positive finite, and count times step is strictly inside 2% of the field width.

    Probe: 0/NaN/inf step, a ratio of exactly 2%, a ratio above 2%, module_m 0.60, and an empty per_facade.
    A ratio of 1% passes.
    """
    target = SHEET_FACADES[1]
    doc = _settle_target_facade(load(), target, rib_count=14, step_m=1.0, field_width_m=14.0)
    _validate_unit(doc)

    inside = _settle_target_facade(load(), target, rib_count=101, step_m=1.0, field_width_m=100.0)
    _validate_unit(inside)

    exact = _settle_target_facade(load(), target, rib_count=102, step_m=1.0, field_width_m=100.0)
    with pytest.raises(ValueError, match=target):
        _validate_unit(exact)

    bad_steps = (0, float('nan'), float('inf'), float('-inf'))
    step_caught = 0
    for bad in bad_steps:
        step_doc = load()
        for node in _panel_nodes(step_doc):
            for facade in node['joint_spec']['per_facade']:
                if facade['facade'] == target:
                    facade.pop('status', None)
                    facade.pop('question', None)
                    facade['rib_count'] = 14
                    facade['step_m'] = bad
        with pytest.raises(ValueError, match=target):
            _validate_unit(step_doc)
        step_caught += 1
    assert step_caught == len(bad_steps)

    mismatch = load()
    for node in _panel_nodes(mismatch):
        for facade in node['joint_spec']['per_facade']:
            if facade['facade'] == target:
                facade.pop('status', None)
                facade.pop('question', None)
                facade['rib_count'] = 10
                facade['step_m'] = 1.0
                facade['field_width_m'] = 14.0
    with pytest.raises(ValueError, match=target):
        _validate_unit(mismatch)

    fallback = load()
    for node in _panel_nodes(fallback):
        node['joint_spec']['module_m'] = 0.60
    with pytest.raises(ValueError, match='0.60'):
        _validate_unit(fallback)

    empty = load()
    for node in _panel_nodes(empty):
        node['joint_spec']['per_facade'] = []
    with pytest.raises(ValueError, match='per_facade'):
        _validate_unit(empty)


def test_width_ratio_just_inside_exact_and_just_outside():
    """The field-width ratio is strict: exactly 2% and 2.01% fail; 1.99% passes.

    Worked synthetic widths, all with step_m 1:
    rib_count 10199 / field 10000 = 1.99% (accepted);
    rib_count 10200 / field 10000 = 2% (rejected);
    rib_count 10201 / field 10000 = 2.01% (rejected).
    NaN/inf field width is an error. A finite step whose product overflows
    to a non-finite ratio is an error.
    """
    target = SHEET_FACADES[2]
    width = 10000.0
    inside = _settle_target_facade(load(), target, rib_count=10199, step_m=1.0, field_width_m=width)
    _validate_unit(inside)

    exact = _settle_target_facade(load(), target, rib_count=10200, step_m=1.0, field_width_m=width)
    with pytest.raises(ValueError, match='2%'):
        _validate_unit(exact)

    outside = _settle_target_facade(load(), target, rib_count=10201, step_m=1.0, field_width_m=width)
    with pytest.raises(ValueError, match='2%'):
        _validate_unit(outside)

    for bad in (float('nan'), float('inf'), float('-inf')):
        width_doc = _settle_target_facade(load(), target, rib_count=14, step_m=1.0, field_width_m=14.0)
        for node in _panel_nodes(width_doc):
            for facade in node['joint_spec']['per_facade']:
                if facade['facade'] == target:
                    facade['field_width_m'] = bad
        with pytest.raises(ValueError, match='field_width_m'):
            _validate_unit(width_doc)

    overflow = _settle_target_facade(load(), target, rib_count=10, step_m=1e308, field_width_m=1.0)
    with pytest.raises(ValueError, match='2%'):
        _validate_unit(overflow)


def test_unresolved_facade_keeps_gate_approved_and_is_listed():
    """An unresolved facade does not revoke approved-gate1. The report lists it."""
    doc = load()
    validate_gate1(doc)
    _validate_unit(doc)
    assert doc['gate_1_status'] == 'approved-gate1'
    report = unresolved_facade_report(doc)
    assert report
    assert doc['joint_report']['unresolved_facades'] == report
    for name in report:
        assert name in SHEET_FACADES
    md = (ROOT / 'MATERIALS.md').read_text(encoding='utf-8')
    for name in report:
        assert name in md


def test_acceptance_picture_blocks_a_count_mismatch():
    """Each facade render sits beside the sheet facade. A differing rib count is not sent to Artem."""
    doc = load()
    picture = doc['acceptance_picture']
    assert picture['required'] is True
    assert picture['made_by'] == 'build card'
    text = picture['rule']
    assert 'same scale' in text
    assert 'rib count' in text.lower()
    assert 'not sent' in text.lower()
    md = (ROOT / 'MATERIALS.md').read_text(encoding='utf-8')
    assert 'same scale' in md
    assert 'not sent' in md.lower()


def test_below_grade_must_be_plain():
    """Invariant: below +-0.000 the panel finish is plain, with no joints."""
    bad_values = ('joints', 'vertical_joints', 'solid', '', None)
    caught = 0
    for below in bad_values:
        doc = load()
        for node in _panel_nodes(doc):
            spec = node.get('joint_spec')
            if isinstance(spec, dict):
                spec['below_grade'] = below
        with pytest.raises(ValueError, match='plain'):
            _validate_unit(doc)
        caught += 1
    assert caught == len(bad_values)


def test_texture_sha_mismatch_is_an_error():
    """Invariant: the recorded panel-texture SHA256 matches the bytes the reader returns."""
    bad_hashes = ('0' * 64, PANEL_TEXTURE_SHA[:-1] + ('0' if PANEL_TEXTURE_SHA[-1] != '0' else '1'))
    caught = 0
    for bad in bad_hashes:
        with pytest.raises(ValueError, match='sha256 mismatch'):
            _validate_unit(load(), sha=bad)
        caught += 1
    assert caught == len(bad_hashes)


def test_texture_bytes_fail_closed():
    """Invariant: empty, partial and unsupported texture bytes are errors, never a pass."""
    def empty(_path):
        return b''

    def partial(_path):
        return SYNTHETIC_PANEL_BYTES[:4]

    def missing(_path):
        return None

    def text(_path):
        return 'unsupported'

    readers = (empty, partial, missing, text)
    caught = 0
    for reader in readers:
        with pytest.raises(ValueError):
            validate_panel_joints(_use_synthetic_panel(load()), read_bytes=reader)
        caught += 1
    assert caught == len(readers)


def test_valid_synthetic_panel_control_passes():
    """A synthetic panel payload validates, and the control is marked synthetic=True.

    The reader serves only the in-memory bytes. The provisioned publication path is not used.
    """
    doc = load()
    seen = []

    def read_bytes(path):
        seen.append(path)
        if path != SYNTHETIC_PANEL_PATH:
            raise FileNotFoundError(path)
        return SYNTHETIC_PANEL_BYTES

    _use_synthetic_panel(doc)
    panels = _panel_nodes(doc)
    assert panels
    for node in panels:
        source = node['joint_spec']['source_texture']
        assert source['synthetic'] is True
        assert source['path'] == SYNTHETIC_PANEL_PATH
        assert source['sha256'] == hashlib.sha256(SYNTHETIC_PANEL_BYTES).hexdigest()
    validate_panel_joints(doc, read_bytes=read_bytes)
    assert seen == [SYNTHETIC_PANEL_PATH] * len(panels)


def test_missing_provisioned_panel_texture_is_an_error():
    """Invariant: the publication check fails when the provisioned file is absent. It does not skip."""
    original = Path.is_file

    def missing(self):
        if Path(str(self)) == Path(PANEL_TEXTURE):
            return False
        return original(self)

    Path.is_file = missing
    try:
        with pytest.raises(FileNotFoundError, match=PANEL_TEXTURE_SHA):
            test_ac04_ral5015_panel_texture_publication_evidence()
    finally:
        Path.is_file = original


@pytest.mark.panel_texture
def test_hash_mismatched_publication_panel_bytes_are_an_error():
    """The provisioned file is present, but injected bytes do not match its recorded SHA256.

    The reader is injected on the publication path. The file on disk is not modified.
    A mismatch is an error and must not pass.
    """
    path = Path(PANEL_TEXTURE)
    if not path.is_file():
        raise FileNotFoundError(
            f'required provisioned panel texture is missing: {PANEL_TEXTURE} sha256 {PANEL_TEXTURE_SHA}'
        )
    on_disk = path.read_bytes()
    assert hashlib.sha256(on_disk).hexdigest() == PANEL_TEXTURE_SHA
    mismatched = b'hash-mismatch-' + on_disk[:16]
    assert hashlib.sha256(mismatched).hexdigest() != PANEL_TEXTURE_SHA

    def read_mismatched(requested):
        if requested != PANEL_TEXTURE:
            raise AssertionError(requested)
        return mismatched

    doc = load()
    for node in _panel_nodes(doc):
        source = node['joint_spec']['source_texture']
        assert source['path'] == PANEL_TEXTURE
        assert source['sha256'] == PANEL_TEXTURE_SHA
        assert source.get('synthetic') is not True
    with pytest.raises(ValueError, match='sha256 mismatch'):
        validate_panel_joints(doc, read_bytes=read_mismatched)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PANEL_TEXTURE_SHA


_PROBE_TEST = 'test_default_unit_tests_do_not_read_private_panel_texture'
_INTEGRATION_MARKER = 'panel_texture'


def _pytest_marks(fn):
    marks = getattr(fn, 'pytestmark', ())
    if not isinstance(marks, (list, tuple)):
        return (marks,)
    return tuple(marks)


def _default_unit_test_functions():
    selected = []
    for name, fn in sorted(globals().items()):
        if not name.startswith('test_') or not callable(fn) or name == _PROBE_TEST:
            continue
        marks = _pytest_marks(fn)
        if any(getattr(mark, 'name', None) == _INTEGRATION_MARKER for mark in marks):
            continue
        selected.append((name, fn, marks))
    return selected


def test_default_unit_tests_do_not_read_private_panel_texture(monkeypatch):
    """Invariant: the default unit selection never reads the private panel texture.

    Probe: Path.read_bytes and Path.open raise FileNotFoundError for
    C:/x/tec26-oks/user-textures/panel_RAL5015_vertical_joints_4096.png,
    and Path.exists on that path is recorded. Every default unit test still passes,
    and none of those calls touch the path.
    """
    hits = []
    original_read = Path.read_bytes
    original_open = Path.open
    original_exists = Path.exists

    def is_private(path):
        try:
            return Path(str(path)) == Path(PANEL_TEXTURE)
        except (TypeError, ValueError):
            return False

    def guarded_read(self):
        if is_private(self):
            hits.append(('read_bytes', str(self)))
            raise FileNotFoundError(PANEL_TEXTURE)
        return original_read(self)

    def guarded_open(self, *args, **kwargs):
        if is_private(self):
            hits.append(('open', str(self)))
            raise FileNotFoundError(PANEL_TEXTURE)
        return original_open(self, *args, **kwargs)

    def guarded_exists(self):
        if is_private(self):
            hits.append(('exists', str(self)))
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, 'read_bytes', guarded_read)
    monkeypatch.setattr(Path, 'open', guarded_open)
    monkeypatch.setattr(Path, 'exists', guarded_exists)

    ran = []
    for name, fn, marks in _default_unit_test_functions():
        skipped = False
        for mark in marks:
            if getattr(mark, 'name', None) == 'skipif' and mark.args and bool(mark.args[0]):
                skipped = True
                break
        if skipped:
            continue
        fn()
        ran.append(name)
    assert ran
    assert hits == []


SWATCH_V007 = Path('G:/Мой диск/AGR-evidence/tec26-oks/AC04/gate1-v007/swatches.png')


@pytest.mark.skipif(not SWATCH_V007.exists(), reason='Drive evidence not mounted')
def test_published_swatches_use_pinned_kpp_colours():
    from PIL import Image

    im = Image.open(SWATCH_V007).convert('RGB')
    counts = {}
    for count, colour in im.getcolors(maxcolors=1 << 20):
        counts[colour] = count
    assert counts.get((238, 201, 0), 0) >= 40000, 'ID5 RAL1021 yellow missing'
    assert (243, 165, 5) not in counts, 'wrong ID5 yellow present'
    assert counts.get((34, 113, 179), 0) > 0 and counts.get((150, 153, 146), 0) > 0
    assert hashlib.sha256(SWATCH_V007.read_bytes()).hexdigest() == (
        '014cc4011049e5d26a8b2eede5cf898788f6e73bd2c4fa0c34b0e99fc356ba7d')
