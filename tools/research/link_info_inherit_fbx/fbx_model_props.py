"""SYNTHETIC Q10 test: dump raw FBX Model properties (InheritType, Lcl TRS, pre/post rotation) with Blender's parser.

    blender --background --factory-startup --python-exit-code 1 --python fbx_model_props.py -- <in.fbx> <out.json>

Reads the file only; no import, no scene.
"""
import json
import sys

from io_scene_fbx import parse_fbx

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
root, version = parse_fbx.parse(src)


def text(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else v


def child(elem, name):
    return [e for e in elem.elems if e.id == name.encode()]


models = []
for objects in child(root, "Objects"):
    for model in child(objects, "Model"):
        props = {}
        for p70 in child(model, "Properties70"):
            for p in child(p70, "P"):
                vals = [text(v) for v in p.props[4:]]
                props[text(p.props[0])] = vals[0] if len(vals) == 1 else vals
        models.append({"name": text(model.props[1]).split("\x00")[0], "type": text(model.props[2]), "props": props})
settings = {}
for gs in child(root, "GlobalSettings"):
    for p70 in child(gs, "Properties70"):
        for p in child(p70, "P"):
            vals = [text(v) for v in p.props[4:]]
            settings[text(p.props[0])] = vals[0] if len(vals) == 1 else vals
creator = [text(e.props[0]) for e in child(root, "Creator")]
with open(out, "w", encoding="utf-8") as f:
    json.dump({"fbx_version": version, "creator": creator, "global_settings": settings, "models": models}, f, indent=1)
print("DONE fbx_model_props", version, len(models))
