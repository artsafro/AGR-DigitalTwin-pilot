"""Decision ids (#120, #138).

docs/decisions.md is one dated user decision per row. A mention of a dated user decision carries
`[D<n>]` on the same line, by kind of file: Markdown outside the excluded folders; tracked Python
except under `jobs/`, `technical_library/`, `data/`, `docs/agr/` and this file;
and `standards/material_id_ranges.yaml`. Locked standards YAML is not edited: a top-level
`conflicts:` entry whose note says "decided" must list an `ids` number whose item in
`docs/domain/conflicts.md` carries a `[D<n>]` from the log. JSON, `jobs/**` and frozen fixtures
(`tests/fixtures/` and `evals/*/fixtures/`) are out of scope for Markdown and Python alike.
"""
import datetime
import re
import subprocess
from pathlib import Path

import yaml
import pytest

ROOT = Path(__file__).resolve().parents[1]
LOG = "docs/decisions.md"
ROW = re.compile(r"^\| (D\d{3}) \|")
REF = re.compile(r"\[(D\d{3}(?:, D\d{3})*)\]")
# A dated user decision in prose: "user ... 2026-10-08" or "2026-10-08 ... user" on one line.
MENTION = re.compile(
    r"(user|пользовател|decided|решен|прожарк).{0,40}2026-\d\d-\d\d"
    r"|2026-\d\d-\d\d.{0,25}(user|пользовател|decided|решен)", re.IGNORECASE)
# Out of scope for Markdown: Russian originals (own index), research notes, job files, state and handoff.
EXCLUDED = ("docs/agr/", "docs/research/", "jobs/", "technical_library/", "data/",
            "docs/HANDOFF", "docs/PROJECT_STATE.md", LOG)
# Python stays out of scope under these prefixes, plus this file (the checker's own examples).
PY_EXCLUDED = ("jobs/", "technical_library/", "data/", "docs/agr/", "tests/fixtures/")
# Frozen fixtures carry no id, for Markdown and Python alike.
FROZEN_FIXTURE = re.compile(r"^evals/[^/]+/fixtures/")
CONFLICT_ITEM = re.compile(r"^(\d+)\. ")
# Lines that match MENTION but state no decision: (file, text on the line).
NOT_DECISIONS = [
    ("tests/test_task_to_model.py", '"status": "confirmed", "gate1": {"actor": "synthetic test user", "date": "2026-10-20",'),
    ("tests/test_task_to_model.py", 'receipt.update(decision="approved", actor_role="user", actor="synthetic test user", date="2026-10-20",'),
    ("tests/placement/test_site_job.py", 'e["approved"] = {"by": "user (synthetic)", "date": "2026-10-20"'),
    ("tests/placement/test_site_placement.py", '"approved": {"by": "user", "date": "2026-10-20", "quote": "q"}'),
    ("docs/experiments/flora-library-audit.md", "user Flora grilling notes (2026-10-15)"),
    ("tests/contracts/test_parts_list.py", 'approval = {"actor": "user", "date": "2026-10-18"'),  # synthetic approval fixture, not a decision
    ("docs/backlog.md", "AGR_Project-uncommitted-2026-10-06.zip"),  # an archive name next to "the user plans"
    ("tests/test_ready_gate.py", "(user, 2026-10-14)"),  # a quoted chat fixture line
    ("tests/test_area_requirement_sheet.py", "Decided 2026-10-15 [{record}] (user)"),  # an f-string template asserting the format
]


def is_frozen_fixture(path: str) -> bool:
    """True when the normalized path is under tests/fixtures/ or evals/<one segment>/fixtures/."""
    path = path.replace("\\", "/")
    return path.startswith("tests/fixtures/") or FROZEN_FIXTURE.match(path) is not None


def in_scope(path: str) -> bool:
    """One repo-relative path: Markdown as today, Python except the excluded trees, one standards file.

    Frozen fixtures (`tests/fixtures/` and `evals/*/fixtures/`) are out of scope for Markdown and Python alike.
    """
    path = path.replace("\\", "/")
    if is_frozen_fixture(path):
        return False
    if not path:
        return False
    if path.endswith(".md"):
        return not path.startswith(EXCLUDED)
    if path.endswith(".py"):
        return path != "tests/test_decisions.py" and not path.startswith(PY_EXCLUDED)
    return path == "standards/material_id_ranges.yaml"


def log_rows():
    rows = []
    for line in (ROOT / LOG).read_text(encoding="utf-8").splitlines():
        if line.startswith("| D"):
            assert ROW.match(line), f"malformed decision row: {line[:60]}"
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def scope_files():
    listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert listed.returncode == 0, listed.stderr
    return [f for f in listed.stdout.splitlines() if in_scope(f)]


def unreferenced(files, known_ids):
    problems = []
    for name in files:
        for n, line in enumerate((ROOT / name).read_text(encoding="utf-8").splitlines(), 1):
            if not MENTION.search(line) or any(f == name and t in line for f, t in NOT_DECISIONS):
                continue
            refs = [i for group in REF.findall(line) for i in group.split(", ")]
            if not refs:
                problems.append(f"{name}:{n}: dated user decision without [D<n>]")
            problems += [f"{name}:{n}: unknown {i}" for i in refs if i not in known_ids]
    return problems


def _conflict_decisions(conflicts_md_text):
    """Conflict number -> decision ids carried on its `N. ` item lines."""
    found = {}
    for line in conflicts_md_text.splitlines():
        item = CONFLICT_ITEM.match(line)
        if item:
            found.setdefault(int(item.group(1)), set()).update(
                i for group in REF.findall(line) for i in group.split(", "))
    return found


def _conflict_entries(node, prefix=""):
    """Entries of a conflicts block: a mapping with `ids` and a string `note`, or its nested mappings."""
    if not isinstance(node, dict):
        return
    if "ids" in node and isinstance(node.get("note"), str):
        yield prefix, node
        return
    for key, value in node.items():
        if isinstance(value, dict):
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _conflict_entries(value, child)


def undecided_standards(conflicts_md_text, yaml_texts, known_ids):
    """Locked-YAML rule: a decided conflicts entry must cite a conflict item that carries a known id."""
    carried = _conflict_decisions(conflicts_md_text)
    problems = []
    for name, text in yaml_texts.items():
        data = yaml.safe_load(text) or {}
        block = data.get("conflicts") if isinstance(data, dict) else None
        if not isinstance(block, dict):
            continue
        for path, entry in _conflict_entries(block):
            if "decided" not in entry["note"].lower():
                continue
            ids = entry.get("ids") or []
            if any(d in known_ids for n in ids for d in carried.get(int(n), ())):
                continue
            shown = ", ".join(str(n) for n in ids)
            problems.append(
                f"{name}: conflicts.{path}: decided, but none of conflicts #[{shown}] carries [D<n>]")
    return problems


def log_order_problems(rows):
    """Regular rows are sorted by date; a backfill row (Source `backfill ...`, #138) is exempt but must be no later
    than the regular row before it: it was decided before it was logged. Later regular rows follow as usual."""
    problems = []
    last = None
    for row in rows:
        date = datetime.date.fromisoformat(row[1])
        if row[4].startswith("backfill"):
            if last is not None and date > last:
                problems.append(f"{row[0]}: a backfill row is later than the decision before it")
            continue
        if last is not None and date < last:
            problems.append(f"{row[0]}: regular rows must be sorted by date")
        last = date
    return problems


def test_log_format():
    rows = log_rows()
    assert rows, "no decisions"
    previous_id = 0
    for row in rows:
        assert len(row) == 5 and all(row), row
        current_id = int(row[0][1:])
        assert current_id > previous_id, f"{row[0]}: ids must be unique and increasing (open PRs may reserve gaps)"
        previous_id = current_id
    assert log_order_problems(rows) == []


def test_backfill_rows_rule():
    def row(id_, date, source):
        return [id_, date, "decision", "file", source]

    regular = [row("D001", "2026-10-06", "chat"), row("D002", "2026-10-08", "PR #1")]
    backfill = [row("D003", "2026-10-07", "backfill #138 (a.py; #1)"),
                row("D004", "2026-10-06", "backfill #138 (b.py)")]
    assert log_order_problems(regular + backfill) == []
    assert log_order_problems(regular + [row("D003", "2026-10-05", "chat")]) == [
        "D003: regular rows must be sorted by date"]
    later = row("D005", "2026-10-09", "chat")                    # a new decision after the backfill rows
    assert log_order_problems(regular + backfill + [later]) == []
    assert log_order_problems(regular + backfill + [row("D005", "2026-10-07", "chat")]) == [
        "D005: regular rows must be sorted by date"]
    assert log_order_problems(regular + [row("D003", "2026-10-09", "backfill #138 (c.py)")]) == [
        "D003: a backfill row is later than the decision before it"]
    assert log_order_problems([]) == []


def test_every_dated_decision_carries_its_id():
    known = {row[0] for row in log_rows()}
    assert unreferenced(scope_files(), known) == []


def test_every_decision_is_anchored_where_it_applies():
    anchored = set()
    names = list(dict.fromkeys([*scope_files(), "docs/prd/agent-ready-harness.md"]))
    for name in names:
        for group in REF.findall((ROOT / name).read_text(encoding="utf-8")):
            anchored.update(group.split(", "))
    assert [row[0] for row in log_rows() if row[0] not in anchored] == []


def test_unreferenced_mentions_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__(__name__), "ROOT", tmp_path)
    (tmp_path / "a.md").write_text(
        "Rule (user 2026-10-12): x.\nRule (пользователь 2026-10-12 [D999]).\nOK (user 2026-10-12 [D001]).\n",
        encoding="utf-8")
    problems = unreferenced(["a.md"], {"D001"})
    assert problems == ["a.md:1: dated user decision without [D<n>]", "a.md:2: unknown D999"]


def test_scope_by_kind():
    assert [in_scope(p) for p in [
        "src/dt_ai/spec/mesh.py",
        "tests/qa/test_from_spec.py",
        "tools/git-hooks/pipeline_gate.py",
        ".claude/hooks/subagents.py",
        "standards/material_id_ranges.yaml",
        "docs/domain/geometry.md",
    ]] == [True] * 6
    assert [in_scope(p) for p in [
        "jobs/KPP1/scripts/build_kpp1.py",
        "jobs/KPP1/STATE.md",
        "benchmark/bench-b01-box/etalon.json",
        "schemas/Spec.schema.json",
        "standards/VPM_STANDARD.yaml",
        "tests/fixtures/agent_trace/transcript.jsonl",
        "evals/pr-numeric-literals/fixtures/agr-pr76.diff",
        "tests/test_decisions.py",
        "technical_library/x/y.py",
        "docs/research/a.md",
        "docs/agr/b.py",
        "",
    ]] == [False] * 12


def test_frozen_fixtures_out_of_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__(__name__), "ROOT", tmp_path)
    fixtures = [
        "tests/fixtures/rules.md",
        "evals/example/fixtures/rules.md",
        "evals/example/fixtures/rules.py",
        "tests/fixtures/rules.py",
    ]
    controls = [
        "tests/test_x.py",
        "evals/example/grader.py",
        "evals/example/README.md",
        "evals/fixtures_notes.md",
        "tests/fixturesx/a.py",
        "docs/fixtures/a.md",
    ]
    assert [in_scope(p) for p in fixtures] == [False, False, False, False]
    assert [in_scope(p) for p in controls] == [True, True, True, True, True, True]
    line = "# user 2026-10-12: deliberately untagged synthetic fixture\n"
    for name in fixtures[:3] + ["docs/rules.md"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(line, encoding="utf-8")
    filtered = [p for p in [*fixtures, "docs/rules.md"] if in_scope(p)]
    assert unreferenced(filtered, set()) == ["docs/rules.md:1: dated user decision without [D<n>]"]


def test_historical_backfill_rows_keep_scope():
    rows = {row[0]: row for row in log_rows()}
    for id_ in ("D146", "D147"):
        decision = rows[id_][2]
        assert "from_source" in decision
        assert "D079" in decision
        assert "experimental" in decision
    assert "rejected" in rows["D146"][2]
    assert "from_spec" in rows["D147"][2]
    from twinqa.geometry.checks import check_mesh
    doc = " ".join(check_mesh.__doc__.split())
    assert "[D079]" in doc and "do not authorize skipping topology" in doc


def test_unreferenced_code_mentions_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(__import__(__name__), "ROOT", tmp_path)
    (tmp_path / "a.py").write_text(
        "# user 2026-10-12: x\n"
        '"""Rule (user decision 2026-10-12 [D999])."""\n'
        "X = 1  # user 2026-10-12 [D001]\n"
        "# ids (user 2026-10-12 [D001, D002])\n"
        "y = 2\n",
        encoding="utf-8")
    assert unreferenced(["a.py"], {"D001", "D002"}) == [
        "a.py:1: dated user decision without [D<n>]",
        "a.py:2: unknown D999",
    ]
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    assert unreferenced(["empty.py"], {"D001", "D002"}) == []


def test_standards_decided_conflicts_carry_ids():
    known = {row[0] for row in log_rows()}
    texts = {name: (ROOT / name).read_text(encoding="utf-8") for name in (
        "standards/NPM_STANDARD.yaml", "standards/VPM_STANDARD.yaml", "standards/DELIVERY_VALIDATOR.yaml")}
    assert undecided_standards((ROOT / "docs/domain/conflicts.md").read_text(encoding="utf-8"), texts, known) == []


def test_undecided_standards_fail():
    conflicts = "1. One conflict, decided [D001].\n8. Alpha, still open.\n"
    known = {"D001"}

    def check(body, ids):
        text = "conflicts:\n  " + body + "\n"
        return undecided_standards(conflicts, {"standards/X.yaml": text}, ids)

    assert check("a: {ids: [8], status: noted, note: 'decided 2026-10-07'}", known) == [
        "standards/X.yaml: conflicts.a: decided, but none of conflicts #[8] carries [D<n>]"]
    assert check("b: {ids: [8, 1], note: 'Decided ...'}", known) == []
    assert check("c: {ids: [8], status: review, note: 'open'}", known) == []
    assert check("d: {ids: [1], note: 'decided'}", set()) == [
        "standards/X.yaml: conflicts.d: decided, but none of conflicts #[1] carries [D<n>]"]
    assert undecided_standards(conflicts, {"standards/X.yaml": "version: 1\n"}, known) == []


@pytest.mark.parametrize("ids,valid", [(["D001", "D003"], True),
                                      (["D001", "D001"], False), (["D003", "D001"], False)])
def test_log_format_reserved_ids(monkeypatch, ids, valid):
    """Rule 42: open PR reservations may leave gaps, but duplicate/descending IDs still fail."""
    rows = [[i, "2026-10-19", "decision", "anchor", "user"] for i in ids]
    monkeypatch.setitem(globals(), "log_rows", lambda: rows)
    if valid:
        test_log_format()
    else:
        with pytest.raises(AssertionError):
            test_log_format()


def test_log_rejects_every_duplicate_id(monkeypatch):
    """Exhaustive synthetic mutations: a backfill must not weaken id uniqueness."""
    rows = log_rows()
    module = __import__(__name__)
    for i in range(len(rows)):
        # Rule 42 (#166) allows reserved gaps, so a removed id is valid; a duplicated id must still fail.
        mutations = [rows[:i] + [rows[i]] + rows[i:]]
        for mutated in mutations:
            monkeypatch.setattr(module, "log_rows", lambda mutated=mutated: mutated)
            with pytest.raises(AssertionError):
                test_log_format()
    monkeypatch.setattr(module, "log_rows", lambda: [])
    with pytest.raises(AssertionError, match="no decisions"):
        test_log_format()


def test_live_main_ground_mentions_resolve_to_distinct_sources():
    """#337: real integration input, not a synthetic replacement of the four mentions."""
    rows = {row[0]: row for row in log_rows()}
    paths = ["src/dt_ai/geometry/ground_cake.py", "tests/test_ground_cake.py"]
    assert unreferenced(paths, set(rows)) == []
    for path in paths:
        mentions = [line for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
                    if MENTION.search(line)]
        assert len(mentions) == 2
        assert "[D153]" in mentions[0] and "[D154]" in mentions[1]
    for id_, source in (("D153", "6265799957"), ("D154", "6274902891")):
        assert rows[id_][1] == "2026-10-19"
        assert "(decided 2026-10-19, recorded 2026-10-20)" in rows[id_][2]
        assert rows[id_][4].startswith("backfill #337") and source in rows[id_][4]
    assert "6267750172" in rows["D153"][4]  # removes the orchestrator's own 1 m threshold
    assert "1 cm" in rows["D153"][2] and "4 x 4 m" in rows["D153"][2]
    assert "5-20 mm" in rows["D154"][2] and "+6 / +12 mm" in rows["D154"][2]
    assert "12 steep/flatter-junction vertices" in rows["D150"][2]
    assert "not a general spacing-rule relaxation" in rows["D150"][2]


def test_placement_approval_fixtures_do_not_hide_real_mentions(tmp_path, monkeypatch):
    """Synthetic approval literals are not decisions; adjacent real prose stays in scope."""
    paths = ["tests/placement/test_site_job.py", "tests/placement/test_site_placement.py",
             "tests/test_task_to_model.py"]
    known = {row[0] for row in log_rows()}
    assert unreferenced(paths, known) == []
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# user 2026-10-20: real untagged rule\n"
                        "# user 2026-10-20 [D999]: unknown rule\n", encoding="utf-8")
        assert in_scope(name)
        assert unreferenced([name], known) == [
            f"{name}:1: dated user decision without [D<n>]", f"{name}:2: unknown D999"]
        path.write_text("", encoding="utf-8")
        assert unreferenced([name], known) == []
    # Partial approval lookalikes must not exempt the whole task-to-model file.
    name = "tests/test_task_to_model.py"
    path = tmp_path / name
    path.write_text('"actor": "user", "date": "2026-10-20"\n'
                    'actor_role="user", date="2026-10-20"\n', encoding="utf-8")
    assert unreferenced([name], known) == [
        f"{name}:1: dated user decision without [D<n>]",
        f"{name}:2: dated user decision without [D<n>]"]


def test_drawing_review_decision_is_logged_and_anchored():
    rows = [row for row in log_rows() if row[0] == "D132"]
    assert len(rows) == 1, "#85 drawing-review decision must be canonical"
    row = rows[0]
    # Recorded 2026-10-19 between D131 and D134 (ids and dates both ascending, rule 42); decided 2026-10-16.
    assert row[1] == "2026-10-19" and "decided 2026-10-16" in row[2]
    assert "drawings" in row[2] and "missing wall" in row[2]
    assert row[3] == "`src/dt_ai/spec/mesh.py` `_panel_contour`"
    assert "/pull/274" in row[4] and "#85" in row[4]
    source = (ROOT / "src/dt_ai/spec/mesh.py").read_text(encoding="utf-8")
    rule = source.split("def _panel_contour(", 1)[1].split('"""')[1]
    assert "[D132]" in rule and "the extractor does not decide it" in rule
