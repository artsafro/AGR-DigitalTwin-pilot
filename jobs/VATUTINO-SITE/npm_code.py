"""Rename the NPM site ZIP to the territorial code SINTEZ issues [D231]; one command, then validate.

new-case: job-local; the code is a single parameter. The placeholder `0000` marks a package built before SINTEZ
issued the code (Artem 2026-11-09: the code comes from the SINTEZ upload, like the FNO in [D220]).

  uv run python jobs/VATUTINO-SITE/npm_code.py <src.zip> <code4> <out_dir> [--address Vatutino] [--scene]

Writes <out_dir>/<code4>_<Address>.zip with every inner `<old stem>_*.fbx` renamed to `<code4>_<Address>_*.fbx`
(bytes unchanged), then runs tools/qa/validate_package.py --profile npm --json (exit 0/1/2 are verdicts).
"""
import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = '0000'


def rename_npm_zip(src, code, out_dir, address='Vatutino'):
    if not re.fullmatch(r'\d{4}', code):
        raise ValueError(f'territorial code must be 4 digits, got {code!r}')
    src, out_dir = Path(src), Path(out_dir)
    old = src.stem
    new = f'{code}_{address}'
    dest = out_dir / f'{new}.zip'
    if dest.exists():
        raise FileExistsError(f'refusing existing output {dest}')
    out_dir.mkdir(parents=True, exist_ok=True)
    names = {}
    with zipfile.ZipFile(src) as zin:
        for info in zin.infolist():
            name = info.filename
            if '/' in name or not name.lower().endswith('.fbx') or not name.startswith(old + '_'):
                raise ValueError(f'unexpected NPM ZIP entry {name!r} (expected {old}_*.fbx in the root)')
            names[name] = new + name[len(old):]
        with zipfile.ZipFile(dest, 'x', zipfile.ZIP_DEFLATED) as zout:
            for name, renamed in names.items():
                zout.writestr(renamed, zin.read(name))
    return dest, names, hashlib.sha256(dest.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('code')
    ap.add_argument('out_dir')
    ap.add_argument('--address', default='Vatutino')
    ap.add_argument('--scene', action='store_true')
    a = ap.parse_args()
    dest, names, sha = rename_npm_zip(a.src, a.code, a.out_dir, a.address)
    print(f'{dest} sha256 {sha} {names}', flush=True)
    cmd = [sys.executable, str(ROOT / 'tools/qa/validate_package.py'), str(dest), '--profile', 'npm', '--json']
    if a.scene:
        cmd.append('--scene')
    r = subprocess.run(cmd, capture_output=True, text=True)
    (dest.parent / f'validate-{dest.stem}{"-scene" if a.scene else ""}.json').write_text(r.stdout, encoding='utf-8')
    print('validate_package exit', r.returncode)
    return 0 if r.returncode in (0, 1, 2) else r.returncode


if __name__ == '__main__':
    raise SystemExit(main())
