"""new-case: tests for tools/pr_body_identity.py (offline PR body identity snapshot check).

Data provenance:
- SYNTHETIC: every body built by ``_synthetic_body`` is synthetic test text, not a real PR body.
- HISTORICAL EXCERPTS (not full bodies): ``GROUND_TRACE_EXCERPT`` is the ``## Agent trace`` section
  of PR #654 as read with ``gh pr view 654 --repo artsafro/AGR-DigitalTwin-pilot --json body``
  on 2026-10-24 (the 21:21:45Z corrected body, docs/research/pr-body-cross-card-contamination.md F1);
  ``FACADE_TRACE_EXCERPT`` is the same section of PR #655 read the same way. The excerpts are trimmed,
  so their SHA-256 values are computed here and are NOT the historic body hashes of the report.
- ``GROUND_HEAD`` is the full SHA resolved with ``git rev-parse 34c10acb`` in this repository
  (commit "fix: clearance finding fails on malformed face geometry for every role (#651)"); the
  report only gives the 8-hex prefix ``34c10acb``. ``FACADE_HEAD`` is ``headRefOid`` of PR #655 from
  ``gh pr view 655 --json headRefOid`` (report prefix ``5ea10c13``).
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "pr_body_identity.py"

REPO = "artsafro/AGR-DigitalTwin-pilot"
GROUND_PR = 654
GROUND_CARD = "t_3f8f00e2"
GROUND_BRANCH = "improve/issue-651-ground-footprint-hole"
GROUND_HEAD = "34c10acb8ceebcfb7186fc7a6191fcdd93d4e6ca"
FACADE_CARD = "t_fce04873"
FACADE_HEAD = "5ea10c13b6d708653300cea3725e472c7315744b"

GROUND_TRACE_EXCERPT = (
    "## Agent trace\n"
    "\n"
    "- Card: t_3f8f00e2; profile dt-worker-cursor; driver model claude-sonnet-5-5; "
    "code written by Cursor (grok-4.7-medium)\n"
    "- Commit range: 832578a, 57bafa4, 34c10ac (origin/main..HEAD)\n"
    "- CI: not run (billing lock)\n"
    "\n"
    "Closes #651\n"
)
FACADE_TRACE_EXCERPT = (
    "## Agent trace\n"
    "- Card: t_fce04873; profile dt-worker-cursor; driver model claude-sonnet-5-5\n"
    "- Code written by Cursor (grok-4.7-medium); Cursor rounds: 1; review rounds: 0\n"
    "- Not measured: regression evals (no transcript), CI.\n"
)
GROUND_BODY = (
    "## Summary\n\nGround footprint hole fix (historical excerpt, trimmed).\n\n"
    + GROUND_TRACE_EXCERPT
)
FACADE_BODY = (
    "## Summary\n\nSource-cut legacy four-normal frames; tests/jobs/test_source_cut_legacy_frames.py "
    "(historical excerpt, trimmed).\n\n" + FACADE_TRACE_EXCERPT
)


def _load():
    assert TOOL.is_file(), f"verifier missing: {TOOL}"
    spec = importlib.util.spec_from_file_location("pr_body_identity", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _synthetic_body(trace_lines: list[str] | None, prose: str = "") -> str:
    head = (
        "SYNTHETIC test body - not a real PR description.\n\n## Summary\n\n"
        + prose
        + "\n"
    )
    if trace_lines is None:
        return head
    return head + "\n## Agent trace\n\n" + "".join(line + "\n" for line in trace_lines)


def _expected(body: str, **over) -> dict:
    data = {
        "repo": REPO,
        "pr": GROUND_PR,
        "card": GROUND_CARD,
        "branch": GROUND_BRANCH,
        "head_commit": GROUND_HEAD,
        "body_sha256": _sha(body),
    }
    data.update(over)
    return data


def _observed(body: str, **over) -> dict:
    data = {
        "repo": REPO,
        "pr": GROUND_PR,
        "headRefName": GROUND_BRANCH,
        "headRefOid": GROUND_HEAD,
        "body": body,
    }
    data.update(over)
    return data


def _run(tmp_path, expected, observed, capsys, raw_expected=None, raw_observed=None):
    mod = _load()
    exp = tmp_path / "expected.json"
    obs = tmp_path / "observed.json"
    exp.write_bytes(
        raw_expected
        if raw_expected is not None
        else json.dumps(expected).encode("utf-8")
    )
    obs.write_bytes(
        raw_observed
        if raw_observed is not None
        else json.dumps(observed).encode("utf-8")
    )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    code = mod.main(["--expected", str(exp), "--observed", str(obs)])
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert after == before, "inputs changed or unexpected files written"
    report = json.loads(capsys.readouterr().out)
    return code, report


def _codes(report) -> set[str]:
    return {d["code"] for d in report["diagnostics"]}


@pytest.fixture(autouse=True)
def _no_network_or_subprocess(monkeypatch, request):
    if request.node.name == "test_fresh_process_cli":
        return  # the test itself spawns the CLI; the CLI's own imports are checked by AST below

    def deny(*a, **k):
        raise AssertionError("network/subprocess call from verifier")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(subprocess, "Popen", deny)


# --- frozen acceptance -------------------------------------------------------------------------


def test_ground_snapshot_matches(tmp_path, capsys):
    code, report = _run(
        tmp_path, _expected(GROUND_BODY), _observed(GROUND_BODY), capsys
    )
    assert code == 0
    assert report["identity_match"] is True
    assert report["status"] == "match"
    assert report["observed_card"] == GROUND_CARD
    assert (
        "not authenticated" in report["note"] and "does not authorize" in report["note"]
    )


def test_facade_body_on_ground_pr_is_card_mismatch_even_with_recomputed_hash(
    tmp_path, capsys
):
    # Body hash recomputed to match the foreign body: only the trace card catches it.
    code, report = _run(
        tmp_path, _expected(FACADE_BODY), _observed(FACADE_BODY), capsys
    )
    assert code == 1
    assert report["identity_match"] is False
    assert _codes(report) == {"card_mismatch"}
    assert report["observed_card"] == FACADE_CARD


def test_facade_body_with_ground_hash_is_card_and_body_mismatch(tmp_path, capsys):
    code, report = _run(
        tmp_path, _expected(GROUND_BODY), _observed(FACADE_BODY), capsys
    )
    assert code == 1
    assert _codes(report) == {"card_mismatch", "body_sha256_mismatch"}


@pytest.mark.parametrize(
    ("field", "value", "diag"),
    [
        ("repo", "artsafro/AGR-DigitalTwin", "repo_mismatch"),
        ("pr", 655, "pr_mismatch"),
        (
            "headRefName",
            "improve/source-cut-legacy-four-normal-frames",
            "branch_mismatch",
        ),
        ("headRefOid", FACADE_HEAD, "head_mismatch"),
    ],
)
def test_each_identity_field_changed_alone(tmp_path, capsys, field, value, diag):
    code, report = _run(
        tmp_path,
        _expected(GROUND_BODY),
        _observed(GROUND_BODY, **{field: value}),
        capsys,
    )
    assert code == 1
    assert report["identity_match"] is False
    assert _codes(report) == {diag}


def test_stale_body_hash_is_body_mismatch(tmp_path, capsys):
    stale = GROUND_BODY.replace("trimmed", "stale")
    code, report = _run(tmp_path, _expected(stale), _observed(GROUND_BODY), capsys)
    assert code == 1
    assert _codes(report) == {"body_sha256_mismatch"}


def test_crlf_body_is_not_normalised(tmp_path, capsys):
    crlf = GROUND_BODY.replace("\n", "\r\n")
    code, report = _run(tmp_path, _expected(GROUND_BODY), _observed(crlf), capsys)
    assert code == 1
    assert _codes(report) == {"body_sha256_mismatch"}


@pytest.mark.parametrize(
    ("trace", "diag"),
    [
        (["- Commit range: origin/main..HEAD"], "trace_card_missing"),
        (
            [f"- Card: {GROUND_CARD}; profile dt-worker", f"- Card: {FACADE_CARD}"],
            "trace_card_multiple",
        ),
        ([f"- Card: {GROUND_CARD}", f"- Card: {GROUND_CARD}"], "trace_card_multiple"),
        ([f"- Card: {GROUND_CARD}, {FACADE_CARD}"], "trace_card_multiple"),
    ],
)
def test_trace_card_missing_or_ambiguous_is_invalid(tmp_path, capsys, trace, diag):
    body = _synthetic_body(trace)
    code, report = _run(tmp_path, _expected(body), _observed(body), capsys)
    assert code == 2
    assert report["identity_match"] is False
    assert report["status"] == "invalid"
    assert diag in _codes(report)


@pytest.mark.parametrize(
    "decl", ["- Card: none", "- Card: t_3f8f00e2x", "- Card: T_3F8F00E2", "- Card:"]
)
def test_malformed_trace_card_declaration_is_invalid(tmp_path, capsys, decl):
    body = _synthetic_body([decl])
    code, report = _run(tmp_path, _expected(body), _observed(body), capsys)
    assert code == 2
    assert "trace_card_malformed" in _codes(report)


def test_bold_card_declaration_is_accepted(tmp_path, capsys):
    body = _synthetic_body([f"- **Card:** {GROUND_CARD} (dt-worker)"])
    code, report = _run(tmp_path, _expected(body), _observed(body), capsys)
    assert code == 0, report


def test_no_agent_trace_section_is_invalid(tmp_path, capsys):
    body = _synthetic_body(None, prose=f"- Card: {GROUND_CARD}")
    code, report = _run(tmp_path, _expected(body), _observed(body), capsys)
    assert code == 2
    assert "trace_section_missing" in _codes(report)


def test_two_agent_trace_sections_is_invalid(tmp_path, capsys):
    body = (
        _synthetic_body([f"- Card: {GROUND_CARD}"])
        + "\n## Agent trace\n\n- Card: t_3f8f00e2\n"
    )
    code, report = _run(tmp_path, _expected(body), _observed(body), capsys)
    assert code == 2
    assert "trace_section_multiple" in _codes(report)


def test_card_mentions_outside_agent_trace_are_ignored(tmp_path, capsys):
    prose = f"Related: card {FACADE_CARD}.\n- Card: {FACADE_CARD}\n"
    body = _synthetic_body(
        [
            f"- Card: {GROUND_CARD}; profile dt-worker",
            f"- Notes: mentions {FACADE_CARD}",
        ],
        prose,
    )
    body += "\n## Next\n\n- Card: t_00000000\n"
    code, report = _run(tmp_path, _expected(body), _observed(body), capsys)
    assert code == 0, report
    assert report["observed_card"] == GROUND_CARD


def test_agent_trace_inside_code_fence_is_not_a_section(tmp_path, capsys):
    fenced = "```\n## Agent trace\n- Card: t_fce04873\n```\n"
    body = _synthetic_body([f"- Card: {GROUND_CARD}"], prose=fenced)
    code, report = _run(tmp_path, _expected(body), _observed(body), capsys)
    assert code == 0, report


@pytest.mark.parametrize(
    ("which", "field", "value"),
    [
        ("expected", "pr", True),
        ("expected", "pr", 0),
        ("expected", "pr", "654"),
        ("observed", "pr", True),
        ("expected", "head_commit", "34c10acb"),
        ("observed", "headRefOid", "34c10acb"),
        ("expected", "head_commit", GROUND_HEAD.upper()),
        ("expected", "body_sha256", "265123791241"),
        ("expected", "card", "3f8f00e2"),
        ("expected", "repo", "AGR-DigitalTwin-pilot"),
        ("expected", "branch", ""),
        ("observed", "body", None),
    ],
)
def test_invalid_field_values(tmp_path, capsys, which, field, value):
    exp, obs = _expected(GROUND_BODY), _observed(GROUND_BODY)
    (exp if which == "expected" else obs)[field] = value
    code, report = _run(tmp_path, exp, obs, capsys)
    assert code == 2
    assert report["identity_match"] is False
    assert any(
        d["code"] == "invalid_field" and d["field"] == f"{which}.{field}"
        for d in report["diagnostics"]
    )


@pytest.mark.parametrize("which", ["expected", "observed"])
def test_missing_and_unknown_fields(tmp_path, capsys, which):
    exp, obs = _expected(GROUND_BODY), _observed(GROUND_BODY)
    target = exp if which == "expected" else obs
    target.pop("repo")
    target["extra"] = 1
    code, report = _run(tmp_path, exp, obs, capsys)
    assert code == 2
    fields = {(d["code"], d["field"]) for d in report["diagnostics"]}
    assert ("missing_field", f"{which}.repo") in fields
    assert ("unknown_field", f"{which}.extra") in fields


def test_duplicate_json_key_is_invalid(tmp_path, capsys):
    exp = _expected(GROUND_BODY)
    raw = json.dumps(exp)[:-1] + ', "pr": 655}'
    code, report = _run(
        tmp_path, exp, _observed(GROUND_BODY), capsys, raw_expected=raw.encode()
    )
    assert code == 2
    assert "duplicate_key" in _codes(report)


@pytest.mark.parametrize("raw", [b"", b"[]", b"{not json", b"\xff\xfe"])
def test_unreadable_snapshot_is_invalid(tmp_path, capsys, raw):
    code, report = _run(
        tmp_path, None, _observed(GROUND_BODY), capsys, raw_expected=raw
    )
    assert code == 2
    assert report["identity_match"] is False
    assert _codes(report) & {"invalid_json", "not_an_object"}


def test_lone_surrogate_body_is_invalid(tmp_path, capsys):
    raw_obs = json.dumps(_observed("x")).replace('"x"', '"\\ud800"').encode()
    code, report = _run(tmp_path, _expected("x"), None, capsys, raw_observed=raw_obs)
    assert code == 2
    assert any(d["field"] == "observed.body" for d in report["diagnostics"])


def test_missing_file_and_same_path_are_invalid(tmp_path, capsys):
    mod = _load()
    exp = tmp_path / "expected.json"
    exp.write_text(json.dumps(_expected(GROUND_BODY)), encoding="utf-8")
    code = mod.main(
        ["--expected", str(exp), "--observed", str(tmp_path / "absent.json")]
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 2 and "unreadable_file" in _codes(report)
    alias = tmp_path / "." / "expected.json"
    code = mod.main(["--expected", str(exp), "--observed", str(alias)])
    report = json.loads(capsys.readouterr().out)
    assert code == 2 and "same_input_file" in _codes(report)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["expected.json"]


def test_module_is_stdlib_read_only():
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {
        "subprocess",
        "socket",
        "urllib",
        "http",
        "requests",
        "shutil",
        "tempfile",
    }
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}
    doc = ast.get_docstring(tree) or ""
    assert "new-case" in doc


def test_fresh_process_cli(tmp_path):
    exp = tmp_path / "e.json"
    obs = tmp_path / "o.json"
    exp.write_text(json.dumps(_expected(GROUND_BODY)), encoding="utf-8")
    obs.write_text(json.dumps(_observed(GROUND_BODY)), encoding="utf-8")
    cmd = [sys.executable, str(TOOL), "--expected", str(exp), "--observed", str(obs)]
    ok = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["identity_match"] is True
    obs.write_text(json.dumps(_observed(FACADE_BODY)), encoding="utf-8")
    bad = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["identity_match"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["e.json", "o.json"]
