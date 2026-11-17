"""new-case: shared NPM ZIP command using the AGR Tools packaging owner (#1361).

PKG-01/03/13: one flat {code4}_{Address}.zip, only embedded-texture FBX,
Ground + contiguous 01..20 OKS. Missing Ground is never manufactured. Explicit
--allow-incomplete emits a diagnostic ZIP/report, exits 1, and never claims pass.

Export binding (#1637): the planned FBX members are compared with export_meta both ways - every member is
recorded in fbx_records (name + SHA-256) or, for producers without hashes, exported_files (name only, reported
as hash_not_recorded), and every recorded FBX is a member. A foreign, missing or edited FBX, or metadata that
records no exported FBX, is a refusal naming the file. The written ZIP is read back and its FBX bytes are
compared with the hashes checked before writing; a change in between removes this run's ZIP and refuses.
"""
import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.max.agr_tools import package_core
from export_meta import load_package_meta


def _sha256(path):
    value = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def export_binding(pkg, members, meta):
    """Compare planned FBX members with export_meta both ways (#1637) -> (binding, problems naming each file)."""
    if 'fbx_records' in meta:
        source, recorded = 'fbx_records', {n: r['fbx_sha256'] for n, r in meta['fbx_records'].items()}
    elif 'exported_files' in meta:
        source, recorded = 'exported_files', dict.fromkeys(meta['exported_files'])
    else:
        return ({'source': None, 'members': []},
                ['export_meta records no exported FBX (no fbx_records / exported_files): the ZIP cannot be bound '
                 'to the export; re-export with a current exporter or pass --meta'])
    fbx = {m['name']: _sha256(Path(pkg) / m['name']) for m in members if m['name'].lower().endswith('.fbx')}
    rows, problems = [], []
    for name in [m['name'] for m in members if m['name'] in fbx] + sorted(set(recorded) - set(fbx)):
        want, have = recorded.get(name), fbx.get(name)
        if name not in recorded:
            status = 'not_recorded'
            problems.append(f'{name}: FBX in the package is not recorded in export_meta {source} '
                            '(foreign file added after export?)')
        elif name not in fbx:
            status = 'missing'
            problems.append(f'{name}: recorded in export_meta {source} but missing from the package')
        elif want is None:
            status = 'hash_not_recorded'
        elif want != have:
            status = 'hash_mismatch'
            problems.append(f'{name}: SHA-256 {have} differs from export_meta {source} {want} '
                            '(file changed after export)')
        else:
            status = 'match'
        rows.append({'name': name, 'recorded_sha256': want, 'zip_sha256': have, 'status': status})
    return {'source': source, 'members': rows}, problems


def _zip_hashes(target):
    with zipfile.ZipFile(target) as z:
        return {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('package_dir')
    ap.add_argument('--meta', help='explicit export metadata (required when several exporter sidecars exist)')
    ap.add_argument('--allow-incomplete', action='store_true', help='diagnostic archive, exit 1 if composition incomplete')
    a = ap.parse_args(argv)
    pkg = Path(a.package_dir).resolve(strict=True)
    meta = load_package_meta(pkg, a.meta)
    if meta['address'] == 'unknown':
        raise ValueError('export_meta address unknown; provide sourced naming token')
    plan = package_core.zip_plan(str(pkg), address=meta['address'])
    archives = [r for r in plan['archives'] if r['role'] == 'npm']
    if len(archives) != 1:
        raise ValueError('expected exactly one NPM territorial code/address archive')
    archive = archives[0]
    binding, bind_problems = export_binding(pkg, archive['members'], meta)
    problems = list(archive['problems']) + bind_problems
    if problems and not a.allow_incomplete:
        raise ValueError('; '.join(problems) + '; --allow-incomplete is diagnostic only')
    target = pkg.parent / archive['name']
    report_path = pkg.parent / 'package_report.json'
    for path in (target, report_path, Path(str(target) + '.partial')):
        if os.path.lexists(path):
            raise FileExistsError(f'output {path} already exists; choose a new version')
    result, size = package_core._write_zip(str(pkg), archive, str(target))
    if result is None:
        raise ValueError(f'NPM archive exceeds {archive["limit"]} bytes')
    zipped = _zip_hashes(target)
    changed = sorted(r['name'] for r in binding['members']
                     if r['zip_sha256'] is not None and zipped.get(r['name']) != r['zip_sha256'])
    if changed:
        os.remove(target)  # this run's own output, created above; never an input
        raise ValueError(f'{", ".join(changed)}: FBX bytes changed between the export_meta check and the ZIP; '
                         'nothing written')
    report = {'zip': str(target), 'zip_bytes': size, 'files': [r['name'] for r in archive['members']],
              'problems': problems, 'export_binding': binding, 'skipped': plan['skipped'], 'passed': False,
              'status': 'incomplete' if problems else 'packaged_not_validated'}
    with open(report_path, 'x', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(f'refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
