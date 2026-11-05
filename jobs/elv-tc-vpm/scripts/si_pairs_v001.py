"""elv-tc-vpm: V004 self-intersection pairs of SM_Elevatornaya_1A_Main by part pair (read-only diagnostics).

blender -b --factory-startup --python si_pairs_v001.py -- <master.blend> <out.json> [--tri]

Uses the regulatory counter src/twinqa/geometry/topology.py (same internals as count_defects: clusters at 0.002 m,
AABB candidates, pierce | edge-on-plane). Polygons are mapped to the face attribute part_idx and the object
property part_ids. --tri: triangulate a copy first (beauty, like the export copy) so the count matches the FBX.
Writes per part pair: count, rule (pierce / on_plane), sample pair centres; and the full pair list (poly ids).
"""
import bpy, bmesh, json, os, sys, importlib.util
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("topology", ROOT / "src/twinqa/geometry/topology.py")
topo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(topo)

args = sys.argv[sys.argv.index("--") + 1:]
src, out = args[0], args[1]
tri = "--tri" in args
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
bpy.ops.wm.open_mainfile(filepath=src)
ob = bpy.data.objects["SM_Elevatornaya_1A_Main"]
parts = json.loads(ob["part_ids"])
bm = bmesh.new()
bm.from_mesh(ob.data)
lay = bm.faces.layers.int.get("part_idx")
if tri:
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()
mw = ob.matrix_world
verts = np.array([tuple(mw @ v.co) for v in bm.verts], dtype=np.float64)
polys = [np.array([v.index for v in f.verts], dtype=np.int64) for f in bm.faces]
pidx = [f[lay] for f in bm.faces]
mats = [f.material_index + 1 for f in bm.faces]
nrm = [tuple(round(c, 3) for c in f.normal) for f in bm.faces]
cen = [tuple(round(c, 3) for c in (mw @ f.calc_center_median())) for f in bm.faces]
bm.free()

tol = topo.TOL_M
clusters = topo._cluster_ids(verts, tol)
pairs = topo._aabb_pairs(verts, polys)
poly_clusters = [set(int(c) for c in clusters[p]) for p in polys]
fans = []
for poly in polys:
    p0 = int(poly[0])
    fans.append(np.asarray([(p0, int(poly[i]), int(poly[i + 1])) for i in range(1, len(poly) - 1)], dtype=np.int64))
edge_map, fan_ids, fan_verts = topo._fan_edge_map(fans, clusters)
cluster_fans = topo._fans_by_cluster(fan_verts, clusters)
usable = []
for p, q in pairs:
    shared = poly_clusters[p] & poly_clusters[q]
    if len(shared) >= 3 or len(fans[p]) == 0 or len(fans[q]) == 0:
        continue
    usable.append((p, q, shared))
pierced = topo._pierce_pairs(verts, polys, clusters, fans, usable, tol, edge_map, fan_ids, fan_verts, cluster_fans)
on_plane = topo._edge_on_plane_pairs(verts, fans, fan_ids, usable, edge_map, clusters, tol, fan_verts, cluster_fans)
allp = sorted(pierced | on_plane)
by = {}
for p, q in allp:
    a, b = sorted((parts[pidx[p]], parts[pidx[q]]))
    k = f"{a} x {b}"
    d = by.setdefault(k, {"count": 0, "pierce": 0, "on_plane": 0, "samples": []})
    d["count"] += 1
    d["pierce"] += (p, q) in pierced
    d["on_plane"] += (p, q) in on_plane and (p, q) not in pierced
    if len(d["samples"]) < 6:
        d["samples"].append({"p": [p, parts[pidx[p]], mats[p], cen[p], nrm[p]], "q": [q, parts[pidx[q]], mats[q], cen[q], nrm[q]]})
rep = {"src": src, "tri": tri, "faces": len(polys), "self_intersections": len(allp),
       "by_part_pair": dict(sorted(by.items(), key=lambda kv: -kv[1]["count"])),
       "pairs": [[p, q, parts[pidx[p]], parts[pidx[q]], cen[p], cen[q]] for p, q in allp]}
json.dump(rep, open(out, "w", encoding="utf-8"), indent=1)
print("SI", len(allp))
for k, v in rep["by_part_pair"].items():
    print("SI", v["count"], k, "pierce", v["pierce"])
