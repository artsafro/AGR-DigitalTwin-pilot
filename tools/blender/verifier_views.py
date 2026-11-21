"""new-case: the 6 verifier views (#1739) rendered headless from a read-back export, for tools/qa/verifier.py.

  blender --background --factory-startup --python tools/blender/verifier_views.py -- \
      --vpm VPM.(blend|fbx) --npm NPM.(blend|fbx) --out NEW_DIR

Writes NEW_DIR/{vpm_south,vpm_north,vpm_east,vpm_west,vpm_iso,npm_iso}.png (tools/qa/vlm_checklist.py VIEWS) and
NEW_DIR/views.json (inputs, sha256, camera per view). Orthographic Workbench, material/texture colours, UCX_ hidden,
the camera fitted to the world bounding box. South = camera on -Y looking +Y (world axes, no project north is guessed).
Read-only: the sources are opened/imported and never saved; NEW_DIR must not exist.
"""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

VIEWS = ("vpm_south", "vpm_north", "vpm_east", "vpm_west", "vpm_iso", "npm_iso")
DIRS = {"south": (0, -1, 0), "north": (0, 1, 0), "east": (1, 0, 0), "west": (-1, 0, 0), "iso": (-1, -1, 0.8)}


def _args():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = {}
    for i in range(0, len(a), 2):
        out[a[i].lstrip("-")] = a[i + 1]
    for k in ("vpm", "npm", "out"):
        if k not in out:
            raise SystemExit(f"missing --{k}")
    return out


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _load(path):
    p = Path(path)
    if p.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(p), load_ui=False, use_scripts=False)
    elif p.suffix.lower() == ".fbx":
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(p))
    else:
        raise SystemExit(f"unsupported input {p}")


def _bbox(sc):
    lo, hi = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    n = 0
    for o in sc.objects:
        if o.type != "MESH" or o.name.startswith("UCX_"):
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo, hi = Vector(map(min, lo, w)), Vector(map(max, hi, w))
            n += 1
    if not n:
        raise SystemExit("no mesh to render")
    return lo, hi


def _render(names, out):
    sc = bpy.context.scene
    for o in sc.objects:
        if o.name.startswith("UCX_"):
            o.hide_render = True
    lo, hi = _bbox(sc)
    ctr, size = (lo + hi) / 2, hi - lo
    cam = bpy.data.objects.new("VerifierCam", bpy.data.cameras.new("VerifierCam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    cam.data.clip_end = 10 * max(size) + 100
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "TEXTURE"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    rows = {}
    for name in names:
        side = name.split("_")[1]
        d = Vector(DIRS[side]).normalized()
        cam.location = ctr + d * (2 * max(size) + 10)
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        span = max(size) * (1.5 if side == "iso" else 1.1)
        cam.data.ortho_scale = span
        sc.render.filepath = str(out / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        rows[name] = {"location": list(cam.location), "ortho_scale": span}
    return rows


def main():
    a = _args()
    out = Path(a["out"]).resolve()
    if out.exists():
        raise SystemExit(f"{out} exists; use a new folder")
    out.mkdir(parents=True)
    shas = {k: _sha(a[k]) for k in ("vpm", "npm")}
    _load(a["vpm"])
    cams = _render([v for v in VIEWS if v.startswith("vpm_")], out)
    _load(a["npm"])
    cams.update(_render(["npm_iso"], out))
    if {k: _sha(a[k]) for k in ("vpm", "npm")} != shas:
        raise SystemExit("input changed during render")
    missing = [v for v in VIEWS if not (out / f"{v}.png").is_file()]
    if missing:
        raise SystemExit(f"views not written: {missing}")
    (out / "views.json").write_text(json.dumps({"views": list(VIEWS), "inputs": {k: {"path": a[k], "sha256": shas[k]}
                                                for k in shas}, "cameras": cams, "blender": bpy.app.version_string},
                                               indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
