"""new-case: explicit R1 atlas layout compatibility, without changing legacy defaults."""
import importlib.util
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


@pytest.mark.parametrize('args,cell,pad,cols', [([],409,16,5),(['--cell','512','--pad','8'],512,8,4),
    (['--cell','512','--pad','4'],512,4,4)])
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


@pytest.mark.parametrize('pad', [4, 8])
def test_custom_layout_readback_matches_declared_padding(packet, pad):
    result = run(packet, '--cell', '512', '--pad', str(pad))
    assert result.returncode == 0, result.stderr
    out = packet[2]
    paths = [out/'npm_atlas.json', out/'T_Synthetic_001_Main_d_1.png',
             out/'T_Synthetic_001_Main_o_1.png']
    command = [sys.executable, str(ROOT/'tools/derive/npm_atlas.py'), '--check', *map(str, paths)]
    checked = subprocess.run(command, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    measured = json.loads(checked.stdout)
    assert measured['per_side_padding_px'] == pad
    assert measured['region_gap_px'] == 2*pad
    assert measured['usable_area_px'] == 7*(512-2*pad)**2
    data = json.loads(paths[0].read_text())
    data['pad'] = 16  # Stale/forged declaration cannot certify unchanged rectangles.
    paths[0].write_text(json.dumps(data))
    before = [p.read_bytes() for p in paths]
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert [p.read_bytes() for p in paths] == before


@pytest.mark.parametrize('pad', range(4))
def test_regulatory_floor_refused_before_output(packet, pad):
    result = run(packet, '--cell', '512', '--pad', str(pad))
    assert result.returncode != 0
    assert '8 px' in result.stderr
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


def runner():
    spec = importlib.util.spec_from_file_location('benchmark1318', ROOT/'jobs/KPP1/benchmark-1318/run_benchmark.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('mutation', ['empty', 'missing', 'changed', 'extra', 'duplicate', 'escape'])
def test_packet_integrity_fail_closed(tmp_path, mutation):
    import hashlib
    packet = tmp_path/'packet'
    packet.mkdir()
    source = packet/'input'
    source.write_bytes(b'original')
    line = hashlib.sha256(source.read_bytes()).hexdigest()+'  input\n'
    manifest = packet/'SHA256SUMS.txt'
    manifest.write_text(line)
    module = runner()
    assert module.verify(packet)
    if mutation == 'empty': manifest.write_text('')
    if mutation == 'missing': source.unlink()
    if mutation == 'changed': source.write_bytes(b'changed')
    if mutation == 'extra': (packet/'cache.pyc').write_bytes(b'unexpected cache')
    if mutation == 'duplicate': manifest.write_text(line+line)
    if mutation == 'escape': manifest.write_text(line.replace('input','../input'))
    with pytest.raises(ValueError):
        module.verify(packet)


def test_failed_integrity_still_retains_native_exit_and_run_report(tmp_path, monkeypatch):
    module=runner()
    calls=0
    def verify(_):
        nonlocal calls
        calls += 1
        if calls >= 3: raise ValueError('packet integrity mismatch')
        return 'hash'
    monkeypatch.setattr(module, 'verify', verify)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *a, **k: 'sha')
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a,1))
    out=tmp_path/'out'
    with pytest.raises(ValueError,match='integrity'):
        module.main(tmp_path/'packet',out)
    record=json.loads((out/'run.json').read_text())
    assert record['packet_unchanged'] is False
    assert record['stages'][0]['exit'] == 1
    assert 'integrity_error' in record
