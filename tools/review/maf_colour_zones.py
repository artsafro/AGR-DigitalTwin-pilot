"""Map Vatutino showcase MAF faces onto approved v005 material IDs (#889).

The geometry is not rebuilt. Assignment only attaches an ID to each existing face.
IDs are the pilot MAF list (1..31). A face ID >= 1001 is a UDIM tile, not a material
ID, and is an error [D030]. An unknown position, zone or material is named in the
error. Nothing is filled in from the first catalogue entry.

Colours recorded by ``rows_from_set`` are the v005 target of the ID the existing
atlas slot already uses. They are not measurements from a passport photo.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

UDIM_AS_MATERIAL_ID = 1001

# Existing site-atlas slot -> approved v005 key. No other slot is accepted.
ATLAS_TO_ID = {
    "steel_ral7047": "paint_ral7047",
    "larch_light_oak": "wood_light",
    "hpl_satin_wood": "wood_light",
    "rope_pp": "rope_pp",
}

COLOUR_SOURCE = {
    "steel_ral7047": "schedule RAL 7047; v005 target, photo not measured",
    "larch_light_oak": "schedule finish light oak; v005 target, photo not measured",
    "hpl_satin_wood": "schedule HPL satin wood merged to wood_light; v005 target, photo not measured",
    "rope_pp": "schedule polypropylene rope, no RAL; v005 target, photo not measured",
}


class ZoneError(Exception):
    """Fail closed: no table, no rewritten mesh."""


def _key(path: Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def assert_distinct_paths(paths: dict) -> None:
    """No two of the named paths are the same file. Checked before any write."""
    seen = {}
    for role, path in paths.items():
        if path is None:
            continue
        token = _key(Path(path))
        if token in seen:
            raise ZoneError(f"output path is the same file as an input: {role} and {seen[token]} -> {path}")
        seen[token] = role


def _finite_int(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ZoneError(f"{what}: not a finite number: {value!r}")
    if isinstance(value, float) and not value.is_integer():
        raise ZoneError(f"{what}: not a finite integer: {value!r}")
    return int(value)


def _hex(value, what: str) -> str:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise ZoneError(f"{what}: colour {value!r} is not #RRGGBB")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ZoneError(f"{what}: colour {value!r} is not #RRGGBB") from exc
    return value.upper()


def load_id_catalogue(doc: dict) -> dict:
    """key -> {id, key, target, ral, name}. Rejects an empty list, duplicate keys and ID >= 1001."""
    if not isinstance(doc, dict):
        raise ZoneError("material id catalogue: not an object")
    rows = doc.get("ids")
    if not isinstance(rows, list) or not rows:
        raise ZoneError("material id catalogue: empty")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or "key" not in row:
            raise ZoneError(f"material id catalogue: row missing key: {row!r}")
        key = row["key"]
        if not isinstance(key, str) or not key.strip():
            raise ZoneError(f"material id catalogue: blank key {key!r}")
        if key in out:
            raise ZoneError(f"material id catalogue: duplicate key {key}")
        if "id" not in row:
            raise ZoneError(f"{key}: material id missing")
        mid = _finite_int(row["id"], key)
        if mid >= UDIM_AS_MATERIAL_ID or mid < 1:
            raise ZoneError(f"{key}: material id {mid} is outside 1..{UDIM_AS_MATERIAL_ID - 1}")
        name = row.get("name_ru") or row.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ZoneError(f"{key}: name missing")
        ral = row.get("ral")
        if ral is not None and not isinstance(ral, str):
            raise ZoneError(f"{key}: ral {ral!r} is not a string")
        out[key] = {"id": mid, "key": key, "target": _hex(row.get("target"), key),
                    "ral": ral, "name": name.strip()}
    return out


def _require_id(id_key, catalogue: dict) -> dict:
    if not isinstance(id_key, str) or id_key not in catalogue:
        raise ZoneError(f"unmapped material: {id_key}")
    entry = catalogue[id_key]
    mid = entry["id"]
    if not isinstance(mid, int) or isinstance(mid, bool) or mid >= UDIM_AS_MATERIAL_ID or mid < 1:
        raise ZoneError(f"{id_key}: material id {mid} is outside 1..{UDIM_AS_MATERIAL_ID - 1}")
    return entry


def assign_face_ids(face_zones, zone_keys: dict, catalogue: dict) -> list:
    """One v005 ID per input face. Unknown zone or material is an error naming it."""
    if not isinstance(face_zones, (list, tuple)) or not face_zones:
        raise ZoneError("empty face list")
    if not isinstance(zone_keys, dict) or not zone_keys:
        raise ZoneError("empty zone map")
    ids = []
    for zone in face_zones:
        if not isinstance(zone, str) or zone not in zone_keys:
            raise ZoneError(f"unmapped zone: {zone}")
        ids.append(_require_id(zone_keys[zone], catalogue)["id"])
    if len(ids) != len(face_zones):
        raise ZoneError("dropped faces")
    return ids


def apply_zone_ids(mesh: dict, zone_keys: dict, catalogue: dict) -> dict:
    """Copy vertices and faces unchanged and attach material IDs. Drops nothing on success."""
    if not isinstance(mesh, dict) or "vertices" not in mesh or "faces" not in mesh:
        raise ZoneError("mesh is missing vertices or faces")
    vertices = list(mesh["vertices"])
    faces = list(mesh["faces"])
    ids = assign_face_ids(faces, zone_keys, catalogue)
    return {"vertices": vertices, "faces": faces, "material_ids": ids, "dropped": []}


def _zone_record(zone_name: str, id_key: str, colour_source: str, catalogue: dict) -> dict:
    if not isinstance(zone_name, str) or not zone_name.strip():
        raise ZoneError(f"blank zone for material {id_key!r}")
    if not isinstance(colour_source, str) or not colour_source.strip():
        raise ZoneError(f"{zone_name}: colour source missing")
    entry = _require_id(id_key, catalogue)
    return {"zone": zone_name, "id_key": id_key, "id": entry["id"], "colour": entry["target"],
            "ral": entry["ral"], "name": entry["name"], "colour_source": colour_source.strip()}


def _profiles(set_id: str, zones: list, profiles: dict) -> dict:
    if not isinstance(profiles, dict) or set(profiles) != {"npm", "vpm"}:
        raise ZoneError(f"{set_id}: profiles must be npm and vpm")
    names = [z["zone"] for z in zones]
    if len(names) != len(set(names)):
        raise ZoneError(f"{set_id}: duplicate zone")
    out = {}
    for prof, raw in profiles.items():
        if not isinstance(raw, dict):
            raise ZoneError(f"{set_id} {prof}: profile is not an object")
        for field in ("vertices_before", "faces_before", "vertices_after", "faces_after", "zone_faces"):
            if field not in raw:
                raise ZoneError(f"{set_id} {prof}: {field} missing")
        vertices_before = _finite_int(raw["vertices_before"], f"{set_id} {prof} vertices_before")
        faces_before = _finite_int(raw["faces_before"], f"{set_id} {prof} faces_before")
        vertices_after = _finite_int(raw["vertices_after"], f"{set_id} {prof} vertices_after")
        faces_after = _finite_int(raw["faces_after"], f"{set_id} {prof} faces_after")
        if min(vertices_before, faces_before, vertices_after, faces_after) <= 0:
            raise ZoneError(f"{set_id} {prof}: empty face or vertex count")
        if vertices_before != vertices_after:
            raise ZoneError(f"{set_id} {prof}: vertices {vertices_before} != {vertices_after}")
        if faces_before != faces_after:
            raise ZoneError(f"{set_id} {prof}: faces {faces_before} != {faces_after}")
        zone_faces = raw["zone_faces"]
        if not isinstance(zone_faces, dict):
            raise ZoneError(f"{set_id} {prof}: zone_faces is not an object")
        missing = [name for name in names if name not in zone_faces]
        extra = [name for name in zone_faces if name not in names]
        if missing or extra:
            raise ZoneError(f"{set_id} {prof}: unmapped zone: {missing or extra}")
        counts = {}
        for name in names:
            count = _finite_int(zone_faces[name], f"{set_id} {prof} {name}")
            if count <= 0:
                raise ZoneError(f"{set_id} {prof}: zone {name} has no faces")
            counts[name] = count
        if sum(counts.values()) != faces_before:
            raise ZoneError(f"{set_id} {prof}: zone faces {sum(counts.values())} != faces {faces_before}")
        out[prof] = {"vertices_before": vertices_before, "faces_before": faces_before,
                     "vertices_after": vertices_after, "faces_after": faces_after,
                     "zone_faces": counts}
    return out


def compile_zones(required_ids, rows, catalogue: dict) -> dict:
    """Every required position is in ``rows`` and every zone resolves to one ID below 1001."""
    if not isinstance(required_ids, (list, tuple)) or not required_ids or not rows:
        raise ZoneError("empty position list")
    if not isinstance(catalogue, dict) or not catalogue:
        raise ZoneError("empty material id catalogue")
    got = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("set_id"):
            raise ZoneError(f"row without set_id: {row!r}")
        got.append(row["set_id"])
    dup = sorted({i for i in got if got.count(i) > 1})
    if dup:
        raise ZoneError(f"duplicate set ids: {dup}")
    missing = [i for i in required_ids if i not in got]
    if missing:
        raise ZoneError(f"unmapped position: {', '.join(missing)}")
    extra = [i for i in got if i not in required_ids]
    if extra:
        raise ZoneError(f"unmapped position: {', '.join(extra)}")
    by = {row["set_id"]: row for row in rows}
    positions = []
    for set_id in required_ids:
        row = by[set_id]
        raw_zones = row.get("zones")
        if not isinstance(raw_zones, list) or not raw_zones:
            raise ZoneError(f"{set_id}: empty zone list")
        zones = [_zone_record(z.get("zone"), z.get("id_key"), z.get("colour_source"), catalogue)
                 for z in raw_zones]
        if any(z["id"] >= UDIM_AS_MATERIAL_ID for z in zones):
            raise ZoneError(f"{set_id}: material id >= {UDIM_AS_MATERIAL_ID}")
        profiles = _profiles(set_id, zones, row.get("profiles"))
        item = {"set_id": set_id, "zones": zones, "profiles": profiles}
        for field in ("name", "catalogue_id", "schedule", "material_reason", "split_note"):
            if field in row:
                item[field] = row[field]
        positions.append(item)
    return {
        "ok": True,
        "accepted": False,
        "photo_status": "missing",
        "geometry_rewrite": False,
        "reason": "passport photos are not on disk; colours are v005 targets of the existing atlas slots, not photo measurements; meshes were not rewritten",
        "positions": positions,
    }


def rows_from_set(set_report: dict, catalogue: dict, counts: dict) -> list:
    """One row per showcase position from the recorded atlas slots. No new zone is invented."""
    positions = set_report.get("positions") if isinstance(set_report, dict) else None
    if not isinstance(positions, list) or not positions:
        raise ZoneError("set report has no positions")
    if not isinstance(counts, dict) or not counts:
        raise ZoneError("empty geometry counts")
    rows = []
    for pos in positions:
        set_id = pos.get("set_id")
        if not isinstance(set_id, str) or not set_id:
            raise ZoneError(f"set position without set_id: {pos!r}")
        if set_id not in counts:
            raise ZoneError(f"unmapped position: {set_id}")
        used = {}
        for prof in ("npm", "vpm"):
            uv = pos[prof]["uv_slots"]
            per = uv.get("per_material") or {}
            if not isinstance(per, dict) or not per:
                raise ZoneError(f"{set_id} {prof}: empty material slots")
            faces = {}
            for name, info in per.items():
                count = info.get("faces") if isinstance(info, dict) else None
                count = _finite_int(count, f"{set_id} {prof} {name}")
                if count < 0:
                    raise ZoneError(f"{set_id} {prof}: {name} face count {count}")
                if count == 0:
                    continue
                if name not in ATLAS_TO_ID:
                    raise ZoneError(f"unmapped material: {name}")
                faces[name] = count
            if not faces:
                raise ZoneError(f"{set_id} {prof}: empty material slots")
            if sum(faces.values()) != uv.get("faces"):
                raise ZoneError(f"{set_id} {prof}: zone faces {sum(faces.values())} != faces {uv.get('faces')}")
            measured = counts[set_id].get(prof) if isinstance(counts.get(set_id), dict) else None
            if not isinstance(measured, dict):
                raise ZoneError(f"{set_id} {prof}: geometry counts missing")
            vertices = _finite_int(measured.get("vertices"), f"{set_id} {prof} vertices")
            face_count = _finite_int(measured.get("faces"), f"{set_id} {prof} faces")
            if face_count != uv.get("faces"):
                raise ZoneError(f"{set_id} {prof}: counted faces {face_count} != recorded faces {uv.get('faces')}")
            used[prof] = faces
            counts[set_id][prof] = {"vertices": vertices, "faces": face_count, "zone_faces": faces}
        names = sorted(set(used["npm"]) | set(used["vpm"]))
        zones = [{"zone": name, "id_key": ATLAS_TO_ID[name], "colour_source": COLOUR_SOURCE[name]}
                 for name in names]
        note = None
        if len(names) == 1:
            note = ("source mesh has one atlas material; passport photo not on disk; "
                    "no further colour zone invented")
        profiles = {}
        for prof in ("npm", "vpm"):
            block = counts[set_id][prof]
            zone_faces = {name: block["zone_faces"].get(name, 0) for name in names}
            profiles[prof] = {
                "vertices_before": block["vertices"], "faces_before": block["faces"],
                "vertices_after": block["vertices"], "faces_after": block["faces"],
                "zone_faces": zone_faces,
            }
        rows.append({
            "set_id": set_id,
            "catalogue_id": pos.get("catalogue_id"),
            "schedule": pos.get("schedule"),
            "name": pos.get("name"),
            "material_reason": pos.get("material_reason"),
            "split_note": note,
            "zones": zones,
            "profiles": profiles,
        })
    return rows


def render_md(report: dict) -> str:
    lines = [
        "# Vatutino showcase MAF colour zones (#889)",
        "",
        "Geometry is the accepted v005-set mesh. Vertex and face counts below are one read of that mesh;",
        "before and after are equal because no mesh was written. Colours are the v005 target of the atlas",
        "slot the position already uses. Passport photos for these 13 positions were not on disk, so no",
        "colour was measured from a photo and no extra zone was added to a single-material mesh.",
        "",
        f"Photo status: {report.get('photo_status')}. Accepted: {report.get('accepted')}.",
        "",
        "| position | zone | ID | key | colour | faces npm | faces vpm | vertices npm | vertices vpm | colour source |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for pos in report["positions"]:
        npm, vpm = pos["profiles"]["npm"], pos["profiles"]["vpm"]
        for zone in pos["zones"]:
            lines.append(
                f"| {pos['set_id']} | {zone['zone']} | {zone['id']} | {zone['id_key']} | {zone['colour']} "
                f"| {npm['zone_faces'][zone['zone']]} | {vpm['zone_faces'][zone['zone']]} "
                f"| {npm['vertices_before']} | {vpm['vertices_before']} | {zone['colour_source']} |"
            )
        if pos.get("split_note"):
            lines.append(f"| {pos['set_id']} | — | — | — | — | — | — | — | — | {pos['split_note']} |")
    lines += ["", "Positions with one zone were left as the recorded atlas slot. A passport photo is required before splitting them.", ""]
    return "\n".join(lines)


def _load(path: Path, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ZoneError(f"{what}: {exc}") from exc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compile the Vatutino MAF colour-zone table (#889)")
    ap.add_argument("--set", required=True)
    ap.add_argument("--ids", required=True)
    ap.add_argument("--counts", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--required", nargs="*", default=None)
    args = ap.parse_args(argv)
    out_json, out_md = Path(args.out_json), Path(args.out_md)
    try:
        assert_distinct_paths({
            "set": args.set, "ids": args.ids, "counts": args.counts,
            "out-json": out_json, "out-md": out_md,
        })
        catalogue = load_id_catalogue(_load(args.ids, "id catalogue"))
        report_in = _load(args.set, "set report")
        counts = _load(args.counts, "geometry counts")
        rows = rows_from_set(report_in, catalogue, counts)
        required = list(args.required) if args.required else [row["set_id"] for row in rows]
        report = compile_zones(required, rows, catalogue)
        text = json.dumps(report, ensure_ascii=False, indent=1)
        md = render_md(report)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(text + "\n", encoding="utf-8")
        out_md.write_text(md, encoding="utf-8")
        print(text)
        return 0
    except ZoneError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
