"""Broken ZIP names and broken JPEGs stay in the report (issue #751).

Empty and partial archives fail closed. A second member is named in the finding
when its name cannot be decoded. An output path that is an input writes nothing.
"""
import base64
import pytest
import json
import struct
import subprocess
import sys
import zlib
from io import BytesIO
from pathlib import Path

from PIL import Image

import validate_package as vp
from twinqa.bundle import BundleError, read_bundle
from twinqa.geojson import _image
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
UTF = 0x800
PAYLOAD = b"hi"
ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"


def _stored(name: bytes, payload: bytes, flag: int):
    crc = zlib.crc32(payload)
    n = len(payload)
    local = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, flag, 0, 0, 0x21, crc, n, n, len(name), 0)
    local += name + payload
    central = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, flag, 0, 0, 0x21, crc, n, n,
                          len(name), 0, 0, 0, 0, 0, 0) + name
    return local, central


def _zip(members: list[tuple[bytes, bytes]]) -> bytes:
    locals_, centrals = [], []
    offset = 0
    for local, central in members:
        (sig, ver, need, flag, meth, time, date, crc, csize, usize, nlen, elen, clen,
         disk, iattr, eattr, _off) = struct.unpack("<IHHHHHHIIIHHHHHII", central[:46])
        name = central[46:]
        assert nlen == len(name) and elen == clen == 0
        central = struct.pack("<IHHHHHHIIIHHHHHII", sig, ver, need, flag, meth, time, date, crc,
                              csize, usize, nlen, elen, clen, disk, iattr, eattr, offset) + name
        locals_.append(local)
        centrals.append(central)
        offset += len(local)
    body = b"".join(locals_)
    central_blob = b"".join(centrals)
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(members), len(members),
                       len(central_blob), len(body), 0)
    return body + central_blob + eocd


def test_empty_and_partial_zip_fail_closed(tmp_path):
    blobs = {"empty": b"", "partial": b"PK\x03\x04", "truncated-header": b"PK"}
    for name, blob in blobs.items():
        path = tmp_path / f"{name}.zip"
        path.write_bytes(blob)
        report = vp.validate(path, "npm", PROFILES)
        v1 = next(stage for stage in report.stages if stage.id == "V001")
        assert any(item.name == "ZIP" and item.status == "fail" for item in v1.findings)
        assert report.passed is False and report.exit_code == 1
        assert v1.status == "fail"
        assert path.read_bytes() == blob
        assert not list(tmp_path.glob("*.partial"))


def test_bad_second_member_is_named_and_the_first_is_not_a_pass(tmp_path):
    good, bad = b"a.bin", b"\xff.bin"
    blob = _zip([_stored(good, PAYLOAD, 0), _stored(bad, PAYLOAD, UTF)])
    path = tmp_path / "two.zip"
    path.write_bytes(blob)
    with pytest.raises(BundleError) as info:
        read_bundle(path, 10**6)
    assert isinstance(info.value.__cause__, UnicodeDecodeError)
    assert info.value.member == bad.decode("utf-8", errors="backslashreplace")
    report = vp.validate(path, "npm", PROFILES)
    v1 = next(stage for stage in report.stages if stage.id == "V001")
    (finding,) = v1.findings
    assert finding.name == "ZIP" and finding.status == "fail"
    assert finding.data["member"] == info.value.member
    assert "a.bin" not in finding.data["member"]
    assert report.passed is False and report.exit_code == 1
    assert path.read_bytes() == blob


def test_jpeg_size_and_non_image_tokens_fail_closed():
    """256x256 is the required size. One pixel off, empty, and non-image tokens fail."""
    def encoded(size):
        buf = BytesIO()
        Image.new("RGB", size, (1, 2, 3)).save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    assert _image(encoded((256, 256))).status == "pass"
    assert _image(encoded((257, 257))).status == "fail"
    assert _image("").status == "fail"
    assert _image("nan").status == "fail"
    assert _image("Infinity").status == "fail"


def test_output_alias_of_an_input_writes_nothing(tmp_path):
    src = tmp_path / "in.json"
    src.write_bytes(b"{}")
    before = src.read_bytes()
    with pytest.raises(ValueError, match="input"):
        vp.write_new(src, b'{"report":1}', [src])
    assert src.read_bytes() == before
    assert not (tmp_path / "in.json.partial").exists()

    partial_as_input = tmp_path / "out.json.partial"
    partial_as_input.write_bytes(b"keep")
    with pytest.raises(ValueError, match="input"):
        vp.write_new(tmp_path / "out.json", b"report", [partial_as_input])
    assert partial_as_input.read_bytes() == b"keep"
    assert not (tmp_path / "out.json").exists()


def test_cli_undecodable_name_stdout_is_the_report(tmp_path):
    blob = _zip([_stored(b"\xff.bin", PAYLOAD, UTF)])
    archive = tmp_path / "badname.zip"
    archive.write_bytes(blob)
    proc = subprocess.run(
        [sys.executable, str(CLI), str(archive), "--profile", "npm", "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120)
    assert proc.returncode == 1 and proc.stderr == ""
    report = json.loads(proc.stdout)
    assert report["exit_code"] == 1 and report["passed"] is False
    v1 = next(stage for stage in report["stages"] if stage["id"] == "V001")
    (finding,) = [item for item in v1["findings"] if item["name"] == "ZIP"]
    assert finding["status"] == "fail"
    assert finding["data"]["exception_class"] == "UnicodeDecodeError"
    assert finding["data"]["rule_id"] == "V001"
    assert finding["data"]["file"] == archive.name
    assert archive.read_bytes() == blob
    assert not list(tmp_path.glob("*.partial"))
