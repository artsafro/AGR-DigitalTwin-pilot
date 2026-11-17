"""new-case: source-bound course-grid D/ERM/Normal bake around existing cores.

Experimental reusable entry point, not `agr unwrap-atlas` or a delivery validator.
Every input is hash-bound. No fitting, density fallback, geometry edits, live DCC
access or source writes. Readback, all-map equivalence and visual gates stay open.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from adapters.max.agr_tools.udimtile_core import tile_origin

ROLES = frozenset(('layout','references','chart','placements_1001','placements_1002',
    'base_fields','historical_fields','actual_fields','boundary_report',
    'source_Diffuse','source_ERM','source_Normal','brick_Diffuse','brick_ERM','brick_Normal'))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def validate_config(config, output):
    """No writes, including on a stale hash, illegal density or path alias."""
    if not isinstance(config,dict) or config.get('schema')!='course-grid-bake/1':
        raise ValueError('unsupported bake schema')
    files=config.get('files',{})
    if not isinstance(files,dict) or set(files)!=ROLES:
        raise ValueError('missing or unknown bake input role')
    if config.get('tile_px') not in (2048,4096) or config.get('tiles')!=[1001,1002]:
        raise ValueError('explicit two-tile VPM configuration required')
    rho=config.get('texel_px_m');repeat=config.get('repeat_m')
    if (type(rho) not in (int,float) or not math.isfinite(rho) or not 512<=rho<=1706
            or type(repeat) not in (int,float) or not math.isfinite(repeat) or repeat<=0):
        raise ValueError('invalid frozen scale/repeat')
    if config.get('normal_encoding')!='DirectX':
        raise ValueError('explicit DirectX source convention required')
    if (type(config.get('background_origin_px')) is not int
            or config['background_origin_px']<0):
        raise ValueError('invalid explicit background phase')
    if type(config.get('dilation_px')) is not int or config['dilation_px']<0:
        raise ValueError('invalid dilation')
    for key in ('colour_joint_rgb','erm_joint_rgb'):
        c=config.get(key)
        if not isinstance(c,list) or len(c)!=3 or any(type(x) is not int or not 0<=x<=255 for x in c):
            raise ValueError('invalid joint RGB')
    if not config.get('decision_refs'):raise ValueError('missing scope decisions')
    output=Path(output).resolve()
    if output.exists():raise ValueError('output must be a new directory')
    paths={}
    for role,record in files.items():
        if not isinstance(record,dict) or set(record)!= {'path','sha256'}:
            raise ValueError(f'invalid input receipt: {role}')
        p=Path(record['path']).resolve()
        if p==output or output in p.parents:raise ValueError(f'input/output alias: {role}')
        if not p.is_file():raise ValueError(f'missing input: {role}')
        if any(p==q or p.samefile(q) for q in paths.values()):raise ValueError(f'duplicated input path: {role}')
        if digest(p)!=record['sha256']:raise ValueError(f'stale input: {role}')
        paths[role]=p
    return dict(source_hashes_verified=len(paths),paths=paths)


def bake(config, output):
    """Bake the explicit saved page plan, retaining nonpassing QA status."""
    checked=validate_config(config,output);paths=checked['paths']
    import numpy as np
    from PIL import Image
    from scipy.ndimage import distance_transform_edt
    from shapely import intersects_xy
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from .course_grid_native import raster_cell_intersections
    load=lambda role:json.loads(paths[role].read_text(encoding='utf8'))
    plan=load('layout');refs={(r['object'],r['face']):r for r in load('references')}
    charts={(r['object'],r['face']):r['chart_m'] for r in load('chart')['faces']}
    placements=[dict(r,tile=t) for t in config['tiles'] for r in load(f'placements_{t}')['placed']]
    member={tuple(m['key']):(tuple(p['key']),p['tile']) for p in placements for m in p['members']}
    boundary={tuple(r['source']) for r in load('boundary_report')['rows'] if not r['passed']}
    fields=np.load(paths['base_fields']);observed=np.asarray(Image.open(paths['source_Diffuse']).convert('RGB'))
    base=fields['base_diffuse'];jc=np.array(config['colour_joint_rgb']);axis=jc-base
    alpha=np.clip(np.einsum('ijk,ijk->ij',observed-base,axis)/np.maximum(np.einsum('ijk,ijk->ij',axis,axis),1e-12),0,1)
    alpha[~((fields['alpha']>0)|(np.abs(observed.astype(int)-jc).sum(2)<=10))]=0
    original=np.load(paths['historical_fields']);actual=np.load(paths['actual_fields'])
    relief=actual['groove'].copy();relief[np.linalg.norm(original['groove'],axis=2)<=1e-7]=0
    sourcefield=np.dstack([alpha,relief]).astype('float32')
    dark=(np.abs(observed.astype(int)-jc).sum(2)<=4)[::-1]
    brick={role:np.asarray(Image.open(paths['brick_'+role]).convert('RGB')) for role in ('Diffuse','ERM','Normal')}
    T=config['tile_px'];rho=config['texel_px_m'];repeat=config['repeat_m'];dilation=config['dilation_px']
    if observed.shape!=(T,T,3) or any(a.shape!=(T,T,3) for a in brick.values()):
        raise ValueError('map dimensions differ from frozen tile size')
    groups={}
    for face in plan['faces']:
        if not face['joint']:continue
        group,tile=member[tuple(face['patch'])];key=(group,tile)
        groups.setdefault(key,dict(faces=[],reference=face))['faces'].append(Polygon((np.asarray(face['uv'])-tile_origin(tile))*T))
    if set(pg for _,pg in groups)!=set(config['tiles']):raise ValueError('missing planned tile')
    for g in groups.values():g['shape']=unary_union(g['faces'])
    def sample(image,uv,wrap=False):
        h,w=image.shape[:2];x=uv[:,0]*w-.5;y=(1-uv[:,1])*h-.5
        if not wrap:x=np.clip(x,0,w-1);y=np.clip(y,0,h-1)
        ix=np.floor(x).astype(int);iy=np.floor(y).astype(int);fx=(x-ix)[:,None];fy=(y-iy)[:,None]
        if wrap:ix1=(ix+1)%w;iy1=(iy+1)%h;ix%=w;iy%=h
        else:ix1=np.minimum(ix+1,w-1);iy1=np.minimum(iy+1,h-1)
        return (image[iy,ix]*(1-fx)+image[iy,ix1]*fx)*(1-fy)+(image[iy1,ix]*(1-fx)+image[iy1,ix1]*fx)*fy
    output=Path(output);output.mkdir(parents=True,exist_ok=False);reports=[];artifacts=[]
    for tile in config['tiles']:
        maps={r:np.empty((T,T,3),dtype='uint8') for r in brick}
        # Explicit background phase; this is not a packing border calculation.
        for y in range(0,T,64):
            yy,xx=np.mgrid[y:min(y+64,T),0:T];origin=config['background_origin_px'];xy=np.c_[(xx.ravel()+.5-origin)/rho,(T-yy.ravel()-.5-origin)/rho]
            for role,image in brick.items():maps[role][y:min(y+64,T)]=np.rint(sample(image,xy/repeat,True)).clip(0,255).astype('uint8').reshape(min(64,T-y),T,3)
        painted=np.zeros((T,T),bool)
        for (group,pg),g in groups.items():
            if pg!=tile:continue
            shape=g['shape'];x0,y0,x1,y1=shape.bounds;margin=dilation+1
            left=max(0,int(np.floor(x0))-margin);right=min(T,int(np.ceil(x1))+margin)
            top=max(0,T-int(np.ceil(y1))-margin);bottom=min(T,T-int(np.floor(y0))+margin)
            yy,xx=np.mgrid[top:bottom,left:right];f=g['reference'];key=tuple(f['source'])
            domain=shape.buffer(0.707106781187) if key in boundary else shape
            inside=intersects_xy(domain,xx+.5,T-yy-.5)
            if not inside.any():raise ValueError(f'empty raster group: {group}')
            dist,(iy,ix)=distance_transform_edt(~inside,return_indices=True);dilated=dist<=dilation
            if np.any(painted[top:bottom,left:right]&inside):raise ValueError(f'overlapping source classes: {group}')
            painted[top:bottom,left:right]|=inside
            chart=np.asarray(charts[key]);uv=np.asarray(refs[key]['uv'])
            matrix=np.linalg.lstsq(np.c_[chart-chart[0],np.ones(len(chart))],uv-uv[0],rcond=None)[0]
            residual=np.max(np.linalg.norm((np.c_[chart-chart[0],np.ones(len(chart))]@matrix-(uv-uv[0]))@np.linalg.inv(matrix[:2]),axis=1))
            if residual>2e-5:raise ValueError(f'nonaffine source group: {group}')
            xy=np.c_[(xx[inside]+.5)/rho,(T-yy[inside]-.5)/rho]-f['translation_m']
            srcuv=np.c_[xy-chart[0],np.ones(len(xy))]@matrix+uv[0]
            values=sample(sourcefield,srcuv);a=values[:,:1];signed=values[:,1:]
            covered=raster_cell_intersections(dark,(srcuv*T).tolist(),(matrix[:2]*T/rho).tolist());a[covered]=1
            u,_,vh=np.linalg.svd(np.linalg.inv(matrix[:2]));rotation=u@vh
            if np.linalg.det(rotation)<0:raise ValueError('mirrored source frame')
            axes=rotation.copy();axes[1]*=-1;transported=signed@axes@np.diag([1,-1])
            for role,image in brick.items():
                base=sample(image,xy/repeat,True)
                if role=='Diffuse':colour=base*(1-a)+jc*a
                elif role=='ERM':colour=base*(1-a)+np.array(config['erm_joint_rgb'])*a
                else:
                    n=base/127.5-1;n[:,:2]+=transported;n/=np.linalg.norm(n,axis=1,keepdims=True);colour=(n+1)*127.5
                patch=np.zeros((*inside.shape,3),dtype='uint8');patch[inside]=np.rint(colour).clip(0,255).astype('uint8');patch[dilated]=patch[iy[dilated],ix[dilated]]
                maps[role][top:bottom,left:right][dilated]=patch[dilated]
            reports.append(dict(group=list(group),tile=tile,pixels=int(inside.sum()),source_uv_fit_residual_m=float(residual)))
        for role,image in maps.items():
            path=output/f'T_CourseGrid_{role}.{tile}.png'
            with path.open('xb') as stream:Image.fromarray(image).save(stream,format='PNG')
            artifacts.append(dict(path=str(path.resolve()),sha256=digest(path)))
        print(f'baked tile {tile}',flush=True)
    # Detect input changes during the actual operation, not only at preflight.
    for role,path in paths.items():
        if digest(path)!=config['files'][role]['sha256']:raise ValueError(f'input changed during bake: {role}')
    report=dict(passed=False,status='baked_readback_and_appearance_QA_required',source_hashes_verified=len(paths),decision_refs=config['decision_refs'],groups=reports,artifacts=artifacts)
    (output/'bake-report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf8')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--validate-only',action='store_true');args=parser.parse_args(argv)
    try:
        if args.output.resolve()==args.config.resolve() or args.output.resolve() in args.config.resolve().parents:raise ValueError('config/output alias')
        config=json.loads(args.config.read_text(encoding='utf8'))
        if args.validate_only:
            checked=validate_config(config,args.output);print(json.dumps(dict(source_hashes_verified=checked['source_hashes_verified'],passed=False,status='preflight_only')))
        else:bake(config,args.output)
    except (ValueError,OSError,KeyError) as error:
        parser.exit(2,f'ERROR: {error}\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
