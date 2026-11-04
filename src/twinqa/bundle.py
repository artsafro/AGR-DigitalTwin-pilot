# Ported from AGR src/dt_ai/publish/bundle.py (sha256 0d190a116dd4) on 2026-10-06;
# changes: read_bundle only (package() dropped), BundleError, caller-supplied uncompressed
# limit, CRC check, directory entries skipped; size_finding() moved here from the previous
# tools/qa/validate_package.py; conflict #12 decided 2026-10-07 [D015] (binary units).
"""Safe ZIP reading (no extraction of archive-controlled paths) and archive size rules."""
import zipfile
from pathlib import PurePosixPath


class BundleError(ValueError):
    def __init__(self, message: str, member: str | None = None):
        super().__init__(message)
        self.member = member


def _member_text(exc: UnicodeDecodeError) -> str:
    raw = exc.object
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).decode("utf-8", errors="backslashreplace")
    if isinstance(raw, str):
        return raw
    return ""


def _decode_error(prefix: str, exc: UnicodeDecodeError, member: str | None = None) -> BundleError:
    shown = member if member is not None else _member_text(exc)
    return BundleError(f"{prefix}: member {shown}: {type(exc).__name__}: {exc}", member=shown)


def read_bundle(path, max_uncompressed: int) -> dict[str, bytes]:
    """Return {member: bytes}. Rejects broken ZIPs, unsafe paths, duplicates, oversize content."""
    try:
        archive = zipfile.ZipFile(path)
    except UnicodeDecodeError as exc:
        raise _decode_error("Not a readable ZIP", exc) from exc
    except (zipfile.BadZipFile, OSError) as exc:
        raise BundleError(f"Not a readable ZIP: {exc}") from exc
    with archive:
        try:
            infos = [x for x in archive.infolist() if not x.is_dir()]
        except UnicodeDecodeError as exc:
            raise _decode_error("Not a readable ZIP", exc) from exc
        names = [x.filename for x in infos]
        if len(names) != len(set(names)):
            raise BundleError("Duplicate ZIP members")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
                raise BundleError(f"Unsafe ZIP path: {name}")
        total = sum(x.file_size for x in infos)
        if total > max_uncompressed:
            raise BundleError(f"Uncompressed content {total} B exceeds safety limit {max_uncompressed} B")
        try:
            return {name: archive.read(name) for name in names}
        except UnicodeDecodeError as exc:
            raw = _member_text(exc)
            shown = raw
            for name in names:
                try:
                    archive.read(name)
                except UnicodeDecodeError:
                    shown = name
                    break
            text = f"Broken ZIP member: member {shown}"
            if raw and raw != shown:
                text += f" local {raw}"
            raise BundleError(f"{text}: {type(exc).__name__}: {exc}", member=shown) from exc
        except (zipfile.BadZipFile, OSError, EOFError) as exc:  # CRC errors, truncated members
            raise BundleError(f"Broken ZIP member: {exc}") from exc


def size_status(size_bytes: int, limit_bytes: int) -> tuple[str, str]:
    """Limits are binary bytes (MiB/GiB), as SINTEZ AGR Checker (conflict #12, decided 2026-10-07 [D015])."""
    label = f"{limit_bytes / 1024 ** 2:g} MiB"
    if size_bytes > limit_bytes:
        return "fail", f"{size_bytes} B exceeds {label}"
    return "pass", f"{size_bytes} B <= {label}"
