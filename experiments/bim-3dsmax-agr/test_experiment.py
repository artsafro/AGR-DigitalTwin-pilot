"""Offline controls for the comparator and assertions over real native evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
from twinqa.geometry.mesh import from_dump

BASE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('agr_e1_analyze', BASE/'analyze.py')
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def synthetic():
    return {'meshes': [{'name': 'synthetic', 'vertices': [[0,0,0],[1,0,0],[0,1,0],
              [0,0,1],[1,0,1],[0,1,1]], 'triangles': [[0,1,2],[3,4,5]],
              'material_ids': [1,21], 'polygon_sizes': [3,3]}],
            'helpers': [{'name':'LEVEL_0','location':[0,0,0]}]}


def test_bijection_accepts_reordering_and_float_noise():
    ref = synthetic()
    data = copy.deepcopy(ref)
    data['meshes'][0]['triangles'] = [[4,5,3],[1,2,0]]
    data['meshes'][0]['material_ids'] = [21,1]
    data['meshes'][0]['vertices'][0][0] += 4e-7
    result = analyze.compare(data,ref)
    assert result['geometry_winding_equal']
    assert result['finish_triangles_correct'] == 2
    assert 0 < result['bijective_corner_max_mm'] < .001


@pytest.mark.parametrize('mutation', ['reverse','delete','duplicate','move'])
def test_bijection_rejects_topology_or_coordinate_mutation(mutation):
    ref = synthetic()
    data = copy.deepcopy(ref)
    mesh = data['meshes'][0]
    if mutation == 'reverse':
        mesh['triangles'][0].reverse()
    elif mutation == 'delete':
        mesh['triangles'].pop()
        mesh['material_ids'].pop()
    elif mutation == 'duplicate':
        mesh['triangles'][1] = mesh['triangles'][0][:]
    else:
        mesh['vertices'][0][0] += .0005
    assert analyze.correspondence(from_dump(data),from_dump(ref))[0] is None


def test_wrong_finish_not_hidden_by_geometry_pass():
    ref = synthetic()
    data = copy.deepcopy(ref)
    data['meshes'][0]['material_ids'] = [21,1]
    result = analyze.compare(data,ref)
    assert result['geometry_winding_equal']
    assert result['finish_triangles_correct'] == 0
    assert result['finish_area_correct_percent'] == 0


def test_ambiguous_triangles_rejected():
    data = synthetic()
    data['meshes'][0]['triangles'][1] = [0,1,2]
    assert analyze.correspondence(from_dump(data),from_dump(data))[0] is None


def test_real_native_evidence():
    evidence = json.loads((BASE/'evidence.json').read_text())
    assert evidence['sources_unchanged'] and not evidence['delivery_passed']
    rows = evidence['rows']
    assert len(rows) == 12
    assert len({(r['bench'],r['arm'],r['rep']) for r in rows}) == 12
    for row in rows:
        assert len(row['checks']) == 10
        assert row['geometry_winding_equal']
        assert row['vertex_delta'] == row['triangle_delta'] == 0
        assert row['bijective_corner_max_mm'] < .001
        assert row['helpers_names_equal'] and row['helpers_max_mm'] < .001
        failed = {c['id'] for c in row['checks'] if c['status'] != 'pass'}
        if row['arm'] == 'prototype':
            assert not failed
            assert row['finish_triangles_correct'] == row['finish_triangles_total']
            assert row['material_histogram'] == row['reference_material_histogram']
            assert abs(row['finish_area_correct_percent']-100) < 1e-8
        else:
            assert failed == {'mesh','opening_planes'}
            assert set(row['material_histogram']) == {'1'}
    for arm in ['baseline','prototype']:
        assert len(evidence['native'][arm]['rows']) == 6
        assert evidence['native'][arm]['inventory']['initial_objects'] == 0
        assert evidence['native'][arm]['inventory']['document'] == ''
    assert len(evidence['native']['readback']['rows']) == 14
