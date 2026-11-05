"""Cold-entry token budget and curated PROJECT_STATE milestones (#1015).

new-case: offline guard for the cold-entry read set measured with tiktoken o200k_base.
"""
import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUDGET_SCRIPT = ROOT / "tools" / "state" / "entry_budget.py"
STATE_SCRIPT = ROOT / "tools" / "state" / "project_state.py"
RECEIPT = ROOT / "tests" / "fixtures" / "cold_entry" / "receipt.json"
CARD = "tests/fixtures/cold_entry/card-t_9e27c5ff.md"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _budget():
    assert BUDGET_SCRIPT.is_file(), "tools/state/entry_budget.py is missing"
    return _load(BUDGET_SCRIPT, "entry_budget")


def _state():
    return _load(STATE_SCRIPT, "project_state_entry")


def _receipt(files, budget=10_000):
    return {
        "schema": 1,
        "tokenizer": "tiktoken o200k_base",
        "budget": budget,
        "card": "synthetic",
        "files": files,
        "total_tokens": sum(row["tokens"] for row in files),
    }


def _tree(tmp_path, sizes, tokens):
    """Synthetic repo: AGENTS.md, docs/PROJECT_STATE.md and extras with given char sizes."""
    names = ["AGENTS.md", "docs/PROJECT_STATE.md"] + [f"docs/extra{i}.md" for i in range(len(sizes) - 2)]
    files = []
    for name, size, count in zip(names, sizes, tokens):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        files.append({"path": name, "chars": size, "tokens": count})
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(_receipt(files)), encoding="utf-8")
    return receipt


# --- acceptance: the live cold-entry set of the real card fits the budget -------------------------

def test_live_cold_entry_set_is_within_10k_tokens():
    module = _budget()
    rows, total = module.check(ROOT, RECEIPT)
    paths = [row["path"] for row in rows]
    assert paths[:2] == ["AGENTS.md", "docs/PROJECT_STATE.md"]
    assert CARD in paths
    assert "docs/domain/areas/derivation.md" in paths
    print("cold entry (tiktoken o200k_base, live estimate):",
          ", ".join(f"{row['path']}={row['estimate']}" for row in rows), "total", total)
    assert 0 < total <= 10_000


def test_receipt_names_the_tokenizer_and_a_real_card():
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert data["tokenizer"] == "tiktoken o200k_base"
    assert data["budget"] == 10_000
    assert "t_9e27c5ff" in data["card"] and "#968" in data["card"]
    assert data["total_tokens"] == sum(row["tokens"] for row in data["files"]) <= 10_000


def test_cli_check_fresh_process_prints_the_total():
    result = subprocess.run([sys.executable, str(BUDGET_SCRIPT), "--check"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert "total" in result.stdout and "/ 10000" in result.stdout


# --- the guard fails when the entry set grows past the budget --------------------------------------

def test_growth_past_the_budget_fails(tmp_path):
    module = _budget()
    receipt = _tree(tmp_path, [4000, 4000], [5000, 4999])
    assert module.check(tmp_path, receipt)[1] == 9999
    (tmp_path / "AGENTS.md").write_bytes(b"x" * 4001)  # +1 char -> ceil(5000*4001/4000) = 5002
    with pytest.raises(module.FailClosed) as err:
        module.check(tmp_path, receipt)
    assert "over budget" in err.value.reason and "10001" in err.value.reason


def test_exactly_at_budget_passes_one_over_fails(tmp_path):
    module = _budget()
    assert module.check(tmp_path, _tree(tmp_path, [100, 100], [5000, 5000]))[1] == 10_000
    with pytest.raises(module.FailClosed):
        module.check(tmp_path, _tree(tmp_path, [100, 100], [5000, 5001]))


def test_generated_totals_around_the_budget(tmp_path):
    module = _budget()
    rng = random.Random(1015)
    samples = [9_998, 9_999, 10_000, 10_001, 10_002] + [rng.randrange(2, 20_000) for _ in range(40)]
    for index, total in enumerate(samples):
        base = tmp_path / f"s{index}"
        first = rng.randrange(1, total)
        receipt = _tree(base, [50, 70], [first, total - first])
        if total <= 10_000:
            assert module.check(base, receipt)[1] == total
        else:
            with pytest.raises(module.FailClosed):
                module.check(base, receipt)


def test_shrinking_file_scales_down(tmp_path):
    module = _budget()
    receipt = _tree(tmp_path, [1000, 1000], [3000, 3000])
    (tmp_path / "docs" / "PROJECT_STATE.md").write_bytes(b"x" * 500)
    rows, total = module.check(tmp_path, receipt)
    assert total == 4500


def test_large_growth_demands_a_remeasure(tmp_path):
    module = _budget()
    receipt = _tree(tmp_path, [1000, 1000], [100, 100])
    (tmp_path / "AGENTS.md").write_bytes(b"x" * 1251)
    with pytest.raises(module.FailClosed) as err:
        module.check(tmp_path, receipt)
    assert "re-measure" in err.value.reason and "AGENTS.md" in err.value.reason


# --- fail closed on bad receipts and inputs --------------------------------------------------------

@pytest.mark.parametrize("mutate, word", [
    (lambda d: d.update(files=[]), "empty"),
    (lambda d: d.update(schema=2), "unsupported"),
    (lambda d: d.update(tokenizer="chars/4"), "tokenizer"),
    (lambda d: d.update(budget=20_000), "budget"),
    (lambda d: d.update(total_tokens=d["total_tokens"] + 1), "total"),
    (lambda d: d["files"][0].update(tokens=0), "tokens"),
    (lambda d: d["files"][0].update(tokens=True), "tokens"),
    (lambda d: d["files"][0].update(tokens=1.5), "tokens"),
    (lambda d: d["files"][0].update(chars="nan"), "chars"),
    (lambda d: d["files"][0].update(path="../outside.md"), "outside"),
    (lambda d: d["files"].append(dict(d["files"][1])), "duplicate"),
    (lambda d: d["files"].append({"path": "./docs/PROJECT_STATE.md", "chars": 10, "tokens": 1}), "duplicate"),
    (lambda d: d["files"].pop(0), "AGENTS.md"),
    (lambda d: d["files"].append({"path": "docs/missing.md", "chars": 10, "tokens": 1}), "partial"),
    (lambda d: d["files"][0].pop("tokens"), "tokens"),
])
def test_bad_receipt_fails_closed(tmp_path, mutate, word):
    module = _budget()
    receipt = _tree(tmp_path, [100, 100], [10, 10])
    data = json.loads(receipt.read_text(encoding="utf-8"))
    mutate(data)
    if "total_tokens" in data and word != "total":
        data["total_tokens"] = sum(row.get("tokens", 0) for row in data["files"]
                                   if isinstance(row.get("tokens"), int))
    receipt.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(module.FailClosed) as err:
        module.check(tmp_path, receipt)
    assert word in err.value.reason


@pytest.mark.parametrize("raw", ["", "{", "NaN", '{"schema": NaN}', "[]"])
def test_unreadable_receipt_fails_closed(tmp_path, raw):
    module = _budget()
    receipt = tmp_path / "receipt.json"
    receipt.write_text(raw, encoding="utf-8")
    with pytest.raises(module.FailClosed):
        module.check(tmp_path, receipt)
    with pytest.raises(module.FailClosed):
        module.check(tmp_path, tmp_path / "absent.json")


def test_empty_entry_file_fails_closed(tmp_path):
    module = _budget()
    receipt = _tree(tmp_path, [100, 100], [10, 10])
    (tmp_path / "AGENTS.md").write_bytes(b" \r\n")
    with pytest.raises(module.FailClosed) as err:
        module.check(tmp_path, receipt)
    assert "empty" in err.value.reason


def test_write_refuses_a_receipt_path_that_is_an_entry_file(tmp_path):
    module = _budget()
    _tree(tmp_path, [100, 100], [10, 10])
    target = tmp_path / "AGENTS.md"
    before = target.read_bytes()
    with pytest.raises(module.FailClosed):
        module.write_receipt(tmp_path, ["AGENTS.md", "docs/PROJECT_STATE.md"], "synthetic", target,
                             counter=len)
    assert target.read_bytes() == before


def test_write_then_check_round_trip(tmp_path):
    module = _budget()
    _tree(tmp_path, [120, 80], [1, 1])
    out = tmp_path / "out" / "receipt.json"
    data = module.write_receipt(tmp_path, ["AGENTS.md", "docs/PROJECT_STATE.md"], "synthetic", out,
                                counter=len)
    assert data["total_tokens"] == 200
    assert module.check(tmp_path, out)[1] == 200
    assert not list(out.parent.glob("*.partial"))


# --- PROJECT_STATE milestones ----------------------------------------------------------------------

def test_milestones_render_inside_goal_without_a_new_heading(tmp_path):
    module = _state()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PROJECT_STATE.milestones.md").write_text(
        "Ground v015 accepted (#906)\n\nAGR Tools 0.8.0 released (#979)\n", encoding="utf-8")
    lines = module._milestone_lines(tmp_path)
    text = module.render([("abc1234", "Merge pull request #1 from a/b")], [], milestone_lines=lines)
    assert text.index("## Goal") < text.index("Reached so far") < text.index("## In production")
    assert [line for line in text.splitlines() if line.startswith("#")] == [
        "# Project state", "## Goal", "## In production", "## Harness", "## Next step", "## Links"]
    assert "- Ground v015 accepted (#906)" in text
    assert "- AGR Tools 0.8.0 released (#979)" in text


@pytest.mark.parametrize("raw, word", [
    ("", "empty"), (" \n\n", "empty"), ("no reference here\n", "unsupported"),
    ("## heading #1\n", "unsupported"), ("nan\n", "non-finite"),
])
def test_bad_milestones_fail_closed(tmp_path, raw, word):
    module = _state()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PROJECT_STATE.milestones.md").write_text(raw, encoding="utf-8")
    with pytest.raises(module.FailClosed) as err:
        module._milestone_lines(tmp_path)
    assert err.value.reason == word


def test_absent_milestones_render_nothing(tmp_path):
    module = _state()
    assert module._milestone_lines(tmp_path) == []
    text = module.render([("abc1234", "Merge pull request #1 from a/b")], [])
    assert "Reached so far" not in text


def test_milestones_file_is_a_protected_input(tmp_path):
    module = _state()
    assert tmp_path / "docs" / "PROJECT_STATE.milestones.md" in module._inputs(tmp_path)


def test_checked_in_state_names_the_merged_milestones():
    text = (ROOT / "docs" / "PROJECT_STATE.md").read_text(encoding="utf-8")
    section = text.split("Reached so far", 1)[1].split("\n## ", 1)[0]
    for needle in ("Ground v015", "#906", "D193", "AC08", "#891", "#968", "#1006",
                   "0.8.0", "0.9", "#887"):
        assert needle in section, needle
