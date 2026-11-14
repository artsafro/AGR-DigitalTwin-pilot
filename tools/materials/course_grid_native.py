"""new-case: project saved/native positions into an existing fixed metre chart.

Native bridge for Blender/Max Python (NumPy only in float32 encoding). No packing, normalization, vertex
motion or guessed phase; the reference first triangle freezes the source frame.
"""
import math


def project_saved_points(points, reference_xyz, reference_chart):
    """Project actual stored XYZ, not ideal pre-cast cutter coordinates.

    Retain the source chart origin and its first-triangle linear map. This
    avoids interpreting native float32 storage noise as UV stretch in 10-mm
    strips. The caller must measure residuals and all directional densities.
    """
    for rows,dim,name in [(points,3,'points'),(reference_xyz,3,'reference_xyz'),(reference_chart,2,'reference_chart')]:
        if not isinstance(rows,list) or not rows or any(not isinstance(p,list) or len(p)!=dim or any(
            isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p) for p in rows):
            raise ValueError(f'invalid {name}')
    if len(reference_xyz)<3 or len(reference_xyz)!=len(reference_chart):raise ValueError('partial reference frame')
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    sub=lambda a,b:[x-y for x,y in zip(a,b)]
    e,f=[sub(p,reference_xyz[0]) for p in reference_xyz[1:3]]
    aa,ab,bb=dot(e,e),dot(e,f),dot(f,f)
    determinant=aa*bb-ab*ab
    if not math.isfinite(determinant) or determinant<=max(aa*bb*1e-14,1e-24):raise ValueError('degenerate source frame')
    u,v=[sub(p,reference_chart[0]) for p in reference_chart[1:3]]
    out=[]
    for point in points:
        delta=sub(point,reference_xyz[0]);a,b=dot(delta,e),dot(delta,f)
        s=(a*bb-b*ab)/determinant;t=(b*aa-a*ab)/determinant
        q=[reference_chart[0][k]+s*u[k]+t*v[k] for k in (0,1)]
        if not all(math.isfinite(x) for x in q):raise ValueError('nonfinite projected chart')
        out.append(q)
    return out


def rigid_triangle_uv(xyz, reference_uv, *, texel_px_m, tile_px):
    """Rectify an explicitly authorized minor triangle at the frozen density.

    Keep its longest source edge's UV heading and anchor; unfold its true stored
    surface, not its projection onto a neighbouring face. No pack rotation.
    """
    if len(xyz)!=3 or len(reference_uv)!=3:raise ValueError('triangle required')
    project_saved_points(xyz,xyz,reference_uv)  # finite/degenerate frame checks
    if isinstance(texel_px_m,bool) or not isinstance(texel_px_m,(int,float)) or not math.isfinite(texel_px_m) or not 512<=texel_px_m<=1706:
        raise ValueError('illegal texel_px_m')
    if type(tile_px) is not int or tile_px not in (2048,4096):raise ValueError('unsupported tile_px')
    sub=lambda a,b:[x-y for x,y in zip(a,b)]
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    i,j=max(((0,1),(1,2),(2,0)),key=lambda ij:math.dist(xyz[ij[0]],xyz[ij[1]]))
    k=3-i-j
    edge=sub(xyz[j],xyz[i]);length=math.sqrt(dot(edge,edge));direction=[v/length for v in edge]
    off=sub(xyz[k],xyz[i]);s=dot(off,direction);height=math.sqrt(sum((off[d]-s*direction[d])**2 for d in range(3)))
    heading=sub(reference_uv[j],reference_uv[i]);size=math.hypot(*heading)
    if size<=0 or height<=0:raise ValueError('degenerate triangle heading')
    u=[v/size for v in heading];v=[-u[1],u[0]]
    if dot(sub(reference_uv[k],reference_uv[i]),v)<0:v=[-a for a in v]
    factor=texel_px_m/tile_px
    out=[list(q) for q in reference_uv];out[i]=list(reference_uv[i])
    out[j]=[out[i][d]+length*u[d]*factor for d in (0,1)]
    out[k]=[out[i][d]+(s*u[d]+height*v[d])*factor for d in (0,1)]
    return out


def encode_triangle_uv(xyz, ideal_uv, *, tile_px):
    """Choose a directed float32 encoding within 0.01 pixel of a rigid chart.

    Fixed-density geometry and packing are already frozen. Search only the two
    neighbouring float32 representable values per coordinate, not pixels or a
    density scale. Refuse if format quantization cannot satisfy legal bounds.
    """
    import itertools
    import numpy as np
    if type(tile_px) is not int or tile_px not in (2048,4096):raise ValueError('unsupported tile_px')
    if len(xyz)!=3 or len(ideal_uv)!=3:raise ValueError('triangle required')
    project_saved_points(xyz,xyz,ideal_uv)
    x=np.asarray(xyz,dtype=float);ideal=np.asarray(ideal_uv,dtype=float)
    e=x[1:]-x[0];a=e[0]/np.linalg.norm(e[0]);n=np.cross(e[0],e[1]);n/=np.linalg.norm(n);b=np.cross(n,a)
    physical=np.c_[e@a,e@b];inverse=np.linalg.inv(physical)
    rounded=ideal.astype(np.float32).ravel()
    if not np.isfinite(rounded).all():raise ValueError('float32 UV overflow')
    for radius in (1,2):
        choices=[]
        for v in rounded:
            low=[];high=[];lo=v;hi=v
            for _ in range(radius):
                lo=np.nextafter(lo,np.float32(-np.inf));hi=np.nextafter(hi,np.float32(np.inf));low.append(lo);high.append(hi)
            choices.append(low[::-1]+[v]+high)
        candidates=np.asarray(list(itertools.product(*choices)),dtype=float).reshape(-1,3,2)
        delta=(candidates[:,1:]-candidates[:,:1])*tile_px
        jac=np.einsum('ij,njk->nik',inverse,delta)
        singular=np.linalg.svd(jac,compute_uv=False)
        errors=np.max(np.linalg.norm(candidates-ideal,axis=2),axis=1)*tile_px
        ok=(singular[:,1]>=512)&(singular[:,0]<=1706)&(singular[:,0]/singular[:,1]<=1.02)&(errors<=.01)
        ok &= (np.linalg.det(delta)>0)&(candidates.min(axis=(1,2))>=0)&(candidates.max(axis=(1,2))<=1)
        good=np.flatnonzero(ok)
        if len(good):
            best=min(good,key=lambda i:(errors[i],float(np.sum((candidates[i]-ideal)**2))))
            return dict(uv=candidates[best].tolist(),singular_px_m=singular[best].tolist(),
                        max_encoding_error_px=float(errors[best]),ulp_radius=radius)
    raise ValueError('native float32 encoding exceeds density/anisotropy/subpixel budget')
