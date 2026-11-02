"""Hash-bound real-corpus characterization of the five-decimal rounding in ``qa_packages._new_vertices`` (#663).

Adopts docs/experiments/hyp-663.md "Adoption scope": on the unmodified real TEC26 AC08 pilot-v010 VPM and NPM
readbacks, ``np.unique(np.round(..., 5))`` and exact-row ``np.unique`` give the same ``geometry_report`` (both cut
flags) and ``cut_joint_report`` scored fields. Evidence for this corpus only; it does not change ``tol``, widths,
the rounding policy or any production predicate (``delivery_passed=false``). The private ``C:/x/...`` readbacks
are skipped with an explicit message when missing; a pinned-hash mismatch fails with both hashes.

Pattern: new-case: test-only real-corpus characterization of qa_packages vertex quantization (#663).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "experiments" / "hyp-663" / "run_hyp663.py"

PINNED = {  # docs/experiments/hyp-663.md, Setup
    "max-dump-008.json": "f1fc27dc77d5d194ae25aebe8aeb23e71993ab0890cb08def97279bac3e45225",
    "vpm_textures.json": "3329bff4bf8e431f1cad2a31a5f2c637f7083d61e8b093c50bd1fd6e8e425722",
    "vpm.readback.json": "79195308ae9b70214f5d487880ed941298aee725f27a347c1f67485d3e095817",
    "npm.readback.json": "336f0e73aedf9c035624ce2b44279a3c14979d258d96a06d2130c21ecd2ac5e0",
}
TRACKED = ("max-dump-008.json", "vpm_textures.json")
PRIVATE = ("vpm.readback.json", "npm.readback.json")


def _load_driver():
    spec = importlib.util.spec_from_file_location("run_hyp663_test", DRIVER)
    assert spec is not None and spec.loader is not None, f"driver not loadable: {DRIVER}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


drv = _load_driver()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_pinned(path: Path, expected: str) -> None:
    actual = _sha(path)
    if actual != expected:
        raise AssertionError(f"pinned hash mismatch for {path}: expected {expected}, actual {actual}")


def assert_arm_unchanged(arm: dict, tag: str) -> None:
    """Fail-closed acceptance of one real arm: present, no exception, no mutation, zero changed scored fields."""
    assert arm.get("omitted") is False, f"{tag}: object {arm.get('object')} omitted from readback"
    assert arm["exceptions"] == [], f"{tag}: exceptions {arm['exceptions']}"
    assert arm["mutations"] == 0, f"{tag}: {arm['mutations']} input mutations"
    assert arm["changed"] == [], f"{tag}: changed scored fields {arm['changed']}"


def _sources() -> dict[str, Path]:
    return {
        "max-dump-008.json": Path(drv.REAL["dump"]),
        "vpm_textures.json": Path(drv.REAL["spec"]),
        "vpm.readback.json": Path(drv.REAL["vpm"]),
        "npm.readback.json": Path(drv.REAL["npm"]),
    }


@pytest.fixture()
def real_copy(tmp_path):
    src = _sources()
    for name in TRACKED:
        assert src[name].is_file(), f"tracked input missing: {src[name]}"
    missing = [str(src[n]) for n in PRIVATE if not src[n].is_file()]
    if missing:
        pytest.skip(f"private AC08 pilot-v010 readbacks missing (not in git): {missing}")
    for name, p in src.items():
        check_pinned(p, PINNED[name])
    wd = tmp_path / "hyp663"
    wd.mkdir()
    for name, p in src.items():
        shutil.copyfile(p, wd / name)
    return src, wd


def test_real_ac08_rounding_equals_exact_unique(real_copy):
    src, wd = real_copy
    res = drv.real(str(wd), drv.diag_module())
    assert res["address"] == "Nku_1" and res["source_vertices"] == 193 and res["source_faces"] == 180
    assert res["has_facades"] and res["ring_cuts"]
    for tag, name in (("vpm", "SM_Nku_1_Main"), ("npm", "SM_Nku_1_001_Main")):
        arm = res["arms"][tag]
        assert_arm_unchanged(arm, tag)
        assert (arm["object"], arm["vertices"], arm["faces"]) == (name, 213, 386)
        rep = arm["reports"]
        for key in ("geo_cutsF", "geo_cutsT", "joint"):
            assert rep[key]["baseline"] is not None and rep[key]["diagnostic"] is not None
        geo_f, geo_t, jnt = (rep[k]["baseline"] for k in ("geo_cutsF", "geo_cutsT", "joint"))
        assert [geo_f[f] for f in drv.GEO] == [False, 0, 20, False, 0]
        assert [geo_t[f] for f in drv.GEO] == [True, 0, 20, True, 0]
        assert [jnt[f] for f in drv.JNT] == [True, 20, 8, 0]
        assert arm["unique_rows"] == {"rounded": 213, "exact": 213, "raw_rows": 213}
        assert arm["new_rows"] == {"baseline": 20, "diagnostic": 20}
        assert arm["source_match_boundary"]["side_flips"] == 0
        assert arm["source_match_boundary"]["max_round_move"] < 5e-6
    for name, p in src.items():  # originals and copies untouched
        check_pinned(p, PINNED[name])
        check_pinned(wd / name, PINNED[name])


def test_synthetic_controls_zero_change_and_sensitivity_exposed():
    syn = drv.synthetic(drv.diag_module())
    assert set(syn["scored"]) == set(drv.SCORED)
    for k, r in syn["scored"].items():
        assert_arm_unchanged({**r, "omitted": False}, k)
    assert set(syn["sensitivity"]) == set(drv.SENSITIVITY)
    for k, r in syn["sensitivity"].items():  # comparator is not blind to known rounding flips
        assert r["witness_exposed"], f"{k}: comparator blind, changed={r['changed']}"
        assert r["exceptions"] == [] and r["mutations"] == 0


def test_hash_mismatch_fails_with_both_hashes(tmp_path):
    p = tmp_path / "vpm.readback.json"
    p.write_text(json.dumps({"objects": []}), encoding="utf-8")
    with pytest.raises(AssertionError) as e:
        check_pinned(p, PINNED["vpm.readback.json"])
    assert PINNED["vpm.readback.json"] in str(e.value) and _sha(p) in str(e.value)


def test_omitted_object_is_rejected(tmp_path):
    """A readback without the delivered mesh ends as omitted=True and the acceptance helper fails on it."""
    src = _sources()
    for name in TRACKED:
        shutil.copyfile(src[name], tmp_path / name)
    for name in PRIVATE:
        (tmp_path / name).write_text(json.dumps({"objects": []}), encoding="utf-8")
    res = drv.real(str(tmp_path), drv.diag_module())
    for tag in ("vpm", "npm"):
        assert res["arms"][tag]["omitted"] is True
        with pytest.raises(AssertionError, match="omitted"):
            assert_arm_unchanged(res["arms"][tag], tag)


def test_changed_field_or_mutation_is_rejected():
    base = {"omitted": False, "exceptions": [], "mutations": 0, "changed": []}
    assert_arm_unchanged(base, "ok")
    for bad in ({"changed": [{"report": "joint", "field": "ok"}]}, {"mutations": 1}, {"exceptions": ["E"]}):
        with pytest.raises(AssertionError):
            assert_arm_unchanged({**base, **bad}, "bad")
