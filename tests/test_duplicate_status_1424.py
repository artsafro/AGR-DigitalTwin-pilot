"""#1424: every duplicates row of every context map carries a status derived from real call chains.

Acceptance table (PR body) -> tests here:
- every row of the six maps has a status; the repo agrees with its call chains  -> test_repo_*
- missing / unknown status, own-duty without why, live-bypass without step  -> test_rows_of_*
- NEW live-bypass fails; a fixed one must leave the baseline  -> test_new_live_bypass_fails, test_fixed_*
- historical only inside finished jobs and only without a live chain  -> test_historical_*
- wrapper must call the owner; a live-bypass that calls it is a wrapper  -> test_wrapper_*
- call chains: imports, lazy imports, `.py` strings, siblings, relative imports, MZP list  -> test_chain_*
- brute-force probe: status_problems == independent oracle on every combination  -> test_probe_*
- Russian table + compaction order, committed report has no drift  -> test_table_*, test_report_*
"""
import itertools
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import call_chains  # noqa: E402
import duplicate_guard as guard  # noqa: E402

OWNER = "src/pkg/owner.py"


def _write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _repo(tmp_path, files=None):
    base = {
        "pyproject.toml": '[project]\nname = "x"\n\n[project.scripts]\nx = "pkg.cli:main"\n\n[tool.other]\n',
        "src/pkg/__init__.py": "",
        "src/pkg/cli.py": "def main():\n    from pkg import live\n    return live\n",
        "src/pkg/live.py": "import subprocess\nsubprocess.run(['python', 'jobs/J/run.py'])\n",
        OWNER: "def f(u, v):\n    return 1001 + u + 10 * v\n",
        "tools/max/build_agr_tools.py": "FILES = ('a_core.py', 'menu.ms')\n",
        "adapters/max/agr_tools/a_core.py": "def tile(u, v):\n    return 1001 + u + 10 * v\n",
        "jobs/J/run.py": "def copy(u, v):\n    return 1001 + u + 10 * v\n",
        "jobs/J/old.py": "def copy(u, v):\n    return 1001 + u + 10 * v\n",
        "jobs/K/old.py": "def copy(u, v):\n    return 1001 + u + 10 * v\n",
        "jobs/J/wrap.py": "from pkg.owner import f\n\ndef copy(u, v):\n    return f(u, v)\n",
        "jobs/J/DONE.md": "accepted by the user\n",
    }
    base.update(files or {})
    _write(tmp_path, base)
    return tmp_path


def _row(at, status, owner=OWNER, step=None, m="contexts", digest=""):
    rel, qual, line = guard._row_at(at)
    return guard.Row(m, "udim", owner, at, rel, qual, line, status, step, "причина", "#1", digest, "", "UDIM")


def _check(root, rows, baseline=frozenset(), finished=None):
    roots, chains = call_chains.load_live(root, routes={}, context_maps={})
    finished = {"jobs/J": "jobs/J/DONE.md"} if finished is None else finished
    return guard.status_problems(root, rows, chains, roots, finished, baseline, own_duty_baseline=frozenset())


# ---------------------------------------------------------------- the repo itself
def test_repo_every_row_has_a_status_and_agrees_with_call_chains():
    maps = guard.load_maps(ROOT)
    rows = guard.rows_of(maps)
    assert len(rows) == sum(len(c.get("duplicates", [])) for m in maps.values()
                            for c in [m["shared_kernel"]] + m["contexts"])
    assert {r.status for r in rows} <= set(guard.STATUSES)
    contexts = maps["contexts"]
    roots, chains = guard.live_chains(ROOT)
    assert guard.status_problems(ROOT, rows, chains, roots, guard.finished_jobs(ROOT, contexts)) == []


def test_repo_guard_cli_fresh_process_exit_0_and_prints_the_russian_table():
    r = subprocess.run([sys.executable, str(ROOT / "tools/architecture/duplicate_guard.py"), "--table"],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Живые обходы по областям" in r.stdout and "STATUS" not in r.stdout


def test_report_1424_holds_the_generated_table():
    rows = guard.rows_of(guard.load_maps(ROOT))
    report = (ROOT / "docs/architecture/report-1424.md").read_text(encoding="utf-8")
    assert guard.bypass_table(rows) in report


# ---------------------------------------------------------------- schema of a row
@pytest.mark.parametrize("dup, needle", [
    ({"at": "jobs/J/a.py:1"}, "status None"),
    ({"at": "jobs/J/a.py:1", "status": "frozen"}, "status 'frozen'"),
    ({"at": "jobs/J/a.py:1", "status": "own-duty"}, "own-duty needs `why`"),
    ({"at": "jobs/J/a.py:1", "status": "own-duty", "why": "other duty"}, "own-duty needs `why`"),
    ({"at": "jobs/J/a.py:1", "status": "live-bypass"}, "live-bypass needs `step`"),
    ({"at": "jobs/J/a.py:1", "status": "live-bypass", "step": "1379"}, "live-bypass needs `step`"),
    ({"at": "jobs/J/a.py:1", "status": "historical", "step": "#1"}, "belongs to live-bypass"),
])
def test_rows_of_rejects_a_bad_status_naming_the_row(dup, needle):
    maps = {"m": {"shared_kernel": {"id": "k"}, "contexts": [{"id": "c", "owner": OWNER, "duplicates": [dup]}]}}
    with pytest.raises(ValueError, match="m: jobs/J/a.py:1") as exc:
        guard.rows_of(maps)
    assert needle in str(exc.value)


def test_rows_of_empty_map_gives_no_rows_and_good_rows_pass():
    assert guard.rows_of({}) == []
    ok = {"m": {"shared_kernel": {"id": "k", "duplicates": [
        {"at": "a.py::f", "status": "own-duty", "why": "другая задача"},
        {"at": "a.py::g", "status": "live-bypass", "step": "-"}]}}}
    assert [r.status for r in guard.rows_of(ok)] == ["own-duty", "live-bypass"]


# ---------------------------------------------------------------- status against call chains
def test_new_live_bypass_fails_and_baselined_one_passes(tmp_path):
    root = _repo(tmp_path)
    row = _row("jobs/J/run.py::copy", "live-bypass", step="#1379")
    assert any(p.startswith("NEW LIVE BYPASS") for p in _check(root, [row]))
    assert _check(root, [row], baseline=frozenset({("contexts", "jobs/J/run.py::copy", "")})) == []


def test_fixed_live_bypass_must_leave_the_baseline(tmp_path):
    root = _repo(tmp_path)
    problems = _check(root, [], baseline=frozenset({("contexts", "jobs/J/run.py::copy", "")}))
    assert len(problems) == 1 and problems[0].startswith("FIXED LIVE BYPASS")


def test_live_bypass_without_live_chain_fails(tmp_path):
    root = _repo(tmp_path)
    key = frozenset({("contexts", "jobs/J/old.py::copy", "")})
    assert any("no live command/route reaches" in p for p in _check(root, [_row("jobs/J/old.py::copy", "live-bypass",
                                                                                step="-")], key))


def test_historical_in_finished_job_without_chain_passes(tmp_path):
    assert _check(_repo(tmp_path), [_row("jobs/J/old.py::copy", "historical")]) == []


def test_historical_reached_by_a_live_command_fails_naming_the_chain(tmp_path):
    problems = _check(_repo(tmp_path), [_row("jobs/J/run.py::copy", "historical")])
    assert any("live command/route uses it: src/pkg/cli.py > src/pkg/live.py > jobs/J/run.py" in p for p in problems)


@pytest.mark.parametrize("at", ["jobs/K/old.py::copy", "adapters/max/agr_tools/a_core.py::tile"])
def test_historical_outside_a_finished_job_fails(tmp_path, at):
    problems = _check(_repo(tmp_path), [_row(at, "historical")])
    assert any("historical only inside a finished job" in p for p in problems)


def test_historical_with_no_finished_jobs_fails(tmp_path):
    problems = _check(_repo(tmp_path), [_row("jobs/J/old.py::copy", "historical")], finished={})
    assert any("historical only inside a finished job" in p for p in problems)


def test_wrapper_must_call_the_owner(tmp_path):
    root = _repo(tmp_path)
    assert _check(root, [_row("jobs/J/wrap.py::copy", "wrapper")]) == []
    assert any("does not call its owner" in p for p in _check(root, [_row("jobs/J/old.py::copy", "wrapper")]))


def test_wrapper_by_sibling_path_string_and_by_line_row(tmp_path):
    root = _repo(tmp_path, {"jobs/J/sib.py": "def _sibling(n):\n    return n\n\nOW = _sibling('owner.py')\n\n\n"
                                             "def copy(u):\n    return OW.f(u, 0)\n\n\ndef other():\n    return 1\n"})
    assert _check(root, [_row("jobs/J/sib.py:8", "wrapper")]) == []
    assert any("does not call" in p for p in _check(root, [_row("jobs/J/sib.py:12", "wrapper")]))


def test_live_bypass_that_calls_the_owner_is_a_wrapper(tmp_path):
    root = _repo(tmp_path, {"src/pkg/live.py": "import subprocess\nsubprocess.run(['python', 'jobs/J/wrap.py'])\n"})
    key = frozenset({("contexts", "jobs/J/wrap.py::copy", "")})
    assert any(p.endswith(": wrapper") for p in _check(root, [_row("jobs/J/wrap.py::copy", "live-bypass", step="-")],
                                                        key))


def test_missing_file_is_a_problem_not_a_pass(tmp_path):
    assert any("file does not exist" in p for p in _check(_repo(tmp_path), [_row("jobs/J/gone.py::f", "historical")]))


@pytest.mark.parametrize("at", ["jobs/J/../K/old.py::copy", "jobs/J/./old.py::copy", "jobs\\J\\old.py::copy"]
                         + (["JOBS/J/old.py::copy"] if sys.platform == "win32" else []))
def test_path_alias_cannot_pass_as_historical(tmp_path, at):
    problems = _check(_repo(tmp_path), [_row(at, "historical")])
    assert any("alias" in p for p in problems), problems


def test_cli_exit_1_on_a_new_live_bypass(monkeypatch, capsys):
    monkeypatch.setattr(guard, "LIVE_BYPASS_BASELINE", frozenset())
    monkeypatch.setattr(guard.status_problems, "__defaults__", (frozenset(),))
    assert guard.main([]) == 1
    out = capsys.readouterr().out
    live = sum(1 for r in guard.rows_of(guard.load_maps(ROOT)) if r.status == "live-bypass")
    assert out.count("STATUS NEW LIVE BYPASS") == live == 7   # #1593 inventories two existing KPP1 writers; no new build behaviour


def test_finished_jobs_evidence_must_exist_and_match(tmp_path):
    root = _repo(tmp_path)
    good = {"finished_jobs": [{"job": "jobs/J", "evidence": "jobs/J/DONE.md", "match": "accepted"}]}
    assert guard.finished_jobs(root, good) == {"jobs/J": "jobs/J/DONE.md"}
    for bad, needle in [({"job": "jobs/J", "evidence": "jobs/J/NO.md", "match": "x"}, "does not exist"),
                        ({"job": "jobs/J", "evidence": "jobs/J/DONE.md", "match": "rejected"}, "does not contain"),
                        ({"job": "jobs/J/sub", "evidence": "jobs/J/DONE.md", "match": "a"}, "needs job"),
                        ({"job": "jobs/J", "evidence": "", "match": "a"}, "needs job")]:
        with pytest.raises(ValueError, match=needle):
            guard.finished_jobs(root, {"finished_jobs": [bad]})
    assert guard.finished_jobs(root, {}) == {}


# ---------------------------------------------------------------- call chains
def test_chain_roots_and_edges(tmp_path):
    root = _repo(tmp_path, {
        "tools/a/run.py": "from . import helper\nimport sib\n",
        "tools/a/helper.py": "",
        "tools/a/sib.py": "P = 'src/pkg/deep.py'\n",
        "src/pkg/deep.py": "def g():\n    from pkg.sub import leaf\n",
        "src/pkg/sub/__init__.py": "", "src/pkg/sub/leaf.py": "",
    })
    roots, chains = call_chains.load_live(root, routes={}, context_maps={})
    assert roots["src/pkg/cli.py"] == "команда x"
    assert roots["adapters/max/agr_tools/a_core.py"].startswith("AGR Tools")
    assert chains["jobs/J/run.py"] == ["src/pkg/cli.py", "src/pkg/live.py", "jobs/J/run.py"]
    assert chains["src/pkg/sub/leaf.py"][-2:] == ["src/pkg/deep.py", "src/pkg/sub/leaf.py"]
    assert "tools/a/helper.py" in chains and "src/pkg/sub/__init__.py" in chains
    assert "jobs/J/old.py" not in chains and "jobs/K/old.py" not in chains


def test_chain_route_evidence_is_a_root_but_hotspot_evidence_is_not(tmp_path):
    root = _repo(tmp_path)
    routes = {"r": {"stages": [{"id": "s", "evidence": ["jobs/J/old.py", "docs/x.md"]}],
                    "hotspots": [{"id": "h", "evidence": ["jobs/K/old.py"]}]}}
    roots = call_chains.live_roots(root, routes, {})
    assert roots["jobs/J/old.py"] == "маршрут r: этап s" and "jobs/K/old.py" not in roots


@pytest.mark.parametrize("files, needle", [
    ({"pyproject.toml": "[project]\nname = 'x'\n"}, "no \\[project.scripts\\]"),
    ({"pyproject.toml": '[project.scripts]\nx = "nope.mod:main"\n'}, "module not found"),
    ({"tools/max/build_agr_tools.py": "OTHER = 1\n"}, "no FILES list"),
    ({"tools/max/build_agr_tools.py": "FILES = ('gone.py',)\n"}, "names missing"),
    ({"src/pkg/live.py": "def (:\n"}, "src/pkg/live.py: cannot parse"),
])
def test_chain_fails_closed(tmp_path, files, needle):
    root = _repo(tmp_path, files)
    with pytest.raises((ValueError, FileNotFoundError, SyntaxError), match=needle):
        call_chains.load_live(root, routes={}, context_maps={})


# ---------------------------------------------------------------- brute-force probe
def _oracle(status, live, job, wrapper, baselined):
    ok = {"wrapper": wrapper,
          "historical": not live and job == "J",
          "live-bypass": live and not wrapper and baselined,
          "own-duty": not live or baselined,
          "superseded": not live}[status]
    return ok


def test_probe_status_problems_equal_an_independent_oracle(tmp_path):
    """Every status x live chain x job (finished J / unfinished K) x calls-owner x baselined: 5*2*2*2*2 = 80."""
    files, cases = {}, []
    for i, (status, live, job, wrapper, base) in enumerate(itertools.product(
            guard.STATUSES, (True, False), ("J", "K"), (True, False), (True, False))):
        rel = f"jobs/{job}/c{i}.py"
        body = "from pkg.owner import f\n\ndef copy(u):\n    return f(u, 0)\n" if wrapper else \
            "def copy(u):\n    return 1001 + u\n"
        files[rel] = body
        cases.append((rel, status, live, job, wrapper, base))
    files["src/pkg/live.py"] = "\n".join(f"R{i} = '{c[0]}'" for i, c in enumerate(cases) if c[2]) + "\n"
    root = _repo(tmp_path, files)
    roots, chains = call_chains.load_live(root, routes={}, context_maps={})
    passed = 0
    for rel, status, live, job, wrapper, base in cases:
        row = _row(f"{rel}::copy", status, step="-" if status == "live-bypass" else None)
        key = frozenset({("contexts", row.at, "")})
        baseline = key if base and status == "live-bypass" else frozenset()
        # #1429: a baselined own-duty key without a live chain is a stale (FIXED) key, so only live ones get it
        own = key if base and live and status == "own-duty" else frozenset()
        got = guard.status_problems(root, [row], chains, roots, {"jobs/J": "jobs/J/DONE.md"}, baseline,
                                    own_duty_baseline=own) == []
        ratcheted = status in ("live-bypass", "own-duty")
        assert got == _oracle(status, live, job, wrapper, base or not ratcheted), (rel, status, live,
                                                                                 job, wrapper, base)
        passed += 1
    assert passed == 80


# ---------------------------------------------------------------- table
def test_table_counts_one_copy_in_two_maps_once_and_orders_steps():
    rows = [_row("jobs/J/a.py:1", "live-bypass", step="#1404", m="m1"),
            _row("jobs/J/a.py:1", "live-bypass", step="#1404", m="m2"),
            _row("jobs/J/b.py:1", "live-bypass", step="#1379"),
            _row("jobs/J/c.py:1", "live-bypass", step="#1379"),
            _row("jobs/J/d.py:1", "historical")]
    table = guard.bypass_table(rows)
    assert "живой обход 4, обёртка 0, исторические 1, своя обязанность 0; разных живых копий 3." in table
    order = [line.split("|")[2].strip() for line in table.splitlines() if line.startswith("| ") and
             line.split("|")[1].strip().isdigit()]
    assert order[:2] == ["#1379", "#1404"] and order[2:] == [s for s in guard.COMPACTION_STEPS
                                                               if s not in ("#1379", "#1404")]
    assert guard.bypass_table([]).count("| 0 |") == len(guard.COMPACTION_STEPS)
