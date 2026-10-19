from pathlib import Path
import pytest
DOC = Path(__file__).resolve().parents[1] / "docs/domain/areas/groundel-maf.md"
LINKS = [f"[{t}](../../decisions.md)" for t in ("<= 10 cm", "10 cm")] + [
    f"[{t}](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/181)"
    for t in ("512 x 512 px", "64 x 64 or 128 x 128 px", "approximately 15 material IDs", "30-45 degrees")]
TOKENS = (
    "library", "visual selection", "audit", "headless", "copies", "original untouched", "per-maf", ".max",
    "catalogue", "previews", "specification", "manufacturer", "picture", "colour", "material", "construction",
    "individual", "reference", "legend", "npm", "light versions", "atlas", "512", "solid", "64", "128", "patterned",
    "larger", "15", "hard edges", "30-45 degrees", "spozu", "placement", "pivot", "lowest point", "raised", "10 cm",
    "projected", "ground", "deleted bottoms", "d094", "d095", "d096")

def section():
    text = DOC.read_text(encoding="utf-8")
    assert text.count("## Project practice") == 1
    t_end = text[:text.index("\n## Source-image evidence")].rindex("\n|")
    p_idx, e_idx = text.index("\n## Project practice"), text.index("\n## Source-image evidence")
    assert t_end < p_idx < e_idx and "## " not in text[t_end + 1:p_idx]
    return text[p_idx:e_idx]

def test_maf_project_practice():
    sec = section().lower()
    assert "project practice" in sec and "not regulation" in sec and not [t for t in TOKENS if t not in sec]

@pytest.mark.parametrize("link", LINKS)
def test_maf_project_practice_links(link):
    assert link in section()
