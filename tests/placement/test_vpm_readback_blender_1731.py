"""NPM -> VPM placement readback in a real background Blender (#1731, opt-in ``-m blender``).

Pattern: n/a | new-case: real-Blender test of tools/blender/vpm_placement_readback.py.

Reproduces the Staropetrovskiy VPM v001 incident on SYNTHETIC meshes: a MAF library whose object sits at the
package pivot is appended, the v001 assembly reads the stale ``matrix_world`` (identity right after the append)
and subtracts the pivot a second time. The reader (``tools/blender/vpm_placement_readback.py``) must
- fail that assembly with every part diagnosed ``pivot subtracted twice`` and pass the corrected one (parts CLI);
- read fresh positions itself (``view_layer.update()``) and block the export before ``export_scene.fbx``.
"""
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from twinqa.scene import find_blender

pytestmark = pytest.mark.blender

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "tools" / "blender" / "vpm_placement_readback.py"
PIV = (130.132, 17616.178, 166.49)
NPM = {"MAF_A01": (171.872, 17608.536, 166.49), "MAF_B03": (140.5, 17630.25, 167.1),
       "FLORA_S12": (120.0, 17600.0, 165.9)}

BUILD = textwrap.dedent("""
    import bpy, json, sys
    from mathutils import Matrix, Vector
    a = sys.argv[sys.argv.index('--') + 1:]
    lib, twice_blend, fixed_blend, out_json, driver_dir = a[:5]
    PIV = Vector(%(piv)r)
    NPM = %(npm)r
    sys.path.insert(0, driver_dir)
    import vpm_placement_readback as rb

    def box(c, s=0.2):
        v = [(c[0] + dx * s, c[1] + dy * s, c[2] + dz * s) for dx in (-1, 1) for dy in (-1, 1) for dz in (0, 2)]
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        return v, f

    # library: one GroundEl mesh (data = NPM - pivot, object at the pivot) + one object per instance (at NPM)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    V, F = [], []
    for p in NPM.values():
        v, f = box([p[i] - PIV[i] for i in range(3)])
        F += [[j + len(V) for j in q] for q in f]
        V += v
    me = bpy.data.meshes.new('el'); me.from_pydata(V, [], F)
    el = bpy.data.objects.new('X_GroundEl', me); bpy.context.scene.collection.objects.link(el); el.location = PIV
    for h, p in NPM.items():
        v, f = box((0, 0, 0)); m = bpy.data.meshes.new(h); m.from_pydata(v, [], f)
        o = bpy.data.objects.new(h, m); bpy.context.scene.collection.objects.link(o); o.location = p
    bpy.ops.wm.save_as_mainfile(filepath=lib)
    rep = {}

    def append(names):
        with bpy.data.libraries.load(lib, link=False) as (src, dst):
            dst.objects = names
        for o in dst.objects:
            bpy.context.scene.collection.objects.link(o)
        return dst.objects

    for tag, path in (('twice', twice_blend), ('fixed', fixed_blend)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        maf = append(['X_GroundEl'])[0]
        rep[tag + '_stale_translation'] = list(maf.matrix_world.translation)
        if tag == 'fixed':
            bpy.context.view_layer.update()
        maf.data.transform(maf.matrix_world)      # v001: stale identity -> no-op
        maf.matrix_world = Matrix.Identity(4)
        maf.data.transform(Matrix.Translation(-PIV))
        bpy.ops.wm.save_as_mainfile(filepath=path)

    # pre-export gate on appended instance objects; no manual depsgraph update before the reader
    for tag in ('gate_fixed', 'gate_twice'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        obs = append(list(NPM))
        rep[tag + '_stale_before'] = {o.name: list(o.matrix_world.translation) for o in obs}
        for o in obs:
            o.location = o.location - PIV * (2 if tag == 'gate_twice' else 1)
        fbx = out_json + '.' + tag + '.fbx'
        try:
            rb.check_before_export(NPM, obs, list(PIV), report_path=out_json + '.' + tag + '.report.json')
            bpy.ops.export_scene.fbx(filepath=fbx)
            rep[tag] = 'exported'
        except rb.vr.PlacementReadbackFailed as e:
            rep[tag] = 'blocked: ' + str(e)
    json.dump(rep, open(out_json, 'w'), indent=1)
""") % {"piv": PIV, "npm": NPM}


def run(exe, *args):
    return subprocess.run([exe, "--background", "--factory-startup", "--python-exit-code", "3", *args],
                          capture_output=True, text=True, timeout=600)


def test_append_pivot_twice_fails_fixed_passes(tmp_path):
    exe = find_blender()
    if exe is None:
        pytest.skip("Blender not installed")
    script = tmp_path / "build.py"
    script.write_text(BUILD, encoding="utf-8")
    lib, twice, fixed, out = (tmp_path / n for n in ("lib.blend", "twice.blend", "fixed.blend", "build.json"))
    r = run(exe, "--python", str(script), "--", str(lib), str(twice), str(fixed), str(out), str(DRIVER.parent))
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    rep = json.loads(out.read_text(encoding="utf-8"))
    # the Blender pitfall itself: matrix_world right after the append is the identity
    assert rep["twice_stale_translation"] == [0.0, 0.0, 0.0]
    assert all(v == [0.0, 0.0, 0.0] for v in rep["gate_fixed_stale_before"].values())
    # pre-export gate: fresh read passes the correct placement and blocks the doubled pivot before the export
    assert rep["gate_fixed"] == "exported", rep
    assert rep["gate_twice"].startswith("blocked:") and "pivot subtracted twice" in rep["gate_twice"]
    assert not Path(str(out) + ".gate_twice.fbx").exists()
    gate = json.loads(Path(str(out) + ".gate_twice.report.json").read_text(encoding="utf-8"))
    assert sorted(o["handle"] for o in gate["offenders"]) == sorted(NPM)

    piv = ",".join(map(str, PIV))
    res = {}
    for tag, scene in (("twice", twice), ("fixed", fixed)):
        rp = tmp_path / f"{tag}.report.json"
        r = run(exe, "--python", str(DRIVER), "--", "parts", "--npm", str(lib), "--npm-object", "X_GroundEl",
                "--scene", str(scene), "--scene-object", "X_GroundEl", "--pivot", piv, "--out", str(rp))
        res[tag] = (r.returncode, json.loads(rp.read_text(encoding="utf-8")))
    code, bad = res["twice"]
    assert code == 1 and bad["status"] == "fail" and bad["n_npm"] == 3
    assert {o["diagnosis"] for o in bad["offenders"]} == {"pivot subtracted twice"}
    code, good = res["fixed"]
    assert code == 0 and good["status"] == "pass" and good["n_ok"] == 3

    # report path that is an input: exit 2, the input is untouched
    before = lib.read_bytes()
    r = run(exe, "--python", str(DRIVER), "--", "parts", "--npm", str(lib), "--npm-object", "X_GroundEl",
            "--scene", str(fixed), "--scene-object", "X_GroundEl", "--pivot", piv, "--out", str(lib))
    assert r.returncode == 2 and lib.read_bytes() == before
