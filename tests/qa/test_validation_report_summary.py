"""Synthetic ValidationReport fixtures for summary() text. Not a real delivery."""

from twinqa.report import Finding, Stage, ValidationReport

SHA = "0123456789abcdef" + ("0" * 48)


def finding(name, status="pass", observed="seen", expected="wanted", pages=(1,), conflicts=()):
    return Finding(
        name=name,
        status=status,
        observed=observed,
        expected=expected,
        source_pdf_pages=list(pages),
        conflicts=list(conflicts),
    )


def stage(stage_id, gate="blocking", check="synthetic check", findings=(), pages=(1,)):
    return Stage(
        id=stage_id,
        check=check,
        gate=gate,
        source_pdf_pages=list(pages),
        findings=list(findings),
    )


def report(stages, **overrides):
    fields = {
        "profile": "vpm",
        "target": "synthetic-target.fbx",
        "target_sha256": "a" * 64,
        "source_sha256": SHA,
        "source_pdf_verified": True,
        "stages": stages,
        "notes": [],
    }
    fields.update(overrides)
    return ValidationReport(**fields)


def test_all_pass_report_verdict_and_stage_prefixes():
    stages = [
        stage("V001", findings=[finding("mesh_closed")]),
        stage("V002", findings=[finding("uv_in_range")]),
        stage("V003", findings=[finding("tri_budget")]),
    ]
    lines = report(stages).summary().splitlines()
    assert "Verdict: PASSED (exit 0)" in lines[-1]
    stage_lines = [line for line in lines if line.startswith("V00")]
    assert [line.split(" ", 1)[0] for line in stage_lines] == ["V001", "V002", "V003"]
    assert all(line.startswith(f"{sid} [PASS   ]") for line, sid in zip(stage_lines, ("V001", "V002", "V003")))


def test_failing_finding_line_and_not_passed_verdict():
    failed = finding(
        "tri_count",
        status="fail",
        observed="9000",
        expected="7500",
        pages=(12, 14),
    )
    lines = report([stage("V004", findings=[failed])]).summary().splitlines()
    assert "     - fail    tri_count: 9000 (expected: 7500; reg p.12,14)" in lines
    assert lines[-1].startswith("Verdict: NOT PASSED (exit 1)")


def test_pass_findings_hidden_only_when_stage_has_more_than_three():
    crowded = stage(
        "V005",
        findings=[
            finding("alpha", status="pass", observed="a", expected="a"),
            finding("beta", status="pass", observed="b", expected="b"),
            finding("gamma", status="pass", observed="c", expected="c"),
            finding("delta", status="fail", observed="bad", expected="good", pages=(4,)),
        ],
    )
    short = stage(
        "V006",
        findings=[
            finding("epsilon", status="pass", observed="e", expected="e"),
            finding("zeta", status="pass", observed="z", expected="z"),
            finding("eta", status="review", observed="maybe", expected="sure", pages=(5,)),
        ],
    )
    lines = report([crowded, short]).summary().splitlines()
    finding_lines = [line for line in lines if line.startswith("     - ")]
    assert finding_lines == [
        "     - fail    delta: bad (expected: good; reg p.4)",
        "     - pass    epsilon: e (expected: e; reg p.1)",
        "     - pass    zeta: z (expected: z; reg p.1)",
        "     - review  eta: maybe (expected: sure; reg p.5)",
    ]


def test_conflicts_render_inside_parentheses():
    flagged = finding("clearance", pages=(12,), conflicts=(3, 7))
    lines = report([stage("V007", findings=[flagged])]).summary().splitlines()
    match = [line for line in lines if "clearance:" in line]
    assert match == [
        "     - pass    clearance: seen (expected: wanted; reg p.12 conflict #3,7)"
    ]
    assert "; reg p.12 conflict #3,7)" in match[0]


def test_source_pdf_verified_flag_changes_regulation_line():
    stages = [stage("V001", findings=[finding("mesh_closed")])]
    unverified = report(stages, source_pdf_verified=False).summary().splitlines()
    verified = report(stages, source_pdf_verified=True).summary().splitlines()
    unverified_line = next(line for line in unverified if line.startswith("Regulation sha256"))
    verified_line = next(line for line in verified if line.startswith("Regulation sha256"))
    assert unverified_line == (
        "Regulation sha256 0123456789ab... (PDF not found; hash from lock only)"
    )
    assert verified_line == "Regulation sha256 0123456789ab... verified"


def test_manual_review_ids_listed_on_verdict_line_only():
    stages = [
        stage("V001", gate="blocking", findings=[finding("mesh_closed")]),
        stage("V016", gate="manual_review", findings=[finding("sign_off", status="review")]),
        stage("V017", gate="manual_review", findings=[finding("photo", status="review")]),
    ]
    last = report(stages).summary().splitlines()[-1]
    assert "manual checks V016, V017 still need signed review." in last
    assert "V001" not in last


def test_notes_render_one_line_each():
    lines = report(
        [stage("V001", findings=[finding("mesh_closed")])],
        notes=["heights are synthetic", "no source pdf attached"],
    ).summary().splitlines()
    assert [line for line in lines if line.startswith("Note:")] == [
        "Note: heights are synthetic",
        "Note: no source pdf attached",
    ]
