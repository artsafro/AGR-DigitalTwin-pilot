"""Run #369 geometric calibration on copied native inventory and bitmaps.

Pattern: n/a | new-case: full Flora island accounting with conservative unknowns.
Class colours are RGB heuristics, NOT ground-truth foliage/bark annotation.
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


def compact_measure(record, indices, alpha, cells, profile, whole_texture=True):
    """Native-pixel clipping in a cropped ROI; exact polygon area via Shapely."""
    if profile not in ('NPM','VPM'):raise ValueError('unsupported profile '+str(profile))
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
    score=area.intersection(rectangle).area/rectangle.area if profile=='VPM' else rectangle.area/area.area
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
    return result,offset,target


def classify_pixels(rgb,alpha):
    """Display-only hypotheses, unknown brown/red flowers are not silently bark."""
    r,g,b=rgb.astype(float).transpose(2,0,1)
    green=(g>r*1.05)&(g>b*1.05)&alpha
    brown=(r>g*1.1)&(g>b*1.1)&alpha
    out=np.full((*alpha.shape,3),235,np.uint8)
    out[alpha]=(160,80,200);out[green]=(40,170,50);out[brown]=(150,95,40)
    return Image.fromarray(out),{'foliage_candidate':int(green.sum()),'bark_candidate':int(brown.sum()),'unknown_opaque':int((alpha&~green&~brown).sum()),'empty':int((~alpha).sum())}


MEASURE_CACHE={}


def analyze(record,key,tag,job,pictures=None):
    profile=key.split('_')[-1];vertices=np.asarray(record['vertices']);faces=np.asarray(record['faces'])
    height=float(np.ptp(vertices[:,2]));groups=uv_components(record['uvfaces'],len(record['uv']));rows=[];panels={}
    elements=uv_components(record['faces'],len(vertices));face_elements={};element_roles={}
    for element,element_faces in enumerate(elements):
        element_roles[element]=island_role(vertices[np.unique(faces[element_faces])],height,profile)
        for face in element_faces:face_elements[face]=element
    for number,indices in enumerate(groups):
        ids=sorted({record['face_material_ids'][i] for i in indices})
        owners=sorted({face_elements[i] for i in indices})
        roles={element_roles[e] for e in owners}
        role,reason=roles.pop() if len(roles)==1 else ('unknown','UV component spans elements with different geometric roles')
        row={'island':number,'faces':indices,'role':role,'role_reason':reason,'material_ids':ids,'geometry_elements':owners}
        try:
            mat=slot_material(record,ids);paths=bound_images(mat,tag,job);rgb,alpha,cells=images(*paths)
            corners=np.asarray(record['uv'])[np.asarray(record['uvfaces'])[indices]]
            whole_texture=tag in ('ours','light')
            cache_key=(paths,profile,whole_texture,tuple(sorted(tuple(sorted(map(tuple,triangle))) for triangle in corners)))
            if cache_key not in MEASURE_CACHE:
                MEASURE_CACHE[cache_key]=compact_measure(record,indices,alpha,cells,profile,whole_texture)
            result,offset,target=MEASURE_CACHE[cache_key]
            row.update(result,bitmap=paths[0],opacity=paths[1],alpha_mode=paths[2],sprite_bbox=target,
                       candidate_cells=len(cells),integer_tile_offset=offset,
                       star_uv_extent=np.ptp(np.asarray(record['uv'])[np.unique(np.asarray(record['uvfaces'])[indices])],axis=0).tolist())
            row['geometric_pass']=row['pass']
            row['policy_applicable']=role!='unknown' and (profile!='NPM' or role=='star_plane')
            row['pass']=row['pass'] and row['policy_applicable']
            row['plant_region']='whole bound texture' if whole_texture else 'independent alpha-cell candidate in original atlas'
            if pictures is not None:
                if paths not in panels:
                    mask,counts=classify_pixels(rgb,alpha);panels[paths]={'mask':mask,'overlay':mask.copy(),'classes':counts,'islands':[]}
                panel=panels[paths];panel['islands'].append(number)
                draw=ImageDraw.Draw(panel['overlay']);color=(20,130,240) if role=='unknown' else ((0,220,40) if result['pass'] else (255,30,30))
                uv=np.asarray(record['uv'])-offset;h,w=alpha.shape
                for face in np.asarray(record['uvfaces'])[indices]:
                    p=[(float(uv[i,0]*w),float((1-uv[i,1])*h)) for i in face];draw.line(p+[p[0]],fill=color,width=max(1,w//600))
                x,y,X,Y=target;draw.rectangle((x,y,X-1,Y-1),outline=(0,180,255),width=max(1,w//600))
        except ValueError as exc:row.update(status='unknown',error=str(exc),**{'pass':False})
        rows.append(row)
    if sum(len(r['faces']) for r in rows)!=record['triangles']:raise ValueError('lost faces '+key)
    if pictures is not None:
        for i,(paths,panel) in enumerate(panels.items()):
            name=f'{key}-{tag}-semantic-{i}'
            for kind in ('mask','overlay'):panel[kind].save(pictures/f'{name}-{kind}.png')
    return {'object':key,'source_name':record['name'],'profile':profile,'tag':tag,'triangles':record['triangles'],
            'islands':rows,'roles':dict(Counter(r['role'] for r in rows)),
            'unknown_metric_islands':sum('score' not in r for r in rows),
            'scored_islands':sum('score' in r for r in rows),
            'passing_islands':sum(r['pass'] for r in rows),
            'class_masks':[{'diffuse':k[0],'opacity':k[1],'classes':v['classes']} for k,v in panels.items()]}


def original_gate(rows):
    """No replacement scoring from incomplete, failed or unknown originals."""
    if len(rows)!=99 or len({r.get('object') for r in rows})!=99:raise ValueError('99 unique original objects required')
    for row in rows:
        if not row.get('islands'):raise ValueError('empty original islands '+str(row.get('object')))
        for island in row['islands']:
            if island.get('pass') is not True or island.get('role')=='unknown' or not np.isfinite(island.get('score',float('nan'))):
                raise ValueError('original calibration not clean: '+str(row.get('object'))+' island '+str(island.get('island')))


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pictures',type=Path)
    args=p.parse_args();job=json.loads(args.job.read_text());inventory=Path(job['work'])/job['inventory']
    guard_outputs([args.job,inventory],[args.output,args.output.with_suffix('.partial.json')]+([args.pictures] if args.pictures else []))
    if args.pictures:args.pictures.mkdir(parents=True)
    data=json.loads(inventory.read_text(encoding='utf-8'))
    if data['failures']:raise ValueError('native failures '+str(data['failures']))
    selected={s['objects'][profile] for s in job['species'] if s['material_id'] in [101,102,103,105,204,225] for profile in ('NPM','VPM') if profile in s['objects']}
    rows=[];started=time.perf_counter()
    for tag,scene in data['scenes'].items():
        if tag=='ours':original_gate(rows)
        for key,record in scene['records'].items():
            rows.append(analyze(record,key,tag,job,args.pictures if key in selected else None))
            print(tag,key,rows[-1]['scored_islands'],rows[-1]['passing_islands'],'cache',len(MEASURE_CACHE),flush=True)
            args.output.with_suffix('.partial.json').write_text(json.dumps({'objects':rows,'complete':False}),encoding='utf-8')
        print(tag,len(scene['records']),flush=True)
    for name,record in data['light'].items():
        rows.append(analyze(record,name.removesuffix('_light'),'light',job,args.pictures))
    counts={tag:{'objects':len([r for r in rows if r['tag']==tag]),'islands':sum(len(r['islands']) for r in rows if r['tag']==tag),'scored':sum(r['scored_islands'] for r in rows if r['tag']==tag),'passing':sum(r['passing_islands'] for r in rows if r['tag']==tag),'unknown':sum(r['unknown_metric_islands'] for r in rows if r['tag']==tag)} for tag in ('original','florio','ours','light')}
    result={'policy':'Artem 2026-10-20 geometric bbox; replaces prior density metrics','resolution':'native bitmap dimensions; 1 pixel dilation for NPM clipping','atlas_segmentation':'alpha-only whitespace guillotine candidates, touching sprites unresolved','pixel_classes':'RGB heuristic candidates, NOT semantic ground truth','objects':rows,'counts':counts,'seconds':time.perf_counter()-started,'accepted':False}
    args.output.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');print(json.dumps(counts),flush=True)


if __name__=='__main__':main()
