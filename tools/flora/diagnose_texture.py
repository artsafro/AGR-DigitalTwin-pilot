"""Pure-Python Flora UV/layout diagnosis helpers (#369).

Pattern: n/a | new-case: read-only Flora UV/layout diagnosis (#369).
"""
import argparse
import json
import math
import os
from pathlib import Path, PureWindowsPath


def uv_pixel(uv, size):
    if len(uv) != 2 or not isinstance(size, int) or size < 2 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in uv):
        raise ValueError('finite UV pair in [0,1] and size >= 2 required')
    return tuple(round(v*(size-1)) for v in (uv[0],1-uv[1]))


def resolve_bitmap(name, folder):
    basename = PureWindowsPath(name).name
    matches = [p for p in Path(folder).iterdir() if p.is_file() and p.name.lower()==basename.lower()]
    if len(matches) != 1:
        raise ValueError(f'{basename}: {len(matches)} bitmap matches in {folder}')
    return matches[0]


def guard_outputs(inputs, outputs):
    paths = [Path(p).resolve() for p in [*inputs,*outputs]]
    for i, p in enumerate(paths):
        for j, q in enumerate(paths[:i]):
            if i < len(inputs) and j < len(inputs):
                continue
            if os.path.normcase(str(p)) == os.path.normcase(str(q)) or (p.exists() and q.exists() and p.samefile(q)):
                raise ValueError(f'path alias: {p} / {q}')
    for p in paths[len(inputs):]:
        if p.exists():
            raise ValueError(f'fresh output required: {p}')


def compare_inventory(source, ours):
    if not ours or source.keys() != ours.keys():
        raise ValueError('incomplete object mapping: '+str(sorted(source.keys() ^ ours.keys())))
    result = {'total':len(ours),'uv_identical':[],'uv_changed':[]}
    for name, row in sorted(ours.items()):
        for record in (row, source[name]):
            count=record.get('triangles')
            if not isinstance(record.get('uv_sha256'),str) or not record['uv_sha256'] or type(count) is not int or count<=0:
                raise ValueError('invalid mesh evidence: '+name)
        identical = row['uv_sha256'] == source[name]['uv_sha256'] and row['triangles'] == source[name]['triangles']
        result['uv_identical' if identical else 'uv_changed'].append(name)
    return result


def replacement_evidence(source, ours):
    compare_inventory(source,ours)
    rows=[]
    for name in sorted(ours):
        filenames=[]
        for record in (source[name],ours[name]):
            textures=record.get('material',{}).get('textures',[])
            if not textures or any(not t.get('filename') for t in textures):
                raise ValueError('unmapped material '+name)
            filenames.append(sorted({PureWindowsPath(t['filename']).name.lower() for t in textures}))
        rows.append({'object':name,'source_object':source[name]['name'],
                     'source_class':source[name]['material']['class'],
                     'original_bitmaps':filenames[0],'library_bitmaps':filenames[1],
                     'maps_replaced':set(filenames[0]).isdisjoint(filenames[1])})
    return rows


def centered_deviation_mm(a,b):
    if not a or len(a)!=len(b) or any(len(p)!=3 or any(not math.isfinite(c) for c in p) for p in [*a,*b]):
        raise ValueError('finite equally sized 3D vertex arrays required')
    centers=[[(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)] for points in (a,b)]
    return 1000*max(math.dist([v-centers[0][i] for i,v in enumerate(p)],
                              [v-centers[1][i] for i,v in enumerate(q)]) for p,q in zip(a,b))


def bound_diffuse(record, receipt):
    """Use the actual slot path, never an ambiguous texture display name/order."""
    path=record['material']['slot_paths'].get('diffuseMap')
    if not path:
        raise ValueError('unmapped diffuse slot '+record.get('name','<unnamed>'))
    basename=PureWindowsPath(path).name.lower()
    matches={t['source_copy'] for t in receipt['resolved_bitmaps'] if Path(t['source_copy']).name.lower()==basename}
    if len(matches)!=1:
        raise ValueError('unmapped diffuse bitmap '+basename)
    return matches.pop()


def overlay(record, diffuse, output, size=640):
    from PIL import Image, ImageDraw
    guard_outputs([diffuse],[output])
    if not record.get('uv') or not record.get('uvfaces'):
        raise ValueError('missing UV topology')
    points = [uv_pixel(uv,size) for uv in record['uv']]
    image = Image.open(diffuse).convert('RGBA').convert('RGB').resize((size,size))
    draw = ImageDraw.Draw(image)
    for face in record['uvfaces']:
        if len(face)!=3 or any(not isinstance(i,int) or not 0<=i<len(points) for i in face):
            raise ValueError('invalid UV face')
        poly = [points[i] for i in face]
        draw.line(poly+[poly[0]], fill=(255,0,255),width=1)
    image.save(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    data=json.loads(args.inventory.read_text(encoding='utf-8'))
    source={**data['scenes']['original']['records'],**data['scenes']['florio']['records']}
    guard_outputs([args.inventory],[args.output])
    args.output.write_text(json.dumps(compare_inventory(source,data['scenes']['ours']['records']),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
