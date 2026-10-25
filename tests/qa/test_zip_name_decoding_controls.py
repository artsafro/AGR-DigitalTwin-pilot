"""Measured legacy characterization (NOT approved handling, NOT delivery certification) of ZIP member
names that are invalid UTF-8 while general-purpose flag bit 11 is set (pilot PR #685, next task 1).

Pattern: new-case: persist central-open vs local-read UnicodeDecodeError escape controls.

Fixtures are stored ZIPs built with struct (no zipfile writer); local and central name bytes and flag
words are set independently and the raw headers are re-parsed independently before any reader runs.
Observed today: the exception escapes read_bundle/validate() (no V001 ZIP finding, no report); the
CLI prints a traceback, stdout is empty, exit 1. A future fix may legitimately change these rows.
"""
import hashlib
import struct
import subprocess
import sys
import traceback
import zipfile
import zlib
from pathlib import Path

import pytest

import validate_package as vp
from dt_ai.publish.bundle import read_bundle as dev_read_bundle
from twinqa.bundle import read_bundle as qa_read_bundle
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
PAYLOAD = b"payload-bytes-0123456789"
BAD = b"\xff\xfe.bin"
UTF = 0x800
ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"

# name: (local name, central name, local flag, central flag, readable)
FIXTURES = {
    "ascii_off": (b"a.bin", b"a.bin", 0, 0, b"a.bin"),
    "ascii_on": (b"a.bin", b"a.bin", UTF, UTF, b"a.bin"),
    "utf8_on": ("é.bin".encode(), "é.bin".encode(), UTF, UTF, "é.bin".encode()),
    "cp437_off": (BAD, BAD, 0, 0, BAD),
    "bad_both": (BAD, BAD, UTF, UTF, None),
    "bad_central": (b"a.bin", BAD, UTF, UTF, None),
    "bad_local": (BAD, b"a.bin", UTF, UTF, None),
}
EXPECTED_NAME = {"ascii_off": "a.bin", "ascii_on": "a.bin", "utf8_on": "é.bin", "cp437_off": BAD.decode("cp437")}
CENTRAL_BAD = ("bad_both", "bad_central")
LOCAL_BAD = ("bad_local",)


def build(local_name, central_name, lflag, cflag) -> bytes:
    crc = zlib.crc32(PAYLOAD)
    n = len(PAYLOAD)
    local = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, lflag, 0, 0, 0x21, crc, n, n, len(local_name), 0)
    local += local_name + PAYLOAD
    central = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, cflag, 0, 0, 0x21, crc, n, n,
                          len(central_name), 0, 0, 0, 0, 0, 0) + central_name
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(central), len(local), 0)
    return local + central + eocd


def parse(blob: bytes) -> dict:
    """Independent raw-header parse; no zipfile."""
    sig, _v, lflag, meth, _t, _d, crc, csize, usize, nlen, xlen = struct.unpack_from("<IHHHHHIIIHH", blob, 0)
    assert sig == 0x04034B50 and meth == 0 and xlen == 0 and csize == usize
    lname = blob[30:30 + nlen]
    data = blob[30 + nlen:30 + nlen + usize]
    cpos = 30 + nlen + usize
    (csig, _a, _b, cflag, _m, _t2, _d2, ccrc, ccs, cus, cnl, cxl, ccl, _dn, _ia, _ea,
     loff) = struct.unpack_from("<IHHHHHHIIIHHHHHII", blob, cpos)
    assert csig == 0x02014B50 and cxl == 0 and ccl == 0 and loff == 0
    cname = blob[cpos + 46:cpos + 46 + cnl]
    epos = cpos + 46 + cnl
    esig, _d3, _d4, ne, nt, esize, eoff, ecl = struct.unpack_from("<IHHHHIIH", blob, epos)
    assert esig == 0x06054B50 and ne == nt == 1 and eoff == cpos and esize == epos - cpos and ecl == 0
    assert epos + 22 == len(blob)
    assert crc == ccrc == zlib.crc32(data) and ccs == cus == usize == len(PAYLOAD)
    return {"lname": lname, "cname": cname, "lflag": lflag, "cflag": cflag, "data": data}


@pytest.fixture(scope="module")
def zips(tmp_path_factory):
    folder = tmp_path_factory.mktemp("zipnames")
    out = {}
    for key, (ln, cn, lf, cf, _r) in FIXTURES.items():
        blob = build(ln, cn, lf, cf)
        p = folder / f"{key}.zip"
        p.write_bytes(blob)
        info = parse(blob)
        assert (info["lname"], info["cname"], info["lflag"], info["cflag"]) == (ln, cn, lf, cf)
        assert info["data"] == PAYLOAD
        out[key] = (p, hashlib.sha256(blob).hexdigest())
    yield out
    for p, digest in out.values():  # inputs unchanged after every call
        assert hashlib.sha256(p.read_bytes()).hexdigest() == digest


def frames(exc) -> set[str]:
    return {f.name for f in traceback.extract_tb(exc.__traceback__)}


def raises_unicode(fn, *args):
    with pytest.raises(UnicodeDecodeError) as info:
        fn(*args)
    return frames(info.value)


@pytest.mark.parametrize("key", list(EXPECTED_NAME))
def test_readable_controls_return_exact_name_and_payload(zips, key):
    path, _ = zips[key]
    name = EXPECTED_NAME[key]
    with zipfile.ZipFile(path) as z:
        assert z.namelist() == [name] and z.read(name) == PAYLOAD
    assert qa_read_bundle(path, 10**6) == {name: PAYLOAD}
    assert dev_read_bundle(path) == {name: PAYLOAD}


@pytest.mark.parametrize("key", list(EXPECTED_NAME))
def test_readable_controls_give_ordinary_composition_failures_not_zip_finding(zips, key):
    report = vp.validate(zips[key][0], "npm", PROFILES)
    v1 = next(s for s in report.stages if s.id == "V001")
    names = {f.name: f.status for f in v1.findings}
    assert "ZIP" not in names
    assert names["foreign files"] == "fail" and names["FBX count"] == "fail"
    assert report.passed is False


@pytest.mark.parametrize("key", CENTRAL_BAD)
def test_central_invalid_fails_at_open_in_every_reader(zips, key):
    path, _ = zips[key]
    assert "_RealGetContents" in raises_unicode(zipfile.ZipFile, path)
    for fn, args in ((qa_read_bundle, (path, 10**6)), (dev_read_bundle, (path,)),
                     (vp.validate, (path, "npm", PROFILES))):
        assert "_RealGetContents" in raises_unicode(fn, *args)


@pytest.mark.parametrize("key", LOCAL_BAD)
def test_local_only_invalid_opens_lists_then_fails_at_read(zips, key):
    path, _ = zips[key]
    with zipfile.ZipFile(path) as z:
        assert z.namelist() == ["a.bin"]
        with pytest.raises(UnicodeDecodeError) as info:
            z.read("a.bin")
    assert "open" in frames(info.value) and "_RealGetContents" not in frames(info.value)
    for fn, args in ((qa_read_bundle, (path, 10**6)), (dev_read_bundle, (path,)),
                     (vp.validate, (path, "npm", PROFILES))):
        fr = raises_unicode(fn, *args)
        assert "open" in fr and "_RealGetContents" not in fr


def cli(path):
    return subprocess.run([sys.executable, str(CLI), str(path), "--profile", "npm", "--json"],
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=300)


@pytest.mark.parametrize("key", ["bad_central", "bad_local"])
def test_cli_malformed_loses_report(zips, key):
    run = cli(zips[key][0])
    assert run.returncode == 1 and run.stdout == ""
    assert "Traceback" in run.stderr and "UnicodeDecodeError" in run.stderr


@pytest.mark.parametrize("key", ["ascii_on", "cp437_off"])
def test_cli_readable_controls_emit_json(zips, key):
    import json
    run = cli(zips[key][0])
    assert run.returncode == 1 and run.stderr == ""
    data = json.loads(run.stdout)
    v1 = next(s for s in data["stages"] if s["id"] == "V001")
    names = {f["name"] for f in v1["findings"]}
    assert "ZIP" not in names and {"foreign files", "FBX count"} <= names
