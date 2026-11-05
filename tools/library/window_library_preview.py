"""Preview scene of library/windows/window_types.json for a visual check in Blender (not a production asset).

Every type is laid out flat in the XZ plane, grouped in rows by role: the frame as a 50 mm deep slab with the
glass panes (panes_m) and opaque leaves (opaque_m) as faces 10 mm in front, plus a text label «ID name W×H».
Unconfirmed types get a red label.

blender -b --factory-startup --python tools/library/window_library_preview.py -- <window_types.json> <out.blend>
"""
import json
import sys
from pathlib import Path

import bpy

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
out = Path(out)
if out.exists():
    raise SystemExit(f"output exists, refusing to overwrite: {out}")
types = json.loads(Path(src).read_text(encoding="utf-8"))["types"]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"


def mat(name, rgba, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgba, alpha)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgba, 1.0)
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


M_FRAME = mat("frame", (0.08, 0.08, 0.09))
M_GLASS = mat("glass", (0.35, 0.6, 0.75), 0.6)
M_OPAQUE = mat("leaf", (0.45, 0.45, 0.47))
M_LABEL = mat("label", (0.9, 0.9, 0.9))
M_LABEL_U = mat("label_unconfirmed", (0.9, 0.2, 0.15))


def box(name, x0, z0, x1, z1, y0, y1, m, coll):
    me = bpy.data.meshes.new(name)
    v = [(x, y, z) for y in (y0, y1) for z in (z0, z1) for x in (x0, x1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def quad(name, x0, z0, x1, z1, y, m, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [], [(0, 1, 2, 3)])
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


ROLE_ORDER = ["window", "curtain", "balcony_block", "door", "door_system", "gate", "revolving_door"]
rows = {}
for t in types:
    rows.setdefault(t.get("role") or "other", []).append(t)
z_cursor = 0.0
GAP = 1.0
for role in ROLE_ORDER + sorted(r for r in rows if r not in ROLE_ORDER):
    items = rows.get(role)
    if not items:
        continue
    coll = bpy.data.collections.new(f"{role} ({len(items)})")
    sc.collection.children.link(coll)
    row_h = max(t["height_m"] for t in items)
    x = 0.0
    for t in items:
        w, h = t["width_m"], t["height_m"]
        tid = t["id"]
        tc = bpy.data.collections.new(tid)
        coll.children.link(tc)
        box(f"{tid}_frame", x, z_cursor, x + w, z_cursor + h, 0.0, 0.05, M_FRAME, tc)
        for i, (a, b, c, d) in enumerate(t.get("panes_m") or []):
            quad(f"{tid}_pane{i + 1}", x + a, z_cursor + b, x + c, z_cursor + d, -0.01, M_GLASS, tc)
        for i, (a, b, c, d) in enumerate(t.get("opaque_m") or []):
            quad(f"{tid}_leaf{i + 1}", x + a, z_cursor + b, x + c, z_cursor + d, -0.011, M_OPAQUE, tc)
        cu = bpy.data.curves.new(f"{tid}_label", "FONT")
        cu.body = f"{tid}\n{t.get('name', '')}\n{w:.2f}×{h:.2f}" + ("" if t.get("status") == "confirmed" else "\n(unconfirmed)")
        cu.size = 0.16
        lab = bpy.data.objects.new(f"{tid}_label", cu)
        lab.location = (x, -0.02, z_cursor - 0.25)
        lab.rotation_euler = (1.5708, 0, 0)
        cu.materials.append(M_LABEL if t.get("status") == "confirmed" else M_LABEL_U)
        tc.objects.link(lab)
        x += max(w, 2.2) + GAP
    z_cursor -= row_h + 1.6

cam = bpy.data.objects.new("Front", bpy.data.cameras.new("Front"))
sc.collection.objects.link(cam)
cam.location = (40, -60, z_cursor / 2)
cam.rotation_euler = (1.5708, 0, 0)
cam.data.type = "ORTHO"
cam.data.ortho_scale = 90
sc.camera = cam
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print("WINDOW_PREVIEW", len(types), {r: len(v) for r, v in rows.items()}, str(out))
