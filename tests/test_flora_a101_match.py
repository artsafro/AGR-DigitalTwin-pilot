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


def test_validate_rejects_missing_hash(monkeypatch):
    bad = dict(match.COPIED_SHA256)
    del bad["el_nidiformis_t1_h60_high.png"]
    monkeypatch.setattr(match, "COPIED_SHA256", bad)
    with pytest.raises(ValueError, match="COPIED_SHA256"):
        match.validate()
