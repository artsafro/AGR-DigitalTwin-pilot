"""Reproduce #298 assembly and machine evidence at a new output version.

new-case: job-local copy-only package evidence driver, not a shared publish tool.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUND_AREA_M2 = 16743.96  # VPM GND-06 basis: S_ter 25,854.04 - S_pz 9,110.08 (build_ground report)
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
from twinqa.scene import find_blender
from assembly_rules import new_output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--source', default='C:/x/t_5e4ea2be/run_v006', help='placement run (place_site.py --out)')
    ap.add_argument('--site', choices=('v014', 'v015'), default='v014')
    ap.add_argument('--maf-list', default='C:/x/vatutino-maf/v005-set/atlas/material-list.json')
    ap.add_argument('--npm-stem', default='SM_Vatutino', help='NPM ZIP stem; {code4}_Vatutino once the code is known')
    a = ap.parse_args()
    source = Path(a.source)
    out = new_output(source, a.out)
    out.mkdir(parents=True)
    commands = []

    def run(label, cmd, allowed=(0,), timeout=1800):
        result = subprocess.run(list(map(str, cmd)), cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        rec = {'label': label, 'command': list(map(str, cmd)), 'exit_code': result.returncode}
        commands.append(rec)
        (out / f'{label}.stdout').write_text(result.stdout, encoding='utf-8')
        (out / f'{label}.stderr').write_text(result.stderr, encoding='utf-8')
        (out / 'commands.json').write_text(json.dumps(commands, indent=1), encoding='utf-8')
        print(label, 'exit', result.returncode, flush=True)
        if result.returncode not in allowed:
            raise RuntimeError(f'{label}: {result.stdout[-500:]} {result.stderr[-1500:]}')
        return result

    blender = find_blender()
    def dcc(label, script, *args):
        return run(label, [blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python', ROOT / script, '--', *args])

    for profile in ('npm', 'vpm'):
        scene = source / profile / f'VATUTINO-SITE_placement_{profile}_v001.blend'
        dcc(f'prepare-{profile}', 'jobs/VATUTINO-SITE/prepare_assembly.py', scene, out / profile, profile, a.maf_list)
    run('flora-atlas', [sys.executable, 'tools/library/flora_atlas_from_scene.py', '--scene-json', out / 'npm/flora-placed.json', '--catalogue', 'library/flora/catalogue.json', '--out-dir', out / 'atlas', '--address', 'Vatutino', '--scene', out / 'npm/prepared.blend'])
    run('maf-atlas', [sys.executable, 'tools/materials/atlas_maf.py', out / 'npm/maf-materials.json', '--out-png', out / 'atlas/T_Vatutino_GroundEl_D_1.png', '--out-json', out / 'atlas/maf-uv.json'])
    hashes = {}
    for profile in ('npm', 'vpm'):
        dcc(f'assemble-{profile}', 'jobs/VATUTINO-SITE/assemble_delivery.py', out / profile, profile, a.site)
        folder = out / 'packages' / profile
        folder.mkdir(parents=True)
        stem = a.npm_stem if profile == 'npm' else 'SM_Vatutino_Ground'
        archive = folder / f'{stem}.zip'
        fbx = out / profile / 'SM_Vatutino_Ground.fbx'
        # NPM: {stem}_Ground.fbx next to the OKS parts (reg p.11 10.1); VPM: SM_{Address}_Ground.fbx
        arcname = f'{stem}_Ground.fbx' if profile == 'npm' else fbx.name
        files = [(fbx, arcname)] + ([(f, f.name) for f in (out / profile).glob('*.png')] if profile == 'vpm' else [])
        with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
            for file, name in files:
                z.write(file, name)
        hashes[profile] = {'zip': str(archive), 'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'fbx_sha256': hashlib.sha256(fbx.read_bytes()).hexdigest()}
        # ZIP extracted once into a new directory. Both readback routes use these bytes.
        extracted = out / 'readback' / profile
        with zipfile.ZipFile(archive) as z:
            z.extractall(extracted)
        dcc(f'readback-{profile}', 'tools/blender/fbx_readback.py', extracted / arcname, out / f'readback-{profile}.json')
        run(f'validate-{profile}', [sys.executable, 'tools/qa/validate_package.py', archive, '--profile', profile, '--json'], allowed=(0, 1, 2))
        area = ['--ground-area-m2', str(GROUND_AREA_M2)] if profile == 'vpm' else []  # S_ter - S_pz, GND-06
        run(f'validate-scene-{profile}', [sys.executable, 'tools/qa/validate_package.py', archive, '--profile', profile, '--scene', '--json', *area], allowed=(0, 1, 2))
        run(f'sintez-{profile}', [blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python', 'jobs/KPP1/scripts/run_agr_checker.py', '--', folder, out / f'sintez-{profile}.json'], allowed=(0, 1))
    (out / 'hashes.json').write_text(json.dumps(hashes, indent=1), encoding='utf-8')
    print(json.dumps(hashes, indent=1))


if __name__ == '__main__':
    main()
