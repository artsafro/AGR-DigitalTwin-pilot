"""new-case: #1563 KPP1 quad master v003 - per-version R1 pin, archived xView input, plan diff, provenance.

Probes for the guarantees of the card: any other source is refused, the archived xView report is used only with its
pinned hash, every zone of both plans ends in exactly one diff list, outputs are never replaced, no admission.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import random

import pytest

ROOT = Path(__file__).resolve().parents[2]
QDIR = ROOT / "jobs/KPP1/quad-1372"


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, QDIR / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


puz = _load("plan_union_zones_1563", "plan_union_zones.py")
qp = _load("quad_provenance_1563", "quad_provenance.py")

V002, V003 = qp.R1_V002, qp.R1_V003


# --- source pin per version ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("version,digest", [("v001", V002), ("v002", V002), ("v003", V003)])
def test_each_version_accepts_only_its_own_r1(version, digest):
    assert qp.check_source(version, digest) in ("r1-v002", "r1-v003")
    other = V003 if digest == V002 else V002
    with pytest.raises(ValueError, match="is not the approved"):
        qp.check_source(version, other)
    with pytest.raises(ValueError, match="is not the approved"):
        qp.check_source(version, "0" * 64)


@pytest.mark.parametrize("version", ["v004", "", None, "V003", "v003 "])
def test_unknown_version_is_refused(version):
    with pytest.raises(ValueError, match="no pinned R1 source"):
        qp.check_source(version, V003)


def test_plan_of_another_source_is_refused():
    assert qp.check_source("v003", V003, {"source_sha256": V003}) == "r1-v003"
    for bad in ({"source_sha256": V002}, {}, {"source_sha256": None}):
        with pytest.raises(ValueError, match="union plan source"):
            qp.check_source("v003", V003, bad)


def test_planner_accepts_both_r1_versions_and_nothing_else():
    assert puz.SOURCE_SHAS == {V002: "r1-v002", V003: "r1-v003"}
    assert puz.SOURCE_SHA == V002  # v001/v002 outputs keep their source


def test_planner_cli_refuses_unknown_source_and_aliases(tmp_path):
    src = tmp_path / "SM_Kpp_1.fbx"
    src.write_bytes(b"r1-v003 lookalike")
    out = tmp_path / "union-zones-v003.json"
    with pytest.raises(SystemExit, match="not the approved"):
        puz.main([str(src), str(out)])
    with pytest.raises(SystemExit, match="aliases the source or the output"):
        puz.main([str(src), str(out), "--xview-json", str(src)])
    with pytest.raises(SystemExit, match="aliases the source or the output"):
        puz.main([str(src), str(out), "--compare", str(out)])
    assert not out.exists() and src.read_bytes() == b"r1-v003 lookalike"


# --- archived xView input --------------------------------------------------------------------------------------------

def _xview(tmp_path, digest, pairs, face_m=0.005, part="SM_Kpp_1_Main", name="xview.json"):
    rep = {"input": {"sha256": digest}, "thresholds": {"vertex_m": 0.002, "face_m": face_m},
           "parts": [{"part": part, "face_pairs": [{"a": a + 1, "b": b + 1} for a, b in pairs]}]}
    p = tmp_path / name
    p.write_text(json.dumps(rep))
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def test_archived_xview_used_only_with_its_pinned_hash(tmp_path, monkeypatch):
    p, h = _xview(tmp_path, V003, [(0, 5), (2, 7)])
    monkeypatch.setitem(puz.ARCHIVED_XVIEW, V003, h)
    path, got, pairs = puz.archived_pairs(p, V003)
    assert got == h and pairs == {(0, 5), (2, 7)}
    p.write_text(p.read_text() + " ")  # one byte changed -> hash differs -> rerun xView
    with pytest.raises(SystemExit, match="rerun xView"):
        puz.archived_pairs(p, V003)
    with pytest.raises(SystemExit, match="missing; rerun xView"):
        puz.archived_pairs(tmp_path / "absent.json", V003)
    with pytest.raises(SystemExit, match="no archived xView report is pinned"):
        puz.archived_pairs(p, V002)


@pytest.mark.parametrize("kw,msg", [({"digest": V002}, "input is not the source"),
                                    ({"face_m": 0.0051}, "not the xView defaults"),
                                    ({"part": "SM_Kpp_1_MainGlass"}, "appears 0 times")])
def test_archived_xview_of_other_input_or_thresholds_is_refused(tmp_path, monkeypatch, kw, msg):
    digest = kw.pop("digest", V003)
    p, h = _xview(tmp_path, digest, [(0, 1)], **kw)
    monkeypatch.setitem(puz.ARCHIVED_XVIEW, V003, h)
    with pytest.raises(SystemExit, match=msg):
        puz.archived_pairs(p, V003)


PLACED = "eb9d105af9de642d03928078917a174e9d2f5cb46b0a8d8460fd38e6cd47cc72"  # #1278 site-r1-v003 (rotated, D262)


def test_v003_source_is_local_r1_not_the_site_placed_copy(tmp_path):
    """D135 / conflicts.md #39: master in world x/y; the placed copy and its archived xView are not v003 inputs."""
    assert V003 == "76a7c97e523d6ac6475443a84f51e4b2ec588de3cbeb1b300d08adf07e97dc50"
    assert qp.R1_V003_PLACED == PLACED and PLACED not in puz.SOURCE_SHAS
    assert puz.SOURCE_SHAS[V003] == "r1-v003" and V003 not in puz.ARCHIVED_XVIEW
    with pytest.raises(ValueError, match="not the approved"):
        qp.check_source("v003", PLACED)
    p, _ = _xview(tmp_path, PLACED, [(0, 1)])  # archived #1278 report shape: input = the placed copy
    with pytest.raises(SystemExit, match="no archived xView report is pinned"):
        puz.archived_pairs(p, V003)


# --- plan diff and corners -------------------------------------------------------------------------------------------

def _zone(axis, value, cents, lo=None, hi=None):
    lo = lo or [min(c[i] for c in cents) for i in range(3)]
    hi = hi or [max(c[i] for c in cents) for i in range(3)]
    return {"axis": axis, "value": value, "centroids": cents, "faces": list(range(len(cents))), "lo": lo, "hi": hi}


def test_diff_counts_identical_changed_new_removed():
    a = _zone(0, 12.415, [[12.415, 0.8, 3.9], [12.415, 1.0, 4.0]])
    b = _zone(1, 6.12, [[-10.0, 6.12, 1.0]])
    gone = _zone(2, 7.5, [[0.0, 0.0, 7.5]])
    b2 = _zone(1, 6.1205, [[-10.0, 6.1205, 1.0], [-10.1, 6.1205, 1.1]])
    new = _zone(0, -15.03, [[-15.03, -5.73, 2.0]])
    d = puz.diff_plans({"zones": [a, b, gone]}, {"zones": [dict(a), b2, new]})
    assert d["counts"] == {"new": 1, "changed": 1, "identical": 1, "removed": 1}
    assert d["removed_old_zones"] == [2]
    assert [z["status"] for z in d["zones"]] == ["identical", "changed", "new"]


def test_diff_every_zone_in_exactly_one_list_generated():
    rnd = random.Random(1563)
    for _ in range(200):
        def zs():
            return [_zone(rnd.randrange(3), round(rnd.uniform(-15, 15), 4),
                          [[round(rnd.uniform(-15, 15), 4) for _ in range(3)] for _ in range(rnd.randint(1, 3))])
                    for _ in range(rnd.randint(0, 6))]
        old, new = zs(), zs()
        if old and rnd.random() < .5:
            new.append(dict(old[0]))
        d = puz.diff_plans({"zones": old}, {"zones": new})
        c = d["counts"]
        assert c["new"] + c["changed"] + c["identical"] == len(new)
        matched = {j for z in d["zones"] for j in z["old_zones"]}
        assert matched.isdisjoint(d["removed_old_zones"])
        assert matched | set(d["removed_old_zones"]) == set(range(len(old)))


def test_diff_identical_across_a_rounding_boundary_and_not_beyond_tol():
    """Measured on R1 v003: zones within 0.03-0.1 mm were 'changed' by 0.1 mm rounding buckets."""
    a = _zone(1, 5.975, [[0.27494, 5.975, 1.8], [0.39, 5.975, 3.6]])
    near = _zone(1, 5.975, [[0.27503, 5.975, 1.8], [0.39, 5.975, 3.6]])   # 0.09 mm, crosses a bucket edge
    at = _zone(1, 5.975, [[0.27504, 5.975, 1.8], [0.39, 5.975, 3.6]])     # 0.1 mm (float: just below/at)
    far = _zone(1, 5.975, [[0.27514, 5.975, 1.8], [0.39, 5.975, 3.6]])    # 0.2 mm
    swap = _zone(1, 5.975, [[0.39, 5.975, 3.6], [0.27494, 5.975, 1.8]])
    dup = _zone(1, 5.975, [[0.27494, 5.975, 1.8], [0.27494, 5.975, 1.8]])  # same count, one centroid twice
    st = [puz.diff_plans({"zones": [a]}, {"zones": [z]})["zones"][0]["status"] for z in (near, at, far, swap, dup)]
    assert st == ["identical", "identical", "changed", "identical", "changed"]


def test_diff_of_a_plan_with_itself_is_all_identical():
    a = _zone(0, 1.0, [[1.0, 0.0, 0.0]])
    d = puz.diff_plans({"zones": [a, a]}, {"zones": [a]})
    assert d["counts"] == {"new": 0, "changed": 0, "identical": 1, "removed": 0}


def test_corner_zones_at_exactly_the_radius_touch_and_beyond_do_not():
    x, y = puz.CORNER_POSTS["SW"]
    r = puz.CORNER_RADIUS_M
    at = _zone(0, x + r, [[x + r, y, 1.0]])
    beyond = _zone(0, x + r + 1e-3, [[x + r + 1e-3, y, 1.0]])
    far = _zone(1, 0.0, [[0.0, 0.0, 1.0]])
    got = puz.corner_zones([at, beyond, far])
    assert got == {"SW": [0], "NW": []}


# --- provenance record ------------------------------------------------------------------------------------------------

def _packet(tmp_path, monkeypatch):
    src = tmp_path / "source" / "SM_Kpp_1.fbx"
    src.parent.mkdir()
    src.write_bytes(b"fake r1 for the provenance probe (synthetic)")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    monkeypatch.setitem(qp.VERSION_SOURCE, "v003", digest)
    monkeypatch.setitem(qp.SOURCE_NAME, digest, "r1-v003")
    outs = []
    for n in ("master-quad-v003.blend", "SM_Kpp_1.quad-v003.fbx", "quad-build-v003.json"):
        (tmp_path / n).write_bytes(n.encode())
        outs.append(tmp_path / n)
    plan = tmp_path / "union-zones-v003.json"
    plan.write_text("{}")
    return src, digest, outs, plan


def test_provenance_binds_source_plan_outputs_commit_and_no_admission(tmp_path, monkeypatch):
    src, digest, outs, plan = _packet(tmp_path, monkeypatch)
    p = qp.write_provenance(tmp_path, "v003", src, digest, plan, outs, "a" * 40, True)
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert rec["source"]["sha256"] == digest and rec["union_plan"]["sha256"] == qp.sha(plan)
    assert rec["outputs"] == {o.name: qp.sha(o) for o in outs}
    assert rec["script_commit"] == "a" * 40 and rec["admission"] is None
    der = json.loads(Path(rec["derivation_record"]["path"]).read_text(encoding="utf-8"))
    assert der["schema"] == "agr.derivation/1" and der["master_sha256"] == digest
    assert der["artifacts"] == {"SM_Kpp_1.quad-v003.fbx": {"kind": "vpm_fbx", "sha256": qp.sha(outs[1])}}
    before = p.read_bytes()
    with pytest.raises(FileExistsError):
        qp.write_provenance(tmp_path, "v003", src, digest, plan, outs, "a" * 40, True)
    assert p.read_bytes() == before
    assert not list(tmp_path.rglob("*.partial"))


def test_provenance_refuses_changed_source_and_bad_outputs(tmp_path, monkeypatch):
    src, digest, outs, plan = _packet(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="exactly one work FBX"):
        qp.write_provenance(tmp_path, "v003", src, digest, plan, [outs[0], outs[2]], "a" * 40, True)
    with pytest.raises(ValueError, match="alias"):
        qp.write_provenance(tmp_path, "v003", src, digest, plan, outs + [outs[0]], "a" * 40, True)
    src.write_bytes(b"changed during the build")
    with pytest.raises(ValueError, match="master_changed_during_export"):
        qp.write_provenance(tmp_path, "v003", src, digest, plan, outs, "a" * 40, True)
    assert not (tmp_path / "quad-provenance-v003.json").exists()
    assert not (tmp_path / "derivation").exists()


# --- residual pairs of a previous build (SW/NW posts of r1-v003) ------------------------------------------------------

np = pytest.importorskip("numpy")
TRI_V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1e-3], [0, 0, 1]], dtype=np.float64)
TRI_F = [(0, 1, 2), (0, 3, 4)]   # face 0 in z = 0; face 1 is degenerate (collinear) and never matches


@pytest.mark.parametrize("p,want", [((0.2, 0.2, 0.0), [0]), ((0.2, 0.2, 9e-5), [0]), ((0.2, 0.2, 2e-4), []),
                                    ((1.2, 1.2, 0.0), []), ((0.5, 0.5, 0.0), [0]), ((0.5005, 0.5005, 0.0), [])])
def test_faces_under_plane_and_inside_with_tolerance(p, want):
    assert puz.faces_under(p, TRI_V, TRI_F) == want


@pytest.mark.parametrize("p", [(float("nan"), 0, 0), (0, float("inf"), 0), (0, 0)])
def test_faces_under_refuses_non_finite_or_short_points(p):
    with pytest.raises(ValueError, match="3 finite numbers"):
        puz.faces_under(p, TRI_V, TRI_F)


class _Part:
    def __init__(self, name, vertices, faces):
        self.name, self.vertices, self.faces = name, vertices, faces


def _gate(pairs):
    return lambda part, tol, mode: {"face_pairs": [{"a": a, "b": b, "kind": "contact", "centre": [0, 0, 0]}
                                                   for a, b in pairs]}


def test_residual_pairs_map_master_faces_back_to_r1(monkeypatch):
    # master: two quads lying on R1 face 0 and on R1 face 1 (1-based ids in the gate, like xView)
    mv = np.array([[.1, .1, 0], [.3, .1, 0], [.3, .3, 0], [.1, .3, 0], [0, .1, .1], [0, .3, .1], [0, .3, .3],
                   [0, .1, .3]], dtype=np.float64)
    master = _Part("SM_Kpp_1_Main", mv, [(0, 1, 2, 3), (4, 5, 6, 7)])
    r1v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float64)
    r1f = [(0, 1, 2), (0, 2, 3)]
    monkeypatch.setattr(puz.xview_gate, "part_gate", _gate([(1, 2)]))
    pairs, log = puz.residual_pairs([master], r1v, r1f)
    assert pairs == [(0, 1)] and log[0]["r1_faces"] == [[0], [1]] and log[0]["master_faces"] == [1, 2]
    monkeypatch.setattr(puz.xview_gate, "part_gate", _gate([]))
    assert puz.residual_pairs([master], r1v, r1f) == ([], [])          # no residual -> nothing added


def test_residual_face_on_no_r1_face_or_missing_part_is_an_error(monkeypatch):
    mv = np.array([[5, 5, 5], [6, 5, 5], [6, 6, 5], [5, 6, 5]], dtype=np.float64)
    master = _Part("SM_Kpp_1_Main", mv, [(0, 1, 2, 3), (0, 1, 2, 3)])
    monkeypatch.setattr(puz.xview_gate, "part_gate", _gate([(1, 2)]))
    with pytest.raises(SystemExit, match="lies on no R1 face"):
        puz.residual_pairs([master], TRI_V, TRI_F)
    with pytest.raises(SystemExit, match="not in the residual master"):
        puz.residual_pairs([_Part("SM_Kpp_1_MainGlass", mv, [(0, 1, 2, 3)])], TRI_V, TRI_F)


def test_residual_aliasing_source_or_output_is_refused(tmp_path):
    src = tmp_path / "SM_Kpp_1.fbx"
    src.write_bytes(b"x")
    out = tmp_path / "union-zones-v003.json"
    for alias in (src, out):
        with pytest.raises(SystemExit, match="aliases the source or the output"):
            puz.main([str(src), str(out), "--residual", str(alias)])
    assert not out.exists()


def test_sheet_unknown_camera_set_and_existing_output_fail(tmp_path):
    pytest.importorskip("PIL")
    ms = _load("make_sheet_1563", "make_sheet.py")
    with pytest.raises(SystemExit, match="unknown camera set"):
        ms.main(tmp_path, tmp_path / "s.png", "wire", "nope")
    with pytest.raises(SystemExit, match="missing renders"):
        ms.main(tmp_path, tmp_path / "s.png", "wire", "corners")
    (tmp_path / "s.png").write_bytes(b"keep")
    with pytest.raises(SystemExit, match="exists"):
        ms.main(tmp_path, tmp_path / "s.png", "wire", "corners")
    assert (tmp_path / "s.png").read_bytes() == b"keep"
    assert ms.SETS["corners"][0] == ["sw_from_sw", "sw_from_s", "nw_from_nw", "nw_from_n"]
