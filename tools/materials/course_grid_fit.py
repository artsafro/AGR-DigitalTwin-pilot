"""new-case: fixed-scale full-appearance-repeat folding for course-grid charts.

Consumed after course_grid_chart (existing uvlayout/facadeatlas cores). This is
only a containment candidate: joint masks and all-map appearance must be checked
before reuse. Never normalize, rotate, reflect, cut or silently drop a face.
"""
from __future__ import annotations
import math


def fold_chart(faces, *, repeat_m, texel_px_m, tile_px, border_px):
    """Fold each source face by whole periods into a shared brick field.

    Keep metre offsets until conversion to UV. A contained result is NOT a fit
    certificate: incompatible panel masks can still make this placement invalid.
    """
    for name, value in [('repeat_m',repeat_m),('texel_px_m',texel_px_m),('border_px',border_px)]:
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError(f'{name} must be finite and positive')
    if not 512 <= texel_px_m <= 1706:
        raise ValueError('texel_px_m outside legal 512..1706')
    if type(tile_px) is not int or tile_px not in (2048,4096):
        raise ValueError('tile_px must be 2048 or 4096')
    if border_px*2 >= tile_px:
        raise ValueError('border_px leaves no usable tile')
    if not isinstance(faces,list) or not faces:
        raise ValueError('faces must be nonempty')
    seen=set(); result=[]; unplaced=[]
    for f in faces:
        if not isinstance(f,dict) or not {'object','face','chart_m'} <= set(f):
            raise ValueError('partial face')
        key=(f['object'],f['face'])
        if not isinstance(key[0],str) or not key[0] or type(key[1]) is not int or key[1]<0:
            raise ValueError(f'invalid face key {key}')
        if key in seen:
            raise ValueError(f'duplicate face {key}')
        seen.add(key)
        points=f['chart_m']
        if not isinstance(points,list) or len(points)<3 or any(
            not isinstance(p,list) or len(p)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in p)
            for p in points):
            raise ValueError(f'invalid chart_m {key}')
        # Translation-invariant shoelace: large world origins must not cancel area.
        q=[[p[k]-points[0][k] for k in (0,1)] for p in points]
        area=abs(sum(q[i][0]*q[(i+1)%len(q)][1]-q[(i+1)%len(q)][0]*q[i][1] for i in range(len(q))))/2
        if area<=1e-12:
            raise ValueError(f'degenerate chart_m {key}')
        lo=[min(p[k] for p in points) for k in (0,1)]
        shift=[-math.floor(x/repeat_m)*repeat_m for x in lo]
        px=[[border_px+(p[k]+shift[k])*texel_px_m for k in (0,1)] for p in points]
        extent=[(max(p[k] for p in points)-lo[k])*texel_px_m for k in (0,1)]
        if any(p[k] < border_px-1e-9 or p[k] > tile_px-border_px+1e-9 for p in px for k in (0,1)):
            unplaced.append(list(key))
        result.append({'object':key[0],'face':key[1],'translation_m':shift,
                       'required_extent_px':extent,'uv':[[x/tile_px for x in p] for p in px]})
    return {'status':'fold_overflow' if unplaced else 'fold_contained_masks_unchecked',
            'passed':False,'faces':result,'unplaced':unplaced,'dropped_faces':[],
            'repeat_m':repeat_m,'texel_px_m':texel_px_m,'tile_px':tile_px,'border_px':border_px,
            'limitations':['joint mask equivalence, all-map sampling and padding unchecked',
                           'canonical fold only; overflow is not an impossibility proof']}
