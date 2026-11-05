"""Requirement ids on AGR Tools actions equal docs/plans/agr-tools-suite.json (#862).

Reqs stay literals in ui_model.py (the Max install has no docs/ tree). This test is the
check that those literals still match the suite.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'

# Apply variants share the suite row of the tool they apply. Every ACTIONS id is here
# or in NO_SUITE_ENTRY; a new id in neither is an error that names it.
SUITE_KEY = {
    'xview': 'qa.xview',
    'matid': 'qa.matid',
    'names': 'qa.names',
    'tris': 'qa.tris',
    'textures': 'tex.check',
    'pivot': 'qa.pivot',
    'nudge': 'udim.nudge',
    'nudge_apply': 'udim.nudge',
    'atlas': 'atlas.npm',
    'atlas_apply': 'atlas.npm',
    'texel': 'udim.texel',
    'ucx': 'ucx.build',
    'ucx_apply': 'ucx.build',
    'cleanup': 'export.cleanup',
    'cleanup_apply': 'export.cleanup',
    'export': 'export.checked',
    'geojson': 'qa.geojson',
    'census': 'scene.census',
    'units': 'scene.units',
    'missing_maps': 'scene.missing_maps',
    'perimeter_drop': 'model.perimeter_drop',
    'triangulate': 'model.triangulate',
    'material_type': 'tex.material_type',
    'format_fix': 'tex.format_fix',
    'placeholders': 'tex.placeholders',
    'ucx_audit': 'ucx.audit',
    'ucx_triangulate': 'ucx.triangulate',
    'ucx_rename': 'ucx.rename',
    'ids_to_udims': 'udim.ids_to_udims',
    'sets_count': 'atlas.sets_count',
    'fbx_split': 'qa.fbx_split',
    'glass': 'qa.glass',
    'scene_hygiene': 'qa.scene_hygiene',
    'xform': 'qa.xform',
    'zero_area': 'qa.zero_area',
    'preflight': 'qa.preflight',
    'names_fix': 'qa.names_fix',
    'package': 'qa.package',
    'geojson_write': 'export.geojson_write',
    'ground_fbx': 'export.ground_fbx',
    'pivot_place': 'export.pivot_place',
    'zip': 'export.zip',
}
NO_SUITE_ENTRY = ()


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load(PKG / 'ui_model.py', 'agr_tools_ui_model_reqs')


def _suite_rows():
    data = json.loads((ROOT / 'docs/plans/agr-tools-suite.json').read_text(encoding='utf-8'))
    rows = {}
    for row in data['rows']:
        raw = row['reqs']
        rows[row['id']] = set() if raw.strip() == '-' else set(raw.split())
    return rows


SUITE = _suite_rows()


def test_every_action_id_is_mapped_or_named_without_a_suite_entry():
    ids = {a.id for a in m.ACTIONS}
    mapped = set(SUITE_KEY)
    bare = set(NO_SUITE_ENTRY)
    overlap = mapped & bare
    if overlap:
        raise KeyError('action both mapped and without a suite entry: ' + repr(sorted(overlap)))
    missing = sorted(ids - mapped - bare)
    if missing:
        raise KeyError('unmapped AGR Tools action: ' + repr(missing[0] if len(missing) == 1 else missing))
    extra = sorted((mapped | bare) - ids)
    if extra:
        raise KeyError('suite map names unknown AGR Tools action: ' + repr(extra[0] if len(extra) == 1 else extra))


@pytest.mark.parametrize('action_id', sorted(SUITE_KEY))
def test_action_reqs_equal_suite(action_id):
    key = SUITE_KEY[action_id]
    assert key in SUITE, key
    assert set(m.action(action_id).reqs) == SUITE[key]


def test_geojson_tooltip_cites_gj1_not_a_free_label():
    tip = m.tooltip(m.action('geojson'))
    assert 'GJ-1' in tip
    assert 'VPM GeoJSON' not in tip
