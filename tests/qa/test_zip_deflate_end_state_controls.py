"""new-case only. Legacy method-8 DEFLATE end state for one-member ZIPs.

docs/domain/patterns/INDEX.md lists building-node patterns. None covers a ZIP
deflate end state, so this module cites no pattern id.

The baseline is the current reader, already green: CRC-matching bytes ``b"hi"``
are returned for a finished stream, an unfinished stream, a three-byte prefix
and a finished stream with one trailing byte. A reserved block raises
``zlib.error``. Prefix-1 and prefix-2 CRC rows are out of scope (#676). This
module does not adopt eof rejection or zlib.error normalization.
"""
import hashlib
import importlib.util
import json
import platform
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

import pytest

import validate_package as vp
import twinqa.bundle as bundle_mod

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "src" / "twinqa" / "bundle.py"
SOURCE_HASH = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
PROFILES = vp.load_profiles()
LIMIT = 4 * 10**9
NAME = b"a.bin"
MEMBER = "a.bin"
PLAIN = b"hi"
CRC = zlib.crc32(PLAIN) & 0xFFFFFFFF

VALID = bytes.fromhex("cbc80400")
UNFINISHED = bytes.fromhex("cac80400")
PREFIX3 = bytes.fromhex("cbc804")
SUFFIX = bytes.fromhex("cbc8040000")
RESERVED = bytes.fromhex("07")

# Frozen before any reader call. Measured from the struct builder below.
PINNED = {
    VALID.hex(): "6ee8de1fec3e03ac32c425e837fac906299fcfe2cefac87007c031c4f56950de",
    UNFINISHED.hex(): "79eecc981ec5e0de4fec420c080b1f94d4457e56a4cb3c65eb040ec38e0904af",
    PREFIX3.hex(): "eccaf9145e90f1831707107aad3e0bf024e557198269f2a04b14cbb5d39d4aa5",
    SUFFIX.hex(): "a954308b4684701ef1e39e88a26d543b1fb0faa285c1d51ebd044faf2e5e9e8e",
    RESERVED.hex(): "390194baa3d92192e04e1c3776bbe684d64050c6959dd4d59c50451ef075e6d2",
}

READER_ROWS = [
    pytest.param(VALID, True, b"", id="cbc80400"),
    pytest.param(UNFINISHED, False, b"", id="cac80400"),
    pytest.param(PREFIX3, False, b"", id="cbc804"),
    pytest.param(SUFFIX, True, b"\x00", id="cbc8040000"),
]
JSON_CONTROLS = [
    pytest.param(VALID, id="valid-cbc80400"),
    pytest.param(UNFINISHED, id="incomplete-cac80400"),
]


def build_zip(method: int, payload: bytes) -> bytes:
    local = struct.pack(
        "<4sHHHHHIIIHH",
        b"PK\x03\x04",
        20,
        0,
        method,
        0,
        0x0021,
        CRC,
        len(payload),
        len(PLAIN),
        len(NAME),
        0,
    ) + NAME + payload
    central = struct.pack(
        "<4sHHHHHHIIIHHHHHII",
        b"PK\x01\x02",
        20,
        20,
        0,
        method,
        0,
        0x0021,
        CRC,
        len(payload),
        len(PLAIN),
        len(NAME),
        0,
        0,
        0,
        0,
        0,
        0,
    ) + NAME
    eocd = struct.pack("<4sHHHHIIH", b"PK\x05\x06", 0, 0, 1, 1, len(central), len(local), 0)
    return local + central + eocd


def parse_zip(blob: bytes) -> dict:
    assert len(blob) >= 30
    (
        sig, version, flags, method, _mtime, _mdate, crc, comp_size, uncomp_size, name_len, extra_len,
    ) = struct.unpack_from("<4sHHHHHIIIHH", blob, 0)
    assert sig == b"PK\x03\x04"
    assert (version, flags, name_len, extra_len) == (20, 0, len(NAME), 0)
    assert blob[30:35] == NAME
    payload = blob[35:35 + comp_size]
    assert len(payload) == comp_size
    central_at = 35 + comp_size
    (
        csig, _vmade, vneed, cflags, cmethod, _ctime, _cdate, ccrc, ccomp, cuncomp,
        cname_len, cextra_len, ccomment_len, _cdisk, _cinternal, _cexternal, clocal,
    ) = struct.unpack_from("<4sHHHHHHIIIHHHHHII", blob, central_at)
    assert csig == b"PK\x01\x02"
    cname = blob[central_at + 46:central_at + 46 + cname_len]
    central_len = 46 + cname_len + cextra_len + ccomment_len
    eocd_at = central_at + central_len
    esig, _disk, _cd_disk, disk_entries, total_entries, cd_size, cd_offset, comment_len = struct.unpack_from(
        "<4sHHHHIIH", blob, eocd_at,
    )
    assert esig == b"PK\x05\x06"
    assert eocd_at + 22 + comment_len == len(blob)
    return {
        "method": method,
        "crc": crc,
        "comp_size": comp_size,
        "uncomp_size": uncomp_size,
        "payload": payload,
        "central_method": cmethod,
        "central_version": vneed,
        "central_flags": cflags,
        "central_crc": ccrc,
        "central_comp": ccomp,
        "central_uncomp": cuncomp,
        "central_name": cname,
        "local_offset": clocal,
        "central_at": central_at,
        "central_len": central_len,
        "entries": total_entries,
        "disk_entries": disk_entries,
        "cd_size": cd_size,
        "cd_offset": cd_offset,
    }


def assert_headers(parsed: dict, payload: bytes) -> None:
    assert parsed["method"] == 8
    assert parsed["payload"] == payload
    assert parsed["comp_size"] == len(payload)
    assert parsed["uncomp_size"] == len(PLAIN) == 2
    assert parsed["crc"] == CRC
    assert parsed["central_method"] == parsed["method"]
    assert parsed["central_flags"] == 0
    assert parsed["central_version"] == 20
    assert parsed["central_crc"] == parsed["crc"]
    assert parsed["central_comp"] == parsed["comp_size"]
    assert parsed["central_uncomp"] == parsed["uncomp_size"]
    assert parsed["central_name"] == NAME
    assert parsed["local_offset"] == 0
    assert parsed["entries"] == parsed["disk_entries"] == 1
    assert parsed["cd_offset"] == parsed["central_at"]
    assert parsed["cd_size"] == parsed["central_len"]


def stage(tmp_path: Path, payload: bytes) -> tuple[Path, str]:
    """Parse headers and freeze the zip hash before any inflate or reader call."""
    blob = build_zip(8, payload)
    assert_headers(parse_zip(blob), payload)
    digest = hashlib.sha256(blob).hexdigest()
    assert digest == PINNED[payload.hex()]
    path = tmp_path / f"{payload.hex()}.zip"
    assert not path.exists()
    path.write_bytes(blob)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    return path, digest


def assert_unchanged(path: Path, digest: str) -> None:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def assert_invalid_block(exc: BaseException) -> None:
    text = str(exc).lower()
    assert type(exc) is zlib.error
    assert "invalid" in text and "block" in text


def assert_no_zip_finding(report) -> None:
    names = [finding.name for stage_ in report.stages for finding in stage_.findings]
    assert "ZIP" not in names


def v001_fail_names(report) -> dict[str, str]:
    stage_ = next(item for item in report.stages if item.id == "V001")
    return {finding.name: finding.observed for finding in stage_.findings if finding.status == "fail"}


def run_cli(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "qa" / "validate_package.py"), str(path),
         "--profile", "npm", "--json"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=60,
    )


def assert_source_unchanged() -> None:
    assert hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == SOURCE_HASH
    text = SOURCE_PATH.read_text(encoding="utf-8")
    assert "except (zipfile.BadZipFile, OSError, EOFError) as exc:" in text
    assert "zlib.error" not in text
    assert "strict eof" not in text


def scratch_reader(tmp_path: Path, kind: str):
    """Process-local copy of bundle.py. The repository file is not written."""
    text = SOURCE_PATH.read_text(encoding="utf-8")
    assert "zlib.error" not in text
    text = text.replace(
        "import zipfile\nfrom pathlib import PurePosixPath\n",
        "import struct\nimport zipfile\nimport zlib\nfrom pathlib import Path, PurePosixPath\n",
        1,
    )
    if kind == "swallow-zlib":
        needle = "except (zipfile.BadZipFile, OSError, EOFError) as exc:"
        assert text.count(needle) == 1
        text = text.replace(needle, "except (zipfile.BadZipFile, OSError, EOFError, zlib.error) as exc:", 1)
    elif kind == "strict-eof":
        head = (
            '    """Return {member: bytes}. Rejects broken ZIPs, unsafe paths, duplicates, oversize content."""\n'
            "    try:\n"
        )
        assert head in text
        text = text.replace(head, head.replace("    try:\n", "    prefetched = Path(path).read_bytes()\n    try:\n", 1), 1)
        ret = "            return {name: archive.read(name) for name in names}\n"
        body = (
            "            found = {}\n"
            "            for name in names:\n"
            "                info = archive.getinfo(name)\n"
            "                data = archive.read(name)\n"
            "                if info.compress_type == zipfile.ZIP_DEFLATED:\n"
            "                    name_len, extra_len = struct.unpack_from('<HH', prefetched, info.header_offset + 26)\n"
            "                    start = info.header_offset + 30 + name_len + extra_len\n"
            "                    raw = prefetched[start:start + info.compress_size]\n"
            "                    dec = zlib.decompressobj(-15)\n"
            "                    dec.decompress(raw)\n"
            "                    dec.flush()\n"
            "                    if not dec.eof:\n"
            "                        raise BundleError('strict eof rejection')\n"
            "                found[name] = data\n"
            "            return found\n"
        )
        assert text.count(ret) == 1
        text = text.replace(ret, body, 1)
    else:
        raise AssertionError(kind)
    dest = tmp_path / f"scratch_{kind.replace('-', '_')}.py"
    assert not dest.resolve().is_relative_to(ROOT)
    dest.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"scratch_{kind.replace('-', '_')}", dest)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BundleError = bundle_mod.BundleError
    return module


def test_runtime_versions_are_recorded():
    recorded = {
        "python": platform.python_version(),
        "zlib": zlib.ZLIB_VERSION,
        "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
        "zlib_ng": zlib.ZLIBNG_VERSION,
    }
    assert all(isinstance(value, str) and value for value in recorded.values())


@pytest.mark.parametrize("payload", [VALID, UNFINISHED, PREFIX3, SUFFIX, RESERVED], ids=lambda payload: payload.hex())
def test_headers_and_hashes_frozen_before_readers(tmp_path, payload):
    path, digest = stage(tmp_path, payload)
    assert_unchanged(path, digest)
    assert digest == PINNED[payload.hex()]


@pytest.mark.parametrize("payload,eof,unused", READER_ROWS)
def test_raw_deflate_end_state(tmp_path, payload, eof, unused):
    path, digest = stage(tmp_path, payload)
    dec = zlib.decompressobj(-15)
    assert dec.decompress(payload) == PLAIN
    assert dec.flush() == b""
    assert dec.eof is eof
    assert dec.unused_data == unused
    assert dec.unconsumed_tail == b""
    assert_unchanged(path, digest)


@pytest.mark.parametrize("payload,eof,unused", READER_ROWS)
def test_zipfile_and_read_bundle_return_member(tmp_path, payload, eof, unused):
    del eof, unused
    path, digest = stage(tmp_path, payload)
    with zipfile.ZipFile(path) as archive:
        opened = {MEMBER: archive.open(MEMBER).read()}
    with zipfile.ZipFile(path) as archive:
        read = {MEMBER: archive.read(MEMBER)}
    assert opened == {MEMBER: PLAIN}
    assert read == {MEMBER: PLAIN}
    assert bundle_mod.read_bundle(path, LIMIT) == {MEMBER: PLAIN}
    assert_unchanged(path, digest)


@pytest.mark.parametrize("payload,eof,unused", READER_ROWS)
def test_validate_npm_composition_without_zip_finding(tmp_path, payload, eof, unused):
    del eof, unused
    path, digest = stage(tmp_path, payload)
    report = vp.validate(path, "npm", PROFILES, scene=False)
    failed = v001_fail_names(report)
    assert "foreign files" in failed and MEMBER in failed["foreign files"]
    assert "FBX count" in failed
    assert_no_zip_finding(report)
    assert report.passed is False
    assert report.exit_code == 1
    assert_unchanged(path, digest)


def test_reserved_block_raises_zlib_error_not_a_report(tmp_path):
    path, digest = stage(tmp_path, RESERVED)
    dec = zlib.decompressobj(-15)
    with pytest.raises(zlib.error) as raw:
        dec.decompress(RESERVED)
    assert_invalid_block(raw.value)
    with pytest.raises(zlib.error) as opened:
        with zipfile.ZipFile(path) as archive:
            archive.open(MEMBER).read()
    assert_invalid_block(opened.value)
    with pytest.raises(zlib.error) as read:
        with zipfile.ZipFile(path) as archive:
            archive.read(MEMBER)
    assert_invalid_block(read.value)
    with pytest.raises(zlib.error) as bundled:
        bundle_mod.read_bundle(path, LIMIT)
    assert_invalid_block(bundled.value)
    assert not isinstance(bundled.value, bundle_mod.BundleError)
    report = None
    with pytest.raises(zlib.error) as validated:
        report = vp.validate(path, "npm", PROFILES, scene=False)
    assert report is None
    assert_invalid_block(validated.value)
    assert not isinstance(validated.value, bundle_mod.BundleError)
    assert_unchanged(path, digest)


def test_reserved_cli_has_traceback_and_empty_stdout(tmp_path):
    path, digest = stage(tmp_path, RESERVED)
    proc = run_cli(path)
    assert proc.returncode == 1
    assert proc.stdout == b""
    err = proc.stderr.decode("utf-8", errors="replace")
    assert "Traceback" in err
    assert "zlib.error" in err
    assert "invalid" in err.lower() and "block" in err.lower()
    assert_unchanged(path, digest)


@pytest.mark.parametrize("payload", JSON_CONTROLS)
def test_valid_and_incomplete_cli_json_has_no_zip_finding(tmp_path, payload):
    path, digest = stage(tmp_path, payload)
    proc = run_cli(path)
    assert proc.returncode == 1
    assert proc.stderr == b""
    report = json.loads(proc.stdout.decode("utf-8"))
    assert report["passed"] is False
    names = [finding["name"] for stage_ in report["stages"] for finding in stage_["findings"]]
    assert "ZIP" not in names
    assert "foreign files" in names and "FBX count" in names
    assert_unchanged(path, digest)


def test_strict_eof_mutation_triggers_rejection_then_restores(tmp_path, monkeypatch):
    unfinished, unfinished_hash = stage(tmp_path, UNFINISHED)
    prefix3, prefix3_hash = stage(tmp_path, PREFIX3)
    valid, valid_hash = stage(tmp_path, VALID)
    suffix, suffix_hash = stage(tmp_path, SUFFIX)
    original = bundle_mod.read_bundle
    assert vp.read_bundle is original
    mutated = scratch_reader(tmp_path, "strict-eof")
    monkeypatch.setattr(bundle_mod, "read_bundle", mutated.read_bundle)
    monkeypatch.setattr(vp, "read_bundle", mutated.read_bundle)
    with pytest.raises(bundle_mod.BundleError, match="strict eof rejection") as unfinished_fired:
        bundle_mod.read_bundle(unfinished, LIMIT)
    assert str(unfinished_fired.value) == "strict eof rejection"
    with pytest.raises(bundle_mod.BundleError, match="strict eof rejection") as prefix3_fired:
        bundle_mod.read_bundle(prefix3, LIMIT)
    assert str(prefix3_fired.value) == "strict eof rejection"
    rejected = vp.validate(unfinished, "npm", PROFILES, scene=False)
    zip_findings = [finding for stage_ in rejected.stages for finding in stage_.findings if finding.name == "ZIP"]
    assert len(zip_findings) == 1 and zip_findings[0].status == "fail"
    assert zip_findings[0].observed == "strict eof rejection"
    assert bundle_mod.read_bundle(valid, LIMIT) == {MEMBER: PLAIN}
    assert bundle_mod.read_bundle(suffix, LIMIT) == {MEMBER: PLAIN}
    kept = vp.validate(valid, "npm", PROFILES, scene=False)
    assert_no_zip_finding(kept)
    monkeypatch.undo()
    assert bundle_mod.read_bundle is original
    assert vp.read_bundle is original
    assert bundle_mod.read_bundle(unfinished, LIMIT) == {MEMBER: PLAIN}
    assert bundle_mod.read_bundle(prefix3, LIMIT) == {MEMBER: PLAIN}
    restored = vp.validate(unfinished, "npm", PROFILES, scene=False)
    assert_no_zip_finding(restored)
    assert restored.passed is False and restored.exit_code == 1
    assert_source_unchanged()
    assert_unchanged(unfinished, unfinished_hash)
    assert_unchanged(prefix3, prefix3_hash)
    assert_unchanged(valid, valid_hash)
    assert_unchanged(suffix, suffix_hash)


def test_swallow_zlib_error_mutation_triggers_bundle_error_then_restores(tmp_path, monkeypatch):
    reserved, reserved_hash = stage(tmp_path, RESERVED)
    unfinished, unfinished_hash = stage(tmp_path, UNFINISHED)
    original = bundle_mod.read_bundle
    assert vp.read_bundle is original
    mutated = scratch_reader(tmp_path, "swallow-zlib")
    monkeypatch.setattr(bundle_mod, "read_bundle", mutated.read_bundle)
    monkeypatch.setattr(vp, "read_bundle", mutated.read_bundle)
    with pytest.raises(bundle_mod.BundleError) as fired:
        bundle_mod.read_bundle(reserved, LIMIT)
    assert type(fired.value) is bundle_mod.BundleError
    assert not isinstance(fired.value, zlib.error)
    assert "invalid" in str(fired.value).lower() and "block" in str(fired.value).lower()
    assert bundle_mod.read_bundle(unfinished, LIMIT) == {MEMBER: PLAIN}
    report = vp.validate(reserved, "npm", PROFILES, scene=False)
    zip_findings = [finding for stage_ in report.stages for finding in stage_.findings if finding.name == "ZIP"]
    assert len(zip_findings) == 1 and zip_findings[0].status == "fail"
    observed = zip_findings[0].observed.lower()
    assert "invalid" in observed and "block" in observed
    assert report.passed is False and report.exit_code == 1
    monkeypatch.undo()
    assert bundle_mod.read_bundle is original
    assert vp.read_bundle is original
    with pytest.raises(zlib.error) as restored_reader:
        bundle_mod.read_bundle(reserved, LIMIT)
    assert_invalid_block(restored_reader.value)
    restored_report = None
    with pytest.raises(zlib.error) as restored_validate:
        restored_report = vp.validate(reserved, "npm", PROFILES, scene=False)
    assert restored_report is None
    assert_invalid_block(restored_validate.value)
    assert bundle_mod.read_bundle(unfinished, LIMIT) == {MEMBER: PLAIN}
    assert_source_unchanged()
    assert_unchanged(reserved, reserved_hash)
    assert_unchanged(unfinished, unfinished_hash)
