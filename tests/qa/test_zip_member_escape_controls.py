"""Characterization of ZIP member read crashes in V001 validation.

new-case: Pattern n/a. Until #979 these witnesses pinned that encrypted-flag and unsupported-method members ESCAPE the
validator as exceptions. The approved qa.package rework of #979 (row_updates #973/#978: "зашифрованный GeoJSON ... свой
код, без падения") is the user-approved wrapping this module foresaw: the bundle reader (twinqa) still lets them
escape, while tools/qa/validate_package.py names them before reading (V001 `zip_encrypted`,
`zip_unsupported_method`). No encryption/compression policy is adopted beyond refusing.
Synthetic bytes; results never establish official compliance.
Source: docs/research/zip-member-error-report-boundary.md (PR #675).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools" / "qa")]
import validate_package as vp  # noqa: E402

from twinqa.bundle import BundleError, read_bundle  # noqa: E402
from twinqa.profiles import load_profiles  # noqa: E402

LIMIT = 4 * 10**9
HEX = {
    "stored.zip": (
        "504b030414000000000000002100ac2a93d8020000000200000005000000612e62696e6869504b01"
        "02140014000000000000002100ac2a93d80200000002000000050000000000000000000000000000"
        "000000612e62696e504b0506000000000100010033000000250000000000"
    ),
    "deflated.zip": (
        "504b030414000000080000002100ac2a93d8040000000200000005000000612e62696ecbc8040050"
        "4b0102140014000000080000002100ac2a93d8040000000200000005000000000000000000000000"
        "0000000000612e62696e504b0506000000000100010033000000270000000000"
    ),
    "encrypted-flag.zip": (
        "504b030414000100000000002100ac2a93d8020000000200000005000000612e62696e6869504b01"
        "02140014000100000000002100ac2a93d80200000002000000050000000000000000000000000000"
        "000000612e62696e504b0506000000000100010033000000250000000000"
    ),
    "method-shrink.zip": (
        "504b030414000000010000002100ac2a93d8020000000200000005000000612e62696e6869504b01"
        "02140014000000010000002100ac2a93d80200000002000000050000000000000000000000000000"
        "000000612e62696e504b0506000000000100010033000000250000000000"
    ),
}
SHA = {
    "stored.zip": "d043f43957d7144d0f9486eda1daf1105a5da1c198c3053e5f4e3a20bb6393b4",
    "deflated.zip": "6ee8de1fec3e03ac32c425e837fac906299fcfe2cefac87007c031c4f56950de",
    "encrypted-flag.zip": "92e24ded66dba40d2196f3b815ee0e84f97c52adbc9aceffad1a5562c3a7b94f",
    "method-shrink.zip": "6ae11817e94cd68b8cc00280aa68738ad51f78d3c4b6a2713fdd6274cec7699d",
}


def _write(tmp_path, name):
    data = bytes.fromhex(HEX[name])
    assert hashlib.sha256(data).hexdigest() == SHA[name]
    p = tmp_path / name
    p.write_bytes(data)
    return p, SHA[name]


def _digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_frozen_headers(tmp_path):
    enc, _ = _write(tmp_path, "encrypted-flag.zip")
    shr, _ = _write(tmp_path, "method-shrink.zip")
    e, s = enc.read_bytes(), shr.read_bytes()
    assert e[6] & 1 and e[45] & 1  # flag bit 0 local + central
    assert s[8] == 1 and s[47] == 1  # method 1 local + central
    assert not s[6] & 1 and not e[8]  # independent: other fields clean


@pytest.mark.parametrize("name,exc,frag", [
    ("encrypted-flag.zip", RuntimeError, ("encrypted", "password")),
    ("method-shrink.zip", NotImplementedError, ("compression method",)),
])
def test_api_escapes(tmp_path, name, exc, frag):
    """The bundle reader (twinqa) still lets these escape; the validator names them as a V001 finding since #979
    (qa.package acceptance: an encrypted GeoJSON gets its own code, no crash). This is the deliberate update of
    the witness the module docstring foresaw."""
    p, h = _write(tmp_path, name)
    profiles = load_profiles()
    with pytest.raises(exc) as e1:
        read_bundle(p, max_uncompressed=LIMIT)
    assert _digest(p) == h
    assert not isinstance(e1.value, BundleError)
    assert all(f in str(e1.value) for f in frag), str(e1.value)
    rep = vp.validate(p, "vpm", profiles, scene=False)
    assert _digest(p) == h
    v001 = next(s for s in rep.stages if s.id == "V001")
    zip_rows = [f for f in v001.findings if f.name == "ZIP"]
    assert rep.exit_code == 1 and len(zip_rows) == 1 and zip_rows[0].status == "fail"
    assert zip_rows[0].data["code"] == CODE[name]


CODE = {"encrypted-flag.zip": "zip_encrypted", "method-shrink.zip": "zip_unsupported_method"}


@pytest.mark.parametrize("name,exc", [
    ("encrypted-flag.zip", "RuntimeError"),
    ("method-shrink.zip", "NotImplementedError"),
])
def test_cli_reports_v001_code_not_a_crash(tmp_path, name, exc):
    """Before #979 the CLI died with a traceback (stdout empty); now a JSON report with the V001 code."""
    p, h = _write(tmp_path, name)
    proc = subprocess.run([sys.executable, str(REPO / "tools/qa/validate_package.py"),
                           str(p), "--profile", "vpm", "--json"],
                          cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr and exc not in proc.stderr
    report = json.loads(proc.stdout)
    v001 = next(s for s in report["stages"] if s["id"] == "V001")
    assert [f["data"]["code"] for f in v001["findings"] if f["name"] == "ZIP"] == [CODE[name]]
    assert _digest(p) == h
    assert sorted(x.name for x in tmp_path.iterdir()) == [name]


@pytest.mark.parametrize("name", ["stored.zip", "deflated.zip"])
def test_clean_controls(tmp_path, name):
    p, h = _write(tmp_path, name)
    assert read_bundle(p, max_uncompressed=LIMIT) == {"a.bin": b"hi"}
    assert _digest(p) == h
    rep = vp.validate(p, "vpm", load_profiles(), scene=False)
    assert _digest(p) == h
    v001 = next(s for s in rep.stages if s.id == "V001")
    assert not any(f.name == "ZIP" for f in v001.findings)
    # ordinary composition failure: a bundle with only a.bin is not a valid VPM package
    assert rep.exit_code != 0


def _escapes(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def test_mutation_without_the_precheck_escapes_again(tmp_path, monkeypatch):
    """In-memory only: zip_precheck is what keeps the validator from crashing; without it the escapes return."""
    enc, _ = _write(tmp_path, "encrypted-flag.zip")
    shr, _ = _write(tmp_path, "method-shrink.zip")
    ok, _ = _write(tmp_path, "stored.zip")
    profiles = load_profiles()

    def witness():
        return (_escapes(lambda: vp.validate(enc, "vpm", profiles), RuntimeError)
                and _escapes(lambda: vp.validate(shr, "vpm", profiles), NotImplementedError))

    assert not witness()  # reported, not escaping (#979)
    real = vp.zip_precheck
    monkeypatch.setattr(vp, "zip_precheck", lambda target: None)
    assert witness()  # mutation detected: the old escapes come back
    monkeypatch.setattr(vp, "zip_precheck", real)
    assert not witness()  # restored
    assert read_bundle(ok, max_uncompressed=LIMIT) == {"a.bin": b"hi"}
    assert real(ok) is None  # a clean control is not refused
