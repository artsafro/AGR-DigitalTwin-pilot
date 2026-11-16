"""new-case: source pinning per master version and the provenance record of the KPP1 quad master (#1563).

Stdlib only: imported by `build_quad_master.py` inside Blender and by the tests.

- `VERSION_SOURCE`: every master version is built from exactly one R1 `SM_Kpp_1.fbx`, pinned by sha256
  (v001/v002 from r1-v002 #1230, v003 from r1-v003 of rerun-1230 #1246). An unknown version, another source or a
  zone plan of another source is an error naming it.
- `write_provenance`: after the build, the export-time derivation record of #1505/#1551
  (`build_manifest.write_export_derivation`: work FBX sha256 + R1 master sha256 + builder commit) goes to
  `<packet>/derivation/`, and `quad-provenance-<version>.json` binds source sha256, union plan sha256, every output
  sha256, the script commit and that record. No admission is written: admission is Artem's decision bound to the
  output hash (`admission: null`). Existing files are never replaced.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'adapters' / 'max' / 'agr_tools'))
import build_manifest as bm  # noqa: E402  stdlib owner of derivation records (#1505/#1551)

R1_V002 = '1f46b0dd5973b6e3ba40acbe04d65fb3595dcacb0d90a7724e921eda9b56b676'
# r1-v003 = the LOCAL axis-aligned R1 of rerun-1230 (#1246, `1246-kpp1-corner-pairs/SM_Kpp_1.fbx`). The #1278
# `site-r1-v003` copy (R1_V003_PLACED) is the same mesh rotated -6.053 deg for the site (D262): the editable master
# is modelled in world x/y and placement stays the last (package) step [D135, conflicts.md #39], so it is refused.
R1_V003 = '76a7c97e523d6ac6475443a84f51e4b2ec588de3cbeb1b300d08adf07e97dc50'
R1_V003_PLACED = 'eb9d105af9de642d03928078917a174e9d2f5cb46b0a8d8460fd38e6cd47cc72'
SOURCE_NAME = {R1_V002: 'r1-v002', R1_V003: 'r1-v003'}
VERSION_SOURCE = {'v001': R1_V002, 'v002': R1_V002, 'v003': R1_V003}
SCHEMA = 'agr.kpp1-quad-provenance/1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_source(version, digest, plan=None):
    """Raise ValueError unless `digest` is the pinned R1 of `version` and the plan (if any) is a plan of it."""
    want = VERSION_SOURCE.get(version)
    if want is None:
        raise ValueError(f'master version {version!r} has no pinned R1 source (known: {", ".join(VERSION_SOURCE)})')
    if digest != want:
        raise ValueError(f'source sha {digest} is not the approved {SOURCE_NAME[want]} SM_Kpp_1.fbx of {version} '
                         f'({want})')
    if plan is not None and plan.get('source_sha256') != digest:
        raise ValueError(f"union plan source {plan.get('source_sha256')!r} is not the {version} source {digest}")
    return SOURCE_NAME[want]


def script_state(root=ROOT):
    """(commit, clean) of the builder scripts: clean = no uncommitted change under jobs/KPP1/quad-1372."""
    commit = bm.git_commit(root)
    try:
        r = subprocess.run(['git', '-C', os.fspath(root), 'status', '--porcelain', '--', 'jobs/KPP1/quad-1372'],
                           capture_output=True, text=True, timeout=30)
        clean = r.returncode == 0 and not r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        clean = False
    return commit, clean


def write_provenance(packet, version, source, source_digest, plan_path, outputs, commit, clean):
    """Write the derivation record + `quad-provenance-<version>.json` (new files only); return the record path."""
    packet = Path(packet)
    check_source(version, source_digest)
    if sha(source) != source_digest:
        raise ValueError(f'master_changed_during_export: {source} is no longer {source_digest}')
    out = packet / f'quad-provenance-{version}.json'
    if os.path.lexists(out):
        raise FileExistsError(f'refusing to overwrite: {out}')
    names = [Path(p).name for p in outputs]
    if len(set(names)) != len(names) or out.name in names:
        raise ValueError(f'outputs alias each other or the provenance record: {names}')
    fbx = [p for p in outputs if str(p).lower().endswith('.fbx')]
    if len(fbx) != 1:
        raise ValueError(f'exactly one work FBX expected among the outputs, got {len(fbx)}')
    rec = bm.write_export_derivation(fbx, source, packet / bm.DERIVATION_STORE, commit, source_digest,
                                     inputs=[p for p in outputs if p not in fbx] + ([plan_path] if plan_path else []),
                                     role='oks')
    data = {'schema': SCHEMA, 'version': version,
            'source': {'path': str(source), 'sha256': source_digest, 'r1': SOURCE_NAME[source_digest]},
            'union_plan': None if plan_path is None else {'path': str(plan_path), 'sha256': sha(plan_path)},
            'outputs': {Path(p).name: sha(p) for p in outputs},
            'script_commit': commit, 'scripts_clean': clean,
            'derivation_record': {'path': str(rec), 'sha256': sha(rec)},
            'admission': None,
            'admission_note': 'not decided here: admission is a decision of Artem bound to the output sha256'}
    bm.write_new(os.fspath(out), bm.dumps(data), [os.fspath(p) for p in outputs] + [os.fspath(source)])
    return out
