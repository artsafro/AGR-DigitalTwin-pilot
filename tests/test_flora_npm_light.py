"""Synthetic, no-DCC controls for #347 light-variant publication."""
import copy
import importlib
import json
from pathlib import Path

import pytest


def catalogue():
    return json.loads(Path('library/flora/catalogue.json').read_text(encoding='utf-8'))


def document(cat):
    variants = []
    for row in cat['species']:
        if row['material_id'] not in {103, 105, 204}:
            continue
        variants.append({
            'material_id': row['material_id'], 'object': row['objects']['NPM'] + '_light',
            'file': 'C:/x/flora-light/v001/flora-npm-light-v001.max', 'sha256': 'a' * 64,
            'fbx': 'C:/x/flora-light/v001/fbx/' + row['objects']['NPM'] + '_light.fbx',
            'fbx_sha256': 'b' * 64, 'triangles': {105:220, 204:32, 103:83}[row['material_id']],
            'height_m': row['height_m'], 'crown_diameter_m': row['crown_diameter_m'],
            'method': 'alpha-aware source triangle subset',
            'maps': {k: row['maps'][k] for k in ('diffuse','opacity')},
            'silhouettes': {v: {'iou': 0.9, 'hausdorff_upper_m': 0.01} for v in ('top','front','side','front45','side45')},
        })
    return {'schema': 'flora-npm-light-v1', 'variants': variants}


def test_missing_readback_triangles_is_rejected():
    # Import inside the test so pre-implementation RED is an assertion, not a collection error.
    assert importlib.util.find_spec('dt_ai.materials.flora_light') is not None, 'light validation feature missing'
    from dt_ai.materials.flora_light import validate_records
    cat = catalogue()
    data = document(cat)
    del data['variants'][0]['triangles']
    with pytest.raises(ValueError, match='triangles'):
        validate_records(cat, data)
