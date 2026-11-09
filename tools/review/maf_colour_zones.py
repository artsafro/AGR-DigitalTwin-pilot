"""new-case: MAF colour-zone table builder. Map Vatutino showcase MAF faces onto approved v005 material IDs (#889).

The geometry is not rebuilt. Assignment only attaches an ID to each existing face.
IDs are the pilot MAF list (1..31). A face ID >= 1001 is a UDIM tile, not a material
ID, and is an error [D030]. An unknown position, zone or material is named in the
error. Nothing is filled in from the first catalogue entry.

Colour source: schedule finishes, no passport photo (issue #889 card comment). A schedule RAL is that paint.
A named finish with no number (light oak, HPL satin wood, polypropylene rope) keeps
the existing atlas-slot hex and is marked ``colour assumed``. The vendor images in
``C:/x/vatutino-maf/v001/candidates_part*.jpg`` and ``candidates_sheet.jpg`` are
library viewport colours, not product photos, so they are not measured.

Face groups (single-material meshes): faces that share an edge stay in one group
while the dihedral angle is at most 40 degrees (the MAF smoothing angle). A sharper
edge is a boundary even when the parts are one welded mesh. Each group is classified
from the sorted extents ``t <= u <= v`` of its vertices, in metres:

- ``fastener`` when ``v < 0.06``
- ``slab`` when ``t <= 0.045`` and ``u >= 0.08`` and ``u >= 3t`` (a panel)
- ``tube`` when ``u <= 0.12`` and ``v >= 0.15`` and ``v >= 2.5u`` (a rail or leg)
- ``shell`` otherwise

``POSITION_POLICY`` maps those kinds to v005 keys per position. A product whose
schedule finish is only RAL 7047 (the steel urn, the tree grate) maps every kind
to that paint, so the groups stay one colour. When fastener faces exceed
``fastener_max_share`` they fold into ``shell`` so a fragmented panel is not
reported as plastic caps.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

UDIM_AS_MATERIAL_ID = 1001

# Existing site-atlas slot -> approved v006 key, zone name and stated colour.
# No other slot is accepted. ``colour assumed`` means the schedule names the
# finish but not a number, and the vendor sheet was not measured.
FINISH = {
    "steel_ral7047": {
        "id_key": "paint_ral7047", "zone": "frame", "colour": "#D0D0D0",
        "colour_source": "schedule RAL 7047",
    },
    "larch_light_oak": {
        "id_key": "wood_light", "zone": "boards", "colour": "#C49A6C",
        "colour_source": ("schedule finish light oak; no RAL; vendor candidates_part*.jpg and "
                          "candidates_sheet.jpg are library viewport colours, not a finish measurement; "
                          "colour assumed; atlas slot larch_light_oak #C49A6C"),
    },
    # D229 (#993): HPL has its own ID 32; ID 14 stays larch / light oak.
    "hpl_satin_wood": {
        "id_key": "wood_hpl_satin", "zone": "hpl", "colour": "#B4825A",
        "colour_source": ("schedule HPL satin wood; no RAL; vendor images are library viewport colours, "
                          "not a finish measurement; colour assumed; atlas slot hpl_satin_wood #B4825A"),
    },
    "rope_pp": {
        "id_key": "rope_pp", "zone": "rope", "colour": "#7A7A7A",
        "colour_source": ("schedule polypropylene rope; no RAL; colour assumed; atlas slot rope_pp #7A7A7A"),
    },
}
ATLAS_TO_ID = {slot: row["id_key"] for slot, row in FINISH.items()}
COLOUR_SOURCE = {slot: row["colour_source"] for slot, row in FINISH.items()}

SPLIT_ANGLE_DEG = 40.0
# Single-material meshes only. Kinds that the schedule does not split stay on one key.
POSITION_POLICY = {
    "VAT_MAF_T3510_02": {"slab": "paint_ral7047", "shell": "paint_ral7047",
                         "tube": "paint_ral7047", "fastener": "paint_ral7047"},
    "VAT_MAF_T3510_07": {"slab": "wood_light", "shell": "wood_light",
                         "tube": "paint_ral7047", "fastener": "paint_ral7047"},
    "VAT_MAF_T3510_12": {"slab": "wood_light", "shell": "paint_ral7047",
                         "tube": "paint_ral7047", "fastener": "cap_black"},
    # ДП 090: schedule is steel RAL 7047 + larch. groups.json "frame" is shell+tube
    # (npm 957+240). Slabs stay larch. A large fastener share folds into shell.
    "VAT_MAF_T3510_16": {"slab": "wood_light", "shell": "paint_ral7047",
                         "tube": "paint_ral7047", "fastener": "cap_black"},
    "VAT_MAF_T3510_29": {"slab": "wood_light", "shell": "wood_light",
                         "tube": "paint_ral7047", "fastener": "cap_black"},
    "VAT_MAF_T3510_31": {"slab": "wood_light", "shell": "wood_light",
                         "tube": "paint_ral7047", "fastener": "paint_ral7047"},
    "VAT_MAF_T3510_32": {"slab": "paint_ral7047", "shell": "paint_ral7047",
                         "tube": "paint_ral7047", "fastener": "paint_ral7047"},
}
ZONE_OF_KEY = {
    "wood_light": "boards", "paint_ral7047": "frame", "cap_black": "fasteners", "rope_pp": "rope",
    "wood_hpl_satin": "hpl",
}
# Split keys use the atlas slot hex of their key. One ID has one colour across the set (#993).
KEY_SLOT = {"wood_light": "larch_light_oak", "paint_ral7047": "steel_ral7047", "rope_pp": "rope_pp",
            "wood_hpl_satin": "hpl_satin_wood"}
CAP_SOURCE = "schedule polyamide caps; no RAL; colour assumed; v005 cap_black #303030"
# Finishes the schedule assigns to the showcase position. The AST boilerplate pastes
# "лиственница" onto the steel urn (*T3510/2); that position's record is steel only.
# The tree grate (*T3510/32) is "сталь RAL 7047" only. ДП 090 names steel and larch.
SCHEDULE_FINISHES = {
    "VAT_MAF_T3510_01": ("wood_light", "paint_ral7047"),
    "VAT_MAF_T3510_02": ("paint_ral7047",),
    "VAT_MAF_T3510_07": ("wood_light", "paint_ral7047"),
    "VAT_MAF_T3510_09": ("wood_light", "paint_ral7047"),
    "VAT_MAF_T3510_11": ("wood_light", "paint_ral7047"),
    "VAT_MAF_T3510_12": ("wood_light", "paint_ral7047", "cap_black"),
    "VAT_MAF_T3510_16": ("wood_light", "paint_ral7047"),
    "VAT_MAF_T3510_26": ("wood_hpl_satin", "paint_ral7047"),
    "VAT_MAF_T3510_27": ("wood_light", "paint_ral7047"),
    "VAT_MAF_T3510_28": ("rope_pp", "paint_ral7047"),
    "VAT_MAF_T3510_29": ("wood_light", "paint_ral7047", "cap_black"),
    "VAT_MAF_T3510_31": ("wood_light", "paint_ral7047"),
    "VAT_MAF_T3510_32": ("paint_ral7047",),
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


def _xyz(value, what: str):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ZoneError(f"{what}: expected 3 coordinates")
    out = []
    for coord in value:
        if isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord):
            raise ZoneError(f"{what}: not a finite number: {coord!r}")
        out.append(float(coord))
    return tuple(out)


def _unit(normal):
    if normal is None:
        return None
    length = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if length < 1e-12:
        return None
    return (normal[0] / length, normal[1] / length, normal[2] / length)


def _face_normal(vertices, face):
    nx = ny = nz = 0.0
    count = len(face)
    for i in range(count):
        x1, y1, z1 = vertices[face[i]]
        x2, y2, z2 = vertices[face[(i + 1) % count]]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return _unit((nx, ny, nz))


def _angle(a, b):
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.degrees(math.acos(dot))


def face_groups(vertices, faces, angle_deg=SPLIT_ANGLE_DEG) -> list:
    """Group id per face. Coplanar neighbours share a group; a sharp edge splits."""
    coords = [_xyz(v, "vertex") for v in vertices]
    if not isinstance(faces, (list, tuple)) or not faces:
        raise ZoneError("empty face list")
    polys = []
    for face in faces:
        if not isinstance(face, (list, tuple)) or len(face) < 3:
            raise ZoneError(f"face is not a polygon: {face!r}")
        idxs = []
        for index in face:
            if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= len(coords):
                raise ZoneError(f"face index out of range: {index!r}")
            idxs.append(index)
        polys.append(tuple(idxs))
    parent = list(range(len(polys)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    normals = [_face_normal(coords, face) for face in polys]
    edge_faces = {}
    for fi, face in enumerate(polys):
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            edge_faces.setdefault((a, b) if a < b else (b, a), []).append(fi)
    for pair in edge_faces.values():
        if len(pair) != 2:
            continue
        i, j = pair
        if normals[i] is None or normals[j] is None:
            continue
        if _angle(normals[i], normals[j]) <= angle_deg:
            a, b = find(i), find(j)
            if a != b:
                parent[a] = b
    roots = [find(i) for i in range(len(polys))]
    order = sorted(set(roots))
    renumber = {root: n for n, root in enumerate(order)}
    return [renumber[root] for root in roots]


def kind_from_dims(dims) -> str:
    t, u, v = sorted(float(x) for x in dims)
    if not math.isfinite(t) or not math.isfinite(v):
        raise ZoneError(f"group extents are not finite: {dims!r}")
    if v < 0.06:
        return "fastener"
    if t <= 0.045 and u >= 0.08 and u >= 3.0 * t:
        return "slab"
    if u <= 0.12 and v >= 0.15 and v >= 2.5 * max(u, 1e-9):
        return "tube"
    return "shell"


def _group_kind(vertices, faces, members) -> str:
    used = set()
    for index in members:
        used.update(faces[index])
    xs = [vertices[i][0] for i in used]
    ys = [vertices[i][1] for i in used]
    zs = [vertices[i][2] for i in used]
    return kind_from_dims((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))


def split_mesh(mesh: dict, policy: dict, catalogue: dict, fastener_max_share=None) -> dict:
    """Attach one v005 ID per existing face. Vertices and faces are copied, never rebuilt."""
    if not isinstance(mesh, dict) or "vertices" not in mesh or "faces" not in mesh:
        raise ZoneError("mesh is missing vertices or faces")
    if not isinstance(policy, dict) or not policy:
        raise ZoneError("empty zone map")
    vertices = [_xyz(v, "vertex") for v in mesh["vertices"]]
    if not vertices:
        raise ZoneError("empty vertex list")
    groups = face_groups(vertices, mesh["faces"])
    faces = list(mesh["faces"])
    if len(groups) != len(faces):
        raise ZoneError("dropped faces")
    members = {}
    for index, group in enumerate(groups):
        members.setdefault(group, []).append(index)
    ids = [None] * len(faces)
    kinds = [None] * len(faces)
    counts = {}
    for group, which in members.items():
        kind = _group_kind(vertices, faces, which)
        if kind not in policy:
            raise ZoneError(f"unmapped zone: {kind}")
        entry = _require_id(policy[kind], catalogue)
        counts[kind] = counts.get(kind, 0) + len(which)
        for index in which:
            ids[index] = entry["id"]
            kinds[index] = kind
    if fastener_max_share is not None:
        share = _finite_number(fastener_max_share, "fastener_max_share")
        if share < 0 or share > 1:
            raise ZoneError(f"fastener_max_share out of range: {share}")
        fastener_n = counts.get("fastener", 0)
        if fastener_n and fastener_n / len(faces) > share:
            if "shell" not in policy:
                raise ZoneError("unmapped zone: shell")
            shell_id = _require_id(policy["shell"], catalogue)["id"]
            for index, kind in enumerate(kinds):
                if kind == "fastener":
                    ids[index] = shell_id
            counts["shell"] = counts.get("shell", 0) + fastener_n
            del counts["fastener"]
    if any(i is None for i in ids) or len(ids) != len(faces):
        raise ZoneError("dropped faces")
    return {"vertices": vertices, "faces": faces, "material_ids": ids,
            "zone_faces": counts, "dropped": []}


def _finite_number(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ZoneError(f"{what}: not a finite number: {value!r}")
    return float(value)


def finish_colour(slot, catalogue: dict) -> dict:
    """Schedule RAL, or the atlas slot marked colour assumed. Unknown slots are named."""
    if not isinstance(slot, str) or slot not in FINISH:
        raise ZoneError(f"unmapped material: {slot}")
    row = FINISH[slot]
    entry = _require_id(row["id_key"], catalogue)
    return {"zone": row["zone"], "id_key": row["id_key"], "id": entry["id"],
            "colour": _hex(row["colour"], slot), "ral": entry["ral"], "name": entry["name"],
            "colour_source": row["colour_source"]}


def check_id_colours(records) -> dict:
    """``(where, id, colour)`` records across the whole site set -> {id: colour}.

    The site 512 set has one atlas cell per ID, so one ID with two colours loses one of them (#993).
    """
    seen, where_of = {}, {}
    for where, mid, colour in records:
        colour = _hex(colour, str(where))
        if mid in seen and seen[mid] != colour:
            raise ZoneError(f"material id {mid} has two colours: {seen[mid]} ({where_of[mid]}) and {colour} ({where})")
        seen.setdefault(mid, colour)
        where_of.setdefault(mid, where)
    if not seen:
        raise ZoneError("colour per id: empty set")
    return seen


def check_rows_id_colours(rows) -> dict:
    """Zone rows of every position (``set_id`` + ``zones``) -> one colour per ID or ZoneError."""
    return check_id_colours((row["set_id"], zone["id"], zone["colour"]) for row in rows for zone in row["zones"])


def zone_rows_for_keys(keys, catalogue: dict) -> list:
    """Face counts per v005 key, with the schedule colour of that key."""
    if not isinstance(keys, (list, tuple)) or not keys:
        raise ZoneError("empty face list")
    counts = {}
    for key in keys:
        if not isinstance(key, str):
            raise ZoneError(f"unmapped material: {key!r}")
        counts[key] = counts.get(key, 0) + 1
    rows = []
    for key, count in sorted(counts.items(), key=lambda item: ZONE_OF_KEY.get(item[0], item[0])):
        if key == "cap_black":
            entry = _require_id(key, catalogue)
            rows.append({"zone": "fasteners", "id_key": key, "id": entry["id"], "faces": count,
                         "colour": entry["target"], "colour_source": CAP_SOURCE})
            continue
        if key not in KEY_SLOT:
            raise ZoneError(f"unmapped material: {key}")
        fin = finish_colour(KEY_SLOT[key], catalogue)
        rows.append({**fin, "faces": count})
    names = [row["zone"] for row in rows]
    if len(names) != len(set(names)):
        raise ZoneError(f"duplicate zone: {names}")
    if sum(row["faces"] for row in rows) != len(keys):
        raise ZoneError("dropped faces")
    return rows


def aggregate_zones(material_ids, catalogue: dict) -> list:
    """One zone per v005 key, face counts summed. Empty input is an error."""
    if not isinstance(material_ids, (list, tuple)) or not material_ids:
        raise ZoneError("empty face list")
    by_id = {}
    for entry in catalogue.values():
        by_id.setdefault(entry["id"], entry)
    counts = {}
    for mid in material_ids:
        if isinstance(mid, bool) or not isinstance(mid, int) or mid not in by_id:
            raise ZoneError(f"unmapped material: {mid}")
        if mid >= UDIM_AS_MATERIAL_ID:
            raise ZoneError(f"material id {mid} is outside 1..{UDIM_AS_MATERIAL_ID - 1}")
        counts[mid] = counts.get(mid, 0) + 1
    zones = []
    for mid, count in sorted(counts.items()):
        entry = by_id[mid]
        zone = ZONE_OF_KEY.get(entry["key"])
        if zone is None:
            raise ZoneError(f"unmapped material: {entry['key']}")
        zones.append({"zone": zone, "id_key": entry["key"], "id": mid, "faces": count})
    names = [z["zone"] for z in zones]
    if len(names) != len(set(names)):
        raise ZoneError(f"duplicate zone: {names}")
    return zones


def _zone_record(zone_name: str, id_key: str, colour_source: str, catalogue: dict, colour=None) -> dict:
    if not isinstance(zone_name, str) or not zone_name.strip():
        raise ZoneError(f"blank zone for material {id_key!r}")
    if not isinstance(colour_source, str) or not colour_source.strip():
        raise ZoneError(f"{zone_name}: colour source missing")
    entry = _require_id(id_key, catalogue)
    stated = entry["target"] if colour is None else _hex(colour, zone_name)
    return {"zone": zone_name, "id_key": id_key, "id": entry["id"], "colour": stated,
            "ral": entry["ral"], "name": entry["name"], "colour_source": colour_source.strip()}


def guard_schedule_zones(set_id: str, finishes, zones: list) -> None:
    """A schedule that names two or more finishes cannot end as one zone."""
    if finishes is None:
        return
    if not isinstance(finishes, (list, tuple)) or not finishes:
        raise ZoneError(f"{set_id}: schedule finishes missing")
    named = []
    for key in finishes:
        if not isinstance(key, str) or key not in ZONE_OF_KEY:
            raise ZoneError(f"unmapped material: {key}")
        if key not in named:
            named.append(key)
    if len(named) >= 2 and len(zones) < 2:
        raise ZoneError(f"{set_id}: schedule names {len(named)} finishes but one zone")


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
        zones = [_zone_record(z.get("zone"), z.get("id_key"), z.get("colour_source"), catalogue,
                              z.get("colour"))
                 for z in raw_zones]
        guard_schedule_zones(set_id, row.get("schedule_finishes"), zones)
        if any(z["id"] >= UDIM_AS_MATERIAL_ID for z in zones):
            raise ZoneError(f"{set_id}: material id >= {UDIM_AS_MATERIAL_ID}")
        profiles = _profiles(set_id, zones, row.get("profiles"))
        item = {"set_id": set_id, "zones": zones, "profiles": profiles}
        for field in ("name", "catalogue_id", "schedule", "material_reason", "split_note",
                      "schedule_finishes"):
            if field in row:
                item[field] = row[field]
        positions.append(item)
    return {
        "ok": True,
        "accepted": False,
        "photo_status": "not_required",
        "geometry_rewrite": False,
        "reason": ("2026-11-05: passport photos are not required. RAL comes from the schedule; "
                   "a finish with no number keeps the atlas slot and is marked colour assumed. "
                   "Vertex and face counts are unchanged."),
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
        merged = {}
        order = []
        for name in names:
            fin = finish_colour(name, catalogue)
            if fin["zone"] not in merged:
                merged[fin["zone"]] = {"zone": fin["zone"], "id_key": fin["id_key"],
                                        "colour_source": fin["colour_source"], "colour": fin["colour"]}
                order.append(fin["zone"])
            elif merged[fin["zone"]]["id_key"] != fin["id_key"]:
                raise ZoneError(f"{set_id}: zone {fin['zone']} maps two materials")
        zones = [merged[name] for name in order]
        note = None
        if len(zones) == 1 and set_id in POSITION_POLICY:
            keys = set(POSITION_POLICY[set_id].values())
            if len(keys) == 1:
                note = "schedule names one finish; face groups keep that material id"
            else:
                note = "single atlas slot; face-group split is applied when a mesh is supplied"
        profiles = {}
        for prof in ("npm", "vpm"):
            block = counts[set_id][prof]
            zone_faces = {}
            for name in names:
                fin = finish_colour(name, catalogue)
                zone_faces[fin["zone"]] = zone_faces.get(fin["zone"], 0) + block["zone_faces"].get(name, 0)
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


def rows_from_applied(set_report: dict, applied: dict, catalogue: dict, before_counts=None) -> list:
    """Zone rows from the Max assignment. Before-counts are the pre-apply read; after is the apply readback."""
    if not isinstance(applied, dict) or applied.get("ok") is not True:
        raise ZoneError("applied report is not ok")
    positions = applied.get("positions")
    if not isinstance(positions, dict) or not positions:
        raise ZoneError("applied report has no positions")
    if before_counts is not None and not isinstance(before_counts, dict):
        raise ZoneError("empty geometry counts")
    rows = []
    seen = []
    for pos in set_report.get("positions") or []:
        set_id = pos.get("set_id")
        if set_id not in positions:
            raise ZoneError(f"unmapped position: {set_id}")
        seen.append(set_id)
        if set_id not in SCHEDULE_FINISHES:
            raise ZoneError(f"unmapped position: {set_id}")
        block = positions[set_id]
        prior = None
        if before_counts is not None:
            prior = before_counts.get(set_id)
            if not isinstance(prior, dict):
                raise ZoneError(f"{set_id}: geometry counts missing")
        profiles = {}
        zone_names = None
        zone_meta = None
        for prof in ("npm", "vpm"):
            side = block.get(prof)
            if not isinstance(side, dict):
                raise ZoneError(f"{set_id} {prof}: geometry counts missing")
            vertices = _finite_int(side.get("vertices"), f"{set_id} {prof} vertices")
            faces = _finite_int(side.get("faces"), f"{set_id} {prof} faces")
            vertices_after = _finite_int(side.get("vertices_after"), f"{set_id} {prof} vertices_after")
            faces_after = _finite_int(side.get("faces_after"), f"{set_id} {prof} faces_after")
            if vertices_after != vertices or faces_after != faces:
                raise ZoneError(f"{set_id} {prof}: vertices {vertices} != {vertices_after}")
            if prior is None:
                vertices_before, faces_before = vertices, faces
            else:
                measured = prior.get(prof)
                if not isinstance(measured, dict):
                    raise ZoneError(f"{set_id} {prof}: geometry counts missing")
                vertices_before = _finite_int(measured.get("vertices"), f"{set_id} {prof} vertices_before")
                faces_before = _finite_int(measured.get("faces"), f"{set_id} {prof} faces_before")
                if vertices_before != vertices_after or faces_before != faces_after:
                    raise ZoneError(
                        f"{set_id} {prof}: vertices {vertices_before} != {vertices_after}")
            raw = side.get("zones")
            if not isinstance(raw, list) or not raw:
                raise ZoneError(f"{set_id} {prof}: empty zone list")
            counts = {}
            meta = {}
            for zone in raw:
                name = zone.get("zone")
                count = _finite_int(zone.get("faces"), f"{set_id} {prof} {name}")
                if count <= 0:
                    raise ZoneError(f"{set_id} {prof}: zone {name} has no faces")
                if name in counts:
                    raise ZoneError(f"{set_id}: duplicate zone")
                counts[name] = count
                meta[name] = zone
            if sum(counts.values()) != faces:
                raise ZoneError(f"{set_id} {prof}: zone faces {sum(counts.values())} != faces {faces}")
            names = list(counts)
            if zone_names is None:
                zone_names = names
                zone_meta = meta
            elif names != zone_names:
                raise ZoneError(f"{set_id}: npm/vpm zones differ: {zone_names} vs {names}")
            profiles[prof] = {"vertices_before": vertices_before, "faces_before": faces_before,
                              "vertices_after": vertices_after, "faces_after": faces_after,
                              "zone_faces": counts}
        zones = []
        for name in zone_names:
            src = zone_meta[name]
            zones.append({"zone": name, "id_key": src.get("id_key"), "colour_source": src.get("colour_source"),
                          "colour": src.get("colour")})
        finishes = list(SCHEDULE_FINISHES[set_id])
        note = None
        if len(zones) == 1:
            policy_keys = set(POSITION_POLICY.get(set_id, {}).values())
            if len(policy_keys) <= 1 and len(finishes) == 1:
                note = "schedule names one finish; face groups keep that material id"
        rows.append({"set_id": set_id, "catalogue_id": pos.get("catalogue_id"), "schedule": pos.get("schedule"),
                     "name": pos.get("name"), "material_reason": pos.get("material_reason"),
                     "split_note": note, "schedule_finishes": finishes,
                     "zones": zones, "profiles": profiles})
    dropped = [sid for sid in positions if sid not in seen]
    if dropped:
        raise ZoneError(f"unmapped position: {', '.join(dropped)}")
    return rows


def render_md(report: dict) -> str:
    lines = [
        "# Vatutino showcase MAF colour zones (#889)",
        "",
        "Geometry is the accepted v005-set mesh. `before` is the pre-apply readback",
        "(site-maf-set.md / site-maf-zone-counts.json). `after` is the apply readback.",
        "Vertex and face counts are equal before and after.",
        "A schedule RAL is stated as that paint. A named finish with no number keeps the atlas-slot",
        "hex and is marked colour assumed (the vendor candidate sheet is a library viewport, not a measurement).",
        "Single-material meshes are split into face groups at a dihedral of 40 degrees; the kind of each",
        "group (slab, tube, shell, fastener) is mapped by POSITION_POLICY.",
        "",
        "QA: `maf_surface` readback from tools/blender/fbx_readback.py.",
        "",
        f"Photo status: {report.get('photo_status')}. Accepted: {report.get('accepted')}.",
        "",
    ]
    if report.get("apply_marker"):
        lines.append(
            f"{report['apply_marker']} {report.get('apply_report', '')} "
            f"max_exit_code={report.get('max_exit_code')} ({report.get('max_exit_note', '')})"
        )
        lines.append("")
    lines += [
        "| position | zone | ID | key | colour | npm faces before | npm faces after | npm verts before | npm verts after | vpm faces before | vpm faces after | vpm verts before | vpm verts after | zone faces npm | zone faces vpm | colour source |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for pos in report["positions"]:
        npm, vpm = pos["profiles"]["npm"], pos["profiles"]["vpm"]
        for zone in pos["zones"]:
            lines.append(
                f"| {pos['set_id']} | {zone['zone']} | {zone['id']} | {zone['id_key']} | {zone['colour']} "
                f"| {npm['faces_before']} | {npm['faces_after']} | {npm['vertices_before']} | {npm['vertices_after']} "
                f"| {vpm['faces_before']} | {vpm['faces_after']} | {vpm['vertices_before']} | {vpm['vertices_after']} "
                f"| {npm['zone_faces'][zone['zone']]} | {vpm['zone_faces'][zone['zone']]} | {zone['colour_source']} |"
            )
        if pos.get("split_note"):
            lines.append(
                f"| {pos['set_id']} | — | — | — | — | — | — | — | — | — | — | — | — | — | — | {pos['split_note']} |"
            )
    lines += ["", "Method: shared-edge components with dihedral <= 40 deg; slab / tube / shell / fastener extents as in the module docstring.", ""]
    surface = report.get("maf_surface")
    if isinstance(surface, dict) and surface:
        lines += [
            "maf_surface (tools/blender/fbx_readback.py):",
            "",
            "| position | profile | vertices | faces | flipped_faces | inconsistent_edges | soft_over_40 |",
            "|---|---|---|---|---|---|---|",
        ]
        for set_id, profs in surface.items():
            for prof in ("npm", "vpm"):
                row = profs[prof]
                lines.append(
                    f"| {set_id} | {prof} | {row['vertices']} | {row['faces']} | {row['flipped_faces']} "
                    f"| {row['inconsistent_edges']} | {row['soft_over_40']} |"
                )
        lines.append("")
    return "\n".join(lines)


def _exit_code(value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ZoneError(f"max exit: not a finite integer: {value!r}")
    if isinstance(value, int):
        return value
    text = value.strip()
    if not text.lstrip("-").isdigit():
        raise ZoneError(f"max exit: not a finite integer: {value!r}")
    return int(text)


def _load_surface(path, report: dict) -> dict:
    """maf_surface facts from tools/blender/fbx_readback.py. Counts must match the apply readback."""
    doc = _load(path, "maf_surface")
    if not isinstance(doc, dict) or not doc:
        raise ZoneError("maf_surface: empty")
    needed = [pos["set_id"] for pos in report["positions"]]
    missing = [sid for sid in needed if sid not in doc]
    extra = [sid for sid in doc if sid not in needed]
    if missing or extra:
        raise ZoneError(f"unmapped position: {', '.join(missing or extra)}")
    out = {}
    for pos in report["positions"]:
        set_id = pos["set_id"]
        block = doc[set_id]
        if not isinstance(block, dict):
            raise ZoneError(f"{set_id}: maf_surface missing")
        out[set_id] = {}
        for prof in ("npm", "vpm"):
            row = block.get(prof)
            if not isinstance(row, dict):
                raise ZoneError(f"{set_id} {prof}: maf_surface missing")
            for field in ("vertices", "faces", "flipped_faces", "inconsistent_edges", "soft_over_40"):
                if field not in row:
                    raise ZoneError(f"{set_id} {prof}: {field} missing")
            vertices = _finite_int(row["vertices"], f"{set_id} {prof} vertices")
            faces = _finite_int(row["faces"], f"{set_id} {prof} faces")
            geo = pos["profiles"][prof]
            if vertices != geo["vertices_after"] or faces != geo["faces_after"]:
                raise ZoneError(f"{set_id} {prof}: vertices {vertices} != {geo['vertices_after']}")
            out[set_id][prof] = {
                "vertices": vertices,
                "faces": faces,
                "flipped_faces": _finite_int(row["flipped_faces"], f"{set_id} {prof} flipped_faces"),
                "inconsistent_edges": _finite_int(row["inconsistent_edges"], f"{set_id} {prof} inconsistent_edges"),
                "soft_over_40": _finite_int(row["soft_over_40"], f"{set_id} {prof} soft_over_40"),
            }
    return out


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
    ap.add_argument("--applied", default=None, help="Max assignment report; replaces atlas-only rows")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--required", nargs="*", default=None)
    ap.add_argument("--max-exit", default=None, help="raw 3dsmaxbatch exit code recorded next to APPLIED")
    ap.add_argument("--max-exit-note", default="known polyunwrapper_autoload.mse startup error")
    ap.add_argument("--surface", default=None, help="maf_surface summary json from fbx_readback.py")
    args = ap.parse_args(argv)
    out_json, out_md = Path(args.out_json), Path(args.out_md)
    try:
        paths = {
            "set": args.set, "ids": args.ids, "counts": args.counts,
            "out-json": out_json, "out-md": out_md,
        }
        if args.applied:
            paths["applied"] = args.applied
        if args.surface:
            paths["surface"] = args.surface
        assert_distinct_paths(paths)
        catalogue = load_id_catalogue(_load(args.ids, "id catalogue"))
        report_in = _load(args.set, "set report")
        counts = _load(args.counts, "geometry counts")
        if args.applied:
            rows = rows_from_applied(report_in, _load(args.applied, "applied report"), catalogue, counts)
        else:
            rows = rows_from_set(report_in, catalogue, counts)
        required = list(args.required) if args.required else [row["set_id"] for row in rows]
        report = compile_zones(required, rows, catalogue)
        check_rows_id_colours(report["positions"])
        if args.applied:
            if args.max_exit is None:
                raise ZoneError("max exit missing")
            report["apply_marker"] = "APPLIED"
            report["apply_report"] = str(Path(args.applied))
            report["max_exit_code"] = _exit_code(args.max_exit)
            report["max_exit_note"] = args.max_exit_note
        if args.surface:
            report["maf_surface"] = _load_surface(args.surface, report)
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
