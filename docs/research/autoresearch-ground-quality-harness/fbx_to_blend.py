"""Blender helper (standing #31): FBX -> .blend with image search off, so the repo dump can open it unchanged.

The FBX importer's default `use_image_search=True` walked the texture paths of A3 (COD) for > 17 min without
finishing; geometry does not depend on it. Usage:
  blender -b --factory-startup --python fbx_to_blend.py -- <src.fbx> <out.blend>
"""
import sys

import bpy

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src, use_image_search=False)
bpy.ops.wm.save_as_mainfile(filepath=out, check_existing=False)
print("FBX_TO_BLEND", len([o for o in bpy.context.scene.objects if o.type == "MESH"]), "meshes")
