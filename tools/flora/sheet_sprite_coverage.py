"""Publish preliminary #369 geometric evidence without editing existing sheets.

Pattern: n/a | new-case: versioned diagnostic sheets, explicit calibration failures.
"""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from diagnose_texture import guard_outputs


def statistics(row):
    scores=[i['score'] for i in row['islands'] if 'score' in i]
    return {'object':row['object'],'tag':row['tag'],'islands':len(row['islands']),
            'scored':len(scores),'pass':row['passing_islands'],'roles':row['roles'],
            'unknown_roles':row['roles'].get('unknown',0),'unknown_metric':row['unknown_metric_islands'],
            'quantiles':np.quantile(scores,[0,.25,.5,.75,1]).tolist() if scores else [],
            'star_plane_elements':len({e for i in row['islands'] if i['role']=='star_plane' for e in i['geometry_elements']}),
            'clipped_islands':sum(i.get('clipped_opaque_px_tolerance_1',0)>0 for i in row['islands'])}


def main():
    p=argparse.ArgumentParser()
    for name in ('job','metrics','pictures','witness','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();j=json.loads(a.job.read_text());inventory=Path(j['work'])/j['inventory']
    rows=json.loads(a.metrics.read_text(encoding='utf-8'))['objects'];native=json.loads(inventory.read_text(encoding='utf-8'))
    source={**native['scenes']['original']['records'],**native['scenes']['florio']['records']};ours=native['scenes']['ours']['records']
    if len(source)!=99 or source.keys()!=ours.keys() or native['failures']:raise ValueError('99 native pairs required')
    if any(r['tag'] in ('ours','light') for r in rows):raise ValueError('original-only checkpoint required')
    guard_outputs([a.job,a.metrics,a.pictures,a.witness,inventory],[a.output]);a.output.mkdir(parents=True)
    summaries=[statistics(r) for r in rows];measured={r['object'] for r in rows}
    for file in a.pictures.glob('*.png'):shutil.copy2(file,a.output/file.name)
    for source_file,name in [(a.witness,a.witness.name),(a.metrics,'partial-original-metrics.json'),(inventory,'inventory-all.json')]:shutil.copy2(source_file,a.output/name)
    counts={'native_source_pairs':99,'native_library_objects':99,'native_light_fbx':len(native['light']),
            'measured_original_objects':len(rows),'not_measured_original_objects':sorted(source.keys()-measured),
            'replacement_objects_scored':0,'final_routes_issued':0,'accepted':False}
    (a.output/'checkpoint.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    (a.output/'per-object-summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    page='<!doctype html><meta charset="utf-8"><h1>Flora #369 — original calibration BLOCKED / NOT accepted</h1>'
    page+='<p>Все 99 пар извлечены на копиях.<br>Foliage-card липы: 100%, соседних спрайтов нет.<br>Bark-island: 0,244472% всей полосы коры при корректном попадании.<br>Нужно уточнить применимость 80–95% к непрерывной коре.<br>Замены новой метрикой не оценивались; итоговых маршрутов нет; ассеты не изменены.</p>'
    page+='<a href="../index.html">Existing six render sheets</a> | <a href="checkpoint.json">Exact checkpoint / unmeasured names</a> | <a href="per-object-summary.json">Partial original distribution</a>'
    page+='<p><a href="'+a.witness.name+'"><img width="1200" src="'+a.witness.name+'"></a></p>'
    page+='<h2>Candidate masks, NOT semantic ground truth</h2><p>Green/red UV edges: geometric pass/fail; blue: unknown role. Cyan: alpha-derived candidate bbox. Green pixels: foliage candidate, brown: bark candidate, purple: UNKNOWN opaque, grey: empty.</p>'
    for r in summaries:page+='<pre>'+html.escape(json.dumps(r))+'</pre>'
    for f in sorted(a.output.glob('*-overlay.png')):page+='<h3>'+html.escape(f.stem)+'</h3><a href="'+f.name+'"><img width="600" src="'+f.name+'"></a>'
    (a.output/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps({k:v for k,v in counts.items() if k!='not_measured_original_objects'}))


if __name__=='__main__':main()

