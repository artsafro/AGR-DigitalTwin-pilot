"""#1429: an own-duty row reached by a live command/route passes only through the reviewed OWN_DUTY_BASELINE ratchet.

Acceptance table (PR body) -> tests here:
- NEW live own-duty fails `NEW OWN-DUTY <where>: <chain>`; baselined one passes  -> test_new_live_own_duty_*
- own-duty with no live chain passes without a baseline key                        -> test_own_duty_without_live_chain_*
- baseline key without its live own-duty row fails as FIXED (row gone / chain gone) -> test_fixed_own_duty_*
- reviewer repro on the real repo: a live-bypass relabelled own-duty, key removed  -> test_repo_relabel_*
- real repo: OWN_DUTY_BASELINE == the live own-duty rows exactly                   -> test_repo_own_duty_baseline_*
- key is (map, at, hash): another map / hash of the same copy is NEW               -> test_key_is_map_at_hash
- two ratchets are separate: live-bypass key does not admit own-duty, and back      -> test_ratchets_do_not_cross
- CLI fresh process exits 1 on a NEW OWN-DUTY                                       -> test_cli_exit_1_on_new_own_duty
- brute-force probe: every own-duty row x live x baselined x map x hash            -> test_probe_own_duty_*
"""
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
sys.path.insert(0, str(ROOT / "tests"))
import call_chains  # noqa: E402
import duplicate_guard as guard  # noqa: E402
from test_duplicate_status_1424 import _repo, _row  # noqa: E402

RUN = "jobs/J/run.py::copy"      # reached: x -> src/pkg/cli.py > src/pkg/live.py > jobs/J/run.py
OLD = "jobs/J/old.py::copy"      # no live chain


def _check(root, rows, own=frozenset(), live=frozenset()):
    roots, chains = call_chains.load_live(root, routes={}, context_maps={})
    return guard.status_problems(root, rows, chains, roots, {"jobs/J": "jobs/J/DONE.md"}, live,
                                 own_duty_baseline=own)


def test_new_live_own_duty_fails_naming_the_chain(tmp_path):
    problems = _check(_repo(tmp_path), [_row(RUN, "own-duty")])
    assert len(problems) == 1, problems
    assert problems[0].startswith(f"NEW OWN-DUTY contexts: {RUN}: ")
    assert "src/pkg/cli.py > src/pkg/live.py > jobs/J/run.py" in problems[0] and "OWN_DUTY_BASELINE" in problems[0]


def test_new_live_own_duty_baselined_passes(tmp_path):
    assert _check(_repo(tmp_path), [_row(RUN, "own-duty")], own=frozenset({("contexts", RUN, "")})) == []


def test_own_duty_without_live_chain_passes_without_a_key(tmp_path):
    assert _check(_repo(tmp_path), [_row(OLD, "own-duty")]) == []


def test_fixed_own_duty_row_gone_must_leave_the_baseline(tmp_path):
    problems = _check(_repo(tmp_path), [], own=frozenset({("contexts", RUN, "")}))
    assert len(problems) == 1 and problems[0].startswith(f"FIXED OWN-DUTY contexts: {RUN}"), problems
    assert "OWN_DUTY_BASELINE" in problems[0]


def test_fixed_own_duty_chain_gone_must_leave_the_baseline(tmp_path):
    """A baselined own-duty row no live command reaches any more: the key is stale - tighten the ratchet."""
    problems = _check(_repo(tmp_path), [_row(OLD, "own-duty")], own=frozenset({("contexts", OLD, "")}))
    assert len(problems) == 1 and problems[0].startswith(f"FIXED OWN-DUTY contexts: {OLD}"), problems


def test_key_is_map_at_hash(tmp_path):
    root = _repo(tmp_path)
    own = frozenset({("contexts", RUN, "")})
    for row in (_row(RUN, "own-duty", m="vpm-contexts"), _row(RUN, "own-duty", digest="abc")):
        problems = _check(root, [row], own=own)
        assert any(p.startswith("NEW OWN-DUTY") for p in problems), problems
        assert any(p.startswith("FIXED OWN-DUTY") for p in problems), problems


def test_ratchets_do_not_cross(tmp_path):
    root = _repo(tmp_path)
    key = frozenset({("contexts", RUN, "")})
    own_in_live = _check(root, [_row(RUN, "own-duty")], live=key)
    assert any(p.startswith("NEW OWN-DUTY") for p in own_in_live)
    assert any(p.startswith("FIXED LIVE BYPASS") for p in own_in_live)
    live_in_own = _check(root, [_row(RUN, "live-bypass", step="-")], own=key)
    assert any(p.startswith("NEW LIVE BYPASS") for p in live_in_own)
    assert any(p.startswith("FIXED OWN-DUTY") for p in live_in_own)


# ---------------------------------------------------------------- the real repo
def _real():
    maps = guard.load_maps(ROOT)
    roots, chains = guard.live_chains(ROOT)
    return guard.rows_of(maps), chains, roots, guard.finished_jobs(ROOT, maps["contexts"])


def test_repo_own_duty_baseline_equals_the_live_own_duty_rows():
    rows, chains, _, _ = _real()
    live_own = {(r.map, r.at, r.hash) for r in rows if r.status == "own-duty" and chains.get(r.rel)}
    assert live_own == set(guard.OWN_DUTY_BASELINE) and len(live_own) == 13


def test_repo_relabel_live_bypass_as_own_duty_fails():
    """Reviewer repro of #1429 on today's rows: every live-bypass relabelled own-duty with a Russian why and its key
    removed from LIVE_BYPASS_BASELINE must fail NEW OWN-DUTY (before #1429: [])."""
    rows, chains, roots, finished = _real()
    live = [r for r in rows if r.status == "live-bypass"]
    assert live
    for r in live:
        key = (r.map, r.at, r.hash)
        fake = [x._replace(status="own-duty", step=None, why="другая обязанность") if x is r else x for x in rows]
        problems = guard.status_problems(ROOT, fake, chains, roots, finished, guard.LIVE_BYPASS_BASELINE - {key})
        assert len(problems) == 1 and problems[0].startswith(f"NEW OWN-DUTY {r.map}: {r.at}"), (key, problems)


def test_cli_exit_1_on_new_own_duty(monkeypatch, capsys):
    monkeypatch.setattr(guard.status_problems, "__kwdefaults__", {"own_duty_baseline": frozenset()})
    assert guard.main([]) == 1
    assert capsys.readouterr().out.count("STATUS NEW OWN-DUTY") == len(guard.OWN_DUTY_BASELINE) == 13


# ---------------------------------------------------------------- brute-force probe
def test_probe_own_duty_every_combination(tmp_path):
    """own-duty x live chain x baselined x key map x key hash: passes iff no chain, or chain and exact key."""
    root = _repo(tmp_path)
    n = 0
    for at, base, kmap, kdigest in itertools.product((RUN, OLD), (True, False), ("contexts", "other"), ("", "h")):
        live = at == RUN
        own = frozenset({(kmap, at, kdigest)}) if base else frozenset()
        exact = base and kmap == "contexts" and kdigest == ""
        problems = _check(root, [_row(at, "own-duty")], own=own)
        new = [p for p in problems if p.startswith("NEW OWN-DUTY")]
        fixed = [p for p in problems if p.startswith("FIXED OWN-DUTY")]
        assert bool(new) == (live and not exact), (at, own, problems)
        assert bool(fixed) == (base and not (live and exact)), (at, own, problems)
        assert problems == new + fixed
        n += 1
    assert n == 16
