"""Thin AGR command facade [D271].

Pattern: n/a | new-case: aliases over existing CLI processes, without geometry code.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ALIASES = {"inspect": ["inspect"], "package-vpm": ["derive", "package"], "ground": ["ground", "v015"]}


STUBS = {
    "unwrap-atlas": "dt derive atlas --help; tools/materials/npm_atlas_udim.py (job-specific UV work)",
    "delivery-export": "dt derive npm --help; routes/npm-oks.md (export/readback)",
    "open-in-max": "routes/npm-oks.md step 7; existing Max bridge (confirm ownership first)",
    "contact-renders": "routes/npm-oks.md step 7; existing job review/contact renders, no universal command",
    "brick-seams": "routes/npm-oks.md step 4; source-bound job algorithms, no shared implementation",
    "ucx": "docs/domain/areas/ucx.md; existing approved job collision tools, no universal command",
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
        print("  validate           tools/qa/validate_package.py")
        print("  vpm-to-npm         dt derive atlas + dt derive npm (stop on failure)")
        for name, pointer in STUBS.items():
            print(f"  {name:18} unavailable: {pointer}")
        print("\nvpm-to-npm [--blender EXE] ATLAS_ARGS --then-npm NPM_ARGS\n"
              "Use agr vpm-to-npm --help for argument groups. Other aliases forward --help unchanged.\n"
              "PDF intake: dt index-pdf --help; exported topology: dt qa xview --help.\n"
              "Arguments and relative paths are unchanged; existing tools own validation and writes.")
        return 0
    if args and args[0] in STUBS:
        print(f"ERROR: {args[0]} is not implemented; use {STUBS[args[0]]}", file=sys.stderr)
        return 2
    if args and args[0] in ALIASES:
        return subprocess.run([sys.executable, "-m", "dt_ai.cli.main", *ALIASES[args[0]], *args[1:]], check=False).returncode
    if args and args[0] == "validate":
        script = Path(__file__).resolve().parents[3] / "tools/qa/validate_package.py"
        return subprocess.run([sys.executable, str(script), *args[1:]], check=False).returncode
    if args and args[0] == "vpm-to-npm":
        tail = args[1:]
        if tail in (["--help"], ["-h"]):
            print("usage: agr vpm-to-npm [--blender EXE] ATLAS_ARGS --then-npm NPM_ARGS\n"
                  "ATLAS_ARGS: dt derive atlas --help (SPEC NEW_ATLAS --recipe-dir RECIPE)\n"
                  "NPM_ARGS: dt derive npm --help (MASTER SPEC ATLAS NEW_EXPORT PREFIX)\n"
                  "No inferred paths, rollback or extra validation; existing tools own those contracts.\n"
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
        return 0
    print(f"ERROR: unknown or missing command {args[:1]!r}; use agr --help (routes/npm-oks.md)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
