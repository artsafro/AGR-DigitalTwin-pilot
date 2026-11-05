"""elv-tc-vpm: read-only diagnostic - what surface is behind each fixture (raycast on the Main mesh of a build blend).

blender -b outputs/build-v003/elv_full_v003.blend --python scripts/light_diag.py -- <out.json>
Per run: samples every 0.5 m (u on its outline), horizontal ray from 1.0 m outside towards the outline; reports the
surface offset from the outline (+ = proud), the slot name and the part; plus an upward ray (5 cm outside the hit) to
the first overhang above (cap / soffit) for runs at a parapet.
"""
import bpy, sys, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from light_paths import runs_and_points, POLYS  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
LAY = json.load(open(os.path.join(HERE, "..", "parts", "lighting_layout_v001.json"), encoding="utf-8"))
ob = bpy.data.objects["SM_Elevatornaya_1A_Main"]
me = ob.data
parts = json.loads(ob["part_ids"])
att = me.attributes["part_idx"].data
bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])


def probe(pk, u, z):
    poly = POLYS[pk]
    b = poly.base(u)
    n = poly.unit_normal(u)
    o = Vector((b[0] + n[0], b[1] + n[1], z))
    loc, nrm, fi, d = bvh.ray_cast(o, Vector((-n[0], -n[1], 0)), 3.0)
    if loc is None:
        return {"u": round(u, 2), "hit": None}
    p = me.polygons[fi]
    r = {"u": round(u, 2), "off": round(1.0 - d, 3), "slot": me.materials[p.material_index].name[:4],
         "part": parts[att[fi].value][:12]}
    up = bvh.ray_cast(loc + Vector((n[0], n[1], 0)) * 0.05, Vector((0, 0, 1)), 1.5)
    if up[0] is not None:
        r["up_z"] = round(up[0].z, 3)
        r["up_part"] = parts[att[up[2]].value][:12]
    return r


runs, pts = runs_and_points(LAY)
rep = {"runs": [], "points": []}
for r in runs:
    us = [r["u0"] + (r["u1"] - r["u0"]) * k / max(1, int((r["u1"] - r["u0"]) / 0.5)) for k in
          range(max(1, int((r["u1"] - r["u0"]) / 0.5)) + 1)]
    smp = [probe(r["poly"], u, r["z"] - 0.06) for u in us]
    offs = [s["off"] for s in smp if s.get("off") is not None]
    rep["runs"].append({**r, "n": len(smp), "off_min": min(offs) if offs else None, "off_max": max(offs) if offs else None,
                        "slots": sorted({s.get("slot") for s in smp if s.get("slot")}),
                        "parts": sorted({s.get("part") for s in smp if s.get("part")}),
                        "up_z": sorted({s.get("up_z") for s in smp if s.get("up_z")}),
                        "misses": sum(1 for s in smp if s.get("hit", 1) is None),
                        "big": [s for s in smp if s.get("off") is not None and abs(s["off"]) > 0.03][:6]})
for p in pts:
    s = probe(p["poly"], p["u"], p["z"])
    rep["points"].append({**p, **s})
json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1)
for r in rep["runs"]:
    print("RUN", r["id"], r["type"], r["poly"], round(r["u0"], 2), round(r["u1"], 2), r["z"], "off", r["off_min"],
          r["off_max"], r["slots"], r["parts"], "up", r["up_z"][:5], "miss", r["misses"], "split", r["split"],
          "big", [(b["u"], b["off"], b["part"]) for b in r["big"]])
for p in rep["points"]:
    print("PT", p["id"], p["type"], p["poly"], round(p["u"], 2), p["z"], p.get("off"), p.get("slot"), p.get("part"),
          p.get("up_z"), p.get("up_part"))
