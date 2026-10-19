"""Patterns follow the weld of #99 and the triangle fans of #100 (#105)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ROOT / "docs" / "domain" / "patterns"


def test_non_90_corner_follows_weld_and_fans():
    text = (PATTERNS / "non-90-corner.md").read_text(encoding="utf-8")
    assert "0.1 mm" not in text
    assert "weld_m" in text
    assert "triangle" in text
    assert "a triangle is not built" not in text
    for line in text.splitlines():
        if "BuildError" in line:
            assert "x-extreme corner" not in line


def test_roof_inset_plane_gap_is_past_weld():
    text = (PATTERNS / "INDEX.md").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if "`roof-inset-plane`" in line and line.startswith("|")]
    assert rows
    for row in rows:
        assert "weld_m" in row
        assert "2-10 mm" not in row
