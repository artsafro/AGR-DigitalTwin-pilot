"""Handled ZIP CRC and central-directory controls for V001 (PKG-01 / PKG-02).

Pattern: n/a | new-case: ZIP V001 handled CRC/central-directory controls

Inventory of tests/ (read_bundle, BundleError, "Broken ZIP", CRC): nothing in QA
calls twinqa.bundle.read_bundle or BundleError, and nothing mentions a broken ZIP
member or a damaged central directory. CRC appears only as a PNG IDAT check in
tests/qa/test_png_fixed_field_errors.py. tests/test_bundle_package_safety.py and
tests/integration/test_pipeline.py call dt_ai.publish.bundle.read_bundle for
unsafe paths, duplicates and empty archives. tests/qa/test_validator.py covers
unsafe ZIP paths and archive composition. new-case: this module is the QA
coverage for the reader wrappers that already exist.

These are GREEN characterization tests of the unchanged code. read_bundle already
wraps ZipFile() failures as BundleError("Not a readable ZIP: ...") and
archive.read failures as BundleError("Broken ZIP member: ..."); validate()
already turns that BundleError into one V001 finding named ZIP.

Acceptance
----------
| Case | Fixture | read_bundle | validate / CLI |
| clean stored and deflated | one member a.bin, payload b'hi'; struct local header, central directory and EOCD; date_time 1980-01-01; external attr 0; deflate via zlib.compressobj(6, DEFLATED, -15) | exactly {'a.bin': b'hi'}; file hash unchanged | not a passing delivery; V001 has no finding named ZIP |
| bad CRC | stored: first payload byte flipped, CRC fields unchanged; deflated: body is deflate(b'hj'), CRC fields still crc32(b'hi') | BundleError startswith 'Broken ZIP member:', cause BadZipFile | V001 status fail, exactly one finding named ZIP (status fail); exit code 1 |
| central-directory signature | first byte of the central-directory signature flipped (stored and deflated) | BundleError startswith 'Not a readable ZIP:', cause BadZipFile | same V001 ZIP fail |
| EOCD central-directory size + 1 | 110-byte stored fixture; uint32 at offset 100 set to 52 | on this Python, ZipFile() fails at open, so the 'Not a readable ZIP:' branch | same V001 ZIP fail |
| fresh process | both malformed inputs, no --scene | (see the two branches above) | exit 1; stdout JSON; V001 ZIP fail; stderr empty; scene stage not executed |

Out of scope: encrypted and unsupported-method handling, unfinished-deflate XOR,
size / codec / permission policy, Proposal 1.
"""
import hashlib
import json
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

import validate_package as vp
from twinqa.bundle import BundleError, read_bundle
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
REPO = Path(__file__).resolve().parents[2]
NAME = b"a.bin"
PAYLOAD = b"hi"
# ZipInfo default date_time (1980, 1, 1, 0, 0, 0) as a DOS date; time is 0.
DOS_TIME = 0
DOS_DATE = (1 << 5) | 1
VERSION = 20  # ZipInfo create_version / extract_version; create_system stays 0
EXTERNAL_ATTR = 0
MAX_UNCOMPRESSED = 4 * 10**9
METHODS = ("stored", "deflated")


def _deflate(payload: bytes) -> bytes:
    compressor = zlib.compressobj(6, zlib.DEFLATED, -15)
    return compressor.compress(payload) + compressor.flush()


def _body(method: str, payload: bytes) -> tuple[int, bytes]:
    if method == "stored":
        return 0, payload
    if method == "deflated":
        return 8, _deflate(payload)
    raise ValueError(method)


def zip_bytes(method: str, payload: bytes = PAYLOAD, *, crc_of: bytes | None = None) -> bytes:
    """One-member ZIP packed with struct. zipfile does not write this buffer."""
    method_id, body = _body(method, payload)
    crc = zlib.crc32(payload if crc_of is None else crc_of) & 0xFFFFFFFF
    local = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        VERSION,
        0,
        method_id,
        DOS_TIME,
        DOS_DATE,
        crc,
        len(body),
        len(payload),
        len(NAME),
        0,
    ) + NAME + body
    central = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        VERSION,
        VERSION,
        0,
        method_id,
        DOS_TIME,
        DOS_DATE,
        crc,
        len(body),
        len(payload),
        len(NAME),
        0,
        0,
        0,
        0,
        EXTERNAL_ATTR,
        0,
    ) + NAME
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(central), len(local), 0)
    return local + central + eocd


def crc_fields(blob: bytes) -> tuple[bytes, bytes]:
    """CRC bytes in the local header and the central-directory header."""
    name_len, = struct.unpack_from("<H", blob, 26)
    comp_size, = struct.unpack_from("<I", blob, 18)
    central_at = 30 + name_len + comp_size
    return blob[14:18], blob[central_at + 16:central_at + 20]


def bad_crc_bytes(method: str) -> bytes:
    """CRC fields stay those of b'hi'. Stored flips the payload byte in place.

    Deflated swaps in deflate(b'hj') and keeps crc32(b'hi'), so inflation finishes
    and the reader fails the CRC check.
    """
    clean = zip_bytes(method)
    if method == "stored":
        damaged = bytearray(clean)
        assert damaged[35:37] == PAYLOAD
        damaged[35] ^= 0x01
        damaged = bytes(damaged)
    else:
        damaged = zip_bytes(method, b"hj", crc_of=PAYLOAD)
    assert crc_fields(damaged) == crc_fields(clean)
    return damaged


def damage_central_directory_signature(method: str) -> bytes:
    blob = bytearray(zip_bytes(method))
    _, body = _body(method, PAYLOAD)
    central_at = 30 + len(NAME) + len(body)
    assert blob[central_at:central_at + 4] == b"PK\x01\x02"
    blob[central_at] ^= 0xFF
    return bytes(blob)


def damage_eocd_central_directory_size() -> bytes:
    """Report mutation: stored fixture is 110 bytes; EOCD size at offset 100 becomes 52.

    On CPython 3.14 the size is also how ZipFile infers where the central directory
    starts (location - size - offset). size+1 shifts that start by one byte, ZipFile()
    raises BadZipFile before any member is read, and read_bundle takes the
    'Not a readable ZIP:' branch. This is not forced: it is what this interpreter does.
    """
    blob = bytearray(zip_bytes("stored"))
    assert len(blob) == 110
    assert blob[88:92] == b"PK\x05\x06"
    assert struct.unpack_from("<I", blob, 100)[0] == 51
    struct.pack_into("<I", blob, 100, 52)
    return bytes(blob)


MALFORMED = {
    "bad-crc-stored": lambda: bad_crc_bytes("stored"),
    "bad-crc-deflated": lambda: bad_crc_bytes("deflated"),
    "cd-signature-stored": lambda: damage_central_directory_signature("stored"),
    "cd-signature-deflated": lambda: damage_central_directory_signature("deflated"),
    "eocd-cd-size-plus-one": damage_eocd_central_directory_size,
}


def write_zip(tmp_path: Path, blob: bytes) -> Path:
    path = tmp_path / "member.zip"
    path.write_bytes(blob)
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_v001_zip_fail(report) -> None:
    v001 = next(stage for stage in report.stages if stage.id == "V001")
    assert v001.status == "fail"
    assert [(finding.name, finding.status) for finding in v001.findings] == [("ZIP", "fail")]
    assert report.exit_code == 1


def assert_open_error(path: Path, prefix: str) -> None:
    with pytest.raises(BundleError) as caught:
        read_bundle(path, max_uncompressed=MAX_UNCOMPRESSED)
    error = caught.value
    assert str(error).startswith(prefix)
    assert type(error.__cause__) is zipfile.BadZipFile


@pytest.mark.parametrize("method", METHODS)
def test_clean_read_bundle(tmp_path, method):
    path = write_zip(tmp_path, zip_bytes(method))
    digest = sha256(path)
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("a.bin")
        assert archive.read("a.bin") == PAYLOAD
        assert info.date_time == (1980, 1, 1, 0, 0, 0)
        assert info.external_attr == EXTERNAL_ATTR
    assert sha256(path) == digest
    assert read_bundle(path, max_uncompressed=MAX_UNCOMPRESSED) == {"a.bin": b"hi"}
    assert sha256(path) == digest


@pytest.mark.parametrize("method", METHODS)
def test_clean_archive_is_not_a_passing_delivery(tmp_path, method):
    path = write_zip(tmp_path, zip_bytes(method))
    digest = sha256(path)
    report = vp.validate(path, "vpm", PROFILES, scene=False)
    assert sha256(path) == digest
    assert report.passed is False
    v001 = next(stage for stage in report.stages if stage.id == "V001")
    assert v001.status == "fail"
    assert all(finding.name != "ZIP" for finding in v001.findings)
    assert any(finding.status == "fail" for finding in v001.findings)


@pytest.mark.parametrize("method", METHODS)
def test_bad_crc_is_broken_member_and_v001_zip(tmp_path, method):
    path = write_zip(tmp_path, bad_crc_bytes(method))
    digest = sha256(path)
    assert_open_error(path, "Broken ZIP member:")
    assert sha256(path) == digest
    report = vp.validate(path, "vpm", PROFILES, scene=False)
    assert sha256(path) == digest
    assert_v001_zip_fail(report)


@pytest.mark.parametrize("method", METHODS)
def test_central_directory_signature_is_not_readable_and_v001_zip(tmp_path, method):
    path = write_zip(tmp_path, damage_central_directory_signature(method))
    digest = sha256(path)
    assert_open_error(path, "Not a readable ZIP:")
    assert sha256(path) == digest
    report = vp.validate(path, "vpm", PROFILES, scene=False)
    assert sha256(path) == digest
    assert_v001_zip_fail(report)


def test_eocd_central_directory_size_plus_one_is_not_readable_and_v001_zip(tmp_path):
    path = write_zip(tmp_path, damage_eocd_central_directory_size())
    digest = sha256(path)
    assert_open_error(path, "Not a readable ZIP:")
    assert sha256(path) == digest
    report = vp.validate(path, "vpm", PROFILES, scene=False)
    assert sha256(path) == digest
    assert_v001_zip_fail(report)


@pytest.mark.parametrize("case", list(MALFORMED))
def test_cli_malformed_zip_exits_1_with_v001_zip(tmp_path, case):
    path = write_zip(tmp_path, MALFORMED[case]())
    digest = sha256(path)
    command = [
        sys.executable,
        "tools/qa/validate_package.py",
        str(path),
        "--profile",
        "vpm",
        "--json",
    ]
    assert "--scene" not in command
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        cwd=REPO,
        check=False,
    )
    assert sha256(path) == digest
    assert completed.returncode == 1
    assert completed.stderr == ""
    report = json.loads(completed.stdout)
    stages = {stage["id"]: stage for stage in report["stages"]}
    assert stages["V001"]["status"] == "fail"
    assert [(finding["name"], finding["status"]) for finding in stages["V001"]["findings"]] == [("ZIP", "fail")]
    assert stages["V003"]["status"] == "not_run"
    assert stages["V003"]["findings"] == []
    assert all("scene readback" not in note and "Blender" not in note for note in report["notes"])
