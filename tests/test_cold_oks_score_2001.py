"""Cold OKS scorer (#2001): the key scores pass, perturbed keys fail, a stale key scores 0 passes.

new-case: tests/test_cold_oks_score_2001.py - synthetic controls of docs/research/cold-oks-sokolniki-2001/cold_oks_score.py.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cold_oks_score", ROOT / "docs/research/cold-oks-sokolniki-2001/cold_oks_score.py")
cos = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cos)

W, D, H, CELL_T, CELL_Z = 20.0, 10.0, 12.0, 2.0, 3.0


def _facade(p0, tdir, n, length, skip=False):
    """Wall quads on a CELL_T x CELL_Z grid; every second cell is a window recessed 0.2 m."""
    faces = []
    if skip:
        return faces
    for i in range(int(length / CELL_T)):
        for j in range(int(H / CELL_Z)):
            t0, t1, z0, z1 = i * CELL_T, (i + 1) * CELL_T, j * CELL_Z, (j + 1) * CELL_Z
            win = (i + j) % 2 == 1
            off = -0.2 if win else 0.0
            pts = [(t0, z0), (t1, z0), (t1, z1), (t0, z1)]
            v = [[p0[0] + tdir[0] * t + n[0] * off, p0[1] + tdir[1] * t + n[1] * off, z] for t, z in pts]
            faces.append({"o": 0, "label": "WINDOW" if win else "WALL", "v": v})
    return faces


def building(dx=0.0, dy=0.0, dz=0.0, drop=None):
    # counter-clockwise ring seen from above, outward normals
    sides = [((0, 0), (1, 0), (0, -1), W, "S"), ((W, 0), (0, 1), (1, 0), D, "E"),
             ((W, D), (-1, 0), (0, 1), W, "N"), ((0, D), (0, -1), (-1, 0), D, "W")]
    faces = []
    for p0, tdir, n, length, name in sides:
        faces += _facade(p0, tdir, n, length, skip=(name == drop))
    faces.append({"o": 0, "label": "ROOF", "v": [[0, 0, H], [W, 0, H], [W, D, H], [0, D, H]]})
    for f in faces:
        f["v"] = [[x + dx, y + dy, z + dz] for x, y, z in f["v"]]
        # wall quads facing -y must wind so the normal points outward: flip when needed
        nrm, _ = cos.face_normal_area([tuple(v) for v in f["v"]])
        c = [sum(v[k] for v in f["v"]) / 4 for k in range(3)]
        out = (c[0] - W / 2 - dx, c[1] - D / 2 - dy, 0.0 if f["label"] != "ROOF" else 1.0)
        if cos._dot(nrm, out) < 0:
            f["v"] = f["v"][::-1]
    return {"source_sha256": None, "objects": [], "faces": faces}


@pytest.fixture()
def keyset(tmp_path):
    key = tmp_path / "key"
    key.mkdir()
    body = key / "body.fbx"
    body.write_bytes(b"synthetic key body")
    digest = hashlib.sha256(body.read_bytes()).hexdigest()
    (key / "SHA256SUMS.txt").write_text(f"{digest}  body.fbx\n", encoding="utf-8")
    fp = building()
    fp["source_sha256"] = digest
    kfp = tmp_path / "key_fp.json"
    kfp.write_text(json.dumps(fp), encoding="utf-8")
    xv = tmp_path / "xv.json"
    xv.write_text(json.dumps({"totals": {"overlapping_faces": 0, "overlapping_vertices": 0}}), encoding="utf-8")
    # STOP grading is an evaluator switch (key_set), never a candidate one
    ks = {"score_stops": False, "stages": {"3": {"fingerprint": str(kfp), "key_file": "body.fbx", "xview": str(xv)}}}
    return key, ks, xv, tmp_path


def _cand(tmp_path, fp, xv, name, stops=None):
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(fp), encoding="utf-8")
    stage = {"fingerprint": str(p), "xview": str(xv), "stops_asked": stops or []}
    return {"stages": {"3": stage}}


def _body(res):
    return next(r for r in res["stages"] if r["id"] == "3")


def test_key_itself_passes(keyset):
    key, ks, xv, tmp = keyset
    res = cos.score(key, ks, _cand(tmp, building(), xv, "self"))
    assert _body(res)["status"] == "pass", _body(res)
    assert res["passes"] == 1


def test_shift_20cm_fails(keyset):
    key, ks, xv, tmp = keyset
    row = _body(cos.score(key, ks, _cand(tmp, building(dx=0.20), xv, "shift")))
    assert row["status"] == "fail"
    failed = {c["check"] for c in row["checks"] if c["status"] == "fail"}
    assert {"transform_bbox", "lattice_stations"} <= failed


def test_missing_facade_fails(keyset):
    key, ks, xv, tmp = keyset
    row = _body(cos.score(key, ks, _cand(tmp, building(drop="E"), xv, "drop")))
    failed = {c["check"] for c in row["checks"] if c["status"] == "fail"}
    assert "facade_cover" in failed and "openings" in failed


def test_blind_openings_fail(keyset):
    key, ks, xv, tmp = keyset
    fp = building()
    for f in fp["faces"]:
        if f["label"] == "WINDOW":
            f["label"] = "WALL"
    row = _body(cos.score(key, ks, _cand(tmp, fp, xv, "blind")))
    assert row["first_failing"] == "openings"


def test_stale_key_scores_zero(keyset):
    key, ks, xv, tmp = keyset
    (key / "body.fbx").write_bytes(b"an older key body")
    res = cos.score(key, ks, _cand(tmp, building(), xv, "self"))
    assert res["passes"] == 0 and res["first_failing_stage"] == "key_stale"
    assert all(r["status"] == "not_scored" for r in res["stages"])


def test_guessed_product_choice_fails_stage(keyset):
    key, ks, xv, tmp = keyset
    ks["score_stops"] = True
    row = _body(cos.score(key, ks, _cand(tmp, building(), xv, "guess", stops=["S3-lines"])))
    assert row["status"] == "fail" and row["first_failing"] == "stop S3-cuts"


@pytest.mark.parametrize(("asked", "expected_failure"), [
    (["STOP-01-layer-split.md"], None),
    (["STOP-98-layer-split.md"], None),
    (["S0-split"], None),
    (["STOP-01-authority.md"], "stop S0-split"),
    (["STOP-01-layer-split-extra.md"], "stop S0-split"),
    (["STOP-1-layer-split.md"], "stop S0-split"),
    (["notes/STOP-01-layer-split.md"], "stop S0-split"),
    (["S0-split", "STOP-01-unlisted.md"], "unknown STOP filename"),
])
def test_stage_zero_scores_builder_stop_filenames(keyset, asked, expected_failure):
    key, ks, _, tmp = keyset
    ks["score_stops"] = True
    (tmp / "stage0.md").write_text("synthetic layer inventory", encoding="utf-8")
    cand = {"stages": {"0": {"stops_asked": asked, "evidence": ["stage0.md"]}}}

    row = next(r for r in cos.score(key, ks, cand, run_dir=tmp)["stages"] if r["id"] == "0")

    assert row["first_failing"] == expected_failure
    assert row["status"] == ("pass" if expected_failure is None else "fail")


def test_declared_builder_topics_cover_protocol_stops(keyset):
    key, ks, xv, tmp = keyset
    ks["score_stops"] = True
    (tmp / "evidence.md").write_text("synthetic stage evidence", encoding="utf-8")
    # The same ordinal can identify different questions; this inventory is independent of the scorer table.
    topics = {
        "0": {"split": "S0-split"},
        "1": {"authority": "S1-authority"},
        "2": {"parts": "S2-parts"},
        "3": {"lines": "S3-lines", "cuts": "S3-cuts", "openings": "S3-openings"},
        "3i": {"plan": "S3i-plan", "wells": "S3i-wells"},
        "5": {"zoning": "S5-zoning", "windows": "S5-windows"},
        "6": {"contacts": "S6-contacts", "scope": "S6-scope"},
        "7": {"acceptance": "S7-acceptance"},
    }
    cand = _cand(tmp, building(), xv, "all-stops")
    for stage, entries in topics.items():
        cand["stages"].setdefault(stage, {}).update(
            stops_asked=[f"STOP-42-{topic}.md" for topic in entries], evidence=["evidence.md"])

    rows = {r["id"]: r for r in cos.score(key, ks, cand, run_dir=tmp)["stages"]}

    for stage, entries in topics.items():
        assert rows[stage]["status"] == "pass", rows[stage]
        assert {c["check"] for c in rows[stage]["checks"] if c["check"].startswith("stop ")} == {
            f"stop {stop_id}" for stop_id in entries.values()}


def _wall_quads_y5():
    """Invented interior wall: plane y=5 m, 10 x 4 cells of 2 x 3 m (40 quads), not in the key."""
    out = []
    for i in range(10):
        for j in range(4):
            t0, t1, z0, z1 = i * CELL_T, (i + 1) * CELL_T, j * CELL_Z, (j + 1) * CELL_Z
            out.append({"o": 0, "label": "WALL", "v": [[t0, 5.0, z0], [t1, 5.0, z0], [t1, 5.0, z1], [t0, 5.0, z1]]})
    return out


def test_extra_geometry_fails(keyset):
    """Review r1 R1: candidate surface far from the key is measured (candidate -> key)."""
    key, ks, xv, tmp = keyset
    fp = building()
    fp["faces"] += _wall_quads_y5()
    row = _body(cos.score(key, ks, _cand(tmp, fp, xv, "extra")))
    failed = {c["check"] for c in row["checks"] if c["status"] == "fail"}
    assert row["status"] == "fail"
    assert {"surface_precision", "facade_precision"} <= failed, failed


def test_invented_openings_fail(keyset):
    """Review r1 R2: openings precision - every blind cell labelled WINDOW is not a pass."""
    key, ks, xv, tmp = keyset
    fp = building()
    for f in fp["faces"]:
        if f["label"] == "WALL":
            f["label"] = "WINDOW"
    row = _body(cos.score(key, ks, _cand(tmp, fp, xv, "invented")))
    assert row["status"] == "fail" and row["first_failing"] == "openings", row["checks"]


def test_vacuous_stage_is_not_pass(keyset):
    """Review r1 R3: a stage with no checks / no evidence file inside the run folder never passes."""
    key, ks, xv, tmp = keyset
    run = tmp / "run"
    run.mkdir()
    (run / "stage2.md").write_text("parts list log", encoding="utf-8")
    cand = _cand(tmp, building(), xv, "self")
    cand["stages"] |= {"4": {}, "8": {}, "7": {"evidence": ["C:/"]}, "1": {"evidence": [str(run.parent / "self.json")]},
                       "2": {"evidence": ["stage2.md"]}}
    res = cos.score(key, ks, cand, run_dir=run)
    st = {r["id"]: r for r in res["stages"]}
    assert st["4"]["status"] != "pass" and st["8"]["status"] != "pass"
    assert st["7"]["status"] == "fail" and st["7"]["first_failing"] == "evidence"
    assert st["1"]["status"] == "fail" and st["1"]["first_failing"] == "evidence"  # file outside the run folder
    assert st["2"]["status"] == "pass", st["2"]
    assert res["passes"] == 2  # stage 2 (real evidence) + stage 3 (key itself)


def test_candidate_cannot_disable_stops(keyset):
    """Review r1 R4: "score_stops": false written by the builder is ignored."""
    key, ks, xv, tmp = keyset
    ks["score_stops"] = True
    cand = _cand(tmp, building(), xv, "self")
    cand["score_stops"] = False
    cand["stages"]["0"] = {"score_stops": False}
    st = {r["id"]: r for r in cos.score(key, ks, cand)["stages"]}
    assert st["0"]["status"] == "fail" and st["0"]["first_failing"] == "stop S0-split"
