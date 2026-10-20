"""Read-only scene-copy material/UV evidence for #369; run only in Max batch.

Pattern: n/a | new-case: Flora texture diagnosis, no production asset changes.
FLORA_DIAG_JOB points at a job with copied scenes and explicit catalogue records.
"""
import hashlib
import json
import os
from pathlib import Path
from pymxs import runtime as rt


def xyz(p):
    return [float(p.x), float(p.y), float(p.z)]


def prop(obj, name):
    try:
        v = getattr(obj, name)
        if isinstance(v, (str, bool, int, float)):
            return v
        return str(v)
    except Exception:
        return None


def material_info(mat):
    if mat == rt.undefined or mat is None:
        return None
    result = {'name': str(mat.name), 'class': str(rt.classOf(mat)), 'properties': {}, 'textures': []}
    result['bindings'] = {k: prop(mat,k) for k in ('diffuseMap','opacityMap','diffuseMapEnable','opacityMapEnable','diffuseMapAmount','opacityMapAmount')}
    result['slot_paths']={}
    result['slot_settings']={}
    for slot in ('diffuseMap','opacityMap'):
        try:
            texture=getattr(mat,slot)
            result['slot_paths'][slot]=str(texture.filename)
            result['slot_settings'][slot]={k:prop(texture,k) for k in ('monoOutput','rgbOutput','alphaSource')}
        except (AttributeError,RuntimeError):
            result['slot_paths'][slot]=None
    for key in rt.getPropNames(mat):
        key = str(key)
        if any(s in key.lower() for s in ('map', 'opacity', 'diffuse', 'base_color', 'cutout', 'two', 'alpha')):
            result['properties'][key] = prop(mat, key)
    for tex in rt.getClassInstances(rt.Bitmaptexture, target=mat):
        coords = tex.coords
        result['textures'].append({'name': str(tex.name), 'filename': str(tex.filename),
            'settings': {k: prop(tex,k) for k in ('monoOutput','rgbOutput','alphaSource','premultAlpha','filtering','gamma')},
            'coords': {k: prop(coords,k) for k in ('mapChannel','U_Tiling','V_Tiling','U_Offset','V_Offset','U_Angle','V_Angle','W_Angle','U_Mirror','V_Mirror','U_Tile','V_Tile')}})
    if str(rt.classOf(mat)) == 'Multimaterial':
        result['submaterial_ids'] = [int(v) for v in mat.materialIDList]
    for i in range(1, int(rt.getNumSubMtls(mat))+1):
        result.setdefault('submaterials',[]).append(material_info(rt.getSubMtl(mat,i)))
    return result


def inspect(node, detail):
    mesh = rt.snapshotAsMesh(node)
    try:
        nf = int(mesh.numfaces)
        nv = int(rt.meshop.getNumMapVerts(mesh,1))
        uv = [xyz(rt.meshop.getMapVert(mesh,1,i))[:2] for i in range(1,nv+1)]
        uvfaces = [[int(c)-1 for c in xyz(rt.meshop.getMapFace(mesh,1,i))] for i in range(1,nf+1)]
        corners = [[uv[j] for j in face] for face in uvfaces]
        result = {'name':str(node.name), 'triangles':nf, 'uv_vertices':nv,
                  'material':material_info(node.material),
                  'uv_bounds': [[min(p[a] for p in uv),max(p[a] for p in uv)] for a in range(2)] if uv else None,
                  'uv_sha256': hashlib.sha256(json.dumps(corners,separators=(',',':')).encode()).hexdigest(),
                  'material_ids': sorted({int(rt.getFaceMatID(mesh,i)) for i in range(1,nf+1)})}
        if detail:
            result.update(vertices=[xyz(rt.getVert(mesh,i)) for i in range(1,int(mesh.numverts)+1)],
                          faces=[[int(c)-1 for c in xyz(rt.getFace(mesh,i))] for i in range(1,nf+1)],
                          uv=uv,uvfaces=uvfaces,
                          face_material_ids=[int(rt.getFaceMatID(mesh,i)) for i in range(1,nf+1)])
        return result
    finally:
        rt.delete(mesh)


def main():
    job = json.loads(Path(os.environ['FLORA_DIAG_JOB']).read_text(encoding='utf-8'))
    work = Path(job['work']).resolve()
    output=(work/job.get('inventory','inventory.json')).resolve()
    if not output.is_relative_to(work) or output.exists():raise ValueError('fresh inventory inside private scratch required')
    for scene in job['scenes']:
        copy=Path(scene['copy']).resolve()
        if not copy.is_relative_to(work):raise ValueError('scene must be a private copy')
        expected=[h for p,h in job['hashes_before'].items() if Path(p).name==copy.name]
        with copy.open('rb') as handle:found=hashlib.file_digest(handle,'sha256').hexdigest()
        if len(set(expected))!=1 or found!=expected[0]:raise ValueError('scene copy hash mismatch')
    evidence = {'version':str(rt.maxVersion()), 'scenes':{}, 'failures':[]}
    for scene in job['scenes']:
        rt.resetMaxFile(rt.Name('noPrompt'))
        if not rt.loadMaxFile(scene['copy'].replace('\\','/'),quiet=True):
            raise RuntimeError('load failed '+scene['copy'])
        tag = scene['tag']
        records = {}
        evidence['scenes'][tag] = {'units':str(rt.units.SystemType),'scale':float(rt.units.SystemScale),'records':records}
        for species in job['species']:
            for profile in ('NPM','VPM'):
                ref = species[profile.lower()]
                if not ref:
                    continue
                if tag != 'ours' and ref['scene'] != Path(scene['copy']).name:
                    continue
                key = species['objects'][profile]
                name = key if tag == 'ours' else ref['source_name']
                matches = [n for n in rt.geometry if str(n.name)==name]
                if len(matches)>1:
                    matches=[n for n in matches if int(rt.getNumFaces(rt.snapshotAsMesh(n)))==int(ref['triangles'])]
                if len(matches)!=1:
                    evidence['failures'].append({'tag':tag,'key':key,'name':name,'matches':len(matches)})
                    continue
                records[key] = inspect(matches[0],species['material_id'] in job['selected'])
        output.write_text(json.dumps(evidence,ensure_ascii=False),encoding='utf-8')
        print('DIAG_SCENE',tag,len(records),flush=True)
    evidence['light']={}
    rt.pluginManager.loadClass(rt.FBXIMP)
    for fbx in job['fbxs']:
        rt.resetMaxFile(rt.Name('noPrompt'))
        rt.FBXImporterSetParam('Mode',rt.Name('create'))
        if not rt.importFile(fbx.replace('\\','/'),rt.Name('noPrompt'),using=rt.FBXIMP):
            raise RuntimeError('import failed '+fbx)
        nodes=list(rt.geometry)
        if len(nodes)!=1:raise RuntimeError('expected one FBX geometry '+fbx)
        evidence['light'][Path(fbx).stem]=inspect(nodes[0],True)
    output.write_text(json.dumps(evidence,ensure_ascii=False),encoding='utf-8')
    print('DIAG_COMPLETE',len(evidence['failures']),flush=True)


if __name__ == '__main__':
    main()
