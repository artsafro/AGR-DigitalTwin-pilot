"""Blender-side adapter for shared tools with stdout-only modes.

Pattern: n/a | new-case: report successful tool completion to the canonical Blender runner.
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import runpy
import sys


def main():
    receipt, script, *args = sys.argv[sys.argv.index("--") + 1:]
    stdout = io.StringIO()
    original_argv = sys.argv
    try:
        sys.argv = [script, "--", *args]
        with redirect_stdout(stdout):
            try:
                runpy.run_path(script, run_name="__main__")
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
    finally:
        sys.argv = original_argv
        # Keep the tool's output in the runner log even when it fails.
        sys.stdout.write(stdout.getvalue())
    with Path(receipt).open("x", encoding="utf-8") as stream:
        json.dump({"stdout": stdout.getvalue()}, stream)


if __name__ == "__main__":
    main()
