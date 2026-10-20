"""new-case: atomic visual-review publication, verdicts and protected scratch cleanup (#348).

Publishes a 3ds Max scene under C:/x/review/<YYYY-MM-DD>/<task>-<slug>/,
appends C:/x/review/pending.json, records a verdict, and lists old scratch
directories without touching the review store or library directories.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

REVIEW_ROOT = Path("C:/x/review")
SCRATCH_ROOT = Path("C:/x")
FLORA_LIBRARY = Path("C:/x/flora-library")
REPO = Path(__file__).resolve().parents[2]

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_CANDIDATE = re.compile(r"^(?:t_.+|ci-receipt-.+)$", re.IGNORECASE)
_GROUND = re.compile(r"(^|[_\-])ground([_\-.]|$)", re.IGNORECASE)
_REPARSE = 0x400


class ReviewError(Exception):
    """Fail closed: the review store and the inputs stay unchanged."""


def default_manifests() -> list[Path]:
    library = REPO / "library"
    if not library.is_dir():
        return []
    return sorted(path for path in library.rglob("*.json") if path.is_file())


def publish(*, task, slug, source, what, pngs, review_root, adapter, today) -> int:
    task_n = _parse_task(task)
    slug_s = _parse_slug(slug)
    what_s = _parse_what(what)
    source_p = _check_source(Path(source))
    png_paths = [_check_png(Path(path)) for path in pngs]
    if len({path.name.casefold() for path in png_paths}) != len(png_paths):
        raise ReviewError("duplicate preview names")

    root = Path(review_root)
    _check_ancestors(root)
    folder = root / today.isoformat() / f"{task_n}-{slug_s}"
    scene = folder / f"{task_n}-{slug_s}.max"
    readme = folder / "README.txt"
    copied = [folder / path.name for path in png_paths]
    preview = folder / "preview.png"
    outputs = [scene, readme, *copied]
    if not png_paths:
        outputs.append(preview)
    for output in outputs:
        if not _within(output, root):
            raise ReviewError("path outside C:/x/review")
    pending = root / "pending.json"
    for output in outputs + [pending]:
        _check_ancestors(output)
    inputs = [source_p, *png_paths]
    if any(_same(output, item) for output in outputs + [pending] for item in inputs):
        raise ReviewError("output path resolves to an input")
    # Windows readers can deny atomic replacement while their handle is open.
    # Serialize preflight reads as well as read-modify-write transactions.
    if pending.exists():
        with _store_lock(root):
            _read_pending(pending)
    if folder.exists() or any(path.exists() for path in outputs):
        raise ReviewError("review folder already exists")

    work = Path(tempfile.mkdtemp(prefix="agr-review-"))
    created = False
    try:
        max_tmp = work / scene.name
        preview_tmp = None if png_paths else work / "preview.png"
        try:
            info = adapter.build(source_p.resolve(), max_tmp, preview_tmp)
        except ReviewError:
            raise
        except Exception as exc:
            raise ReviewError(f"adapter failed: {exc}") from exc
        version, cameras, materials = _adapter_result(info)
        if not max_tmp.is_file() or max_tmp.stat().st_size == 0:
            raise ReviewError("adapter wrote no scene")
        if preview_tmp is not None and (not preview_tmp.is_file() or preview_tmp.stat().st_size == 0):
            raise ReviewError("adapter wrote no preview")
        try:
            folder.mkdir(parents=True, exist_ok=False)
            created = True
            os.replace(max_tmp, scene)
            if preview_tmp is not None:
                os.replace(preview_tmp, preview)
            for src, dest in zip(png_paths, copied):
                shutil.copyfile(src, dest)
            readme.write_text(
                _readme(what_s, version, cameras, materials, task_n, slug_s, today.isoformat()),
                encoding="utf-8",
                newline="\n",
            )
            with _store_lock(root):
                rows = _read_pending(pending)
                rows.append({"task": f"#{task_n}", "path": scene.resolve().as_posix(), "what": what_s})
                _atomic_write_json(pending, rows)
        except Exception as exc:
            if created and folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            day = folder.parent
            try:
                if day.exists() and day != root and not any(day.iterdir()):
                    day.rmdir()
            except OSError:
                pass
            if isinstance(exc, ReviewError):
                raise
            raise ReviewError(f"pending.json was not updated: {exc}") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


def verdict(*, task, status, note, review_root) -> int:
    task_n = _parse_task(task)
    status_s = _parse_status(status)
    note_s = _parse_note(note)
    pending = Path(review_root) / "pending.json"
    _check_ancestors(pending)
    key = f"#{task_n}"
    if not pending.exists():
        raise ReviewError(f"unknown task {key}")
    with _store_lock(pending.parent):
        entries = _read_pending(pending)
        if not any(row.get("task") == key for row in entries):
            raise ReviewError(f"unknown task {key}")
        for row in entries:
            if row.get("task") == key:
                row["status"] = status_s
                row["note"] = note_s
        _atomic_write_json(pending, entries)
    return 0


def cleanup(*, days, scratch, manifests, now: datetime, apply: bool) -> list[Path]:
    limit = _parse_days(days)
    root = Path(scratch)
    protected = _protected_dirs(root, manifests)
    if not root.is_dir():
        return []
    now_ts = now.timestamp()
    scratch_key = os.path.normcase(os.path.abspath(root))
    guard_keys = _guard_keys(protected)
    chosen: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if not child.is_dir() or not _CANDIDATE.match(child.name):
            continue
        if _blocked_key(child, scratch_key, guard_keys):
            continue
        age = now_ts - child.stat().st_mtime
        if not age > limit + 0.05:
            continue
        chosen.append(child)
    if apply:
        for child in chosen:
            if _blocked_key(child, scratch_key, guard_keys):
                raise ReviewError("refusing to delete a protected path")
            if _reparse(child) or os.path.normcase(os.path.abspath(child.parent)) != scratch_key:
                raise ReviewError("refusing to delete a path outside the scratch root")
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    return chosen


def _parse_task(task) -> str:
    text = str(task).strip()
    if text.startswith("#"):
        text = text[1:].strip()
    if text.casefold() in {"nan", "inf", "+inf", "-inf", "infinity"}:
        raise ReviewError("task must be a positive integer")
    if not re.fullmatch(r"[1-9][0-9]{0,8}", text):
        raise ReviewError("task must be a positive integer")
    return text


def _parse_slug(slug) -> str:
    text = str(slug)
    if text != text.strip() or not _SLUG.fullmatch(text) or text in _RESERVED or len(text) > 64:
        raise ReviewError("slug is not a single review folder name")
    return text


def _parse_what(what) -> str:
    if not isinstance(what, str) or "\n" in what or "\r" in what:
        raise ReviewError("what must be one non-empty line")
    text = what.strip()
    if not text or text.casefold() in {"nan", "inf", "+inf", "-inf", "infinity"}:
        raise ReviewError("what must be one non-empty line")
    return text


def _parse_note(note) -> str:
    if not isinstance(note, str) or "\n" in note or "\r" in note:
        raise ReviewError("note must be one non-empty line")
    text = note.strip()
    if not text:
        raise ReviewError("note must be one non-empty line")
    return text


def _parse_status(status) -> str:
    if status not in {"ok", "changes"}:
        raise ReviewError("status must be ok or changes")
    return status


def _parse_days(days) -> float:
    if isinstance(days, bool) or not isinstance(days, (int, float)) or not math.isfinite(days) or days <= 0:
        raise ReviewError("days must be a finite number greater than 0")
    return float(days) * 86400.0


def _check_source(path: Path) -> Path:
    if path.suffix.casefold() not in {".fbx", ".max"}:
        raise ReviewError("unsupported source")
    if not path.is_file():
        raise ReviewError("missing source")
    if path.stat().st_size == 0:
        raise ReviewError("empty source")
    return path


def _check_png(path: Path) -> Path:
    if path.suffix.casefold() != ".png" or not path.is_file() or path.stat().st_size == 0:
        raise ReviewError("missing preview png")
    return path


def _adapter_result(info) -> tuple[str, int, int]:
    if not isinstance(info, dict):
        raise ReviewError("adapter returned no scene report")
    version = info.get("version")
    cameras = info.get("cameras")
    materials = info.get("materials")
    if not isinstance(version, str) or not version.strip():
        raise ReviewError("max version missing")
    if type(cameras) is not int or cameras < 1:
        raise ReviewError("no camera")
    if type(materials) is not int or materials < 1:
        raise ReviewError("no materials")
    return version.strip(), cameras, materials


def _readme(what: str, version: str, cameras: int, materials: int, task: str, slug: str, day: str) -> str:
    return (
        "What to look at:\n"
        f"{what}\n\n"
        "Acceptance points:\n"
        "- The scene opens in 3ds Max with the imported materials kept.\n"
        "- At least one camera frames the model.\n"
        "- Units are 1 unit = 1 m, scale 1:1.\n"
        "- Coordinates stay as imported (Z-up). NPM geometry is in MSK Moscow coordinates "
        "with project heights. VPM origin is 0,0,0 per file; the MSK-77 insertion point "
        "stays in GeoJSON and is not applied in this review scene.\n\n"
        "Units: 1 unit = 1 m; scale 1:1.\n"
        "Coordinate system: Z-up, metres. Do not mix MSK Moscow coordinates with a local VPM origin.\n"
        f"3ds Max: {version}\n"
        f"Cameras: {cameras}\n"
        f"Materials: {materials}\n"
        f"Folder: C:/x/review/{day}/{task}-{slug}/ (issue #348)\n"
    )


def _read_pending(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys, parse_constant=_invalid_constant)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReviewError("malformed pending.json") from exc
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ReviewError("malformed pending.json")
    return data


def _atomic_write_json(path: Path, data) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="pending-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _invalid_constant(value):
    raise ValueError(f"non-finite JSON value: {value}")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _check_ancestors(path):
    for ancestor in [path, *path.parents]:
        if ancestor.is_symlink() or (ancestor.exists() and _reparse(ancestor)):
            raise ReviewError("reparse path outside C:/x/review")


@contextmanager
def _store_lock(root):
    """Serialize read-modify-replace across processes; stale locks fail closed."""
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".pending-lock"
    deadline = time.monotonic() + 30
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ReviewError("review store is busy; inspect stale .pending-lock")
            time.sleep(0.02)
    try:
        yield
    finally:
        lock.rmdir()


def _same(left: Path, right: Path) -> bool:
    if left.exists() and right.exists() and os.path.samefile(left, right):
        return True
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _within(path: Path, root: Path) -> bool:
    child = os.path.normcase(str(path.resolve()))
    parent = os.path.normcase(str(root.resolve()))
    if child == parent:
        return True
    prefix = parent if parent.endswith(os.sep) else parent + os.sep
    return child.startswith(prefix)


def _reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attrs = getattr(path.lstat(), "st_file_attributes", 0) or 0
    except OSError:
        return True
    return bool(attrs & _REPARSE)


def _protected_dirs(scratch: Path, manifests) -> list[Path]:
    guards = [scratch / "review", scratch / "flora-library", REVIEW_ROOT, FLORA_LIBRARY]
    for manifest in manifests:
        guards.extend(_manifest_dirs(Path(manifest), scratch))
    return guards


def _manifest_dirs(manifest: Path, scratch: Path) -> list[Path]:
    """Ground directories and any other library path named by a manifest.

    A path that is the scratch root itself is not a guard: that would block every candidate.
    """
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"malformed library manifest: {manifest}") from exc
    found = []
    scratch_key = os.path.normcase(os.path.abspath(scratch))
    for text in _strings(data):
        if not isinstance(text, str):
            continue
        bare = "/" not in text and "\\" not in text and not (len(text) > 1 and text[1] == ":")
        if bare:
            # A bare asset name ("model.max", "textures") is relative to the
            # manifest directory, even when the file is already gone (fail-safe:
            # a suffix marks it as a file name); other bare words are not paths.
            candidate = manifest.parent / text
            if not text.strip() or text in (".", "..") or not (candidate.exists() or Path(text).suffix):
                continue
        path = Path(text)
        if not path.is_absolute():
            path = manifest.parent / path
        # Resolve absolute aliases too: a library may be reached via a Windows
        # directory junction while its physical directory has a scratch name.
        path = path.resolve()
        acc: list[str] = []
        for part in path.parts:
            acc.append(part)
            if _GROUND.search(part):
                found.append(Path(*acc))
                break
        if path.is_absolute():
            library = path.parent if path.suffix else path
            library_key = os.path.normcase(os.path.abspath(library))
            if library_key != scratch_key and _within(library, scratch):
                found.append(library)
    return found


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
        for key in node:
            if isinstance(key, str):
                yield key
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)


def _guard_keys(protected: list[Path]) -> list[str]:
    keys = []
    for guard in protected:
        key = os.path.normcase(os.path.abspath(guard))
        if key.endswith(os.sep):
            key = key[:-1]
        keys.append(key)
    return keys


def _blocked_key(child: Path, scratch_key: str, guard_keys: list[str]) -> bool:
    if _reparse(child):
        return True
    try:
        resolved = os.path.normcase(os.path.abspath(child))
    except OSError:
        return True
    if os.path.dirname(resolved) != scratch_key:
        return True
    child_prefix = resolved + os.sep
    for key in guard_keys:
        if resolved == key or child_prefix.startswith(key + os.sep) or (key + os.sep).startswith(child_prefix):
            return True
    return False
