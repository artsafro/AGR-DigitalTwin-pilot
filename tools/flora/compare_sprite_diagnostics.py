"""Raw #369 sprite diagnostic ledger. Not calibrated acceptance.

Pattern: n/a | new-case: offline source, library and light inventory.
Calls the existing original gate and records its failure. It does not turn an
unresolved original into a pass, and it does not certify a replacement.
Does not call 3ds Max.
"""
import argparse
import math
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from diagnose_texture import guard_outputs
from measure_sprite_coverage import analyze, original_gate


REVIEW_ROOT=Path('C:/x/review/2026-10-20/flora-texture-diagnosis')
SHEET_IDS=(101,102,103,105,204,225)
SOURCE_TAGS=('original','florio')
HORIZONTAL_NORMAL_Z=0.02
STAR_PLANE_LIMIT=12


def _refuse_review_write(path):
    path=Path(path).resolve()
    root=REVIEW_ROOT.resolve()
    if path==root or (path.parent==root and path.suffix.lower()=='.png'):
        raise ValueError('review sheets are read only')


def output_targets(output):
    output=Path(output)
    names=['metrics.json','metrics.partial.json','distribution.json','routes.json','index.html','checkpoint.json','panels']
    return [output,*[output/name for name in names],*[output/f'{material_id}.png' for material_id in SHEET_IDS]]


def guard_run_paths(inputs, output):
    _refuse_review_write(output)
    for path in output_targets(output):
        _refuse_review_write(path)
    guard_outputs(list(inputs), output_targets(output))


def _finite_score(island):
    score=island.get('score')
    return type(score) is not bool and isinstance(score,(int,float)) and math.isfinite(score)


def source_unresolved(row):
    islands=row.get('islands') or []
    if not islands:
        return True
    for island in islands:
        if island.get('pass') is not True or island.get('role')=='unknown' or island.get('status')=='unknown' or not _finite_score(island):
            return True
    return False


def _opacity_enabled(material):
    if not isinstance(material,dict):
        return None
    kind=material.get('class')
    if kind=='Standardmaterial':
        flag=(material.get('bindings') or {}).get('opacityMapEnable')
        if flag is True:return True
        if flag is False:return False
        return None
    if kind!='Multimaterial':
        return None
    subs=material.get('submaterials')
    if not isinstance(subs,list):
        return None
    flags=[]
    for sub in subs:
        if sub is None:continue
        flag=_opacity_enabled(sub)
        if flag is None:return None
        flags.append(flag)
    if not flags:return None
    return True if all(flags) else False


def _star_result(count, vertical, uv_extent, opacity, is_star, unknowns, normals):
    return {'candidate_plane_count':count,'vertical_plane_count':vertical,'horizontal_normal_count':vertical,
            'uv_extent':uv_extent,'opacity_enabled':opacity,'is_star':bool(is_star),'unknowns':list(unknowns),
            'plane_normal_z':normals}


def npm_star_check(record):
    """Plane count, vertical-plane normals, UV extent and opacity. A complex mesh is not a star."""
    if not isinstance(record,dict):
        return _star_result(None,None,None,None,False,['source record missing'],[])
    vertices=np.asarray(record.get('vertices'),float)
    faces=record.get('faces')
    unknowns=[]
    if vertices.ndim!=2 or vertices.shape[1:]!=(3,) or len(vertices)<3 or not isinstance(faces,list) or not faces or not np.isfinite(vertices).all():
        return _star_result(None,None,None,_opacity_enabled(record.get('material')),False,['invalid geometry'],[])
    span=float(np.max(np.ptp(vertices,axis=0)))
    tolerance=max(span*1e-4,1e-8)
    groups=[]
    degenerate=False
    for face in faces:
        if not isinstance(face,(list,tuple)) or len(face)!=3 or any(type(index) is not int or not 0<=index<len(vertices) for index in face):
            degenerate=True
            continue
        tri=vertices[list(face)]
        normal=np.cross(tri[1]-tri[0], tri[2]-tri[0])
        length=float(np.linalg.norm(normal))
        if length<=1e-10 or not np.isfinite(normal).all():
            degenerate=True
            continue
        normal=normal/length
        origin=tri[0]
        placed=False
        for group in groups:
            if abs(float(np.dot(group['normal'], normal)))<0.999:continue
            if abs(float(np.dot(origin-group['origin'], group['normal'])))>tolerance:continue
            group['count']+=1
            placed=True
            break
        if not placed:
            groups.append({'normal':normal,'origin':origin,'count':1})
    vertical=sum(abs(float(group['normal'][2]))<=HORIZONTAL_NORMAL_Z for group in groups)
    normals=[round(abs(float(group['normal'][2])),6) for group in groups]
    uv=np.asarray(record.get('uv'),float)
    uv_extent=None
    if uv.ndim==2 and uv.shape[1:]==(2,) and len(uv)>0 and np.isfinite(uv).all():
        extent=[float(value) for value in np.ptp(uv,axis=0)]
        if extent[0]!=0 or extent[1]!=0:
            uv_extent=extent
    opacity=_opacity_enabled(record.get('material'))
    if degenerate:unknowns.append('degenerate face')
    if opacity is None:unknowns.append('opacity enable unknown')
    elif opacity is False:unknowns.append('opacity disabled')
    if uv_extent is None:unknowns.append('nonfinite or missing UV')
    if any(abs(float(group['normal'][2]))>HORIZONTAL_NORMAL_Z for group in groups):
        unknowns.append('plane is not vertical')
    if len(groups)>STAR_PLANE_LIMIT:
        unknowns.append('complex whole-tree mesh is not a star')
    elif len(groups)<2:
        unknowns.append('star arrangement not confirmed')
    is_star=(not unknowns and opacity is True and 2<=len(groups)<=STAR_PLANE_LIMIT and vertical==len(groups) and uv_extent is not None)
    return _star_result(len(groups),vertical,uv_extent,opacity,is_star,unknowns,normals)


def provisional_route(row, star):
    if source_unresolved(row):
        return 'source_validation_required'
    if row.get('profile')=='VPM':
        return 'rebind_original_atlas'
    if row.get('profile')=='NPM' and isinstance(star,dict) and star.get('is_star') is True:
        return 'keep_or_rebuild_star'
    return 'source_validation_required'


def island_ledger(row):
    if row is None:
        return []
    ledger=[]
    for island in row.get('islands') or []:
        unknown=island.get('role')=='unknown' or island.get('status')=='unknown' or not _finite_score(island)
        ledger.append({'island':island.get('island'),'role':island.get('role'),'faces':island.get('faces'),
                       'pass':island.get('pass'),'status':island.get('status'),
                       'score':float(island['score']) if _finite_score(island) else None,'unknown':unknown})
    return ledger


def score_quantiles(scores):
    if not scores:
        return {'min':None,'q25':None,'median':None,'q75':None,'max':None}
    values=np.quantile(np.asarray(scores,float),[0,.25,.5,.75,1])
    return {key:float(value) for key,value in zip(('min','q25','median','q75','max'), values)}


def build_distribution(rows):
    groups={}
    for row in rows:
        tag=row.get('tag') or 'unknown'
        for island in row.get('islands') or []:
            role=island.get('role') or 'unknown'
            bucket=groups.setdefault((tag,role),{'scores':[],'fail':0,'unknown':0,'islands':0})
            bucket['islands']+=1
            unknown=island.get('role')=='unknown' or island.get('status')=='unknown' or not _finite_score(island)
            if unknown:bucket['unknown']+=1
            if island.get('pass') is not True:bucket['fail']+=1
            if _finite_score(island):bucket['scores'].append(float(island['score']))
    report={}
    for (tag,role),bucket in sorted(groups.items()):
        report[f'{tag}|{role}']={**score_quantiles(bucket['scores']),'fail':bucket['fail'],'unknown':bucket['unknown'],'islands':bucket['islands']}
    return report


def build_routes(measured, records_by_object, gate_failed):
    by={(row.get('object'), row.get('tag')):row for row in measured}
    routes=[]
    for row in measured:
        if row.get('tag') not in SOURCE_TAGS:continue
        record=records_by_object.get(row.get('object'))
        star=npm_star_check(record) if row.get('profile')=='NPM' else None
        route=provisional_route(row, star)
        routes.append({'object':row.get('object'),'profile':row.get('profile'),'source_tag':row.get('tag'),
                       'provisional_route':route,'definitive_route':None if gate_failed else route,
                       'source_islands':island_ledger(row),
                       'library_islands':island_ledger(by.get((row.get('object'),'ours'))),
                       'light_islands':island_ledger(by.get((row.get('object'),'light'))),
                       'star':star})
    return routes


def status_lines(calibration_gate, unknown_islands, failed_islands, blocked_objects, records):
    return [
        f'Калибровка исходников: {calibration_gate}; принятие не выдано (accepted=false).',
        f'Неразрешённые острова: неизвестных {unknown_islands}, провалов {failed_islands}.',
        f'Исходные объекты с провалом или неизвестным островом: {blocked_objects} из 99.',
        f'Сырые записи: {records}. Предварительные маршруты не являются калиброванным принятием.',
        'Фиолетовые пиксели — неизвестная непрозрачность, не семантическая разметка.',
    ]


def seal_diagnostic(measured, records_by_object):
    """Call the original gate after the inventory. A failure stays a failure."""
    source_rows=[row for row in measured if row.get('tag') in SOURCE_TAGS]
    names=[row.get('object') for row in source_rows]
    if len(names)!=len(set(names)):
        raise ValueError('duplicate source object')
    try:
        original_gate(source_rows)
    except ValueError as exc:
        gate,reason,failed='failed',str(exc),True
    else:
        gate,reason,failed='not_failed',None,False
    routes=build_routes(measured, records_by_object, failed)
    ledgers=[island for row in measured for island in island_ledger(row)]
    unknown=sum(island['unknown'] for island in ledgers)
    failed_islands=sum(island.get('pass') is not True for row in measured for island in (row.get('islands') or []))
    blocked=sum(source_unresolved(row) for row in source_rows)
    return {'accepted':False,'calibrated_acceptance':False,'replacement_failures_certified':False,
            'calibration_gate':gate,'calibration_gate_reason':reason,'definitive_routes_issued':not failed,
            'metrics':measured,'routes':routes,'distribution':build_distribution(measured),
            'status_lines':status_lines(gate, unknown, failed_islands, blocked, len(measured))}


def write_progress(checkpoint, partial, rows):
    last=rows[-1]
    payload={'complete':False,'accepted':False,'calibration_gate':None,'objects':len(rows),
             'last_object':last.get('object'),'last_tag':last.get('tag')}
    Path(checkpoint).write_text(json.dumps(payload),encoding='utf-8')
    Path(partial).write_text(json.dumps({'complete':False,'accepted':False,'objects':rows}),encoding='utf-8')


def measure_records(sequence, job, pictures, selected, checkpoint, partial):
    """Score every supplied record. The original gate is not called from this loop."""
    rows=[]
    for tag,key,record in sequence:
        use_pictures=pictures if pictures is not None and key in selected else None
        rows.append(analyze(record,key,tag,job,use_pictures))
        write_progress(checkpoint, partial, rows)
    return rows


def objects_for_sheet(job, material_id):
    for species in job.get('species') or []:
        if species.get('material_id')==material_id and isinstance(species.get('objects'),dict):
            return species['objects']
    return {}


def selected_names(job):
    names=set()
    for material_id in SHEET_IDS:
        for profile in ('NPM','VPM'):
            name=objects_for_sheet(job, material_id).get(profile)
            if isinstance(name,str) and name:
                names.add(name)
    return names


def row_summary(label, row):
    if row is None:
        return f'{label}: missing unknown=1 score=none'
    scores=[]
    for island in row.get('islands') or []:
        if _finite_score(island):scores.append(float(island['score']))
    shown='none' if not scores else ','.join(f'{score:.4f}' for score in scores[:6])
    return (f"{label} roles={row.get('roles')} pass_islands={row.get('passing_islands')} "
            f"unknown={row.get('unknown_metric_islands')} scores={shown}")


def compose_evidence_sheet(base_path, panels, summary_lines, dest):
    """Append masks under a render. Purple unknown pixels stay purple."""
    base_path,dest=Path(base_path),Path(dest)
    _refuse_review_write(dest)
    if base_path.resolve()==dest.resolve():
        raise ValueError('refusing to overwrite a render sheet')
    base=Image.open(base_path).convert('RGB')
    prepared=[]
    for label,mask_path,overlay_path in panels:
        if mask_path is None or overlay_path is None or not Path(mask_path).is_file() or not Path(overlay_path).is_file():
            prepared.append((f'{label} mask=missing',None,None))
            continue
        mask=Image.open(mask_path).convert('RGB')
        overlay=Image.open(overlay_path).convert('RGB')
        scale=min(1.0,360/max(mask.size))
        size=(max(1,int(mask.width*scale)),max(1,int(mask.height*scale)))
        prepared.append((label,mask.resize(size,Image.Resampling.NEAREST),overlay.resize(size,Image.Resampling.NEAREST)))
    font=ImageFont.load_default()
    text_h=14*(len(summary_lines)+1)
    width=max([base.width,960,*[mask.width*2+32 for _,mask,_ in prepared if mask is not None]])
    height=base.height+text_h+8
    for _,mask,_ in prepared:
        height+=18+(mask.height if mask is not None else 16)
    canvas=Image.new('RGB',(width,max(1,height)),(245,245,245))
    canvas.paste(base,(0,0))
    draw=ImageDraw.Draw(canvas)
    y=base.height+4
    for line in summary_lines:
        draw.text((4,y),line,fill=(0,0,0),font=font)
        y+=14
    y=base.height+text_h
    for label,mask,overlay in prepared:
        draw.text((4,y),label,fill=(0,0,0),font=font)
        y+=16
        if mask is not None:
            canvas.paste(mask,(0,y))
            canvas.paste(overlay,(mask.width+8,y))
            y+=mask.height+8
    dest.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(dest)
    return dest


def write_index(path, lines, sheet_names):
    text='\n'.join(lines)+'\n<!doctype html><meta charset="utf-8">\n'
    text+='<p>RAW diagnostic evidence. accepted=false.</p>\n'
    for name in sheet_names:
        text+=f'<p><a href="{name}">{name}</a></p>\n'
    Path(path).write_text(text,encoding='utf-8')


def panel_triplet(pictures, row):
    if row is None or pictures is None:
        return []
    found=[]
    for mask in sorted(Path(pictures).glob(f"{row['object']}-{row['tag']}-semantic-*-mask.png")):
        overlay=Path(str(mask).replace('-mask.png','-overlay.png'))
        found.append((f"{row['tag']} {row['object']}",mask,overlay))
    return found


def write_evidence_sheets(job, measured, pictures, output):
    by={(row.get('object'), row.get('tag')):row for row in measured}
    written=[]
    for material_id in SHEET_IDS:
        base=REVIEW_ROOT/f'{material_id}.png'
        objects=objects_for_sheet(job, material_id)
        lines=[f'#{material_id} raw diagnostic; purple unknown pixels are not semantic ground truth']
        panels=[]
        for profile in ('NPM','VPM'):
            name=objects.get(profile)
            for tag in ('original','florio','ours','light'):
                row=by.get((name,tag)) if name else None
                if row is None:continue
                lines.append(row_summary(f'{tag} {profile}', row))
                panels.extend(panel_triplet(pictures, row))
        dest=Path(output)/f'{material_id}.png'
        compose_evidence_sheet(base, panels, lines, dest)
        written.append(dest.name)
    return written


def split_records(data):
    if not isinstance(data,dict):
        raise ValueError('partial inventory')
    if data.get('failures'):
        raise ValueError('native failures '+str(data.get('failures')))
    scenes=data.get('scenes')
    if not isinstance(scenes,dict) or any(tag not in scenes or not isinstance(scenes[tag],dict) or not isinstance(scenes[tag].get('records'),dict) for tag in ('original','florio','ours')):
        raise ValueError('partial inventory')
    if not isinstance(data.get('light'),dict):
        raise ValueError('partial inventory')
    source=[]
    seen=set()
    for tag in SOURCE_TAGS:
        for key,record in scenes[tag]['records'].items():
            if not isinstance(key,str) or key in seen:
                raise ValueError('partial inventory')
            seen.add(key)
            source.append((tag,key,record))
    ours=[]
    for key,record in scenes['ours']['records'].items():
        if not isinstance(key,str):
            raise ValueError('partial inventory')
        ours.append((key,record))
    light=[]
    light_seen=set()
    for name,record in data['light'].items():
        if not isinstance(name,str):
            raise ValueError('partial inventory')
        key=name.removesuffix('_light')
        if key in light_seen:
            raise ValueError('partial inventory')
        light_seen.add(key)
        light.append((key,record))
    if len(source)!=99 or len(ours)!=99 or {key for _,key,_ in source}!={key for key,_ in ours} or len(light)!=3:
        raise ValueError('partial inventory')
    return source,ours,light


def measurement_sequence(source, ours, light):
    sequence=list(source)
    sequence.extend(('ours',key,record) for key,record in ours)
    sequence.extend(('light',key,record) for key,record in light)
    return sequence


def input_paths(job_path, inventory_path, job):
    paths=[Path(job_path),Path(inventory_path)]
    for scene in job.get('scenes') or []:
        if isinstance(scene,dict) and scene.get('maps'):
            paths.append(Path(scene['maps']))
    for copied in (job.get('bitmap_copies') or {}).values():
        paths.append(Path(copied))
    return paths


def write_report(output, report, sheet_names):
    output=Path(output)
    metrics={'accepted':False,'calibrated_acceptance':False,'replacement_failures_certified':False,
             'calibration_gate':report['calibration_gate'],'calibration_gate_reason':report['calibration_gate_reason'],
             'count':len(report['metrics']),'records':report['metrics']}
    routes={'accepted':False,'calibrated_acceptance':False,'replacement_failures_certified':False,
            'calibration_gate':report['calibration_gate'],'definitive_routes_issued':report['definitive_routes_issued'],
            'count':len(report['routes']),'routes':report['routes']}
    distribution={'accepted':False,'calibration_gate':report['calibration_gate'],'groups':report['distribution']}
    (output/'metrics.json').write_text(json.dumps(metrics),encoding='utf-8')
    (output/'routes.json').write_text(json.dumps(routes),encoding='utf-8')
    (output/'distribution.json').write_text(json.dumps(distribution),encoding='utf-8')
    write_index(output/'index.html', report['status_lines'], sheet_names)
    (output/'checkpoint.json').write_text(json.dumps({
        'complete':False,'inventory_complete':True,'accepted':False,
        'calibration_gate':report['calibration_gate'],'objects':len(report['metrics']),
        'routes':len(report['routes'])}),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    job=json.loads(Path(args.job).read_text(encoding='utf-8'))
    if not isinstance(job,dict) or 'work' not in job or 'inventory' not in job:
        raise ValueError('partial inventory')
    inventory_path=Path(job['work'])/job['inventory']
    data=json.loads(inventory_path.read_text(encoding='utf-8'))
    source,ours,light=split_records(data)
    review_sheets=[REVIEW_ROOT/f'{material_id}.png' for material_id in SHEET_IDS]
    missing=[path for path in review_sheets if not path.is_file()]
    if missing:
        raise ValueError('review sheet missing '+str(missing[0]))
    inputs=input_paths(args.job, inventory_path, job)+[REVIEW_ROOT,*review_sheets]
    guard_run_paths(inputs, args.output)
    args.output.mkdir(parents=True)
    pictures=args.output/'panels'
    pictures.mkdir()
    rows=measure_records(measurement_sequence(source, ours, light), job, pictures, selected_names(job),
                         args.output/'checkpoint.json', args.output/'metrics.partial.json')
    records={key:record for _,key,record in source}
    report=seal_diagnostic(rows, records)
    sheets=write_evidence_sheets(job, rows, pictures, args.output)
    write_report(args.output, report, sheets)
    print(json.dumps({'objects':len(rows),'routes':len(report['routes']),'calibration_gate':report['calibration_gate'],'accepted':False}),flush=True)


if __name__=='__main__':
    main()
