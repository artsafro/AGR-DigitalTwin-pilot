"""Thin AGR command facade [D271].

Pattern: n/a | new-case: aliases over existing CLI processes, without geometry code.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ALIASES = {"inspect": ["inspect"], "package-vpm": ["derive", "package"], "package-npm": ["derive", "package-npm"], "ground": ["ground", "v015"],
           "zero": ["ground", "zero"],
           "place": ["place", "site"],   # #1407: MAF + Flora NPM + VPM at the same points
           "npm-light": ["derive", "maf-npm-light"]}   # #1410: MAF NPM-light + atlas UV (D293 conversion branch)
# agr ground (#1406): `agr ground site|zero|v015 ARGS` picks the step; any other first argument keeps the
# frozen Vatutino record `dt ground v015 ARGS` (unchanged for existing callers).
GROUND_STEPS = ("site", "zero", "v015")
# Repo scripts run unchanged with the caller's arguments; the scripts own validation and writes.
# export-meta (#1409): core adapters/max/agr_tools/export_meta.py, also importable inside 3ds Max (AGR Tools).
# checker (#1379): the SINTEZ stage command; Blender side tools/blender/sintez_checker.py via blender_runner.
# build-manifest (#1423): core adapters/max/agr_tools/build_manifest.py (delivery set consistency, FBX export owner).
SCRIPTS = {"openings": "tools/source/openings.py", "validate": "tools/qa/validate_package.py", "export-meta": "tools/derive/export_meta.py",
           "checker": "tools/qa/sintez_checker.py", "build-manifest": "tools/derive/build_manifest.py"}


STUBS = {
    "unwrap-atlas": "dt derive atlas --help; tools/materials/npm_atlas_udim.py (job-specific UV work)",
    "delivery-export": "dt derive npm --help; routes/npm-oks.md (export/readback)",
    "open-in-max": "routes/npm-oks.md step 7; existing Max bridge (confirm ownership first)",
    "contact-renders": "routes/npm-oks.md step 7; existing job review/contact renders, no universal command",
}


def main(argv=None) -> int:
    """Return the delegated status; refuse unavailable commands without launching tools."""
    try:
        return _dispatch(list(sys.argv[1:] if argv is None else argv))
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: list[str]) -> int:
    if args in (["--help"], ["-h"]):
        print("usage: agr COMMAND [existing tool arguments]\n\nThin aliases [D271]; no new geometry implementation.")
        for name, target in ALIASES.items():
            print(f"  {name:18} dt {' '.join(target)}")
        for name, script in SCRIPTS.items():
            print(f"  {name:18} {script}")
        print("  ground site|zero   dt ground site SPEC NEW_OUT (any site, D293 order) | dt ground zero (#1406)")
        print("  brick-seams        tools.materials.brick_seams (shared stdlib core, JSON candidate)")
        print("  vpm-to-npm         dt derive atlas + dt derive npm (stop on failure)")
        print("  ucx                UCX Main/Ground: ucx_build -> readback -> ucx10_core gap + V010 [D330]")
        for name, pointer in STUBS.items():
            print(f"  {name:18} unavailable: {pointer}")
        print("\nvpm-to-npm [--blender EXE] ATLAS_ARGS --then-npm NPM_ARGS\n"
              "Use agr vpm-to-npm --help for argument groups. Other aliases forward --help unchanged.\n"
              "ucx MODEL OUT Main|Ground [key=value ...] [--blender EXE] [--gap-m M] (agr ucx --help)\n"
              "export-meta check PATH | record FBX --source S [--top Z|unknown] [--out NEW.json]\n"
              "PDF intake: dt index-pdf --help; exported topology: dt qa xview --help.\n"
              "Arguments and relative paths are unchanged; existing tools own validation and writes.")
        return 0
    if args and args[0] in STUBS:
        print(f"ERROR: {args[0]} is not implemented; use {STUBS[args[0]]}", file=sys.stderr)
        return 2
    if args[:1] == ["ground"] and args[1:2] and args[1] in GROUND_STEPS:
        return subprocess.run([sys.executable, "-m", "dt_ai.cli.main", "ground", *args[1:]], check=False).returncode
    if args and args[0] in ALIASES:
        return subprocess.run([sys.executable, "-m", "dt_ai.cli.main", *ALIASES[args[0]], *args[1:]], check=False).returncode
    if args and args[0] == "brick-seams":
        script = Path(__file__).resolve().parents[3] / "tools/materials/brick_seams.py"
        return subprocess.run([sys.executable, str(script), *args[1:]], check=False).returncode
    if args and args[0] in SCRIPTS:
        script = Path(__file__).resolve().parents[3] / SCRIPTS[args[0]]
        return subprocess.run([sys.executable, str(script), *args[1:]], check=False).returncode
    if args and args[0] == "ucx":
        # #1404 [D330]: one UCX command; build core ucx_build, gap core ucx10_core (also AGR Tools in Max)
        from dt_ai.geometry import ucx_command
        return ucx_command.main(args[1:])
    if args and args[0] == "vpm-to-npm":
        tail = args[1:]
        if tail in (["--help"], ["-h"]):
            print("usage: agr vpm-to-npm [--blender EXE] ATLAS_ARGS --then-npm NPM_ARGS\n"
                  "ATLAS_ARGS: dt derive atlas --help (SPEC NEW_ATLAS --master MASTER --recipe-dir RECIPE)\n"
                  "NPM_ARGS: dt derive npm --help (MASTER SPEC ATLAS NEW_EXPORT PREFIX)\n"
                  "No rollback; existing tools own their contracts. After npm, the NPM UV readback (#1580,\n"
                  "python -m twinqa.npm_uv) checks the exported FBX named in NEW_EXPORT/../export_npm_meta.json\n"
                  "against ATLAS/npm_atlas.json (every face inside its region, 8 px padding); a fail exits 1.\n"
                  "DT_BLENDER is used when --blender is omitted. Atlas must succeed before npm starts.")
            return 0
        blender = []
        if tail[:1] == ["--blender"] and len(tail) >= 2:
            blender, tail = tail[:2], tail[2:]
        if tail.count("--then-npm") != 1:
            print("ERROR: use dt derive atlas ARGS, then dt derive npm ARGS; agr needs ATLAS_ARGS --then-npm NPM_ARGS", file=sys.stderr)
            return 2
        split = tail.index("--then-npm")
        if split == 0 or split == len(tail) - 1:
            print("ERROR: dt derive atlas and dt derive npm both need arguments", file=sys.stderr)
            return 2
        for step in (["derive", "atlas", *tail[:split]], ["derive", *blender, "npm", *tail[split + 1:]]):
            status = subprocess.run([sys.executable, "-m", "dt_ai.cli.main", *step], check=False).returncode
            if status != 0:
                return status
        return npm_uv_readback(tail[split + 1:], blender)
    print(f"ERROR: unknown or missing command {args[:1]!r}; use agr --help (routes/npm-oks.md)", file=sys.stderr)
    return 2


NPM_VALUE_OPTIONS = {"--address", "--index", "--pivot", "--recipe-dir"}


def npm_positionals(npm_args: list[str]) -> list[str]:
    """MASTER SPEC ATLAS NEW_EXPORT [PREFIX] of dt derive npm arguments (value options skipped)."""
    out, skip = [], False
    for token in npm_args:
        if skip:
            skip = False
        elif token in NPM_VALUE_OPTIONS:
            skip = True
        elif not token.startswith("--"):
            out.append(token)
    return out


def npm_uv_readback(npm_args: list[str], blender: list[str]) -> int:
    """#1580: read the exported NPM FBX back and check its UVs against npm_atlas.json (twinqa.npm_uv)."""
    import json
    pos = npm_positionals(npm_args)
    if len(pos) < 4:
        print(f"ERROR: NPM UV readback needs MASTER SPEC ATLAS NEW_EXPORT, got {pos}", file=sys.stderr)
        return 2
    atlas, out = Path(pos[2]) / "npm_atlas.json", Path(pos[3]).resolve()
    meta = out.parent / "export_npm_meta.json"
    try:
        fbx = Path(json.loads(meta.read_text(encoding="utf-8"))["fbx"]).resolve()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: NPM UV readback: no exported FBX in {meta}: {exc}", file=sys.stderr)
        return 2
    if fbx.parent != out or not fbx.is_file():
        print(f"ERROR: NPM UV readback: {fbx} is not an exported FBX inside {out}", file=sys.stderr)
        return 2
    if not blender and os.environ.get("DT_BLENDER"):
        blender = ["--blender", os.environ["DT_BLENDER"]]  # the same Blender as the npm step
    return subprocess.run([sys.executable, "-m", "twinqa.npm_uv", str(fbx), str(atlas), *blender],
                          check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
