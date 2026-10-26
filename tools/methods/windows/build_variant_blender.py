"""Build one windows-glazing variant of a benchmark model in factory Blender (methods catalog, #721).

Pattern: new-case: Blender driver for the windows-glazing variants (bmesh frames, numpy planes / trim).

    blender --background --factory-startup --python-exit-code 1 \\
        --python tools/methods/windows/build_variant_blender.py -- <model.fbx> <out.fbx> <variant> \\
        tile=<UDIM> [glass_map=<metallic.png>]

Glass source, first that applies: the `*_MainGlass` object; else the Main polygons whose UV centre is white
(> 0.5) on `glass_map` (the metallic map, glass white per reg p.9 §5.10, WIN-08); else none (0 openings,
the model is exported unchanged). The glass source is removed and replaced by the variant's windows; the
body and the UCX pieces are kept as they are. New UVs go to UDIM `tile`. `<out>.variant.json` records the
build wall time (after import, up to the end of the export), openings, drops with reasons and any error.
Exit 0 built; 2 build failed (report written); 4 refused before any write (bad arguments, output aliasing
an input).
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


def _parse(argv):
    if len(argv) < 4:
        return None, "usage -- <model.fbx> <out.fbx> <variant> tile=<UDIM> [glass_map=<png>]"
    if argv[2] not in wv.VARIANTS:
        return None, f"unknown variant {argv[2]!r}; expected one of {wv.VARIANTS}"
    if not argv[1].lower().endswith(".fbx"):
        return None, "output must be an .fbx path"
    opts = {}
    for a in argv[3:]:
        k, sep, val = a.partition("=")
        if not sep or k not in ("tile", "glass_map") or k in opts:
            return None, f"bad option {a!r} (tile=<UDIM> once, glass_map=<png> at most once)"
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


def _new_object(name, verts, faces, uvs, material, uv_name, matrix=None):
    import bpy
    import numpy as np
    from mathutils import Matrix

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
    """modelled-frames, one opening: inset ring, mullions by grid subdivide + inset, panes out, solidify."""
    import bmesh
    import numpy as np

    plan = wv.frame_plan(o)
    bm = bmesh.new()
    face = bm.faces.new([bm.verts.new(tuple(p)) for p in plan["outer"]])
    bmesh.ops.inset_region(bm, faces=[face], thickness=plan["frame_w"], depth=0.0, use_even_offset=True)
    inner = [face]
    if plan["panes"] > 1:
        horiz = [e for e in face.edges if abs((e.verts[1].co - e.verts[0].co).normalized().dot(tuple(o["u"]))) > 0.9]
        bmesh.ops.subdivide_edges(bm, edges=horiz, cuts=plan["panes"] - 1, use_grid_fill=True)
        lim = o["width"] / 2 - plan["frame_w"] + 1e-6
        limv = o["height"] / 2 - plan["frame_w"] + 1e-6
        inner = []
        for f in bm.faces:  # panes = faces with every corner inside the inner rectangle
            inside = all(abs((np.array(v.co) - o["centre"]) @ o["u"]) <= lim and
                         abs((np.array(v.co) - o["centre"]) @ o["v"]) <= limv for v in f.verts)
            if inside:
                inner.append(f)
        bmesh.ops.inset_individual(bm, faces=inner, thickness=plan["mullion_w"] / 2, use_even_offset=True)
    glass = [np.array([v.co[:] for v in f.verts]) for f in inner]
    bmesh.ops.delete(bm, geom=inner, context="FACES_ONLY")
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=plan["depth"])
    co = np.array([v.co[:] for v in bm.verts])
    along = (co - o["centre"]) @ o["n"]
    shift = -(along.max() + along.min()) / 2  # centre the frame depth on the glass plane
    bm.verts.index_update()
    verts = co + shift * o["n"]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
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
    inputs = [src] + ([Path(opts["glass_map"])] if "glass_map" in opts else [])
    for dst in (out, rep_path):
        for inp in inputs:
            alias = ua.output_alias_reason(inp, dst)
            if alias:
                print(f"WINDOWS_VARIANT refused: {alias}; nothing written", file=sys.stderr)
                return 4
    if not src.is_file():
        print(f"WINDOWS_VARIANT refused: no input file {src}", file=sys.stderr)
        return 4
    import bmesh
    import bpy
    import numpy as np

    report = {"source": src.name, "variant": variant, "options": {k: str(v) for k, v in opts.items()},
              "blender": bpy.app.version_string, "ok": False}
    code = 2
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(src))
        t0 = time.perf_counter()
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        mains = [o for o in meshes if o.name.endswith("_Main")]
        if len(mains) != 1:
            raise ValueError(f"expected one *_Main mesh, found {[o.name for o in mains]}")
        main = mains[0]
        address = main.name[: -len("_Main")]
        glass_objs = [o for o in meshes if o.name.endswith("_MainGlass")]
        if len(glass_objs) > 1:
            raise ValueError(f"more than one *_MainGlass mesh: {[o.name for o in glass_objs]}")
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
        # remove the glass source (the variant replaces it)
        if glass_objs:
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
        joins = []
        if built["frame"] is not None:
            joins.append(_new_object(f"{address}_Frame_tmp", *built["frame"],
                                     _material(f"M_{address}_Main_Frame" if variant == "modelled-frames"
                                               else f"M_{address}_Main_FrameTrim"), uv_name))
        if built["atlas"] is not None:
            joins.append(_new_object(f"{address}_Atlas_tmp", *built["atlas"],
                                     _material(f"M_{address}_Main_WindowAtlas"), uv_name))
        if joins:
            bpy.ops.object.select_all(action="DESELECT")
            for o in joins + [main]:
                o.select_set(True)
            bpy.context.view_layer.objects.active = main
            bpy.ops.object.join()
        export = [main] + [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.upper().startswith("UCX")]
        if built["glass"] is not None:
            g = _new_object(f"{address}_MainGlass", *built["glass"],
                            _material(f"M_{address}_MainGlass_1", glass_mat), uv_name, matrix=main.matrix_world.copy())
            g.name = f"{address}_MainGlass"
            export.append(g)
        bpy.ops.object.select_all(action="DESELECT")
        for o in export:
            o.select_set(True)
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH"},
                                 axis_forward="Y", axis_up="Z", apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                                 bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type="FACE",
                                 use_triangles=True, use_custom_props=False, add_leaf_bones=False,
                                 bake_anim=False, path_mode="STRIP", embed_textures=False)
        report["wall_time_s"] = round(time.perf_counter() - t0, 3)
        report.update({"ok": True, "glass_source": source, "glass_polygons_in": len(polys),
                       "glass_polygons_removed": removed, "openings": len(openings),
                       "dropped_polygons": sum(len(d["polygons"]) for d in dropped),
                       "dropped_by_reason": _by_reason(dropped),
                       "exported": sorted(o.name for o in export), **built["info"]})
        code = 0
    except Exception as exc:  # report, never hide
        report["error"] = f"{type(exc).__name__}: {exc}"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("WINDOWS_VARIANT", code, report.get("openings"), report.get("error", ""))
    return code


if __name__ == "__main__":
    sys.exit(main())
