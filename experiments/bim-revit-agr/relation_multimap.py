"""IFC relation multi-map census helper.

new-case: report-only synthetic IFC void/fill/contain relation census, no production adapter policy.

Extracts void, fill, and containment relations with deterministic ordering,
deduplication, and cardinality diagnostic detection.
"""

from __future__ import annotations

import json
from typing import Any


def _get_id(entity: Any) -> str | None:
    if entity is None:
        return None
    if isinstance(entity, str):
        return entity
    return getattr(entity, "GlobalId", None)


def _null_safe_sort_key(value: Any) -> tuple[int, str]:
    if value is None:
        return (1, "")
    return (0, str(value))


def _record_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _null_safe_sort_key(row.get("family")),
        _null_safe_sort_key(row.get("relation_id")),
        _null_safe_sort_key(row.get("source_id")),
        _null_safe_sort_key(row.get("endpoint_id")),
    )


def census(ifc: Any, reverse: bool = False) -> dict[str, Any]:
    """Census IFC relations for void, fill, and containment families.

    API census(ifc, reverse=False) returns dict with keys: 'records', 'maps', 'diagnostics'.
    """
    raw_rows: list[dict[str, Any]] = []

    # 1. Enumerate void: IfcRelVoidsElement
    # standard: source RelatedOpeningElement, endpoint RelatingBuildingElement
    void_rels = list(ifc.by_type("IfcRelVoidsElement"))
    if reverse:
        void_rels.reverse()
    for rel in void_rels:
        rel_id = _get_id(rel)
        opening = getattr(rel, "RelatedOpeningElement", None)
        building = getattr(rel, "RelatingBuildingElement", None)
        raw_rows.append({
            "family": "void",
            "relation_id": rel_id,
            "source_id": _get_id(opening),
            "endpoint_id": _get_id(building),
        })

    # 2. Enumerate fill: IfcRelFillsElement
    # standard: source RelatingOpeningElement, endpoint RelatedBuildingElement
    fill_rels = list(ifc.by_type("IfcRelFillsElement"))
    if reverse:
        fill_rels.reverse()
    for rel in fill_rels:
        rel_id = _get_id(rel)
        opening = getattr(rel, "RelatingOpeningElement", None)
        building = getattr(rel, "RelatedBuildingElement", None)
        raw_rows.append({
            "family": "fill",
            "relation_id": rel_id,
            "source_id": _get_id(opening),
            "endpoint_id": _get_id(building),
        })

    # 3. Enumerate contain: IfcRelContainedInSpatialStructure
    # standard: expand RelatedElements source, endpoint RelatingStructure
    contain_rels = list(ifc.by_type("IfcRelContainedInSpatialStructure"))
    if reverse:
        contain_rels.reverse()
    for rel in contain_rels:
        rel_id = _get_id(rel)
        structure = getattr(rel, "RelatingStructure", None)
        elements = getattr(rel, "RelatedElements", None)
        if elements:
            elems = list(elements)
            if reverse:
                elems.reverse()
            for el in elems:
                raw_rows.append({
                    "family": "contain",
                    "relation_id": rel_id,
                    "source_id": _get_id(el),
                    "endpoint_id": _get_id(structure),
                })
        else:
            raw_rows.append({
                "family": "contain",
                "relation_id": rel_id,
                "source_id": None,
                "endpoint_id": _get_id(structure),
            })

    # Deterministic sort null-safe for raw records
    records = sorted(raw_rows, key=_record_sort_key)

    maps: dict[str, dict[str, list[str]]] = {
        "void": {},
        "fill": {},
        "contain": {},
    }
    diagnostics: list[dict[str, Any]] = []

    for family in ("void", "fill", "contain"):
        family_rows = [r for r in records if r.get("family") == family]
        by_source: dict[str, list[dict[str, Any]]] = {}
        for r in family_rows:
            src = r.get("source_id")
            if src is not None:
                if src not in by_source:
                    by_source[src] = []
                by_source[src].append(r)

        for src in sorted(by_source.keys()):
            rows = by_source[src]
            distinct_endpoints = sorted({r["endpoint_id"] for r in rows if r.get("endpoint_id") is not None})
            maps[family][src] = distinct_endpoints

            if len(distinct_endpoints) > 1:
                relation_ids = sorted({r["relation_id"] for r in rows if r.get("relation_id") is not None})
                diagnostics.append({
                    "family": family,
                    "source_id": src,
                    "endpoint_ids": distinct_endpoints,
                    "relation_ids": relation_ids,
                    "kind": "cardinality",
                    "status": "unresolved",
                    "selected_endpoint": None,
                })

    diagnostics.sort(key=lambda d: (_null_safe_sort_key(d["family"]), _null_safe_sort_key(d["source_id"])))

    return {
        "records": records,
        "maps": maps,
        "diagnostics": diagnostics,
    }


def singletons(maps_or_census: dict[str, Any], family: str) -> dict[str, str | None]:
    """Return singleton endpoint dictionary for a relation family.

    Unambiguous singleton chosen; conflicting source present in dict with value None;
    absent stays absent.
    """
    if "maps" in maps_or_census and isinstance(maps_or_census["maps"], dict):
        maps = maps_or_census["maps"]
    else:
        maps = maps_or_census

    endpoint_map = maps.get(family, {})
    out: dict[str, str | None] = {}
    for src, endpoints in endpoint_map.items():
        if len(endpoints) == 1:
            out[src] = endpoints[0]
        elif len(endpoints) > 1:
            out[src] = None
    return out


def canonical(c: dict[str, Any]) -> str:
    """Return deterministically sorted JSON string for census dictionary."""
    return json.dumps(c, sort_keys=True, separators=(",", ":"))
