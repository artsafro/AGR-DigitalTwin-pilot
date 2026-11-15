"""KPP1 #1416 round 3 [D313]: exception row, wire-v003 evidence hashes, wire_sheet.py fail-closed."""
import importlib.util
import json
import re
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "jobs/KPP1/ground-budget-1416"
SPEC = importlib.util.spec_from_file_location("wire_sheet_1416", JOB / "wire_sheet.py")
wire_sheet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wire_sheet)
SHOTS = ["01_overview_top", "02_densest_cell", "03_skirt_edge", "04_building_edge"]


def test_d313_exception_row_records_numbers_and_open_items():
    rows = [r for r in (ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines() if r.startswith("| D313 |")]
    assert len(rows) == 1
    for needle in ("150 567", "15 976", "63 537", "skirt", "406 pairs", "V015", "V017", "s_podz", "[D256]",
                   "wire-v003", "passed=false stays honest"):
        assert needle in rows[0], needle


def test_report_round3_cites_d313_and_names_every_wire_file():
    rep = (JOB / "REPORT.md").read_text(encoding="utf-8")
    assert "[D313]" in rep and "D256-type exception?" not in rep
    for name in SHOTS:
        assert f"{name}.png" in rep, name
    assert "wire-sheet-v003.png" in rep and "s_podz" in rep


def test_evidence_hashes_cover_wire_v003_once_each():
    lines = (JOB / "evidence-SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    wire = [ln for ln in lines if "*wire-v003/" in ln]
    names = sorted(ln.split("*wire-v003/")[1] for ln in wire)
    assert names == sorted([f"{s}.png" for s in SHOTS] + ["wire-report.json", "wire-sheet-v003.png"])
    assert all(re.fullmatch(r"[0-9a-f]{64} \*wire-v003/\S+", ln) for ln in wire)


def _fixture(d: Path, skip=None):
    d.mkdir()
    for s in SHOTS:
        if s != skip:
            Image.new("RGB", (160, 120), "grey").save(d / f"{s}.png")
    (d / "wire-report.json").write_text(json.dumps({
        "ground_sha256": "a" * 64, "tris_equiv_total": 179816,
        "quad_review_view_by_sides": {"SM_Kpp_1_Flora": {"3": 1, "4": 2}},
        "densest_cell_10m": {"center": [1.0, 2.0], "polygons": 3}}), encoding="utf-8")


def test_sheet_writes_once_and_hashes_every_file(tmp_path):
    d = tmp_path / "wire"
    _fixture(d)
    wire_sheet.main(d)
    assert b"\r" not in (d / "SHA256SUMS.txt").read_bytes()  # review P3 #1418: LF, never CRLF
    sums = (d / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert sorted(ln.split("*")[1] for ln in sums) == sorted(
        [f"{s}.png" for s in SHOTS] + ["wire-report.json", "wire-sheet-v003.png"])
    before = (d / "wire-sheet-v003.png").read_bytes()
    with pytest.raises(SystemExit, match="exists"):
        wire_sheet.main(d)
    assert (d / "wire-sheet-v003.png").read_bytes() == before


@pytest.mark.parametrize("skip", SHOTS)
def test_missing_render_fails_and_writes_nothing(tmp_path, skip):
    d = tmp_path / "wire"
    _fixture(d, skip=skip)
    with pytest.raises(SystemExit, match=skip):
        wire_sheet.main(d)
    assert not (d / "wire-sheet-v003.png").exists() and not (d / "SHA256SUMS.txt").exists()
