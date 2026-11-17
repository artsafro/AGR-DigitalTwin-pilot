"""new-case: unfold measured tower B rings, cut source openings and add reveals."""
import json
from itertools import product
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np
from shapely import Polygon, constrained_delaunay_triangles, get_parts


def build(design):
    verts, faces, roles, groups, indices = [], [], [], [], {}
    buckets = defaultdict(list)
    seen = set()

    def bucket(p):
        return tuple(int(np.floor(x/.00201)) for x in p)

    def face(points, zone, role):
        keys = [tuple(round(float(x), 5) for x in p) for p in points]
        ids=[]
        for key in keys:
            if key in indices:
                ids.append(indices[key]); continue
            cell=bucket(key)
            match=next((i for d in product((-1,0,1),repeat=3)
                        for i in buckets.get(tuple(a+b for a,b in zip(cell,d)),())
                        if sum((x-y)**2 for x,y in zip(key,verts[i])) <= .00201**2),None)
            if match is None:
                match=len(verts); verts.append(key); buckets[cell].append(match)
            indices[key]=match; ids.append(match)
        ident=tuple(sorted(ids))
        if len(set(ids)) != len(ids) or ident in seen:
            if role.startswith('shoulder'): return
            raise ValueError(f'Repeated or collapsed {role}: {keys}')
        seen.add(ident); faces.append(ids); groups.append(zone); roles.append(role)

    def layout(m):
        a = np.array(m['ring']); b = np.roll(a, -1, axis=0)
        length = np.linalg.norm(b-a, axis=1); t = (b-a)/length[:,None]
        n = np.c_[-t[:,1],t[:,0]]; prev = np.roll(n,1,axis=0)
        mit = (n+prev)/(1+np.sum(n*prev,axis=1))[:,None]
        return a,b,length,n,mit,np.r_[0.,np.cumsum(length)]

    layouts = {key: layout(m) for key,m in design['modules'].items()}
    profiles = {key: Polygon(m['ring']) for key,m in design['modules'].items()}
    boundaries = {key: [] for key in layouts}
    for part in get_parts(profiles['A'].boundary.intersection(profiles['B'].boundary)):
        if hasattr(part,'coords'):
            for xy in part.coords:
                for key,(a,b,L,n,mit,S) in layouts.items():
                    t=(b-a)/L[:,None]; d=np.array(xy)-a; u=np.sum(d*t,axis=1); clip=np.clip(u,0,L)
                    j=np.argmin(np.linalg.norm(d-t*clip[:,None],axis=1)); boundaries[key].append(S[j]+clip[j])
    floor_map={key: [f for f in design['floors'] if f['type']==key] for key in layouts}
    grids={}
    for key,(a,b,L,n,mit,S) in layouts.items():
        fixed=list(S); total=S[-1]; moving=[]
        for s in boundaries[key]:
            if min(abs(s-q) for q in fixed)>.006:
                fixed.append(s)
        for floor in floor_map[key]:
            for op in floor['openings']:
                moving += [op['s0']%total,op['s1']%total]
        # Revit float noise is not a finish seam. Keep structural/arc stations fixed.
        clean=[]
        for s in sorted(fixed):
            if not clean or s-clean[-1]>1e-4: clean.append(s)
        for s in sorted(moving):
            if min(abs(s-q) for q in clean)>.018: clean.append(s)
        clean.sort(); grids[key]=clean
        for floor in floor_map[key]:
            for op in floor['openings']:
                for field in ('s0','s1'):
                    s=op[field]; period=int(s//total); s=s%total
                    op[field]=min(clean,key=lambda q:abs(q-s))+period*total

    def point(key,s,z,d=0.):
        a,b,L,n,mit,S=layouts[key]
        j=min(len(L)-1,max(0,int(np.searchsorted(S,s,side='right')-1)))
        u=(s-S[j])/L[j]
        if u<1e-6: offset=mit[j]
        elif u>1.-1e-6: offset=mit[(j+1)%len(L)]
        else: offset=n[j]
        xy=a[j]*(1-u)+b[j]*u+d*offset
        return (*xy,z)

    def material(key,s):
        return design['modules'][key]['zone'][int(np.searchsorted(layouts[key][-1],s,side='right')-1)]

    floors=design['floors']; blocks=[]
    for f in floors:
        if not blocks or f['type']!=blocks[-1][-1]['type']: blocks.append([])
        blocks[-1].append(f)
    for block in blocks:
        key=block[0]['type']; ss=grids[key]; period=ss[-1]; count=len(ss)-1
        ops=[o for f in block for o in f['openings']]
        low=block[0]['bottom']; high=block[-1]['top']
        zz=sorted({low,high}|{z for o in ops for z in [o['z0'],o['z1']] if low<z<high})
        cells=[]
        for z0,z1 in zip(zz,zz[1:]):
            z=(z0+z1)/2; active=[o for o in ops if o['z0']<z<o['z1']]; row=[]
            for s0,s1 in zip(ss,ss[1:]):
                s=(s0+s1)/2
                opening=[o for o in active if o['s0']<s<o['s1'] or o['s0']<s+period<o['s1']]
                row.append(max((o['depth'] for o in opening),default=0.))
                if not opening:
                    face([point(key,s0,z0),point(key,s1,z0),point(key,s1,z1),point(key,s0,z1)],material(key,s),'facade')
            cells.append(row)
        for j,(z0,z1) in enumerate(zip(zz,zz[1:])):
            for i,(s0,s1) in enumerate(zip(ss,ss[1:])):
                d=cells[j][i]; prev=cells[j][i-1]; zone=material(key,(s0+s1)/2)
                # Between adjacent windows leave a continuous void; no artificial inward partition.
                if bool(d)!=bool(prev):
                    depth=max(d,prev); q=[point(key,s0,z0),point(key,s0,z0,depth),point(key,s0,z1,depth),point(key,s0,z1)]
                    face(q if d else q[::-1],zone,'jamb')
                if d:
                    if j>0 and not cells[j-1][i]:
                        face([point(key,s0,z0),point(key,s1,z0),point(key,s1,z0,d),point(key,s0,z0,d)],zone,'sill')
                    if j+1<len(cells) and not cells[j+1][i]:
                        face([point(key,s1,z1),point(key,s0,z1),point(key,s0,z1,d),point(key,s1,z1,d)],zone,'head')

    expanded={key:Polygon([point(key,s,0)[:2] for s in ss[:-1]]) for key,ss in grids.items()}
    for below,above in zip(blocks,blocks[1:]):
        lo,hi=below[-1]['type'],above[0]['type']; z=below[-1]['top']
        for a,b,direction in ((lo,hi,1),(hi,lo,-1)):
            difference=expanded[a].difference(expanded[b]);
            for part in get_parts(difference):
                if part.area<1e-5: continue
                for tri in get_parts(constrained_delaunay_triangles(part)):
                    if tri.area<1e-9: continue
                    q=np.asarray(tri.exterior.coords)[:-1]; normal=np.linalg.det(q[1:]-q[0]);
                    if len({tuple(np.round(xy,5)) for xy in q}) < 3:
                        continue  # coincident precision nodes from overlapping contour boundaries
                    face([(*xy,z) for xy in (q if normal*direction>0 else q[::-1])],2,'shoulder_up' if direction>0 else 'shoulder_down')
    used=sorted({i for f in faces for i in f}); reindex={i:j for j,i in enumerate(used)}
    return dict(vertices=[verts[i] for i in used], faces=[[reindex[i] for i in f] for f in faces], face_zones=groups, roles=roles)


if __name__ == '__main__':
    source,out=map(Path,sys.argv[1:]); model=build(json.loads(source.read_text(encoding='utf-8')))
    with out.open('x',encoding='utf-8') as stream:
        json.dump(model,stream,separators=(',',':'))
    print(len(model['vertices']),len(model['faces']))
