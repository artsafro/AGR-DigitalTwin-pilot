"""#163 Blender stage: exterior wall segments of the Silikatny OBJ + one frontal, clipped ortho render per wall.

Run by run.py:  blender -b --factory-startup --python blender_walls.py -- <obj> <outdir> <params.json>
Writes walls.json and wall_<id>.png (glass black, other geometry grey, white background).
"""
import json
import math
import sys

import bpy
import mathutils
import numpy as np

src, outdir, pfile = sys.argv[sys.argv.index('--') + 1:][:3]
P = json.load(open(pfile, encoding='utf-8'))
glass = set(P['glass_objects'])
hidden = set(P['hidden_objects'])
facade = set(P['facade_objects'])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=src)
sc = bpy.context.scene
for ob in sc.objects:
    if ob.type != 'MESH':
        continue
    # identical to #161: raw OBJ millimetres -> metres, original Revit X/Y/Z
    ob.matrix_world = mathutils.Matrix.Diagonal((0.001, 0.001, 0.001, 1)) @ mathutils.Matrix.Rotation(
        math.radians(-90), 4, 'X') @ ob.matrix_world
    ob.color = (0, 0, 0, 1) if ob.name in glass else (0.6, 0.6, 0.6, 1)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()

# ---- 1. exterior vertical facade faces ------------------------------------------------------------
Z0, Z1 = P['band_z']
rows = []  # cx, cy, cz, nx, ny, area
for ob in sc.objects:
    if ob.type != 'MESH' or ob.name not in facade:
        continue
    me = ob.data
    n = len(me.polygons)
    cen = np.zeros(n * 3); nor = np.zeros(n * 3); area = np.zeros(n)
    me.polygons.foreach_get('center', cen); me.polygons.foreach_get('normal', nor); me.polygons.foreach_get('area', area)
    M = np.array(ob.matrix_world)
    R = M[:3, :3]
    cen = cen.reshape(-1, 3) @ R.T + M[:3, 3]
    nor = nor.reshape(-1, 3) @ np.linalg.inv(R)  # normal transform (inverse transpose, row form)
    nor /= np.linalg.norm(nor, axis=1, keepdims=True) + 1e-12
    area = area * abs(np.linalg.det(R)) ** (2 / 3)
    keep = (np.abs(nor[:, 2]) < P['vertical_nz']) & (area >= P['min_face_area']) & (cen[:, 2] >= Z0) & (cen[:, 2] <= Z1)
    for c, v, a in zip(cen[keep], nor[keep], area[keep]):
        rows.append((c[0], c[1], c[2], v[0], v[1], a))
rows = np.array(rows)
nh = rows[:, 3:5] / np.linalg.norm(rows[:, 3:5], axis=1, keepdims=True)
el = math.radians(P['sky_elev_deg'])
ext = np.zeros(len(rows), bool)
for i, (r, h) in enumerate(zip(rows, nh)):
    d = mathutils.Vector((h[0] * math.cos(el), h[1] * math.cos(el), math.sin(el)))
    o = mathutils.Vector((r[0] + h[0] * 0.05, r[1] + h[1] * 0.05, r[2]))
    hit = sc.ray_cast(dg, o, d, distance=P['sky_ray_m'])[0]
    ext[i] = not hit
rows, nh = rows[ext], nh[ext]
az = (np.degrees(np.arctan2(nh[:, 1], nh[:, 0])) + 360) % 360

# ---- 2. walls = (azimuth peak, plane offset cluster, connected u-interval) ----------------------
walls = []
for a0 in P['azimuths']:
    dd = np.abs((az - a0 + 180) % 360 - 180)
    sel = dd <= P['az_tol_deg']
    if not sel.any():
        continue
    n = np.array([math.cos(math.radians(a0)), math.sin(math.radians(a0))])
    t = np.array([-n[1], n[0]])
    xy = rows[sel, :2]; ar = rows[sel, 5]
    d = xy @ n; u = xy @ t
    order = np.argsort(d)
    groups, cur = [], [order[0]]
    for i, j in zip(order[:-1], order[1:]):
        if d[j] - d[i] > P['plane_gap_m']:
            groups.append(cur); cur = []
        cur.append(j)
    groups.append(cur)
    for g in groups:
        g = np.array(g)
        ug = np.argsort(u[g]); g = g[ug]
        runs, cur = [], [g[0]]
        for i, j in zip(g[:-1], g[1:]):
            if u[j] - u[i] > P['u_gap_m']:
                runs.append(cur); cur = []
            cur.append(j)
        runs.append(cur)
        for rr in runs:
            rr = np.array(rr)
            A = float(ar[rr].sum())
            u0, u1 = float(u[rr].min()), float(u[rr].max())
            if A < P['min_wall_area'] or u1 - u0 < P['min_wall_len']:
                continue
            dm = float(np.average(d[rr], weights=ar[rr]))
            walls.append(dict(az=int(a0), d=round(dm, 3), u0=round(u0, 3), u1=round(u1, 3), area=round(A, 2),
                              length=round(u1 - u0, 3),
                              p0=[round(float(dm * n[0] + u0 * t[0]), 2), round(float(dm * n[1] + u0 * t[1]), 2)],
                              p1=[round(float(dm * n[0] + u1 * t[0]), 2), round(float(dm * n[1] + u1 * t[1]), 2)]))
walls.sort(key=lambda w: (w['az'], w['d'], w['u0']))
for k, w in enumerate(walls):
    w['id'] = f"W{k:02d}"

# ---- 3. frontal clipped ortho render per wall ----------------------------------------------------
for ob in sc.objects:
    if ob.type == 'MESH' and ob.name in hidden:
        ob.hide_render = True
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'OBJECT'; sh.background_type = 'VIEWPORT'
sh.background_color = (1, 1, 1); sc.view_settings.view_transform = 'Standard'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.sensor_fit = 'HORIZONTAL'
res = P['render_res_m']; m = P['lateral_margin_m']; front, back = P['depth_front_m'], P['depth_back_m']
stand = 10.0
for w in walls:
    a = math.radians(w['az'])
    n = np.array([math.cos(a), math.sin(a)]); t = np.array([-n[1], n[0]])
    width = w['length'] + 2 * m
    uc = (w['u0'] + w['u1']) / 2
    c = w['d'] * n + uc * t
    pos = c + n * (front + stand)
    cam.location = (float(pos[0]), float(pos[1]), (Z0 + Z1) / 2)
    cam.rotation_euler = (math.radians(90), 0, a + math.radians(90))
    cam.data.ortho_scale = width
    cam.data.clip_start = stand; cam.data.clip_end = stand + front + back
    sc.render.resolution_x = max(1, int(round(width / res))); sc.render.resolution_y = int(round((Z1 - Z0) / res))
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1
    sc.render.filepath = f"{outdir}/wall_{w['id']}.png"
    bpy.ops.render.render(write_still=True)
    w['render_w_m'] = round(width, 3)
json.dump(dict(walls=walls, n_ext_faces=int(ext.sum()), n_vert_faces=int(len(ext))), open(f'{outdir}/walls.json', 'w'), indent=1)
print('WALLS_OK', len(walls))
