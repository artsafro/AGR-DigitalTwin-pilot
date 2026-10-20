"""Synthetic PNG fixed-field new-case regressions; metadata is not integrity approval."""
import hashlib
import json
import struct
import zipfile
import zlib

import numpy as np
import pytest

import validate_package as vp
from twinqa.png import PngFacts, SIGNATURE, npm_texture_findings, png_facts, vpm_texture_findings
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
FROZEN = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63103209030000f8009dcc6a21780000000049454e44ae426082"
)
TRUNCATED = list(range(16, 33)) + list(range(41, 57))
ROUTES = ["direct", "npm", "Diffuse", "ERM", "Normal"]


def chunk(kind, body=b""):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body)))


def image(side=1, ct=2, trns=False):
    pixel = {2: b"\x12\x34\x56", 6: b"\x12\x34\x56\x80", 3: b"\x00"}[ct]
    extra = chunk(b"PLTE", b"\x12\x34\x56") if ct == 3 else b""
    if trns:
        extra += chunk(b"tRNS", b"\x00")
    return (SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, ct, 0, 0, 0))
            + extra + chunk(b"IDAT", zlib.compress((b"\x00" + pixel * side) * side))
            + chunk(b"IEND"))


def test_frozen_synthetic_rgb():
    assert image() == FROZEN
    assert len(FROZEN) == 69
    assert hashlib.sha256(FROZEN).hexdigest() == "4258699ba0181027db1c32e7d9360339ccf87658015a24cd1424a0a5bd1b329c"


def assert_rejected(data, route, diagnostic):
    before = bytes(data)
    name = "probe.png" if route in ("direct", "npm") else f"T_Probe_{route}_1.1001.png"
    if route == "direct":
        with pytest.raises(ValueError, match=diagnostic):
            png_facts(name, data)
    else:
        if route == "npm":
            findings = npm_texture_findings({name: data}, PROFILES.npm)
        else:
            findings, sets = vpm_texture_findings({name: data}, PROFILES.vpm, "T_Probe")
            assert sets == {}
        assert len(findings) == 1
        f = findings[0]
        assert (f.status, f.name, f.evidence) == ("fail", "PNG readable", name)
        assert diagnostic in f.observed
        assert f.observed.startswith(name + ": ")
    assert data == before


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("n", TRUNCATED)
def test_truncated_fixed_fields(n, route):
    assert_rejected(FROZEN[:n], route, "truncated")


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("n", range(16))
def test_empty_and_short_signature_remain_rejected(n, route):
    assert_rejected(FROZEN[:n], route, "not a PNG")


@pytest.mark.parametrize("route", ROUTES)
def test_existing_idat_crc_failure(route):
    data = FROZEN[:53] + bytes([FROZEN[53] ^ 1]) + FROZEN[54:]
    assert_rejected(data, route, "CRC error in IDAT chunk")


@pytest.mark.parametrize("ct,trns,length", [(2, False, 69), (6, False, 70), (3, True, 95)])
def test_valid_facts_and_wrapper_policy_unchanged(ct, trns, length):
    data = image(ct=ct, trns=trns)
    before = bytes(data)
    assert len(data) == length
    assert png_facts("probe.png", data) == PngFacts("probe.png", 1, 1, 8, ct, trns, length)
    alpha = ct == 6 or trns
    assert png_facts("probe.png", data).has_alpha == alpha
    npm = npm_texture_findings({"probe.png": data}, PROFILES.npm)
    assert [(f.status, f.name) for f in npm] == [("fail", "atlas size")] + ([("fail", "no alpha")] if alpha else [])
    for role in ("Diffuse", "ERM", "Normal"):
        name = f"T_Probe_{role}_1.1001.png"
        # The original 1x1 Normal heuristic produces a NaN review, not a pass.
        with np.errstate(invalid="ignore"):
            findings, sets = vpm_texture_findings({name: data}, PROFILES.vpm, "T_Probe")
        expected = ([] if ct in (2, 6) else [("fail", "8-bit RGB/RGBA")]) + [("fail", "map size")]
        if role != "Diffuse" and alpha:
            expected += [("fail", "no alpha in ERM/Normal")]
        if role == "ERM":
            expected += [("review", "ERM channel order")]
        elif role == "Normal":
            expected += [("review", "DirectX normal")]
        expected += [("fail", "map set")]
        assert [(f.status, f.name) for f in findings] == expected
        assert sets == {(1, 1001): {role: PngFacts(name, 1, 1, 8, ct, trns, length)}}
    assert data == before


@pytest.mark.parametrize("n", [33, *range(34, 41), *range(57, 70)])
def test_existing_structural_acceptance_is_not_integrity_approval(n):
    data = FROZEN[:n]
    assert png_facts("probe.png", data) == PngFacts("probe.png", 1, 1, 8, 2, False, n)
    assert [(f.status, f.name) for f in npm_texture_findings({"probe.png": data}, PROFILES.npm)] == [("fail", "atlas size")]
    name = "T_Probe_Diffuse_1.1001.png"
    findings, sets = vpm_texture_findings({name: data}, PROFILES.vpm, "T_Probe")
    assert [(f.status, f.name) for f in findings] == [("fail", "map size"), ("fail", "map set")]
    assert sets[(1, 1001)]["Diffuse"].size_bytes == n
    assert data == FROZEN[:n]


@pytest.mark.parametrize("profile,stage_id", [("npm", "V006"), ("vpm", "V007")])
def test_outer_validate_returns_strict_json_and_preserves_input(tmp_path, profile, stage_id):
    if profile == "npm":
        path = tmp_path / "probe.png"
        path.write_bytes(FROZEN[:25])
        bad_name = path.name
    else:
        path = tmp_path / "SM_Probe.zip"
        bad_name = "T_Probe_Diffuse_1.1001.png"
        members = {bad_name: FROZEN[:25], "T_Probe_ERM_1.1001.png": image(256),
                   "T_Probe_Normal_1.1001.png": image(256)}
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
    before = path.read_bytes()
    report = vp.validate(path, profile, PROFILES)
    stage = next(s for s in report.stages if s.id == stage_id)
    assert stage.status == "fail"
    failures = [f for f in stage.findings if f.name == "PNG readable"]
    assert len(failures) == 1
    assert failures[0].status == "fail" and failures[0].evidence == bad_name
    assert "truncated" in failures[0].observed
    assert report.passed is False
    assert json.loads(json.dumps(report.to_dict(), allow_nan=False))["passed"] is False
    assert path.read_bytes() == before
    if profile == "vpm":
        with zipfile.ZipFile(path) as archive:
            assert {name: archive.read(name) for name in archive.namelist()} == members
