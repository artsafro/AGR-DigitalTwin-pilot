"""Prototype (experiment only): one headless Blender runner for every Python call site.

Not wired into the project. Contract: fixed isolation flags, timeout always set, log on disk,
nonzero exit rejected, promised outputs must exist, be non-empty and (for .json) parse.
"""
import json
import os
import subprocess
from pathlib import Path

FLAGS = ("--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1")


class BlenderRunError(RuntimeError):
    pass


def command(blender, script, *args):
    return [str(blender), *FLAGS, "--python", str(script), "--", *map(str, args)]


def kill_tree(child):
    """Kill the child and its descendants; a grandchild holding the pipes would block otherwise."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, timeout=10)
    else:
        child.kill()
    try:
        child.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def run(blender, script, *args, outputs=(), log=None, timeout=900):
    """Run `script` in isolated background Blender; return parsed JSON outputs (or paths)."""
    cmd = command(blender, script, *args)
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
    try:
        text, _ = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        kill_tree(child)
        raise BlenderRunError(f"{Path(script).name}: timed out after {timeout} s") from exc
    done = child
    text = text or ""
    if log is not None:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text(text, encoding="utf-8")
    tail = text[-800:]
    if done.returncode != 0:
        raise BlenderRunError(f"{Path(script).name}: exit {done.returncode}: {tail}")
    result = {}
    for out in map(Path, outputs):
        if not out.is_file() or out.stat().st_size == 0:
            raise BlenderRunError(f"{Path(script).name}: exit 0 but no {out.name}: {tail}")
        if out.suffix.lower() == ".json":
            try:
                result[out.name] = json.loads(out.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise BlenderRunError(f"{Path(script).name}: {out.name} is not JSON ({exc})") from exc
        else:
            result[out.name] = out
    return result
