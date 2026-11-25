"""Isolated launcher for the trainer's ``agr inspect --manifest`` step (oks-vpm stage 2).

Pattern: n/a | new-case: sandbox-safe, no-``uv run`` launcher for the oks-vpm ``inspect`` stage.

The trainer's ``oks-vpm`` lane runs a FRESH Codex agent in a ``codex exec -s workspace-write``
sandbox. Inside that sandbox ``uv run agr inspect ...`` fails before it reaches ``agr``
(Windows ``os error 5``, #1608 -> #1858). The mechanism is not fully diagnosed; the working
hypothesis is that ``uv`` tries to write its cache / managed-Python directories OUTSIDE the
workspace, which the sandbox denies (pointing ``UV_CACHE_DIR`` at an unwritable directory
reproduces ``os error 5`` deterministically). Whatever the exact mechanism, the fix is to
preflight the environment OUTSIDE the sandbox (``uv sync`` -> ``.venv`` inside the checkout)
and then launch the venv's own Python directly, never through ``uv``:

    .venv/Scripts/python.exe -m dt_ai.trainer.inspect_launcher --manifest JOB.json      (Windows)
    .venv/bin/python        -m dt_ai.trainer.inspect_launcher --manifest JOB.json      (POSIX)

This reaches the SAME logic as ``agr inspect --manifest`` (``dt_ai.cli.agr`` aliases ``inspect``
to ``dt_ai.cli.main inspect``) with distinguishable, actionable outcomes:

    EXIT_OK            (0)  manifest valid; pipeline attempts-gate (#128) open
    EXIT_BOOTSTRAP     (2)  isolated interpreter missing / cannot import dt_ai.cli.main -- preflight first
    EXIT_MISSING       (3)  the --manifest file does not exist
    EXIT_MALFORMED     (4)  the manifest is not a readable BuildJob (bad JSON / validation)
    EXIT_ATTEMPTS_GATE (5)  the manifest's job is locked by the pipeline attempts-gate (#128)

The bootstrap-vs-malformed split is classified INSIDE the launched process: the child runs a
``-c`` shim that imports ``dt_ai.cli.main`` and exits with a dedicated code on import failure,
before the manifest is ever read. So an interpreter without ``dt_ai``, or one missing a
dependency (the #1608 "no shapely/ezdxf" condition), reports EXIT_BOOTSTRAP, never a
"manifest malformed" verdict.

``--preflight`` reports whether the isolated environment is ready and, when it is not, prints the
one command to run outside the sandbox.

A practice run must NOT transfer the historical pipeline attempts-gate state
(``jobs/<JOB>/pipeline/state.json``): a fresh checkout starts clean, and a copied lock is
reported as EXIT_ATTEMPTS_GATE, never silently skipped. The launcher only reads; it writes
nothing and never deletes the input.

Gate 1 (the user's ``parts.json`` confirmation, docs/procedure/TASK_TO_MODEL.md, "Gate 1 handoff")
is OUT OF SCOPE for this launcher: the ``inspect`` step reads a BuildJob manifest
(``project.json``) and runs before ``parts.json`` exists, so there is no Gate 1 approval to
transfer or verify at this step. The attempts-gate (#128) is a separate, distinct check and is
reported under EXIT_ATTEMPTS_GATE, never as "Gate 1".
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
EXIT_ATTEMPTS_GATE = 5

# The child process exits with this code only when it cannot import dt_ai.cli.main (a bootstrap
# failure), so a manifest the CLI reads but fails to parse (the CLI exits 1) is never misreported
# as a bootstrap failure. The value is far from the CLI's own 0/1/2/3 return codes.
_BOOTSTRAP_CHILD_CODE = 250

_LAUNCH_SHIM = (
    "import sys\n"
    "try:\n"
    "    from dt_ai.cli import main as cli_main\n"
    "except Exception as exc:\n"
    "    print('bootstrap: cannot import dt_ai.cli.main: ' + repr(exc), file=sys.stderr)\n"
    "    sys.exit({code})\n"
    "sys.argv = ['agr', 'inspect', '--manifest', sys.argv[1]]\n"
    "sys.exit(cli_main.main())\n"
).format(code=_BOOTSTRAP_CHILD_CODE)

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
    """Reasons a run of ``jobs/<JOB>`` is denied by the pipeline attempts-gate (#128); [] when open.

    Fails closed: when the gate script is missing or cannot be loaded, it reports
    "attempts-gate not checked" instead of silently treating the job as open.
    """
    gate = repo_root() / "tools" / "git-hooks" / "pipeline_gate.py"
    if not gate.is_file():
        return [f"attempts-gate not checked: {gate} is missing"]
    try:
        spec = importlib.util.spec_from_file_location("pipeline_gate", gate)
        if spec is None or spec.loader is None:
            return [f"attempts-gate not checked: cannot load {gate}"]
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run_errors(root, job)
    except Exception as exc:  # a gate that cannot run must not count as open
        return [f"attempts-gate not checked: {gate} failed to load: {exc}"]


def launch(python: Path, manifest: Path) -> subprocess.CompletedProcess:
    """Run the actual ``agr inspect`` logic (``dt_ai.cli.main inspect``) in a fresh subprocess.

    The child is a ``-c`` shim that imports ``dt_ai.cli.main`` FIRST and exits
    ``_BOOTSTRAP_CHILD_CODE`` when that import fails, so an import/bootstrap failure is
    distinguishable from a manifest the CLI reads but fails to parse.
    """
    return subprocess.run(
        [str(python), "-c", _LAUNCH_SHIM, str(manifest)],
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
    if proc.returncode == _BOOTSTRAP_CHILD_CODE:
        print("ERROR: bootstrap: isolated interpreter cannot import dt_ai.cli.main", file=sys.stderr)
        if proc.stderr.strip():
            print(proc.stderr.rstrip(), file=sys.stderr)
        print("Preflight outside the sandbox (`uv sync`), then relaunch without `uv run`.", file=sys.stderr)
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
                print(f"ERROR: attempts-gate (#128): {error}", file=sys.stderr)
            print(
                "Do not transfer historical gate state (pipeline/state.json) into a practice run.",
                file=sys.stderr,
            )
            return EXIT_ATTEMPTS_GATE
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dt_ai.trainer.inspect_launcher",
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
