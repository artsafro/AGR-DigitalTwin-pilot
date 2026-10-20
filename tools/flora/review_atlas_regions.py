"""Candidate contact sheets for human certification of source atlas regions (#369).

Pattern: n/a | new-case: copied inventory only, candidate boxes without semantic labels.
Loads full inventory JSON and bitmap copies. Does not call 3ds Max.
Sheets show source RGB, opacity, sprite-cell boxes and tall-strip candidates.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from diagnose_texture import guard_outputs, resolve_bitmap
from measure_sprite_coverage import BARK_STRIP_PROVENANCE, bark_strip_candidates, bitmap_key, images


SHEET_LIMIT=8


def standard_materials(material):
    """Explicit Standard and Multimaterial walk. Other classes are not guessed."""
    if not isinstance(material,dict):raise ValueError('empty material')
    kind=material.get('class')
    if kind=='Standardmaterial':return [material]
    if kind!='Multimaterial':raise ValueError('unsupported material '+str(kind))
    subs=material.get('submaterials')
    if not isinstance(subs,list):raise ValueError('multimaterial without explicit submaterials')
    found=[]
    for sub in subs:found.extend(standard_materials(sub))
    return found


def bound_slot_pair(mat):
    if not mat.get('bindings',{}).get('opacityMapEnable'):return None
    slots=mat.get('slot_paths') or {}
    diffuse,opacity=slots.get('diffuseMap'),slots.get('opacityMap')
    if not diffuse or not opacity:raise ValueError('unmapped bound slots '+str(mat.get('name')))
    mode=(mat.get('slot_settings') or {}).get('opacityMap',{}).get('monoOutput')
    if mode not in (0,1):raise ValueError('unsupported opacity slot mode '+str(mode)+' '+str(mat.get('name')))
    return diffuse,opacity,mode==1


def source_bound_pairs(inventory, job):
    """Unique resolved diffuse/opacity pairs from original and florio copies."""
    scenes={s['tag']:s for s in job['scenes']}
    found=[];seen=set()
    for tag in ('original','florio'):
        maps=scenes[tag]['maps']
        for record in inventory['scenes'][tag]['records'].values():
            for mat in standard_materials(record['material']):
                pair=bound_slot_pair(mat)
                if pair is None:continue
                diffuse,opacity=str(resolve_bitmap(pair[0],maps)),str(resolve_bitmap(pair[1],maps))
                key=(diffuse.replace('\\','/').lower(),opacity.replace('\\','/').lower(),pair[2])
                if key in seen:continue
                seen.add(key)
                found.append({'diffuse':diffuse,'opacity':opacity,'diffuse_key':bitmap_key(diffuse),
                              'alpha_mode':pair[2],'tag':tag})
    return found


def sheet_slices(count):
    if type(count) is not int or count<0:raise ValueError('pair count required')
    return [(start,min(start+SHEET_LIMIT,count)) for start in range(0,count,SHEET_LIMIT)]


def _scaled_box(bbox, scale):
    left,top,right,bottom=[int(round(v*scale)) for v in bbox]
    return (left,top,max(right,left+1),max(bottom,top+1))


def contact_pair(rgb, alpha, cells, strips, max_side=480):
    """Source RGB beside opacity. Boxes are candidates: cell index and pixel size only."""
    height,width=np.shape(alpha)
    scale=min(1.0,max_side/max(height,width))
    tw,th=max(1,int(round(width*scale))),max(1,int(round(height*scale)))
    color=Image.fromarray(np.asarray(rgb,dtype=np.uint8)).convert('RGB').resize((tw,th),Image.Resampling.BOX)
    gray=Image.fromarray(np.where(np.asarray(alpha,dtype=bool),255,0).astype(np.uint8)).convert('RGB').resize((tw,th),Image.Resampling.NEAREST)
    def draw(image):
        pen=ImageDraw.Draw(image)
        for cell in cells:
            box=_scaled_box(cell['bbox'],scale)
            pen.rectangle(box,outline=(0,180,255))
            pen.text((box[0]+2,box[1]+2),f"{cell['cell']} {cell['width']}x{cell['height']}",fill=(0,180,255))
        for cand in strips:
            box=_scaled_box(cand['bbox'],scale)
            pen.rectangle(box,outline=(255,140,0))
            pen.text((box[0]+2,max(box[1]+2,box[3]-12)),'candidate',fill=(255,140,0))
    draw(color);draw(gray)
    sheet=Image.new('RGB',(tw*2+8,th),(30,30,30))
    sheet.paste(color,(0,0));sheet.paste(gray,(tw+8,0))
    return sheet


def save_sheet(thumbs, path):
    if not 1<=len(thumbs)<=SHEET_LIMIT:raise ValueError('sheet holds at most 8 pairs')
    width=max(thumb.width for thumb in thumbs)
    height=sum(thumb.height+8 for thumb in thumbs)
    sheet=Image.new('RGB',(width,max(1,height)),(20,20,20))
    y=0
    for thumb in thumbs:
        sheet.paste(thumb,(0,y));y+=thumb.height+8
    sheet.save(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    job=json.loads(args.job.read_text(encoding='utf-8'))
    inventory_path=Path(job['work'])/job['inventory']
    inventory=json.loads(inventory_path.read_text(encoding='utf-8'))
    if inventory.get('failures'):raise ValueError('native failures '+str(inventory['failures']))
    pairs=source_bound_pairs(inventory,job)
    loaded=[]
    for pair in pairs:
        rgb,alpha,cells=images(pair['diffuse'],pair['opacity'],pair['alpha_mode'])
        cell_rows=[{'cell':i,'bbox':[int(a),int(b),int(c),int(d)],'width':int(c-a),'height':int(d-b)}
                   for i,(a,b,c,d) in enumerate(cells)]
        strips=bark_strip_candidates(alpha,cells)
        loaded.append((pair,rgb,alpha,cell_rows,strips))
    inputs=[args.job,inventory_path]
    for scene in job['scenes']:inputs.append(Path(scene['maps']))
    for pair in pairs:inputs.extend((pair['diffuse'],pair['opacity']))
    guard_outputs(inputs,[args.output])
    args.output.mkdir(parents=True)
    records=[];thumbs=[]
    for pair,rgb,alpha,cell_rows,strips in loaded:
        records.append({**pair,'width':int(alpha.shape[1]),'height':int(alpha.shape[0]),
                        'cells':cell_rows,'strip_candidates':strips})
        thumbs.append(contact_pair(rgb,alpha,cell_rows,strips))
    sheets=[]
    for start,end in sheet_slices(len(thumbs)):
        name=f'sheet-{start//SHEET_LIMIT:03d}.png'
        save_sheet(thumbs[start:end],args.output/name)
        sheets.append(name)
    payload={'semantic_labels':False,'strip_candidate_provenance':BARK_STRIP_PROVENANCE,
             'pairs':records,'sheets':sheets}
    (args.output/'atlas-regions.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'pairs':len(records),'sheets':len(sheets)}),flush=True)


if __name__=='__main__':main()
