"""Hook `after` stage `body` (#1619 polygon stage 2): add window fills, capsules and AC baskets to the ACCEPTED body.

Pattern: n/a | new-case: stage-2 inset elements (D336) on an accepted stage-1 body; the body is appended unchanged.

blender -b --factory-startup --python stage2_build.py -- STAGE2.json BODY.blend OUT_DIR [--name k2_s2_v001]

STAGE2.json from stage2_from_dump.py; BODY.blend = the accepted stage-1 build (its object SM_Body_Main is appended
as is - no vertex, face, UV or material of the body is touched). Per opening and floor (one module, replicated by the
floor step, BM-10) the script adds SEPARATE objects (D336: never welded into the body or into each other):
- SM_Win_Fnn_kk_Frame: closed quad shell of the frame bars (opening minus panes) from the reveal back r to r + fd;
  mullions and transoms are bars because they are geometry in Revit; sash detail inside a bar is texture;
- SM_Win_Fnn_kk_Glass: one outward quad per pane at the Revit glass depth;
- SM_Win_Fnn_kk_Flash: flashing (отлив) top + front lip, open sheet sitting on the sill reveal;
- SM_Cap_Fnn_kk: D205 capsule - open at the frame middle, 100 mm outline, 1.0 m deep, faces point INTO it;
- SM_AC_Fnn_kk: AC box, 5 quads, NO back face, back side `embed` m behind the facade line, no niche (Artem
  2026-11-17 «бокс врезается в стену без заднего полигона»).
Collections: Body, Win_Frame, Win_Glass, Win_Flash, Capsules, AC_Baskets. Writes OUT_DIR/<name>.blend, <name>.fbx
(all objects), <name>_joined.fbx and <name>_joined_noglass.fbx (one mesh, shells NOT merged: metric and wire
sheets only) and build.json. OUT_DIR must be new.
"""
import json
import math
import os
import sys

TEX_M = 1.0  # UV metres per tile for frames, flashings and baskets (colour materials; panels = texture, D336)


def _norm(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def _quad(verts, idx, want):
    """Order quad idx so its normal (Newell) points along `want`."""
    p = [verts[i] for i in idx]
    n = [0.0, 0.0, 0.0]
    for i in range(4):
        a, b = p[i], p[(i + 1) % 4]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    if sum(x * y for x, y in zip(n, want)) < 0:
        idx = idx[::-1]
    return tuple(idx)


class Mesh:
    """Tiny vertex-deduplicating quad builder in local (u, d, z): u along the opening, d into the body, z up."""

    def __init__(self):
        self.verts, self.faces, self._key = [], [], {}

    def v(self, p):
        k = tuple(round(c, 6) for c in p)
        if k not in self._key:
            self._key[k] = len(self.verts)
            self.verts.append(tuple(float(c) for c in p))
        return self._key[k]

    def quad(self, pts, want):
        idx = [self.v(p) for p in pts]
        if len(set(idx)) != 4:
            raise ValueError("degenerate quad %r" % (pts,))
        self.faces.append(_quad(self.verts, idx, want))


def frame_shell(w, h, panes, d0, d1):
    """Closed quad shell of the window frame: rectangle 0..w x 0..h minus the panes, from depth d0 to d1.

    Grid lines = the opening and pane edges; a cell inside a pane is a hole. Front faces (d0) look out (-d), back
    faces (d1) look in (+d); side faces close every solid/hole and solid/outside border. Refuses panes outside the
    opening, overlapping panes and d1 <= d0."""
    if not (d1 > d0):
        raise ValueError("frame depth must be > 0")
    for p in panes:
        if not (0 < p[0] < p[1] < w and 0 < p[2] < p[3] < h):
            raise ValueError("pane %r is not inside the opening %.3f x %.3f" % (p, w, h))
    for i, p in enumerate(panes):
        for q in panes[i + 1:]:
            if p[0] < q[1] and q[0] < p[1] and p[2] < q[3] and q[2] < p[3]:
                raise ValueError("panes %r and %r overlap" % (p, q))
    us = sorted({0.0, w} | {p[0] for p in panes} | {p[1] for p in panes})
    zs = sorted({0.0, h} | {p[2] for p in panes} | {p[3] for p in panes})

    def solid(i, j):
        if not (0 <= i < len(us) - 1 and 0 <= j < len(zs) - 1):
            return False
        cu, cz = (us[i] + us[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
        return not any(p[0] < cu < p[1] and p[2] < cz < p[3] for p in panes)
    m = Mesh()
    for i in range(len(us) - 1):
        for j in range(len(zs) - 1):
            if not solid(i, j):
                continue
            u0, u1, z0, z1 = us[i], us[i + 1], zs[j], zs[j + 1]
            m.quad([(u0, d0, z0), (u1, d0, z0), (u1, d0, z1), (u0, d0, z1)], (0, -1, 0))
            m.quad([(u0, d1, z0), (u1, d1, z0), (u1, d1, z1), (u0, d1, z1)], (0, 1, 0))
            if not solid(i - 1, j):
                m.quad([(u0, d0, z0), (u0, d1, z0), (u0, d1, z1), (u0, d0, z1)], (-1, 0, 0))
            if not solid(i + 1, j):
                m.quad([(u1, d0, z0), (u1, d1, z0), (u1, d1, z1), (u1, d0, z1)], (1, 0, 0))
            if not solid(i, j - 1):
                m.quad([(u0, d0, z0), (u1, d0, z0), (u1, d1, z0), (u0, d1, z0)], (0, 0, -1))
            if not solid(i, j + 1):
                m.quad([(u0, d0, z1), (u1, d0, z1), (u1, d1, z1), (u0, d1, z1)], (0, 0, 1))
    return m


def glass_quads(panes):
    """One outward (-d) quad per pane [u0, u1, z0, z1, d]."""
    m = Mesh()
    for u0, u1, z0, z1, d in panes:
        m.quad([(u0, d, z0), (u1, d, z0), (u1, d, z1), (u0, d, z1)], (0, -1, 0))
    return m


def flashing_sheet(w, top, front, r):
    """Flashing (отлив): top quad at z=top from d=front to the frame front r, and the front lip down to z=0."""
    if not (top > 0 and front < r):
        raise ValueError("flashing needs top > 0 and front < r")
    m = Mesh()
    m.quad([(0, front, top), (w, front, top), (w, r, top), (0, r, top)], (0, 0, 1))
    m.quad([(0, front, 0), (w, front, 0), (w, front, top), (0, front, top)], (0, -1, 0))
    return m


def capsule_box(w, h, dm, depth, outline):
    """D205 capsule: open at d=dm, u -outline..w+outline, z -outline..h+outline, back at dm+depth; normals INWARD."""
    o = outline
    u0, u1, z0, z1, d0, d1 = -o, w + o, -o, h + o, dm, dm + depth
    m = Mesh()
    m.quad([(u0, d1, z0), (u1, d1, z0), (u1, d1, z1), (u0, d1, z1)], (0, -1, 0))  # back looks to the window
    m.quad([(u0, d0, z0), (u0, d1, z0), (u0, d1, z1), (u0, d0, z1)], (1, 0, 0))
    m.quad([(u1, d0, z0), (u1, d1, z0), (u1, d1, z1), (u1, d0, z1)], (-1, 0, 0))
    m.quad([(u0, d0, z0), (u1, d0, z0), (u1, d1, z0), (u0, d1, z0)], (0, 0, 1))
    m.quad([(u0, d0, z1), (u1, d0, z1), (u1, d1, z1), (u0, d1, z1)], (0, 0, -1))
    return m


def basket_box(w, out, embed, z0, z1):
    """AC box centred on u=0: from d=embed (behind the facade, in the wall) to d=-out (outside); 5 outward quads,
    NO back face (Artem 2026-11-17)."""
    if not (w > 0 and out > 0 and embed > 0 and z1 > z0):
        raise ValueError("basket needs w, out, embed > 0 and z1 > z0")
    u0, u1, db, df = -w / 2, w / 2, embed, -out
    m = Mesh()
    m.quad([(u0, df, z0), (u1, df, z0), (u1, df, z1), (u0, df, z1)], (0, -1, 0))
    m.quad([(u0, df, z0), (u0, db, z0), (u0, db, z1), (u0, df, z1)], (-1, 0, 0))
    m.quad([(u1, df, z0), (u1, db, z0), (u1, db, z1), (u1, df, z1)], (1, 0, 0))
    m.quad([(u0, df, z0), (u1, df, z0), (u1, db, z0), (u0, db, z0)], (0, 0, -1))
    m.quad([(u0, df, z1), (u1, df, z1), (u1, db, z1), (u0, db, z1)], (0, 0, 1))
    return m


def to_world(p, a, t, zb):
    """Local (u, d, z) -> world: a + t*u + n_in*d, z + zb; n_in = left normal of the CCW ring (into the body)."""
    u, d, z = p
    return (a[0] + t[0] * u - t[1] * d, a[1] + t[1] * u + t[0] * d, zb + z)


def planar_uv(p, n, scale=TEX_M):
    """Box-projected UV of a local point by the dominant axis of the face normal n, scale m per tile."""
    ax = max(range(3), key=lambda i: abs(n[i]))
    u, d, z = p
    if ax == 1:
        return (u / scale, z / scale)
    if ax == 0:
        return (d / scale, z / scale)
    return (u / scale, d / scale)


def _run():  # Blender only; the tests import the pure helpers above
    import bpy

    args = sys.argv[sys.argv.index("--") + 1:]
    spec_path, body_blend, out = args[0], args[1], args[2]
    name = args[args.index("--name") + 1] if "--name" in args else "stage2"
    if os.path.exists(out):
        sys.exit("refused: OUT_DIR exists, outputs are versioned (new folder per run)")
    spec = json.load(open(spec_path, encoding="utf-8"))
    os.makedirs(out)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(body_blend, link=False) as (src, dst):
        if "SM_Body_Main" not in src.objects:
            sys.exit("refused: %s has no SM_Body_Main" % body_blend)
        dst.objects = ["SM_Body_Main"]
    body = dst.objects[0]
    scene = bpy.context.scene

    def coll(n):
        c = bpy.data.collections.new(n)
        scene.collection.children.link(c)
        return c
    C = {k: coll(k) for k in ("Body", "Win_Frame", "Win_Glass", "Win_Flash", "Capsules", "AC_Baskets")}
    C["Body"].objects.link(body)
    body_sig = (len(body.data.vertices), len(body.data.polygons), round(sum(v.co.x + v.co.y + v.co.z for v in body.data.vertices), 4))

    def material(n, rgb, alpha=1.0):
        m = bpy.data.materials.new(n)
        m.diffuse_color = (*rgb, alpha)
        return m
    M = {"FRAME": material("WIN_FRAME", (0.82, 0.82, 0.80)), "GLASS": material("WIN_GLASS", (0.20, 0.30, 0.38), 0.6),
         "FLASH": material("WIN_FLASHING", (0.55, 0.56, 0.58)), "CAP": material("CAPSULE_INTERIOR", (0.62, 0.55, 0.47)),
         "AC": material("AC_GRILLE", (0.30, 0.31, 0.33))}

    def emit(mesh, nm, a, t, zb, mat, collection, uv_fn):
        me = bpy.data.meshes.new(nm)
        world = [to_world(p, a, t, zb) for p in mesh.verts]
        me.from_pydata(world, [], [list(f) for f in mesh.faces])
        me.materials.append(M[mat])
        lay = me.uv_layers.new(name="UVMap")
        for poly, f in zip(me.polygons, mesh.faces):
            loc = [mesh.verts[i] for i in f]
            n = _norm(loc[0], loc[1], loc[2])
            for li, p in zip(poly.loop_indices, loc):
                lay.data[li].uv = uv_fn(p, n, loc)
        me.validate()
        me.update()
        ob = bpy.data.objects.new(nm, me)
        collection.objects.link(ob)
        return ob

    def uv_box(p, n, loc):
        return planar_uv(p, n)

    def uv_unit(p, n, loc):  # 0..1 per face (glass, capsule walls: one picture per face)
        ax = max(range(3), key=lambda i: abs(n[i]))
        ia, ib = [(0, 2), (1, 2), (0, 1)][[1, 0, 2].index(ax)]
        lo_a, hi_a = min(q[ia] for q in loc), max(q[ia] for q in loc)
        lo_b, hi_b = min(q[ib] for q in loc), max(q[ib] for q in loc)
        return ((p[ia] - lo_a) / (hi_a - lo_a), (p[ib] - lo_b) / (hi_b - lo_b))

    z0, step, floors = float(spec["z0"]), float(spec["step"]), int(spec["floors"])
    cap = spec["capsule"]
    rep = {"objects": {}, "faces": {}, "body_signature": body_sig}

    def add(kind, ob):
        rep["objects"][kind] = rep["objects"].get(kind, 0) + 1
        rep["faces"][kind] = rep["faces"].get(kind, 0) + len(ob.data.polygons)
    mods = []
    for k, w in enumerate(spec["windows"]):  # module meshes built once (BM-10), placed per floor
        panes = [p[:4] for p in w["panes"]]
        fr = frame_shell(w["w"], w["h"], panes, w["r"], w["r"] + w["fd"])
        gl = glass_quads(w["panes"])
        fl = flashing_sheet(w["w"], w["flashing"]["top"], w["flashing"]["front"], w["r"]) if w["flashing"] else None
        cp = capsule_box(w["w"], w["h"], w["r"] + w["fd"] / 2, cap["depth"], cap["outline"])
        mods.append((k, w, fr, gl, fl, cp))
    for f in range(floors):
        zb = z0 + f * step
        for k, w, fr, gl, fl, cp in mods:
            tag = "F%02d_%02d" % (f + 1, k + 1)
            add("frame", emit(fr, "SM_Win_%s_Frame" % tag, w["a"], w["t"], zb, "FRAME", C["Win_Frame"], uv_box))
            add("glass", emit(gl, "SM_Win_%s_Glass" % tag, w["a"], w["t"], zb, "GLASS", C["Win_Glass"], uv_unit))
            if fl:
                add("flash", emit(fl, "SM_Win_%s_Flash" % tag, w["a"], w["t"], zb, "FLASH", C["Win_Flash"], uv_box))
            add("capsule", emit(cp, "SM_Cap_%s" % tag, w["a"], w["t"], zb, "CAP", C["Capsules"], uv_unit))
        for k, b in enumerate(spec["baskets"]):
            bx = basket_box(b["w"], b["out"], b["embed"], b["z0"], b["z1"])
            add("basket", emit(bx, "SM_AC_F%02d_%02d" % (f + 1, k + 1), b["c"], b["t"], zb, "AC", C["AC_Baskets"], uv_box))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, name + ".blend"), copy=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, name + ".fbx"), use_selection=False, mesh_smooth_type="FACE",
                             path_mode="COPY", embed_textures=False)

    def joined(fname, skip):
        sel = [o for o in scene.objects if o.type == "MESH" and not any(o.name.startswith(s) for s in skip)]
        copies = []
        for o in sel:
            c = o.copy()
            c.data = o.data.copy()
            scene.collection.objects.link(c)
            copies.append(c)
        bpy.ops.object.select_all(action="DESELECT")
        for c in copies:
            c.select_set(True)
        bpy.context.view_layer.objects.active = copies[0]
        bpy.ops.object.join()
        j = bpy.context.view_layer.objects.active
        j.name = "SM_Stage2_Joined"
        bpy.ops.export_scene.fbx(filepath=os.path.join(out, fname), use_selection=True, mesh_smooth_type="FACE",
                                 path_mode="COPY", embed_textures=False)
        rep.setdefault("joined", {})[fname] = len(j.data.polygons)
        bpy.data.objects.remove(j)
    joined(name + "_joined.fbx", [])
    joined(name + "_joined_noglass.fbx", ["SM_Win_F"])  # frames/glass/flash hidden: capsule close-ups
    after = (len(body.data.vertices), len(body.data.polygons), round(sum(v.co.x + v.co.y + v.co.z for v in body.data.vertices), 4))
    rep["body_untouched"] = after == body_sig
    json.dump(rep, open(os.path.join(out, "build.json"), "w"), indent=1)
    print("BUILT", json.dumps(rep))


if __name__ == "__main__":
    _run()
