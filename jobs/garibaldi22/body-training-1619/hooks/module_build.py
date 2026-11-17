"""Hook `after` stage `body` (#1619 training polygon): build ONE typical-floor module, then replicate it.

Pattern: n/a | new-case: module-first body grid by BM-01..BM-14 (contour + jamb rings + sill/head loops).

blender -b --factory-startup --python module_build.py -- FLOOR.json OUT_DIR [--tex DIR] [--max-side M]
(--tex: DIR/<material>.png is bound to that material when present.)

FLOOR.json (from floor_from_dump.py): rings (plan contours, CCW, metres), per ring `cuts` = sorted perimeter
positions s of the vertical rings (jambs, zone joints), `windows` = [ring, s0, s1], `loops` = module-relative z of
the horizontal loops (0 = module base at the sill line, BM-10), `step`, `z0`, `floors`, `insets` (boxes).
Rules applied: BM-01 contour vertices only at breaks and cut lines; BM-02 loops only at sill/head; BM-03 verticals
are full rings through the module; BM-04/BM-08 insets are separate closed shells in the same object, the wall
under them is not cut; BM-10 the module is built once, checked, then copied with an identical vertex layout;
BM-11 material IDs and UV are set on the module before replication. Writes OUT_DIR/module.blend,
OUT_DIR/body.blend, OUT_DIR/body.fbx and OUT_DIR/build.json; OUT_DIR must be new (nothing is overwritten).
"""
import json
import math
import os
import sys


def box_corners(cx, cy, z0, w, d, h, rot):
    """8 corners: bottom ring then top ring, each (-w/2,0) (w/2,0) (w/2,d) (-w/2,d) in (tangent, outward).

    Box spec [cx, cy, z0, w, d, h, rot] from floor_from_dump.py `insets`: foot on the contour, rot = tangent angle of
    the CCW ring, d along the OUTWARD normal (tangent rotated -90 deg). Round 2 built d along the left normal, so
    every AC basket sat inside the body (Artem 2026-11-17)."""
    vals = (cx, cy, z0, w, d, h, rot)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
        raise ValueError("inset box needs 7 finite numbers, got %r" % (vals,))
    if w <= 0 or d <= 0 or h <= 0:
        raise ValueError("inset box needs w, d, h > 0, got %r" % (vals,))
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    nx, ny = s, -c  # outward normal of a CCW ring = tangent rotated by -90 deg
    out = []
    for dz in (0.0, h):
        for du, dv in ((-w / 2, 0.0), (w / 2, 0.0), (w / 2, d), (-w / 2, d)):
            out.append((cx + c * du + nx * dv, cy + s * du + ny * dv, z0 + dz))
    return out


def inner_offset(xy, r):
    """Points of an open run of a CCW ring moved INTO the body by r (left normal; mitre at inner corners).

    Stage 1 opening reveal (Artem 2026-11-17 «бадик с проемами»): the run a..b of a window, the back edge of its
    откос. Ends use their own segment's normal; inner points the mitre of both, so every reveal face stays planar
    and r deep. Refuses r outside (0, 1) m, a non-finite point, a run shorter than 2 points or a zero segment."""
    if not (isinstance(r, (int, float)) and math.isfinite(r) and 0 < r < 1.0):
        raise ValueError("reveal depth must be finite in (0, 1) m, got %r" % (r,))
    pts = [(float(x), float(y)) for x, y in xy]
    if len(pts) < 2 or not all(math.isfinite(v) for p in pts for v in p):
        raise ValueError("opening run needs >= 2 finite points, got %r" % (xy,))
    nrm = []
    for p, q in zip(pts, pts[1:]):
        L = math.dist(p, q)
        if L < 1e-6:
            raise ValueError("zero-length segment in the opening run at %r" % (p,))
        nrm.append((-(q[1] - p[1]) / L, (q[0] - p[0]) / L))  # left normal of a CCW ring = into the body
    out = []
    for i, (x, y) in enumerate(pts):
        n1 = nrm[max(0, i - 1)]
        n2 = nrm[min(len(nrm) - 1, i)]
        mx, my = n1[0] + n2[0], n1[1] + n2[1]
        m = math.hypot(mx, my)
        if m < 1e-6:
            raise ValueError("opening run folds back on itself at %r" % ((x, y),))
        mx, my = mx / m, my / m
        k = r / (mx * n1[0] + my * n1[1])
        out.append((x + mx * k, y + my * k))
    return out


def _run():  # Blender only; the tests import the pure helpers above
    import bmesh
    import bpy

    args = sys.argv[sys.argv.index("--") + 1:]
    cfg_path, out = args[0], args[1]
    tex_dir = args[args.index("--tex") + 1] if "--tex" in args else None
    max_side = float(args[args.index("--max-side") + 1]) if "--max-side" in args else 0.0
    if os.path.exists(out):
        sys.exit("refused: OUT_DIR exists, outputs are versioned (new folder per run)")
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    step, loops, floors = float(cfg["step"]), [float(z) for z in cfg["loops"]], int(cfg["floors"])
    if not (loops and loops[0] == 0.0 and all(a < b for a, b in zip(loops, loops[1:] + [step])) and floors >= 1):
        sys.exit("loops must start at 0 and rise strictly inside the step; floors >= 1")
    os.makedirs(out)
    TEX_M = float(cfg.get("wall_tile_m", 3.0))

    bpy.ops.wm.read_factory_settings(use_empty=True)


    def material(name, rgb):
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*rgb, 1.0)
        img_path = os.path.join(tex_dir, name + ".png") if tex_dir else None
        if img_path and os.path.exists(img_path):
            m.use_nodes = True
            nt = m.node_tree
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = bpy.data.images.load(img_path)
            nt.links.new(tex.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        return m


    mat_names = list(cfg["materials"])  # e.g. ["WALL_A", "WALL_B", "WINDOW", "INSET"]
    mats = [material(n, tuple(cfg["materials"][n])) for n in mat_names]
    MID = {n: i for i, n in enumerate(mat_names)}


    def ring_points(ring, cuts):
        """Perimeter points of one ring: contour corners plus cut positions, each with its perimeter s."""
        pts, s_acc = [], 0.0
        n = len(ring)
        cuts = sorted(cuts)
        ci = 0
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            L = math.dist(a, b)
            pts.append((s_acc, a[0], a[1], i))
            while ci < len(cuts) and cuts[ci] < s_acc + L - 1e-4:
                if cuts[ci] > s_acc + 1e-4:
                    t = (cuts[ci] - s_acc) / L
                    pts.append((cuts[ci], a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), i))
                ci += 1
            s_acc += L
        if max_side > 0:  # BM-11: no facade face wider than max_side; extra full-height rings split it evenly
            dense = []
            for k, p in enumerate(pts):
                dense.append(p)
                q = pts[k + 1] if k + 1 < len(pts) else (s_acc, pts[0][1], pts[0][2], p[3])
                gap = q[0] - p[0]
                parts = math.ceil(gap / max_side - 1e-9)
                for j in range(1, parts):
                    t = j / parts
                    dense.append((p[0] + t * gap, p[1] + t * (q[1] - p[1]), p[2] + t * (q[2] - p[2]), p[3]))
            pts = dense
        return pts, s_acc


    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    levels = loops + [step]
    report = {"rings": [], "insets": 0}
    for ri, ring in enumerate(cfg["rings"]):
        pts, perim = ring_points(ring["xy"], ring.get("cuts", []))
        wins = [(w[1], w[2], w[3] if len(w) > 3 else 0, w[4] if len(w) > 4 else 1, w[5] if len(w) > 5 else 0.0)
                for w in cfg.get("windows", []) if w[0] == ri]
        for w in wins:
            if not (math.isfinite(w[4]) and 0.0 <= w[4] < 1.0) or not (0 <= w[2] < w[3] < len(levels)):
                sys.exit("window %r: reveal must be finite in [0, 1) m and loops inside the module" % (w,))
        zones = ring.get("zones", [[0.0, perim, "WALL_A"]])
        for z in zones:
            if z[2] not in MID:
                sys.exit("zone material %r is not in materials" % z[2])
        grid = [[bm.verts.new((x, y, z)) for (_, x, y, _) in pts] for z in levels]
        n = len(pts)
        for li in range(len(levels) - 1):
            for k in range(n):
                s0 = pts[k][0]
                s1 = pts[(k + 1) % n][0] if k + 1 < n else perim
                sm = (s0 + s1) / 2
                is_win = any(a - 1e-4 <= sm <= b + 1e-4 and wl <= li < wh for a, b, wl, wh, _ in wins)
                zone = next((z[2] for z in zones if z[0] - 1e-4 <= sm <= z[1] + 1e-4), None)
                if zone is None:
                    sys.exit("ring %d face at s=%.3f is in no finish zone" % (ri, sm))
                if is_win and next(r for a, b, wl, wh, r in wins if a - 1e-4 <= sm <= b + 1e-4 and wl <= li < wh) > 0:
                    continue  # stage 1 opening: the wall has a hole here, the reveal is built below
                f = bm.faces.new((grid[li][k], grid[li][(k + 1) % n], grid[li + 1][(k + 1) % n], grid[li + 1][k]))
                f.material_index = MID["WINDOW"] if is_win else MID[zone]
                z0, z1 = levels[li], levels[li + 1]
                if is_win:
                    a, b = next((a, b) for a, b, wl, wh, _ in wins if a - 1e-4 <= sm <= b + 1e-4)
                    us = ((s0 - a) / (b - a), (s1 - a) / (b - a))
                    vs = ((z0 - levels[0]) / (levels[1] - levels[0]), (z1 - levels[0]) / (levels[1] - levels[0]))
                else:
                    us = (s0 / TEX_M, s1 / TEX_M)
                    vs = (z0 / TEX_M, z1 / TEX_M)
                for lp, (u, v) in zip(f.loops, ((us[0], vs[0]), (us[1], vs[0]), (us[1], vs[1]), (us[0], vs[1]))):
                    lp[uv].uv = (u, v)
        # Stage 1 openings: a reveal tube (jambs, sill, head) from the wall hole back to the frame depth r; the
        # back stays open for the stage-2 window (inset element, D336). Reveal verts are welded to the wall.
        for a, b, wl, wh, r in wins:
            if r <= 0:
                continue
            ks = [k for k in range(n) if a - 1e-4 <= pts[k][0] <= b + 1e-4]
            if len(ks) < 2 or ks != list(range(ks[0], ks[-1] + 1)):
                sys.exit("window [%.3f, %.3f] is not a run of ring points" % (a, b))
            inner = inner_offset([(pts[k][1], pts[k][2]) for k in ks], r)
            zone = next(z[2] for z in zones if z[0] - 1e-4 <= (a + b) / 2 <= z[1] + 1e-4)
            iv = {}

            def ivert(j, li):
                if (j, li) not in iv:
                    iv[(j, li)] = bm.verts.new((inner[j][0], inner[j][1], levels[li]))
                return iv[(j, li)]

            def reveal(quad, want, uvs):
                f = bm.faces.new(quad)
                f.normal_update()
                if f.normal.dot(want) < 0:
                    f.normal_flip()
                f.material_index = MID[zone]
                for lp in f.loops:
                    lp[uv].uv = uvs(lp.vert.co)
                report["reveal_faces"] = report.get("reveal_faces", 0) + 1

            from mathutils import Vector
            t0 = Vector((pts[ks[1]][1] - pts[ks[0]][1], pts[ks[1]][2] - pts[ks[0]][2], 0)).normalized()
            t1 = Vector((pts[ks[-1]][1] - pts[ks[-2]][1], pts[ks[-1]][2] - pts[ks[-2]][2], 0)).normalized()
            for li in range(wl, wh):  # jambs, one quad per band level
                reveal((grid[li][ks[0]], ivert(0, li), ivert(0, li + 1), grid[li + 1][ks[0]]), t0,
                       lambda co: ((co.x + co.y) / TEX_M, co.z / TEX_M))
                j = len(ks) - 1
                reveal((grid[li][ks[-1]], grid[li + 1][ks[-1]], ivert(j, li + 1), ivert(j, li)), -t1,
                       lambda co: ((co.x + co.y) / TEX_M, co.z / TEX_M))
            for j in range(len(ks) - 1):  # sill (faces up) and head (faces down)
                k0, k1 = ks[j], ks[j + 1]
                reveal((grid[wl][k0], grid[wl][k1], ivert(j + 1, wl), ivert(j, wl)), Vector((0, 0, 1)),
                       lambda co: (co.x / TEX_M, co.y / TEX_M))
                reveal((grid[wh][k0], ivert(j, wh), ivert(j + 1, wh), grid[wh][k1]), Vector((0, 0, -1)),
                       lambda co: (co.x / TEX_M, co.y / TEX_M))
            report["openings"] = report.get("openings", 0) + 1
        report["rings"].append({"points": n, "perimeter_m": round(perim, 3)})


    def box(cx, cy, z0, w, d, h, rot):
        vs = [bm.verts.new(p) for p in box_corners(cx, cy, z0, w, d, h, rot)]  # outward side of the ring (inset_geom)
        q = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        for idx in q:
            f = bm.faces.new([vs[i] for i in idx])
            f.material_index = MID["INSET"]
            for lp in f.loops:
                lp[uv].uv = (0.5, 0.5)


    wall_faces = set(bm.faces)
    for ins in cfg.get("insets", []):
        box(*ins["box"])
        report["insets"] += 1
    # walls keep the CCW-ring winding (outward = tangent x up); only the closed inset shells are recalculated,
    # an open tube can be flipped inward by recalc.
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f not in wall_faces])
    me = bpy.data.meshes.new("SM_Body_Module")
    bm.to_mesh(me)
    bm.free()
    used = sorted({p.material_index for p in me.polygons})  # no empty slot travels (stage 1: no WINDOW/INSET)
    remap = {old: new for new, old in enumerate(used)}
    for p in me.polygons:
        p.material_index = remap[p.material_index]
    for old in used:
        me.materials.append(mats[old])
    report["materials"] = [mat_names[i] for i in used]
    mod_ob = bpy.data.objects.new("SM_Body_Module", me)
    bpy.context.scene.collection.objects.link(mod_ob)
    mod_ob.location.z = float(cfg["z0"])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "module.blend"), copy=True)
    report["module"] = {"verts": len(me.vertices), "faces": len(me.polygons),
                        "tris": sum(1 for p in me.polygons if len(p.vertices) == 3)}

    # Replicate (BM-10): Array along Z by the floor step, merge the shared sill loop.
    body = mod_ob.copy()
    body.data = me.copy()
    body.name = body.data.name = "SM_Body_Main"
    bpy.context.scene.collection.objects.link(body)
    bpy.data.objects.remove(mod_ob)
    arr = body.modifiers.new("floors", "ARRAY")
    arr.count = floors
    arr.use_relative_offset, arr.use_constant_offset = False, True
    arr.constant_offset_displace = (0, 0, step)
    arr.use_merge_vertices, arr.merge_threshold = True, 1e-4
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier="floors")
    report["body"] = {"verts": len(body.data.vertices), "faces": len(body.data.polygons), "floors": floors}
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "body.blend"), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "body.fbx"), use_selection=False, mesh_smooth_type="FACE",
                             path_mode="COPY", embed_textures=False)
    json.dump(report, open(os.path.join(out, "build.json"), "w"), indent=1)
    print("BUILT", json.dumps(report))


if __name__ == "__main__":
    _run()
