"""Build a Flora library catalogue with stable material IDs.

Pattern / new-case: Flora library catalogue - curated species -> NPM/VPM source selection -> stable material IDs (#216).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import unicodedata
from pathlib import Path

RANGES = {
    "tree": (101, 199),
    "bush": (201, 299),
    "hedge": (301, 399),
    "flower": (401, 499),
    "climber": (501, 599),
}
LIBRARY_FILE = "C:/x/flora-library/v003/flora-library-v003.max"
MAPS_ROOT = "C:/x/flora-library/v001/maps"
LIBRARY_SCENE = "FLORA_Union_v1.max"
REVIEW_STATUS = ("approved", "pending_review", "missing")
VPM_STATUS = ("available", "unconfirmed", "none")
SHARED_STAND_IN_STATUS = "gap: shared multi-species FLORIO mesh, no own mesh"
REPO = Path(__file__).resolve().parents[3]

_TOP_KEYS = ("schema", "library_file", "id_ranges", "retired_ids", "species", "gaps", "counts")
_SPECIES_KEYS = (
    "material_id", "latin", "russian", "type", "geometry_basis", "note", "objects",
    "npm", "vpm", "vpm_status", "vpm_identity", "vpm_evidence", "merged",
    "height_m", "crown_diameter_m", "triangles",
    "source_scenes", "maps",
)
_SOURCE_KEYS = (
    "entry_id", "scene", "source_name", "triangles", "height_m", "crown_diameter_m", "basis",
)
_MERGED_KEYS = ("entry_id", "scene", "source_name", "reason")
_MAP_KEYS = ("diffuse", "opacity", "review_status", "evidence")
_GAP_KEYS = ("unresolved", "species_without_approved_maps", "project_species_shared_stand_in")
_STAND_IN_KEYS = ("latin", "russian", "type", "material_id", "sources", "status")
_COUNT_KEYS = (
    "species", "by_type", "with_vpm", "merged_duplicates", "maps",
    "shared_stand_in_gaps", "unresolved",
)
_NPM_PROFILE = {"LP": 0, "LP -> HP": 1, "unlabelled": 2}
_VPM_PROFILE = {"HP": 0, "LP -> HP": 1}
_VPM_IDENTITY = ("unverified",)
_GEOMETRY_RELATIONS = ("unverified",)
_KEPT_VPM_RELATIONS = ("unverified",)
_EVIDENCE_KEYS = ("relation", "translation_dev_m", "scaled_dev_rel")
_IDENTITY_SCHEMA = "flora-geometry-identity-v3"
_IDENTITY_TOLERANCE = 1e-4
_IDENTITY_METHOD = "VPM identity: unverified, see #305; no geometry classification or identity-based filtering"
_PAIR_KEYS = ("a", "b", "relation", "translation_dev_m", "scaled_dev_rel")


def object_name(latin: str, profile: str) -> str:
    return f"{_stem(latin)}_{profile}"


def slug(latin: str) -> str:
    return _stem(latin).lower().replace("_", "-")


class PairIdentity(dict):
    """Pair relation map (frozenset of two entry ids -> relation) plus deviation details."""

    def __init__(self, relations: dict[frozenset, str], details: dict[frozenset, dict]):
        super().__init__(relations)
        self.details = details


def compare_clouds(a_points, b_points, tolerance: float = _IDENTITY_TOLERANCE) -> dict:
    """Identity is deliberately unverified in #216; coverage checking belongs to #305."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    return {"relation": "unverified", "translation_dev_m": None, "scaled_dev_rel": None}


def compare_surfaces(a_faces, b_faces, tolerance: float = _IDENTITY_TOLERANCE) -> dict:
    """Identity is deliberately unverified in #216; coverage checking belongs to #305."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    return {"relation": "unverified", "translation_dev_m": None, "scaled_dev_rel": None}


def build_identity(points: dict[str, list], curation: dict) -> dict:
    """Inventory unverified source pairs for every curated species with its own mesh."""
    if not isinstance(points, dict) or not isinstance(curation, dict):
        raise ValueError("points and curation must be objects")
    used: set[str] = set()
    pair_keys: set[tuple[str, str]] = set()
    for item in curation.get("species", []):
        if not isinstance(item, dict):
            raise ValueError("curation species row is not an object")
        if item.get("geometry_basis") == "shared_multi_species_stand_in":
            continue
        sources = item.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError(f"{item.get('latin')!r} sources is not a list")
        ids: list[str] = []
        for source in sources:
            if not isinstance(source, str):
                raise ValueError(f"source id {source!r} is not a string")
            if source not in points:
                raise ValueError(f"missing points for {source}")
            ids.append(source)
            used.add(source)
        for index, left in enumerate(ids):
            for right in ids[index + 1:]:
                if left == right:
                    continue
                pair_keys.add((left, right) if left < right else (right, left))
    entries = {entry_id: {"triangles": _listed_faces(points[entry_id])} for entry_id in sorted(used)}
    pairs = []
    for left, right in sorted(pair_keys):
        compared = compare_surfaces(points[left], points[right], _IDENTITY_TOLERANCE)
        pairs.append({
            "a": left,
            "b": right,
            "relation": compared["relation"],
            "translation_dev_m": compared["translation_dev_m"],
            "scaled_dev_rel": compared["scaled_dev_rel"],
        })
    return {
        "schema": _IDENTITY_SCHEMA,
        "method": _IDENTITY_METHOD,
        "tolerance": _IDENTITY_TOLERANCE,
        "entries": entries,
        "pairs": pairs,
    }


def load_identity(value: dict) -> PairIdentity:
    """Return frozenset({id_a, id_b}) -> relation from a flora-geometry-identity-v3 document."""
    if not isinstance(value, dict) or value.get("schema") != _IDENTITY_SCHEMA:
        raise ValueError(f"schema is not {_IDENTITY_SCHEMA}")
    if value.get("method") != _IDENTITY_METHOD:
        raise ValueError("method is not the flora geometry identity method")
    if value.get("tolerance") != _IDENTITY_TOLERANCE:
        raise ValueError("tolerance is not 1e-4")
    entries = value.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("entries is not an object")
    vertices: dict[str, int] = {}
    for entry_id, row in entries.items():
        if not isinstance(entry_id, str) or not entry_id or not isinstance(row, dict):
            raise ValueError(f"invalid identity entry {entry_id!r}")
        if set(row) != {"triangles"} or not _is_int(row.get("triangles")) or row["triangles"] < 0:
            raise ValueError(f"invalid triangle count for {entry_id}")
        vertices[entry_id] = row["triangles"]
    pairs = value.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("pairs is not a list")
    relations: dict[frozenset, str] = {}
    details: dict[frozenset, dict] = {}
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict) or set(pair) != set(_PAIR_KEYS):
            raise ValueError(f"pairs[{index}] does not match the identity pair schema")
        left, right = pair["a"], pair["b"]
        if not isinstance(left, str) or not isinstance(right, str) or not left or not right:
            raise ValueError(f"pairs[{index}] ids are not strings")
        if not left < right:
            raise ValueError(f"pairs[{index}] is not ordered {left!r} < {right!r}")
        if left not in vertices or right not in vertices:
            raise ValueError(f"pairs[{index}] ids are not in entries")
        relation = pair["relation"]
        if relation not in _GEOMETRY_RELATIONS:
            raise ValueError(f"pairs[{index}] relation {relation!r} is not a geometry relation")
        for key in ("translation_dev_m", "scaled_dev_rel"):
            if pair[key] is not None and not _is_number(pair[key]):
                raise ValueError(f"pairs[{index}].{key} is not a number")
        _require_relation_devs(relation, pair, index)
        key = frozenset((left, right))
        if key in relations:
            raise ValueError(f"duplicate pair {left} {right}")
        relations[key] = relation
        details[key] = {
            "translation_dev_m": pair["translation_dev_m"],
            "scaled_dev_rel": pair["scaled_dev_rel"],
        }
    return PairIdentity(relations, details)


def geometry_relation(a: dict, b: dict, identity: dict | None) -> str:
    """Never use historical identity evidence to drop a profile (#305)."""
    return "unverified"


def select_sources(entries: list[dict], identity: dict | None = None, selection: dict | None = None) -> dict:
    """Pick one NPM mesh and one VPM mesh for a single species."""
    npm_candidates = [entry for entry in entries if _npm_basis(entry) is not None]
    vpm_candidates = [entry for entry in entries if _vpm_basis(entry) is not None]
    if not npm_candidates:
        raise ValueError("species has no NPM candidate")
    npm_entry = min(npm_candidates, key=_npm_key)
    qualifying = [entry for entry in vpm_candidates if _qualifies_as_vpm(entry, npm_entry, identity)]
    vpm_entry = min(qualifying, key=_vpm_key) if qualifying else None
    if selection is not None:
        # Preserve the existing saved library, not an inferred geometry verdict.
        if not isinstance(selection, dict) or set(selection) != {"NPM", "VPM", "vpm_status"}:
            raise ValueError("library_selection must contain NPM, VPM and vpm_status")
        indexed = {entry["id"]: entry for entry in entries}
        if selection["NPM"] not in indexed or selection["VPM"] is not None and selection["VPM"] not in indexed:
            raise ValueError("library_selection source is not in the curated species")
        npm_entry = indexed[selection["NPM"]]
        vpm_entry = indexed.get(selection["VPM"])
        if _npm_basis(npm_entry) is None or vpm_entry is not None and _vpm_basis(vpm_entry) is None:
            raise ValueError("library_selection source has no matching profile label")
        if selection["vpm_status"] not in VPM_STATUS or (selection["vpm_status"] == "available") != (vpm_entry is not None):
            raise ValueError("library_selection vpm_status does not match VPM")
    npm = _record(npm_entry, _npm_basis(npm_entry))
    vpm = None if vpm_entry is None else _record(vpm_entry, _vpm_basis(vpm_entry))
    kept = {npm_entry["id"]}
    if vpm_entry is not None:
        kept.add(vpm_entry["id"])
    merged = []
    for entry in entries:
        if entry["id"] in kept:
            continue
        merged.append({
            "entry_id": entry["id"],
            "scene": entry["scene"],
            "source_name": entry["source_name"],
            "reason": _merged_reason(entry, npm_entry, vpm_entry, identity),
        })
    unknown_skipped = False
    for entry in vpm_candidates:
        if entry["id"] == npm_entry["id"]:
            continue
        if vpm_entry is not None and entry["id"] == vpm_entry["id"]:
            continue
        if geometry_relation(entry, npm_entry, identity) == "unverified":
            unknown_skipped = True
    if vpm_entry is not None:
        vpm_status = "available"
        relation = geometry_relation(vpm_entry, npm_entry, identity)
        vpm_identity = "unverified"
        vpm_evidence = _vpm_evidence(vpm_entry, npm_entry, identity, relation)
    elif _npm_basis(npm_entry) == "LP -> HP" or unknown_skipped:
        vpm_status = "unconfirmed"
        vpm_identity = None
        vpm_evidence = None
    else:
        vpm_status = "none"
        vpm_identity = None
        vpm_evidence = None
    if selection is not None:
        vpm_status = selection["vpm_status"]
    return {
        "NPM": npm,
        "VPM": vpm,
        "merged": merged,
        "vpm_status": vpm_status,
        "vpm_identity": vpm_identity,
        "vpm_evidence": vpm_evidence,
    }


def assign_ids(species: list[dict], previous: dict | None = None, gaps: list[dict] | None = None) -> dict:
    """Keep previous material IDs, reserve shared stand-in IDs, and retire IDs that left."""
    gap_rows = list(gaps or [])
    current_rows = list(species) + gap_rows
    _require_unique_latin(current_rows)
    history, retired = _history(previous)
    assigned: dict[str, int] = {}
    for item in current_rows:
        latin = item["latin"]
        if latin not in history:
            continue
        material_id = history[latin]["material_id"]
        _require_range(item["type"], material_id, latin)
        assigned[latin] = material_id
    retired = [row for row in retired if not isinstance(row["latin"], str) or row["latin"] not in assigned]
    current = {item["latin"] for item in current_rows}
    for latin, item in history.items():
        if item["origin"] == "active" and latin not in current:
            retired.append(_retired_object(item["material_id"], latin, item["type"]))
    used = {row["material_id"] for row in retired} | set(assigned.values())
    for item in current_rows:
        latin = item["latin"]
        if latin in assigned:
            continue
        low, high = _range_for(item["type"])
        material_id = next((number for number in range(low, high + 1) if number not in used), None)
        if material_id is None:
            raise ValueError(f"{item['type']} material-id range {low}-{high} is full")
        assigned[latin] = material_id
        used.add(material_id)
    retired.sort(key=lambda row: row["material_id"])
    return {"by_latin": assigned, "retired_ids": retired}


def build(
    audit: dict,
    curation: dict,
    maps: dict,
    previous: dict | None = None,
    identity: dict | None = None,
) -> dict:
    indexed = _index_audit(audit)
    library, gap_items = _split_curation(curation)
    rows = []
    for item in library:
        missing = [source for source in item["sources"] if source not in indexed]
        if missing:
            raise ValueError(f"{item['latin']} sources not in the audit: {missing}")
        chosen = select_sources([indexed[source] for source in item["sources"]], identity, item.get("library_selection"))
        map_info = _maps_for(item["latin"], maps)
        scenes = [chosen["NPM"]["scene"]]
        if chosen["VPM"] is not None:
            scenes.append(chosen["VPM"]["scene"])
        rows.append({
            "latin": item["latin"],
            "russian": item["russian"],
            "type": item["type"],
            "geometry_basis": item["geometry_basis"],
            "note": item["note"],
            "objects": {
                "NPM": object_name(item["latin"], "NPM"),
                "VPM": None if chosen["VPM"] is None else object_name(item["latin"], "VPM"),
            },
            "npm": chosen["NPM"],
            "vpm": chosen["VPM"],
            "vpm_status": chosen["vpm_status"],
            "vpm_identity": chosen["vpm_identity"],
            "vpm_evidence": chosen["vpm_evidence"],
            "merged": chosen["merged"],
            "height_m": chosen["NPM"]["height_m"],
            "crown_diameter_m": chosen["NPM"]["crown_diameter_m"],
            "triangles": {
                "NPM": chosen["NPM"]["triangles"],
                "VPM": None if chosen["VPM"] is None else chosen["VPM"]["triangles"],
            },
            "source_scenes": sorted(set(scenes)),
            "maps": map_info,
        })
    gap_rows = [
        {
            "latin": item["latin"],
            "russian": item["russian"],
            "type": item["type"],
            "sources": list(item["sources"]),
        }
        for item in gap_items
    ]
    ids = assign_ids(rows, previous, gap_rows)
    species = []
    for row in rows:
        species.append({"material_id": ids["by_latin"][row["latin"]], **row})
    stand_in = []
    for item in gap_rows:
        stand_in.append({
            "latin": item["latin"],
            "russian": item["russian"],
            "type": item["type"],
            "material_id": ids["by_latin"][item["latin"]],
            "sources": item["sources"],
            "status": SHARED_STAND_IN_STATUS,
        })
    unresolved = _unresolved(curation.get("unresolved", []), indexed)
    return {
        "schema": "flora-library-v1",
        "library_file": LIBRARY_FILE,
        "id_ranges": {kind: list(bounds) for kind, bounds in RANGES.items()},
        "retired_ids": ids["retired_ids"],
        "species": species,
        "gaps": _gaps(species, unresolved, stand_in),
        "counts": _counts(species, stand_in, unresolved),
    }


def check(catalogue: dict) -> list[str]:
    """Return human-readable schema and material-ID findings. Empty means OK."""
    findings: list[str] = []
    if not isinstance(catalogue, dict):
        return ["catalogue is not an object"]
    findings.extend(_key_findings(catalogue, _TOP_KEYS, "catalogue"))
    if findings:
        return findings
    if catalogue["schema"] != "flora-library-v1":
        findings.append(f"schema {catalogue['schema']!r} is not flora-library-v1")
    if not isinstance(catalogue["library_file"], str):
        findings.append("library_file is not a string")
    findings.extend(_check_ranges(catalogue["id_ranges"]))
    findings.extend(_check_retired(catalogue["retired_ids"]))
    if not isinstance(catalogue["species"], list):
        findings.append("species is not a list")
        return findings
    retired = _retired_material_ids(catalogue["retired_ids"])
    seen_ids: dict[int, str] = {}
    seen_latin: dict[str, int] = {}
    seen_names: dict[str, str] = {}
    for index, item in enumerate(catalogue["species"]):
        where = f"species[{index}]"
        if not isinstance(item, dict):
            findings.append(f"{where} is not an object")
            continue
        findings.extend(_key_findings(item, _SPECIES_KEYS, where))
        findings.extend(_check_species(item, where, retired, seen_ids, seen_latin, seen_names))
    findings.extend(_check_gaps(catalogue))
    findings.extend(_check_retired_latins(catalogue))
    findings.extend(_check_counts(catalogue))
    return findings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Flora library catalogue builder and material-ID check.")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--audit", required=True)
    build_parser.add_argument("--curation", required=True)
    build_parser.add_argument("--maps", required=True)
    build_parser.add_argument("--out", required=True)
    build_parser.add_argument("--previous")
    build_parser.add_argument("--identity")
    identity_parser = sub.add_parser("identity")
    identity_parser.add_argument("--points", required=True)
    identity_parser.add_argument("--curation", required=True)
    identity_parser.add_argument("--out", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--catalogue", required=True)
    args = parser.parse_args(argv)
    if args.command == "identity":
        try:
            points = _points_from_dump(_read_json(args.points))
            document = build_identity(points, _read_json(args.curation))
        except ValueError as exc:
            print(exc)
            raise SystemExit(1) from exc
        _write_json(args.out, document)
        return
    if args.command == "build":
        previous = _read_json(args.previous) if args.previous else None
        identity = load_identity(_read_json(args.identity)) if args.identity else None
        catalogue = build(
            _read_json(args.audit),
            _read_json(args.curation),
            _read_json(args.maps),
            previous,
            identity,
        )
        findings = check(catalogue)
        if findings:
            for line in findings:
                print(line)
            raise SystemExit(1)
        _write_json(args.out, catalogue)
        return
    catalogue = _read_json(args.catalogue)
    findings = check(catalogue)
    if findings:
        for line in findings:
            print(line)
        raise SystemExit(1)
    print(f"OK {len(catalogue['species'])} species")


def _stem(latin: str) -> str:
    text = latin.replace("×", " ").replace("'", "").replace("’", "").replace(".", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[\s\-]+", "_", text)
    text = "".join(char for char in text if char.isascii() and (char.isalnum() or char == "_"))
    return re.sub(r"_+", "_", text).strip("_")


def _npm_basis(entry: dict) -> str | None:
    raw = entry["profile_raw"]
    if "LP" in raw:
        return "LP"
    if "LP -> HP" in raw:
        return "LP -> HP"
    if not raw:
        return "unlabelled"
    return None


def _vpm_basis(entry: dict) -> str | None:
    raw = entry["profile_raw"]
    if "HP" in raw:
        return "HP"
    if "LP -> HP" in raw:
        return "LP -> HP"
    return None


def _npm_key(entry: dict) -> tuple:
    return (
        _NPM_PROFILE[_npm_basis(entry)],
        0 if entry["scene"] == LIBRARY_SCENE else 1,
        int(bool(entry["hidden"])),
        entry["triangles"],
        entry["id"],
    )


def _vpm_key(entry: dict) -> tuple:
    # Library scene outranks an explicit HP label so FLORIO HP does not replace
    # a qualifying library mesh (Acer tataricum subsp. ginnala keeps library-024
    # when that source is selected for the built VPM).
    return (
        0 if entry["scene"] == LIBRARY_SCENE else 1,
        _VPM_PROFILE[_vpm_basis(entry)],
        int(bool(entry["hidden"])),
        -entry["triangles"],
        entry["id"],
    )


def _size(dimensions: list) -> tuple[float, float]:
    return round(float(dimensions[2]), 3), round(max(float(dimensions[0]), float(dimensions[1])), 3)


def _record(entry: dict, basis: str) -> dict:
    height, crown = _size(entry["dimensions_m"])
    return {
        "entry_id": entry["id"],
        "scene": entry["scene"],
        "source_name": entry["source_name"],
        "triangles": entry["triangles"],
        "height_m": height,
        "crown_diameter_m": crown,
        "basis": basis,
    }


def _require_relation_devs(relation: str, pair: dict, index: int) -> None:
    if relation != "unverified" or any(pair[k] is not None for k in ("translation_dev_m", "scaled_dev_rel")):
        raise ValueError(f"pairs[{index}] must be unverified without deviations; see #305")


def _listed_faces(value) -> int:
    """Count listed face records only; this is not surface-validity evidence."""
    if not isinstance(value, list):
        return 0
    return sum(isinstance(face, (list, tuple)) and len(face) == 3
               and all(isinstance(point, (list, tuple)) and len(point) == 3 for point in face)
               for face in value)


def _points_from_dump(dump: dict) -> dict[str, list]:
    if not isinstance(dump, dict):
        raise ValueError("points dump is not an object")
    failures = dump.get("failures")
    if not isinstance(failures, list):
        raise ValueError("points dump is missing failures")
    if failures:
        raise ValueError("points dump has failures")
    entries = dump.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("points dump is missing entries")
    points: dict[str, list] = {}
    for entry_id, row in entries.items():
        if not isinstance(entry_id, str) or not isinstance(row, dict):
            raise ValueError(f"invalid points entry {entry_id!r}")
        if isinstance(row.get("triangles"), list):
            points[entry_id] = row["triangles"]
        elif isinstance(row.get("points"), list):
            points[entry_id] = row["points"]
        else:
            raise ValueError(f"invalid points entry {entry_id!r}")
    return points


def _vpm_evidence(entry: dict, npm_entry: dict, identity: dict | None, relation: str) -> dict:
    return {"relation": "unverified", "translation_dev_m": None, "scaled_dev_rel": None}


def _qualifies_as_vpm(entry: dict, npm_entry: dict, identity: dict | None) -> bool:
    # A lone LP -> HP label does not establish a separate profile. Explicit HP is
    # retained regardless of old geometry evidence; frozen built choices are below.
    return entry["id"] != npm_entry["id"] and _vpm_basis(entry) == "HP"


def _merged_reason(entry: dict, npm_entry: dict, vpm_entry: dict | None, identity: dict | None) -> str:
    if _vpm_basis(entry) is not None and not _qualifies_as_vpm(entry, npm_entry, identity):
        return f"not selected as separate VPM: kept NPM {npm_entry['id']}; VPM identity: unverified, see #305"
    winner = vpm_entry if vpm_entry is not None and _npm_basis(entry) is None else npm_entry
    kind = "VPM" if winner is vpm_entry else "NPM"
    return f"alternate source: kept {winner['id']} ({_rule(winner, entry, kind)}); VPM identity: unverified, see #305"


def _rule(winner: dict, loser: dict, kind: str) -> str:
    for name in ("profile", "scene", "hidden", "triangles", "id") if kind == "NPM" else (
        "scene", "profile", "hidden", "triangles", "id"
    ):
        reason = _step(name, winner, loser, kind)
        if reason is not None:
            return reason
    return "entry id"


def _step(name: str, winner: dict, loser: dict, kind: str) -> str | None:
    if name == "profile":
        ranks = _NPM_PROFILE if kind == "NPM" else _VPM_PROFILE
        basis = _npm_basis if kind == "NPM" else _vpm_basis
        winner_basis = basis(winner)
        loser_basis = basis(loser)
        if ranks[winner_basis] == ranks[loser_basis]:
            return None
        return _profile_phrase(winner_basis, loser_basis)
    if name == "scene":
        winner_library = winner["scene"] == LIBRARY_SCENE
        loser_library = loser["scene"] == LIBRARY_SCENE
        if winner_library == loser_library:
            return None
        return "library before FLORIO"
    if name == "hidden":
        if bool(winner["hidden"]) == bool(loser["hidden"]):
            return None
        return "not hidden before hidden"
    if name == "triangles":
        if winner["triangles"] == loser["triangles"]:
            return None
        if kind == "NPM":
            return "fewer triangles"
        return "more triangles"
    if winner["id"] == loser["id"]:
        return None
    return "entry id"


def _profile_phrase(better: str, worse: str) -> str:
    phrases = {
        ("LP", "LP -> HP"): "explicit LP before LP -> HP",
        ("LP", "unlabelled"): "explicit LP before unlabelled",
        ("LP -> HP", "unlabelled"): "LP -> HP before unlabelled",
        ("HP", "LP -> HP"): "explicit HP before LP -> HP",
    }
    return phrases.get((better, worse), f"{better} before {worse}")


def _index_audit(audit: dict) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for scene in audit["scenes"]:
        scene_name = scene["source"]["scene"]
        for entry in scene["entries"]:
            item = dict(entry)
            item["scene"] = scene_name
            indexed[item["id"]] = item
    return indexed


def _maps_for(latin: str, maps: dict) -> dict:
    if latin not in maps:
        return {"diffuse": None, "opacity": None, "review_status": "missing", "evidence": None}
    item = maps[latin]
    return {
        "diffuse": item.get("diffuse"),
        "opacity": item.get("opacity"),
        "review_status": item.get("review_status", "missing"),
        "evidence": item.get("evidence"),
    }


def _require_unique_latin(rows: list[dict]) -> None:
    seen = set()
    for item in rows:
        if item["latin"] in seen:
            raise ValueError(f"duplicate latin {item['latin']}")
        seen.add(item["latin"])


def _retired_object(material_id: int, latin, kind) -> dict:
    return {"material_id": material_id, "latin": latin, "type": kind}


def _coerce_retired(item) -> dict:
    if _is_int(item):
        return _retired_object(item, None, None)
    if isinstance(item, dict) and _is_int(item.get("material_id")):
        return _retired_object(item["material_id"], item.get("latin"), item.get("type"))
    raise ValueError("retired_ids entry is not an int or an object with material_id")


def _remember_id(seen: dict[int, str], material_id: int) -> None:
    if not _is_int(material_id):
        raise ValueError(f"material_id {material_id!r} is not an int")
    if material_id in seen:
        raise ValueError(f"duplicate material_id {material_id}")
    seen[material_id] = ""


def _remember_latin(seen: set[str], latin: str) -> None:
    if latin in seen:
        raise ValueError(f"duplicate latin {latin}")
    seen.add(latin)


def _history(previous: dict | None) -> tuple[dict[str, dict], list[dict]]:
    if previous is None:
        return {}, []
    seen_ids: dict[int, str] = {}
    seen_latin: set[str] = set()
    history: dict[str, dict] = {}
    retired = [_coerce_retired(item) for item in previous.get("retired_ids", [])]
    for item in _previous_id_rows(previous):
        _remember_id(seen_ids, item["material_id"])
        _remember_latin(seen_latin, item["latin"])
        _require_range(item["type"], item["material_id"], item["latin"])
        history[item["latin"]] = {
            "material_id": item["material_id"],
            "type": item["type"],
            "origin": "active",
        }
    for row in retired:
        _remember_id(seen_ids, row["material_id"])
        if isinstance(row["latin"], str):
            _remember_latin(seen_latin, row["latin"])
            history[row["latin"]] = {
                "material_id": row["material_id"],
                "type": row["type"],
                "origin": "retired",
            }
    return history, retired


def _previous_id_rows(previous: dict) -> list[dict]:
    rows = [item for item in previous.get("species", []) if isinstance(item, dict)]
    stand_in = previous.get("gaps", {}).get("project_species_shared_stand_in", [])
    for item in stand_in:
        if isinstance(item, dict) and "material_id" in item and "latin" in item:
            rows.append(item)
    return rows


def _split_curation(curation: dict) -> tuple[list[dict], list[dict]]:
    library = []
    gaps = [item for item in curation.get("shared_stand_in_gaps", [])]
    for item in curation["species"]:
        if item.get("geometry_basis") == "shared_multi_species_stand_in":
            gaps.append(item)
        else:
            library.append(item)
    return library, gaps


def _unresolved(entries: list, indexed: dict[str, dict]) -> list:
    rows = []
    for item in entries:
        row = copy.deepcopy(item)
        names = []
        for source in item.get("sources", []):
            if source in indexed:
                names.append(indexed[source]["source_name"])
        row["source_names"] = names
        row["status"] = item.get("status", "unidentified")
        rows.append(row)
    return rows


def _gaps(species: list[dict], unresolved: list, stand_in: list[dict]) -> dict:
    return {
        "unresolved": unresolved,
        "species_without_approved_maps": [
            item["latin"] for item in species if item["maps"]["review_status"] != "approved"
        ],
        "project_species_shared_stand_in": stand_in,
    }


def _counts(species: list[dict], stand_in: list[dict], unresolved: list) -> dict:
    by_type = {kind: 0 for kind in RANGES}
    map_counts = {status: 0 for status in REVIEW_STATUS}
    with_vpm = 0
    merged = 0
    for item in species:
        if item["type"] in by_type:
            by_type[item["type"]] += 1
        if item["vpm"] is not None:
            with_vpm += 1
        merged += len(item["merged"])
        status = item["maps"]["review_status"]
        if status in map_counts:
            map_counts[status] += 1
    return {
        "species": len(species),
        "by_type": by_type,
        "with_vpm": with_vpm,
        "merged_duplicates": merged,
        "maps": map_counts,
        "shared_stand_in_gaps": len(stand_in),
        "unresolved": len(unresolved),
    }


def _range_for(kind: str) -> tuple[int, int]:
    if kind not in RANGES:
        raise ValueError(f"type {kind!r} is outside the Flora ranges")
    return RANGES[kind]


def _require_range(kind: str, material_id: int, latin: str) -> None:
    low, high = _range_for(kind)
    if not low <= material_id <= high:
        raise ValueError(
            f"previous material_id {material_id} for {latin} is outside the {kind} range {low}-{high}"
        )


def _read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, value: dict) -> None:
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _key_findings(
    value: dict,
    expected: tuple[str, ...],
    where: str,
    optional: tuple[str, ...] = (),
) -> list[str]:
    allowed = set(expected) | set(optional)
    findings = []
    for key in expected:
        if key not in value:
            findings.append(f"{where} missing key {key}")
    for key in value:
        if key not in allowed:
            findings.append(f"{where} extra key {key}")
    return findings


def _check_ranges(value) -> list[str]:
    expected = {kind: list(bounds) for kind, bounds in RANGES.items()}
    if not isinstance(value, dict):
        return ["id_ranges is not an object"]
    findings = _key_findings(value, tuple(RANGES), "id_ranges")
    if value != expected:
        findings.append("id_ranges does not match the Flora ranges")
    return findings


def _retired_material_ids(value) -> set[int]:
    if not isinstance(value, list):
        return set()
    found = set()
    for item in value:
        if isinstance(item, dict) and _is_int(item.get("material_id")):
            found.add(item["material_id"])
    return found


def _check_retired(value) -> list[str]:
    if not isinstance(value, list):
        return ["retired_ids is not a list"]
    findings = []
    seen_ids: set[int] = set()
    seen_latin: set[str] = set()
    for index, item in enumerate(value):
        where = f"retired_ids[{index}]"
        if not isinstance(item, dict):
            findings.append(f"{where} is not an object")
            continue
        findings.extend(_key_findings(item, ("material_id", "latin", "type"), where))
        material_id = item.get("material_id")
        latin = item.get("latin")
        kind = item.get("type")
        if "material_id" in item and not _is_int(material_id):
            findings.append(f"{where}.material_id is not an int")
        elif _is_int(material_id):
            if 1 <= material_id <= 100:
                findings.append(f"retired_ids contains ID {material_id} in 1-100")
            if material_id in seen_ids:
                findings.append(f"duplicate retired material_id {material_id}")
            else:
                seen_ids.add(material_id)
        if "latin" in item and latin is not None and not isinstance(latin, str):
            findings.append(f"{where}.latin is not a string")
        if "type" in item and kind is not None and not isinstance(kind, str):
            findings.append(f"{where}.type is not a string")
        elif isinstance(kind, str) and kind not in RANGES:
            findings.append(f"{where}.type {kind!r} is not a Flora range")
        latin_set = isinstance(latin, str)
        type_present = kind is not None
        if latin_set != type_present:
            findings.append(f"{where} latin and type must both be set or both be null")
        if isinstance(kind, str) and kind in RANGES and _is_int(material_id):
            low, high = RANGES[kind]
            if not low <= material_id <= high:
                findings.append(
                    f"{where}.material_id {material_id} is outside the {kind} range {low}-{high}"
                )
        if latin_set:
            if latin in seen_latin:
                findings.append(f"duplicate retired latin {latin}")
            else:
                seen_latin.add(latin)
    return findings


def _check_retired_latins(catalogue: dict) -> list[str]:
    retired = catalogue.get("retired_ids")
    if not isinstance(retired, list):
        return []
    active: set[str] = set()
    for item in catalogue.get("species", []):
        if isinstance(item, dict) and isinstance(item.get("latin"), str):
            active.add(item["latin"])
    gaps = catalogue.get("gaps")
    stand_in = gaps.get("project_species_shared_stand_in", []) if isinstance(gaps, dict) else []
    if isinstance(stand_in, list):
        for item in stand_in:
            if isinstance(item, dict) and isinstance(item.get("latin"), str):
                active.add(item["latin"])
    findings = []
    reported: set[str] = set()
    for item in retired:
        if not isinstance(item, dict) or not isinstance(item.get("latin"), str):
            continue
        latin = item["latin"]
        if latin in active and latin not in reported:
            findings.append(f"retired latin {latin} is also active")
            reported.add(latin)
    return findings


def _check_species(item: dict, where: str, retired: set, seen_ids: dict, seen_latin: dict, seen_names: dict) -> list[str]:
    findings: list[str] = []
    material_id = item.get("material_id")
    latin = item.get("latin")
    kind = item.get("type")
    if "material_id" in item and not _is_int(material_id):
        findings.append(f"{where}.material_id is not an int")
    if "latin" in item and not isinstance(latin, str):
        findings.append(f"{where}.latin is not a string")
    for key in ("russian", "geometry_basis", "note"):
        if key in item and not isinstance(item[key], str):
            findings.append(f"{where}.{key} is not a string")
    if "type" in item and not isinstance(kind, str):
        findings.append(f"{where}.type is not a string")
    elif isinstance(kind, str) and kind not in RANGES:
        findings.append(f"{where}.type {kind!r} is not a Flora range")
    if _is_int(material_id):
        if 1 <= material_id <= 100:
            findings.append(f"{where}.material_id {material_id} is in 1-100")
        if isinstance(kind, str) and kind in RANGES:
            low, high = RANGES[kind]
            if not low <= material_id <= high:
                findings.append(f"{where}.material_id {material_id} is outside the {kind} range {low}-{high}")
        if material_id in retired:
            findings.append(f"{where}.material_id {material_id} is retired")
        if material_id in seen_ids:
            findings.append(f"duplicate material_id {material_id}")
        else:
            seen_ids[material_id] = where
    if isinstance(latin, str):
        if latin in seen_latin:
            findings.append(f"duplicate latin {latin}")
        else:
            seen_latin[latin] = 1
    for key, kind_name in (("height_m", "number"), ("crown_diameter_m", "number")):
        if key in item and not _is_number(item[key]):
            findings.append(f"{where}.{key} is not a {kind_name}")
    findings.extend(_check_objects(item, where, seen_names))
    if "npm" in item:
        findings.extend(_check_source(item.get("npm"), f"{where}.npm"))
    if "vpm" in item and item["vpm"] is not None:
        findings.extend(_check_source(item["vpm"], f"{where}.vpm"))
    if "merged" in item:
        findings.extend(_check_merged(item.get("merged"), where))
    if "triangles" in item:
        findings.extend(_check_triangles(item.get("triangles"), where))
    if "source_scenes" in item:
        findings.extend(_check_scenes(item.get("source_scenes"), where))
    if "maps" in item:
        findings.extend(_check_maps(item.get("maps"), where))
    findings.extend(_check_vpm_status(item, where))
    findings.extend(_check_distinct_vpm(item, where))
    if item.get("geometry_basis") == "shared_multi_species_stand_in":
        findings.append(f"{where} is a shared stand-in and is not a library species")
    return findings


def _check_distinct_vpm(item: dict, where: str) -> list[str]:
    """Check disclosure only, never claim or infer geometric identity (#305)."""
    findings = []
    has_vpm = item.get("vpm") is not None
    if item.get("vpm_identity") != ("unverified" if has_vpm else None):
        findings.append(f"{where}.vpm_identity must be unverified for a VPM, otherwise null (see #305)")
    expected = {"relation": "unverified", "translation_dev_m": None, "scaled_dev_rel": None} if has_vpm else None
    if item.get("vpm_evidence") != expected:
        findings.append(f"{where}.vpm_evidence must disclose unverified identity without deviations (see #305)")
    return findings


def _check_vpm_status(item: dict, where: str) -> list[str]:
    if "vpm_status" not in item:
        return []
    status = item["vpm_status"]
    if status not in VPM_STATUS:
        return [f"{where}.vpm_status {status!r} is not available, unconfirmed or none"]
    has_vpm = item.get("vpm") is not None
    if (status == "available") != has_vpm:
        return [f"{where}.vpm_status {status!r} does not match vpm"]
    return []


def _check_objects(item: dict, where: str, seen_names: dict) -> list[str]:
    findings = []
    objects = item.get("objects")
    if "objects" not in item:
        return findings
    if not isinstance(objects, dict):
        return [f"{where}.objects is not an object"]
    findings.extend(_key_findings(objects, ("NPM", "VPM"), f"{where}.objects"))
    latin = item.get("latin")
    npm_name = objects.get("NPM")
    vpm_name = objects.get("VPM")
    if not isinstance(npm_name, str):
        findings.append(f"{where}.objects.NPM is not a string")
    if vpm_name is not None and not isinstance(vpm_name, str):
        findings.append(f"{where}.objects.VPM is not a string")
    if isinstance(latin, str) and isinstance(npm_name, str) and npm_name != object_name(latin, "NPM"):
        findings.append(f"{where}.objects.NPM {npm_name!r} != {object_name(latin, 'NPM')}")
    if isinstance(latin, str) and isinstance(vpm_name, str) and vpm_name != object_name(latin, "VPM"):
        findings.append(f"{where}.objects.VPM {vpm_name!r} != {object_name(latin, 'VPM')}")
    vpm = item.get("vpm", None)
    if "vpm" in item and (vpm is None) != (vpm_name is None):
        findings.append(f"{where}.objects.VPM does not match VPM availability")
    for name in (npm_name, vpm_name):
        if not isinstance(name, str):
            continue
        if name in seen_names:
            findings.append(f"duplicate object name {name}")
        else:
            seen_names[name] = where
    return findings


def _check_source(value, where: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where} is not an object"]
    findings = _key_findings(value, _SOURCE_KEYS, where)
    for key in ("entry_id", "scene", "source_name", "basis"):
        if key in value and not isinstance(value[key], str):
            findings.append(f"{where}.{key} is not a string")
    if "triangles" in value and not _is_int(value["triangles"]):
        findings.append(f"{where}.triangles is not an int")
    for key in ("height_m", "crown_diameter_m"):
        if key in value and not _is_number(value[key]):
            findings.append(f"{where}.{key} is not a number")
    return findings


def _check_merged(value, where: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{where}.merged is not a list"]
    findings = []
    for index, item in enumerate(value):
        slot = f"{where}.merged[{index}]"
        if not isinstance(item, dict):
            findings.append(f"{slot} is not an object")
            continue
        findings.extend(_key_findings(item, _MERGED_KEYS, slot))
        for key in _MERGED_KEYS:
            if key in item and not isinstance(item[key], str):
                findings.append(f"{slot}.{key} is not a string")
    return findings


def _check_triangles(value, where: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}.triangles is not an object"]
    findings = _key_findings(value, ("NPM", "VPM"), f"{where}.triangles")
    if "NPM" in value and not _is_int(value["NPM"]):
        findings.append(f"{where}.triangles.NPM is not an int")
    if "VPM" in value and value["VPM"] is not None and not _is_int(value["VPM"]):
        findings.append(f"{where}.triangles.VPM is not an int")
    return findings


def _check_scenes(value, where: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{where}.source_scenes is not a list"]
    findings = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            findings.append(f"{where}.source_scenes[{index}] is not a string")
    return findings


def _check_maps(value, where: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}.maps is not an object"]
    findings = _key_findings(value, _MAP_KEYS, f"{where}.maps")
    for key in ("diffuse", "opacity", "evidence"):
        if key in value and value[key] is not None and not isinstance(value[key], str):
            findings.append(f"{where}.maps.{key} is not a string")
    status = value.get("review_status")
    if "review_status" in value and status not in REVIEW_STATUS:
        findings.append(f"{where}.maps.review_status {status!r} is not approved, pending_review or missing")
    if status == "approved" and (not value.get("diffuse") or not value.get("opacity")):
        findings.append(f"{where}.maps approved without both diffuse and opacity paths")
    for key in ("diffuse", "opacity"):
        path = value.get(key)
        if not isinstance(path, str) or not path:
            continue
        if Path(path).suffix != ".png":
            findings.append(f"{where}.maps.{key} {path} extension is not .png")
        if _inside_repo(path):
            findings.append(f"{where}.maps.{key} {path} is inside the repository")
    return findings


def _inside_repo(path: str) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute():
        return True
    try:
        candidate.resolve().relative_to(REPO.resolve())
    except ValueError:
        return False
    return True


def _check_gaps(catalogue: dict) -> list[str]:
    gaps = catalogue.get("gaps")
    if not isinstance(gaps, dict):
        return ["gaps is not an object"]
    findings = _key_findings(gaps, _GAP_KEYS, "gaps")
    if "unresolved" in gaps:
        findings.extend(_check_unresolved(gaps["unresolved"]))
    species = catalogue.get("species")
    if not isinstance(species, list):
        return findings
    if "species_without_approved_maps" in gaps:
        expected = [
            item["latin"] for item in species
            if isinstance(item, dict) and isinstance(item.get("latin"), str)
            and isinstance(item.get("maps"), dict) and item["maps"].get("review_status") != "approved"
        ]
        if gaps["species_without_approved_maps"] != expected:
            findings.append("gaps.species_without_approved_maps does not match the species")
    if "project_species_shared_stand_in" in gaps:
        retired = _retired_material_ids(catalogue.get("retired_ids"))
        seen_ids = {}
        seen_latin = {}
        for item in species:
            if isinstance(item, dict) and _is_int(item.get("material_id")):
                seen_ids[item["material_id"]] = "species"
            if isinstance(item, dict) and isinstance(item.get("latin"), str):
                seen_latin[item["latin"]] = "species"
        findings.extend(_check_stand_in(gaps["project_species_shared_stand_in"], retired, seen_ids, seen_latin))
    return findings


def _check_unresolved(value) -> list[str]:
    if not isinstance(value, list):
        return ["gaps.unresolved is not a list"]
    findings = []
    for index, item in enumerate(value):
        where = f"gaps.unresolved[{index}]"
        if not isinstance(item, dict):
            findings.append(f"{where} is not an object")
            continue
        if not isinstance(item.get("status"), str):
            findings.append(f"{where}.status is not a string")
        names = item.get("source_names")
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            findings.append(f"{where}.source_names is not a list of strings")
    return findings


def _check_stand_in(value, retired: set, seen_ids: dict, seen_latin: dict) -> list[str]:
    if not isinstance(value, list):
        return ["gaps.project_species_shared_stand_in is not a list"]
    findings = []
    for index, item in enumerate(value):
        where = f"gaps.project_species_shared_stand_in[{index}]"
        if not isinstance(item, dict):
            findings.append(f"{where} is not an object")
            continue
        findings.extend(_key_findings(item, _STAND_IN_KEYS, where))
        latin = item.get("latin")
        kind = item.get("type")
        material_id = item.get("material_id")
        for key in ("latin", "russian", "type"):
            if key in item and not isinstance(item[key], str):
                findings.append(f"{where}.{key} is not a string")
        if "type" in item and isinstance(kind, str) and kind not in RANGES:
            findings.append(f"{where}.type {kind!r} is not a Flora range")
        if "status" in item and item["status"] != SHARED_STAND_IN_STATUS:
            findings.append(f"{where}.status is not the shared stand-in gap status")
        sources = item.get("sources")
        if "sources" in item and (
            not isinstance(sources, list) or not all(isinstance(source, str) for source in sources)
        ):
            findings.append(f"{where}.sources is not a list of strings")
        if isinstance(latin, str):
            if latin in seen_latin:
                findings.append(f"duplicate latin {latin}")
            else:
                seen_latin[latin] = where
        if "material_id" in item and not _is_int(material_id):
            findings.append(f"{where}.material_id is not an int")
        if not _is_int(material_id):
            continue
        if 1 <= material_id <= 100:
            findings.append(f"{where}.material_id {material_id} is in 1-100")
        if isinstance(kind, str) and kind in RANGES:
            low, high = RANGES[kind]
            if not low <= material_id <= high:
                findings.append(f"{where}.material_id {material_id} is outside the {kind} range {low}-{high}")
        if material_id in retired:
            findings.append(f"{where}.material_id {material_id} is retired")
        if material_id in seen_ids:
            findings.append(f"duplicate material_id {material_id}")
        else:
            seen_ids[material_id] = where
    return findings


def _check_counts(catalogue: dict) -> list[str]:
    counts = catalogue.get("counts")
    if not isinstance(counts, dict):
        return ["counts is not an object"]
    findings = _key_findings(counts, _COUNT_KEYS, "counts")
    species = catalogue.get("species")
    if not isinstance(species, list) or not all(isinstance(item, dict) for item in species):
        return findings
    if "species" in counts and counts["species"] != len(species):
        findings.append("counts.species does not match the species list")
    if isinstance(counts.get("by_type"), dict):
        findings.extend(_key_findings(counts["by_type"], tuple(RANGES), "counts.by_type"))
        for kind in RANGES:
            actual = sum(1 for item in species if item.get("type") == kind)
            if counts["by_type"].get(kind) != actual:
                findings.append(f"counts.by_type.{kind} does not match the species list")
    elif "by_type" in counts:
        findings.append("counts.by_type is not an object")
    if "with_vpm" in counts:
        actual = sum(1 for item in species if item.get("vpm") is not None)
        if counts["with_vpm"] != actual:
            findings.append("counts.with_vpm does not match the species list")
    if "merged_duplicates" in counts:
        actual = sum(len(item["merged"]) for item in species if isinstance(item.get("merged"), list))
        if counts["merged_duplicates"] != actual:
            findings.append("counts.merged_duplicates does not match the species list")
    maps = counts.get("maps")
    if isinstance(maps, dict):
        findings.extend(_key_findings(maps, REVIEW_STATUS, "counts.maps"))
        for status in REVIEW_STATUS:
            actual = sum(
                1 for item in species
                if isinstance(item.get("maps"), dict) and item["maps"].get("review_status") == status
            )
            if maps.get(status) != actual:
                findings.append(f"counts.maps.{status} does not match the species list")
    elif "maps" in counts:
        findings.append("counts.maps is not an object")
    gaps = catalogue.get("gaps") if isinstance(catalogue.get("gaps"), dict) else {}
    stand_in = gaps.get("project_species_shared_stand_in")
    unresolved = gaps.get("unresolved")
    if "shared_stand_in_gaps" in counts and isinstance(stand_in, list):
        if counts["shared_stand_in_gaps"] != len(stand_in):
            findings.append("counts.shared_stand_in_gaps does not match the gap list")
    if "unresolved" in counts and isinstance(unresolved, list):
        if counts["unresolved"] != len(unresolved):
            findings.append("counts.unresolved does not match the gap list")
    return findings


if __name__ == "__main__":
    main()
