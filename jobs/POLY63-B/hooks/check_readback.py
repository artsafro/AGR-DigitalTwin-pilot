"""new-case: check shared FBX readback against body intent; extract the #1616 band."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from shapely import Point, Polygon


METRIC_TOL = .0002  # m; FBX float storage and export welding, not a construction tolerance
PHASE_TOL = 1e-5    # texture repeats


def phase_delta(a,b):
    delta = np.asarray(a)-np.asarray(b)
    return float(np.abs(delta-np.rint(delta)).max())


def measure_arc(points, stations, center, radius, samples, step):
    """Measure native chord lengths and UV phase, not agreement with authored UV."""
    points = np.asarray(points)
    lengths = np.linalg.norm(np.diff(points,axis=0),axis=1)
    chain = np.r_[0., lengths.cumsum()]
    repeats = np.diff(chain[stations]); residual = chain[-1]-chain[stations[-1]]
    uv_error = anchor_error = 0.
    for i, (xy,u) in enumerate(samples):
        if not len(xy): raise ValueError(f'No native face on arc chord {i}')
        xy=np.asarray(xy); u=np.asarray(u)
        distance = (xy-points[i]) @ ((points[i+1]-points[i])/lengths[i])
        # Each row contains both horizontal loops of a native face, in arc order.
        uv_error=max(uv_error,float(np.abs(np.diff(u,axis=-1)*step-np.diff(distance,axis=-1)).max()))
        anchor_error=max(anchor_error,phase_delta(u,(distance+chain[i])/step)*step)
    return dict(full_repeats_m=repeats.tolist(), terminal_remainder_m=float(residual),
                max_step_error_m=float(np.abs(repeats-step).max(initial=0.)),
                max_uv_metric_error_m=uv_error, max_anchor_error_m=anchor_error,
                max_sagitta_m=float(np.abs(radius-np.linalg.norm((points[1:]+points[:-1])/2-center,axis=1)).max()),
                max_radius_error_m=float(np.abs(np.linalg.norm(points-center,axis=1)-radius).max()))


def registration_failures(arcs, phase, step):
    return ([name for name, a in arcs.items() if (
        max(a['max_step_error_m'],a['max_uv_metric_error_m'],a['max_anchor_error_m']) > METRIC_TOL
        or a['max_sagitta_m'] > .020 or a['max_radius_error_m'] > METRIC_TOL
        or a['terminal_remainder_m'] >= step+METRIC_TOL)]
        + (['same-ID facade edge phase'] if phase > PHASE_TOL else []))


def project_arc_station(point, samples):
    # A curtain can remove the tangency vertex. Use the planned station only
    # along a native chord line; disclose this reconstruction in the receipt.
    a,b = max((xy for xy,_ in samples), key=lambda xy: np.linalg.norm(xy[1]-xy[0]))
    u = (b-a)/np.linalg.norm(b-a)
    projected = a+((point-a)@u)*u
    if np.linalg.norm(point-projected)>METRIC_TOL:
        raise ValueError(f'Tangency off native chord: {point}')
    return projected


def shell_audit(vertices, faces, labels, allowed):
    """Count shells and free edges on native indices, never welded positions."""
    edges=defaultdict(list); incident=defaultdict(set); fan_links=defaultdict(list)
    adjacency=[set() for _ in faces]
    for i,f in enumerate(faces):
        for a,b in zip(f,f[1:]+f[:1]):
            edges[tuple(sorted((a,b)))].append(i)
            incident[a].add(i)
    unexpected=[]; observed=Counter(); reasons=Counter(); rim_degree=Counter()
    for (a,b),owners in edges.items():
        for i in owners: adjacency[i].update(owners)
        if len(owners)==2:
            fan_links[a].append(owners); fan_links[b].append(owners)
        if len(owners)!=1: continue
        rim_degree.update((a,b))
        key=tuple(sorted((labels[a],labels[b])))
        if key not in allowed or observed[key]:
            unexpected.append(dict(face=owners[0], vertices=[a,b], edge=vertices[[a,b]].tolist()))
        else:
            observed[key]+=1; reasons[allowed[key]]+=1

    def walk(todo, neighbors):
        while todo:
            stack=[min(todo)]; todo.remove(stack[0]); component=[]
            while stack:
                i=stack.pop(); component.append(i)
                near=neighbors[i]&todo; todo.difference_update(near); stack.extend(near)
            yield component

    bad_fans=[]
    for v,attached in incident.items():
        linked={i:set() for i in attached}
        for a,b in fan_links[v]: linked[a].add(b); linked[b].add(a)
        if rim_degree[v] not in (0,2) or len(list(walk(attached.copy(),linked)))!=1:
            bad_fans.append(v)
    shells=[]
    for ids in walk(set(range(len(faces))),adjacency):
        points=vertices[sorted({v for i in ids for v in faces[i]})]
        shells.append(dict(first_face=min(ids), faces=len(ids), bounds_m=[points.min(0).tolist(),points.max(0).tolist()],
                           reason='single typical body' if len(ids)==len(faces) else 'unjustified fragment'))
    return dict(shell_count=len(shells), shells=shells, bad_vertex_fans=sorted(bad_fans),
                unexpected_boundary_edges=unexpected, open_boundary_edges_outside_openings=len(unexpected),
                missing_boundary_edges=[[*key,allowed[key]] for key in sorted(allowed.keys()-observed.keys())],
                planned_boundary_counts=reasons)


def check(master, readback, design, step):
    (obj,) = readback['meshes']
    assert readback['readback_ok'] and not readback['other_objects']
    assert obj['uv_channels']==1 and master['arcs']
    g=obj['face_geometry']; got=np.asarray(g['vertices']); want=np.asarray(master['vertices']); roles=master['roles']
    assert len(g['polygons']) == len(master['faces'])
    rings={key:Polygon(ring) for key,ring in master.get('effective_rings',{
        key:v['ring'] for key,v in design['modules'].items()}).items()}
    ends=[design['floors'][0]['bottom'],design['floors'][-1]['top']]
    transitions=[f['top'] for f,g in zip(design['floors'],design['floors'][1:]) if f['type']!=g['type']]
    free_facade=[]; shoulders=Counter(); arc_samples=Counter(); uv_error=0.
    native_arcs=defaultdict(list); facade_edges=defaultdict(list)
    reversed_faces=[]; inward=[]; positions=0.; facet=[]; mats=[]; nonmanifold=Counter(); directions=Counter()
    palette=['01_Ventfacade_regular','02_Render_return','03_Ventfacade_band']
    owner={}
    labels={}
    for i,(f,k,role) in enumerate(zip(g['polygons'],master['faces'],roles,strict=True)):
        a,b=got[f],want[k]; parity=min(np.abs(np.roll(a,t,axis=0)-b).max() for t in range(len(a)))
        flip=min(np.abs(np.roll(a[::-1],t,axis=0)-b).max() for t in range(len(a)))
        if flip<parity: reversed_faces.append(i)
        positions=max(positions,min(parity,flip))
        if 'polygon_uv' in master:
            order=np.arange(len(a))[::-1] if flip<parity else np.arange(len(a))
            order=min((np.roll(order,t) for t in range(len(a))),key=lambda ix:np.abs(a[ix]-b).max())
            for corner,label in zip(order,k,strict=True):
                if labels.setdefault(f[corner],label)!=label:
                    raise ValueError('Native vertex maps to conflicting planned vertices')
            uv=np.asarray(g['polygon_uv'][i])[order]
            uv_error=max(uv_error,float(np.abs(uv-np.asarray(master['polygon_uv'][i])).max()))
            arc=master['arc_faces'].get(str(i))
            if arc:
                arc_id, segment = arc
                for corners in ([0,1],[3,2]):
                    native_arcs[arc_id,segment].append((a[order[corners],:2],uv[corners,0]))
                arc_samples[arc_id]+=1
            if role=='facade':
                loops=np.asarray(g['polygon_uv'][i]); material=g['polygon_material'][i]
                for j,(u,v) in enumerate(zip(f,f[1:]+f[:1])):
                    if np.linalg.norm(got[u,:2]-got[v,:2]) < 1e-6:
                        pair=loops[[j,(j+1)%len(f)]]
                        facade_edges[min(u,v),max(u,v),material].append(pair if u<v else pair[::-1])
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
    phase_checks=[phase_delta(*pairs) for pairs in facade_edges.values() if len(pairs)==2]
    registration={}
    reconstructed={}
    for name, arc in master['arcs'].items():
        samples=[native_arcs[name,i] for i in range(arc['count'])]
        points=[]
        for i, match in enumerate(arc['points']):
            distance=np.linalg.norm(got[:,:2]-match,axis=1)
            nearest=int(distance.argmin())
            if distance[nearest]>METRIC_TOL:
                if i not in (0,arc['count']): raise ValueError(f'Missing native interior station {name}:{i}')
                points.append(project_arc_station(match,samples[0 if i==0 else -1]))
                reconstructed.setdefault(name,[]).append(i)
            else:
                points.append(got[nearest,:2])
        registration[name]=measure_arc(points,arc['stations'],arc['center'],arc['radius'],
            [(np.asarray([p for p,_ in s]),np.asarray([u for _,u in s])) for s in samples],step)
    phase=max(phase_checks,default=0.)
    expected={(a,b):reason for a,b,reason in master['planned_boundary']}
    shell=shell_audit(got,g['polygons'],labels,expected)
    native_joins = {}
    for f in design['floors'][:-1]:
        z=f['top']
        native_joins[str(z)] = sum(1 for edge,n in nonmanifold.items()
                                   if n==2 and np.all(np.abs(got[list(edge),2]-z)<.0001))
    report: dict = dict(face_count=len(roles),roles=Counter(roles),maximum_vertex_drift_m=positions,
                inverted_readback=reversed_faces,inward_exterior=inward,
                boundary_edges=sum(v==1 for v in nonmanifold.values()),
                edges_over_two_faces=sum(v>2 for v in nonmanifold.values()),
                seating_winding_conflicts=sum(v==2 and (directions[k]==2 or directions[k[::-1]]==2) for k,v in nonmanifold.items()),
                topology=obj['topology'],bounds_m=obj['bounds_m'],polygon_degrees=obj['polygon_degrees'],
                unexpected_facade_free_edges=free_facade, shoulder_mouth_edges=shoulders,
                uv_channels=obj['uv_channels'], maximum_uv_delta=uv_error,
                arc_chord_sagitta_m={k:v['max_sagitta_m'] for k,v in registration.items()},
                arc_face_samples=arc_samples, training_step_m=step, arc_registration=registration,
                same_id_vertical_edges=len(phase_checks), max_same_id_phase_delta=phase,
                registration_failures=registration_failures(registration,phase,step),
                reconstructed_arc_tangencies=reconstructed, paired_horizontal_edges_at_floor_joins=native_joins,
                **shell)
    band={'objects':[{'name':obj['name'],'verts':g['vertices'],'faces':facet,'materials':mats}], 'dropped':[]}
    return report,band

if __name__=='__main__':
    inp,fbx,design,report,band=map(Path,sys.argv[1:])
    master,readback,ledger=(json.loads(p.read_bytes()) for p in (inp,fbx,design))
    config=json.loads((Path(__file__).resolve().parents[1]/'sources.json').read_bytes())['training']
    result,extract=check(master,readback,ledger,config['texture_step_m'])
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
        or result['registration_failures'] or result['shell_count']!=1
        or result['unexpected_boundary_edges'] or result['missing_boundary_edges'] or result['bad_vertex_fans']
        or not all(result['paired_horizontal_edges_at_floor_joins'].values())
        or any(v for k,v in result['topology'].items() if k!='tol_m')))
