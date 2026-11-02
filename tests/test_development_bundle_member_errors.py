"""new-case: C001 member-exception escapes on synthetic development bundles.

Scope: the frozen one-member ZIP corpus (stored, deflated, bad CRC, encrypted
flag bit 0, compression method 1) through ``dt_ai.publish.bundle.read_bundle``,
``dt_ai.validate.bundle.validate(..., blender=None)`` and a fresh-process
``dt validate`` CLI. This pins today's observed behavior ONLY, not a desired
encryption/compression policy; an explicit user-approved future wrap may
deliberately update these witnesses; synthetic evidence never establishes
official package compliance.

baseline characterization, no historical RED. RED step: this module did not
exist, so the affected-test count before it was 0. The new tests pass on the
current production code; no historical failing revision is claimed.
"""

import hashlib
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

import dt_ai.validate.bundle as validate_bundle
from dt_ai.publish.bundle import read_bundle
from dt_ai.validate.bundle import validate

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b"hi"
GOOD_CRC = zlib.crc32(PAYLOAD) & 0xFFFFFFFF
BAD_CRC = (~GOOD_CRC) & 0xFFFFFFFF
LOCAL_SIG = b"PK\x03\x04"
CENTRAL_SIG = b"PK\x01\x02"

# Frozen synthetic bytes and SHA-256 from the C001 member-error report.
FROZEN_HEX = {
    "stored-a-bin": (
        "504b03041400000000000000215cac2a93d8020000000200000005000000612e62696e6869"
        "504b010214001400000000000000215cac2a93d802000000020000000500000000000000"
        "00000000800100000000612e62696e504b0506000000000100010033000000250000000000"
    ),
    "deflated-a-bin": (
        "504b03041400000008000000215cac2a93d8040000000200000005000000612e62696ecbc80400"
        "504b010214001400000008000000215cac2a93d804000000020000000500000000000000"
        "00000000800100000000612e62696e504b0506000000000100010033000000270000000000"
    ),
    "bad-crc": (
        "504b03041400000000000000215c53d56c27020000000200000005000000612e62696e6869"
        "504b010214001400000000000000215c53d56c2702000000020000000500000000000000"
        "00000000800100000000612e62696e504b0506000000000100010033000000250000000000"
    ),
    "flag-bit0-encrypted-no-password": (
        "504b03041400010000000000215cac2a93d8020000000200000005000000612e62696e6869"
        "504b010214001400010000000000215cac2a93d802000000020000000500000000000000"
        "00000000800100000000612e62696e504b0506000000000100010033000000250000000000"
    ),
    "method-1-local-and-central": (
        "504b03041400000001000000215cac2a93d8020000000200000005000000612e62696e6869"
        "504b010214001400000001000000215cac2a93d802000000020000000500000000000000"
        "00000000800100000000612e62696e504b0506000000000100010033000000250000000000"
    ),
}
FROZEN_SHA256 = {
    "stored-a-bin": "02fc9aed515b0c187fd6c267773e14725f47eb1fc86572c71233058f31c857af",
    "deflated-a-bin": "ab9860e6d351c30c06214c44cfdc2136de0d31373ade8145ae0aabd82a654056",
    "bad-crc": "025ae2b05ddeba0e5196a973a8c3b51ca9646e9757db92ba09bdcdbe9db9ae2f",
    "flag-bit0-encrypted-no-password": "39ca305de460274e79ecc75915625a4d6f067037e02fb9a89fb0b12d4682b50d",
    "method-1-local-and-central": "a78539b40a95921e9705856920d2ad721cbabc1d1f5cfc95811b10727fe49a57",
}
# Local flag/method, then central flag/method.
HEADER_FIELDS = {
    "stored-a-bin": (0, 0, 0, 0),
    "deflated-a-bin": (0, 8, 0, 8),
    "bad-crc": (0, 0, 0, 0),
    "flag-bit0-encrypted-no-password": (1, 0, 1, 0),
    "method-1-local-and-central": (0, 1, 0, 1),
}


@pytest.fixture(autouse=True)
def _no_blender(monkeypatch):
    monkeypatch.delenv("DT_BLENDER", raising=False)


def _frozen_blob(name: str) -> bytes:
    blob = bytes.fromhex(FROZEN_HEX[name])
    assert hashlib.sha256(blob).hexdigest() == FROZEN_SHA256[name]
    return blob


def _archive(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.zip"
    assert not path.exists()
    path.write_bytes(_frozen_blob(name))
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preserving(archive: Path, fn):
    before = _sha256(archive)
    assert before == FROZEN_SHA256[archive.stem]
    try:
        return fn()
    finally:
        assert _sha256(archive) == before


def _parse_headers(blob: bytes):
    assert blob.startswith(LOCAL_SIG)
    local_flag, local_method = struct.unpack_from("<HH", blob, 6)
    local_crc, compressed, uncompressed, name_len, extra_len = struct.unpack_from("<IIIHH", blob, 14)
    name_at = 30
    name = blob[name_at:name_at + name_len]
    payload_at = name_at + name_len + extra_len
    payload = blob[payload_at:payload_at + compressed]
    central_at = blob.find(CENTRAL_SIG)
    assert central_at > 0
    central_flag, central_method = struct.unpack_from("<HH", blob, central_at + 8)
    central_crc = struct.unpack_from("<I", blob, central_at + 16)[0]
    return {
        "local_flag": local_flag,
        "local_method": local_method,
        "central_flag": central_flag,
        "central_method": central_method,
        "local_crc": local_crc,
        "central_crc": central_crc,
        "name": name,
        "payload": payload,
        "uncompressed": uncompressed,
    }


def _uncompressed(parsed: dict) -> bytes:
    if parsed["local_method"] == 8:
        return zlib.decompress(parsed["payload"], wbits=-15)
    return parsed["payload"]


def _fresh_out(tmp_path: Path, name: str) -> Path:
    out = tmp_path / name
    assert not out.exists()
    return out


def _assert_failed_report(report, out: Path):
    assert report.passed is False
    assert report.development_checks_passed is False
    assert (out / "report.json").is_file()
    assert (out / "report.html").is_file()
    written = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert written["passed"] is False
    assert written["passed"] == report.passed
    assert written["development_checks_passed"] is False
    model_c001 = next(item for item in report.checks if item.id == "C001")
    file_c001 = next(item for item in written["checks"] if item["id"] == "C001")
    assert model_c001.status == "fail"
    assert file_c001["status"] == model_c001.status
    assert file_c001["observed"] == model_c001.observed
    return model_c001


def _exact_error(exc, exc_type: type, fragments: tuple[str, ...]) -> None:
    assert type(exc) is exc_type
    text = str(exc)
    assert all(part in text for part in fragments)


def baseline_escape_holds(archive: Path, out: Path, exc_type: type, fragments: tuple[str, ...]) -> bool:
    """True only when validate raises exactly exc_type and leaves out absent."""
    if out.exists():
        return False
    before = _sha256(archive)
    try:
        validate(ROOT, archive, out, blender=None)
    except exc_type as exc:
        held = type(exc) is exc_type and all(part in str(exc) for part in fragments) and not out.exists()
    except Exception:
        held = False
    else:
        held = False
    assert _sha256(archive) == before
    return held


def _swallow(monkeypatch, exc_type: type) -> None:
    original = validate_bundle.read_bundle

    def wrapper(path):
        try:
            return original(path)
        except (RuntimeError, NotImplementedError) as exc:
            if type(exc) is exc_type:
                raise ValueError(str(exc)) from exc
            raise

    monkeypatch.setattr(validate_bundle, "read_bundle", wrapper)


def _assert_swallowed_report(out: Path) -> None:
    assert (out / "report.json").is_file()
    assert (out / "report.html").is_file()
    written = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert written["passed"] is False
    c001 = next(item for item in written["checks"] if item["id"] == "C001")
    assert c001["status"] == "fail"


def _cli(archive: Path, out: Path):
    assert not out.exists()
    env = os.environ.copy()
    env.pop("DT_BLENDER", None)
    before = _sha256(archive)
    proc = subprocess.run(
        [sys.executable, "-m", "dt_ai.cli.main", "validate", "--archive", str(archive), "--output", str(out)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert _sha256(archive) == before
    return proc


def test_frozen_corpus_sha256_headers_and_payload():
    assert GOOD_CRC == 3633523372
    assert BAD_CRC == 661443923
    for name, fields in HEADER_FIELDS.items():
        blob = _frozen_blob(name)
        parsed = _parse_headers(blob)
        assert (
            parsed["local_flag"],
            parsed["local_method"],
            parsed["central_flag"],
            parsed["central_method"],
        ) == fields
        assert parsed["name"] == b"a.bin"
        assert parsed["uncompressed"] == len(PAYLOAD)
        assert _uncompressed(parsed) == PAYLOAD
        expected_crc = BAD_CRC if name == "bad-crc" else GOOD_CRC
        assert parsed["local_crc"] == parsed["central_crc"] == expected_crc


def test_encrypted_flag_escapes_reader_and_validate(tmp_path):
    archive = _archive(tmp_path / "in", "flag-bit0-encrypted-no-password")
    before = _sha256(archive)
    with pytest.raises(RuntimeError) as reader:
        read_bundle(archive)
    assert _sha256(archive) == before
    _exact_error(reader.value, RuntimeError, ("password", "encrypted"))

    out = _fresh_out(tmp_path, "validate-encrypted")
    before = _sha256(archive)
    with pytest.raises(RuntimeError) as validator:
        validate(ROOT, archive, out, blender=None)
    assert _sha256(archive) == before
    _exact_error(validator.value, RuntimeError, ("password", "encrypted"))
    assert not out.exists()


def test_compression_method_1_escapes_reader_and_validate(tmp_path):
    archive = _archive(tmp_path / "in", "method-1-local-and-central")
    before = _sha256(archive)
    with pytest.raises(NotImplementedError) as reader:
        read_bundle(archive)
    assert _sha256(archive) == before
    _exact_error(reader.value, NotImplementedError, ("compression method",))

    out = _fresh_out(tmp_path, "validate-method-1")
    before = _sha256(archive)
    with pytest.raises(NotImplementedError) as validator:
        validate(ROOT, archive, out, blender=None)
    assert _sha256(archive) == before
    _exact_error(validator.value, NotImplementedError, ("compression method",))
    assert not out.exists()


def test_bad_crc_is_a_handled_c001_fail(tmp_path):
    archive = _archive(tmp_path / "in", "bad-crc")
    out = _fresh_out(tmp_path, "validate-bad-crc")
    report = _preserving(archive, lambda: validate(ROOT, archive, out, blender=None))
    c001 = _assert_failed_report(report, out)
    assert "CRC" in c001.observed


@pytest.mark.parametrize("name", ["stored-a-bin", "deflated-a-bin"])
def test_readable_member_fails_c001_on_missing_manifest(tmp_path, name):
    archive = _archive(tmp_path / "in", name)
    files = _preserving(archive, lambda: read_bundle(archive))
    assert files == {"a.bin": PAYLOAD}
    out = _fresh_out(tmp_path, "validate-readable")
    report = _preserving(archive, lambda: validate(ROOT, archive, out, blender=None))
    c001 = _assert_failed_report(report, out)
    assert "bundle-manifest.json" in c001.observed
    assert "CRC" not in c001.observed
    assert "BadZipFile" not in c001.observed


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ("flag-bit0-encrypted-no-password", "password"),
        ("method-1-local-and-central", "compression method"),
    ],
)
def test_cli_escape_is_one_error_line_and_writes_nothing(tmp_path, name, fragment):
    archive = _archive(tmp_path / "in", name)
    out = _fresh_out(tmp_path, "cli-out")
    proc = _cli(archive, out)
    assert proc.returncode == 1
    assert proc.stdout == ""
    lines = [line for line in proc.stderr.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("ERROR:")
    assert fragment in lines[0]
    assert "Traceback" not in proc.stderr
    assert not out.exists()


@pytest.mark.parametrize(
    ("name", "exc_type", "fragments"),
    [
        ("flag-bit0-encrypted-no-password", RuntimeError, ("password", "encrypted")),
        ("method-1-local-and-central", NotImplementedError, ("compression method",)),
    ],
)
def test_swallowing_member_escape_breaks_the_characterization(tmp_path, monkeypatch, name, exc_type, fragments):
    archive = _archive(tmp_path / "in", name)
    _swallow(monkeypatch, exc_type)
    mutated = _fresh_out(tmp_path, "mutated-out")
    assert baseline_escape_holds(archive, mutated, exc_type, fragments) is False
    _assert_swallowed_report(mutated)
    monkeypatch.undo()
    monkeypatch.delenv("DT_BLENDER", raising=False)
    restored = _fresh_out(tmp_path, "restored-out")
    assert baseline_escape_holds(archive, restored, exc_type, fragments) is True
    assert not restored.exists()
