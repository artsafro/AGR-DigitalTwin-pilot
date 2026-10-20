"""new-case: locked live/3dsmaxbatch adapter for review scenes; tests inject a fake."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import max_job

SCRIPTS = Path(os.environ.get("AGR_KANBAN_SCRIPTS", "C:/Users/artsafro/hermes_kanban/scripts"))


def max_batch_path():
    for version in ("2026", "2024"):
        path = Path(f"C:/Program Files/Autodesk/3ds Max {version}/3dsmaxbatch.exe")
        if path.is_file():
            return path
    return None


def _call(args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False, timeout=750)


class BatchAdapter:
    live = False

    def build(self, source: Path, max_out: Path, preview_png: Path | None) -> dict:
        return self._run(source, max_out, preview_png)

    def selftest(self, work: Path, max_out: Path, preview_png: Path) -> dict:
        work.mkdir(parents=True, exist_ok=True)
        return self._run(work / "synthetic-box.fbx", max_out, preview_png, selftest=True)

    def _run(self, source, max_out, preview_png, selftest=False):
        # Work belongs to staging, never to the source library directory.
        work = Path(max_out).parent / "max-job"
        work.mkdir(parents=True, exist_ok=True)
        result = work / "result.json"
        if result.exists():
            result.unlink()
        cfg = dict(source=str(source), max_out=str(max_out), result=str(result),
                   preview_png=None if preview_png is None else str(preview_png),
                   selftest=selftest, live=self.live)
        job = work / "review.ms"
        job.write_text(max_job.script(cfg), encoding="utf-8")
        card = os.environ.get("HERMES_KANBAN_TASK", "review-publisher")
        if self.live:
            args = [SCRIPTS / "max_exec.py", "--file", job, "--card", card, "--timeout", "600"]
        else:
            executable = max_batch_path()
            if executable is None:
                raise RuntimeError("3ds Max is not installed")
            version = executable.parent.name.rsplit(" ", 1)[-1]
            args = [SCRIPTS / "dcc_batch.py", "max", "--file", job, "--card", card,
                    "--timeout", "600", "--wait", "60", "--version", version]
        proc = _call(args)
        if proc.returncode != 0 or not result.is_file():
            raise RuntimeError("Max adapter failed: " + (proc.stdout + proc.stderr)[-2000:])
        info = json.loads(result.read_text(encoding="utf-8-sig"))
        if not info.get("ok"):
            raise RuntimeError(info.get("error") or "Max review job failed")
        return info


class LiveAdapter(BatchAdapter):
    live = True


def default_adapter():
    # A reachable user scene must only be accessed through max_exec's session lock.
    probe = _call([SCRIPTS / "max_exec.py", "--ping"])
    if probe.returncode == 0:
        payload = json.loads(probe.stdout)
        if payload.get("status") == "success" and payload.get("result", {}).get("success"):
            return LiveAdapter()
    if max_batch_path() is not None:
        return BatchAdapter()
    raise RuntimeError("3ds Max is not available")
