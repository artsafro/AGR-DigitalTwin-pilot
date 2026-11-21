"""Blender reader for the NPM -> VPM placement readback (#1731); the check itself is
``dt_ai.placement.vpm_readback`` (pure, no bpy).

Pattern: none (new-case: Blender position reader + pre-export gate of the VPM assembly step; no placement math).

Every read starts with ``bpy.context.view_layer.update()``: right after ``bpy.data.libraries.load`` + collection
link an appended object's ``matrix_world`` is the identity until the depsgraph updates (``matrix_basis`` is
already right). Reading it before the update is how Staropetrovskiy VPM v001 subtracted the pivot twice.

In an assembly script (before ``export_scene.fbx``)::

    from vpm_placement_readback import check_before_export
    check_before_export(npm_positions, placed_objects, pivot, report_path=...)   # raises on any offender

CLI (exit 0 pass, 1 fail, 2 bad arguments / report path is an input):
  blender -b --factory-startup --python tools/blender/vpm_placement_readback.py -- objects
      --npm-json <npm.json {handle: [x, y, z]}> --scene <.blend|.fbx> --pivot x,y,z [--tol 0.01] --out <report.json>
      (handle = scene object name; labelled check)
  ... -- parts --npm <.blend|.fbx> --npm-object <name> --scene <.blend|.fbx> --scene-object <name>
      --pivot x,y,z [--tol 0.01] --out <report.json>
      (loose parts of the NPM-side object, world bbox centres, against the loose-part centres of the scene object,
      e.g. the joined VPM Ground; unlabelled check)
"""
import argparse
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from dt_ai.placement import vpm_readback as vr  # noqa: E402


def fresh():
    """Depsgraph update before any matrix_world read (stale after append / link)."""
    bpy.context.view_layer.update()


def object_records(objects) -> list[dict]:
    fresh()
    return [{"handle": o.name, "position": [float(c) for c in o.matrix_world.translation]} for o in objects]


def part_centres(obj) -> list[list[float]]:
    """World bbox centre of every loose part (vertices connected by edges) of a mesh object."""
    import numpy as np
    fresh()
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    M = np.array(obj.matrix_world, dtype=np.float64)
    co = co @ M[:3, :3].T + M[:3, 3]
    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", ev)
    parent = list(range(n))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in ev.reshape(-1, 2).tolist():
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
    lab = np.array([root(i) for i in range(n)], dtype=np.int64)
    _, inv = np.unique(lab, return_inverse=True)
    k = int(inv.max()) + 1 if n else 0
    lo = np.full((k, 3), np.inf)
    hi = np.full((k, 3), -np.inf)
    np.minimum.at(lo, inv, co)
    np.maximum.at(hi, inv, co)
    return ((lo + hi) / 2.0).tolist()


def check_before_export(npm_positions, objects, pivot, tol_m=vr.TOL_M, report_path=None, inputs=()):
    """Gate of the VPM assembly step: scene objects (handle = object name) vs NPM - pivot; raises
    ``vr.PlacementReadbackFailed`` with the offenders, returns the report on pass."""
    scene, errs = vr.records_to_map(object_records(objects))
    rep = vr.check(npm_positions, scene, pivot, tol_m, errs)
    if report_path:
        vr.write_report(rep, report_path, inputs)
    return vr.require_pass(rep)


def load(path):
    p = str(path)
    if p.lower().endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=p)
    elif p.lower().endswith(".fbx"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=p)
    else:
        raise ValueError(f"unsupported scene file {p}")
    fresh()


def _obj(name):
    o = bpy.data.objects.get(name)
    if o is None or o.type != "MESH":
        raise ValueError(f"no mesh object {name!r}")
    return o


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="vpm_placement_readback")
    ap.add_argument("mode", choices=("objects", "parts"))
    ap.add_argument("--npm-json")
    ap.add_argument("--npm")
    ap.add_argument("--npm-object")
    ap.add_argument("--scene", required=True)
    ap.add_argument("--scene-object")
    ap.add_argument("--pivot", required=True)
    ap.add_argument("--tol", type=float, default=vr.TOL_M)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        pivot = [float(v) for v in a.pivot.split(",")]
    except ValueError:
        print(f"VPM_READBACK bad pivot {a.pivot!r}")
        return 2
    inputs = [p for p in (a.npm_json, a.npm, a.scene) if p]
    out = Path(a.out)
    for i in inputs:
        if vr.same_path(out, Path(i)) or vr.same_path(out.with_name(out.name + ".partial"), Path(i)):
            print(f"VPM_READBACK report path {out} is an input ({i})")
            return 2
    if a.mode == "objects":
        import json
        if not a.npm_json:
            print("VPM_READBACK objects mode needs --npm-json")
            return 2
        npm = json.loads(Path(a.npm_json).read_text(encoding="utf-8"))
        load(a.scene)
        recs = object_records([o for o in bpy.data.objects if o.name in npm])
        scene, errs = vr.records_to_map(recs)
        rep = vr.check(npm, scene, pivot, a.tol, errs)
    else:
        if not (a.npm and a.npm_object and a.scene_object):
            print("VPM_READBACK parts mode needs --npm, --npm-object and --scene-object")
            return 2
        load(a.npm)
        npm = {f"{a.npm_object}#{i:05d}": c for i, c in enumerate(part_centres(_obj(a.npm_object)))}
        load(a.scene)
        rep = vr.check_points(npm, part_centres(_obj(a.scene_object)), pivot, a.tol)
        rep["source"] = {"npm": str(a.npm), "npm_object": a.npm_object, "scene": str(a.scene),
                         "scene_object": a.scene_object, "blender": bpy.app.version_string}
    vr.write_report(rep, out, inputs)
    diag = {}
    for o in rep["offenders"]:
        diag[o["diagnosis"]] = diag.get(o["diagnosis"], 0) + 1
    print(f"VPM_READBACK {rep['status']} n_npm={rep['n_npm']} n_ok={rep['n_ok']} offenders={len(rep['offenders'])} "
          f"diagnosis={diag} errors={rep['errors'][:5]}")
    return 0 if rep["status"] == "pass" else 1


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sys.exit(main(argv))
