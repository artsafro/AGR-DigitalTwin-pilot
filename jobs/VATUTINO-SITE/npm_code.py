"""Rename the NPM site ZIP to the territorial code SINTEZ issues [D235]; one command, then validate.

new-case: job-local; the code is a single parameter. The placeholder `0000` marks a package built before SINTEZ
issued the code (Artem 2026-11-09: the code comes from the SINTEZ upload, like the FNO in [D220]).

  uv run python jobs/VATUTINO-SITE/npm_code.py <src.zip> <code4> <out_dir> [--address Vatutino] [--scene]

Writes <out_dir>/<code4>_<Address>.zip with every inner `<old stem>_*.fbx` renamed to `<code4>_<Address>_*.fbx`
(bytes unchanged) and a .zip.delivery.json receipt tying both ZIPs by SHA-256 [D347].
Then runs tools/qa/validate_package.py --profile npm --json and returns its verdict (0/1/2).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools.package_core import (
    ADDRESS, LIMITS, _write_zip, check_delivery_receipt, check_members, delivery_receipt, validator_argv,
)

PLACEHOLDER = '0000'


def rename_npm_zip(src, code, out_dir, address='Vatutino'):
    if not re.fullmatch(r'[0-9]{4}', code):
        raise ValueError(f'territorial code must be 4 digits, got {code!r}')
    if not re.fullmatch(ADDRESS, address):
        raise ValueError(f'invalid NPM address: {address!r}')
    src, out_dir = Path(src), Path(out_dir)
    old = src.stem
    new = f'{code}_{address}'
    dest = out_dir / f'{new}.zip'
    sidecar = dest.with_suffix('.zip.delivery.json')
    for path in (dest, sidecar):
        if os.path.lexists(path):
            raise FileExistsError(f'refusing existing output {path}')
    if src.suffix.lower() != '.zip':
        raise ValueError(f'expected a source ZIP: {src}')
    source_path = src.resolve(strict=True)
    source = delivery_receipt(src)['delivered']
    out_dir.mkdir(parents=True, exist_ok=True)
    names = {}
    with tempfile.TemporaryDirectory(prefix='.rename-', dir=out_dir) as staging:
        staged_zip = Path(staging) / dest.name
        staged_receipt = Path(staging) / sidecar.name
        member_dir = Path(staging) / 'members'
        member_dir.mkdir()
        with zipfile.ZipFile(src) as zin:
            for name in zin.namelist():
                if ('/' in name or '\\' in name or not name.lower().endswith('.fbx')
                        or not name.startswith(old + '_')):
                    raise ValueError(f'unexpected NPM ZIP entry {name!r} (expected {old}_*.fbx in the root)')
                if name in names:
                    raise ValueError(f'duplicate NPM ZIP entry {name!r}')
                names[name] = new + name[len(old):]
            if not names:
                raise ValueError(f'empty NPM ZIP: {src}')
            plan = {'name': dest.name, 'limit': LIMITS['npm'], 'members': [{'name': n} for n in names.values()]}
            check_members(plan)
            for name, renamed in names.items():
                with (member_dir / renamed).open('xb') as stream:
                    stream.write(zin.read(name))
        packed, size = _write_zip(member_dir, plan, str(staged_zip))
        if packed is None:
            raise ValueError(f'{dest.name}: {size} bytes exceeds the NPM ZIP limit')
        check_delivery_receipt(src, source)
        if src.resolve(strict=True) != source_path:
            raise ValueError(f'source ZIP path changed: {src}')
        receipt = delivery_receipt(staged_zip)
        receipt['source'] = {'path': str(source_path), 'sha256': source['sha256']}
        with staged_receipt.open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        # Same-volume hard links expose complete files without overwriting. Publish the ZIP last.
        os.link(staged_receipt, sidecar)
        try:
            os.link(staged_zip, dest)
        except OSError:
            if os.path.lexists(sidecar) and staged_receipt.samefile(sidecar):
                sidecar.unlink()
            raise
    return dest, names, receipt['delivered']['sha256']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('code')
    ap.add_argument('out_dir')
    ap.add_argument('--address', default='Vatutino')
    ap.add_argument('--scene', action='store_true')
    a = ap.parse_args()
    report = Path(a.out_dir) / f'validate-{a.code}_{a.address}{"-scene" if a.scene else ""}.json'
    if os.path.lexists(report):
        ap.error(f'refusing existing output {report}')
    dest, names, sha = rename_npm_zip(a.src, a.code, a.out_dir, a.address)
    print(f'{dest} sha256 {sha} {names}', flush=True)
    cmd = validator_argv(sys.executable, ROOT, dest, profile='npm', scene=a.scene)
    r = subprocess.run(cmd, capture_output=True, encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if r.stdout:
        with report.open('x', encoding='utf-8') as stream:
            stream.write(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr, end='')
    print('validate_package exit', r.returncode)
    return r.returncode


if __name__ == '__main__':
    raise SystemExit(main())
