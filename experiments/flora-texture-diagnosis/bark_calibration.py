"""Render the original-only bark calibration witness (#369), no DCC/asset writes.

Pattern: n/a | new-case: show geometric bbox calibration failure on original bark.
"""
import argparse
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/flora'))
from diagnose_texture import guard_outputs


def main():
    p=argparse.ArgumentParser();p.add_argument('--metrics',type=Path,required=True);p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=json.loads(a.metrics.read_text());row=next(r for r in data['objects'] if r['tag']=='original' and r['object']=='Tilia_cordata_VPM');card=row['islands'][0];bark=next(i for i in row['islands'] if i['island']==166)
    j=json.loads(a.job.read_text());inv=Path(j['work'])/j['inventory'];record=json.loads(inv.read_text(encoding='utf-8'))['scenes']['original']['records']['Tilia_cordata_VPM'];guard_outputs([a.metrics,a.job,inv,card['bitmap']],[a.output])
    image=Image.open(card['bitmap']).convert('RGBA').convert('RGB');W,H=image.size;draw=ImageDraw.Draw(image)
    for r,color in [(card,(0,255,0)),(bark,(255,0,0))]:
        for face in r['faces']:
            points=[(record['uv'][v][0]*W,(1-record['uv'][v][1])*H) for v in record['uvfaces'][face]];draw.line(points+[points[0]],fill=color,width=12)
        x,y,X,Y=r['sprite_bbox'];draw.rectangle((x,y,X-1,Y-1),outline=(0,180,255),width=10)
    image.thumbnail((1024,1024));sheet=Image.new('RGB',(1500,1120),'white');sheet.paste(image,(0,0));d=ImageDraw.Draw(sheet);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    lines=['ORIGINAL Tilia VPM','19_Lipa_HP','', 'Green: leaf card #0',f'Geometric coverage {card["score"]:.6%}','Neighbour opaque pixels: 0','>95% allowed: PASS','','Red: bark UV island #166','Single face 332',f'Geometric coverage {bark["score"]:.6%}',f'UV polygon {bark["island_area_px"]:.3f} px2',f'Bark bbox {bark["sprite_bbox_area_px"]:.0f} px2',f'Opaque density {bark["opaque_density"]:.4%}','Neighbour opaque pixels: 0','','80% of entire bark strip: FAIL','Despite sampling bark correctly.','','Cyan: independent alpha bbox','No threshold changed.','Calibration is NOT accepted.']
    for n,text in enumerate(lines):d.text((1038,10+n*35),text,font=font,fill='black')
    d.text((10,1050),'Geometric sprite coverage is NOT opaque-pixel density. This is the original atlas, not our replacement.',font=font,fill='black');sheet.save(a.output)
    print(json.dumps({'card':card,'bark':bark},ensure_ascii=False))


if __name__=='__main__':main()
