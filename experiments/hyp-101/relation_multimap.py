"""Report-only multimap of IFC void, fill and containment relations."""

from __future__ import annotations

import json

# class, source attribute, endpoint attribute. Containment expands RelatedElements.
FAMILIES = {
    "void": ("IfcRelVoidsElement", "RelatedOpeningElement", "RelatingBuildingElement"),
    "fill": ("IfcRelFillsElement", "RelatingOpeningElement", "RelatedBuildingElement"),
    "contain": ("IfcRelContainedInSpatialStructure", "RelatedElements", "RelatingStructure"),
}


def _blank(value):
    return "" if value is None else value


def _gid(entity):
    if entity is None:
        return None
    return getattr(entity, "GlobalId", None)


def _records(ifc, reverse):
    found = []
    for family, (cls, source_attr, endpoint_attr) in FAMILIES.items():
        relations = list(ifc.by_type(cls))
        if reverse:
            relations.reverse()
        for rel in relations:
            relation_id = getattr(rel, "GlobalId", None)
            endpoint_id = _gid(getattr(rel, endpoint_attr, None))
            if source_attr == "RelatedElements":
                elements = list(getattr(rel, source_attr, None) or [])
                if reverse:
                    elements.reverse()
                sources = elements or [None]
            else:
                sources = [getattr(rel, source_attr, None)]
            for source in sources:
                found.append(
                    {
                        "family": family,
                        "relation_id": relation_id,
                        "source_id": _gid(source),
                        "endpoint_id": endpoint_id,
                    }
                )
    found.sort(key=lambda row: (_blank(row["family"]), _blank(row["source_id"]), _blank(row["endpoint_id"]), _blank(row["relation_id"])))
    return found


def _maps(records):
    maps = {family: {} for family in FAMILIES}
    for row in records:
        source_id = row["source_id"]
        if source_id is None:
            continue
        bucket = maps[row["family"]].setdefault(source_id, [])
        if row["endpoint_id"] not in bucket:
            bucket.append(row["endpoint_id"])
    for family in maps.values():
        for source_id, endpoints in family.items():
            family[source_id] = sorted(endpoints, key=_blank)
    return maps


def _diagnostics(records):
    grouped = {}
    for row in records:
        grouped.setdefault((row["family"], row["source_id"]), []).append(row)
    found = []
    for (family, source_id), rows in grouped.items():
        endpoints = sorted({row["endpoint_id"] for row in rows if row["endpoint_id"] is not None}, key=_blank)
        if len(endpoints) < 2:
            continue
        relation_ids = sorted({row["relation_id"] for row in rows if row["endpoint_id"] is not None}, key=_blank)
        found.append(
            {
                "kind": "cardinality",
                "family": family,
                "source_id": source_id,
                "endpoint_ids": endpoints,
                "relation_ids": relation_ids,
                "status": "unresolved",
                "selected_endpoint": None,
            }
        )
    found.sort(key=lambda row: (_blank(row["family"]), _blank(row["source_id"])))
    return found


def census(ifc, reverse=False) -> dict:
    records = _records(ifc, reverse)
    return {"records": records, "maps": _maps(records), "diagnostics": _diagnostics(records)}


def canonical(c) -> str:
    return json.dumps(c, sort_keys=True, separators=(",", ":"))
