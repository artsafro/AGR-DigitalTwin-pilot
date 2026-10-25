"""Build six diagnostic sheets and machine-readable evidence from native receipts.

Pattern: n/a | new-case: #369 Flora contact sheets, no production-asset publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parent))
from diagnose_texture import compare_inventory, overlay, bound_diffuse, replacement_evidence, centered_deviation_mm
from prepare_texture_diagnosis import sha


def build(job_path, output):
    job=json.loads(job_path.read_text(encoding='utf-8'));work=Path(job['work'])
    inventory=json.loads((work/job.get('inventory','inventory.json')).read_text(encoding='utf-8'))
    if inventory['failures']:raise ValueError('unaccounted source objects')
    source={**inventory['scenes']['original']['records'],**inventory['scenes']['florio']['records']}
    ours=inventory['scenes']['ours']['records']
    summary=compare_inventory(source,ours)
    replacements=replacement_evidence(source,ours)
    summary['maps_replaced']=sum(r['maps_replaced'] for r in replacements)
    renders=work/job['render_folder']
    receipts=json.loads((renders/'render-receipts.json').read_text(encoding='utf-8'))
    if len(receipts)!=17:raise ValueError('expected 6 NPM source + 6 NPM library + 3 light + 2 Union VPM receipts')
    after={p:sha(p) for p in job['hashes_before']}
    if after!=job['hashes_before']:raise ValueError('protected source changed')
    output.mkdir(parents=True,exist_ok=False)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    selected=[s for s in job['species'] if s['material_id'] in job['selected']]
    summaries=[]
    for species in selected:
        key=species['objects']['NPM']; rows=[r for r in receipts if r['key']==key]
        original=next(r for r in rows if r['tag']!='ours' and r['tag']!='light')
        library=next(r for r in rows if r['tag']=='ours')
        sheet=Image.new('RGB',(1536,2280),'white');draw=ImageDraw.Draw(sheet)
        draw.text((12,10),f"#{species['material_id']} {species['latin']} — NPM / native 3ds Max 2026",font=font,fill='black')
        draw.text((12,42),'Diagnostic: common framing/light/gamma 2.2; two-sided cutouts; indexed PNGs decoded losslessly in scratch.',font=small,fill='black')
        for col,(tag,title) in enumerate([(original['tag'],'(a) Original source + original maps'),('ours','(b) v003 + published species maps'),('light','(c) NPM light FBX + published maps')]):
            draw.text((col*512+10,76),title,font=small,fill='black')
            for row,view in enumerate(('front','45','top')):
                path=renders/f'{key}-{tag}-{view}.png';y=108+row*440
                if path.exists():
                    image=Image.open(path).convert('RGB')
                    sheet.paste(image.resize((440,440)),(col*512+36,y))
                    shutil.copy2(path,output/path.name)
                else:draw.text((col*512+30,y+160),'N/A — no light FBX for this species',font=small,fill='black')
                draw.text((col*512+10,y+4),view,font=small,fill='black')
        for col,(record,receipt,title) in enumerate([(source[key],original,'Original UV + original diffuse'),(ours[key],library,'Same UV + our diffuse')]):
            diffuse=bound_diffuse(record,receipt)
            target=output/f'{key}-uv-{col}.png';overlay(record,diffuse,target,size=640)
            sheet.paste(Image.open(target),(col*768+64,1500))
            draw.text((col*768+12,1460),title,font=font,fill='black')
            bounds=record['uv_bounds']
            draw.text((col*768+12,2150),f'U {bounds[0][0]:.5f}..{bounds[0][1]:.5f}; V {bounds[1][0]:.5f}..{bounds[1][1]:.5f}',font=small,fill='black')
            draw.text((col*768+12,2178),Path(diffuse).name,font=small,fill='black')
        draw.text((12,2220),'Magenta = UV edges; V=0 at image bottom. Overlays use original pixels, not a proposed remap.',font=small,fill='black')
        sheet.save(output/f'{species["material_id"]}.png')
        summaries.append({'id':species['material_id'],'species':species['latin'],'object':key,'source_object':source[key]['name'],
                          'source_scene':species['npm']['scene'],'uv_bounds':source[key]['uv_bounds'],'uv_identical':source[key]['uv_sha256']==ours[key]['uv_sha256'],
                          'centered_vertex_deviation_mm':centered_deviation_mm(source[key]['vertices'],ours[key]['vertices']),
                          'front_alpha_pixels_gt127':{r['tag']:sum(Image.open(renders/f"{key}-{r['tag']}-front.png").convert('RGBA').getchannel('A').histogram()[128:]) for r in rows}})
    extra=''
    key='Amelanchier_lamarckii_VPM'
    for tag,record in [('original',source[key]),('ours',ours[key])]:
        receipt=next(r for r in receipts if r['key']==key and r['tag']==tag)
        target=output/f'{key}-uv-{tag}.png'
        overlay(record,bound_diffuse(record,receipt),target)
        for view in ('front','45','top'):
            image=f'{key}-{tag}-{view}.png'
            shutil.copy2(renders/image,output/image)
            extra+=f'<a href="{image}"><img width="320" src="{image}"></a>'
        extra+=f'<a href="{target.name}"><img width="320" src="{target.name}"></a><br>'
    summary.update(selected=summaries,protected_hashes_equal=len(after),
                   render_count=sum(len(r['render_seconds']) for r in receipts),
                   median_render_seconds=statistics.median(t for r in receipts for t in r['render_seconds']),
                   render_medians={tag:statistics.median(t for r in receipts if r['tag']==tag for t in r['render_seconds']) for tag in {r['tag'] for r in receipts}})
    (output/'affected-objects.json').write_text(json.dumps(replacements,indent=2),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    shutil.copy2(work/job.get('inventory','inventory.json'),output/'inventory.json')
    shutil.copy2(renders/'render-receipts.json',output/'render-receipts.json')
    shutil.copy2(work/'native-texture-controls.json',output/'native-texture-controls.json')
    decoder=[]
    for source_path,decoded in job['diagnostic_decode'].items():
        hashes=[hashlib.sha256(Image.open(p).convert('RGBA').tobytes()).hexdigest() for p in (source_path,decoded)]
        if hashes[0]!=hashes[1]:raise ValueError('diagnostic decoder changed pixels')
        decoder.append({'source_copy':source_path,'decoded_copy':decoded,'rgba_sha256':hashes[0],'equal':True})
    (output/'decoder-pixel-identity.json').write_text(json.dumps(decoder,indent=2),encoding='utf-8')
    (output/'source-integrity.json').write_text(json.dumps({'before':job['hashes_before'],'after':after},indent=2),encoding='utf-8')
    links=''.join(f'<h2>{s["material_id"]}: {s["latin"]}</h2><a href="{s["material_id"]}.png"><img width="1000" src="{s["material_id"]}.png"></a>' for s in selected)
    links+='<h2>105: Union VPM counterpart / v003 VPM (not the NPM/light geometry)</h2>'+extra
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Flora texture diagnosis #369</title><h1>Flora: original / v003 / NPM light</h1><p>Диагностика, не исправление. Original is the actual catalogue source; #105 NPM comes from FLORIO, not Union. Indexed PNG scratch copies preserve every RGBA pixel. No assets changed.</p>'+links,encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('uv_identical','uv_changed','selected')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('job',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();build(args.job,args.output)
