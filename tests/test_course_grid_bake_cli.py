"""new-case: reusable bake preflight refuses stale/aliased inputs before writes."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROLES = ('layout','references','chart','placements_1001','placements_1002',
 'base_fields','historical_fields','actual_fields','boundary_report',
 'source_Diffuse','source_ERM','source_Normal','brick_Diffuse','brick_ERM','brick_Normal')


def config(tmp_path):
    files = {}
    for role in ROLES:
        p = tmp_path / (role + '.input')
        p.write_bytes(b'frozen input')
        files[role] = {'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    return {'schema':'course-grid-bake/1','files':files,'tile_px':4096,
      'texel_px_m':512.1,'repeat_m':48*3.15/38,'tiles':[1001,1002],
      'colour_joint_rgb':[40,32,32],'erm_joint_rgb':[0,252,0],
      'normal_encoding':'DirectX','background_origin_px':32,'dilation_px':16,'decision_refs':['D304','D317']}


def test_bake_preflight_validates_every_frozen_input_without_creating_output(tmp_path):
    from tools.materials.course_grid_bake import validate_config
    c = config(tmp_path)
    out = tmp_path / 'new'
    assert validate_config(c,out)['source_hashes_verified'] == len(ROLES)
    assert not out.exists()


@pytest.mark.parametrize('failure', ['stale','missing','alias','existing','bad_scale','missing_role','duplicated_path'])
def test_bake_preflight_fail_closed(tmp_path,failure):
    from tools.materials.course_grid_bake import validate_config
    c = config(tmp_path);out = tmp_path / 'new'
    if failure=='stale':Path(c['files']['layout']['path']).write_bytes(b'changed')
    if failure=='missing':Path(c['files']['layout']['path']).unlink()
    if failure=='alias':out = Path(c['files']['layout']['path']).parent
    if failure=='existing':out.mkdir()
    if failure=='bad_scale':c['texel_px_m'] = 420
    if failure=='missing_role':del c['files']['chart']
    if failure=='duplicated_path':c['files']['chart']=c['files']['layout'].copy()
    with pytest.raises(ValueError):validate_config(c,out)
    if failure not in ('alias','existing'):assert not out.exists()


def test_bake_cli_validate_only_is_a_real_fresh_process(tmp_path):
    c = config(tmp_path);path = tmp_path / 'config.json';path.write_text(json.dumps(c))
    out = tmp_path / 'new'
    r = subprocess.run([sys.executable,'-m','tools.materials.course_grid_bake',
      '--config',str(path),'--output',str(out),'--validate-only'],capture_output=True,text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)['source_hashes_verified']==len(ROLES)
    assert not out.exists()
