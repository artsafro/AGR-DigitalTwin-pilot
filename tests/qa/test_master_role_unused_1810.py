"""#1810: an explicitly supplied `--master role=PATH` that no check used is disclosed, never silently dropped.

V001 gets one not_run finding per unused role (data.code=master_role_unused, role, reason) on a single FBX and on a
ZIP without a build manifest. A role compared by the manifest, or consumed by the independent OKS quad readback,
is not reported unused. No new fail, no fail turned into pass, exit-code rules unchanged. Fixtures are synthetic.
"""
import itertools
import json
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ground_master_1525 as gm  # noqa: E402


def unused(report):
    return [f for s in report.stages for f in s.findings if f.data.get("code") == "master_role_unused"]


def fails(report):
    return sorted((s.id, f.name, f.data.get("code")) for s in report.stages for f in s.findings
                  if f.status == "fail")


def codes(report, stage="V001"):
    return [f.data.get("code") for s in report.stages if s.id == stage for f in s.findings]


def masters(tmp):
    out = {}
    for role in ("oks", "ground", "groundel", "flora"):
        p = tmp / f"{role}_master.bin"
        p.write_bytes(b"synthetic master " + role.encode())
        out[role] = p
    return out


def single_fbx(tmp):
    p = tmp / f"{STEM}.fbx"
    p.write_bytes(fbx())
    return p


def zip_without_manifest(tmp):
    p = tmp / f"{STEM}.zip"
    with zipfile.ZipFile(p, "w") as z:
        for n, d in good_files().items():
            z.writestr(n, d)
    assert not Path(vp.build_manifest.manifest_path(p)).exists()
    return p


@pytest.fixture
def scene_double(monkeypatch):
    calls = []

    def fake(path, *a, **k):
        calls.append(Path(path).name)
        return rb(mesh())

    monkeypatch.setattr(vp, "readback", fake)
    return calls


def one_per_role(report, roles):
    found = unused(report)
    assert sorted(f.data["role"] for f in found) == sorted(roles), [f.data for f in found]
    for f in found:
        assert f.status == "not_run" and f.name == "master role"
        assert f.data["reason"] and f.data["role"] in f.observed
    v001 = [s for s in report.stages if s.id == "V001"][0]
    assert all(f in v001.findings for f in found)
    return found


# ---- single FBX ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("role", ["ground", "groundel"])
def test_fbx_without_scene_reports_each_ignored_role(tmp_path, role):
    m = masters(tmp_path)
    target = single_fbx(tmp_path)
    base = vp.validate(target, None, PROFILES)
    r = vp.validate(target, None, PROFILES, master={role: m[role]})
    found = one_per_role(r, [role])
    assert m[role].name in found[0].data["paths"][0]
    assert fails(r) == fails(base) and r.exit_code == base.exit_code and not r.passed


@pytest.mark.parametrize("role", ["ground", "groundel"])
def test_fbx_with_scene_reports_ignored_role_and_keeps_oks_quad_check(tmp_path, scene_double, role):
    m = masters(tmp_path)
    target = single_fbx(tmp_path)
    r = vp.validate(target, None, PROFILES, scene=True, master={"oks": m["oks"], role: m[role]})
    one_per_role(r, [role])
    assert "oks_master.bin" in scene_double  # the OKS quad readback ran on the oks input
    v003 = [f.name for s in r.stages if s.id == "V003" for f in s.findings]
    assert "master quads" in v003 or "master quad size" in v003
    assert not any("quad work FBX not given" in f.observed for s in r.stages for f in s.findings)


def test_fbx_without_scene_oks_role_is_unused_too(tmp_path):
    m = masters(tmp_path)
    r = vp.validate(single_fbx(tmp_path), None, PROFILES, master={"oks": m["oks"], "ground": m["ground"]})
    one_per_role(r, ["oks", "ground"])


def test_fbx_two_independent_sources_of_one_role_give_one_finding(tmp_path):
    m = masters(tmp_path)
    second = tmp_path / "ground_recipe.json"
    second.write_bytes(b"synthetic recipe")
    r = vp.validate(single_fbx(tmp_path), None, PROFILES, master={"ground": [m["ground"], second]})
    found = one_per_role(r, ["ground"])
    assert len(found[0].data["paths"]) == 2


def test_fbx_scene_with_several_oks_sources_reports_oks_unused(tmp_path, scene_double):
    m = masters(tmp_path)
    other = tmp_path / "oks_b.bin"
    other.write_bytes(b"synthetic oks b")
    r = vp.validate(single_fbx(tmp_path), None, PROFILES, scene=True, master={"oks": [m["oks"], other]})
    one_per_role(r, ["oks"])
    assert "oks_master.bin" not in scene_double


# ---- ZIP without a build manifest -------------------------------------------------------------------------------
def test_zip_without_manifest_keeps_manifest_missing_and_reports_unused_roles(tmp_path):
    m = masters(tmp_path)
    target = zip_without_manifest(tmp_path)
    base = vp.validate(target, None, PROFILES)
    r = vp.validate(target, None, PROFILES, master={"ground": m["ground"], "groundel": m["groundel"]})
    assert "manifest_missing" in codes(r)
    one_per_role(r, ["ground", "groundel"])
    assert fails(r) == fails(base) and r.exit_code == base.exit_code


def test_zip_without_manifest_oks_used_by_scene_readback_is_not_unused(tmp_path, scene_double):
    m = masters(tmp_path)
    r = vp.validate(zip_without_manifest(tmp_path), None, PROFILES, scene=True,
                    master={"oks": m["oks"], "ground": m["ground"]})
    assert "manifest_missing" in codes(r)
    one_per_role(r, ["ground"])
    assert "oks_master.bin" in scene_double


def test_zip_without_manifest_raw_path_shorthand_still_feeds_the_quad_check(tmp_path, scene_double):
    m = masters(tmp_path)
    r = vp.validate(zip_without_manifest(tmp_path), None, PROFILES, scene=True, master=m["oks"])
    assert unused(r) == [] and "oks_master.bin" in scene_double


def test_zip_with_unreadable_manifest_reports_roles_unused_and_keeps_the_fail(tmp_path):
    m = masters(tmp_path)
    target = zip_without_manifest(tmp_path)
    Path(vp.build_manifest.manifest_path(target)).write_bytes(b"{not json")
    r = vp.validate(target, None, PROFILES, master={"ground": m["ground"]})
    assert "manifest_unreadable" in codes(r) and r.exit_code == 1
    one_per_role(r, ["ground"])


# ---- controls: compared roles, no roles -------------------------------------------------------------------------
def test_zip_with_manifest_compared_roles_are_not_unused(tmp_path):
    pkg, oks, ground, stores = gm.mixed(tmp_path)
    assert gm.build(pkg, ["oks=" + str(oks), "ground=" + str(ground)], stores) == 0
    r = vp.validate(pkg, None, PROFILES, master={"oks": oks, "ground": ground})
    assert unused(r) == []
    assert not any((c or "").startswith("manifest_master") for c in codes(r))
    ground.write_bytes(b"edited after the build")  # a compared, stale role stays a fail, not unused
    stale = vp.validate(pkg, None, PROFILES, master={"oks": oks, "ground": ground})
    assert unused(stale) == [] and "manifest_master_stale" in codes(stale) and stale.exit_code == 1


def test_zip_with_manifest_foreign_role_stays_a_fail_not_unused(tmp_path):
    pkg, oks, ground, stores = gm.mixed(tmp_path)
    assert gm.build(pkg, ["oks=" + str(oks), "ground=" + str(ground)], stores) == 0
    flora = tmp_path / "flora.bin"
    flora.write_bytes(b"synthetic flora")
    r = vp.validate(pkg, None, PROFILES, master={"oks": oks, "ground": ground, "flora": flora})
    assert unused(r) == [] and "manifest_master_role" in codes(r) and r.exit_code == 1


def test_no_master_gives_no_unused_finding(tmp_path, scene_double):
    fbx_target, zip_target = single_fbx(tmp_path), zip_without_manifest(tmp_path)
    for target, scene in itertools.product((fbx_target, zip_target), (False, True)):
        assert unused(vp.validate(target, None, PROFILES, scene=scene)) == []


# ---- generated probe: every subset of roles x scene x target ----------------------------------------------------
def test_probe_role_subsets_unused_count_and_no_new_fail(tmp_path, scene_double):
    m = masters(tmp_path)
    targets = {"fbx": single_fbx(tmp_path), "zip": zip_without_manifest(tmp_path)}
    n = 0
    for kind, scene in itertools.product(targets, (False, True)):
        target = targets[kind]
        base = vp.validate(target, None, PROFILES, scene=scene)
        for k in range(1, 5):
            for roles in itertools.combinations(sorted(m), k):
                r = vp.validate(target, None, PROFILES, scene=scene, master={x: m[x] for x in roles})
                expected = [x for x in roles if not (x == "oks" and scene)]
                one_per_role(r, expected)
                assert all(f.status != "fail" for f in unused(r))
                if "oks" not in roles or not scene:  # the oks readback adds its own V003 findings
                    assert fails(r) == fails(base) and r.exit_code == base.exit_code
                n += 1
    assert n == 60


# ---- fresh-process CLI -------------------------------------------------------------------------------------------
def test_cli_json_discloses_unused_role_with_same_exit_code(tmp_path):
    m = masters(tmp_path)
    vpath = ROOT / "tools/qa/validate_package.py"
    for target in (single_fbx(tmp_path), zip_without_manifest(tmp_path)):
        base = subprocess.run([sys.executable, str(vpath), str(target), "--json"], capture_output=True, text=True,
                              timeout=300, cwd=ROOT)
        r = subprocess.run([sys.executable, str(vpath), str(target), "--json", "--master", "ground=" + str(m["ground"])],
                           capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert r.returncode == base.returncode == 2, (r.returncode, r.stderr[-800:])
        doc = json.loads(r.stdout)
        found = [f for s in doc["stages"] for f in s["findings"] if f.get("data", {}).get("code") == "master_role_unused"]
        assert [(f["status"], f["data"]["role"]) for f in found] == [("not_run", "ground")]
        assert "master_role_unused" not in base.stdout
