"""Render four 63C review panels, using Workbench on a disposable copy of the scene.
Blender --background scene.blend --python stage2_views.py -- OUT_DIR FRAME_ID [ISO_ORTHO_SCALE]
"""
from pathlib import Path
import sys
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index('--')+1:]; folder, key = args[:2]; folder = Path(folder); folder.mkdir(exist_ok=True)
iso_scale = float(args[2]) if len(args) > 2 else 65  # optional ISO_ORTHO_SCALE (63B: taller tower)
s = bpy.context.scene
body = bpy.data.objects['SM_Body_Main']; frame = bpy.data.objects[f'SM_Win_{key}_Frame']; glass = bpy.data.objects[f'SM_Win_{key}_Glass']; cap = next(o for o in bpy.data.objects if o.name.startswith('CAPSULE_') and o.name.endswith(f'_{key}'))  # 63C/63B
s.render.engine = 'BLENDER_WORKBENCH'; s.display.shading.color_type = 'MATERIAL'; s.display.shading.light = 'STUDIO'; s.display.shading.show_cavity = True
s.render.resolution_x = 960; s.render.resolution_y = 720; s.render.resolution_percentage = 100
cam = bpy.data.objects.new('Review camera', bpy.data.cameras.new('Review camera')); s.collection.objects.link(cam); s.camera = cam
pts = [body.matrix_world @ Vector(c) for c in body.bound_box]; mid = sum(pts,Vector())/8
centre=lambda o: sum([o.matrix_world @ Vector(c) for c in o.bound_box],Vector())/8
wc=centre(frame); out=wc-centre(cap); out.z=0; out.normalize(); side=Vector((-out.y,out.x,0)); z=Vector((0,0,1))
meshes=[o for o in s.objects if o.type=='MESH']; wire={}
black=bpy.data.materials.new('Graphite wire'); black.diffuse_color=(.014,.021,.03,1)
for ob in (body,frame,glass,cap):
    w=ob.copy(); w.data=ob.data.copy(); s.collection.objects.link(w); w.data.materials.clear(); w.data.materials.append(black); m=w.modifiers.new('Edges','WIREFRAME'); m.thickness=.014 if ob==body else .007; m.use_even_offset=False; wire[ob]=w

def render(name,target,delta,scale,visible=None):
    for ob in meshes:
        ob.hide_render=visible is not None and ob not in visible
        if ob in wire: wire[ob].hide_render=ob.hide_render
    cam.location=target+delta; cam.rotation_euler=(-delta).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.data.clip_end=300
    s.render.filepath=str(folder/(name+'.png')); bpy.ops.render.render(write_still=True)

render('iso',mid,Vector((-45,-75,40)),iso_scale)
render('window',wc,out*3+side*.75+z*.5,4.6)
render('capsule',(wc+centre(cap))*.5,out*2+side*3+z*1.5,4.7,{frame,glass,cap})
render('cut',Vector((mid.x,mid.y,max(p.z for p in pts)-.4)),Vector((-35,-50,60)),45)
