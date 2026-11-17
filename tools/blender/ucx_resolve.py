"""Resolve intersecting / too-close UCX pairs of a model by plane clipping (#1540), in an isolated factory Blender.

    blender --background --factory-startup --python-exit-code 1 --python tools/blender/ucx_resolve.py -- \\
        <model.fbx|.blend> <out.fbx> [gap=M]

Pattern: n/a | new-case: Blender I/O glue around adapters/max/agr_tools/ucx10_core.py::resolve (the UCX gap-fix
core [D330]); no geometry logic here.

The model holds its UCX already (e.g. a delivered archive). Every `UCX_*` mesh is read in world metres and passed
to `ucx10_core.resolve`: for each pair under `gap` (default 3 mm, 2 mm - 1 cm [D098]) the smaller convex hull is
cut by the plane of a face of the larger one moved out by the gap. The cut pieces replace the mesh data of their
objects (same names, same transforms); every other object is exported unchanged. Before export the driver checks
the whole-file UCX triangle budget [D012] and the model -> UCX distance [D134] (surface samples of every non-UCX
mesh, exact distance to the union of the UCX hulls, limit `limit=` metres, default 1 m = remaining OKS R13).
The report `<out>.ucx_resolve.json` lists per pair the plane, the gap before/after and the volume removed, and
the SINTEZ-style intersection count (twinqa ucx_audit) before and after.

Exit 0 resolved and every check passed; 3 written but a check failed (ambiguous or left pair, D012, D134);
2 failed (report written, no OUT); 4 refused before any write. The source file is never written.
"""
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAP_DEFAULT_M = 0.003
LIMIT_DEFAULT_M = 1.0  # D134 remaining OKS; pass limit=0.3 for a pedestrian-reachable body
SAMPLE_M = 0.25


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse(argv):
    if len(argv) < 2:
        return None, "usage -- <model.fbx|.blend> <out.fbx> [gap=M] [limit=M]"
    opts = {}
    for a in argv[2:]:
        k, sep, val = a.partition("=")
        if not sep or k not in ("gap", "limit"):
            return None, f"bad option {a!r}"
        if k in opts:
            return None, f"option {k!r} given twice"
        try:
            opts[k] = float(val)
        except ValueError:
            return None, f"{k} must be a number in metres"
        if not math.isfinite(opts[k]):
            return None, f"{k} must be finite"
    if not argv[1].lower().endswith(".fbx"):
        return None, "output must be an .fbx path"
    if not 0.0 < opts.get("limit", LIMIT_DEFAULT_M) <= 1.0:
        return None, "limit must be 0 < limit <= 1 m (D134)"
    return opts, None


def intersections(rows, ua, reach=0.1):
    """SINTEZ-style count: pairs whose findings include intersect / nested / too_close (AABB prefilter)."""
    boxes = [ua.bounds(r["verts"]) for r in rows]
    bad = 0
    for i, j in itertools.combinations(range(len(rows)), 2):
        if ua.bbox_gap(boxes[i], boxes[j]) > reach:
            continue
        kinds = {f["type"] for f in ua.pair_findings((rows[i]["verts"], rows[i]["tris"]),
                                                     (rows[j]["verts"], rows[j]["tris"]))}
        bad += bool(kinds & {"intersect", "nested", "too_close"})
    return bad


def _ucx_row(o, handle, core, np):
    """Read world geometry and its actual object-local storage frame in float64."""
    me = o.data
    me.calc_loop_triangles()
    mw = np.asarray(o.matrix_world, dtype=float)
    return {"handle": handle, "name": o.name,
            "verts": core.transform_points([tuple(v.co) for v in me.vertices], mw),
            "world_to_local": np.linalg.inv(mw).tolist(),
            "tris": [list(t.vertices) for t in me.loop_triangles]}


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts, err = _parse(args)
    if err:
        print(f"UCX_RESOLVE refused: {err}", file=sys.stderr)
        return 4
    ua = _load("ucx_audit", "src/twinqa/geometry/ucx_audit.py")
    src, out = Path(args[0]), Path(args[1])
    rep_path = out.with_name(out.name + ".ucx_resolve.json")
    for dst in (out, rep_path):
        alias = ua.output_alias_reason(src, dst)
        if alias:
            print(f"UCX_RESOLVE refused: {alias}; nothing written", file=sys.stderr)
            return 4
    if not src.is_file():
        print(f"UCX_RESOLVE refused: no input file {src}", file=sys.stderr)
        return 4
    import bpy
    import numpy as np

    ub = _load("ucx_build", "src/dt_ai/geometry/ucx_build.py")
    core = _load("agr_ucx10_core", "adapters/max/agr_tools/ucx10_core.py")
    gap, limit = opts.get("gap", GAP_DEFAULT_M), opts.get("limit", LIMIT_DEFAULT_M)
    report = {"source": src.name, "blender": bpy.app.version_string, "ok": False, "gap_m": gap,
              "model_to_ucx_limit_m": limit, "core": "adapters/max/agr_tools/ucx10_core.py::resolve (#1540)"}
    code = 2
    try:
        copts = core.gap_options({"gap_m": gap})
        if src.suffix.lower() == ".blend":
            bpy.ops.wm.open_mainfile(filepath=str(src))
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(src))
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        ucx = [o for o in meshes if o.name.upper().startswith("UCX")]
        model = [o for o in meshes if o not in ucx]
        if not ucx or not model:
            raise ValueError(f"need UCX and model meshes, got {len(ucx)} UCX / {len(model)} model")
        rows = []
        for h, o in enumerate(ucx):
            rows.append(_ucx_row(o, h, core, np))
        report["intersections_before"] = intersections(rows, ua)
        res = core.resolve(rows, copts)
        s = res["summary"]
        report.update({k: s[k] for k in ("pieces", "pairs_resolved", "pairs_ambiguous", "pieces_changed", "left",
                                         "not_convex", "skipped", "triangles_before", "triangles_after",
                                         "volume_removed_m3")})
        report.update(pairs=res["pairs"], ambiguous=res["ambiguous"], skipped_items=res["skipped"],
                      findings={ucx[h].name: v for h, v in res["findings"].items()})
        after = []
        for h, p in res["pieces"].items():
            after.append({"name": p["name"], "verts": p["verts"], "tris": p["tris"]})
            if not p["changed"]:
                continue
            o = ucx[h]
            inv = rows[h]["world_to_local"]
            me = bpy.data.meshes.new(o.data.name)
            me.from_pydata(core.transform_points(p["verts"], inv), [],
                           [tuple(t) for t in p["tris"]])
            me.update()
            o.data = me
        changed_names = {res["pieces"][h]["name"] for h in res["pieces"] if res["pieces"][h]["changed"]}
        rows_after = [r for r in rows if r["name"] not in changed_names] + \
            [a for a in after if a["name"] in changed_names]
        report["intersections_after"] = intersections(rows_after, ua)
        for o in model:
            o.data.calc_loop_triangles()
        model_tris = sum(len(o.data.loop_triangles) for o in model)
        ucx_tris = sum(len(r["tris"]) for r in rows_after)
        limit_d012 = ub.ucx_triangle_limit(model_tris)
        report.update(model_triangles_excl_ucx=model_tris, ucx_triangles=ucx_tris, file_ucx_limit_D012=limit_d012,
                      within_D012=ucx_tris <= limit_d012)
        mv, mt = _world(model, np)
        pts = ub.sample_surface(mv, mt, SAMPLE_M)
        before = ub.hull_deviation(pts, [(r["verts"], r["tris"]) for r in rows if r["tris"]])
        dev = ub.hull_deviation(pts, [(r["verts"], r["tris"]) for r in rows_after if r["tris"]])
        report.update(model_points=int(len(pts)), model_to_ucx_before_max_m=round(float(before.max()), 4),
                      model_to_ucx_max_m=round(float(dev.max()), 4), within_D134=bool(dev.max() <= limit),
                      D134_not_worse=bool(dev.max() <= before.max() + 1e-4))
        bpy.ops.object.select_all(action="DESELECT")
        for o in meshes:
            o.select_set(True)
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH"},
                                 axis_forward="Y", axis_up="Z", apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                                 bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type="FACE",
                                 use_triangles=False, use_custom_props=False, add_leaf_bones=False,
                                 bake_anim=False, path_mode="STRIP", embed_textures=False)
        report["ok"] = True
        good = (s["ok"] and report["within_D012"] and report["within_D134"])
        code = 0 if good else 3
    except Exception as exc:  # report, never hide
        report["error"] = f"{type(exc).__name__}: {exc}"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("UCX_RESOLVE", code, report.get("pairs_resolved"), report.get("intersections_before"),
          report.get("intersections_after"), report.get("error", ""))
    return code


def _world(objs, np):
    vs, ts, off = [], [], 0
    for o in objs:
        me = o.data
        me.calc_loop_triangles()
        mw = np.asarray(o.matrix_world, dtype=float)
        local = np.array([tuple(x.co) for x in me.vertices], dtype=float).reshape(-1, 3)
        v = local @ mw[:3, :3].T + mw[:3, 3]
        t = np.array([tuple(x.vertices) for x in me.loop_triangles], dtype=np.int64).reshape(-1, 3)
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(ts)


if __name__ == "__main__":
    sys.exit(main())
