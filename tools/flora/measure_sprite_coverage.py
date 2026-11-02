"""Run #369 geometric calibration on copied native inventory and bitmaps.

Pattern: n/a | new-case: full Flora island accounting with conservative unknowns.
Class colours are RGB heuristics, NOT ground-truth foliage/bark annotation.
Continuous bark is containment on an explicit bark mask, never opacity alone.
Source trunks score only from a reviewed atlas bbox, for both NPM and VPM.
"""
import argparse
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path, PureWindowsPath
import time
import numpy as np
from PIL import Image, ImageDraw
from diagnose_texture import guard_outputs, resolve_bitmap
from sprite_coverage import bbox, coverage, island_role, sprite_cells, uv_components


def slot_material(record, ids):
    mat=record['material']
    if mat['class']=='Standardmaterial':return mat
    if mat['class']!='Multimaterial':raise ValueError('unsupported material '+mat['class'])
    if len(ids)!=1:raise ValueError('UV component spans multiple material slots '+str(ids))
    slots=mat.get('submaterial_ids',[])
    if len(slots)!=len(mat['submaterials']) or slots.count(ids[0])!=1:raise ValueError('unmapped material ID '+str(ids))
    sub=mat['submaterials'][slots.index(ids[0])]
    if sub is None:raise ValueError('empty material slot '+str(ids))
    return sub


def map_path(mat, slot, tag, job):
    name=mat['slot_paths'].get(slot)
    if not name:raise ValueError('unmapped '+slot+' in '+mat['name'])
    if tag in ('ours','light'):
        key=name.replace('\\','/').lower()
        if key not in job['bitmap_copies']:raise ValueError('unmapped bitmap '+name)
        return job['bitmap_copies'][key]
    scene=next(s for s in job['scenes'] if s['tag']==tag)
    return str(resolve_bitmap(name,scene['maps']))


@lru_cache(maxsize=16)
def images(diffuse, opacity, alpha_mode):
    rgb=np.asarray(Image.open(diffuse).convert('RGB'))
    image=Image.open(opacity).convert('RGBA')
    a=np.asarray(image.getchannel('A') if alpha_mode else image.convert('L'))>=128
    if rgb.shape[:2]!=a.shape:raise ValueError('map size mismatch')
    return rgb,a,sprite_cells(a)


IMAGE_DERIVED={}


def _cached(key, build):
    if key not in IMAGE_DERIVED:
        IMAGE_DERIVED[key]=build()
    return IMAGE_DERIVED[key]


_clear_loaded_images=images.cache_clear


def clear_loaded_images():
    """Drop decoded bitmaps and every mask derived from them."""
    IMAGE_DERIVED.clear()
    _clear_loaded_images()


images.cache_clear=clear_loaded_images


def bound_images(mat,tag,job):
    if not mat['bindings'].get('opacityMapEnable'):raise ValueError('opacity disabled '+mat['name'])
    diffuse=map_path(mat,'diffuseMap',tag,job);opacity=map_path(mat,'opacityMap',tag,job)
    mode=mat.get('slot_settings',{}).get('opacityMap',{}).get('monoOutput')
    if mode not in (0,1):raise ValueError('unsupported opacity slot mode '+str(mode)+' '+mat['name'])
    alpha_mode=mode==1
    for t in mat['textures']:
        c=t['coords']
        if any(c.get(k)!=v for k,v in {'mapChannel':1,'U_Tiling':1.0,'V_Tiling':1.0,'U_Offset':0.0,'V_Offset':0.0,'U_Angle':0.0,'V_Angle':0.0,'W_Angle':0.0,'U_Mirror':False,'V_Mirror':False}.items()):
            raise ValueError('unsupported texture transform '+t['name'])
    return diffuse,opacity,alpha_mode


def island_mask(record, indices, shape):
    uv=np.asarray(record['uv'],float);faces=np.asarray(record['uvfaces'])[indices]
    points=uv[np.unique(faces)]
    if not np.isfinite(points).all():raise ValueError('nonfinite UV')
    # Bitmap tiling is explicitly enabled; unwrap an integer-offset cell, never
    # modulo corners individually (which would turn boundary faces inside out).
    offset=np.floor(points.min(axis=0)+1e-7);uv=uv-offset
    if (uv[np.unique(faces)] < -1e-6).any() or (uv[np.unique(faces)]>1+1e-6).any():raise ValueError('island crosses repeated bitmap tile')
    h,w=shape
    polygons=[[(float(uv[i,0]*w),float((1-uv[i,1])*h)) for i in face] for face in faces]
    points=np.array([p for poly in polygons for p in poly])
    x,y=np.maximum(np.floor(points.min(axis=0)).astype(int)-2,0)
    X,Y=np.minimum(np.ceil(points.max(axis=0)).astype(int)+3,[w,h])
    im=Image.new('1',(int(X-x),int(Y-y)));draw=ImageDraw.Draw(im)
    for poly in polygons:draw.polygon([(px-x,py-y) for px,py in poly],fill=1)
    return np.asarray(im,dtype=bool),offset.tolist(),(int(x),int(y),int(X),int(Y)),polygons


BARK_STRIP_PROVENANCE=(
    'source opacity-cell candidate only, independent of UV islands: '
    'aspect height/width>=3 and opaque occupancy>=0.95; not a semantic bark mask')
REVIEWED_BARK_PROVENANCE=(
    'reviewed atlas bbox intersected with opacity; containment on that mask; '
    'not an RGB heuristic and not a tall-strip candidate')


def bitmap_key(path):
    return str(path).replace('\\','/').lower()


def _integer_bbox(bbox, width, height):
    valid=(isinstance(bbox,(list,tuple)) and not isinstance(bbox,(str,bytes)) and len(bbox)==4
           and all(type(v) is int for v in bbox)
           and 0<=bbox[0]<bbox[2]<=width and 0<=bbox[1]<bbox[3]<=height)
    if not valid:raise ValueError('malformed reviewed bark bbox')
    return [int(v) for v in bbox]


def reviewed_bark_region(job, diffuse, shape):
    """Reviewed rectangles for one diffuse, or None when that path is not certified.

    Only reviewed is True, plus a note and either bbox or bboxes, may score.
    Several rectangles are stored as a list. Callers union those masks; they must
    not replace an L-shaped strip by its bounding square.
    """
    if 'bark_annotations' not in job or job['bark_annotations'] is None:return None
    raw=job['bark_annotations']
    if raw=={}:return None
    if not isinstance(raw,dict):raise ValueError('bark_annotations must map normalized diffuse paths')
    table={}
    for key,value in raw.items():
        norm=bitmap_key(key)
        if norm in table:raise ValueError('duplicate bark annotation '+norm)
        table[norm]=value
    entry=table.get(bitmap_key(diffuse))
    if not isinstance(entry,dict) or entry.get('reviewed') is not True:return None
    note=entry.get('note')
    height,width=shape
    has_bbox='bbox' in entry
    has_boxes='bboxes' in entry
    if has_bbox==has_boxes or not isinstance(note,str):
        raise ValueError('malformed reviewed bark bbox')
    if has_boxes:
        boxes=entry['bboxes']
        if isinstance(boxes,(str,bytes)) or not isinstance(boxes,(list,tuple)) or len(boxes)==0:
            raise ValueError('malformed reviewed bark bbox')
        boxes=[_integer_bbox(box,width,height) for box in boxes]
    else:
        boxes=[_integer_bbox(entry.get('bbox'),width,height)]
    result={'boxes':[list(box) for box in boxes],'note':note}
    if len(boxes)==1:result['bbox']=list(boxes[0])
    return result


def reviewed_bark_mask(alpha, bbox):
    """Pixels inside one reviewed rectangle that are also opaque. No colour test."""
    mask=np.zeros(np.shape(alpha),dtype=bool)
    left,top,right,bottom=bbox
    mask[top:bottom,left:right]=True
    return mask & np.asarray(alpha,dtype=bool)


def reviewed_bark_union(alpha, boxes):
    """Union of reviewed rectangles, then opacity. Overlaps count once. No colour test."""
    mask=None
    for box in boxes:
        part=reviewed_bark_mask(alpha, box)
        mask=part if mask is None else mask|part
    if mask is None:raise ValueError('malformed reviewed bark bbox')
    return mask


def bark_strip_candidates(alpha, cells):
    """Tall, nearly solid opacity cells. Annotation only, not a bark label."""
    found=[]
    for index,(left,top,right,bottom) in enumerate(cells):
        width,height=right-left,bottom-top
        if width<=0 or height<=0 or height/width<3:continue
        opaque=int(np.asarray(alpha)[top:bottom,left:right].sum());occupancy=opaque/(width*height)
        if opaque*20>=width*height*19:
            found.append({'cell':index,'bbox':[int(left),int(top),int(right),int(bottom)],
                          'aspect_height_over_width':height/width,'opaque_occupancy':occupancy})
    return found


def brown_candidate_mask(rgb, alpha):
    red,green,blue=np.asarray(rgb).astype(float).transpose(2,0,1)
    return (red>green*1.1)&(green>blue*1.1)&np.asarray(alpha,bool)


def bark_containment(record, indices, alpha, bark_mask):
    """Share of island raster pixels that lie on an explicit semantic bark mask."""
    if bark_mask is None:
        raise ValueError('explicit bark mask required for trunk; refusing to infer bark from opacity')
    mask=np.asarray(bark_mask)
    if mask.ndim!=2 or mask.shape!=np.shape(alpha) or mask.dtype!=np.bool_ or not mask.size or not np.isfinite(mask).all():
        raise ValueError('finite bool same-size bark mask required')
    island,offset,roi,_=island_mask(record,indices,np.shape(alpha))
    left,top,right,bottom=roi
    area=int(island.sum())
    if area<=0:raise ValueError('empty island raster')
    overlap=int((island&mask[top:bottom,left:right]).sum())
    score=overlap/area
    rows,cols=np.nonzero(island)
    target=(int(left+cols.min()),int(top+rows.min()),int(left+cols.max())+1,int(top+rows.max())+1)
    result={'score':score,'pass':bool(overlap*20>=area*19),'metric':'bark_containment',
            'island_area_px':area,'bark_overlap_px':overlap}
    return result,offset,target


def compact_measure(record, indices, alpha, cells, profile, whole_texture=True, role='foliage', bark_mask=None):
    """Native-pixel clipping in a cropped ROI; exact polygon area via Shapely."""
    if profile not in ('NPM','VPM'):raise ValueError('unsupported profile '+str(profile))
    if role=='trunk':return bark_containment(record,indices,alpha,bark_mask)
    from shapely import Polygon, box, union_all
    m,offset,roi,polygons=island_mask(record,indices,alpha.shape)
    x,y,X,Y=roi;local=alpha[y:Y,x:X]
    counts=[]
    for l,t,r,b in cells:
        L,T,R,B=max(l,x),max(t,y),min(r,X),min(b,Y)
        counts.append(int((m[T-y:B-y,L-x:R-x]&alpha[T:B,L:R]).sum()) if L<R and T<B else 0)
    maximum=max(counts)
    if not maximum:raise ValueError('no opaque sprite intersects island')
    chosen=[i for i,n in enumerate(counts) if n==maximum]
    if len(chosen)!=1:raise ValueError('ambiguous sprite cell '+str(chosen))
    target=(min(c[0] for c in cells),min(c[1] for c in cells),max(c[2] for c in cells),max(c[3] for c in cells)) if profile=='NPM' and whole_texture else cells[chosen[0]]
    l,t,r,b=target;area=union_all([Polygon(p) for p in polygons]);rectangle=box(l,t,r,b)
    if not area.is_valid or area.area<=0:raise ValueError('invalid polygon area')
    intersection=area.intersection(rectangle).area
    bbox_over_island=rectangle.area/area.area
    region_coverage=intersection/rectangle.area
    # NPM pass stays on bbox/island. Region coverage is recorded beside it.
    score=region_coverage if profile=='VPM' else bbox_over_island
    selected=np.zeros_like(m);L,T,R,B=max(l,x),max(t,y),min(r,X),min(b,Y)
    if L<R and T<B:selected[T-y:B-y,L-x:R-x]=True
    overlap=int((m&local&selected).sum());neighbour=int((m&local&~selected).sum())
    padded=np.pad(m,1);dilated=np.zeros_like(m)
    for dy in range(3):
        for dx in range(3):dilated|=padded[dy:dy+m.shape[0],dx:dx+m.shape[1]]
    clipped=int(alpha[t:b,l:r].sum())-int((dilated&local&selected).sum())
    passed=.80<=score<=.95 and (profile!='NPM' or clipped==0)
    if profile=='VPM' and score>.95:passed=neighbour==0
    result={'score':score,'pass':bool(passed),'island_area_px':area.area,'sprite_bbox_area_px':rectangle.area,
            'clipped_opaque_px_tolerance_1':clipped,'neighbour_opaque_px':neighbour,
            'opaque_density':int((m&local).sum())/max(1,int(m.sum()))}
    if profile=='NPM':
        result['bbox_area_over_island_area']=bbox_over_island
        result['island_intersect_target_bbox_over_target_bbox']=region_coverage
        result['ratio_labels']={
            'bbox_area_over_island_area':'area(target bbox)/area(island)',
            'island_intersect_target_bbox_over_target_bbox':'area(island intersect target bbox)/area(target bbox)',
            'clipped_opaque_px_tolerance_1':'clipped opaque pixels in the target bbox outside the island, 1px tolerance',
        }
    return result,offset,target


def classify_pixels(rgb,alpha):
    """Display-only hypotheses, unknown brown/red flowers are not silently bark."""
    r,g,b=rgb.astype(float).transpose(2,0,1)
    green=(g>r*1.05)&(g>b*1.05)&alpha
    brown=brown_candidate_mask(rgb,alpha)
    out=np.full((*alpha.shape,3),235,np.uint8)
    out[alpha]=(160,80,200);out[green]=(40,170,50);out[brown]=(150,95,40)
    return Image.fromarray(out),{'foliage_candidate':int(green.sum()),'bark_candidate':int(brown.sum()),'unknown_opaque':int((alpha&~green&~brown).sum()),'empty':int((~alpha).sum())}


MEASURE_CACHE={}


def analyze(record,key,tag,job,pictures=None):
    if 'geometry_parts' in job and type(job['geometry_parts']) is not bool:
        raise ValueError('geometry_parts must be bool')
    profile=key.split('_')[-1];vertices=np.asarray(record['vertices']);faces=np.asarray(record['faces'])
    metric_record={**record,'uv':np.asarray(record['uv']),'uvfaces':np.asarray(record['uvfaces'])}
    height=float(np.ptp(vertices[:,2]));groups=uv_components(record['uvfaces'],len(record['uv']));rows=[];panels={}
    elements=uv_components(record['faces'],len(vertices));face_elements={};element_roles={}
    for element,element_faces in enumerate(elements):
        element_roles[element]=island_role(vertices[np.unique(faces[element_faces])],height,profile)
        for face in element_faces:face_elements[face]=element
    part_charts=None;parts=[]
    if job.get('geometry_parts') is True:
        from geometry_parts import parts_and_charts
        parts,part_charts=parts_and_charts(record)
        groups=[chart['faces'] for chart in part_charts]
    source=tag in ('original','florio');annotations=[];seen=set()
    for number,indices in enumerate(groups):
        ids=sorted({record['face_material_ids'][i] for i in indices})
        owners=sorted({face_elements[i] for i in indices})
        roles={element_roles[e] for e in owners}
        role,reason=roles.pop() if len(roles)==1 else ('unknown','UV component spans elements with different geometric roles')
        if part_charts is not None:
            role,reason=part_charts[number]['role'],part_charts[number]['reason']
            part_ids=part_charts[number]['geometry_parts']
            if profile=='NPM' and role=='foliage' and all(
                    parts[i]['kind']=='flat_card' and float(np.ptp(vertices[np.unique(faces[parts[i]['faces']]),2]))>=.75*height
                    for i in part_ids):
                role='star_plane'
                reason+='; full-height flat-card candidate, star arrangement checked separately'
        row={'island':number,'faces':indices,'role':role,'role_reason':reason,'material_ids':ids,'geometry_elements':owners}
        if part_charts is not None:row['geometry_parts']=part_charts[number]['geometry_parts']
        try:
            mat=slot_material(record,ids);paths=bound_images(mat,tag,job);rgb,alpha,cells=images(*paths)
            if source:
                candidates=_cached(('strips', paths), lambda a=alpha, c=cells: bark_strip_candidates(a, c))
                row['bark_strip_candidates']=candidates;row['bark_strip_provenance']=BARK_STRIP_PROVENANCE
                if paths not in seen:
                    seen.add(paths)
                    annotations.append({'diffuse':paths[0],'opacity':paths[1],'candidates':candidates,'provenance':BARK_STRIP_PROVENANCE})
            annotation=reviewed_bark_region(job,paths[0],alpha.shape) if role=='trunk' and source else None
            if role=='trunk' and source and annotation is None:
                if len(row['bark_strip_candidates'])!=1:raise ValueError('ambiguous or missing source bark strip')
                row.update(status='candidate_only',semantic_pass=False,bitmap=paths[0],opacity=paths[1],alpha_mode=paths[2])
                row['pass']=False
            else:
                corners=metric_record['uv'][metric_record['uvfaces'][indices]]
                whole_texture=tag in ('ours','light')
                if annotation is not None:
                    boxes=annotation['boxes']
                    box_key=tuple(tuple(box) for box in boxes)
                    bark=_cached(('reviewed', paths, box_key), lambda a=alpha, b=box_key: reviewed_bark_union(a, b))
                    mask_id=('reviewed', box_key)
                else:
                    bark=_cached(('brown', paths), lambda rgb=rgb, a=alpha: brown_candidate_mask(rgb, a)) if role=='trunk' else None
                    mask_id=('heuristic',) if role=='trunk' else ('sprite',)
                cache_key=(paths,profile,whole_texture,role,mask_id,tuple(sorted(tuple(sorted(map(tuple,triangle))) for triangle in corners)))
                if cache_key not in MEASURE_CACHE:
                    MEASURE_CACHE[cache_key]=compact_measure(metric_record,indices,alpha,cells,profile,whole_texture,role,bark)
                result,offset,target=MEASURE_CACHE[cache_key]
                row.update(result,bitmap=paths[0],opacity=paths[1],alpha_mode=paths[2],sprite_bbox=target,
                           candidate_cells=len(cells),integer_tile_offset=offset,
                           star_uv_extent=np.ptp(metric_record['uv'][np.unique(metric_record['uvfaces'][indices])],axis=0).tolist())
                if annotation is not None:
                    row['geometric_pass']=bool(result['pass']);row['semantic_confidence']='reviewed_region'
                    row['semantic_pass']=False;row['measurement_scope']='reviewed_region'
                    row['policy_applicable']=profile in ('NPM','VPM')
                    row['pass']=bool(result['pass']) and row['policy_applicable']
                    row['containment_provenance']=REVIEWED_BARK_PROVENANCE
                    row['reviewed_bboxes']=[list(box) for box in annotation['boxes']]
                    if 'bbox' in annotation:row['reviewed_bbox']=list(annotation['bbox'])
                    row['reviewed_note']=annotation['note']
                    row['plant_region']='reviewed bark bbox intersected with opacity'
                elif role=='trunk':
                    row['geometric_pass']=bool(result['pass']);row['semantic_confidence']='unverified'
                    row['semantic_pass']=False;row['measurement_scope']='geometric_only';row['pass']=False
                    row['plant_region']='whole bound texture' if whole_texture else 'independent alpha-cell candidate in original atlas'
                else:
                    row['geometric_pass']=row['pass']
                    row['policy_applicable']=role!='unknown' and (profile!='NPM' or role=='star_plane')
                    row['pass']=row['pass'] and row['policy_applicable']
                    row['plant_region']='whole bound texture' if whole_texture else 'independent alpha-cell candidate in original atlas'
                if pictures is not None:
                    if paths not in panels:
                        mask,counts=classify_pixels(rgb,alpha);panels[paths]={'mask':mask,'overlay':mask.copy(),'classes':counts,'islands':[]}
                    panel=panels[paths];panel['islands'].append(number)
                    draw=ImageDraw.Draw(panel['overlay']);color=(20,130,240) if role=='unknown' else ((0,220,40) if row['pass'] else (255,30,30))
                    uv=metric_record['uv']-offset;h,w=alpha.shape
                    for face in metric_record['uvfaces'][indices]:
                        p=[(float(uv[i,0]*w),float((1-uv[i,1])*h)) for i in face];draw.line(p+[p[0]],fill=color,width=max(1,w//600))
                    x,y,X,Y=target;draw.rectangle((x,y,X-1,Y-1),outline=(0,180,255),width=max(1,w//600))
        except ValueError as exc:row.update(status='unknown',error=str(exc),**{'pass':False})
        rows.append(row)
    if sum(len(r['faces']) for r in rows)!=record['triangles']:raise ValueError('lost faces '+key)
    if pictures is not None:
        for i,(paths,panel) in enumerate(panels.items()):
            name=f'{key}-{tag}-semantic-{i}'
            for kind in ('mask','overlay'):panel[kind].save(pictures/f'{name}-{kind}.png')
    result={'object':key,'source_name':record['name'],'profile':profile,'tag':tag,'triangles':record['triangles'],
            'islands':rows,'roles':dict(Counter(r['role'] for r in rows)),
            'unknown_metric_islands':sum('score' not in r for r in rows),
            'scored_islands':sum('score' in r for r in rows),
            'passing_islands':sum(r['pass'] for r in rows),
            'class_masks':[{'diffuse':k[0],'opacity':k[1],'classes':v['classes'],'islands':v['islands']} for k,v in panels.items()]}
    if part_charts is not None:
        result['role_method']='geometry_parts'
        result['geometry_parts']=parts
    if source:result['bark_strip_annotations']=annotations
    return result


def original_gate(rows):
    """No replacement scoring from incomplete, failed or unknown originals."""
    if len(rows)!=99 or len({r.get('object') for r in rows})!=99:raise ValueError('99 unique original objects required')
    for row in rows:
        if not row.get('islands'):raise ValueError('empty original islands '+str(row.get('object')))
        for island in row['islands']:
            if (island.get('pass') is not True or island.get('role') not in ('foliage','trunk','star_plane')
                    or island.get('status') in ('unknown','failed','fail','error','candidate_only','not_run','review')
                    or type(island.get('score')) is bool or not np.isfinite(island.get('score',float('nan')))):
                raise ValueError('original calibration not clean: '+str(row.get('object'))+' island '+str(island.get('island')))


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pictures',type=Path)
    p.add_argument('--sources-only',action='store_true',help='score original and florio only and skip the replacement gate')
    args=p.parse_args();job=json.loads(args.job.read_text());inventory=Path(job['work'])/job['inventory']
    guard_outputs([args.job,inventory],[args.output,args.output.with_suffix('.partial.json')]+([args.pictures] if args.pictures else []))
    if args.pictures:args.pictures.mkdir(parents=True)
    data=json.loads(inventory.read_text(encoding='utf-8'))
    if data['failures']:raise ValueError('native failures '+str(data['failures']))
    selected={s['objects'][profile] for s in job['species'] if s['material_id'] in [101,102,103,105,204,225] for profile in ('NPM','VPM') if profile in s['objects']}
    rows=[];started=time.perf_counter();source_tags=('original','florio')
    for tag,scene in data['scenes'].items():
        if args.sources_only and tag not in source_tags:continue
        if tag=='ours' and not args.sources_only:original_gate(rows)
        for key,record in scene['records'].items():
            rows.append(analyze(record,key,tag,job,args.pictures if key in selected else None))
            print(tag,key,rows[-1]['scored_islands'],rows[-1]['passing_islands'],'cache',len(MEASURE_CACHE),flush=True)
            args.output.with_suffix('.partial.json').write_text(json.dumps({'objects':rows,'complete':False}),encoding='utf-8')
        print(tag,len(scene['records']),flush=True)
    if not args.sources_only:
        for name,record in data['light'].items():
            rows.append(analyze(record,name.removesuffix('_light'),'light',job,args.pictures))
    counts={tag:{'objects':len([r for r in rows if r['tag']==tag]),'islands':sum(len(r['islands']) for r in rows if r['tag']==tag),'scored':sum(r['scored_islands'] for r in rows if r['tag']==tag),'passing':sum(r['passing_islands'] for r in rows if r['tag']==tag),'unknown':sum(r['unknown_metric_islands'] for r in rows if r['tag']==tag)} for tag in ('original','florio','ours','light')}
    result={'policy':'D155: sprite bbox for discrete roles; bark containment >=95% of island raster on explicit bark pixels','resolution':'native bitmap dimensions; 1 pixel dilation for NPM clipping','atlas_segmentation':'alpha-only whitespace guillotine candidates, touching sprites unresolved','pixel_classes':'RGB heuristic candidates, NOT semantic ground truth','objects':rows,'counts':counts,'seconds':time.perf_counter()-started,'accepted':False}
    if args.sources_only:
        result['sources_only']=True;result['complete']=True;result['original_gate']='not_required'
    args.output.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');print(json.dumps(counts),flush=True)


if __name__=='__main__':main()
