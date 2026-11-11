"""#1244 KPP1 R1: the V004 5-20 mm band pairs are listed and classified; xView receipts for the r1-v002 FBX.

new-case: receipt tests for jobs/KPP1/rerun-1244/ (band-pair listing + xView rerun with explicit profiles).
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "jobs" / "KPP1" / "rerun-1244"
R1230 = ROOT / "jobs" / "KPP1" / "rerun-1230"


def _mod():
    spec = importlib.util.spec_from_file_location("kpp1_r1244_band", RUN / "list_band_pairs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _plate(y, x0=0.0, w=1.0, h=1.0):
    """A -Y facing square (vertices ordered so the normal is -Y) at depth y."""
    return [[x0, y, 0.0], [x0 + w, y, 0.0], [x0 + w, y, h], [x0, y, h]]


def _mesh(name, polys):
    verts, idx = [], []
    for poly in polys:
        idx.append(list(range(len(verts), len(verts) + len(poly))))
        verts.extend(poly)
    return {"name": name, "face_geometry": {"vertices": verts, "polygons": idx}}


def _run(monkeypatch, tmp_path, meshes, kind="vpm"):
    mod = _mod()
    monkeypatch.setattr(mod, "readback", lambda fbx: {"meshes": meshes})
    fbx = tmp_path / "x.fbx"
    fbx.write_bytes(b"fbx")
    return mod, mod.band_pairs(fbx, kind)


# --- receipts ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind,validate,count", [
    ("vpm", "SM_Kpp_1.zip.r1-v002.validate.json", 98),
    ("npm", "0000_Kpp_1_01.r1-v002.validate.json", 52),
])
def test_listing_matches_validator_in_band_count(kind, validate, count):
    rep = _load(RUN / f"band-pairs-{kind}-r1-v002.json")
    observed = json.dumps(_load(R1230 / validate))
    assert f"{count} in band" in observed
    assert rep["distribution"]["in_band"] == count == len(rep["in_band_pairs"])
    assert rep["distribution"]["below_band"] == 0
    # every pair: the parapet inner face (y 5.625, roof top 7.909..8.59) 15 mm in front of the С35 glass pane
    assert all(abs(r["distance_mm"] - 15.0) < 0.001 for r in rep["in_band_pairs"])
    assert all(r["a"][0].endswith("_Main") and r["b"][0].endswith("_MainGlass") for r in rep["in_band_pairs"])
    assert rep["in_band_by_axis"] == {"-Y": count}
    assert {r["bbox_a_m"][0][1] for r in rep["in_band_pairs"]} == {5.625}
    assert min(r["bbox_a_m"][0][2] for r in rep["in_band_pairs"]) == 7.909
    assert len({tuple(r["b"]) for r in rep["in_band_pairs"]}) == 2


@pytest.mark.parametrize("kind,count_1209,count_now", [("vpm", 14, 98), ("npm", 4, 52)])
def test_overlap_area_not_above_1209(kind, count_1209, count_now):
    """The count rose by face splitting; the glass/parapet overlap area did not grow."""
    old = _load(RUN / f"band-pairs-{kind}-1209.json")
    new = _load(RUN / f"band-pairs-{kind}-r1-v002.json")
    assert (old["distribution"]["in_band"], new["distribution"]["in_band"]) == (count_1209, count_now)
    glass = lambda rep: sum(r["overlap_area_m2"] for r in rep["in_band_pairs"] if r["b"][0].endswith("Glass"))
    assert glass(new) < glass(old)


@pytest.mark.parametrize("kind,faces", [("vpm", 112), ("npm", 12)])
def test_xview_receipt_reproduced_with_explicit_profile(kind, faces):
    rep = _load(RUN / f"xview-{kind}-r1-v002.json")
    assert rep["profile"] == kind.upper()
    assert rep["totals"]["overlapping_faces"] == faces and rep["totals"]["overlapping_vertices"] == 0
    assert rep["passed"] is False
    assert rep["totals"] == _load(R1230 / f"xview-{kind}-r1-v002.json")["totals"]


def test_sha_of_listed_fbx_matches_sealed_evidence():
    sums = (R1230 / "evidence-r1-v002-SHA256SUMS.txt").read_text(encoding="utf-8")
    for kind, name in (("vpm", "SM_Kpp_1.fbx"), ("npm", "0000_Kpp_1_01.fbx")):
        sha = _load(RUN / f"band-pairs-{kind}-r1-v002.json")["sha256"]
        assert any(line.startswith(sha) and line.rstrip().endswith(name) for line in sums.splitlines())


# --- script probes (synthetic, readback stubbed) -----------------------------------------------------------

def test_band_edges_inclusive(monkeypatch, tmp_path):
    meshes = [_mesh("A", [_plate(0.0)]),
              _mesh("B", [_plate(-0.005, x0=0.0)]),       # exactly 5 mm: in band
              _mesh("C", [_plate(-0.020, x0=0.0)]),       # exactly 20 mm: in band
              ]
    _, rep = _run(monkeypatch, tmp_path, meshes)
    # pairs A-B 5, A-C 20, B-C 15: all in band
    assert sorted(r["distance_mm"] for r in rep["in_band_pairs"]) == [5.0, 15.0, 20.0]


def test_random_brute_force_counts(monkeypatch, tmp_path):
    rng = random.Random(1244)
    for _ in range(25):
        depths = [round(rng.uniform(-0.06, 0.0), 4) for _ in range(rng.randint(2, 6))]
        meshes = [_mesh(f"M{i}", [_plate(y)]) for i, y in enumerate(depths)]
        _, rep = _run(monkeypatch, tmp_path, meshes)
        expected = sum(1 for i in range(len(depths)) for j in range(i + 1, len(depths))
                       if 0.005 - 1e-5 <= abs(depths[i] - depths[j]) <= 0.02 + 1e-5)
        assert len(rep["in_band_pairs"]) == expected == rep["distribution"]["in_band"]


@pytest.mark.parametrize("meshes,message", [
    ([], "no measurable faces"),
    ([_mesh("UCX_A", [_plate(0.0)])], "no measurable faces"),
    ([{"name": "A"}], "A: no face geometry"),
    ([_mesh("A", [[[0, 0, 0], [1, 0, math.nan], [1, 0, 1]]])], "A#0: non-finite"),
    ([_mesh("A", [[[0, 0, 0], [1, 0, math.inf], [1, 0, 1]]])], "A#0: non-finite"),
])
def test_fail_closed_inputs(monkeypatch, tmp_path, meshes, message):
    with pytest.raises(ValueError, match=message):
        _run(monkeypatch, tmp_path, meshes)


def test_unsupported_profile_is_error(monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="unsupported profile 'ground'"):
        _run(monkeypatch, tmp_path, [_mesh("A", [_plate(0.0)])], kind="ground")


def test_cli_output_equal_to_input_writes_nothing(tmp_path):
    mod = _mod()
    fbx = tmp_path / "x.fbx"
    fbx.write_bytes(b"fbx")
    assert mod.main([str(fbx), "vpm", str(tmp_path / "." / "x.fbx")]) == 2
    assert fbx.read_bytes() == b"fbx"
    assert mod.main([str(tmp_path / "missing.fbx"), "vpm", str(tmp_path / "o.json")]) == 2
    assert not (tmp_path / "o.json").exists()
