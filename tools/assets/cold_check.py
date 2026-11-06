"""Cold retrieval check: resolve and hash every assets/manifest.json entry from the manifest alone.

new-case: read-only cold-agent retrieval proof for the asset manifest (#1017).

For each entry the candidate copies are ``<local_root>/<local_path>`` and
``<Drive-for-desktop mount>/<drive_folder>/<drive_path>`` (mounts: ``--drive-mount`` or the
``sync.py`` candidates such as ``G:/Мой диск``). Every copy that exists is hashed. An entry is
``match`` only when at least one copy exists and every existing copy has the declared SHA-256 and
size; a wrong copy is ``mismatch``, no copy is ``missing``. An invalid manifest is ``invalid``
before any hashing. Exit 0 only when every entry matches. Writes nothing: the JSON report goes to
stdout.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_SYNC_PATH = Path(__file__).resolve().with_name("sync.py")
_SPEC = importlib.util.spec_from_file_location("asset_sync_for_cold_check", _SYNC_PATH)
sync = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
_SPEC.loader.exec_module(sync)  # type: ignore[union-attr]


def default_mounts() -> list[Path]:
    return [path for path in sync._DRIVE_ROOT_CANDIDATES if sync._is_dir(path)]


def _locations(entry: dict, root: Path, folder: str | None, mounts: list[Path]) -> list[tuple[str, Path]]:
    found = [("local", root / entry["local_path"])]
    if folder:
        rel = sync._effective_drive_path(entry)
        found += [("drive", mount / folder / rel) for mount in mounts]
    return found


def check(manifest: Path, *, root: Path | None = None, drive_mounts: list[Path] | None = None) -> tuple[int, dict]:
    document, load_error = sync._load(Path(manifest))
    errors = [load_error] if load_error else sync.validate_document(document)
    report: dict = {"manifest": str(manifest), "status": "invalid", "errors": errors, "assets": []}
    if errors:
        return 1, report
    root = Path(root) if root is not None else Path(document["local_root"])
    mounts = default_mounts() if drive_mounts is None else [Path(path) for path in drive_mounts]
    folder = document.get("drive_folder")
    report.update(root=str(root), drive_folder=folder, drive_mounts=[str(path) for path in mounts])
    for entry in document["assets"]:
        rows = []
        for where, path in _locations(entry, root, folder, mounts):
            if not path.is_file():
                continue
            size = path.stat().st_size
            digest = sync._sha256(path)
            ok = digest == entry["sha256"] and size == entry["size"]
            rows.append({"where": where, "path": str(path), "sha256": digest, "size": size, "ok": ok})
        status = "missing" if not rows else ("match" if all(row["ok"] for row in rows) else "mismatch")
        report["assets"].append({"id": entry["id"], "status": status, "locations": rows})
    bad = [row["id"] for row in report["assets"] if row["status"] != "match"]
    report["status"] = "match" if not bad else "fail"
    report["errors"] = [f"{asset_id}: not retrievable" for asset_id in bad]
    report["counts"] = {
        status: sum(row["status"] == status for row in report["assets"]) for status in ("match", "mismatch", "missing")
    }
    return (0 if not bad else 1), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=sync.DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, help="Local store root; default: the manifest local_root.")
    parser.add_argument(
        "--drive-mount", type=Path, action="append", help="Drive-for-desktop root (repeatable); default: detected."
    )
    args = parser.parse_args(argv)
    code, report = check(args.manifest, root=args.root, drive_mounts=args.drive_mount)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
