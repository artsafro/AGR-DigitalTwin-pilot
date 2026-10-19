"""Task #211: Documentation quotation regression for Textures L1 requirement sheet."""
from pathlib import Path


def test_textures_source_quote():
    sheet_path = Path(__file__).resolve().parents[1] / "docs" / "domain" / "areas" / "textures.md"
    assert sheet_path.is_file(), f"Requirement sheet not found: {sheet_path}"

    text = sheet_path.read_text(encoding="utf-8")
    anchors = [
        line for line in text.splitlines()
        if line.startswith("- **TEX-09")
    ]
    assert len(anchors) == 1, f"Expected 1 TEX-09 anchor, found {len(anchors)}"
    anchor = anchors[0]

    assert "Растровое изображение в формате PNG с разрешением 128×128 пикселей" in anchor
    assert "глубиной цвета 8 бит на канал" in anchor
