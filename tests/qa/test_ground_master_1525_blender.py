"""new-case: the real Ground producer writes its derivation record; OKS + Ground package gets manifest_ok (#1525, [D328]).

Opt-in (`-m blender`): headless Blender runs tools/blender/ground_json_to_fbx.py build on a synthetic ground mesh JSON
(no customer data). The producer writes `<out>.derivation.json` (role ground, master = the mesh JSON). The OKS member's
record comes from the export hook tools/derive/export_npm.py calls (`write_export_derivation`, its real run is in
tests/qa/test_export_derivation_1505_blender.py). The package then builds and passes with `--master oks= --master ground=`.
"""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402
from tools.derive import build_manifest as cli  # noqa: E402

pytestmark = pytest.mark.blender

MESH = dict(verts=[[10, 20, 169.65], [12, 20, 171.05], [10, 22, 170.0], [12, 22, 170.5]],
            faces=[[0, 1, 3, 2]], slots=['Tile'], mat=[0], level=[0], uv=[[[0, 0], [1, 0], [1, 1], [0, 1]]])


def blender_exe():
    for p in (os.environ.get('DT_BLENDER'), 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe',
              'C:/Program Files/Blender Foundation/Blender 4.4/blender.exe'):
        if p and Path(p).is_file():
            return p
    pytest.skip('Blender not installed (opt-in -m blender test)')


def ground_build(src, out):
    cmd = [blender_exe(), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
           '--python', str(ROOT / 'tools/blender/ground_json_to_fbx.py'), '--', 'build', str(src), str(out), 'Syn']
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300,
                          cwd=str(ROOT))


def stub_rb(path):
    stem = Path(path).stem
    return {'readback_ok': True, 'blender': 'stub', 'meshes': [
        {'name': 'SM_' + stem, 'bounds_m': [[0, 0, 0], [1, 2, 3]], 'location': [10, 20, 0],
         'materials': ['M_' + stem], 'uv_channels': 1, 'triangles': 12},
        {'name': 'UCX_SM_' + stem + '_01', 'bounds_m': [[0, 0, 0], [1, 2, 3]], 'location': [10, 20, 0],
         'materials': [], 'uv_channels': 0, 'triangles': 12}]}


def test_real_ground_producer_record_and_oks_record_give_manifest_ok(tmp_path):
    src = tmp_path / 'in' / 'ground_mesh.json'
    src.parent.mkdir()
    src.write_text(json.dumps(MESH), encoding='utf-8')
    gout = tmp_path / 'ground' / '0000_Syn_Ground.fbx'
    gout.parent.mkdir()
    r = ground_build(src, gout)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    rec_path = Path(str(gout) + bm.DERIVATION_SUFFIX)
    rec = bm.check_derivation(bm.strict_json(rec_path.read_bytes()))
    assert rec['role'] == 'ground' and rec['master_name'] == 'ground_mesh.json'
    assert rec['master_sha256'] == bm.sha256_file(src)
    assert rec['artifacts']['0000_Syn_Ground.fbx']['sha256'] == bm.sha256_file(gout)

    # a second build into the same output is refused before any write (records are never replaced)
    before = gout.read_bytes()
    again = ground_build(src, gout)
    assert again.returncode != 0 and 'already exists' in (again.stdout + again.stderr)
    assert gout.read_bytes() == before

    # output resolving to the input mesh JSON: refused, the input is not touched
    src_bytes = src.read_bytes()
    alias = ground_build(src, src)
    assert alias.returncode != 0 and 'is the input' in (alias.stdout + alias.stderr)
    assert src.read_bytes() == src_bytes and not Path(str(src) + bm.DERIVATION_SUFFIX).exists()
    oks_master = tmp_path / 'in' / 'Syn_master.blend'
    oks_master.write_bytes(b'synthetic OKS master')
    oout = tmp_path / 'npm' / 'fbx'
    oout.mkdir(parents=True)
    (oout / '0000_Syn_01.fbx').write_bytes(b'Kaydara FBX Binary  \x00 synthetic oks')
    bm.write_export_derivation([oout / '0000_Syn_01.fbx'], oks_master, bm.derivation_store(oout), 'abc1234',
                               master_sha256=bm.sha256_file(oks_master))

    package = tmp_path / 'pkg' / '0000_Syn.zip'
    package.parent.mkdir()
    with zipfile.ZipFile(package, 'w') as z:
        z.write(gout, gout.name)
        z.write(oout / '0000_Syn_01.fbx', '0000_Syn_01.fbx')
    stores = [str(rec_path), bm.derivation_store(oout)]

    # missing Ground record: refused naming the member, nothing written
    argv = ['build', str(package), '--master', 'oks=' + str(oks_master), '--master', 'ground=' + str(src),
            '--transform-name', 'identity', '--builder-commit', 'abc1234', '--derivation']
    assert cli.main(argv + stores[1:], reader=stub_rb) == 2
    assert not Path(bm.manifest_path(package)).exists()

    assert cli.main(argv + stores, reader=stub_rb) == 0
    with zipfile.ZipFile(package) as z:
        members = {n: bm.sha256_bytes(z.read(n)) for n in z.namelist()}
    raw = Path(bm.manifest_path(package)).read_bytes()
    rows = bm.manifest_findings(raw, members, package.name, bm.sha256_file(package),
                                {'oks': bm.sha256_file(oks_master), 'ground': bm.sha256_file(src)}, str(package.parent))
    assert [(s, c) for s, c, _ in rows] == [('pass', 'manifest_ok')], rows

    vp = subprocess.run([sys.executable, str(ROOT / 'tools/qa/validate_package.py'), str(package), '--json',
                         '--master', 'oks=' + str(oks_master), '--master', 'ground=' + str(src)],
                        capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert 'manifest_master' not in vp.stdout and 'build manifest' in vp.stdout, vp.stdout[-2000:] + vp.stderr
