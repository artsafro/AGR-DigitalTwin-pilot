"""Checks for generated MAF FBX (#790, gate #817): readback JSON -> maf_findings, dimension verdict, atlas-slot measurement.

    uv run python tools/library/maf_gen_bench_checks.py <build-report.json> <readback_dir> <out.json> [--reference <ref.json>]

Pattern: new-case: generated MAF verification - reads the fbx_readback.py JSON of every NPM/VPM FBX named in the
build report (`<readback_dir>/<role>_<set_id>.json`), runs twinqa.maf_checks.maf_findings (smoothing threshold
from the report), compares the readback bbox with a reference size within 0.10 m per axis [D094] and counts faces
whose UV leaves their material's 512 atlas slot (tools/library/maf_site_set.uv_slot_report).

Reference size: `--reference` names a JSON `{"rows": {"<row>": {"size_m": [x, y, z], "basis": "schedule" |
"dwg_outline", "source": "<where the size comes from>"}}}` in the readback axis order; every row of the build
report must have an entry (an unused entry is listed in the report). Without `--reference` the size is the
generator's own `generator_facts.dims_m` (basis "generator": a round-trip self-check, not a [D094] check).
Each row records the reference it used.

Exit codes: 0 every row/role passes (dimension, every maf_findings status "pass", no UV face outside its slot);
1 any of them fails (the report is still written, `verdict` "fail" and `failures` name each one);
2 input error or refused output (existing file, or a path that is one of the inputs) - nothing is written.
The overlap gate is separate (`dt qa xview`).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from twinqa.maf_checks import DIMENSION_TOL_M, maf_findings  # noqa: E402

_spec = importlib.util.spec_from_file_location("maf_site_set", ROOT / "tools/library/maf_site_set.py")
mss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mss)

BASES = ("schedule", "dwg_outline")
ROLES = ("npm", "vpm")


class InputError(ValueError):
    """Bad or missing input: exit 2, nothing written."""


def _size3(value, label):
    if not isinstance(value, list) or len(value) != 3 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in value):
        raise InputError(f"{label}: size_m must be three finite positive numbers, got {value!r}")
    return [float(v) for v in value]


def load_reference(data, rows: list[int]) -> tuple[dict, list[str]]:
    """Validate the reference JSON against the build-report rows -> ({row: entry}, unused keys)."""
    if not isinstance(data, dict) or not isinstance(data.get("rows"), dict):
        raise InputError("reference: expected {\"rows\": {\"<row>\": {...}}}")
    table = data["rows"]
    out = {}
    for row in rows:
        key = str(row)
        label = f"reference row {key}"
        entry = table.get(key)
        if not isinstance(entry, dict):
            raise InputError(f"{label}: no entry for build-report row {key}")
        size = _size3(entry.get("size_m"), label)
        if entry.get("basis") not in BASES:
            raise InputError(f"{label}: basis {entry.get('basis')!r} not in {BASES}")
        source = entry.get("source")
        if not isinstance(source, str) or not source.strip():
            raise InputError(f"{label}: source must be a non-empty string")
        out[row] = {"basis": entry["basis"], "source": source, "size_m": size}
    used = {str(r) for r in rows}
    unused = sorted((k for k in table if k not in used), key=lambda k: (len(k), k))
    return out, unused


def _read_json(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError(f"{label}: missing {path}") from None
    except (OSError, ValueError) as exc:
        raise InputError(f"{label}: cannot read {path}: {exc}") from None


def check(report: dict, readback_dir: Path, rects: dict, reference: dict | None = None) -> dict:
    rows = report.get("rows")
    if not isinstance(rows, list) or not rows:
        raise InputError("build report: no rows to check")
    out = {"smoothing_deg": report["smoothing_deg"], "tol_m": DIMENSION_TOL_M, "rows": []}
    for row in rows:
        if reference is not None:
            ref = reference[row["row"]]
        else:
            ref = {"basis": "generator", "source": "generator_facts.dims_m (round-trip self-check, not [D094])",
                   "size_m": row["generator_facts"]["dims_m"]}
        want = ref["size_m"]
        entry = {"row": row["row"], "set_id": row["set_id"], "expected_m": want, "reference": ref}
        for role in ROLES:
            path = readback_dir / f"{role}_{row['set_id']}.json"
            meshes = _read_json(path, f"readback {role} row {row['row']}").get("meshes")
            if not meshes:
                raise InputError(f"readback {path.name}: no meshes")
            lo = [min(m["bounds_m"][0][i] for m in meshes) for i in range(3)]
            hi = [max(m["bounds_m"][1][i] for m in meshes) for i in range(3)]
            size = [hi[i] - lo[i] for i in range(3)]
            dev = [abs(size[i] - want[i]) for i in range(3)]
            name = meshes[0]["name"]
            found = maf_findings(meshes, "ground", f"{role}/{row['set_id']}.fbx",
                                 smoothing_angle_deg=report["smoothing_deg"], maf_sizes={name: want})
            faces = []
            for m in meshes:
                fg = m["face_geometry"]
                for mat, uv in zip(fg["polygon_material"], fg["polygon_uv"]):
                    faces.append((mat[4:] if mat and mat.startswith("MAF_") else mat, uv))
            # all() and not max(): max() drops a NaN that is not first; a NaN deviation must fail
            ok = all(math.isfinite(d) and d <= DIMENSION_TOL_M for d in dev)
            entry[role] = {"name": name, "triangles": sum(m["triangles"] for m in meshes),
                           "size_m": size, "deviation_m": dev,
                           "dimension": "pass" if ok else "fail",
                           "maf_findings": {f.name: {"status": f.status, "observed": f.observed} for f in found},
                           "maf_findings_counts": dict(Counter(f.status for f in found)),
                           "uv_slots": mss.uv_slot_report(faces, rects)}
        out["rows"].append(entry)
    return out


def failures(res: dict) -> list[str]:
    """Every row/role/check that is not a pass; an empty list means the gate passes."""
    bad = []
    for row in res["rows"]:
        for role in ROLES:
            e = row[role]
            where = f"row {row['row']} {row['set_id']} {role}"
            if e["dimension"] != "pass":
                dev = [round(d, 4) if math.isfinite(d) else str(d) for d in e["deviation_m"]]
                bad.append(f"{where}: dimension deviation {dev} m vs {row['reference']['basis']} "
                           f"over {DIMENSION_TOL_M} m")
            if not e["maf_findings"]:
                bad.append(f"{where}: maf_findings empty")
            for name, f in e["maf_findings"].items():
                if f["status"] != "pass":
                    bad.append(f"{where}: maf_findings {name} {f['status']}")
            if e["uv_slots"]["faces_outside"]:
                bad.append(f"{where}: uv {e['uv_slots']['faces_outside']} faces outside the slot")
    return bad


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve() or (a.exists() and b.exists() and a.samefile(b))
    except OSError:
        return False


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report")
    ap.add_argument("readback_dir")
    ap.add_argument("out")
    ap.add_argument("--reference")
    args = ap.parse_args(argv)
    out = Path(args.out)
    try:
        report_path = Path(args.report)
        inputs = [report_path] + ([Path(args.reference)] if args.reference else [])
        if out.exists() or any(_same(out, p) for p in inputs):
            raise InputError(f"refusing to overwrite {out}")
        report = _read_json(report_path, "build report")
        atlas_path = Path(report["atlas_uv_json"])
        if _same(out, atlas_path):
            raise InputError(f"refusing to write {out} onto the atlas input")
        atlas = _read_json(atlas_path, "atlas")
        rects = {n: m["uv"] for n, m in atlas["materials"].items()}
        reference, unused = None, []
        if args.reference:
            rows = [r["row"] for r in report.get("rows") or []]
            reference, unused = load_reference(_read_json(Path(args.reference), "reference"), rows)
        res = check(report, Path(args.readback_dir), rects, reference)
    except (InputError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    bad = failures(res)
    res = {"verdict": "fail" if bad else "pass", "failures": bad,
           "reference_file": str(Path(args.reference).resolve()) if args.reference else None,
           "reference_rows_unused": unused, **res}
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for row in res["rows"]:
        for role in ROLES:
            e = row[role]
            print(row["set_id"], role, e["triangles"], [round(v, 3) for v in e["size_m"]], e["dimension"],
                  "vs", row["reference"]["basis"], e["maf_findings_counts"],
                  "uv outside", e["uv_slots"]["faces_outside"])
    if not args.reference:
        print("note: no --reference, sizes checked against the generator's own dims only", file=sys.stderr)
    print("verdict:", res["verdict"])
    for b in bad:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
