"""new-case: locked live/3dsmaxbatch adapter for review scenes; tests inject a fake."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import max_job
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from dt_ai.core.max_env import max_child_env  # noqa: E402

SCRIPTS = Path(os.environ.get("AGR_KANBAN_SCRIPTS", "C:/Users/artsafro/hermes_kanban/scripts"))


def max_batch_path():
    for version in ("2026", "2024"):
        path = Path(f"C:/Program Files/Autodesk/3ds Max {version}/3dsmaxbatch.exe")
        if path.is_file():
            return path
    return None


def _call(args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False, timeout=750, env=max_child_env())


class MaxAdapterError(RuntimeError):
    """A failed Max batch/live call; ``returncode`` 3 is the busy lock (dcc_batch.py)."""

    def __init__(self, returncode: int, output: str):
        # The output starts on its own line so a busy JSON answer stays a whole line.
        super().__init__(f"Max adapter failed (exit {returncode}):\n{output}")
        self.returncode = returncode


def startup_script_error(proc) -> bool:
    """True when a non-zero ``dcc_batch`` exit is explained by the user's Max startup
    auto-load scripts failing under ``3dsmaxbatch`` (polyunwrapper_autoload.mse, the
    ``_maxUsd`` USD import), not by the job script.

    ``dcc_batch.py`` downgrades the MAXScript form to a warning, but the Python ``_maxUsd``
    form carries a ``Traceback`` and is misreported as a job error even though the job
    script still runs to completion (the review jobs are MAXScript, so a Traceback here is
    always the startup import). The job's own output stays authoritative (#1024 review tests).
    """
    if getattr(proc, "returncode", 1) == 0:
        return False
    out = (getattr(proc, "stdout", "") or "") + (getattr(proc, "stderr", "") or "")
    if "Auto-load Script Error" not in out:
        return False
    return not any(k in out for k in ("ExecuteMAXScriptScript Exception", "-- Syntax error", "Unable to open"))


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
        if not result.is_file():
            raise MaxAdapterError(proc.returncode, (proc.stdout + proc.stderr)[-2000:])
        info = json.loads(result.read_text(encoding="utf-8-sig"))
        if not info.get("ok"):
            detail = (proc.stdout + proc.stderr)[-2000:]
            if proc.returncode != 0:
                raise MaxAdapterError(proc.returncode, detail)
            raise RuntimeError((info.get("error") or "Max review job failed")
                               + ((": " + detail) if detail else ""))
        # A non-zero batch exit here is the user's Max startup auto-load scripts
        # (polyunwrapper_autoload.mse, _maxUsd USD import) failing under 3dsmaxbatch;
        # the job itself completed, so result.json is authoritative (merge-gate review tests).
        return info


class LiveAdapter(BatchAdapter):
    live = True


def default_adapter():
    # COORDINATION_RULES 27: the user's bridge is safe-mode only; review jobs
    # write reports and run on copies through the authorized headless lock.
    if max_batch_path() is not None:
        return BatchAdapter()
    raise RuntimeError("3ds Max is not available")
