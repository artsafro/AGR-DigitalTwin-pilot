"""new-case: AGR Tools 0.8.1 owner decisions of 05.11.2026 on team audit T04 (#908).

1. qa.scene_hygiene `hyg_layer`: every object on the default layer "0" (reg p.28 §3.2; idea of the team script
   agr_max_check_37.ms check_Layers, sha256 ead38669..., no code taken).
2. FNO registry (standards/data/fno_codes_utf8.csv): V011 checks that an OKS FNO_code exists and FNO_name matches.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, PKG / name)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod] = m
    spec.loader.exec_module(m)
    return m


checks = _load('checks_core.py', 'agr_tools_checks_core')
core = _load('suite_core.py', 'agr_tools_suite_core_owner_test')


def row(key, name='SM_Addr_001_Main', **kw):
    r = {'key': key, 'name': name, 'superclass': 'geometry', 'cls': 'Editable_Poly', 'faces': 12,
         'parent': None, 'children': 0, 'group': False, 'animated': False, 'modifiers': [], 'layer': '0'}
    r.update(kw)
    return r


def codes(found, key):
    return sorted(c for c, _, _ in found.get(key, []))


# ---- 1. layer "0" -------------------------------------------------------------------------------------------
def test_hyg_layer_object_off_default_layer_fails_with_clear_text():
    rows = [row(1), row(2, 'SM_Addr_Ground', layer='Ground'), row(3, 'Camera001', superclass='camera', layer='cams')]
    f, _, _ = core.scene_hygiene(rows)
    assert codes(f, 1) == []
    assert codes(f, 2) == ['hyg_layer']
    assert codes(f, 3) == ['hyg_layer', 'hyg_non_mesh']
    text = dict((c, d) for c, d, _ in f[2])['hyg_layer']
    assert '«Ground»' in text and '«0»' in text and 'p.28' in text


def test_hyg_layer_is_registered_for_scene_hygiene_and_preflight():
    assert 'hyg_layer' in core.CODES['scene_hygiene']
    assert 'hyg_layer' in core.CODES['preflight']


def test_hyg_layer_missing_layer_field_is_an_error_never_a_pass():
    r = row(1)
    del r['layer']
    try:
        core.scene_hygiene([r])
    except ValueError as exc:
        assert 'layer' in str(exc)
    else:
        raise AssertionError('missing layer must not pass')


def test_hyg_layer_is_case_and_space_exact():
    f, _, _ = core.scene_hygiene([row(1, layer=' 0'), row(2, layer='0 ')])
    assert codes(f, 1) == ['hyg_layer'] and codes(f, 2) == ['hyg_layer']


# ---- 2. FNO registry ------------------------------------------------------------------------------------------
def test_fno_registry_data_and_provenance():
    import hashlib
    from twinqa import fno
    data = ROOT / 'standards/data/fno_codes_utf8.csv'
    sha = hashlib.sha256(data.read_bytes()).hexdigest()
    assert sha == fno.REGISTRY_SHA256
    note = (ROOT / 'standards/data/fno_codes.PROVENANCE.md').read_text(encoding='utf-8')
    assert sha in note and 'SINTEZ AGR Checker' in note and '1.6.1' in note
    reg = fno.registry()
    assert reg['001'] == 'Административно-деловые объекты'
    assert reg['001 001 001'] == 'Объект органов государственной власти Российской Федерации'
    assert all(len(c.replace(' ', '')) in (3, 6, 9) for c in reg)


def test_fno_check_unknown_code_and_wrong_name():
    from twinqa import fno
    assert fno.check('001 001 001', 'Объект органов государственной власти Российской Федерации') == []
    assert fno.check('001001001', 'Объект органов государственной власти Российской Федерации') == []
    assert fno.check('001', 'Административно-деловые  объекты') == []  # spaces ignored, as SINTEZ
    assert fno.check('999 999 999', 'x')[0][0] == 'FNO_code not in registry'
    name, observed, expected = fno.check('001 001 001', 'Суд')[0]
    assert name == 'FNO_name vs registry' and 'Суд' in observed and 'Российской Федерации' in expected


def _geojson(code, name, stem_ground=False):
    import base64
    import json
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (256, 256), (1, 2, 3)).save(buf, format='JPEG')
    keys = ['address', 'okrug', 'rajon', 'name', 'developer', 'designer', 'cadNum', 'FNO_code', 'FNO_name',
            'ZU_area', 'h_relief', 'h_otn', 'h_abs', 's_obsh', 's_naz', 's_podz', 'spp_gns', 'act_AGR',
            'imageBase64', 'other']
    props = {k: 'x' for k in keys}
    props.update(FNO_code=code, FNO_name=name, imageBase64=base64.b64encode(buf.getvalue()).decode('ascii'))
    doc = {'type': 'FeatureCollection', 'features': [{'type': 'ObjectFeature', 'properties': props,
                                                      'geometry': {'type': 'Point', 'coordinates': [1.5, 2.5]},
                                                      'Glasses': []}]}
    return json.dumps(doc, ensure_ascii=False).encode('utf-8')


def _v011(raw, ground=False):
    from twinqa.geojson import geojson_findings
    from twinqa.profiles import load_profiles
    return {f.name: f.status for f in geojson_findings(raw, load_profiles(ROOT / 'standards').vpm, ground)}


def test_v011_uses_the_fno_registry_for_oks():
    good = _v011(_geojson('001 002 001', 'Суд'))
    assert good.get('schema') == 'pass' and not {'FNO_code not in registry', 'FNO_name vs registry'} & set(good)
    assert _v011(_geojson('123 456', 'x'))['FNO_code not in registry'] == 'fail'
    assert _v011(_geojson('001 002 001', 'Прокуратура'))['FNO_name vs registry'] == 'fail'


def test_v011_ground_is_not_checked_against_the_registry():
    statuses = _v011(_geojson('', ''), ground=True)
    assert 'FNO_code not in registry' not in statuses and 'FNO_name vs registry' not in statuses
