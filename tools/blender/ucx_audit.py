"""UCX collision audit of a delivered VPM FBX in an isolated factory Blender process.

    blender --background --factory-startup --python-exit-code 1 \
        --python tools/blender/ucx_audit.py -- <model.fbx> <report.json> [samples]

Measures (does not judge, never writes the source): per UCX piece kind (box_aabb /
box_oriented / convex / custom), triangles, size; naming against reg p.34 §4.2; pairwise
overlap / touch / gap (reg p.36 §13.4) for neighbours; Main coverage: area-weighted points
on the Main surface either inside a UCX piece or at a distance from the nearest piece
(reg p.36 §13.5 tolerances 0.3 m / 1 m), and the reverse distance from UCX surface to the
Main surface (collision standing in the air). Geometry helpers: src/twinqa/geometry/ucx_audit.py.
"""
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ucx_audit", ROOT / "src/twinqa/geometry/ucx_audit.py")
ua = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ua)

args = sys.argv[sys.argv.index("--") + 1:]
source, out = Path(args[0]).resolve(), Path(args[1]).resolve()
SAMPLES = int(args[2]) if len(args) > 2 else 20000
BANDS = (0.01, 0.3, 1.0)  # covered / pedestrian-zone tolerance / other OKS tolerance (reg p.36 §13.5)


def world_mesh(obj):
    me = obj.data
    me.calc_loop_triangles()
    mw = obj.matrix_world
    verts = [tuple(mw @ v.co) for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    return verts, tris


def tri_area(a, b, c):
    return ((Vector(b) - Vector(a)).cross(Vector(c) - Vector(a))).length / 2


def sample_surface(verts, tris, n, rng):
    areas = [tri_area(verts[a], verts[b], verts[c]) for a, b, c in tris]
    total = sum(areas)
    if total <= 0:
        return [], 0.0
    cum, acc = [], 0.0
    for x in areas:
        acc += x
        cum.append(acc)
    pts = []
    import bisect
    for _ in range(n):
        i = min(bisect.bisect_left(cum, rng.random() * total), len(tris) - 1)
        a, b, c = (Vector(verts[k]) for k in tris[i])
        r1, r2 = rng.random(), rng.random()
        if r1 + r2 > 1:
            r1, r2 = 1 - r1, 1 - r2
        pts.append(a + (b - a) * r1 + (c - a) * r2)
    return pts, total


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(math.ceil(q * len(s))) - 1)]


def dist_stats(d):
    return {"n": len(d), **{f"le_{b}m": round(sum(x <= b for x in d) / len(d), 4) for b in BANDS},
            "p50_m": round(pct(d, 0.5), 3), "p95_m": round(pct(d, 0.95), 3), "max_m": round(max(d), 3)} if d else None


report = {"source": str(source), "blender": bpy.app.version_string, "readback_ok": False,
          "scope": "UCX measurement only; not a delivery verdict", "samples": SAMPLES}
try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    ucx_objs = [o for o in meshes if o.name.upper().startswith("UCX")]
    other = [o for o in meshes if o not in ucx_objs]
    mains = [o for o in other if o.name.endswith("_Main")]
    grounds = [o for o in other if o.name.endswith("_Ground")]
    report["meshes"] = {o.name: len(world_mesh(o)[1]) for o in other}
    model_tris = sum(report["meshes"].values())
    ucx_tris = 0
    pieces = []
    for o in sorted(ucx_objs, key=lambda o: o.name):
        v, t = world_mesh(o)
        ucx_tris += len(t)
        c = ua.classify(v, t)
        wv, wt = ua.weld(v, t)
        lo, hi = ua.bounds(wv)
        size = [hi[i] - lo[i] for i in range(3)]
        pieces.append({"name": o.name, **c, "slots": len(o.material_slots), "uv": len(o.data.uv_layers),
                       "lo": [round(x, 4) for x in lo], "hi": [round(x, 4) for x in hi],
                       "size": [round(x, 4) for x in size], "faces_hvt": ua.face_signature(v, t), "_hull": (wv, wt), "_b": (lo, hi)})
    report["ucx"] = {
        "count": len(pieces), "triangles": ucx_tris, "model_triangles_excl_ucx": model_tris,
        "limit_D012": (15000 if model_tris < 50000 else min(math.ceil(model_tris * 0.05), 100000)),
        "kinds": {k: sum(p["kind"] == k for p in pieces) for k in ("box_aabb", "box_oriented", "convex", "custom")},
        "tris_per_piece": {str(k): sum(p["tris"] == k for p in pieces) for k in sorted({p["tris"] for p in pieces})},
        "faces_hvt": {f"{k[0]}-{k[1]}-{k[2]}": n for k, n in sorted(
            {tuple(p["faces_hvt"]): sum(tuple(q["faces_hvt"]) == tuple(p["faces_hvt"]) for q in pieces) for p in pieces}.items(),
            key=lambda kv: -kv[1])},
        "with_slots": sum(p["slots"] > 0 for p in pieces), "with_uv": sum(p["uv"] > 0 for p in pieces),
        "min_dim_hist": {
            "lt_0.05": sum(min(p["size"]) < 0.05 for p in pieces),
            "0.05-0.3": sum(0.05 <= min(p["size"]) < 0.3 for p in pieces),
            "0.3-1": sum(0.3 <= min(p["size"]) < 1 for p in pieces),
            "ge_1": sum(min(p["size"]) >= 1 for p in pieces)},
        "volume_m3": round(sum(p["size"][0] * p["size"][1] * p["size"][2] for p in pieces), 1),
    }
    report["naming"] = ua.name_report([p["name"] for p in pieces], mains[0].name if mains else "")
    report["targets"] = {"main": [o.name for o in mains], "ground": [o.name for o in grounds],
                         "ucx_ground_pieces": report["naming"]["Ground"]["count"]}
    # pairwise relations for neighbours (AABB gap < NEIGHBOUR_M)
    rel = {"overlap": [], "touch": [], "recommended": [], "wide": [], "apart": []}
    for i, a in enumerate(pieces):
        for b in pieces[i + 1:]:
            if ua.bbox_gap(a["_b"], b["_b"]) > ua.NEIGHBOUR_M:
                continue
            cls, gap, pen = ua.pair_relation(a["_hull"], b["_hull"])
            rel[cls].append((a["name"][-3:], b["name"][-3:], round(gap * 1000, 2), round(pen * 1000, 2)))
    gaps = [g for cls in ("touch", "recommended", "wide") for (_, _, g, _) in rel[cls]]
    report["pairs"] = {
        "neighbour_pairs": sum(len(v) for k, v in rel.items() if k != "apart"),
        **{k: len(v) for k, v in rel.items() if k != "apart"},
        "overlap_max_pen_mm": max([p for *_, p in rel["overlap"]], default=0.0),
        "overlap_examples": sorted(rel["overlap"], key=lambda r: -r[3])[:10],
        "gap_mm_min": min(gaps, default=None), "gap_mm_p50": pct(gaps, 0.5),
        "gap_mm_hist": {"0": sum(g < 0.2 for g in gaps), "0.2-2": sum(0.2 <= g <= 2.0 for g in gaps),
                        "2-10": sum(2.0 < g <= 10 for g in gaps), "10-100": sum(g > 10 for g in gaps)},
    }
    # coverage: Main surface -> UCX, UCX surface -> Main
    rng = random.Random(165)
    if pieces:
        all_v, all_t = [], []
        for p in pieces:
            v, t = p["_hull"]
            off = len(all_v)
            all_v += v
            all_t += [(a + off, b + off, c + off) for a, b, c in t]
        ucx_bvh = BVHTree.FromPolygons(all_v, all_t)
    for target in mains + grounds:
        v, t = world_mesh(target)
        pts, area = sample_surface(v, t, SAMPLES, rng)
        d, dz = [], {"z_lt_0": [], "z_0_6": [], "z_ge_6": []}
        for q in pts:
            inside = any(p["_b"][0][0] - 1e-6 <= q.x <= p["_b"][1][0] + 1e-6 and p["_b"][0][1] - 1e-6 <= q.y <= p["_b"][1][1] + 1e-6
                         and p["_b"][0][2] - 1e-6 <= q.z <= p["_b"][1][2] + 1e-6 and ua.inside_convex(tuple(q), *p["_hull"], tol=1e-4)
                         for p in pieces) if pieces else False
            if inside:
                x = 0.0
            elif pieces:
                hit = ucx_bvh.find_nearest(q)
                x = hit[3] if hit[0] is not None else math.inf
            else:
                x = math.inf
            d.append(x)
            dz["z_lt_0" if q.z < 0 else "z_0_6" if q.z < 6 else "z_ge_6"].append(x)
        cov = {"surface_area_m2": round(area, 1), "inside_ucx": round(sum(x == 0 for x in d) / len(d), 4) if d else None,
               "main_to_ucx": dist_stats(d), "by_height": {k: dist_stats(x) for k, x in dz.items()}}
        if pieces:
            bvh = BVHTree.FromPolygons(v, t)
            up, _ = sample_surface(all_v, all_t, SAMPLES // 2, rng)

            def contact(q, tol=0.02):
                # on a face that touches / nearly touches another piece (internal joint, not exposed);
                # a point lies on its own piece's surface, so "inside within tol" holds for >= 2 pieces
                hits = 0
                for p in pieces:
                    lo, hi = p["_b"]
                    if all(lo[i] - tol <= q[i] <= hi[i] + tol for i in range(3)) and ua.inside_convex(tuple(q), *p["_hull"], tol=tol):
                        hits += 1
                        if hits > 1:
                            return True
                return False
            exposed = [q for q in up if not contact(q)]
            back = [bvh.find_nearest(q)[3] for q in exposed]
            cov["ucx_exposed_share"] = round(len(exposed) / len(up), 4) if up else None
            cov["ucx_exposed_to_surface"] = dist_stats(back)
        report.setdefault("coverage", {})[target.name] = cov
    for p in pieces:
        del p["_hull"], p["_b"]
    report["pieces"] = pieces
    report["readback_ok"] = True
except Exception as exc:  # report, never hide
    import traceback
    report["error"] = f"{type(exc).__name__}: {exc}"
    report["traceback"] = traceback.format_exc()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("UCX_AUDIT", report["readback_ok"], report.get("error", ""))
sys.exit(0 if report["readback_ok"] else 2)
