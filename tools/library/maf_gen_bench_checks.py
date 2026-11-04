"""Checks for generated MAF FBX (#790): readback JSON -> maf_findings, dimension verdict, atlas-slot measurement.

    uv run python tools/library/maf_gen_bench_checks.py <build-report.json> <readback_dir> <out.json>

Pattern: new-case: generated MAF verification - reads the fbx_readback.py JSON of every NPM/VPM FBX named in the
build report (`<readback_dir>/<role>_<set_id>.json`), runs twinqa.maf_checks.maf_findings (smoothing threshold
from the report), compares the readback bbox with the generator's own plan size within 0.10 m per axis [D094]
and counts faces whose UV leaves their material's 512 atlas slot (tools/library/maf_site_set.uv_slot_report).
The overlap gate is separate (`dt qa xview`). Writes a new JSON; refuses to overwrite (exit 2).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from twinqa.maf_checks import DIMENSION_TOL_M, maf_findings  # noqa: E402

_spec = importlib.util.spec_from_file_location("maf_site_set", ROOT / "tools/library/maf_site_set.py")
mss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mss)


def check(report: dict, readback_dir: Path, rects: dict) -> dict:
    out = {"smoothing_deg": report["smoothing_deg"], "tol_m": DIMENSION_TOL_M, "rows": []}
    for row in report["rows"]:
        want = row["generator_facts"]["dims_m"]
        entry = {"row": row["row"], "set_id": row["set_id"], "expected_m": want}
        for role in ("npm", "vpm"):
            rb = json.loads((readback_dir / f"{role}_{row['set_id']}.json").read_text(encoding="utf-8"))
            meshes = rb["meshes"]
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
            entry[role] = {"name": name, "triangles": sum(m["triangles"] for m in meshes),
                           "size_m": size, "deviation_m": dev,
                           "dimension": "pass" if max(dev) <= DIMENSION_TOL_M else "fail",
                           "maf_findings": {f.name: {"status": f.status, "observed": f.observed} for f in found},
                           "maf_findings_counts": dict(Counter(f.status for f in found)),
                           "uv_slots": mss.uv_slot_report(faces, rects)}
        out["rows"].append(entry)
    return out


def main(argv):
    report = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    out = Path(argv[2])
    if out.exists():
        print("refusing to overwrite", out, file=sys.stderr)
        return 2
    atlas = json.loads(Path(report["atlas_uv_json"]).read_text(encoding="utf-8"))
    rects = {n: m["uv"] for n, m in atlas["materials"].items()}
    res = check(report, Path(argv[1]), rects)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for row in res["rows"]:
        for role in ("npm", "vpm"):
            e = row[role]
            print(row["set_id"], role, e["triangles"], [round(v, 3) for v in e["size_m"]], e["dimension"],
                  e["maf_findings_counts"], "uv outside", e["uv_slots"]["faces_outside"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
