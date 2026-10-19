"""Narrowed #216 contract; synthetic geometry is not a verified plant asset."""
import json
from pathlib import Path

import pytest

from dt_ai.materials import flora_catalogue as fc

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / 'library/flora' / name).read_text(encoding='utf-8'))


def square(tiled=False, hole=False):
    """The round-4 solid/tessellated/10 cm hole witness, constructed in metres."""
    faces = []
    size = 10 if tiled else 1
    for x in range(size):
        for y in range(size):
            if hole and (x, y) == (2, 1):
                continue
            a, b = x / size, y / size
            c, d = (x + 1) / size, (y + 1) / size
            faces.extend([[[a, b, 0], [c, b, 0], [c, d, 0]],
                          [[a, b, 0], [c, d, 0], [a, d, 0]]])
    return faces


@pytest.mark.parametrize('hole', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_round4_surfaces_are_unverified(hole, reverse):
    left, right = square(), square(tiled=True, hole=hole)
    if reverse:
        left, right = right, left
    result = fc.compare_surfaces(left, right)
    assert result['relation'] == 'unverified'
    assert result['translation_dev_m'] is None
    assert result['scaled_dev_rel'] is None


@pytest.mark.parametrize('legacy', ['same', 'scaled_copy', 'distinct', 'unknown', 'unverified'])
def test_identity_never_drops_an_explicit_hp(legacy):
    entries = [dict(id=key, scene='Synthetic.max', source_name=key,
                    profile_raw=[profile], triangles=tris, hidden=False,
                    dimensions_m=[1., 1., 1.])
               for key, profile, tris in [('lp', 'LP', 2), ('hp', 'HP', 198)]]
    selected = fc.select_sources(entries, {frozenset(('lp', 'hp')): legacy})
    assert selected['VPM']['entry_id'] == 'hp'
    assert selected['vpm_identity'] == 'unverified'
    assert selected['vpm_evidence'] == dict(relation='unverified', translation_dev_m=None, scaled_dev_rel=None)
    assert selected['merged'] == []


def test_current_library_records_survive_without_identity():
    previous = load('catalogue.json')
    audit = json.loads((ROOT / 'experiments/flora-library-audit/catalogue.json').read_text(encoding='utf-8'))
    rebuilt = fc.build(audit, load('species-curation.json'), load('maps.json'), previous)
    stable = ('latin', 'npm', 'vpm', 'objects', 'vpm_status', 'material_id', 'maps')
    assert [[row[k] for k in stable] for row in rebuilt['species']] == [
        [row[k] for k in stable] for row in previous['species']]
    assert {row['vpm_identity'] for row in rebuilt['species'] if row['vpm']} == {'unverified'}
    assert fc.check(rebuilt) == []


@pytest.mark.parametrize('legacy', ['same', 'scaled_copy', 'distinct', 'unknown', 'unverified'])
def test_frozen_lp_hp_choices_are_not_filtered(legacy):
    entries = [dict(id=key, scene='Synthetic.max', source_name=key,
                    profile_raw=['LP -> HP'], triangles=12, hidden=False,
                    dimensions_m=[1., 1., 1.]) for key in ('np', 'vp')]
    selection = dict(NPM='np', VPM='vp', vpm_status='available')
    selected = fc.select_sources(entries, {frozenset(('np', 'vp')): legacy}, selection)
    assert selected['NPM']['entry_id'] == 'np'
    assert selected['VPM']['entry_id'] == 'vp'
    assert selected['vpm_identity'] == 'unverified'
    assert selected['merged'] == []


@pytest.mark.parametrize('selection', [
    {},
    dict(NPM='missing', VPM=None, vpm_status='unconfirmed'),
    dict(NPM='np', VPM='missing', vpm_status='available'),
    dict(NPM='vp', VPM=None, vpm_status='none'),
    dict(NPM='np', VPM='vp', vpm_status='none'),
    dict(NPM='np', VPM=None, vpm_status='available'),
])
def test_invalid_frozen_choice_fails_instead_of_reselecting(selection):
    entries = [dict(id=key, scene='Synthetic.max', source_name=key,
                    profile_raw=[profile], triangles=12, hidden=False,
                    dimensions_m=[1., 1., 1.]) for key, profile in [('np', 'LP'), ('vp', 'HP')]]
    with pytest.raises(ValueError, match='library_selection'):
        fc.select_sources(entries, selection=selection)


def test_checker_rejects_verified_identity_claims():
    catalogue = load('catalogue.json')
    row = next(row for row in catalogue['species'] if row['vpm'])
    row['vpm_identity'] = 'verified_distinct'
    row['vpm_evidence'] = dict(relation='distinct', translation_dev_m=.1, scaled_dev_rel=.1)
    assert any('vpm_identity' in finding for finding in fc.check(catalogue))


def test_identity_document_has_no_classification_claims():
    document = load('geometry-identity.json')
    assert {row['relation'] for row in document['pairs']} == {'unverified'}
    assert all(row['translation_dev_m'] is None and row['scaled_dev_rel'] is None for row in document['pairs'])
    assert '#305' in document['method']
