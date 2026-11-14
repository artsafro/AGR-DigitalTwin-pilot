"""new-case: Ground exporter must preserve an explicit source CRS label, without numeric transforms."""
import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('crs', ['DWG WCS metres; CRS unspecified', 'SYNTHETIC_LOCAL', 'MSK-77', None])
def test_ground_export_coordinate_label(tmp_path, crs):
    blender = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    if not blender.exists():
        pytest.skip('Blender 5.1.2 required')
    mesh = dict(verts=[[10, 20, 169.65], [12, 20, 171.05], [10, 22, 170.0]], faces=[[0, 1, 2]],
                slots=['Tile'], mat=[0], level=[0], uv=[[[0, 0], [1, 0], [0, 1]]])
    source, target = tmp_path/'mesh.json', tmp_path/'mesh.fbx'
    source.write_text(json.dumps(mesh))
    args = [str(blender), '--background', '--factory-startup', '--threads', '1',
            '--python-exit-code', '1', '--python', 'tools/blender/ground_json_to_fbx.py',
            '--', 'build', str(source), str(target), 'Synthetic']
    if crs:
        args.append(crs)
    run = subprocess.run(args, capture_output=True, text=True)
    if crs == 'DWG WCS metres; CRS unspecified':
        assert run.returncode != 0
        assert not target.exists() and not Path(str(target)+'.placement.json').exists()
        return
    assert run.returncode == 0, run.stdout + run.stderr
    meta = json.loads(Path(str(target)+'.placement.json').read_text())
    assert meta['crs'] == (crs or 'MSK-77')
    assert meta['origin_msk77_xyz'] == [11, 21, 0]
    assert json.loads(source.read_text()) == mesh
    report = tmp_path / 'readback.json'
    check = subprocess.run(args[:args.index('--') + 1] +
        ['readback', str(target), str(source), str(report)], capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    facts = json.loads(report.read_text())
    assert facts['world_bbox']['z'] == pytest.approx([169.65, 171.05], abs=0.0001)
