"""Direct byte-boundary and encoding contract tests for FBX header parser (V002).

Closes the standalone header-test gap identified in docs/research/repo-health.md
Open Questions #3 without changing format policy (PKG-09; FBX 7.4 binary 2014).
Tests fbx_header and check_fbx_header in src/twinqa/fbx_header.py using purely
synthetic byte buffers constructed with struct; no FBX files or DCC dependencies.
"""
import struct

import pytest

from twinqa.fbx_header import MAGIC, REQUIRED_VERSION, check_fbx_header, fbx_header


def _valid_7400_header() -> bytes:
    """Exact 27-byte header: 23-byte MAGIC followed by uint32 LE 7400."""
    return MAGIC + struct.pack("<I", 7400)


def test_valid_7400_header_without_payload():
    """Exact 23-byte MAGIC plus uint32 little-endian 7400, with no payload -> ('binary', 7400) and (True, 'binary FBX version 7400')."""
    data = _valid_7400_header()
    assert len(data) == 27
    assert fbx_header(data) == ("binary", 7400)
    assert check_fbx_header(data) == (True, "binary FBX version 7400")


@pytest.mark.parametrize("version", [0, 7300, 7500])
def test_binary_header_disallowed_versions(version: int):
    """Versions 0, 7300, 7500 -> binary with exact version and False with its version reason."""
    data = MAGIC + struct.pack("<I", version)
    assert fbx_header(data) == ("binary", version)
    assert check_fbx_header(data) == (False, f"binary FBX version {version}")


@pytest.mark.parametrize("prefix_len", range(27))
def test_valid_header_prefixes_are_unknown(prefix_len: int):
    """Every prefix of the valid 27-byte header of lengths 0..26 -> ('unknown', None) and (False, 'not an FBX header'), no exception."""
    data = _valid_7400_header()[:prefix_len]
    assert len(data) == prefix_len
    assert fbx_header(data) == ("unknown", None)
    assert check_fbx_header(data) == (False, "not an FBX header")


@pytest.mark.parametrize("corrupt_idx", range(len(MAGIC)))
def test_magic_single_byte_corruption(corrupt_idx: int):
    """One-byte magic corruption -> unknown/False."""
    raw = bytearray(_valid_7400_header())
    raw[corrupt_idx] ^= 0x01
    corrupted = bytes(raw)
    assert fbx_header(corrupted) == ("unknown", None)
    assert check_fbx_header(corrupted) == (False, "not an FBX header")


@pytest.mark.parametrize(
    "ascii_sample",
    [
        b"; FBX 7.4.0 project file",
        b";FBX",
        b"; FBX",
        b";\n; FBX Header Block\n;",
        b";" + b"X" * 100 + b"FBX" + b"X" * 50,
        b";" + b" " * 196 + b"FBX",  # 'FBX' ends at byte index 200 (within first 200 bytes)
        b";" + b" " * 196 + b"FBX" + b" extra trailing payload beyond 200 bytes",
    ],
)
def test_ascii_header_within_200_bytes_recognized(ascii_sample: bytes):
    """Semicolon-leading ASCII containing the complete FBX token within first 200 bytes -> ascii/False/'ASCII FBX'."""
    assert fbx_header(ascii_sample) == ("ascii", None)
    assert check_fbx_header(ascii_sample) == (False, "ASCII FBX")


@pytest.mark.parametrize(
    "invalid_sample",
    [
        b"FBX 7.4.0 project file",  # missing leading semicolon
        b"// FBX 7.4.0 project file",  # wrong comment character
        b" ; FBX 7.4.0 project file",  # semicolon is not the first byte
        b"; pure ASCII comment with no token",  # missing FBX token
        b";" + b" " * 197 + b"FBX",  # token starts at byte index 198 (ends at 201; not within first 200 bytes)
        b";" + b" " * 250 + b"FBX project file",  # token only beyond first 200 bytes
        b";" + b" " * 198 + b"FBX",  # token split across boundary: only 'FB' in [:200]
        b";" + b" " * 199 + b"FBX",  # token split across boundary: only 'F' in [:200]
        b"",  # empty data
    ],
)
def test_ascii_header_missing_semicolon_or_beyond_window_is_unknown(invalid_sample: bytes):
    """Missing leading semicolon or token only beyond that window -> unknown/False."""
    assert fbx_header(invalid_sample) == ("unknown", None)
    assert check_fbx_header(invalid_sample) == (False, "not an FBX header")


@pytest.mark.parametrize(
    "trailing_payload",
    [
        b"\x00" * 64,
        b"arbitrary trailing payload \xff\xfe\x00\x01\x02",
        b"GlobalSettings\x00\x00\x00",
        b"\xde\xad\xbe\xef" * 50,
        b"; FBX in trailing data should not override binary magic",
    ],
)
def test_valid_7400_header_with_arbitrary_trailing_bytes(trailing_payload: bytes):
    """Arbitrary trailing bytes after a valid 7400 header -> header accepted (explicitly not whole-file certification)."""
    data = _valid_7400_header() + trailing_payload
    assert len(data) > 27
    assert fbx_header(data) == ("binary", 7400)
    assert check_fbx_header(data) == (True, "binary FBX version 7400")
