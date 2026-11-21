"""Open a new native review copy, never replace a user's running document.

new-case: consent-gated DCC review launch in an independent process (#1297).
This launcher does not certify that the application loaded the scene. Inspect
its document/version/units afterwards. No live bridge or shared lock is touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

EXECUTABLES = {
    'blender': Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'),
    'max': Path('C:/Program Files/Autodesk/3ds Max 2026/3dsmax.exe'),
}
SUFFIXES = {'blender': '.blend', 'max': '.max'}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def open_scene(app: str, source: Path, output: Path, *, approved: bool,
               executable: Path | None = None) -> dict:
    """Copy exclusively and spawn a new app; raise on refusal/launch failure.

    A failed launch leaves the new copy for inspection/retry under a new version.
    The source must remain unchanged during preparation. Native parsing is left
    to the DCC; the header check rejects obvious wrong/partial file types only.
    """
    if app not in EXECUTABLES:
        raise ValueError(f'Unsupported app: {app}')
    if approved is not True:
        raise ValueError('Opening requires the task-start yes (--open-approved)')
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    suffix = SUFFIXES[app]
    if source.suffix.lower() != suffix or output.suffix.lower() != suffix:
        raise ValueError(f'{app} requires native {suffix} source and output')
    if source == output or output.exists():
        raise ValueError(f'Output must be a new file, not an input/occupied path: {output}')
    if not re.search(r'(?:^|[_-])v\d{3,}(?:[_-]|$)', output.stem):
        raise ValueError('Output name needs a version token, e.g. review_v002')
    with source.open('rb') as stream:
        header = stream.read(12)
    if app == 'blender':
        # Blender 5.1 saves Zstandard by default; older files may use gzip.
        # These are container signatures, not a claim of valid scene contents.
        valid = len(header) == 12 and header.startswith((
            b'BLENDER', bytes.fromhex('28b52ffd'), bytes.fromhex('1f8b08')))
    else:
        valid = len(header) == 12 and header.startswith(bytes.fromhex('d0cf11e0a1b11ae1'))
    if not valid:
        raise ValueError(f'Invalid/partial native {suffix} header: {source}')
    exe = Path(executable or EXECUTABLES[app]).resolve(strict=True)
    if not exe.is_file():
        raise ValueError(f'Executable is not a file: {exe}')
    before = digest(source)
    # Private staging prevents predictable .partial names from clobbering inputs.
    # Hard-link publication is atomic no-replace, including races after preflight.
    with tempfile.TemporaryDirectory(prefix='agr-review-') as staging:
        staged = Path(staging) / ('review' + suffix)
        shutil.copyfile(source, staged)
        if digest(staged) != before or digest(source) != before:
            raise ValueError('Source changed during review-copy preparation')
        # Cross-volume copies need staging beside the destination for os.link.
        # Use an exclusively created random sibling directory, never a fixed name.
        with tempfile.TemporaryDirectory(prefix='.agr-review-', dir=output.parent) as sibling:
            ready = Path(sibling) / staged.name
            shutil.copyfile(staged, ready)
            if digest(ready) != before:
                raise ValueError('Review copy checksum mismatch')
            os.link(ready, output)
    args = [str(exe)]
    if app == 'blender':
        args += ['--disable-autoexec', str(output)]
    else:
        args += ['-sceneFile', str(output)]
    # Inherited Qt paths from Hermes/PySide can break standalone DCC startup.
    env = {k: v for k, v in os.environ.items() if k not in {
        'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'QT_PLUGIN_PATH',
        'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_QPA_PLATFORM', 'QT_API'}}
    child = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {'status': 'launched', 'app': app, 'pid': child.pid,
            'path': str(output), 'source_sha256': before, 'command': args,
            'acceptance': 'not_measured'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', choices=tuple(EXECUTABLES), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--open-approved', action='store_true', help='Task-start yes was received')
    args = parser.parse_args()
    try:
        result = open_scene(args.app, args.source, args.output, approved=args.open_approved)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
