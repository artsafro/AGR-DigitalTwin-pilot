"""new-case: AC06 source-bound export audit, supplementing unchanged AC08 QA.

AC08 QA assumes no glass, equal polygon counts across UCX triangulation and
one finish per ID. Keep that raw report; independently certify its inapplicable
checks against this building's source polygons and presentation region rules.
Source coverage uses original corners, directed boundary cancellation and
positive projected triangle area, not a coplanarity rejection of warped quads.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import numpy as np


def source_coverage(source, output, shift):
    """Return source polygon per triangle; refuse omissions, duplicates or new corners."""
    sv=np.asarray(source['vertices'],float)
    ov=np.asarray(output['vertices'],float)+np.asarray(shift,float)
    if not source['faces'] or not output['faces'] or not np.isfinite(sv).all() or not np.isfinite(ov).all():
        raise ValueError('empty/non-finite source or output')
    index=[]
    for p in ov:
        hits=np.flatnonzero(np.max(np.abs(sv-p),axis=1)<2e-5)
        if len(hits)!=1:
            raise ValueError(f'new or ambiguous source corner {p.tolist()}')
        index.append(int(hits[0]))
    if set(index)!=set(range(len(sv))):
        raise ValueError('missing source vertices')
    incidence=defaultdict(set)
    for i,f in enumerate(source['faces']):
        for k in f:
            incidence[k].add(i)
    groups=defaultdict(list); owners=[]
    for f in output['faces']:
        if len(f)!=3 or len(set(f))!=3:
            raise ValueError('non-triangle/degenerate output')
        tri=[index[k] for k in f]
        hits=set.intersection(*(incidence[k] for k in tri))
        if len(hits)!=1:
            raise ValueError(f'non-source or ambiguous triangle {tri}')
        owner=hits.pop(); owners.append(owner); groups[owner].append(tri)
    for i,poly in enumerate(source['faces']):
        tris=groups[i]
        if len(tris)!=len(poly)-2:
            raise ValueError(f'polygon {i} triangle count mismatch')
        boundary=Counter((poly[k],poly[(k+1)%len(poly)]) for k in range(len(poly)))
        edges=Counter((f[k],f[(k+1)%3]) for f in tris for k in range(3))
        for a,b in list(edges):
            if (a,b)<(b,a):
                cancel=min(edges[a,b],edges[b,a]); edges[a,b]-=cancel; edges[b,a]-=cancel
        if +edges!=boundary:
            raise ValueError(f'polygon {i} boundary/winding mismatch')
        p=sv[poly]; normal=np.sum(np.cross(p,np.roll(p,-1,axis=0)),axis=0)
        axis=int(np.argmax(np.abs(normal))); keep=[k for k in range(3) if k!=axis]
        def signed(q):
            return sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(q,np.roll(q,-1,axis=0)))/2
        area=signed(p[:,keep]); areas=[signed(sv[f][:,keep]) for f in tris]
        if not area or any(a*area<=0 for a in areas) or abs(sum(areas)-area)>1e-8:
            raise ValueError(f'polygon {i} overlapping/outside triangulation')
    return owners


def snapshot(paths):
    result = {}
    for path in paths:
        p = Path(path).resolve()
        if any(p.samefile(old) for old in result):
            raise ValueError(f'duplicate input {p}')
        result[p] = p.read_bytes()
    return result


def verify_snapshot(inputs):
    for path, raw in inputs.items():
        if not path.is_file() or path.read_bytes() != raw:
            raise ValueError(f'input changed during audit: {path}')


def main(root, out):
    root=Path(root).resolve(); out=Path(out).resolve()
    job=Path(__file__).resolve().parent
    scripts=job.parent/'scripts'; sys.path.insert(0,str(scripts)); sys.path.insert(0,str(job))
    import build_ac06
    protected=[job,root]
    if out.exists() or any(out==p or p in out.parents for p in protected):
        raise ValueError('audit output must be a new path outside inputs/build root')
    import hashlib
    spec_path, dump_path = job/'vpm_textures.json', job/'max-dump-006.json'
    inputs = snapshot([spec_path, dump_path, root/'qa_packages.json', root/'readback/vpm.json', root/'readback/npm.json', root/'textures-npm/npm_atlas.json', root/'package-vpm/SM_Prg_1.zip', root/'package-npm/0000_Prg_1.zip'])
    def load(path):
        return json.loads(inputs[Path(path).resolve()])
    spec=load(spec_path)
    dump=load(dump_path)
    # Refuse output alias to any source or transitive receipt, including absent targets.
    source,glass,hulls=build_ac06.partition(dump,spec)
    sv=np.asarray(source['vertices']); shift=[(sv[:,0].min()+sv[:,0].max())/2,(sv[:,1].min()+sv[:,1].max())/2,0]
    atlas=load(root/'textures-npm/npm_atlas.json')['finishes']
    raw=load(root/'qa_packages.json')
    checks={}; facts={}
    def check(name,ok,detail):
        checks[name]={'ok':bool(ok),'detail':detail}
    raw_replaced={'names_vpm','names_npm','source_finish_vpm','source_finish_npm','vpm_texel_contract'}|{n for n in raw['checks'] if n.startswith('geometry_unchanged_UCX_')}
    for name,item in raw['checks'].items():
        if name not in raw_replaced:
            checks['ac08.'+name]=item
    expected=build_ac06.region_finishes(source['vertices'],source['faces'],source['mat_ids'],spec)
    for tag in ('vpm','npm'):
        objects=load(root/f'readback/{tag}.json')['objects']
        suffix='_001' if tag=='npm' else ''
        prefix=f'SM_{spec["address"]}{suffix}'
        byname={o['name']:o for o in objects}
        wanted={prefix+'_Main',prefix+'_MainGlass'}
        if tag=='vpm': wanted|={f'UCX_SM_{spec["address"]}_Main_{i:03d}' for i in range(1,22)}
        check(tag+'.names',set(byname)==wanted,sorted(byname))
        for label,src in [('Main',source),('MainGlass',glass)]:
            o=byname[prefix+'_'+label]
            try:
                owners=source_coverage(src,o,shift)
                check(tag+'.coverage.'+label,True,{'triangles':len(owners),'source_polygons':len(src['faces']),'source_vertices':len(src['vertices'])})
            except ValueError as e:
                check(tag+'.coverage.'+label,False,str(e)); continue
            if label=='MainGlass':
                check(tag+'.map_free_glass',all(not m['images'] for m in o['materials']),o['materials'])
                continue
            got=[]
            for uv in o['face_uvs']:
                c=np.asarray(uv).mean(0)
                if tag=='vpm':
                    tile=1001+int(np.floor(c[0]))+10*int(np.floor(c[1]))
                    hits=[name for name,t in spec['finishes'].items() if t['udim']==tile]
                else:
                    hits=[name for name,r in atlas.items() if r['u0']<=c[0]<=r['u0']+r['size'] and r['v0']<=c[1]<=r['v0']+r['size']]
                got.append(hits[0] if len(hits)==1 else None)
            wrong=[i for i,owner in enumerate(owners) if got[i]!=expected[owner]]
            check(tag+'.presentation_finish_all_triangles',not wrong,{'triangles':len(owners),'wrong':len(wrong),'examples':wrong[:10]})
            if tag=='vpm':
                density=[]
                for i,owner in enumerate(owners):
                    if not expected[owner].startswith('Sandwich_'):continue
                    v=np.asarray(o['vertices'])[o['faces'][i]]; u=np.asarray(o['face_uvs'][i])
                    area=np.linalg.norm(np.cross(v[1]-v[0],v[2]-v[0]))/2
                    e1,e2=u[1]-u[0],u[2]-u[0]; ua=abs(e1[0]*e2[1]-e1[1]*e2[0])/2
                    density.append(float(np.sqrt(ua*4096**2/area)) if area>0 else float('nan'))
                check('vpm.density',bool(density) and all(np.isfinite(d) and abs(d-1000)<=10 for d in density),{'measured_triangles':len(density),'min':min(density),'max':max(density),'target':1000})
        if tag=='vpm':
            for i,src in enumerate(sorted(hulls,key=lambda h:h['name']),start=1):
                o=byname[f'UCX_SM_{spec["address"]}_Main_{i:03d}']
                try:
                    owners=source_coverage(src,o,shift)
                    check('ucx.coverage.'+str(i),True,{'triangles':len(owners),'source_handle':src['handle']})
                except ValueError as e:
                    check('ucx.coverage.'+str(i),False,str(e))
    result={'checks':checks,'failed':[n for n,c in checks.items() if not c['ok']],
            'raw_ac08_report':str(root/'qa_packages.json'),'raw_replaced_with_building_specific_probes':sorted(raw_replaced),
            'user_acceptance':'pending','final_sintez':'pending user visual approval','delivery_passed':False}
    verify_snapshot(inputs)
    result['input_sha256'] = {str(p):hashlib.sha256(raw).hexdigest() for p,raw in inputs.items()}
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
    print('AC06-AUDIT',len(checks)-len(result['failed']),'/',len(checks),'failed',result['failed'])
    return int(bool(result['failed']))


if __name__=='__main__':
    sys.exit(main(*sys.argv[1:]))
