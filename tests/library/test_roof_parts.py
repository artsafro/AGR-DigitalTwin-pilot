"""new-case: fail-closed roof extraction plans and source coverage probes."""
import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('roof_parts', Path(__file__).resolve().parents[2]/'tools/library/roof_parts.py')
roof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roof)


def plan():
    return {'schema': 'roof-extraction/1', 'source_sha256': 'a'*64,
            'assets': [{'id': 'R01', 'name': 'Open shaft body', 'component': 'G01-o0-c12',
                        'faces': [0, 1], 'source_object': 'SM_Source',
                        'triangles': 2, 'material_slot': 0}]}


def test_valid_plan_is_returned_without_mutating():
    doc = plan()
    before = copy.deepcopy(doc)
    assert roof.validate_plan(doc) == doc
    assert doc == before


@pytest.mark.parametrize('field,value', [('schema', 'roof-extraction/2'), ('assets', []),
                                        ('source_sha256', 'z'*64), ('assets', None)])
def test_reject_partial_or_unsupported_plan(field, value):
    doc = plan()
    doc[field] = value
    with pytest.raises(ValueError, match='schema|assets|sha256'):
        roof.validate_plan(doc)


@pytest.mark.parametrize('field,value', [('faces', []), ('faces', [0, 0]), ('faces', [-1]),
                                        ('faces', [True]), ('triangles', 0), ('triangles', float('nan')),
                                        ('triangles', float('inf')), ('material_slot', True),
                                        ('material_slot', -1), ('id', '../R01'),
                                        ('component', ''), ('source_object', '')])
def test_reject_invalid_asset(field, value):
    doc = plan()
    doc['assets'][0][field] = value
    with pytest.raises(ValueError):
        roof.validate_plan(doc)


def test_reject_duplicate_ids_and_component_bindings():
    for field in ('id', 'component'):
        doc = plan()
        other = copy.deepcopy(doc['assets'][0])
        other['id'] = 'R02'
        other['component'] = 'G01-o0-c13'
        other[field] = doc['assets'][0][field].lower()
        doc['assets'].append(other)
        with pytest.raises(ValueError, match='duplicate'):
            roof.validate_plan(doc)


def test_reject_overlapping_face_claims():
    doc = plan()
    other = copy.deepcopy(doc['assets'][0])
    other.update(id='R02', component='G01-o0-c13', faces=[1, 2])
    doc['assets'].append(other)
    with pytest.raises(ValueError, match='face'):
        roof.validate_plan(doc)


def test_no_implicit_material_or_unknown_key():
    doc = plan()
    del doc['assets'][0]['material_slot']
    with pytest.raises(ValueError, match='material_slot'):
        roof.validate_plan(doc)
    doc = plan()
    doc['assets'][0]['unknown'] = 1
    with pytest.raises(ValueError, match='unknown'):
        roof.validate_plan(doc)
