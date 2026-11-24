"""#1837: Ground FBX readback matches quads (and triangles) to the source mesh by the degree-aware centre.

Native Blender 5.1 headless build + readback of synthetic, non-origin fixtures (no mocked Blender API).
"""
import json
import subprocess
from pathlib import Path

import pytest

BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
SCRIPT = 'tools/blender/ground_json_to_fbx.py'

# SYNTHETIC: planar slope z = 150 + 0.1 x, far from the origin (placement offset is non-zero).
X0, Y0 = 1000.5, 2000.25
_XY = [(0, 0), (2, 0), (2, 2), (0, 2), (4, 1)]
VERTS = [[X0 + x, Y0 + y, round(150 + 0.1 * (X0 + x), 6)] for x, y in _XY]
QUAD, TRI = [0, 1, 2, 3], [1, 4, 2]


def mesh(quad=QUAD, mat=(0, 1)) -> dict:
    return dict(verts=VERTS, faces=[list(quad), TRI], slots=['Tile', 'Lawn'], mat=list(mat), level=[0, 0],
                uv=[[[0, 0], [1, 0], [1, 1], [0, 1]], [[1, 0], [1, 0.5], [1, 1]]])


def _blender(*args):
    return subprocess.run([str(BLENDER), '--background', '--factory-startup', '--threads', '1',
                           '--python-exit-code', '1', '--python', SCRIPT, '--', *map(str, args)],
                          capture_output=True, text=True)


def _build(tmp_path, name, data):
    src, fbx = tmp_path / f'{name}.json', tmp_path / f'{name}.fbx'
    src.write_text(json.dumps(data))
    run = _blender('build', src, fbx, 'Synthetic', 'SYNTHETIC_LOCAL')
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    return fbx


def _readback(tmp_path, fbx, name, data):
    src, rep = tmp_path / f'{name}.src.json', tmp_path / f'{name}.readback.json'
    src.write_text(json.dumps(data))
    run = _blender('readback', fbx, src, rep)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    return json.loads(rep.read_text())


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    if not BLENDER.exists():
        pytest.skip('Blender 5.1.2 required')
    tmp = tmp_path_factory.mktemp('gr1837')
    return tmp, _build(tmp, 'good', mesh()), _build(tmp, 'flipped', mesh(quad=QUAD[::-1]))


def test_quad_and_triangle_fully_matched_off_origin(built):
    tmp, fbx, _ = built
    facts = _readback(tmp, fbx, 'good', mesh())
    assert facts['placement_offset'][:2] == pytest.approx([X0 + 2, Y0 + 1])
    assert facts['faces_matched_by_centre'] == 2
    cm = facts['centre_match']
    assert (cm['expected'], cm['matched'], cm['unmatched_source_faces'], cm['unmatched_imported_faces']) == (2, 2, [], [])
    assert cm['complete'] is True
    assert facts['material_mismatch'] == 0 and facts['material_by_centre'] == 'pass'
    assert facts['surface_faces_normal_down'] == 0 and facts['surface_normals_by_centre'] == 'pass'
    assert facts['material_mismatch_by_order'] == 0


def test_wrong_quad_material_is_caught_by_centre(built):
    tmp, fbx, _ = built
    facts = _readback(tmp, fbx, 'wrongmat', mesh(mat=(1, 1)))  # JSON says the quad is Lawn; FBX has Tile
    assert facts['material_mismatch'] == 1, facts['faces_matched_by_centre']
    assert facts['centre_match']['matched'] == 2 and facts['centre_match']['complete'] is True
    assert facts['material_by_centre'] == 'fail'
    assert facts['material_mismatch_by_order'] == 1  # the separate order-based check stays intact


def test_reversed_surface_quad_normal_is_caught(built):
    tmp, _, flipped = built
    data = mesh(quad=QUAD[::-1])
    facts = _readback(tmp, flipped, 'flipped', data)
    assert facts['surface_faces_normal_down'] == 1, facts['faces_matched_by_centre']
    assert facts['centre_match']['matched'] == 2 and facts['centre_match']['complete'] is True
    assert facts['surface_normals_by_centre'] == 'fail'
    assert facts['material_mismatch'] == 0


def test_unmatched_quad_is_reported_not_passed(built):
    tmp, fbx, _ = built
    data = mesh()
    verts = [list(v) for v in VERTS]
    verts[3][0] += 0.5  # SYNTHETIC: source quad no longer matches the exported quad
    data['verts'] = verts
    facts = _readback(tmp, fbx, 'moved', data)
    cm = facts['centre_match']
    assert (cm['matched'], cm['unmatched_source_faces'], cm['unmatched_imported_faces']) == (1, [0], [0])
    assert cm['complete'] is False
    assert facts['material_mismatch'] == 0 and facts['material_by_centre'] == 'incomplete'
    assert facts['surface_normals_by_centre'] == 'incomplete'
