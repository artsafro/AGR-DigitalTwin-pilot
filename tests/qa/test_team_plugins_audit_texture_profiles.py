"""new-case: static probe asserting the team-plugins audit separates NPM vs VPM texture contracts.

Static probe: the team-plugins audit must not conflate NPM and VPM textures.

Reads the report and the texture standards only. Does not import a DCC,
generate PNGs, or execute V007.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "research" / "team-plugins-audit.md"
VPM = ROOT / "standards" / "VPM_STANDARD.yaml"
TEXTURES = ROOT / "docs" / "domain" / "areas" / "textures.md"
UV = ROOT / "docs" / "domain" / "areas" / "uv-atlas.md"

WITNESSES = (
    "T_Probe_Diffuse_1.1001.png",
    "T_Probe_ERM_1.1001.png",
    "T_Probe_Normal_1.1001.png",
    "T_Probe_Ground_Diffuse_1.1001.png",
    "T_Probe_Ground_ERM_1.1001.png",
    "T_Probe_Ground_Normal_1.1001.png",
)

DOT_SENTENCE = (
    "The dot before UDIM is mandatory for VPM, not a naming gap "
    "and not an illegal-character gap."
)
NPM_CONTRACT = "separate suffix and packing contract"
INSUFFICIENT = "VPM 4096 with 8 px unique-island spacing is insufficient"
FLORA_FORBIDDEN = "NPM Flora 4096 is forbidden"


def _text(path: Path) -> str:
    assert path.is_file(), f"missing required file: {path}"
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"empty file: {path}"
    return text


def _between(text: str, start: str, end: str) -> str:
    i = text.find(start)
    assert i >= 0, f"missing start marker {start!r}"
    j = text.find(end, i + len(start))
    assert j > i, f"missing end marker {end!r} after {start!r}"
    body = text[i:j]
    assert body.strip(), f"empty section {start!r}"
    return body


def _one_line(text: str, needle: str) -> str:
    hits = [line for line in text.splitlines() if needle in line]
    assert len(hits) == 1, f"{needle!r} matched {len(hits)} lines, expected 1"
    assert hits[0].strip(), f"blank line for {needle!r}"
    return hits[0]


def _standards() -> None:
    vpm = _text(VPM)
    textures = _text(TEXTURES)
    uv = _text(UV)
    assert "required_maps: [Diffuse, ERM, Normal]" in vpm
    assert "texture_oks: 'T_{Address}_{Diffuse|ERM|Normal}_{SlotNumber}.{UDIM}.png'" in vpm
    assert "texture_ground: 'T_{Address}_Ground_{Diffuse|ERM|Normal}_{SlotNumber}.{UDIM}.png'" in vpm
    assert "explicit_texture_filename_exception: 'dot between SlotNumber and UDIM before .png'" in vpm
    assert "padding_px_min: {2048: 16, 4096: 32}" in vpm
    assert "TypeTexture = Diffuse / ERM / Normal" in textures
    tex13 = _one_line(textures, "TEX-13 —")
    assert "≥ 8 px" in tex13 and "≥ 16 px at 2048" in tex13 and "≥ 32 px at 4096" in tex13
    tex16 = _one_line(textures, "TEX-16 —")
    assert "Flora" in tex16 and "2048" in tex16
    uv05 = _one_line(uv, "UV-05 —")
    assert "2048" in uv05 and "Flora" in uv05
    uv13 = _one_line(uv, "UV-13 —")
    assert ">= 8 px" in uv13 and ">= 16 px at 2048" in uv13 and ">= 32 px at 4096" in uv13


def _naming_slices(report: str) -> dict[str, str]:
    return {
        "card": _between(report, "### Texture Map Generator", "### VV layer helpers"),
        "step6": _one_line(report, "6. **UV and atlases.**"),
        "name_row": _one_line(report, "| (new) UDIM name"),
        "r19": _between(report, "19. **Title.**", "20. **Title.**"),
    }


def _assert_no_unqualified_naming_gap(part: str, label: str) -> None:
    chunks = re.split(r"(?<=[.!?])\s+|\n", part)
    for chunk in chunks:
        low = chunk.lower()
        if "naming gap" in low:
            assert "not a naming gap" in low, f"{label} classifies a naming gap: {chunk!r}"
        assert "do not adopt" not in low, f"{label} says do not adopt: {chunk!r}"
        assert "do-not-adopt" not in low, f"{label} says do-not-adopt: {chunk!r}"


def test_udim_diffuse_erm_normal_matches_vpm():
    _standards()
    slices = _naming_slices(_text(REPORT))
    for label, part in slices.items():
        assert "matches VPM" in part, label
        assert "T_Address_Type_Slot.UDIM" in part, label
        assert "T_Address_Ground_Type_Slot.UDIM" in part, label
        assert "Diffuse" in part and "ERM" in part and "Normal" in part, label
        _assert_no_unqualified_naming_gap(part, label)
    cells = [c.strip() for c in slices["name_row"].strip().strip("|").split("|")]
    assert len(cells) >= 4, slices["name_row"]
    assert cells[3] == "matches VPM", cells
    assert "Keep ERM renames out of the pilot" not in slices["r19"]
    assert "not `_d/_r/_m/_n/_o`" not in slices["step6"]


def test_dot_before_udim_is_mandatory_not_a_gap():
    _standards()
    report = _text(REPORT)
    slices = _naming_slices(report)
    charset = _one_line(report, "| (new) Filename letters")
    assert DOT_SENTENCE in slices["card"]
    assert DOT_SENTENCE in slices["r19"]
    assert "not a naming gap" in charset
    assert "matches VPM" in charset
    assert " | hyphen and dot |" not in charset
    _assert_no_unqualified_naming_gap(charset, "charset row")


def test_npm_suffix_packing_is_a_separate_contract():
    _standards()
    slices = _naming_slices(_text(REPORT))
    for label, part in slices.items():
        assert NPM_CONTRACT in part, label
        assert "`_d`" in part or "_d" in part, label


def test_npm_flora_4096_forbidden_capped_at_2048():
    _standards()
    report = _text(REPORT)
    r17 = _between(report, "17. **Title.**", "18. **Title.**")
    flora = _one_line(report, "| (new) Flora atlas default")
    for label, part in (("R17", r17), ("flora row", flora)):
        assert FLORA_FORBIDDEN in part, label
        assert "capped at 2048" in part, label
    assert "2048 and 4096 remain the allowed squares" not in r17
    assert "2048 and 4096 remain the allowed squares" not in flora


def test_vpm_4096_8px_unique_island_insufficient():
    _standards()
    report = _text(REPORT)
    r17 = _between(report, "17. **Title.**", "18. **Title.**")
    flora = _one_line(report, "| (new) Flora atlas default")
    for label, part in (("R17", r17), ("flora row", flora)):
        assert INSUFFICIENT in part, label
        assert ">= 16 px at 2048" in part, label
        assert ">= 32 px at 4096" in part, label
        assert "NPM padding" in part and ">= 8 px" in part, label


def test_r19_does_not_reject_vpm_udim_scheme():
    _standards()
    r19 = _between(_text(REPORT), "19. **Title.**", "20. **Title.**")
    low = r19.lower()
    assert "do not adopt" not in low
    assert "do-not-adopt" not in low
    assert "won't-do" not in r19
    assert "Keep ERM renames out" not in r19
    assert "Pilot texture names stay" not in r19
    assert "**Action.** rule." in r19
    assert "ignore" not in low
    assert "matches VPM" in r19
    assert "Diffuse" in r19 and "ERM" in r19 and "Normal" in r19
    assert "T_Address_Type_Slot.UDIM" in r19
    assert "T_Address_Ground_Type_Slot.UDIM" in r19
    assert "not implemented yet (`app.py:452`)" in r19
    _assert_no_unqualified_naming_gap(r19, "R19")


def test_correction_evidence_records_witnesses():
    _standards()
    evidence = _between(
        _text(REPORT),
        "## Correction evidence (review round 2)",
        "## Missing inputs & limitations",
    )
    for name in WITNESSES:
        assert name in evidence, name
    assert len(WITNESSES) == 6
    assert "2048" in evidence and "RGB" in evidence
    assert "2/2" in evidence and "6/6" in evidence
    assert "VPM maps: pass" in evidence
    assert "matches VPM" in evidence
    assert FLORA_FORBIDDEN in evidence and "capped at 2048" in evidence
    assert INSUFFICIENT in evidence
    assert ">= 32 px" in evidence
    _assert_no_unqualified_naming_gap(evidence, "correction evidence")
