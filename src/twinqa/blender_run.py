"""One headless Blender runner so every call site uses the same flags.

docs/domain/export-import.md: ``--background --factory-startup --disable-autoexec
--python-exit-code 1``. ``--disable-autoexec`` blocks scripts embedded in .blend
files; ``--python-exit-code 1`` turns a Python exception in the script into a
nonzero exit.
"""
import subprocess
from pathlib import Path

HEADLESS_FLAGS = ("--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1")


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _write_logs(log_dir, script, stdout, stderr) -> None:
    if log_dir is None:
        return
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(script).stem
    (directory / f"{stem}.stdout.log").write_text(_as_text(stdout), encoding="utf-8")
    (directory / f"{stem}.stderr.log").write_text(_as_text(stderr), encoding="utf-8")


def run_blender_script(script, args, *, timeout, blender=None, log_dir=None, tail_chars=400) -> subprocess.CompletedProcess:
    if blender is None:
        from twinqa.scene import find_blender
        blender = find_blender()
    if not blender:
        raise FileNotFoundError("Blender not found (set TWINQA_BLENDER)")
    cmd = [blender, *HEADLESS_FLAGS, "--python", str(script), "--", *map(str, args)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _write_logs(log_dir, script, exc.stdout, exc.stderr)
        raise RuntimeError(f"{Path(script).name} timed out after {timeout} seconds") from exc
    _write_logs(log_dir, script, proc.stdout, proc.stderr)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-tail_chars:]
        raise RuntimeError(f"{Path(script).name} exit {proc.returncode}: {tail}")
    return proc
