"""Ground curb/stair construction from typed adapter paths (#295).

Pattern: n/a | new-case: source-traced Step-8 solids, prescribed curb sections and VP-derived treads.
No DXF parsing and no inferred dimensions for unclassified elements. Source Z of plan symbols
is not a design height: the approved VP TIN alone determines elevation. The solid bottom
uses the method-C top datum + 6 mm (18 mm above VP; covering stack is at most 12 mm).
"""
from __future__ import annotations

import math
import numpy as np
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, shape
from shapely.ops import unary_union, polygonize
from . import ground_cake as gc

SECTIONS = {'curb_garden': (.08,.05,'CurbGarden'), 'curb_drive': (.15,.15,'CurbDrive')}
DATUM = .018


def _empty(cell=4.):
    return gc.Mesh(np.empty((0,3)),np.empty((0,3),int),[],np.empty(0,int),np.empty((0,3,2)),cell)


def combine(meshes):
    meshes=[m for m in meshes if len(m.faces)]
    if not meshes:
        return _empty()
    vs,fs,ss,ls,uv=[],[],[],[],[]; off=0
    for m in meshes:
        vs.extend(m.verts);fs.extend(m.faces+off);ss.extend(m.slot);ls.extend(m.level);uv.extend(m.uv);off+=len(m.verts)
    return gc.Mesh(np.array(vs),np.array(fs,int),ss,np.array(ls,int),np.array(uv),meshes[0].cell)


def triangle_uv(verts, faces, repeat=4.):
    """Metric, non-mirrored local projection for placeholder solids; tile-contained or fail closed."""
    p=verts[faces]; a=p[:,1]-p[:,0]; b=p[:,2]-p[:,0]
    # Orient each placeholder island along the edge that minimises its square extent.
    candidates=[]
    for shift in range(3):
        q=np.roll(p,shift,axis=1); a=q[:,1]-q[:,0]; b=q[:,2]-q[:,0]
        lengths=np.linalg.norm(a,axis=1)
        if np.any(lengths<1e-9):raise ValueError('degenerate detail triangle')
        u=np.einsum('ij,ij->i',a,b)/lengths
        v=np.linalg.norm(np.cross(a,b),axis=1)/lengths
        local=np.stack([np.zeros((len(p),2)),np.stack([lengths,np.zeros(len(p))],axis=1),np.stack([u,v],axis=1)],axis=1)
        local=np.roll(local,-shift,axis=1);local-=local.min(axis=1,keepdims=True)
        candidates.append(local)
    candidates=np.array(candidates)
    extents=candidates.max(axis=(2,3))
    choice=extents.argmin(axis=0)
    local=candidates[choice,np.arange(len(p))]
    extent=local.max(axis=(1,2))
    scale=np.maximum(repeat,extent)
    if repeat==4. and np.any(4096/scale<520):
        raise ValueError('detail triangle exceeds a tile at 520 px/m; subdivide the source contour')
    return local/scale[:,None,None]


def _curb_solid(geom, sampler, height, slot):
    """One shared 4 m surface partition; bottom copy and perimeter walls make a closed solid."""
    mp=MultiPolygon(gc._polys(geom))
    plan=gc.Plan(mp,[],[gc.Layer(slot,slot,0,mp)],.006)
    flat=gc.build_flat(plan,cell=4,chord=0,sampler=sampler,tol=.01,snap=.001)
    top,miss=gc.project_z(flat,sampler,.006)
    if miss:
        raise ValueError(f'curb relief misses: {len(miss)}')
    top=gc.clean_topology(top)
    n=len(top.verts);v=np.vstack([top.verts,top.verts]);v[:n,2]+=DATUM+height;v[n:,2]+=DATUM
    faces=top.faces.tolist()+[(f[::-1]+n).tolist() for f in top.faces]
    edges={}
    for f in top.faces:
        for a,b in zip(f,np.roll(f,-1)):
            edges.setdefault(tuple(sorted((int(a),int(b)))),[]).append((int(a),int(b)))
    for uses in edges.values():
        if len(uses)==1:
            a,b=uses[0];faces.extend([[b,a,a+n],[b,a+n,b+n]])
    faces=np.array(faces,int)
    return gc.Mesh(v,faces,[slot]*len(faces),np.full(len(faces),-2),np.zeros((len(faces),3,2)),4.)


def _stairs_solid(outline, cells, heights, sampler):
    """Horizontal source treads, connecting risers, outer walls and a single bottom."""
    z,hit=sampler.sample(np.array(outline.exterior.coords)[:,:2])
    if not hit.all():
        raise ValueError('stair VP misses')
    bottom=float(z.min())-.05
    v=[];f=[];index={};edge_heights={}
    def vid(x,y,z):
        k=(round(float(x),6),round(float(y),6),round(float(z),6))
        if k not in index:index[k]=len(v);v.append(k)
        return index[k]
    for poly,h in zip(cells,heights):
        poly=shapely.orient_polygons(poly)
        for tri in gc._tri_piece(poly):
            f.append([vid(x,y,bottom) for x,y in tri[::-1]])
        for tri in gc._tri_piece(poly):
            f.append([vid(x,y,h) for x,y in tri])
        for ring in [poly.exterior,*poly.interiors]:
            cs=list(ring.coords)
            for a,b in zip(cs,cs[1:]):
                a,b=tuple(a[:2]),tuple(b[:2]); key=tuple(sorted((a,b)))
                edge_heights.setdefault(key,[]).append((a,b,h))
    for uses in edge_heights.values():
        a,b,h=uses[0]
        if len(uses)==1:
            low=bottom
        else:
            h2=uses[1][2]
            if abs(h-h2)<1e-6:continue
            if h<h2:a,b,h=uses[1]
            low=min(h,uses[0][2],uses[1][2])
        ai,bi,al,bl=vid(*a,h),vid(*b,h),vid(*a,low),vid(*b,low)
        f.extend([[bi,ai,al],[bi,al,bl]])

    f=np.array(f,int)
    return gc.Mesh(np.array(v),f,['Stairs']*len(f),np.full(len(f),-2),np.zeros((len(f),3,2)),4.)


def build_details(elements, boundary, sampler):
    """Return solid mesh and one disposition per adapter entity (including group INSERTs)."""
    if boundary.is_empty or not boundary.is_valid:
        raise ValueError('valid nonempty boundary required')
    meshes=[];report=[]; curbs={};stair_groups={}
    for e in elements:
        row={k:e.get(k) for k in ('ref','handle','container','role','layer','label')}
        row.update(status='skipped',reason='')
        report.append(row)
        role=e['role'];geom=shape(e['geometry']) if e.get('geometry') else None
        if e.get('problem'):
            row['reason']=e['problem'];continue
        if role=='stairs':
            root=e['ref'].split('>')[0];stair_groups.setdefault(root,[]).append((e,row));continue
        if geom is None:
            row['reason']='no path geometry in DWG';continue
        path=shapely.force_2d(geom).intersection(boundary)
        if path.is_empty or path.length<.002:
            row['reason']='outside Ground boundary or collapsed at 2 mm';continue
        if role not in SECTIONS:
            row['reason']='DWG/user do not define visible height and cross-section for this curb class';continue
        width,height,slot=SECTIONS[role]
        area=path.buffer(width/2,cap_style='flat',join_style='mitre').intersection(boundary)
        if area.is_empty:
            row['reason']='empty clipped curb footprint';continue
        curbs.setdefault(role,[]).append(area)
        row.update(status='modeled',reason='approved section; polyline is the width centreline',width_m=width,height_m=height,
                   length_m=path.length,footprint_m2=area.area,bottom_above_vp_m=DATUM)
    for role,gs in curbs.items():
        width,height,slot=SECTIONS[role]
        meshes.append(_curb_solid(unary_union(gs),sampler,height,slot))
    for root,group in stair_groups.items():
        parent=next((e for e,r in group if e['kind']=='INSERT'),None)
        lines=[shapely.force_2d(shape(e['geometry'])) for e,r in group if e.get('geometry')]
        outlines=[]
        for g in lines:
            coords=list(g.coords)
            if len(coords)>=4 and math.dist(coords[0],coords[-1])<=.002:
                coords[-1]=coords[0]
                poly=Polygon(coords)
                if poly.is_valid and poly.area>1e-6:outlines.append(poly)
        reason='DWG does not define a closed stair footprint and tread lines'
        if parent and str(parent.get('label','')).lower().startswith('скамья'):
            reason='bench symbol, MAF excluded from Ground surface scope'
            outlines=[]
        if outlines:
            outline=max(outlines,key=lambda p:p.area).intersection(boundary)
            ps=gc._polys(outline)
            if len(ps)==1 and not ps[0].interiors:
                outline=ps[0]
                cuts=[outline.boundary]
                for line in lines:
                    if len(line.coords)>=4 and math.dist(line.coords[0],line.coords[-1])<=.002:continue
                    cs=np.array(line.coords);delta=cs[-1]-cs[0];length=np.linalg.norm(delta)
                    if length<.002:continue
                    # Tread endpoints in the plan miss the footprint by sub-mm; extend at most 20 mm.
                    cs[0]-=delta/length*.02;cs[-1]+=delta/length*.02
                    cuts.append(LineString(cs).intersection(outline))
                cells=[p for p in polygonize(unary_union(cuts)) if outline.covers(p.representative_point())]
                centres=np.array([[p.centroid.x,p.centroid.y] for p in cells])
                if len(cells)>1:
                    heights,hit=sampler.sample(centres)
                    if hit.all() and np.ptp(heights)>.001:
                        # Elevations follow VP at tread centres, rather than corrupt symbol-local Z.
                        meshes.append(_stairs_solid(outline,cells,heights+DATUM,sampler))
                        for e,r in group:r.update(status='modeled',reason='source footprint/tread cuts; heights from VP',treads=len(cells),
                                                   min_vp_z=float(heights.min()),max_vp_z=float(heights.max()))
                        continue
                    reason='VP does not define distinct tread elevations (or projection misses)'
                else:reason='DWG tread lines do not partition the stair footprint'
            else:reason='stair footprint outside Ground or unsupported holes/multiple parts'
        for e,r in group:r['reason']=reason
    mesh=combine(meshes)
    if len(mesh.faces):
        # Detail UV is derived after cleanup. No loose edges or near-duplicate solid vertices are retained.
        mesh=gc.clean_topology(mesh)
    return mesh,report
