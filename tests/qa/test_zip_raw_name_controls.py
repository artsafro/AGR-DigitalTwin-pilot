"""new-case: measured ZIP raw-name split between the official and development readers.

Fixtures are synthetic stored archives. These tests are baseline-GREEN
characterizations of current reader behavior. No historical RED proof is
possible from this tree; none is claimed. The tests do not choose which
member identity is correct.

A synthetic composition failure is not evidence of delivery compliance.
Readers run in memory: no extraction and no input deletion.
"""
import hashlib
import json
import struct
import subprocess
import sys
import zipfile
import zlib
from itertools import product
from pathlib import Path, PurePosixPath

import pytest

import validate_package
import twinqa.bundle as official_bundle
from dt_ai.publish.bundle import read_bundle as read_development_bundle
from twinqa.bundle import BundleError
from twinqa.profiles import load_profiles

MAX_UNCOMPRESSED = 4 * 10**9
PROFILES = load_profiles()
REPO = Path(__file__).resolve().parents[2]

SIG_LOCAL = b"PK\x03\x04"
SIG_CENTRAL = b"PK\x01\x02"
SIG_EOCD = b"PK\x05\x06"
LOCAL_FMT = "<4s2B4HL2L2H"
CENTRAL_FMT = "<4s4B4HL2L5H2L"
EOCD_FMT = "<4s4H2LH"
LOCAL_FIXED = 30
CENTRAL_FIXED = 46

NAME_SAFE = b"a.bin"
NAME_NUL_SUFFIX = b"a.bin\x00../escape"
NAME_LEADING = b"\x00../escape"
NAME_DIR = b"../escape/"
NAME_DOTDOT = b"../escape"
NAME_BACKSLASH = b"sub\\a.bin"

PAYLOAD_SAFE = b"payload-safe"
PAYLOAD_SUFFIX = b"payload-suffix"
PAYLOAD_LEAD = b"payload-lead"
PAYLOAD_DOT = b"payload-dot"
PAYLOAD_MISMATCH = b"payload-mismatch"
PAYLOAD_BACKSLASH = b"payload-bs"
PAYLOAD_EMPTY = b""
PROBE_PAYLOAD = b"probe-payload"

# Frozen before any ZIP API. Same byte strings as the measured synthetic corpus.
FROZEN_SHA256 = {
    NAME_SAFE: "4fef9cffec13baaa0b8bab5ae61005c5ee8bdb7880b255d60c27e8b7b45202ba",
    NAME_NUL_SUFFIX: "1960b2a5d32c32b6724575ea60fcd61b8597fe759b2e1c74266e8f23bdab9fb2",
    NAME_LEADING: "74e443a07e524ad06f2b7a187e954372f590f25ce2e0f643a9ae8b1ef214fca1",
    NAME_DIR: "e2edd88100797ecd45abe62ea40e80946707ee0baabea201e58ceb7952ae1b12",
    NAME_DOTDOT: "1ba7343c47dc442de7dec43a995deb9a7b62234ecca16d7c6f597b5155bd85b1",
    NAME_BACKSLASH: "f2065dfcf6b4a772bfe9f8db825401e3d1fcbf9873664110bb786f1d49935ddf",
    PAYLOAD_SAFE: "a9792369b5d2caa60674a82d1a694e50eab72e8cb94e1a065a0ab8161f892b22",
    PAYLOAD_SUFFIX: "2c4a464e116cb01659fd8bbbe81ad042963c78b4428fafcb6d7426c986a412df",
    PAYLOAD_LEAD: "2d23b5fb8ba8a2705dc54c27d3fb18028b2d819f3795d5a663aa579422dee086",
    PAYLOAD_DOT: "5a048b7ad11f62a0863ae9f4c00fab5cdc0203e261895e7fc6654176b7b95461",
    PAYLOAD_MISMATCH: "d641ea6b3d8d71883a5d9d4f89e99ccb1263ba1e453c45793b0021b2803ac971",
    PAYLOAD_BACKSLASH: "5001595da002dc6b345ffda65cd0decedbb6cfe4f336408652cfda60de2af137",
    PAYLOAD_EMPTY: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    PROBE_PAYLOAD: "40c1fcca7ab33fdf9e1a44976a73d3df7dec1556b72e35aad9a087c5cfba4f63",
}

PROBE_PREFIXES = (
    "",
    "a.bin",
    "safe",
    "n",
    "nested/",
    "../escape",
    "a/../../x",
    "/abs",
    "c:x",
    "sub\\a.bin",
)
PROBE_SUFFIXES = ("../escape", "..\\escape", "/../x", "discarded", "")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_stored_zip(members: list[tuple[bytes, bytes, bytes]]) -> bytes:
    """Stored ZIP whose local and central names are independent raw bytes.

    ZipInfo is not used. Its constructor sanitizes at the first NUL, so a
    constructor argument cannot be the source of these raw names.
    """
    blobs = []
    central_parts = []
    offset = 0
    for local_name, central_name, payload in members:
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        blobs.append(struct.pack(
            LOCAL_FMT,
            SIG_LOCAL, 20, 0, 0, 0, 0, 0, crc, len(payload), len(payload),
            len(local_name), 0,
        ) + local_name + payload)
        central_parts.append(struct.pack(
            CENTRAL_FMT,
            SIG_CENTRAL, 20, 0, 20, 0, 0, 0, 0, 0, crc, len(payload), len(payload),
            len(central_name), 0, 0, 0, 0, 0, offset,
        ) + central_name)
        offset += len(blobs[-1])
    body = b"".join(blobs)
    central = b"".join(central_parts)
    eocd = struct.pack(
        EOCD_FMT, SIG_EOCD, 0, 0, len(members), len(members), len(central), len(body), 0,
    )
    return body + central + eocd


def parse_stored(data: bytes) -> tuple[list[bytes], list[bytes], list[bytes]]:
    """Return raw local names, raw central names, and stored payloads."""
    eocd_at = data.rfind(SIG_EOCD)
    if eocd_at < 0:
        raise AssertionError("synthetic archive has no end of central directory")
    eocd = struct.unpack_from(EOCD_FMT, data, eocd_at)
    if eocd[0] != SIG_EOCD or eocd[7] != 0:
        raise AssertionError("unexpected end-of-central-directory trailer")
    count, cd_size, cd_off = eocd[4], eocd[5], eocd[6]
    if cd_off + cd_size != eocd_at:
        raise AssertionError("central directory does not end at the trailer")
    centrals = []
    pos = cd_off
    for _ in range(count):
        fixed = struct.unpack_from(CENTRAL_FMT, data, pos)
        if fixed[0] != SIG_CENTRAL or fixed[5] != 0 or fixed[6] != 0:
            raise AssertionError("central header is not a stored, flag-free member")
        name_len, extra_len, comment_len = fixed[12], fixed[13], fixed[14]
        name = data[pos + CENTRAL_FIXED:pos + CENTRAL_FIXED + name_len]
        centrals.append(name)
        pos += CENTRAL_FIXED + name_len + extra_len + comment_len
    if pos != eocd_at:
        raise AssertionError("central directory size does not match the trailer")
    locals_ = []
    payloads = []
    pos = 0
    for _ in range(count):
        fixed = struct.unpack_from(LOCAL_FMT, data, pos)
        if fixed[0] != SIG_LOCAL or fixed[3] != 0 or fixed[4] != 0:
            raise AssertionError("local header is not a stored, flag-free member")
        name_len, extra_len, comp_size = fixed[10], fixed[11], fixed[8]
        name = data[pos + LOCAL_FIXED:pos + LOCAL_FIXED + name_len]
        payload_at = pos + LOCAL_FIXED + name_len + extra_len
        locals_.append(name)
        payloads.append(data[payload_at:payload_at + comp_size])
        pos = payload_at + comp_size
    if pos != cd_off:
        raise AssertionError("local members do not end where the central directory starts")
    return locals_, centrals, payloads


def materialize(tmp_path: Path, filename: str, members: list[tuple[bytes, bytes, bytes]]) -> tuple[Path, bytes, str]:
    """Freeze raw names and payload hashes, then write the archive once."""
    for local_name, central_name, payload in members:
        assert sha256(local_name) == FROZEN_SHA256[local_name]
        assert sha256(central_name) == FROZEN_SHA256[central_name]
        assert sha256(payload) == FROZEN_SHA256[payload]
    blob = build_stored_zip(members)
    local_names, central_names, payloads = parse_stored(blob)
    assert local_names == [item[0] for item in members]
    assert central_names == [item[1] for item in members]
    assert payloads == [item[2] for item in members]
    path = tmp_path / filename
    path.write_bytes(blob)
    digest = sha256(blob)
    assert sha256(path.read_bytes()) == digest
    return path, blob, digest


def assert_archive_untouched(path: Path, blob: bytes, digest: str) -> None:
    assert path.read_bytes() == blob
    assert sha256(path.read_bytes()) == digest
    assert list(path.parent.iterdir()) == [path]


def assert_development_rejects_unsafe(path: Path) -> None:
    with pytest.raises(ValueError, match="^Unsafe ZIP path$") as caught:
        read_development_bundle(path)
    assert type(caught.value) is ValueError


def v001(report):
    return next(stage for stage in report.stages if stage.id == "V001")


def validate_npm(path: Path):
    return validate_package.validate(path, "npm", PROFILES, scene=False)


def assert_composition(report, foreign_observed: str) -> None:
    """V001 failed on archive content. A synthetic composition failure is not delivery compliance."""
    assert report.passed is False
    assert report.exit_code == 1
    stage = v001(report)
    assert "ZIP" not in [item.name for item in stage.findings]
    foreign = [item for item in stage.findings if item.name == "foreign files"]
    count = [item for item in stage.findings if item.name == "FBX count"]
    assert len(foreign) == 1 and foreign[0].status == "fail"
    assert foreign[0].observed == foreign_observed
    assert len(count) == 1 and count[0].status == "fail"
    assert count[0].observed == "0"
    text = "\n".join(f"{item.name} {item.observed}" for item in stage.findings)
    assert "../escape" not in text
    assert "\x00" not in text


def assert_zip_finding(report, snippet: str) -> None:
    assert report.passed is False
    assert report.exit_code == 1
    stage = v001(report)
    assert [item.name for item in stage.findings] == ["ZIP"]
    assert stage.findings[0].status == "fail"
    assert snippet in stage.findings[0].observed


def test_safe_member_both_readers_return_exact_payload(tmp_path):
    path, blob, digest = materialize(tmp_path, "safe-a-bin.zip", [(NAME_SAFE, NAME_SAFE, PAYLOAD_SAFE)])
    assert official_bundle.read_bundle(path, MAX_UNCOMPRESSED) == {"a.bin": PAYLOAD_SAFE}
    assert read_development_bundle(path) == {"a.bin": PAYLOAD_SAFE}
    assert_composition(validate_npm(path), "a.bin")
    assert_archive_untouched(path, blob, digest)


def test_matching_nul_suffix_official_returns_truncated_name(tmp_path):
    path, blob, digest = materialize(
        tmp_path, "nul-suffix.zip", [(NAME_NUL_SUFFIX, NAME_NUL_SUFFIX, PAYLOAD_SUFFIX)],
    )
    assert official_bundle.read_bundle(path, MAX_UNCOMPRESSED) == {"a.bin": PAYLOAD_SUFFIX}
    assert_development_rejects_unsafe(path)
    assert_composition(validate_npm(path), "a.bin")
    assert_archive_untouched(path, blob, digest)


def test_leading_nul_official_returns_empty_string_key(tmp_path):
    path, blob, digest = materialize(
        tmp_path, "leading-nul.zip", [(NAME_LEADING, NAME_LEADING, PAYLOAD_LEAD)],
    )
    assert official_bundle.read_bundle(path, MAX_UNCOMPRESSED) == {"": PAYLOAD_LEAD}
    assert_development_rejects_unsafe(path)
    assert_composition(validate_npm(path), "")
    assert_archive_untouched(path, blob, digest)


def test_safe_file_plus_unsafe_directory_official_returns_only_file(tmp_path):
    path, blob, digest = materialize(tmp_path, "file-plus-dir.zip", [
        (NAME_SAFE, NAME_SAFE, PAYLOAD_SAFE),
        (NAME_DIR, NAME_DIR, PAYLOAD_EMPTY),
    ])
    found = official_bundle.read_bundle(path, MAX_UNCOMPRESSED)
    assert found == {"a.bin": PAYLOAD_SAFE}
    assert list(found) == ["a.bin"]
    assert_development_rejects_unsafe(path)
    assert_composition(validate_npm(path), "a.bin")
    assert_archive_untouched(path, blob, digest)


def test_explicit_dotdot_file_is_rejected_by_both_readers(tmp_path):
    path, blob, digest = materialize(
        tmp_path, "explicit-dotdot.zip", [(NAME_DOTDOT, NAME_DOTDOT, PAYLOAD_DOT)],
    )
    with pytest.raises(BundleError, match=r"^Unsafe ZIP path: \.\./escape$"):
        official_bundle.read_bundle(path, MAX_UNCOMPRESSED)
    assert_development_rejects_unsafe(path)
    assert_zip_finding(validate_npm(path), "Unsafe ZIP path: ../escape")
    assert_archive_untouched(path, blob, digest)


def test_local_nul_suffix_with_safe_central_name_is_a_broken_member(tmp_path):
    path, blob, digest = materialize(
        tmp_path, "mismatch-local-suffix.zip", [(NAME_NUL_SUFFIX, NAME_SAFE, PAYLOAD_MISMATCH)],
    )
    with pytest.raises(BundleError, match="Broken ZIP member"):
        official_bundle.read_bundle(path, MAX_UNCOMPRESSED)
    with pytest.raises(zipfile.BadZipFile, match="differ"):
        read_development_bundle(path)
    assert_zip_finding(validate_npm(path), "Broken ZIP member")
    assert_archive_untouched(path, blob, digest)


def test_backslash_normalization_follows_os_sep(tmp_path):
    """sub\\a.bin is not a portable identity.

    On Windows, zipfile rewrites os.sep before the official reader, so that
    reader returns sub/a.bin while the development reader still rejects the raw
    backslash. On any other host backslash is not os.sep, so both readers see
    the raw name and reject it. The branch freezes that documented behavior.
    """
    path, blob, digest = materialize(
        tmp_path, "backslash.zip", [(NAME_BACKSLASH, NAME_BACKSLASH, PAYLOAD_BACKSLASH)],
    )
    if sys.platform == "win32":
        reason = "Windows zipfile rewrites os.sep backslash to slash before ZipInfo.filename"
        assert official_bundle.read_bundle(path, MAX_UNCOMPRESSED) == {"sub/a.bin": PAYLOAD_BACKSLASH}, reason
        assert_development_rejects_unsafe(path)
        assert_composition(validate_npm(path), "sub/a.bin")
    else:
        reason = (
            "backslash is not os.sep on this host, so zipfile keeps the raw name; "
            "both readers reject it instead of applying the Windows slash rewrite"
        )
        with pytest.raises(BundleError, match=r"Unsafe ZIP path: sub\\a\.bin"):
            official_bundle.read_bundle(path, MAX_UNCOMPRESSED)
        assert_development_rejects_unsafe(path)
        assert_zip_finding(validate_npm(path), "Unsafe ZIP path")
        assert reason
    assert_archive_untouched(path, blob, digest)


def test_nul_suffix_cli_json_is_a_composition_failure(tmp_path):
    path, blob, digest = materialize(
        tmp_path, "nul-suffix-cli.zip", [(NAME_NUL_SUFFIX, NAME_NUL_SUFFIX, PAYLOAD_SUFFIX)],
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "qa" / "validate_package.py"),
            str(path),
            "--profile", "npm",
            "--json",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert proc.returncode == 1
    assert proc.stderr == ""
    assert "Traceback" not in proc.stdout
    assert "Traceback" not in proc.stderr
    assert "../escape" not in proc.stdout
    assert "\x00" not in proc.stdout
    assert "\\u0000" not in proc.stdout
    assert "\\x00" not in proc.stdout
    report = json.loads(proc.stdout)
    assert report["passed"] is False
    assert report["exit_code"] == 1
    assert report["profile"] == "npm"
    stage = next(item for item in report["stages"] if item["id"] == "V001")
    failed = [item for item in stage["findings"] if item["status"] == "fail"]
    assert "ZIP" not in [item["name"] for item in stage["findings"]]
    foreign = next(item for item in failed if item["name"] == "foreign files")
    count = next(item for item in failed if item["name"] == "FBX count")
    assert foreign["observed"] == "a.bin"
    assert count["observed"] == "0"
    assert_archive_untouched(path, blob, digest)


def test_in_memory_raw_nul_rejection_fails_the_acceptance_witness(monkeypatch, tmp_path):
    """Baseline-GREEN: the unmutated reader already accepts the truncated name.

    A temporary monkeypatch rejects raw member names that contain NUL and makes
    that acceptance witness fail. The patch is undone in the test. This is not
    a historical RED run and does not choose which identity is correct.
    """
    path, blob, digest = materialize(
        tmp_path, "nul-suffix-witness.zip", [(NAME_NUL_SUFFIX, NAME_NUL_SUFFIX, PAYLOAD_SUFFIX)],
    )

    def acceptance_witness():
        found = official_bundle.read_bundle(path, MAX_UNCOMPRESSED)
        assert found == {"a.bin": PAYLOAD_SUFFIX}

    acceptance_witness()
    original = official_bundle.read_bundle

    def reject_raw_nul(archive_path, max_uncompressed):
        local_names, central_names, _payloads = parse_stored(Path(archive_path).read_bytes())
        if any(b"\x00" in name for name in local_names + central_names):
            raise BundleError("Unsafe ZIP path")
        return original(archive_path, max_uncompressed)

    monkeypatch.setattr(official_bundle, "read_bundle", reject_raw_nul)
    with pytest.raises(BundleError, match="^Unsafe ZIP path$"):
        acceptance_witness()
    monkeypatch.undo()
    acceptance_witness()
    assert_archive_untouched(path, blob, digest)


def key_is_unsafe(name: str) -> bool:
    """Traversal predicate used by the official reader, plus a surviving NUL.

    The empty string is the measured leading-NUL identity. It is not a
    traversal key; the leading-NUL acceptance test pins that return value.
    """
    if not isinstance(name, str) or "\x00" in name or "\\" in name or ":" in name:
        return True
    path = PurePosixPath(name)
    return path.is_absolute() or ".." in path.parts


def test_accepted_reader_never_returns_an_unsafe_key(tmp_path):
    """Generated probe: invariant is that the official reader never returns an unsafe key.

    Each variant is one stored member whose raw name is prefix + NUL + suffix.
    Fail closed: an unexpected exception, a mutated archive, or an extracted
    file fails the probe. No input is deleted.
    """
    assert sha256(PROBE_PAYLOAD) == FROZEN_SHA256[PROBE_PAYLOAD]
    variants = [prefix + "\x00" + suffix for prefix, suffix in product(PROBE_PREFIXES, PROBE_SUFFIXES)]
    failures = []
    written = []
    for index, raw in enumerate(variants):
        raw_name = raw.encode("ascii")
        blob = build_stored_zip([(raw_name, raw_name, PROBE_PAYLOAD)])
        local_names, central_names, payloads = parse_stored(blob)
        if local_names != [raw_name] or central_names != [raw_name] or payloads != [PROBE_PAYLOAD]:
            failures.append((raw, "header bytes drifted before the readers"))
            continue
        path = tmp_path / f"probe-{index}.zip"
        path.write_bytes(blob)
        written.append((path, blob, sha256(blob)))
        try:
            found = official_bundle.read_bundle(path, MAX_UNCOMPRESSED)
        except BundleError:
            found = None
        except Exception as exc:
            failures.append((raw, "official", type(exc).__name__, str(exc)))
            found = None
        else:
            if not isinstance(found, dict):
                failures.append((raw, "official returned", type(found).__name__))
            else:
                for key, payload in found.items():
                    if key_is_unsafe(key) or payload != PROBE_PAYLOAD:
                        failures.append((raw, "unsafe or substituted", key, payload))
        try:
            returned = read_development_bundle(path)
        except ValueError as exc:
            if type(exc) is not ValueError or str(exc) != "Unsafe ZIP path":
                failures.append((raw, "development", type(exc).__name__, str(exc)))
        except Exception as exc:
            failures.append((raw, "development", type(exc).__name__, str(exc)))
        else:
            failures.append((raw, "development returned", list(returned)))
        if path.read_bytes() != blob:
            failures.append((raw, "archive bytes changed"))
    assert len(variants) == len(PROBE_PREFIXES) * len(PROBE_SUFFIXES) == 50
    assert len(written) == 50
    left = sorted(item for item in tmp_path.iterdir() if item.is_file())
    assert left == sorted(path for path, _blob, _digest in written)
    for path, blob, digest in written:
        assert path.read_bytes() == blob
        assert sha256(path.read_bytes()) == digest
    assert not failures
