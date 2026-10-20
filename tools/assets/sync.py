"""Check the local asset store and report Google Drive links.

new-case: fail-closed local asset inventory and non-destructive Drive mirroring.

Dry-run is the default: nothing is copied and no report file is written.
``--apply`` mirrors verified files and writes a report only when every check succeeded and ``--out`` does
not resolve to the manifest or a file the run read.

Backends: ``local`` (default), ``rclone``, ``drive-desktop``. Dropbox and any
other name fail. With no rclone remote and no Drive-for-desktop folder the
run stays on the local root and leaves ``drive_link`` as ``pending``. This
tool never prompts for the one-time Google login.

A declared sha256 that does not match the local file, a missing or blank source [D151], an empty or partial manifest, a non-finite size, or size exactly 0
(the minimum-size threshold) fails closed. Status is never ``pass`` or
``not_run``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import subprocess
import tempfile
from pathlib import Path

LOCAL_ROOT = "C:/x/assets"
SCHEMA_ID = "asset-store/1"
PENDING = "pending"
SHA256_HEX_LENGTH = 64
MIN_ASSET_SIZE = 1
BACKENDS = frozenset({"local", "rclone", "drive-desktop"})
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^v[0-9]{3}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DRIVE_LINK_RE = re.compile(r"^https://(drive|docs)\.google\.com/\S+$")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "assets" / "manifest.json"


def prompt_for_login() -> None:
    """The one-time Google login is a user action. Sync never calls this."""
    raise RuntimeError("sync does not perform the one-time Google Drive login")


def which_rclone() -> str | None:
    return shutil.which("rclone")


def drive_desktop_root(explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        path = Path(explicit)
        return path if path.is_dir() else None
    candidates = (
        Path("G:/My Drive"),
        Path("G:/"),
        Path.home() / "Google Drive",
        Path.home() / "My Drive",
    )
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


def _credentials(backend: str, drive_root: Path | None) -> str:
    if backend == "rclone" and which_rclone() and os.environ.get("AGR_RCLONE_REMOTE"):
        return "present"
    if backend == "drive-desktop" and drive_desktop_root(drive_root) is not None:
        return "present"
    return "absent"


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def validate_document(document: object) -> list[str]:
    """Return fail-closed errors. An empty list means the document is usable."""
    if not isinstance(document, dict) or not document:
        return ["empty"]
    errors: list[str] = []
    allowed = {"schema", "local_root", "login", "drive", "rejected_backends", "provenance_gaps", "assets"}
    if set(document) - allowed:
        errors.append("unsupported_manifest_field")
    if document.get("login") not in {"pending", "rclone", "drive-desktop"}:
        errors.append("partial: login")
    if document.get("drive") != "google-drive" or document.get("rejected_backends") != ["dropbox"]:
        errors.append("unsupported_drive")
    assets = document.get("assets", None)
    if "assets" not in document or not isinstance(assets, list):
        return ["partial: assets"]
    if document.get("schema") != SCHEMA_ID:
        errors.append("partial: schema")
    if document.get("local_root") != LOCAL_ROOT:
        errors.append("partial: local_root")
    if len(assets) == 0:
        errors.append("empty")
    seen: set[str] = set()
    for index, entry in enumerate(assets):
        label = f"entry[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: partial")
            continue
        allowed_entry = {"id", "version", "local_path", "sha256", "size", "drive_link", "licence", "source", "recorded_path"}
        if set(entry) - allowed_entry:
            errors.append(f"{label}: unsupported_field")
        for field in ("licence", "source"):
            if field in entry and entry[field] is not None and not isinstance(entry[field], str):
                errors.append(f"{label}: partial: {field}")
        identifier = entry.get("id")
        if isinstance(identifier, str) and ID_RE.fullmatch(identifier):
            label = identifier
            if identifier in seen:
                errors.append(f"{label}: duplicate_id")
            seen.add(identifier)
        else:
            errors.append(f"{label}: partial: id")
        version = entry.get("version", None)
        if version is not None and not (isinstance(version, str) and VERSION_RE.fullmatch(version)):
            errors.append(f"{label}: partial: version")
        if "version" not in entry:
            errors.append(f"{label}: partial: version")
        local_path = entry.get("local_path")
        if not isinstance(local_path, str) or not local_path.strip() or _path_escapes(local_path):
            errors.append(f"{label}: partial: local_path")
        sha = entry.get("sha256", None)
        if "sha256" not in entry:
            errors.append(f"{label}: partial: sha256")
        elif not (isinstance(sha, str) and SHA256_RE.fullmatch(sha) and len(sha) == SHA256_HEX_LENGTH):
            errors.append(f"{label}: sha256_length")
        if "size" not in entry:
            errors.append(f"{label}: partial: size")
        else:
            errors.extend(_size_errors(label, entry.get("size")))
        link = entry.get("drive_link", None)
        if link != PENDING and not (isinstance(link, str) and DRIVE_LINK_RE.fullmatch(link)):
            errors.append(f"{label}: partial: drive_link")
        if not _text(entry.get("source")):
            errors.append(f"{label}: missing_source")
    return errors


def _size_errors(label: str, size: object) -> list[str]:
    if size is None:
        return [f"{label}: missing_size"]
    if isinstance(size, bool) or isinstance(size, str):
        return [f"{label}: size_not_finite"]
    if isinstance(size, float):
        if not math.isfinite(size):
            return [f"{label}: size_not_finite"]
        if size == 0:
            return [f"{label}: size_at_threshold"]
        return [f"{label}: size_not_finite"]
    if isinstance(size, int):
        if size == 0:
            return [f"{label}: size_at_threshold"]
        if size < MIN_ASSET_SIZE:
            return [f"{label}: size_at_threshold"]
        return []
    return [f"{label}: size_not_finite"]


def _path_escapes(local_path: str) -> bool:
    path = Path(local_path.replace("\\", "/"))
    if path.is_absolute() or path.drive or ":" in local_path:
        return True
    return any(part == ".." for part in path.parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve() or (left.exists() and right.exists() and left.samefile(right))
    except OSError:
        return False


def _contained(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _load(path: Path) -> tuple[object | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"partial: {exc.__class__.__name__}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return None, "partial: manifest_json"


def _entry_label(entry: object, index: int) -> str:
    if isinstance(entry, dict) and isinstance(entry.get("id"), str):
        return entry["id"]
    return f"entry[{index}]"


def _errors_for(label: str, errors: list[str]) -> list[str]:
    prefix = f"{label}:"
    return [error for error in errors if error.startswith(prefix)]


def execute(
    manifest: Path,
    *,
    root: Path,
    backend: str = "local",
    apply: bool = False,
    out: Path | None = None,
    drive_root: Path | None = None,
) -> tuple[int, dict]:
    manifest = Path(manifest)
    root = Path(root)
    document, load_error = _load(manifest)
    errors = [load_error] if load_error else validate_document(document)
    assets_in = document.get("assets") if isinstance(document, dict) else None
    if not isinstance(assets_in, list):
        assets_in = []
    if backend not in BACKENDS:
        errors.append("unsupported_backend")

    rows: list[dict] = []
    read_paths = [manifest]
    for index, entry in enumerate(assets_in):
        label = _entry_label(entry, index)
        row_errors = _errors_for(label, errors)
        status = "error" if row_errors else "absent"
        link = PENDING
        local_file: Path | None = None
        if isinstance(entry, dict):
            raw_link = entry.get("drive_link")
            if isinstance(raw_link, str) and (raw_link == PENDING or DRIVE_LINK_RE.fullmatch(raw_link)):
                link = raw_link if _credentials(backend, drive_root) == "present" or raw_link == PENDING else PENDING
            local_path = entry.get("local_path")
            if isinstance(local_path, str) and not _path_escapes(local_path):
                local_file = (root / local_path)
                try:
                    if not _contained(root, local_file):
                        row_errors.append(f"{label}: partial: local_path")
                        local_file = None
                except OSError:
                    row_errors.append(f"{label}: partial: local_path")
                    local_file = None
        if local_file is not None:
            declared = entry.get("sha256") if isinstance(entry, dict) else None
            declared_size = entry.get("size") if isinstance(entry, dict) else None
            if local_file.is_file():
                read_paths.append(local_file)
                digest = _sha256(local_file)
                actual_size = local_file.stat().st_size
                if not isinstance(declared, str):
                    row_errors.append(f"{label}: missing_sha256")
                elif digest != declared:
                    row_errors.append(f"{label}: sha256_mismatch")
                elif isinstance(declared_size, int) and not isinstance(declared_size, bool) and actual_size != declared_size:
                    row_errors.append(f"{label}: size_mismatch")
                elif actual_size < MIN_ASSET_SIZE:
                    row_errors.append(f"{label}: size_at_threshold")
                elif not row_errors:
                    status = "match"
            else:
                row_errors.append(f"{label}: missing_file")
        if any(item.endswith("sha256_mismatch") for item in row_errors) and not any(
            not item.endswith("sha256_mismatch") for item in row_errors
        ):
            status = "mismatch"
        elif row_errors:
            status = "error"
        if backend not in BACKENDS:
            status = "error"
        if link != PENDING:
            link = PENDING if _credentials(backend, drive_root) != "present" else link
        for item in row_errors:
            if item not in errors:
                errors.append(item)
        rows.append({"id": label, "status": status, "drive_link": link if link == PENDING or status == "match" else PENDING, "errors": row_errors})

    # Preflight ALL destinations before any write, including missing asset paths.
    local_paths = [root / e["local_path"] for e in assets_in
                   if isinstance(e, dict) and isinstance(e.get("local_path"), str)]
    desktop = drive_desktop_root(drive_root) if backend == "drive-desktop" else None
    targets = [desktop / e["local_path"] for e in assets_in
               if isinstance(e, dict) and isinstance(e.get("local_path"), str)] if desktop else []
    # Query only during apply; dry-run must never invoke a remote client.
    if not errors and apply and backend == "rclone" and _credentials(backend, drive_root) == "present":
        try:
            remote_root = _rclone_local_root()
            if remote_root is not None:
                targets = [remote_root / e["local_path"] for e in assets_in]
                desktop = remote_root  # shared filesystem destination safety checks
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            errors.append(f"rclone_preflight_failed: {exc}")
    protected = [manifest, *local_paths, *targets]
    if out is not None and any(_same(Path(out), p) for p in protected):
        errors.append("output_aliases_input")
    for target in targets:
        if desktop is None or not _contained(desktop, target) or any(_same(target, p) for p in [manifest, *local_paths]):
            errors.append("destination_aliases_input_or_escapes_root")
    if len({str(p.resolve()) for p in local_paths}) != len(local_paths):
        errors.append("duplicate_local_path")
    code = 0 if not errors else 1
    if code == 0 and apply and _credentials(backend, drive_root) == "present":
        for entry, row in zip(assets_in, rows):
            if row["status"] != "match":
                continue
            try:
                row["drive_link"] = _copy(entry, root, backend, desktop)
                row["synced"] = True
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                errors.append(f"{row['id']}: sync_failed: {exc}")
                row["status"] = "error"
                code = 1
                break
    if out is not None and apply:
        for existing in read_paths:
            if _same(Path(out), existing):
                errors.append("output_aliases_input")
                code = 2
                break
        else:
            if code == 0:
                _write_report(Path(out), _report(apply, backend, root, drive_root, rows, errors))
    elif out is not None and any(_same(Path(out), existing) for existing in read_paths):
        errors.append("output_aliases_input")
        code = 2 if code == 0 else code

    report = _report(apply, backend, root, drive_root, rows, errors)
    for row in report["assets"]:
        if row["status"] in {"pass", "not_run"}:
            row["status"] = "error"
            report["errors"].append(f"{row['id']}: status_rejected")
            code = 1
    return code, report


def _report(apply: bool, backend: str, root: Path, drive_root: Path | None, rows: list[dict], errors: list[str]) -> dict:
    return {
        "dry_run": not apply,
        "backend": backend,
        "local_root": str(root),
        "store_root": LOCAL_ROOT,
        "credentials": _credentials(backend, drive_root) if backend in BACKENDS else "absent",
        "assets": rows,
        "errors": list(errors),
    }


def _rclone_local_root() -> Path | None:
    """Resolve local backend roots before writes; reject opaque filesystem wrappers."""
    remote = os.environ["AGR_RCLONE_REMOTE"].rstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_-]+:[^\n\r]*", remote):
        raise ValueError("AGR_RCLONE_REMOTE must name a configured remote:path")
    executable = which_rclone()
    if executable is None:
        raise ValueError("rclone unavailable")
    result = subprocess.run([executable, "backend", "features", remote],
                            capture_output=True, text=True, timeout=60, check=False)
    info = json.loads(result.stdout) if result.returncode == 0 else {}
    features = info.get("Features") if isinstance(info, dict) else None
    if not isinstance(features, dict) or type(features.get("IsLocal")) is not bool:
        raise ValueError("remote filesystem identity unavailable")
    if features.get("Overlay") or features.get("WrapFs"):
        raise ValueError("wrapped remote filesystems are unsupported")
    if not features["IsLocal"]:
        return None
    root = info.get("Root")
    if not isinstance(root, str) or not root:
        raise ValueError("local remote root unavailable")
    # rclone on Windows emits extended-length paths; normalize even absent targets.
    root = root.replace("\\", "/")
    if root.startswith("//?/UNC/"):
        root = "//" + root[8:]
    elif root.startswith("//?/"):
        root = root[4:]
    path = Path(root)
    if not path.is_absolute():
        raise ValueError("local remote root must be absolute")
    return path


def _copy(entry: dict, root: Path, backend: str, desktop: Path | None) -> str:
    """Copy verified bytes; never create public shares or replace remote versions."""
    source = root / entry["local_path"]
    # Recheck immediately before the side effect, not just during preflight.
    if _sha256(source) != entry["sha256"]:
        raise ValueError("sha256_mismatch before copy")
    if backend == "drive-desktop":
        target = desktop / entry["local_path"]
        if target.exists():
            if _sha256(target) != entry["sha256"]:
                raise ValueError("destination differs; use a new versioned path")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output, source.open("rb") as incoming:
                shutil.copyfileobj(incoming, output)
            if _sha256(target) != entry["sha256"]:
                target.unlink()
                raise ValueError("destination sha256_mismatch")
        # Desktop does not expose a trustworthy file-id API. No fabricated link.
        return PENDING
    remote = os.environ["AGR_RCLONE_REMOTE"].rstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_-]+:[^\n\r]*", remote):
        raise ValueError("AGR_RCLONE_REMOTE must name a configured remote:path")
    target = remote + ("" if remote.endswith(":") else "/") + entry["local_path"].replace("\\", "/")
    executable = which_rclone()
    if executable is None:
        raise ValueError("rclone unavailable")
    result = subprocess.run([executable, "copyto", "--ignore-existing", "--checksum", str(source), target],
                            capture_output=True, text=True, timeout=1800, check=False)
    if result.returncode:
        raise ValueError("rclone copyto failed")
    metadata = subprocess.run([executable, "lsjson", target, "--stat", "--hash", "--hash-type", "MD5"],
                              capture_output=True, text=True, timeout=60, check=False)
    # Drive supports MD5 for uploaded binaries. Fail closed if verification is
    # unavailable, including an existing different file skipped by copyto.
    info = json.loads(metadata.stdout) if metadata.returncode == 0 else {}
    with source.open("rb") as handle:
        md5 = hashlib.file_digest(handle, "md5").hexdigest()
    hashes = info.get("Hashes") if isinstance(info, dict) else None
    if not isinstance(info, dict) or not isinstance(hashes, dict) or info.get("Size") != source.stat().st_size or hashes.get("md5") != md5:
        raise ValueError("remote size/md5 mismatch or unavailable")
    # Never invoke `rclone link`: file-ID URLs retain existing access controls.
    file_id = info.get("ID")
    return f"https://drive.google.com/file/d/{file_id}/view" if isinstance(file_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", file_id) else PENDING


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(report, handle, indent=2)
        handle.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run the local asset store. Google Drive login is not performed.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=Path(LOCAL_ROOT))
    parser.add_argument("--backend", default="local", help="local, rclone, or drive-desktop")
    parser.add_argument("--apply", action="store_true", help="Mirror verified files and write --out on success. Default is dry-run.")
    parser.add_argument("--out", type=Path, help="Report path used only with --apply, and only when it is not an input.")
    parser.add_argument("--drive-root", type=Path, help="Existing Google Drive for desktop folder. Absent folder keeps links pending.")
    args = parser.parse_args(argv)
    code, report = execute(
        args.manifest,
        root=args.root,
        backend=args.backend,
        apply=args.apply,
        out=args.out,
        drive_root=args.drive_root,
    )
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
