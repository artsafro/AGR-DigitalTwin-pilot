"""#1738: shared-surface Ground (one vertex set per covering boundary, no stacked layers) + skirt check on export.

Pattern: n/a | new-case: tests/test_ground_shared_surfaces_1738.py - tests of the #1738 shared-surface core.
All site data here is SYNTHETIC (generated squares and planes), never a real object.
"""
import math
import random
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry import ground_site as gs
from dt_ai.ops.inv_xview import mesh_report


def _plan(extra=()):
    covers = {"base": [box(0, 0, 20, 20)], "b": [box(5, 5, 12, 12)], "c": [box(9, 9, 15, 14)], **dict(extra)}
    slots = {k: k.upper() for k in covers}
    return gc.plan_layers(box(0, 0, 20, 20), covers, "base", slots, footprint_min_area=1000.0)


def _area(mesh, mask=None):
    v = mesh.verts
    f = mesh.faces if mask is None else mesh.faces[mask]
    a = v[f[:, 1], :2] - v[f[:, 0], :2]
    b = v[f[:, 2], :2] - v[f[:, 0], :2]
    return 0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])


def test_shared_mode_one_face_per_xy_and_topmost_slot():
    plan = _plan()
    m = gc.build_flat(plan, cell=3.0, surfaces="shared")
    assert set(m.level.tolist()) == {0}
    assert np.allclose(m.verts[:, 2], 0.0)
    # every XY point is covered once: triangle area sum == surface area (layered would add the insets again)
    assert math.isclose(_area(m).sum(), plan.surface.area, rel_tol=1e-9)
    # one vertex set: no two vertices share an XY
    xy = {(round(x, 6), round(y, 6)) for x, y, _ in m.verts}
    assert len(xy) == len(m.verts)
    # topmost covering wins: c over b over base
    cen = m.verts[m.faces][:, :, :2].mean(axis=1)
    for (x, y), s in zip(cen, m.slot):
        want = "C" if (9 < x < 15 and 9 < y < 14) else "B" if (5 < x < 12 and 5 < y < 12) else "BASE"
        assert s == want, (x, y, s)
    assert m.report["surfaces"] == "shared"


def test_layered_default_still_stacks():
    plan = _plan()
    m = gc.build_flat(plan, cell=3.0)
    assert m.report["surfaces"] == "layered"
    assert _area(m).sum() > plan.surface.area + 1.0


def test_shared_mode_xview_zero_and_skirt_closed():
    m = gc.add_skirt(gc.build_flat(_plan(), cell=3.0, surfaces="shared"), 1.0)
    r = mesh_report(m.verts, m.faces, profile="NPM-GROUND", part="ground")
    assert (r["vertex_pairs"], r["face_pairs"]) == (0, 0), r
    assert gs.skirt_gaps(m, 1.0) == []


def test_unknown_surfaces_mode_is_an_error_naming_it():
    with pytest.raises(ValueError, match="stacked"):
        gc.build_flat(_plan(), cell=3.0, surfaces="stacked")


@pytest.mark.parametrize("seed", range(12))
def test_probe_random_covers_shared_partition(seed):
    """Probe: random overlapping covers -> one face per XY, area == surface, xView 0/0, no skirt gap."""
    rnd = random.Random(seed)
    covers = {"base": [box(0, 0, 30, 25)]}
    for k in range(rnd.randint(1, 5)):
        x, y = rnd.uniform(0, 25), rnd.uniform(0, 20)
        covers[f"k{k}"] = [box(x, y, min(30, x + rnd.uniform(1, 12)), min(25, y + rnd.uniform(1, 10)))]
    slots = {k: k.upper() for k in covers}
    plan = gc.plan_layers(box(0, 0, 30, 25), covers, "base", slots)
    m = gc.build_flat(plan, cell=3.0, surfaces="shared", snap=0.001)
    assert math.isclose(_area(m).sum(), plan.surface.area, rel_tol=1e-6)
    m = gc.add_skirt(m, 1.0)
    r = mesh_report(m.verts, m.faces, profile="NPM-GROUND", part="ground")
    assert (r["vertex_pairs"], r["face_pairs"]) == (0, 0)
    assert gs.skirt_gaps(m, 1.0) == []


# ---------------------------------------------------------------- skirt check on the export (group-agnostic)


def _write(tmp_path, mesh, name="g.obj"):
    p = tmp_path / name
    slots = sorted(set(mesh.slot) - {"Skirt"})
    gs.write_obj(p, mesh, slots + ["Skirt"], "SM_T_Ground", "synthetic")
    return p


def _flat_one():
    plan = gc.plan_layers(box(0, 0, 6, 6), {"base": [box(0, 0, 6, 6)]}, "base", {"base": "ID01_Base"})
    return gc.build_flat(plan, cell=3.0, surfaces="shared")


def test_export_skirt_check_pass_and_short_and_missing(tmp_path):
    good = gs.skirt_check_export(_write(tmp_path, gc.add_skirt(_flat_one(), 1.0), "a.obj"), 1.0)
    assert good["status"] == "pass" and good["outer_edges"] > 0 and good["min_drop_m"] >= 1.0
    deep = gc.add_skirt(_flat_one(), 1.0)
    deep.verts[deep.verts[:, 2] < -0.5, 2] = -0.5  # skirt shortened to 0.5 m after the build
    short = gs.skirt_check_export(_write(tmp_path, deep, "b.obj"), 1.0)
    assert short["status"] == "fail" and short["gaps"] and short["min_drop_m"] == pytest.approx(0.5)
    none = gs.skirt_check_export(_write(tmp_path, _flat_one(), "c.obj"), 1.0)
    assert none["status"] == "fail" and none["gaps"][0]["reason"] == "no skirt wall"


def test_export_skirt_check_exactly_at_threshold_passes_and_just_below_fails(tmp_path):
    at = gs.skirt_check_export(_write(tmp_path, gc.add_skirt(_flat_one(), 1.0), "a.obj"), 1.0)
    assert at["status"] == "pass"
    m = gc.add_skirt(_flat_one(), 1.0)
    m.verts[m.verts[:, 2] < -0.5, 2] = -0.999
    assert gs.skirt_check_export(_write(tmp_path, m, "b.obj"), 1.0)["status"] == "fail"


def test_export_skirt_check_fail_closed(tmp_path):
    empty = tmp_path / "e.obj"
    empty.write_text("# nothing\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no faces"):
        gs.skirt_check_export(empty, 1.0)
    nan = tmp_path / "n.obj"
    nan.write_text("v 0 0 nan\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="finite"):
        gs.skirt_check_export(nan, 1.0)
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            gs.skirt_check_export(_write(tmp_path, gc.add_skirt(_flat_one(), 1.0), "x.obj"), bad)


def test_export_skirt_check_rejects_downward_top(tmp_path):
    """A flipped top (normal down) is not a Ground top: every edge is then unclassified -> fail, not pass."""
    p = tmp_path / "flip.obj"
    p.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 3 2\n", encoding="utf-8")
    r = gs.skirt_check_export(p, 1.0)
    assert r["status"] == "fail" and r["top_faces"] == 0


def test_export_skirt_check_layered_inset_rim_is_not_perimeter(tmp_path):
    """A layered inset rim (open edge with base under its outer side) is not the perimeter: no false gap."""
    m = gc.add_skirt(gc.build_flat(_plan(), cell=3.0), 1.0)
    r = gs.skirt_check_export(_write(tmp_path, m), 1.0)
    assert r["status"] == "pass", r["gaps"][:3]
    assert r["outer_edges"] == gs.skirt_check_export(
        _write(tmp_path, gc.add_skirt(gc.build_flat(_plan(), cell=3.0, surfaces="shared"), 1.0), "s.obj"),
        1.0)["outer_edges"]


def test_export_skirt_check_ngon_fan_wall_counts_and_outer_rings(tmp_path):
    """A skirt wall triangulated as a fan across two top edges (Max n-gon) is measured by covered depth."""
    p = tmp_path / "fan.obj"
    v = [(0, 0, 0), (2, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0), (0, 0, -1.2), (4, 0, -1.2)]
    f = [(1, 2, 5), (2, 4, 5), (2, 3, 4),  # top (CCW)
         (1, 6, 2), (2, 6, 7), (2, 7, 3)]  # fan wall under the y=0 side, 1.2 m
    p.write_text("".join(f"v {x} {y} {z}\n" for x, y, z in v) + "".join(f"f {a} {b} {c}\n" for a, b, c in f),
                 encoding="utf-8")
    r = gs.skirt_check_export(p, 1.0)
    walled = {(0, 1), (1, 2)}
    assert r["status"] == "fail" and r["outer_edges"] == 5
    assert not walled & {tuple(sorted(g["edge"])) for g in r["gaps"]}
    assert r["gap_count"] == 3
    hole = gc.plan_layers(box(0, 0, 60, 60), {"base": [box(0, 0, 60, 60).difference(box(20, 20, 50, 50))]}, "base",
                          {"base": "ID01_Base"}, footprint_min_area=100.0)
    m = gc.build_flat(hole, cell=6.0, surfaces="shared")
    m = gc.add_skirt(m, 1.0)
    keep = np.ones(len(m.faces), bool)  # drop the hole skirt (D251 exempts inner rings)
    cen = m.verts[m.faces].mean(axis=1)
    keep &= ~((m.level < 0) & (cen[:, 0] > 19) & (cen[:, 0] < 51) & (cen[:, 1] > 19) & (cen[:, 1] < 51))
    m2 = gc.Mesh(m.verts, m.faces[keep], [s for s, k in zip(m.slot, keep) if k], m.level[keep], m.uv[keep], m.cell)
    q = _write(tmp_path, m2, "hole.obj")
    assert gs.skirt_check_export(q, 1.0)["status"] == "fail"
    assert gs.skirt_check_export(q, 1.0, rings="outer")["status"] == "pass"
    with pytest.raises(ValueError, match="rings"):
        gs.skirt_check_export(q, 1.0, rings="inner")


def _relief(w, h, n=6, margin=1.0):
    pts = []
    for i in range(n):
        for j in range(n):
            x = -margin + (w + 2 * margin) * i / (n - 1)
            y = -margin + (h + 2 * margin) * j / (n - 1)
            pts.append((x, y, 100.0 + 0.05 * x - 0.03 * y))
    return pts


def _covers():
    return [gs.Cover(1, "Base", [box(0, 0, 20, 20)], (10, 10, 10), "spec"),
            gs.Cover(2, "Tile", [box(5, 5, 12, 12)], (200, 0, 0), "spec"),
            gs.Cover(3, "Lawn", [Polygon([(9, 9), (15, 9), (15, 14), (9, 14)])], (0, 200, 0), "spec")]


def test_build_site_shared_end_to_end(tmp_path):
    res = gs.build_site(box(0, 0, 20, 20), _covers(), 1, _relief(20, 20), 100.0, origin_xy=(0, 0), cell=3.0,
                        surfaces="shared")
    m = res.mesh
    assert res.report["stages"]["surfaces"]["mode"] == "shared"
    assert set(m.level.tolist()) <= {0, -1}
    r = mesh_report(m.verts, m.faces, profile="NPM-GROUND", part="ground")
    assert (r["vertex_pairs"], r["face_pairs"]) == (0, 0)
    assert res.report["stages"]["skirt"]["skirt_gap_edges"] == []
    assert res.report["findings"] == [f for f in res.report["findings"] if f.startswith("UCX")]
    check = gs.skirt_check_export(_write(tmp_path, m), 1.0)
    assert check["status"] == "pass"
    top = m.level >= 0
    assert math.isclose(_area(m, top).sum(), 400.0, rel_tol=1e-9)


def test_build_site_rejects_unknown_surfaces():
    with pytest.raises(ValueError, match="surfaces"):
        gs.build_site(box(0, 0, 20, 20), _covers(), 1, _relief(20, 20), 100.0, surfaces="cake")


def test_cli_accepts_surfaces_param():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bgs", Path(__file__).resolve().parents[1]
                                                  / "tools/ground/build_ground_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "surfaces" in mod.PARAMS and "adapter" in mod.TOP_KEYS


@pytest.mark.parametrize("name", ["sil13-shared.json", "vatutino-shared.json"])
def test_real_site_specs_are_shared_mode_and_pinned(name):
    """The two real-site specs of the #1738 evidence table: shared mode, a sha-pinned source, only known keys."""
    import json
    mod = _cli()
    spec = json.loads((Path(__file__).parent / "fixtures/ground_1738" / name).read_text(encoding="utf-8"))
    assert set(spec) <= mod.TOP_KEYS and set(spec["params"]) <= mod.PARAMS
    assert spec["params"]["surfaces"] == "shared" and spec["params"]["skirt_m"] >= 1.0
    src = spec.get("dxf") or spec.get("adapter")
    assert len(src["sha256"]) == 64 and ("dxf" in spec) != ("adapter" in spec)
    assert sorted(c["id"] for c in spec["covers"]) == list(range(1, len(spec["covers"]) + 1))


def test_sil13_job_skeleton_calls_the_core():
    import json
    root = Path(__file__).resolve().parents[1]
    sk = json.loads((root / "jobs/SIL13-COLD-1315/ground-1738/skeleton.json").read_text(encoding="utf-8"))
    assert sk["scenario"] == "ground-npm" and sk["hooks"] == []
    assert (root / sk["config"]["sources"]).is_file()
    cells = json.loads((root / "docs/agents/skeletons.json").read_text(encoding="utf-8"))
    for st in ("surfaces", "skirt"):
        assert cells["stages"][st]["gap"] is None and "ground_site.py" in " ".join(cells["stages"][st]["owners"])


def _cli():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bgs2", Path(__file__).resolve().parents[1]
                                                  / "tools/ground/build_ground_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _adapter(tmp_path, extra_cov=None):
    import json
    from shapely.geometry import mapping
    cov = {"base": {"geometry": mapping(box(0, 0, 20, 20))}, "tile": {"geometry": mapping(box(5, 5, 12, 12))},
           "deck": {"geometry": {"type": "MultiPolygon", "coordinates": []}}, **(extra_cov or {})}
    d = {"boundary": mapping(box(0, 0, 20, 20)), "coverings": cov,
         "elevations": [{"x": x, "y": y, "z": z} for x, y, z in _relief(20, 20)]}
    p = tmp_path / "adapter.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def _adapter_spec(tmp_path, adapter, **kw):
    import json
    spec = {"site": "SYN", "adapter": {"path": str(adapter), "sha256": gs.sha256(adapter)},
            "zero": {"project_zero_m": 100.0, "source": "synthetic"}, "base_id": 1,
            "covers": [{"id": 1, "name": "Base", "adapter_keys": ["base"], "colour": [1, 2, 3], "colour_reason": "syn"},
                       {"id": 2, "name": "Tile", "adapter_keys": ["tile"], "colour": [4, 5, 6], "colour_reason": "syn"}],
            "adapter_empty": ["deck"], "params": {"origin_xy": [0, 0], "cell": 3.0, "snap": 0.003,
                                                  "surfaces": "shared"}}
    spec.update(kw)
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return p


def test_cli_adapter_shared_builds_xview_zero_and_skirt(tmp_path):
    import json
    mod = _cli()
    a = _adapter(tmp_path)
    s = _adapter_spec(tmp_path, a)
    before = a.read_bytes(), s.read_bytes()
    assert mod.run(s, tmp_path / "out") == 0
    rep = json.loads((tmp_path / "out/ground-report.json").read_text(encoding="utf-8"))
    assert rep["skirt_export_check"]["status"] == "pass" and rep["skirt_export_check"]["min_drop_m"] >= 1.0
    assert rep["xview"]["passed"] and (rep["xview"]["vertex_pairs"], rep["xview"]["face_pairs"]) == (0, 0)
    assert rep["stages"]["surfaces"]["mode"] == "shared"
    assert (a.read_bytes(), s.read_bytes()) == before  # inputs untouched


@pytest.mark.parametrize("case", ["unmapped", "twice", "empty_not_empty", "no_colour", "both_sources", "out_is_input"])
def test_cli_adapter_fail_closed(tmp_path, case):
    from shapely.geometry import mapping
    mod = _cli()
    a = _adapter(tmp_path, {"extra": {"geometry": mapping(box(1, 1, 2, 2))}} if case == "unmapped" else None)
    kw = {}
    if case == "twice":
        kw["covers"] = [{"id": 1, "name": "Base", "adapter_keys": ["base"], "colour": [1, 2, 3], "colour_reason": "s"},
                        {"id": 2, "name": "Tile", "adapter_keys": ["tile", "base"], "colour": [1, 2, 3],
                         "colour_reason": "s"}]
    if case == "empty_not_empty":
        kw["adapter_empty"] = ["deck", "tile"]
    if case == "no_colour":
        kw["covers"] = [{"id": 1, "name": "Base", "adapter_keys": ["base"]},
                        {"id": 2, "name": "Tile", "adapter_keys": ["tile"], "colour": [1, 2, 3], "colour_reason": "s"}]
    if case == "both_sources":
        kw["dxf"] = {"path": str(a), "sha256": "x"}
    s = _adapter_spec(tmp_path, a, **kw)
    out = a if case == "out_is_input" else tmp_path / "out"
    with pytest.raises(ValueError):
        mod.run(s, out)
    assert not (tmp_path / "out").exists() and not (tmp_path / "out.partial").exists()
