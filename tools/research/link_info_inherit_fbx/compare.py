"""SYNTHETIC Q10 test: compare each node's world vertices in Max with the FBX readbacks (Blender, Max re-import).

    py -3 compare.py <out_dir>

Inputs in <out_dir>: max_<v>.json, blender_<v>.json (tools/blender/fbx_readback.py), maxreimport_<v>.json, v in raw/baked.
Per node: max vertex distance in mm (same vertex index; order-free nearest-neighbour as a cross-check), max angle
between centroid->vertex directions in degrees, centroid shift in mm. Pass: <= 1 mm and <= 0.01 deg.
Prints a Markdown table and writes compare.json.
Pattern: new-case (standalone synthetic Link Info/FBX experiment).
"""
import json
import math
import sys
from pathlib import Path

TOL_MM, TOL_DEG = 1.0, 0.01


def dist(a, b):
    return math.dist(a, b)


def centroid(pts):
    return [sum(p[i] for p in pts) / len(pts) for i in range(3)]


def angle_deg(u, v):
    nu, nv = math.hypot(*u), math.hypot(*v)
    if nu == 0 or nv == 0:
        return 0.0
    c = max(-1.0, min(1.0, sum(a * b for a, b in zip(u, v)) / (nu * nv)))
    return math.degrees(math.acos(c))


def compare(ref, got):
    if len(ref) != len(got):
        return {"error": f"vertex count {len(ref)} vs {len(got)}"}
    by_index = max(dist(a, b) for a, b in zip(ref, got)) * 1000
    nearest = max(min(dist(a, b) for b in got) for a in ref) * 1000
    cr, cg = centroid(ref), centroid(got)
    ang = max(angle_deg([a[i] - cr[i] for i in range(3)], [b[i] - cg[i] for i in range(3)]) for a, b in zip(ref, got))
    shift = dist(cr, cg) * 1000
    return {"max_vertex_mm": by_index, "nearest_mm": nearest, "max_angle_deg": ang, "centroid_shift_mm": shift,
            "pass": by_index <= TOL_MM and ang <= TOL_DEG}


def main(out_dir):
    out = Path(out_dir)
    result = {}
    lines = []
    for variant in ("raw", "baked"):
        mx = json.loads((out / f"max_{variant}.json").read_text(encoding="utf-8"), strict=False)
        bl = json.loads((out / f"blender_{variant}.json").read_text(encoding="utf-8"), strict=False)
        mr = json.loads((out / f"maxreimport_{variant}.json").read_text(encoding="utf-8"), strict=False)
        bl_nodes = {m["name"]: m["face_geometry"]["vertices"] for m in bl["meshes"]}
        mr_nodes = {n["name"]: n["world_verts"] for n in mr["nodes"]}
        rows = []
        for node in mx["nodes"]:
            ref = node["world_verts"]
            row = {"name": node["name"], "inherit": node["inherit"],
                   "max_centroid_m": [round(c, 4) for c in centroid(ref)],
                   "blender": compare(ref, bl_nodes[node["name"]]) if node["name"] in bl_nodes else {"error": "missing"},
                   "max_reimport": compare(ref, mr_nodes[node["name"]]) if node["name"] in mr_nodes else {"error": "missing"}}
            if node["name"] in bl_nodes:
                row["blender_centroid_m"] = [round(c, 4) for c in centroid(bl_nodes[node["name"]])]
            if node["name"] in mr_nodes:
                row["max_reimport_centroid_m"] = [round(c, 4) for c in centroid(mr_nodes[node["name"]])]
            rows.append(row)
        result[variant] = rows
        lines.append(f"\n### {variant}\n")
        lines.append("| Node | Inherit (move/rot/scale XYZ) | Max centroid, m | Blender centroid, m | Blender max vertex delta, mm "
                     "| Blender max angle, deg | Max re-import max vertex delta, mm | Max re-import angle, deg | Verdict |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            b, m = r["blender"], r["max_reimport"]
            ok = b.get("pass") and m.get("pass")
            flags = "".join(str(x) for x in r["inherit"])
            b_delta = b["error"] if "error" in b else f"{b['max_vertex_mm']:.3f}"
            m_delta = m["error"] if "error" in m else f"{m['max_vertex_mm']:.3f}"
            lines.append(f"| {r['name']} | {flags[:3]} {flags[3:6]} {flags[6:]} | {r['max_centroid_m']} "
                         f"| {r.get('blender_centroid_m')} | {b_delta} "
                         f"| {b.get('max_angle_deg', 0):.4f} | {m_delta} "
                         f"| {m.get('max_angle_deg', 0):.4f} | {'match' if ok else 'MISMATCH'} |")
    (out / "compare.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
