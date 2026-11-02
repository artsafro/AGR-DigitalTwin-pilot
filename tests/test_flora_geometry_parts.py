"""Synthetic topology witnesses, not botanical ground truth."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
import hashlib
import json
import os
import subprocess
import sys


def load():
    path=Path(__file__).parents[1]/'tools/flora/geometry_parts.py'
    assert path.exists(), 'geometry-only decomposition module is missing'
    spec=importlib.util.spec_from_file_location('geometry_parts',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def test_duplicate_uv_indices_join_only_across_same_geometry_edge():
    mod=load()
    record={'vertices':[[0,0,0],[1,0,0],[1,0,1],[0,0,1]],
            'faces':[[0,1,2],[0,2,3]],
            'uv':[[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]],
            'uvfaces':[[0,1,2],[3,4,5]], 'face_material_ids':[1,1]}
    assert mod.uv_charts(record)==[[0,1]]
    record['uv'][3]=[.1,0]
    assert mod.uv_charts(record)==[[0],[1]]


def test_bent_card_and_tilted_tapered_branch_are_geometry_only():
    mod=load()
    assert hasattr(mod,'geometry_parts'), 'geometry-only role decomposition missing'
    card=np.array([[x,.12*(1-x*x),z] for z in (0.,1.,2.) for x in (-1.,0.,1.)])
    faces=[]
    for z in range(2):
        for x in range(2):
            i=z*3+x;faces.extend([[i,i+1,i+4],[i,i+4,i+3]])
    result=mod.geometry_parts(card,faces)
    assert len(result)==1 and result[0]['role']=='foliage'
    assert result[0]['kind']=='bent_card'
    # Triangular-ring tube with a closed tip, rotated away from vertical.
    branch=np.array([[np.cos(a)*r,np.sin(a)*r,z] for z,r in ((0.,.1),(1.,.07)) for a in np.arange(3)*2*np.pi/3]+[[0.,0.,2.]])
    tube=[]
    for i in range(3):
        j=(i+1)%3;tube.extend([[i,j,j+3],[i,j+3,i+3],[i+3,j+3,6]])
    transform=np.array([[0.,0.,1.],[1.,0.,0.],[0.,1.,0.]])
    for vertices in (branch,branch@transform):
        rows=mod.geometry_parts(vertices,tube)
        assert len(rows)==1 and rows[0]['role']=='trunk'
        assert rows[0]['boundary_loops']==1


def test_folded_open_card_is_not_mistaken_for_a_tube():
    mod=load()
    vertices=[[x,y,z] for z in (0.,2.) for x,y in ((-.1,1.),(0.,0.),(.1,1.))]
    faces=[[0,1,4],[0,4,3],[1,2,5],[1,5,4]]
    result=mod.geometry_parts(vertices,faces)
    assert result[0]['role']=='foliage'
    assert result[0]['kind']=='folded_card'
    assert result[0]['normal_hemisphere_min_dot']>0


def test_parts_account_for_faces_and_ignore_uv_pixels():
    mod=load()
    assert hasattr(mod,'parts_and_charts'), 'geometry parts/chart adapter missing'
    record={'vertices':[[0,0,0],[1,0,0],[1,0,1],[0,0,1]],
            'faces':[[0,1,2],[0,2,3]],'uv':[[0,0],[1,0],[1,1],[0,1]],
            'uvfaces':[[0,1,2],[0,2,3]],'face_material_ids':[1,1]}
    parts,charts=mod.parts_and_charts(record)
    assert [i for p in parts for i in p['faces']]==[0,1]
    assert charts[0]['role']=='foliage' and charts[0]['faces']==[0,1]
    record['uv']=[[20.,-10.],[50.,-10.],[50.,25.],[20.,25.]]
    assert mod.parts_and_charts(record)[0]==parts


@pytest.mark.parametrize('seed',range(12))
def test_geometry_roles_are_rotation_translation_scale_invariant(seed):
    rng=np.random.default_rng(seed)
    mod=load()
    vertices=np.array([[x,.1*(1-x*x),z] for z in (0.,1.,2.) for x in (-1.,0.,1.)])
    faces=[[i,i+1,i+4] for i in (0,1,3,4)]+[[i,i+4,i+3] for i in (0,1,3,4)]
    rotation,_=np.linalg.qr(rng.normal(size=(3,3)))
    transformed=vertices@rotation*10**rng.uniform(-3,3)+rng.uniform(-100,100,size=3)
    base=mod.geometry_parts(vertices,faces)
    changed=mod.geometry_parts(transformed,faces)
    assert [(p['faces'],p['role']) for p in changed]==[(p['faces'],p['role']) for p in base]
    flipped=mod.geometry_parts(transformed,np.array(faces)[:,::-1])
    assert [p['role'] for p in flipped]==[p['role'] for p in base]


def test_chart_does_not_join_material_seam_or_disconnected_coincident_cards():
    mod=load()
    record={'vertices':[[0,0,0],[1,0,0],[1,0,1],[0,0,1]],
            'faces':[[0,1,2],[0,2,3]],'uv':[[0,0],[1,0],[1,1],[0,1]],
            'uvfaces':[[0,1,2],[0,2,3]],'face_material_ids':[1,2]}
    assert mod.uv_charts(record)==[[0],[1]]
    record['vertices']*=2
    record['faces'][1]=[4,6,7]
    record['face_material_ids']=[1,1]
    assert mod.uv_charts(record)==[[0],[1]]


def test_nonmanifold_and_degenerate_surfaces_stay_unknown():
    mod=load()
    rows=mod.geometry_parts([[0,0,0],[1,0,0],[0,0,1],[0,1,0],[0,-1,0]],[[0,1,2],[0,1,3],[0,1,4]])
    assert rows[0]['role']=='unknown' and 'nonmanifold' in rows[0]['reason']
    assert mod.geometry_parts([[0,0,0],[1,0,0],[2,0,0]],[[0,1,2]])[0]['role']=='unknown'


@pytest.mark.parametrize('driver',['benchmark_geometry.py','source_crop_witness.py'])
def test_benchmark_cli_rejects_alias_and_partial_without_writing(tmp_path,driver):
    script=Path(__file__).parents[1]/'experiments/flora-texture-diagnosis'/driver
    inventory=tmp_path/'inventory.json';inventory.write_text('{}')
    job=tmp_path/'job.json';job.write_text(json.dumps({'work':str(tmp_path),'inventory':inventory.name}))
    alias=tmp_path/'alias.json';os.link(job,alias)
    hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (job,alias,inventory)}
    for output in (job,alias,tmp_path/'fresh.json'):
        result=subprocess.run([sys.executable,str(script),'--job',str(job),'--output',str(output)],capture_output=True,timeout=20)
        assert result.returncode!=0
        if output.name=='fresh.json':assert not output.exists()
    assert hashes=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in hashes}
    assert subprocess.run([sys.executable,str(script),'--help'],capture_output=True,timeout=20).returncode==0


@pytest.mark.parametrize('bad',[[],[[float('nan'),0,0]],[[float('inf'),0,0]]])
def test_bad_geometry_fails_closed(bad):
    with pytest.raises(ValueError):load().geometry_parts(bad,[[0,1,2]])
