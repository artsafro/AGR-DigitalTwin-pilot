"""Cached TOW02 snapped contours vs the shipped snap_band_z0 (#880): every differing band has a named cause.

Synthetic contours below reuse the TOW02 band elevations (bands 6-10, 23.9 .. 72.2 m) with a 1 m square plan;
they are synthetic test data, not the TOW02 geometry. The real-file test skips when the fixture is absent.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SNAP_DIFF_PY = ROOT / "tools" / "methods" / "body" / "snap_diff.py"
CONTOURS_PY = ROOT / "tools" / "methods" / "body" / "contours.py"
TOW02_SOURCE = Path(r"C:/x/t_ad9bc345/in/contours.json")
TOW02_CACHED_CANDIDATES = (Path(r"C:/x/t_ad9bc345/snapped_contours.json"),
                           Path("G:/Мой диск/AGR-evidence/t_ad9bc345-body-gn-z0-snap/snapped_contours.json"))
TOW02_SOURCE_SHA256 = "92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e"
TOW02_CACHED_SHA256 = "21bbc3e2422c409ed2a24b9fbede247274340589b3837ab83172f92d7fecc532"
SQUARE = [{"exterior": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "holes": []}]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def snap_diff():
    return _load(SNAP_DIFF_PY, "body_snap_diff_test")


def contours_mod():
    return _load(CONTOURS_PY, "body_contours_snap_diff_test")


def chain(levels):
    return {"schema": "body-contours/1", "synthetic_drawing": True,
            "bands": [{"z0": a, "z1": b, "polygons": copy.deepcopy(SQUARE)} for a, b in zip(levels, levels[1:])]}


def probe_snap(source, skip=()):
    """Emulates C:/x/t_ad9bc345/snap.py: one pass on the unsnapped source, lower top from the lower band's own
    source z0 (point-domain formula), bands in ``skip`` keep their source z0."""
    mod = contours_mod()
    out = copy.deepcopy(source)
    for i, lo in mod._snap_parents(source["bands"]).items():
        if i in skip:
            continue
        b = source["bands"][lo]
        out["bands"][i]["z0"] = mod._point_domain_top(float(b["z0"]), float(b["z1"]))
    return out


TOW02_LEVELS = [23.9, 27.3, 30.7, 65.4, 69.45, 72.2]  # TOW02 bands 6..10 -> local bands 0..4


def test_tow02_elevations_reproduce_the_four_band_difference():
    source = chain(TOW02_LEVELS)
    # TOW02: the probe skipped band 9 (lower band 8's face-domain top had two float32 z) -> local band 3
    cached = probe_snap(source, skip={3})
    report = snap_diff().diff_snapped(source, cached)
    reasons = {r["band"]: r["reason"] for r in report["bands"]}
    assert reasons == {0: "equal", 1: "equal", 2: "probe_single_pass", 3: "probe_kept_nominal",
                       4: "probe_single_pass"}
    rows = {r["band"]: r for r in report["bands"]}
    # the same float64 values as TOW02 bands 8, 9, 10 in the cached file and in the shipped snap
    assert (rows[2]["cached_z0"], rows[2]["shipped_z0"]) == (30.69999885559082, 30.700000762939453)
    assert (rows[3]["cached_z0"], rows[3]["shipped_z0"]) == (65.4, 65.4000015258789)
    assert (rows[4]["cached_z0"], rows[4]["shipped_z0"]) == (69.45000457763672, 69.44999694824219)
    assert all(r["parent"] == r["band"] - 1 for r in report["bands"][1:]) and report["bands"][0]["parent"] is None
    assert report["unexplained"] == [] and report["differing_bands"] == [2, 3, 4]


def test_shipped_snap_as_cached_is_all_equal():
    source = chain(TOW02_LEVELS)
    report = snap_diff().diff_snapped(source, contours_mod().snap_band_z0(source))
    assert report["differing_bands"] == [] and report["counts"] == {"equal": 5}


def test_other_difference_is_unexplained():
    source = chain(TOW02_LEVELS)
    cached = contours_mod().snap_band_z0(source)
    cached["bands"][2]["z0"] += 1e-3
    report = snap_diff().diff_snapped(source, cached)
    assert report["unexplained"] == [2]


@pytest.mark.parametrize("mutate, message", [
    (lambda c: c["bands"].pop(), "band count differs"),
    (lambda c: c["bands"][1].__setitem__("z1", 30.8), "band 1: z1 differs"),
    (lambda c: c["bands"][2]["polygons"][0]["exterior"].pop(), "band 2: polygons differ"),
    (lambda c: c["bands"][1].__setitem__("z0", float("nan")), "cached band 1 z0"),
    (lambda c: c["bands"][1].__setitem__("z0", float("inf")), "cached band 1 z0"),
    (lambda c: c["bands"][1].__setitem__("z0", "27.3"), "cached band 1 z0"),
    (lambda c: c.__setitem__("bands", None), "no bands list"),
])
def test_invalid_cached_input_names_the_band(mutate, message):
    source = chain(TOW02_LEVELS)
    cached = probe_snap(source)
    mutate(cached)
    with pytest.raises(ValueError, match=message):
        snap_diff().diff_snapped(source, cached)


def test_empty_source_raises():
    with pytest.raises(ValueError, match="empty bands"):
        snap_diff().diff_snapped({"bands": []}, {"bands": []})


def test_generated_chains_every_band_classified():
    """Random chains, random probe skip sets: every band is in the report, none is unexplained, and a band
    is listed as differing exactly when its cached and shipped z0 differ."""
    rng = random.Random(880)
    mod, sd = contours_mod(), snap_diff()
    checked = 0
    for _ in range(300):
        n = rng.randint(2, 9)
        levels = [round(rng.uniform(-5, 5), 2)]
        for _ in range(n):
            levels.append(round(levels[-1] + rng.uniform(0.05, 40.0), rng.choice([1, 2, 3, 4])))
        source = chain(levels)
        cached = probe_snap(source, skip={i for i in range(n) if rng.random() < 0.3})
        report = sd.diff_snapped(source, cached)
        shipped = mod.snap_band_z0(source)
        assert [r["band"] for r in report["bands"]] == list(range(n))
        assert report["unexplained"] == []
        assert report["differing_bands"] == [i for i in range(n)
                                             if cached["bands"][i]["z0"] != shipped["bands"][i]["z0"]]
        checked += 1
    assert checked == 300


def _cli(*args):
    return subprocess.run([sys.executable, str(SNAP_DIFF_PY), *map(str, args)], capture_output=True, text=True,
                          check=False, timeout=120)


def test_cli_fresh_process_exit_codes(tmp_path):
    source = chain(TOW02_LEVELS)
    src, cac, out = tmp_path / "src.json", tmp_path / "cached.json", tmp_path / "report.json"
    src.write_text(json.dumps(source), encoding="utf-8")
    cac.write_text(json.dumps(probe_snap(source, skip={3})), encoding="utf-8")
    before = (src.read_bytes(), cac.read_bytes())
    proc = _cli(src, cac, out)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["differing_bands"] == [2, 3, 4]
    # output aliasing an input: refused, nothing written, inputs unchanged
    for alias in (src, cac, tmp_path / "." / "src.json"):
        proc = _cli(src, cac, alias)
        assert proc.returncode == 4, proc.stderr
    assert (src.read_bytes(), cac.read_bytes()) == before
    # invalid input: exit 5, no report
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"bands": []}), encoding="utf-8")
    out2 = tmp_path / "report2.json"
    assert _cli(src, bad, out2).returncode == 5 and not out2.exists()
    # unexplained difference: exit 3, report written
    odd = contours_mod().snap_band_z0(source)
    odd["bands"][1]["z0"] += 1e-3
    cac.write_text(json.dumps(odd), encoding="utf-8")
    out3 = tmp_path / "report3.json"
    proc = _cli(src, cac, out3)
    assert proc.returncode == 3 and json.loads(out3.read_text(encoding="utf-8"))["unexplained"] == [1]
    assert _cli(src, cac).returncode == 2


def test_tow02_cached_file_differs_only_in_bands_3_8_9_10():
    cached_path = next((p for p in TOW02_CACHED_CANDIDATES if p.is_file()), None)
    if not TOW02_SOURCE.is_file() or cached_path is None:
        pytest.skip("TOW02 contours / cached snapped_contours.json not on this machine")
    assert hashlib.sha256(TOW02_SOURCE.read_bytes()).hexdigest() == TOW02_SOURCE_SHA256
    assert hashlib.sha256(cached_path.read_bytes()).hexdigest() == TOW02_CACHED_SHA256
    report = snap_diff().diff_snapped(json.loads(TOW02_SOURCE.read_text(encoding="utf-8")),
                                      json.loads(cached_path.read_text(encoding="utf-8")))
    assert {r["band"]: r["reason"] for r in report["bands"] if r["reason"] != "equal"} == {
        3: "probe_kept_nominal", 8: "probe_single_pass", 9: "probe_kept_nominal", 10: "probe_single_pass"}
    assert all(r["parent"] == r["band"] - 1 for r in report["bands"][1:])
    assert report["unexplained"] == []
