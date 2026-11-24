"""Isolated launcher for the trainer's ``agr inspect --manifest`` step (oks-vpm stage 2).

Pattern: n/a | new-case: sandbox-safe, no-``uv run`` launcher for the oks-vpm ``inspect`` stage.

The trainer's ``oks-vpm`` lane runs a FRESH Codex agent in a ``codex exec -s workspace-write``
sandbox. Inside that sandbox ``uv run agr inspect ...`` fails before it reaches ``agr``, because
``uv`` tries to write its cache / managed-Python directories OUTSIDE the workspace (Windows
``os error 5``, #1608 -> #1858). The fix is to preflight the environment OUTSIDE the sandbox
(``uv sync`` -> ``.venv`` inside the checkout) and then launch the venv's own Python directly,
never through ``uv``:

    .venv/Scripts/python.exe -m dt_ai.trainer.inspect --manifest JOB.json      (Windows)
    .venv/bin/python        -m dt_ai.trainer.inspect --manifest JOB.json      (POSIX)

This reaches the SAME logic as ``agr inspect --manifest`` (``dt_ai.cli.agr`` aliases ``inspect``
to ``dt_ai.cli.main inspect``) with distinguishable, actionable outcomes:

    EXIT_OK        (0)  manifest valid; Gate 1 (pipeline attempts-gate, #128) open
    EXIT_BOOTSTRAP (2)  isolated interpreter missing / cannot start -- preflight first
    EXIT_MISSING   (3)  the --manifest file does not exist
    EXIT_MALFORMED (4)  the manifest is not a readable BuildJob (bad JSON / validation)
    EXIT_GATE1     (5)  the manifest's job is locked by the pipeline attempts-gate (#128)

``--preflight`` reports whether the isolated environment is ready and, when it is not, prints the
one command to run outside the sandbox. A practice run must NOT transfer the historical gate
approvals (``jobs/<JOB>/pipeline/state.json`` stop records): a fresh checkout starts clean, and a
copied lock is reported as EXIT_GATE1, never silently skipped. The launcher only reads; it writes
nothing and never deletes the input.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_BOOTSTRAP = 2
EXIT_MISSING = 3
EXIT_MALFORMED = 4
EXIT_GATE1 = 5

_VENV_CANDIDATES = (".venv/Scripts/python.exe", ".venv/bin/python")


class BootstrapError(RuntimeError):
    """The isolated interpreter is missing or cannot start."""


def repo_root() -> Path:
    """The repository checkout this module lives in (works in any checkout, incl. a disposable worktree)."""
    return Path(__file__).resolve().parents[3]


def isolated_python(root: Path, override: Path | None = None) -> Path:
    """The venv Python inside the checkout, or ``override``; raises BootstrapError when absent."""
    if override is not None:
        if not override.is_file():
            raise BootstrapError(f"--python {override} is not a file")
        return override
    for rel in _VENV_CANDIDATES:
        candidate = root / rel
        if candidate.is_file():
            return candidate
    raise BootstrapError(
        f"no isolated interpreter at {root / _VENV_CANDIDATES[0]!s} (tried {_VENV_CANDIDATES!r})"
    )


def manifest_job(root: Path, manifest: Path) -> str | None:
    """The ``jobs/<JOB>`` the manifest lives in, or None when it is outside ``jobs/``."""
    try:
        rel = manifest.resolve().relative_to((root / "jobs").resolve())
    except (ValueError, OSError):
        return None
    return rel.parts[0] if rel.parts else None


def gate_errors(root: Path, job: str) -> list[str]:
    """Reasons a run of ``jobs/<JOB>`` is denied by the pipeline attempts-gate (#128); [] when open."""
    gate = repo_root() / "tools" / "git-hooks" / "pipeline_gate.py"
    if not gate.is_file():
        return []
    spec = importlib.util.spec_from_file_location("pipeline_gate", gate)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_errors(root, job)


def launch(python: Path, manifest: Path) -> subprocess.CompletedProcess:
    """Run the actual ``agr inspect`` logic (``dt_ai.cli.main inspect``) in a fresh subprocess."""
    return subprocess.run(
        [str(python), "-m", "dt_ai.cli.main", "inspect", "--manifest", str(manifest)],
        capture_output=True,
        text=True,
    )


def preflight(root: Path, override: Path | None = None) -> int:
    """Report whether the isolated environment is ready; 0 ready, EXIT_BOOTSTRAP otherwise."""
    try:
        python = isolated_python(root, override)
    except BootstrapError as exc:
        print(f"NOT READY: {exc}", file=sys.stderr)
        print("Run once OUTSIDE the sandbox: `uv sync` (creates .venv).", file=sys.stderr)
        return EXIT_BOOTSTRAP
    try:
        proc = subprocess.run(
            [str(python), "-c", "import dt_ai.cli.main"], capture_output=True, text=True
        )
    except OSError as exc:
        print(f"NOT READY: cannot start {python}: {exc}", file=sys.stderr)
        return EXIT_BOOTSTRAP
    if proc.returncode != 0:
        print(f"NOT READY: {python} cannot import dt_ai.cli.main", file=sys.stderr)
        if proc.stderr.strip():
            print(proc.stderr.rstrip(), file=sys.stderr)
        return EXIT_BOOTSTRAP
    print(f"READY: {python}")
    return EXIT_OK


def run(root: Path, manifest: Path, override: Path | None = None) -> int:
    """Launch ``agr inspect --manifest`` in isolation and classify the outcome (see module docstring)."""
    try:
        python = isolated_python(root, override)
    except BootstrapError as exc:
        print(f"ERROR: bootstrap: {exc}", file=sys.stderr)
        print("Preflight outside the sandbox (`uv sync`), then relaunch without `uv run`.", file=sys.stderr)
        return EXIT_BOOTSTRAP
    if not manifest.exists():
        print(f"ERROR: manifest missing: {manifest}", file=sys.stderr)
        return EXIT_MISSING
    if not manifest.is_file():
        print(f"ERROR: manifest is not a file: {manifest}", file=sys.stderr)
        return EXIT_MALFORMED
    try:
        proc = launch(python, manifest)
    except OSError as exc:
        print(f"ERROR: bootstrap: cannot start isolated interpreter: {exc}", file=sys.stderr)
        return EXIT_BOOTSTRAP
    if proc.returncode != 0:
        print(f"ERROR: manifest malformed: {manifest}", file=sys.stderr)
        if proc.stderr.strip():
            print(proc.stderr.rstrip(), file=sys.stderr)
        return EXIT_MALFORMED
    sys.stdout.write(proc.stdout)
    job = manifest_job(root, manifest)
    if job is not None:
        errors = gate_errors(root, job)
        if errors:
            for error in errors:
                print(f"ERROR: gate1: {error}", file=sys.stderr)
            print(
                "Do not transfer historical gate approvals (pipeline/state.json) into a practice run.",
                file=sys.stderr,
            )
            return EXIT_GATE1
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dt_ai.trainer.inspect",
        description="Isolated (no-`uv run`) launcher for the trainer's `agr inspect --manifest` step.",
    )
    ap.add_argument("--manifest", type=Path, help="BuildJob manifest (JOB.json) to inspect")
    ap.add_argument("--python", type=Path, help="override the isolated interpreter")
    ap.add_argument("--preflight", action="store_true", help="verify the isolated environment only")
    args = ap.parse_args(argv)
    root = repo_root()
    if args.preflight:
        return preflight(root, args.python)
    if args.manifest is None:
        ap.error("--manifest is required (or use --preflight)")
    return run(root, args.manifest, args.python)


if __name__ == "__main__":
    raise SystemExit(main())
