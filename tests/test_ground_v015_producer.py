"""Fresh-process fail-closed controls for the Vatutino-only v015 producer."""
from pathlib import Path
import subprocess,sys
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'jobs/VATUTINO-SITE/build_ground_v015.py'


def test_v015_driver_exposes_a_real_fresh_process_cli():
    assert SCRIPT.exists(),'the checkpoint must have a reproducible producer, not scratch-only code'
    r=subprocess.run([sys.executable,str(SCRIPT),'--help'],capture_output=True,text=True)
    assert r.returncode==0
    for text in ('--adapter-json','--source-master','--d150-reference','--out'):
        assert text in r.stdout


@pytest.mark.parametrize('alias',['direct','relative','report','hardlink'])
def test_v015_output_alias_refuses_before_any_write(tmp_path,alias):
    assert SCRIPT.exists(),'v015 producer missing'
    source=tmp_path/'source.json';source.write_text('{}')
    out=tmp_path/'out'
    if alias=='direct':out=source
    elif alias=='relative':out=tmp_path/'x'/'..'/'source.json'
    else:
        out.mkdir()
        if alias=='report':(out/'report.json').write_text('{}')
        else:(out/'master-npm.json').hardlink_to(source)
    before={p.name:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    cmd=[sys.executable,str(SCRIPT),'--adapter-json',str(source),'--source-master',str(source),
         '--d150-reference',str(source),'--out',str(out)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode!=0 and ('alias' in r.stderr or 'new output' in r.stderr)
    after={p.name:p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert before==after


def test_world_face_matching_does_not_round_coordinates_before_matching():
    import importlib.util
    import numpy as np
    from dt_ai.geometry.ground_cake import Mesh
    spec=importlib.util.spec_from_file_location('producer_world_test',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    old=np.array([(0,0,.00001499999),(4,0,0),(0,4,0)])
    current=old.copy();current[0,2]=.000015
    m=Mesh(current,np.array([(0,1,2)]),['TileLight'],np.array([0]),np.zeros((1,3,2)),4.)
    reference={'verts':old,'faces':np.array([(0,1,2)])}
    assert module.match_reference_faces(m,reference,[0])=={0:0}
    reference['verts']=old+10
    with pytest.raises(ValueError,match='unmapped'):module.match_reference_faces(m,reference,[0])


def test_pair_hints_are_geometry_bound_and_never_a_pass_receipt():
    import importlib.util
    import numpy as np
    from dt_ai.geometry.ground_cake import Mesh
    spec=importlib.util.spec_from_file_location('producer_hint_test',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    m=Mesh(np.array([(0,0,0),(1,0,0),(0,1,0)],float),np.array([(0,1,2)]),['TileLight'],np.array([0]),np.zeros((1,3,2)),4.)
    hints={'source_geometry_sha256':module.legacy.surface_fingerprint(m.verts,m.faces),'profiles':{'npm':[],'vpm':[]}}
    assert module.validate_pair_hints(m,hints)=={'npm':[],'vpm':[]}
    m.verts[0,2]=.001
    with pytest.raises(ValueError,match='fingerprint'):module.validate_pair_hints(m,hints)
    hints['profiles']['unknown']=[]
    with pytest.raises(ValueError):module.validate_pair_hints(m,hints)


def test_distinct_input_spellings_of_one_hardlink_are_rejected_before_parsing(tmp_path):
    source=tmp_path/'adapter.json';source.write_text('{}')
    alias=tmp_path/'master.json';alias.hardlink_to(source)
    reference=tmp_path/'reference.npz';reference.write_bytes(b'not an npz')
    out=tmp_path/'new-output'
    r=subprocess.run([sys.executable,str(SCRIPT),'--adapter-json',str(source),'--source-master',str(alias),
        '--d150-reference',str(reference),'--out',str(out)],capture_output=True,text=True)
    assert r.returncode!=0 and 'alias' in r.stderr
    assert not out.exists() and source.read_text()=='{}' and alias.read_text()=='{}'


def test_changed_head_or_input_never_publishes_a_stale_run(tmp_path,monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('producer_snapshot_test',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    p=tmp_path/'input';p.write_bytes(b'original');snapshot={p:b'original'}
    monkeypatch.setattr(module,'git_head',lambda:'head-a',raising=False)
    module.assert_unchanged(snapshot,'head-a')
    monkeypatch.setattr(module,'git_head',lambda:'head-b')
    with pytest.raises(ValueError,match='HEAD changed'):module.assert_unchanged(snapshot,'head-a')
    monkeypatch.setattr(module,'git_head',lambda:'head-a');p.write_bytes(b'changed')
    with pytest.raises(ValueError,match='inputs changed'):module.assert_unchanged(snapshot,'head-a')
