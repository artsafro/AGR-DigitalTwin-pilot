"""new-case: source-bound joint appearance sampling before atlas reuse.

RGB is sampled in the source PNG's declared encoding. This is not a colour-space
conversion, tangent-frame Normal transport, or an appearance/geometry certificate.
A caller must compare/transport frames before reusing the samples in a new UV basis.
"""
from __future__ import annotations

import numpy as np
from shapely.geometry import Point, Polygon


def _xy(value, name, minimum):
    if not isinstance(value,list) or len(value)<minimum or any(
        not isinstance(p,list) or len(p)!=2 or any(
            isinstance(x,bool) or not isinstance(x,(int,float)) or not np.isfinite(x)
            for x in p) for p in value):
        raise ValueError(f'invalid {name}')
    return np.asarray(value,dtype=float)


def sample_chart_rgb(image, source_uv, chart_m, points_m):
    """Bilinear source PNG RGB at chart points; reject outside/partial frames.

    UV V increases upward; PNG rows downward; UV boundaries use edge-clamping,
    never wrap into unrelated atlas content. Affine-fit residual is in metres
    and must be <=20 micrometres, matching the source-frame readback envelope.
    Empty sample requests are errors, not evidence of appearance coverage.
    """
    if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.ndim!=3 or image.shape[2]!=3 or min(image.shape[:2])<1:
        raise ValueError('unsupported source RGB image')
    uv=_xy(source_uv,'source_uv',3)
    chart=_xy(chart_m,'chart_m',3)
    points=_xy(points_m,'points_m',1)
    if len(chart)!=len(uv):raise ValueError('partial source UV/chart')
    domain=Polygon(chart);uv_domain=Polygon(uv)
    if not domain.is_valid or domain.area<=1e-12 or not uv_domain.is_valid or uv_domain.area<=1e-16 or uv.min()<0 or uv.max()>1:
        raise ValueError('unsupported source UV/chart domain')
    if any(not domain.buffer(1e-10).covers(Point(p)) for p in points):
        raise ValueError('sample outside source face')
    # Centre both frames to avoid loss of precision on long unrolled perimeters.
    matrix=np.linalg.lstsq(np.c_[uv-uv[0],np.ones(len(uv))],chart-chart[0],rcond=None)[0]
    if np.linalg.matrix_rank(matrix[:2])!=2 or np.max(np.linalg.norm(np.c_[uv-uv[0],np.ones(len(uv))]@matrix-(chart-chart[0]),axis=1))>2e-5:
        raise ValueError('unsupported nonaffine source UV frame')
    sampled_uv=(points-chart[0]-matrix[2])@np.linalg.inv(matrix[:2])+uv[0]
    if not np.isfinite(sampled_uv).all() or sampled_uv.min() < -1e-8 or sampled_uv.max()>1+1e-8:
        raise ValueError('sample outside source image')
    h,w=image.shape[:2]
    x=np.clip(sampled_uv[:,0]*w-.5,0,w-1)
    y=np.clip((1-sampled_uv[:,1])*h-.5,0,h-1)
    ix=np.floor(x).astype(int);iy=np.floor(y).astype(int)
    fx=(x-ix)[:,None];fy=(y-iy)[:,None]
    a=image[iy,ix].astype(float);b=image[iy,np.minimum(ix+1,w-1)].astype(float)
    c=image[np.minimum(iy+1,h-1),ix].astype(float);d=image[np.minimum(iy+1,h-1),np.minimum(ix+1,w-1)].astype(float)
    return ((a*(1-fx)+b*fx)*(1-fy)+(c*(1-fx)+d*fx)*fy).tolist()


def audit_sample_reuse(records, *, max_rgb_error):
    """Falsify equal-texel reuse with explicit D/ERM/Normal sample owners.

    Caller supplies samples at the SAME output pixel centre, in a common
    declared colour/tangent frame. Conflicts are complete pairwise witnesses,
    not first-entry wins. Even a compatible finite set never gives passed=True.
    """
    if isinstance(max_rgb_error,bool) or not isinstance(max_rgb_error,(int,float)) or not np.isfinite(max_rgb_error) or not 0<=max_rgb_error<=255:
        raise ValueError('invalid max_rgb_error')
    if not isinstance(records,list) or not records:raise ValueError('empty samples')
    roles={'Diffuse','ERM','Normal'};seen=set();pixels={}
    for r in records:
        if not isinstance(r,dict) or set(r)!={'owner','pixel','maps'}:raise ValueError('partial sample')
        owner=r['owner'];pixel=r['pixel'];maps=r['maps']
        if not isinstance(owner,list) or len(owner)!=3 or not isinstance(owner[0],str) or not owner[0] or any(type(v) is not int or v<0 for v in owner[1:]):raise ValueError(f'invalid owner {owner}')
        if tuple(owner) in seen:raise ValueError(f'duplicate owner {owner}')
        seen.add(tuple(owner))
        if not isinstance(pixel,list) or len(pixel)!=2 or any(type(v) is not int or v<0 for v in pixel):raise ValueError('invalid output pixel')
        if not isinstance(maps,dict) or set(maps)!=roles:raise ValueError(f'unmapped roles {list(maps) if isinstance(maps,dict) else maps}')
        for role,colour in maps.items():
            if not isinstance(colour,list) or len(colour)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not np.isfinite(x) or not 0<=x<=255 for x in colour):raise ValueError(f'invalid {role} RGB')
        pixels.setdefault(tuple(pixel),[]).append(r)
    conflicts=[]
    for pixel,owners in pixels.items():
        for i,a in enumerate(owners):
            for b in owners[i+1:]:
                for role in sorted(roles):
                    delta=float(np.max(np.abs(np.asarray(a['maps'][role])-b['maps'][role])))
                    if delta>max_rgb_error:
                        conflicts.append(dict(pixel=list(pixel),role=role,owners=[a['owner'],b['owner']],max_rgb_delta=delta))
    return dict(passed=False,compatible=not conflicts,samples=len(records),texels=len(pixels),conflicts=conflicts,
                limitation='finite same-pixel samples only; caller owns frame transport and full coverage')
