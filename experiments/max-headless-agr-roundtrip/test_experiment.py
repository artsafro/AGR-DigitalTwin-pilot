"""Synthetic reader checks plus real-file checks when this experiment has been run."""
import json
import struct
from pathlib import Path
import numpy as np
import pytest

from analyze import compare, point_surface_max
from offline import read_fbx, read_obj
from prepare import BENCHES, NATIVE, SCRATCH


def test_obj_negative_indices(tmp_path):
    p = tmp_path / 'test.obj'
    p.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3/1 -2/2 -1/3\n')
    data = read_obj(p)
    assert data['meshes'][0]['triangles'] == [[0, 1, 2]]
    assert data['units'] == 'unspecified'


def test_empty_obj_rejected(tmp_path):
    p = tmp_path / 'empty.obj'
    p.write_text('# SYNTHETIC empty fixture\n')
    with pytest.raises(ValueError, match='Empty OBJ'):
        read_obj(p)


def test_fbx_bad_header(tmp_path):
    p = tmp_path / 'bad.fbx'
    p.write_bytes(b'not an FBX')
    with pytest.raises(ValueError, match='Binary FBX'):
        read_fbx(p)


def test_fbx_unsupported_version(tmp_path):
    p = tmp_path / 'unsupported.fbx'
    p.write_bytes(b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7500))
    with pytest.raises(ValueError, match='7400'):
        read_fbx(p)


@pytest.mark.parametrize('point, expected', [([0.2,0.2,1],1), ([0.2,0.2,0],0), ([2,0,0],1)])
def test_point_surface_distance(point, expected):
    tri = np.array([[[0,0,0], [1,0,0], [0,1,0]]], dtype=float)
    assert point_surface_max(np.array([point]), tri) == pytest.approx(expected)


@pytest.mark.parametrize('bench', BENCHES)
@pytest.mark.parametrize('rep', range(3))
def test_actual_fbx_agrees_with_native(bench, rep):
    path = NATIVE / (bench + '-r' + str(rep) + '.fbx')
    if not path.exists():
        pytest.skip('Run prepare.py and native_job.py through dcc_batch first')
    offline = read_fbx(path)
    native = json.loads((NATIVE / (path.stem + '-fbx-readback.json')).read_text())
    diff = compare(offline, native)
    assert diff['symmetric_vertex_max_mm'] < 1e-6
    assert diff['vertices'] == sum(len(m['vertices']) for m in native['meshes'])
    assert diff['triangles'] == sum(len(m['triangles']) for m in native['meshes'])
    assert offline['fbx_settings']['UnitScaleFactor'] == 100


@pytest.mark.parametrize('bench', BENCHES)
def test_obj_raw_axis_mismatch_is_visible(bench):
    path = NATIVE / (bench + '-r0.obj')
    if not path.exists():
        pytest.skip('Native experiment exports unavailable')
    offline = read_obj(path)
    engine = json.loads((SCRATCH / bench / 'engine.json').read_text())
    assert compare(offline, engine)['bbox_max_mm'] >= 9000
    for m in offline['meshes']:
        m['vertices'] = [[x,-z,y] for x,y,z in m['vertices']]
    corrected = compare(offline, engine)
    assert corrected['bbox_max_mm'] < 1e-6
    assert corrected['symmetric_vertex_max_mm'] < 0.1
