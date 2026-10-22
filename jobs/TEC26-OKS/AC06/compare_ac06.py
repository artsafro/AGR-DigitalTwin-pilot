"""new-case: AC06 slide39/40 pixel-counted, contrast-gated facade comparisons.

Uses AC08 v010 joint_count.runs and camera metadata, adapted to two slides,
gabled blue/grey sandwich fields and separate glass. Counts come from actual
pixels, never the spec's expected count. Regular vertical strokes are extracted
in 2-D so labels, windows and pipes cannot turn a single chosen row into an
invented count. Candidate/outlier positions and exact ROIs remain in the report.
"""
import json
import hashlib
import io
import math
from pathlib import Path
import sys
import warnings

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from joint_count import runs

LUMA=np.array([.2126,.7152,.0722])
FACADES=[('A-D','west',39,(281,109,747,172),277,(380,200,600,235)),
         ('D-A','east',39,(281,506,747,570),674,(300,577,350,610)),
         ('1-3','north',40,(245,125,822,187),293,(390,210,590,240)),
         ('3-1','south',40,(245,522,822,584),690,(420,590,477,630))]


def count_blue(rgb,ppm):
    a=np.asarray(rgb,float)
    if a.ndim!=3 or a.shape[2]!=3 or not a.shape[0] or not a.shape[1] or not np.isfinite(a).all():
        raise ValueError('empty/non-finite/unsupported RGB pixels')
    if not math.isfinite(ppm) or ppm<=0:raise ValueError('invalid scale')
    lum=a@LUMA
    blue=(a[:,:,2]>100)&(a[:,:,2]-a[:,:,0]>30)&(a[:,:,0]<80)
    if blue.sum()<10:raise ValueError('no blue sandwich pixels')
    radius=max(2,round(.04*ppm));left=np.zeros_like(blue);right=left.copy()
    for k in range(1,min(radius,a.shape[1]-1)+1):
        left[:,k:]|=blue[:,:-k];right[:,:-k]|=blue[:,k:]
    ink=(lum<.5*np.median(lum[blue]))&left&right
    run=np.zeros(a.shape[1],int);longest=run.copy()
    for row in ink:
        run=(run+1)*row;longest=np.maximum(longest,run)
    mask=longest>=max(4,round(.09*ppm))
    centres=[float((lo+hi-1)/2) for lo,hi in runs(mask) if lo>1 and hi<a.shape[1]-1]
    if len(centres)<2:raise ValueError('insufficient measured vertical strokes')
    pitch=.2*ppm;best=[];tolerance=max(1.,.015*ppm)
    for phase in centres:
        good=[x for x in centres if abs((x-phase+pitch/2)%pitch-pitch/2)<=tolerance]
        if len(good)>len(best):best=good
    if len(best)<2:raise ValueError('no measurable regular grid')
    origin=best[0]
    for _ in range(3):
        indices=np.round((np.asarray(best)-best[0])/pitch)
        pitch,origin=np.polyfit(indices,best,1)
        best=[x for x in centres if abs((x-origin+pitch/2)%pitch-pitch/2)<=tolerance]
    if not .18< pitch/ppm <.22:raise ValueError('unsupported measured pitch')
    # An occluder/resampling hole can split one physical joint into two dark
    # strokes only 3px apart. Count distinct measured grid positions, never
    # both fragments of the SAME ~40px-period joint. Retain their coordinates.
    fragments={}
    for x in best:fragments.setdefault(int(np.rint((x-origin)/pitch)),[]).append(x)
    split_fragments=[g for g in fragments.values() if len(g)>1]
    best=[float(np.mean(g)) for _,g in sorted(fragments.items())]
    sample=lum.copy();sample[~(blue|ink)]=np.nan
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        profile=np.nanmedian(sample,axis=0)
    finite=profile[np.isfinite(profile)]
    contrast=float(np.percentile(finite,50)-np.percentile(finite,5))
    return {'ribs':len(best)+1,'joints':len(best),'pitch_m':float(pitch/ppm),
            'candidate_centres_px':centres,'regular_centres_px':best,
            'outlier_centres_px':[x for x in centres if not any(x in g for g in fragments.values())],
            'split_stroke_fragments_px':split_fragments,
            'luma_delta_p50_p05':contrast}


def white_crop(im,box):
    result=Image.new('RGB',(box[2]-box[0],box[3]-box[1]),'white')
    clipped=(max(0,box[0]),max(0,box[1]),min(im.width,box[2]),min(im.height,box[3]))
    if clipped[0]<clipped[2] and clipped[1]<clipped[3]:
        result.paste(im.crop(clipped),(clipped[0]-box[0],clipped[1]-box[1]))
    return result


def grey_contrast(im,box):
    a=np.asarray(im.crop(box),float)
    if not a.size:raise ValueError('empty grey control patch')
    profile=np.median(a@LUMA,axis=0)
    return float(np.percentile(profile,50)-np.percentile(profile,5))


def main(root,out):
    root,out=Path(root).resolve(),Path(out).resolve()
    if out.exists() or out==root:raise ValueError('comparison output must be new')
    job=Path(__file__).resolve().parent
    spec=json.loads((job/'vpm_textures.json').read_text())
    dump=json.loads((job/'max-dump-006.json').read_text())
    body=next(n for n in dump['nodes'] if n['handle']==170);v=np.asarray(body['vertices'])
    wall=v[sorted(set(k for f,m in zip(body['faces'],body['mat_ids']) if m==3 for k in f))]
    shift=(v.min(0)+v.max(0))/2;shift[2]=0
    meta=json.loads((root/'renders/renders.json').read_text())
    ppm=200.;top,bottom,pad=4.25,-.2,1.2
    out.mkdir(parents=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',28)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    report={'scope':'Actual regular pixel strokes in the blue field; grey control patches; no source geometry changes',
            'luma_metric':'Rec709 sRGB luma, median column profile P50-P05; contrast in the final resampled comparison panels',
            'px_per_m':ppm,'facades':{}}
    for name,view,slide,blue_box,zero,grey_box in FACADES:
        axis=1 if view in ('east','west') else 0
        lo,hi=float(wall[:,axis].min()),float(wall[:,axis].max());width=hi-lo
        sx0,_,sx1,_=blue_box;sp=(sx1-sx0)/width
        raw=Path(f'C:/x/tec26-oks/pptx/facades/slide{slide}.png').read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        if sha!=spec['presentation']['slide_sha256'][str(slide)]:raise ValueError('slide SHA256 mismatch')
        sheet=Image.open(io.BytesIO(raw)).convert('RGB')
        source_box=(round(sx0-pad*sp),round(zero-top*sp),round(sx1+pad*sp),round(zero-bottom*sp))
        size=(round((width+2*pad)*ppm),round((top-bottom)*ppm))
        panels=[sheet.crop(source_box).resize(size,Image.Resampling.LANCZOS)]
        for tag in ('vpm','npm'):
            vm=meta[tag]['views'][view];W,H=vm['res'];scale=vm['px_per_m'];c=vm['center']
            def px(q):return W/2+(q-shift[axis]-c[axis])*vm['right'][axis]*scale
            xa,xb=sorted((px(lo-pad),px(hi+pad)))
            box=(round(xa),round(H/2-(top-c[2])*scale),round(xb),round(H/2-(bottom-c[2])*scale))
            rgba=Image.open(root/f'renders/{tag}_{view}.png').convert('RGBA')
            white=Image.new('RGBA',rgba.size,'white');white.alpha_composite(rgba)
            panels.append(white_crop(white.convert('RGB'),box).resize(size,Image.Resampling.LANCZOS))
        roi=(round(pad*ppm),round((top-4.)*ppm),round((pad+width)*ppm),round((top-2.5)*ppm))
        # Exact same physical grey control region in each final resampled panel.
        gb=(round((grey_box[0]-sx0)/sp*ppm+pad*ppm),round((top-(zero-grey_box[1])/sp)*ppm),
            round((grey_box[2]-sx0)/sp*ppm+pad*ppm),round((top-(zero-grey_box[3])/sp)*ppm))
        measurements={}
        for tag,panel in zip(('slide','vpm','npm'),panels):
            measured=count_blue(np.asarray(panel.crop(roi)),ppm)
            measured['grey_luma_delta_p50_p05']=grey_contrast(panel,gb)
            measurements[tag]=measured
        target=measurements['slide']['ribs']
        match=all(m['ribs']==target for m in measurements.values())
        contrast=all(measurements[t]['luma_delta_p50_p05']>=measurements['slide']['luma_delta_p50_p05'] and
                     measurements[t]['grey_luma_delta_p50_p05']>=measurements['slide']['grey_luma_delta_p50_p05'] for t in ('vpm','npm'))
        gap=24;plate=Image.new('RGB',(3*size[0]+4*gap,size[1]+170),'white');d=ImageDraw.Draw(plate)
        ok=match and contrast
        d.text((gap,8),f'AC06 facade {name} | slide {slide} | 200 px/m | '+('MATCH' if ok else 'MISMATCH — NOT FOR ACCEPTANCE'),fill='black' if ok else 'red',font=font)
        for i,(tag,panel) in enumerate(zip(('slide','vpm','npm'),panels)):
            x=gap+i*(size[0]+gap);plate.paste(panel,(x,45));m=measurements[tag]
            d.text((x,50+size[1]),f'{tag.upper()}: {m["ribs"]} ribs / {m["joints"]} joints (measured pixels)',fill='black',font=font)
            d.text((x,88+size[1]),f'Joint ΔY blue {m["luma_delta_p50_p05"]:.2f}; grey {m["grey_luma_delta_p50_p05"]:.2f}',fill='black',font=small)
        path=out/f'compare-{name}.png';plate.save(path,optimize=True)
        report['facades'][name]={'measurements':measurements,'count_match':match,'contrast_at_least_slide':contrast,
                                 'passed':ok,'source_blue_box':blue_box,'source_grey_box':grey_box,'panel_blue_roi':roi,'panel_grey_roi':gb,'png':path.name,'source_slide_sha256':sha}
        print('COMPARE',name,{t:(m['ribs'],round(m['luma_delta_p50_p05'],2),round(m['grey_luma_delta_p50_p05'],2)) for t,m in measurements.items()},ok)
    report['passed']=all(f['passed'] for f in report['facades'].values())
    (out/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    sys.exit(main(*sys.argv[1:]))
