"""new-case: `agr build-manifest` CLI over adapters/max/agr_tools/build_manifest.py (#1423 delivery set consistency).

    agr build-manifest record ARTIFACT [ARTIFACT ...] --master MASTER --out NEW.derivation.json [--builder-commit SHA]
        Right after an export: which master revision (file SHA-256) these exported files were derived from.
    agr build-manifest build PACKAGE.zip --master MASTER --derivation REC.json [REC.json ...]
        --transform-name NAME [--transform-file FILE] [--builder-commit SHA] [--no-readback] [--blender EXE]
        The FBX export owner readback (dimensions, part positions, materials, UV, UCX-to-visual binding) runs on the
        FBX members of the ZIP (the exact bytes that are delivered) and writes `<stem>.readback.json`; then
        `<stem>.build.json` is written beside the ZIP. Both are new files (never overwritten, never an input).
        --no-readback writes a manifest without the required check: the validator refuses it (not ready).
        --derivation also takes an exporter's record store `<export root>/derivation/` (#1505: export_npm and the
        KPP1 export_vpm write their records there automatically); every `*.derivation.json` in it is read.

Exit: 0 written (status in the JSON line; `agr validate PACKAGE.zip` gives the verdict), 2 refused, nothing written.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402


def git_commit():
    return bm.git_commit(ROOT)


def blender_readback(path, blender=None):
    from twinqa.scene import readback
    return readback(Path(path), blender=blender)


def run_readback(package_zip, reader):
    """Export owner readback of every FBX member, on the zipped bytes themselves (extracted to a temp folder)."""
    summaries = []
    with zipfile.ZipFile(package_zip) as z, tempfile.TemporaryDirectory() as tmp:
        for info in z.infolist():
            if not info.filename.lower().endswith('.fbx'):
                continue
            data = z.read(info)
            path = os.path.join(tmp, os.path.basename(info.filename))
            with open(path, 'xb') as fh:
                fh.write(data)
            try:
                rb = reader(path)
            except Exception as exc:  # any readback failure is a failed check, never a skipped one
                rb = {'readback_ok': False, 'error': str(exc)[:500], 'meshes': []}
            summaries.append(bm.readback_summary(info.filename, bm.sha256_bytes(data), rb))
    return bm.readback_report(package_zip, summaries)


def cmd_record(a):
    rec = bm.derivation_record(a.artifacts, a.master, a.builder_commit or git_commit())
    inputs = list(a.artifacts) + [a.master]
    bm.write_new(a.out, bm.dumps(rec), inputs)
    print(json.dumps({'derivation': os.path.abspath(a.out), 'master_sha256': rec['master_sha256'],
                      'artifacts': sorted(rec['artifacts'])}, ensure_ascii=False))
    return 0


def cmd_build(a, reader=None):
    package = os.path.abspath(a.package)
    if not os.path.isfile(package):
        raise ValueError('no package ' + package)
    out_manifest, out_readback = bm.manifest_path(package), bm.readback_path(package)
    a.derivation = bm.derivation_files(a.derivation)  # a store folder (#1505) -> its *.derivation.json records
    inputs = [package, a.master] + list(a.derivation) + ([a.transform_file] if a.transform_file else [])
    taken = {os.path.normcase(os.path.realpath(p)) for p in inputs}
    for p in (out_manifest, out_readback, out_manifest + '.partial', out_readback + '.partial'):
        if os.path.normcase(os.path.realpath(p)) in taken:
            raise ValueError('output {} is an input'.format(p))
        if os.path.lexists(p):
            raise FileExistsError('refusing to overwrite: ' + p)
    derivations = []
    for p in a.derivation:
        with open(p, 'rb') as fh:
            derivations.append(bm.strict_json(fh.read()))
    transform = bm.transform_entry(a.transform_name, a.transform_file)
    commit = a.builder_commit or git_commit()
    readback = None
    if not a.no_readback:
        readback = run_readback(package, reader or (lambda p: blender_readback(p, a.blender)))
    # every refusal of make_manifest happens before the first write
    manifest = bm.make_manifest(package, a.master, commit, derivations, transform, readback, None)
    if readback is not None:
        bm.write_new(out_readback, bm.dumps(readback), inputs)
        manifest = bm.make_manifest(package, a.master, commit, derivations, transform, readback, out_readback,
                                    build_id=manifest['build_id'], now=manifest['created_utc'])
    bm.write_new(out_manifest, bm.dumps(manifest), inputs)
    stale = sorted({x['master_sha256'] for x in manifest['artifacts']} - {manifest['master']['sha256']})
    print(json.dumps({'manifest': out_manifest, 'readback': out_readback if readback else None,
                      'build_id': manifest['build_id'], 'master_sha256': manifest['master']['sha256'],
                      'readback_status': readback['status'] if readback else 'not_run',
                      'artifacts_from_other_masters': stale}, ensure_ascii=False))
    return 0


def parser():
    ap = argparse.ArgumentParser(prog='agr build-manifest', description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record', help='derivation record of exported files (export time)')
    r.add_argument('artifacts', nargs='+')
    r.add_argument('--master', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--builder-commit')
    b = sub.add_parser('build', help='export owner readback + <stem>.build.json beside the ZIP')
    b.add_argument('package')
    b.add_argument('--master', required=True)
    b.add_argument('--derivation', nargs='+', required=True)
    b.add_argument('--transform-name', required=True)
    b.add_argument('--transform-file')
    b.add_argument('--builder-commit')
    b.add_argument('--no-readback', action='store_true')
    b.add_argument('--blender')
    return ap


def main(argv=None, reader=None):
    a = parser().parse_args(argv)
    try:
        return cmd_record(a) if a.cmd == 'record' else cmd_build(a, reader)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        print('refused: {}'.format(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
