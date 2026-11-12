"""new-case: multi-source prototype inventory bounds, duplicates and schema probes."""
import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('roof_parts_set', Path(__file__).resolve().parents[2]/'tools/library/roof_parts.py')
roof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roof)


def source_set(count=8):
    rows = [dict(id=f'R{i}', name='Source part', component=f'G-c{i}', faces=[i],
                 source_object='SM_Source', triangles=2, material_slot=0) for i in range(count)]
    return {'schema': 'roof-extraction-set/1', 'plans': [
        {'schema': 'roof-extraction/1', 'source_sha256': 'a'*64, 'assets': rows}]}


def test_source_set_valid_and_rejects_conflicts():
    doc = source_set()
    assert roof.validate_set(doc) == doc
    other = copy.deepcopy(doc['plans'][0])
    doc['plans'].append(other)
    with pytest.raises(ValueError, match='duplicate'):
        roof.validate_set(doc)
    other['source_sha256'] = 'b'*64
    with pytest.raises(ValueError, match='duplicate'):
        roof.validate_set(doc)


@pytest.mark.parametrize('count', [0, 1, 7, 13, 25])
def test_prototype_count_boundaries_fail_closed(count):
    with pytest.raises(ValueError, match='assets|8.*12'):
        roof.validate_set(source_set(count))


@pytest.mark.parametrize('count', [8, 12])
def test_prototype_count_inclusive_boundaries(count):
    doc = source_set(count)
    assert roof.validate_set(doc) == doc


@pytest.mark.parametrize('value', [{}, None, {'schema':'roof-extraction-set/2','plans':[]},
                                   {'schema':'roof-extraction-set/1','plans':[]}])
def test_partial_sets_fail_closed(value):
    with pytest.raises(ValueError, match='schema|plans'):
        roof.validate_set(value)
