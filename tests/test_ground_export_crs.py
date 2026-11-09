"""new-case: Ground exporter must preserve an explicit source CRS label, without numeric transforms."""
import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('crs', ['DWG WCS metres; CRS unspecified', None])
def test_ground_export_coordinate_label(tmp_path, crs):
    blender = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    if not blender.exists():
        pytest.skip('Blender 5.1.2 required')
    mesh = dict(verts=[[10, 20, 0], [12, 20, 0], [10, 22, 0]], faces=[[0, 1, 2]],
                slots=['Tile'], mat=[0], uv=[[[0, 0], [1, 0], [0, 1]]])
    source, target = tmp_path/'mesh.json', tmp_path/'mesh.fbx'
    source.write_text(json.dumps(mesh))
    args = [str(blender), '--background', '--factory-startup', '--threads', '1',
            '--python-exit-code', '1', '--python', 'tools/blender/ground_json_to_fbx.py',
            '--', 'build', str(source), str(target), 'Synthetic']
    if crs:
        args.append(crs)
    run = subprocess.run(args, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    meta = json.loads(Path(str(target)+'.placement.json').read_text())
    assert meta['crs'] == (crs or 'MSK-77 (SPOZU drawing coordinates, $INSUNITS=6 metres)')
    assert meta['origin_msk77_xyz'] == [11, 21, 0]
    assert json.loads(source.read_text()) == mesh
