"""Contract of the `model-ground` project skill (#176).

The skill is an agent procedure: SPOZU DWG -> boundary -> coverings -> layered cake -> elevations -> relief ->
projection -> curbs/steps -> NPM/VPM -> checks, each step with a tool route and a Needs marker, fallbacks A/B,
and links instead of copied rule text. `skill_findings` is the checker; the generated mutations prove it rejects
each kind of breakage, not only that the real file passes.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/model-ground/SKILL.md"
SHEET = ROOT / "docs/domain/areas/ground-surface.md"
DECISIONS = ROOT / "docs/decisions.md"
CONFLICTS = ROOT / "docs/domain/conflicts.md"

# (step number, words its heading must contain), in procedure order.
STEPS = [
    (1, ("spozu",)),
    (2, ("boundary",)),
    (3, ("coverings", "contours")),
    (4, ("layered cake",)),
    (5, ("elevations",)),
    (6, ("relief surface",)),
    (7, ("project", "relief")),
    (8, ("curbs", "steps", "ramps", "retaining walls")),
    (9, ("npm", "vpm")),
    (10, ("checks",)),
]
# Tokens the body of a step must carry (the issue's parameters for that step).
STEP_TOKENS = {
    1: ("DXFOUT", "ezdxf"),
    2: ("граница проектируемого участка", "граница ГП", "GND-01"),
    3: ("hatch", "one DWG per covering type"),
    4: ("largest", "6 mm", "Subdivide", "3 m", "tiling"),
    5: ("vertical-planning", "flat"),
    6: ("Triangulate",),
    7: ("Z only", "UV"),
    8: ("GND-07", "C37"),
    9: ("2K", "10-40", "4K", "520-1706", "px per linear metre", "[D097]"),
    10: ("seams", "convex", "[D098]", "gaps", "open polygons", "flipped normals", "validate-delivery"),
}
ROUTE_TOOLS = ("dcc_batch.py acad", "ezdxf", "dcc_batch.py max", "3ds Max batch", "Blender headless",
               "validate_package.py", "3ds Max")
NEEDS = ("headless", "live", "human")
STEP_RE = re.compile(r"^### Step (\d+) — (.+)$", re.M)
LINK_RE = re.compile(r"\]\(([^)#\s]+)(#[^)\s]*)?\)")


def _steps(text: str) -> list[tuple[int, str, str]]:
    marks = list(STEP_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        tail = text.find("\n## ", m.end())
        if tail != -1 and tail < end:
            end = tail
        out.append((int(m.group(1)), m.group(2), text[m.end():end]))
    return out


def _section(text: str, heading: str) -> str:
    start = text.find(f"\n## {heading}")
    if start == -1:
        return ""
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def _shingles(text: str, n: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[\wА-Яа-яЁё]+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _rule_text() -> str:
    """Rule text the skill must link, not copy: the sheet's table rows and every decision line."""
    sheet = [line for line in SHEET.read_text(encoding="utf-8").splitlines() if line.startswith("| GND-")]
    decisions = [line for line in DECISIONS.read_text(encoding="utf-8").splitlines() if line.startswith("| D")]
    return "\n".join(sheet + decisions)


def skill_findings(text: str, base: Path = SKILL.parent) -> list[str]:
    found: list[str] = []
    lines = text.splitlines()
    parts = text.split("---", 2)
    if not lines or lines[0] != "---" or len(parts) < 3 or "name: model-ground" not in parts[1]:
        found.append("frontmatter: missing `name: model-ground`")
    steps = _steps(text)
    numbers = [n for n, _, _ in steps]
    if numbers != [n for n, _ in STEPS]:
        found.append(f"steps: expected 1..10 in order, got {numbers}")
    by_number = {n: (title, body) for n, title, body in steps}
    for n, words in STEPS:
        if n not in by_number:
            continue
        title, body = by_number[n]
        for word in words:
            if word not in title.lower():
                found.append(f"step {n}: heading lacks {word!r}")
        for token in STEP_TOKENS[n]:
            if token not in body:
                found.append(f"step {n}: body lacks {token!r}")
        route = re.search(r"^- Route: (.+)$", body, re.M)
        if not route or not any(tool in route.group(1) for tool in ROUTE_TOOLS):
            found.append(f"step {n}: no `- Route:` line naming an existing tool route")
        need = re.search(r"^- Needs: (.+)$", body, re.M)
        if not need or not any(re.search(rf"\b{m}\b", need.group(1)) for m in NEEDS):
            found.append(f"step {n}: no `- Needs:` line with headless/live/human")
        if not re.search(r"^- Done when: .+", body, re.M):
            found.append(f"step {n}: no completion criterion")
    fallbacks = _section(text, "Fallback methods")
    for method in ("Method A", "Method B"):
        block = fallbacks.split(f"**{method}")[1].split("\n- **")[0] if f"**{method}" in fallbacks else ""
        if not block:
            found.append(f"fallbacks: {method} missing")
            continue
        for token in ("Use when:", "Route:", "Needs:"):
            if token not in block:
                found.append(f"fallbacks: {method} lacks {token!r}")
    if "stitch" not in fallbacks.lower() or "ShapeMerge" not in fallbacks or "Conform" not in fallbacks:
        found.append("fallbacks: A must be stitch + subdivide, B ShapeMerge/Conform")
    targets = {}
    for m in LINK_RE.finditer(text):
        if m.group(1).startswith("http"):
            continue
        path = (base / m.group(1)).resolve()
        targets[m.group(1)] = path
        if not path.exists():
            found.append(f"link: {m.group(1)} does not exist")
        elif m.group(2) and m.group(2) != "#":
            anchor = m.group(2)[1:]
            heads = {re.sub(r"[^\w\- ]", "", h.strip("# ").lower()).replace(" ", "-")
                     for h in path.read_text(encoding="utf-8").splitlines() if h.startswith("#")}
            if anchor not in heads:
                found.append(f"link: anchor #{anchor} not in {m.group(1)}")
    names = {Path(t).name for t in targets}
    for required in ("ground-surface.md", "decisions.md", "conflicts.md"):
        if required not in names:
            found.append(f"link: no link to {required}")
    decided = set(re.findall(r"^\| (D\d+) ", DECISIONS.read_text(encoding="utf-8"), re.M))
    for d in set(re.findall(r"\[(D\d+)\]", text)) - decided:
        found.append(f"decision {d} is not in docs/decisions.md")
    conflict_ids = set(re.findall(r"^(\d+)\. ", CONFLICTS.read_text(encoding="utf-8"), re.M))
    for c in set(re.findall(r"\bC(\d+)\b", text)) - conflict_ids:
        found.append(f"conflict C{c} is not in docs/domain/conflicts.md")
    copied = _shingles(text) & _shingles(_rule_text())
    if copied:
        found.append(f"rule text copied: {' '.join(sorted(copied)[0])!r} (+{len(copied) - 1})")
    if "«" in text and re.search(r"«[^»]{40,}»", text):
        found.append("rule text copied: long «quotation»")
    return found


@pytest.fixture(scope="module")
def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_exists_with_frontmatter(text):  # A1
    assert text.splitlines()[0] == "---" and "name: model-ground" in text.split("---")[1]


def test_skill_has_no_findings(text):  # A1-A10 on the real file
    assert skill_findings(text) == []


def test_steps_in_issue_order(text):  # A2, E1
    assert [n for n, _, _ in _steps(text)] == list(range(1, 11))


def test_every_step_has_route_and_needs(text):  # A8
    for n, _, body in _steps(text):
        assert re.search(r"^- Route: ", body, re.M), n
        assert re.search(r"^- Needs: (headless|live|human)", body, re.M), n


def test_fallbacks_have_use_when(text):  # A7
    section = _section(text, "Fallback methods")
    assert section.count("Use when:") >= 2 and "Method A" in section and "Method B" in section


def test_empty_input_rejected():  # E4
    found = skill_findings("")
    assert any(f.startswith("frontmatter") for f in found)
    assert any(f.startswith("steps:") for f in found)
    assert any(f.startswith("fallbacks:") for f in found)
    assert any(f.startswith("link:") for f in found)


def _mutations(text: str):
    steps = _steps(text)
    for n, title, body in steps:  # drop each step
        yield f"drop step {n}", text.replace(f"### Step {n} — {title}{body}", "")
    for (a, ta, ba), (b, tb, bb) in zip(steps, steps[1:]):  # swap neighbours
        yield f"swap {a}/{b}", text.replace(f"### Step {a} — {ta}{ba}### Step {b} — {tb}{bb}",
                                            f"### Step {b} — {tb}{bb}### Step {a} — {ta}{ba}")
    for n, title, body in steps:  # remove route / needs / done-when per step
        for prefix in ("- Route: ", "- Needs: ", "- Done when: "):
            line = next(l for l in body.splitlines() if l.startswith(prefix))
            yield f"step {n} no {prefix.strip()}", text.replace(f"### Step {n} — {title}{body}",
                                                                 f"### Step {n} — {title}" + body.replace(line, ""))
        need = next(l for l in body.splitlines() if l.startswith("- Needs: "))
        yield f"step {n} bogus needs", text.replace(f"### Step {n} — {title}{body}",
                                                   f"### Step {n} — {title}" + body.replace(need, "- Needs: maybe"))
    for n, tokens in STEP_TOKENS.items():  # remove each required token from its step
        title, body = next((t, b) for k, t, b in steps if k == n)
        for token in tokens:
            yield f"step {n} lacks {token}", text.replace(f"### Step {n} — {title}{body}",
                                                          f"### Step {n} — {title}" + body.replace(token, "X"))
    for method in ("Method A", "Method B"):
        yield f"drop {method}", text.replace(f"**{method}", "**Method Z")
        block = text.split(f"**{method}")[1].split("\n- **")[0]
        yield f"{method} no use-when", text.replace(block, block.replace("Use when:", "Also:"))
    yield "broken link", text.replace("docs/domain/areas/ground-surface.md)", "docs/domain/areas/ground-surfaces.md)", 1)
    yield "broken anchor", text.replace("#project-practice", "#project-practise")
    yield "unknown decision", text.replace("[D097]", "[D9097]", 1)
    yield "unknown conflict", text.replace("C37", "C937", 1)
    rows = [l for l in SHEET.read_text(encoding="utf-8").splitlines() if l.startswith("| GND-")]
    for i, row in enumerate(rows):  # paste the longest rule cell of each row into the skill
        cell = max(row.split(" | ")[2:4], key=len)
        yield f"copied GND row {i + 1}", text + "\n" + cell + "\n"
    yield "copied quote", text + "\n«Полигоны по периметру объекта геометрии благоустройства должны быть выдавлены»\n"


def test_generated_mutations_are_rejected(text):  # E5, probe
    mutations = list(_mutations(text))
    missed = [name for name, mutated in mutations if mutated != text and not skill_findings(mutated)]
    unchanged = [name for name, mutated in mutations if mutated == text]
    assert not unchanged, unchanged
    assert not missed, f"{len(missed)}/{len(mutations)} mutations passed: {missed}"
    assert len(mutations) >= 100
