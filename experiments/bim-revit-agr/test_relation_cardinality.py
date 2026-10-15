"""Cardinality and conflict tests for IFC relation census."""

from collections import Counter
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import ifcopenshell
import ifcopenshell.guid
import pytest

_custom_temp = os.path.join(tempfile.gettempdir(), "pytest_temp_dir")
os.makedirs(_custom_temp, exist_ok=True)
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", _custom_temp)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ifc_probe
import relation_multimap


def build_independent_raw_counter(model: Any) -> Counter[tuple[str, str | None, str | None, str | None]]:
    counts: Counter[tuple[str, str | None, str | None, str | None]] = Counter()
    for rel in model.by_type("IfcRelVoidsElement"):
        rel_id = rel.GlobalId if rel else None
        opening = getattr(rel, "RelatedOpeningElement", None)
        wall = getattr(rel, "RelatingBuildingElement", None)
        counts[(
            "void",
            rel_id,
            getattr(opening, "GlobalId", None) if opening else None,
            getattr(wall, "GlobalId", None) if wall else None,
        )] += 1
    for rel in model.by_type("IfcRelFillsElement"):
        rel_id = rel.GlobalId if rel else None
        opening = getattr(rel, "RelatingOpeningElement", None)
        window = getattr(rel, "RelatedBuildingElement", None)
        counts[(
            "fill",
            rel_id,
            getattr(opening, "GlobalId", None) if opening else None,
            getattr(window, "GlobalId", None) if window else None,
        )] += 1
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        rel_id = rel.GlobalId if rel else None
        structure = getattr(rel, "RelatingStructure", None)
        elements = getattr(rel, "RelatedElements", None) or []
        if elements:
            for el in elements:
                counts[(
                    "contain",
                    rel_id,
                    getattr(el, "GlobalId", None) if el else None,
                    getattr(structure, "GlobalId", None) if structure else None,
                )] += 1
        else:
            counts[(
                "contain",
                rel_id,
                None,
                getattr(structure, "GlobalId", None) if structure else None,
            )] += 1
    return counts


def build_independent_singletons(model: Any) -> dict[str, dict[str, str]]:
    void_map: dict[str, str] = {}
    for rel in model.by_type("IfcRelVoidsElement"):
        op = getattr(rel, "RelatedOpeningElement", None)
        bldg = getattr(rel, "RelatingBuildingElement", None)
        if op and bldg and op.GlobalId and bldg.GlobalId:
            void_map[op.GlobalId] = bldg.GlobalId

    fill_map: dict[str, str] = {}
    for rel in model.by_type("IfcRelFillsElement"):
        op = getattr(rel, "RelatingOpeningElement", None)
        bldg = getattr(rel, "RelatedBuildingElement", None)
        if op and bldg and op.GlobalId and bldg.GlobalId:
            fill_map[op.GlobalId] = bldg.GlobalId

    contain_map: dict[str, str] = {}
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        struct = getattr(rel, "RelatingStructure", None)
        for el in getattr(rel, "RelatedElements", None) or []:
            if el and struct and el.GlobalId and struct.GlobalId:
                contain_map[el.GlobalId] = struct.GlobalId

    return {
        "void": void_map,
        "fill": fill_map,
        "contain": contain_map,
    }


@dataclass
class CleanModelData:
    spec_name: str
    unit: str
    path: Path
    independent_counter: Counter[tuple[str, str | None, str | None, str | None]]
    independent_singletons: dict[str, dict[str, str]]
    product_count: int


@dataclass
class ConflictingModelData:
    family: str
    clean_info: CleanModelData
    path: Path
    injected_tuple: tuple[str, str | None, str | None, str | None]
    source_id: str
    expected_relation_ids: list[str]
    expected_endpoint_ids: list[str]


@pytest.fixture(scope="module")
def dataset(tmp_path_factory: pytest.TempPathFactory):
    base_tmp = tmp_path_factory.mktemp("ifc_cardinality_data")
    benchmark_dir = Path(__file__).resolve().parents[2] / "benchmark"
    specs = [
        "bench-b01-box",
        "bench-b02-corner-niche",
        "bench-b02t-terrace",
    ]
    units = [("m", False), ("mm", True)]

    clean_files: list[CleanModelData] = []
    conflicting_files: list[ConflictingModelData] = []

    for spec_name in specs:
        spec_path = benchmark_dir / spec_name / "spec.json"
        assert spec_path.is_file(), f"Spec missing at {spec_path}"
        spec = ifc_probe.Spec.model_validate_json(spec_path.read_text(encoding="utf-8"))

        for unit_name, milli in units:
            clean_path = base_tmp / f"{spec_name}_{unit_name}_clean.ifc"
            ifc_probe.write_ifc(spec, clean_path, milli=milli)

            clean_model = ifcopenshell.open(str(clean_path))
            clean_counter = build_independent_raw_counter(clean_model)
            clean_singletons_map = build_independent_singletons(clean_model)
            prod_count = len(clean_model.by_type("IfcProduct"))

            clean_data = CleanModelData(
                spec_name=spec_name,
                unit=unit_name,
                path=clean_path,
                independent_counter=clean_counter,
                independent_singletons=clean_singletons_map,
                product_count=prod_count,
            )
            clean_files.append(clean_data)

            for family in ("void", "fill", "contain"):
                conflicting_path = base_tmp / f"{spec_name}_{unit_name}_conflict_{family}.ifc"
                model_to_modify = ifcopenshell.open(str(clean_path))
                fresh_guid = ifcopenshell.guid.new()

                if family == "void":
                    orig_rels = [r for r in model_to_modify.by_type("IfcRelVoidsElement") if r.RelatedOpeningElement]
                    assert orig_rels, "Must have IfcRelVoidsElement"
                    orig_rel = orig_rels[0]
                    opening = orig_rel.RelatedOpeningElement
                    orig_wall = orig_rel.RelatingBuildingElement
                    assert orig_wall is not None
                    second_wall = [w for w in model_to_modify.by_type("IfcWall") if w.GlobalId != orig_wall.GlobalId][0]
                    model_to_modify.create_entity(
                        "IfcRelVoidsElement",
                        GlobalId=fresh_guid,
                        RelatingBuildingElement=second_wall,
                        RelatedOpeningElement=opening,
                    )
                    source_id = opening.GlobalId
                    expected_rel_ids = sorted([orig_rel.GlobalId, fresh_guid])
                    expected_end_ids = sorted([orig_wall.GlobalId, second_wall.GlobalId])
                    injected_tup = ("void", fresh_guid, opening.GlobalId, second_wall.GlobalId)

                elif family == "fill":
                    orig_rels = [r for r in model_to_modify.by_type("IfcRelFillsElement") if r.RelatingOpeningElement]
                    assert orig_rels, "Must have IfcRelFillsElement"
                    orig_rel = orig_rels[0]
                    opening = orig_rel.RelatingOpeningElement
                    orig_window = orig_rel.RelatedBuildingElement
                    assert orig_window is not None
                    second_window = [w for w in model_to_modify.by_type("IfcWindow") if w.GlobalId != orig_window.GlobalId][0]
                    model_to_modify.create_entity(
                        "IfcRelFillsElement",
                        GlobalId=fresh_guid,
                        RelatingOpeningElement=opening,
                        RelatedBuildingElement=second_window,
                    )
                    source_id = opening.GlobalId
                    expected_rel_ids = sorted([orig_rel.GlobalId, fresh_guid])
                    expected_end_ids = sorted([orig_window.GlobalId, second_window.GlobalId])
                    injected_tup = ("fill", fresh_guid, opening.GlobalId, second_window.GlobalId)

                else:  # contain
                    orig_wall = model_to_modify.by_type("IfcWall")[0]
                    contain_rels = [
                        r for r in model_to_modify.by_type("IfcRelContainedInSpatialStructure")
                        if any(e.GlobalId == orig_wall.GlobalId for e in (r.RelatedElements or []))
                    ]
                    assert contain_rels, "Must have containment relation for wall"
                    orig_rel = contain_rels[0]
                    orig_storey = orig_rel.RelatingStructure
                    assert orig_storey is not None
                    second_storey = [s for s in model_to_modify.by_type("IfcBuildingStorey") if s.GlobalId != orig_storey.GlobalId][0]
                    model_to_modify.create_entity(
                        "IfcRelContainedInSpatialStructure",
                        GlobalId=fresh_guid,
                        RelatingStructure=second_storey,
                        RelatedElements=[orig_wall],
                    )
                    source_id = orig_wall.GlobalId
                    expected_rel_ids = sorted([orig_rel.GlobalId, fresh_guid])
                    expected_end_ids = sorted([orig_storey.GlobalId, second_storey.GlobalId])
                    injected_tup = ("contain", fresh_guid, orig_wall.GlobalId, second_storey.GlobalId)

                model_to_modify.write(str(conflicting_path))
                reopened = ifcopenshell.open(str(conflicting_path))
                assert len(reopened.by_type("IfcProduct")) == prod_count, "Products must remain unchanged"

                conflicting_files.append(ConflictingModelData(
                    family=family,
                    clean_info=clean_data,
                    path=conflicting_path,
                    injected_tuple=injected_tup,
                    source_id=source_id,
                    expected_relation_ids=expected_rel_ids,
                    expected_endpoint_ids=expected_end_ids,
                ))

    return {
        "clean_files": clean_files,
        "conflicting_files": conflicting_files,
    }


def test_competing_void_ledger(tmp_path: Path):
    spec_path = Path(__file__).resolve().parents[2] / "benchmark" / "bench-b01-box" / "spec.json"
    assert spec_path.is_file(), f"Spec file not found at {spec_path}"
    spec = ifc_probe.Spec.model_validate_json(spec_path.read_text(encoding="utf-8"))

    clean_ifc_path = tmp_path / "bench-b01-box.ifc"
    ifc_probe.write_ifc(spec, clean_ifc_path, milli=False)

    model = ifcopenshell.open(str(clean_ifc_path))

    openings = model.by_type("IfcOpeningElement")
    assert len(openings) >= 1
    opening = openings[0]

    orig_rel_voids = [r for r in model.by_type("IfcRelVoidsElement") if r.RelatedOpeningElement == opening]
    assert len(orig_rel_voids) == 1
    orig_rel = orig_rel_voids[0]
    orig_wall = orig_rel.RelatingBuildingElement
    assert orig_wall is not None

    walls = model.by_type("IfcWall")
    distinct_walls = [w for w in walls if w != orig_wall]
    assert len(distinct_walls) >= 1
    second_wall = distinct_walls[0]

    fresh_guid = ifcopenshell.guid.new()
    second_rel = model.create_entity(
        "IfcRelVoidsElement",
        GlobalId=fresh_guid,
        RelatingBuildingElement=second_wall,
        RelatedOpeningElement=opening,
    )
    assert second_rel is not None

    injected_path = tmp_path / "bench-b01-box-competing.ifc"
    model.write(str(injected_path))

    reopened = ifcopenshell.open(str(injected_path))
    independent_void_rels = [
        rel
        for rel in reopened.by_type("IfcRelVoidsElement")
        if rel.RelatedOpeningElement and rel.RelatedOpeningElement.GlobalId == opening.GlobalId
    ]
    assert len(independent_void_rels) == 2

    relation_tuples = [
        (rel.GlobalId, rel.RelatedOpeningElement.GlobalId, rel.RelatingBuildingElement.GlobalId)
        for rel in independent_void_rels
    ]
    assert relation_tuples[0][0] != relation_tuples[1][0]
    assert relation_tuples[0][1] == relation_tuples[1][1] == opening.GlobalId
    assert relation_tuples[0][2] != relation_tuples[1][2]

    expected_source_id = opening.GlobalId
    expected_relation_ids = sorted([t[0] for t in relation_tuples])
    expected_endpoint_ids = sorted([t[2] for t in relation_tuples])

    ledger = ifc_probe.read_ledger(injected_path)

    assert "relation_census" in ledger, "read_ledger must return relation_census"
    census = ledger["relation_census"]
    assert isinstance(census, dict)
    assert "records" in census
    assert "maps" in census
    assert "diagnostics" in census

    assert len(census["diagnostics"]) == 1
    diag = census["diagnostics"][0]

    expected_diag = {
        "family": "void",
        "source_id": expected_source_id,
        "endpoint_ids": expected_endpoint_ids,
        "relation_ids": expected_relation_ids,
        "kind": "cardinality",
        "status": "unresolved",
        "selected_endpoint": None,
    }
    assert diag == expected_diag

    assert diag["family"] == "void"
    assert diag["source_id"] == expected_source_id
    assert diag["endpoint_ids"] == expected_endpoint_ids
    assert diag["endpoint_ids"] == sorted(diag["endpoint_ids"])
    assert diag["relation_ids"] == expected_relation_ids
    assert diag["relation_ids"] == sorted(diag["relation_ids"])
    assert diag["kind"] == "cardinality"
    assert diag["status"] == "unresolved"
    assert diag["selected_endpoint"] is None

    affected_openings = [op for op in ledger["openings"] if op["global_id"] == opening.GlobalId]
    assert len(affected_openings) == 1
    assert affected_openings[0]["host_id"] is None


def test_conflicting_links(dataset):
    assert len(dataset["conflicting_files"]) == 18
    for case in dataset["conflicting_files"]:
        ledger = ifc_probe.read_ledger(case.path)
        census = ledger["relation_census"]

        reopened = ifcopenshell.open(str(case.path))
        independent_counter = build_independent_raw_counter(reopened)
        expected_counter = case.clean_info.independent_counter + Counter([case.injected_tuple])
        assert independent_counter == expected_counter

        raw_counter = Counter(
            (r["family"], r["relation_id"], r["source_id"], r["endpoint_id"])
            for r in census["records"]
        )
        assert raw_counter == independent_counter

        assert len(census["diagnostics"]) == 1
        diag = census["diagnostics"][0]
        assert diag["family"] == case.family
        assert diag["source_id"] == case.source_id
        assert diag["relation_ids"] == case.expected_relation_ids
        assert diag["endpoint_ids"] == case.expected_endpoint_ids
        assert diag["kind"] == "cardinality"
        assert diag["status"] == "unresolved"
        assert diag["selected_endpoint"] is None

        if case.family == "void":
            opening = [op for op in ledger["openings"] if op["global_id"] == case.source_id][0]
            assert opening["host_id"] is None
        elif case.family == "fill":
            opening = [op for op in ledger["openings"] if op["global_id"] == case.source_id][0]
            assert opening["fill_id"] is None
        elif case.family == "contain":
            elem = [x for x in ledger["slabs"] + ledger["walls"] + ledger["windows"] if x["global_id"] == case.source_id][0]
            assert elem["storey_id"] is None

        assert f"cardinality {case.family} {case.source_id} unresolved" in ledger["issues"]
        if case.family == "void":
            assert f"missing host {case.source_id}" not in ledger["issues"]
        elif case.family == "fill":
            assert f"missing fill {case.source_id}" not in ledger["issues"]
        elif case.family == "contain":
            assert f"missing containment {case.source_id}" not in ledger["issues"]


def test_clean_singletons(dataset):
    assert len(dataset["clean_files"]) == 6
    for clean in dataset["clean_files"]:
        ledger = ifc_probe.read_ledger(clean.path)
        census = ledger["relation_census"]

        assert len(ledger["issues"]) == 0
        assert len(census["diagnostics"]) == 0

        raw_counter = Counter(
            (r["family"], r["relation_id"], r["source_id"], r["endpoint_id"])
            for r in census["records"]
        )
        assert raw_counter == clean.independent_counter

        for op in ledger["openings"]:
            assert op["host_id"] == clean.independent_singletons["void"][op["global_id"]]
            assert op["fill_id"] == clean.independent_singletons["fill"][op["global_id"]]

        for elem in ledger["slabs"] + ledger["walls"] + ledger["windows"]:
            assert elem["storey_id"] == clean.independent_singletons["contain"][elem["global_id"]]


class ReverseByTypeWrapper:
    """Wrapper that reverses the order of entities returned by by_type."""

    def __init__(self, model: Any):
        self._model = model

    def by_type(self, type_name: str) -> list[Any]:
        return list(reversed(self._model.by_type(type_name)))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)


def test_iteration_order(dataset):
    all_paths = [clean.path for clean in dataset["clean_files"]] + [
        conflict.path for conflict in dataset["conflicting_files"]
    ]
    assert len(all_paths) == 24

    for p in all_paths:
        model = ifcopenshell.open(str(p))

        for _ in range(3):
            fwd = relation_multimap.canonical(relation_multimap.census(model, reverse=False))
            rev = relation_multimap.canonical(relation_multimap.census(model, reverse=True))
            assert fwd == rev

        wrapper = ReverseByTypeWrapper(model)
        wrapped_canonical = relation_multimap.canonical(relation_multimap.census(wrapper, reverse=False))
        fwd_canonical = relation_multimap.canonical(relation_multimap.census(model, reverse=False))
        assert wrapped_canonical == fwd_canonical


def test_missing_links(dataset, tmp_path: Path):
    clean_sample = dataset["clean_files"][0]

    for family in ("void", "fill", "contain"):
        punched_path = tmp_path / f"missing_{family}.ifc"
        model = ifcopenshell.open(str(clean_sample.path))

        if family == "void":
            rel = model.by_type("IfcRelVoidsElement")[0]
            target_id = rel.RelatedOpeningElement.GlobalId
            model.remove(rel)
            expected_issue = f"missing host {target_id}"
        elif family == "fill":
            rel = model.by_type("IfcRelFillsElement")[0]
            target_id = rel.RelatingOpeningElement.GlobalId
            model.remove(rel)
            expected_issue = f"missing fill {target_id}"
        else:
            rel = max(model.by_type("IfcRelContainedInSpatialStructure"), key=lambda item: len(item.RelatedElements or []))
            elems = list(rel.RelatedElements or [])
            assert len(elems) > 0
            removed_el = elems[0]
            target_id = removed_el.GlobalId
            if len(elems) > 1:
                rel.RelatedElements = elems[1:]
            else:
                model.remove(rel)
            expected_issue = f"missing containment {target_id}"

        model.write(str(punched_path))
        ledger = ifc_probe.read_ledger(punched_path)
        assert expected_issue in ledger["issues"]


def test_same_endpoint(dataset, tmp_path: Path):
    clean_sample = dataset["clean_files"][0]

    for family in ("void", "fill", "contain"):
        dup_path = tmp_path / f"same_endpoint_{family}.ifc"
        model = ifcopenshell.open(str(clean_sample.path))
        fresh_guid = ifcopenshell.guid.new()

        if family == "void":
            orig_rel = model.by_type("IfcRelVoidsElement")[0]
            source_id = orig_rel.RelatedOpeningElement.GlobalId
            endpoint_id = orig_rel.RelatingBuildingElement.GlobalId
            model.create_entity(
                "IfcRelVoidsElement",
                GlobalId=fresh_guid,
                RelatedOpeningElement=orig_rel.RelatedOpeningElement,
                RelatingBuildingElement=orig_rel.RelatingBuildingElement,
            )
        elif family == "fill":
            orig_rel = model.by_type("IfcRelFillsElement")[0]
            source_id = orig_rel.RelatingOpeningElement.GlobalId
            endpoint_id = orig_rel.RelatedBuildingElement.GlobalId
            model.create_entity(
                "IfcRelFillsElement",
                GlobalId=fresh_guid,
                RelatingOpeningElement=orig_rel.RelatingOpeningElement,
                RelatedBuildingElement=orig_rel.RelatedBuildingElement,
            )
        else:
            orig_rel = [r for r in model.by_type("IfcRelContainedInSpatialStructure") if r.RelatedElements][0]
            el = orig_rel.RelatedElements[0]
            source_id = el.GlobalId
            endpoint_id = orig_rel.RelatingStructure.GlobalId
            model.create_entity(
                "IfcRelContainedInSpatialStructure",
                GlobalId=fresh_guid,
                RelatingStructure=orig_rel.RelatingStructure,
                RelatedElements=[el],
            )

        model.write(str(dup_path))
        ledger = ifc_probe.read_ledger(dup_path)
        census = ledger["relation_census"]

        matching_rows = [
            r for r in census["records"]
            if r["family"] == family and r["source_id"] == source_id and r["endpoint_id"] == endpoint_id
        ]
        assert len(matching_rows) == 2
        retained_ids = {r["relation_id"] for r in matching_rows}
        assert orig_rel.GlobalId in retained_ids
        assert fresh_guid in retained_ids

        assert len([d for d in census["diagnostics"] if d["family"] == family and d["source_id"] == source_id]) == 0

        singletons = relation_multimap.singletons(census["maps"], family)
        assert singletons.get(source_id) == endpoint_id


def test_empty_census():
    empty_ifc = ifcopenshell.file(schema="IFC4")
    c = relation_multimap.census(empty_ifc)
    assert c["records"] == []
    assert c["maps"] == {"void": {}, "fill": {}, "contain": {}}
    assert c["diagnostics"] == []
    assert relation_multimap.canonical(c) == '{"diagnostics":[],"maps":{"contain":{},"fill":{},"void":{}},"records":[]}'


def test_partial_relation(tmp_path: Path):
    model = ifcopenshell.file(schema="IFC4")
    opening_guid = ifcopenshell.guid.new()
    opening = model.create_entity("IfcOpeningElement", GlobalId=opening_guid)
    void_rel_guid = ifcopenshell.guid.new()
    model.create_entity(
        "IfcRelVoidsElement",
        GlobalId=void_rel_guid,
        RelatedOpeningElement=opening,
        RelatingBuildingElement=None,
    )

    storey_guid = ifcopenshell.guid.new()
    storey = model.create_entity("IfcBuildingStorey", GlobalId=storey_guid)
    contain_rel_guid = ifcopenshell.guid.new()
    model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=contain_rel_guid,
        RelatingStructure=storey,
        RelatedElements=None,
    )

    c = relation_multimap.census(model)

    void_rows = [r for r in c["records"] if r["family"] == "void"]
    assert len(void_rows) == 1
    assert void_rows[0]["source_id"] == opening_guid
    assert void_rows[0]["endpoint_id"] is None

    contain_rows = [r for r in c["records"] if r["family"] == "contain"]
    assert len(contain_rows) == 1
    assert contain_rows[0]["source_id"] is None
    assert contain_rows[0]["endpoint_id"] == storey_guid

    assert len(c["diagnostics"]) == 0

    s_void = relation_multimap.singletons(c["maps"], "void")
    assert opening_guid not in s_void
    s_contain = relation_multimap.singletons(c["maps"], "contain")
    assert None not in s_contain
