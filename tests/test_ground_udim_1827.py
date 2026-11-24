"""#1827: Ground report UDIM fields delegate tile numbering to shared udimtile_core.

- ``stages.surfaces.ids[].udim`` and ``stages.textures.expected_tiles`` compute first-row UDIM tiles
  via ``udimtile_core.udim_of_cell(cover_id - 1, 0)`` rather than local ``1000 + c.id`` arithmetic.
- Preserves both report contracts: surface inventory order, filtering to slots present on the projected
  mesh, first-row boundaries (IDs 1 and 10 -> tiles 1001 and 1010), sparse present IDs, absent slots,
  ID validation error paths, and flat/projected/skirt UV placement + tile readback.

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

    If local ``1000 + c.id`` arithmetic is pasted back into either ``stages.surfaces.ids[].udim`` or
    ``stages.textures.expected_tiles``, both the sentinel tile values and the per-stage call log fail.
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
        1001 + i + sentinel_offset for i in range(10)
    ]
    assert st["textures"]["expected_tiles"] == [1001 + sentinel_offset, 1010 + sentinel_offset]
    assert st["textures"]["tiles"]["tiles"] == [1001 + sentinel_offset, 1010 + sentinel_offset]
    assert calls_by_phase["surfaces"] == [(i, 0) for i in range(10)]
    assert calls_by_phase["textures"] == [(0, 0), (9, 0)]
    assert res.report["geometry_status"] == "built" and res.report["geometry_failures"] == []


def test_first_row_boundaries_id1_and_id10_with_sparse_present_and_absent_slots():
    """IDs 1..10 (1001..1010): only IDs 1 and 10 appear on the projected mesh; 2..9 are absent."""
    res = build(covers=_ten_covers_sparse_present(), base_id=1)
    st = res.report["stages"]

    ids = st["surfaces"]["ids"]
    assert [(row["id"], row["slot"], row["udim"]) for row in ids] == [
        (1, "ID01_Lawn", 1001),
        *[(i, f"ID{i:02d}_Unused{i}", 1000 + i) for i in range(2, 10)],
        (10, "ID10_Tile10", 1010),
    ]
    assert st["textures"]["expected_tiles"] == [1001, 1010]
    assert st["textures"]["tiles"]["tiles"] == [1001, 1010]
    assert st["textures"]["tiles"]["straddling"] == 0
    assert st["textures"]["tiles"]["outside_udim_range"] == 0
    assert res.report["geometry_status"] == "built" and res.report["geometry_failures"] == []

    # Flat, projected, and skirt UVs keep exact tile placement (cell u = id - 1, v = 0).
    for mesh in (res.flat, res.mesh):
        slots = np.array(mesh.slot)
        m1 = slots == "ID01_Lawn"
        m10 = slots == "ID10_Tile10"
        assert m1.any() and m10.any()
        assert (mesh.uv[m1, :, 0] >= -1e-9).all() and (mesh.uv[m1, :, 0] <= 1.0 + 1e-9).all()
        assert (mesh.uv[m10, :, 0] >= 9.0 - 1e-9).all() and (mesh.uv[m10, :, 0] <= 10.0 + 1e-9).all()
        assert (mesh.uv[..., 1] >= -1e-9).all() and (mesh.uv[..., 1] <= 1.0 + 1e-9).all()

    skirt = res.mesh.level < 0
    assert skirt.any() and set(np.array(res.mesh.slot)[skirt]) == {"ID01_Lawn"}
    assert (res.mesh.uv[skirt, :, 0] >= -1e-9).all() and (res.mesh.uv[skirt, :, 0] <= 1.0 + 1e-9).all()


def test_surface_inventory_order_and_crop_absent_slot_preserved():
    """Input cover order is preserved in both report fields; slots absent after crop are filtered out."""
    by_id = {c.id: c for c in _ten_covers_sparse_present()}
    by_id[4] = gs.Cover(4, "Plaza4", [box(12, 12, 16, 16)], (150, 150, 150), "spec")
    order = [10, 4, 1, 2, 3, 5, 6, 7, 8, 9]
    cs = [by_id[i] for i in order]

    full = build(covers=cs, base_id=1)
    assert [(row["id"], row["udim"]) for row in full.report["stages"]["surfaces"]["ids"]] == [
        (i, 1000 + i) for i in order
    ]
    assert full.report["stages"]["textures"]["expected_tiles"] == [1010, 1004, 1001]
    assert full.report["stages"]["textures"]["tiles"]["tiles"] == [1001, 1004, 1010]
    assert full.report["geometry_status"] == "built"

    # Crop excludes Plaza4 ([12, 16]^2) while retaining Lawn (ID 1) and Tile10 ([5, 10]^2).
    cropped = build(covers=cs, base_id=1, crop_box=[0, 0, 11, 11])
    assert [(row["id"], row["udim"]) for row in cropped.report["stages"]["surfaces"]["ids"]] == [
        (i, 1000 + i) for i in order
    ]
    assert cropped.report["stages"]["textures"]["expected_tiles"] == [1010, 1001]
    assert cropped.report["stages"]["textures"]["tiles"]["tiles"] == [1001, 1010]
    assert cropped.report["geometry_status"] == "built"


@pytest.mark.parametrize("ids,match", [
    ([1, 3], "without gaps"),
    ([1, 10], "without gaps"),
    ([2, 3], "without gaps"),
    ([0, 1], "without gaps"),
    (list(range(1, 12)), r"cover ID 11 > 10.*1001-1010"),
])
def test_id_validation_and_existing_error_paths_preserved(ids, match):
    cs = [gs.Cover(ids[0], f"C{ids[0]}", [box(0, 0, 20, 20)], (10, 20, 30), "spec")]
    for cid in ids[1:]:
        cs.append(gs.Cover(cid, f"C{cid}", [box(2, 2, 4, 4)], (10, 20, 30), "spec"))
    with pytest.raises(ValueError, match=match):
        gs.build_site(box(0, 0, 20, 20), cs, ids[0], relief(), 100.0, origin_xy=(0, 0))


def test_obj_readback_tiles_match_id1_and_id10(tmp_path):
    res = build(covers=_ten_covers_sparse_present(), base_id=1)
    obj = tmp_path / "SM_SYN_Ground.obj"
    gs.write_obj(obj, res.mesh, res.slots, "SM_SYN_Ground", "synthetic #1827")
    back = gs.read_obj(obj)
    assert back["tiles"] == {
        "M_SYN_Ground_ID01_Lawn": [1001],
        "M_SYN_Ground_ID10_Tile10": [1010],
    }
