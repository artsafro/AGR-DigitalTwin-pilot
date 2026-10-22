"""new-case: depth-correct Blender TEC26 inspection renders; no model saves or source edits."""
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector

JOB = Path(__file__).resolve().parents[1]
ROOT = Path('C:/x/tec26-oks/max-readback-v002')
OUT = Path('G:/Мой диск/AGR-evidence/tec26-oks/depth-census-v001')
OUT.mkdir(parents=True,exist_ok=False)


def colour(mid):
    import colorsys
    return (*colorsys.hsv_to_rgb((mid*0.61803398875)%1,0.65,0.9),1)


def create_mesh(node, mode):
    raw=json.loads((ROOT/node['diagnostic_buffer']).read_text(encoding='utf-8'))
    mesh=bpy.data.meshes.new('source-'+str(node['handle']))
    mesh.from_pydata(raw['vertices'],[],raw['triangles'])
    mesh.update()
    obj=bpy.data.objects.new(node['name'],mesh)
    bpy.context.collection.objects.link(obj)
    ids=sorted(set(raw['material_ids']))
    index={mid:i for i,mid in enumerate(ids)}
    for mid in ids:
        mat=bpy.data.materials.new('ID_'+str(mid))
        mat.diffuse_color=colour(mid) if mode=='ids' else (0.55,0.58,0.62,1)
        obj.data.materials.append(mat)
    for poly,mid in zip(mesh.polygons,raw['material_ids'],strict=True):
        poly.material_index=index[mid]
    return raw['vertices']


def zero_line(low,high):
    # No ground plane: the required below-zero geometry must remain visible.
    pad=max((high-low).length*0.015,0.1)
    points=[(low.x-pad,low.y-pad,0),(high.x+pad,low.y-pad,0),
            (high.x+pad,high.y+pad,0),(low.x-pad,high.y+pad,0)]
    curve=bpy.data.curves.new('project-zero-outline','CURVE')
    curve.dimensions='3D'
    curve.bevel_depth=max((high-low).length*0.0005,0.006)
    spline=curve.splines.new('POLY')
    spline.points.add(3)
    for p,co in zip(spline.points,points,strict=True):
        p.co=(*co,1)
    spline.use_cyclic_u=True
    obj=bpy.data.objects.new('PROJECT_ZERO_Z_0',curve)
    bpy.context.collection.objects.link(obj)
    mat=bpy.data.materials.new('ProjectZero_Red')
    mat.diffuse_color=(0.8,0.015,0.01,1)
    curve.materials.append(mat)


oks=json.loads((JOB/'census/oks.json').read_text(encoding='utf-8'))
truba=json.loads((JOB/'census/truba.json').read_text(encoding='utf-8'))
sets=[(f'ac{i:02d}',[n for n in oks['objects'] if n['layer']==f'{i:03d}' and n['kind']=='surface']) for i in range(4,10)]
sets += [('truba',[n for n in truba['objects'] if n['kind']=='surface'])]
receipts=[]
for name,nodes in sets:
    for mode in ('ids','shaded'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        assert bpy.app.version[:2]==(5,1), bpy.app.version_string
        scene=bpy.context.scene
        scene.unit_settings.system='METRIC'
        scene.unit_settings.scale_length=1
        vertices=[]
        for node in nodes:
            assert node['snapshot_bbox_parity_0_01mm'] and node['kind']=='surface'
            vertices += create_mesh(node,mode)
        low=Vector(tuple(min(v[a] for v in vertices) for a in range(3)))
        high=Vector(tuple(max(v[a] for v in vertices) for a in range(3)))
        center=(low+high)/2
        zero_line(low,high)
        camera_data=bpy.data.cameras.new('CensusCamera')
        camera=bpy.data.objects.new('CensusCamera',camera_data)
        scene.collection.objects.link(camera)
        scene.camera=camera
        direction=Vector((1.4,-1.8,1.0)).normalized()
        camera.location=center+direction*max((high-low).length*2,10)
        camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        camera_data.type='ORTHO'
        camera_data.ortho_scale=max((high-low).length*1.12,1)
        camera_data.clip_start=0.001
        camera_data.clip_end=max((high-low).length*10,1000)
        scene.render.engine='BLENDER_WORKBENCH'
        shade=scene.display.shading
        shade.light='STUDIO'
        shade.color_type='MATERIAL'
        shade.show_shadows=True
        shade.show_cavity=True
        shade.cavity_type='BOTH'
        shade.show_object_outline=False
        shade.background_type='WORLD'
        scene.world.color=(0.88,0.88,0.88)
        scene.view_settings.view_transform='Standard'
        scene.render.resolution_x=1000
        scene.render.resolution_y=850
        scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG'
        scene.render.image_settings.color_mode='RGB'
        scene.render.filepath=str(OUT/f'{name}-{mode}.png')
        assert not Path(scene.render.filepath).exists()
        bpy.ops.render.render(write_still=True)
        receipts.append({'building':name,'mode':mode,'path':scene.render.filepath,
            'application':bpy.app.version_string,'engine':scene.render.engine,
            'surface_handles':[n['handle'] for n in nodes],
            'collision_objects_loaded':0,'world_bounds_m':[list(low),list(high)],
            'zero_line_world_z_m':0,'surface_triangles':sum(n['triangles'] for n in nodes),
            'not_verified':'per-wall perimeter continuity; material finish; human acceptance'})
with (OUT/'render-receipts.json').open('x',encoding='utf-8') as stream:
    json.dump(receipts,stream,indent=2)
print('TEC26_DEPTH_RENDER_COMPLETE',len(receipts))
