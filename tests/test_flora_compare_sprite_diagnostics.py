"""Fail-closed raw Flora sprite diagnostics. Not a calibrated acceptance run."""
import json
import math
import subprocess
import sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/flora'))
import compare_sprite_diagnostics as diag
import measure_sprite_coverage as coverage


def _passing(index, tag, profile='VPM', role='foliage', passed=True, faces=None, score=1.0):
    name=f'Plant{index:02d}_{profile}'
    island={'island':0,'role':role,'faces':[index] if faces is None else faces,'pass':passed,'score':score}
    if role=='unknown' or not passed and score is None:
        island.pop('score',None)
        island['status']='unknown'
        island['pass']=False
    return {'object':name,'tag':tag,'profile':profile,'triangles':1,'roles':{role:1},
            'unknown_metric_islands':0 if passed and role!='unknown' else 1,
            'scored_islands':1 if 'score' in island else 0,
            'passing_islands':1 if passed and role!='unknown' else 0,
            'islands':[island]}


def _material(enabled=True):
    return {'class':'Standardmaterial','bindings':{'opacityMapEnable':enabled}}


def _two_planes(enabled=True):
    return {'vertices':[[0,0,0],[1,0,0],[1,0,1],[0,0,1],[0,0,0],[0,1,0],[0,1,1],[0,0,1]],
            'faces':[[0,1,2],[0,2,3],[4,5,6],[4,6,7]],
            'uv':[[0,0],[1,0],[1,1],[0,1],[0,0],[1,0],[1,1],[0,1]],
            'material':_material(enabled)}


def _many_vertical_planes(count):
    vertices=[];faces=[];uv=[]
    for index in range(count):
        angle=index*math.pi/count
        base=len(vertices)
        direction=(math.cos(angle),math.sin(angle))
        vertices.extend([[0,0,0],[direction[0],direction[1],0],[direction[0],direction[1],1],[0,0,1]])
        faces.extend([[base,base+1,base+2],[base,base+2,base+3]])
        uv.extend([[0,0],[1,0],[1,1],[0,1]])
    return {'vertices':vertices,'faces':faces,'uv':uv,'material':_material(True)}


def _cube():
    vertices=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]]
    faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[3,7,6],[3,6,2],[0,4,7],[0,7,3],[1,2,6],[1,6,5]]
    return {'vertices':vertices,'faces':faces,'uv':[[0,0],[1,0],[1,1],[0,1]]*2,'material':_material(True)}


def test_compare_calls_the_existing_original_gate():
    assert diag.original_gate is coverage.original_gate


def test_star_check_counts_planes_and_rejects_a_complex_mesh():
    star=diag.npm_star_check(_two_planes())
    assert star['is_star'] is True and star['candidate_plane_count']==2 and star['horizontal_normal_count']==2
    assert star['vertical_plane_count']==2 and star['opacity_enabled'] is True and star['unknowns']==[]
    assert star['uv_extent']==[1.0,1.0]
    indexed=_two_planes();indexed['uv'].append([.5,.5])
    assert diag.npm_star_check(indexed)['uv_extent']==[1.0,1.0]
    assert 'nonfinite or missing UV' not in diag.npm_star_check(indexed)['unknowns']
    single=diag.npm_star_check({'vertices':_two_planes()['vertices'][:4],'faces':[[0,1,2],[0,2,3]],
                                 'uv':[[0,0],[1,0],[1,1],[0,1]],'material':_material(True)})
    assert single['is_star'] is False and 'star arrangement not confirmed' in single['unknowns']
    disabled=diag.npm_star_check(_two_planes(False))
    assert disabled['is_star'] is False and 'opacity disabled' in disabled['unknowns']
    cube=diag.npm_star_check(_cube())
    assert cube['is_star'] is False and cube['candidate_plane_count']==6 and 'plane is not vertical' in cube['unknowns']
    complex_mesh=diag.npm_star_check(_many_vertical_planes(13))
    assert complex_mesh['candidate_plane_count']==13 and complex_mesh['is_star'] is False
    assert 'complex whole-tree mesh is not a star' in complex_mesh['unknowns']
    assert 'plane is not vertical' not in complex_mesh['unknowns']
    missing=diag.npm_star_check(None)
    assert missing['is_star'] is False and missing['unknowns']==['source record missing']


def test_distribution_reports_quantiles_and_fail_unknown_counts():
    rows=[{'tag':'ours','islands':[
        {'role':'foliage','score':0,'pass':False},
        {'role':'foliage','score':0.5,'pass':True},
        {'role':'foliage','score':1,'pass':True},
        {'role':'unknown','pass':False,'status':'unknown'}]}]
    report=diag.build_distribution(rows)
    foliage=report['ours|foliage']
    assert foliage['min']==0 and foliage['max']==1 and foliage['median']==pytest.approx(.5)
    assert foliage['q25']==pytest.approx(.25) and foliage['q75']==pytest.approx(.75)
    assert foliage['fail']==1 and foliage['unknown']==0 and foliage['islands']==3
    unknown=report['ours|unknown']
    assert unknown['unknown']==1 and unknown['fail']==1 and unknown['min'] is None and unknown['max'] is None


def test_failed_gate_keeps_every_failure_and_blocks_definitive_routes():
    source=[_passing(i,'original' if i<68 else 'florio') for i in range(99)]
    source[0]=_passing(0,'original',role='unknown',passed=False,faces=[11],score=None)
    ours=[_passing(i,'ours',faces=[8]) for i in range(99)]
    ours[0]=_passing(0,'ours',faces=[8],passed=False,score=0.2)
    light=_passing(0,'light',faces=[4],passed=False,score=0.1)
    light['object']='Plant00_VPM'
    measured=source+ours+[light,_passing(1,'light'),_passing(2,'light')]
    report=diag.seal_diagnostic(measured,{row['object']:_two_planes() for row in source})
    assert report['calibration_gate']=='failed' and report['accepted'] is False
    assert report['calibrated_acceptance'] is False and report['replacement_failures_certified'] is False
    assert report['definitive_routes_issued'] is False and len(report['routes'])==99
    assert len({route['object'] for route in report['routes']})==99 and len(report['metrics'])==201
    assert all(route['definitive_route'] is None for route in report['routes'])
    assert report['routes'][0]['provisional_route']=='source_validation_required'
    assert report['routes'][0]['source_islands'][0]['faces']==[11]
    assert report['routes'][0]['source_islands'][0]['unknown'] is True
    assert report['routes'][0]['library_islands'][0]['faces']==[8]
    assert report['routes'][0]['library_islands'][0]['pass'] is False
    assert report['routes'][0]['light_islands'][0]['pass'] is False
    assert report['routes'][1]['provisional_route']=='rebind_original_atlas'
    blob=json.dumps(report)
    assert '"accepted": true' not in blob and '"calibrated_acceptance": true' not in blob
    assert report['distribution']['original|unknown']['unknown']>=1
    assert report['distribution']['original|unknown']['min'] is None


def test_clean_sources_propose_routes_without_acceptance():
    source=[_passing(i,'original' if i<68 else 'florio') for i in range(99)]
    ours=[_passing(i,'ours') for i in range(99)]
    light=[_passing(i,'light') for i in range(3)]
    report=diag.seal_diagnostic(source+ours+light,{})
    assert report['calibration_gate']=='not_failed' and report['accepted'] is False
    assert report['definitive_routes_issued'] is True and len(report['routes'])==99
    assert {route['provisional_route'] for route in report['routes']}=={'rebind_original_atlas'}
    assert {route['definitive_route'] for route in report['routes']}=={'rebind_original_atlas'}
    assert report['distribution']['original|foliage']['fail']==0
    assert report['distribution']['original|foliage']['min']==1
    assert 'accepted=false' in report['status_lines'][0]


def test_npm_star_route_is_provisional_when_the_gate_fails():
    star=_passing(0,'original',profile='NPM')
    complex_row=_passing(1,'original',profile='NPM')
    failed=_passing(2,'original',profile='NPM',passed=False,score=0.1)
    vpm=_passing(3,'florio')
    measured=[star,complex_row,failed,vpm]
    records={'Plant00_NPM':_two_planes(),'Plant01_NPM':_many_vertical_planes(13),'Plant02_NPM':_two_planes()}
    report=diag.seal_diagnostic(measured,records)
    routes={route['object']:route for route in report['routes']}
    assert report['calibration_gate']=='failed' and report['accepted'] is False
    assert routes['Plant00_NPM']['provisional_route']=='keep_or_rebuild_star'
    assert routes['Plant00_NPM']['definitive_route'] is None and routes['Plant00_NPM']['star']['is_star'] is True
    assert routes['Plant01_NPM']['provisional_route']=='source_validation_required'
    assert routes['Plant01_NPM']['star']['is_star'] is False
    assert routes['Plant02_NPM']['provisional_route']=='source_validation_required'
    assert routes['Plant03_VPM']['provisional_route']=='rebind_original_atlas' and routes['Plant03_VPM']['star'] is None


def test_measurement_order_checkpoints_failures_before_the_gate(tmp_path, monkeypatch):
    calls=[]
    monkeypatch.setattr(diag,'original_gate',lambda rows: calls.append(len(rows)) or (_ for _ in ()).throw(AssertionError('gate during inventory')))
    def fake(record, key, tag, job, pictures=None):
        return {'object':key,'tag':tag,'profile':'VPM','triangles':1,'roles':{'unknown':1},
                'unknown_metric_islands':1,'scored_islands':0,'passing_islands':0,
                'islands':[{'island':0,'role':'unknown','faces':[7],'pass':False,'status':'unknown'}]}
    monkeypatch.setattr(diag,'analyze',fake)
    seen=[]
    real=diag.write_progress
    monkeypatch.setattr(diag,'write_progress',lambda *args: seen.append([row['tag'] for row in args[2]]) or real(*args))
    checkpoint,partial=tmp_path/'checkpoint.json',tmp_path/'metrics.partial.json'
    sequence=[('original','A_VPM',{}),('ours','A_VPM',{}),('light','A_VPM',{})]
    rows=diag.measure_records(sequence,{},None,set(),checkpoint,partial)
    assert calls==[] and seen==[['original'],['original','ours'],['original','ours','light']]
    saved=json.loads(partial.read_text(encoding='utf-8'))
    assert saved['accepted'] is False and saved['complete'] is False and saved['objects'][0]['islands'][0]['faces']==[7]
    monkeypatch.setattr(diag,'original_gate',coverage.original_gate)
    report=diag.seal_diagnostic(rows,{})
    assert report['calibration_gate']=='failed' and report['accepted'] is False
    assert report['routes'][0]['source_islands'][0]['faces']==[7]
    assert report['routes'][0]['provisional_route']=='source_validation_required'
    order=diag.measurement_sequence([('original','A',{}),('florio','B',{})],[('A',{}),('B',{})],[('A',{})])
    assert [item[0] for item in order]==['original','florio','ours','ours','light']


def test_index_and_sheet_keep_status_purple_and_the_source_render(tmp_path):
    lines=diag.status_lines('failed',4,9,2,201)
    index=tmp_path/'index.html'
    diag.write_index(index,lines,['101.png'])
    head=index.read_text(encoding='utf-8').splitlines()[:5]
    assert head==lines
    assert all(any('\u0400'<=ch<='\u04ff' for ch in line) for line in head)
    assert 'accepted=false' in head[0] and 'failed' in head[0] and '4' in head[1] and '9' in head[1]
    assert 'calibrated pass' not in index.read_text(encoding='utf-8').lower()
    base=tmp_path/'render.png'
    Image.new('RGB',(20,10),(255,255,255)).save(base)
    before=base.read_bytes()
    mask,overlay=tmp_path/'mask.png',tmp_path/'overlay.png'
    Image.new('RGB',(4,4),(160,80,200)).save(mask)
    Image.new('RGB',(4,4),(255,30,30)).save(overlay)
    dest=tmp_path/'out'/'101.png'
    summary=diag.row_summary('source NPM',{'roles':{'unknown':2},'passing_islands':0,'unknown_metric_islands':2,'islands':[{'score':0.1}]})
    assert 'unknown=2' in summary and 'roles=' in summary and 'scores=0.1000' in summary
    diag.compose_evidence_sheet(base,[('source',mask,overlay),('light',tmp_path/'missing-mask.png',tmp_path/'missing-overlay.png')],[summary],dest)
    assert base.read_bytes()==before
    image=np.asarray(Image.open(dest))
    assert image.shape[0]>10 and (image==np.array([160,80,200])).all(axis=-1).any()
    with pytest.raises(ValueError):
        diag.compose_evidence_sheet(base,[],[summary],base)
    with pytest.raises(ValueError,match='read only'):
        diag._refuse_review_write(diag.REVIEW_ROOT/'101.png')


def test_guard_rejects_aliased_or_existing_output(tmp_path):
    job,inventory,maps=tmp_path/'job.json',tmp_path/'inventory.json',tmp_path/'maps'
    job.write_text('{}',encoding='utf-8');inventory.write_text('{}',encoding='utf-8');maps.mkdir()
    with pytest.raises(ValueError):
        diag.guard_run_paths([job,inventory,maps],job)
    # A fresh versioned child bundle is allowed; published root PNGs stay read-only.
    diag.guard_run_paths([job,inventory,maps],diag.REVIEW_ROOT/'raw-diagnostic-test-fresh')
    output=tmp_path/'out';output.mkdir()
    with pytest.raises(ValueError,match='fresh'):
        diag.guard_run_paths([job,inventory,maps],output)


def test_cli_empty_or_partial_input_fails(tmp_path):
    script=Path(__file__).resolve().parents[1]/'tools'/'flora'/'compare_sprite_diagnostics.py'
    job=tmp_path/'job.json'
    job.write_text('{}',encoding='utf-8')
    empty_out=tmp_path/'empty-out'
    empty=subprocess.run([sys.executable,str(script),'--job',str(job),'--output',str(empty_out)],capture_output=True,text=True)
    assert empty.returncode!=0 and not empty_out.exists()
    inventory={'failures':[],'light':{},'scenes':{
        'original':{'records':{}},'florio':{'records':{}},'ours':{'records':{}}}}
    (tmp_path/'inventory.json').write_text(json.dumps(inventory),encoding='utf-8')
    job.write_text(json.dumps({'work':str(tmp_path),'inventory':'inventory.json','species':[],'scenes':[]}),encoding='utf-8')
    partial_out=tmp_path/'partial-out'
    partial=subprocess.run([sys.executable,str(script),'--job',str(job),'--output',str(partial_out)],capture_output=True,text=True)
    assert partial.returncode!=0 and not partial_out.exists()
