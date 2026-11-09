"""Contract of the modelling gates in the `validate-delivery` skill (#1030).

new-case: doc contract for three manual gates (texture-joint continuity, 10-20 mm decor embed, edge loops [D200])
and the "never bend geometry to pass a validator" guidance. The gates are manual: each starts as `not checked`
and keeps the verdict `not passed` until measured and signed. `gate_findings` is the checker; the mutations prove
it rejects a skill with a gate removed, weakened or unlinked, not only that the real files pass.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/validate-delivery/SKILL.md"
CHECKLIST = ROOT / "docs/domain/validation.md"
PRINCIPLES = ROOT / "docs/agents/working-principles.md"

# gate id -> phrases its paragraph must contain (case-insensitive)
GATES = {
    "G1": ("texture-joint continuity", "joint phase", "cassette joints", "docs/domain/uv-textures.md",
           "joint_continuity_v008.py", "unmatched"),
    "G2": ("decor embed", "10-20 mm", "[d199]", "docs/domain/geometry.md", "gap > 0", "stand-off",
           "conflicts #44"),
    "G3": ("edge loops", "[d200]"),
}
PRINCIPLE_HEADING = "## Never bend geometry to pass a validator"
PRINCIPLE_PHRASES = ("cut a continuous element", "stand-off", "move parts", "stop and ask the user",
                     "docs/domain/conflicts.md", "[d199]")


def gate_paragraph(text: str, gate: str) -> str:
    match = re.search(rf"^- \*\*{gate}\b.*?(?=^- \*\*G\d|^#|\Z)", text, re.M | re.S)
    return match.group(0) if match else ""


def gate_findings(skill: str, checklist: str, principles: str) -> list[str]:
    out = []
    for gate, phrases in GATES.items():
        for name, text in (("skill", skill), ("checklist", checklist)):
            para = " ".join(gate_paragraph(text, gate).lower().split())
            if not para:
                out.append(f"{name}: gate {gate} missing")
                continue
            out += [f"{name}: gate {gate} lacks {p!r}" for p in phrases if p not in para]
            if name == "skill" and "not checked" not in para:
                out.append(f"skill: gate {gate} does not start as 'not checked'")
    low = skill.lower()
    if "working-principles.md#never-bend-geometry-to-pass-a-validator" not in low:
        out.append("skill: no link to the never-bend-geometry guidance")
    if "g1-g3" not in low.split("## completion", 1)[-1]:
        out.append("skill: completion does not hold the verdict on gates G1-G3")
    section = principles.split(PRINCIPLE_HEADING, 1)
    if len(section) < 2:
        out.append("principles: heading missing")
    else:
        body = " ".join(section[1].split("\n## ", 1)[0].lower().split())
        out += [f"principles: lacks {p!r}" for p in PRINCIPLE_PHRASES if p not in body]
    return out


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_real_files_pass():
    assert gate_findings(read(SKILL), read(CHECKLIST), read(PRINCIPLES)) == []


def _drop_gate(text: str, gate: str) -> str:
    return text.replace(gate_paragraph(text, gate), "")


MUTATIONS = {
    "skill without G1": lambda s, c, p: (_drop_gate(s, "G1"), c, p),
    "skill without G2": lambda s, c, p: (_drop_gate(s, "G2"), c, p),
    "skill without G3": lambda s, c, p: (_drop_gate(s, "G3"), c, p),
    "checklist without G2": lambda s, c, p: (s, _drop_gate(c, "G2"), p),
    "G2 loses the gap rule": lambda s, c, p: (s.replace("gap > 0", "gap"), c, p),
    "G1 starts as pass": lambda s, c, p: (s.replace(gate_paragraph(s, "G1"),
                                                    gate_paragraph(s, "G1").replace("not checked", "pass")), c, p),
    "skill unlinks guidance": lambda s, c, p: (s.replace("#never-bend-geometry-to-pass-a-validator", ""), c, p),
    "completion ignores gates": lambda s, c, p: (s.replace("G1-G3", "G1"), c, p),
    "principles heading gone": lambda s, c, p: (s, c, p.replace(PRINCIPLE_HEADING, "## Other")),
    "principles lose stop-and-ask": lambda s, c, p: (s, c, p.replace("stop and ask the user", "decide")),
    "all empty": lambda s, c, p: ("", "", ""),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_mutation_is_rejected(name):
    texts = MUTATIONS[name](read(SKILL), read(CHECKLIST), read(PRINCIPLES))
    assert texts != (read(SKILL), read(CHECKLIST), read(PRINCIPLES)), f"mutation {name} changed nothing"
    assert gate_findings(*texts), name
