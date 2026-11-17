"""new-case: unfold measured tower B rings, cut source openings and add reveals."""
import json
import math
from copy import deepcopy
import hashlib
from itertools import product
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np
from shapely import Polygon, constrained_delaunay_triangles, get_parts


def resample_arc(points, step):
    """Fit a circle through both retained tangencies; snap developed UV, not the envelope."""
    start, end = points[[0,-1]]
    mid = (start+end)/2
    tangent = (end-start)/np.linalg.norm(end-start)
    normal = np.array([-tangent[1], tangent[0]])
    q = points-mid
    x = q@normal
    y = (np.sum(q*q, axis=1)-np.sum((end-mid)**2))/2
    center = mid+(x@y)/(x@x)*normal
    radius = float(np.linalg.norm(start-center))
    assert np.max(np.abs(np.linalg.norm(points-center, axis=1)-radius)) < .002
    angle = np.unwrap(np.arctan2(*(points-center).T[::-1]))
    sweep = float(angle[-1]-angle[0])
    steps = max(1, round(radius*abs(sweep)/step))
    # Include every texture division plus any subdivisions required for sagitta.
    count = max(steps, math.ceil(abs(sweep)/(2*math.acos(1-.020/radius))))
    breaks = np.linspace(0,1,steps*math.ceil(count/steps)+1)
    phi = angle[0]+sweep*np.asarray(breaks)
    xy = center+radius*np.c_[np.cos(phi), np.sin(phi)]
    xy[[0,-1]] = points[[0,-1]]
    return dict(center=center.tolist(), radius=radius, steps=steps, sweep=sweep), xy


def build(design, config=None):
    design = deepcopy(design)
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

    modules = design['modules']
    original = {key: layout(m)[-1] for key,m in modules.items()}
    arc_segments = {}
    step = config['texture_step_m'] if config else None
    if step is not None:
        for key, spans in config['arc_spans'].items():
            module = modules[key]
            ring = np.asarray(module['ring']); n = len(ring)
            starts = {start: end for start,end in spans}
            i = min(starts); stop = i+n
            points, zones = [], []
            while i < stop:
                j = i%n

                if j not in starts:
                    points.append(ring[j].tolist()); zones.append(module['zone'][j]); i += 1
                    continue
                end = i + (starts[j]-j)%n
                ids = np.arange(i,end+1)%n
                ids_zone = {module['zone'][k] for k in ids[:-1]}
                assert len(ids_zone)==1
                arc, xy = resample_arc(ring[ids], step)
                offset = len(points)
                for k,pt in enumerate(xy[:-1]):
                    points.append(pt.tolist()); zones.append(module['zone'][j])
                    arc_segments[key,offset+k] = (arc,k,len(xy)-1)
                i = end
            # The old origin lies within a wraparound arc; rebase through the
            # first retained tangency and project the old opening endpoints.
            old_ring = ring.copy()
            module.update(ring=points, zone=zones)
            new = layout(module)
            for floor in design['floors']:
                if floor['type'] != key: continue
                for op in floor['openings']:
                    mapped = []
                    for field in ('s0','s1'):
                        s = op[field] % original[key][-1]
                        index = min(n-1,np.searchsorted(original[key],s,side='right')-1)
                        fraction = (s-original[key][index])/(original[key][index+1]-original[key][index])
                        xy = old_ring[index]+fraction*(old_ring[(index+1)%n]-old_ring[index])
                        a,b,L,_,_,S = new
                        t = (b-a)/L[:,None]; u = np.clip(np.sum((xy-a)*t, axis=1),0,L)
                        k = np.argmin(np.linalg.norm(xy-a-u[:,None]*t,axis=1))
                        mapped.append(float(S[k]+u[k]))
                    op['s0'],op['s1'] = mapped[0], mapped[1] + (new[-1][-1] if mapped[1]<mapped[0] else 0)
    # Coalesce endpoints of nearly coincident section traces before computing the
    # Boolean. Welding only after tessellation leaves wedges and T-junctions.
    before_snap = layout(modules['B'])[-1]
    a = np.asarray(modules['A']['ring'])
    b = np.asarray(modules['B']['ring'], dtype=float)
    for i, xy in enumerate(b):
        nearest = a[np.argmin(np.linalg.norm(a-xy, axis=1))]
        if np.linalg.norm(nearest-xy) <= .006:
            b[i] = nearest
    modules['B']['ring'] = b.tolist()
    layouts = {key: layout(m) for key,m in modules.items()}
    updated = layouts['B'][-1]
    for floor in design['floors']:
        if floor['type'] == 'B':
            for op in floor['openings']:
                for field in ('s0', 's1'):
                    turn, s = divmod(op[field], before_snap[-1])
                    op[field] = float(turn*updated[-1] + np.interp(s, before_snap, updated))
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

    # Share every station along geometrically coincident contour edges, including
    # opening-grid cuts that only occur on one of the two profiles.
    for src, dst in (('A', 'B'), ('B', 'A')):
        a, b, L, _, _, S = layouts[dst]
        t = (b-a)/L[:,None]
        sa, sb, _, _, _, SS = layouts[src]
        for s in list(grids[src]):
            j = min(len(sa)-1, np.searchsorted(SS,s,side='right')-1)
            xy = sa[j] + (sb[j]-sa[j]) * ((s-SS[j])/(SS[j+1]-SS[j]))
            u = np.clip(np.sum((xy-a)*t, axis=1), 0, L)
            for i in np.flatnonzero(np.linalg.norm(xy-a-u[:,None]*t, axis=1) < 1e-8):
                q = S[i]+u[i]
                if min(abs(q-existing) for existing in grids[dst]) > .00201:
                    grids[dst].append(q)
        grids[dst].sort()

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
    uvs, arc_faces = {}, {}
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
                    if step is not None:
                        idx = len(faces)-1
                        j = np.searchsorted(layouts[key][-1],s)-1
                        base = next(f['bottom'] for f in block if f['bottom'] <= z < f['top'])
                        u0,u1 = s0/step,s1/step
                        if (key,j) in arc_segments:
                            arc,k,count = arc_segments[key,j]
                            S=layouts[key][-1]
                            u0,u1 = [(k+(p-S[j])/(S[j+1]-S[j]))*arc['steps']/count for p in (s0,s1)]
                            arc_faces[idx] = {**arc, 'module': key, 'segment': k,
                                              'segment_count': count, 'u': [u0,u1]}
                        # Local repeating UV chart; zone IDs are separate slots.
                        u0,u1 = u0-math.floor(u0+1e-8),u1-math.floor(u0+1e-8)
                        v0,v1 = (z0-base)/step,(z1-base)/step
                        uvs[idx]=[(u0,v0),(u1,v0),(u1,v1),(u0,v1)]
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
    model = dict(vertices=[verts[i] for i in used], faces=[[reindex[i] for i in f] for f in faces], face_zones=groups, roles=roles)
    if step is not None:
        for i,f in enumerate(faces):
            if i in uvs: continue
            p = np.asarray([verts[j] for j in f]); d = p-p[0]; u = d[1]/np.linalg.norm(d[1])
            normal = np.cross(d[1],d[-1]); normal /= np.linalg.norm(normal)
            uvs[i] = (np.c_[d@u,d@np.cross(normal,u)]/step).tolist()
        model.update(polygon_uv=[uvs[i] for i in range(len(faces))], arc_faces=arc_faces,
                     effective_rings={k:m['ring'] for k,m in modules.items()})
    return model


if __name__ == '__main__':
    from adapters.max.agr_tools.body_core import prepare_plan

    source,out=map(Path,sys.argv[1:]); job=Path(__file__).resolve().parents[1]
    manifest=json.loads((job/'sources.json').read_bytes())
    config=manifest['training']
    gate=manifest['gate1']
    inputs={source:manifest['design_sha256'], Path(manifest['fbx']['path']):manifest['fbx']['sha256']}
    inputs.update({Path(gate['directory'])/name: digest for name,digest in gate.items() if name!='directory'})
    for path, expected in inputs.items():
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
                raise ValueError(f'Frozen input mismatch: {path}')
    design=json.loads(source.read_bytes())
    floors=design['floors']
    levels=[floors[0]['bottom']]+[f['top'] for f in floors]
    plan=prepare_plan([dict(handle=1,name='63B shell',kind='geometry',material='Stage1')],
                      opts={'levels':[dict(name=f'B{i:02d}',z_m=z) for i,z in enumerate(levels)]})
    if plan['ambiguous'] or plan['findings'] or len(plan['levels'])!=len(levels):
        raise ValueError(f'body.prepare refused: {plan}')
    prepared=[p['z_m'] for p in plan['levels']]
    for f,lo,hi in zip(floors,prepared[:-1],prepared[1:],strict=True):
        if (f['bottom'],f['top'])!=(lo,hi): raise ValueError('Non-contiguous frozen floor schedule')
        f.update(bottom=lo,top=hi)
    model=build(design,config)
    model.update(body_name=plan['renames'][0][2],body_role=dict(plan['roles'])[1],
                 body_prepare=plan,input_sha256={str(p):v for p,v in inputs.items()},
                 stage2='not_run')
    with out.open('x',encoding='utf-8') as stream:
        json.dump(model,stream,separators=(',',':'))
    print(len(model['vertices']),len(model['faces']))
