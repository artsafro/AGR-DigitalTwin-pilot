"""new-case: the real exporters (tools/derive/export_npm.py, jobs/KPP1/scripts/export_vpm.py) on a synthetic master (#1505).

Opt-in (`-m blender`): headless Blender builds a synthetic master .blend (no customer data), then
* export_npm with an atlas bound to that master writes the FBX, export_meta with master_sha256 and the derivation record;
* export_npm with an atlas bound to another master revision is refused with `atlas_master_mismatch`, nothing written;
* export_vpm writes its derivation record + master_sha256;
* the zipped NPM FBX + export-time records give a build manifest pass; editing the master afterwards gives a finding.
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402
from adapters.max.agr_tools import export_meta as em  # noqa: E402

pytestmark = pytest.mark.blender

MAKE_MASTER = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
def quad_mesh(name, quads, uvs=None):
    verts, faces = [], []
    for q in quads:
        faces.append(tuple(range(len(verts), len(verts) + 4)))
        verts += q
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if uvs is not None:
        uv = me.uv_layers.new(name="UVMap")
        for i, loop in enumerate(me.loops):
            uv.data[i].uv = uvs[loop.index]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob
def mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.new("ShaderNodeTexImage")
    return m
wall = [(0, 0, 0), (4, 0, 0), (4, 0, 3), (0, 0, 3)]
roof = [(0, 0, 3), (4, 0, 3), (4, 2, 3), (0, 2, 3)]
uvs = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9), (1.1, 0.1), (1.9, 0.1), (1.9, 0.9), (1.1, 0.9)]
main = quad_mesh("SM_Syn_Main", [wall, roof], uvs)
fin = main.data.attributes.new("finish", "INT", "FACE")
fin.data[0].value, fin.data[1].value = 0, 1
main["finish_names"] = "Brick,Plaster"
main.data.materials.append(mat("M_Brick"))
glass = quad_mesh("SM_Syn_MainGlass", [[(1, -0.01, 1), (2, -0.01, 1), (2, -0.01, 2), (1, -0.01, 2)]],
                  [(0.2, 0.2), (0.4, 0.2), (0.4, 0.4), (0.2, 0.4)])
glass.data.materials.append(mat("M_Glass"))
quad_mesh("UCX_SM_Syn_Main_001", [wall])
bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def blender_exe():
    for p in (os.environ.get('DT_BLENDER'), 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe',
              'C:/Program Files/Blender Foundation/Blender 4.4/blender.exe'):
        if p and Path(p).is_file():
            return p
    pytest.skip('Blender not installed (opt-in -m blender test)')


def blender(script_args, timeout=300):
    cmd = [blender_exe(), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
           *script_args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in Path(root).rglob('*') if p.is_file()}


@pytest.fixture
def inputs(tmp_path):
    from PIL import Image
    d = tmp_path / 'inputs'
    d.mkdir()
    script = d / 'make_master.py'
    script.write_text(MAKE_MASTER, encoding='utf-8')
    master = d / 'master.blend'
    r = blender(['--python', str(script), '--', str(master)])
    assert r.returncode == 0 and master.is_file(), r.stdout[-2000:] + r.stderr[-2000:]
    spec = d / 'spec.json'
    spec.write_text(json.dumps({'address': 'Syn', 'finishes': {'Brick': {'udim': 1001}, 'Plaster': {'udim': 1002}}}))
    atlas = d / 'atlas'
    atlas.mkdir()
    finishes = {'Brick': {'udim': 1001, 'u0': 0.0, 'v0': 0.5, 'size': 0.25},
                'Plaster': {'udim': 1002, 'u0': 0.5, 'v0': 0.5, 'size': 0.25}}
    for suffix in ('d', 'o'):
        Image.new('RGB', (64, 64), (200, 120, 90)).save(atlas / f'T_Syn_001_Main_{suffix}_1.png')
    (atlas / 'npm_atlas.json').write_text(json.dumps({'atlas': 2048, 'finishes': finishes,
                                                      'master': bm.atlas_master_binding(master, finishes)}))
    return master, spec, atlas


def export_npm(master, spec, atlas, out):
    return blender(['--python', str(ROOT / 'tools/derive/export_npm.py'), '--', str(master), str(spec), str(atlas),
                    str(out)])


def test_export_npm_writes_derivation_record_and_master_hash(inputs, tmp_path):
    master, spec, atlas = inputs
    before = bm.sha256_file(master)
    out = tmp_path / 'npm-v001' / 'fbx'
    r = export_npm(master, spec, atlas, out)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    fbx = out / '0000_Syn_01.fbx'
    rec_path = tmp_path / 'npm-v001' / 'derivation' / '0000_Syn_01.fbx.derivation.json'
    rec = bm.check_derivation(bm.strict_json(rec_path.read_bytes()))
    assert rec['master_sha256'] == before == bm.sha256_file(master)
    assert rec['master_path'] == os.path.abspath(master)
    assert rec['artifacts'] == {fbx.name: {'kind': 'npm_fbx', 'sha256': bm.sha256_file(fbx)}}
    meta = em.load_meta(out / 'export_meta.json')
    assert meta['master_sha256'] == before
    # the store is outside the package folder: package members stay FBX + export_meta
    assert sorted(p.name for p in out.iterdir()) == ['0000_Syn_01.fbx', 'export_meta.json']

    # synthetic complete set: the export-time record is the only derivation input of the manifest build
    package = tmp_path / '0000_Syn.zip'
    with zipfile.ZipFile(package, 'w') as z:
        z.write(fbx, fbx.name)
    sys.path.insert(0, str(ROOT / 'tests' / 'qa'))
    from test_build_manifest_1423 import cli, good_rb
    argv = ['build', str(package), '--master', str(master), '--derivation', str(rec_path.parent),
            '--transform-name', 'identity', '--builder-commit', 'abc1234']
    assert cli.main(argv, reader=good_rb) == 0
    raw = Path(bm.manifest_path(package)).read_bytes()
    members = {fbx.name: bm.sha256_file(fbx)}

    def rows():
        return [(s, c) for s, c, _ in bm.manifest_findings(raw, members, package.name, bm.sha256_file(package),
                                                           bm.sha256_file(master), str(tmp_path))]
    assert rows() == [('pass', 'manifest_ok')]
    with open(master, 'ab') as fh:  # master edited after the export
        fh.write(b'\0')
    assert ('fail', 'manifest_master_stale') in rows() and ('pass', 'manifest_ok') not in rows()


@pytest.mark.parametrize('case,reason', [('other_master', 'atlas_master_mismatch'), ('unbound', 'atlas_unbound'),
                                         ('udims', 'atlas_udim_mismatch')])
def test_export_npm_refuses_an_atlas_not_bound_to_this_master(inputs, tmp_path, case, reason):
    master, spec, atlas = inputs
    data = json.loads((atlas / 'npm_atlas.json').read_text())
    if case == 'other_master':
        data['master']['sha256'] = '0' * 64
    elif case == 'unbound':
        del data['master']
    else:
        data['master']['udims'] = [1001]
    bad = tmp_path / 'atlas-bad'
    shutil.copytree(atlas, bad)
    (bad / 'npm_atlas.json').write_text(json.dumps(data))
    before = snapshot(tmp_path)
    r = export_npm(master, spec, bad, tmp_path / 'npm-v002' / 'fbx')
    assert r.returncode != 0
    assert reason in r.stdout + r.stderr, r.stdout[-2000:] + r.stderr[-2000:]
    assert snapshot(tmp_path) == before
    assert not (tmp_path / 'npm-v002').exists()


def test_export_vpm_writes_derivation_record_and_master_hash(inputs, tmp_path):
    master, _, _ = inputs
    before = bm.sha256_file(master)
    pkg = tmp_path / 'vpm-v001' / 'package'
    r = blender(['--python', str(ROOT / 'jobs/KPP1/scripts/export_vpm.py'), '--', str(master), str(pkg)])
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    fbx = pkg / 'SM_Syn.fbx'
    rec = bm.check_derivation(bm.strict_json(
        (tmp_path / 'vpm-v001' / 'derivation' / 'SM_Syn.fbx.derivation.json').read_bytes()))
    assert rec['master_sha256'] == before
    assert rec['artifacts'] == {'SM_Syn.fbx': {'kind': 'vpm_fbx', 'sha256': bm.sha256_file(fbx)}}
    meta = json.loads((tmp_path / 'vpm-v001' / 'export_meta.json').read_text())
    assert meta['master_sha256'] == before
    em.validate_meta(meta)
    assert sorted(p.name for p in pkg.iterdir()) == ['SM_Syn.fbx']  # package_vpm zips this folder
