"""new-case: texel mixed-size UDIM lookup and edge pooling controls.

Scope: per-polygon package tile sides and a complete edge pool for
methods_metrics.texel / package_tile_sides. Not a density-policy change
and not an area-versus-edge comparison.

Two synthetic axis-aligned quads. A is a 1 m square whose 0.5 x 0.5 UV
square sits strictly inside tile 1001. B is a 2 m square whose 0.5 x 0.5 UV
square sits strictly inside tile 1012 (UV in [1.25, 1.75] x [1.25, 1.75]).
Each quad contributes its four boundary edges. Analytic edge ratio is
texture_px * 0.5 / world_edge_m. The median is statistics.median of that
sorted list (stdlib), not edge_densities and not _udim.

Acceptance table, input -> expected:

| input | expected |
|---|---|
| A tile 1001/64 + B tile 1012/256, readback diffuse 1024 | eight edges, min 32 px/m, median 48 px/m, texture_px [64, 256], texture_px_source 'package diffuse PNG', reason None |
| swap the two package image sizes (1001/256, 1012/64) | min 16, median 72, eight edges |
| reverse mesh order, polygon ring order and tile-map insertion order, then add a slot-free UCX with no UV | same complete metric result |
| remove only the tile 1012 diffuse | min/median null, reason names mesh B and tile 1012, not a partial A-only result |
| two diffuse filenames for tile 1001 in different subdirectories | MetricError naming tile 1001 |
| one untiled diffuse plus tiled 1001 | MetricError 'mixes tiled and untiled' |
| Normal/ERM-only images | no diffuse map, None |
| B missing polygon_uv | null naming B |
"""
from __future__ import annotations

import copy
import statistics

import pytest
from PIL import Image

from tests.methods.test_methods_catalog import mm, scene

UV_EDGE_M = 0.5  # UV span of each square edge; world span is the quad side
A_WORLD_M = 1.0
B_WORLD_M = 2.0
A_UV = ((0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75))  # tile 1001, strictly inside [0, 1)
B_UV = ((1.25, 1.25), (1.75, 1.25), (1.75, 1.75), (1.25, 1.75))  # tile 1012, strictly inside [1, 2)


def _quad(name, world_m, uv):
    """One axis-aligned square in the XY plane. One polygon, four edges, no diagonal."""
    s = float(world_m)
    verts = [[0.0, 0.0, 0.0], [s, 0.0, 0.0], [s, s, 0.0], [0.0, s, 0.0]]
    return {"name": name, "vertices": 4, "polygons": 1, "triangles": 2, "polygon_degrees": {"4": 1},
            "bounds_m": [[0.0, 0.0, 0.0], [s, s, 0.0]], "location": [0.0, 0.0, 0.0],
            "rotation_euler_deg": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0], "world_scale": [1.0, 1.0, 1.0],
            "parent": None, "uv_channels": 1, "materials": ["M_Test_Main_1"], "udim_tiles": [],
            "mirrored_uv_triangles": 0,
            "face_geometry": {"vertices": verts, "polygons": [[0, 1, 2, 3]], "uv": [list(p) for p in uv],
                              "polygon_uv": [[list(p) for p in uv]]}}


def _ucx_slot_free():
    """Collision hull with no material slot and no UV. texel must ignore it."""
    return {"name": "UCX_SM_A_001", "materials": [], "uv_channels": 0, "udim_tiles": [],
            "face_geometry": {"vertices": [[0.0, 0.0, 0.0], [0.2, 0.0, 0.0], [0.0, 0.2, 0.0]],
                              "polygons": [[0, 1, 2]]}}


def _readback():
    """scene() readback kept on purpose: one readable 1024 px diffuse, which conflicts with 64 and 256."""
    rb, _ = scene(with_ucx=False)
    rb["meshes"] = [_quad("SM_A", A_WORLD_M, A_UV), _quad("SM_B", B_WORLD_M, B_UV)]
    assert rb["images"][0]["size"] == [1024, 1024]
    assert rb["materials"][0]["maps"][0]["socket"] == "Base Color"
    return rb


def _save_png(path, side):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (side, side), (side & 255, 0, 0)).save(path)


def _package(folder, side_1001, side_1012):
    _save_png(folder / "T_A_Diffuse.1001.png", side_1001)
    _save_png(folder / "T_B_Diffuse.1012.png", side_1012)
    return mm.package_tile_sides(folder)


def _strictly_inside(uv, tile_u, tile_v):
    for u, v in uv:
        assert tile_u < u < tile_u + 1 and tile_v < v < tile_v + 1
        assert u != int(u) and v != int(v)
    cu = sum(p[0] for p in uv) / len(uv)
    cv = sum(p[1] for p in uv) / len(uv)
    assert tile_u < cu < tile_u + 1 and tile_v < cv < tile_v + 1


def _edge_pool(px_a, px_b, *, source="package diffuse PNG", texture_px=None):
    """Oracle: literal UV/world edge ratios, then the stdlib median of the sorted pool.

    Four edges per square. This does not call edge_densities, _udim, or texel.
    """
    ratios = []
    for px, world in ((px_a, A_WORLD_M), (px_b, B_WORLD_M)):
        ratio = px * (UV_EDGE_M / world)
        ratios.extend((ratio, ratio, ratio, ratio))
    ordered = sorted(ratios)
    return {"min_px_m": round(ordered[0], 3), "median_px_m": round(statistics.median(ordered), 3),
            "texture_px": sorted({px_a, px_b}) if texture_px is None else texture_px,
            "texture_px_source": source, "edges": len(ordered), "reason": None}


def test_mixed_tiles_pool_eight_edges_min_32_median_48(tmp_path):
    _strictly_inside(A_UV, 0, 0)
    _strictly_inside(B_UV, 1, 1)
    rb = _readback()
    sides = _package(tmp_path, 64, 256)
    assert sides == {1001: 64, 1012: 256}
    # The 1024 readback is readable and would report a different pool. The package sides have to win.
    readback_only = _edge_pool(1024, 1024, source="readback", texture_px=1024)
    assert readback_only["min_px_m"] == 256 and readback_only["median_px_m"] == 384
    assert mm.texel(rb) == readback_only
    expected = _edge_pool(64, 256)
    assert (expected["min_px_m"], expected["median_px_m"], expected["edges"]) == (32, 48, 8)
    assert expected["texture_px"] == [64, 256] and expected["reason"] is None
    assert mm.texel(rb, sides) == expected


def test_swapped_package_sizes_dispatch_min_16_median_72(tmp_path):
    rb = _readback()
    sides = _package(tmp_path, 256, 64)
    assert sides == {1001: 256, 1012: 64}
    expected = _edge_pool(256, 64)
    assert (expected["min_px_m"], expected["median_px_m"], expected["edges"]) == (16, 72, 8)
    assert mm.texel(rb, sides) == expected


def test_reversed_order_and_slotfree_ucx_keep_the_complete_result(tmp_path):
    rb = _readback()
    sides = _package(tmp_path, 64, 256)
    expected = _edge_pool(64, 256)
    forward = mm.texel(rb, sides)
    flipped = copy.deepcopy(rb)
    flipped["meshes"] = [_reverse_ring(m) for m in reversed(flipped["meshes"])]
    flipped["meshes"].append(_ucx_slot_free())
    assert [m["name"] for m in flipped["meshes"]] == ["SM_B", "SM_A", "UCX_SM_A_001"]
    assert "polygon_uv" not in flipped["meshes"][-1]["face_geometry"]
    assert flipped["meshes"][-1]["materials"] == []
    sides_rev = dict(reversed(list(sides.items())))
    assert list(sides_rev) == [1012, 1001]
    assert mm.texel(flipped, sides_rev) == expected
    assert forward == expected


def _reverse_ring(mesh):
    mesh = copy.deepcopy(mesh)
    fg = mesh["face_geometry"]
    fg["polygons"] = [list(reversed(poly)) for poly in reversed(fg["polygons"])]
    if "polygon_uv" in fg:
        fg["polygon_uv"] = [list(reversed(ring)) for ring in reversed(fg["polygon_uv"])]
    return mesh


def test_removed_tile_1012_is_null_naming_b_not_partial(tmp_path):
    rb = _readback()
    _package(tmp_path, 64, 256)
    (tmp_path / "T_B_Diffuse.1012.png").unlink()
    sides = mm.package_tile_sides(tmp_path)
    assert sides == {1001: 64}
    result = mm.texel(rb, sides)
    assert result["min_px_m"] is None and result["median_px_m"] is None
    assert result == {"min_px_m": None, "median_px_m": None, "texture_px": None,
                      "reason": "SM_B: UV tile 1012 has no diffuse PNG in the package"}


def test_two_diffuse_files_for_tile_1001_name_the_tile(tmp_path):
    _save_png(tmp_path / "east" / "T_East_Diffuse.1001.png", 64)
    _save_png(tmp_path / "west" / "T_West_Diffuse.1001.png", 256)
    with pytest.raises(mm.MetricError, match="tile 1001"):
        mm.package_tile_sides(tmp_path)


def test_untiled_plus_tiled_1001_mixes_tiled_and_untiled(tmp_path):
    _save_png(tmp_path / "T_Loose_Diffuse.png", 64)
    _save_png(tmp_path / "T_A_Diffuse.1001.png", 64)
    with pytest.raises(mm.MetricError, match="mixes tiled and untiled"):
        mm.package_tile_sides(tmp_path)


def test_normal_and_erm_only_images_are_not_a_diffuse_map(tmp_path):
    _save_png(tmp_path / "T_Facade_Normal.1001.png", 128)
    _save_png(tmp_path / "T_Facade_ERM.1012.png", 64)
    assert mm.package_tile_sides(tmp_path) is None


def test_missing_polygon_uv_on_b_is_null_naming_b(tmp_path):
    rb = _readback()
    sides = _package(tmp_path, 64, 256)
    rb["meshes"][1]["face_geometry"].pop("polygon_uv")
    assert rb["meshes"][1]["name"] == "SM_B"
    result = mm.texel(rb, sides)
    assert result == {"min_px_m": None, "median_px_m": None, "texture_px": None,
                      "reason": "no corner UV on SM_B"}


def test_repeated_calls_leave_readback_and_tile_map_unchanged(tmp_path):
    rb = _readback()
    sides = _package(tmp_path, 64, 256)
    rb_copy = copy.deepcopy(rb)
    sides_items = list(sides.items())
    first = mm.texel(rb, sides)
    second = mm.texel(rb, sides)
    assert first == second == _edge_pool(64, 256)
    assert rb == rb_copy
    assert list(sides.items()) == sides_items
    assert rb["images"] == rb_copy["images"] and rb["materials"] == rb_copy["materials"]
