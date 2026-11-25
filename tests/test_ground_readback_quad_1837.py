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


def _build(tmp_path, name, data, *extra):
    src, fbx = tmp_path / f'{name}.json', tmp_path / f'{name}.fbx'
    src.write_text(json.dumps(data))
    run = _blender('build', src, fbx, 'Synthetic', 'SYNTHETIC_LOCAL', *extra)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    return fbx


def _readback(tmp_path, fbx, name, data, *extra):
    src, rep = tmp_path / f'{name}.src.json', tmp_path / f'{name}.readback.json'
    src.write_text(json.dumps(data))
    run = _blender('readback', fbx, src, rep, *extra)
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


@pytest.fixture(scope='module')
def tile_exports(tmp_path_factory):
    if not BLENDER.exists():
        pytest.skip('Blender 5.1.2 required')
    tmp = tmp_path_factory.mktemp('gr1854')
    data = mesh()
    data['uv'][1] = [[1, 0], [2, 0], [1, 1]]
    swapped = {**data, 'uv': [
        [[u + shift, v] for u, v in face] for face, shift in zip(data['uv'], [1, -1])
    ]}
    return tmp, data, _build(tmp, '0001_Decoy_Ground', data, '--profile', 'vpm'), _build(
        tmp, 'swapped', swapped, '--profile', 'vpm')


@pytest.mark.parametrize('case,status', [
    ('matched', 'pass'), ('swapped', 'fail'), ('missing', 'not_measured'), ('empty', 'not_measured'),
    ('partial', 'fail'), ('crossing', 'fail'), ('nonfinite', 'fail'), ('unsupported', 'fail'),
])
def test_vpm_readback_udim_by_material(tile_exports, case, status):
    tmp, data, fbx, swapped = tile_exports
    expected = dict(data)
    if case == 'missing':
        del expected['uv']
    elif case == 'empty':
        expected['uv'] = []
    elif case == 'partial':
        expected['uv'] = data['uv'][:1]
    elif case in {'crossing', 'nonfinite', 'unsupported'}:
        u = {'crossing': 2.25, 'nonfinite': float('nan'), 'unsupported': '2'}[case]
        expected['uv'] = [data['uv'][0], [[1, 0], [u, 0], [1, 1]]]
    report = _readback(tmp, swapped if case == 'swapped' else fbx, case, expected)
    tile, lawn = ('M_Synthetic_Ground_' + slot for slot in ('Tile', 'Lawn'))
    facts = report['uv_tiles']
    assert facts['tiles'] == [1001, 1002]
    assert facts['by_material'] == ({tile: [1002], lawn: [1001]} if case == 'swapped'
                                    else {tile: [1001], lawn: [1002]})
    assignment = facts['udim_assignment']
    assert assignment['status'] == status
    if case in ('matched', 'swapped'):
        assert assignment['differences'] == ({
            tile: {'expected': [1001], 'observed': [1002]},
            lawn: {'expected': [1002], 'observed': [1001]},
        } if case == 'swapped' else {})


@pytest.mark.parametrize('case', ['missing_profile', 'stale_profile', 'npm'])
def test_readback_without_vpm_profile_evidence(tile_exports, tmp_path, case):
    _, data, fbx, _ = tile_exports
    copied = tmp_path / ('SM_Synthetic_Ground.fbx' if case == 'missing_profile' else fbx.name)
    copied.write_bytes(fbx.read_bytes())
    if case != 'missing_profile':
        meta = json.loads(Path(str(fbx) + '.export_meta.json').read_text(encoding='utf-8'))
        if case == 'stale_profile':
            meta['exported_sha256'][fbx.name] = '0' * 64
        else:
            # Explicit NPM atlas: deliberately shares tile 1001 across source slots.
            atlas = {**data, 'uv': [data['uv'][0], [[0, 0], [1, 0], [0, 1]]]}
            copied = _build(tmp_path, 'SM_Synthetic_Ground', atlas, '--profile', 'npm')
        if case == 'stale_profile':
            Path(str(copied) + '.export_meta.json').write_text(json.dumps(meta))
    facts = _readback(tmp_path, copied, case, data, 4096, 0, 5000)['uv_tiles']
    if case == 'npm':
        assert facts == {'tiles': [1001], 'straddling': 0, 'mirrored_faces': 0}
    else:
        assert facts['udim_assignment']['status'] == 'not_measured'
        assert facts['tiles'] == [1001, 1002]


def test_readback_report_cannot_alias_source(tile_exports):
    tmp, data, fbx, _ = tile_exports
    src = tmp / 'alias.src.json'
    src.write_text(json.dumps(data))
    original = src.read_bytes()
    alias = tmp / 'hardlink.json'
    alias.hardlink_to(src)
    for dst in (src, alias):
        run = _blender('readback', fbx, src, dst)
        assert run.returncode != 0
        assert src.read_bytes() == alias.read_bytes() == original
