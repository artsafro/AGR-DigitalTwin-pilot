"""elv-tc-vpm: V004 topology defect breakdown (twinqa.geometry.topology.count_defects) per FBX mesh, read-only.

blender -b --factory-startup --python topology_breakdown_v001.py -- <out.json> <a.fbx> [<b.fbx> ...]
"""
import bpy
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("topology", ROOT / "src/twinqa/geometry/topology.py")
topo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(topo)

args = sys.argv[sys.argv.index("--") + 1:]
out, fbxs = args[0], args[1:]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
rep = {}
for f in fbxs:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=f)
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o.name.startswith("UCX_"):
            continue
        me = o.data
        v = [tuple(o.matrix_world @ x.co) for x in me.vertices]
        polys = [list(p.vertices) for p in me.polygons]
        edges = [tuple(e.vertices) for e in me.edges]
        rep[f"{Path(f).name}::{o.name}"] = topo.count_defects(v, polys, edges)
json.dump(rep, open(out, "w", encoding="utf-8"), indent=1)
for k, v in rep.items():
    print("TOPO", k, json.dumps(v))
