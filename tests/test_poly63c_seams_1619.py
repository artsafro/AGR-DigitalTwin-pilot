"""Native Blender regression on the published stage-1 v002, never modifying it."""
import hashlib
import os
from pathlib import Path
import subprocess

import pytest


CHECK = Path(__file__).resolve().parents[1] / 'jobs/POLY63-C/hooks/check_corners.py'
MUTATE = '''
import bmesh, bpy, sys
src, dest = sys.argv[-2:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
body, = bpy.context.scene.objects
bm = bmesh.new()
bm.from_mesh(body.data)
bm.faces.ensure_lookup_table()
edge, = set(bm.faces[43].edges) & set(bm.faces[240].edges)
assert edge.index == 147
bmesh.ops.split_edges(bm, edges=list(bm.faces[43].edges))
bm.to_mesh(body.data)
bm.free()
bpy.ops.export_scene.fbx(filepath=dest)
'''


@pytest.mark.blender
@pytest.mark.parametrize('split', [False, True], ids=['intact-v002', 'split-face-43'])
def test_front_lip(tmp_path, split):
    src = Path(os.environ['POLY63C_V002']).resolve()
    assert hashlib.sha256(src.read_bytes()).hexdigest() == '462ba61b2c379de53a72667635fd0714703764b2409407cc67ff28d8684de1da'
    blender = [os.environ['DT_BLENDER'], '-b', '--factory-startup', '--disable-autoexec', '--threads', '1', '--python-exit-code', '1']
    if split:
        dest = tmp_path / 'split.fbx'
        subprocess.run([*blender, '--python-expr', MUTATE, '--', src, dest], check=True, timeout=120)
        src = dest
    run = subprocess.run([*blender, '--python', CHECK, '--', src], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, errors='replace', timeout=120)
    assert run.returncode == int(split), run.stdout
    if split:
        assert 'disconnected facade/jamb seam' in run.stdout and 'jamb=240 ' in run.stdout, run.stdout
    else:
        assert '"corners": 1452' in run.stdout, run.stdout
