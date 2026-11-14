"""new-case: source-traced planar partition at explicitly approved joint zones.

Consumes metre charts from course_grid_chart; fold_chart remains the brick packer.
No file writes, implicit seam permission, geometry movement or packing scale search.
"""
from __future__ import annotations

import math
import numpy as np
from shapely import constrained_delaunay_triangles, set_precision
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union


def _points(value, dim, name):
    if not isinstance(value,list) or len(value)<3 or any(
        not isinstance(p,list) or len(p)!=dim or any(isinstance(x,bool) or
        not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in value):
        raise ValueError(f'invalid {name}')
    return np.asarray(value,dtype=float)


def partition_joint_zones(row, zones):
    """Partition one planar source polygon; retain source identity and surface.

    zones are explicit chart-metre polygon footprints, not guessed edge classes.
    Refuse nonplanar/degenerate/holed outcomes instead of altering their surface.
    New segments are only shared brick/joint boundaries, never original edges.
    """
    if not isinstance(row,dict) or not {'object','face','chart_m','xyz','material_id'}<=set(row):
        raise ValueError('partial source face')
    key=[row['object'],row['face']]
    if not isinstance(key[0],str) or not key[0] or type(key[1]) is not int or key[1]<0:
        raise ValueError(f'invalid source key {key}')
    if row['material_id']!=1 or type(row['material_id']) is not int:
        raise ValueError(f'unsupported material_id {row["material_id"]}: {key}')
    uv=_points(row['chart_m'],2,'chart_m'); xyz=_points(row['xyz'],3,'xyz')
    if len(uv)!=len(xyz):raise ValueError(f'partial xyz {key}')
    poly=Polygon(uv)
    if not poly.is_valid or poly.area<=1e-12 or not poly.exterior.is_ccw:
        raise ValueError(f'degenerate/unsupported chart winding {key}')
    # Fit relative coordinates to avoid cancellation at real building coordinates.
    a=np.c_[uv-uv[0],np.ones(len(uv))]
    matrix=np.linalg.lstsq(a,xyz-xyz[0],rcond=None)[0]
    residual=float(np.max(np.linalg.norm(a@matrix-(xyz-xyz[0]),axis=1)))
    if not math.isfinite(residual):
        raise ValueError(f'nonfinite surface {key}')
    if residual>2e-5:
        # Retain original fan diagonal: clipping a best-fit plane would move
        # the surface. No new vertex lies off its original source triangle.
        children=[]
        for i in range(1,len(uv)-1):
            idx=[0,i,i+1]
            child=dict(row,chart_m=uv[idx].tolist(),xyz=xyz[idx].tolist())
            children.append(partition_joint_zones(child,zones))
        return dict(source=key,pieces=[p for c in children for p in c['pieces']],
                    new_segments=[s for c in children for s in c['new_segments']],
                    dropped_faces=[],source_area_m2=poly.area,
                    joint_area_m2=sum(c['joint_area_m2'] for c in children),
                    planar_fit_residual_m=residual,source_fan_retained=True,
                    passed=False,status='partition_only')
    if np.linalg.matrix_rank(matrix[:2])!=2:
        raise ValueError(f'degenerate surface {key}')
    if not isinstance(zones,list):raise ValueError('zones must be explicit list')
    # Canonicalize GEOS overlay arithmetic only (one picometre), never a texel
    # or modelling snap. Keep original input arrays for XYZ interpolation.
    poly=set_precision(poly,1e-12)
    clips=[]
    for zone in zones:
        z=Polygon(_points(zone,2,'zone'))
        if not z.is_valid or z.area<=1e-12:raise ValueError(f'degenerate zone {key}')
        z=set_precision(z,1e-12)
        clipped=poly.intersection(z)
        if not clipped.is_empty:clips.append(clipped)
    joint=unary_union(clips)
    brick=poly.difference(joint)
    pieces=[];numerical_fragments=[]
    for label,geometry in [(False,brick),(True,joint)]:
        geoms=[geometry] if geometry.geom_type=='Polygon' else list(geometry.geoms)
        simple=[]
        for p in geoms:
            if p.area<=0:continue
            if p.geom_type!='Polygon':raise ValueError(f'unsupported partition {key}')
            if len(p.interiors):
                # A polygon with a hole needs connectivity tessellation in a DCC.
                # Constrained triangulation preserves every joint perimeter; this
                # is recorded separately from the actual brick/joint cut paths.
                cells=list(constrained_delaunay_triangles(p).geoms)
                # Dissolve tessellation edges wherever a single valid hole-free
                # n-gon is possible. Do not carry tiny triangulation slivers into
                # the packer or pretend that each diagonal is a panel-joint cut.
                changed=True
                while changed:
                    changed=False
                    for i in range(len(cells)):
                        for j in range(i+1,len(cells)):
                            if cells[i].boundary.intersection(cells[j].boundary).length<=0:continue
                            merged=cells[i].union(cells[j])
                            if merged.geom_type=='Polygon' and merged.is_valid and not merged.interiors:
                                cells[i]=merged;cells.pop(j);changed=True;break
                        if changed:break
                simple.extend(cells)
            else:simple.append(p)
        for p in simple:
            if p.area<=max(1e-12,poly.length*1e-12*16):
                numerical_fragments.append(dict(joint=label,area_m2=p.area,
                    chart_m=[list(c) for c in p.exterior.coords[:-1]],
                    reason='sub-overlay-area fragment; bounded below'))
                continue
            p=p.simplify(4e-12,preserve_topology=True)
            points=np.asarray(orient(p,sign=1).exterior.coords[:-1])
            # Preserve source corners exactly; interpolate new vertices in source
            # fan triangles, not the best-fit plane (source float32 may warp).
            world=[]
            for point in points:
                found=None
                for i in range(1,len(uv)-1):
                    tri=uv[[0,i,i+1]]
                    m=np.column_stack([tri[1]-tri[0],tri[2]-tri[0]])
                    if abs(np.linalg.det(m))<1e-14:continue
                    ab=np.linalg.solve(m,point-tri[0])
                    if min(ab)>=-1e-7 and sum(ab)<=1+1e-7:
                        found=xyz[0]+ab[0]*(xyz[i]-xyz[0])+ab[1]*(xyz[i+1]-xyz[0]);break
                if found is None:raise ValueError(f'unmapped partition point {key}: {point}')
                world.append(found.tolist())
            pieces.append(dict(source=key.copy(),joint=label,chart_m=points.tolist(),xyz=world))
    covered=unary_union([Polygon(p['chart_m']) for p in pieces])
    coverage_error=poly.symmetric_difference(covered).area
    overlay_area_bound=max(1e-12,poly.length*1e-12*16)
    if coverage_error>overlay_area_bound or sum(f['area_m2'] for f in numerical_fragments)>overlay_area_bound:
        raise ValueError(f'incomplete partition {key}')
    # Overlay can retain zero-area lines in a GeometryCollection. Derive the
    # surface boundary from actual polygon pieces, not GEOS collection.boundary
    # (which is None). Zero-area contacts are not mesh faces.
    brick=unary_union([Polygon(p['chart_m']) for p in pieces if not p['joint']])
    joint=unary_union([Polygon(p['chart_m']) for p in pieces if p['joint']])
    boundary=brick.boundary.intersection(joint.boundary) if not brick.is_empty and not joint.is_empty else None
    segments=[]
    for line in ([] if boundary is None else [boundary] if boundary.geom_type=='LineString' else getattr(boundary,'geoms',[])):
        if line.geom_type=='LineString' and line.length>1e-10:
            coords=list(line.coords)
            segments.extend([[list(a),list(b)] for a,b in zip(coords,coords[1:])])
    return dict(source=key,pieces=pieces,new_segments=segments,dropped_faces=[],
                source_area_m2=poly.area,joint_area_m2=joint.area,
                planar_fit_residual_m=residual,overlay_grid_m=1e-12,
                numerical_fragments=numerical_fragments,coverage_error_m2=coverage_error,
                overlay_area_bound_m2=overlay_area_bound,
                passed=False,status='partition_only')


def native_piece_cells(piece):
    """Keep convex triangles/quads; make larger/concave chart cells explicit.

    Use only existing corners, retaining XYZ and source lineage. This avoids
    native tessellation selecting a zero-UV-area triangle from collinear points.
    """
    xy=_points(piece.get('chart_m'),2,'chart_m');world=_points(piece.get('xyz'),3,'xyz')
    if len(xy)!=len(world):raise ValueError('partial native piece')
    poly=Polygon(xy)
    if not poly.is_valid or poly.area<=1e-12 or not poly.exterior.is_ccw:raise ValueError('invalid native piece')
    original_poly=poly
    # Near-collinear boundary corners below the real-coordinate float32 storage
    # envelope can otherwise become native zero-area triangles. Remove only
    # those existing corners; never move retained XYZ or hide the bound.
    poly=orient(poly.simplify(2e-5,preserve_topology=True),sign=1)
    retained=np.asarray(poly.exterior.coords[:-1])
    removed=[p.tolist() for p in xy if not any(np.linalg.norm(p-q)<1e-10 for q in retained)]
    metadata=dict(piece,native_corner_error_bound_m=2e-5,native_removed_corners=removed,
                  native_area_change_m2=abs(original_poly.area-poly.area))
    if len(retained)<=4 and poly.convex_hull.area-poly.area<=1e-12:
        ids=[int(np.argmin(np.linalg.norm(xy-q,axis=1))) for q in retained]
        return [dict(metadata,chart_m=retained.tolist(),xyz=world[ids].tolist())]
    cells=list(constrained_delaunay_triangles(poly).geoms)
    # Merge adjacent triangles into convex quads only, preserving boundaries.
    changed=True
    while changed:
        changed=False
        for i in range(len(cells)):
            for j in range(i+1,len(cells)):
                if cells[i].boundary.intersection(cells[j].boundary).length<=0:continue
                merged=cells[i].union(cells[j])
                if merged.geom_type=='Polygon' and len(merged.exterior.coords)==5 and merged.convex_hull.area-merged.area<=1e-12:
                    corners=list(merged.exterior.coords[:-1])
                    span=max(math.dist(a,b) for a in corners for b in corners)
                    # Both possible native diagonals must be nonsingular. Three
                    # collinear corners can form a convex four-point boundary,
                    # but Blender may choose its zero-area fan.
                    if min(Polygon([corners[k],corners[(k+1)%4],corners[(k+2)%4]]).area for k in range(4))<=span*1e-5:
                        continue
                    cells[i]=merged;cells.pop(j);changed=True;break
            if changed:break
    out=[];collapsed_native_cells=[]
    for cell in cells:
        if cell.area<=max(1e-12,poly.length*1e-12*16):
            collapsed_native_cells.append(dict(area_m2=cell.area,reason='sub-overlay-area collinear connectivity cell'))
            continue
        points=np.asarray(orient(cell,sign=1).exterior.coords[:-1]);indices=[]
        for q in points:
            matches=np.flatnonzero(np.linalg.norm(xy-q,axis=1)<1e-10)
            if not len(matches):raise ValueError('unmapped/ambiguous native corner')
            if len(matches)>1 and max(np.linalg.norm(world[i]-world[matches[0]]) for i in matches)>1e-9:
                raise ValueError('ambiguous native corner has distinct XYZ')
            indices.append(int(matches[0]))
        canonical=xy[indices]
        if len(set(indices))<3:
            if cell.area>poly.length*1e-10:raise ValueError('collapsed native cell exceeds identity bound')
            collapsed_native_cells.append(dict(area_m2=cell.area,reason='sub-nanometre proven XYZ identity'))
            continue
        out.append(dict(metadata,chart_m=canonical.tolist(),xyz=world[indices].tolist(),
                        native_collapsed_cells=collapsed_native_cells,native_identity_bound_m=1e-9))
    if abs(sum(Polygon(c['chart_m']).area for c in out)-poly.area)>max(1e-12,poly.area*1e-10):raise ValueError('incomplete native tessellation')
    return out


def edge_joint_zone(chart_m, indices, *, width_m):
    """Exact-width inward strip through a convex source edge.

    Extend longitudinal endpoints beyond this face before clipping so a slightly
    slanted adjacent edge cannot leave a microscopic wedge. Not a geometry move.
    """
    xy=_points(chart_m,2,'chart_m');poly=Polygon(xy)
    if not poly.is_valid or poly.area<=1e-12 or abs(poly.convex_hull.area-poly.area)>1e-10:
        raise ValueError('edge joint requires a nondegenerate convex face')
    if not isinstance(indices,list) or len(indices)!=2 or any(type(i) is not int or i<0 or i>=len(xy) for i in indices) or indices[0]==indices[1]:
        raise ValueError('invalid edge indices')
    if (indices[0]-indices[1])%len(xy) not in (1,len(xy)-1):raise ValueError('not a source edge')
    if isinstance(width_m,bool) or not isinstance(width_m,(int,float)) or not math.isfinite(width_m) or width_m<=0:
        raise ValueError('width_m must be finite and positive')
    a,b=xy[indices];direction=b-a;length=float(np.linalg.norm(direction))
    if length<=1e-12:raise ValueError('degenerate source edge')
    direction/=length;n=np.array([-direction[1],direction[0]])
    if np.dot(xy.mean(0)-(a+b)/2,n)<0:n=-n
    extension=float(np.linalg.norm(np.ptp(xy,axis=0)))+width_m
    a=a-direction*extension;b=b+direction*extension
    return [a.tolist(),b.tolist(),(b+n*width_m).tolist(),(a+n*width_m).tolist()]


def layout_joint_partition(partitions, *, repeat_m, texel_px_m, tile_px, border_px, gap_px):
    """Fold brick by full repeat; translate constant joint polygons into a
    disjoint field. Caller must declare constant D/ERM/N joint content; this
    is not source-normal groove equivalence and remains a candidate.
    """
    from tools.materials.course_grid_fit import fold_chart
    if not isinstance(partitions,list) or not partitions:raise ValueError('empty partitions')
    if isinstance(gap_px,bool) or not isinstance(gap_px,(int,float)) or not math.isfinite(gap_px) or gap_px<32:
        raise ValueError('gap_px must be finite and >=32')
    pieces=[];seen=set()
    for r in partitions:
        if not isinstance(r,dict) or not r.get('pieces') or r.get('dropped_faces')!=[]:
            raise ValueError('partial partition')
        key=tuple(r['source'])
        if key in seen:raise ValueError(f'duplicate source {key}')
        seen.add(key)
        for p in r['pieces']:
            if p.get('source')!=r['source'] or type(p.get('joint')) is not bool:
                raise ValueError(f'unmapped piece {key}')
            _points(p.get('xyz'),3,'xyz')
            pieces.append(dict(p,object=key[0],face=len(pieces)))
    brick=[p for p in pieces if not p['joint']]
    if not brick:raise ValueError('no brick field')
    f=fold_chart(brick,repeat_m=repeat_m,texel_px_m=texel_px_m,tile_px=tile_px,border_px=border_px)
    by_id={p['face']:p for p in f['faces']}
    start=math.ceil(max(q[0]*tile_px for p in f['faces'] for q in p['uv']))+gap_px
    faces=[];unplaced=list(f['unplaced'])
    for p in pieces:
        if not p['joint']:
            q=by_id[p['face']]
            trans=[q['translation_m'][k]+border_px/texel_px_m for k in (0,1)]
            uv=q['uv']
        else:
            xy=_points(p['chart_m'],2,'chart_m')
            trans=([start/texel_px_m,border_px/texel_px_m]-xy.min(0)).tolist()
            uv=((xy+trans)*texel_px_m/tile_px).tolist()
            if any(v*tile_px<border_px-1e-8 or v*tile_px>tile_px-border_px+1e-8 for q in uv for v in q):
                unplaced.append([p['object'],p['face']])
        faces.append(dict(p,uv=uv,translation_m=trans))
    return dict(status='partition_layout_overflow' if unplaced else 'partition_layout_candidate',passed=False,
                faces=faces,unplaced=unplaced,dropped_faces=[],joint_field_min_px=[start,border_px],
                texel_px_m=texel_px_m,tile_px=tile_px,border_px=border_px,gap_px=gap_px,repeat_m=repeat_m,
                limitations=['constant joint D/ERM/N only; source groove normals not preserved',
                             'export, density, topology, masks and human acceptance remain open'])
