"""new-case characterization of the synthetic development bundle validator.

Synthetic development findings never establish official package compliance or user acceptance.
This file exercises ``dt_ai.publish.bundle.read_bundle`` and the development
``validate(root, archive, out, blender=None)`` whose C001 check handles the bundle
read. It is not twinqa V001 and it is not a delivery gate.

Acceptance, for both a stored ZIP (method 0) and a deflated ZIP (method 8),
member ``a.bin`` = ``b'hi'``, built with ``struct`` and ``zlib``:

1. Clean archive -> ``read_bundle`` returns exactly ``{'a.bin': b'hi'}``.
2. The same readable archive, which has no manifest, -> ``validate`` gives C001
   fail identifying missing ``bundle-manifest.json``, and does not claim ZIP corruption.
3. A payload byte mutated without a CRC update -> direct ``read_bundle`` raises
   ``zipfile.BadZipFile``; ``validate`` returns exactly one C-prefixed check, C001
   fail, whose diagnostic contains ``CRC`` (the rest of the zipfile text is not pinned).
4. A damaged central-directory signature -> direct ``BadZipFile`` and C001 fail
   with a nonempty readable-bundle diagnostic.
5. Each early-failure report (cases 2, 3, 4, and the missing-path control) has
   ``development_checks_passed`` False and ``passed`` False, does not execute
   C002/C003/C004, leaves V001-V017 at the real ``not_run`` / ``review`` statuses,
   persists ``report.json`` that parses and agrees with the returned model, and
   writes ``report.html`` containing a failure notice.
6. One missing-path control: an archive path that does not exist -> an ``OSError``
   becomes that same C001 failure report. Existing input archive bytes are
   unchanged after ``validate``. Every case writes to its own new output directory.
7. An in-memory mutation that drops ``BadZipFile`` from the C001 ``except`` tuple
   makes the corrupted cases raise instead of producing C001. The tuple is a
   literal inside ``validate``, so the probe execs a source copy; nothing on disk
   is modified, and the installed function is unchanged afterwards.
"""

import inspect
import struct
import zlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pytest

from dt_ai.core.io import read_json
from dt_ai.core.models import ValidationReport
from dt_ai.publish.bundle import read_bundle
from dt_ai.validate.bundle import validate

MEMBER_NAME = "a.bin"
MEMBER_PAYLOAD = b"hi"
# Blocking delivery stages stay not_run; manual stages stay review. Those are the
# status names finish() records for V001-V017 on a synthetic development bundle.
EARLY_FAILURE_CHECKS = (
    ("C001", "fail"),
    ("V001", "not_run"),
    ("V002", "not_run"),
    ("V003", "not_run"),
    ("V004", "not_run"),
    ("V005", "not_run"),
    ("V006", "not_run"),
    ("V007", "not_run"),
    ("V008", "not_run"),
    ("V009", "not_run"),
    ("V010", "not_run"),
    ("V011", "not_run"),
    ("V012", "not_run"),
    ("V013", "not_run"),
    ("V014", "not_run"),
    ("V015", "review"),
    ("V016", "review"),
    ("V017", "review"),
)
_C001_EXCEPT = "except (ValueError, KeyError, OSError, TypeError, BadZipFile) as exc:"
_C001_EXCEPT_WITHOUT_BADZIPFILE = "except (ValueError, KeyError, OSError, TypeError) as exc:"
_FAILURE_NOTICE = "не завершены или есть ошибки"


def _zip_with_member(method: int) -> bytes:
    """One-member ZIP: local header, deflated or stored payload, central directory, EOCD."""
    name = MEMBER_NAME.encode("ascii")
    payload = MEMBER_PAYLOAD
    if method == 0:
        compressed = payload
        version = 10
    elif method == 8:
        compressor = zlib.compressobj(level=9, wbits=-15)
        compressed = compressor.compress(payload) + compressor.flush()
        version = 20
    else:
        raise ValueError(method)
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    local = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        version,
        0,
        method,
        0,
        0,
        crc,
        len(compressed),
        len(payload),
        len(name),
        0,
    ) + name + compressed
    central = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        version,
        version,
        0,
        method,
        0,
        0,
        crc,
        len(compressed),
        len(payload),
        len(name),
        0,
        0,
        0,
        0,
        0,
        0,
    ) + name
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(central), len(local), 0)
    return local + central + eocd


def _payload_span(blob: bytes) -> tuple[int, int]:
    name_len, extra_len = struct.unpack_from("<HH", blob, 26)
    compressed_size = struct.unpack_from("<I", blob, 18)[0]
    start = 30 + name_len + extra_len
    return start, compressed_size


def _crc_fields(blob: bytes) -> tuple[bytes, bytes]:
    local_crc = blob[14:18]
    central_at = _payload_span(blob)[0] + _payload_span(blob)[1]
    central_crc = blob[central_at + 16:central_at + 20]
    return local_crc, central_crc


def _mutate_payload_byte(blob: bytes) -> bytes:
    """Flip compressed-payload index 1. Leave both CRC fields as stored."""
    start, compressed_size = _payload_span(blob)
    assert compressed_size > 1
    mutated = bytearray(blob)
    mutated[start + 1] ^= 0x01
    assert _crc_fields(bytes(mutated)) == _crc_fields(blob)
    return bytes(mutated)


def _damage_central_directory_signature(blob: bytes) -> bytes:
    central_at = _payload_span(blob)[0] + _payload_span(blob)[1]
    assert blob[central_at:central_at + 4] == b"PK\x01\x02"
    damaged = bytearray(blob)
    damaged[central_at:central_at + 4] = b"\x00\x00\x00\x00"
    return bytes(damaged)


def _write_archive(tmp_path: Path, name: str, blob: bytes) -> Path:
    path = tmp_path / f"{name}.zip"
    path.write_bytes(blob)
    return path


def _fresh_output(tmp_path: Path, name: str) -> Path:
    output = tmp_path / name
    assert not output.exists()
    return output


def _assert_early_c001_report(report, output: Path) -> None:
    assert report.development_checks_passed is False
    assert report.passed is False
    assert [(check.id, check.status) for check in report.checks] == list(EARLY_FAILURE_CHECKS)
    c_checks = [check for check in report.checks if check.id.startswith("C")]
    assert [(check.id, check.status) for check in c_checks] == [("C001", "fail")]
    assert not any(check.id in {"C002", "C003", "C004"} for check in report.checks)
    finding = report.checks[0]
    assert finding.expected == "Readable development bundle"
    assert finding.observed.strip()
    persisted = ValidationReport.model_validate(read_json((output / "report.json").read_bytes()))
    assert persisted == report
    html = (output / "report.html").read_text(encoding="utf-8")
    assert _FAILURE_NOTICE in html
    assert not (output / "dcc-roundtrip.json").exists()


def _validate_unchanged(root: Path, archive: Path, output: Path, before: bytes):
    report = validate(root, archive, output, blender=None)
    assert archive.read_bytes() == before
    return report


@pytest.mark.parametrize("method", [0, 8], ids=["stored", "deflated"])
def test_clean_archive_reads_member_bytes(tmp_path, method):
    path = _write_archive(tmp_path, "clean", _zip_with_member(method))
    before = path.read_bytes()
    with ZipFile(path) as archive:
        assert archive.getinfo(MEMBER_NAME).compress_type == method
    assert read_bundle(path) == {MEMBER_NAME: MEMBER_PAYLOAD}
    assert path.read_bytes() == before


@pytest.mark.parametrize("method", [0, 8], ids=["stored", "deflated"])
def test_missing_manifest_is_c001_and_not_zip_corruption(root, tmp_path, method):
    path = _write_archive(tmp_path, "manifest-less", _zip_with_member(method))
    before = path.read_bytes()
    output = _fresh_output(tmp_path, f"manifest-less-report-{method}")
    report = _validate_unchanged(root, path, output, before)
    _assert_early_c001_report(report, output)
    observed = report.checks[0].observed.casefold()
    assert "bundle-manifest.json" in report.checks[0].observed
    assert "crc" not in observed
    assert "corrupt" not in observed
    assert "bad magic" not in observed


@pytest.mark.parametrize("method", [0, 8], ids=["stored", "deflated"])
def test_payload_byte_without_crc_update_is_c001(root, tmp_path, method):
    path = _write_archive(tmp_path, "bad-crc", _mutate_payload_byte(_zip_with_member(method)))
    before = path.read_bytes()
    with ZipFile(path) as archive:
        assert archive.getinfo(MEMBER_NAME).compress_type == method
    with pytest.raises(BadZipFile):
        read_bundle(path)
    assert path.read_bytes() == before
    output = _fresh_output(tmp_path, f"bad-crc-report-{method}")
    report = _validate_unchanged(root, path, output, before)
    _assert_early_c001_report(report, output)
    assert "crc" in report.checks[0].observed.casefold()


@pytest.mark.parametrize("method", [0, 8], ids=["stored", "deflated"])
def test_damaged_central_directory_signature_is_c001(root, tmp_path, method):
    path = _write_archive(tmp_path, "bad-cd", _damage_central_directory_signature(_zip_with_member(method)))
    before = path.read_bytes()
    assert struct.unpack_from("<H", before, 8)[0] == method
    with pytest.raises(BadZipFile):
        read_bundle(path)
    assert path.read_bytes() == before
    output = _fresh_output(tmp_path, f"bad-cd-report-{method}")
    report = _validate_unchanged(root, path, output, before)
    _assert_early_c001_report(report, output)
    assert report.checks[0].observed.strip()
    assert report.checks[0].expected == "Readable development bundle"


def test_missing_archive_path_is_c001(root, tmp_path):
    archive = tmp_path / "missing-archive" / "absent.zip"
    assert not archive.exists()
    output = _fresh_output(tmp_path, "missing-path-report")
    report = validate(root, archive, output, blender=None)
    assert not archive.exists()
    _assert_early_c001_report(report, output)
    assert isinstance(report.checks[0].observed, str) and report.checks[0].observed.strip()


def test_dropping_badzipfile_from_c001_except_lets_corruption_escape(root, tmp_path):
    """Exec a copy of validate() whose C001 handler no longer names BadZipFile.

    The except tuple is a literal, so it cannot be wrapped in place. The copy
    lives only in this process. The module function and its source file stay
    as they were.
    """
    source_path = Path(inspect.getsourcefile(validate))
    disk_before = source_path.read_bytes()
    installed = validate
    source = inspect.getsource(validate)
    assert source.count(_C001_EXCEPT) == 1
    mutated_source = source.replace(_C001_EXCEPT, _C001_EXCEPT_WITHOUT_BADZIPFILE, 1)
    assert "BadZipFile" not in mutated_source
    namespace = dict(validate.__globals__)
    exec(compile(mutated_source, "<c001-except-mutation>", "exec"), namespace)
    mutated = namespace["validate"]
    assert mutated is not installed
    try:
        for method in (0, 8):
            clean = _zip_with_member(method)
            damaged = {
                "crc": _mutate_payload_byte(clean),
                "central-directory": _damage_central_directory_signature(clean),
            }
            for label, blob in damaged.items():
                archive = _write_archive(tmp_path, f"mut-{label}-{method}", blob)
                before = archive.read_bytes()
                output = _fresh_output(tmp_path, f"mut-{label}-{method}-report")
                with pytest.raises(BadZipFile):
                    mutated(root, archive, output, blender=None)
                assert not (output / "report.json").exists()
                assert archive.read_bytes() == before
        # KeyError is still inside the copied tuple, so a readable manifest-less
        # archive still becomes C001. That pins the edit to BadZipFile.
        readable = _write_archive(tmp_path, "mut-manifest-less", _zip_with_member(0))
        manifest_output = _fresh_output(tmp_path, "mut-manifest-less-report")
        manifest_report = mutated(root, readable, manifest_output, blender=None)
        _assert_early_c001_report(manifest_report, manifest_output)
        restored_archive = _write_archive(tmp_path, "restored-crc", _mutate_payload_byte(_zip_with_member(0)))
        restored_before = restored_archive.read_bytes()
        restored_output = _fresh_output(tmp_path, "restored-crc-report")
        restored = _validate_unchanged(root, restored_archive, restored_output, restored_before)
        _assert_early_c001_report(restored, restored_output)
        assert "crc" in restored.checks[0].observed.casefold()
    finally:
        assert validate is installed
        assert source_path.read_bytes() == disk_before
