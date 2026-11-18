"""Read-back of a stage-1 body (#1619 round 5): openings, reveal depth, inward faces, boundary loops, UV/geo.

Pattern: n/a | new-case: read-back of a body with opening reveals (stage 1 «бадик с проемами»).

uv run python readback_openings.py DUMP.npz FLOOR.json OUT.json
Reads the exported FBX dump (dump_mesh.py), not the build report. OUT is opened with "x": an existing path (any
input included) is refused. UV/geo (PR #1660 review): per face, every edge's |dUV| * wall_tile_m / |dXYZ|; the
min/max are reported per class (wall, jamb, sill/head) and a face outside [0.99, 1.01] is a defect (exit 1).
Faces of the WINDOW material carry a normalized 0..1 UV by design and are counted, not measured; a face without a
usable UV is a defect.
"""
import collections
import json
import math
import sys

import numpy as np

UV_TOL = (0.99, 1.01)


def edge_uv_ratios(P, UV, tex_m):
    """Per-edge |dUV| * tex_m / |dXYZ| of one face; refuses a missing/mismatched UV, a non-finite value,
    tex_m <= 0 and a zero-length edge (each a ValueError naming it)."""
    if not (isinstance(tex_m, (int, float)) and math.isfinite(tex_m) and tex_m > 0):
        raise ValueError("tex_m must be finite > 0, got %r" % (tex_m,))
    P, UV = np.asarray(P, dtype=float), np.asarray(UV, dtype=float)
    if UV.ndim != 2 or len(UV) != len(P) or len(P) < 3:
        raise ValueError("face UV does not match its %d corners" % len(P))
    if not (np.isfinite(P).all() and np.isfinite(UV).all()):
        raise ValueError("non-finite corner or UV")
    out = []
    for i in range(len(P)):
        g = float(np.linalg.norm(P[(i + 1) % len(P)] - P[i]))
        if g < 1e-9:
            raise ValueError("zero-length edge at corner %d" % i)
        out.append(float(np.linalg.norm(UV[(i + 1) % len(P)] - UV[i])) * tex_m / g)
    return out


def uv_defect(ratios):
    """A face is a UV/geo defect when any edge ratio leaves [0.99, 1.01] (NaN included)."""
    return not all(UV_TOL[0] <= r <= UV_TOL[1] for r in ratios)


def face_class(nrm, sd):
    """wall (on the contour, vertical), jamb (inside, vertical), sill_head (inside, horizontal) or other."""
    if abs(sd) <= 0.01 and abs(nrm[2]) < 0.1:
        return "wall"
    if sd < -0.01:
        return "jamb" if abs(nrm[2]) < 0.1 else ("sill_head" if abs(nrm[2]) > 0.9 else "other")
    return "other"


def main(argv):
    from shapely.geometry import Point, Polygon

    d = np.load(argv[0])
    fl = json.load(open(argv[1], encoding="utf-8"))
    tex_m = float(fl.get("wall_tile_m", 3.0))
    V, fn, fi, mats = d["verts"], d["fn"], d["fi"], d["mats"]
    names = [str(n) for n in d["names"]] if "names" in d.files else []
    uvn, uvf = d["uvn"], d["uvf"]
    faces, fuv, o, ou = [], [], 0, 0
    for k, n in enumerate(fn):
        faces.append(fi[o:o + n].tolist()); o += n
        fuv.append(uvf[ou:ou + uvn[k]]); ou += uvn[k]
    ring = Polygon(fl["rings"][0]["xy"])
    ext = ring.exterior
    rmax = max(w[5] for w in fl["windows"])
    edges = collections.Counter()
    inward, outside, reveal, wall, bad_n = 0, 0, 0, 0, 0
    uvr = {c: [math.inf, -math.inf, 0, 0] for c in ("wall", "jamb", "sill_head", "other")}  # min, max, n, defects
    window_faces, uv_bad = 0, 0
    for fk, f in enumerate(faces):
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
            p0 = ext.interpolate(max(0, s - 0.05)); p1 = ext.interpolate(min(ext.length, s + 0.05))
            out_n = np.array([p1.y - p0.y, -(p1.x - p0.x)]); out_n /= np.linalg.norm(out_n)
            if nrm[:2] @ out_n < 0:
                inward += 1
        elif sd < -0.01:
            reveal += 1
            if -sd > rmax + 0.02:
                bad_n += 1
        if names and names[mats[fk]] == "WINDOW":
            window_faces += 1
            continue
        try:
            rs = edge_uv_ratios(P, fuv[fk], tex_m)
        except ValueError:
            uv_bad += 1
            continue
        b = uvr[face_class(nrm, sd)]
        b[0], b[1], b[2] = min(b[0], min(rs)), max(b[1], max(rs)), b[2] + 1
        b[3] += int(uv_defect(rs))
    bnd = [e for e, k in edges.items() if k == 1]
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
    uv_rep = {c: {"faces": b[2], "min": round(b[0], 6) if b[2] else None, "max": round(b[1], 6) if b[2] else None,
                  "defects": b[3]} for c, b in uvr.items()}
    rep = {"faces": len(faces), "quads": sum(1 for f in faces if len(f) == 4), "wall_faces_on_contour": wall,
           "wall_faces_facing_inward": inward, "faces_outside_contour": outside, "reveal_faces": reveal,
           "reveal_faces_deeper_than_rmax": bad_n, "rmax_m": rmax, "boundary_edges": len(bnd),
           "boundary_loops": loops, "nonmanifold_edges": sum(1 for k in edges.values() if k > 2),
           "openings_expected": len(fl["windows"]) * fl["floors"], "zmin": float(V[:, 2].min()),
           "zmax": float(V[:, 2].max()), "uv_geo_tol": list(UV_TOL), "tex_m": tex_m, "uv_geo": uv_rep,
           "uv_window_faces_skipped": window_faces, "uv_missing_or_bad_faces": uv_bad,
           "uv_geo_defects": sum(b[3] for b in uvr.values()) + uv_bad}
    json.dump(rep, open(argv[2], "x"), indent=1)
    print(json.dumps(rep))
    return 1 if rep["uv_geo_defects"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
