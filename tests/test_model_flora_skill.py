"""Contract of the `model-flora` project skill (#188).

The skill is an agent procedure: planting schedule + SPOZU points -> flower beds (texture or models) -> library
species -> schedule check -> new-species texture route -> NPM star / VPM shell -> trees -> placement and bed scatter ->
one 2048 atlas from the placed scene -> checks, each step with a tool route, a Needs marker and a completion criterion, and links instead of
copied rule text. `skill_findings` is the checker; the generated mutations prove it rejects each kind of breakage,
not only that the real file passes. `procedure_walk` follows the steps in their written order on a schedule with an
area-only modelled bed (review round 1 of PR #237): every plant in the scene must have an atlas tile, and texture-only
beds and lawns must stay Ground texture.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/model-flora/SKILL.md"
SHEET = ROOT / "docs/domain/areas/flora.md"
DECISIONS = ROOT / "docs/decisions.md"
CONFLICTS = ROOT / "docs/domain/conflicts.md"

# (step number, words its heading must contain), in procedure order. Beds are classified before the library so their
# species go through it; placement (points and bed scatter) precedes the one atlas (#216, #217, PR #237 round 1).
STEPS = [
    (1, ("planting schedule", "spozu")),
    (2, ("flower beds", "texture", "models")),
    (3, ("library",)),
    (4, ("schedule",)),
    (5, ("new species", "texture")),
    (6, ("npm", "star", "vpm", "shell")),
    (7, ("trees", "library")),
    (8, ("placement", "spozu", "bed")),
    (9, ("atlas", "2048", "placed scene")),
    (10, ("checks",)),
]
# Tokens the body of a step must carry (the issue's parameters for that step).
STEP_TOKENS = {
    1: ("PyMuPDF", "DXFOUT", "ezdxf", "Latin", "no rotation"),
    2: ("[D101]", "Ground texture", "lists the plants", "big bushes", "model-ground", "no Flora tile",
        "species rows"),
    3: ("catalogue.json", "Text objects", "Tris", "#189", "never invented"),
    4: ("±20 %", "[D099]", "FLO-04", "colour", "review"),
    5: ("dt_ai.materials.flora", "review sheet", "explicit approval", "opacity", "2K front view"),
    6: ("[D102]", "only when the user asks", "library's VPM bushes", "201-299", "opacity"),
    7: ("101-199", "speedtree-mcp", "trunk"),
    8: ("10 cm", "random rotation about Z", "±10 %", "±20 %", "[D100]", "[D095]", "seed", "pivot on the point",
        "scatter", "bed area"),
    9: ("one atlas", "2048", "same factor", "[D020]", "#217", "material ID", "atlas_maf.py"),
    10: ("validate-delivery", "validate_package.py", "FLO-15", "[D097]", "`passed`"),
}
# Steps whose Needs line must name the user (texture review, colour, visual review).
HUMAN_STEPS = (4, 5, 10)
ROUTE_TOOLS = ("PyMuPDF", "dcc_batch.py", "ezdxf", "3ds Max batch", "Blender headless", "validate_package.py",
               "dt_ai.materials.flora", "catalogue", "atlas_maf.py")
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


def _shingles(text: str, n: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[\wА-Яа-яЁё]+", re.sub(r"https?://\S+", " ", text).lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _rule_text() -> str:
    """Rule text the skill must link, not copy: the sheet's rows and practice bullets, every decision line."""
    sheet = SHEET.read_text(encoding="utf-8")
    practice = sheet.split("## Project practice", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in sheet.splitlines() if line.startswith("| FLO-")]
    decisions = [line for line in DECISIONS.read_text(encoding="utf-8").splitlines() if line.startswith("| D")]
    return "\n".join(rows + decisions + [practice])


def _anchor(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip("# ").lower()).replace(" ", "-")


# Schedule of the dry walk (Silikatniy UVK sheet 6): point plants, the area-only modelled bed pos. 10, a bed that only
# says «цветник» and the lawns pos. 11-12.
WALK_ROWS = [
    {"pos": 3, "kind": "point", "species": ("Acer platanoides",)},
    {"pos": 5, "kind": "point", "species": ("Hydrangea arborescens",)},
    {"pos": 10, "kind": "bed_listed", "species": ("Iris hybrida", "Hosta glauca", "Geranium perenne"), "area_m2": 21.3},
    {"pos": 90, "kind": "bed_unlisted", "species": (), "area_m2": 12.0},
    {"pos": 11, "kind": "lawn", "species": (), "area_m2": 300.0},
]


def _role(title: str) -> str | None:
    low = title.lower()
    for role, word in (("beds", "flower beds"), ("library", "library"), ("placement", "placement"), ("atlas", "atlas")):
        if word in low and not (role == "library" and "trees" in low):
            return role
    return None


def procedure_walk(text: str, rows: list[dict] = WALK_ROWS) -> dict:
    """Follow the steps in written order on `rows`; return the scene, the atlas and the Ground texture items.

    Beds step: rows naming their plants become modelled species (scattered then, or by a later placement step whose
    body scatters over the bed area); other beds and lawns go to Ground. Library step: every species known so far is
    resolved. Placement: point species, plus modelled-bed species when it scatters. Atlas: tiles for the scene now.
    """
    state = {"scene": [], "atlas": None, "atlases": 0, "ground": [], "resolved": set(), "bed_species": []}
    for _, title, body in _steps(text):
        role = _role(title)
        if role == "beds":
            for row in rows:
                if row["kind"] == "bed_listed" and "lists the plants" in body:
                    state["bed_species"] += list(row["species"])
                elif row["kind"] in ("bed_unlisted", "lawn") and "Ground texture" in body:
                    state["ground"].append(row["pos"])
            if state["atlases"] and "scatter" in body:  # a late scatter adds plants after the atlas
                state["scene"] += state["bed_species"]
        elif role == "library":
            state["resolved"] |= {s for r in rows if r["kind"] == "point" for s in r["species"]}
            state["resolved"] |= set(state["bed_species"])
        elif role == "placement":
            state["scene"] += [s for r in rows if r["kind"] == "point" for s in r["species"]]
            if "scatter" in body and "bed area" in body:
                state["scene"] += state["bed_species"]
        elif role == "atlas":
            state["atlases"] += 1
            state["atlas"] = set(state["scene"])
    return state


def walk_findings(text: str, rows: list[dict] = WALK_ROWS) -> list[str]:
    state = procedure_walk(text, rows)
    found = []
    atlas = state["atlas"] or set()
    expected = {s for r in rows if r["kind"] in ("point", "bed_listed") for s in r["species"]}
    for species in sorted(expected - set(state["scene"])):
        found.append(f"walk: {species} never reaches the placed scene")
    for species in sorted(set(state["scene"]) - atlas):
        found.append(f"walk: {species} is in the scene but has no atlas tile")
    for species in sorted(set(state["scene"]) - state["resolved"]):
        found.append(f"walk: {species} placed without the library / texture route")
    for row in rows:
        if row["kind"] in ("bed_unlisted", "lawn") and row["pos"] not in state["ground"]:
            found.append(f"walk: pos. {row['pos']} ({row['kind']}) is not handed to Ground texture")
    if state["atlases"] != 1:
        found.append(f"walk: {state['atlases']} atlas steps, expected 1")
    return found


def skill_findings(text: str, base: Path = SKILL.parent) -> list[str]:
    found: list[str] = []
    lines = text.splitlines()
    parts = text.split("---", 2)
    if not lines or lines[0] != "---" or len(parts) < 3 or "name: model-flora" not in parts[1]:
        found.append("frontmatter: missing `name: model-flora`")
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
        elif n in HUMAN_STEPS and not re.search(r"\bhuman\b", need.group(1)):
            found.append(f"step {n}: `- Needs:` does not mark the user (human)")
        if not re.search(r"^- Done when: .+", body, re.M):
            found.append(f"step {n}: no completion criterion")
    targets = {}
    for m in LINK_RE.finditer(text):
        if m.group(1).startswith("http"):
            continue
        path = (base / m.group(1)).resolve()
        targets[m.group(1)] = path
        if not path.exists():
            found.append(f"link: {m.group(1)} does not exist")
        elif m.group(2) and m.group(2) != "#":
            heads = {_anchor(h) for h in path.read_text(encoding="utf-8").splitlines() if h.startswith("#")}
            if m.group(2)[1:] not in heads:
                found.append(f"link: anchor {m.group(2)} not in {m.group(1)}")
    names = {Path(t).name for t in targets}
    for required in ("flora.md", "decisions.md", "conflicts.md", "pipeline-flora-textures.md"):
        if required not in names:
            found.append(f"link: no link to {required}")
    decided = set(re.findall(r"^\| (D\d+) ", DECISIONS.read_text(encoding="utf-8"), re.M))
    for d in set(re.findall(r"\[(D\d+)\]", text)) - decided:
        found.append(f"decision {d} is not in docs/decisions.md")
    conflict_ids = set(re.findall(r"^(\d+)\. ", CONFLICTS.read_text(encoding="utf-8"), re.M))
    for c in set(re.findall(r"\bC(\d+)\b", text)) - conflict_ids:
        found.append(f"conflict C{c} is not in docs/domain/conflicts.md")
    sheet_rows = set(re.findall(r"^\| (FLO-\d+) ", SHEET.read_text(encoding="utf-8"), re.M))
    for row in set(re.findall(r"\bFLO-\d+\b", text)) - sheet_rows:
        found.append(f"sheet row {row} is not in docs/domain/areas/flora.md")
    found += walk_findings(text)
    copied = _shingles(text) & _shingles(_rule_text())
    if copied:
        found.append(f"rule text copied: {' '.join(sorted(copied)[0])!r} (+{len(copied) - 1})")
    if re.search(r"«[^»]{40,}»", text):
        found.append("rule text copied: long «quotation»")
    return found


@pytest.fixture(scope="module")
def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_exists_with_frontmatter(text):  # A1
    assert text.splitlines()[0] == "---" and "name: model-flora" in text.split("---")[1]


def test_skill_has_no_findings(text):  # A1-A6 on the real file
    assert skill_findings(text) == []


def test_steps_in_order_beds_library_placement_atlas(text):  # A2, E1
    steps = _steps(text)
    assert [n for n, _, _ in steps] == list(range(1, 11))
    roles = [_role(t) for _, t, _ in steps]
    assert roles.index("beds") < roles.index("library") < roles.index("placement") < roles.index("atlas")


def test_area_only_modelled_bed_reaches_atlas(text):  # R1: PR #237 round 1 P1, dry-walk pos. 10
    state = procedure_walk(text)
    bed = {"Iris hybrida", "Hosta glauca", "Geranium perenne"}
    assert bed <= set(state["scene"]) and bed <= state["atlas"] and bed <= state["resolved"]
    assert {"Acer platanoides", "Hydrangea arborescens"} <= state["atlas"]  # point plants preserved
    assert state["atlases"] == 1
    assert walk_findings(text) == []


def test_texture_only_beds_and_lawns_stay_ground(text):  # R1 edge: no Flora tile for texture rows
    state = procedure_walk(text)
    assert sorted(state["ground"]) == [11, 90]
    assert state["atlas"] == {"Acer platanoides", "Hydrangea arborescens", "Iris hybrida", "Hosta glauca",
                              "Geranium perenne"}


def test_walk_rejects_beds_after_atlas(text):  # R1 negative control: the round-1 order
    steps = _steps(text)
    block = {n: f"### Step {n} — {title}{body}" for n, title, body in steps}
    beds = next(n for n, t, _ in steps if _role(t) == "beds")
    atlas = next(n for n, t, _ in steps if _role(t) == "atlas")
    late = text.replace(block[beds], "").replace(block[atlas], block[atlas] + block[beds])
    assert any("no atlas tile" in f or "never reaches" in f for f in walk_findings(late))


def test_walk_empty_schedule():  # edge: empty input
    assert procedure_walk(SKILL.read_text(encoding="utf-8"), [])["atlas"] == set()


def test_every_step_has_route_needs_done(text):  # A4
    for n, _, body in _steps(text):
        assert re.search(r"^- Route: ", body, re.M), n
        assert re.search(r"^- Needs: (headless|live|human)", body, re.M), n
        assert re.search(r"^- Done when: ", body, re.M), n


def test_texture_review_step_needs_the_user(text):  # A5
    body = next(b for _, t, b in _steps(text) if "new species" in t.lower())
    assert re.search(r"^- Needs: human \(texture review", body, re.M)


def test_empty_input_rejected():  # E4
    found = skill_findings("")
    assert any(f.startswith("frontmatter") for f in found)
    assert any(f.startswith("steps:") for f in found)
    assert any(f.startswith("link:") for f in found)


def _mutations(text: str):
    steps = _steps(text)
    block = {n: f"### Step {n} — {title}{body}" for n, title, body in steps}
    for n in block:  # drop each step
        yield f"drop step {n}", text.replace(block[n], "")
    for (a, *_), (b, *_) in zip(steps, steps[1:]):  # swap neighbours
        yield f"swap {a}/{b}", text.replace(block[a] + block[b], block[b] + block[a])
    for n, title, body in steps:  # remove route / needs / done-when per step; bogus needs
        for prefix in ("- Route: ", "- Needs: ", "- Done when: "):
            line = next(ln for ln in body.splitlines() if ln.startswith(prefix))
            yield f"step {n} no {prefix.strip()}", text.replace(block[n], block[n].replace(line, ""))
        need = next(ln for ln in body.splitlines() if ln.startswith("- Needs: "))
        yield f"step {n} bogus needs", text.replace(block[n], block[n].replace(need, "- Needs: maybe"))
        if n in HUMAN_STEPS:
            yield f"step {n} needs without human", text.replace(
                block[n], block[n].replace(need, "- Needs: headless"))
    for n, tokens in STEP_TOKENS.items():  # remove each required token from its step
        for token in tokens:
            yield f"step {n} lacks {token}", text.replace(block[n], block[n].replace(token, "X"))
    for n, words in STEPS:  # remove each heading word
        title = next(t for k, t, _ in steps if k == n)
        for word in words:
            low = title.lower().find(word)
            yield f"step {n} heading lacks {word}", text.replace(
                f"### Step {n} — {title}", f"### Step {n} — {title[:low]}X{title[low + len(word):]}")
    beds = next(n for n, t, _ in steps if _role(t) == "beds")
    atlas = next(n for n, t, _ in steps if _role(t) == "atlas")
    yield "beds moved after atlas", text.replace(block[beds], "").replace(block[atlas], block[atlas] + block[beds])
    place = next(n for n, t, _ in steps if _role(t) == "placement")
    yield "placement without bed scatter", text.replace(block[place], block[place].replace("scatter", "X"))
    yield "broken link", text.replace("docs/domain/areas/flora.md)", "docs/domain/areas/floras.md)", 1)
    yield "broken anchor", text.replace("#project-practice", "#project-practise")
    yield "unknown decision", text.replace("[D099]", "[D9099]", 1)
    yield "unknown conflict", text.replace("C18", "C918", 1)
    yield "unknown sheet row", text.replace("FLO-04", "FLO-94", 1)
    yield "no pipeline link", text.replace("pipeline-flora-textures.md", "pipeline.md")
    sheet = SHEET.read_text(encoding="utf-8")
    for i, row in enumerate(ln for ln in sheet.splitlines() if ln.startswith("| FLO-")):  # paste longest rule cell
        cell = max(row.split(" | ")[2:5], key=len)  # NPM, VPM, how checked; cells < 8 words are below the shingle
        yield f"copied FLO row {i + 1}", text + "\n" + cell + "\n"
    practice = sheet.split("## Project practice", 1)[1].split("\n## ", 1)[0]
    for i, bullet in enumerate(b for b in practice.split("\n- ") if b.startswith("**")):  # paste each bullet
        yield f"copied practice bullet {i + 1}", text + "\n- " + bullet + "\n"
    for d in ("D099", "D100", "D101", "D102"):  # paste each Flora decision's text cell
        line = next(ln for ln in DECISIONS.read_text(encoding="utf-8").splitlines() if ln.startswith(f"| {d} "))
        yield f"copied {d}", text + "\n" + line.split(" | ")[2] + "\n"
    yield "copied quote", text + "\n«для благоустройства, его элементов и элементов растительности в сумме»\n"


def test_generated_mutations_are_rejected(text):  # E1-E5, probe
    mutations = list(_mutations(text))
    unchanged = [name for name, mutated in mutations if mutated == text]
    missed = [name for name, mutated in mutations if mutated != text and not skill_findings(mutated)]
    assert not unchanged, unchanged
    assert not missed, f"{len(missed)}/{len(mutations)} mutations passed: {missed}"
    assert len(mutations) >= 120
