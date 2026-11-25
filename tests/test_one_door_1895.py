"""One door (#1895): AGENTS.md -> SKELETONS index -> cell block -> trail; truth on the first page.

Pattern: n/a | new-case: regression probes for the hygiene batch-3 entry (cell block, door measure, trail text).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.architecture import skeleton_guard as sg  # noqa: E402
from tools.state import entry_budget as eb  # noqa: E402

SK = sg.load_skeletons(ROOT)
FALSE_GAPS = {"brick-seams": "agr brick-seams", "ucx-ground": "agr ucx", "ucx-oks": "agr ucx", "maf-light": "agr npm-light",
              "ground-textures": "agr ground site", "relief": "agr ground site"}


def _text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# --- false gaps (PLAN-ru §4.2) ------------------------------------------------------------------------------------

@pytest.mark.parametrize("sid,cmd", sorted(FALSE_GAPS.items()))
def test_former_false_gap_now_calls_the_served_command(sid, cmd):
    st = SK["stages"][sid]
    assert st["gap"] is None and st["calls"].startswith(cmd), st
    gaps = _text("docs/agents/SKELETONS.md").split("## Пробелы", 1)[1]
    assert f"`{sid}`" not in gaps


def test_zero_stays_a_gap_but_names_the_verifier():
    gap = SK["stages"]["zero"]["gap"]
    assert "`agr zero`" in gap and "verifies" in gap and "[D279]" in gap


# --- cell block ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cell", sorted(SK["cells"]))
def test_cell_block_lists_trail_and_every_stage_once(cell):
    block = sg.cell_block(ROOT, SK, cell)
    spec = SK["cells"][cell]
    assert f"trail: {spec['trail']}" in block and (ROOT / spec["trail"]).is_file()
    lines = [ln for ln in block.splitlines() if re.match(r"^\s*\d+\. ", ln)]
    assert [ln.split(". ", 1)[1].split(" - ", 1)[0] for ln in lines] == spec["stages"]
    for ln, sid in zip(lines, spec["stages"]):
        assert ("GAP:" in ln) == (SK["stages"][sid]["gap"] is not None), ln


@pytest.mark.parametrize("trail", [None, "", "   ", "routes/nope.md", "../outside.md", "routes"])
def test_cell_block_fails_closed_on_a_bad_trail(tmp_path, trail):
    (tmp_path / "docs/agents").mkdir(parents=True)
    (tmp_path / "routes").mkdir()
    data = json.loads(_text(sg.SKELETONS))
    if trail is None:
        data["cells"]["oks-npm"].pop("trail")
    else:
        data["cells"]["oks-npm"]["trail"] = trail
    (tmp_path / sg.SKELETONS).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(sg.ConfigError, match="oks-npm"):
        sg.cell_block(tmp_path, sg.load_skeletons(tmp_path), "oks-npm")


@pytest.mark.parametrize("cell", ["", "OKS-NPM", "oks-npm ", "nope", None])
def test_cell_block_unknown_cell_is_an_error_naming_it(cell):
    with pytest.raises(sg.ConfigError, match="unknown cell"):
        sg.cell_block(ROOT, SK, cell)


def test_show_cli_fresh_process():
    import subprocess
    ok = subprocess.run([sys.executable, "tools/architecture/skeleton_guard.py", "--show", "ground-npm"], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8")
    assert ok.returncode == 0 and "trail: routes/site.md" in ok.stdout
    bad = subprocess.run([sys.executable, "tools/architecture/skeleton_guard.py", "--show", "nope"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2 and "unknown cell" in bad.stderr and bad.stdout == ""


# --- door measure -------------------------------------------------------------------------------------------------

def _counter(text):
    return len(text) // 4 + 1


def test_door_path_order_and_drop_against_the_1886_path():
    for tid in eb.targets(ROOT):
        cell, _, stage = tid.partition(":")
        labels = [label for label, _ in eb.door_path(ROOT, cell, stage or None)]
        assert labels[:3] == ["AGENTS.md", "docs/agents/SKELETONS.md", f"skeleton_guard.py --show {cell}"], tid
        assert eb.DOOR_INTAKE in labels and SK["cells"][cell]["trail"] in labels, tid
        assert len(labels) == len(set(labels)), tid
        legacy = sum(_counter(_text(f)) for f in eb.cell_path(ROOT, cell, stage or None)["files"])
        door = sum(_counter(t) for _, t in eb.door_path(ROOT, cell, stage or None))
        assert door < legacy / 3, (tid, door, legacy)


@pytest.mark.parametrize("cell,stage,needle", [("nope", None, "unknown cell"), ("ground-npm", None, "stage required"),
                                               ("ground-npm", "roof", "names no skill"), ("oks-npm", "maf", "names no skill")])
def test_door_path_fails_closed(cell, stage, needle):
    with pytest.raises(eb.FailClosed, match=needle):
        eb.door_path(ROOT, cell, stage)


def test_door_on_a_tree_without_cell_block_fails_closed(tmp_path):
    for rel in ("docs/scenarios/scenarios.json", sg.SKELETONS, "tools/architecture/skeleton_guard.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    guard = tmp_path / "tools/architecture/skeleton_guard.py"
    guard.write_text(guard.read_text(encoding="utf-8").replace("def cell_block(", "def _old_block("), encoding="utf-8")
    with pytest.raises(eb.FailClosed, match="no cell_block"):
        eb.door_path(tmp_path, "oks-npm")


def test_door_output_onto_an_input_is_refused_and_writes_nothing(tmp_path):
    before = _text("AGENTS.md")
    with pytest.raises(eb.FailClosed, match="output path is an input"):
        eb.write_door(ROOT, ROOT / "AGENTS.md", _counter, "0" * 40)
    assert _text("AGENTS.md") == before and not (ROOT / "AGENTS.md.partial").exists()
    with pytest.raises(eb.FailClosed, match="40-hex"):
        eb.write_door(ROOT, tmp_path / "out.json", _counter, "abc")
    assert not (tmp_path / "out.json").exists()


def test_door_cli_needs_cells_and_no_walkers(tmp_path):
    assert eb.main(["--check", "--door"]) == 2
    assert eb.main(["--cells", "--door", "--walkers", str(tmp_path), "--output", str(tmp_path / "o.json")]) == 2


# --- first-page text ----------------------------------------------------------------------------------------------

def test_agents_md_one_door_and_frozen_agr_tools():
    text = _text("AGENTS.md")
    head = text.split("## Goal", 1)[0]
    for must in ("docs/agents/SKELETONS.md", "--show <cell>", "routes/npm-oks.md", "routes/site.md", "[D397]"):
        assert must in head, must
    assert "[D393]" in text and "[D394]" in text and "agr-tools-1.0-rules.md" not in text
    assert len(text.splitlines()) <= 85


def test_no_old_body_route_on_the_oks_trail():
    route = _text("routes/npm-oks.md")
    card = _text("docs/scenarios/oks-vpm.md").split("## Route by stage", 1)[1].split("## Etalons", 1)[0]
    index = _text("docs/agents/SKELETONS.md")
    for doc in (route, card, index):
        assert "[D373]" in doc and "agr body" in doc
        assert "AGR Tools stages 1–4" not in doc and "no universal `agr build`" not in doc
    assert "is permitted only as\n`path: deviation` [D250]" not in card


def test_passport_first():
    intake = _text("docs/agents/task-intake.md")
    assert intake.index("**Passport first** [D397]") < intake.index("1. Read the sources")
    entry = _text("routes/npm-oks.md").split("## Entry", 1)[1].split("\n", 1)[1]
    assert entry.lstrip().startswith("Passport first")
    assert "D247 permits" not in _text("routes/npm-oks.md")


def test_no_stale_pointers_on_live_trails():
    stale = re.compile(r"will publish|until merged|recipes? (are )?still to be published", re.I)
    trails = ["AGENTS.md", "docs/agents/SKELETONS.md", *[p.relative_to(ROOT).as_posix() for p in
              [*(ROOT / "routes").glob("*.md"), *(ROOT / "docs/scenarios").glob("*.md")]]]
    assert [t for t in trails if stale.search(_text(t))] == []
    assert "docs/procedure/NODE_RECIPES.md" in _text("routes/npm-oks.md")


@pytest.mark.parametrize("rel", ["jobs/elv-tc-vpm/TASK.md", "jobs/elv-tc-vpm/PASSPORT.md", "jobs/elv-tc-vpm/passport.json",
                                 "jobs/REGISTRY.md", "docs/scenarios/oks-vpm.md", "docs/cases.md", "docs/pipeline.md"])
def test_elv_marked_not_delivered(rel):
    assert "geometry accepted, not delivered [#1441]" in _text(rel)


LIVE_IMPORTS_RULE = (
    "Before hiding or archiving a `jobs/` path, run `uv run pytest -q tests/test_live_route_imports.py`. "
    "The fresh-process runtime guard must show no live route loads Python from that path; if the affected "
    "route is not covered, add its runtime import probe first. Static search and duplicate checks alone do "
    "not prove that lazy or path-based imports are gone. Explicit job data inputs are not Python dependencies.")


def test_live_route_imports_rule_survives_the_move():
    """r1 P1-1: the hide/archive rule from the old SKELETONS.md is kept verbatim on the index or stage file."""
    flat = " ".join(re.sub(r"\s+", " ", _text(rel)) for rel in
                    ("docs/agents/SKELETONS.md", "docs/agents/SKELETONS-stages.md"))
    assert LIVE_IMPORTS_RULE in flat
    assert (ROOT / "tests/test_live_route_imports.py").is_file()


def test_psu275_is_not_a_body_etalon():
    row = next(ln for ln in _text("docs/cases.md").splitlines() if ln.startswith("| PSU275"))
    assert "before the lattice method [D373]" in row


def test_committed_after_fixtures_are_consistent():
    base = json.loads(_text("tests/fixtures/cold_entry/cells_baseline.json"))["targets"]
    for name in ("door_after_1895.json", "cells_after_1895.json"):
        data = json.loads(_text(f"tests/fixtures/cold_entry/{name}"))
        assert re.fullmatch(r"[0-9a-f]{40}", data["measured_on"]) and set(data["targets"]) == set(base), name
        for tid, t in data["targets"].items():
            assert t["total_tokens"] == sum(f["tokens"] for f in t["files"]) > 0, (name, tid)
            assert t["total_tokens"] < base[tid]["total_tokens"], (name, tid)
