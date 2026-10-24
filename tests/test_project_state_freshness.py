"""Offline freshness checks for a pinned docs/PROJECT_STATE.md snapshot.

Historical controls cite docs/research/project-state-snapshot-freshness.md
(pilot PR #662): pin dcb9237b08d0036df232fd4e061f34103bc0e9a7, blob
3f9c7474dfbe6905ce576b93e87d32525510ae2c, content commit
c5f5b5192709efbdbcf190b999eb0c7a4fdf8881. GitHub states and shas marked
synthetic below were not re-read from the network.
"""
import hashlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "state" / "project_state_freshness.py"
PIN = "dcb9237b08d0036df232fd4e061f34103bc0e9a7"
BLOB = "3f9c7474dfbe6905ce576b93e87d32525510ae2c"
CONTENT = "c5f5b5192709efbdbcf190b999eb0c7a4fdf8881"
STAMP = "2026-10-21T21:14:40+02:00"
CLOCK = "2026-10-24T03:25:44+00:00"
ORIGIN = "https://github.com/artsafro/AGR-DigitalTwin-pilot.git"
SLUG = "artsafro/AGR-DigitalTwin-pilot"
REPORT = "docs/research/project-state-snapshot-freshness.md"

FROZEN_MERGES = [
    ("a29e633", 515, "Merge pull request #515 from artsafro/job/vyatskaya-tow02-midpoly"),
    ("d64a2b3", 476, "Merge pull request #476 from artsafro/improve/issue-462-report-measured-value-threshold-and-sign"),
    ("ed4d774", 501, "Merge pull request #501 from artsafro/improve/ucx-too-close-exact-boundary"),
    ("c3ac83c", 500, "Merge pull request #500 from artsafro/engine/roof-screen-shell"),
    ("b58fa5d", 499, "Merge pull request #499 from artsafro/experiment/sliver-etalon-check"),
    ("a46bdfd", 498, "Merge pull request #498 from artsafro/docs/research-ucx-sintez-collision-crosscheck-contract"),
    ("b7ed7e9", 497, "Merge pull request #497 from artsafro/improve/ucx-scene-volume-local-frame"),
    ("af6f516", 494, "Merge pull request #494 from artsafro/improve/issue-488-maf-library-one-library-wide-material-id"),
    ("2c9076a", 492, "Merge pull request #492 from artsafro/improve/issue-489-maf-rules-lego-decomposition-inserts-no"),
    ("766d3f6", 496, "Merge pull request #496 from artsafro/docs/research-cursor-wrapper-settings-test-exposure"),
    ("79a01c4", 495, "Merge pull request #495 from artsafro/improve/ucx-scene-routing-controls"),
    ("f704dfa", 493, "Merge pull request #493 from artsafro/improve/issue-487-maf-vatutino-showcase-scene-of-the-exist"),
]
FROZEN_OPENS = [
    (377, "Experiment: Flora texture diagnosis and UV evidence (#369)", "docs/research-flora-texture-diagnosis"),
    (505, "Research: UCX distance: which endpoint reconstructions change a strict boundary verdict?", "docs/research-ucx-distance-endpoint-cancellation"),
    (506, "P3: Align UCX boundary controls with order and mutation scope (#503)", "improve/issue-503-p3-align-ucx-boundary-controls-with-orde"),
    (507, "docs: BODY-Z row reflects bounded mid/VPM roof screen shell (#504)", "improve/issue-504-docs-body-z-row-still-says-mid-vpm-roof"),
    (508, "Research: UCX distance: do edge-edge and plane-projection paths retain independent cancellation witnesses?", "docs/research-ucx-edge-edge-projection-arithmetic"),
    (509, "Correct UCX exact-boundary arithmetic claim to 813 ulps (#502)", "improve/issue-502-p2-correct-ucx-exact-boundary-arithmetic"),
    (513, "Research: Suite slots: why do worker instructions, coordination rules and receipts say 2, 4 and 3?", "docs/research-suite-capacity-provenance-drift"),
    (516, "twinqa V003: VPM Ground triangle limit from the site-area table (reg p.29) (#510)", "improve/issue-510-twinqa-v003-vpm-ground-triangle-limit-fr"),
]
WINDOW_660 = [660, 659, 658, 652, 648, 646, 642, 641, 640, 639, 637, 636]
OPEN_660 = [599, 601, 610, 611, 629, 631, 633, 643, 654, 655, 656, 661]
MERGED_ON_2026_10_24 = [505, 506, 507, 508, 509, 513, 516]
KEYS = [
    "checked_at", "diagnostics", "evidence_missing", "expected_origin", "head",
    "open_window_missing_prs", "open_window_outside_prs", "origin", "pin", "repo",
    "source_timestamp", "stale_merges_prs", "stale_open_prs", "status", "truncated_open",
    "truncated_open_prs", "unexpected_snapshot_merge_prs", "wrong_head",
]


@pytest.fixture
def mod():
    import tools.state.project_state_freshness as freshness
    return freshness


def _full(short, index):
    return (short.lower() + f"{index:033x}")[:40]


def _merge_line(short, number, subject):
    return f"- `{short}` {subject}"


def _open_line(number, title, branch, draft=False):
    suffix = " draft" if draft else ""
    return f"- #{number} {title} [{branch}]{suffix}"


def _snapshot(merges, opens, capability="Capability A (`capability-b01`, codex): synthetic readiness reprint."):
    lines = [
        "# Project state",
        "",
        "## In production",
        "",
        "PR merges do not imply delivery acceptance. Per-object gates stay in `jobs/<ID>/STATE.md`. "
        "Merged pull requests, newest first:",
        *merges,
        "",
        "## Harness",
        "",
        capability,
        "",
        "Open pull requests:",
        *(opens or ["- (none)"]),
        "",
        "## Next step",
        "",
        "Consult the board and the assigned card for the next action.",
        "",
    ]
    return "\n".join(lines)


def _log(rows):
    return "".join(f"{sha}\t{subject}\n" for sha, subject in rows)


def _list_json(numbers):
    return json.dumps([
        {"number": n, "title": f"title {n}", "headRefName": f"branch-{n}", "isDraft": False}
        for n in numbers
    ])


def _views(states):
    return {n: json.dumps({"number": n, "state": state}) for n, state in states.items()}


def _search(total, incomplete=False):
    return json.dumps({"total_count": total, "incomplete_results": incomplete})


class FakeRun:
    def __init__(self, *, pin=PIN, head=None, origin=ORIGIN, blob="", merges="", stamp=STAMP,
                 listing="[]", search=None, views=None, fail=None):
        self.pin = pin
        self.head = PIN if head is None else head
        self.origin = origin
        self.blob = blob
        self.merges = merges
        self.stamp = stamp
        self.listing = listing
        self.search = _search(0) if search is None else search
        self.views = views or {}
        self.fail = fail
        self.calls = []
        self.timeouts = []

    def __call__(self, argv, cwd, timeout):
        self.calls.append(list(argv))
        self.timeouts.append(timeout)
        kind = self.fail(argv) if self.fail else None
        if kind == "timeout":
            raise subprocess.TimeoutExpired(argv, timeout)
        if kind == "oserror":
            raise OSError("synthetic failure")
        if kind == "nonzero":
            return 1, ""
        return 0, self._out(argv)

    def _out(self, argv):
        if argv[:3] == ["git", "rev-parse", "--verify"]:
            return self.pin + "\n"
        if argv == ["git", "rev-parse", "HEAD"]:
            return self.head + "\n"
        if argv == ["git", "remote", "get-url", "origin"]:
            return self.origin + "\n"
        if argv[:2] == ["git", "show"]:
            return self.blob
        if argv[:2] == ["git", "log"] and "--merges" in argv:
            limit = int(argv[argv.index("-n") + 1])
            lines = [line for line in self.merges.splitlines() if line]
            return "".join(line + "\n" for line in lines[:limit])
        if argv[:4] == ["git", "log", "-1", "--format=%cI"]:
            return self.stamp + "\n"
        if argv[:3] == ["gh", "pr", "list"]:
            return self.listing
        if argv[:2] == ["gh", "api"]:
            return self.search
        if argv[:3] == ["gh", "pr", "view"]:
            return self.views[int(argv[3])]
        raise AssertionError(argv)


def _argv(repo, ref="origin/main", origin=SLUG, max_merges=12, timeout=30):
    return [
        "--repo", str(repo), "--ref", ref, "--expected-origin", origin,
        "--max-merges", str(max_merges), "--timeout", str(timeout),
    ]


def _invoke(mod, monkeypatch, fake, repo, **kwargs):
    monkeypatch.setattr(mod, "_run", fake)
    seen = {"n": 0}

    def clock():
        seen["n"] += 1
        return CLOCK

    monkeypatch.setattr(mod, "_now", clock)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mod.main(_argv(repo, **kwargs))
    raw = buf.getvalue()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssertionError(repr(raw[:300])) from exc
    assert list(data) == sorted(data) == KEYS
    assert raw.endswith("\n")
    assert raw.count("\n") == 1
    for call in fake.calls:
        assert mod._argv_allowed(call), call
    return code, data, seen["n"]


def _frozen_blob():
    merges = [_merge_line(s, n, sub) for s, n, sub in FROZEN_MERGES]
    opens = [_open_line(n, t, b) for n, t, b in FROZEN_OPENS]
    return _snapshot(merges, opens)


def _frozen_log():
    return _log([(_full(s, i), sub) for i, (s, _n, sub) in enumerate(FROZEN_MERGES, start=1)])


def _window_660():
    rows = []
    for index, number in enumerate(WINDOW_660):
        if number == 660:
            sha = PIN
            subject = "Merge pull request #660 from artsafro/docs/research-source-new-vertex-quantization-boundary"
        else:
            sha = f"{number:040x}"
            subject = f"Merge pull request #{number} from x/y"
        rows.append((sha, number, subject))
    return rows


def _base(mod, monkeypatch, tmp_path, *, head=None, origin=ORIGIN, blob=None, log=None,
          listing=None, search=None, views=None, fail=None, numbers=None, stamp=STAMP, **kwargs):
    numbers = list(FROZEN_OPENS and [n for n, _t, _b in FROZEN_OPENS]) if numbers is None else numbers
    if blob is None:
        blob = _frozen_blob()
    if log is None:
        log = _frozen_log()
    if views is None:
        views = _views({n: "OPEN" for n in numbers})
    if listing is None:
        listing = _list_json(numbers)
    if search is None:
        try:
            count = len(json.loads(listing))
        except (json.JSONDecodeError, TypeError):
            count = 0
        search = _search(count)
    fake = FakeRun(head=head, origin=origin, blob=blob, merges=log, listing=listing,
                   search=search, views=views, fail=fail, stamp=stamp)
    code, data, clocks = _invoke(mod, monkeypatch, fake, tmp_path, **kwargs)
    return code, data, fake, clocks


def test_docstring_names_new_case_and_report(mod):
    assert "new-case" in mod.__doc__
    assert REPORT in mod.__doc__
    assert PIN in mod.__doc__
    assert BLOB in mod.__doc__
    assert CONTENT in mod.__doc__
    assert mod.OPEN_LIMIT == 12


def test_historical_a_matching_window_is_current(mod, monkeypatch, tmp_path):
    """Synthetic open states: every frozen open row is OPEN and the list matches."""
    code, data, _fake, clocks = _base(mod, monkeypatch, tmp_path)
    assert clocks == 1
    assert code == 0
    assert data["status"] == "current"
    assert data["pin"] == PIN
    assert data["head"] == PIN
    assert data["origin"] == SLUG
    assert data["expected_origin"] == SLUG
    assert data["source_timestamp"] == STAMP
    assert data["checked_at"] == CLOCK
    assert Path(data["repo"]) == tmp_path.resolve()
    assert data["diagnostics"] == []
    assert data["wrong_head"] is False
    assert data["truncated_open"] is False
    assert data["stale_open_prs"] == []
    assert data["stale_merges_prs"] == []
    assert data["truncated_open_prs"] == []
    assert data["evidence_missing"] == []


def test_historical_b_recorded_merges_are_stale_open(mod, monkeypatch, tmp_path):
    states = {n: ("OPEN" if n == 377 else "MERGED") for n, _t, _b in FROZEN_OPENS}
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path,
        listing=_list_json([377]), search=_search(1), views=_views(states))
    assert code == 1
    assert data["status"] == "stale"
    assert data["stale_open_prs"] == MERGED_ON_2026_10_24
    assert "stale_open" in data["diagnostics"]
    assert data["stale_merges_prs"] == []
    assert data["evidence_missing"] == []
    assert data["wrong_head"] is False


def test_historical_c_window_660_coexists_with_stale_open(mod, monkeypatch, tmp_path):
    rows = _window_660()
    states = {n: ("OPEN" if n == 377 else "MERGED") for n, _t, _b in FROZEN_OPENS}
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, log=_log([(sha, sub) for sha, _n, sub in rows]),
        listing=_list_json([377]), search=_search(1), views=_views(states))
    assert code == 1
    assert data["status"] == "stale"
    assert data["stale_merges_prs"] == WINDOW_660
    assert data["stale_merges_prs"][0] == 660
    assert data["stale_open_prs"] == MERGED_ON_2026_10_24
    assert data["diagnostics"] == ["stale_merges", "stale_open"]


def test_historical_d_twelve_open_and_total_29_is_truncated_current(mod, monkeypatch, tmp_path):
    """#377 and #525 stay outside the limit-12 list; their numbers are not fetched."""
    rows = _window_660()
    merges = [_merge_line(sha[:7], n, sub) for sha, n, sub in rows]
    opens = [_open_line(n, f"synthetic title {n}", f"branch-{n}") for n in OPEN_660]
    states = {n: "OPEN" for n in OPEN_660}
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, blob=_snapshot(merges, opens),
        log=_log([(sha, sub) for sha, _n, sub in rows]),
        listing=_list_json(list(reversed(OPEN_660))), search=_search(29),
        views=_views(states), numbers=OPEN_660)
    assert code == 0
    assert data["status"] == "current"
    assert data["truncated_open"] is True
    assert data["truncated_open_prs"] == []
    assert data["diagnostics"] == []
    assert data["wrong_head"] is False


def test_snapshot_open_outside_the_full_window_is_truncation(mod, monkeypatch, tmp_path):
    rows = _window_660()
    merges = [_merge_line(sha[:7], n, sub) for sha, n, sub in rows]
    numbers = OPEN_660 + [377, 525]
    opens = [_open_line(n, f"synthetic title {n}", f"branch-{n}", draft=(n == 525)) for n in numbers]
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, blob=_snapshot(merges, opens),
        log=_log([(sha, sub) for sha, _n, sub in rows]),
        listing=_list_json(OPEN_660), search=_search(29),
        views=_views({n: "OPEN" for n in numbers}), numbers=numbers)
    assert code == 0
    assert data["status"] == "current"
    assert data["truncated_open"] is True
    assert data["truncated_open_prs"] == [377, 525]
    assert data["stale_open_prs"] == []


def test_limit_12_numbers_missing_from_snapshot_are_window_mismatch(mod, monkeypatch, tmp_path):
    """Full open window absent from the snapshot, snapshot opens absent from that window."""
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, listing=_list_json(OPEN_660), search=_search(20),
        views=_views({n: "OPEN" for n, _t, _b in FROZEN_OPENS}))
    assert code == 1
    assert data["status"] == "stale"
    assert data["diagnostics"] == ["open_window_mismatch"]
    assert data["open_window_missing_prs"] == OPEN_660
    assert data["open_window_outside_prs"] == [n for n, _t, _b in FROZEN_OPENS]
    assert data["stale_open_prs"] == []


def test_wrong_head_is_not_current_and_adds_no_age_diagnostic(mod, monkeypatch, tmp_path):
    other = "b" * 40
    code, data, _fake, _clocks = _base(mod, monkeypatch, tmp_path, head=other)
    assert code == 1
    assert data["wrong_head"] is True
    assert data["status"] == "stale"
    assert data["head"] == other
    assert data["diagnostics"] == []
    assert data["stale_open_prs"] == []
    assert data["stale_merges_prs"] == []


def test_origin_slug_mismatch_is_wrong_head(mod, monkeypatch, tmp_path):
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, origin="git@github.com:other/repo.git")
    assert code == 1
    assert data["wrong_head"] is True
    assert data["origin"] == "other/repo"
    assert data["status"] != "current"


def test_origin_casefold_https_and_ssh_match(mod, monkeypatch, tmp_path):
    for remote in (
        "https://github.com/Artsafro/AGR-DigitalTwin-pilot.git",
        "git@github.com:artsafro/AGR-DigitalTwin-pilot.git",
        "ssh://git@github.com/artsafro/AGR-DigitalTwin-pilot",
        "https://github.com/artsafro/AGR-DigitalTwin-pilot/",
    ):
        code, data, _fake, _clocks = _base(mod, monkeypatch, tmp_path, origin=remote)
        assert code == 0, remote
        assert data["wrong_head"] is False
        assert data["status"] == "current"
        assert data["origin"].casefold() == SLUG.casefold()


def test_closed_state_is_stale_open(mod, monkeypatch, tmp_path):
    states = {n: "OPEN" for n, _t, _b in FROZEN_OPENS}
    states[377] = "CLOSED"
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, listing=_list_json([n for n, _t, _b in FROZEN_OPENS if n != 377]),
        search=_search(7), views=_views(states))
    assert data["stale_open_prs"] == [377]
    assert data["status"] == "stale"
    assert code == 1


def test_sha_mismatch_is_stale_merges(mod, monkeypatch, tmp_path):
    rows = [(_full(s, i), sub) for i, (s, _n, sub) in enumerate(FROZEN_MERGES, start=1)]
    sha, subject = rows[0]
    rows[0] = ("c" * 40, subject)
    code, data, _fake, _clocks = _base(mod, monkeypatch, tmp_path, log=_log(rows))
    assert data["stale_merges_prs"] == [515]
    assert data["status"] == "stale"
    assert code == 1


def test_extra_snapshot_merge_is_not_current(mod, monkeypatch, tmp_path):
    blob = _frozen_blob().replace(
        "- `f704dfa`",
        "- `f704dfa` Merge pull request #493 from artsafro/improve/issue-487-maf-vatutino-showcase-scene-of-the-exist\n"
        "- `abc1234` Merge pull request #1 from x/y",
        1)
    # The replace duplicates the subject because the original line already has it.
    # Build explicitly instead.
    merges = [_merge_line(s, n, sub) for s, n, sub in FROZEN_MERGES]
    merges.append(_merge_line("abc1234", 1, "Merge pull request #1 from x/y"))
    opens = [_open_line(n, t, b) for n, t, b in FROZEN_OPENS]
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, blob=_snapshot(merges, opens))
    assert code == 1
    assert data["status"] == "stale"
    assert "stale_merges" in data["diagnostics"]
    assert data["stale_merges_prs"] == []
    assert data["unexpected_snapshot_merge_prs"] == [1]
    assert blob  # historical blob id is cited, not parsed from this synthetic text
    assert BLOB


def test_invalid_source_timestamp_is_evidence_missing(mod, monkeypatch, tmp_path):
    probes = ["not-a-timestamp"]
    hits = 0
    for stamp in probes:
        code, data, _fake, _clocks = _base(mod, monkeypatch, tmp_path, stamp=stamp)
        assert code == 2, stamp
        assert data["status"] == "evidence_missing", stamp
        assert "invalid_timestamp" in data["evidence_missing"]
        assert data["source_timestamp"] is None
        assert data["status"] != "current"
        hits += 1
    assert hits == len(probes), f"{hits}/{len(probes)}"


def test_evidenced_open_union_above_total_is_evidence_missing(mod, monkeypatch, tmp_path):
    """Twelve listed opens plus snapshot #377 and #525 are 14 distinct OPEN PRs."""
    rows = _window_660()
    merges = [_merge_line(sha[:7], n, sub) for sha, n, sub in rows]
    numbers = OPEN_660 + [377, 525]
    opens = [_open_line(n, f"synthetic title {n}", f"branch-{n}") for n in numbers]
    probes = [13]
    hits = 0
    for total in probes:
        code, data, _fake, _clocks = _base(
            mod, monkeypatch, tmp_path, blob=_snapshot(merges, opens),
            log=_log([(sha, sub) for sha, _n, sub in rows]),
            listing=_list_json(OPEN_660), search=_search(total),
            views=_views({n: "OPEN" for n in numbers}), numbers=numbers)
        assert code == 2, total
        assert data["status"] == "evidence_missing"
        assert "total_count_short" in data["evidence_missing"]
        assert data["truncated_open"] is False
        assert data["status"] != "current"
        hits += 1
    assert hits == len(probes), f"{hits}/{len(probes)}"


def test_view_state_array_is_evidence_missing(mod, monkeypatch, tmp_path):
    views = _views({n: "OPEN" for n, _t, _b in FROZEN_OPENS})
    views[377] = json.dumps({"number": 377, "state": []})
    probes = [views]
    hits = 0
    for view in probes:
        code, data, _fake, _clocks = _base(mod, monkeypatch, tmp_path, views=view)
        assert code == 2
        assert data["status"] == "evidence_missing"
        assert "partial_json" in data["evidence_missing"]
        assert data["status"] != "current"
        hits += 1
    assert hits == len(probes), f"{hits}/{len(probes)}"


def test_empty_open_list_with_total_zero_is_current(mod, monkeypatch, tmp_path):
    merges = [_merge_line(s, n, sub) for s, n, sub in FROZEN_MERGES]
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, blob=_snapshot(merges, []),
        listing="[]", search=_search(0), views={}, numbers=[])
    assert code == 0
    assert data["status"] == "current"
    assert data["truncated_open"] is False


def test_empty_open_list_without_total_is_evidence(mod, monkeypatch, tmp_path):
    merges = [_merge_line(s, n, sub) for s, n, sub in FROZEN_MERGES]
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, blob=_snapshot(merges, []),
        listing="[]", search='{"incomplete_results": false}', views={}, numbers=[])
    assert code == 2
    assert data["status"] == "evidence_missing"
    assert data["status"] != "current"


def test_evidence_matrix_never_current(mod, monkeypatch, tmp_path):
    """Fail closed: empty, partial, unsupported, non-finite, and exact-threshold floats."""
    numbers = [n for n, _t, _b in FROZEN_OPENS]
    base_views = _views({n: "OPEN" for n in numbers})
    cases = {
        "gh_nonzero": dict(fail=lambda argv: "nonzero" if argv[0] == "gh" else None),
        "gh_timeout": dict(fail=lambda argv: "timeout" if argv[:2] == ["gh", "api"] else None),
        "gh_oserror": dict(fail=lambda argv: "oserror" if argv[0] == "gh" else None),
        "malformed": dict(listing="{"),
        "partial_view": dict(views={**base_views, 377: '{"number": 377}'}),
        "bool_number": dict(listing='[{"number": true, "title": "t", "headRefName": "b", "isDraft": false}]'),
        "nan_total": dict(search='{"total_count": NaN, "incomplete_results": false}'),
        "inf_total": dict(search='{"total_count": Infinity, "incomplete_results": false}'),
        "threshold_float": dict(search='{"total_count": 12.0, "incomplete_results": false}'),
        "duplicate": dict(listing=_list_json([377, 377])),
        "incomplete": dict(search=_search(8, incomplete=True)),
        "total_short": dict(search=_search(1)),
        "unsupported": dict(blob="# not a snapshot\n"),
        "empty_blob": dict(blob=""),
        "zero_merges": dict(blob=_snapshot([], [_open_line(1, "Title here", "branch")])),
        "missing_blob": dict(fail=lambda argv: "nonzero" if argv[:2] == ["git", "show"] else None),
        "bad_ref": dict(fail=lambda argv: "nonzero" if argv[:3] == ["git", "rev-parse", "--verify"] else None),
        "lowercase_state": dict(views=_views({n: "merged" for n in numbers})),
    }
    hits = 0
    for name, updates in cases.items():
        code, data, _fake, _clocks = _base(mod, monkeypatch, tmp_path, **updates)
        assert code == 2, name
        assert data["status"] == "evidence_missing", name
        assert data["status"] != "current"
        hits += 1
    assert hits == len(cases), f"{hits}/{len(cases)}"


def test_exactly_twelve_matching_opens_is_current_not_truncated(mod, monkeypatch, tmp_path):
    rows = _window_660()
    merges = [_merge_line(sha[:7], n, sub) for sha, n, sub in rows]
    opens = [_open_line(n, f"synthetic title {n}", f"b{n}") for n in OPEN_660]
    code, data, _fake, _clocks = _base(
        mod, monkeypatch, tmp_path, blob=_snapshot(merges, opens),
        log=_log([(sha, sub) for sha, _n, sub in rows]),
        listing=_list_json(OPEN_660), search=_search(12),
        views=_views({n: "OPEN" for n in OPEN_660}), numbers=OPEN_660)
    assert code == 0
    assert data["status"] == "current"
    assert data["truncated_open"] is False


def test_allowlist_never_accepts_forbidden_or_unlisted(mod):
    rng = random.Random(662)
    verbs = ["fetch", "checkout", "pull", "push", "add", "commit", "merge", "status", "rebase", "clean"]
    forbidden = [
        ["git", "fetch", "origin"],
        ["git", "checkout", "main"],
        ["git", "pull"],
        ["git", "push"],
        ["git", "add", "docs/PROJECT_STATE.md"],
        ["git", "commit", "-m", "x"],
        ["git", "merge", "side"],
        ["gh", "pr", "create", "--title", "x"],
        ["gh", "pr", "edit", "1"],
        ["gh", "pr", "merge", "1"],
        ["gh", "pr", "comment", "1", "--body", "x"],
        ["gh", "api", "repos/o/r", "-X", "POST"],
        ["gh", "api", "repos/o/r", "--method", "PATCH"],
        ["gh", "api", "repos/o/r", "--method", "GET"],
        ["git", "show", PIN + ":docs/OTHER.md"],
    ]
    hits = 0
    for argv in forbidden:
        assert mod._argv_allowed(argv) is False
        hits += 1
    for _ in range(80):
        argv = ["git", rng.choice(verbs), rng.choice(verbs)]
        assert mod._argv_allowed(argv) is False
        hits += 1
    for _ in range(40):
        argv = [rng.choice(["git", "gh", "python"]), "pr", rng.choice(["create", "edit", "merge", "comment"])]
        assert mod._argv_allowed(argv) is False
        hits += 1
    assert hits == len(forbidden) + 120, f"{hits}/{len(forbidden) + 120}"
    assert mod._argv_allowed(["git", "rev-parse", "--verify", f"origin/main^{{commit}}"])
    assert mod._argv_allowed(["git", "rev-parse", "HEAD"])
    assert mod._argv_allowed(["git", "remote", "get-url", "origin"])
    assert mod._argv_allowed(["git", "show", f"{PIN}:docs/PROJECT_STATE.md"])
    assert mod._argv_allowed([
        "git", "log", PIN, "--merges", "--grep=^Merge pull request #", "-n", "12", "--format=%H%x09%s"])
    assert mod._argv_allowed(["git", "log", "-1", "--format=%cI", PIN, "--", "docs/PROJECT_STATE.md"])
    assert mod._argv_allowed([
        "gh", "pr", "list", "--repo", SLUG, "--state", "open", "--limit", "12",
        "--json", "number,title,headRefName,isDraft"])
    assert mod._argv_allowed(["gh", "api", f"search/issues?q=repo:{SLUG}+is:pr+is:open&per_page=1"])
    assert mod._argv_allowed(["gh", "pr", "view", "377", "--repo", SLUG, "--json", "number,state"])


def test_runner_refuses_unlisted_without_subprocess(mod, tmp_path):
    code, _out = mod._run(["git", "status", "--porcelain"], tmp_path, 5)
    assert code != 0


def test_clock_once_and_commands_at_most_the_window(mod, monkeypatch, tmp_path):
    hits = 0
    for width in range(1, 13):
        rows = [(_full(s, i), n, sub) for i, (s, n, sub) in enumerate(FROZEN_MERGES, start=1)][:width]
        merges = [_merge_line(s, n, sub) for s, n, sub in [(sha[:7], n, sub) for sha, n, sub in rows]]
        # rows above rebuilt wrong. Use frozen prefix directly.
        prefix = FROZEN_MERGES[:width]
        merges = [_merge_line(s, n, sub) for s, n, sub in prefix]
        log = _log([(_full(s, i), sub) for i, (s, _n, sub) in enumerate(prefix, start=1)])
        opens = FROZEN_OPENS[:2]
        code, data, fake, clocks = _base(
            mod, monkeypatch, tmp_path, blob=_snapshot(merges, [_open_line(n, t, b) for n, t, b in opens]),
            log=log, listing=_list_json([n for n, _t, _b in opens]), search=_search(2),
            views=_views({n: "OPEN" for n, _t, _b in opens}), numbers=[n for n, _t, _b in opens],
            max_merges=width, timeout=7)
        assert clocks == 1
        assert code == 0 and data["status"] == "current"
        limits = [call[call.index("-n") + 1] for call in fake.calls if "--merges" in call]
        assert limits == [str(width)]
        gh_limits = [call[call.index("--limit") + 1] for call in fake.calls if call[:3] == ["gh", "pr", "list"]]
        assert gh_limits == ["12"]
        views = [call[3] for call in fake.calls if call[:3] == ["gh", "pr", "view"]]
        assert len(views) == len(set(views)) == 2
        assert fake.timeouts and all(item == 7 for item in fake.timeouts)
        assert sum(1 for call in fake.calls if call[:2] == ["gh", "api"]) == 1
        hits += 1
    assert hits == 12, f"{hits}/12"


def test_generated_probe_removed_rows_and_flipped_states(mod, monkeypatch, tmp_path):
    rng = random.Random(662)
    k = 24
    hits = 0
    numbers = [n for _s, n, _sub in FROZEN_MERGES]
    opens = [n for n, _t, _b in FROZEN_OPENS]
    for _ in range(k):
        drop = set(rng.sample(numbers, k=rng.randint(1, len(numbers) - 1)))
        flip = set(rng.sample(opens, k=rng.randint(1, len(opens) - 1)))
        kept = [row for row in FROZEN_MERGES if row[1] not in drop]
        merges = [_merge_line(s, n, sub) for s, n, sub in kept]
        open_lines = [_open_line(n, t, b) for n, t, b in FROZEN_OPENS]
        states = {n: ("MERGED" if n in flip else "OPEN") for n in opens}
        still = [n for n in opens if n not in flip]
        code, data, _fake, _clocks = _base(
            mod, monkeypatch, tmp_path, blob=_snapshot(merges, open_lines),
            listing=_list_json(still), search=_search(len(still)), views=_views(states))
        assert data["stale_merges_prs"] == [n for n in numbers if n in drop]
        assert data["stale_open_prs"] == [n for n in opens if n in flip]
        assert data["status"] == "stale"
        assert code == 1
        assert data["evidence_missing"] == []
        hits += 1
    assert hits == k, f"{hits}/{k}"


def test_mocked_run_writes_nothing(mod, monkeypatch, tmp_path):
    before = list(tmp_path.rglob("*"))
    _base(mod, monkeypatch, tmp_path)
    assert list(tmp_path.rglob("*")) == before


def test_invalid_args_exit_2_without_current_json(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_run", lambda *args: (_ for _ in ()).throw(AssertionError("ran")))
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mod.main(["--repo", str(tmp_path), "--ref", "", "--expected-origin", SLUG])
    data = json.loads(buf.getvalue())
    assert code == 2
    assert data["status"] == "evidence_missing"
    assert data["evidence_missing"] == ["invalid_args"]
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mod.main(["--repo", str(tmp_path), "--ref", "HEAD", "--expected-origin", "not a slug"])
    assert code == 2
    assert json.loads(buf.getvalue())["status"] == "evidence_missing"


def test_cli_argument_errors_never_current():
    cases = [
        [],
        ["--repo", ".", "--ref", "HEAD"],
        ["--repo", ".", "--ref", "", "--expected-origin", SLUG],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", "nope"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", "a/b/c"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--max-merges", "0"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--max-merges", "-1"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--max-merges", "NaN"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--max-merges", "inf"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--max-merges", "true"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--max-merges", "12.0"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--timeout", "0"],
        ["--repo", ".", "--ref", "HEAD", "--expected-origin", SLUG, "--timeout", "NaN"],
    ]
    hits = 0
    for argv in cases:
        proc = subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == 2, argv
        assert '"status": "current"' not in proc.stdout
        hits += 1
    assert hits == len(cases), f"{hits}/{len(cases)}"


def _git(repo, *args):
    proc = subprocess.run(
        ["git", "-c", "user.email=freshness@example.com", "-c", "user.name=Freshness",
         "-c", "core.autocrlf=false", *args],
        cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout


def _worktree(repo):
    found = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            found.append(Path(dirpath, name).relative_to(repo).as_posix())
    return sorted(found)


def _fixture_repo(tmp_path, open_numbers):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "remote", "add", "origin", ORIGIN)
    _git(repo, "commit", "--allow-empty", "-m", "base")
    for number in (3, 7):
        _git(repo, "checkout", "-b", f"side-{number}")
        _git(repo, "commit", "--allow-empty", "-m", f"side {number}")
        _git(repo, "checkout", "main")
        _git(repo, "merge", "--no-ff", f"side-{number}", "-m", f"Merge pull request #{number} from x/y")
    log = _git(repo, "log", "HEAD", "--merges", "--grep=^Merge pull request #", "-n", "12", "--format=%H%x09%s")
    merges = []
    for line in log.splitlines():
        sha, subject = line.split("\t", 1)
        number = int(subject.split("#", 1)[1].split()[0])
        merges.append(_merge_line(sha[:7], number, subject))
    opens = [_open_line(n, f"synthetic title {n}", f"branch-{n}") for n in open_numbers]
    path = repo / "docs" / "PROJECT_STATE.md"
    path.parent.mkdir()
    path.write_bytes(_snapshot(merges, opens).encode("utf-8"))
    _git(repo, "add", "docs/PROJECT_STATE.md")
    _git(repo, "commit", "-m", "snapshot")
    return repo, path


def _shim(bin_dir, mode, listing, states, search, view_raw=None):
    py = bin_dir / "gh_shim.py"
    py.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['GH_LOG']).open('a', encoding='utf-8').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if os.environ.get('GH_MODE') == 'fail':\n"
        "    sys.exit(1)\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['pr', 'list']:\n"
        "    sys.stdout.write(os.environ['GH_LIST'])\n"
        "elif args[:2] == ['pr', 'view']:\n"
        "    raw = os.environ.get('GH_VIEW_RAW')\n"
        "    if raw:\n"
        "        sys.stdout.write(raw)\n"
        "    else:\n"
        "        states = json.loads(os.environ['GH_STATES'])\n"
        "        sys.stdout.write(json.dumps({'number': int(args[2]), 'state': states[args[2]]}))\n"
        "elif args[:1] == ['api']:\n"
        "    sys.stdout.write(os.environ['GH_SEARCH'])\n"
        "else:\n"
        "    sys.exit(1)\n",
        encoding="utf-8")
    cmd = bin_dir / "gh.cmd"
    cmd.write_text(
        f'@echo off\r\n"{sys.executable}" "{py}" %*\r\n',
        encoding="utf-8")
    env = os.environ.copy()
    git_dir = str(Path(shutil.which("git")).parent)
    env["PATH"] = str(bin_dir) + os.pathsep + git_dir
    env["GH_LOG"] = str(bin_dir.parent / "gh-log.jsonl")
    env["GH_MODE"] = mode
    env["GH_LIST"] = listing
    env["GH_STATES"] = json.dumps({str(k): v for k, v in states.items()})
    env["GH_SEARCH"] = search
    if view_raw is not None:
        env["GH_VIEW_RAW"] = view_raw
    return env


def _run_cli(repo, env):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--ref", "HEAD",
         "--expected-origin", SLUG, "--timeout", "30"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", env=env)


def _assert_untouched(repo, path, before_files, before_hash, env):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_hash
    assert _worktree(repo) == before_files
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    assert status.stdout == ""
    log = Path(env["GH_LOG"])
    banned = {"fetch", "checkout", "pull", "push", "add", "commit", "merge", "create", "edit", "comment"}
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            args = json.loads(line)
            assert banned.isdisjoint(args)
            assert "-X" not in args and "--method" not in args


def test_cli_fixture_current_stale_and_missing_gh(tmp_path):
    outcomes = []
    for mode, states, listing, total, expect in (
        ("current", {8: "OPEN", 9: "OPEN"}, [8, 9], 2, 0),
        ("stale", {8: "MERGED", 9: "OPEN"}, [9], 1, 1),
        ("fail", {8: "OPEN", 9: "OPEN"}, [8, 9], 2, 2),
    ):
        work = tmp_path / mode
        work.mkdir()
        repo, path = _fixture_repo(work, [8, 9])
        before = _worktree(repo)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        bin_dir = work / "bin"
        bin_dir.mkdir()
        env = _shim(bin_dir, mode, _list_json(listing), states, _search(total))
        proc = _run_cli(repo, env)
        log_text = Path(env["GH_LOG"]).read_text(encoding="utf-8") if Path(env["GH_LOG"]).exists() else ""
        data = json.loads(proc.stdout)
        assert proc.returncode == expect, (mode, proc.stderr, proc.stdout, log_text)
        assert list(data) == sorted(data)
        if mode == "current":
            assert data["status"] == "current" and data["wrong_head"] is False
        elif mode == "stale":
            assert data["status"] == "stale" and data["stale_open_prs"] == [8]
        else:
            assert data["status"] == "evidence_missing"
            assert data["status"] != "current"
        _assert_untouched(repo, path, before, digest, env)
        outcomes.append(mode)
    assert outcomes == ["current", "stale", "fail"]


def test_cli_malformed_json_and_state_type_are_evidence_missing(tmp_path):
    """Fresh process: malformed JSON and a non-string view state stay JSON, exit 2."""
    probes = [
        ("malformed_list", "{", None, [377], 1),
        ("malformed_view", _list_json([377]), "{", [377], 1),
        ("array_state", _list_json([377]), '{"number":377,"state":[]}', [377], 1),
    ]
    hits = 0
    for name, listing, view_raw, numbers, total in probes:
        work = tmp_path / name
        work.mkdir()
        repo, path = _fixture_repo(work, numbers)
        before = _worktree(repo)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        bin_dir = work / "bin"
        bin_dir.mkdir()
        env = _shim(
            bin_dir, "ok", listing, {n: "OPEN" for n in numbers}, _search(total), view_raw=view_raw)
        proc = _run_cli(repo, env)
        data = json.loads(proc.stdout)
        assert proc.returncode == 2, (name, proc.returncode, proc.stderr, proc.stdout)
        assert data["status"] == "evidence_missing", name
        assert data["status"] != "current"
        assert '"status": "current"' not in proc.stdout
        _assert_untouched(repo, path, before, digest, env)
        hits += 1
    assert hits == len(probes), f"{hits}/{len(probes)}"
