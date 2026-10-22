"""Build colour-only VPM UDIM and NPM atlas exports from the native source bridge.

new-case: unchanged truba geometry/UCX, source ID provenance, UV-only delivery copies.
VPM follows KPP: one named material, no texture paths in delivery FBX, external UDIMs.
The editable master retains the original source object and face-ID attribute;
consolidating export shaders into one atlas/UDIM material is not a source-ID edit.
Run in Blender 5.1: --background --factory-startup --python this.py -- <build-dir>.
"""
import bpy
import json
import math
import sys
import shutil
import zipfile
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(sys.argv[sys.argv.index('--')+1]).resolve()
ID_TILE = {1:1003, 2:1002, 3:1001, 5:1005, 6:1004, 7:1006}
LAYOUT = json.loads((ROOT/'atlas-layout.json').read_text())


def snapshot(obj):
    return {'vertices': [list(obj.matrix_world @ v.co) for v in obj.data.vertices],
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'polygons': len(obj.data.polygons),
            'triangles': sum(len(p.vertices)-2 for p in obj.data.polygons)}


def material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Roughness'].default_value = 0.5
    m.surface_render_method = 'DITHERED'
    return m, bs


def udim_preview(mat, folder=None):
    """One shader with six tile-aware samplers; supports mixed placeholder sizes."""
    nt = mat.node_tree
    bs = nt.nodes.get('Principled BSDF')
    uv = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uv.outputs['UV'], sep.inputs[0])
    floor = nt.nodes.new('ShaderNodeMath'); floor.operation = 'FLOOR'
    nt.links.new(sep.outputs['X'], floor.inputs[0])
    last_col = None; last_alpha = None
    for udim in range(1001,1007):
        cmp = nt.nodes.new('ShaderNodeMath'); cmp.operation = 'COMPARE'
        nt.links.new(floor.outputs[0], cmp.inputs[0]); cmp.inputs[1].default_value = udim-1001
        cmp.inputs[2].default_value = 0.001
        offset = nt.nodes.new('ShaderNodeVectorMath'); offset.operation = 'SUBTRACT'
        nt.links.new(uv.outputs['UV'], offset.inputs[0]); offset.inputs[1].default_value = (udim-1001,0,0)
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(str((folder or ROOT/'textures-vpm')/f'T_Truba_1_Diffuse_1.{udim}.png'),check_existing=True)
        tex.extension = 'EXTEND'
        nt.links.new(offset.outputs[0],tex.inputs['Vector'])
        mix = nt.nodes.new('ShaderNodeMixRGB')
        mix.inputs[1].default_value = (0,0,0,1)
        nt.links.new(cmp.outputs[0],mix.inputs[0])
        if last_col: nt.links.new(last_col,mix.inputs[1])
        nt.links.new(tex.outputs['Color'],mix.inputs[2]); last_col=mix.outputs[0]
        am = nt.nodes.new('ShaderNodeMixRGB'); am.inputs[1].default_value=(1,1,1,1)
        nt.links.new(cmp.outputs[0],am.inputs[0])
        if last_alpha: nt.links.new(last_alpha,am.inputs[1])
        nt.links.new(tex.outputs['Alpha'],am.inputs[2]); last_alpha=am.outputs[0]
    nt.links.new(last_col,bs.inputs['Base Color']); nt.links.new(last_alpha,bs.inputs['Alpha'])


def npm_shader(mat, folder):
    nt=mat.node_tree; bs=nt.nodes.get('Principled BSDF')
    for suffix, socket in [('d','Base Color'),('o','Alpha')]:
        node=nt.nodes.new('ShaderNodeTexImage')
        node.image=bpy.data.images.load(str(folder/f'T_Truba_1_003_Main_{suffix}_1.png'),check_existing=True)
        if suffix=='o': node.image.colorspace_settings.name='Non-Color'
        nt.links.new(node.outputs['Color'],bs.inputs[socket])


def export(nodes,path,embed):
    bpy.ops.object.select_all(action='DESELECT')
    for n in nodes: n.select_set(True)
    bpy.context.view_layer.objects.active=nodes[0]
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},
        axis_forward='Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        global_scale=1.0,bake_space_transform=False,use_mesh_modifiers=False,
        mesh_smooth_type='FACE',use_triangles=False,use_custom_props=False,
        add_leaf_bones=False,bake_anim=False,path_mode='COPY' if embed else 'STRIP',embed_textures=embed)
    assert path.stat().st_size>1000


def main():
    for name in ['build','package-vpm','package-npm']:
        assert not (ROOT/name).exists(), f'new version required: {name}'
        (ROOT/name).mkdir()
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(ROOT/'source.fbx'),use_image_search=False)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
    source=bpy.data.objects['Tuba']; before=snapshot(source)
    assert before['polygons']==25128 and before['triangles']==50256
    ids=[p.material_index+1 for p in source.data.polygons]
    assert set(ids)==set(ID_TILE),set(ids)
    source.name='SOURCE_Tuba'; source.hide_render=True; source.hide_set(True)
    source_ids=source.data.attributes.new('source_material_id','INT','FACE')
    for d,value in zip(source_ids.data,ids): d.value=value
    raw_uv=[list(d.uv) for d in source.data.uv_layers.active.data]
    vpm=source.copy(); vpm.data=source.data.copy(); scene.collection.objects.link(vpm)
    vpm.name='SM_Truba_1_Main'; vpm.hide_set(False); vpm.hide_render=False
    vpm.data.transform(vpm.matrix_world); vpm.matrix_world=Matrix.Identity(4)
    uv=vpm.data.uv_layers.active.data
    for face,src_id in zip(vpm.data.polygons,ids):
        tile=ID_TILE[src_id]
        for li in face.loop_indices:
            u,v=raw_uv[li]
            # Flat source swatches can use any point within their constant tile.
            # Railing keeps its exact source UV rectangle and alpha registration.
            if src_id!=7: u,v=0.05+0.9*(u-math.floor(u)),0.05+0.9*(v-math.floor(v))
            uv[li].uv=(u+tile-1001,v)
    vpm.data.materials.clear()
    vm,bs=material('M_Truba_1_Main_1'); vpm.data.materials.append(vm)
    for p in vpm.data.polygons:p.material_index=0
    udim_preview(vm)
    npm=vpm.copy(); npm.data=vpm.data.copy(); scene.collection.objects.link(npm)
    npm.name='SM_Truba_1_003_Main'; npm.hide_render=True
    for face,src_id in zip(npm.data.polygons,ids):
        tile=ID_TILE[src_id]; region=LAYOUT[str(tile)]
        for li in face.loop_indices:
            u,v=vpm.data.uv_layers.active.data[li].uv
            npm.data.uv_layers.active.data[li].uv=(region['u0']+(u-tile+1001)*region['size'],region['v0']+v*region['size'])
    npm.data.materials.clear(); nm,bs=material('M_Truba_1_003_Main_1'); npm.data.materials.append(nm)
    npm_shader(nm,ROOT/'textures-npm')
    cols=sorted([o for o in scene.objects if o.name.startswith('Col_')],key=lambda o:o.name)
    assert len(cols)==60
    collision_before={o.name:snapshot(o) for o in cols}
    for i,o in enumerate(cols,1):
        o.name=f'UCX_SM_Truba_1_Main_{i:03d}'
        o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
        o.data.materials.clear()
        for layer in list(o.data.uv_layers):o.data.uv_layers.remove(layer)
        o.hide_render=True
        a=collision_before[f'Col_{i:03d}'];b=snapshot(o)
        assert a['faces']==b['faces'] and a['vertices']==b['vertices'],o.name
    for o in (vpm,npm):
        after=snapshot(o)
        assert before['vertices']==after['vertices'] and before['faces']==after['faces'],o.name
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'build'/'Truba_1_master.blend'))
    # Delivery material has no external paths, per VPM and the KPP exporter.
    saved=vm; clean,bs=material('M_Truba_1_Main_1_delivery')
    vm.name='PREVIEW_UDIM';clean.name='M_Truba_1_Main_1'
    vpm.data.materials[0]=clean
    for o in cols:o.hide_render=False
    vf=ROOT/'package-vpm'/'SM_Truba_1.fbx'
    nf=ROOT/'package-npm'/'0000_Truba_1_03.fbx'
    export([vpm,*cols],vf,False)
    export(cols,ROOT/'package-vpm'/'UCX_SM_Truba_1_Main.fbx',False)
    export([npm],nf,True)
    for path in (ROOT/'textures-vpm').glob('*.png'):shutil.copy2(path,ROOT/'package-vpm'/path.name)
    with zipfile.ZipFile(ROOT/'SM_Truba_1.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(vf,vf.name)
        for p in sorted((ROOT/'textures-vpm').glob('*.png')):z.write(p,p.name)
    with zipfile.ZipFile(ROOT/'0000_Truba_1.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(nf,nf.name)
    receipt={'application':bpy.app.version_string,'geometry_changed':False,'ucx_rebuilt':False,
        'source_ids':{str(i):ids.count(i) for i in sorted(set(ids))},'source_polygons':before['polygons'],
        'source_vertices':len(before['vertices']),'source_triangles':before['triangles'],
        'ucx':len(cols),'face_ids':'Original IDs retained on SOURCE_Tuba and source_material_id FACE attribute; export copies consolidate to one UDIM/atlas material.',
        'vpm_archive':'SM_Truba_1.zip','npm_archive':'0000_Truba_1.zip'}
    (ROOT/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('BUILD_OK',json.dumps(receipt))


if __name__=='__main__':main()
