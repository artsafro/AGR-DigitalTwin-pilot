"""Flora NPM/VPM surface-identity report over the library catalogue - report only, the catalogue is not changed.

Pattern: n/a | new-case: Flora NPM/VPM surface-identity report - one row per catalogue species, fail-closed (#305).

Input: ``library/flora/catalogue.json`` and a face dump of the library objects
(``tools/flora/dump_flora_library_faces.py``: ``{"entries": {object_name: {"triangles": [...]}}, "failures": [...]}``).
Every catalogue species gets exactly one row. Verdicts are those of ``dt_ai.geometry.surface_identity`` plus
``no_vpm`` for a species without a VPM object; a missing or unusable mesh is ``error``, never dropped.

    uv run python -m dt_ai.materials.flora_surface_report --catalogue library/flora/catalogue.json \
        --faces C:/x/ev_<card>/flora-library-faces.json --out library/flora/vpm-surface-identity.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from dt_ai.geometry import surface_identity as si

SCHEMA = "flora-vpm-surface-identity-report-v1"
ROW_VERDICTS = si.VERDICTS + ("no_vpm",)


class ReportError(ValueError):
    pass


def build_report(catalogue: dict, faces: dict, *, sources: dict | None = None) -> dict:
    if not isinstance(catalogue, dict) or not isinstance(catalogue.get("species"), list):
        raise ReportError("catalogue has no species list")
    if not isinstance(faces, dict) or not isinstance(faces.get("entries"), dict):
        raise ReportError("face dump has no entries object")
    failures = faces.get("failures")
    if not isinstance(failures, list):
        raise ReportError("face dump has no failures list")
    failed = {str(item.get("object")): str(item.get("reason")) for item in failures if isinstance(item, dict)}
    entries = faces["entries"]
    rows = []
    for index, item in enumerate(catalogue["species"]):
        if not isinstance(item, dict):
            raise ReportError(f"species[{index}] is not an object")
        rows.append(_row(item, entries, failed))
    counts = {verdict: sum(row["verdict"] == verdict for row in rows) for verdict in ROW_VERDICTS}
    if sum(counts.values()) != len(catalogue["species"]):
        raise ReportError("report rows do not match the catalogue species")
    return {
        "schema": SCHEMA,
        "scope": "report only; catalogue.json is not changed - catalogue changes are a user decision (#305)",
        "method": (
            "two-way area coverage per face (shapely clipping), D100 pivot frame, strict tolerance; "
            "same only if both uncovered areas and the face-area difference are <= same_area_m2"
        ),
        "tolerance_m": si.TOLERANCE_M,
        "same_area_m2": si.SAME_AREA_M2,
        "different_area_m2": si.DIFFERENT_AREA_M2,
        "sources": sources or {},
        "counts": {"species": len(rows), **counts},
        "pairs": rows,
    }


def _row(item: dict, entries: dict, failed: dict) -> dict:
    objects = item.get("objects") if isinstance(item.get("objects"), dict) else {}
    npm_name = objects.get("NPM")
    vpm_name = objects.get("VPM") if item.get("vpm") is not None else None
    row = {
        "material_id": item.get("material_id"),
        "latin": item.get("latin"),
        "npm_object": npm_name,
        "vpm_object": vpm_name,
        "vpm_status": item.get("vpm_status"),
        "catalogue_vpm_identity": item.get("vpm_identity"),
        "verdict": "error",
        "reason": "",
        "npm": None,
        "vpm": None,
        "area_difference_m2": None,
    }
    if vpm_name is None:
        row["verdict"] = "no_vpm"
        row["reason"] = "catalogue species has no VPM object"
        return row
    missing = [name for name in (npm_name, vpm_name) if not isinstance(name, str) or name not in entries]
    if missing:
        row["reason"] = "; ".join(
            f"no faces for {name!r}" + (f" ({failed[name]})" if name in failed else "") for name in missing
        )
        return row
    npm_faces, vpm_faces = (entries[name].get("triangles") if isinstance(entries[name], dict) else None
                            for name in (npm_name, vpm_name))
    compared = si.compare_surfaces(npm_faces, vpm_faces)
    row["verdict"] = compared["verdict"]
    row["reason"] = compared["reason"]
    row["npm"] = compared["a"]
    row["vpm"] = compared["b"]
    row["area_difference_m2"] = compared["area_difference_m2"]
    return row


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _same_file(left: str, right: str) -> bool:
    a, b = Path(left).resolve(), Path(right).resolve()
    if a == b:
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flora NPM/VPM surface-identity report (report only).")
    parser.add_argument("--catalogue", required=True)
    parser.add_argument("--faces", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    for name in (args.catalogue, args.faces):
        if _same_file(args.out, name):
            print(f"refused: --out resolves to the input {name}")
            return 2
    try:
        with open(args.catalogue, encoding="utf-8") as handle:
            catalogue = json.load(handle)
        with open(args.faces, encoding="utf-8") as handle:
            faces = json.load(handle)
        report = build_report(catalogue, faces, sources={
            "catalogue": Path(args.catalogue).as_posix(),
            "catalogue_sha256": _sha256(args.catalogue),
            "faces": Path(args.faces).as_posix(),
            "faces_sha256": _sha256(args.faces),
            "library_file": faces.get("library_file"),
            "library_sha256": faces.get("library_sha256"),
        })
    except (OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 1
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print(" ".join(f"{key}={value}" for key, value in report["counts"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
