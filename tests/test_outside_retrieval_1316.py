"""Regression for #1316 portable map routes and honest missing-byte states.

Pattern: n/a | new-case: version-bound A101 retrieval, approval and immutable v003 inputs.
"""
import hashlib
from copy import deepcopy

import pytest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_flora_map_routes_do_not_depend_on_deleted_workstation_cache():
    maps = json.loads((ROOT / 'library/flora/maps.json').read_text(encoding='utf-8'))
    assert maps
    for latin, record in maps.items():
        for slot in ('diffuse', 'opacity'):
            path = record[slot]
            assert path is None or path.startswith('G:/Мой диск/AGR-assets/flora/'), (latin, slot, path)
        if not record['diffuse'] or not record['opacity']:
            assert record['review_status'] == 'missing', latin
            assert record['evidence'], latin


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def identity_hash(identity):
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def test_v003_snapshot_is_immutable():
    snapshot = ROOT / 'library/flora/maps-v003-snapshot.json'
    canonical = snapshot.read_text(encoding='utf-8').replace('\r\n', '\n').encode()
    assert hashlib.sha256(canonical).hexdigest() == 'a20972b8bd7e94240416d7c70035d107be71c4f58789159dbc5b069bdb67afd6'
    current = load('library/flora/maps.json')
    historical = load('library/flora/maps-v003-snapshot.json')
    assert current.keys() == historical.keys()
    for latin, old in historical.items():
        assert current[latin]['evidence'].endswith(old['evidence'])
        if old['diffuse'].startswith('C:/x/'):
            assert current[latin]['review_status'] == 'missing'
        else:
            assert current[latin] == old


def test_current_maps_cannot_silently_rebind_frozen_light_geometry():
    from dt_ai.materials.flora_catalogue import build
    with pytest.raises(ValueError, match='maps changed'):
        build(load('experiments/flora-library-audit/catalogue.json'),
              load('library/flora/species-curation.json'),
              load('library/flora/maps.json'), load('library/flora/catalogue.json'))


def test_tilia_approval_is_bound_to_exact_version():
    verdict = load('library/flora/visual-verdict-1316.json')
    release = load('library/flora/a101-native-v002.json')
    variant = next(v for v in release['variants'] if v['object'] == 'lipa_t1_h550_low')
    digest = identity_hash(variant['identity'])
    assert variant['version_sha256'] == verdict['version_sha256'] == digest
    assert verdict['identity'] == variant['identity']
    assert variant['review_status'] == verdict['status'] == 'approved'
    assert verdict['answer'] == 'Да, липа норм'
    assert verdict['answer_source']['in_reply_to'] == verdict['transport']['message_id'] == '4696'
    maps_version = load('library/flora/maps.json')['Tilia cordata']['versions'][digest]
    assert maps_version['review_status'] == 'approved'
    assert maps_version['object'] == variant['object']
    assert 'NOT Tilia_cordata_NPM/VPM' in maps_version['catalogue_geometry_compatibility']
    assert verdict['preview']['sha256'] == '8ceed9e2cca249b8565cff32f7ca3d7c89e5d855eb11e86d7d69f9bfbb295b64'


@pytest.mark.parametrize('field', ['scene_sha256', 'object', 'rgba_sha256', 'diffuse_sha256', 'opacity_sha256'])
def test_version_identity_mutations_do_not_reuse_approval(field):
    verdict = load('library/flora/visual-verdict-1316.json')
    changed = deepcopy(verdict['identity'])
    changed[field] += 'changed'
    assert identity_hash(changed) != verdict['version_sha256']


def test_unanswered_variants_are_not_approved():
    release = load('library/flora/a101-native-v002.json')
    assert len(release['variants']) == 4
    for variant in release['variants']:
        assert variant['version_sha256'] == identity_hash(variant['identity'])
        assert variant['catalogue_geometry_compatibility'] == 'not_established'
        if variant['object'].endswith('_high'):
            assert variant['review_status'] == 'pending'
            assert 'verdict' not in variant
        if variant['cultivar']:
            assert variant['cultivar'] == 'Royal Red'
        assert len(variant['files']) == 3
        assert len({f['path'] for f in variant['files']}) == 3
        assert all(f['bytes'] > 0 and len(f['sha256']) == 64 for f in variant['files'])


def test_three_asset_selection_has_complete_explicit_boundaries():
    selection = load('library/outside-retrieval-v001.json')
    assert len(selection['assets']) == 3
    assert [len(a['files']) for a in selection['assets']] == [1, 4, 1]
    paths = []
    for asset in selection['assets']:
        assert asset['boundary'] and asset['authority']
        for record in asset['files']:
            assert record['download_url'].startswith('https://drive.usercontent.google.com/download?id=')
            assert record['bytes'] > 0
            assert len(record['sha256']) == 64
            assert not record['path'].startswith(('/', 'C:', 'G:'))
            assert '..' not in Path(record['path']).parts
            paths.append(record['path'])
    assert len(paths) == len(set(paths)) == 6
