"""Per-cell entry path to the first command and its baseline (#1886).

new-case: tests for ``entry_budget.py --cells`` (scenario-cell entry paths, walker coverage).
"""
import importlib.util
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "state" / "entry_budget.py"
BASELINE = ROOT / "tests" / "fixtures" / "cold_entry" / "cells_baseline.json"


def _eb():
    spec = importlib.util.spec_from_file_location("entry_budget_cells", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


eb = _eb()


def count(text):
    return max(1, len(text) // 4)


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(root, cells=None, card_text=None):
    """A minimal repository with the common entry files and one ground cell."""
    for rel in eb.COMMON:
        _write(root, rel, f"# {rel}\nbody text\n")
    for skill in eb.STAGE_SKILLS.values():
        _write(root, skill, "# skill\n")
    _write(root, "routes/npm-oks.md", "# route\n## Entry\nread [body](../docs/domain/areas/body.md)\n")
    _write(root, "docs/domain/areas/body.md", "# body\n")
    _write(root, "docs/domain/areas/flora.md", "# flora\n")
    _write(root, "docs/domain/req.md", "# req\n")
    _write(root, "docs/scenarios/ground-npm.md", card_text if card_text is not None else (
        "# card\n\n## Read first (in order)\n\n"
        "1. [req](../domain/req.md#lp) section.\n"
        "2. Ground -> `.agents/skills/model-ground/SKILL.md`, MAF -> `.agents/skills/model-maf/SKILL.md`,\n"
        "   Flora -> `.agents/skills/model-flora/SKILL.md`.\n"
        "3. [flora](../domain/areas/flora.md), etalon `jobs/<ID>/TASK.md`, GeoAGR `C:\\x\\Geo\\README.md`,\n"
        "   [web](https://example.com/x), [gone](../domain/areas/gone.md).\n\n"
        "## Rules\n\n[not read](../domain/areas/body.md)\n"))
    cells = cells if cells is not None else [
        {"id": "ground-npm", "status": "ready", "card": "docs/scenarios/ground-npm.md",
         "reads": ["docs/domain/areas/flora.md"]},
        {"id": "oks-npm", "status": "ready", "card": "routes/npm-oks.md", "reads": ["docs/domain/req.md"]},
        {"id": "oks-npm-lite", "status": "todo", "card": None, "reads": ["docs/domain/req.md"]},
    ]
    _write(root, "docs/scenarios/scenarios.json", json.dumps({"cells": cells}))
    return root


# --- path derivation ---------------------------------------------------------------

def test_common_prefix_card_reads_and_read_first_in_order(tmp_path):
    root = _repo(tmp_path)
    path = eb.cell_path(root, "ground-npm", "maf")
    files = path["files"]
    assert files[:len(eb.COMMON)] == list(eb.COMMON)
    tail = files[len(eb.COMMON):]
    assert tail == ["docs/scenarios/ground-npm.md", "docs/domain/areas/flora.md", "docs/domain/req.md",
                    ".agents/skills/model-maf/SKILL.md"]
    assert len(files) == len(set(files))


def test_stage_variant_keeps_only_its_skill(tmp_path):
    root = _repo(tmp_path)
    for stage, skill in eb.STAGE_SKILLS.items():
        files = eb.cell_path(root, "ground-npm", stage)["files"]
        assert skill in files
        assert [s for s in eb.STAGE_SKILLS.values() if s in files] == [skill]


def test_rules_section_links_are_not_followed(tmp_path):
    root = _repo(tmp_path)
    assert "docs/domain/areas/body.md" not in eb.cell_path(root, "ground-npm", "ground")["files"]


def test_unfollowable_refs_are_listed_with_reasons(tmp_path):
    root = _repo(tmp_path)
    reasons = {u["ref"]: u["reason"] for u in eb.cell_path(root, "ground-npm", "ground")["unfollowed"]}
    assert reasons["jobs/<ID>/TASK.md"] == "placeholder"
    assert reasons["C:\\x\\Geo\\README.md"] == "outside repo"
    assert reasons["https://example.com/x"] == "url"
    assert reasons["../domain/areas/gone.md"] == "missing"


def test_npm_oks_cells_add_the_route_and_follow_its_entry_section(tmp_path):
    root = _repo(tmp_path)
    lite = eb.cell_path(root, "oks-npm-lite")["files"]
    assert "routes/npm-oks.md" in lite and "docs/domain/areas/body.md" in lite
    npm = eb.cell_path(root, "oks-npm")["files"]
    assert npm.count("routes/npm-oks.md") == 1 and "docs/domain/areas/body.md" in npm


def test_todo_cell_without_card_uses_reads(tmp_path):
    root = _repo(tmp_path)
    path = eb.cell_path(root, "oks-npm-lite")
    assert "docs/domain/req.md" in path["files"]
    assert {"ref": None, "from": "docs/scenarios/scenarios.json", "reason": "cell has no card"} in path["unfollowed"]


def test_card_without_read_first_section_is_reported(tmp_path):
    root = _repo(tmp_path, card_text="# card\n\n## Rules\n\n[x](../domain/req.md)\n")
    path = eb.cell_path(root, "ground-npm")
    assert "docs/domain/req.md" not in path["files"]
    assert any(u["reason"] == "card has no Read first / Entry section" for u in path["unfollowed"])


@pytest.mark.parametrize("cell,stage,word", [
    ("nope", None, "unknown cell: nope"),
    ("ground-npm", "roof", "unknown stage"),
    ("ground-npm", None, "stage required"),
    ("oks-npm", "maf", "names no skill for stage maf"),
])
def test_bad_target_fails_closed(tmp_path, cell, stage, word):
    root = _repo(tmp_path)
    with pytest.raises(eb.FailClosed, match=word):
        eb.cell_path(root, cell, stage)


@pytest.mark.parametrize("cells,word", [
    ([], "no cells"),
    ([{"id": "x", "status": "ready", "card": "docs/missing.md", "reads": []}], "partial"),
    ([{"id": "x", "status": "ready", "card": None, "reads": ["../outside.md"]}], "outside the repository"),
    ([{"id": "x", "status": "ready", "card": None, "reads": ["docs/gone.md"]}], "partial"),
    ([{"id": "x", "card": None, "reads": []}, {"id": "x", "card": None, "reads": []}], "duplicate cell"),
])
def test_bad_scenarios_fail_closed(tmp_path, cells, word):
    root = _repo(tmp_path, cells=cells)
    with pytest.raises(eb.FailClosed, match=word):
        eb.cell_path(root, "x")


def test_empty_entry_file_on_the_path_fails_closed(tmp_path):
    root = _repo(tmp_path)
    (root / "docs/domain/areas/flora.md").write_text("  \n", encoding="utf-8")
    with pytest.raises(eb.FailClosed, match="empty entry file"):
        eb.measure_cells(root, count, "a" * 40)


# --- walker coverage --------------------------------------------------------------

def _walker(rows):
    return {"items": rows}


def test_walker_docs_normalised_and_classified(tmp_path):
    root = _repo(tmp_path)
    path = eb.cell_path(root, "ground-npm", "maf")["files"]
    rows = [
        {"status": "ready", "docs_read": [{"path": "AGENTS.md", "approx_tokens": 1}, "docs/domain/req.md (~2k)",
                                          "docs/domain/areas/body.md#x", "docs/domain/areas/flora.md:12",
                                          "G:/drive/x.md", "docs/none.md", ""]},
        {"status": "contradictory", "subtask": "a", "docs_read": ["AGENTS.md"]},
        {"status": "contradictory", "subtask": "b", "docs_read": ["docs/domain/areas/body.md"]},
    ]
    rep = eb.walker_report(_walker(rows), path, root)
    assert rep["on_path"] == ["AGENTS.md", "docs/domain/areas/flora.md", "docs/domain/req.md"]
    assert rep["beyond_path"] == ["docs/domain/areas/body.md"]
    assert rep["outside_repo"] == ["G:/drive/x.md"]
    assert rep["missing"] == ["docs/none.md"]
    assert rep["unparsed"] == 1
    assert rep["contradictory_rows"] == 2 and rep["contradictory_on_path"] == 1
    # every read entry ends in exactly one bucket
    buckets = rep["on_path"] + rep["beyond_path"] + rep["outside_repo"] + rep["missing"]
    assert len(buckets) == len(set(buckets)) == 6


def test_walker_without_docs_read_fails_closed(tmp_path):
    root = _repo(tmp_path)
    with pytest.raises(eb.FailClosed, match="no docs_read"):
        eb.walker_report({"items": [{"status": "ready"}]}, ["AGENTS.md"], root)


def test_unmapped_or_missing_walker_file_fails_closed(tmp_path):
    root = _repo(tmp_path)
    walkers = tmp_path / "walkers"
    walkers.mkdir()
    (walkers / "w99-new.json").write_text(json.dumps(_walker([{"docs_read": ["AGENTS.md"]}])), encoding="utf-8")
    with pytest.raises(eb.FailClosed, match="unmapped walker: w99-new"):
        eb.load_walkers(walkers)
    (walkers / "w99-new.json").unlink()
    with pytest.raises(eb.FailClosed, match="partial: walker missing"):
        eb.load_walkers(walkers)


def test_walker_with_alternate_form_status_is_not_counted_contradictory(tmp_path):
    root = _repo(tmp_path)
    rows = [{"status": "Contradictory?", "docs_read": ["AGENTS.md"]},
            {"status": "contradictory", "docs_read": ["AGENTS.md"]}]
    rep = eb.walker_report(_walker(rows), ["AGENTS.md"], root)
    assert rep["contradictory_rows"] == 1
    assert rep["unknown_status"] == ["Contradictory?"]


# --- measurement and CLI --------------------------------------------------------------

def test_measure_cells_totals_and_targets(tmp_path):
    root = _repo(tmp_path)
    data = eb.measure_cells(root, count, "b" * 40)
    assert data["measured_on"] == "b" * 40 and data["tokenizer"] == eb.TOKENIZER
    assert set(data["targets"]) == {"ground-npm:ground", "ground-npm:maf", "ground-npm:flora", "oks-npm",
                                    "oks-npm-lite"}
    for target in data["targets"].values():
        assert target["total_tokens"] == sum(f["tokens"] for f in target["files"])
        assert target["files_count"] == len(target["files"])


@pytest.mark.parametrize("sha", ["", "abc", "g" * 40, None])
def test_bad_commit_fails_closed(tmp_path, sha):
    with pytest.raises(eb.FailClosed, match="commit"):
        eb.measure_cells(_repo(tmp_path), count, sha)


def test_output_onto_an_input_is_refused_and_writes_nothing(tmp_path):
    root = _repo(tmp_path)
    target = root / "docs/scenarios/scenarios.json"
    before = target.read_bytes()
    with pytest.raises(eb.FailClosed, match="output path is an input"):
        eb.write_cells(root, target, count, "c" * 40)
    assert target.read_bytes() == before
    assert not target.with_name(target.name + ".partial").exists()


def test_cli_cells_fresh_process_needs_output(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--cells", "--root", str(_repo(tmp_path))],
                          capture_output=True, text=True)
    assert proc.returncode != 0 and "--output" in proc.stderr


def test_generated_cells_never_duplicate_or_escape(tmp_path):
    rng = random.Random(1886)
    root = _repo(tmp_path)
    pool = ["docs/domain/req.md", "docs/domain/areas/flora.md", "docs/domain/areas/body.md", "AGENTS.md"]
    for i in range(40):
        reads = [rng.choice(pool) for _ in range(rng.randint(0, 6))]
        _write(root, "docs/scenarios/scenarios.json", json.dumps({"cells": [
            {"id": "c", "status": "todo", "card": None, "reads": reads}]}))
        files = eb.cell_path(root, "c")["files"]
        assert len(files) == len(set(files))
        assert set(reads) <= set(files)
        assert all(not f.startswith("..") for f in files)


# --- live repository and committed baseline ----------------------------------------------

def test_every_live_cell_resolves():
    scen = json.loads((ROOT / "docs/scenarios/scenarios.json").read_text(encoding="utf-8"))
    targets = eb.targets(ROOT)
    assert {t.split(":")[0] for t in targets} == {c["id"] for c in scen["cells"]}
    for tid in targets:
        cell, _, stage = tid.partition(":")
        assert eb.cell_path(ROOT, cell, stage or None)["files"][:2] == ["AGENTS.md", "docs/PROJECT_STATE.md"]


def test_committed_baseline_is_consistent():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert data["schema"] == 1 and data["kind"] == "entry_budget_cells"
    assert re.fullmatch(r"[0-9a-f]{40}", data["measured_on"])
    assert data["tokenizer"] == eb.TOKENIZER
    assert set(data["targets"]) == set(eb.targets(ROOT))
    for tid, target in data["targets"].items():
        assert target["total_tokens"] == sum(f["tokens"] for f in target["files"]), tid
        assert all(f["tokens"] > 0 for f in target["files"])
    covered = {t for w in data["walkers"].values() for t in w["targets"]}
    assert covered == set(data["targets"])
