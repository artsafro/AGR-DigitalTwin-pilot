"""KPP1 #1609 package step: derivation record of the accepted #1416 Ground copy, per part role [D328, D333].

Pattern: n/a | new-case: re-records, at package time, the export record derive_ground_v003.py (#1416) writes but the
#1416 Drive evidence does not keep: the Ground FBX (bytes unchanged) was derived from the #1416 v002 Ground copy
(REPORT #1416 round 4 command). One dependency per part role (ground / groundel / flora by
build_manifest.role_of), source_id `KPP1.<role>.geometry`; the customer / bridge inputs of #1416 are not re-attested
here (their files are outside this run), so the record names only the geometry source it was derived from.

    uv run python jobs/KPP1/lattice-1609/record_ground.py GROUND_FBX GROUND_MASTER STORE_DIR PARTS_CSV
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402


def main(fbx, master, store, parts_csv):
    parts = [p for p in parts_csv.split(',') if p]
    if not parts:
        raise SystemExit('no parts named')
    sha = bm.sha256_file(master)
    roles = {}
    for name in parts:
        roles.setdefault(bm.role_of(name), []).append(name)
    deps = [{'role': role, 'master': os.path.abspath(master), 'master_sha256': sha, 'parts': sorted(names),
             'source_id': f'KPP1.{role}.geometry'} for role, names in sorted(roles.items())]
    rec = bm.write_export_derivation([fbx], master, store, bm.git_commit(str(ROOT)), master_sha256=sha,
                                     role='ground', dependencies=deps, source_id='KPP1.ground.geometry')
    print('RECORD', rec if isinstance(rec, str) else 'written', sorted(roles))


if __name__ == '__main__':
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
