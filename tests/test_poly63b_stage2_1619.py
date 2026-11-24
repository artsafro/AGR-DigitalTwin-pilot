"""#1619 polygon stage 2, site-63 tower B (jobs/POLY63-B/stage2): Artem 2026-11-20 decisions in the plan hook -
AC baskets as low-poly boxes on the Revit bbox, 0.9 m capsules only for the 8 inner-corner openings. Synthetic only.

Pattern: n/a | new-case: tests/test_poly63b_stage2_1619.py - stage-2 plan hook of the training polygon, tower B.
"""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from adapters.max.agr_tools import capsule_core

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "jobs" / "POLY63-B" / "stage2" / "hooks" / "stage2_63b.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


b = _load(HOOK, "stage2_63b_test")


def _box_tris(cx, cy, w, d, z0, z1, deg):
    """Synthetic basket: an axis box of w x d x (z1-z0) rotated by deg in plan, as Revit-like triangles."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    pts = []
    for z in (z0, z1):
        for x, y in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
            pts.append([cx + c * x - s * y, cy + s * x + c * y, z])
    quads = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return np.array([[pts[q[0]], pts[q[k]], pts[q[k + 1]]] for q in quads for k in (1, 2)])


@pytest.mark.parametrize("deg", [0.0, 23.0, 90.0, 137.5])
def test_basket_box_is_closed_outward_quad_box_on_revit_bbox(deg):
    tri = _box_tris(10.0, -4.0, 0.9, 0.55, 24.42, 26.15, deg)
    el, size = b.basket_box(tri, "SM_ACBasket_01")
    assert el["collection"] == "Stage2_Baskets" and el["mats"] == ["AC_Basket"] * 6
    assert len(el["verts"]) == 8 and all(len(f) == 4 for f in el["faces"]) and len(el["faces"]) == 6
    assert sorted(size[:2]) == pytest.approx([0.55, 0.9], abs=1e-6) and size[2] == pytest.approx(1.73, abs=1e-6)
    assert not capsule_core.open_edges(el["faces"]) and not capsule_core.bad_edges(el["faces"])
    vol = capsule_core.signed_volume(el["verts"], el["faces"])
    assert vol == pytest.approx(0.9 * 0.55 * 1.73, rel=1e-6)  # positive = outward normals
    v = np.array(el["verts"])
    assert np.abs(v.mean(0)[:2] - [10.0, -4.0]).max() < 1e-6


def test_basket_box_rejects_degenerate_plan():
    with pytest.raises(ValueError):
        b.basket_box(np.zeros((2, 3, 3)), "SM_ACBasket_00")


def test_simplify_rim_drops_t_junction_vertices_only():
    rim = [[0, 0, 0], [0.4, 0, 0], [1.5, 0, 0], [1.5, 0, 1.97], [0.7, 0, 1.97], [0, 0, 1.97], [0, 0, 1.0]]
    out = b.simplify_rim(rim)
    assert out.tolist() == [[0, 0, 0], [1.5, 0, 0], [1.5, 0, 1.97], [0, 0, 1.97]]
    l_shape = [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0.5, 0, 1], [0.5, 0, 2], [0, 0, 2]]
    assert len(b.simplify_rim(l_shape)) == 6  # real corners stay


def test_shallow_capsules_are_exactly_the_approved_inner_corner_pairs():
    assert b.SHALLOW_DEPTH_M == 0.9
    assert b.SHALLOW == {210, 211, 226, 227, 373, 374, 389, 390}
    assert b.SHALLOW_BODY_IDS == {27, 28, 57, 58, 209, 210, 226, 227}
    assert capsule_core.options({"interior_depth_m": b.SHALLOW_DEPTH_M})["interior_depth_m"] == 0.9
    assert capsule_core.options({})["interior_depth_m"] == 1.0
