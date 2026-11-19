"""One roof/parapet seam check (#1381; VPM route red block `parapet-seam`; R6 step 4, #1352 / D292).

Pattern: roof-inset-plane | new-case: one verdict over the roof/parapet seam facts that were measured by separate
job scripts before: the K01 KPP1 geometry runner (jobs/KPP1/seam-1339/measure_roof_seam.py, #1339) and the SREDA
texture-joint checker (jobs/elv-tc-vpm/scripts/joint_continuity_v008.py). It sits next to the BODY seam owner
tools/blender/seam_seal.py. Pure Python, no DCC: the counts come from those measurements (or any readback with
the same keys). It repairs nothing.

R6 step 4 is done when the exported file read back shows: T-junctions 0, non-manifold 0, `slabs_not_inset` 0,
no open loop that is not allowed and every open loop closed. The texture joint under the parapet must meet:
unmatched joint crossings 0 (SREDA had 423 on 95 edges in the v004 Max review, 4 after the v005 rework).
Verdict: `pass` only when every count is 0; `fail` when any count is > 0; `incomplete` when nothing failed but a
count is explicitly `null` (not measured). A missing or unknown key, a bool, a negative, fractional or non-finite
count is a ValueError naming the key, never a pass.

    python tools/qa/roof_parapet_seam.py --counts COUNTS.json --output NEW.json
Exit 0 pass, 1 fail or incomplete, 2 input error (nothing written). The output must not exist and must not be the
input; it is written through a `.partial` file next to it.
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

KEYS = ("t_junctions", "non_manifold", "slabs_not_inset", "open_loops_not_allowed", "open_loops_not_closed",
        "texture_joint_unmatched")
RU = {"t_junctions": "Т-узлы на шве", "non_manifold": "неманифолдные рёбра", "slabs_not_inset": "плита не врезана",
      "open_loops_not_allowed": "лишние открытые контуры", "open_loops_not_closed": "незамкнутые открытые контуры",
      "texture_joint_unmatched": "несовпадения стыков текстуры под парапетом"}
# Measured input (#1381): earlier measurements, reported as they are; the delivered objects are not repaired.
MEASURED_INPUT = (
    {"object": "KPP1 K01 welded (#1339 before)", "source": "jobs/KPP1/seam-1339/seam-report.json"},
    {"object": "KPP1 K01 separate (#1339 after)", "source": "jobs/KPP1/seam-1339/seam-report.json"},
    {"object": "SREDA elv-tc-vpm v004", "source": "docs/retros/2026-11-05-elv-tc-vpm-claude.md",
     "texture_joint_unmatched": 423, "edges_with_unmatched": 95},
    {"object": "SREDA elv-tc-vpm v005", "source": "docs/retros/2026-11-05-elv-tc-vpm-claude.md",
     "texture_joint_unmatched": 4},
)

# geometry measure of the #1339 runner (moved here unchanged, #1381)
T_TOL_M = 1e-4          # a vertex closer than 0.1 mm to another polygon's edge is a T-junction (plate gap is 5 mm)
ROOF_BAND_M = 0.02      # roof-band triangles: horizontal, within 20 mm of the roof level (hole 7.909, plate 7.914)
FLAT_M = 1e-4          # horizontal triangle: z spread within 0.1 mm (FBX readback is float32)


def measure(dump, roof_z):
    """Counts of one mesh dump (engine dump or readback): body quads/polygons/triangles, roof-band triangles,
    T-junctions. Fail closed: no `body` mesh, an empty one or a non-finite coordinate is a ValueError."""
    from twinqa.look import _t_junction_count
    if not (isinstance(roof_z, (int, float)) and math.isfinite(roof_z)):
        raise ValueError(f"roof level {roof_z!r} is not a finite number")
    bodies = [m for m in dump.get("meshes", []) if m.get("name") == "body"]
    if len(bodies) != 1:
        raise ValueError(f"expected one mesh 'body', found {len(bodies)}")
    body = bodies[0]
    verts, tris = body.get("vertices") or [], body.get("triangles") or []
    if not verts or not tris:
        raise ValueError("mesh 'body' is empty")
    if not all(math.isfinite(c) for v in verts for c in v):
        raise ValueError("mesh 'body' has a non-finite vertex coordinate")
    sizes = body.get("polygon_sizes") or []
    band = 0
    for t in tris:
        zs = [verts[i][2] for i in t]
        if max(zs) - min(zs) <= FLAT_M and abs(zs[0] - roof_z) <= ROOF_BAND_M:
            band += 1
    return {"quads": sum(1 for s in sizes if s == 4), "polygons": len(sizes), "ngons": sum(1 for s in sizes if s > 4),
            "triangles": len(tris), "roof_band_triangles": band,
            "t_junctions": _t_junction_count([list(v) for v in verts], [list(t) for t in tris], T_TOL_M)}


def _count(key, value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or value < 0 or value != int(value):
        raise ValueError(f"{key}: {value!r} is not a count (integer >= 0 or null = not measured)")
    return int(value)


def verdict(counts):
    """{key: count | None} with exactly KEYS -> {'status': pass|fail|incomplete, 'counts', 'problems', 'not_measured'}."""
    if not isinstance(counts, dict):
        raise ValueError("counts must be a JSON object")
    missing = [k for k in KEYS if k not in counts]
    unknown = sorted(set(counts) - set(KEYS))
    if missing or unknown:
        raise ValueError("counts: missing " + ", ".join(missing) + "; unknown " + ", ".join(unknown))
    clean = {k: _count(k, counts[k]) for k in KEYS}
    problems = [{"key": k, "value": v, "ru": RU[k]} for k, v in clean.items() if v]
    not_measured = [k for k, v in clean.items() if v is None]
    status = "fail" if problems else "incomplete" if not_measured else "pass"
    return {"status": status, "counts": clean, "problems": problems, "not_measured": not_measured}


def from_seam_report(variant):
    """Counts of one #1339 seam-report variant (readback + K01 `mesh` check); the texture joint was not measured."""
    mesh, rb = variant["mesh"], variant["readback"]
    value = mesh["value"]
    return {"t_junctions": rb["t_junctions"], "non_manifold": value["non_manifold"],
            "slabs_not_inset": value["slabs_not_inset"], "open_loops_not_allowed": value["open_loops_not_allowed"],
            "open_loops_not_closed": sum(1 for lp in mesh["open_loops"] if not lp["closed"]),
            "texture_joint_unmatched": None}


def joint_unmatched(report):
    """Unmatched joint crossings from a joint_continuity report (`total.unmatched_crossings`)."""
    total = report.get("total") if isinstance(report, dict) else None
    value = total.get("unmatched_crossings") if isinstance(total, dict) else None
    if value is None:
        raise ValueError("joint report: total.unmatched_crossings missing")
    return _count("texture_joint_unmatched", value)


def _reject_constant(name):
    raise ValueError(f"non-finite JSON number {name}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--counts", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args(argv)
    try:
        src, out = a.counts.resolve(), a.output.resolve()
        if out == src or out.exists() or Path(str(out) + ".partial").exists():
            raise ValueError(f"output {a.output} exists or is the input; give a new path")
        if not src.is_file():
            raise ValueError(f"counts {a.counts} does not exist")
        result = verdict(json.loads(src.read_text(encoding="utf-8"), parse_constant=_reject_constant))
    except ValueError as exc:   # json.JSONDecodeError is a ValueError
        print(f"roof_parapet_seam: {exc}", file=sys.stderr)
        return 2
    result["input"] = str(a.counts)
    tmp = Path(str(out) + ".partial")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, out)
    print(f"roof/parapet seam: {result['status']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
