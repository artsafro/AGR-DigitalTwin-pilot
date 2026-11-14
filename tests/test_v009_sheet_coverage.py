"""new-case: bounded V009 coverage in the four current L2 requirement sheets.

Documentation regressions only; no delivery, metric-policy or model acceptance.
"""
from pathlib import Path
import re

import pytest

from test_area_requirement_sheet import contract

AREAS = Path(__file__).resolve().parents[1] / "docs/domain/areas"
SHEETS = ("body.md", "uv-atlas.md", "textures.md", "package.md")


def coverage_contract(name, text):
    rows = {row[0].split()[0]: row for row in contract(text)}
    for target in ("../../../src/twinqa/scene.py", "../../../tests/qa/test_decision_checks.py",
                   "../../../tests/qa/test_texel_metric_divergence.py"):
        assert f"]({target})" in text, (name, target)
        assert (AREAS / target).is_file(), target
    # No current row, inventory or gap may revive a blanket missing implementation claim.
    for line in text.splitlines():
        if "V009" in line:
            assert not re.search(r"unimplemented|not implemented|no general V009 delivery check", line, re.I), line
    assert not re.search(r"C36[^;\n|]*(?:open|no side chosen)", text), name
    assert "partial" in text.lower()
    assert "512-1706 px/m" in text and "[D160]" in text
    assert "C36 is decided" in text
    assert "not_run" in text
    assert "[D193]" in text and "job-local" in text
    if name == "body.md":
        row = rows["BODY-X"]
        assert row[5] == "none"
        assert "C10 remains a user decision" in row[4]
        assert "split" in row[4].lower() and "V009" in row[4]
        assert re.search(r"^- \*\*BODY-X\*\*.*split", text, re.M)
    if name in ("uv-atlas.md", "textures.md"):
        key = "UV-06" if name == "uv-atlas.md" else "TEX-18"
        assert "V009" in rows[key][5] and "partial" in rows[key][5]
        assert "512-1706 px/m" in rows[key][3] and "[D160]" in rows[key][3]
        assert "C10 remains open" in rows[key][3]
        if "520" in rows[key][3]:
            assert "historical" in rows[key][3] and "superseded" in rows[key][3]
        assert not re.search(rf"^- \*\*{key}:\*\*", text, re.M)
        assert "NPM Ground" in text and "10-40 px/m" in text
        assert "C10" in text and "manual" in text.lower()
    if name == "textures.md":
        assert rows["TEX-17"][5] == "none"
    if name == "uv-atlas.md":
        for token in ("ring-edge", "slot/UDIM", "polygon UV", "Diffuse", "directional",
                      "area", "centroid", "split policy", "NPM Ground density remains unchecked"):
            assert token in text, token
    if name == "package.md":
        entry = next(line for line in text.splitlines() if line.startswith("- **V009**"))
        assert "partial" in entry and "--scene" in entry


@pytest.mark.parametrize("name", SHEETS)
def test_current_v009_coverage_is_bounded(name):
    coverage_contract(name, (AREAS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SHEETS)
def test_stale_claim_at_each_current_v009_statement_is_rejected(name):
    text = (AREAS / name).read_text(encoding="utf-8")
    coverage_contract(name, text)
    lines = text.splitlines()
    witnesses = 0
    for index, line in enumerate(lines):
        if "V009" not in line:
            continue
        for stale in ("V009 unimplemented", "V009 remains unimplemented", "V009 is not implemented"):
            mutated = lines.copy()
            mutated[index] = line.replace("V009", stale, 1)
            with pytest.raises(AssertionError):
                coverage_contract(name, "\n".join(mutated))
            witnesses += 1
    assert witnesses > 0


@pytest.mark.parametrize("name", SHEETS)
def test_evidence_and_exception_omissions_are_rejected(name):
    text = (AREAS / name).read_text(encoding="utf-8")
    coverage_contract(name, text)
    for token in ("../../../src/twinqa/scene.py", "../../../tests/qa/test_decision_checks.py",
                  "../../../tests/qa/test_texel_metric_divergence.py", "[D193]", "job-local",
                  "C36 is decided", "512-1706 px/m", "not_run"):
        assert token in text
        with pytest.raises(AssertionError):
            coverage_contract(name, text.replace(token, "OMITTED"))


@pytest.mark.parametrize("name,key", (("body.md", "BODY-X"), ("textures.md", "TEX-17")))
def test_density_does_not_automatically_cover_npm_or_body_splits(name, key):
    text = (AREAS / name).read_text(encoding="utf-8")
    # Keep the table structurally valid and remove the corresponding none-gap:
    # rejection must come from the bounded-coverage requirement, not generic shape.
    lines = []
    for line in text.splitlines():
        if line.startswith(f"| {key} "):
            line = line.replace(" | none | ", " | V009 | ")
        if line.startswith(f"- **{key}"):
            continue
        lines.append(line)
    with pytest.raises(AssertionError):
        coverage_contract(name, "\n".join(lines))
