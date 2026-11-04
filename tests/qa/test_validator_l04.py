"""Lab L04 (qa.package, #908): the 22-case synthetic set of the lab's make_and_validate.py as a pytest fixture,
plus the two named defects fixed for AGR Tools 0.8:

* the profile comes from the name grammar (`{code4}_{Address}` NPM, `SM_{Address}` VPM), not from the content:
  NPM `0127_X.zip` with a stray PNG was judged VPM and the report never named the foreign file;
* V006 "embedded textures" no longer passes vacuously on an NPM FBX without any texture.

Evidence: GeoAGR-private branch lab-exp/L04, work/lab-experiments/qa.package/ (RESULT.md, host_summary.json).
The case set is rebuilt here from the lab description (synthetic bytes); no lab code is copied.
"""
import io
import json
import struct
import zipfile

import pytest
from PIL import Image

import validate_package as vp
from test_scene import mesh, rb
from twinqa.profiles import load_profiles

PROFILES = load_profiles()
FBX = b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7400) + b"\x00" * 64
FBX_75 = b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7500) + b"\x00" * 64


def _png(mode="RGB", size=256):
    b = io.BytesIO()
    Image.new(mode, (size, size), (128, 128, 128) if mode == "RGB" else (128, 128, 128, 255)).save(b, "PNG")
    return b.getvalue()


P = _png()


def _geojson():
    return json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"synthetic": True},
                       "geometry": {"type": "Point", "coordinates": [0, 0, 0]}}]}).encode()


VPM_TEX = [(f"T_TestAddr_{m}_1.1001.png", P) for m in ("Diffuse", "ERM", "Normal")]
VPM_GTEX = [(f"T_TestAddr_Ground_{m}_1.1001.png", P) for m in ("Diffuse", "ERM", "Normal")]

# case -> (profile argument, archive name, members, expected exit, {stage: substring of a non-pass finding})
CASES = {
    "npm_ok": ("npm", "0123_TestAddr.zip", [("0123_TestAddr_01.fbx", FBX), ("0123_TestAddr_Ground.fbx", FBX)], 2, {}),
    "npm_a101_double_underscore": ("npm", "0123_TestAddr.zip",
                                   [("0123_TestAddr_01.fbx", FBX), ("0123_TestAddr__Ground.fbx", FBX)], 1,
                                   {"V001": "Ground FBX", "V012": "0123_TestAddr__Ground.fbx"}),
    "npm_no_ground": ("npm", "0124_TestAddr.zip", [("0124_TestAddr_01.fbx", FBX)], 1, {"V001": "FBX count"}),
    "npm_mixed_address": ("npm", "0125_TestAddr.zip", [("0125_TestAddr_01.fbx", FBX), ("0125_TestAddr_Ground.fbx", FBX),
                                                       ("0125_Other_01.fbx", FBX)], 1, {"V012": "0125_Other_01.fbx"}),
    "npm_fbx75": ("npm", "0126_TestAddr.zip", [("0126_TestAddr_01.fbx", FBX_75), ("0126_TestAddr_Ground.fbx", FBX)], 1,
                  {"V002": "7500"}),
    "npm_stray_png_autodetect": (None, "0127_TestAddr.zip", [("0127_TestAddr_01.fbx", FBX),
                                                             ("0127_TestAddr_Ground.fbx", FBX), ("preview.png", P)], 1,
                                 {"V001": "preview.png"}),
    "vpm_ok": ("vpm", "SM_TestAddr.zip", [("SM_TestAddr.fbx", FBX), ("SM_TestAddr_Light.fbx", FBX),
                                          ("SM_TestAddr.geojson", _geojson())] + VPM_TEX, 1, {"V011": ""}),
    "vpm_no_light_geoagr_like": ("vpm", "SM_TestAddr.zip", [("SM_TestAddr.fbx", FBX), ("SM_TestAddr.geojson", _geojson())]
                                 + VPM_TEX, 1, {"V011": ""}),
    "vpm_ground_ok": ("vpm", "SM_TestAddr_Ground.zip", [("SM_TestAddr_Ground.fbx", FBX),
                                                        ("SM_TestAddr_Ground_Light.fbx", FBX),
                                                        ("SM_TestAddr_Ground.geojson", _geojson())] + VPM_GTEX, 1,
                      {"V011": ""}),
    "vpm_prefix_collision_geoagr": ("vpm", "SM_TestAddr_001.zip", [
        ("SM_TestAddr_001.fbx", FBX), ("SM_TestAddr_0011.fbx", FBX), ("SM_TestAddr_001.geojson", _geojson()),
        ("T_TestAddr_001_Diffuse_1.1001.png", P), ("T_TestAddr_0011_Diffuse_1.1001.png", P),
        ("T_TestAddr_001_ERM_1.1001.png", P)], 1, {"V001": "SM_TestAddr_0011.fbx"}),
    "vpm_nested": ("vpm", "SM_TestAddr.zip", [("SM_TestAddr/SM_TestAddr.fbx", FBX),
                                              ("SM_TestAddr/SM_TestAddr.geojson", _geojson())] + VPM_TEX, 1,
                   {"V001": "folders"}),
    "vpm_rgba_png": ("vpm", "SM_TestAddr.zip", [("SM_TestAddr.fbx", FBX), ("SM_TestAddr.geojson", _geojson())]
                     + [(n, _png("RGBA")) for n, _ in VPM_TEX], 1, {"V007": ""}),
    "zip_duplicate_member": ("vpm", "SM_TestAddr_dup.zip", "dup", 1, {"V001": "Duplicate"}),
    "zip_slip": ("vpm", "SM_TestAddr_slip.zip", [("../SM_TestAddr_slip.fbx", FBX)], 1, {"V001": ""}),
    "zip_backslash": ("vpm", "SM_TestAddr.zip", "backslash", 1, {"V001": ""}),
    "zip_empty": ("npm", "0128_TestAddr.zip", [], 1, {"V001": "FBX count"}),
    "not_a_zip": ("npm", "0129_TestAddr.zip", "garbage", 1, {"V001": "ZIP"}),
}


def _write(path, members):
    if members == "garbage":
        path.write_bytes(b"synthetic, not a zip")
        return path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if members == "dup":
            import warnings
            warnings.simplefilter("ignore")
            for _ in range(2):
                z.writestr("SM_TestAddr_dup.fbx", FBX)
            z.writestr("SM_TestAddr_dup.geojson", _geojson())
        elif members == "backslash":
            zi = zipfile.ZipInfo("x")
            zi.filename = "sub\\SM_TestAddr.fbx"
            z.writestr(zi, FBX)
        else:
            for n, d in members:
                z.writestr(n, d)
    return path


def _non_pass(report):
    return {s.id: [f"{f.status}: {f.name}: {f.observed}" for f in s.findings if f.status not in ("pass",)]
            for s in report.stages}


@pytest.fixture
def l04_case(tmp_path, request):
    profile, name, members, exit_code, expect = CASES[request.param]
    folder = tmp_path / request.param
    folder.mkdir()
    return _write(folder / name, members), profile, exit_code, expect


@pytest.mark.parametrize("l04_case", sorted(CASES), indirect=True)
def test_lab_l04_case_set(l04_case):
    path, profile, exit_code, expect = l04_case
    report = vp.validate(path, profile, PROFILES)
    assert report.exit_code == exit_code, _non_pass(report)
    bad = _non_pass(report)
    for stage, word in expect.items():
        assert any(word in f for f in bad[stage] if not f.startswith(("not_run", "review"))), (stage, bad[stage])


def test_lab_l04_synthetic_cases_and_size_boundaries():
    """The 17 synthetic archives of the lab set; its real GeoAGR-FBX archives (G1-G3 + renamed control) need the
    runner job output and are covered by run_agr_tools_package_native.py instead. Size boundary as measured."""
    assert len(CASES) == 17
    from twinqa.bundle import size_status
    for limit in (1073741824, 524288000):
        assert [size_status(n, limit)[0] for n in (limit - 1, limit, limit + 1)] == ["pass", "pass", "fail"]
    assert size_status(10**9, 524288000)[0] == "fail"


# ---- defect 1: profile from the name grammar ----------------------------------------------------------------
def test_stray_png_in_npm_archive_is_judged_npm_and_names_the_foreign_file(tmp_path):
    """RED on 4e275ca1: kind 'vpm', V001 'main FBX' / V012 'archive name SM_...'; preview.png never named."""
    path = _write(tmp_path / "0127_X.zip", [("0127_X_01.fbx", FBX), ("0127_X_Ground.fbx", FBX), ("preview.png", P)])
    report = vp.validate(path, None, PROFILES)
    assert report.profile == "npm"
    v1 = [f for s in report.stages if s.id == "V001" for f in s.findings]
    assert any(f.status == "fail" and f.name == "foreign files" and "preview.png" in f.observed for f in v1)
    assert not any(f.name == "main FBX" for f in v1)
    assert any("name grammar" in n for n in report.notes)


@pytest.mark.parametrize("name, kind", [("0127_X.zip", "npm"), ("SM_X.zip", "vpm"), ("SM_X_Ground.zip", "vpm"),
                                        ("0123_X_01.fbx", "npm"), ("SM_X.fbx", "vpm"), ("delivery.zip", None),
                                        ("012_X.zip", None), ("sm_X.zip", None)])
def test_profile_from_name(name, kind):
    assert vp.profile_from_name(name) == kind


def test_vpm_fbx_named_sm_is_vpm_not_npm(tmp_path):
    path = tmp_path / "SM_X.fbx"
    path.write_bytes(FBX)
    assert vp.validate(path, None, PROFILES).profile == "vpm"


def test_unnamed_archive_still_falls_back_to_content_with_a_note(tmp_path):
    path = _write(tmp_path / "delivery.zip", [("a.fbx", FBX), ("b.png", P)])
    report = vp.validate(path, None, PROFILES)
    assert report.profile == "vpm" and any("from archive content" in n for n in report.notes)


# ---- defect 2: vacuous V006 ------------------------------------------------------------------------------------
def _npm_zip(tmp_path):
    return _write(tmp_path / "0123_X.zip", [("0123_X_01.fbx", FBX), ("0123_X_Ground.fbx", FBX)])


def _v006(report):
    return [f for s in report.stages if s.id == "V006" for f in s.findings if f.name == "embedded textures"]


def test_npm_fbx_without_any_texture_is_not_a_v006_pass(monkeypatch, tmp_path):
    """RED on 4e275ca1: 'embedded textures: all embedded' passed on FBX with no image at all."""
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(mesh(name="SM_X_001_Main")))
    report = vp.validate(_npm_zip(tmp_path), "npm", PROFILES, scene=True)
    by_file = {f.evidence: f.status for f in _v006(report)}
    assert by_file == {"0123_X_01.fbx": "fail", "0123_X_Ground.fbx": "review"}, by_file
    assert all("no texture" in f.observed for f in _v006(report))
    assert report.exit_code == 1


def test_npm_fbx_with_packed_texture_still_passes_v006(monkeypatch, tmp_path):
    def packed(path, blender=None, timeout=600):
        r = rb(mesh(name="SM_X_001_Main"))
        r["images"] = [{"name": "T_X_001_Main_d_1.png", "packed": True}]
        return r
    monkeypatch.setattr(vp, "readback", packed)
    report = vp.validate(_npm_zip(tmp_path), "npm", PROFILES, scene=True)
    assert {f.status for f in _v006(report)} == {"pass"}
