"""Regression tests for geometric wall binding in synthetic IFC offline intake."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.util.placement
import numpy as np
import pytest

_loaded = importlib.util.spec_from_file_location("pilot", Path(__file__).with_name("pilot.py"))
pilot = importlib.util.module_from_spec(_loaded)
_loaded.loader.exec_module(pilot)
Spec = pilot.Spec

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = REPO_ROOT / "benchmark"
CASES = ("bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace")
UNITS = (("m", None), ("mm", "MILLI"))
VARIANTS = ("clean", "null", "identical", "suffix")
FAULTS = ("shared_placement", "z_shift")

TOL = {
    "spec_compare": {
        "level_elev_m": 0.03,
        "contour_area_rel": 0.02,
        "contour_hausdorff_m": 0.05,
        "opening_bbox_m": 0.05,
    },
    "verdict": {"enabled": True},
}


def _storey_context(handle: Any, slab: Any) -> tuple[Any, list[Any], list[Any], float, Any, float]:
    bld_pl = handle.by_type("IfcBuilding")[0].ObjectPlacement
    scale = pilot.length_scale(handle)
    inv_b = np.linalg.inv(np.array(ifcopenshell.util.placement.get_local_placement(bld_pl)))
    st = pilot.storey_of(slab)
    st_local = inv_b @ np.array(ifcopenshell.util.placement.get_local_placement(st.ObjectPlacement))
    storey_z = float(st_local[2, 3] * scale)
    solid = pilot.body_solid(slab)
    ring = pilot.to_building(pilot.profile_ring(solid), solid.Position, slab.ObjectPlacement, bld_pl, scale)
    walls = [w for w in handle.by_type("IfcWall") if pilot.storey_of(w).GlobalId == st.GlobalId]
    return st, walls, ring, storey_z, bld_pl, scale


def _all_storey_contexts(handle: Any) -> list[tuple[Any, list[Any], list[Any], float, Any, float]]:
    return [_storey_context(handle, slab) for slab in handle.by_type("IfcSlab")]


def _make_tolerance_fixture(tmp_path: Path, origin_offset: float = 0.0, axis_offset: float = 0.0) -> Path:
    spec = Spec.model_validate(pilot.mini_spec())
    path = tmp_path / "tol_fixture.ifc"
    pilot.generate(spec, None, path)
    handle = ifcopenshell.open(str(path))
    w0 = next(w for w in handle.by_type("IfcWall") if w.Name == "W0000")
    if origin_offset != 0.0:
        loc = w0.ObjectPlacement.RelativePlacement.Location
        c = list(loc.Coordinates)
        c[2] += origin_offset
        loc.Coordinates = tuple(c)
    if axis_offset != 0.0:
        ref = w0.ObjectPlacement.RelativePlacement.RefDirection
        ref.DirectionRatios = (1.0, axis_offset, 0.0)
    for w in handle.by_type("IfcWall"):
        w.Name = None
    handle.write(str(path))
    return path


def test_geometric_opt_in_null_names(tmp_path: Path) -> None:
    spec = Spec.model_validate(pilot.mini_spec())
    ifc_path = tmp_path / "synthetic_mini.ifc"
    pilot.generate(spec, None, ifc_path)

    clean_spec, clean_report = pilot.extract(ifc_path)
    handle = ifcopenshell.open(str(ifc_path))
    walls_before = handle.by_type("IfcWall")
    for wall in walls_before:
        wall.Name = None
    handle.write(str(ifc_path))

    reopened = ifcopenshell.open(str(ifc_path))
    walls_after = reopened.by_type("IfcWall")
    assert len(walls_after) == len(walls_before)
    assert all(w.Name is None for w in walls_after)

    with pytest.raises(pilot.IntakeError, match="unsupported wall mapping"):
        pilot.extract(ifc_path)

    geo_spec, geo_report = pilot.extract(ifc_path, binding="geometric")

    assert geo_report["counts"] == clean_report["counts"] == pilot.expect_counts(spec)
    assert len(geo_spec.levels) == len(clean_spec.levels)
    assert [lv.name for lv in geo_spec.levels] == [lv.name for lv in clean_spec.levels]
    assert [lv.elev_m for lv in geo_spec.levels] == pytest.approx([lv.elev_m for lv in clean_spec.levels], abs=1e-6)

    assert len(geo_spec.floors) == len(clean_spec.floors)
    for geo_fl, clean_fl in zip(geo_spec.floors, clean_spec.floors, strict=True):
        assert geo_fl.level == clean_fl.level
        assert np.allclose(geo_fl.contour, clean_fl.contour, rtol=0.0, atol=1e-6)
        assert len(geo_fl.openings) == len(clean_fl.openings)
        for geo_op, clean_op in zip(geo_fl.openings, clean_fl.openings, strict=True):
            assert geo_op.wall == clean_op.wall
            assert geo_op.x_m == pytest.approx(clean_op.x_m, abs=1e-6)
            assert geo_op.sill_m == pytest.approx(clean_op.sill_m, abs=1e-6)
            assert geo_op.w_m == pytest.approx(clean_op.w_m, abs=1e-6)
            assert geo_op.h_m == pytest.approx(clean_op.h_m, abs=1e-6)
            assert geo_op.depth_m == pytest.approx(clean_op.depth_m, abs=1e-6)

    comparison = pilot.compare_specs(clean_spec.model_dump(mode="json"), geo_spec.model_dump(mode="json"), {}, {}, TOL)
    assert comparison["failing"] == []


@pytest.fixture(scope="module")
def fixture_bundle(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    base_dir = tmp_path_factory.mktemp("ifc_suite")
    tolerances = json.loads((BENCHMARK_DIR / "bench-k01-kpp1" / "tolerances.json").read_text(encoding="utf-8"))

    specs: dict[str, Any] = {}
    base_fixtures: dict[tuple[str, str], dict[str, Any]] = {}
    valid_fixtures: dict[tuple[str, str, str], Path] = {}
    malformed_fixtures: dict[tuple[str, str, str], Path] = {}
    all_36: list[tuple[Path, bool, str, str]] = []

    for case_id in CASES:
        spec_dict = json.loads((BENCHMARK_DIR / case_id / "spec.json").read_text(encoding="utf-8"))
        spec = Spec.model_validate(spec_dict)
        specs[case_id] = spec

        for unit_name, prefix in UNITS:
            clean_path = base_dir / f"{case_id}_{unit_name}_clean.ifc"
            pilot.generate(spec, prefix, clean_path)
            clean_spec, clean_report = pilot.extract(clean_path)

            handle = ifcopenshell.open(str(clean_path))
            oracle: dict[tuple[str, int], str] = {}
            for wall in handle.by_type("IfcWall"):
                st = pilot.storey_of(wall)
                assert wall.Name is not None and wall.Name.startswith("W")
                oracle[(st.GlobalId, int(wall.Name[1:]))] = wall.GlobalId

            base_fixtures[(case_id, unit_name)] = {
                "clean_path": clean_path,
                "clean_spec": clean_spec,
                "clean_report": clean_report,
                "oracle": oracle,
            }

            for variant in VARIANTS:
                if variant == "clean":
                    var_path = clean_path
                else:
                    var_path = base_dir / f"{case_id}_{unit_name}_{variant}.ifc"
                    vh = ifcopenshell.open(str(clean_path))
                    if variant == "null":
                        for w in vh.by_type("IfcWall"):
                            w.Name = None
                    elif variant == "identical":
                        for w in vh.by_type("IfcWall"):
                            w.Name = "Basic Wall:Generic - 200mm"
                    elif variant == "suffix":
                        sorted_w = sorted(vh.by_type("IfcWall"), key=lambda w: str(w.GlobalId))
                        for k, w in enumerate(sorted_w):
                            w.Name = f"Basic Wall:Generic - 200mm:{348921 + 7 * k}"
                    vh.write(str(var_path))

                    reopened_vh = ifcopenshell.open(str(var_path))
                    if variant == "null":
                        assert all(w.Name is None for w in reopened_vh.by_type("IfcWall"))
                    elif variant == "identical":
                        assert all(w.Name == "Basic Wall:Generic - 200mm" for w in reopened_vh.by_type("IfcWall"))
                    elif variant == "suffix":
                        re_sorted = sorted(reopened_vh.by_type("IfcWall"), key=lambda w: str(w.GlobalId))
                        for k, w in enumerate(re_sorted):
                            assert w.Name == f"Basic Wall:Generic - 200mm:{348921 + 7 * k}"

                valid_fixtures[(case_id, unit_name, variant)] = var_path
                all_36.append((var_path, True, case_id, unit_name))

            for fault in FAULTS:
                mf_path = base_dir / f"{case_id}_{unit_name}_{fault}.ifc"
                mh = ifcopenshell.open(str(clean_path))
                for w in mh.by_type("IfcWall"):
                    w.Name = None

                bld_pl = mh.by_type("IfcBuilding")[0].ObjectPlacement
                scale = pilot.length_scale(mh)
                inv_b = np.linalg.inv(np.array(ifcopenshell.util.placement.get_local_placement(bld_pl)))
                lowest_st = min(
                    mh.by_type("IfcBuildingStorey"),
                    key=lambda s: float((inv_b @ np.array(ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement)))[2, 3] * scale),
                )
                w0_gid = oracle[(lowest_st.GlobalId, 0)]
                w1_gid = oracle[(lowest_st.GlobalId, 1)]
                w0 = next(w for w in mh.by_type("IfcWall") if w.GlobalId == w0_gid)
                w1 = next(w for w in mh.by_type("IfcWall") if w.GlobalId == w1_gid)
                orig_z0 = float(w0.ObjectPlacement.RelativePlacement.Location.Coordinates[2])

                if fault == "shared_placement":
                    w1.ObjectPlacement = w0.ObjectPlacement
                elif fault == "z_shift":
                    loc = w0.ObjectPlacement.RelativePlacement.Location
                    coords = list(loc.Coordinates)
                    coords[2] = orig_z0 + 0.001 / scale
                    loc.Coordinates = tuple(coords)

                mh.write(str(mf_path))

                reopened_mh = ifcopenshell.open(str(mf_path))
                rw0 = next(w for w in reopened_mh.by_type("IfcWall") if w.GlobalId == w0_gid)
                rw1 = next(w for w in reopened_mh.by_type("IfcWall") if w.GlobalId == w1_gid)
                if fault == "shared_placement":
                    assert rw1.ObjectPlacement == rw0.ObjectPlacement
                elif fault == "z_shift":
                    delta_m = (float(rw0.ObjectPlacement.RelativePlacement.Location.Coordinates[2]) - orig_z0) * scale
                    assert np.isclose(delta_m, 0.001, rtol=0.0, atol=1e-10)
                assert all(w.Name is None for w in reopened_mh.by_type("IfcWall"))

                malformed_fixtures[(case_id, unit_name, fault)] = mf_path
                all_36.append((mf_path, False, case_id, unit_name))

    return {
        "specs": specs,
        "tolerances": tolerances,
        "base": base_fixtures,
        "valid": valid_fixtures,
        "malformed": malformed_fixtures,
        "all_36": all_36,
    }


@pytest.mark.parametrize("case_id,unit_name,variant", [(c, u, v) for c in CASES for u, _ in UNITS for v in VARIANTS])
def test_geometric_roundtrip_matrix(fixture_bundle: dict[str, Any], case_id: str, unit_name: str, variant: str) -> None:
    path = fixture_bundle["valid"][(case_id, unit_name, variant)]
    base = fixture_bundle["base"][(case_id, unit_name)]
    oracle = base["oracle"]
    clean_spec = base["clean_spec"]
    clean_report = base["clean_report"]
    orig_spec = fixture_bundle["specs"][case_id]
    tolerances = fixture_bundle["tolerances"]

    if variant == "clean":
        _, def_report = pilot.extract(path)
        assert def_report["counts"] == clean_report["counts"]
    else:
        with pytest.raises(pilot.IntakeError, match="unsupported wall mapping"):
            pilot.extract(path)

    geo_spec, geo_report = pilot.extract(path, binding="geometric")

    handle = ifcopenshell.open(str(path))
    for st, walls, ring, storey_z, bld_pl, scale in _all_storey_contexts(handle):
        mapping = pilot.bind_walls_geometric(walls, ring, storey_z, bld_pl, scale)
        for edge_idx, bound_wall in mapping.items():
            assert bound_wall.GlobalId == oracle[(st.GlobalId, edge_idx)]

    assert geo_report["counts"] == clean_report["counts"] == pilot.expect_counts(orig_spec)

    assert len(geo_spec.levels) == len(clean_spec.levels) == len(orig_spec.levels)
    for geo_lv, clean_lv, orig_lv in zip(geo_spec.levels, clean_spec.levels, orig_spec.levels, strict=True):
        assert abs(geo_lv.elev_m - clean_lv.elev_m) <= 1e-5
        assert abs(geo_lv.elev_m - orig_lv.elev_m) <= 1e-5

    assert len(geo_spec.floors) == len(clean_spec.floors) == len(orig_spec.expanded_floors())
    for geo_fl, clean_fl, orig_fl in zip(geo_spec.floors, clean_spec.floors, orig_spec.expanded_floors(), strict=True):
        assert np.allclose(geo_fl.contour, clean_fl.contour, rtol=0.0, atol=1e-5)
        assert np.allclose(geo_fl.contour, orig_fl.contour, rtol=0.0, atol=1e-5)
        assert len(geo_fl.openings) == len(clean_fl.openings) == len(orig_fl.openings)
        for geo_op, clean_op, orig_op in zip(geo_fl.openings, clean_fl.openings, orig_fl.openings, strict=True):
            orig_depth = float(orig_op.depth_m if orig_op.depth_m is not None else orig_spec.opening_depth_default_m)
            assert geo_op.wall == clean_op.wall == orig_op.wall
            assert abs(geo_op.x_m - clean_op.x_m) <= 1e-5
            assert abs(geo_op.sill_m - clean_op.sill_m) <= 1e-5
            assert abs(geo_op.w_m - clean_op.w_m) <= 1e-5
            assert abs(geo_op.h_m - clean_op.h_m) <= 1e-5
            assert abs(geo_op.depth_m - clean_op.depth_m) <= 1e-5
            assert abs(geo_op.x_m - orig_op.x_m) <= 1e-5
            assert abs(geo_op.sill_m - orig_op.sill_m) <= 1e-5
            assert abs(geo_op.w_m - orig_op.w_m) <= 1e-5
            assert abs(geo_op.h_m - orig_op.h_m) <= 1e-5
            assert abs(geo_op.depth_m - orig_depth) <= 1e-5

    compared = json.loads(json.dumps(orig_spec.model_dump(mode="json")))
    compared["roof"] = None
    comp = pilot.compare_specs(compared, geo_spec.model_dump(mode="json"), {}, {}, tolerances)
    assert comp["failing"] == []

    assert geo_report["binding"] == "geometric"
    assert geo_report["wall_profile_vs_geom_m"] <= 1e-3
    assert not any("W0000" in s for s in geo_report["scope"]["supported"])
    assert any("straight vertical walls whose origin and X axis match the slab contour edge" in s for s in geo_report["scope"]["supported"])

    level_m, coord_m, box_m = pilot.independent_devs(compared, geo_spec.model_dump(mode="json"))
    assert level_m <= 1e-5 and coord_m <= 1e-5 and box_m <= 1e-5


@pytest.mark.parametrize("case_id,unit_name,fault", [(c, u, f) for c in CASES for u, _ in UNITS for f in FAULTS])
def test_malformed_binding_evidence(fixture_bundle: dict[str, Any], case_id: str, unit_name: str, fault: str) -> None:
    path = fixture_bundle["malformed"][(case_id, unit_name, fault)]
    oracle = fixture_bundle["base"][(case_id, unit_name)]["oracle"]

    handle = ifcopenshell.open(str(path))
    scale = pilot.length_scale(handle)
    bld_pl = handle.by_type("IfcBuilding")[0].ObjectPlacement
    inv_b = np.linalg.inv(np.array(ifcopenshell.util.placement.get_local_placement(bld_pl)))
    lowest_st = min(
        handle.by_type("IfcBuildingStorey"),
        key=lambda s: float((inv_b @ np.array(ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement)))[2, 3] * scale),
    )
    lowest_slab = next(s for s in handle.by_type("IfcSlab") if pilot.storey_of(s).GlobalId == lowest_st.GlobalId)
    _, walls, ring, storey_z, bld_pl, scale = _storey_context(handle, lowest_slab)

    with pytest.raises(pilot.UnresolvedBinding) as exc_info:
        pilot.bind_walls_geometric(walls, ring, storey_z, bld_pl, scale)

    ev = exc_info.value.evidence
    w0_gid = oracle[(lowest_st.GlobalId, 0)]
    w1_gid = oracle[(lowest_st.GlobalId, 1)]

    if fault == "shared_placement":
        assert "0" in ev["edges_with_multiple_walls"]
        assert w0_gid in ev["edges_with_multiple_walls"]["0"] and w1_gid in ev["edges_with_multiple_walls"]["0"]
        assert 1 in ev["edges_without_wall"]
    elif fault == "z_shift":
        assert w0_gid in ev["walls_without_edge"]
        assert 0 in ev["edges_without_wall"]

    with pytest.raises(pilot.IntakeError):
        pilot.extract(path, binding="geometric")


@pytest.mark.parametrize("idx", range(36))
def test_binding_order_repeat_invariance(fixture_bundle: dict[str, Any], idx: int) -> None:
    path, is_valid, case_id, unit_name = fixture_bundle["all_36"][idx]
    oracle = fixture_bundle["base"][(case_id, unit_name)]["oracle"]

    read_results: list[list[dict[str, Any]]] = []
    for _ in range(3):
        handle = ifcopenshell.open(str(path))
        scale = pilot.length_scale(handle)
        bld_pl = handle.by_type("IfcBuilding")[0].ObjectPlacement
        inv_b = np.linalg.inv(np.array(ifcopenshell.util.placement.get_local_placement(bld_pl)))
        lowest_st = min(
            handle.by_type("IfcBuildingStorey"),
            key=lambda s: float((inv_b @ np.array(ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement)))[2, 3] * scale),
        )
        contexts = _all_storey_contexts(handle)
        order_results: list[list[dict[str, Any]]] = []

        for order_idx in range(3):
            file_storey_out: list[dict[str, Any]] = []
            for st, walls, ring, storey_z, bld_pl, scale in contexts:
                wall_orders = [walls, list(reversed(walls)), walls[1:] + walls[:1] if len(walls) > 1 else walls]
                w_list = wall_orders[order_idx]
                try:
                    mapping = pilot.bind_walls_geometric(w_list, ring, storey_z, bld_pl, scale)
                    file_storey_out.append({
                        "status": "resolved",
                        "storey_gid": st.GlobalId,
                        "mapping": {edge: w.GlobalId for edge, w in sorted(mapping.items())},
                    })
                except pilot.UnresolvedBinding as exc:
                    file_storey_out.append({
                        "status": "unresolved",
                        "storey_gid": st.GlobalId,
                        "evidence": exc.evidence,
                    })

            unresolved = [item for item in file_storey_out if item["status"] == "unresolved"]
            if is_valid:
                assert len(unresolved) == 0
                for item in file_storey_out:
                    st_gid = item["storey_gid"]
                    for edge, w_gid in item["mapping"].items():
                        assert w_gid == oracle[(st_gid, edge)]
            else:
                assert len(unresolved) == 1
                assert unresolved[0]["storey_gid"] == lowest_st.GlobalId
                for item in file_storey_out:
                    if item["status"] == "resolved":
                        st_gid = item["storey_gid"]
                        for edge, w_gid in item["mapping"].items():
                            assert w_gid == oracle[(st_gid, edge)]

            order_results.append(file_storey_out)

        assert order_results[0] == order_results[1] == order_results[2]
        read_results.append(order_results[0])

    assert read_results[0] == read_results[1] == read_results[2]


@pytest.mark.parametrize("param_type,is_inside", [("origin", True), ("origin", False), ("axis", True), ("axis", False)])
def test_binding_tolerance_limits(tmp_path: Path, param_type: str, is_inside: bool) -> None:
    delta = 1e-4 - 1e-6 if is_inside else 1e-4 + 1e-6
    origin_offset = delta if param_type == "origin" else 0.0
    axis_offset = delta if param_type == "axis" else 0.0
    path = _make_tolerance_fixture(tmp_path, origin_offset, axis_offset)

    handle = ifcopenshell.open(str(path))
    _, walls, ring, storey_z, bld_pl, scale = _storey_context(handle, handle.by_type("IfcSlab")[0])

    if is_inside:
        mapping = pilot.bind_walls_geometric(walls, ring, storey_z, bld_pl, scale)
        assert len(mapping) == 4
    else:
        with pytest.raises(pilot.UnresolvedBinding):
            pilot.bind_walls_geometric(walls, ring, storey_z, bld_pl, scale)


def test_binding_failure_after_success(tmp_path: Path) -> None:
    path_good = _make_tolerance_fixture(tmp_path / "good", 0.0, 0.0)
    handle = ifcopenshell.open(str(path_good))
    _, walls, ring, storey_z, bld_pl, scale = _storey_context(handle, handle.by_type("IfcSlab")[0])

    mapping = pilot.bind_walls_geometric(walls, ring, storey_z, bld_pl, scale)
    assert len(mapping) == 4
    assert pilot.bind_walls_geometric.last_evidence is not None
    assert pilot.bind_walls_geometric.last_evidence["reason"] == "exact_match"

    w0 = mapping[0]
    w0_gid = w0.GlobalId
    loc = w0.ObjectPlacement.RelativePlacement.Location
    coords = list(loc.Coordinates)
    coords[2] += 0.001 / scale
    loc.Coordinates = tuple(coords)

    with pytest.raises(pilot.UnresolvedBinding) as exc_info:
        pilot.bind_walls_geometric(walls, ring, storey_z, bld_pl, scale)

    ev = exc_info.value.evidence
    assert pilot.bind_walls_geometric.last_evidence is ev
    assert ev["reason"] == "unresolved_mapping"
    assert ev["walls_without_edge"] == [w0_gid]
    assert ev["edges_without_wall"] == [0]


def test_empty_walls(tmp_path: Path) -> None:
    path = _make_tolerance_fixture(tmp_path, 0.0, 0.0)
    handle = ifcopenshell.open(str(path))
    _, _, ring, storey_z, bld_pl, scale = _storey_context(handle, handle.by_type("IfcSlab")[0])

    with pytest.raises(pilot.UnresolvedBinding) as exc_info:
        pilot.bind_walls_geometric([], ring, storey_z, bld_pl, scale)

    ev = exc_info.value.evidence
    assert ev["n_walls"] == 0 and ev["n_edges"] == 4 and ev["edges_without_wall"] == [0, 1, 2, 3]


def test_partial_binding(tmp_path: Path) -> None:
    path = _make_tolerance_fixture(tmp_path, 0.0, 0.0)
    handle = ifcopenshell.open(str(path))
    _, walls, ring, storey_z, bld_pl, scale = _storey_context(handle, handle.by_type("IfcSlab")[0])

    with pytest.raises(pilot.UnresolvedBinding) as exc_info1:
        pilot.bind_walls_geometric(walls[:3], ring, storey_z, bld_pl, scale)
    assert exc_info1.value.evidence["n_walls"] == 3 and exc_info1.value.evidence["n_edges"] == 4
    assert 3 in exc_info1.value.evidence["edges_without_wall"]

    walls_missing_pl = list(walls)
    walls_missing_pl[2].ObjectPlacement = None
    with pytest.raises(pilot.UnresolvedBinding) as exc_info2:
        pilot.bind_walls_geometric(walls_missing_pl, ring, storey_z, bld_pl, scale)
    assert walls_missing_pl[2].GlobalId in exc_info2.value.evidence["walls_without_edge"]
    assert 2 in exc_info2.value.evidence["edges_without_wall"]


def test_unknown_binding_mode(tmp_path: Path) -> None:
    path = _make_tolerance_fixture(tmp_path, 0.0, 0.0)
    with pytest.raises(pilot.IntakeError, match="unknown binding mode"):
        pilot.extract(path, binding="unknown")


@pytest.mark.parametrize("corrupt_mode", ["none_gid", "empty_gid", "duplicate_gid"])
def test_binding_invalid_or_duplicate_global_ids(tmp_path: Path, corrupt_mode: str) -> None:
    path = _make_tolerance_fixture(tmp_path, 0.0, 0.0)
    handle = ifcopenshell.open(str(path))
    _, walls, ring, storey_z, bld_pl, scale = _storey_context(handle, handle.by_type("IfcSlab")[0])

    if corrupt_mode == "none_gid":
        walls[0].GlobalId = None
    elif corrupt_mode == "empty_gid":
        walls[0].GlobalId = ""
    elif corrupt_mode == "duplicate_gid":
        walls[0].GlobalId = walls[1].GlobalId

    order1 = list(walls)
    order2 = list(reversed(walls))

    with pytest.raises(pilot.UnresolvedBinding) as exc1:
        pilot.bind_walls_geometric(order1, ring, storey_z, bld_pl, scale)
    with pytest.raises(pilot.UnresolvedBinding) as exc2:
        pilot.bind_walls_geometric(order2, ring, storey_z, bld_pl, scale)

    assert exc1.value.evidence["reason"] == "invalid_or_duplicate_wall_global_id"
    assert exc1.value.evidence == exc2.value.evidence


@pytest.mark.parametrize("bad_z", [float("nan"), float("inf"), float("-inf")])
def test_binding_nonfinite_storey_z(tmp_path: Path, bad_z: float) -> None:
    path = _make_tolerance_fixture(tmp_path, 0.0, 0.0)
    handle = ifcopenshell.open(str(path))
    _, walls, ring, _z, bld_pl, scale = _storey_context(handle, handle.by_type("IfcSlab")[0])

    with pytest.raises(pilot.UnresolvedBinding) as exc_info:
        pilot.bind_walls_geometric(walls, ring, bad_z, bld_pl, scale)

    ev = exc_info.value.evidence
    assert ev["reason"] == "unresolved_mapping"
    assert len(ev["walls_without_edge"]) == len(walls)
    assert len(ev["edges_without_wall"]) == len(ring)
    assert ev["eligible_pairs"] == []


def test_binding_multiple_eligible_edges(tmp_path: Path) -> None:
    path = _make_tolerance_fixture(tmp_path, 0.0, 0.0)
    handle = ifcopenshell.open(str(path))
    st, walls, _ring, storey_z, bld_pl, scale = _storey_context(handle, handle.by_type("IfcSlab")[0])

    # 5-segment contour with collinear consecutive edges along X: (0,0)->(5e-5,0) and (5e-5,0)->(10,0)
    ring_5 = [(0.0, 0.0), (5e-5, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]

    # Configure wall 0 at (0, 0) and wall 1 at (5e-5, 0), both facing +X
    w0 = walls[0]
    w1 = walls[1]
    w0.ObjectPlacement.RelativePlacement.Location.Coordinates = (0.0, 0.0, 0.0)
    w0.ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios = (1.0, 0.0, 0.0)
    w1.ObjectPlacement.RelativePlacement.Location.Coordinates = (5e-5, 0.0, 0.0)
    w1.ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios = (1.0, 0.0, 0.0)

    # Configure remaining walls for remaining edges
    walls[2].ObjectPlacement.RelativePlacement.Location.Coordinates = (10.0, 0.0, 0.0)
    walls[2].ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios = (0.0, 1.0, 0.0)
    walls[3].ObjectPlacement.RelativePlacement.Location.Coordinates = (10.0, 5.0, 0.0)
    walls[3].ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios = (-1.0, 0.0, 0.0)

    # Add 5th wall for edge 4
    w4_pl = pilot.placement(handle, st.ObjectPlacement, (0.0, 5.0, 0.0), (0.0, -1.0, 0.0))
    hist = handle.by_type("IfcOwnerHistory")[0]
    w4 = pilot.element(handle, "IfcWall", hist, None, w4_pl, None)

    walls_5 = [w0, w1, walls[2], walls[3], w4]

    with pytest.raises(pilot.UnresolvedBinding) as exc_info:
        pilot.bind_walls_geometric(walls_5, ring_5, storey_z, bld_pl, scale)

    ev = exc_info.value.evidence
    assert ev["reason"] == "unresolved_mapping"
    assert len(ev["walls_with_multiple_edges"]) >= 2
    assert len(ev["edges_with_multiple_walls"]) >= 2
