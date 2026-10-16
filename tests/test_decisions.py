"""Decision ids (#120, #138).

docs/decisions.md is one dated user decision per row. A mention of a dated user decision carries
`[D<n>]` on the same line, by kind of file: Markdown outside the excluded folders; tracked Python
except under `jobs/`, `technical_library/`, `data/`, `docs/agr/`, `tests/fixtures/` and this file;
and `standards/material_id_ranges.yaml`. Locked standards YAML is not edited: a top-level
`conflicts:` entry whose note says "decided" must list an `ids` number whose item in
`docs/domain/conflicts.md` carries a `[D<n>]` from the log. JSON, `jobs/**` and frozen fixtures
are out of scope.
"""
import datetime
import re
import subprocess
from pathlib import Path

import yaml

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
CONFLICT_ITEM = re.compile(r"^(\d+)\. ")
# Lines that match MENTION but state no decision: (file, text on the line).
NOT_DECISIONS = [
    ("docs/backlog.md", "AGR_Project-uncommitted-2026-10-06.zip"),  # an archive name next to "the user plans"
    ("tests/test_ready_gate.py", "(user, 2026-10-14)"),  # a quoted chat fixture line
    ("tests/test_area_requirement_sheet.py", "Decided 2026-10-15 [{record}] (user)"),  # an f-string template asserting the format
]


def in_scope(path: str) -> bool:
    """One repo-relative path: Markdown as today, Python except the excluded trees, one standards file."""
    path = path.replace("\\", "/")
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


def test_log_format():
    rows = log_rows()
    assert rows, "no decisions"
    dates = []
    for number, row in enumerate(rows, 1):
        assert len(row) == 5 and all(row), row
        assert row[0] == f"D{number:03d}", f"{row[0]}: ids must run D001, D002, ... without gaps"
        dates.append(datetime.date.fromisoformat(row[1]))
    assert dates == sorted(dates), "decisions must be sorted by date"


def test_every_dated_decision_carries_its_id():
    known = {row[0] for row in log_rows()}
    assert unreferenced(scope_files(), known) == []


def test_every_decision_is_anchored_where_it_applies():
    anchored = set()
    markdown = [name for name in scope_files() if name.endswith(".md")]
    for name in markdown + ["docs/prd/agent-ready-harness.md"]:
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
