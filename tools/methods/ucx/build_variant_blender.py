"""Build one UCX variant into a copy of a model FBX, in an isolated factory Blender process.

Pattern: new-case: methods-catalog UCX variant driver (#706); geometry in tools/methods/ucx/variants.py.

    blender --background --factory-startup --python-exit-code 1 --python tools/methods/ucx/build_variant_blender.py -- \\
        <model.fbx> <out.fbx> <variant> [cell=<m>]

Every UCX_ mesh of the input is dropped; the new pieces are built from ALL non-UCX meshes of the file
(SM_<Address>_Main plus e.g. the MainGlass) and named UCX_SM_<Address>_Main_NNN (no material, no UV,
identity transform). The source is never written. `<out>.variant.json` records the build wall time
(after import, up to the end of the export), the pieces and any error.
Exit 0 built; 2 build failed (report written, no FBX); 4 refused before any write (bad arguments, output
aliases the input, or the report path would alias the input).
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


variants = _load("methods_ucx_variants", "tools/methods/ucx/ucx_variants.py")
ua = _load("ucx_audit", "src/twinqa/geometry/ucx_audit.py")
ub = variants._load_builder()


def bm_hull(points):
    """Convex hull through bmesh.ops.convex_hull, triangulated; (verts, tris)."""
    import bmesh

    bm = bmesh.new()
    try:
        vs = [bm.verts.new(tuple(map(float, p))) for p in points]
        res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
        drop = [g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)]
        if drop:
            bmesh.ops.delete(bm, geom=drop, context="VERTS")
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.verts.index_update()
        verts = [tuple(v.co) for v in bm.verts]
        tris = [tuple(v.index for v in f.verts) for f in bm.faces]
    finally:
        bm.free()
    if len(tris) < 4:
        raise ValueError("flat hull")
    return verts, tris


def world_arrays(objs):
    import numpy as np

    vs, ts, off = [], [], 0
    for o in objs:
        me = o.data
        me.calc_loop_triangles()
        mw = o.matrix_world
        v = np.array([tuple(mw @ x.co) for x in me.vertices], dtype=float).reshape(-1, 3)
        t = np.array([tuple(x.vertices) for x in me.loop_triangles], dtype=np.int64).reshape(-1, 3)
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(ts)


def _parse(argv):
    if len(argv) < 3:
        return None, "usage -- <model.fbx> <out.fbx> <variant> [cell=<m>]"
    if argv[2] not in variants.VARIANTS:
        return None, f"unknown variant {argv[2]!r}; expected one of {variants.VARIANTS}"
    if not argv[1].lower().endswith(".fbx"):
        return None, "output must be an .fbx path"
    opts = {}
    for a in argv[3:]:
        k, sep, val = a.partition("=")
        if not sep or k != "cell" or k in opts:
            return None, f"bad option {a!r} (only cell=<m> once, kernel-boxes only)"
        try:
            opts[k] = float(val)
        except ValueError:
            return None, "cell must be a number"
        if argv[2] != "kernel-boxes":
            return None, "cell= applies to kernel-boxes only"
    return opts, None


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, err = _parse(args)
    if err:
        print(f"UCX_VARIANT refused: {err}", file=sys.stderr)
        return 4
    src, out, variant = Path(args[0]), Path(args[1]), args[2]
    rep_path = out.with_name(out.name + ".variant.json")
    for dst in (out, rep_path):
        alias = ua.output_alias_reason(src, dst)
        if alias:
            print(f"UCX_VARIANT refused: {alias}; nothing written", file=sys.stderr)
            return 4
    if not src.is_file():
        print(f"UCX_VARIANT refused: no input file {src}", file=sys.stderr)
        return 4
    import bpy

    report = {"source": src.name, "variant": variant, "options": opts, "blender": bpy.app.version_string,
              "ok": False}
    code = 2
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(src))
        t0 = time.perf_counter()
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        old = [o for o in meshes if o.name.upper().startswith("UCX")]
        model = [o for o in meshes if o not in old]
        names = [o.name for o in model]
        main_name, extra, address = ub.select_inputs(names, "Main", None,
                                                     [n for n in names if not n.endswith("_Main")] or None)
        report.update({"inputs": [main_name] + extra, "dropped_ucx": sorted(o.name for o in old)})
        v, t = world_arrays(model)
        model_tris = int(len(t))
        pieces, info = variants.build(variant, v, t, model_triangles=model_tris, hull_fn=bm_hull, **opts)
        for o in old:
            bpy.data.objects.remove(o, do_unlink=True)
        objs = []
        for name, (pv, pt) in zip(ub.ucx_names(address, "Main", len(pieces)), pieces):
            me = bpy.data.meshes.new(name)
            me.from_pydata([tuple(map(float, p)) for p in pv], [], [tuple(map(int, f)) for f in pt])
            me.update()
            ob = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(ob)
            objs.append(ob)
        bpy.ops.object.select_all(action="DESELECT")
        for o in model + objs:
            o.select_set(True)
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH"},
                                 axis_forward="Y", axis_up="Z", apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                                 bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type="FACE",
                                 use_triangles=True, use_custom_props=False, add_leaf_bones=False,
                                 bake_anim=False, path_mode="STRIP", embed_textures=False)
        report["wall_time_s"] = round(time.perf_counter() - t0, 3)
        report.update({"ok": True, "model_triangles": model_tris, **{k: info[k] for k in sorted(info)}})
        code = 0
    except Exception as exc:  # report, never hide
        report["error"] = f"{type(exc).__name__}: {exc}"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("UCX_VARIANT", code, report.get("pieces"), report.get("error", ""))
    return code


if __name__ == "__main__":
    sys.exit(main())
