"""Tests for jobs/VATUTINO-SITE/flora_a101_match.py (#1146 step 2 A101 match)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


match = _load("flora_a101_match", "jobs/VATUTINO-SITE/flora_a101_match.py")


def test_match_covers_exactly_the_11_needed_positions():
    recs = match.records()
    assert [r["pos"] for r in recs] == [2, 4, 5, 6, 7, 8, 9, 10, 13, 16, "Ива"]
    assert {r["status"] for r in recs} <= {"missing", "proxy"}
    # 7 missing + 4 proxy
    assert sum(r["status"] == "missing" for r in recs) == 7
    assert sum(r["status"] == "proxy" for r in recs) == 4


def test_match_summary_numbers():
    s = match.summary(match.records())
    assert s == {"rows": 11, "exact": 1, "exact_species": 1, "no_match": 9, "no_candidates": 4,
                 "gap_positions": ["2", "5", "8", "13"], "udim_tile": 1002}


def test_exact_matches_point_to_real_a101_files():
    for r in match.records():
        if r["a101_match"] in ("exact", "exact-species"):
            assert r["a101_files"], r["pos"]
            assert set(r["a101_files"]) <= match.A101_TEXTURES
            assert set(r["a101_previews"]) <= match.A101_PREVIEWS
        for c in r["a101_candidates"]:
            assert c in match.A101_TEXTURES


def test_pos16_is_full_exact_and_pos9_is_species_only():
    by = {r["pos"]: r for r in match.records()}
    assert by[16]["a101_match"] == "exact"
    assert by[16]["a101_files"] == ["el_nidiformis_t1_h60_high.png", "el_nidiformis_t1_h60_low.png"]
    assert by[9]["a101_match"] == "exact-species"
    assert by[9]["a101_files"][0].startswith("puzyreplodnik_kalinolistnyj_t1_h150")


def test_committed_outputs_are_fresh():
    assert match.main(["--check"]) == 0


def test_validate_rejects_unknown_file(monkeypatch):
    bad = {k: dict(v) for k, v in match.MATCHES.items()}
    bad[16] = dict(bad[16], files=["nope_t1_h60_high.png"])
    monkeypatch.setattr(match, "MATCHES", bad)
    with pytest.raises(ValueError, match="unknown A101 files"):
        match.validate()


def test_validate_rejects_unknown_match_type(monkeypatch):
    bad = {k: dict(v) for k, v in match.MATCHES.items()}
    bad[16] = dict(bad[16], match="exact-hedge")
    monkeypatch.setattr(match, "MATCHES", bad)
    with pytest.raises(ValueError, match="unknown match"):
        match.validate()


def test_validate_rejects_missing_position(monkeypatch):
    bad = {k: v for k, v in match.MATCHES.items() if k != 16}
    monkeypatch.setattr(match, "MATCHES", bad)
    with pytest.raises(ValueError, match="MATCHES keys"):
        match.validate()


def test_validate_rejects_unknown_candidate(monkeypatch):
    bad = {k: dict(v) for k, v in match.MATCHES.items()}
    bad[4] = dict(bad[4], candidates=["fake_t1_h350_high.png"])
    monkeypatch.setattr(match, "MATCHES", bad)
    with pytest.raises(ValueError, match="unknown candidate"):
        match.validate()


def test_copied_sha256_covers_exact_files():
    exact_files = {f for m in match.MATCHES.values() if m["match"] in ("exact", "exact-species")
                   for f in m["files"] + m["previews"]}
    assert set(match.COPIED_SHA256) == exact_files
    assert len(match.COPIED_SHA256) == 11


def test_pos9_variants_described_per_variant_with_measured_colour():
    by = {r["pos"]: r for r in match.records()}
    v = by[9]["a101_variants"]
    assert [(x["file"], x["label"]) for x in v] == [
        ("puzyreplodnik_kalinolistnyj_t1_h150_high.png", "yellow"),
        ("puzyreplodnik_kalinolistnyj_t2_h150_high.png", "dark red"),
        ("puzyreplodnik_kalinolistnyj_t3_h150_high.png", "yellow-green"),
    ]
    for x in v:
        assert x["mean_rgb"] == match.COLOURS[x["file"]]["mean_rgb"]
        assert x["label"] == match.COLOURS[x["file"]]["label"]
    # t2 is the exact-species red candidate for 'Lady in Red' (replaces the 'Diabolo' proxy)
    assert "'Lady in Red'" in by[9]["reason"]
    assert "red" in by[9]["reason"].lower()
    # generic puzyreplodnik_t1 is listed as a candidate
    assert "puzyreplodnik_t1_h150_high.png" in by[9]["a101_candidates"]
    assert "puzyreplodnik_t1_h150_low.png" in by[9]["a101_candidates"]


def test_colour_labels_match_recorded_measurement_and_sha256():
    # the colour label of every pos-9 variant is a recorded table bound to the copied file's sha256
    for fname, c in match.COLOURS.items():
        assert fname in match.COPIED_SHA256, f"{fname} colour is not bound to a copied sha256"
        assert c["label"] == match.label_from_rgb(c["mean_rgb"], c["red_gt_green"]), fname
    g = match.GENERIC_PUZYREPLODNIK_COLOUR
    assert g["label"] == match.label_from_rgb(g["mean_rgb"], g["red_gt_green"])


def _measure_opaque_rgb(path):
    from PIL import Image
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # getdata() deprecation (removed in Pillow 14)
        im = Image.open(path).convert("RGBA")
        data = list(im.getdata())
    rs = gs = bs = n = rgt = 0
    for r, g, b, a in data:
        if a >= 128:
            rs += r; gs += g; bs += b; n += 1
            if r > g:
                rgt += 1
    return [round(rs / n), round(gs / n), round(bs / n)], round(rgt / n, 2)


def test_colour_measurement_reproduces_from_copied_pngs():
    import hashlib
    copies = Path("G:/Мой диск/AGR-evidence/1146-flora-star/a101-matched/")
    if not copies.exists():
        pytest.skip("A101 copy dir not mounted")
    for fname, c in match.COLOURS.items():
        p = copies / fname
        assert p.exists(), fname
        assert hashlib.sha256(p.read_bytes()).hexdigest() == match.COPIED_SHA256[fname], fname
        rgb, rgt = _measure_opaque_rgb(p)
        assert rgb == [int(x) for x in c["mean_rgb"]], f"{fname}: {rgb} != {c['mean_rgb']}"
        assert abs(rgt - c["red_gt_green"]) <= 0.01, f"{fname}: {rgt} != {c['red_gt_green']}"


def test_validate_rejects_missing_hash(monkeypatch):
    bad = dict(match.COPIED_SHA256)
    del bad["el_nidiformis_t1_h60_high.png"]
    monkeypatch.setattr(match, "COPIED_SHA256", bad)
    with pytest.raises(ValueError, match="COPIED_SHA256"):
        match.validate()
