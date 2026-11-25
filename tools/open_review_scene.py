"""Open a new native review copy, never replace a user's running document.

new-case: consent-gated DCC review launch in an independent process (#1297).
new-case: `agr open-review FILE` - the `review-scene` skeleton stage (#1740): copy the stage output to
C:/x/review-<job>/<stem>_review_vNNN<suffix> and open the COPY in a NEW 3ds Max 2026 process; Blender 5.1
when Max is busy (the agr-mcp `max-live` lock is held) or not installed [D255, D270].
This launcher does not certify that the application loaded the scene. Inspect
its document/version/units afterwards. No live bridge is called and no lock is
taken, reclaimed or removed: the `max-live` lock is only read (an unreadable or
unexpired body counts as held, agr_mcp.locks rules).
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
SUFFIXES = {'blender': ('.blend', '.fbx'), 'max': ('.max', '.fbx')}
# Which app opens which stage output, in preference order (Max 2026 is Artem's DCC [D270]).
APPS_FOR = {'.max': ('max',), '.blend': ('blender',), '.fbx': ('max', 'blender')}
REVIEW_ROOT = Path('C:/x')
JOB_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
_FBX_HEADERS = (b'Kaydara FBX ', b'; FBX ')


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_header(source: Path) -> None:
    """Reject obvious wrong/partial file types by container signature (not a scene-validity claim)."""
    suffix = source.suffix.lower()
    with source.open('rb') as stream:
        header = stream.read(12)
    if suffix == '.blend':
        # Blender 5.1 saves Zstandard by default; older files may use gzip.
        valid = len(header) == 12 and header.startswith((
            b'BLENDER', bytes.fromhex('28b52ffd'), bytes.fromhex('1f8b08')))
    elif suffix == '.max':
        valid = len(header) == 12 and header.startswith(bytes.fromhex('d0cf11e0a1b11ae1'))
    elif suffix == '.fbx':
        valid = len(header) == 12 and header.startswith(_FBX_HEADERS)
    else:
        raise ValueError(f'Unsupported review file type {suffix or "(none)"!r}: {source}')
    if not valid:
        raise ValueError(f'Invalid/partial native {suffix} header: {source}')


def max_import_script(output: Path) -> Path:
    """Startup MAXScript beside the copy that imports it (`-mxs` quits Max after the string runs)."""
    return output.with_name(output.stem + '.open.ms')


def launch_args(app: str, exe: Path, output: Path) -> list[str]:
    """Command line of a NEW process that opens `output` (the review copy, never the source)."""
    if output.suffix.lower() == '.fbx':
        if app == 'blender':
            # Import, then frame every 3D view once the UI exists (the splash stays; one click closes it).
            expr = ('import bpy\n'
                    'bpy.ops.wm.read_homefile(use_empty=True)\n'
                    f'bpy.ops.import_scene.fbx(filepath={output.as_posix()!r})\n'
                    'def _frame():\n'
                    '    for w in bpy.context.window_manager.windows:\n'
                    '        for a in w.screen.areas:\n'
                    '            if a.type == "VIEW_3D":\n'
                    '                a.spaces.active.clip_end = 100000.0\n'
                    '                r = [x for x in a.regions if x.type == "WINDOW"][0]\n'
                    '                with bpy.context.temp_override(window=w, area=a, region=r):\n'
                    '                    bpy.ops.view3d.view_all()\n'
                    'bpy.app.timers.register(_frame, first_interval=1.0)\n')
            return [str(exe), '--disable-autoexec', '--python-expr', expr]
        return [str(exe), '-U', 'MAXScript', str(max_import_script(output))]
    if app == 'blender':
        return [str(exe), '--disable-autoexec', str(output)]
    return [str(exe), '-sceneFile', str(output)]


def max_busy() -> str | None:
    """Reason when the agr-mcp `max-live` lock is held; read-only (never reclaims a stale lock)."""
    from agr_mcp import locks
    path = locks.lock_path('max-live')
    if not path.exists():
        return None
    info = locks._read_info(path)
    if locks._info_stale(info):
        return None
    holder = (info or {}).get('card') or (info or {}).get('pid') or 'unreadable body'
    return f'max-live lock held ({holder}): {path}'


def job_of(source: Path) -> str:
    """Job id from .../jobs/<ID>/... or .../review-<ID>/...; otherwise --job is required."""
    parts = source.parts
    for i, part in enumerate(parts[:-1]):
        if part.lower() == 'jobs' and i + 2 < len(parts):
            return parts[i + 1]
    if source.parent.name.startswith('review-') and len(source.parent.name) > 7:
        return source.parent.name[7:]
    raise ValueError(f'Cannot derive the job id from {source}; pass --job ID')


def choose_app(suffix: str, requested: str, executables: dict) -> tuple[str, str]:
    """Max 2026 first, Blender when Max is busy or missing [D255]; an explicit app must fit and be free."""
    if suffix not in APPS_FOR:
        raise ValueError(f'Unsupported review file type {suffix or "(none)"!r}')
    candidates = APPS_FOR[suffix]
    if requested != 'auto':
        if requested not in candidates:
            raise ValueError(f'{requested} cannot open {suffix}; use {"/".join(candidates)}')
        candidates = (requested,)
    reasons = []
    for app in candidates:
        if app == 'max':
            busy = max_busy()
            if busy:
                reasons.append(busy)
                continue
        exe = Path(executables[app])
        if not exe.is_file():
            reasons.append(f'{app} executable not found: {exe}')
            continue
        return app, '; '.join(reasons) or f'{app} available'
    raise ValueError(f'No app can open the {suffix} review copy: {"; ".join(reasons)}')


def next_output(folder: Path, source: Path) -> Path:
    """`<stem>_review_vNNN<suffix>` with NNN one above every existing version in the folder."""
    pattern = re.compile(re.escape(source.stem) + r'_review_v(\d{3,})' + re.escape(source.suffix) + '$',
                         re.IGNORECASE)
    names = [p.name for p in folder.iterdir()] if folder.is_dir() else []
    used = [int(m.group(1)) for name in names if (m := pattern.match(name))]
    return folder / f'{source.stem}_review_v{max(used, default=0) + 1:03d}{source.suffix}'


def review(source: Path, *, job: str | None = None, app: str = 'auto', approved: bool,
           root: Path = REVIEW_ROOT, executables: dict | None = None, prepare_only: bool = False) -> dict:
    """`agr open-review`: copy to <root>/review-<job>/ and open the copy in a new process.

    Every refusal happens before anything is written or launched.
    """
    if not prepare_only and approved is not True:
        raise ValueError('Opening requires the task-start yes (--open-approved)')
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ValueError(f'Not a file: {source}')
    job = job_of(source) if job is None else job
    if not JOB_ID.match(job) or job in ('.', '..'):
        raise ValueError(f'Invalid job id {job!r}')
    check_header(source)
    exes = {**EXECUTABLES, **(executables or {})}
    chosen, reason = choose_app(source.suffix.lower(), app, exes)
    folder = Path(root) / f'review-{job}'
    output = next_output(folder, source)
    folder.mkdir(parents=True, exist_ok=True)
    result = open_scene(chosen, source, output, approved=approved, executable=exes[chosen],
                        launch=not prepare_only)
    result.update({'original': str(source), 'job': job, 'app_reason': reason})
    return result


def open_scene(app: str, source: Path, output: Path, *, approved: bool,
               executable: Path | None = None, launch: bool = True) -> dict:
    """Copy exclusively and spawn a new app; raise on refusal/launch failure.

    A failed launch leaves the new copy for inspection/retry under a new version.
    The source must remain unchanged during preparation. Native parsing is left
    to the DCC; the header check rejects obvious wrong/partial file types only.
    """
    if app not in EXECUTABLES:
        raise ValueError(f'Unsupported app: {app}')
    if launch and approved is not True:
        raise ValueError('Opening requires the task-start yes (--open-approved)')
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    suffix = source.suffix.lower()
    if suffix not in SUFFIXES[app] or output.suffix.lower() != suffix:
        raise ValueError(f'{app} requires a {"/".join(SUFFIXES[app])} source and the same output suffix')
    if source == output or output.exists():
        raise ValueError(f'Output must be a new file, not an input/occupied path: {output}')
    script = max_import_script(output) if (app, suffix) == ('max', '.fbx') else None
    if script is not None and (script.exists() or script == source):
        raise ValueError(f'Import script path is occupied: {script}')
    if not re.search(r'(?:^|[_-])v\d{3,}(?:[_-]|$)', output.stem):
        raise ValueError('Output name needs a version token, e.g. review_v002')
    check_header(source)
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
    if script is not None:
        # Exclusive create: a racing writer of the same name fails instead of being clobbered.
        with script.open('x', encoding='utf-8') as stream:
            stream.write(f'-- agr open-review (#1740): import the review copy, never the original\n'
                         f'importFile @"{output}" #noPrompt\n')
    args = launch_args(app, exe, output)
    if not launch:
        return {'status': 'prepared', 'app': app, 'pid': None, 'path': str(output),
                'source_sha256': before, 'command': args, 'acceptance': 'not_measured'}
    # Inherited Qt paths from Hermes/PySide can break standalone DCC startup.
    env = {k: v for k, v in os.environ.items() if k not in {
        'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'QT_PLUGIN_PATH',
        'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_QPA_PLATFORM', 'QT_API'}}
    child = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {'status': 'launched', 'app': app, 'pid': child.pid,
            'path': str(output), 'source_sha256': before, 'command': args,
            'acceptance': 'not_measured'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', type=Path, help='agr open-review: stage output to copy and open')
    parser.add_argument('--job', help='job id for C:/x/review-<job>/ (default: from jobs/<ID>/ or review-<ID>/)')
    parser.add_argument('--app', choices=('auto', *EXECUTABLES), default=None)
    parser.add_argument('--review-root', type=Path, default=REVIEW_ROOT)
    parser.add_argument('--prepare-only', action='store_true', help='make the copy, launch nothing')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--open-approved', action='store_true', help='Task-start yes was received')
    args = parser.parse_args(argv)
    try:
        if args.file is not None:
            if args.source or args.output:
                raise ValueError('Use FILE or --source/--output, not both')
            result = review(args.file, job=args.job, app=args.app or 'auto', approved=args.open_approved,
                            root=args.review_root, prepare_only=args.prepare_only)
        else:
            if args.app in (None, 'auto') or args.source is None or args.output is None:
                raise ValueError('Legacy form needs --app max|blender --source --output (or pass FILE)')
            result = open_scene(args.app, args.source, args.output, approved=args.open_approved,
                                launch=not args.prepare_only)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
