"""elv-tc-vpm: numeric comparison customer blank vs our delivery v002 (facade planes, sections, UDIM tile stats).

py -3 -I customer_compare_v001.py <out_dir>   (reads fbx_tris_*_uv.npz, fbx_probe_*.json in out_dir; writes new files only)
"""
import sys, os, json
import numpy as np

out = sys.argv[1]
C = np.load(os.path.join(out, "fbx_tris_customer_uv.npz"))
O = np.load(os.path.join(out, "fbx_tris_ours_v002_uv.npz"))
pc = json.load(open(os.path.join(out, "fbx_probe_customer.json"), encoding="utf-8"))
loc = np.array(pc["objects"]["SM_Elevatornaya_Vl_1_A_001_Main"]["location"])
res = {"their_origin_world": loc.tolist()}


def prep(tri):
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    n = np.cross(e1, e2)
    a = np.linalg.norm(n, axis=1) / 2
    n = n / np.maximum(2 * a, 1e-12)[:, None]
    return n, a, tri.mean(axis=1)


models = {"theirs": {k: (C[k] - loc if k.endswith("_tri") else C[k]) for k in C.files},
          "ours": {k: O[k] for k in O.files}}
# 1. facade planes: area-weighted coordinate peaks of faces whose normal is within 5 deg of +-X / +-Y
dirs = {"+X(E)": (0, 1), "-X(W)": (0, -1), "+Y(N)": (1, 1), "-Y(S)": (1, -1)}
planes = {}
for m, d in models.items():
    n, a, c = prep(d["Main_tri"])
    planes[m] = {}
    for name, (ax, s) in dirs.items():
        sel = (n[:, ax] * s) > 0.996
        v = np.round(c[sel, ax], 2)
        w = a[sel]
        u, inv = np.unique(v, return_inverse=True)
        tot = np.bincount(inv, weights=w)
        order = np.argsort(-tot)[:8]
        planes[m][name] = [(float(u[i]), round(float(tot[i]), 1)) for i in order]
res["facade_planes_top8_coord_m_area_m2"] = planes
# 2. extreme wall planes (largest-area plane per direction) and offset ours - theirs
off = {}
for name in dirs:
    t = planes["theirs"][name][0][0]
    o = planes["ours"][name][0][0]
    off[name] = {"theirs": t, "ours": o, "ours_minus_theirs": round(o - t, 3)}
res["main_plane_offset"] = off


# 3. plan sections at heights: segments of triangles cut by z = h
def section(tri, h):
    z = tri[:, :, 2] - h
    segs = []
    for t, zz in zip(tri, z):
        s = np.sign(zz)
        if s.min() >= 0 or s.max() <= 0:
            continue
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if (zz[i] > 0) != (zz[j] > 0):
                f = zz[i] / (zz[i] - zz[j])
                pts.append(t[i] + f * (t[j] - t[i]))
        if len(pts) == 2:
            segs.append([pts[0][:2], pts[1][:2]])
    return np.array(segs)


sec = {}
for h in (1.5, 6.0, 11.0, 14.5):
    for m, d in models.items():
        s = section(d["Main_tri"], h)
        sec[f"{m}_{h}"] = s
        if len(s):
            p = s.reshape(-1, 2)
            res.setdefault("section_bbox", {})[f"{m}_z{h}"] = [p.min(0).round(3).tolist(), p.max(0).round(3).tolist()]
np.savez_compressed(os.path.join(out, "sections_v001.npz"), **{k.replace(".", "_"): v for k, v in sec.items()})
# 4. heights: max z per 2x2 m plan cell, compare
for m, d in models.items():
    t = d["Main_tri"]
    res.setdefault("z_max", {})[m] = round(float(t[:, :, 2].max()), 3)
    res.setdefault("z_min", {})[m] = round(float(t[:, :, 2].min()), 3)
# 5. UDIM tile stats (Main + Glass): area, dominant normal, extents, texel density per 1 px of tile
DIRN = {"+X": (0, 1), "-X": (0, -1), "+Y": (1, 1), "-Y": (1, -1), "+Z": (2, 1), "-Z": (2, -1)}
tiles = {}
for m, d in models.items():
    tiles[m] = {}
    for part in ("Main", "Glass"):
        tri, uv, ud = d[part + "_tri"], d[part + "_uv"], d[part + "_udim"]
        n, a, c = prep(tri)
        ua = np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1]) - (uv[:, 1, 1] - uv[:, 0, 1]) * (uv[:, 2, 0] - uv[:, 0, 0])) / 2
        for t in np.unique(ud):
            s = ud == t
            dd = {}
            for k, (ax, sg) in DIRN.items():
                dd[k] = round(float(a[s & (n[:, ax] * sg > 0.7)].sum()), 1)
            dd = {k: v for k, v in sorted(dd.items(), key=lambda kv: -kv[1]) if v > 0}
            area = float(a[s].sum())
            uva = float(ua[s].sum())
            tiles[m][f"{part}:{int(t)}"] = {"tris": int(s.sum()), "area_m2": round(area, 1), "normals_area": dd,
                                             "x": [round(float(c[s, 0].min()), 2), round(float(c[s, 0].max()), 2)],
                                             "y": [round(float(c[s, 1].min()), 2), round(float(c[s, 1].max()), 2)],
                                             "z": [round(float(tri[s, :, 2].min()), 2), round(float(tri[s, :, 2].max()), 2)],
                                             "uv_area_tiles": round(uva, 4),
                                             "m_per_tile_side": round(float(np.sqrt(area / uva)), 2) if uva > 0 else None}
res["udim_tiles"] = tiles
json.dump(res, open(os.path.join(out, "compare_numbers_v001.json"), "x", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ("main_plane_offset", "z_max", "z_min", "section_bbox")}, indent=1))
for m in tiles:
    print("==", m)
    for k, v in tiles[m].items():
        print(k, v)
