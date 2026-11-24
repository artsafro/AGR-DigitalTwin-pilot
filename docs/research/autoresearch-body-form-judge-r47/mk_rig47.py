"""Derive rig47.py from rig45.py (#45): add mesh-only variants N_tri/N_sub/N_jit and an uncropped OBJ export."""
import shutil
from pathlib import Path

S = Path('C:/x/autoresearch-body-form-r45')
D = Path(__file__).resolve().parent
(D / 'inputs').mkdir(exist_ok=True)
shutil.copyfile(S / 'inputs/A.fbx', D / 'inputs/A.fbx')
shutil.copyfile(S / 'compose41.py', D / 'compose41.py')
t = (S / 'rig45.py').read_text(encoding='utf-8')
VAR = """elif variant == 'N_tri':
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(body.data)
    bm.free()
    plant = {'mesh_only': 'triangulate'}
elif variant == 'N_sub':
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    bm.to_mesh(body.data)
    bm.free()
    plant = {'mesh_only': 'subdivide_1'}
elif variant == 'N_jit':
    import random
    rng = random.Random(47)
    mx = 0.0
    for vtx in body.data.vertices:
        dv = Vector((rng.uniform(-param, param), rng.uniform(-param, param), rng.uniform(-param, param)))
        vtx.co += dv
        mx = max(mx, dv.length)
    plant = {'mesh_only': 'jitter', 'amp_m': param, 'max_disp_m': mx}
"""
subs = [
    ("elif variant not in ('A', 'R'):", VAR + "elif variant not in ('A', 'R'):"),
    ("# crop by bisection (no manifold requirement)\n",
     "# #47: uncropped variant OBJ for the mesh proxy (diagnostic copy, outside the repo)\n"
     "bpy.ops.object.select_all(action='DESELECT')\nbody.select_set(True)\n"
     "bpy.ops.wm.obj_export(filepath=str(out.parent / (out.name + '.obj')), export_selected_objects=True,\n"
     "                      export_materials=False, export_uv=False, export_normals=False,"
     " export_triangulated_mesh=False)\n"
     "# crop by bisection (no manifold requirement)\n"),
    ("Usage: blender ... --python rig45.py -- ROOT FBX VARIANT PARAM OUTDIR (#45: rig41 + size param)",
     "Usage: blender ... --python rig47.py -- ROOT FBX VARIANT PARAM OUTDIR (#47: rig45 + mesh-only variants)"),
]
for a, b in subs:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
(D / 'rig47.py').write_text(t, encoding='utf-8')
print('MK_OK')
