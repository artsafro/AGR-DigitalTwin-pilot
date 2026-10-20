"""Headless, staged Flora light build; publication only after FBX readback and five-view QA.

Pattern: n/a | new-case: #347 alpha-aware subset of three existing NPM library meshes.
Run with uv run python tools/flora/build_flora_npm_light.py --work <private scratch>.
Max and Blender subprocesses run this same file via FLORA_LIGHT_JOB (no NumPy in Max).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('C:/x/flora-library/v003/flora-library-v003.max')
OUTPUT = Path('C:/x/flora-light/v001')
DCC = 'C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py'
BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def max_stage(job):
    from pymxs import runtime as rt
    def xyz(p):
        return [float(p.x),float(p.y),float(p.z)]
    rt.resetMaxFile(rt.Name('noPrompt'))
    require(rt.loadMaxFile(job['copy'], quiet=True), 'loadMaxFile failed')
    require(str(rt.units.SystemType).lower() == 'meters', 'library units not metres')
    require(float(rt.units.SystemScale) == 1, 'unexpected system unit scale')
    nodes = {}
    for row in job['species']:
        matches = [n for n in rt.objects if str(n.name) == row['objects']['NPM']]
        require(len(matches) == 1, 'ambiguous library object')
        nodes[row['material_id']] = matches[0]
    if job['action'] == 'extract':
        meshes = {}
        for mid,n in nodes.items():
            mesh = rt.snapshotAsMesh(n)
            try:
                pivot = xyz(n.pivot)
                vertices = [[c-pivot[i] for i,c in enumerate(xyz(rt.getVert(mesh,j)))] for j in range(1,int(mesh.numverts)+1)]
                faces = [[int(c)-1 for c in xyz(rt.getFace(mesh,j))] for j in range(1,int(mesh.numfaces)+1)]
                uv = [[xyz(rt.getTVert(mesh,int(c)))[:2] for c in xyz(rt.getTVFace(mesh,j))] for j in range(1,int(mesh.numfaces)+1)]
                require(len(faces) == next(s['triangles']['NPM'] for s in job['species'] if s['material_id']==mid), 'source triangle mismatch')
                require({int(rt.getFaceMatID(mesh,j)) for j in range(1,int(mesh.numfaces)+1)} == {mid}, 'source material ID mismatch')
                row = next(s for s in job['species'] if s['material_id']==mid)
                for slot in ('diffuse','opacity'):
                    require(Path(str(getattr(n.material,slot+'Map').filename)).resolve() == Path(row['maps'][slot]).resolve(), 'map mismatch')
                meshes[str(mid)] = {'vertices': vertices, 'faces': faces, 'uv': uv}
            finally:
                rt.delete(mesh)
        save(job['result'], {'version':str(rt.maxVersion()), 'units':'meters', 'meshes':meshes})
    else:
        rt.pluginManager.loadClass(rt.FBXEXP)
        for key,value in [('Animation',False),('Cameras',False),('Lights',False),('EmbedTextures',False),('Triangulate',True)]:
            rt.FBXExporterSetParam(key,value)
        facts = []
        for row in job['species']:
            mid = row['material_id']; clone = rt.copy(nodes[mid]); rt.convertToMesh(clone)
            keep = set(job['selected'][str(mid)])
            drop = [i+1 for i in range(int(rt.getNumFaces(clone))) if i not in keep]
            bits = rt.execute('#{'+','.join(str(i) for i in drop)+'}')
            rt.meshop.deleteFaces(clone,bits,delIsoVerts=True); rt.update(clone)
            clone.name = row['objects']['NPM']+'_light'; clone.pos = rt.point3(0,0,0)
            require(int(rt.getNumFaces(clone)) == len(keep), 'subset triangle mismatch')
            rt.select(clone)
            path = str(Path(job['stage'])/'fbx'/(str(clone.name)+'.fbx')).replace('\\','/')
            require(rt.exportFile(path,rt.Name('noPrompt'),selectedOnly=True,using=rt.FBXEXP), 'FBX export failed')
            ids = sorted({int(rt.getFaceMatID(clone,i)) for i in range(1,int(rt.getNumFaces(clone))+1)})
            require(ids == [mid], 'Max face material IDs changed')
            facts.append({'object':str(clone.name),'triangles':int(rt.getNumFaces(clone)), 'pivot':xyz(clone.pivot),'face_material_ids':ids})
        require(rt.saveMaxFile(str(Path(job['stage'])/'flora-npm-light-v001.max').replace('\\','/'), quiet=True), 'saveMaxFile failed')
        save(job['result'], {'objects':facts})
    print('FLORA_LIGHT_STAGE_COMPLETE',job['action'])


def blender_stage(job):
    import bpy
    result = {}
    for fbx in sorted((Path(job['stage'])/'fbx').glob('*.fbx')):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(fbx),use_custom_normals=True)
        objects = [o for o in bpy.context.scene.objects if o.type=='MESH']
        require(len(objects)==1, 'FBX must hold one mesh')
        obj = objects[0]; m = obj.data; m.calc_loop_triangles()
        require(len(m.loop_triangles)>0 and all(len(p.vertices)==3 for p in m.polygons), 'FBX is empty or not triangulated')
        vertices = [list(obj.matrix_world@v.co) for v in m.vertices]
        uv = [[list(m.uv_layers.active.data[i].uv) for i in t.loops] for t in m.loop_triangles]
        result[fbx.stem] = {'vertices':vertices,'faces':[list(t.vertices) for t in m.loop_triangles], 'uv':uv,
                           'materials':[s.material.name if s.material else None for s in obj.material_slots],
                           'images':[im.filepath for im in bpy.data.images if im.source=='FILE'],
                           'material_indices': sorted(set(p.material_index for p in m.polygons))}
    save(job['result'],result)


def run(command, work, label, env=None):
    result = subprocess.run(command,capture_output=True,env=env,cwd=ROOT)
    (work/(label+'.log')).write_bytes(result.stdout+result.stderr)
    print(label,'exit',result.returncode,flush=True)
    if result.returncode:
        raise RuntimeError(label+' failed: '+(result.stdout+result.stderr).decode('utf-8',errors='replace')[-2000:])


def execute(work, sources):
    import numpy as np
    from PIL import Image
    from dt_ai.materials.flora_light import POINTS, METHOD, guard_output, select_faces, measure, validate_records, validate_binding
    cat = load(ROOT/'library/flora/catalogue.json')
    rows = [s for s in cat['species'] if s['material_id'] in POINTS]
    protected = [SOURCE, *map(Path,sources)]
    guard_output(OUTPUT,protected)
    if len(sources)!=2 or {Path(p).name for p in sources} != {'FLORA_Union_v1.max','FLORIO_2BT_2022.max'}:
        raise ValueError('pass both original source scene paths with --source-scene')
    work = Path(work).resolve()
    if not work.is_relative_to(ROOT/'tmp'):
        raise ValueError('work must be private staging under this worktree/tmp')
    guard_output(work,protected)
    work.mkdir(parents=True,exist_ok=False)
    stage = work/'stage'
    if stage.exists():
        raise ValueError('staging already exists; use a fresh work directory')
    stage.mkdir(); (stage/'fbx').mkdir()
    before = {str(p):sha(p) for p in protected}
    save(work/"source-hashes-before.json",before)
    copy = work/'library-copy.max'; shutil.copy2(SOURCE,copy)
    env = os.environ.copy(); env['FLORA_LIGHT_JOB'] = str(work/'job.json')
    job = {'copy':str(copy).replace('\\','/'), 'species':rows, 'stage':str(stage)}
    for action in ('extract','build'):
        job.update(action=action,result=str(work/(action+'.json')))
        if action=='build':
            meshes = load(work/'extract.json')['meshes']; selected={}
            for row in rows:
                mid = str(row['material_id'])
                opacity = np.asarray(Image.open(row['maps']['opacity']).convert('L'))
                selected[mid] = select_faces(meshes[mid], opacity)
            job['selected'] = selected
            save(work/'selection.json',selected)
        save(work/'job.json',job)
        run([sys.executable,DCC,'max','--file',str(Path(__file__).resolve()),'--version','2026',
             '--timeout','360','--wait','120','--out',str(work/(action+'-runner.json')),'--max-chars','2000'],work,action,env)
        if not Path(job['result']).is_file():
            raise RuntimeError('Max did not write completion receipt: '+action)
    job.update(action='blender',result=str(work/'alpha-readback.json')); save(work/'job.json',job)
    run([BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(Path(__file__).resolve())],work,'alpha-readback',env)
    readback = load(work/'alpha-readback.json'); variants=[]
    for row in rows:
        name=row['objects']['NPM']+'_light'; fbx=stage/'fbx'/(name+'.fbx')
        structural=stage/'fbx'/(name+'-readback.json')
        run([BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'tools/blender/fbx_readback.py'),'--',str(fbx),str(structural)],work,name+'-readback')
        report=load(structural)
        require(report['readback_ok'] and len(report['meshes'])==1, 'structural FBX readback failed')
        facts=report['meshes'][0]; mesh=readback[name]
        require(facts['triangles']==len(mesh['faces']) and facts['polygon_degrees']=={'3':facts['triangles']}, 'inconsistent triangle readbacks')
        validate_binding(row,mesh)
        bounds=np.ptp(np.asarray(mesh['vertices']),axis=0)
        opacity=np.asarray(Image.open(row['maps']['opacity']).convert('L'))
        scores=measure(meshes[str(row['material_id'])],mesh,opacity,images=stage/'silhouettes'/name)
        variants.append({'material_id':row['material_id'],'object':name,'file':str(OUTPUT/'flora-npm-light-v001.max').replace('\\','/'),
            'sha256':sha(stage/'flora-npm-light-v001.max'),'fbx':str(OUTPUT/'fbx'/fbx.name).replace('\\','/'), 'fbx_sha256':sha(fbx),
            'triangles':facts['triangles'],'height_m':float(bounds[2]),'crown_diameter_m':float(max(bounds[:2])),
            'method':METHOD,'maps':{k:row['maps'][k] for k in ('diffuse','opacity')},'silhouettes':scores})
    document={'schema':'flora-npm-light-v1','variants':variants}
    total=validate_records(cat,document)
    after={str(p):sha(p) for p in protected}
    if before!=after:
        raise ValueError('protected source hash changed')
    save(stage/'npm-light.json',document)
    save(stage/'evidence.json',{'before':before,'after':after,'total_triangles':total,'margin':70000-total,
         'placement_basis':'#347 fallback: #296 placement report not merged', 'selection_resolution':512,'verification_resolution':1024,
         'source_sha256':sha(copy),'max_build':load(work/'build.json')})
    guard_output(OUTPUT,protected)
    # mkdir is exclusive. Copy no final files until every variant and input hash passes.
    OUTPUT.mkdir(parents=True,exist_ok=False)
    shutil.copytree(stage,OUTPUT,dirs_exist_ok=True)
    print('PUBLISHED',str(OUTPUT),'Flora triangles',total,'margin',70000-total)


def main():
    if os.environ.get('FLORA_LIGHT_JOB'):
        job=load(os.environ['FLORA_LIGHT_JOB'])
        (blender_stage if job['action']=='blender' else max_stage)(job)
        return
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',required=True)
    parser.add_argument('--source-scene',action='append',default=[])
    args=parser.parse_args()
    try:
        execute(args.work,args.source_scene)
    except (ValueError,RuntimeError,AssertionError,OSError) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__=='__main__':
    main()
