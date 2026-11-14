"""new-case: independently account R1 triangles and inverse-atlas UV on fresh FBX readback."""
from collections import Counter
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector, kdtree


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    return {o.name: {'v':[o.matrix_world @ v.co for v in o.data.vertices],
        'f':[list(p.vertices) for p in o.data.polygons],
        'uv':[[o.data.uv_layers[0].data[i].uv.copy() for i in p.loop_indices] for p in o.data.polygons] if o.data.uv_layers else []}
        for o in bpy.context.scene.objects if o.type == 'MESH'}


def main(packet, run):
    source = load(packet/'source/SM_Kpp_1.fbx')
    exported = load(run/'export/fbx/0000_Kpp_1_01.fbx')
    regions = json.loads((run/'atlas/npm_atlas.json').read_text())['finishes']
    by_udim = {r['udim']:r for r in regions.values()}
    visible=[v for name,o in source.items() if not name.startswith('UCX_') for v in o['v']]
    centre=Vector([(min(v[i] for v in visible)+max(v[i] for v in visible))/2 for i in (0,1)]+[0])
    results={}
    for old,new in [('SM_Kpp_1_Main','SM_Kpp_1_001_Main'),('SM_Kpp_1_MainGlass','SM_Kpp_1_001_MainGlass')]:
        a,b=source[old],exported[new]
        tree=kdtree.KDTree(len(b['v']))
        for i,v in enumerate(b['v']): tree.insert(v,i)
        tree.balance()
        mapping={}
        distances=[]
        for i,v in enumerate(a['v']):
            _,j,d=tree.find(v-centre)
            mapping[i]=j
            distances.append(d)
        expected=Counter(tuple(sorted(mapping[i] for i in face)) for face in a['f'])
        actual=Counter(tuple(sorted(face)) for face in b['f'])
        assert expected == actual, f'triangle disposition differs: {old}'
        assert max(distances) < 1e-5, f'non-profile geometry change: {old}'
        # Match each triangle by mapped vertex identities, then compare the affine UV map.
        keyed={tuple(sorted(face)):(face,uv) for face,uv in zip(b['f'],b['uv'])}
        uv_error=0.0
        for face,uvs in zip(a['f'],a['uv']):
            target,tuv=keyed[tuple(sorted(mapping[i] for i in face))]
            if old.endswith('_Main'):
                cx,cy=sum(v.x for v in uvs)/3,sum(v.y for v in uvs)/3
                tx,ty=int(cx//1),int(cy//1)
                r=by_udim[1001+tx+10*ty]
            for vertex,uv in zip(face,uvs):
                expected_uv=(uv-Vector((tx,ty)))*r['size']+Vector((r['u0'],r['v0'])) if old.endswith('_Main') else uv
                got=tuv[target.index(mapping[vertex])]
                uv_error=max(uv_error,(got-expected_uv).length)
        assert uv_error < 1e-5
        results[old]={'input_triangles':len(a['f']),'output_triangles':len(b['f']),
            'triangle_multiset_equal':True,'max_position_error_m':max(distances),'max_uv_error':uv_error}
    assert set(exported)=={'SM_Kpp_1_001_Main','SM_Kpp_1_001_MainGlass'}
    report={'source':str(packet),'output':str(run),'triangles':results,
        'removed':{n:'UCX excluded from NPM (DER-15)' for n in source if n.startswith('UCX_')},
        'profile_translation_m':list(-centre),'delivery_complete':False}
    with (run/'accounting.json').open('x') as f: json.dump(report,f,indent=2)
    print('ACCOUNTED',json.dumps(report))


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    main(Path(args[0]),Path(args[1]))
