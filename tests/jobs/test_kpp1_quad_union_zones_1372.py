"""new-case: #1372 KPP1 quad master v002 - the R1 overlap zone plan (plan_union_zones.py) fails closed.

The zone merge <= 5 mm is the quad-master-only exception to D254 [D289].
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("plan_union_zones_1372",
                                              ROOT / "jobs/KPP1/quad-1372/plan_union_zones.py")
puz = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(puz)


def _quad(x, y0, y1, z0, z1, flip=False):
    """Two triangles of the rectangle at plane x (normal +x, or -x when flipped)."""
    p = [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]
    return p[::-1] if flip else p


def _mesh(*rects):
    v, faces = [], []
    for r in rects:
        i = len(v)
        v += r
        faces += [(i, i + 1, i + 2), (i, i + 2, i + 3)]
    return np.array(v, dtype=np.float64), tuple(faces)


def test_facing_pair_is_one_zone_on_the_axis_plane():
    v, f = _mesh(_quad(1.0, 0, 1, 0, 1), _quad(1.0003, 0, 1, 0, 1, flip=True))
    z = puz.zones(v, f, [(0, 2), (1, 3), (0, 3)])
    assert len(z) == 1 and z[0]["axis"] == 0
    assert z[0]["faces"] == [0, 1, 2, 3]
    assert abs(z[0]["value"] - 1.0) <= 0.0003 and z[0]["spread_m"] <= 0.0003 + 1e-12
    assert len(z[0]["centroids"]) == 4


def test_two_zones_on_one_plane_share_the_snap_value():
    v, f = _mesh(_quad(2.0, 0, 1, 0, 1), _quad(2.0004, 0, 1, 0, 1, flip=True),
                 _quad(2.0012, 5, 6, 0, 1), _quad(2.0012, 5, 6, 0, 1, flip=True))
    z = puz.zones(v, f, [(0, 2), (4, 6)])
    assert len(z) == 2 and z[0]["value"] == z[1]["value"]


def test_not_axis_aligned_zone_is_an_error():
    a = [(0, 0, 0), (1, 0.5, 0), (1, 0.5, 1)]
    b = [(0, 0, 0.001), (1, 0.5, 1.001), (1, 0.5, 0.001)]
    v = np.array(a + b, dtype=np.float64)
    with pytest.raises(ValueError, match="not on an axis plane"):
        puz.zones(v, ((0, 1, 2), (3, 4, 5)), [(0, 1)])


def test_spread_above_5_mm_is_an_error_and_exactly_5_mm_passes():
    v, f = _mesh(_quad(0.0, 0, 1, 0, 1), _quad(0.0051, 0, 1, 0, 1, flip=True))
    with pytest.raises(ValueError, match="mm"):
        puz.zones(v, f, [(0, 2)])
    v, f = _mesh(_quad(0.0, 0, 1, 0, 1), _quad(0.005, 0, 1, 0, 1, flip=True))
    assert puz.zones(v, f, [(0, 2)])[0]["spread_m"] <= 0.005 + puz.FLOAT_TOL_M


def test_degenerate_zone_face_is_an_error():
    v = np.array([(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 0, 0), (0, 1, 0), (0, 0, 1)], dtype=np.float64)
    with pytest.raises(ValueError, match="degenerate"):
        puz.zones(v, ((0, 1, 2), (3, 4, 5)), [(0, 1)])


def test_no_pairs_gives_no_zone():
    v, f = _mesh(_quad(0.0, 0, 1, 0, 1))
    assert puz.zones(v, f, []) == []


def test_cli_refuses_existing_output_alias_and_wrong_source(tmp_path):
    src = tmp_path / "SM_Kpp_1.fbx"
    src.write_bytes(b"not the approved R1")
    out = tmp_path / "zones.json"
    with pytest.raises(SystemExit, match="not the approved"):
        puz.main([str(src), str(out)])
    assert not out.exists()
    with pytest.raises(SystemExit, match="exists or is the input"):
        puz.main([str(src), str(src)])
    out.write_text("{}")
    with pytest.raises(SystemExit, match="exists or is the input"):
        puz.main([str(src), str(out)])
    assert json.loads(out.read_text()) == {}
    assert src.read_bytes() == b"not the approved R1"
