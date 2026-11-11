"""PROJECT_STATE generator keeps the cold-entry set under the 10k token budget (#1222).

The generator clips long merge subjects and open-PR titles on a fixed width ladder until
``tools/state/entry_budget.py`` passes on the candidate text, keeps all listed rows, and refuses
(writes nothing) when even the narrowest width is over budget. ``after_merge.py --pr N`` runs the
budget check before committing and exits 1 instead of committing an over-budget file.
"""
import importlib.util
import json
import random
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "tools" / "state" / "project_state.py"
BUDGET = ROOT / "tools" / "state" / "entry_budget.py"
AFTER = ROOT / "tools" / "state" / "after_merge.py"
RECEIPT_REL = "tests/fixtures/cold_entry/receipt.json"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ps = _load(STATE, "project_state_budget")
eb = _load(BUDGET, "entry_budget_budget")
am = _load(AFTER, "after_merge_budget")
diet = _load(ROOT / "tests" / "test_context_diet.py", "context_diet_helpers")
WIDTHS = getattr(ps, "TITLE_WIDTHS", (None, 120, 96, 80, 64, 48))


def _merges(count, branch_len):
    rows = []
    for index in range(count):
        number = 2000 - index
        branch = f"artsafro/improve/issue-{number}-" + "x" * branch_len
        rows.append(f"{index + 1:040x}\tMerge pull request #{number} from {branch}")
    return "\n".join(rows) + "\n"


def _opens(count, title_len):
    return json.dumps([{"number": 3000 - index, "title": f"Title {3000 - index} " + "y" * title_len,
                        "headRefName": f"improve/issue-{3000 - index}", "isDraft": index == 0}
                       for index in range(count)])


def _repo(tmp_path, agents_tokens=8800, state_chars=4000, state_tokens=1000, receipt=True):
    """Synthetic repo: AGENTS.md (1000 chars) + PROJECT_STATE (0.25 tokens/char) in the receipt."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / ".git").write_text("gitdir: synthetic\n", encoding="utf-8", newline="\n")
    (repo / "AGENTS.md").write_bytes(b"a" * 1000)
    (repo / "docs" / "PROJECT_STATE.md").write_bytes(b"s" * state_chars)
    if receipt:
        path = repo / RECEIPT_REL
        path.parent.mkdir(parents=True)
        files = [{"path": "AGENTS.md", "chars": 1000, "tokens": agents_tokens},
                 {"path": "docs/PROJECT_STATE.md", "chars": state_chars, "tokens": state_tokens}]
        path.write_text(json.dumps({"schema": 1, "tokenizer": "tiktoken o200k_base", "budget": 10_000,
                                    "card": "synthetic", "files": files,
                                    "total_tokens": sum(r["tokens"] for r in files)}), encoding="utf-8")
    return repo


def _fake_capture(monkeypatch, merges, opens):
    def capture(argv, cwd):
        if argv[:2] == ["git", "log"]:
            return merges
        if argv[:2] == ["git", "remote"]:
            return "https://github.com/fixture/budget.git\n"
        if argv[:3] == ["gh", "pr", "list"]:
            return opens
        raise AssertionError(argv)
    monkeypatch.setattr(ps, "_capture", capture)


def _rows(text):
    merges = re.findall(r"^- `[0-9a-f]{7}` Merge pull request #(\d+) from \S.*$", text, re.M)
    opens = re.findall(r"^- #(\d+) \S.* \[[^\[\]\s]+\]( draft)?$", text, re.M)
    return [int(n) for n in merges], [int(n) for n, _d in opens]


# --- acceptance: long titles at the default 12/12 lists, output passes the budget ----------------

def test_long_titles_over_budget_are_clipped_until_the_budget_passes(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    output = repo / "docs" / "PROJECT_STATE.md"
    _fake_capture(monkeypatch, _merges(12, 160), _opens(12, 160))
    ps.generate(repo, output, 12, 12)
    _rows_checked, total = eb.check(repo, repo / RECEIPT_REL)
    assert total <= eb.BUDGET
    merges, opens = _rows(output.read_text(encoding="utf-8"))
    assert merges == [2000 - i for i in range(12)]  # all 12, newest first
    assert sorted(opens) == sorted(3000 - i for i in range(12))  # all 12 open PR numbers kept
    assert "..." in output.read_text(encoding="utf-8")


def test_unclipped_long_titles_are_over_budget(tmp_path):
    """The fixture really is over budget at full width (guards the acceptance test above)."""
    repo = _repo(tmp_path)
    full = ps.finalize(ps.render(ps.normalize_merges(_merges(12, 160)),
                                 ps.normalize_opens(json.loads(_opens(12, 160)))))
    with pytest.raises(eb.FailClosed) as exc:
        eb.check(repo, repo / RECEIPT_REL, texts={"docs/PROJECT_STATE.md": full})
    assert "over budget" in exc.value.reason or "re-measure" in exc.value.reason


def test_short_titles_are_not_clipped(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    output = repo / "docs" / "PROJECT_STATE.md"
    _fake_capture(monkeypatch, _merges(12, 5), _opens(12, 5))
    text = ps.generate(repo, output, 12, 12)
    assert "..." not in text
    assert eb.check(repo, repo / RECEIPT_REL)[1] <= eb.BUDGET


def test_widest_passing_width_is_chosen(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _fake_capture(monkeypatch, _merges(12, 160), _opens(12, 160))
    text = ps.generate(repo, repo / "docs" / "PROJECT_STATE.md", 12, 12)
    widths = [w for w in WIDTHS if w is not None]
    used = next(w for w in [None, *widths] if ps._budget_reason(
        repo, ps.finalize(ps.render(ps.normalize_merges(_merges(12, 160)),
                                    ps.normalize_opens(json.loads(_opens(12, 160))), width=w))) is None)
    assert text == ps.finalize(ps.render(ps.normalize_merges(_merges(12, 160)),
                                         ps.normalize_opens(json.loads(_opens(12, 160))), width=used))


def test_over_budget_at_the_narrowest_width_refuses_and_writes_nothing(tmp_path, monkeypatch):
    repo = _repo(tmp_path, agents_tokens=9900)  # 100 tokens = 400 chars left: nothing fits
    output = repo / "docs" / "PROJECT_STATE.md"
    before = output.read_bytes()
    _fake_capture(monkeypatch, _merges(12, 160), _opens(12, 160))
    with pytest.raises(ps.FailClosed) as exc:
        ps.generate(repo, output, 12, 12)
    assert "budget" in exc.value.reason
    assert output.read_bytes() == before
    assert not list(output.parent.glob(".*.tmp"))


def test_broken_receipt_refuses_instead_of_skipping(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / RECEIPT_REL).write_text('{"schema": 1, "budget": NaN}', encoding="utf-8")
    output = repo / "docs" / "PROJECT_STATE.md"
    before = output.read_bytes()
    _fake_capture(monkeypatch, _merges(12, 5), _opens(12, 5))
    with pytest.raises(ps.FailClosed):
        ps.generate(repo, output, 12, 12)
    assert output.read_bytes() == before


def test_receipt_is_a_protected_input(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _fake_capture(monkeypatch, _merges(12, 5), _opens(12, 5))
    with pytest.raises(ps.FailClosed) as exc:
        ps.generate(repo, repo / RECEIPT_REL, 12, 12)
    assert exc.value.reason == "output-is-input"


def test_without_a_receipt_no_budget_step_runs(tmp_path, monkeypatch):
    repo = _repo(tmp_path, receipt=False)
    _fake_capture(monkeypatch, _merges(12, 160), _opens(12, 160))
    text = ps.generate(repo, repo / "docs" / "PROJECT_STATE.md", 12, 12)
    assert "..." not in text


@pytest.mark.parametrize("width", WIDTHS[1:])
def test_clipped_rows_still_parse_for_after_merge_and_freshness(width):
    merges = ps.normalize_merges(_merges(12, 300))
    opens = ps.normalize_opens(json.loads(_opens(12, 300)))
    text = ps.render(merges, opens, width=width)
    got_merges, got_opens = _rows(text)
    assert got_merges == [2000 - i for i in range(12)]
    assert sorted(am.listed_open_prs(text)) == sorted(got_opens) == sorted(3000 - i for i in range(12))
    for line in text.splitlines():
        if line.startswith("- `"):
            assert len(line.split("` ", 1)[1]) <= width
        if line.startswith("- #"):
            title = re.match(r"- #\d+ (.*) \[", line).group(1)
            assert len(title) <= width


def test_generated_titles_never_exceed_width_and_keep_the_merge_prefix():
    """Probe: random titles and widths; the clip keeps 'Merge pull request #N from X'."""
    rng = random.Random(1222)
    for _ in range(500):
        width = rng.choice(WIDTHS[1:])
        number = rng.randint(1, 10 ** 6)
        subject = f"Merge pull request #{number} from " + "".join(
            rng.choice("ab/-_ [].") for _ in range(rng.randint(1, 300))).strip() + "z"
        clipped = ps.clip(subject, width)
        assert len(clipped) <= max(width, len(f"Merge pull request #{number} from z..."))
        assert re.match(rf"Merge pull request #{number} from \S", clipped)
        if len(subject) <= width:
            assert clipped == subject


def test_probe_random_title_lengths_pass_or_refuse(tmp_path, monkeypatch):
    """Probe (seed 1222, 80 cases): output within budget with 12/12 rows, or refused and nothing written."""
    rng = random.Random(1222)
    outcomes = {"pass": 0, "refuse": 0}
    for case in range(80):
        repo = _repo(tmp_path / f"c{case}", agents_tokens=rng.choice([8600, 8800, 9000, 9300, 9900]))
        output = repo / "docs" / "PROJECT_STATE.md"
        before = output.read_bytes()
        _fake_capture(monkeypatch, _merges(12, rng.randint(1, 400)), _opens(12, rng.randint(1, 400)))
        try:
            text = ps.generate(repo, output, 12, 12)
        except ps.FailClosed as exc:
            assert "budget" in exc.reason and output.read_bytes() == before
            outcomes["refuse"] += 1
            continue
        assert eb.check(repo, repo / RECEIPT_REL)[1] <= eb.BUDGET
        assert [len(r) for r in _rows(text)] == [12, 12]
        outcomes["pass"] += 1
    assert outcomes["pass"] and outcomes["refuse"]


def test_fresh_process_cli_clips_and_passes_the_budget(tmp_path):
    repo = _repo(tmp_path)
    diet._write_stubs(tmp_path / "bin", _merges(12, 160), _opens(12, 160))
    output = repo / "docs" / "PROJECT_STATE.md"
    code, _out, err = diet._generate(tmp_path, repo, output)
    assert code == 0, err
    assert eb.check(repo, repo / RECEIPT_REL)[1] <= eb.BUDGET


def test_fresh_process_cli_refuses_over_budget_with_exit_1(tmp_path):
    repo = _repo(tmp_path, agents_tokens=9900)
    diet._write_stubs(tmp_path / "bin", _merges(12, 160), _opens(12, 160))
    output = repo / "docs" / "PROJECT_STATE.md"
    before = output.read_bytes()
    code, _out, err = diet._generate(tmp_path, repo, output)
    assert code == 1 and "budget" in err
    assert output.read_bytes() == before


def test_candidate_text_outside_the_entry_set_fails_closed(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(eb.FailClosed) as exc:
        eb.check(repo, repo / RECEIPT_REL, texts={"docs/OTHER.md": "x"})
    assert "outside the entry set" in exc.value.reason
    with pytest.raises(eb.FailClosed):
        eb.check(repo, repo / RECEIPT_REL, texts={"docs/PROJECT_STATE.md": "  \n"})


def test_budget_value_is_unchanged():
    assert eb.BUDGET == 10_000
    assert json.loads((ROOT / RECEIPT_REL).read_text(encoding="utf-8"))["budget"] == 10_000


# --- after_merge.py --pr N: budget check before the commit ---------------------------------------

class BudgetRepo:
    def __init__(self, tmp_path, budget_code):
        self.main = tmp_path / "main"
        (self.main / "docs").mkdir(parents=True)
        self.budget_code = budget_code
        self.calls = []

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        if argv[:3] == ["gh", "pr", "view"]:
            return 0, json.dumps({"state": "MERGED" if argv[3] == "1222" else "OPEN"})
        if argv[:3] == ["git", "worktree", "list"]:
            return 0, f"worktree {self.main}\nHEAD abc\nbranch refs/heads/main\n"
        if argv[:3] == ["git", "status", "--porcelain"]:
            return 0, "" if len(argv) == 3 else " M docs/PROJECT_STATE.md\n"
        if len(argv) > 1 and argv[1] == am.GENERATOR:
            (self.main / am.STATE).write_text("Open pull requests:\n- #7 t [b]\n", encoding="utf-8")
            return 0, ""
        if len(argv) > 1 and argv[1] == am.BUDGET_CHECK:
            return self.budget_code, "total 10010 / 10000 tokens\n"
        return 0, ""


def test_after_merge_refuses_an_over_budget_file_with_exit_1(tmp_path):
    repo = BudgetRepo(tmp_path, budget_code=1)
    code, message = am.refresh(1222, run=repo, cwd=tmp_path, python="py")
    assert code == 1 and "budget" in message
    assert ["py", am.BUDGET_CHECK, "--check"] in repo.calls
    assert not any(a[:2] == ["git", "commit"] for a in repo.calls)
    assert not any(a[:2] == ["git", "add"] for a in repo.calls)
    assert ["git", "checkout", "--", am.STATE] in repo.calls  # the over-budget file is not left behind


def test_after_merge_commits_after_the_budget_check_passes(tmp_path):
    repo = BudgetRepo(tmp_path, budget_code=0)
    code, message = am.refresh(1222, run=repo, cwd=tmp_path, python="py")
    assert code == 0, message
    check = repo.calls.index(["py", am.BUDGET_CHECK, "--check"])
    commit = next(i for i, a in enumerate(repo.calls) if a[:2] == ["git", "commit"])
    assert check < commit


def test_after_merge_cli_exit_1_on_over_budget(tmp_path, monkeypatch, capsys):
    repo = BudgetRepo(tmp_path, budget_code=1)
    monkeypatch.setattr(am, "_run", repo)
    monkeypatch.setattr(am, "ROOT", tmp_path)
    original = am.refresh
    monkeypatch.setattr(am, "refresh", lambda number, commit=True: original(
        number, run=repo, cwd=tmp_path, python="py", commit=commit))
    assert am.main(["--pr", "1222"]) == 1
    assert "budget" in capsys.readouterr().err
