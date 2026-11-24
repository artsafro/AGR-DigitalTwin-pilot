"""Hook `after` stage `body` (#1619 training polygon, G22): job config of the shared body core + stage-2 modes.

Pattern: n/a | new-case: G22 job hook over the shared core (stage 1 delegated to tools/methods/body/body_lattice.py).

Stage 1 (#1736): blender -b --factory-startup --python module_build.py -- FLOOR.json OUT_DIR [--tex DIR] [--max-side M]
runs the shared core `tools/methods/body/body_lattice_blender.py` unchanged (same as `uv run agr body`); the
builder that lived here (BM-01..BM-14 lattice: stations x loops, reveal tubes, insets, Array replication) moved
to the core. `box_corners`, `inner_offset`, `jamb_uv` are re-exported from the core for the stage-2 code and the
#1619 tests. FLOOR.json from floor_from_dump.py = the plan format `schemas/BodyPlan.schema.json`.
G22 k2 v002r1 job setting: --max-side 3.6 (BM-11).

Mode `stage2` (#1619 polygon stage 2): add window fills, capsules and AC baskets to the ACCEPTED body.

Pattern: n/a | new-case: stage-2 inset elements (D336) on an accepted stage-1 body; the body is appended unchanged.

blender -b --factory-startup --python module_build.py -- stage2 STAGE2.json BODY.blend OUT_DIR [--name k2_s2_v001]

STAGE2.json from `floor_from_dump.py stage2`; BODY.blend = the accepted stage-1 build (its object SM_Body_Main is appended
as is - no vertex, face, UV or material of the body is touched). Per opening and floor (one module, replicated by the
floor step, BM-10) the script adds SEPARATE objects (D336: never welded into the body or into each other):
- SM_Win_Fnn_kk_Frame / _Glass: windowgen_core.build_type (AGR Tools stage `body`, D322) of the window's `entry`
  (Revit panes_m + frame_profile_m from floor_from_dump stage2), parts `frame` / `glass`, frame face at the reveal back r;
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

Mode `stage2-readback` (#1619 polygon stage 2): body unchanged, inset elements checked from the EXPORTED FBX.

Pattern: n/a | new-case: read-back of stage-2 inset elements (frame/glass/flashing/capsule/AC box) on an accepted body.

blender -b --factory-startup --python module_build.py -- stage2-readback EXPORT.fbx ACCEPTED_BODY.fbx STAGE2.json OUT.json

Checks (a defect sets exit code 1):
- body: SM_Body_Main of EXPORT equals the accepted FBX (vertex/face counts, sorted world coordinates, per-loop
  UV and material names) - stage 2 is additive only;
- every element is its own object (D336) and all-quad except the 2 back triangles capsule_core gives each capsule
  (element quad share >= 95 %); frames are closed manifold shells; capsules (D205) and AC
  boxes are open on exactly one side (4 boundary edges), capsule faces look INTO the capsule, glass looks out;
- AC box back boundary lies `embed` behind the facade line (inside the contour), its front outside; capsules are
  inside the contour; every element lies in the body's z range (typical floors only);
- coplanar overlaps (face centroid within 2 mm of another object's face plane, parallel, inside it) = 0 between
  elements and the body and between elements.
OUT is opened with "x".
"""
import collections
import importlib.util
import json
import math
import os
import runpy
import sys
from pathlib import Path

_CORE_DIR = Path(__file__).resolve().parents[4] / "tools" / "methods" / "body"
sys.path.insert(0, str(_CORE_DIR))
from body_lattice import box_corners, inner_offset, jamb_uv  # noqa: E402,F401  (shared core, #1736)


def _run():  # stage 1: the shared core does the whole build
    runpy.run_path(str(_CORE_DIR / "body_lattice_blender.py"), run_name="__main__")


# ---- mode `stage2` (#1619): inset elements on the accepted body ---------------------------------------------
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


def _run_stage2():  # Blender only (mode `stage2`); the tests import the pure helpers above
    import bpy

    args = sys.argv[sys.argv.index("--") + 2:]
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


# ---- mode `stage2-readback` (#1619): read-back of the stage-2 export ---------------------------------------
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


def _run_readback():  # Blender only (mode `stage2-readback`)
    import bpy
    import numpy as np

    args = sys.argv[sys.argv.index("--") + 2:]
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
    if allf and rep["elements_quad_share"] < 0.95:
        bad.append("elements quad share %.4f < 0.95" % rep["elements_quad_share"])
    for k, v in stats.items():
        # capsule_core.planar_capsule triangulates the back (ear_clip): exactly 2 triangles per capsule are the core's
        # output, anything else is a defect
        if k == "capsule" and v.get("tris") == 2 * v.get("objects", 0):
            v["core_back_tris"] = v.pop("tris")
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


MODES = {"stage2": _run_stage2, "stage2-readback": _run_readback}


if __name__ == "__main__":
    _argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    MODES.get(_argv[0] if _argv else "", _run)()
