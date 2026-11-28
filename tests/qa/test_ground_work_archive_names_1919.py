"""new-case: tests/qa/test_ground_work_archive_names_1919.py - #1919 validator gaps.

1. An explicit `--master ground=PATH` work FBX is read with --scene and its D312 topology is recorded in V003
   'ground work quads', separate from the delivered-FBX scene checks and from the OKS 'master quads' result; no
   facade checks on Ground. Without an eligible readback (no --scene, several sources, not an FBX, missing,
   the package itself, the OKS file, readback error) it is a V003 not_run naming what was not checked.
2. Archive addresses in V012 use the shared grammar `package_core.ADDRESS`: repeated/leading/trailing `_` fail,
   while the loose profile hint still selects the profile of a malformed name.
Readbacks are fakes, fixtures synthetic; no DCC, no geometric equivalence inferred.
"""
import itertools
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import validate_package as vp
from test_scene import mesh, rb
from test_validator import PROFILES, STEM, fbx, good_files

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import package_core  # noqa: E402

QUADS = {"4": 6}
TRIS = {"4": 4, "3": 2}
NGON = {"4": 4, "5": 1}


def v003(report, name):
    return [f for s in report.stages if s.id == "V003" for f in s.findings if f.name == name]


def unused_roles(report):
    return sorted(f.data["role"] for s in report.stages for f in s.findings
                  if f.data.get("code") == "master_role_unused")


@pytest.fixture
def fake(monkeypatch):
    """Readback double: file name -> polygon histogram; every call is recorded."""
    calls, table = [], {}

    def readback(path, *a, **k):
        name = Path(path).name
        calls.append(name)
        spec = table.get(name, QUADS)
        if isinstance(spec, Exception):
            raise spec
        if spec == "broken":
            return {"source": str(path), "readback_ok": False, "error": "synthetic import error", "meshes": []}
        out = rb(mesh(name="SM_Test_K_1_Main" if "ground" not in name else "SM_Test_K_1_Ground",
                      tris=sum(spec.values()), degrees=dict(spec)))
        out["source"] = str(path)
        return out

    monkeypatch.setattr(vp, "readback", readback)
    return calls, table


def target_fbx(tmp):
    p = tmp / f"{STEM}.fbx"
    p.write_bytes(fbx())
    return p


def work(tmp, name):
    p = tmp / name
    p.write_bytes(b"synthetic work fbx " + name.encode())
    return p


# ---- Ground work FBX -------------------------------------------------------------------------------------------
def test_ground_and_oks_and_delivery_are_separate_results_in_one_report(tmp_path, fake):
    calls, table = fake
    target, oks, ground = target_fbx(tmp_path), work(tmp_path, "oks_work.fbx"), work(tmp_path, "ground_work.fbx")
    table["ground_work.fbx"] = TRIS
    r = vp.validate(target, None, PROFILES, scene=True, master={"oks": oks, "ground": ground})
    assert calls == [target.name, "oks_work.fbx", "ground_work.fbx"]  # delivery, OKS master, Ground work: once each
    [g] = v003(r, "ground work quads")
    [o] = v003(r, "master quads")
    assert g.status == "pass" and g.data["role"] == "ground" and g.data["input"] == str(ground)
    assert g.data["objects"][0]["name"] == "SM_Test_K_1_Ground" and g.data["objects"][0]["triangles"] == 2
    assert "oks_work.fbx" in o.observed and "ground_work" not in o.observed
    assert unused_roles(r) == []
    # delivered-FBX scene checks still ran on the target (V002/V004.. from the target readback)
    assert any(f.name != "master quads" for s in r.stages if s.id != "V003" for f in s.findings)
    assert any("ground work readback: ground_work.fbx" in n for n in r.notes)


def test_ground_ngon_fails_and_oks_result_stays_its_own(tmp_path, fake):
    calls, table = fake
    target, oks, ground = target_fbx(tmp_path), work(tmp_path, "oks_work.fbx"), work(tmp_path, "ground_work.fbx")
    table["ground_work.fbx"] = NGON
    r = vp.validate(target, None, PROFILES, scene=True, master={"oks": oks, "ground": ground})
    [g] = v003(r, "ground work quads")
    assert g.status == "fail" and g.data["objects"][0]["ngons"] == 1
    assert [f.status for f in v003(r, "master quads")] == ["pass"]
    assert r.exit_code == 1


def test_ground_only_runs_no_facade_checks(tmp_path, fake):
    target, ground = target_fbx(tmp_path), work(tmp_path, "ground_work.fbx")
    base = vp.validate(target, None, PROFILES, scene=True)
    r = vp.validate(target, None, PROFILES, scene=True, master={"ground": ground})
    added = sorted((s.id, f.name) for s in r.stages for f in s.findings)
    for s in base.stages:
        for f in s.findings:
            added.remove((s.id, f.name))
    assert added == [("V003", "ground work quads")]  # no decor/edge-loop/quad-size on Ground
    assert [f.observed for f in v003(r, "master quads")] == ["quad work FBX not given (--master)"]


def test_ground_readback_not_ok_is_a_fail(tmp_path, fake):
    _, table = fake
    target, ground = target_fbx(tmp_path), work(tmp_path, "ground_work.fbx")
    table["ground_work.fbx"] = "broken"
    [g] = v003(vp.validate(target, None, PROFILES, scene=True, master={"ground": ground}), "ground work quads")
    assert g.status == "fail" and "synthetic import error" in g.observed


def _not_run_cases(tmp):
    target = target_fbx(tmp)
    oks, ground = work(tmp, "oks_work.fbx"), work(tmp, "ground_work.fbx")
    other = work(tmp, "ground_b.fbx")
    blend = work(tmp, "ground.blend")
    alias = tmp / "sub" / ".." / "oks_work.fbx"
    (tmp / "sub").mkdir()
    return target, {
        "no_scene": (False, {"ground": ground}, "only with --scene"),
        "two_sources": (True, {"ground": [ground, other]}, "never picks one"),
        "not_fbx": (True, {"ground": blend}, "not an FBX work file"),
        "missing": (True, {"ground": tmp / "absent.fbx"}, "does not exist"),
        "is_target": (True, {"ground": target}, "validated package itself"),
        "is_oks_alias": (True, {"oks": oks, "ground": alias}, "also the OKS master"),
        "readback_error": (True, {"ground": ground}, "readback failed"),
    }


@pytest.mark.parametrize("case", ["no_scene", "two_sources", "not_fbx", "missing", "is_target", "is_oks_alias",
                                  "readback_error"])
def test_ground_without_eligible_readback_is_not_run_and_says_what(tmp_path, fake, case):
    calls, table = fake
    target, cases = _not_run_cases(tmp_path)
    scene, master, why = cases[case]
    if case == "readback_error":
        table["ground_work.fbx"] = RuntimeError("blender missing")
    r = vp.validate(target, None, PROFILES, scene=scene, master=master)
    [g] = v003(r, "ground work quads")
    assert g.status == "not_run" and g.data["code"] == "ground_work_unread" and why in g.data["reason"]
    assert "not checked" in g.observed
    # V001 disclosure kept (now with the Ground reason); an alias of the read OKS file is "used" per #1810
    assert ("ground" in unused_roles(r)) is (case != "is_oks_alias")
    if case != "readback_error":
        assert not any("ground" in c for c in calls)  # no first-file pick, nothing read
    assert not r.passed


def test_unnamed_and_oks_masters_get_no_ground_result(tmp_path, fake):
    target, oks = target_fbx(tmp_path), work(tmp_path, "oks_work.fbx")
    for master in (oks, {"oks": oks}, None):
        r = vp.validate(target, None, PROFILES, scene=True, master=master)
        assert v003(r, "ground work quads") == []


def test_v001_hash_audit_is_independent_of_the_ground_read(tmp_path, fake):
    import test_ground_master_1525 as gm
    pkg, oks, ground, stores = gm.mixed(tmp_path)
    assert gm.build(pkg, ["oks=" + str(oks), "ground=" + str(ground)], stores) == 0
    plain = vp.validate(pkg, None, PROFILES, master={"oks": oks, "ground": ground})
    scene = vp.validate(pkg, None, PROFILES, scene=True, master={"oks": oks, "ground": ground})
    v001 = lambda r: [(f.status, f.name, f.observed) for s in r.stages if s.id == "V001" for f in s.findings]
    assert [x for x in v001(scene) if x[1] == "build manifest"] == [x for x in v001(plain) if x[1] == "build manifest"]
    [g] = v003(scene, "ground work quads")  # ground_mesh.json is hashed in V001 but is no work FBX
    assert g.status == "not_run" and "not an FBX work file" in g.data["reason"]


# ---- archive address grammar ------------------------------------------------------------------------------------
def _npm_v012(stem, names=None):
    st = vp.build_stages(PROFILES, "npm")
    names = names or [f"{stem}_Ground.fbx", f"{stem}_01.fbx"]
    vp.validate_npm_zip(stem, {n: fbx() for n in names}, PROFILES.profile("npm"), st)
    return {f.name: f.status for f in st["V012"].findings}


def _vpm_v012(stem):
    st = vp.build_stages(PROFILES, "vpm")
    files = {f"{stem}.fbx": fbx(), f"{stem}.geojson": good_files()[f"{STEM}.geojson"]}
    vp.validate_vpm_zip(stem, files, PROFILES.profile("vpm"), st)
    return [f.status for f in st["V012"].findings if f.name == "archive name"]


@pytest.mark.parametrize("stem, ok", [("0000_A_B", True), ("0000_Ul1_d5", True), ("0000_A__B", False),
                                      ("0000__A", False), ("0000_A_", False), ("0000_", False)])
def test_npm_archive_address_uses_shared_grammar(stem, ok):
    got = _npm_v012(stem)
    if ok:
        assert got == {"FBX names": "pass"}
    else:
        assert got == {"archive name": "fail"}


def test_npm_valid_part_names_still_pass():
    stem = "0000_A_B"
    names = [f"{stem}_Ground.fbx"] + [f"{stem}_{i:02d}.fbx" for i in range(1, 21)]
    assert _npm_v012(stem, names) == {"FBX names": "pass"}
    assert _npm_v012(stem, [f"{stem}_Ground.fbx", f"{stem}_21.fbx"]) == {"FBX names": "fail"}


@pytest.mark.parametrize("stem, status", [("SM_Test_K_1", "review"), ("SM_Test_K_1_Ground", "pass"),
                                          ("SM_Test__K", "fail"), ("SM__Test", "fail"), ("SM_Test_", "fail"),
                                          ("SM_Test__Ground", "fail"), ("SM_", "fail")])
def test_vpm_archive_address_uses_shared_grammar_and_keeps_review(stem, status):
    assert _vpm_v012(stem) == [status]


@pytest.mark.parametrize("name, kind", [("0000_A__B.zip", "npm"), ("0000_A_.zip", "npm"), ("SM__X.zip", "vpm"),
                                        ("SM_X__Ground.zip", "vpm"), ("0000-A.zip", None)])
def test_profile_hint_keeps_malformed_names_on_their_profile(name, kind):
    assert vp.profile_from_name(name) == kind


def test_probe_brute_force_address_verdicts_match_independent_oracle():
    """Every address over {A, 1, _} up to 5 chars: V012 fails iff some `_`-separated word is empty."""
    n = 0
    for length in range(1, 6):
        for chars in itertools.product("A1_", repeat=length):
            addr = "".join(chars)
            oracle = all(w and w.isalnum() for w in addr.split("_"))
            assert bool(vp.NPM_ARCHIVE.match(f"0000_{addr}")) is oracle, addr
            assert bool(vp.VPM_ARCHIVE.match(f"SM_{addr}")) is oracle, addr
            assert vp.profile_from_name(f"0000_{addr}.zip") == "npm"
            n += 1
    assert n == 363


def test_no_duplicate_address_regex_owner():
    src = (ROOT / "tools/qa/validate_package.py").read_text(encoding="utf-8")
    assert "from adapters.max.agr_tools.package_core import ADDRESS" in src
    assert vp.NPM_ARCHIVE.pattern == r"^(?P<code>[0-9]{4})_(?P<address>" + package_core.ADDRESS + r")$"
    assert re.search(r"\(\?P<address>\[A-Za-z0-9_\]", src) is None


def test_cli_fresh_process_reports_malformed_npm_name(tmp_path):
    target = tmp_path / "0000_A__B.zip"
    with zipfile.ZipFile(target, "w") as z:
        z.writestr("0000_A__B_Ground.fbx", fbx())
        z.writestr("0000_A__B_01.fbx", fbx())
    r = subprocess.run([sys.executable, str(ROOT / "tools/qa/validate_package.py"), str(target), "--json"],
                       capture_output=True, text=True, cwd=str(tmp_path))
    doc = json.loads(r.stdout)
    assert doc["profile"] == "npm" and r.returncode == 1
    v12 = [(f["name"], f["status"]) for s in doc["stages"] if s["id"] == "V012" for f in s["findings"]]
    assert ("archive name", "fail") in v12
