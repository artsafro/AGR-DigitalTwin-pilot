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
    ks = {"stages": {"3": {"fingerprint": str(kfp), "key_file": "body.fbx", "xview": str(xv)}}}
    return key, ks, xv, tmp_path


def _cand(tmp_path, fp, xv, name, stops=None):
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(fp), encoding="utf-8")
    stage = {"fingerprint": str(p), "xview": str(xv), "score_stops": stops is not None, "stops_asked": stops or []}
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
    row = _body(cos.score(key, ks, _cand(tmp, building(), xv, "guess", stops=["S3-lines"])))
    assert row["status"] == "fail" and row["first_failing"] == "stop S3-cuts"
