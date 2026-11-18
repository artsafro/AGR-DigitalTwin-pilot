"""Read-back of a stage-2 build (#1619 polygon stage 2): body unchanged, inset elements checked from the EXPORTED FBX.

Pattern: n/a | new-case: read-back of stage-2 inset elements (frame/glass/flashing/capsule/AC box) on an accepted body.

blender -b --factory-startup --python stage2_readback.py -- EXPORT.fbx ACCEPTED_BODY.fbx STAGE2.json OUT.json

Checks (a defect sets exit code 1):
- body: SM_Body_Main of EXPORT equals the accepted FBX (vertex/face counts, sorted world coordinates, per-loop
  UV and material names) - stage 2 is additive only;
- every element is its own object (D336) and all-quad; frames are closed manifold shells; capsules (D205) and AC
  boxes are open on exactly one side (4 boundary edges), capsule faces look INTO the capsule, glass looks out;
- AC box back boundary lies `embed` behind the facade line (inside the contour), its front outside; capsules are
  inside the contour; every element lies in the body's z range (typical floors only);
- coplanar overlaps (face centroid within 2 mm of another object's face plane, parallel, inside it) = 0 between
  elements and the body and between elements.
OUT is opened with "x".
"""
import collections
import json
import math
import sys


def point_in_ring(p, ring):
    """Even-odd test of plan point p in the closed ring [(x, y), ...]."""
    x, y = p
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def ring_depth(p, ring):
    """Signed distance of p to the ring: + inside (behind the facade line), - outside."""
    best = math.inf
    n = len(ring)
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
        best = min(best, math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy))
    return best if point_in_ring(p, ring) else -best


def coplanar_overlaps(tris, owner, tol=0.002, cell=0.5):
    """Triangles (n,3,3) whose centroid lies inside a triangle of ANOTHER owner, on its plane within tol and with
    a parallel normal. Returns a list of (i, j) index pairs (i overlapping j). Pure numpy; spatial hash by cell."""
    import numpy as np
    T = np.asarray(tris, dtype=float)
    own = np.asarray(owner)
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nn = np.linalg.norm(N, axis=1)
    ok = nn > 1e-12
    N[ok] /= nn[ok][:, None]
    C = T.mean(1)
    lo, hi = T.min(1) - tol, T.max(1) + tol
    grid = collections.defaultdict(list)
    for j in np.nonzero(ok)[0]:
        a, b = np.floor(lo[j] / cell).astype(int), np.floor(hi[j] / cell).astype(int)
        for gx in range(a[0], b[0] + 1):
            for gy in range(a[1], b[1] + 1):
                for gz in range(a[2], b[2] + 1):
                    grid[(gx, gy, gz)].append(j)
    out = []
    for i in np.nonzero(ok)[0]:
        c = C[i]
        for j in grid.get(tuple(np.floor(c / cell).astype(int)), ()):
            if own[j] == own[i] or abs(N[i] @ N[j]) < 0.999:
                continue
            if not (np.all(c >= lo[j]) and np.all(c <= hi[j])):
                continue
            if abs((c - T[j, 0]) @ N[j]) > tol:
                continue
            # barycentric inside test with a small margin (touching edges are not overlaps)
            v0, v1, v2 = T[j, 1] - T[j, 0], T[j, 2] - T[j, 0], c - T[j, 0]
            d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
            den = d00 * d11 - d01 * d01
            if den <= 0:
                continue
            b1 = (d11 * d20 - d01 * d21) / den
            b2 = (d00 * d21 - d01 * d20) / den
            if b1 > 1e-4 and b2 > 1e-4 and b1 + b2 < 1 - 1e-4:
                out.append((int(i), int(j)))
    return out


def mesh_edges(faces):
    """Edge -> face count of a polygon list."""
    cnt = collections.Counter()
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            cnt[(min(a, b), max(a, b))] += 1
    return cnt


def _run():  # Blender only
    import bpy
    import numpy as np

    args = sys.argv[sys.argv.index("--") + 1:]
    exp, acc, spec_path, out = args[:4]
    spec = json.load(open(spec_path, encoding="utf-8"))
    ring = [tuple(p) for p in spec["ring"]]
    embed = {round(b["embed"], 4) for b in spec["baskets"]}

    def load(path):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=path)
        res = {}
        for o in bpy.context.scene.objects:
            if o.type != "MESH":
                continue
            me = o.data
            W = np.array([tuple(o.matrix_world @ v.co) for v in me.vertices])
            faces = [list(p.vertices) for p in me.polygons]
            uv = me.uv_layers.active.data if me.uv_layers.active else None
            loops = []
            for p in me.polygons:
                for li, vi in zip(p.loop_indices, p.vertices):
                    loops.append(tuple(np.round(W[vi], 4)) + ((round(uv[li].uv[0], 4), round(uv[li].uv[1], 4)) if uv else ())
                                 + (me.materials[p.material_index].name.split(".")[0] if me.materials else "",))
            res[o.name] = {"W": W, "faces": faces, "loops": sorted(loops)}
        return res
    A = load(acc)
    E = load(exp)
    rep = {"defects": []}
    bad = rep["defects"]
    ab, eb = A.get("SM_Body_Main"), E.get("SM_Body_Main")
    if ab is None or eb is None:
        bad.append("SM_Body_Main missing (accepted %s, export %s)" % (ab is not None, eb is not None))
    else:
        same_counts = len(ab["W"]) == len(eb["W"]) and len(ab["faces"]) == len(eb["faces"])
        sa = ab["W"][np.lexsort(ab["W"].T[::-1])]
        se = eb["W"][np.lexsort(eb["W"].T[::-1])] if same_counts else None
        dmax = float(np.abs(sa - se).max()) if same_counts else math.inf
        rep["body"] = {"verts": len(eb["W"]), "faces": len(eb["faces"]), "max_coord_diff_m": dmax,
                       "loops_uv_mat_equal": ab["loops"] == eb["loops"]}
        if not (same_counts and dmax < 1e-5 and ab["loops"] == eb["loops"]):
            bad.append("body differs from the accepted FBX")
    bz = (float(eb["W"][:, 2].min()), float(eb["W"][:, 2].max())) if eb is not None else (-math.inf, math.inf)
    kinds = {"Frame": "frame", "Glass": "glass", "Flash": "flash"}
    stats = collections.defaultdict(lambda: collections.Counter())
    tris, owner = [], []
    for k, (nm, m) in enumerate(sorted(E.items())):
        W, faces = m["W"], m["faces"]
        for f in faces:  # fan (all faces are quads or the defect below counts them)
            for i in range(1, len(f) - 1):
                tris.append(W[[f[0], f[i], f[i + 1]]])
                owner.append(k)
        if nm == "SM_Body_Main":
            continue
        kind = kinds.get(nm.rsplit("_", 1)[-1]) if nm.startswith("SM_Win_") else \
            "capsule" if nm.startswith("SM_Cap_") else "basket" if nm.startswith("SM_AC_") else None
        if kind is None:
            bad.append("unexpected object %s" % nm)
            continue
        s = stats[kind]
        s["objects"] += 1
        s["faces"] += len(faces)
        s["quads"] += sum(1 for f in faces if len(f) == 4)
        s["tris"] += sum(1 for f in faces if len(f) == 3)
        s["ngons"] += sum(1 for f in faces if len(f) > 4)
        ec = mesh_edges(faces)
        boundary = [e for e, c in ec.items() if c == 1]
        if any(c > 2 for c in ec.values()):
            s["non_manifold"] += 1
        # capsules keep their D205 100 mm outline below the first typical sill (inside the building, unseen)
        zt = 1e-3 + (float(spec["capsule"]["outline"]) if kind == "capsule" else 0.0)
        if W[:, 2].min() < bz[0] - zt or W[:, 2].max() > bz[1] + zt:
            s["outside_body_z"] += 1
        centre = W.mean(0)

        def normal(f):
            P = W[f]
            n = np.zeros(3)
            for i in range(len(f)):
                a, b = P[i], P[(i + 1) % len(f)]
                n += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
            return n / np.linalg.norm(n), P.mean(0)
        if kind == "frame" and boundary:
            s["open_frames"] += 1
        if kind == "glass":
            for f in faces:
                n, c = normal(f)
                if ring_depth(c[:2] + 0.05 * n[:2], ring) >= ring_depth(c[:2], ring):
                    s["glass_facing_in"] += 1
        if kind == "capsule":
            if len(boundary) != 4:
                s["capsule_not_open_once"] += 1
            for f in faces:
                n, c = normal(f)
                if n @ (centre - c) <= 0:
                    s["capsule_face_outward"] += 1
            if min(ring_depth(p[:2], ring) for p in W) <= 0:
                s["capsule_outside_contour"] += 1
        if kind == "basket":
            if len(faces) != 5 or len(boundary) != 4:
                s["basket_not_5_faces_open_back"] += 1
            bv = sorted({v for e in boundary for v in e})
            depths = [ring_depth(W[v][:2], ring) for v in bv]
            s["basket_back_min_mm"] = min(s.get("basket_back_min_mm", 10 ** 6), int(round(min(depths) * 1000)))
            s["basket_back_max_mm"] = max(s.get("basket_back_max_mm", -10 ** 6), int(round(max(depths) * 1000)))
            if min(depths) <= 0:
                s["basket_back_not_in_wall"] += 1
            front = [ring_depth(W[v][:2], ring) for v in range(len(W)) if v not in bv]
            if max(front) >= 0:
                s["basket_front_not_outside"] += 1
            for f in faces:
                n, c = normal(f)
                if n @ (c - centre) <= 0:
                    s["basket_face_inward"] += 1
    ov = coplanar_overlaps(np.array(tris), owner)
    names = sorted(E)
    rep["coplanar_overlaps"] = len(ov)
    rep["coplanar_overlap_pairs"] = sorted({(names[owner[i]], names[owner[j]]) for i, j in ov})[:20]
    if ov:
        bad.append("%d coplanar overlaps" % len(ov))
    rep["elements"] = {k: dict(v) for k, v in sorted(stats.items())}
    allf = sum(v["faces"] for v in stats.values())
    rep["elements_quad_share"] = round(sum(v["quads"] for v in stats.values()) / allf, 4) if allf else None
    for k, v in stats.items():
        for key in ("tris", "ngons", "non_manifold", "outside_body_z", "open_frames", "glass_facing_in",
                    "capsule_not_open_once", "capsule_face_outward", "capsule_outside_contour",
                    "basket_not_5_faces_open_back", "basket_back_not_in_wall", "basket_front_not_outside",
                    "basket_face_inward"):
            if v.get(key):
                bad.append("%s: %s = %d" % (k, key, v[key]))
    if stats.get("basket"):
        want = min(embed) * 1000 if embed else 0
        if abs(stats["basket"]["basket_back_min_mm"] - want) > 15:
            bad.append("basket back %d mm behind the facade, expected ~%d" % (stats["basket"]["basket_back_min_mm"], want))
    rep["expected"] = {"windows": len(spec["windows"]) * spec["floors"], "baskets": len(spec["baskets"]) * spec["floors"]}
    for kind, n in (("frame", rep["expected"]["windows"]), ("glass", rep["expected"]["windows"]),
                    ("capsule", rep["expected"]["windows"]), ("basket", rep["expected"]["baskets"])):
        if stats[kind]["objects"] != n:
            bad.append("%s objects %d, expected %d" % (kind, stats[kind]["objects"], n))
    with open(out, "x", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=str)
    print("READBACK", json.dumps({"defects": bad, "elements_quad_share": rep["elements_quad_share"],
                                  "coplanar_overlaps": len(ov), "body": rep.get("body")}, default=str))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    _run()
