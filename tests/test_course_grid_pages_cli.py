"""new-case: immutable-input, new-output CLI for explicit course-grid pages."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tools.materials.course_grid_pages import main


def recipe(tmp_path):
    source=tmp_path/'source.txt';source.write_text('synthetic source')
    source_key=['synthetic',3]
    piece=dict(source=source_key,joint=True,patch=source_key+[0],chart_m=[[0,0],[.02,0],[.02,1],[0,1]],xyz=[[0,0,0],[.02,0,0],[.02,0,1],[0,0,1]])
    data={'partitions':[dict(source=source_key,pieces=[piece],dropped_faces=[])],
          'brick_fold':dict(faces=[],unplaced=[],dropped_faces=[]),
          'placements':[dict(key=source_key+[0],tile=1002,translation_m=[1,1],members=[dict(key=source_key+[0],fold_shift_m=[0,0])])]}
    inputs={}
    for name,value in data.items():
        p=tmp_path/f'{name}.json';p.write_text(json.dumps(value));inputs[name]=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    payload=dict(schema='course-grid-pages/1',decision='SYNTHETIC',tile_budget=2,tile_px=4096,texel_px_m=512.1,inputs=inputs,source_hashes=[dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())])
    path=tmp_path/'recipe.json';path.write_text(json.dumps(payload))
    return path,payload


def test_fresh_process_cli_produces_candidate_not_qa_receipt(tmp_path):
    p,_=recipe(tmp_path);out=tmp_path/'layout.json';report=tmp_path/'report.json'
    result=subprocess.run([sys.executable,'-m','tools.materials.course_grid_pages','--recipe',str(p),'--out',str(out),'--report',str(report)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    layout=json.loads(out.read_text());receipt=json.loads(report.read_text())
    assert layout['passed'] is False and receipt['passed'] is False
    assert layout['source_faces']==1 and layout['support_members']==1
    assert receipt['source_hashes_verified']==1
    assert not out.with_suffix('.json.partial').exists()


@pytest.mark.parametrize('mode',['alias','hardlink','duplicate_input','stale_source','stale_plan','partial_clobber','existing_output','empty_sources','nan','budget'])
def test_cli_refuses_without_writing_or_deleting_inputs(tmp_path,mode):
    p,payload=recipe(tmp_path);out=tmp_path/'layout.json';report=tmp_path/'report.json'
    if mode=='alias':out=Path(payload['source_hashes'][0]['path'])
    elif mode=='hardlink':os.link(payload['source_hashes'][0]['path'],out)
    elif mode=='duplicate_input':payload['inputs']['placements']=payload['inputs']['partitions'].copy()
    elif mode=='stale_source':Path(payload['source_hashes'][0]['path']).write_text('changed')
    elif mode=='stale_plan':Path(payload['inputs']['placements']['path']).write_text('[]')
    elif mode=='partial_clobber':out.with_suffix('.json.partial').write_text('sentinel')
    elif mode=='existing_output':out.write_text('sentinel')
    elif mode=='empty_sources':payload['source_hashes']=[]
    elif mode=='nan':payload['texel_px_m']=float('nan')
    elif mode=='budget':payload['tile_budget']=1
    p.write_text(json.dumps(payload))
    before={q:q.read_bytes() for q in tmp_path.iterdir() if q.is_file()}
    assert main(['--recipe',str(p),'--out',str(out),'--report',str(report)])!=0
    assert {q:q.read_bytes() for q in tmp_path.iterdir() if q.is_file()}==before


def test_changed_source_during_planning_is_refused(tmp_path,monkeypatch):
    import tools.materials.course_grid_pages as module
    p,payload=recipe(tmp_path);original=module.assemble_support_pages
    def changed(*args,**kw):
        result=original(*args,**kw)
        Path(payload['source_hashes'][0]['path']).write_text('changed during planning')
        return result
    monkeypatch.setattr(module,'assemble_support_pages',changed)
    out=tmp_path/'layout.json';report=tmp_path/'report.json'
    assert main(['--recipe',str(p),'--out',str(out),'--report',str(report)])!=0
    assert not out.exists() and not report.exists()
