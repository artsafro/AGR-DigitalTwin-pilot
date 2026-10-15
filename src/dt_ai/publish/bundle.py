from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


def _validate_member_names(names):
    seen = set()
    for name in names:
        p = PurePosixPath(name)
        if not name or "\x00" in name or p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
            raise ValueError("Unsafe ZIP path")
        key = name.casefold()
        if key in seen:
            raise ValueError("Duplicate ZIP members")
        seen.add(key)


def package(files: dict[str, bytes], output: Path):
    _validate_member_names(files)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, files[name])


def read_bundle(path: Path):
    """Read without extracting user-controlled archive paths."""
    with ZipFile(path) as archive:
        infos = archive.infolist()
        # ZipInfo.filename normalizes backslashes on Windows; validate raw names.
        names = [x.orig_filename for x in infos]
        _validate_member_names(names)
        if sum(x.file_size for x in infos) > 256_000_000:
            raise ValueError("Development bundle exceeds 256 MB uncompressed safety limit")
        return {name: archive.read(name) for name in names}
