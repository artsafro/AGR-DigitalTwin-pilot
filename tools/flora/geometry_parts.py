"""Offline authored-part diagnostics; never semantic acceptance.

Pattern: n/a | new-case: #369 geometry-edge UV charts, without coordinate welding.
Map indices may duplicate; continuity requires the SAME geometry edge, material
and equal UV coordinates at BOTH ends. Coincident disconnected cards never join.
"""
from collections import defaultdict
import numpy as np


def _arrays(record):
    vertices=np.asarray(record['vertices'],dtype=float)
    uv=np.asarray(record['uv'],dtype=float)
    faces=np.asarray(record['faces'])
    maps=np.asarray(record['uvfaces'])
    materials=np.asarray(record['face_material_ids'])
    if (vertices.ndim!=2 or vertices.shape[1:]!=(3,) or not len(vertices)
            or uv.ndim!=2 or uv.shape[1:]!=(2,) or not len(uv)
            or not np.isfinite(vertices).all() or not np.isfinite(uv).all()
            or faces.ndim!=2 or faces.shape[1:]!=(3,) or not len(faces)
            or faces.dtype.kind not in 'iu' or maps.dtype.kind not in 'iu'
            or maps.shape!=faces.shape or materials.shape!=(len(faces),)
            or materials.dtype.kind not in 'iu'
            or (faces<0).any() or (faces>=len(vertices)).any()
            or (maps<0).any() or (maps>=len(uv)).any()):
        raise ValueError('finite nonempty geometry, UV topology and material IDs required')
    return vertices,faces,uv,maps,materials


def _groups(count, links):
    parent=list(range(count))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for a,b in links:parent[root(a)]=root(b)
    groups={}
    for i in range(count):groups.setdefault(root(i),[]).append(i)
    return sorted(groups.values(),key=lambda g:g[0])


def uv_charts(record):
    """Edge-connected charts, invariant to duplicate map indices; exact seams remain."""
    _,faces,uv,maps,materials=_arrays(record)
    edges=defaultdict(list)
    for i,(face,mapface,material) in enumerate(zip(faces,maps,materials)):
        for a,b in ((0,1),(1,2),(2,0)):
            ends=sorted(((int(face[a]),tuple(uv[mapface[a]])),(int(face[b]),tuple(uv[mapface[b]]))))
            edges[(int(material),tuple(ends))].append(i)
    links=[]
    for owners in edges.values():
        if len(owners)==2:links.append(owners)
        # More than two owners is nonmanifold, not an invitation to merge.
    return _groups(len(faces),links)


def geometry_parts(vertices, faces):
    """Geometry-only card/tube candidates; no UVs, bitmaps or profile labels.

    Disk + co-directed normals = card. Disk/annulus + normals wrapping the
    longest PCA axis = tube. Numeric tolerances are diagnostic, not acceptance.
    """
    v=np.asarray(vertices,dtype=float);f=np.asarray(faces)
    if (v.ndim!=2 or v.shape[1:]!=(3,) or not len(v) or not np.isfinite(v).all()
            or f.ndim!=2 or f.shape[1:]!=(3,) or not len(f) or f.dtype.kind not in 'iu'
            or (f<0).any() or (f>=len(v)).any()):
        raise ValueError('finite nonempty triangle geometry required')
    edges=defaultdict(list)
    for i,face in enumerate(f):
        for a,b in ((0,1),(1,2),(2,0)):
            edges[tuple(sorted((int(face[a]),int(face[b]))))].append(i)
    groups=_groups(len(f),[(owners[0],i) for owners in edges.values() for i in owners[1:]])
    normals=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    lengths=np.linalg.norm(normals,axis=1)
    result=[]
    for indices in groups:
        used=np.unique(f[indices]);p=v[used]
        row={'faces':indices,'role':'unknown','kind':'unsupported_surface'}
        local=defaultdict(int)
        for face in f[indices]:
            for a,b in ((0,1),(1,2),(2,0)):
                local[tuple(sorted((int(face[a]),int(face[b]))))]+=1
        boundary=[edge for edge,count in local.items() if count==1]
        adjacency=defaultdict(set)
        for a,b in boundary:adjacency[a].add(b);adjacency[b].add(a)
        loops=0;unseen=set(adjacency)
        while unseen:
            stack=[unseen.pop()];loops+=1
            while stack:
                for other in adjacency[stack.pop()]:
                    if other in unseen:unseen.remove(other);stack.append(other)
        chi=len(used)-len(local)+len(indices)
        row.update(boundary_loops=loops,boundary_edges=len(boundary),euler=chi)
        reason=None
        if min(lengths[indices])<=np.finfo(float).eps*max(float(np.ptp(p,axis=0).max())**2,1e-30):
            reason='degenerate triangle'
        elif max(local.values())>2 or any(len(neighbours)!=2 for neighbours in adjacency.values()):
            reason='nonmanifold surface or boundary'
        elif not ((loops==1 and chi==1) or (loops==2 and chi==0)):
            reason='surface is neither disk nor annulus'
        if reason is None:
            n=normals[indices]/lengths[indices,None]
            mean=n.sum(axis=0);mean_length=float(np.linalg.norm(mean))
            # Cone half-angle <45deg certifies every pair differs by <90deg.
            codirected=mean_length>1e-12 and float((n@(mean/mean_length)).min())>np.sqrt(.5)
            _,s,basis=np.linalg.svd(p-p.mean(axis=0),full_matrices=False)
            planar=s[-1]<=s[0]*1e-3
            if loops==1 and chi==1 and codirected:
                row.update(role='foliage',kind='flat_card' if planar else 'bent_card')
                reason='manifold disk with coherently facing normals (geometry-only card)'
            else:
                radial=n@basis[1:].T
                size=np.linalg.norm(radial,axis=1)
                angles=np.sort(np.arctan2(radial[size>1e-8,1],radial[size>1e-8,0]))
                gap=float(np.diff(np.r_[angles,angles[0]+2*np.pi]).max()) if len(angles) else 2*np.pi
                row['normal_wrap_max_gap_rad']=gap
                if gap<np.pi-1e-8:
                    row.update(role='trunk',kind='tube')
                    reason='disk/annulus with radial normals wrapping longest PCA axis'
                else:
                    # A folded sheet can have opposing panel normals while still
                    # admitting a strict open hemisphere. Store a verifiable
                    # certificate, never call a failed search a pass. Tube test
                    # takes precedence: a capped taper also admits a hemisphere.
                    direction=n.mean(axis=0)
                    for _ in range(2048):
                        length=float(np.linalg.norm(direction))
                        if length<=1e-12:break
                        dots=n@(direction/length)
                        if float(dots.min())>1e-8:
                            if loops==1 and chi==1:
                                row.update(role='foliage',kind='folded_card',
                                           normal_hemisphere_axis=(direction/length).tolist(),
                                           normal_hemisphere_min_dot=float(dots.min()))
                                reason='non-wrapping manifold disk with certified open-hemisphere face normals'
                            break
                        direction+=n[int(np.argmin(dots))]*(-float(dots.min())*length+1e-4)
                    if reason is None:reason='neither coherent card normals nor wrapped tube normals'
        row['reason']=reason;result.append(row)
    return result


def parts_and_charts(record):
    """Join an edge-continuous UV chart to independent geometry role evidence."""
    v,f,_,_,_=_arrays(record)
    parts=geometry_parts(v,f)
    owners={face:number for number,part in enumerate(parts) for face in part['faces']}
    charts=[]
    for indices in uv_charts(record):
        ids=sorted({owners[i] for i in indices})
        roles={parts[i]['role'] for i in ids}
        role=next(iter(roles)) if len(roles)==1 else 'unknown'
        charts.append({'faces':indices,'geometry_parts':ids,'role':role,
                       'reason':'; '.join(sorted({parts[i]['reason'] for i in ids}))})
    return parts,charts
