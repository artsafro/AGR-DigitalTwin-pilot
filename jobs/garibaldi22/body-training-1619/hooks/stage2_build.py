"""Hook `after` stage `body` (#1619 polygon stage 2): add window fills, capsules and AC baskets to the ACCEPTED body.

Pattern: n/a | new-case: stage-2 inset elements (D336) on an accepted stage-1 body; the body is appended unchanged.

blender -b --factory-startup --python stage2_build.py -- STAGE2.json BODY.blend OUT_DIR [--name k2_s2_v001]

STAGE2.json from stage2_from_dump.py; BODY.blend = the accepted stage-1 build (its object SM_Body_Main is appended
as is - no vertex, face, UV or material of the body is touched). Per opening and floor (one module, replicated by the
floor step, BM-10) the script adds SEPARATE objects (D336: never welded into the body or into each other):
- SM_Win_Fnn_kk_Frame / _Glass: windowgen_core.build_type (AGR Tools stage `body`, D322) of the window's `entry`
  (Revit panes_m + frame_profile_m from stage2_from_dump), parts `frame` / `glass`, frame face at the reveal back r;
  mullions and transoms are bars because they are geometry in Revit; sash detail inside a bar is texture;
- SM_Win_Fnn_kk_Flash: flashing (отлив) top + front lip, open sheet sitting on the sill reveal (hook-only, no core);
- SM_Cap_Fnn_kk: capsule_core.planar_capsule (D205) of the opening border at the frame back r + fd: open rim at the
  frame middle, 100 mm outline, 1.0 m deep, faces point INTO it (the core triangulates the back: 2 triangles);
- SM_AC_Fnn_kk: AC box, 5 quads, NO back face, back side `embed` m behind the facade line, no niche (Artem
  2026-11-17 «бокс врезается в стену без заднего полигона»).
The cores are loaded by path from adapters/max/agr_tools (stdlib only); the hook keeps only placement, flashing and
the AC box. Collections: Body, Win_Frame, Win_Glass, Win_Flash, Capsules, AC_Baskets. Writes OUT_DIR/<name>.blend,
<name>.fbx (all objects), <name>_joined.fbx and <name>_joined_noglass.fbx (one mesh, shells NOT merged: metric and
wire sheets only) and build.json (with the per-type core deviations). OUT_DIR must be new.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STANDARD = ROOT / "library" / "windows" / "standard.json"
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

    @classmethod
    def from_core(cls, verts, faces, shift_d=0.0):
        """Wrap a core mesh (verts in local u, d, z) unchanged except a depth shift; faces keep their winding."""
        m = cls()
        m.verts = [(float(p[0]), float(p[1]) + shift_d, float(p[2])) for p in verts]
        m.faces = [tuple(f) for f in faces]
        return m


def load_core(name):
    """AGR Tools core module adapters/max/agr_tools/<name>.py loaded by path (stdlib only, no pymxs)."""
    path = ROOT / "adapters" / "max" / "agr_tools" / (name + ".py")
    spec = importlib.util.spec_from_file_location("agr_core_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_standard(path=STANDARD):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _median(vals):
    s = sorted(vals)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2.0


def window_entry(name, w, h, fd, panes, outer=0.15, gap=0.4):
    """windowgen record of one Revit window: panes_m [[x0, z0, x1, z1]] and the Revit frame_profile_m (D322).

    panes [[u0, u1, z0, z1, (d_glass)]] in the window frame (u from its left edge, z from its sill). Profile from the
    Revit panes: face_m = median distance of the side pane edges within `outer` of the outline, face_bottom_m /
    face_top_m likewise, impost_m = median gap between neighbour panes (<= `gap`, mullions and transoms), depth_m =
    Revit frame depth fd; a window without bars keeps impost_m = face_m (the core then has no impost to place)."""
    side = [p[0] for p in panes if p[0] <= outer] + [w - p[1] for p in panes if w - p[1] <= outer]
    bot = [p[2] for p in panes if p[2] <= outer]
    top = [h - p[3] for p in panes if h - p[3] <= outer]
    if not side:
        raise ValueError("window %s: no pane edge near the frame sides" % name)
    face = _median(side)
    gaps = []
    for i, p in enumerate(panes):
        for q in panes[i + 1:]:
            for a, b in ((p, q), (q, p)):
                if min(a[3], b[3]) - max(a[2], b[2]) > 0.01 and 0 < b[0] - a[1] <= gap:
                    gaps.append(b[0] - a[1])
                if min(a[1], b[1]) - max(a[0], b[0]) > 0.01 and 0 < b[2] - a[3] <= gap:
                    gaps.append(b[2] - a[3])
    prof = {"face_m": round(face, 4), "face_bottom_m": round(_median(bot) if bot else face, 4),
            "face_top_m": round(_median(top) if top else face, 4),
            "impost_m": round(_median(gaps) if gaps else face, 4), "depth_m": round(fd, 4)}
    return {"id": name, "role": "window", "width_m": round(w, 4), "height_m": round(h, 4),
            "panes_m": [[round(p[0], 4), round(p[2], 4), round(p[1], 4), round(p[3], 4)] for p in panes],
            "frame_profile_m": prof, "source": {"revit_type": name, "occurrences": 1}}


def window_module(win, standard, wg):
    """Frame and glass Mesh of one spec window from windowgen_core.build_type(win['entry']), frame face at d = r.

    Returns (frame, glass, info); info: family, status/why, field deviation (core standardize vs the Revit panes, m),
    glass depth shift (core frame middle vs the Revit glass depth, m), number of clamped infill edges."""
    mesh = wg.build_type(win["entry"], standard)
    if mesh["parts"]["grille"] or mesh["parts"]["capsule"]:
        raise ValueError("unexpected grille/capsule part for %s" % win["entry"]["id"])
    r = float(win["r"])
    fr, gl = wg.part_mesh(mesh, "frame"), wg.part_mesh(mesh, "glass")
    src = [rect for _, rect in wg.fields(win["entry"])]
    dev = max((abs(a - b) for (_, n), s in zip(mesh["fields"], src) for a, b in zip(n, s)), default=0.0)
    shift = max((abs(r + mesh["glass_y_m"] - p[4]) for p in win["panes"] if len(p) > 4), default=0.0)
    info = {"family": mesh["family"], "status": mesh["status"], "why": mesh["why"], "field_deviation_m": round(dev, 4),
            "glass_depth_shift_m": round(shift, 4), "glass_d_m": round(r + mesh["glass_y_m"], 4),
            "clamped_infill_edges": len(mesh["clamped_infill_edges"])}
    return Mesh.from_core(fr["verts"], fr["faces"], r), Mesh.from_core(gl["verts"], gl["faces"], r), info


def capsule_module(win, cap, cc):
    """capsule_core.planar_capsule of the opening in local (u, d, z): border = the opening rectangle on the frame back
    plane d = r + fd (the plane win.place puts the rear contour on), wall normal -d (outwards), rim at the frame
    middle (rim = frame_middle, frame_depth_m = fd). Returns (Mesh, core row); refuses a core self-check failure."""
    w, h, r, fd = float(win["w"]), float(win["h"]), float(win["r"]), float(win["fd"])
    db = r + fd
    opening = {"id": 1, "border": [[0.0, db, 0.0], [w, db, 0.0], [w, db, h], [0.0, db, h]],
               "frame": {"z": [0.0, -1.0, 0.0], "x": [1.0, 0.0, 0.0]}, "depth": db}
    opts = cc.options({"outline_m": float(cap["outline"]), "interior_depth_m": float(cap["depth"]),
                       "frame_depth_m": fd})
    row = cc.planar_capsule(opening, opts)
    chk = cc.check_capsule(row)
    if chk["open_off_rim"] or chk["closed_open_edges"] or chk["bad_edges"] or not chk["inward"]:
        raise ValueError("capsule_core self-check failed: %r" % chk)
    return Mesh.from_core(row["verts"], row["faces"]), row


def flashing_sheet(w, top, front, r):
    """Flashing (отлив): top quad at z=top from d=front to the frame front r, and the front lip down to z=0."""
    if not (top > 0 and front < r):
        raise ValueError("flashing needs top > 0 and front < r")
    m = Mesh()
    m.quad([(0, front, top), (w, front, top), (w, r, top), (0, r, top)], (0, 0, 1))
    m.quad([(0, front, 0), (w, front, 0), (w, front, top), (0, front, top)], (0, -1, 0))
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


def build_modules(spec, standard=None):
    """Per-opening module meshes (BM-10: built once, placed per floor) from the cores + the hook-only flashing.

    Returns ([(k, win, frame, glass, flash|None, capsule)], per-type report of the core deviations)."""
    wg, cc = load_core("windowgen_core"), load_core("capsule_core")
    standard = standard if standard is not None else load_standard()
    mods, types = [], {}
    for k, w in enumerate(spec["windows"]):
        fr, gl, info = window_module(w, standard, wg)
        fl = flashing_sheet(w["w"], w["flashing"]["top"], w["flashing"]["front"], w["r"]) if w["flashing"] else None
        cp, _ = capsule_module(w, spec["capsule"], cc)
        mods.append((k, w, fr, gl, fl, cp))
        t = types.setdefault(w["type"], dict(info, count=0, frame_faces=len(fr.faces), glass_faces=len(gl.faces),
                                             capsule_faces=len(cp.faces)))
        t["count"] += 1
        for key in ("field_deviation_m", "glass_depth_shift_m"):
            t[key] = max(t[key], info[key])
    return mods, types


def _run():  # Blender only; the tests import the pure helpers above
    import bpy

    args = sys.argv[sys.argv.index("--") + 1:]
    spec_path, body_blend, out = args[0], args[1], args[2]
    name = args[args.index("--name") + 1] if "--name" in args else "stage2"
    if os.path.exists(out):
        sys.exit("refused: OUT_DIR exists, outputs are versioned (new folder per run)")
    spec = json.load(open(spec_path, encoding="utf-8"))
    mods, types = build_modules(spec)  # refuses before anything is written
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
    rep = {"objects": {}, "faces": {}, "body_signature": body_sig, "types": types,
           "cores": {"window": "adapters/max/agr_tools/windowgen_core.py build_type",
                     "capsule": "adapters/max/agr_tools/capsule_core.py planar_capsule"}}

    def add(kind, ob):
        rep["objects"][kind] = rep["objects"].get(kind, 0) + 1
        rep["faces"][kind] = rep["faces"].get(kind, 0) + len(ob.data.polygons)
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
    with open(os.path.join(out, "build.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False)
    print("BUILT", json.dumps({k: rep[k] for k in ("objects", "faces", "body_untouched")}))


if __name__ == "__main__":
    _run()
