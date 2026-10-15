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
    5: ("vertical-planning", "flat", "not proof", "Steps 5-7", "continue at Step 8", "Steps 8-10 stay mandatory"),
    6: ("Triangulate", "delaunay_2d_cdt", "orig_verts", "source Z", "different Z", "collinear"),
    7: ("Z only", "UV", "vertical offset", "datum", "relief(x, y) + offset", "miss", "face centres", "ray_cast"),
    8: ("GND-07", "C37"),
    9: ("2K", "10-40", "4K", "520-1706", "px per linear metre", "[D097]"),
    10: ("seams", "convex", "[D098]", "gaps", "open polygons", "flipped normals", "validate-delivery"),
}
# Review round 1 (PR #232): phrases a step must not carry. Step 5 must not end the walk on a flat project; the
# Step 6/7 routes must not name operations that were shown to fail (bmesh triangulate on bare points: 0 faces;
# Shrinkwrap/Conform projection: the 6 mm layer steps collapse to 0).
FORBIDDEN = {
    5: ("stop here",),
}
FORBIDDEN_IN_ROUTE = {
    6: ("bmesh triangulation", "Terrain` from points"),
    7: ("Shrinkwrap", "Conform"),
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
        for phrase in FORBIDDEN.get(n, ()):
            if phrase in body.lower():
                found.append(f"step {n}: forbidden {phrase!r}")
        route = re.search(r"^- Route: (.+(?:\n  .+)*)", body, re.M)
        if not route or not any(tool in route.group(1) for tool in ROUTE_TOOLS):
            found.append(f"step {n}: no `- Route:` line naming an existing tool route")
        for phrase in FORBIDDEN_IN_ROUTE.get(n, ()):
            # "Not `X`" / "not used" sentences may name a failing operation as a warning.
            kept = [s for s in re.split(r"(?<=[.;])\s+", route.group(1) if route else "")
                    if not re.match(r"Not\b", s) and "not used" not in s and "not verified" not in s]
            if any(phrase in s for s in kept):
                found.append(f"step {n}: route names failing operation {phrase!r}")
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
    # Review round 1: put back each failing phrase the reviewer found, in the step where it was.
    for n, title, body in steps:
        route = next((l for l in body.splitlines() if l.startswith("- Route: ")), None)
        for phrase in FORBIDDEN.get(n, ()):
            yield f"step {n} says {phrase}", text.replace(f"### Step {n} — {title}{body}",
                                                         f"### Step {n} — {title}\n{phrase.capitalize()} when the project is flat.{body}")
        old_routes = {6: "- Route: Blender headless (bmesh triangulation) or 3ds Max batch (`Terrain` from points).",
                      7: "- Route: 3ds Max batch (`Conform`) or Blender headless (Shrinkwrap, project along Z, then apply)."}
        if n in old_routes and route:
            yield f"step {n} round-1 route", text.replace(route, old_routes[n] + " " + route[len("- Route: "):])


def test_generated_mutations_are_rejected(text):  # E5, probe
    mutations = list(_mutations(text))
    missed = [name for name, mutated in mutations if mutated != text and not skill_findings(mutated)]
    unchanged = [name for name, mutated in mutations if mutated == text]
    assert not unchanged, unchanged
    assert not missed, f"{len(missed)}/{len(mutations)} mutations passed: {missed}"
    assert len(mutations) >= 100


# ---- Review round 1 regressions (PR #232): the procedure, not only its words. -----------------------------------

STEP = 0.006  # layer step of the layered cake, metres
TOL = 0.001


def project_layers(layers: dict[str, list[tuple[float, float, float]]], relief, datum: float):
    """Step 7 as the skill states it: z = relief(x, y) + (z - datum); a miss (relief None) is listed, not moved."""
    out, misses = {}, []
    for name, verts in layers.items():
        moved = []
        for i, (x, y, z) in enumerate(verts):
            r = relief(x, y)
            if r is None:
                misses.append((name, i))
                moved.append((x, y, z))
            else:
                moved.append((x, y, r + (z - datum)))
        out[name] = moved
    return out, misses


def projection_findings(before: dict, after: dict, pairs: list[tuple[str, str]], misses=(), step: float = STEP,
                        centre_gaps: dict | None = None) -> list[str]:
    """The Step 7 `Done when` check. before/after: layer -> {"co": [[x,y,z]...], "uv": [...], "mat": [...]}."""
    found = [f"miss: {m}" for m in misses]
    for name, b in before.items():
        a = after[name]
        if any(abs(p[0] - q[0]) > 1e-6 or abs(p[1] - q[1]) > 1e-6 for p, q in zip(b["co"], a["co"])):
            found.append(f"{name}: XY changed")
        if b.get("uv") != a.get("uv"):
            found.append(f"{name}: UV changed")
        if b.get("mat") != a.get("mat"):
            found.append(f"{name}: material IDs changed")
    for lower, upper in pairs:
        for i, (p, q) in enumerate(zip(after[lower]["co"], after[upper]["co"])):
            if abs((q[2] - p[2]) - step) > TOL:
                found.append(f"{lower}/{upper} vertex {i}: gap {q[2] - p[2]:.4f} m")
    for where, gap in (centre_gaps or {}).items():
        if gap is None or abs(gap - step) > TOL:
            found.append(f"{where}: face-centre gap {gap}")
    return found


def _square(z, half=0.5):
    return [(-half, -half, z), (half, -half, z), (half, half, z), (-half, half, z)]


def _snap(verts, uv=((0, 0.75), (0.25, 0.75), (0.5, 0.75), (0.75, 0.75)), mat=(0,)):
    return {"co": [list(v) for v in verts], "uv": [list(u) for u in uv], "mat": list(mat)}


def _slope(x, y):  # the reviewer's relief z = x on [-2, 2]^2
    return x if -2 <= x <= 2 and -2 <= y <= 2 else None


def test_r1_flat_branch_continues_at_step_8(text):  # R1-flat
    steps = {n: body for n, _, body in _steps(text)}
    flat = steps[5].split("**Flat project:**")[1].split("\n- **")[0]
    assert "stop here" not in steps[5].lower()
    assert "continue at Step 8" in flat and "Steps 8-10 stay mandatory" in flat and "not proof" in flat
    for n in (8, 9, 10):  # the downstream steps carry no flat exemption
        assert "flat" not in steps[n].lower(), n


def test_r1_relief_branch_control(text):  # R1-flat control: a relief project goes on into Steps 6-7
    steps = {n: body for n, _, body in _steps(text)}
    assert "**Relief project:**" in steps[5] and "vertical-planning" in steps[5]
    assert "delaunay_2d_cdt" in steps[6] and "relief(x, y) + offset" in steps[7]


def test_r1_vertical_offset_keeps_6mm_on_slope():  # R1-proj: reviewer input, skill semantics
    datum = 2.0
    before = {"base": _snap(_square(datum), mat=(0,)), "top": _snap(_square(datum + STEP), mat=(1,))}
    moved, misses = project_layers({k: [tuple(c) for c in v["co"]] for k, v in before.items()}, _slope, datum)
    after = {k: {**before[k], "co": [list(c) for c in moved[k]]} for k in before}
    assert misses == []
    assert projection_findings(before, after, [("base", "top")]) == []
    assert [round(t[2] - b[2], 6) for b, t in zip(moved["base"], moved["top"])] == [STEP] * 4


def test_r1_zero_gap_control_fails():  # R1-proj control: plain projection (Shrinkwrap/Conform semantics)
    datum = 2.0
    before = {"base": _snap(_square(datum)), "top": _snap(_square(datum + STEP), mat=(1,))}
    after = {k: {**v, "co": [[x, y, _slope(x, y)] for x, y, _ in v["co"]]} for k, v in before.items()}
    found = projection_findings(before, after, [("base", "top")])
    assert len([f for f in found if "gap 0.0000" in f]) == 4


def test_r1_miss_is_listed_not_moved():  # R1-proj edge: vertex outside the relief
    datum = 0.0
    moved, misses = project_layers({"wide": _square(datum, half=3.0)}, _slope, datum)
    assert misses == [("wide", 0), ("wide", 1), ("wide", 2), ("wide", 3)]
    assert moved["wide"] == _square(datum, half=3.0)
    assert projection_findings({"wide": _snap(_square(0, 3.0))}, {"wide": _snap(moved["wide"])}, [], misses)


def test_r1_combined_defects_all_reported():  # R1 combination: zero gap + UV + material + miss + bent centre
    before = {"base": _snap(_square(0.0)), "top": _snap(_square(STEP), mat=(1,))}
    after = {"base": _snap([(x, y, x) for x, y, _ in _square(0.0)]),
             "top": _snap([(x, y, x) for x, y, _ in _square(STEP)], uv=((0, 0),) * 4, mat=(0,))}
    found = projection_findings(before, after, [("base", "top")], misses=[("top", 9)],
                                centre_gaps={"ridge cell": 1.006})
    for kind in ("miss", "UV changed", "material IDs changed", "gap 0.0000", "face-centre gap"):
        assert any(kind in f for f in found), kind
    assert projection_findings(before, before, [("base", "top")], centre_gaps={"c": STEP}) == []  # clean control


@pytest.mark.blender
def test_r1_blender_routes(tmp_path):  # R1-relief, R1-proj: the routes the skill names, run in Blender
    import json
    import subprocess

    from twinqa.scene import find_blender

    blender = find_blender()
    if blender is None:
        pytest.skip("Blender not installed")
    out = tmp_path / "probe.json"
    subprocess.run([blender, "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
                    "--python", str(ROOT / "tests/fixtures/model_ground_route_probe.py"), "--", str(out)],
                   check=True, capture_output=True, timeout=300)
    d = json.loads(out.read_text(encoding="utf-8"))
    # Step 6: reviewer's four points; control: bmesh.ops.triangulate on bare points gives 0 faces.
    assert d["control_bmesh_triangulate_points"] == {"vertices": 4, "faces": 0}
    s6 = d["step6"]
    assert s6["four"]["status"] == "ok" and s6["four"]["faces"] == 2 and s6["four"]["max_dz_vs_source_m"] < 1e-3
    assert s6["duplicate_same_z"]["faces"] == 2
    for case, status in (("empty", "too_few_points"), ("two", "too_few_points"), ("collinear", "collinear"),
                         ("duplicate_contradictory_z", "contradictory_z")):
        assert s6[case]["status"] == status and s6[case]["faces"] == 0, case
    # Step 7: vertical-offset route keeps 6 mm and XY/UV/material IDs; misses are listed.
    s7 = d["step7"]
    misses = [(k, i) for k, v in s7["misses"].items() for i in v]
    assert projection_findings(s7["before"], s7["after"], [("synthetic_base", "synthetic_top")], misses,
                               centre_gaps={"centre": s7["face_centre_gap_m"]}) == []
    assert s7["outside_misses"] == [0, 1, 2, 3]
    # Controls: Shrinkwrap PROJECT collapses the gap; a ridge inside a cell passes at vertices, fails at the centre.
    assert all(abs(g) < 1e-6 for g in d["control_shrinkwrap_gaps_m"])
    assert abs(d["ridge"]["corner_gap_m"] - STEP) <= TOL and abs(d["ridge"]["face_centre_gap_m"] - STEP) > TOL
