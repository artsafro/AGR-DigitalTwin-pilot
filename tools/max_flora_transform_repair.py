"""New case #189: bake sheared flower transforms into world-space Mesh VALUES.

Native snapshotAsMesh world convention is guarded by v004. Unlike snapshot NODE,
mesh(mesh=world_value) starts at identity; FBX never has to decompose source shear.
One source COPY load; four derived meshes; no original/old FBX overwrite. Never
relax the world-position/UV/winding/finish matcher. Run only dcc_batch.py max.
"""
import json
import sys
import time
from pathlib import Path
TOOLS=Path(__file__).resolve().parent
HERE=TOOLS.parent/'experiments/flora-library-audit'
sys.path[:0]=[str(TOOLS),str(HERE)]
from max_flora_verify import checked_mesh
from catalogue import ROOT, fresh_path
from checkpoints import load_valid, save, sha
from export_fbx import preview
from mesh_compare import compare
from pymxs import runtime as rt

IDS=['library-080','library-081','library-082','library-083']
OUT=ROOT/'out/repairs-v007'


def main():
    if len(rt.objects) or str(rt.maxFileName):
        raise RuntimeError('Fresh headless session required')
    OUT.mkdir(parents=True,exist_ok=True)
    catalog=json.loads((HERE/'catalogue.json').read_text(encoding='utf-8'))
    entries={e['id']:e for s in catalog['scenes'] for e in s['entries'] if e['id'] in IDS}
    source_hash=catalog['sources'][0]['copy_sha256']
    if sha(ROOT/'FLORA_Union_v1.max')!=source_hash:
        raise RuntimeError('Source copy hash mismatch')
    start=time.perf_counter()
    rows=[]
    pending=[]
    for entry_id in IDS:
        row=load_valid(OUT/(entry_id+'.json'),entries[entry_id],source_hash)
        if row:
            rows.append(row)
        else:
            pending.append(entry_id)
    if pending:
        print('FLORA_IDENTITY_LOAD_COPY',len(pending),flush=True)
        if not rt.loadMaxFile(str(ROOT/'FLORA_Union_v1.max'),quiet=True):
            raise RuntimeError('Source copy load failed')
        bank=[]
        for entry_id in pending:
            old=load_valid(ROOT/'out/verified-v004'/(entry_id+'.json'),entries[entry_id],source_hash)
            baseline=json.loads((ROOT/'out/verified-v004'/(entry_id+'-readback.json')).read_text(encoding='utf-8'))
            if baseline['equal'] or baseline['file_sha256']!=old['sha256']:
                raise RuntimeError('Baseline failure not bound to the original FBX')
            source=rt.getNodeByName(entries[entry_id]['source_name'],exact=True)
            expected=checked_mesh(source)
            world_value=rt.snapshotAsMesh(source)
            node=rt.mesh(mesh=world_value)
            node.transform=rt.matrix3(1)
            node.material=source.material
            node.name=entries[entry_id]['source_name']+'_AuditWorldTri'
            before=compare(expected['triangles'],checked_mesh(node)['triangles'])
            if not before['equal']:
                raise RuntimeError('Identity Mesh differs from source: '+entry_id)
            bank.append({'id':entry_id,'node':node,'old':old,'expected':expected,
                         'before':before,'source_transform':str(source.transform),
                         'derived_transform':str(node.transform),'world_value':world_value})
            print('FLORA_IDENTITY_SOURCE_EQUAL',entry_id,before,flush=True)
        keep=[x['node'] for x in bank]
        rt.delete(rt.Array(*[o for o in list(rt.objects) if not any(o==k for k in keep)]))
        if len(rt.objects)!=len(keep):
            raise RuntimeError('Unexpected isolated scene node count')
        rt.pluginManager.loadClass(rt.FbxExporter)
        for key,value in [('Animation',False),('EmbedTextures',False),('ASCII',False),('FileVersion','FBX201400'),('UpAxis','Z'),('Cameras',False),('Lights',False),('SmoothingGroups',True)]:
            rt.FBXExporterSetParam(key,value)
        for item in bank:
            entry_id=item['id']
            if not compare(item['expected']['triangles'],checked_mesh(item['node'])['triangles'])['equal']:
                raise RuntimeError('Isolated Mesh differs from source')
            target=fresh_path(OUT,entry_id+'.fbx')
            svg=fresh_path(OUT,entry_id+'.svg')
            rt.select(rt.Array(item['node']))
            print('FLORA_IDENTITY_EXPORT',entry_id,flush=True)
            t0=time.perf_counter()
            if not rt.exportFile(str(target),rt.Name('noPrompt'),selectedOnly=True,using=rt.FBXEXP):
                raise RuntimeError('Identity Mesh export failed')
            preview(item['expected'],svg)
            row=dict(item['old'],expected=item['expected'],file=str(target),sha256=sha(target),
                     preview=str(svg),preview_sha256=sha(svg),seconds=time.perf_counter()-t0,
                     repair_basis='identity_transform_world_TriMesh_value',
                     derived_before_export=item['before'],source_transform=item['source_transform'],
                     derived_transform=item['derived_transform'],
                     original_unmodified_fbx=item['old']['file'],original_unmodified_fbx_sha256=item['old']['sha256'])
            save(OUT/(entry_id+'.json'),row)
            rows.append(row)
    rt.pluginManager.loadClass(rt.FbxImporter)
    readbacks=[]
    for row in rows:
        path=OUT/(row['id']+'-readback.json')
        if path.exists():
            rb=json.loads(path.read_text(encoding='utf-8'))
            if rb['file_sha256']!=row['sha256']:
                raise RuntimeError('Readback receipt hash mismatch')
        else:
            t0=time.perf_counter()
            rt.resetMaxFile(rt.Name('noPrompt'))
            rt.units.SystemType=rt.Name('meters')
            rt.units.SystemScale=1
            rt.FBXImporterSetParam('Mode',rt.Name('create'))
            if not rt.importFile(row['file'],rt.Name('noPrompt'),using=rt.FBXIMP):
                raise RuntimeError('Identity Mesh readback failed')
            nodes=[o for o in rt.objects if rt.superClassOf(o)==rt.GeometryClass]
            if len(nodes)!=1:
                raise RuntimeError('Expected one geometry node')
            actual=checked_mesh(nodes[0])
            result=compare(row['expected']['triangles'],actual['triangles'])
            result['bitmap_paths_equal']=actual['bitmap_files']==row['expected']['bitmap_files']
            equal=result['equal'] and result['bitmap_paths_equal'] and actual['system_units']=='meters' and actual['system_scale']==1
            rb={'id':row['id'],'file_sha256':row['sha256'],'node_count':1,'equal':equal,'comparison':result,
                'snapshot_bbox':actual['snapshot_bbox'],'snapshot_bbox_probe_error_mm':actual['bbox_probe_error_mm'],
                'seconds':time.perf_counter()-t0}
            save(path,rb)
        readbacks.append(rb)
        if sha(row['original_unmodified_fbx'])!=row['original_unmodified_fbx_sha256']:
            raise RuntimeError('Original FBX changed')
        print('FLORA_IDENTITY_READBACK',row['id'],rb,flush=True)
    save(ROOT/'identity-repair-v007.json',{'readbacks':readbacks,'failures':[r['id'] for r in readbacks if not r['equal']],
        'seconds_total':time.perf_counter()-start})
    if not all(r['equal'] for r in readbacks):
        raise RuntimeError('Identity Mesh FBX still differs: stop, no tolerance changes')
    print('FLORA_IDENTITY_REPAIR_COMPLETE',len(readbacks),flush=True)


if __name__=='__main__':
    main()
