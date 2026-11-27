"""#1827/#1898: shared UDIM numbering, now applied to the dense rank of each used cover.

All site data here is SYNTHETIC (generated squares and planes), never a real object.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry import ground_site as gs
from tests.test_ground_site_1406 import build, relief

ROOT = Path(__file__).resolve().parents[1]
UDIM_OWNER = ROOT / "adapters/max/agr_tools/udimtile_core.py"


def _ten_covers_sparse_present(order: list[int] | None = None) -> list[gs.Cover]:
    """Synthetic valid 1..10 cover set where only selected IDs intersect the [0, 20]^2 boundary."""
    by_id = {
        1: gs.Cover(1, "Lawn", [box(0, 0, 20, 20)], (96, 150, 64), "spec"),
        10: gs.Cover(10, "Tile10", [box(5, 5, 10, 10)], (200, 100, 50), "hatch-bgcolor"),
    }
    for cid in range(2, 10):
        # Disjoint from [0, 20]^2 so the cover is in stages.surfaces.ids but absent on the projected mesh.
        by_id[cid] = gs.Cover(cid, f"Unused{cid}", [box(100 + cid, 100, 101 + cid, 101)], (cid, cid, cid), "spec")
    ids = list(range(1, 11)) if order is None else order
    return [by_id[i] for i in ids]


def test_ground_uses_canonical_udimtile_core_owner():
    assert Path(gc._udimtile.__file__).resolve() == UDIM_OWNER.resolve()


def test_owner_delegation_witness_for_both_report_fields(monkeypatch):
    """Witness calls to udimtile_core.udim_of_cell for BOTH report fields.

    Both fields reuse the same canonical assignment; absent covers never invoke the tile owner.
    """
    real_udim_of_cell = gc._udimtile.udim_of_cell
    real_uv_tile_report = gc.uv_tile_report
    phase = {"name": "surfaces"}
    calls_by_phase: dict[str, list[tuple[int, int]]] = {"surfaces": [], "uv_tile_report": [], "textures": []}
    sentinel_offset = 50_000

    def witnessed_udim_of_cell(cu, cv):
        calls_by_phase[phase["name"]].append((cu, cv))
        return real_udim_of_cell(cu, cv) + sentinel_offset

    def witnessed_uv_tile_report(uv, *args, **kwargs):
        phase["name"] = "uv_tile_report"
        try:
            return real_uv_tile_report(uv, *args, **kwargs)
        finally:
            phase["name"] = "textures"

    monkeypatch.setattr(gc._udimtile, "udim_of_cell", witnessed_udim_of_cell)
    monkeypatch.setattr(gc, "uv_tile_report", witnessed_uv_tile_report)

    res = build(covers=_ten_covers_sparse_present(), base_id=1)
    st = res.report["stages"]

    assert [row["udim"] for row in st["surfaces"]["ids"]] == [
        1001 + sentinel_offset, *([None] * 8), 1002 + sentinel_offset,
    ]
    assert st["textures"]["expected_tiles"] == [1001 + sentinel_offset, 1002 + sentinel_offset]
    assert st["textures"]["tiles"]["tiles"] == [1001 + sentinel_offset, 1002 + sentinel_offset]
    assignment = st["textures"]["udim_assignment"]
    assert assignment["expected"] == assignment["observed"] == {
        "ID01_Lawn": [1001 + sentinel_offset], "ID10_Tile10": [1002 + sentinel_offset],
    }
    assert assignment["status"] == "pass"
    assert calls_by_phase["surfaces"] == [(0, 0), (1, 0)]
    assert res.report["geometry_status"] == "built" and res.report["geometry_failures"] == []


def test_sparse_present_and_absent_slots():
    """Only IDs 1 and 10 appear; 2..9 are recorded but receive no tile."""
    res = build(covers=_ten_covers_sparse_present(), base_id=1)
    st = res.report["stages"]

    ids = st["surfaces"]["ids"]
    assert [(row["id"], row["slot"], row["udim"]) for row in ids] == [
        (1, "ID01_Lawn", 1001),
        *[(i, f"ID{i:02d}_Unused{i}", None) for i in range(2, 10)],
        (10, "ID10_Tile10", 1002),
    ]
    assert st["textures"]["expected_tiles"] == [1001, 1002]
    assert st["textures"]["tiles"]["tiles"] == [1001, 1002]
    assert st["textures"]["tiles"]["straddling"] == 0
    assert st["textures"]["tiles"]["outside_udim_range"] == 0
    assert res.report["geometry_status"] == "built" and res.report["geometry_failures"] == []

    # Flat, projected, and skirt UVs agree on the dense tile placement.
    for mesh in (res.flat, res.mesh):
        slots = np.array(mesh.slot)
        m1 = slots == "ID01_Lawn"
        m10 = slots == "ID10_Tile10"
        assert m1.any() and m10.any()
        assert (mesh.uv[m1, :, 0] >= -1e-9).all() and (mesh.uv[m1, :, 0] <= 1.0 + 1e-9).all()
        assert (mesh.uv[m10, :, 0] >= 1.0 - 1e-9).all() and (mesh.uv[m10, :, 0] <= 2.0 + 1e-9).all()
        assert (mesh.uv[..., 1] >= -1e-9).all() and (mesh.uv[..., 1] <= 1.0 + 1e-9).all()

    skirt = res.mesh.level < 0
    assert skirt.any() and set(np.array(res.mesh.slot)[skirt]) == {"ID01_Lawn"}
    assert (res.mesh.uv[skirt, :, 0] >= -1e-9).all() and (res.mesh.uv[skirt, :, 0] <= 1.0 + 1e-9).all()


def test_surface_inventory_order_and_crop_absent_slot_preserved():
    """Inventory preserves input order; allocation follows IDs and excludes absent covers."""
    by_id = {c.id: c for c in _ten_covers_sparse_present()}
    by_id[4] = gs.Cover(4, "Plaza4", [box(12, 12, 16, 16)], (150, 150, 150), "spec")
    order = [10, 4, 1, 2, 3, 5, 6, 7, 8, 9]
    cs = [by_id[i] for i in order]

    full = build(covers=cs, base_id=1)
    assert [(row["id"], row["udim"]) for row in full.report["stages"]["surfaces"]["ids"]] == [
        (i, {1: 1001, 4: 1002, 10: 1003}.get(i)) for i in order
    ]
    assert full.report["stages"]["textures"]["expected_tiles"] == [1001, 1002, 1003]
    assert full.report["stages"]["textures"]["tiles"]["tiles"] == [1001, 1002, 1003]
    assert full.report["geometry_status"] == "built"

    # Crop excludes Plaza4 ([12, 16]^2) while retaining Lawn (ID 1) and Tile10 ([5, 10]^2).
    cropped = build(covers=cs, base_id=1, crop_box=[0, 0, 11, 11])
    assert [(row["id"], row["udim"]) for row in cropped.report["stages"]["surfaces"]["ids"]] == [
        (i, {1: 1001, 10: 1002}.get(i)) for i in order
    ]
    assert cropped.report["stages"]["textures"]["expected_tiles"] == [1001, 1002]
    assert cropped.report["stages"]["textures"]["tiles"]["tiles"] == [1001, 1002]
    assert cropped.report["geometry_status"] == "built"


@pytest.mark.parametrize("ids,match", [
    ([], "no covers"),
    ([1, 1], "duplicate cover IDs"),
    ([0], "cover ID 0"),
    ([True], "cover ID True"),
    ([3.0], r"cover ID 3\.0"),
    ([float("nan")], "cover ID nan"),
    ([float("inf")], "cover ID inf"),
    ([1001], "cover ID 1001"),
])
def test_invalid_cover_ids(ids, match):
    cs = [gs.Cover(cid, f"C{i}", [box(0, 0, 20, 20)], (10, 20, 30), "spec") for i, cid in enumerate(ids)]
    with pytest.raises(ValueError, match=match):
        gs.check_covers(cs, 1)


def test_obj_readback_tiles_match_id1_and_id10(tmp_path):
    res = build(covers=_ten_covers_sparse_present(), base_id=1)
    obj = tmp_path / "SM_SYN_Ground.obj"
    gs.write_obj(obj, res.mesh, res.slots, "SM_SYN_Ground", "synthetic #1827")
    back = gs.read_obj(obj)
    assert back["tiles"] == {
        "M_SYN_Ground_ID01_Lawn": [1001],
        "M_SYN_Ground_ID10_Tile10": [1002],
    }
