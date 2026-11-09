"""new-case: GeoJSON per D220 (#1107) — the customer's ELV file is the reference for the «округ» field format
(the standard Moscow administrative-okrug abbreviation «ЮАО», not the full name) and the anchor point (MSK-77,
3 decimals). `ZU_area` is written in hectares per [D223] (Artem 2026-11-09; reg p.53 = ha, PSU275 file = ha; the
customer's ELV file = m² is an outlier), conflict #48 in docs/domain/conflicts.md is resolved; the ELV job keeps 1.0386 ha.

Customer ELV file (read-only, not committed):
  `C:\\Users\\artsafro\\Desktop\\!3D viz\\Dima_Andrew\\3_sreda\\customer_2026-11-05\\SM_Elevatornaya_Vl_1_A_001.geojson`
  sha256 6f6285f0be20b12a14c4d474febd31ca076205c8070e972a3afe2d9ab00a7446
  (zip SM_Elevatornaya_Vl_1_A_001.zip sha256 3051e465046c926738d17f83b07ee86d09e64c9a0f2e89f192c9a2a870da813f)
  key values: okrug = "ЮАО", ZU_area = 10386.0000 (m²), coordinates = [9676.355, -7135.700].

The doc/conflict/script tests are RED on the commit that documented m² and wrote the full okrug name, and GREEN
after the rework; the writer tests pin pass-through, the anchor format and fail-closed handling so a future
regression is caught.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
V005 = ROOT / 'jobs/elv-tc-vpm/scripts/package_vpm_v005.py'
V006 = ROOT / 'jobs/elv-tc-vpm/scripts/package_vpm_v006.py'

# The customer's ELV reference values (the RED test is written from this file first).
CUSTOMER_ELV = {
    'okrug': 'ЮАО',                      # abbreviation, NOT "Южный административный округ"
    'coordinates': [9676.355, -7135.700],  # MSK-77, 3 decimals
}
CUSTOMER_ELV_ZU_AREA_M2 = 10386.0   # the customer writes m²; the reg says ha (open conflict)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_zu_area_documented_in_hectares_with_reg_citation():
    """docs/domain/npm-vpm.md documents ZU_area in ha (reg p.53 table 1 row 10 «га»), not m²."""
    text = (ROOT / 'docs/domain/npm-vpm.md').read_text(encoding='utf-8')
    assert 'ZU_area (ha, <=4 decimals)' in text
    assert 'ZU_area (m2,' not in text


def test_zu_area_conflict_recorded_with_three_sources():
    """docs/domain/conflicts.md names the reg (ha) and both customer files (ELV m², PSU275 ha)."""
    text = (ROOT / 'docs/domain/conflicts.md').read_text(encoding='utf-8')
    assert '6f6285f0be20b12a14c4d474febd31ca076205c8070e972a3afe2d9ab00a7446' in text   # ELV
    assert 'ae65d6196f787b81234986e9e98571860b5c55cc47b356f998ad85dfdb218622' in text  # PSU275
    assert '10386.0000' in text
    assert '6.4882' in text
    assert 'га' in text                                                              # the reg unit is named


def test_zu_area_hectares_decision_recorded_and_cited():
    """Artem 2026-11-09 chose ha (reg p.53): D223 is in decisions.md, conflict #48 is resolved, the docs cite it."""
    decisions = (ROOT / 'docs/decisions.md').read_text(encoding='utf-8')
    rows = [line for line in decisions.splitlines() if line.startswith('| D223 |')]
    assert len(rows) == 1 and 'ZU_area' in rows[0] and 'hectares' in rows[0] and '#48' in rows[0]
    conflict = next(line for line in (ROOT / 'docs/domain/conflicts.md').read_text(encoding='utf-8').splitlines()
                    if line.startswith('48. '))
    assert '[D223]' in conflict and 'No side chosen' not in conflict
    assert 'ZU_area (ha, <=4 decimals; [D223])' in (ROOT / 'docs/domain/npm-vpm.md').read_text(encoding='utf-8')
    for rel in ('jobs/elv-tc-vpm/scripts/package_vpm_v006.py', 'adapters/max/agr_tools/package_core.py',
                'docs/research/geojson-d220-customer-files.md'):
        text = (ROOT / rel).read_text(encoding='utf-8')
        assert 'until Artem decides' not in text, rel
        assert 'open source conflict' not in text, rel


def test_v006_uses_okrug_abbreviation():
    """The okrug fix lands in the NEW package_vpm_v006.py, not the delivered v005."""
    v006 = V006.read_text(encoding='utf-8')
    assert '"okrug": "ЮАО"' in v006
    assert '"okrug": "Южный административный округ"' not in v006


def test_v006_keeps_zu_area_in_hectares():
    """ZU_area stays 1.0386 ha per [D223]; the customer's m² value is not applied."""
    v006 = V006.read_text(encoding='utf-8')
    assert '"ZU_area": 1.0386' in v006
    assert '"ZU_area": 10386' not in v006


def test_v005_is_the_delivered_script_unchanged():
    """The delivered v005 keeps the full okrug name and ha — the rework must not edit it."""
    v005 = V005.read_text(encoding='utf-8')
    assert '"okrug": "Южный административный округ"' in v005
    assert '"ZU_area": 1.0386' in v005


def test_geojson_document_is_pass_through_for_okrug_and_zu_area():
    """The writer neither abbreviates/expands okrug nor converts ha<->m²: caller values stay byte-identical."""
    pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_d220')
    props = {'ZU_area': 1.0386, 'okrug': 'Южный административный округ'}  # caller supplies ha + full name
    data = pc.geojson_document(props, image_b64='', coordinates=[0.0, 0.0], glasses=[], ground=False)
    feat = json.loads(data.decode('utf-8'))['features'][0]['properties']
    assert feat['ZU_area'] == 1.0386
    assert feat['okrug'] == 'Южный административный округ'


def test_pivot_coordinates_rounds_to_3_decimals():
    pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_d220b')
    report = {'status': 'pass', 'plan': {'pivot_value': [9676.35512, -7135.70097, 0.0], 'floor': '0.000'}}
    coords, floor = pc.pivot_coordinates(report)
    assert coords == [9676.355, -7135.701]       # 3 decimals, MSK-77
    assert floor == '0.000'


def test_geojson_document_rejects_nonfinite_zu_area():
    """Fail-closed: NaN/inf ZU_area must raise, never serialize to a null/Infinity JSON value."""
    pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_d220c')
    for bad in (float('nan'), float('inf'), float('-inf')):
        props = {'ZU_area': bad}
        try:
            pc.geojson_document(props, image_b64='', coordinates=[0.0, 0.0], glasses=[], ground=False)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError('non-finite ZU_area must raise (allow_nan=False), got a document')
