"""new-case: GeoJSON per D220 (#1107) — the customer's ELV file is the reference for ZU_area units (m², not
hectares), the «округ» field format (abbreviation, not the full name) and the anchor point (MSK-77, 3 decimals).

Customer ELV file (read-only, not committed):
  `C:\\Users\\artsafro\\Desktop\\!3D viz\\Dima_Andrew\\3_sreda\\customer_2026-11-05\\SM_Elevatornaya_Vl_1_A_001.geojson`
  sha256 6f6285f0be20b12a14c4d474febd31ca076205c8070e972a3afe2d9ab00a7446
  (zip SM_Elevatornaya_Vl_1_A_001.zip sha256 3051e465046c926738d17f83b07ee86d09e64c9a0f2e89f192c9a2a870da813f)
  key values: ZU_area = 10386.0000 m², okrug = "ЮАО", coordinates = [9676.355, -7135.700].

The doc test (test_zu_area_documented_in_m2) is RED on the commit that documented hectares and GREEN after the
fix; the writer tests pin the convention so a future regression that reintroduces ha / the full name is caught.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'

# The customer's ELV reference values (the RED test is written from this file first).
CUSTOMER_ELV = {
    'ZU_area': 10386.0,           # m² (sheet 42 item 1 = 10 386 m2), NOT 1.0386 ha
    'okrug': 'ЮАО',               # abbreviation, NOT "Южный административный округ"
    'coordinates': [9676.355, -7135.700],   # MSK-77, 3 decimals
}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_zu_area_documented_in_m2_not_hectares():
    """docs/domain/npm-vpm.md documents ZU_area in m² — the reg/our doc said 'ha' before #1107."""
    text = (ROOT / 'docs/domain/npm-vpm.md').read_text(encoding='utf-8')
    assert 'ZU_area (m2, <=4 decimals)' in text
    assert 'ZU_area (ha,' not in text


def test_geojson_document_writes_customer_zu_area_and_okrug():
    pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_d220')
    import json
    props = {'ZU_area': CUSTOMER_ELV['ZU_area'], 'okrug': CUSTOMER_ELV['okrug']}
    data = pc.geojson_document(props, image_b64='', coordinates=CUSTOMER_ELV['coordinates'],
                               glasses=[], ground=False)
    doc = json.loads(data.decode('utf-8'))
    feat = doc['features'][0]
    # ZU_area stays m² (a number, ~10 386, not ~1.04 hectares) and okrug stays the abbreviation.
    assert feat['properties']['ZU_area'] == 10386.0
    assert abs(feat['properties']['ZU_area'] - 10386.0) < 1.0          # m², not 1.0386
    assert feat['properties']['okrug'] == 'ЮАО'
    assert feat['geometry']['coordinates'] == CUSTOMER_ELV['coordinates']


def test_pivot_coordinates_rounds_to_3_decimals():
    pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_d220b')
    report = {'status': 'pass', 'plan': {'pivot_value': [9676.35512, -7135.70097, 0.0], 'floor': '0.000'}}
    coords, floor = pc.pivot_coordinates(report)
    assert coords == [9676.355, -7135.701]       # 3 decimals, MSK-77
    assert floor == '0.000'


def test_writer_never_converts_units_or_okrug():
    """Counterexample beyond the ELV example: the writer is pass-through — it neither converts m²↔ha nor
    abbreviates/expands okrug, so a caller-supplied hectare value or full okrug name stays byte-identical."""
    import json
    pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_d220c')
    props = {'ZU_area': 1.0386, 'okrug': 'Южный административный округ'}  # the OLD (pre-#1107) values
    data = pc.geojson_document(props, image_b64='', coordinates=[0.0, 0.0], glasses=[], ground=False)
    feat = json.loads(data.decode('utf-8'))['features'][0]['properties']
    assert feat['ZU_area'] == 1.0386                            # NOT 10386.0: no ha→m² conversion
    assert feat['okrug'] == 'Южный административный округ'      # NOT «ЮАО»: no abbreviation


def test_geojson_document_rejects_nonfinite_zu_area():
    """Fail-closed: NaN/inf ZU_area must raise, never serialize to a null/Infinity JSON value."""
    import json
    pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_d220d')
    for bad in (float('nan'), float('inf'), float('-inf')):
        props = {'ZU_area': bad}
        try:
            pc.geojson_document(props, image_b64='', coordinates=[0.0, 0.0], glasses=[], ground=False)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError('non-finite ZU_area must raise (allow_nan=False), got a document')
