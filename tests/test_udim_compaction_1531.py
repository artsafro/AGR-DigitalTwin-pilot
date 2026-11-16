"""new-case: #1531 remaining live UDIM routes; synthetic borders and shared-owner evidence."""
import ast
import importlib.util
import math
from pathlib import Path

import pytest

from tools.architecture import duplicate_guard as guard

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "adapters/max/agr_tools"


def load(stem):
    spec = importlib.util.spec_from_file_location("probe1531_" + stem, PKG / (stem + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_udim_area_has_no_live_bypasses():
    rows = guard.rows_of(guard.load_maps(ROOT))
    remaining = [r.at for r in rows if r.context == "udim" and r.status == "live-bypass"]
    assert remaining == []
    for row in rows:
        if row.context == "udim" and row.status == "wrapper":
            assert guard.calls_owner(ROOT, row), row.at


@pytest.mark.parametrize("stem", ["udim_core", "uvtile_core", "uvlayout_core", "npm2vpm_core", "udimplug_core"])
def test_inverse_routes_all_tiles_and_invalid_inputs(stem):
    mod = load(stem)
    fn = mod.tile_offset if stem == "udimplug_core" else mod.tile_origin
    for row in range(10):
        for col in range(10):
            assert fn(1001 + col + 10 * row) == (col, row)
    for bad in (None, True, 1000, 1001.5, "1001", math.nan, math.inf):
        with pytest.raises((ValueError, TypeError)):
            fn(bad)


def test_point_and_face_border_policies():
    npm, ids, viewer = load("npm_core"), load("udim_core"), load("udimview_core")
    for row in range(10):
        for col in range(10):
            tile = 1001 + col + 10 * row
            assert npm.tile_of(col, row) == ids.tile_of_uv(col, row) == tile
            # A closed right/top face edge is NOT a point in the next tile.
            pts = [(col, row), (col + 1, row), (col + 1, row + 1), (col, row + 1)]
            assert ids.face_tile(pts, list(range(4))) == tile
            assert viewer.face_tile(pts) == (tile, None)
            pts[1] = (col + 1 + 0.5e-6, row)
            assert ids.face_tile(pts, list(range(4))) == tile
            pts[1] = (col + 1 + 2e-6, row)
            assert ids.face_tile(pts, list(range(4))) is None
            # Viewer deliberately uses only the centroid, not strict containment.
            assert viewer.face_tile(pts) == (tile, None)
    assert npm.tile_of(math.nextafter(1.0, 0.0), 0.5) == 1001
    assert npm.tile_of(1.0, 0.5) == 1002
    assert ids.face_tile([(9, 9), (10, 9), (10, 10)], [0, 1, 2]) == 1100


def test_npm_to_vpm_keeps_closed_edge_and_custom_tolerance():
    mod = load("npm2vpm_core")
    for tile in range(1001, 1101):
        u, v = mod.tile_origin(tile)
        pts = [(u, v), (u + 1, v), (u + 1, v + 1)]
        assert mod.in_tile(pts, tile)
        assert mod.tile_excess(pts, tile) == 0
        shifted = [(u, v), (u + 1 + 2e-6, v), (u + 1, v + 1)]
        assert not mod.in_tile(shifted, tile)
        assert mod.in_tile(shifted, tile, tol=3e-6)


def test_live_elv_offset_uses_owner_on_all_tiles():
    rel = "jobs/elv-tc-vpm/scripts/uv_tex_full_v008.py"
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert not [f for f in guard.scan_text(text, rel) if f.rule == "udim-tile"]
    tree = ast.parse(text)
    statement = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "off" for t in n.targets))
    owner = load("udimtile_core")
    for row in range(10):
        for col in range(10):
            ns = {"_udimtile": owner, "Vector": tuple, "t": {"udim": 1001 + col + 10 * row}}
            exec(compile(ast.Module(body=[statement], type_ignores=[]), rel, "exec"), ns)
            assert ns["off"] == (col, row)
