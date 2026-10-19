"""Build UCX for a Main or Ground target with the shared builder, in an isolated factory Blender process.

    blender --background --factory-startup --python-exit-code 1 --python tools/blender/ucx_build.py -- \\
        <model.fbx|.blend> <out.fbx> <Main|Ground> [key=value ...]

Keys: cell, gap, min_cell, tol, depth (metres), object=<target object name> (default: the one
`SM_<Address>_Main` / `SM_<Address>_Ground` mesh), with=<extra object names, comma separated, merged into
the Main input, e.g. the MainGlass; every name must exist, else the build fails before any export>.
Existing UCX of the input objects (`UCX_<input object>_NNN`) are replaced; UCX of other model objects (e.g.
the Ground collision during a Main rebuild) are kept unchanged; a UCX that names no model object fails the
build. The source file is never written. The output FBX holds every non-UCX mesh of the input, the kept
UCX and the new pieces named UCX_SM_<Address>_<Target>_NNN (no materials, no UV, identity transforms); a
JSON report is written next to it (`<out>.ucx_build.json`).

Exit 0 built; 3 built but a Ground deviation (vertical, footprint overhang or uncovered strip) exceeds
`tol` (report and FBX written, not a pass);
2 build failed (report written); 4 refused before any write (bad arguments, or an output that aliases the
input). Job scripts call `build_into_scene(...)` from their own Blender session instead.

Core: src/dt_ai/geometry/ucx_build.py (numpy only).
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ub = _load("ucx_build", "src/dt_ai/geometry/ucx_build.py")
ua = _load("ucx_audit", "src/twinqa/geometry/ucx_audit.py")


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


def build_into_scene(target_objs, address, target, model_triangles=None, **kw):
    """Build UCX for `target_objs` and link the pieces into the current scene; returns (objects, result)."""
    import bpy

    v, t = world_arrays(target_objs)
    res = ub.build(target, v, t, model_triangles=model_triangles, **kw)
    names = ub.ucx_names(address, target, len(res.pieces))
    objs = []
    for name, piece in zip(names, res.pieces):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(map(float, p)) for p in piece.verts], [], [tuple(map(int, f)) for f in piece.tris])
        me.update()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        objs.append(ob)
    return objs, res


def _parse(argv):
    if len(argv) < 3 or argv[2] not in ub.TARGETS:
        return None, "usage -- <model.fbx|.blend> <out.fbx> <Main|Ground> [key=value ...]"
    opts = {}
    for a in argv[3:]:
        if "=" not in a:
            return None, f"bad option {a!r}"
        k, val = a.split("=", 1)
        if k in ("cell", "gap", "min_cell", "tol", "depth"):
            if k in opts:
                return None, f"option {k!r} given twice"
            try:
                opts[k] = float(val)
            except ValueError:
                return None, f"{k} must be a number"
        elif k in opts:
            return None, f"option {k!r} given twice"
        elif k == "object":
            if not val:
                return None, "object= needs a name"
            opts[k] = val
        elif k == "with":
            names = val.split(",")
            if not all(names):
                return None, "with= needs comma-separated object names"
            opts[k] = names
        else:
            return None, f"unknown option {k!r}"
    if not argv[1].lower().endswith(".fbx"):
        return None, "output must be an .fbx path"
    return opts, None


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, err = _parse(args)
    if err:
        print(f"UCX_BUILD refused: {err}", file=sys.stderr)
        return 4
    src, out = Path(args[0]), Path(args[1])
    rep_path = out.with_name(out.name + ".ucx_build.json")
    for dst in (out, rep_path):
        alias = ua.output_alias_reason(src, dst)
        if alias:
            print(f"UCX_BUILD refused: {alias}; nothing written", file=sys.stderr)
            return 4
    if not src.is_file():
        print(f"UCX_BUILD refused: no input file {src}", file=sys.stderr)
        return 4
    target = args[2]
    import bpy

    report = {"source": src.name, "target": target, "blender": bpy.app.version_string, "ok": False,
              "options": opts, "scope": "UCX build; checks: tools/blender/ucx_audit.py + validator V010/V012"}
    code = 2
    try:
        if src.suffix.lower() == ".blend":
            bpy.ops.wm.open_mainfile(filepath=str(src))
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(src))
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        all_ucx = [o for o in meshes if o.name.upper().startswith("UCX")]
        model = [o for o in meshes if o not in all_ucx]
        by_name = {o.name: o for o in model}
        # resolve every requested name once, independent of scene order; refuse before anything is removed
        main_name, extra_names, address = ub.select_inputs(list(by_name), target, opts.pop("object", None),
                                                           opts.pop("with", None))
        main_obj, extra = by_name[main_name], [by_name[n] for n in extra_names]
        replace, keep = ub.ucx_replace_plan([o.name for o in all_ucx], [main_name] + extra_names, list(by_name))
        old_ucx = [o for o in all_ucx if o.name in set(replace)]
        kept_ucx = [o for o in all_ucx if o.name in set(keep)]
        for o in model:
            o.data.calc_loop_triangles()
        model_tris = sum(len(o.data.loop_triangles) for o in model)
        for o in old_ucx:
            bpy.data.objects.remove(o, do_unlink=True)
        objs, res = build_into_scene([main_obj] + extra, address, target, model_triangles=model_tris, **opts)
        report.update({
            "inputs": [o.name for o in [main_obj] + extra], "dropped_ucx": replace, "kept_ucx": keep,
            "model_triangles_excl_ucx": model_tris, "pieces": len(objs), "triangles": res.triangles,
            "budget_D012": res.budget, "cell_m": res.cell_m, "gap_m": res.gap_m, "facade_angle_deg": round(res.angle_deg, 3),
            "attempts": res.attempts, "max_vertical_dev_m": res.max_vertical_dev_m,
            "footprint_overhang_bound_m": res.footprint_overhang_bound_m, "uncovered_strip_m": res.uncovered_strip_m,
            "within_tol": res.within_tol,
        })
        if target == "Main":
            pts = ub.sample_surface(*world_arrays([main_obj] + extra), max(res.cell_m / 2, 0.1))
            dev = ub.main_deviation(pts, res)
            report["main_to_ucx_max_m"] = round(float(dev.max()), 4)
        bpy.ops.object.select_all(action="DESELECT")
        for o in model + kept_ucx + objs:
            o.select_set(True)
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH"},
                                 axis_forward="Y", axis_up="Z", apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                                 bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type="FACE",
                                 use_triangles=False, use_custom_props=False, add_leaf_bones=False,
                                 bake_anim=False, path_mode="STRIP", embed_textures=False)
        report["ok"] = True
        code = 0 if res.within_tol else 3
    except Exception as exc:  # report, never hide
        report["error"] = f"{type(exc).__name__}: {exc}"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("UCX_BUILD", code, report.get("pieces"), report.get("error", ""))
    return code


if __name__ == "__main__":
    sys.exit(main())
