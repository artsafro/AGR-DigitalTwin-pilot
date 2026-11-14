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


def fit_mask_samples(faces, masks, *, repeat_m, texel_px_m, tile_px, border_px, seed):
    """Greedy full-repeat placement with explicit required/forbidden joint samples.

    Samples are chart metres and a boolean panel-joint signature. This necessary
    binary condition is deliberately not an all-map equivalence certificate.
    Try every contained lattice translation for each face, never overwrite an
    incompatible sample. A failure is heuristic, not a minimum-tile theorem.
    """
    import random
    import numpy as np
    folded=fold_chart(faces,repeat_m=repeat_m,texel_px_m=texel_px_m,
                      tile_px=tile_px,border_px=border_px)
    if type(seed) is not int or seed<0:
        raise ValueError('seed must be nonnegative integer')
    if not isinstance(masks,list) or len(masks)!=len(faces):
        raise ValueError('mask mapping must cover every face')
    by_key={(f['object'],f['face']):f for f in faces}
    mapped={}
    for row in masks:
        if not isinstance(row,dict) or set(row)!={'object','face','samples'}:
            raise ValueError('partial/unsupported mask entry')
        key=(row['object'],row['face'])
        if not isinstance(key[0],str) or type(key[1]) is not int or key[1]<0:
            raise ValueError(f'invalid mask key {key}')
        if key not in by_key or key in mapped:
            raise ValueError(f'unmapped or duplicate mask {key}')
        ss=row['samples']
        if not isinstance(ss,list) or not ss or any(not isinstance(s,list) or len(s)!=3 or type(s[2]) is not bool or
            any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in s[:2]) for s in ss):
            raise ValueError(f'invalid samples {key}')
        arr=np.asarray(ss,dtype=float)
        poly=np.asarray(by_key[key]['chart_m'],dtype=float)
        # Translate first to avoid cancellation at large source-world origins.
        q=arr[:,:2]-poly[0]; poly=poly-poly[0]
        inside=np.zeros(len(q),dtype=bool); boundary=inside.copy()
        for a,b in zip(poly,np.roll(poly,-1,axis=0)):
            edge=b-a; rel=q-a
            cross=edge[0]*rel[:,1]-edge[1]*rel[:,0]
            along=rel@edge
            boundary |= (np.abs(cross)<=1e-9*max(1.,np.linalg.norm(edge))) & (along>=-1e-9) & (along<=edge@edge+1e-9)
            if edge[1]!=0:
                inside ^= ((a[1]>q[:,1])!=(b[1]>q[:,1])) & (q[:,0] < a[0]+(q[:,1]-a[1])*edge[0]/edge[1])
        if not np.all(inside|boundary):
            raise ValueError(f'mask sample outside source face {key}')
        mapped[key]=arr
    canvas=np.full((tile_px,tile_px),-1,dtype=np.int8)
    owners=np.full((tile_px,tile_px),-1,dtype=np.int32)
    ordered=list(folded['faces'])
    if seed==0:
        ordered.sort(key=lambda f: (-len(mapped[(f['object'],f['face'])]),f['object'],f['face']))
    elif seed==1:
        ordered.sort(key=lambda f: (-math.prod(f['required_extent_px']),f['object'],f['face']))
    else:
        random.Random(seed).shuffle(ordered)
    placed=[]; unplaced=[]; witnesses=[]
    for f in ordered:
        key=(f['object'],f['face']); ss=mapped[key]
        shift=f['translation_m']
        bbox=np.asarray(f['uv'])*tile_px
        room=[int(math.floor((tile_px-border_px-bbox[:,k].max()+1e-9)/(repeat_m*texel_px_m))) for k in (0,1)]
        candidates=[]; best_bad=None
        for j in range(max(-1,room[1])+1):
            for i in range(max(-1,room[0])+1):
                trans=np.asarray(shift)+np.array([i,j])*repeat_m
                xy=np.floor(border_px+(ss[:,:2]+trans)*texel_px_m).astype(np.int64)
                if np.any(xy<0) or np.any(xy>=tile_px):
                    raise ValueError(f'sample outside tile/face {key}')
                labels=ss[:,2].astype(np.int8)
                linear=xy[:,1]*tile_px+xy[:,0]
                # Opposite signatures within one raster pixel are ambiguous: reject
                # this candidate instead of letting numpy last-writer win.
                indices=np.argsort(linear); ids=linear[indices]; vals=labels[indices]
                internal=(ids[1:]==ids[:-1]) & (vals[1:]!=vals[:-1])
                old=canvas[xy[:,1],xy[:,0]]
                bad=(old>=0)&(old!=labels)
                count=int(bad.sum()+internal.sum())
                if count:
                    if best_bad is None or count<best_bad['conflict_pixels']:
                        q=int(np.flatnonzero(bad)[0]) if bad.any() else int(indices[np.flatnonzero(internal)[0]])
                        best_bad={'object':key[0],'face':key[1],'conflict_pixels':count,
                                  'pixel':xy[q].tolist(),'required_joint':bool(labels[q]),
                                  'existing_joint':int(old[q]),'translation_m':trans.tolist(),
                                  'existing_face':([placed[int(owners[xy[q,1],xy[q,0]])][k] for k in ('object','face')]
                                                   if old[q]>=0 else None)}
                    continue
                candidates.append((int((old<0).sum()),i,j,trans,xy,labels))
        if not candidates:
            unplaced.append(list(key))
            witnesses.append(best_bad or {'object':key[0],'face':key[1],'conflict_pixels':0,'reason':'no contained lattice translation'})
            continue
        _,i,j,trans,xy,labels=min(candidates,key=lambda c:c[:3])
        owners[xy[:,1],xy[:,0]]=len(placed)
        canvas[xy[:,1],xy[:,0]]=labels
        uv=(bbox+np.array([i,j])*repeat_m*texel_px_m)/tile_px
        placed.append(dict(f,translation_m=trans.tolist(),uv=uv.tolist()))
    return {'status':'sample_fit_exhausted' if unplaced else 'sample_fit_masks_only',
            'passed':False,'faces':placed,'unplaced':unplaced,'witnesses':witnesses,
            'dropped_faces':[], 'seed':seed,'input_faces':len(faces),
            'occupied_sample_pixels':int((canvas>=0).sum()),
            'limitations':['greedy full-repeat lattice search, not global infeasibility proof',
                           'sparse binary joint samples only; full D/ERM/N, padding and export QA unchecked']}

