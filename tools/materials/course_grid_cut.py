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
    pieces=[]
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
    if poly.symmetric_difference(covered).area>max(1e-12,poly.area*1e-10):
        raise ValueError(f'incomplete partition {key}')
    boundary=brick.boundary.intersection(joint.boundary) if not brick.is_empty and not joint.is_empty else None
    segments=[]
    for line in ([] if boundary is None else [boundary] if boundary.geom_type=='LineString' else getattr(boundary,'geoms',[])):
        if line.geom_type=='LineString' and line.length>1e-10:
            coords=list(line.coords)
            segments.extend([[list(a),list(b)] for a,b in zip(coords,coords[1:])])
    return dict(source=key,pieces=pieces,new_segments=segments,dropped_faces=[],
                source_area_m2=poly.area,joint_area_m2=joint.area,
                planar_fit_residual_m=residual,overlay_grid_m=1e-12,
                passed=False,status='partition_only')
