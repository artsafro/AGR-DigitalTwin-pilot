"""new-case: check shared FBX readback against body intent; extract the #1616 band."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from shapely import Point, Polygon


def check(master, readback, design):
    (obj,) = readback['meshes']
    assert readback['readback_ok'] and not readback['other_objects']
    g=obj['face_geometry']; got=np.asarray(g['vertices']); want=np.asarray(master['vertices']); roles=master['roles']
    assert len(g['polygons']) == len(master['faces'])
    rings={key:Polygon(ring) for key,ring in master.get('effective_rings',{
        key:v['ring'] for key,v in design['modules'].items()}).items()}
    ends=[design['floors'][0]['bottom'],design['floors'][-1]['top']]
    transitions=[f['top'] for f,g in zip(design['floors'],design['floors'][1:]) if f['type']!=g['type']]
    free_facade=[]; shoulders=Counter(); sagitta=Counter(); arc_samples=Counter(); uv_error=0.
    reversed_faces=[]; inward=[]; positions=0.; facet=[]; mats=[]; nonmanifold=Counter(); directions=Counter()
    palette=['01_Ventfacade_regular','02_Render_return','03_Ventfacade_band']
    owner={}
    for i,(f,k,role) in enumerate(zip(g['polygons'],master['faces'],roles,strict=True)):
        a,b=got[f],want[k]; parity=min(np.abs(np.roll(a,t,axis=0)-b).max() for t in range(len(a)))
        flip=min(np.abs(np.roll(a[::-1],t,axis=0)-b).max() for t in range(len(a)))
        if flip<parity: reversed_faces.append(i)
        positions=max(positions,min(parity,flip))
        if 'polygon_uv' in master:
            assert obj['uv_channels']==1
            rotation=min(range(len(a)),key=lambda t:np.abs(np.roll(a,t,axis=0)-b).max())
            uv=np.roll(np.asarray(g['polygon_uv'][i]),rotation,axis=0)
            uv_error=max(uv_error,float(np.abs(uv-np.asarray(master['polygon_uv'][i])).max()))
            arc=master['arc_faces'].get(str(i))
            if arc:
                edge=np.roll(a,rotation,axis=0)[:2,:2]
                arc_id=f"{arc['module']}:{arc['center']}"
                sagitta[arc_id]=max(sagitta[arc_id],float(arc['radius']-np.linalg.norm(edge.mean(axis=0)-arc['center'])))
                arc_samples[arc_id]+=1
        assert g['polygon_material'][i]==palette[master['face_zones'][i]]
        n=np.cross(a-a[0], np.roll(a,-1,axis=0)-a[0]).sum(axis=0)
        for u,v in zip(f,f[1:]+f[:1]):
            edge=tuple(sorted((u,v)))
            nonmanifold[edge]+=1; directions[(u,v)]+=1; owner[edge]=i
        if role=='facade':
            c=a.mean(axis=0); n/=np.linalg.norm(n); test=c[:2]+.003*n[:2]
            floor=next(f for f in design['floors'] if f['bottom']<c[2]<f['top'])
            if rings[floor['type']].contains(Point(test)): inward.append(i)
        # Shoulder triangles represent exterior floor transitions, not the typical vertical facade.
        if not role.startswith('shoulder'):
            facet.append(f); mats.append(g['polygon_material'][i])
    assert positions<.0001
    assert '5' not in obj['polygon_degrees'] and max(map(int,obj['polygon_degrees']))<=4
    for edge,n in nonmanifold.items():
        if n!=1: continue
        i=owner[edge]; p=got[list(edge)]; role=roles[i]
        at=lambda z: np.all(np.abs(p[:,2]-z)<.0001)
        if role=='facade' and not any(at(z) for z in ends):
            free_facade.append({'face':i,'edge':p.tolist()})
        if role.startswith('shoulder'):
            shoulders[str(next((z for z in transitions if at(z)), 'unexpected elevation'))]+=1
    report=dict(face_count=len(roles),roles=Counter(roles),maximum_vertex_drift_m=positions,
                inverted_readback=reversed_faces,inward_exterior=inward,
                boundary_edges=sum(v==1 for v in nonmanifold.values()),
                edges_over_two_faces=sum(v>2 for v in nonmanifold.values()),
                seating_winding_conflicts=sum(v==2 and (directions[k]==2 or directions[k[::-1]]==2) for k,v in nonmanifold.items()),
                topology=obj['topology'],bounds_m=obj['bounds_m'],polygon_degrees=obj['polygon_degrees'],
                unexpected_facade_free_edges=free_facade, shoulder_mouth_edges=shoulders,
                uv_channels=obj['uv_channels'], maximum_uv_delta=uv_error,
                arc_chord_sagitta_m=sagitta, arc_face_samples=arc_samples)
    band={'objects':[{'name':obj['name'],'verts':g['vertices'],'faces':facet,'materials':mats}], 'dropped':[]}
    return report,band

if __name__=='__main__':
    inp,fbx,design,report,band=map(Path,sys.argv[1:])
    master,readback,ledger=(json.loads(p.read_bytes()) for p in (inp,fbx,design))
    result,extract=check(master,readback,ledger)
    result['stage1_receipt']={
        'scenario':'oks-vpm','body':'adapters/max/agr_tools/body_core.py:prepare_plan',
        'body_prepare':master.get('body_prepare'), 'input_sha256':master.get('input_sha256'),
        'readback':'tools/blender/fbx_readback.py', 'stage2':master.get('stage2'),
        'fbx_sha256':hashlib.sha256(Path(readback['source']).read_bytes()).hexdigest(),
        'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (inp,fbx)},
    }
    for path,data in ((report,result),(band,extract)):
        with path.open('x',encoding='utf-8') as stream: json.dump(data,stream,indent=2 if path==report else None)
    print(json.dumps(result)); sys.exit(bool(result['inverted_readback'] or result['inward_exterior']
        or result['unexpected_facade_free_edges'] or result['edges_over_two_faces']
        or result['seating_winding_conflicts'] or result['maximum_uv_delta']>1e-5
        or max(result['arc_chord_sagitta_m'].values(),default=0)>.020))
