"""Render source/agent/light comparisons using copied scenes, native Max scanline.

Pattern: n/a | new-case: #369 diagnostic-only two-sided neutral renders, never save scenes.
Run via dcc_batch.py max --file; FLORA_DIAG_JOB names the copied-scene job.
"""
import json
import math
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from diagnose_texture import resolve_bitmap, guard_outputs
from diagnose_texture_max import material_info, xyz, prop
from pymxs import runtime as rt


def render_node(node, key, tag, folder, maps, size, receipts):
    if node.material == rt.undefined:
        raise ValueError('unmapped material '+key)
    original_info=material_info(node.material)
    source_color_mode=str(rt.ColorPipelineMgr.Mode)
    rt.ColorPipelineMgr.Mode=rt.Name('Gamma')
    rt.ColorPipelineMgr.DisplayGamma=2.2
    source_material=node.material
    # Detached evaluated world-space mesh avoids hidden display-group inheritance.
    mesh=rt.snapshotAsMesh(node)
    try:
        node=rt.mesh(mesh=mesh)
    finally:
        rt.delete(mesh)
    mat=rt.copy(source_material)
    if str(rt.classOf(mat))!='Standardmaterial':
        raise ValueError('unsupported material '+str(rt.classOf(mat)))
    node.material=mat
    # Common diagnostic override only: show both faces of source/agent cutout planes.
    mat.twoSided=True
    resolved=[]
    for tex in rt.getClassInstances(rt.Bitmaptexture,target=mat):
        if maps:
            path=resolve_bitmap(str(tex.filename),maps)
        else:
            copies=json.loads(Path(os.environ['FLORA_DIAG_JOB']).read_text(encoding='utf-8'))['bitmap_copies']
            stored=str(tex.filename).replace('\\','/').lower()
            if stored not in copies:raise ValueError('unmapped bitmap '+stored)
            path=Path(copies[stored])
        if not path.is_file():raise ValueError('missing bitmap '+str(path))
        original_path=str(path)
        decode=json.loads(Path(os.environ['FLORA_DIAG_JOB']).read_text(encoding='utf-8')).get('diagnostic_decode',{})
        path=Path(decode.get(str(path).replace('\\','/').lower(),str(path)))
        tex.filename=str(path).replace('\\','/')
        bitmap=rt.openBitmap(str(path))
        resolved.append({'path':str(path),'source_copy':original_path,'gamma':prop(bitmap,'gamma'),'hasAlpha':prop(bitmap,'hasAlpha'),
                         'monoOutput':prop(tex,'monoOutput'),'rgbOutput':prop(tex,'rgbOutput'),'alphaSource':prop(tex,'alphaSource')})
        rt.close(bitmap)
    if not mat.diffuseMapEnable or not mat.opacityMapEnable:
        raise ValueError('disabled diffuse/opacity '+key)
    for other in rt.geometry:
        other.isHidden=True
    layer=rt.LayerManager.getLayer(0)
    layer.isHidden=False
    layer.addNode(node)
    node.isHidden=False
    node.renderable=True
    box=rt.nodeGetBoundingBox(node,rt.matrix3(1))
    center=(box[0]+box[1])/2
    # Same physical framing for corresponding original/ours/light variants, recorded in job.
    distance=size*1.55
    rt.renderers.current=rt.Default_Scanline_Renderer()
    rt.backgroundColor=rt.color(190,190,190)
    rt.ambientColor=rt.color(55,55,55)
    rt.environmentMap=rt.undefined
    lights=[]
    for offset,power in [((1,-2,2),.8),((-2,1,1),.45)]:
        light=rt.Omnilight(pos=center+rt.point3(*(c*size for c in offset)),multiplier=power)
        light.castShadows=False
        lights.append(light)
    target=rt.Targetobject(pos=center)
    cam=rt.Targetcamera(pos=center+rt.point3(0,-distance,0),target=target)
    cam.orthoProjection=True
    cam.fov=45
    times=[]
    try:
        for view,vector in [('front',(0,-1,0)),('45',(2**-.5,-2**-.5,0)),('top',(0,0,1))]:
            path=folder/f'{key}-{tag}-{view}.png'
            guard_outputs([t['path'] for t in resolved],[path])
            cam.pos=center+rt.point3(*(distance*v for v in vector))
            t=time.perf_counter()
            image=rt.render(camera=cam,outputsize=rt.point2(512,512),vfb=False,rendertype=rt.Name('normal'))
            image.filename=str(path).replace('\\','/')
            rt.save(image,gamma=2.2)
            rt.close(image)
            times.append(time.perf_counter()-t)
            if not path.is_file():raise RuntimeError('render missing '+str(path))
    finally:
        rt.delete(cam)
        if rt.isValidNode(target):rt.delete(target)
        for light in lights:rt.delete(light)
    receipts.append({'key':key,'tag':tag,'size_m':size,'source_color_mode':source_color_mode,'render_color_mode':'Gamma 2.2; explicit save gamma 2.2','material_before_override':original_info,
                     'resolved_bitmaps':resolved,'render_seconds':times})
    (folder/'render-receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    print('RENDERED',tag,key,round(sum(times),2),flush=True)


def main():
    job=json.loads(Path(os.environ['FLORA_DIAG_JOB']).read_text(encoding='utf-8'))
    work=Path(job['work']).resolve();folder=(work/job.get('render_folder','renders-v001')).resolve()
    if not folder.is_relative_to(work):raise ValueError('render folder escapes private scratch')
    if folder.exists():raise ValueError('fresh render folder required')
    folder.mkdir()
    inventory=json.loads((work/job.get('inventory','inventory.json')).read_text(encoding='utf-8'))
    sizes={}
    for species in job['species']:
        if species['material_id'] not in job['selected']:continue
        for profile in (('NPM','VPM') if species['material_id']==105 else ('NPM',)):
            key=species['objects'][profile]
            r=inventory['scenes']['ours']['records'][key]
            sizes[key]=max(max(v[a] for v in r['vertices'])-min(v[a] for v in r['vertices']) for a in range(3))
    receipts=[]
    for scene in job['scenes']:
        copy=Path(scene['copy']).resolve()
        if not copy.is_relative_to(work):raise ValueError('scene must be a private copy')
        rt.resetMaxFile(rt.Name('noPrompt'))
        if not rt.loadMaxFile(str(copy).replace('\\','/'),quiet=True):raise RuntimeError('load failed')
        if str(rt.units.SystemType).lower()!='meters' or float(rt.units.SystemScale)!=1:raise ValueError('unexpected units')
        for node in rt.objects:
            node.isHidden=True
        for species in job['species']:
            if species['material_id'] not in job['selected']:continue
            for profile in (('NPM','VPM') if species['material_id']==105 else ('NPM',)):
                ref=species[profile.lower()];key=species['objects'][profile];tag=scene['tag']
                if tag!='ours' and ref['scene']!=copy.name:continue
                name=key if tag=='ours' else ref['source_name']
                matches=[n for n in rt.geometry if str(n.name)==name]
                if len(matches)!=1:raise ValueError('ambiguous node '+name)
                maps=None if tag=='ours' else scene['maps']
                render_node(matches[0],key,tag,folder,maps,sizes[key],receipts)
                if job.get('smoke'):return
    rt.pluginManager.loadClass(rt.FBXIMP)
    for fbx in job['fbxs']:
        rt.resetMaxFile(rt.Name('noPrompt'))
        rt.FBXImporterSetParam('Mode',rt.Name('create'))
        if not rt.importFile(fbx.replace('\\','/'),rt.Name('noPrompt'),using=rt.FBXIMP):raise RuntimeError('FBX import failed')
        nodes=list(rt.geometry)
        if len(nodes)!=1:raise ValueError('expected one light mesh')
        key=Path(fbx).stem.removesuffix('_light')
        render_node(nodes[0],key,'light',folder,None,sizes[key],receipts)
    print('RENDER_COMPLETE',len(receipts),flush=True)


if __name__=='__main__':
    main()
