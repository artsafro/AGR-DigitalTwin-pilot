"""new-case: check shared FBX readback against body intent; extract the #1616 band."""
from collections import Counter
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
    rings={key:Polygon(v['ring']) for key,v in design['modules'].items()}
    reversed_faces=[]; inward=[]; positions=0.; facet=[]; mats=[]; nonmanifold=Counter(); directions=Counter()
    palette=['01_Ventfacade_regular','02_Render_return','03_Ventfacade_band']
    for i,(f,k,role) in enumerate(zip(g['polygons'],master['faces'],roles,strict=True)):
        a,b=got[f],want[k]; parity=min(np.abs(np.roll(a,t,axis=0)-b).max() for t in range(len(a)))
        flip=min(np.abs(np.roll(a[::-1],t,axis=0)-b).max() for t in range(len(a)))
        if flip<parity: reversed_faces.append(i)
        positions=max(positions,min(parity,flip))
        assert g['polygon_material'][i]==palette[master['face_zones'][i]]
        n=np.cross(a-a[0], np.roll(a,-1,axis=0)-a[0]).sum(axis=0)
        for u,v in zip(f,f[1:]+f[:1]):
            nonmanifold[tuple(sorted((u,v)))]+=1; directions[(u,v)]+=1
        if role=='facade':
            c=a.mean(axis=0); n/=np.linalg.norm(n); test=c[:2]+.003*n[:2]
            floor=next(f for f in design['floors'] if f['bottom']<c[2]<f['top'])
            if rings[floor['type']].contains(Point(test)): inward.append(i)
        # Shoulder triangles represent exterior floor transitions, not the typical vertical facade.
        if not role.startswith('shoulder'):
            facet.append(f); mats.append(g['polygon_material'][i])
    assert positions<.0001
    assert '5' not in obj['polygon_degrees'] and max(map(int,obj['polygon_degrees']))<=4
    report=dict(face_count=len(roles),roles=Counter(roles),maximum_vertex_drift_m=positions,
                inverted_readback=reversed_faces,inward_exterior=inward,
                boundary_edges=sum(v==1 for v in nonmanifold.values()),
                edges_over_two_faces=sum(v>2 for v in nonmanifold.values()),
                seating_winding_conflicts=sum(v==2 and (directions[k]==2 or directions[k[::-1]]==2) for k,v in nonmanifold.items()),
                topology=obj['topology'],bounds_m=obj['bounds_m'],polygon_degrees=obj['polygon_degrees'])
    band={'objects':[{'name':obj['name'],'verts':g['vertices'],'faces':facet,'materials':mats}], 'dropped':[]}
    return report,band

if __name__=='__main__':
    inp,fbx,design,report,band=map(Path,sys.argv[1:])
    result,extract=check(*(json.loads(p.read_text(encoding='utf-8')) for p in (inp,fbx,design)))
    for path,data in ((report,result),(band,extract)):
        with path.open('x',encoding='utf-8') as stream: json.dump(data,stream,indent=2 if path==report else None)
    print(json.dumps(result)); sys.exit(bool(result['inverted_readback'] or result['inward_exterior']))
