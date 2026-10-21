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
    if not len(verts) or not len(faces):
        raise ValueError('nonempty detail geometry required')
    if not np.isfinite(verts).all() or not math.isfinite(repeat) or repeat <= 0:
        raise ValueError('finite detail coordinates and positive finite repeat required')
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
    # [D160]: inclusive VPM lower bound supersedes D097.
    if repeat==4. and np.any(4096/scale<512):
        raise ValueError('detail triangle exceeds a tile at 512 px/m; subdivide the source contour')
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


def fit_curb_bottom(mesh: gc.Mesh, support: gc.Mesh, gap_m: float = .006,
                    max_trim_m: float = .01) -> gc.Mesh:
    """Trim ONLY the curb underside to clear the actual raised cake along its normal.

    Opt-in construction step, not a changed datum/section policy: the visible top,
    footprint, indices and texture identity stay fixed. For each bottom triangle,
    bound the required lift over every intersecting support triangle (affine-plane
    extrema lie at overlay vertices). Lift all three corners by at least that bound;
    shared corners take the maximum, keeping the solid closed. Refuse an unsupported
    bottom, a trim reaching the relief tolerance, or a collapsed section. No input
    is mutated and no face is dropped. This is not a final xView/coverage receipt.
    """
    from dt_ai.ops.inv_quads import PolyMesh

    for name, value in (("gap_m", gap_m), ("max_trim_m", max_trim_m)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive finite")
    if gap_m <= .005 or max_trim_m > .01:
        raise ValueError("curb fit requires gap_m > 0.005 and max_trim_m <= 0.01 m")
    for name, m in (("curb", mesh), ("support", support)):
        checked = PolyMesh(m.verts, tuple(map(tuple, m.faces)))
        if not checked.faces or any(len(f) != 3 for f in checked.faces):
            raise ValueError(f"{name}: nonempty triangular mesh required")
        if len(m.slot) != len(m.faces) or np.shape(m.level) != (len(m.faces),):
            raise ValueError(f"{name}: missing face metadata")
        if not np.isfinite(m.level).all():
            raise ValueError(f"{name}: nonfinite levels")
        if np.shape(m.uv) != (len(m.faces), 3, 2) or not np.isfinite(m.uv).all():
            raise ValueError(f"{name}: finite corner UV required")
    unknown = sorted(set(mesh.slot) - {s[2] for s in SECTIONS.values()})
    if unknown:
        raise ValueError(f"unsupported curb slots: {unknown}")
    if np.any(mesh.level != -2) or np.any(support.level < 0):
        raise ValueError("curb detail and surface-only support required")
    p = mesh.verts[mesh.faces]
    normals = np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0])
    bottoms = np.flatnonzero(normals[:, 2] < -1e-12)
    tops = np.flatnonzero(normals[:, 2] > 1e-12)
    if not len(bottoms) or not len(tops) or np.any(np.linalg.norm(normals, axis=1) <= 2e-12):
        raise ValueError("curb requires nondegenerate top and bottom faces")
    sp = support.verts[support.faces]
    sn = np.cross(sp[:, 1]-sp[:, 0], sp[:, 2]-sp[:, 0])
    lengths = np.linalg.norm(sn, axis=1)
    if np.any(sn[:, 2] <= 1e-12) or not np.isfinite(lengths).all():
        raise ValueError("support must be an upward nondegenerate heightfield")
    sn /= lengths[:, None]
    polygons = [Polygon(t[:, :2]) for t in sp]
    tree = shapely.STRtree(polygons)
    lift = np.zeros(len(mesh.verts))
    rows = []
    for fi in bottoms:
        poly = Polygon(p[fi, :, :2])
        ids = sorted(tree.query(poly, predicate='intersects').tolist())
        pieces = []
        delta = 0.
        for si in ids:
            overlap = poly.intersection(polygons[si])
            if overlap.area <= 1e-14:
                continue
            pieces.append(overlap)
            xy = shapely.get_coordinates(overlap)
            # Local coordinates avoid cancellation at real-site world offsets.
            s0 = sp[si, 0]
            sz = s0[2] - ((xy-s0[:2]) @ sn[si, :2])/sn[si, 2]
            b0 = p[fi, 0]
            bz = b0[2] - ((xy-b0[:2]) @ normals[fi, :2])/normals[fi, 2]
            delta = max(delta, float(np.max(sz + gap_m/sn[si, 2] - bz)))
        # Union the original shared-edge faces BEFORE clipping. Independently
        # rounded intersection rings can otherwise invent a micron-wide hole.
        if not pieces or poly.difference(unary_union([polygons[si] for si in ids])).area > 1e-10:
            raise ValueError(f"curb bottom face {fi}: incomplete surface support")
        if delta >= max_trim_m:
            raise ValueError(f"curb bottom face {fi}: trim {delta:.12g} m reaches {max_trim_m} m limit")
        lift[mesh.faces[fi]] = np.maximum(lift[mesh.faces[fi]], delta)
        rows.append(dict(face=int(fi), lift_m=delta, support_faces=ids))
    top_ids = np.unique(mesh.faces[tops])
    if np.any(lift[top_ids] > 0):
        raise ValueError("curb bottom/top vertex identity is ambiguous")
    v = mesh.verts.copy()
    v[:, 2] += lift
    columns = {}
    for i, xyz in enumerate(mesh.verts):
        columns.setdefault(tuple(xyz[:2]), []).append(i)
    for ids in columns.values():
        if len(ids) != 2 or np.ptp(v[ids, 2]) <= .002 or np.argmin(v[ids, 2]) != np.argmin(mesh.verts[ids, 2]):
            raise ValueError(f"curb fit collapses or cannot prove paired top/bottom column {ids}")
    report = dict(mesh.report)
    report['curb_support_fit'] = dict(gap_m=gap_m, max_trim_m=max_trim_m,
                                    measured_trim_m=float(lift.max()), bottom_faces=rows,
                                    dropped_faces=[])
    return gc.Mesh(v, mesh.faces.copy(), list(mesh.slot), mesh.level.copy(),
                   mesh.uv.copy(), mesh.cell, report)


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
        # Every wall uses the same horizontal cuts. Adjacent treads otherwise
        # terminate midway along the taller side wall's vertical edge (a T-junction
        # which Editable Poly/xView reports as overlapping faces).
        cuts=sorted({float(low),float(h),*(float(z) for z in heights if low<z<h)})
        for lo,hi in zip(cuts,cuts[1:]):
            ai,bi,al,bl=vid(*a,hi),vid(*b,hi),vid(*a,lo),vid(*b,lo)
            f.extend([[bi,ai,al],[bi,al,bl]])

    f=np.array(f,int)
    return gc.Mesh(np.array(v),f,['Stairs']*len(f),np.full(len(f),-2),np.zeros((len(f),3,2)),4.)


def build_details(elements, boundary, sampler, separate_curbs=False, stair_clearance_m=0.):
    """Return ``(mesh, report, joints)``.

    ``report`` holds one disposition per adapter entity (including group INSERTs). With
    ``separate_curbs`` every modeled curb row also carries its own ``retained_m2``,
    ``stair_trim_m2`` and ``joint_trim_m2`` (``footprint_m2`` reconciles to their sum), and
    a fully covered entity is reported ``status='trimmed'`` with a truthful reason: the
    taller-curb joint policy only when that policy actually removed the geometry, the stair
    footprint when stairs occluded it, and a combined reason when both applied. ``joints``
    holds the role-union joint trim totals once, at their own scope, so no entity row
    inherits another role's union trim.

    ``separate_curbs`` is an explicit model-policy opt-in: continue the taller section
    through mixed-section junctions and end the shorter one with a 6 mm joint.
    The caller must obtain project approval; default/legacy builds never enable it.
    """
    if isinstance(stair_clearance_m, bool) or not isinstance(stair_clearance_m, (int, float)) or not math.isfinite(stair_clearance_m) or not 0 <= stair_clearance_m <= .02:
        raise ValueError('stair_clearance_m must be finite in [0, 0.02] m')
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
        curbs.setdefault(role,[]).append((area,row))
        row.update(status='modeled',reason='approved section; polyline is the width centreline',width_m=width,height_m=height,
                   length_m=path.length,footprint_m2=area.area,bottom_above_vp_m=DATUM)
    stair_footprints=[]
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
                        stair_footprints.append(outline)
                        for e,r in group:r.update(status='modeled',reason='source footprint/tread cuts; heights from VP',treads=len(cells),footprint=shapely.geometry.mapping(outline),
                                                   min_vp_z=float(heights.min()),max_vp_z=float(heights.max()))
                        continue
                    reason='VP does not define distinct tread elevations (or projection misses)'
                else:reason='DWG tread lines do not partition the stair footprint'
            else:reason='stair footprint outside Ground or unsupported holes/multiple parts'
        for e,r in group:r['reason']=reason
    occupied = Polygon()
    roles = sorted(curbs, key=lambda r: -SECTIONS[r][1]) if separate_curbs else curbs
    joints = []
    stair_union = unary_union(stair_footprints)
    if stair_clearance_m:
        # Analytic mitred cuts avoid sub-mm round-buffer segments collapsing
        # under the regulatory weld and bridging back across a stair corner.
        stair_union = stair_union.buffer(stair_clearance_m, join_style='mitre')
    for role in roles:
        width,height,slot=SECTIONS[role]
        footprint=unary_union([a for a,_ in curbs[role]]).difference(stair_union)
        if stair_clearance_m:
            for area, row in curbs[role]:
                retained = area.difference(stair_union).area
                row.update(stair_clearance_m=stair_clearance_m,
                           stair_trim_m2=max(0., area.area-retained), retained_m2=retained)
                if retained <= 1e-9:
                    row.update(status='trimmed', reason='occluded by stair footprint and explicit clearance')
        if separate_curbs:
            # Taller section continues through the joint; shorter section ends with
            # a method-C-sized 6 mm clearance, not a coplanar duplicate bottom.
            union_pre = footprint
            before = union_pre.area
            footprint = union_pre.difference(occupied.buffer(.006, join_style='mitre'))
            union_trim = max(0.0, before - footprint.area)
            for area,row in curbs[role]:
                after_stair = area.difference(stair_union)
                stair_trim = max(0.0, area.area - after_stair.area)
                retained = area.intersection(footprint).area
                joint_trim = max(0.0, after_stair.area - retained)
                row['retained_m2'] = retained
                row['stair_trim_m2'] = stair_trim
                row['joint_trim_m2'] = joint_trim
                if joint_trim > 0:
                    row['joint_gap_m'] = .006
                    row['joint_rule'] = 'taller section continuous'
                if retained <= 1e-9:
                    row['status'] = 'trimmed'
                    if stair_trim > 0 and joint_trim > 0:
                        row['reason'] = 'occluded by stair footprint and taller curb section'
                    elif stair_trim > 0:
                        row['reason'] = 'occluded by stair footprint'
                    else:
                        row['reason'] = 'joint policy: fully covered by taller curb section'
            if union_trim > 0:
                joints.append(dict(role=role, scope='role union', union_trim_m2=union_trim,
                                   union_retained_m2=footprint.area, gap_m=.006,
                                   rule='taller section continuous'))
            occupied = unary_union([occupied, footprint])
        if not footprint.is_empty:meshes.append(_curb_solid(footprint,sampler,height,slot))
    mesh=combine(meshes)
    if len(mesh.faces):
        # Detail UV is derived after cleanup. No loose edges or near-duplicate solid vertices are retained.
        mesh=gc.clean_topology(mesh)
    return mesh, report, joints
