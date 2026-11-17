"""Read-back of a stage-1 body (#1619 round 5): openings, reveal depth, inward faces, boundary loops.

Pattern: n/a | new-case: read-back of a body with opening reveals (stage 1 «бадик с проемами»).

uv run python readback_openings.py DUMP.npz FLOOR.json OUT.json
Reads the exported FBX dump (dump_mesh.py), not the build report. OUT is opened with "x": an existing path (any
input included) is refused."""
import collections, json, math, sys
import numpy as np
from shapely.geometry import Point, Polygon

d = np.load(sys.argv[1])
fl = json.load(open(sys.argv[2], encoding="utf-8"))
V, fn, fi = d["verts"], d["fn"], d["fi"]
faces, o = [], 0
for n in fn:
    faces.append(fi[o:o + n].tolist()); o += n
ring = Polygon(fl["rings"][0]["xy"])
ext = ring.exterior
rmax = max(w[5] for w in fl["windows"])
edges = collections.Counter()
inward, outside, reveal, wall, bad_n = 0, 0, 0, 0, 0
for f in faces:
    P = V[f]
    nrm = np.cross(P[1] - P[0], P[2] - P[0])
    nrm = nrm / (np.linalg.norm(nrm) or 1)
    c = P.mean(0)
    sd = (-1 if ring.contains(Point(c[0], c[1])) else 1) * ext.distance(Point(c[0], c[1]))
    for i in range(len(f)):
        edges[tuple(sorted((f[i], f[(i + 1) % len(f)])))] += 1
    if sd > 0.01:
        outside += 1
    if abs(sd) <= 0.01 and abs(nrm[2]) < 0.1:  # wall face on the facade line: normal must point out of the ring
        wall += 1
        s = ext.project(Point(c[0], c[1]))
        q = ext.interpolate(s); p0 = ext.interpolate(max(0, s - 0.05)); p1 = ext.interpolate(min(ext.length, s + 0.05))
        out_n = np.array([p1.y - p0.y, -(p1.x - p0.x)]); out_n /= np.linalg.norm(out_n)
        if nrm[:2] @ out_n < 0:
            inward += 1
    elif sd < -0.01:
        reveal += 1
        if -sd > rmax + 0.02:
            bad_n += 1
bnd = [e for e, k in edges.items() if k == 1]
# boundary loops
adj = collections.defaultdict(list)
for a, b in bnd:
    adj[a].append(b); adj[b].append(a)
seen, loops = set(), 0
for v in adj:
    if v in seen:
        continue
    loops += 1
    st = [v]
    while st:
        x = st.pop()
        if x in seen:
            continue
        seen.add(x); st += adj[x]
rep = {"faces": len(faces), "quads": sum(1 for f in faces if len(f) == 4), "wall_faces_on_contour": wall,
       "wall_faces_facing_inward": inward, "faces_outside_contour": outside, "reveal_faces": reveal,
       "reveal_faces_deeper_than_rmax": bad_n, "rmax_m": rmax, "boundary_edges": len(bnd),
       "boundary_loops": loops, "nonmanifold_edges": sum(1 for k in edges.values() if k > 2),
       "openings_expected": len(fl["windows"]) * fl["floors"], "zmin": float(V[:, 2].min()), "zmax": float(V[:, 2].max())}
json.dump(rep, open(sys.argv[3], "x"), indent=1)
print(json.dumps(rep))
