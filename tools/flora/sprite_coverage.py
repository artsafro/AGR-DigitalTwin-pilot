"""Diagnostic geometric sprite coverage, not botanical or delivery acceptance.

Pattern: n/a | new-case: #369 bbox coverage with explicit unknown roles/cells.
The bbox metric implements Artem's 2026-10-20 decision, not opacity density.
"""
import math
import numpy as np
from PIL import Image, ImageFilter


def uv_components(faces, count):
    if not faces or type(count) is not int or count<=0:raise ValueError('nonempty UV topology required')
    parent=list(range(count))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for face in faces:
        if len(face)!=3 or any(type(i) is not int or not 0<=i<count for i in face):raise ValueError('invalid UV face')
        for a,b in zip(face,face[1:]):parent[root(a)]=root(b)
    groups={}
    for i,f in enumerate(faces):groups.setdefault(root(f[0]),[]).append(i)
    return list(groups.values())


def bbox(mask):
    y,x=np.nonzero(mask)
    if not len(x):raise ValueError('empty opaque sprite')
    return (int(x.min()),int(y.min()),int(x.max())+1,int(y.max())+1)


def sprite_cells(alpha):
    """Independent alpha-only guillotine split at >=1.5%-image empty gutters.

    Never uses UV coordinates. Touching sprites remain a single ambiguous cell;
    this is a segmentation candidate, not a guaranteed authored atlas partition.
    """
    a=np.asarray(alpha)
    if a.ndim!=2 or not np.isfinite(a).all() or not a.any():raise ValueError('nonempty finite opacity required')
    result=[];height,width=a.shape
    def split(box):
        x0,y0,x1,y1=box;part=a[y0:y1,x0:x1];options=[]
        for axis,projection,scale in [(0,part.any(axis=0),width),(1,part.any(axis=1),height)]:
            zeros=~projection
            edges=np.diff(np.r_[False,zeros,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
            for start,end in zip(starts,ends):
                if start>0 and end<len(projection) and end-start>=max(2,math.ceil(scale*.015)):
                    options.append(((end-start)/scale,axis,(int(start)+int(end))//2))
        if not options:result.append(box);return
        _,axis,cut=max(options)
        if axis==0: boxes=[(x0,y0,x0+cut,y1),(x0+cut,y0,x1,y1)]
        else:boxes=[(x0,y0,x1,y0+cut),(x0,y0+cut,x1,y1)]
        for x,y,X,Y in boxes:
            l,t,r,b=bbox(a[y:Y,x:X]);split((x+l,y+t,x+r,y+b))
    split(bbox(a));return result


def coverage(island, alpha, profile, sprite_box):
    m=np.asarray(island);a=np.asarray(alpha)
    if profile not in ('NPM','VPM'):raise ValueError('unsupported profile')
    if m.ndim!=2 or m.shape!=a.shape or not m.size or not np.isfinite(m).all() or not np.isfinite(a).all():raise ValueError('finite same-size masks required')
    m=m.astype(bool);a=a.astype(bool)
    if not m.any() or not a.any():raise ValueError('empty island or opacity')
    if len(sprite_box)!=4 or any(type(v) is not int for v in sprite_box):raise ValueError('integer sprite bbox required')
    x,y,X,Y=sprite_box;h,w=a.shape
    if not 0<=x<X<=w or not 0<=y<Y<=h:raise ValueError('invalid sprite bbox')
    box=np.zeros_like(a);box[y:Y,x:X]=True
    area=int(m.sum());boxarea=(X-x)*(Y-y)
    neighbour=int((a & ~box & m).sum())
    support=a & box
    # Boolean 3x3 dilation avoids Pillow's very slow binary MaxFilter on 4K atlases.
    padded=np.pad(m,1)
    dilated=np.zeros_like(m)
    for dy in range(3):
        for dx in range(3):dilated |= padded[dy:dy+h,dx:dx+w]
    clipped=int((support & ~dilated).sum())
    score=int((m & box).sum())/boxarea if profile=='VPM' else boxarea/area
    passed=(.80<=score<=.95 and (profile!='NPM' or clipped==0))
    if profile=='VPM' and score>.95:passed=neighbour==0
    return {'score':score,'pass':bool(passed),'island_area_px':area,'sprite_bbox_area_px':boxarea,
            'clipped_opaque_px_tolerance_1':clipped,'neighbour_opaque_px':neighbour,
            'opaque_density':int((m&a).sum())/area}


def island_role(vertices, object_height, profile):
    v=np.asarray(vertices,dtype=float)
    if v.ndim!=2 or v.shape[1:]!=(3,) or len(v)<3 or not np.isfinite(v).all() or not math.isfinite(object_height) or object_height<=0:
        return 'unknown','invalid or missing geometry'
    v=np.unique(v,axis=0)
    if len(v)<3:return 'unknown','degenerate geometry'
    s=np.linalg.svd(v-v.mean(axis=0),compute_uv=False)
    if len(s)<3 or s[1]<=1e-10:return 'unknown','zero-area geometry'
    planar=s[2]<=s[0]*1e-3
    span=np.ptp(v,axis=0)
    if planar and profile=='NPM' and span[2]>=.75*object_height:
        return 'star_plane','planar component spans >=75% of object height (candidate; star arrangement checked separately)'
    if planar:return 'foliage','planar geometry component; leaf-card candidate, not botanical classification'
    if span[2]>=2*max(span[0],span[1]) and span[2]>=.2*object_height:
        return 'trunk','non-planar vertically elongated component, >=20% object height'
    return 'unknown','non-planar component is neither a card nor a vertically elongated trunk'
