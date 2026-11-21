"""Headless master-copy hook for #1737 (new-case: prepare a delivered VPM for shared derivation)."""
import json
import math
import re
import sys
from pathlib import Path

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.derive import vpm_npm_core as core


def prepare(src, config, out):
    out = Path(out)
    cfg = json.loads(Path(config).read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    meshes = {o.name: o for o in bpy.context.scene.objects if o.type == "MESH" and not o.name.startswith("UCX_")}
    excluded = sorted(o.name for o in bpy.context.scene.objects if o.name not in meshes)
    glass_names = cfg["glass"]
    faces, glass = [], []
    tris = {}
    for name, obj in meshes.items():
        mesh = obj.data
        uv = mesh.uv_layers.active
        if uv is None:
            raise ValueError(f"{name}: missing UV map")
        uv.name = "UVMap"
        if any(not all(math.isfinite(c) for c in v.co) for v in mesh.vertices):
            raise ValueError(f"{name}: nonfinite coordinates")
        rows = [{"object": name, "index": p.index, "verts": list(p.vertices),
                 "uv": [tuple(uv.data[i].uv) for i in p.loop_indices]} for p in mesh.polygons]
        tris[name] = core.count_tris(rows)
        (glass if name in glass_names else faces).extend(rows)
    for name in glass_names:
        if name not in meshes or name in cfg["interiors"]["objects"]:
            raise ValueError(f"glass object missing or marked interior: {name}")
    if any(not math.isfinite(c) for f in glass for uv in f["uv"] for c in uv):
        raise ValueError("glass has nonfinite UVs")
    rem = core.remove_interiors(faces, cfg["interiors"])
    kept = [faces[i] for i in rem["kept"]]
    names = sorted({f["object"] for f in kept})
    if len(names) != 1 or not re.fullmatch(r"SM_[A-Za-z0-9_]+_Main", names[0]):
        raise ValueError(f"expected one retained SM_<address>_Main; got {names}")
    main = meshes[names[0]]
    bm = bmesh.new()
    bm.from_mesh(main.data)
    bm.faces.ensure_lookup_table()
    drops = [{**d, "face": faces[d["face"]]["index"]} for d in rem["dropped"]]
    bmesh.ops.delete(bm, geom=[bm.faces[d["face"]] for d in drops if d["object"] == main.name], context="FACES")
    levels = sorted({core.face_udim(f["uv"]) for f in kept})
    names_by_tile = {tile: f"{'Alpha' if str(tile) in cfg['atlas'].get('opacity', {}) else 'Tile'}{tile}"
                     for tile in levels}
    finish = bm.faces.layers.int.new("finish")
    b_uv = bm.loops.layers.uv["UVMap"]
    for face in bm.faces:
        tile = core.face_udim([tuple(loop[b_uv].uv) for loop in face.loops])
        face[finish] = levels.index(tile)
    main["finish_names"] = ",".join(names_by_tile.values())
    bm.to_mesh(main.data)
    bm.free()
    panes = [meshes[n] for n in glass_names]
    for obj in list(bpy.context.scene.objects):
        if obj != main and obj not in panes:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in panes:
        obj.select_set(True)
    gob = panes[0]
    bpy.context.view_layer.objects.active = gob
    if len(panes) > 1:
        bpy.ops.object.join()
    gob.name = main.name + "Glass"
    with (out / "prepare.json").open("x", encoding="utf-8") as stream:
        json.dump({"tris_count": {"vpm": tris, "vpm_total": sum(tris.values()), "excluded": excluded},
                   "remove_interiors": {"config": cfg["interiors"], "tris_before": rem["tris_before"],
                                        "tris_after": rem["tris_after"], "drops": drops},
                   "glass": {"object": gob.name, "merged_from": glass_names, "tris": core.count_tris(glass)},
                   "tile_names": names_by_tile}, stream)
    master = out / "master.blend"
    if master.exists() or master.is_symlink():
        raise FileExistsError(master)
    bpy.ops.wm.save_as_mainfile(filepath=str(master))
    print("VPM2NPM-OK")


if __name__ == "__main__":
    prepare(*sys.argv[sys.argv.index("--") + 1:])
