"""One isolated headless Blender process, with durable logs and fresh evidence.

The default installation is Blender 5.1.2 (5.1 installation directory). Explicit
executables and TWINQA_BLENDER override it; PATH/newest-install discovery is avoided.
The runner certifies process/evidence production, not delivery acceptance.
"""
import json
import os
from pathlib import Path
import subprocess

DEFAULT_BLENDER = 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'


def executable(override=None):
    return str(override or os.environ.get('TWINQA_BLENDER') or DEFAULT_BLENDER)


def find_blender():
    candidate = executable()
    return candidate if Path(candidate).is_file() else None


class BlenderError(RuntimeError):
    """Stable error envelope shared by every entry point."""

    def __init__(self, code, message, command, log, timeout, returncode=None):
        self.envelope = dict(code=code, message=message, command=command,
                             log=str(log), timeout=timeout, returncode=returncode)
        super().__init__(json.dumps(self.envelope, ensure_ascii=False))


def _stamp(path):
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns


def run_blender(script, args=(), *, outputs, log, blender=None, timeout=600,
                execute=None):
    """Return parsed JSON outputs, rejecting missing/stale/invalid evidence.

    Non-JSON outputs (e.g. FBX exports) receive the same freshness checks.
    ``execute`` can bind execution to a RunRecord ledger; it must return a
    CompletedProcess and honor the supplied timeout. No retry is performed.
    """
    command = [executable(blender), '--background', '--factory-startup',
               '--disable-autoexec', '--python-exit-code', '1', '--python',
               str(script), '--', *map(str, args)]
    log = Path(log)
    paths = [Path(p) for p in outputs]
    code, returncode = 'exception', None
    stdout = stderr = ''
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        before = {p: _stamp(p) if p.exists() else None for p in paths}
        # Compare timestamps from the same filesystem, not the wall clock:
        # Windows file timestamps can lag time.time_ns() for immediate writes.
        log.write_text('', encoding='utf-8')
        started = log.stat().st_mtime_ns
        proc = (execute or subprocess.run)(command, capture_output=True, text=True,
                                          encoding='utf-8', errors='replace', timeout=timeout)
        stdout, stderr = proc.stdout or '', proc.stderr or ''
        returncode = proc.returncode
        if returncode:
            code = 'nonzero_exit'
            raise ValueError(f'Blender exit {returncode}: {stderr[-400:]}')
        result = {}
        for path in paths:
            if not path.is_file() or not path.stat().st_size:
                code = 'missing_output'
                raise ValueError(f'Blender produced no report/output: {path}')
            if _stamp(path) == before[path] or path.stat().st_mtime_ns < started:
                code = 'stale_output'
                raise ValueError(f'Stale Blender output: {path}')
            code = 'invalid_json'
            if path.suffix.lower() == '.json':
                result[path] = json.loads(path.read_text(encoding='utf-8'))
        log.write_text(stdout + stderr, encoding='utf-8')
        return result
    except Exception as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            code = 'timeout'
            stdout, stderr = exc.stdout or '', exc.stderr or ''
        def text(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
        try:
            log.write_text(text(stdout) + text(stderr) + '\n' + str(exc), encoding='utf-8')
        except OSError:
            pass
        raise BlenderError(code, str(exc), command, log, timeout, returncode) from exc
