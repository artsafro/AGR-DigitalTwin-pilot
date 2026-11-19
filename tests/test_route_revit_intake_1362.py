"""#1362: the Revit intake route exists, is linked from every entry point and keeps its contract."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "routes/revit-intake.md"
DRY_RUN = ROOT / "jobs/KPP1/revit-intake-1362/DRY-RUN.md"
ENTRIES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "docs/agents/codex.md"]
SKILLS = [".agents/skills/revit-mcp/SKILL.md", ".claude/skills/revit-mcp/SKILL.md"]


def _local_links(path):
    text = path.read_text(encoding="utf-8")
    return [d for d in re.findall(r"\]\(([^)]+)\)", text) if not d.startswith(("https:", "http:", "#"))]


def test_route_and_dry_run_links_resolve():
    for doc in (ROUTE, DRY_RUN):
        links = _local_links(doc)
        assert links or doc is DRY_RUN, doc
        for dest in links:
            assert (doc.parent / dest.split("#")[0]).exists(), (doc, dest)


def test_route_has_every_specified_step_and_section():
    text = ROUTE.read_text(encoding="utf-8")
    assert re.search(r"[А-Яа-я]{4,}", text.split("## Entry")[0]), "Russian summary at the top"
    for heading in ("## Кратко", "## Route by step", "## Inventory checklist", "## Export rules",
                    "## Done criteria", "## Facts that come from Artem", "## Hot spots", "## Candidate commands"):
        assert heading in text, heading
    for tool in ("revit_exec.py --ping", "get_document_info", "revit-http-2025", "revit-bridge",
                 "export_revit_groups.mjs", "measure_spec_revit_twin.mjs", "revit_twin.py",
                 "revit-ifc-offline-intake", "OBR22_ACCEPTED_WORKFLOW.md", "window_types.json",
                 "extract_openings.py", "node-r6-oks-body-facade.md", "placement-heights-1330.md"):
        assert tool in text, tool
    for item in ("±0.000", "Survey Point", "worksets", "Linked models", "sources.json", "PartsList",
                 "drop list", "feet", "homoglyph", "[D237]", "[D270]", "Blender", "3ds Max"):
        assert item in text, item
    for job in ("KPP1", "OBR22", "TEC26"):
        assert f"| {job}" in text, job


def test_candidate_commands_are_listed_not_implemented():
    text = ROUTE.read_text(encoding="utf-8")
    section = text.split("## Candidate commands")[1]
    names = re.findall(r"^\d+\. `agr ([a-z][a-z-]*)", section, re.M)
    assert names == ["revit-inventory", "revit-export-groups", "source-hash", "revit-twin"]
    agr = (ROOT / "src/dt_ai/cli/agr.py").read_text(encoding="utf-8")
    assert all(f'"{name}"' not in agr for name in names), names
    assert "not implemented" in text.split("## Candidate commands")[0] + section


def test_route_never_licenses_a_model_write():
    text = ROUTE.read_text(encoding="utf-8").lower()
    assert "source is never saved" in text and "modified=false" in text
    assert "never invented" in text and "no save, sync or reload" in text
    for forbidden in ("save over the source", "commit=true", "agr_revit_commit=1"):
        assert forbidden not in text, forbidden


def test_dry_run_is_explicitly_offline_and_read_only():
    text = DRY_RUN.read_text(encoding="utf-8")
    assert "documented dry run from existing evidence, not a live Revit session" in text
    assert "Nothing was opened, saved" in text
    assert len(re.findall(r"\b[0-9a-f]{64}\b", text)) == 2
    caught = [line for line in text.splitlines() if re.match(r"\| \d+ \|", line)]
    assert len(caught) == 9


def test_route_linked_once_from_each_entry_and_the_skill():
    line = "For Revit-source tasks read `routes/revit-intake.md`"
    for entry in ENTRIES:
        text = (ROOT / entry).read_text(encoding="utf-8")
        assert text.count(line) == 1, entry
        assert text.index(line) > text.index("routes/npm-oks.md"), entry
    for skill in SKILLS:
        path = ROOT / skill
        assert "routes/revit-intake.md" in path.read_text(encoding="utf-8"), skill
        assert any((path.parent / d).resolve() == ROUTE.resolve() for d in _local_links(path)), skill
