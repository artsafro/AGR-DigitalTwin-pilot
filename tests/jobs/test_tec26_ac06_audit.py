"""AC06 export topology certification regressions (synthetic plus real receipts)."""
import importlib.util
from pathlib import Path

import pytest

PATH=Path(__file__).resolve().parents[2]/'jobs/TEC26-OKS/AC06/audit_build.py'


def module():
    s=importlib.util.spec_from_file_location('ac06_audit',PATH)
    assert s and s.loader
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def test_triangulation_preserves_polygon_boundary_not_polygon_count():
    src={'vertices':[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],'faces':[[0,1,2,3]]}
    out={'vertices':src['vertices'],'faces':[[0,1,2],[0,2,3]]}
    assert module().source_coverage(src,out,[0,0,0])==[0,0]
    for faces in ([[0,1,2],[0,1,2]], [[0,2,1],[0,2,3]], [[0,1,2]], []):
        with pytest.raises(ValueError):
            module().source_coverage(src,{**out,'faces':faces},[0,0,0])
    with pytest.raises(ValueError):
        module().source_coverage(src,{**out,'vertices':[[0,0,0],[1,0,0],[1,1,1],[0,1,0]]},[0,0,0])
    for changed in ([[float('nan'),0,0], *src['vertices'][1:]], [[float('inf'),0,0], *src['vertices'][1:]], [[2e-5,0,0], *src['vertices'][1:]]):
        with pytest.raises(ValueError):
            module().source_coverage(src,{**out,'vertices':changed},[0,0,0])
    with pytest.raises(ValueError):
        module().source_coverage({**src,'vertices':[src['vertices'][0],*src['vertices']]},out,[0,0,0])


@pytest.mark.parametrize('checks', [{}, {'names_vpm': {'ok': 'fail'}}, {'names_vpm': {'ok': True}}])
def test_partial_or_nonboolean_raw_receipts_refused(checks):
    with pytest.raises(ValueError):
        module().validate_raw({'checks': checks, 'failed': []})


def test_complete_raw_status_schema_and_lying_summary():
    import json
    import copy
    names=json.loads((PATH.parents[3]/'tests/fixtures/tec26_ac06_raw_check_names.json').read_text())
    raw={'checks': {n:{'ok':True,'detail':{}} for n in names}, 'failed':[]}
    assert module().validate_raw(raw) is None
    for value in ('fail','review','not_run','unknown',None,0,1):
        changed=copy.deepcopy(raw)
        changed['checks']['xview_vpm']['ok']=value
        with pytest.raises(ValueError,match='boolean'):
            module().validate_raw(changed)
    raw['checks']['xview_vpm']['ok']=False
    with pytest.raises(ValueError,match='summary'):
        module().validate_raw(raw)
    raw['failed']=['xview_vpm']
    assert module().validate_raw(raw) is None  # Fail is valid evidence, NOT a pass.


def test_snapshot_rejects_changed_or_duplicated_input(tmp_path):
    p=tmp_path/'one.json'; p.write_text('{}')
    snap=module().snapshot([p])
    assert module().verify_snapshot(snap) is None
    p.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='changed'):
        module().verify_snapshot(snap)
    with pytest.raises(ValueError,match='duplicate'):
        module().snapshot([p,p])


def test_fresh_cli_refuses_build_input_output_alias(tmp_path):
    import subprocess
    import sys
    root=tmp_path/'input'; root.mkdir()
    target=root/'absent-input.json'
    done=subprocess.run([sys.executable,str(PATH),str(root),str(target)],capture_output=True,text=True)
    assert done.returncode!=0 and 'audit output' in done.stderr
    assert list(root.iterdir())==[]
