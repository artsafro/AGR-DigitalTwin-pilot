"""Reproduce Vatutino v014 -> v015 construction without source writes.

Pattern: n/a | new-case: source-bound paired Ground profiles with D150/D169 retention (#371).
Geometry output only: native export/readback, UCX and review publication remain separate.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import numpy as np
import shapely
from shapely.geometry import Polygon, MultiPoint, shape
from shapely.ops import unary_union
from dt_ai.geometry import ground_cake as gc, ground_details as gd
from dt_ai.geometry.ground_quads import pair_triangles, detail_polygon_uv
from dt_ai.ops.inv_quads import PolyMesh, part_report as quad_report
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ground_v014_builder', ROOT/'build_ground.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


def git_head():
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parents[1],text=True).strip()


def assert_unchanged(payload, initial_head):
    if any(p.read_bytes()!=v for p,v in payload.items()):
        raise ValueError('inputs changed during build; no output written')
    if git_head()!=initial_head:
        raise ValueError('HEAD changed during build; no output written')


def load_json(data):
    def pairs(rows):
        d = {}
        for k,v in rows:
            if k in d: raise ValueError(f'duplicate JSON key {k!r}')
            d[k] = v
        return d
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'nonfinite JSON {value}')))


def subset(m, mask):
    f=m.faces[mask];used=np.unique(f);remap=np.full(len(m.verts),-1);remap[used]=np.arange(len(used))
    return gc.Mesh(m.verts[used].copy(),remap[f],np.asarray(m.slot)[mask].tolist(),
                   m.level[mask].copy(),m.uv[mask].copy(),m.cell)


def clip_curtain(curtain, stairs):
    """Retain every curtain fragment or an explicit stair-wall replacement disposition."""
    vertices=[];faces=[];slots=[];levels=[];source=[];lookup={};dropped=[]
    def append(points,slot,level,source_id):
        ids=[]
        for p in points:
            key=tuple(np.round(p,9))
            if key not in lookup:lookup[key]=len(vertices);vertices.append(p)
            ids.append(lookup[key])
        if len(set(ids))<3:raise ValueError(f'collapsed curtain fragment from source face {source_id}')
        faces.append(ids);slots.append(slot);levels.append(level);source.append(source_id)
    def slab(points,normal,origin):
        points=list(points)
        for sign in (1,-1):
            result=[]
            for a,b in zip(points,points[1:]+points[:1]):
                da=sign*np.dot(a-origin,normal)-.0051;db=sign*np.dot(b-origin,normal)-.0051
                if da<=0:result.append(a)
                if (da<0<db) or (db<0<da):result.append(a+(b-a)*(da/(da-db)))
            points=result
            if not points:break
        return np.asarray(points)
    for i,(face,slot,level) in enumerate(zip(curtain.faces,curtain.slot,curtain.level)):
        points=curtain.verts[face]
        if slot!='Skirt':append(points,slot,int(level),i);continue
        origin=points[0]
        horizontal=next((p-origin for p in points[1:] if np.linalg.norm((p-origin)[:2])>1e-8),None)
        if horizontal is None:raise ValueError(f'invalid curtain source face {i}')
        ex=np.array([*horizontal[:2],0.]);ex/=np.linalg.norm(ex);ey=np.array([0.,0.,1.]);normal=np.cross(ex,ey)
        poly=Polygon(np.column_stack(((points-origin)@ex,(points-origin)@ey)))
        nearby=[]
        for tri in stairs:
            dist=(tri-origin)@normal
            if np.all(dist>.0051) or np.all(dist<-.0051):continue
            clipped=slab(tri,normal,origin)
            if len(clipped)>=2:
                coords=np.column_stack(((clipped-origin)@ex,(clipped-origin)@ey))
                nearby.append(MultiPoint(coords).convex_hull.buffer(.0051))
        cut=poly.difference(unary_union(nearby)) if nearby else poly
        if cut.equals(poly):append(points,slot,int(level),i);continue
        emitted=0
        for part in gc._polys(cut):
            for tri in gc._tri_piece(part):
                q=np.asarray(tri);p=origin+q[:,0,None]*ex+q[:,1,None]*ey
                if np.dot(np.cross(p[1]-p[0],p[2]-p[0]),np.cross(points[1]-points[0],points[2]-points[0]))<0:p=p[::-1]
                append(p,slot,int(level),i);emitted+=1
        if not emitted:dropped.append({'source_face':i,'reason':'curtain replaced at stair wall; perimeter-depth readback required'})
    m=gc.Mesh(np.asarray(vertices),np.asarray(faces),slots,np.asarray(levels),np.zeros((len(faces),3,2)),curtain.cell)
    return m,{'output_source_faces':source,'dropped':dropped}


def geometry(data, raw, approval, void_data):
    m=gc.Mesh(np.asarray(raw['verts']),np.asarray(raw['faces']),[raw['slots'][i] for i in raw['mat']],
              np.asarray(raw['level']),np.asarray(raw['uv']),4.)
    surface=gc.weld_base_boundary(subset(m,m.level>=0))
    surface=gc.close_base_notch(surface,approval['triangle_xy'],approval_reference=approval['decision_reference'])
    surface.uv=surface.verts[surface.faces,:2]/4
    b=np.asarray(approval['triangle_xy'][1]);ids=np.flatnonzero(np.linalg.norm(surface.verts[:,:2]-b,axis=1)<1e-8)
    if len(ids)!=1:raise ValueError('approved notch tip must identify one interior sample')
    surface=gc.dissolve_base_vertex(surface,int(ids[0]))
    void=shape(void_data['geometry'])
    if void.intersection(Polygon(approval['triangle_xy'])).area:raise ValueError('source remainder removes approved patch')
    surface=gc.cut_base_void(surface,void)
    source_void=surface.report['base_void'];surface=subset(surface,surface.level>=0)
    sampler=gc.ReliefSampler(gc.build_tin([(e['x'],e['y'],e['z']) for e in data['elevations']]))
    plan=gc.plan_layers(shape(data['boundary']),{t:list(getattr(shape(c['geometry']),'geoms',[])) for t,c in data['coverings'].items()},data['base_covering'],legacy.SLOTS,footprint_min_area=1000.,step=.006)
    detail,dispositions,joints=gd.build_details(data.get('ground_elements',[]),plan.surface,sampler,stair_clearance_m=.012)
    foot=unary_union([shape(r['footprint']) for r in dispositions if r.get('footprint')])
    patch=Polygon(approval['triangle_xy'])
    plan.surface=gc.MultiPolygon(gc._polys(plan.surface.union(patch).difference(foot)))
    for layer in plan.layers:layer.geom=gc.MultiPolygon(gc._polys((layer.geom.union(patch) if layer.level==0 else layer.geom).difference(foot)))
    corners=np.asarray(void.exterior.coords)
    bound=0.
    for a,b in zip(corners,corners[1:]):
        distances=shapely.distance(shapely.points(np.linspace(a,b,10001)),plan.surface.boundary)
        bound=max(bound,float(distances.max()+np.linalg.norm(b-a)/20000))
    if bound>.0022:raise ValueError(f'source void contour certificate exceeds 2.2 mm: {bound}')
    tin=sampler.tin
    reference=gc.Mesh(tin.pts,tin.tris,['TileLight']*len(tin.tris),np.zeros(len(tin.tris),int),np.zeros((len(tin.tris),3,2)),4.)
    curbs=np.isin(detail.slot,['CurbGarden','CurbDrive'])
    fitted=gd.fit_curb_bottom(subset(detail,curbs),gd.combine([surface,reference]))
    detail=gd.combine([subset(detail,~curbs),fitted])
    curtain,clipping=clip_curtain(gc.add_skirt(surface),detail.verts[detail.faces[np.asarray(detail.slot)=='Stairs']])
    m=gd.combine([curtain,detail])
    for i,p in enumerate(m.verts[m.faces]):
        axes=[j for j in range(3) if j!=abs(np.cross(p[1]-p[0],p[2]-p[0])).argmax()]
        m.uv[i]=p[:,axes]/4
    m=gc.clean_topology(m)
    return m,plan,sampler,{'void_contour_upper_bound_m':bound,'source_void':source_void,
        'curtain':clipping,'details':dispositions,'joints':joints,'curb_support':fitted.report}


def match_reference_faces(m, reference, face_ids):
    """Unique world-coordinate correspondence, without lossy pre-rounding."""
    candidates=np.flatnonzero(m.level>=0)
    xyz=m.verts[m.faces[candidates]];centres=xyz.mean(axis=1)
    mapping={}
    for face_id in face_ids:
        target=reference['verts'][reference['faces'][face_id]]
        nearby=np.flatnonzero(np.linalg.norm(centres-target.mean(axis=0),axis=1)<2e-6)
        found=[]
        for k in nearby:
            distances=np.linalg.norm(xyz[k,:,None,:]-target[None,:,:],axis=2)
            nearest=distances.argmin(axis=1)
            if len(set(nearest.tolist()))==3 and np.max(distances[np.arange(3),nearest])<2e-6:
                found.append(int(candidates[k]))
        if len(found)!=1:
            raise ValueError(f"D150 face {face_id}: {'unmapped' if not found else 'ambiguous'} world identity")
        mapping[int(face_id)]=found[0]
    return mapping


def retain_d150(m, reference, policy):
    if legacy.surface_fingerprint(reference['verts'],reference['faces'])!=policy['surface_sha256']:
        raise ValueError('D150 original reference surface fingerprint mismatch')
    protected=sorted({s[k] for s in policy['samples'] for k in ('upper_face','lower_face')})
    mapping=match_reference_faces(m,reference,protected)
    vm={}
    for vi in policy['vertices']:
        ids=np.flatnonzero(np.linalg.norm(m.verts-reference['verts'][vi],axis=1)<2e-6)
        if len(ids)!=1:raise ValueError(f'D150 vertex {vi}: ambiguous world-coordinate identity')
        vm[vi]=int(ids[0])
    for vi in vm.values():m.verts[vi,2]-=.00002
    surf=m.level>=0;sf=np.flatnonzero(surf);sm=subset(m,surf)
    fm={int(k):i for i,k in enumerate(sf)}
    # subset compacts vertices in increasing source index order.
    used=np.unique(m.faces[surf]);vr=np.full(len(m.verts),-1);vr[used]=np.arange(len(used))
    gaps=gc.measure_stack_gaps(sm,.006)
    actual={(s['kind'],s['upper_face'],s['lower_face'],s['vertex']):s for s in gaps['normal_gap_over_band_samples']}
    rows=[]
    for s in policy['samples']:
        k=(s['kind'],fm[mapping[s['upper_face']]],fm[mapping[s['lower_face']]],None if s['vertex'] is None else int(vr[vm[s['vertex']]]))
        a=actual.pop(k)
        if a['gap_mm']>s['gap_mm']+.000001:raise ValueError(f'D150 frozen maximum increased: {s} -> {a}')
        rows.append({'frozen':s,'current':a})
    if actual:raise ValueError(f'new unaccepted D150 samples: {actual}')
    return set(mapping.values()),{'samples':rows,'upper_vertex_delta_z_m':-.00002,'stack_gaps':gaps}


def validate_pair_hints(m, hints):
    """Optional exclusions only; the full export-safety proof always runs again."""
    if not len(m.faces) or not isinstance(hints,dict) or set(hints)!={'source_geometry_sha256','profiles'}:
        raise ValueError('invalid pair-hint keys or empty geometry')
    if hints['source_geometry_sha256']!=legacy.surface_fingerprint(m.verts,m.faces):
        raise ValueError('pair-hint geometry fingerprint mismatch')
    profiles=hints['profiles']
    if not isinstance(profiles,dict) or set(profiles)!={'npm','vpm'}:
        raise ValueError('unmapped pair-hint profile keys')
    result={}
    for profile,pairs in profiles.items():
        seen=set();result[profile]=[]
        if not isinstance(pairs,list):raise ValueError(f'{profile}: pair-hint list required')
        for pair in pairs:
            if (not isinstance(pair,list) or len(pair)!=2 or pair[0]==pair[1]
                    or any(isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(m.faces) for i in pair)):
                raise ValueError(f'{profile}: invalid pair hint {pair!r}')
            key=tuple(sorted(pair))
            if key in seen:raise ValueError(f'{profile}: duplicate pair hint {key}')
            seen.add(key);result[profile].append(list(key))
    return result


def derive(m,profile,sampler,protected,initial_exclusions=()):
    surf=m.level>=0;xy=m.verts[m.faces[surf],:2];base=np.floor(xy.mean(axis=1)/4)*4
    m.uv[surf]=(xy-base[:,None,:])/4
    uv,layout=legacy.profile_uv(m,profile);uv[~surf]=m.uv[~surf]
    seed=gc.Mesh(m.verts,m.faces,m.slot,m.level,uv,4.)
    edges=defaultdict(list)
    for i,f in enumerate(m.faces):
        for a,b in zip(f,np.roll(f,-1)):edges[tuple(sorted((int(a),int(b))))].append(i)
    excluded={tuple(sorted(v)) for v in edges.values() if len(v)==2 and any(i in protected for i in v)}
    excluded.update(tuple(pair) for pair in initial_exclusions)
    origin=np.r_[(m.verts.min(0)[:2]+m.verts.max(0)[:2])/2,0.]
    verts=(m.verts-origin).astype(np.float32).astype(float)+origin
    z,hit=sampler.sample(m.verts[:,:2]);offset=m.verts[:,2]-z;offset[np.unique(m.faces[m.level==0])]=0
    history=[]
    for iteration in range(12):
        q=pair_triangles(seed,excluded_pairs=sorted(excluded))
        cycles=list(q.faces);uvs=list(q.uv);owners=list(range(len(q.faces)))
        for i,(f,u) in enumerate(zip(q.faces,q.uv)):
            if len(f)==4:cycles.append(f[1:]+f[:1]);uvs.append(np.roll(u,-1,axis=0));owners.append(i)
        found=face_pairs(PolyMesh(verts,tuple(cycles)),XviewTolerance());bad=set();count=0
        for a,b,kind,gap in found:
            if owners[a]==owners[b]:continue
            count+=1;changed=[owners[k] for k in (a,b) if k>=len(q.faces)]
            if not changed:raise ValueError(f'original-diagonal xView defect: {a}/{b} {kind}')
            bad.update(changed)
        tris=[];tex=[];own=[]
        for f,u,i in zip(cycles,uvs,owners):
            if q.level[i]<0:continue
            for j in range(1,len(f)-1):tris.append((f[0],f[j],f[j+1]));tex.append([u[0],u[j],u[j+1]]);own.append(i)
        tris=np.asarray(tris);p=verts[tris]
        errors=sampler.max_error(p[:,:,:2],p[:,:,2]-offset[tris])
        px,lo,hi=(2048,10,40) if profile=='npm' else (4096,512,1706)
        den=gc.texel_density(verts,tris,np.asarray(tex),px)
        failed=(errors>.01)|(~np.isfinite(den))|(den<lo)|(den>hi)
        for i in np.flatnonzero(failed):
            if len(q.source_faces[own[i]])!=2:raise ValueError(f'unsafe original surface triangle {own[i]}')
            bad.add(own[i])
        history.append({'iteration':iteration,'overlap_combinations':count,'relief_max_mm':float(errors.max()*1000),
                        'density_min':float(den.min()),'density_max':float(den.max()),'rejected_pairs':len(bad)})
        print(profile,history[-1],flush=True)
        if not bad:break
        excluded.update(tuple(q.source_faces[i]) for i in bad)
    else:raise ValueError('bounded export-safe pairing did not converge')
    q=detail_polygon_uv(q,profile)
    share=sum(len(f)==3 for f in q.faces)/len(q.faces)
    if share>.35:raise ValueError(f'{profile}: D157 triangle share {share} exceeds 35%')
    if sum(len(f)-2 for f in q.faces)>180000 or sum(l>=0 for l in q.level)>50000:
        raise ValueError('unchanged Ground triangle/surface budget exceeded')
    reasons={s:asdict(quad_report(s,PolyMesh(q.verts,tuple(f for f,slot in zip(q.faces,q.slot) if slot==s)),profile+'-GROUND')) for s in sorted(set(q.slot))}
    return q,{'history':history,'triangle_share':share,'raw_D129':reasons,'excluded_pairs':sorted(excluded),'layout':layout}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--adapter-json',required=True,type=Path);ap.add_argument('--source-master',required=True,type=Path)
    ap.add_argument('--d150-reference',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--pair-hints',type=Path,help='geometry-bound exclusions, never cached acceptance')
    a=ap.parse_args(argv)
    paths=[a.adapter_json,a.source_master,a.d150_reference,ROOT/'ground-notch-approval-v015.json',ROOT/'ground-gap-exceptions.json',ROOT/'ground-source-void-v015.json',ROOT/'ground-material-ids-v015.json']
    if a.pair_hints is not None:paths.append(a.pair_hints)
    paths.extend([Path(__file__),Path(gc.__file__),Path(gd.__file__),Path(sys.modules[pair_triangles.__module__].__file__),Path(legacy.__file__)])
    initial_head=git_head()
    out=a.out.resolve()
    if out.exists():raise ValueError('new output directory required; refusing alias or stale receipts')
    resolved=[p.resolve() for p in paths]
    if (len(set(resolved))!=len(resolved) or out in resolved
            or any(p.exists() and q.exists() and p.samefile(q)
                   for i,p in enumerate(resolved) for q in resolved[:i])):
        raise ValueError('input/output path alias')
    payload={p:p.read_bytes() for p in paths};hashes={str(p):hashlib.sha256(v).hexdigest() for p,v in payload.items()}
    data=load_json(payload[a.adapter_json]);raw=load_json(payload[a.source_master]);approval=load_json(payload[paths[3]])
    policy=load_json(payload[paths[4]]);void=load_json(payload[paths[5]]);materials=load_json(payload[paths[6]])['slots']
    order=[r['slot'] for r in materials]
    if len(order)!=12 or len(set(order))!=12 or [r['material_id'] for r in materials]!=list(range(1,13)):
        raise ValueError('fixed 12-slot/ID inventory invalid')
    unknown=set(raw['slots'])-set(order)
    if unknown:raise ValueError(f'unmapped source texture slots: {sorted(unknown)}')
    for row in materials:
        if row['material_name']!='M_Vatutino_Ground_'+row['slot']:
            raise ValueError(f'unmapped texture material {row["material_name"]!r}')
    if hashes[str(a.adapter_json)]!=approval['source_adapter_sha256'] or hashes[str(a.source_master)]!=approval['source_v014_mesh_sha256']:
        raise ValueError('source adapter/v014 master fingerprint mismatch')
    m,plan,sampler,construction=geometry(data,raw,approval,void)
    protected,gap_receipt=retain_d150(m,np.load(a.d150_reference),policy)
    surf=subset(m,m.level>=0);coverage=gc.measure_coverage(surf,plan,tol=.0022)
    edges=gc.measure_open_edges(surf,plan,eps=.0022)
    if coverage['uncovered_beyond_tol_m2'] or coverage['outside_surface_beyond_tol_m2'] or edges['open_edges_off_outline'] or edges['non_manifold']:
        raise ValueError(f'contour construction failed: {coverage}; {edges}')
    if gap_receipt['stack_gaps']['normal_gap_vertices_below'] or gap_receipt['stack_gaps']['normal_gap_centroids_below']:
        raise ValueError('normal gap below unchanged 5 mm')
    hints=validate_pair_hints(m,load_json(payload[a.pair_hints])) if a.pair_hints is not None else {'npm':[],'vpm':[]}
    profiles={};stats={}
    for profile in ('npm','vpm'):
        q,r=derive(m,profile,sampler,protected,hints[profile])
        if set(q.slot)!=set(order):raise ValueError(f'expected all fixed texture IDs used, actual {sorted(set(q.slot))}')
        profiles[profile]={'verts':q.verts.tolist(),'faces':[list(map(int,f)) for f in q.faces],'uv':[u.tolist() for u in q.uv],
            'slots':order,'mat':[order.index(s) for s in q.slot],'level':q.level.tolist(),'source_faces':q.source_faces,'cell':4.}
        stats[profile]=r
    report={'delivery_accepted':False,'native_readback':'not_run','ucx':'not_run','inputs_sha256':hashes,'git_head':initial_head,
        'construction':construction,'D150':gap_receipt,'coverage':coverage,'open_edges':edges,'profiles':stats}
    assert_unchanged(payload,initial_head)
    out.mkdir(parents=True,exist_ok=False)
    for profile,d in profiles.items():
        with (out/f'master-{profile}.json').open('x',encoding='utf-8') as f:json.dump(d,f,default=int,allow_nan=False)
    with (out/'report.json').open('x',encoding='utf-8') as f:json.dump(report,f,default=int,allow_nan=False)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,KeyError,OSError) as exc:
        print(f'refused: {exc}',file=sys.stderr);raise SystemExit(1)
