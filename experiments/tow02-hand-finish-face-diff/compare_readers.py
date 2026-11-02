"""M1: compare the research's pure-Python FBX reader (raw local vertices) with Blender 5.1.2 import (world vertices).
Then re-run the research matcher on the Blender geometry (world, and world minus the object translation).
Usage: python compare_readers.py <tmpdir>   (tmpdir holds v005.fbx, user05.fbx, bl_v005.json, bl_user05.json, atlas, ovl)
"""
import json, math, statistics, sys, time
import face_diff as fd

T = sys.argv[1]
fd.V5, fd.USER, fd.ATLAS, fd.OVL = T + "/v005.fbx", T + "/user05.fbx", T + "/atlas_layout.json", T + "/ovl_pairs.json"
raw_mesh = fd.mesh
bl = {k: json.load(open("%s/bl_%s.json" % (T, k)))[fd.OBJ] for k in ("v005", "user05")}


def bbox(V):
    return [round(min(v[a] for v in V), 3) for a in range(3)] + [round(max(v[a] for v in V), 3) for a in range(3)]


rep = {}
for k, path in (("v005", fd.V5), ("user05", fd.USER)):
    RV, RP, _, _ = raw_mesh(path, fd.OBJ)
    BV, BP = bl[k]["verts"], bl[k]["polys"]
    same_topo = RP == BP
    dmax = max(math.dist(a, b) for a, b in zip(RV, BV)) if len(RV) == len(BV) else None
    t = [r[3] for r in bl[k]["matrix"][:3]]
    dmax_local = max(math.dist(a, [b[i] - t[i] for i in range(3)]) for a, b in zip(RV, BV)) if len(RV) == len(BV) else None
    rep[k] = dict(raw_v=len(RV), raw_f=len(RP), bl_v=len(BV), bl_f=len(BP), same_polys=same_topo,
                  max_dev_world_m=dmax, max_dev_world_minus_T_m=dmax_local, obj_translation=t,
                  raw_bbox=bbox(RV), bl_bbox=bbox(BV))
print("READERS " + json.dumps(rep))

# baseline: research matcher with its own reader, 3 runs
times = []
for i in range(3):
    t0 = time.perf_counter(); fd.main(T + "/out_raw"); times.append(time.perf_counter() - t0)
print("T_RAW_MATCH", [round(x, 2) for x in times], "median", round(statistics.median(times), 2))


def bl_mesh(mode):
    def m(path, want):
        k = "v005" if path == fd.V5 else "user05"
        V = bl[k]["verts"]
        if mode == "local":
            t = [r[3] for r in bl[k]["matrix"][:3]]
            V = [[v[i] - t[i] for i in range(3)] for v in V]
        uv = bl[k]["uv"]
        return [tuple(v) for v in V], bl[k]["polys"], uv, list(range(len(uv) // 2))
    return m


for mode in ("world", "local"):
    fd.mesh = bl_mesh(mode)
    t0 = time.perf_counter(); fd.main(T + "/out_bl_" + mode)
    print("T_BL_MATCH", mode, round(time.perf_counter() - t0, 2))
fd.mesh = raw_mesh
