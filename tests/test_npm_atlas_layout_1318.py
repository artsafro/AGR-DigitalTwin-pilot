"""new-case: explicit R1 atlas layout compatibility, without changing legacy defaults."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def packet(tmp_path):
    recipe = tmp_path / "recipe"
    recipe.mkdir()
    (recipe / "finish_map.py").write_text('''from pathlib import Path
import os
def load_kpp(): return {}
def validate_spec(spec, kpp): assert spec['finishes']
def fresh_out_dir(out, inputs):
    o = Path(out).resolve()
    if any(o == Path(p).resolve() for p in inputs): raise ValueError('aliases input')
    os.makedirs(out, exist_ok=False)
''')
    (recipe / "make_textures.py").write_text("# Synthetic solid-only fixture; no painter called.\n")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"address": "Synthetic", "finishes": {
        f"f{i}": {"udim": 1001+i, "kind": "placeholder", "rgb": [i, 2, 3]}
        for i in range(7)}}))
    return spec, recipe, tmp_path / "out"


def run(packet, *args):
    spec, recipe, out = packet
    return subprocess.run([sys.executable, str(ROOT / "tools/derive/npm_atlas.py"),
        str(spec), str(out), "--recipe-dir", str(recipe), *args], capture_output=True, text=True)


@pytest.mark.parametrize('args,cell,pad,cols', [([],409,6,5),(['--cell','512','--pad','8'],512,8,4)])
def test_layout(packet, args, cell, pad, cols):
    result = run(packet, *args)
    assert result.returncode == 0, result.stderr
    layout = json.loads((packet[2] / 'npm_atlas.json').read_text())
    assert (layout['cell'],layout['pad'],layout['region']) == (cell,pad,cell-2*pad)
    for i, region in enumerate(layout['finishes'].values()):
        assert region['u0'] == ((i % cols)*cell+pad)/2048
        assert region['v0'] == 1-((i // cols)*cell+cell-pad)/2048
        assert region['size'] == (cell-2*pad)/2048


@pytest.mark.parametrize('args', [
    ['--cell','0'], ['--cell','2049'], ['--cell','-1'], ['--cell','nan'],
    ['--pad','-1'], ['--cell','512','--pad','256'], ['--pad','inf'],
    ['--cell','2048','--pad','8'],
])
def test_bad_layout_refused_before_output(packet,args):
    result=run(packet,*args)
    assert result.returncode != 0
    assert not packet[2].exists()


def test_occupied_output_not_clobbered(packet):
    packet[2].mkdir()
    sentinel=packet[2]/'sentinel'
    sentinel.write_bytes(b'keep')
    assert run(packet).returncode != 0
    assert sentinel.read_bytes() == b'keep'


def test_output_alias_input_not_written(packet):
    spec, recipe, _ = packet
    before=spec.read_bytes()
    assert run((spec,recipe,spec)).returncode != 0
    assert spec.read_bytes() == before
