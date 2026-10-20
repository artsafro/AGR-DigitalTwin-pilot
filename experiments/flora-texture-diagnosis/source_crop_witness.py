"""Render an original-only UV crop witness; not a texture or asset repair.

Pattern: n/a | new-case: #369 independently reproducible source crop evidence.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/flora'))
from diagnose_texture import guard_outputs
from measure_sprite_coverage import bound_images, compact_measure, images, reviewed_bark_region
from geometry_parts import parts_and_charts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    job=json.loads(args.job.read_text());inventory=Path(job['work'])/job['inventory']
    report=args.output.with_suffix('.json')
    inputs=[args.job,inventory]+[Path(s['maps']) for s in job['scenes']]
    guard_outputs(inputs,[args.output,report])
    data=json.loads(inventory.read_text(encoding='utf-8'))
    key='Padus_maackii_VPM';record=data['scenes']['original']['records'][key]
    parts,charts=parts_and_charts(record)
    chart=next(c for c in charts if c['faces']==[182,183,184,185,298,299,300,301])
    paths=bound_images(record['material'],'original',job)
    rgb,alpha,cells=images(*paths)
    result,offset,target=compact_measure(record,chart['faces'],alpha,cells,'VPM',False,'foliage')
    h,w=alpha.shape
    display=Image.fromarray(np.where(alpha[...,None],rgb,245).astype(np.uint8))
    classes=np.full_like(rgb,245);classes[alpha]=(45,160,65)
    # Regions independently reviewed on the source atlas: right-hand continuous bark.
    entry=reviewed_bark_region(job,paths[0],alpha.shape)
    if entry is None:raise ValueError('reviewed source bark region required')
    for l,t,r,b in entry['boxes']:
        classes[t:b,l:r][alpha[t:b,l:r]]=(145,95,45)
    overlay=Image.fromarray(classes);draw=ImageDraw.Draw(overlay)
    uv=np.asarray(record['uv'])-offset;uvfaces=np.asarray(record['uvfaces'])
    for face in uvfaces[chart['faces']]:
        points=[(float(uv[i,0]*w),float((1-uv[i,1])*h)) for i in face]
        draw.line(points+[points[0]],fill=(245,20,25),width=10)
    draw.rectangle((target[0],target[1],target[2]-1,target[3]-1),outline=(0,80,255),width=12)
    canvas=Image.new('RGB',(1500,1060),(250,250,250));draw=ImageDraw.Draw(canvas)
    draw.text((20,15),'ORIGINAL Padus_maackii_VPM / authored foliage card / no asset acceptance',fill='black')
    for x,image in ((10,display),(760,overlay)):
        canvas.paste(image.resize((730,730)),(x,50))
    labels=['Original diffuse+alpha (left); opaque region classes and exact UV triangles (right).',
            'Green: discrete foliage sprites; brown: reviewed continuous bark; grey: alpha <128.',
            'Red: intact 8-triangle foliage UV chart; blue: bbox of ONE bottom-left branch sprite.',
            f"Coverage = {result['score']:.12f}; required >=0.80; measured pass={result['pass']}.",
            f"Island/bbox px2: {result['island_area_px']:.6f} / {result['sprite_bbox_area_px']}; intersection used for score.",
            f"Opaque pixels outside UV (1px tolerance): {result['clipped_opaque_px_tolerance_1']}; neighbour pixels: {result['neighbour_opaque_px']}.",
            f"Faces: {chart['faces']}; chart role={chart['role']}; source UVs/bitmaps unchanged.",
            'The original atlas was visually inspected. This is not a replacement score or a bark-policy question.']
    for i,line in enumerate(labels):draw.text((15,805+i*24),line,fill='black')
    receipt={'object':key,'faces':chart['faces'],'geometry_parts':[parts[i] for i in chart['geometry_parts']],
             'diffuse':paths[0],'opacity':paths[1],'sprite_bbox':list(target),'result':result,'accepted':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);canvas.save(args.output)
    report.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
