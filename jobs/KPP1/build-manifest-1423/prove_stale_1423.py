"""#1423 KPP1 proof: one roof part changed in a master COPY -> the stale NPM / VPM set is detected and refused.

Pattern: n/a | new-case: proof driver over agr build-manifest / agr validate / package_core.cross_masters.

    uv run python jobs/KPP1/build-manifest-1423/prove_stale_1423.py OUT_DIR [--blender EXE]

Inputs (read only, hashes checked): quad master v002 (#1372) = master A, its NPM derivative 0000_Kpp_1_01.fbx
(run-quad-v002-r6b, agr vpm-to-npm), Ground v004 (#1416 package-v002), VPM v008 PNG/GeoJSON (#1371), the #1371
bridge mapping.json (transform). OUT_DIR must not exist. Writes OUT_DIR/proof.json (summary) and every file it made.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402
from adapters.max.agr_tools import package_core as pc  # noqa: E402

EV = Path('G:/Мой диск/AGR-evidence')
MASTER_A = EV / '1372-kpp1-quad-master/v002/SM_Kpp_1.quad-v002.fbx'
NPM_01 = EV / '1372-kpp1-quad-master/v002/run-quad-v002-r6b/0000_Kpp_1_01.fbx'
GROUND = EV / '1416-kpp1-ground-budget/package-v002/npm/0000_Kpp_1_Ground.fbx'
VPM_V008 = EV / '1371-kpp1-delivered/package-v008/SM_Kpp_1.zip'
BRIDGE = ROOT / 'jobs/KPP1/delivered-1371/mapping.json'
GROUND_SHA = '8006f0a3'  # #1416 REPORT: Ground v004 prefix
HERE = Path(__file__).resolve().parent


def run(argv, **kw):
    p = subprocess.run([str(a) for a in argv], capture_output=True, cwd=str(ROOT), **kw)
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def agr(*args):
    return run([sys.executable, '-m', 'dt_ai.cli.agr', *args])


def blender(exe, mode, src, out, rep):
    code, out_text, err = run([exe, '-b', '--factory-startup', '-noaudio', '--python', HERE / 'edit_export_1423.py',
                               '--', mode, src, out, rep], timeout=1800)
    if code != 0 or 'EDIT-EXPORT-OK' not in out_text:
        raise RuntimeError('blender {} failed: {}'.format(mode, (err or out_text)[-1500:]))
    return json.loads(Path(rep).read_text(encoding='utf-8'))


def zip_flat(target, files):
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, arcname=Path(f).name)


def manifest_rows(package, master=None):
    args = ['validate', str(package), '--json'] + (['--master', str(master)] if master else [])
    code, out, err = agr(*args)
    rep = json.loads(out)
    v001 = [s for s in rep['stages'] if s['id'] == 'V001'][0]
    rows = [{'status': f['status'], 'code': (f.get('data') or {}).get('code'), 'observed': f['observed'][:400]}
            for f in v001['findings'] if f['name'] == 'build manifest']
    return {'package': package.name, 'master_given': master.name if master else None, 'exit': code, 'rows': rows}


def build(package, master, recs, transform):
    code, out, err = agr('build-manifest', 'build', str(package), '--master', str(master), '--derivation',
                         *map(str, recs), '--transform-name', '1371-bridge', '--transform-file', str(transform))
    if code != 0:
        raise RuntimeError('build-manifest refused: ' + err)
    return json.loads(out.strip().splitlines()[-1])


def record(artifacts, master, out):
    code, o, err = agr('build-manifest', 'record', *map(str, artifacts), '--master', str(master), '--out', str(out))
    if code != 0:
        raise RuntimeError('record refused: ' + err)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--blender', default='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    a = ap.parse_args()
    E = Path(a.out)
    E.mkdir(parents=True)  # FileExistsError: never reuse a proof folder
    if not bm.sha256_file(GROUND).startswith(GROUND_SHA):
        raise SystemExit('Ground v004 hash changed')
    for d in ('master', 'npm-A', 'vpm-A', 'vpm-B', 'pkg-A', 'pkg-B', 'rec', 'logs'):
        (E / d).mkdir()
    master_a = E / 'master' / 'SM_Kpp_1.quad-v002.fbx'
    shutil.copyfile(MASTER_A, master_a)
    for f in (NPM_01, GROUND):
        shutil.copyfile(f, E / 'npm-A' / f.name)
    with zipfile.ZipFile(VPM_V008) as z:
        for n in z.namelist():
            if n.endswith(('.png', '.geojson')):
                (E / 'vpm-A' / n).write_bytes(z.read(n))
    tex = sorted(p for p in (E / 'vpm-A').iterdir())
    proof = {'inputs': {str(p): bm.sha256_file(p) for p in (MASTER_A, NPM_01, GROUND, VPM_V008, BRIDGE)}}

    # 1. baseline: one master revision A for NPM and VPM
    proof['vpm_A_export'] = blender(a.blender, 'vpm', master_a, E / 'vpm-A' / 'SM_Kpp_1.fbx', E / 'logs' / 'vpm-A.json')
    rec_npm = record(sorted((E / 'npm-A').iterdir()), master_a, E / 'rec' / 'npm-A.derivation.json')
    rec_vpm = record([E / 'vpm-A' / 'SM_Kpp_1.fbx'] + tex, master_a, E / 'rec' / 'vpm-A.derivation.json')
    npm_zip, vpm_zip = E / 'pkg-A' / '0000_Kpp_1.zip', E / 'pkg-A' / 'SM_Kpp_1.zip'
    zip_flat(npm_zip, sorted((E / 'npm-A').iterdir()))
    zip_flat(vpm_zip, sorted((E / 'vpm-A').iterdir()))
    proof['build_A'] = [build(npm_zip, master_a, [rec_npm], BRIDGE), build(vpm_zip, master_a, [rec_vpm], BRIDGE)]
    proof['validate_A'] = [manifest_rows(npm_zip, master_a), manifest_rows(vpm_zip, master_a)]
    proof['cross_A'] = pc.cross_masters([str(npm_zip), str(vpm_zip)])

    # 2. one roof part changed in a COPY of the master -> master B
    master_b = E / 'master' / 'SM_Kpp_1.quad-v002.roof-edit.fbx'
    proof['roof_edit'] = blender(a.blender, 'roof', master_a, master_b, E / 'logs' / 'roof-edit.json')
    proof['master_sha'] = {'A': bm.sha256_file(master_a), 'B': bm.sha256_file(master_b)}
    proof['validate_A_against_B'] = [manifest_rows(npm_zip, master_b), manifest_rows(vpm_zip, master_b)]

    # 3. only the VPM FBX re-exported from B; textures/GeoJSON and the NPM stay from A
    proof['vpm_B_export'] = blender(a.blender, 'vpm', master_b, E / 'vpm-B' / 'SM_Kpp_1.fbx', E / 'logs' / 'vpm-B.json')
    rec_b = record([E / 'vpm-B' / 'SM_Kpp_1.fbx'], master_b, E / 'rec' / 'vpm-B-fbx.derivation.json')
    rec_tex_a = record(tex, master_a, E / 'rec' / 'vpm-A-textures.derivation.json')
    vpm_zip_b = E / 'pkg-B' / 'SM_Kpp_1.zip'
    zip_flat(vpm_zip_b, [E / 'vpm-B' / 'SM_Kpp_1.fbx'] + tex)
    proof['build_B'] = build(vpm_zip_b, master_b, [rec_b, rec_tex_a], BRIDGE)
    proof['validate_B'] = manifest_rows(vpm_zip_b, master_b)
    npm_in_b = E / 'pkg-B' / '0000_Kpp_1.zip'
    shutil.copyfile(npm_zip, npm_in_b)
    shutil.copyfile(bm.manifest_path(npm_zip), bm.manifest_path(npm_in_b))
    shutil.copyfile(bm.readback_path(npm_zip), bm.readback_path(npm_in_b))
    proof['cross_B'] = pc.cross_masters([str(npm_in_b), str(vpm_zip_b)])
    proof['validate_npm_in_B'] = manifest_rows(npm_in_b, master_b)
    with open(E / 'proof.json', 'x', encoding='utf-8') as fh:
        json.dump(proof, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: proof[k] for k in ('master_sha', 'roof_edit')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
