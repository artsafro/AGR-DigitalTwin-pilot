"""Offline disposable-copy staging. Never connects to, starts or resets a DCC.

Only the source hash is invariant: authorized edits may change the working copy.
This is file evidence, not a scene lease, sandbox or delivery validator.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_fixture(run_directory: Path) -> dict:
    """Read original and working-copy hashes, without saving or deleting anything."""
    run_directory = Path(run_directory).resolve()
    manifest = json.loads((run_directory / "fixture.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Invalid fixture manifest")
    source_text = manifest.get("source")
    expected_hash = manifest.get("source_sha256")
    if (
        manifest.get("schema_version") != "1.0.0"
        or not isinstance(source_text, str)
        or not Path(source_text).is_absolute()
        or not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(c not in "0123456789abcdef" for c in expected_hash)
        or manifest.get("working_copy") != "working" + Path(source_text).suffix.lower()
        or manifest.get("delivery_passed") is not False
    ):
        raise ValueError("Invalid fixture manifest")
    source = Path(source_text)
    working = run_directory / manifest["working_copy"]
    source_hash = _sha256(source) if source.is_file() else None
    working_hash = _sha256(working) if working.is_file() else None
    return {
        "source_unchanged": source_hash == manifest["source_sha256"],
        "source_sha256_before": manifest["source_sha256"],
        "source_sha256_after": source_hash,
        "working_copy_exists": working_hash is not None,
        "working_copy_changed": working_hash != manifest["source_sha256"],
        "working_copy_sha256": working_hash,
        "delivery_passed": False,
    }


def stage_fixture(source: Path, run_directory: Path) -> dict:
    """Copy one source into an exclusively created directory; retain it on failure."""
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() not in {".blend", ".max", ".rvt"}:
        raise ValueError("Expected .blend, .max or .rvt")
    run_directory = Path(run_directory).resolve()
    before = _sha256(source)
    run_directory.mkdir(parents=True, exist_ok=False)
    working_name = "working" + source.suffix.lower()
    working = run_directory / working_name
    shutil.copyfile(source, working)
    if _sha256(source) != before or _sha256(working) != before:
        raise RuntimeError("Source or copy changed during staging; preserve directory for inspection")
    manifest = {
        "schema_version": "1.0.0",
        "source": str(source),
        "source_sha256": before,
        "working_copy": working_name,
        "delivery_passed": False,
    }
    (run_directory / "fixture.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    """Exit 0=file checks OK, 1=changed/missing files, 2=invalid input or I/O error."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage", help="Create a fresh disposable copy, never launch DCC")
    stage.add_argument("source", type=Path)
    stage.add_argument("run_directory", type=Path)
    verify = commands.add_parser("verify", help="Read hashes; never reset or delete files")
    verify.add_argument("run_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            result = stage_fixture(args.source, args.run_directory)
            code = 0
        else:
            result = verify_fixture(args.run_directory)
            code = 0 if result["source_unchanged"] and result["working_copy_exists"] else 1
    except (OSError, ValueError) as exc:
        print(f"Fixture error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"Fixture error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
