"""Calibrate the proposed whole-island-area denominator on an original alpha card.

Pattern: n/a | new-case: #369 calibration upper bound, NOT a semantic pass/fail scorer.
Foliage/bark are subsets of opaque pixels. If opaque/whole UV area < .95, no
semantic segmentation can make the literal whole-area metric pass .95.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/flora'))
from diagnose_texture import guard_outputs, uv_pixel


def components(faces, count):
    parent=list(range(count))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for face in faces:
        if len(face)!=3 or any(type(i) is not int or not 0<=i<count for i in face):
            raise ValueError('invalid UV face')
        for a,b in zip(face,face[1:]):parent[root(a)]=root(b)
    groups={}
    for i,face in enumerate(faces):groups.setdefault(root(face[0]),[]).append(i)
    return list(groups.values())


def measure(record, bitmap, component, resolution):
    islands=components(record['uvfaces'],len(record['uv']))
    if not 0<=component<len(islands):raise ValueError('unknown UV component')
    uv=record['uv'];faces=record['uvfaces'];indices=islands[component]
    alpha=np.array(Image.open(bitmap).convert('RGBA').getchannel('A').resize((resolution,resolution),Image.Resampling.NEAREST))>=128
    mask=Image.new('1',(resolution,resolution));draw=ImageDraw.Draw(mask)
    for i in indices:draw.polygon([uv_pixel(uv[v],resolution) for v in faces[i]],fill=1)
    occupied=np.array(mask,dtype=bool);area=int(occupied.sum())
    if not area:raise ValueError('zero rasterized UV area')
    opaque=int((occupied&alpha).sum())
    return {'resolution':resolution,'component':component,'component_faces':indices,
            'uv_area_pixels':area,'opaque_pixels':opaque,'matching_class_upper_bound':opaque/area,
            'semantic_roles_classified':False,'acceptance_metric_approved':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('inventory','bitmap','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--object',required=True);parser.add_argument('--scene',default='original')
    parser.add_argument('--component',type=int,default=0)
    args=parser.parse_args();guard_outputs([args.inventory,args.bitmap],[args.output])
    data=json.loads(args.inventory.read_text(encoding='utf-8'))
    record=data['scenes'][args.scene]['records'][args.object]
    result={'object':record['name'],'bitmap':str(args.bitmap),
            'samples':[measure(record,args.bitmap,args.component,n) for n in (1024,2048)]}
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
