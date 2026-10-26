"""Build one windows-glazing variant of a benchmark model in factory Blender (methods catalog, #721).

Pattern: new-case: Blender driver for the windows-glazing variants (bmesh frames, numpy planes / trim).

    blender --background --factory-startup --python-exit-code 1 \\
        --python tools/methods/windows/build_variant_blender.py -- <model.fbx> <out.fbx> <variant> \\
        tile=<UDIM> [glass_map=<metallic.png>] [texture=<file name.png>] [texture_side=<px>]

Glass source, first that applies: the `*_MainGlass` object; else the Main polygons whose UV centre is white
(> 0.5) on `glass_map` (the metallic map, glass white per reg p.9 §5.10, WIN-08); else none (0 openings,
the model is exported unchanged). The glass source is removed and replaced by the variant's windows; every
other mesh (body, UCX pieces, accessories) is exported as it is; a non-mesh object is reported in
`dropped_objects` with its reason. New UVs go to UDIM `tile`. The variant's new material
(`M_<address>_Main_<Frame|WindowAtlas|FrameTrim>`) gets our generated diffuse `texture` (default
`T_<address>_<kind>.png`, `texture_side` px, default 1024), written next to `<out>` and bound to its Base Color.
The FBX is exported to a staging file this invocation creates exclusively (`~<out stem>.<random>.staging.fbx`,
mkstemp, never a predictable name, so an unrelated file next to `<out>` is never overwritten or removed), read
back in a clean scene and published as `<out>` only when the read-back mesh inventory reconciles with the source
one (unchanged meshes keep triangles, slots and world bounding box) and the new material samples exactly the
written PNG; else only that staging FBX and the PNG are removed. `WINDOWS_VARIANT_FAULT=readback` (test seam)
forces the read-back gate to fail; any other non-empty value is refused (exit 4). `<out>.variant.json` records the build wall time (after import, up to the end of the export),
openings, drops with reasons, the inventories and any error. Exit 0 built; 2 build failed (report written,
no FBX published); 4 refused before any write (bad arguments, a destination aliasing an input).
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


wv = _load("methods_windows_variants", "tools/methods/windows/windows_variants.py")
ua = _load("ucx_audit", "src/twinqa/geometry/ucx_audit.py")


FAULTS = ("readback",)  # test seam: WINDOWS_VARIANT_FAULT=readback forces the read-back gate to fail


def _fault_error(value):
    """None for an unset/empty or known WINDOWS_VARIANT_FAULT; else an error naming the value."""
    if value in ("",) + FAULTS:
        return None
    return f"unknown WINDOWS_VARIANT_FAULT={value!r}; known: {list(FAULTS)}"


def _staging(out):
    """Exclusively create a unique, invocation-owned staging FBX next to <out> (O_EXCL via mkstemp)."""
    import os
    import tempfile

    fd, name = tempfile.mkstemp(prefix=f"~{out.stem}.", suffix=".staging.fbx", dir=out.parent)
    os.close(fd)
    return Path(name)


def _parse(argv):
    if len(argv) < 4:
        return None, ("usage -- <model.fbx> <out.fbx> <variant> tile=<UDIM> [glass_map=<png>] "
                      "[texture=<name.png>] [texture_side=<px>]")
    if argv[2] not in wv.VARIANTS:
        return None, f"unknown variant {argv[2]!r}; expected one of {wv.VARIANTS}"
    if not argv[1].lower().endswith(".fbx"):
        return None, "output must be an .fbx path"
    opts = {}
    for a in argv[3:]:
        k, sep, val = a.partition("=")
        if not sep or k not in ("tile", "glass_map", "texture", "texture_side") or k in opts:
            return None, (f"bad option {a!r} (tile=<UDIM> once; glass_map=<png>, texture=<name.png>, "
                          "texture_side=<px> at most once)")
        opts[k] = val
    if "tile" not in opts:
        return None, "tile=<UDIM> is required"
    try:
        opts["tile"] = int(opts["tile"])
        wv.tile_offset(opts["tile"])
    except ValueError as exc:
        return None, f"bad tile: {exc}"
    if "glass_map" in opts and not Path(opts["glass_map"]).is_file():
        return None, f"glass_map {opts['glass_map']} does not exist"
    if "texture" in opts:
        t = opts["texture"]
        if Path(t).name != t or not t.lower().endswith(".png") or len(t) <= 4:
            return None, f"texture {t!r} must be a bare file name ending .png (it is written next to the output)"
    try:
        opts["texture_side"] = int(opts.get("texture_side", 1024))
        if not 16 <= opts["texture_side"] <= 16384:
            raise ValueError(f"{opts['texture_side']} outside 16..16384")
    except ValueError as exc:
        return None, f"bad texture_side: {exc}"
    return opts, None


def _world_polys(obj, indices=None):
    import numpy as np

    mw = np.array(obj.matrix_world)
    me = obj.data
    co = np.array([v.co[:] for v in me.vertices], float).reshape(-1, 3)
    co = co @ mw[:3, :3].T + mw[:3, 3]
    polys = me.polygons if indices is None else [me.polygons[i] for i in indices]
    return [co[list(p.vertices)] for p in polys]


def _glass_by_map(main, png):
    """Main polygon indices whose UV centre samples > 0.5 on the (untiled, wrapped) map's red channel."""
    import bpy
    import numpy as np

    img = bpy.data.images.load(str(png), check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    red = px.reshape(h, w, 4)[:, :, 0]
    me = main.data
    uv = me.uv_layers.active.data
    hits = []
    for p in me.polygons:
        c = np.mean([uv[li].uv[:] for li in p.loop_indices], axis=0) % 1.0
        if red[min(h - 1, int(c[1] * h)), min(w - 1, int(c[0] * w))] > 0.5:
            hits.append(p.index)
    bpy.data.images.remove(img)
    return hits


def _material(name, existing=None):
    import bpy

    return existing or bpy.data.materials.get(name) or bpy.data.materials.new(name)


def _new_material(name):
    """A fresh material; a source material of the same name is an error naming it, never reused."""
    import bpy

    if bpy.data.materials.get(name) is not None:
        raise ValueError(f"source already has a material {name!r}; the variant material would collide")
    return bpy.data.materials.new(name)


def _textured(mat, png: Path, variant: str, side: int, grid: int):
    """Write our generated diffuse to `png` and bind it to the Base Color of `mat` (Principled BSDF)."""
    import bpy

    img = bpy.data.images.new(png.stem, side, side, alpha=True)
    img.pixels.foreach_set(wv.texture_pixels(variant, side, grid).ravel())
    img.filepath_raw = str(png)
    img.file_format = "PNG"
    img.save()
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def _sha256(path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh_inventory(objects) -> dict:
    """{mesh name: {"tris", "slots", "bbox"}} in world metres (the reconciliation entries)."""
    import numpy as np

    inv = {}
    for o in objects:
        me = o.data
        mw = np.array(o.matrix_world)
        co = np.array([v.co[:] for v in me.vertices], float).reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        bbox = [co.min(axis=0).tolist(), co.max(axis=0).tolist()] if len(co) else None
        inv[o.name] = {"tris": int(sum(len(p.vertices) - 2 for p in me.polygons)),
                       "slots": [s.material.name if s.material else None for s in o.material_slots], "bbox": bbox}
    return inv


def _image_file(img, tile):
    """The file a read-back image node samples for UDIM `tile` (tiled images resolved per tile)."""
    import bpy

    path = bpy.path.abspath(img.filepath, library=img.library)
    if img.source == "TILED":
        path = path.replace("<UDIM>", str(tile))
    return Path(path)


def readback_check(fbx: Path, expected: dict, gen_mat: str | None, png: Path | None, png_sha: str | None,
                   tile: int) -> dict:
    """Import `fbx` into a clean scene and reconcile it: mesh inventory vs `expected` and, for the new
    material, a linked Base Color image node whose file is `png` with `png_sha`, used by >= 1 polygon whose
    UV centre is inside `tile`. Returns the facts; `problems` empty = reconciled."""
    import bpy
    import numpy as np

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    actual = mesh_inventory(meshes)
    problems = wv.inventory_diff(expected, actual)
    facts = {"meshes": sorted(actual)}
    if gen_mat is not None:
        mat = bpy.data.materials.get(gen_mat)
        files = []
        if mat is None or mat.node_tree is None:
            problems.append(f"{gen_mat}: not in the read-back scene")
        else:
            bsdf_inputs = [lk for lk in mat.node_tree.links if lk.to_socket.name == "Base Color"
                           and lk.from_node.type == "TEX_IMAGE" and lk.from_node.image is not None]
            files = [_image_file(lk.from_node.image, tile) for lk in bsdf_inputs]
            if len(files) != 1:
                problems.append(f"{gen_mat}: {len(files)} image nodes linked to Base Color (expected 1)")
            elif not files[0].is_file() or not png.is_file() or not files[0].samefile(png):
                problems.append(f"{gen_mat}: Base Color samples {files[0]}, not the written {png}")
            elif _sha256(files[0]) != png_sha:
                problems.append(f"{gen_mat}: bound image bytes differ from the written PNG")
        du, dv = wv.tile_offset(tile)
        used, outside = 0, 0
        for o in meshes:
            slots = [s.material.name if s.material else None for s in o.material_slots]
            if gen_mat not in slots or not o.data.uv_layers:
                continue
            k = slots.index(gen_mat)
            uv = o.data.uv_layers.active.data
            for p in o.data.polygons:
                if p.material_index != k:
                    continue
                c = np.mean([uv[li].uv[:] for li in p.loop_indices], axis=0)
                used += 1
                outside += not (du <= c[0] <= du + 1 and dv <= c[1] <= dv + 1)
        if used == 0:
            problems.append(f"{gen_mat}: no read-back polygon uses it")
        if outside:
            problems.append(f"{gen_mat}: {outside} of {used} polygons have their UV centre outside tile {tile}")
        facts.update({"material": gen_mat, "image_files": [str(f) for f in files], "polygons": used})
    facts["problems"] = problems
    return facts


def _new_object(name, verts, faces, uvs, material, uv_name, matrix=None):
    import bpy
    import numpy as np

    pts = np.asarray(verts, float).reshape(-1, 3)
    if matrix is not None:  # world -> the target object's local space (shared pivot, WIN-14)
        inv = np.array(matrix.inverted())
        pts = pts @ inv[:3, :3].T + inv[:3, 3]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, p)) for p in pts], [], [tuple(map(int, f)) for f in faces])
    layer = me.uv_layers.new(name=uv_name)
    li = 0
    for poly in me.polygons:
        for k, _ in enumerate(poly.loop_indices):
            layer.data[li].uv = tuple(map(float, uvs[poly.index][k]))
            li += 1
    me.materials.append(material)
    me.update()
    ob = bpy.data.objects.new(name, me)
    if matrix is not None:
        ob.matrix_world = matrix
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _bmesh_frame(o):
    """modelled-frames, one opening: inset ring, mullions by grid subdivide + inset, panes out, solidify.

    Built in the opening's own frame (x = u, y = v, z = n, origin at its centre): bmesh coordinates are
    float32, so building at world coordinates hundreds of metres from the origin loses the 1e-4 m tests."""
    import bmesh
    import numpy as np

    plan = wv.frame_plan(o)
    hw, hh, fw, tol = o["width"] / 2, o["height"] / 2, plan["frame_w"], 1e-4
    bm = bmesh.new()
    face = bm.faces.new([bm.verts.new(p) for p in ((-hw, -hh, 0.0), (hw, -hh, 0.0), (hw, hh, 0.0), (-hw, hh, 0.0))])
    bm.normal_update()  # inset ops move along the face normal: without it the ring is degenerate
    bmesh.ops.inset_individual(bm, faces=[face], thickness=fw, depth=0.0, use_even_offset=True)
    inner = [face]
    if plan["panes"] > 1:
        horiz = [e for e in face.edges if abs(e.verts[1].co.x - e.verts[0].co.x) > tol]
        bmesh.ops.subdivide_edges(bm, edges=horiz, cuts=plan["panes"] - 1, use_grid_fill=True)
        inner = [f for f in bm.faces  # panes = faces with every corner inside the inner rectangle
                 if all(abs(v.co.x) <= hw - fw + tol and abs(v.co.y) <= hh - fw + tol for v in f.verts)]
        bm.normal_update()
        bmesh.ops.inset_individual(bm, faces=inner, thickness=plan["mullion_w"] / 2, use_even_offset=True)
    local_glass = [np.array([v.co[:] for v in f.verts], float) for f in inner]
    bmesh.ops.delete(bm, geom=inner, context="FACES_ONLY")
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=plan["depth"])
    bm.verts.index_update()
    co = np.array([v.co[:] for v in bm.verts], float)
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    co[:, 2] -= (co[:, 2].max() + co[:, 2].min()) / 2  # centre the frame depth on the glass plane
    basis = np.stack([o["u"], o["v"], o["n"]])
    verts = o["centre"] + co @ basis
    glass = [o["centre"] + g @ basis for g in local_glass]
    pane_area = sum(float(np.linalg.norm(wv._newell(g))) for g in glass)
    if not faces or not glass:  # fail closed: an opening never silently loses its frame or its glass
        raise ValueError(f"bmesh frame of opening at {np.round(o['centre'], 3).tolist()} gave {len(faces)} "
                         f"frame faces and {len(glass)} panes")
    if pane_area >= 0.99 * o["width"] * o["height"]:
        raise ValueError(f"bmesh inset did not move: panes cover {pane_area:.3f} m2 of {o['width'] * o['height']:.3f}")
    return verts, faces, glass


def _by_reason(dropped):
    """Dropped glass polygons per reason kind (the reason text up to its first number)."""
    import re

    out = {}
    for d in dropped:
        kind = re.split(r"[\d.]", d["reason"], maxsplit=1)[0].strip(" :=|")
        out[kind] = out.get(kind, 0) + len(d["polygons"])
    return dict(sorted(out.items()))


def build(variant, openings, tile):
    """{'frame': (verts, faces, uvs) | None, 'atlas': ... | None, 'glass': ... | None, 'info': {...}}"""
    import numpy as np

    full = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    if variant == "atlas-planes":
        a = wv.atlas_planes(openings, tile)
        return {"atlas": (a["verts"], a["faces"], a["uvs"]) if openings else None, "frame": None, "glass": None,
                "info": {"window_types": len(a["types"]), "atlas_grid": a["grid"]}}
    if variant == "inset-glass-trim":
        r = wv.inset_glass_trim(openings, tile)
        return {"frame": r["frame"] if openings else None, "glass": r["glass"] if openings else None, "atlas": None,
                "info": {"trim_scale_uv_per_m": round(r["trim_scale"], 5), "trim_w_m": wv.TRIM_W_M}}
    s = wv.trim_scale(openings)
    fv, ff, fuv, gv, gf, guv = [], [], [], [], [], []
    for o in openings:
        verts, faces, glass = _bmesh_frame(o)
        base = len(fv)
        fv += list(verts)
        for f in faces:
            ff.append([base + i for i in f])
            fuv.append(wv.metric_uv(verts[f], o, s, tile).tolist())
        for pane in glass:
            gb = len(gv)
            gv += list(pane)
            gf.append(list(range(gb, gb + len(pane))))
            guv.append(full[:len(pane)] if len(pane) == 4 else [[0.5, 0.5]] * len(pane))
    return {"frame": (np.array(fv).reshape(-1, 3), ff, fuv) if openings else None,
            "glass": (np.array(gv).reshape(-1, 3), gf, guv) if openings else None, "atlas": None,
            "info": {"panes": len(gf), "frame_w_m": wv.FRAME_W_M, "frame_d_m": wv.FRAME_D_M,
                     "trim_scale_uv_per_m": round(s, 5)}}


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, err = _parse(args)
    if err:
        print(f"WINDOWS_VARIANT refused: {err}", file=sys.stderr)
        return 4
    src, out, variant = Path(args[0]), Path(args[1]), args[2]
    rep_path = out.with_name(out.name + ".variant.json")
    import os

    fault = os.environ.get("WINDOWS_VARIANT_FAULT", "")
    if _fault_error(fault):
        print(f"WINDOWS_VARIANT refused: {_fault_error(fault)}; nothing written", file=sys.stderr)
        return 4
    tex_name = opts.get("texture")  # default needs the address: resolved after import, checked again then
    inputs = [src] + ([Path(opts["glass_map"])] if "glass_map" in opts else [])
    dests = [out, rep_path] + ([out.with_name(tex_name)] if tex_name else [])

    def refused(dsts):
        for i, dst in enumerate(dsts):
            for inp in inputs:
                alias = ua.output_alias_reason(inp, dst)
                if alias:
                    return alias
            for other in dsts[i + 1:]:
                if dst.resolve() == other.resolve() or (dst.exists() and other.exists() and dst.samefile(other)):
                    return f"two destinations are the same file: {dst} and {other}"
        return None

    why = refused(dests)
    if why:
        print(f"WINDOWS_VARIANT refused: {why}; nothing written", file=sys.stderr)
        return 4
    if not src.is_file():
        print(f"WINDOWS_VARIANT refused: no input file {src}", file=sys.stderr)
        return 4
    import bmesh
    import bpy
    import numpy as np

    report = {"source": src.name, "variant": variant, "options": {k: str(v) for k, v in opts.items()},
              "blender": bpy.app.version_string, "ok": False}
    code, written = 2, []
    try:
        out.unlink(missing_ok=True)  # a stale output never survives a failed build (destinations checked above)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(src))
        t0 = time.perf_counter()
        objects = list(bpy.context.scene.objects)
        meshes = [o for o in objects if o.type == "MESH"]
        source_inv = mesh_inventory(meshes)
        report["source_inventory"] = sorted(source_inv)
        dropped_objects = [{"name": o.name, "reason": f"non-mesh object ({o.type}); the export is MESH-only"}
                           for o in objects if o.type != "MESH"]
        mains = [o for o in meshes if o.name.endswith("_Main")]
        if len(mains) != 1:
            raise ValueError(f"expected one *_Main mesh, found {[o.name for o in mains]}")
        main = mains[0]
        address = main.name[: -len("_Main")]
        glass_objs = [o for o in meshes if o.name.endswith("_MainGlass")]
        if len(glass_objs) > 1:
            raise ValueError(f"more than one *_MainGlass mesh: {[o.name for o in glass_objs]}")
        kind = wv.GEN_MATERIAL[variant]
        png = out.with_name(tex_name or f"T_{address}_{kind}.png")
        why = refused(dests + ([] if tex_name else [png]))
        if why:
            raise ValueError(f"{why} (default texture name)")
        bb = np.array([main.matrix_world @ __import__("mathutils").Vector(c) for c in main.bound_box])
        centre_xy = (bb[:, :2].min(axis=0) + bb[:, :2].max(axis=0)) / 2
        glass_mat = None
        if glass_objs:
            source, polys = "object " + glass_objs[0].name, _world_polys(glass_objs[0])
            glass_mat = glass_objs[0].material_slots[0].material if glass_objs[0].material_slots else None
            removed = len(polys)
        elif "glass_map" in opts:
            idx = _glass_by_map(main, opts["glass_map"])
            source, polys, removed = f"{main.name} polygons white on {Path(opts['glass_map']).name}", \
                _world_polys(main, idx), len(idx)
        else:
            source, polys, removed, idx = "none (no *_MainGlass object, no glass_map)", [], 0, []
        openings, dropped = wv.extract_openings(polys, centre_xy)
        kept = sum(len(o["polygons"]) for o in openings) + sum(len(d["polygons"]) for d in dropped)
        if kept != len(polys):
            raise ValueError(f"opening extraction accounts for {kept} of {len(polys)} glass polygons")
        # expected output inventory: every source mesh unchanged, except Main (rebuilt windows) and the glass
        expected = {n: e for n, e in source_inv.items() if n != main.name and not (glass_objs and n == glass_objs[0].name)}
        expected[main.name] = None
        if glass_objs:  # remove the glass source (the variant replaces it)
            report["replaced_objects"] = [{"name": glass_objs[0].name, "reason": "glass source, rebuilt by the variant"}]
            bpy.data.objects.remove(glass_objs[0], do_unlink=True)
        elif polys:
            bm = bmesh.new()
            bm.from_mesh(main.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in idx], context="FACES")
            bm.to_mesh(main.data)
            bm.free()
        built = build(variant, openings, opts["tile"])
        uv_name = main.data.uv_layers.active.name if main.data.uv_layers else "UVMap"
        joins, gen_mat = [], None
        if built["frame"] is not None or built["atlas"] is not None:
            gen_mat = f"M_{address}_Main_{kind}"
            mat = _new_material(gen_mat)
            written.append(png)
            _textured(mat, png, variant, opts["texture_side"], int(built["info"].get("atlas_grid") or 1))
            part = built["frame"] if built["frame"] is not None else built["atlas"]
            joins.append(_new_object(f"{address}_{kind}_tmp", *part, mat, uv_name))
        if joins:
            bpy.ops.object.select_all(action="DESELECT")
            for o in joins + [main]:
                o.select_set(True)
            bpy.context.view_layer.objects.active = main
            bpy.ops.object.join()
        if built["glass"] is not None:
            g = _new_object(f"{address}_MainGlass", *built["glass"],
                            _material(f"M_{address}_MainGlass_1", glass_mat), uv_name, matrix=main.matrix_world.copy())
            g.name = f"{address}_MainGlass"
            if g.name in expected:
                raise ValueError(f"rebuilt glass name {g.name} collides with a kept source mesh")
            expected[g.name] = None
        export = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if sorted(o.name for o in export) != sorted(expected):
            raise ValueError(f"export set {sorted(o.name for o in export)} != expected {sorted(expected)}")
        bpy.ops.object.select_all(action="DESELECT")
        for o in export:
            o.select_set(True)
        out.parent.mkdir(parents=True, exist_ok=True)
        partial = _staging(out)  # never a predictable name: an unrelated file is never overwritten or removed
        written.append(partial)
        bpy.ops.export_scene.fbx(filepath=str(partial), use_selection=True, object_types={"MESH"},
                                 axis_forward="Y", axis_up="Z", apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                                 bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type="FACE",
                                 use_triangles=True, use_custom_props=False, add_leaf_bones=False,
                                 bake_anim=False, path_mode="STRIP", embed_textures=False)
        report["wall_time_s"] = round(time.perf_counter() - t0, 3)
        png_sha = _sha256(png) if gen_mat else None
        check = readback_check(partial, expected, gen_mat, png if gen_mat else None, png_sha, opts["tile"])
        report["readback"] = check
        if fault == "readback":
            check["problems"].append("forced read-back failure (WINDOWS_VARIANT_FAULT=readback)")
        if check["problems"]:
            raise ValueError(f"read-back does not reconcile: {check['problems'][:5]}")
        partial.replace(out)
        written.remove(partial)
        report.update({"ok": True, "glass_source": source, "glass_polygons_in": len(polys),
                       "glass_polygons_removed": removed, "openings": len(openings),
                       "dropped_polygons": sum(len(d["polygons"]) for d in dropped),
                       "dropped_by_reason": _by_reason(dropped), "dropped_objects": dropped_objects,
                       "exported": sorted(expected), "texture": png.name if gen_mat else None,
                       "texture_sha256": png_sha, **built["info"]})
        code = 0
    except Exception as exc:  # report, never hide; publish nothing
        report["error"] = f"{type(exc).__name__}: {exc}"
        for w in written:
            Path(w).unlink(missing_ok=True)
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("WINDOWS_VARIANT", code, report.get("openings"), report.get("error", ""))
    return code


if __name__ == "__main__":
    sys.exit(main())
