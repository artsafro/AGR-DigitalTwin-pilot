"""#1396: a duplicate_guard allowlist row covers `count` copies (default 1), not every copy in its function.

Since #1387 rows are keyed by `path.py::qualname` (+ optional hash); without a count an identical 2nd copy pasted
into the same function was silently covered. Covered findings > count -> the extra ones are NEW COPY; covered
findings < count -> STALE ALLOWLIST.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))

import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402

COPY = "    return 1001 + u + 10 * v\n"
TWO = "def f(u, v):\n    x = 1001 + u + 10 * v\n" + COPY          # issue repro: identical 2nd copy in f


def _root(tmp_path, files, rows=""):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    for top in ("jobs", "tools", "src"):
        (tmp_path / top).mkdir(exist_ok=True)
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text("contexts:\n  - id: x\n    duplicates:\n" + rows if rows else "contexts:\n  - id: x\n",
                   encoding="utf-8")
    return ["--root", str(tmp_path), "--contexts", str(ctx), "--copies-only"]


def _row(at="jobs/J/a.py::f", digest=None, count=None):
    row = f'      - at: "{at}"\n        rule: udim-tile\n        issue: "#1337"\n'
    row += f'        hash: "{digest}"\n' if digest else ""
    return row + (f"        count: {count}\n" if count is not None else "")


def _digest(code=TWO):
    digests = {f.digest for f in guard.scan_text(code)}
    assert len(digests) == 1, digests
    return digests.pop()


def _allowed(**row):
    return guard.allowlist(mini_yaml.loads("contexts:\n  - id: x\n    duplicates:\n" + _row(**row)))


def test_issue_repro_identical_second_copy_in_hashed_function_is_red():
    new, stale = guard.compare(guard.scan_text(TWO, "jobs/J/a.py"), _allowed(digest=_digest()))
    assert [(f.line, f.qualname) for f in new] == [(3, "f")] and stale == []


def test_identical_second_copy_with_no_hash_row_is_red(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": TWO}, _row())) == 1
    out = capsys.readouterr().out
    assert "NEW COPY [udim-tile] jobs/J/a.py:3 in f" in out and "count 1" in out and "STALE" not in out


@pytest.mark.parametrize("hashed", [False, True])
def test_identical_second_copy_at_module_level_is_red(tmp_path, hashed, capsys):
    code = "t = 1001 + u + 10 * v\n"
    row = _row("jobs/J/a.py::<module>", _digest(code) if hashed else None)
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": code}, row)) == 0
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": code + "\n# pasted\n" + code}, row)) == 1
    assert "NEW COPY [udim-tile] jobs/J/a.py:4 in <module>" in capsys.readouterr().out


def test_two_identical_copies_on_one_line_are_two_findings(tmp_path, capsys):
    code = "a = 1001 + u + 10 * v; b = 1001 + u + 10 * v\n"
    assert len(guard.scan_text(code)) == 2
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": code}, _row("jobs/J/a.py::<module>"))) == 1
    assert "NEW COPY [udim-tile] jobs/J/a.py:1 in <module>" in capsys.readouterr().out
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": code}, _row("jobs/J/a.py::<module>", count=2))) == 0


@pytest.mark.parametrize("hashed", [False, True])
@pytest.mark.parametrize("prefix,body", [("\n" * 5, ""), ("", "    y = 2\n" * 4), ("import os\n\n\n", "    # m\n")])
def test_moving_lines_stays_green(tmp_path, hashed, prefix, body, capsys):
    code = prefix + "def f(u, v):\n" + body + "    x = 1001 + u + 10 * v\n" + body + COPY
    row = _row(digest=_digest() if hashed else None, count=2)
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": code}, row)) == 0, capsys.readouterr().out


def test_count_two_green_three_red_one_stale(tmp_path, capsys):
    row = _row(digest=_digest(), count=2)
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": TWO}, row)) == 0
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": TWO + COPY}, row)) == 1
    out = capsys.readouterr().out
    assert "NEW COPY [udim-tile] jobs/J/a.py:4 in f" in out and ":3 in f" not in out and "STALE" not in out
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": "def f(u, v):\n" + COPY}, row)) == 1
    out = capsys.readouterr().out
    assert "STALE ALLOWLIST [udim-tile] jobs/J/a.py::f hash" in out and "1 of count 2" in out and "NEW" not in out


@pytest.mark.parametrize("hashed", [False, True])
def test_brute_force_found_vs_count(tmp_path, hashed):
    """Probe: for found n in 1..5 and count c in 1..5 -> new = max(0, n - c), stale iff n < c, exit 0 iff n == c."""
    digest = _digest() if hashed else None
    for n in range(1, 6):
        code = "def f(u, v):\n" + COPY * n
        findings = guard.scan_text(code, "jobs/J/a.py")
        assert len(findings) == n
        for c in range(1, 6):
            new, stale = guard.compare(findings, _allowed(digest=digest, count=c))
            assert len(new) == max(0, n - c) and bool(stale) == (n < c), (n, c)
            assert [f.line for f in new] == list(range(2 + c, 2 + n))      # the extra copies are the last ones
            assert guard.main(_root(tmp_path, {"jobs/J/a.py": code}, _row(digest=digest, count=c))) == (n != c)


@pytest.mark.parametrize("count", ["0", "-1", '"2"'])
def test_bad_count_is_an_error_naming_the_row(tmp_path, count, capsys):
    row = _row() + f"        count: {count}\n"
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": TWO}, row)) == 2
    assert "jobs/J/a.py::f" in capsys.readouterr().err


@pytest.mark.parametrize("count", ["'1'", "1.0", "[]", "true", ".nan", ""])
def test_count_yaml_cannot_parse_is_an_error_naming_the_line(tmp_path, count, capsys):
    row = _row() + f"        count: {count}\n"
    assert guard.main(_root(tmp_path, {"jobs/J/a.py": TWO}, row)) == 2
    err = capsys.readouterr().err
    assert "line 7" in err or "jobs/J/a.py::f" in err


def test_default_count_is_one_and_plain_issue_dicts_still_work():
    allowed = _allowed()
    value = list(allowed.values())[0]
    assert value.copies == 1 and value.issue == "#1337" and value == "#1337"      # still compares as the issue
    plain = {("udim-tile", "jobs/J/a.py", "f", None): "#1"}                  # pre-#1396 callers: count 1
    assert len(guard.compare(guard.scan_text(TWO, "jobs/J/a.py"), plain)[0]) == 1


def test_unguarded_documentation_row_excess_is_not_new_but_shortfall_is_stale():
    code = "def f(u, v):\n" + COPY * 2
    findings = guard.scan_text(code, "adapters/x.py")
    assert guard.compare(findings, _allowed(at="adapters/x.py::f")) == ([], [])
    assert guard.compare(findings, _allowed(at="adapters/x.py::f", count=3))[1]


def test_json_reports_count_and_found(tmp_path, capsys):
    args = _root(tmp_path, {"jobs/J/a.py": "def f(u, v):\n" + COPY}, _row(count=2)) + ["--json"]
    assert guard.main(args) == 1
    out = capsys.readouterr().out
    doc = json.loads(out[out.index("{"):out.rindex("}") + 1])
    assert doc["stale"] == [{"rule": "udim-tile", "path": "jobs/J/a.py", "qualname": "f", "hash": None,
                             "count": 2, "found": 1}]


def test_real_kpp1_export_npm_third_identical_copy_is_red(tmp_path, capsys):
    """Real instance from the issue: export_npm.py rows cover two copies; a third identical copy is NEW."""
    def only_py(directory, names):
        return [n for n in names if not (Path(directory) / n).is_dir() and not n.endswith(".py")]

    for top in ("jobs", "adapters", "tools", "src"):
        shutil.copytree(ROOT / top, tmp_path / top, ignore=only_py)
    args = ["--root", str(tmp_path), "--contexts", str(ROOT / "docs/architecture/contexts.yaml"), "--copies-only"]
    assert guard.main(args) == 0, capsys.readouterr().out
    rel = "jobs/KPP1/scripts/export_npm.py"
    src = (tmp_path / rel).read_text(encoding="utf-8")
    hit = [f for f in guard.scan_text(src, rel) if f.rule == "udim-tile" and f.qualname == "<module>"]
    assert len(hit) == 2
    line = src.splitlines()[hit[0].line - 1]
    (tmp_path / rel).write_text(src + "\n" + line.strip() + "\n", encoding="utf-8")
    assert guard.main(args) == 1
    assert f"NEW COPY [udim-tile] {rel}:" in capsys.readouterr().out


def test_fresh_process_cli_repo_green():
    r = subprocess.run([sys.executable, str(ROOT / "tools/architecture/duplicate_guard.py"), "--copies-only"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
