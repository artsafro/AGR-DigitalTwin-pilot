"""`dt derive` (NPM<->VPM derivation steps) and `dt ground` (Ground producers): one CLI over the shared tools.

Pattern: n/a | new-case: CLI routing to the shared tools that replace per-job copies (#1106).

Each step is one implementation in tools/derive/ or tools/ground/; the job copies (jobs/KPP1, jobs/PSU275,
jobs/TEC26-OKS scripts) stay as frozen records of their accepted runs. Arguments after the step name are
passed to the tool unchanged; the tool's exit code is returned (0 ok, nonzero refused / failed).
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dt_ai.core.blender_runner import BlenderRunError, blender_command, run_blender

DEFAULT_TIMEOUT = 900  # Match the canonical Blender runner.
BLENDER_ENTRY = Path(__file__).with_name("_blender_tool.py").resolve()

DERIVE_STEPS = {
    "atlas": ("python", "tools/derive/npm_atlas.py", "NPM 2048 atlas (d + o PNG, npm_atlas.json) from a VPM texture spec"),
    "npm": ("blender", "tools/derive/export_npm.py", "NPM OKS FBX from a VPM stage-6 master + atlas (headless Blender)"),
    "package-npm": ("python", "tools/derive/package_npm.py", "NPM flat ZIP with Ground and embedded-texture OKS FBX"),
    "package": ("python", "tools/derive/package_vpm.py", "VPM package ZIP: FBX + external PNG set (+ GeoJSON)"),
    "maf-npm-light": ("python", "tools/library/maf_npm_light.py",
                      "MAF NPM-light version + atlas UV for a MAF set, gated on readback (#1410, D293 conversion)"),
}
GROUND_STEPS = {
    "v015": ("python", "tools/ground/build_ground_v015.py", "Ground v015 NPM/VPM masters (layered cake + paired quads)"),
    "site": ("python", "tools/ground/build_ground_site.py", "Ground for any site in the D293 order from a site spec (#1406)"),
    "zero": ("python", "tools/ground/project_zero.py", "project zero h_relief (D279) + export Z check (#1406)"),
}
PLACE_STEPS = {   # #1407: MAF + Flora NPM and VPM at the same points in one run (core dt_ai.placement.site)
    "site": ("python", "src/dt_ai/placement/site.py", "MAF + Flora placement, NPM and VPM at the same points (D293)"),
}
TABLES = {"derive": DERIVE_STEPS, "ground": GROUND_STEPS, "place": PLACE_STEPS}


def _positive_seconds(value: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number of seconds")
    return seconds


def add_parsers(sub):
    derive = sub.add_parser("derive", help="NPM<->VPM derivation: atlas | npm | package | package-npm | maf-npm-light (shared tools, #1106, #1410)")
    derive.add_argument("--blender", default=os.environ.get("DT_BLENDER"),
                        help="Blender executable for the npm step (default: DT_BLENDER)")
    derive.add_argument("--timeout", type=_positive_seconds, default=DEFAULT_TIMEOUT,
                        help="Blender timeout in seconds (default: %(default)s); place before the step")
    derive.add_argument("step", choices=sorted(DERIVE_STEPS), help="; ".join(f"{k}: {v[2]}" for k, v in DERIVE_STEPS.items()))
    derive.add_argument("args", nargs=argparse.REMAINDER, help="arguments of the tool (see its --help)")
    ground = sub.add_parser("ground", help="Ground: site (any site, D293 order) | zero (project zero) | v015 (Vatutino record)")
    ground.add_argument("step", choices=sorted(GROUND_STEPS), help="; ".join(f"{k}: {v[2]}" for k, v in GROUND_STEPS.items()))
    ground.add_argument("args", nargs=argparse.REMAINDER, help="arguments of the tool (see its --help)")
    place = sub.add_parser("place", help="Site placement: site = MAF + Flora NPM and VPM at the same points (#1407)")
    place.add_argument("step", choices=sorted(PLACE_STEPS), help="; ".join(f"{k}: {v[2]}" for k, v in PLACE_STEPS.items()))
    place.add_argument("args", nargs=argparse.REMAINDER, help="arguments of the tool (see its --help)")


def _step(root: Path, kind: str, step: str, args: list[str], blender: str | None):
    table = TABLES.get(kind)
    if table is None or step not in table:
        raise ValueError(f"unknown {kind} step {step!r}")
    host, rel, _ = table[step]
    script = Path(root) / rel
    if not script.is_file():
        raise ValueError(f"shared tool missing: {script}")
    args = list(args[1:] if args[:1] == ["--"] else args)
    if host == "blender":
        if not blender:
            raise ValueError(f"the {step} step needs Blender: pass --blender or set DT_BLENDER")
        if not Path(blender).is_file():
            raise ValueError(f"Blender executable not found: {blender}")
    return host, script, args


def command(root: Path, kind: str, step: str, args: list[str], blender: str | None = None) -> list[str]:
    """Preview the tool command line; use run() to execute with the host's runtime policy."""
    host, script, args = _step(root, kind, step, args, blender)
    if host == "python":
        return [sys.executable, str(script), *args]
    return blender_command(script, args, executable=blender)   # the one Blender command line (#1378, #1530)


def run(root: Path, ns) -> int:
    blender = getattr(ns, "blender", None)
    try:
        host, script, args = _step(root, ns.command, ns.step, ns.args, blender)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    env = dict(os.environ)
    src = str(Path(root) / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if host == "python":
        return subprocess.run([sys.executable, str(script), *args], cwd=str(root), env=env).returncode

    # The runner inherits the caller's environment. Restore just this key after
    # the synchronous CLI call, including when Blender fails to start.
    previous = os.environ.get("PYTHONPATH")
    try:
        os.environ["PYTHONPATH"] = env["PYTHONPATH"]
        # The runner requires fresh evidence even for stdout-only modes such
        # as --help and --dry-check. The receipt is not an export certificate.
        with tempfile.TemporaryDirectory(prefix="dt-blender-tool-") as temp:
            receipt = Path(temp) / "completed.json"
            result = run_blender(BLENDER_ENTRY, [receipt, script.absolute(), *args], executable=blender,
                                 timeout=getattr(ns, "timeout", DEFAULT_TIMEOUT), output_json=receipt, cwd=str(root))
    except BlenderRunError as exc:
        error = exc.envelope
        detail = f"{error['code']}: {error['message']} (log: {error['log']})"
        print("ERROR: " + " ".join(detail.splitlines()), file=sys.stderr)
        return 2 if error.get("returncode") == 2 else 1
    finally:
        if previous is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = previous
    print(result["stdout"], end="")
    return 0
