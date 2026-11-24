"""KPP1 v004 package run (#1609): NPM derive + checks + NPM/VPM packages + validate (incl. V013) on a frozen packet.

Pattern: n/a | new-case: KPP1 package of the v004 lattice master; same frozen-packet discipline as
jobs/KPP1/quad-1372/run_checks.py (packet verified before/after every stage, NEW run dir, argv + exit per stage in
run.json). Never certifies delivery: V015-V017 are manual and s_podz is customer data [D306, D377].

    uv run python jobs/KPP1/lattice-1609/run_package_v004.py PACKET RUN GROUND_NPM_FBX THUMBNAIL GROUND_MASTER

PACKET (SHA256SUMS.txt + files): master-v004-delivery.blend (oks master, elements joined as loose parts),
master-v004-lattice.blend (element master), SM_Kpp_1.v004-lattice.fbx (element work FBX for V003 --master),
spec_v004.json, assemble.json. GROUND_NPM_FBX: the accepted #1416 Ground copy (package-v002, D306-D313), copied
byte-for-byte. THUMBNAIL: the real site thumbnail (#1361). Stages: derive (agr vpm-to-npm) -> readback -> export
xView (whole + element-wise [D336]) -> NPM package dir (OKS FBX + Ground + export_meta with fbx_records) ->
agr package-npm -> agr build-manifest build (masters per role [D328]) -> agr validate ZIP --scene (V013 via
--export-meta) -> VPM export (export_vpm.py) -> agr package-vpm --no-geojson [D224] -> agr validate VPM ZIP.
"""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
_spec = importlib.util.spec_from_file_location('run_checks_1372', ROOT / 'jobs/KPP1/quad-1372/run_checks.py')
_rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rc)
verify = _rc.verify


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(packet, out, ground, thumb, ground_master):
    packet, out, ground, thumb, ground_master = (Path(p).resolve() for p in (packet, out, ground, thumb,
                                                                             ground_master))
    if out.is_relative_to(packet) or packet.is_relative_to(out):
        raise ValueError('run root aliases the frozen packet')
    for p in (ground, thumb, ground_master):
        if not p.is_file():
            raise ValueError(f'missing input {p}')
        if p.is_relative_to(out):
            raise ValueError(f'input {p} lies inside the run dir')
    manifest = verify(packet)
    ground_sha = sha(ground)
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', DT_BLENDER=BLENDER)
    env.pop('MSYS_NO_PATHCONV', None)
    env.pop('MSYS2_ARG_CONV_EXCL', None)
    rec = {'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'manifest_sha256': manifest,
           'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
           'ground_npm_fbx': {'path': str(ground), 'sha256': ground_sha}, 'stages': [], 'delivery_passed': False}

    def stage(name, cmd):
        verify(packet)
        t = time.perf_counter()
        with (out / f'{name}.log').open('xb') as log:
            r = subprocess.run([str(c) for c in cmd], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        rec['stages'].append({'name': name, 'argv': [str(c) for c in cmd], 'exit': r.returncode,
                              'wall_seconds': round(time.perf_counter() - t, 1)})
        verify(packet)
        return r.returncode

    master, spec = packet / 'master-v004-delivery.blend', packet / 'spec_v004.json'
    recipe = ROOT / 'jobs/TEC26-OKS/scripts'
    bl = [BLENDER, '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1', '--python']
    try:
        if stage('derive', ['uv', 'run', 'agr', 'vpm-to-npm', '--blender', BLENDER, spec, out / 'atlas',
                            '--master', master, '--recipe-dir', recipe, '--cell', '512', '--pad', '8',
                            '--then-npm', master, spec, out / 'atlas', out / 'export/fbx', '0000',
                            '--recipe-dir', recipe]):
            raise RuntimeError('derive failed')
        fbx = out / 'export/fbx/0000_Kpp_1_01.fbx'
        stage('readback', bl + [ROOT / 'tools/blender/fbx_readback.py', '--', fbx, out / 'readback.json'])
        stage('export-xview', ['uv', 'run', 'dt', 'qa', 'xview', fbx, '--out', out / 'export-xview.json',
                               '--blender', BLENDER])
        stage('split-export', bl + [ROOT / 'jobs/KPP1/quad-1372/split_elements.py', '--',
                                    out / 'export/NPM_export_tri.blend', out / 'export-elements.blend',
                                    out / 'export-elements.json'])
        stage('export-xview-elements', ['uv', 'run', 'dt', 'qa', 'xview', out / 'export-elements.blend',
                                        '--out', out / 'export-xview-elements.json', '--blender', BLENDER])
        # NPM package dir: derived OKS FBX + the accepted Ground copy, one export_meta with fbx_records (V013)
        npm = out / 'npm/pkg'
        npm.mkdir(parents=True)
        shutil.copy2(fbx, npm / fbx.name)
        shutil.copy2(ground, npm / '0000_Kpp_1_Ground.fbx')
        if sha(npm / fbx.name) != sha(fbx) or sha(npm / '0000_Kpp_1_Ground.fbx') != ground_sha:
            raise RuntimeError('package copy changed bytes')
        derived = json.loads((out / 'export/fbx/export_meta.json').read_text(encoding='utf-8'))
        stage('ground-bounds', bl + [ROOT / 'tools/blender/fbx_readback.py', '--', npm / '0000_Kpp_1_Ground.fbx',
                                     out / 'ground-readback.json'])
        meta = dict(derived)
        meta['exported_files'] = [fbx.name, '0000_Kpp_1_Ground.fbx']
        meta['thumbnail'] = str(thumb)
        meta['exported_sha256'] = {fbx.name: sha(npm / fbx.name), '0000_Kpp_1_Ground.fbx': ground_sha}
        meta.setdefault('provenance', {})['exported_files'] = (
            f'{fbx.name} = agr vpm-to-npm of master-v004-delivery.blend (this run); 0000_Kpp_1_Ground.fbx = #1416 '
            f'package-v002 Ground copy byte-for-byte (sha {ground_sha[:16]}) [D306-D313]')
        (npm / 'export_meta.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
        # V013 input: exact FBX name -> {bounds_m (render meshes, no UCX), fbx_sha256} from the fresh readbacks
        v013 = {}
        for name, rb in ((fbx.name, out / 'readback.json'), ('0000_Kpp_1_Ground.fbx', out / 'ground-readback.json')):
            ms = [m for m in json.loads(rb.read_text(encoding='utf-8'))['meshes'] if not m['name'].startswith('UCX_')]
            v013[name] = {'bounds_m': [[min(m['bounds_m'][0][a] for m in ms) for a in range(3)],
                                       [max(m['bounds_m'][1][a] for m in ms) for a in range(3)]],
                          'fbx_sha256': sha(npm / name)}
        (out / 'npm/v013-bounds.json').write_text(json.dumps(v013, indent=1), encoding='utf-8')
        stage('package-npm', ['uv', 'run', 'agr', 'package-npm', npm])
        rec['npm_zip'] = sorted(str(p) for p in (out / 'npm').glob('*.zip'))
        # [D328]/[D333]: masters per role. OKS = the delivery master (export_npm wrote its record); Ground = the
        # #1416 v002 Ground copy the accepted v004 Ground was derived from (derive_ground_v003.py, REPORT #1416),
        # recorded here at package time because the #1416 record store is not on Drive
        (out / 'derivation-ground').mkdir()
        roles = [a for r in ('ground', 'groundel', 'flora') for a in ('--master', f'{r}={ground_master}')]
        stage('record-ground', ['uv', 'run', 'python', ROOT / 'jobs/KPP1/lattice-1609/record_ground.py',
                                npm / '0000_Kpp_1_Ground.fbx', ground_master, out / 'derivation-ground',
                                'SM_Kpp_1_Ground,SM_Kpp_1_GroundEl,SM_Kpp_1_Flora'])
        stage('build-manifest', ['uv', 'run', 'agr', 'build-manifest', 'build', *rec['npm_zip'][:1],
                                 '--master', f'oks={master}', *roles,
                                 '--derivation', out / 'export/derivation', out / 'derivation-ground',
                                 '--transform-name', 'OKS: export_npm plan-centre pivot; Ground: #1416 copy as is',
                                 '--blender', BLENDER])
        common = ['uv', 'run', 'agr', 'validate', *rec['npm_zip'][:1], '--profile', 'npm', '--scene', '--json',
                  '--export-meta', out / 'npm/v013-bounds.json',
                  '--npm-atlas', f'{fbx.name}={out / "atlas/npm_atlas.json"}']
        # the validator takes either role masters (V001 stale check per role [D328]) or the unkeyed work FBX
        # (V003 master quads, DER-03 [D198]); both reports are kept, the open items are their union
        stage('validate-npm', common + ['--master', f'oks={master}', *roles])
        stage('validate-npm-work', common + ['--master', packet / 'SM_Kpp_1.v004-lattice.fbx'])
        rec['quality_status'] = 'not_passed'   # V015-V017 manual + s_podz customer, even if machine stages pass
    finally:
        rec['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            rec['packet_unchanged'] = verify(packet) == manifest
        except ValueError as exc:
            rec['packet_unchanged'] = False
            rec['integrity_error'] = str(exc)
        (out / 'run.json').write_text(json.dumps(rec, indent=2), encoding='utf-8')
        print(json.dumps({s['name']: s['exit'] for s in rec['stages']}))


if __name__ == '__main__':
    if len(sys.argv) != 6:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
