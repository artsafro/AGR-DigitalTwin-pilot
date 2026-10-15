"""Single isolated headless Blender boundary (default installation: Blender 5.1.2).

Explicit executable > TWINQA_BLENDER > pinned installation; never search PATH or
silently select a newer install. Logs survive temporary report/config cleanup.
Scripts without a JSON protocol must declare their native output artifacts.
The CLI lets RunRecord retain its locking, signatures and evidence verification.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

BLENDER_VERSION = '5.1.2'
DEFAULT_BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'


def blender_executable(executable=None) -> str:
    return str(executable or os.environ.get('TWINQA_BLENDER') or DEFAULT_BLENDER)


class BlenderRunError(RuntimeError):
    """Every launch/process/evidence failure carries the same serializable envelope."""
    def __init__(self, envelope):
        self.envelope = envelope
        super().__init__(json.dumps(envelope, ensure_ascii=False))


def _text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def _write_signature(stat):
    # Reads can change atime (and metadata operations can change ctime) without
    # producing evidence. Only replacement, size or mtime indicate a new write.
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def run_blender(script, args=(), *, executable=None, output_json=None, outputs=(),
                timeout=900, log_path=None, cwd=None):
    """Return parsed fresh JSON (or None for native-only output protocols).

    No existing output is removed. Unchanged pre-existing files, timestamps older
    than launch, empty files and malformed JSON cannot count as current evidence.
    """
    command = [blender_executable(executable), '--background', '--factory-startup',
               '--disable-autoexec', '--python-exit-code', '1', '--python', str(script),
               '--', *map(str, args)]
    log = Path(log_path or Path.cwd() / 'logs' / 'blender' / (uuid.uuid4().hex + '.log')).resolve()
    code = None
    def fail(kind, message, cause=None):
        error = BlenderRunError(dict(code=kind, message=message, command=command,
                                     log=str(log), returncode=code, timeout=timeout))
        raise error from cause
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('Command: ' + json.dumps(command) + '\n', encoding='utf-8')
        if timeout is None or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be a finite positive number of seconds')
        # Relative artifact paths belong to the child's working directory, just
        # like script arguments; the parent's cwd may be entirely different.
        base = Path(cwd).resolve() if cwd is not None else Path.cwd()
        paths = [(base / p).resolve() for p in outputs]
        report = (base / output_json).resolve() if output_json is not None else None
        if report is not None:
            paths.insert(0, report)
        if not paths:
            raise ValueError('Declare output_json or native outputs')
        with tempfile.TemporaryDirectory(prefix='config-', dir=log.parent) as config:
            env = os.environ.copy()
            for key in ('BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_DATAFILES'):
                directory = Path(config) / key.lower()
                directory.mkdir()
                env[key] = str(directory)
            # Snapshot only after setup, immediately before launch: evidence
            # created during setup is not a result of this Blender process.
            before = {p: p.stat() if p.exists() else None for p in paths}
            # Use the same filesystem clock as the evidence, not wall-clock
            # precision. Keep this marker separate from the persistent log.
            marker = Path(config) / 'launch-marker'
            marker.write_bytes(b'launch')
            started = marker.stat().st_mtime_ns
            try:
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                        errors='replace', timeout=timeout, env=env, cwd=cwd)
            except subprocess.TimeoutExpired as exc:
                with log.open('a', encoding='utf-8') as stream:
                    stream.write(_text(exc.stdout) + _text(exc.stderr))
                fail('timeout', f'Blender timed out after {timeout} seconds', exc)
            code = result.returncode
            stdout, stderr = _text(result.stdout), _text(result.stderr)
            with log.open('a', encoding='utf-8') as stream:
                stream.write(stdout + stderr)
            if code:
                fail('nonzero_exit', f'Blender exit {code}: {(stderr or stdout)[-400:]}')
            for path in paths:
                kind = 'json' if path == report else 'output'
                if not path.is_file():
                    fail('missing_' + kind, f'Blender produced no report/output: {path}')
                stat = path.stat()
                if stat.st_mtime_ns < started or (before[path] is not None and
                        _write_signature(stat) == _write_signature(before[path])):
                    fail('stale_' + kind, f'Blender left stale evidence: {path}')
                if stat.st_size == 0:
                    fail('invalid_' + kind, f'Blender left empty evidence: {path}')
            if report is not None:
                try:
                    return json.loads(report.read_text(encoding='utf-8'))
                except (ValueError, UnicodeError) as exc:
                    fail('invalid_json', f'Blender left invalid JSON: {report}', exc)
    except BlenderRunError:
        raise
    except Exception as exc:
        # Also normalize launch, filesystem, config and decoding failures.
        try:
            with log.open('a', encoding='utf-8') as stream:
                stream.write(f'\n{type(exc).__name__}: {exc}\n')
        except OSError:
            pass  # The envelope still names the requested log if the disk is unavailable.
        fail('exception', f'{type(exc).__name__}: {exc}', exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable')
    parser.add_argument('--script', required=True)
    parser.add_argument('--output-json', required=True)
    parser.add_argument('--log', required=True)
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('args', nargs=argparse.REMAINDER)
    options = parser.parse_args(argv)
    try:
        run_blender(options.script, options.args[1:] if options.args[:1] == ['--'] else options.args,
                    executable=options.executable, output_json=options.output_json,
                    log_path=options.log, timeout=options.timeout)
    except BlenderRunError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
