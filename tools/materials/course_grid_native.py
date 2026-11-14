"""new-case: project saved/native positions into an existing fixed metre chart.

Stdlib-only bridge for Blender/Max Python. No packing, normalization, vertex
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
