"""elv-tc-vpm: plan / vertical sections of the clean reference scene in the pilot zone (read-only).

blender -b elv_ref_clean_v001.blend --python ref_sections.py -- <out.json>
Writes segments per cut: {cut: [[cat, name, x0, y0, z0, x1, y1, z1], ...]}. Plotting: plot_sections.py.
Cuts: plan z = -0.3, 1.0, 3.0, 4.5, 5.0, 8.0, 12.5, 13.95; vertical y = -38.0 (lower CW + door), -24.0 (niche),
-10.0, x = 60.0 (south return), x = 77.5 (arcs).
"""
import bpy, sys, json, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
BOX = ((38.0, 82.0), (-53.0, 6.0), (-2.0, 15.0))
cuts = [("z", v) for v in (-0.3, 1.0, 3.0, 4.5, 4.69, 5.0, 8.0, 12.5, 13.95)] + \
       [("y", v) for v in (-38.0, -24.0, -10.0, -48.0)] + [("x", v) for v in (60.0, 77.5)]
AX = {"x": 0, "y": 1, "z": 2}
res = {f"{a}={v}": [] for a, v in cuts}
dg = bpy.context.evaluated_depsgraph_get()
for o in bpy.context.scene.objects:
    if o.type != "MESH":
        continue
    me = o.data
    if not me.vertices:
        continue
    mw = o.matrix_world
    vs = [mw @ v.co for v in me.vertices]
    mn = [min(v[i] for v in vs) for i in range(3)]; mx = [max(v[i] for v in vs) for i in range(3)]
    if mx[0] < BOX[0][0] or mn[0] > BOX[0][1] or mx[1] < BOX[1][0] or mn[1] > BOX[1][1]:
        continue
    cat = o.get("ref_category", "?")
    me.calc_loop_triangles()
    for a, val in cuts:
        i = AX[a]
        if mx[i] < val or mn[i] > val:
            continue
        key = f"{a}={val}"
        for t in me.loop_triangles:
            p = [vs[k] for k in t.vertices]
            d = [q[i] - val for q in p]
            pts = []
            for k in range(3):
                d0, d1 = d[k], d[(k + 1) % 3]
                if (d0 < 0) != (d1 < 0):
                    f = d0 / (d0 - d1)
                    pts.append(p[k].lerp(p[(k + 1) % 3], f))
            if len(pts) == 2:
                res[key].append([cat, o.name[:40]] + [round(c, 4) for c in pts[0]] + [round(c, 4) for c in pts[1]])
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print("SECTIONS", {k: len(v) for k, v in res.items()})
