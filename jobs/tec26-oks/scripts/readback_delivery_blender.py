"""Read delivered ZIPs back, inspect embedded pixels and render the exported UVs.

new-case: truba ZIP pixel-role/stale-map rejection and exported geometry readback.
Operational readback, not whole-site validation or human acceptance.
"""
import bpy
import sys
import json
import math
import struct
import zipfile
from pathlib import Path
from mathutils import Vector
from io_scene_fbx import parse_fbx
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_delivery_blender as build

ROOT=build.ROOT


def png(data, size, mode):
    assert data[:8]==b'\x89PNG\r\n\x1a\n','not PNG'
    w,h,depth,kind=struct.unpack('>IIBB',data[16:26])
    assert (w,h,depth,kind)==(size,size,8,mode),f'PNG mismatch: {(w,h,depth,kind)} != {(size,size,8,mode)}'
    return {'size':w,'bit_depth':depth,'mode':'RGBA' if kind==6 else 'RGB'}


def inspect_zip(path, profile):
    with zipfile.ZipFile(path) as z:
        assert len(z.namelist())==len(set(z.namelist())),'duplicated ZIP entries'
        if profile=='npm':
            assert z.namelist()==['0000_Truba_1_03.fbx'],f'NPM must contain only FBX: {z.namelist()}'
        else:
            expected={'SM_Truba_1.fbx'}|{f'T_Truba_1_{kind}_1.{t}.png' for t in range(1001,1007) for kind in ['Diffuse','ERM','Normal']}
            assert set(z.namelist())==expected,f'VPM members mismatch: {set(z.namelist()) ^ expected}'
            for t in range(1001,1007):
                for kind in ['Diffuse','ERM','Normal']:
                    name=f'T_Truba_1_{kind}_1.{t}.png'
                    expected_bytes=(ROOT/'textures-vpm'/name).read_bytes()
                    png(z.read(name),4096 if t==1006 and kind=='Diffuse' else 256,6 if t==1006 and kind=='Diffuse' else 2)
                    assert z.read(name)==expected_bytes,f'stale VPM map {name}'
        return z.namelist()


def embedded(path, folder):
    tree,version=parse_fbx.parse(str(path))
    result={}
    def walk(e):
        if e.id==b'Video':
            props={s.id:s.props for s in e.elems}
            if b'Content' in props:
                name=Path(props[b'Filename'][0].decode().replace('\\','/')).name
                data=props[b'Content'][0]
                assert name not in result,'duplicate embedded map'
                png(data,2048,2)
                assert data==(ROOT/'textures-npm'/name).read_bytes(),f'stale NPM {name}'
                (folder/name).write_bytes(data);result[name]=len(data)
        for sub in e.elems:walk(sub)
    walk(tree)
    assert set(result)=={f'T_Truba_1_003_Main_{s}_1.png' for s in ['d','o']},result
    return result


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def geometry_equal(a,b):
    assert a['faces']==b['faces'],'face topology/winding changed'
    assert len(a['vertices'])==len(b['vertices']),'vertex count changed'
    delta=max(abs(x-y) for p,q in zip(a['vertices'],b['vertices']) for x,y in zip(p,q))
    assert delta<0.00001,f'vertex movement {delta} m'
    return delta


def render(obj, out, side=False):
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
    scene.world=bpy.data.worlds.new('ReadbackWorld');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(0.75,0.75,0.75,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=0.8
    pts=[obj.matrix_world@v.co for v in obj.data.vertices]
    lo=Vector([min(p[k] for p in pts) for k in range(3)]);hi=Vector([max(p[k] for p in pts) for k in range(3)])
    centre=(lo+hi)/2
    cam=bpy.data.objects.new('CompareCamera',bpy.data.cameras.new('CompareCamera'));scene.collection.objects.link(cam)
    direction=Vector((0,-1,0.06) if side else (1,-1.5,0.55)).normalized()
    cam.location=centre+direction*160;cam.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=88;cam.data.clip_end=1000;scene.camera=cam
    light=bpy.data.objects.new('Key',bpy.data.lights.new('Key','AREA'));scene.collection.objects.link(light)
    light.location=centre+Vector((35,-60,85));light.data.energy=15000;light.data.shape='DISK';light.data.size=50
    light.rotation_euler=(centre-light.location).to_track_quat('-Z','Y').to_euler()
    # A small cylinder marks exactly z=0 without occluding the perimeter drop.
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=0.055,depth=70,location=(centre.x,lo.y-1,0),rotation=(0,math.pi/2,0))
    bar=bpy.context.object;bar.name='PREVIEW_ZERO_000'
    mat,bs=build.material('PREVIEW_ZERO');bs.inputs['Base Color'].default_value=(0.65,0.015,0.015,1)
    bar.data.materials.append(mat)
    scene.render.filepath=str(out);bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam,do_unlink=True);bpy.data.objects.remove(light,do_unlink=True);bpy.data.objects.remove(bar,do_unlink=True)


def main():
    # Optional explicit old ZIP probe fails before any extraction/render or writes.
    if len(sys.argv)>sys.argv.index('--')+2:
        inspect_zip(Path(sys.argv[-1]),'vpm');return
    members={p:inspect_zip(ROOT/n,p) for p,n in [('vpm','SM_Truba_1.zip'),('npm','0000_Truba_1.zip')]}
    rb=ROOT/'readback'
    assert not rb.exists(),'readback must use a new directory'
    rb.mkdir();(ROOT/'renders').mkdir()
    for profile,name in [('vpm','SM_Truba_1.zip'),('npm','0000_Truba_1.zip')]:
        folder=rb/profile;folder.mkdir()
        with zipfile.ZipFile(ROOT/name) as z:z.extractall(folder)
    embed_dir=rb/'embedded';embed_dir.mkdir()
    images=embedded(rb/'npm'/'0000_Truba_1_03.fbx',embed_dir)
    clear();bpy.ops.import_scene.fbx(filepath=str(ROOT/'source.fbx'),use_image_search=False)
    source=bpy.data.objects['Tuba'];baseline=build.snapshot(source)
    ids=[p.material_index+1 for p in source.data.polygons]
    source_uv=[tuple(d.uv) for d in source.data.uv_layers.active.data]
    hulls={o.name:build.snapshot(o) for o in bpy.data.objects if o.name.startswith('Col_')}
    receipt={'zip_members':members,'npm_embedded':images,'profiles':{},'acceptance':'not claimed; human/SINTEZ gates deferred'}
    for profile in ['vpm','npm']:
        clear();folder=rb/profile
        fbx_name='SM_Truba_1.fbx' if profile=='vpm' else '0000_Truba_1_03.fbx'
        bpy.ops.import_scene.fbx(filepath=str(folder/fbx_name),use_image_search=False)
        obj=next(o for o in bpy.data.objects if o.name.startswith('SM_'))
        delta=geometry_equal(baseline,build.snapshot(obj))
        assert len(obj.data.uv_layers)==1
        assert len(obj.data.materials)==1
        expected_mat='M_Truba_1_Main_1' if profile=='vpm' else 'M_Truba_1_003_Main_1'
        assert obj.data.materials[0].name==expected_mat,obj.data.materials[0].name
        cols=sorted([o for o in bpy.data.objects if o.name.startswith('UCX_')],key=lambda o:o.name)
        assert len(cols)==(60 if profile=='vpm' else 0)
        for i,o in enumerate(cols,1):
            assert o.name==f'UCX_SM_Truba_1_Main_{i:03d}'
            geometry_equal(hulls[f'Col_{i:03d}'],build.snapshot(o));o.hide_render=True
        uv=obj.data.uv_layers.active.data
        for face,src_id in zip(obj.data.polygons,ids):
            tile=build.ID_TILE[src_id]
            for li in face.loop_indices:
                u,v=uv[li].uv
                if profile=='npm':
                    region=build.LAYOUT[str(tile)]
                    u=(u-region['u0'])/region['size'];v=(v-region['v0'])/region['size']
                else:u-=tile-1001
                assert -0.00001<=u<=1.00001 and -0.00001<=v<=1.00001,(profile,face.index,u,v)
                if src_id==7:
                    assert abs(u-source_uv[li][0])<0.00001 and abs(v-source_uv[li][1])<0.00001,'railing registration changed'
        mat=obj.data.materials[0]
        if profile=='vpm':build.udim_preview(mat,folder)
        else:
            # Use the actual FBX embedded bytes, not paths back to the build maps.
            for n in list(mat.node_tree.nodes):
                if n.type=='TEX_IMAGE':mat.node_tree.nodes.remove(n)
            build.npm_shader(mat,embed_dir)
        info={'vertices':len(obj.data.vertices),'quads':sum(len(p.vertices)==4 for p in obj.data.polygons),
            'triangles':sum(len(p.vertices)-2 for p in obj.data.polygons),'material_count':len(obj.data.materials),
            'ucx':len(cols),'max_world_vertex_delta_m':delta,'min_z_m':min(p[2] for p in build.snapshot(obj)['vertices']),
            'railing_source_uv_registration':'preserved'}
        receipt['profiles'][profile]=info
        render(obj,ROOT/'renders'/f'{profile}_angle.png')
        render(obj,ROOT/'renders'/f'{profile}_front.png',side=True)
    (ROOT/'readback-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('ZIP_READBACK_OK',json.dumps(receipt))


if __name__=='__main__':main()
