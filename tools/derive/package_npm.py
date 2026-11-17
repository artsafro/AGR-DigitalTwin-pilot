"""new-case: shared NPM ZIP command using the AGR Tools packaging owner (#1361).

PKG-01/03/13: one flat {code4}_{Address}.zip, only embedded-texture FBX,
Ground + contiguous 01..20 OKS. Missing Ground is never manufactured. Explicit
--allow-incomplete emits a diagnostic ZIP/report, exits 1, and never claims pass.

Export binding (#1637): the planned FBX members are compared both ways with the export records in the package -
the union of the address record (--meta, export_meta.json, or the one OKS sidecar) and every
<fbx>.export_meta.json sidecar, because OKS and Ground come from different exporters and each records only its own
FBX. Every member must be recorded with a SHA-256 (fbx_records or exported_sha256, written by record_export) equal
to its bytes, and every recorded FBX must be a member. A foreign, missing, edited or hash-less FBX, one FBX
recorded twice with different hashes, or records that name no FBX, is a refusal naming the file. The written ZIP
is read back and its FBX bytes are compared with the hashes checked before writing; a change in between removes
this run's ZIP and refuses.
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
from export_meta import load_meta


def _sha256(path):
    value = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def _sidecars(pkg):
    return sorted(p for p in Path(pkg).glob('*.fbx.export_meta.json')
                  if not p.name.endswith('_Light.fbx.export_meta.json'))


def address_meta_path(pkg, explicit=None):
    """load_package_meta's order (--meta, export_meta.json, the single sidecar, parent). A Ground route sidecar
    records only its own FBX, so among several sidecars the single non-Ground (OKS) one names the package (#1637);
    two or more OKS sidecars stay ambiguous - never the first entry."""
    pkg = Path(pkg)
    if explicit is not None:
        return Path(explicit)
    if os.path.lexists(pkg / 'export_meta.json'):
        return pkg / 'export_meta.json'
    side = _sidecars(pkg)
    oks = [p for p in side if not p.name.endswith('_Ground.fbx.export_meta.json')]
    if len(side) == 1:
        return side[0]
    if len(oks) == 1:
        return oks[0]
    if side:
        raise ValueError(f'ambiguous export metadata {side}; choose --meta explicitly')
    return pkg.parent / 'export_meta.json'


def export_records(pkg, address_path):
    """(label, meta) of the address record plus every FBX sidecar in the package, each validated, no duplicates."""
    out, seen = [], set()
    for path in [Path(address_path)] + _sidecars(pkg):
        key = os.path.normcase(os.path.realpath(path))
        if key in seen:
            continue
        seen.add(key)
        label = path.name if path.parent.resolve() == Path(pkg).resolve() else str(path)
        out.append((label, load_meta(path)))
    return out


def export_binding(pkg, members, records):
    """Compare planned FBX members with the union of export records both ways (#1637) -> (binding, problems)."""
    claims = {}  # FBX name -> {(label, recorded sha or None)}
    for label, meta in records:
        hashes = {}
        for name, rec in meta.get('fbx_records', {}).items():
            hashes.setdefault(name, set()).add(rec['fbx_sha256'])
        for name, sha in meta.get('exported_sha256', {}).items():
            hashes.setdefault(name, set()).add(sha)
        for name in meta.get('exported_files', []):
            hashes.setdefault(name, set())
        for name, values in hashes.items():
            for sha in values or {None}:
                claims.setdefault(name, set()).add((label, sha))
    labels = [label for label, _ in records]
    if not claims:
        return ({'records': labels, 'members': []},
                [f'export_meta records no exported FBX (no fbx_records / exported_files in {labels}): the ZIP cannot '
                 'be bound to the export; re-export with a current exporter or pass --meta'])
    fbx = {m['name']: _sha256(Path(pkg) / m['name']) for m in members if m['name'].lower().endswith('.fbx')}
    rows, problems = [], []
    for name in [m['name'] for m in members if m['name'] in fbx] + sorted(set(claims) - set(fbx)):
        have = fbx.get(name)
        recorded_in = sorted({label for label, _ in claims.get(name, ())})
        wants = {sha for _, sha in claims.get(name, ())}
        want = next(iter(wants)) if len(wants) == 1 else None
        if name not in claims:
            status = 'not_recorded'
            problems.append(f'{name}: FBX in the package is not recorded in any export record {labels} '
                            '(foreign file added after export?)')
        elif len(wants) > 1:
            status = 'recorded_conflict'
            problems.append(f'{name}: recorded twice with different SHA-256 {sorted(claims[name], key=str)}')
        elif name not in fbx:
            status = 'missing'
            problems.append(f'{name}: recorded in {recorded_in} but missing from the package')
        elif want is None:
            status = 'hash_not_recorded'
            problems.append(f'{name}: recorded in {recorded_in} with no recorded SHA-256; re-export so '
                            'record_export stores exported_sha256')
        elif want != have:
            status = 'hash_mismatch'
            problems.append(f'{name}: SHA-256 {have} differs from {recorded_in} {want} (file changed after export)')
        else:
            status = 'match'
        rows.append({'name': name, 'recorded_sha256': want, 'zip_sha256': have, 'status': status,
                     'recorded_in': recorded_in})
    return {'records': labels, 'members': rows}, problems


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
