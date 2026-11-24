"""Compare view-scoped Revit material IDs with used FBX materials (offline readback)."""
import json
import re
from collections import Counter
from pathlib import Path
from typing import Annotated

from pydantic import Field, StrictInt, StringConstraints, TypeAdapter

from dt_ai.intake.model import Part
from dt_ai.parts.readers.fbx import FORMAT

EVIDENCE = "revit-materials.json"
Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class Element(Part):
    id: Text
    family: Text
    material_ids: list[Text]
    meshes: list[Text]


class Export(Part):
    source: Text
    source_sha256: Text
    export: Text
    readback: Text
    elements: list[Element] = Field(min_length=1)


_EXPORTS = TypeAdapter(Annotated[list[Export], Field(min_length=1)])
_FACE_COUNTS = TypeAdapter(dict[str, StrictInt])


def _used_materials(obj):
    """Count only named materials on faces, not the slots merely declared by the mesh."""
    slots = obj.get("material_slots")
    counts = _FACE_COUNTS.validate_python(obj.get("face_material_counts"))
    polygons = obj.get("polygons")
    if (not isinstance(slots, list) or any(s is not None and not isinstance(s, str) for s in slots)
            or type(polygons) is not int or polygons < 1 or sum(counts.values()) != polygons
            or any(n <= 0 or not re.fullmatch(r"0|[1-9][0-9]*", i) for i, n in counts.items())):
        raise ValueError("invalid nonempty mesh face/material inventory")
    # Blender assigns index 0 to faces even on a mesh with no material slots.
    if not slots and counts.keys() == {"0"}:
        return set()
    indices = [int(i) for i in counts]
    if any(i >= len(slots) for i in indices):
        raise ValueError("face references a nonexistent material slot")
    return {slots[i] for i in indices if slots[i]}


def _compare(folder, entry, source, export, result):
    if not source or source.format != "rvt" or not source.opened or source.sha256 != entry.source_sha256:
        raise ValueError("expected an opened RVT with matching source_sha256 in sources.json")
    if not export or export.format != "fbx" or not export.opened or not export.sha256:
        raise ValueError("expected an opened FBX with sha256 in sources.json")
    basename = Path(entry.readback)
    path = (folder / basename).resolve()
    if basename.name != entry.readback or path.parent != folder.resolve():
        raise ValueError("readback must name a JSON file inside the intake folder")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("format") != FORMAT or "error" in data
            or not isinstance(data.get("source"), dict) or data["source"].get("sha256") != export.sha256
            or not isinstance(data.get("objects"), list)):
        raise ValueError("expected successful fbx_structure/1 with sha256 matching sources.json")
    meshes = {}
    names = set()
    for obj in data["objects"]:
        if (not isinstance(obj, dict) or not isinstance(obj.get("name"), str) or not obj["name"]
                or obj["name"] in names or not isinstance(obj.get("type"), str) or not obj["type"]):
            raise ValueError("invalid or duplicate FBX object identity")
        names.add(obj["name"])
        if obj["type"] == "MESH" and not (type(obj.get("polygons")) is int and obj["polygons"] == 0):
            meshes[obj["name"]] = obj
    if not meshes:
        raise ValueError("readback has no nonempty meshes")
    owners = Counter(name for element in entry.elements for name in element.meshes)
    ids = Counter(element.id for element in entry.elements)
    result["unmapped_meshes"] = sorted(meshes.keys() - owners.keys())
    for element in entry.elements:
        row = {"id": element.id, "family": element.family, "source_count": len(set(element.material_ids)),
               "export_count": None, "status": "not_run"}
        invalid = [name for name in element.meshes if name not in meshes or owners[name] != 1]
        if ids[element.id] != 1:
            row["reason"] = "duplicate Revit element ID"
        elif not element.meshes or invalid:
            row["reason"] = f"missing or ambiguous mesh mapping: {invalid!r}"
        else:
            try:
                used = set().union(*(_used_materials(meshes[name]) for name in element.meshes))
            except ValueError as exc:
                row["reason"] = str(exc)
            else:
                row["export_count"] = len(used)
                row["status"] = "match" if row["source_count"] == row["export_count"] else "mismatch"
        if row["status"] != "match":
            result["findings"].append(row)
    statuses = {row["status"] for row in result["findings"]}
    result["status"] = ("mismatch" if "mismatch" in statuses else "not_run"
                        if statuses or result["unmapped_meshes"] else "match")
    result["elements_compared"] = len(entry.elements) - sum(
        row["status"] == "not_run" for row in result["findings"])


def material_count_report(folder, by_path):
    """Return export-level diagnostics. Missing evidence is visible, never counted as a match."""
    candidates = {p for p, item in by_path.items() if item.format == "fbx"} if any(
        item.format == "rvt" for item in by_path.values()) else set()
    path = folder / EVIDENCE
    try:
        entries = _EXPORTS.validate_json(path.read_bytes())
    except FileNotFoundError:
        return [{"export": p, "status": "not_run", "reason": f"no {EVIDENCE}"} for p in sorted(candidates)]
    except (OSError, ValueError) as exc:
        return [{"status": "not_run", "reason": f"{EVIDENCE}: {exc}"}]
    exports = Counter(e.export for e in entries)
    results = []
    for entry in entries:
        result = {"source": entry.source, "export": entry.export, "readback": entry.readback,
                  "status": "not_run", "findings": []}
        try:
            if exports[entry.export] != 1:
                raise ValueError("duplicate evidence for this FBX")
            _compare(folder, entry, by_path.get(entry.source), by_path.get(entry.export), result)
        except (OSError, ValueError) as exc:
            result["reason"] = str(exc)
        results.append(result)
    results.extend({"export": p, "status": "not_run", "reason": f"no entry in {EVIDENCE}"}
                   for p in sorted(candidates - exports.keys()))
    return results
