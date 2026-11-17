"""new-case: shared NPM ZIP command using the AGR Tools packaging owner (#1361).

PKG-01/03/13: one flat {code4}_{Address}.zip, only embedded-texture FBX,
Ground + contiguous 01..20 OKS. Missing Ground is never manufactured. Explicit
--allow-incomplete emits a diagnostic ZIP/report, exits 1, and never claims pass.

Export binding (#1637, #1650) is shared with AGR Tools in export_meta.py.
The writer checks bound member bytes before publishing the final ZIP name.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.max.agr_tools import package_core
from adapters.max.agr_tools.export_meta import address_meta_path, export_binding, export_records, load_meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('package_dir')
    ap.add_argument('--meta', help='explicit export metadata (required when several exporter sidecars exist)')
    ap.add_argument('--allow-incomplete', action='store_true', help='diagnostic archive, exit 1 if composition incomplete')
    a = ap.parse_args(argv)
    pkg = Path(a.package_dir).resolve(strict=True)
    meta_path = address_meta_path(pkg, a.meta)
    meta = load_meta(meta_path)
    if meta['address'] == 'unknown':
        raise ValueError('export_meta address unknown; provide sourced naming token')
    plan = package_core.zip_plan(str(pkg), address=meta['address'])
    archives = [r for r in plan['archives'] if r['role'] == 'npm']
    if len(archives) != 1:
        raise ValueError('expected exactly one NPM territorial code/address archive')
    archive = archives[0]
    binding, bind_problems = export_binding(pkg, archive['members'], export_records(pkg, meta_path))
    problems = list(archive['problems']) + bind_problems
    if problems and not a.allow_incomplete:
        raise ValueError('; '.join(problems) + '; --allow-incomplete is diagnostic only')
    target = pkg.parent / archive['name']
    report_path = pkg.parent / 'package_report.json'
    for path in (target, report_path, Path(str(target) + '.partial')):
        if os.path.lexists(path):
            raise FileExistsError(f'output {path} already exists; choose a new version')
    # Diagnostic mode preserves its measured mismatches, but still binds the snapshot
    # actually checked above: a later change must not be published even diagnostically.
    expected = {r['name']: r['zip_sha256'] for r in binding['members'] if r['zip_sha256'] is not None}
    result, size = package_core._write_zip(str(pkg), archive, str(target), expected_sha256=expected)
    if result is None:
        raise ValueError(f'NPM archive exceeds {archive["limit"]} bytes')
    report = {'zip': str(target), 'zip_bytes': size, 'files': [r['name'] for r in archive['members']],
              'problems': problems, 'export_binding': binding, 'skipped': plan['skipped'], 'passed': False,
              'status': 'incomplete' if problems else 'packaged_not_validated'}
    report.update(package_core.delivery_receipt(target))
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
