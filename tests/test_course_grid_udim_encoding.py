"""new-case: quantify UV encoding AFTER the absolute UDIM offset is applied."""
import numpy as np
import pytest
from tools.materials.course_grid_native import encode_triangle_uv


def singular(xyz, uv):
    e = np.asarray(xyz)[1:] - xyz[0]
    a = e[0] / np.linalg.norm(e[0])
    n = np.cross(*e); n /= np.linalg.norm(n)
    return np.linalg.svd(np.linalg.solve(np.c_[e @ a, e @ np.cross(n, a)],
        (np.asarray(uv)[1:] - uv[0]) * 4096), compute_uv=False)


@pytest.mark.parametrize('tile_u', [0, 1, 9])
def test_absolute_tile_encoding_is_native_and_measured_at_final_coordinates(tile_u):
    xyz = [[0., 0., 0.], [1., 0., 0.], [0., .01, 0.]]
    ideal = [[tile_u + .3, .4], [tile_u + .3 + 512.1/4096, .4],
             [tile_u + .3, .4 + .01*512.1/4096]]
    out = encode_triangle_uv(xyz, ideal, tile_px=4096, tile_u=tile_u)
    assert np.asarray(out['uv'], dtype=np.float32).astype(float).tolist() == out['uv']
    measured = singular(xyz, out['uv'])
    assert measured == pytest.approx(out['singular_px_m'], abs=1e-8)
    assert 512 <= min(measured) <= max(measured) <= 1706
    assert max(measured)/min(measured) <= 1.02
    assert np.max(np.linalg.norm(np.asarray(out['uv'])-ideal, axis=1))*4096 <= .01
    assert all(tile_u <= p[0] <= tile_u+1 and 0 <= p[1] <= 1 for p in out['uv'])


@pytest.mark.parametrize('tile_u', [True, -1, 10, 1., float('nan'), float('inf')])
def test_absolute_tile_encoding_rejects_unsupported_tile(tile_u):
    with pytest.raises(ValueError, match='tile_u'):
        encode_triangle_uv([[0,0,0],[1,0,0],[0,1,0]],
            [[.2,.2],[.4,.2],[.2,.4]], tile_px=4096, tile_u=tile_u)


def test_absolute_tile_encoding_cannot_move_into_another_tile():
    with pytest.raises(ValueError, match='encoding exceeds'):
        encode_triangle_uv([[0,0,0],[1,0,0],[0,1,0]],
            [[.2,.2],[.325,.2],[.2,.325]], tile_px=4096, tile_u=1)
