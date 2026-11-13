"""new-case: documentation contract for node recipe coverage and entry links.

These are documentation checks, not model QA or evidence of human acceptance.
"""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCEDURE = "docs/procedure/"
RECIPES = (
    ("node-r1-colouring.md", "fast", ("reference", "material IDs", "readback", "UV", "map paths")),
    ("node-r2-library-maf.md", "standard", ("real size", "material IDs", "normals", "library entry", "UCX")),
    ("node-r3-fence-railing-gates.md", "standard", ("dimensions", "simple joints", "step", "count")),
    ("node-r4-window-glazing.md", "standard", ("openings", "MainGlass", "hidden", "mullion", "exported file")),
    ("node-r5-ground.md", "standard", ("DWG", "joints", "material ID", "overlap", "exported")),
    ("node-r6-oks-body-facade.md", "standard", ("album", "openings", "decor", "joints", "validators", "passed=true")),
    ("node-r7-flora-star-planes.md", "standard", ("species", "transparent", "edge-on", "texel", "upscaling")),
)


def _documents():
    return {path: (ROOT / path).read_text(encoding="utf-8") for path in
            [*(PROCEDURE + name for name, _, _ in RECIPES), PROCEDURE + "NODE_RECIPES.md",
             "AGENTS.md", PROCEDURE + "TASK_TO_MODEL.md"]}


def _check_recipe(text, number, level, clauses):
    assert text.startswith(f"# R{number}. ")
    for clause in (f"**Default level:** `{level}`", "[D273]", "## Steps", "## Definition of done",
                   "deviate if you state why in one line", *clauses):
        assert clause in text, clause
    steps = re.findall(r"^(\d+)\. (.+)$", text, re.M)
    assert len(steps) >= 3
    assert [int(n) for n, _ in steps] == list(range(1, len(steps) + 1))
    for _, step in steps:
        assert re.search(r"\[Source: [^\]]+\]\([^)]+\)", step), step
    assert "TASK_TO_MODEL.md#check-levels" in text
    assert "NODE_RECIPES.md" in text


@pytest.mark.parametrize("number,recipe", list(enumerate(RECIPES, 1)))
def test_recipe_contract(number, recipe):
    name, level, clauses = recipe
    _check_recipe((ROOT / PROCEDURE / name).read_text(encoding="utf-8"), number, level, clauses)


def _local_links(path, text):
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if "://" not in target:
            relative, _, anchor = target.partition("#")
            destination = (ROOT / path).parent / relative if relative else ROOT / path
            assert destination.exists(), (path, target)
            if anchor:
                headings = re.findall(r"^#+ (.+)$", destination.read_text(encoding="utf-8"), re.M)
                slugs = [re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings]
                assert anchor in slugs, (path, target)


def test_entry_routes_resolve():
    documents = _documents()
    index = PROCEDURE + "NODE_RECIPES.md"
    for entry, target in (("AGENTS.md", index), (PROCEDURE + "TASK_TO_MODEL.md", "NODE_RECIPES.md")):
        assert f"]({target})" in documents[entry]
    for name, _, _ in RECIPES:
        assert f"]({name})" in documents[index]
    assert len(re.findall(r"\]\(node-r\d[^)]+\)", documents[index])) == 7
    for path, text in documents.items():
        if path != "AGENTS.md" and path != PROCEDURE + "TASK_TO_MODEL.md":
            _local_links(path, text)


def test_job_local_preferences_excluded():
    documents = _documents()
    body = "\n".join(documents[PROCEDURE + name] for name, _, _ in RECIPES)
    for local in ("20×20", "40 mm rail", "flat base", "reveals separate", "164/171"):
        assert local not in body
    assert "Canopy" not in body
    assert "first canopy job" in documents[PROCEDURE + "NODE_RECIPES.md"]


def test_mutation_probes():
    """Exhaust required-clause omissions, then reset and repeat; synthetic text only."""
    documents = _documents()
    for number, (name, level, clauses) in enumerate(RECIPES, 1):
        text = documents[PROCEDURE + name]
        for missing in (f"**Default level:** `{level}`", "[D273]", "## Steps", "## Definition of done",
                        "deviate if you state why in one line", *clauses):
            with pytest.raises(AssertionError):
                _check_recipe(text.replace(missing, ""), number, level, clauses)
        for invalid in ("", text.split("## Definition of done")[0], text.replace("1. ", "9. ", 1),
                        re.sub(r"\[Source: [^\]]+\]\([^)]+\)", "", text)):
            with pytest.raises(AssertionError):
                _check_recipe(invalid, number, level, clauses)
        for _ in range(2):
            _check_recipe(text, number, level, clauses)
    with pytest.raises(AssertionError):
        _local_links(PROCEDURE + "NODE_RECIPES.md", "[missing](absent-recipe.md)")
    with pytest.raises(AssertionError):
        _local_links(PROCEDURE + "NODE_RECIPES.md", "[missing](TASK_TO_MODEL.md#absent-heading)")
