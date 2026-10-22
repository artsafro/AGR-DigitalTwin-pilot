"""AC07 acceptance gates (#564 review round 1): source-polygon coverage in qa_packages and the slide rib verdict
in compare_slides. Pure Python; the fresh-process slide cases run on the real build-v005 renders when present.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "jobs", "TEC26-OKS", "scripts")
AC07 = os.path.join(ROOT, "jobs", "TEC26-OKS", "AC07")
sys.path.insert(0, SCRIPTS)

import compare_slides as cs  # noqa: E402
import qa_packages as qa  # noqa: E402

# ---------------------------------------------------------------- coverage (P1-1)

TRAP = [[0, 0, 0], [2, 0, 0], [1, 1, 0], [0, 1, 0]]          # planar trapezoid, area 1.5 m2
TWIST = [[0, 0, 0], [2, 0, 0], [2, 1, 0.5], [0, 1, 0]]      # non-planar quad (corner 2 lifted 0.5 m)


def _cover(src_v, tris, finish="F"):
    faces = [[0, 1, 2, 3]]
    owners = qa.match_source_faces(src_v, faces, src_v, tris, [0, 0, 0])
    tw = qa.twisted_quad_cover(src_v, faces, src_v, tris, owners, [0, 0, 0])
    rep = qa.source_finish_report([finish], faces, owners, [finish] * len(tris), qa.tri_areas(src_v, tris),
                                  qa.poly_areas(src_v, faces), tw["covered"])
    return rep, tw


def test_planar_overlap_and_gap_fails_coverage():
    """Reviewer witness: [0,1,2]+[0,1,3] on the trapezoid sums 2.0 m2 against 1.5 m2 - overlap + gap."""
    rep, tw = _cover(TRAP, [[0, 1, 2], [0, 1, 3]])
    assert tw == {"twisted": [], "covered": []}
    assert not rep["ok"] and rep["source_polygons_not_covered"] == 1


def test_planar_valid_triangulation_passes():
    for tris in ([[0, 1, 2], [0, 2, 3]], [[0, 1, 3], [1, 2, 3]]):
        rep, _ = _cover(TRAP, tris)
        assert rep["ok"] and rep["source_polygons_not_covered"] == 0, tris


@pytest.mark.parametrize("tris", [[[0, 1, 2], [0, 2, 3]], [[0, 1, 3], [1, 2, 3]]])
def test_twisted_quad_complementary_pair_passes(tris):
    rep, tw = _cover(TWIST, tris)
    assert tw == {"twisted": [0], "covered": [0]}
    assert rep["ok"]


@pytest.mark.parametrize("tris", [
    [[0, 1, 2], [0, 1, 3]],                  # overlapping pair, gap at corner 2-3
    [[0, 1, 2]],                             # partial
    [],                                      # empty
    [[0, 1, 2], [0, 2, 3], [0, 2, 3]],       # repeated triangle
    [[0, 1, 2], [0, 2, 3], [1, 2, 3]],       # third triangle
])
def test_twisted_quad_bad_triangulation_fails(tris):
    rep, tw = _cover(TWIST, tris)
    assert tw["twisted"] == [0] and tw["covered"] == []
    assert not rep["ok"]


def test_twisted_exemption_never_applies_to_planar_polygons():
    """The exemption list from twisted_quad_cover is the only bypass; a planar polygon handed in by mistake still
    has to come from that list, which never contains planar quads."""
    rep, tw = _cover(TRAP, [[0, 1, 2], [0, 1, 3]])
    assert 0 not in tw["covered"] and not rep["ok"]


def test_real_ac07_dump_has_exactly_the_four_twisted_trims():
    d = json.load(open(os.path.join(AC07, "max-dump-007.json"), encoding="utf-8"))
    body = [n for n in d["nodes"] if n["name"] == "АС.07"][0]
    v, f = body["vertices"], body["faces"]
    tris = [[p[0], p[k], p[k + 1]] for p in f for k in range(1, len(p) - 1)]   # fan = the export triangulation
    owners = qa.match_source_faces(v, f, v, tris, [0, 0, 0])
    tw = qa.twisted_quad_cover(v, f, v, tris, owners, [0, 0, 0])
    assert len(tw["twisted"]) == 4 and tw["covered"] == tw["twisted"]
    rep = qa.source_finish_report(["F"] * len(f), f, owners, ["F"] * len(tris), qa.tri_areas(v, tris),
                                  qa.poly_areas(v, f), tw["covered"])
    assert rep["ok"], rep
    # control: without the proven exemption the twisted trims are uncovered (strict area rule everywhere else)
    rep0 = qa.source_finish_report(["F"] * len(f), f, owners, ["F"] * len(tris), qa.tri_areas(v, tris),
                                   qa.poly_areas(v, f))
    assert rep0["source_polygons_not_covered"] == 4


# ---------------------------------------------------------------- slide rib estimate (P1-2)

def _grid(ribs, width=520.0, phase=0.0, drop=(), extra=()):
    p = width / ribs
    xs = [phase + k * p for k in range(1, ribs) if k not in drop] + list(extra)
    return sorted(xs), width


def test_estimate_clean_grid():
    e = cs.slide_rib_estimate(*_grid(55))
    assert e["status"] == "measured" and e["ribs"] == 55


def test_estimate_robust_to_windows_and_labels():
    e = cs.slide_rib_estimate(*_grid(55, drop=range(10, 22), extra=(103.3, 250.1)))
    assert e["status"] == "measured" and e["ribs"] == 55


def test_estimate_other_count_is_measured_not_forced():
    e = cs.slide_rib_estimate(*_grid(50))
    assert e["status"] == "measured" and e["ribs"] == 50


@pytest.mark.parametrize("found,width", [
    ([], 520.0), ([260.0], 520.0), ([100.0, 200.0], 520.0),          # empty / reviewer's 1 joint / partial
    ([1.0, float("nan"), 3.0, 4.0], 520.0), (_grid(55)[0], float("inf")), (_grid(55)[0], 0.0),
    (["x", 1, 2], 520.0),
])
def test_estimate_unmeasurable_is_unresolved(found, width):
    e = cs.slide_rib_estimate(found, width)
    assert e["status"] == "unresolved" and e["ribs"] is None and e["reason"]


def test_estimate_sparse_grid_unresolved():
    e = cs.slide_rib_estimate(*_grid(55, drop=range(2, 40)))
    assert e["status"] == "unresolved"


def test_estimate_edge_ambiguous_unresolved():
    """width / pitch = 54.25 (the real AC07 slide: 200 mm pitch over 10.9 m): a node sits near the p/2 limit."""
    p = 9.605
    found = [3.4 + k * p for k in range(1, 54)]
    e = cs.slide_rib_estimate(found, 521.0)
    assert e["status"] == "unresolved" and "ambiguous" in e["reason"]


def _row(model_ok=True, slide=None):
    return {"vpm": {"ok": model_ok}, "npm": {"ok": True}, "slide_estimate": slide or {"status": "unresolved"}}


@pytest.mark.parametrize("rows,want", [
    ([_row(True, {"status": "measured", "ribs": 55})] * 3, "match"),
    ([_row(True, {"status": "measured", "ribs": 55}), _row(True, {"status": "measured", "ribs": 54})], "mismatch"),
    ([_row(False, {"status": "measured", "ribs": 55})], "mismatch"),
    ([_row(True, {"status": "measured", "ribs": 55}), _row(True, {"status": "unresolved", "ribs": None})],
     "unresolved"),
    ([_row(True, {"status": "unresolved", "ribs": None})], "unresolved"),
    ([], "unresolved"),
    ([{"slide_estimate": {"status": "measured", "ribs": 55}}], "mismatch"),        # model rows missing
])
def test_facade_verdict(rows, want):
    assert cs.facade_verdict(rows, 55) == want


# ---------------------------------------------------------------- fresh-process compare on real renders

B5 = "C:/x/tec26-oks/AC07/build-v005"
REAL = os.path.exists(os.path.join(B5, "renders", "renders.json"))
WRAP = """import sys, json
sys.path.insert(0, {scripts!r})
import compare_slides as cs
mode = sys.argv[1]
orig = cs.slide_row_count
def fake(im, x0, x1, y, ribs, colour):
    r = orig(im, x0, x1, y, ribs, colour)
    if mode == "one":                       # reviewer mutation: 1 joint, ok=false
        return {{"ok": False, "joints_found": 1, "found_m": [r["found_m"][0]], "missing": [], "extra": []}}
    if mode == "exact":                     # matching control: clean grid of the spec rib count
        w = x1 - x0
        f = [k * w / ribs for k in range(1, ribs)]
        return {{"ok": True, "joints_found": len(f), "found_m": f, "missing": [], "extra": []}}
    if mode == "other":                     # measured, but 3 ribs fewer than the spec
        w = x1 - x0
        f = [k * w / (ribs - 3) for k in range(1, ribs - 3)]
        return {{"ok": True, "joints_found": len(f), "found_m": f, "missing": [], "extra": []}}
    return r
cs.slide_row_count = fake
sys.exit(cs.main(sys.argv[2:]))
"""


@pytest.mark.skipif(not REAL, reason="build-v005 renders not on this machine")
@pytest.mark.parametrize("mode,rc,status", [("one", 1, {"unresolved"}), ("other", 1, {"mismatch"}),
                                            ("exact", 0, {"match"}), ("real", 1, {"unresolved"})])
def test_compare_cli_fresh_process(tmp_path, mode, rc, status):
    w = tmp_path / "wrap.py"
    w.write_text(WRAP.format(scripts=SCRIPTS), encoding="utf-8")
    out = tmp_path / "cmp"
    p = subprocess.run([sys.executable, str(w), mode, os.path.join(AC07, "vpm_textures.json"),
                        os.path.join(B5, "renders"), os.path.join(B5, "readback", "vpm.readback.json"), str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == rc, p.stderr[-2000:]
    rep = json.load(open(out / "compare.json", encoding="utf-8"))
    assert {f["status"] for f in rep["facades"].values()} == status
    assert all(f["match"] == (f["status"] == "match") for f in rep["facades"].values())
    # repeat into the same dir: refused, nothing rewritten
    before = (out / "compare.json").read_bytes()
    p2 = subprocess.run([sys.executable, str(w), mode, os.path.join(AC07, "vpm_textures.json"),
                         os.path.join(B5, "renders"), os.path.join(B5, "readback", "vpm.readback.json"), str(out)],
                        capture_output=True, text=True, encoding="utf-8")
    assert p2.returncode != 0 and (out / "compare.json").read_bytes() == before
