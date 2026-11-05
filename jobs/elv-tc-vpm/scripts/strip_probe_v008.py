"""elv-tc-vpm v008 probe: what interrupts the cover strips P44 of build-v007 (read only).

For every built strip outline: rays every 2.5 cm from 0.3 m outside towards the facade (first hit: part / ID / offset),
and every non-facade polygon that overlaps the strip slab (0..0.06 m off the facade, strip z +-1 cm) with its s range,
offset range and z range. Also the facade section at the strip mid height around each outline end (corner shape).

blender -b --factory-startup --disable-autoexec <elv_full_v007c.blend> --python strip_probe_v008.py -- <out.json>
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
JOB = os.path.abspath(os.path.join(HERE, ".."))
OUT = sys.argv[sys.argv.index("--") + 1]
OFF = (35.1000, -24.2535)
ob = bpy.data.objects["SM_Elevatornaya_Vl_1_A_001_Main"]
PART_IDS = json.loads(ob["part_ids"])
me = ob.data
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
lay = bm.faces.layers.int["part_idx"]
bvh = BVHTree.FromBMesh(bm)
STR = json.load(open(os.path.join(JOB, "outputs", "build-v007", "strips_selected_v007.json"), encoding="utf-8"))
ADD = {s["name"]: s for s in json.load(open(os.path.join(JOB, "outputs", "build-v007", "additions_v007c.json"),
                                             encoding="utf-8"))["strips"]}
rep = []
for st in STR:
    if st["name"] not in ADD:
        continue
    a_ = ADD[st["name"]]
    vs = [(v[0] + OFF[0], v[1] + OFF[1], v[2]) for v in st["verts"]]
    z0, z1 = min(v[2] for v in vs), max(v[2] for v in vs)
    bot = sorted([v for v in vs if abs(v[2] - z0) < 1e-3])[:2]
    p0, p1 = Vector((bot[0][0], bot[0][1], 0)), Vector((bot[-1][0], bot[-1][1], 0))
    L = (p1 - p0).length
    a = (p1 - p0) / L
    out = Vector((a_["out"][0], a_["out"][1], 0))
    zm = (z0 + z1) / 2
    hits = []
    n = int(L / 0.025)
    for k in range(n + 1):
        s = k * L / n
        q = p0 + a * s + out * 0.3
        q.z = zm
        loc, nrm, fi, d = bvh.ray_cast(q, -out, 0.8)
        if loc is None:
            hits.append((round(s, 3), None, None, None))
            continue
        f = bm.faces[fi]
        hits.append((round(s, 3), PART_IDS[f[lay]], f.material_index + 1, round(0.3 - d, 4)))
    # facade offset (from the outline, along out) = median of the ID01/05 hits
    fo = sorted(h[3] for h in hits if h[2] in (1, 5))
    dmed = fo[len(fo) // 2] if fo else None
    runs, cur = [], None
    for h in hits:
        tag = (h[1], h[2], None if h[3] is None or dmed is None else round(h[3] - dmed, 2))
        if cur and cur["tag"] == tag:
            cur["s1"] = h[0]
        else:
            cur = {"tag": tag, "s0": h[0], "s1": h[0]}
            runs.append(cur)
    runs = [{"part": r["tag"][0], "id": r["tag"][1], "d_from_facade_m": r["tag"][2], "s": [r["s0"], r["s1"]]}
            for r in runs]
    # polygons in the slab 0..0.06 m off the facade
    obst = {}
    if dmed is not None:
        for f in bm.faces:
            part = PART_IDS[f[lay]]
            if part == "P44_CoverStrips":
                continue
            ss = [(v.co.xy - p0.xy).dot(a.xy) for v in f.verts]
            dd = [(v.co.xy - p0.xy).dot(out.xy) - dmed for v in f.verts]
            zz = [v.co.z for v in f.verts]
            if max(ss) < -0.4 or min(ss) > L + 0.4 or max(zz) < z0 - 0.01 or min(zz) > z1 + 0.01:
                continue
            if max(dd) < 0.001 or min(dd) > 0.06:
                continue
            if f.material_index + 1 in (1, 5) and max(dd) - min(dd) < 0.002:
                continue                     # the facade plane itself
            o = obst.setdefault(part, [])
            o.append({"id": f.material_index + 1, "s": [round(min(ss), 3), round(max(ss), 3)],
                      "d": [round(min(dd), 4), round(max(dd), 4)], "z": [round(min(zz), 3), round(max(zz), 3)]})
    # merge per part into s clusters
    obs = {}
    for part, lst in obst.items():
        lst.sort(key=lambda o: o["s"][0])
        cl = []
        for o in lst:
            if cl and o["s"][0] <= cl[-1]["s"][1] + 0.05:
                c = cl[-1]
                c["s"][1] = max(c["s"][1], o["s"][1])
                c["d"] = [min(c["d"][0], o["d"][0]), max(c["d"][1], o["d"][1])]
                c["z"] = [min(c["z"][0], o["z"][0]), max(c["z"][1], o["z"][1])]
                c["faces"] += 1
            else:
                cl.append(dict(o, faces=1))
        obs[part] = cl
    rep.append({"name": st["name"], "p0": [round(p0.x, 3), round(p0.y, 3)], "p1": [round(p1.x, 3), round(p1.y, 3)],
                "L": round(L, 3), "out": [round(out.x, 4), round(out.y, 4)], "z": [z0, z1], "facade_d_m": dmed,
                "ray_runs": runs, "slab_obstacles": obs, "built_pieces": a_["pieces"]})
json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1)
print("PROBE", len(rep))
