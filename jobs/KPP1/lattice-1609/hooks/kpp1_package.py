"""KPP1 #1609 package-input hook (oks-npm stage `package-npm`, point `before`): NPM package dir, V013 bounds, Ground record.

Pattern: n/a | new-case: the job-specific inputs of the KPP1 v004 NPM package around the skeleton commands (review r1
P1-1, [D324]): the derive, readback, xView, `agr package-npm`, `agr build-manifest` and `agr validate` stages run as
the skeleton commands in README.md; this hook only writes what those commands read and the job has no owner for.

    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_package.py verify PACKET
    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_package.py npm-dir FBX GROUND_FBX THUMBNAIL READBACK GROUND_READBACK PKG_DIR V013_OUT
    uv run python jobs/KPP1/lattice-1609/hooks/kpp1_package.py record-ground GROUND_FBX GROUND_MASTER STORE_DIR PARTS_CSV

- `verify`: the frozen packet (SHA256SUMS.txt + files) is intact (`quad-1372/run_checks.verify`); run it before and
  after every stage, the packet is never written. Prints the manifest sha256.
- `npm-dir`: NEW PKG_DIR = the derived OKS FBX + the accepted #1416 Ground copy, both byte-for-byte, and one
  export_meta.json (the derived export_meta next to FBX + exported_files / thumbnail / sha256 / provenance); V013_OUT =
  exact FBX name -> {bounds_m of the render meshes (no UCX), fbx_sha256} from the two fresh readbacks (V013 input of
  `agr validate --export-meta`). Every input must exist; PKG_DIR and V013_OUT must not exist and must not hold or
  alias an input.
- `record-ground`: derivation record of the accepted #1416 Ground copy per part role [D328, D333] (the #1416 Drive
  evidence does not keep the export record derive_ground_v003.py writes); one dependency per role.
Never certifies delivery: V015-V017 are manual and s_podz is customer data [D306, D377].
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
GROUND_NAME = '0000_Kpp_1_Ground.fbx'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(packet):
    spec = importlib.util.spec_from_file_location('run_checks_1372', ROOT / 'jobs/KPP1/quad-1372/run_checks.py')
    if spec is None or spec.loader is None:
        raise ValueError('cannot load jobs/KPP1/quad-1372/run_checks.py')
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    digest = rc.verify(Path(packet).resolve())
    print('PACKET', digest)
    return digest


def bounds(readback):
    ms = [m for m in json.loads(Path(readback).read_text(encoding='utf-8'))['meshes']
          if not m['name'].startswith('UCX_')]
    if not ms:
        raise ValueError(f'{readback}: no render mesh')
    return [[min(m['bounds_m'][0][a] for m in ms) for a in range(3)],
            [max(m['bounds_m'][1][a] for m in ms) for a in range(3)]]


def npm_dir(fbx, ground, thumb, readback, ground_readback, pkg, v013_out):
    fbx, ground, thumb, readback, ground_readback, pkg, v013_out = (
        Path(p).resolve() for p in (fbx, ground, thumb, readback, ground_readback, pkg, v013_out))
    meta_in = fbx.parent / 'export_meta.json'
    inputs = (fbx, ground, thumb, readback, ground_readback, meta_in)
    for p in inputs:
        if not p.is_file():
            raise ValueError(f'missing input {p}')
    for out in (pkg, v013_out):
        if os.path.lexists(out):
            raise ValueError(f'{out} exists; never overwrite')
        if any(p == out or p.is_relative_to(out) for p in inputs):
            raise ValueError(f'{out} holds or aliases an input')
    if v013_out.is_relative_to(pkg):
        raise ValueError('V013_OUT must not lie inside the package dir')
    if fbx.name == GROUND_NAME:
        raise ValueError(f'the OKS FBX must not be named {GROUND_NAME}')
    meta = json.loads(meta_in.read_text(encoding='utf-8'))
    pkg.mkdir(parents=True)
    shutil.copy2(fbx, pkg / fbx.name)
    shutil.copy2(ground, pkg / GROUND_NAME)
    fbx_sha, ground_sha = sha(fbx), sha(ground)
    if sha(pkg / fbx.name) != fbx_sha or sha(pkg / GROUND_NAME) != ground_sha:
        raise RuntimeError('package copy changed bytes')
    meta['exported_files'] = [fbx.name, GROUND_NAME]
    meta['thumbnail'] = str(thumb)
    meta['exported_sha256'] = {fbx.name: fbx_sha, GROUND_NAME: ground_sha}
    meta.setdefault('provenance', {})['exported_files'] = (
        f'{fbx.name} = agr vpm-to-npm of master-v004-delivery.blend; {GROUND_NAME} = #1416 package-v002 Ground copy '
        f'byte-for-byte (sha {ground_sha[:16]}) [D306-D313]')
    (pkg / 'export_meta.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
    v013 = {fbx.name: {'bounds_m': bounds(readback), 'fbx_sha256': fbx_sha},
            GROUND_NAME: {'bounds_m': bounds(ground_readback), 'fbx_sha256': ground_sha}}
    v013_out.parent.mkdir(parents=True, exist_ok=True)
    v013_out.write_text(json.dumps(v013, indent=1), encoding='utf-8')
    print('NPM-DIR', pkg, sorted(v013))


def record_ground(fbx, master, store, parts_csv):
    """Derivation record of the accepted #1416 Ground copy, per part role [D328, D333] (was record_ground.py).

    The Ground FBX (bytes unchanged) was derived from the #1416 v002 Ground copy. One dependency per part role
    (ground / groundel / flora by build_manifest.role_of), source_id `KPP1.<role>.geometry`; the customer / bridge
    inputs of #1416 are not re-attested here, so the record names only the geometry source.
    """
    sys.path.insert(0, str(ROOT))
    from adapters.max.agr_tools import build_manifest as bm
    parts = [p for p in parts_csv.split(',') if p]
    if not parts:
        raise SystemExit('no parts named')
    digest = bm.sha256_file(master)
    roles = {}
    for name in parts:
        roles.setdefault(bm.role_of(name), []).append(name)
    deps = [{'role': role, 'master': os.path.abspath(master), 'master_sha256': digest, 'parts': sorted(names),
             'source_id': f'KPP1.{role}.geometry'} for role, names in sorted(roles.items())]
    rec = bm.write_export_derivation([fbx], master, store, bm.git_commit(str(ROOT)), master_sha256=digest,
                                     role='ground', dependencies=deps, source_id='KPP1.ground.geometry')
    print('RECORD', rec if isinstance(rec, str) else 'written', sorted(roles))


COMMANDS = {'verify': (verify, 1), 'npm-dir': (npm_dir, 7), 'record-ground': (record_ground, 4)}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS or len(sys.argv) - 2 != COMMANDS[sys.argv[1]][1]:
        raise SystemExit(__doc__)
    try:
        COMMANDS[sys.argv[1]][0](*sys.argv[2:])
    except ValueError as exc:
        print('ERROR', exc, file=sys.stderr)
        sys.exit(2)
