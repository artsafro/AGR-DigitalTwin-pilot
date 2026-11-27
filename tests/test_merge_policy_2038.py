"""#2038: team merge policy file + read-only observe classifier (tools/merge_policy.py).

new-case: tests/test_merge_policy_2038.py - tests of the merge-policy classifier.
"""
import json
from pathlib import Path

import pytest

from tools import merge_policy as mp

ROOT = Path(__file__).resolve().parents[1]
HEAD = "5b7a5a7fd00dfeedd00dfeedd00dfeedd00dfeed"


def review(verdict="CLEAN", head=HEAD, extra="", reviewer: str | None = "dt-reviewer"):
    who = f"\nReviewer: {reviewer} (card t_x)." if reviewer else ""
    return {"body": f"## Review r1 — PR #1 (card t_x) — **{verdict}**\n\nHead `{head[:8]}`, base `187a0be3`. "
                    f"P1/P2/P3 = {'0' if verdict == 'CLEAN' else '1'}/0/0.{who}{extra}\n"}


def pr(**kw):
    base = {"number": 1, "title": "fix: something", "body": "## Agent trace\n- Written by: Hermes / Claude (dt-worker, t_x)\n",
            "baseRefName": "main", "headRefName": "fix/issue-1-x", "headRefOid": HEAD, "isDraft": False,
            "mergeable": "MERGEABLE", "additions": 10, "deletions": 2, "files": [{"path": "tools/x.py"}],
            "comments": [review()], "closingIssuesReferences": []}
    base.update(kw)
    return base


def run(p, **kw):
    kw.setdefault("stop_present", False)
    kw.setdefault("hygiene_issues", set())
    kw.setdefault("card_text", "")
    return mp.classify(p, policy=mp.load_policy(), **kw)


def failed(res):
    return {f["id"] for f in res["failed_preconditions"]}


def test_clean_small_pr_would_merge_auto():
    r = run(pr())
    assert r["bucket"] == "auto" and r["rule"] == "small_pr"
    assert failed(r) == set() and r["would_merge"] is True
    assert r["mode"] == "observe"


def test_stacked_pr_refused_with_base_named():
    r = run(pr(baseRefName="feat/issue-9-parent"))
    assert "base_is_main" in failed(r) and r["would_merge"] is False
    msg = next(f["reason"] for f in r["failed_preconditions"] if f["id"] == "base_is_main")
    assert "feat/issue-9-parent" in msg


def test_red_main_refused_but_waived_for_red_main_fix():
    r = run(pr(), stop_present=True)
    assert "main_green" in failed(r) and r["would_merge"] is False
    fix = run(pr(headRefName="fix/red-main-1a7c71ef"), stop_present=True)
    assert fix["rule"] == "red_main_fix" and fix["bucket"] == "auto"
    assert "main_green" not in failed(fix)


def test_author_equals_reviewer_refused():
    r = run(pr(comments=[review(reviewer="dt-worker")]))
    assert "reviewer_not_author" in failed(r) and r["would_merge"] is False
    ok = run(pr(comments=[review(reviewer="dt-reviewer")]))
    assert "reviewer_not_author" not in failed(ok)


def test_review_on_old_head_or_not_clean_refused():
    assert "review_clean_on_head" in failed(run(pr(comments=[review(head="0ad76097aaaa")])))
    assert "review_clean_on_head" in failed(run(pr(comments=[review(verdict="CHANGES NEEDED")])))
    assert "review_clean_on_head" in failed(run(pr(comments=[])))


def test_model_output_path_goes_to_artem():
    r = run(pr(files=[{"path": "jobs/kpp1/output/kpp1_npm_v004.fbx"}]))
    assert r["bucket"] == "artem" and r["rule"] == "delivered_model"
    assert any("jobs/kpp1/output/kpp1_npm_v004.fbx" in e for x in r["reasons"] for e in x["evidence"])


def test_model_text_classifier_quotes_evidence_and_ignores_negation():
    r = run(pr(body="This PR changes the delivered model of KPP1 (new UV)."))
    assert r["rule"] == "delivered_model"
    assert any("changes the delivered model" in e.lower() for x in r["reasons"] for e in x["evidence"])
    neg = run(pr(body="Scorer only. No accepted file changed; it never changes the delivered model."))
    assert neg["rule"] == "small_pr"
    quoted = run(pr(body='Adds classifiers "changes a delivered model" / "changes how agents work".'))
    assert quoted["rule"] == "small_pr"


def test_hygiene_batch_goes_auto():
    p = pr(files=[{"path": "docs/ARCHIVE.md"}, {"path": ".agents/skills/x/SKILL.md"}], additions=300,
           body="Closes #2017", title="Normalize agent skill triggers (#2017)")
    r = run(p, hygiene_issues={2017})
    assert r["bucket"] == "auto" and r["rule"] == "hygiene_queue"


def test_hygiene_batch_touching_model_output_stays_artem():
    p = pr(files=[{"path": "library/maf/bench.json"}], body="Closes #2017")
    assert run(p, hygiene_issues={2017})["bucket"] == "artem"


def test_protected_path_goes_never():
    r = run(pr(files=[{"path": "data/sources/kpp1/plan.dwg"}, {"path": "docs/research/x.md"}]))
    assert r["bucket"] == "never" and r["rule"] == "protected_path"
    assert r["would_merge"] is False
    assert run(pr(files=[{"path": "standards/npm.yaml"}]))["bucket"] == "never"


def test_agent_working_order_goes_artem():
    r = run(pr(files=[{"path": "docs/agents/WORKFLOW.md"}]))
    assert r["bucket"] == "artem" and r["rule"] == "agent_working_order"
    r = run(pr(files=[{"path": ".claude/hooks/guard.py"}]))
    assert r["bucket"] == "artem" and r["rule"] == "agent_hooks"


def test_user_decision_on_card_goes_artem():
    r = run(pr(), card_text="blocked kind=needs_input: Artem must choose A or B")
    assert r["bucket"] == "artem" and r["rule"] == "user_decision_on_card"


def test_research_docs_auto_and_large_code_artem():
    assert run(pr(files=[{"path": "docs/research/a.md"}], additions=900))["rule"] == "research_decision_docs"
    big = run(pr(additions=500))
    assert big["bucket"] == "artem" and big["rule"] == "production_code"


# ---- review r1 (PR #2041) P1-2..P1-5: each was fail-open (auto / would_merge True) ----

@pytest.mark.parametrize("path", [
    "src/dt_ai/geometry/foo.py", "src/dt_ai/materials/foo.py", "jobs/KPP1/hooks/stage2_build.py",
    "jobs/KPP1/build_facade.py", "jobs/KPP1/task-a/hooks/stage3.py", "tools/export/fbx_export.py",
    "jobs/KPP1/textures/wall.png", "jobs/KPP1/passport.json"])
def test_r1_p1_2_model_building_code_goes_artem(path):
    r = run(pr(files=[{"path": path}], additions=50, deletions=10))
    assert (r["bucket"], r["rule"], r["would_merge"]) == ("artem", "delivered_model", False)


@pytest.mark.parametrize("comments", [
    [{"body": "## Review r1: not clean, P1 later\nhead deadbeef1\nReviewer: dt-reviewer\nP1/P2/P3 = 0/0/0"}],
    [{"body": "## Review r1 — PR #1 at deadbeef1: changes needed, P1/P2/P3 = 1/0/0\nReviewer: dt-reviewer"},
     {"body": "## Review fixes: clean up done on head deadbeef1\nWritten by dt-worker"}],
    [{"body": "## Review r1 — PR #1 — CLEAN at deadbeef1\nReviewer: dt-reviewer"}],  # no P1/P2/P3 count
])
def test_r1_p1_3_review_must_be_a_clean_verdict(comments):
    r = run(pr(headRefOid="deadbeef1" + "0" * 31, comments=comments))
    assert "review_clean_on_head" in failed(r) and r["would_merge"] is False


def test_r1_p1_3_real_verdict_shapes_are_read():
    for first in ("## Review r1 (dt-reviewer, card t_7772b586): CLEAN at 5bff6c3a",
                  "## Review r2 — PR #2007 @ 5bff6c3a: **CLEAN**",
                  "## Review r1 — PR #2010 @ `5bff6c3a` — **CLEAN** (P1/P2/P3 = 0/1/2)"):
        r = run(pr(headRefOid="5bff6c3a" + "0" * 32, comments=[{"body": first + "\nP1/P2/P3 = 0/1/2\nReviewer: dt-reviewer"}]))
        assert failed(r) == set(), (first, r["failed_preconditions"])


def test_r1_p1_4_unknown_author_or_reviewer_fails_closed():
    r = run(pr(body="No trace here."))
    assert "reviewer_not_author" in failed(r) and r["would_merge"] is False
    r = run(pr(comments=[review(reviewer=None)]))
    assert "reviewer_not_author" in failed(r) and r["would_merge"] is False


def test_r1_p1_5_hygiene_queue_with_large_production_code_goes_artem():
    p = pr(files=[{"path": "src/dt_ai/cli/agr.py"}], additions=900, body="Closes #2017")
    r = run(p, hygiene_issues={2017})
    assert (r["bucket"], r["rule"], r["would_merge"]) == ("artem", "production_code", False)


# ---- review r2 (PR #2041) P1-A / P1-B: each was fail-open (auto / would_merge True) ----

@pytest.mark.parametrize("path", [".claude/hooks/pretool.py", "tools/hooks/pre_tool.py", "tools/git-hooks/pre-commit"])
def test_r2_p1_a_hygiene_queue_touching_agent_hooks_goes_artem(path):
    r = run(pr(files=[{"path": path}], additions=50, body="Closes #2017"), hygiene_issues={2017})
    assert (r["bucket"], r["rule"], r["would_merge"]) == ("artem", "agent_hooks", False)


@pytest.mark.parametrize("path,rule", [
    ("tools/review/maf_colour_apply_max.py", "delivered_model"), ("tools/review/max_job.py", "delivered_model"),
    ("tools/review/publish.py", "delivered_model"), ("src/dt_ai/publish/bundle.py", "delivered_model"),
    ("tools/merge_policy.py", "agent_hooks"), ("docs/agents/MERGE_POLICY.yaml", "agent_hooks"),
    ("tests/test_merge_policy_2038.py", "agent_hooks")])
def test_r2_p1_b_small_publish_and_policy_code_goes_artem(path, rule):
    r = run(pr(files=[{"path": path}], additions=8, deletions=2))
    assert (r["bucket"], r["rule"], r["would_merge"]) == ("artem", rule, False)


def test_gh_wrapper_is_read_only():
    for bad in (("pr", "merge", "1"), ("api", "-X", "DELETE", "x"), ("pr", "edit", "1"), ("pr", "review", "1")):
        with pytest.raises(PermissionError):
            mp.gh_json(*bad)
    src = (ROOT / "tools" / "merge_policy.py").read_text(encoding="utf-8")
    assert '"merge",' not in src and "'merge'," not in src


def test_observe_appends_jsonl_outside_repo(tmp_path):
    log = tmp_path / "obs" / "decisions.jsonl"
    rows = mp.observe([pr(), pr(number=2, baseRefName="feat/x")], log_path=log, policy=mp.load_policy(),
                      stop_present=False, hygiene_issues=set(), cards={})
    assert len(rows) == 2
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [x["pr"] for x in lines] == [1, 2] and lines[1]["would_merge"] is False
    assert all(x["mode"] == "observe" and "ts" in x for x in lines)
    mp.observe([pr()], log_path=log, policy=mp.load_policy(), stop_present=False, hygiene_issues=set(), cards={})
    assert len(log.read_text(encoding="utf-8").splitlines()) == 3


def test_observe_refuses_log_inside_repo():
    with pytest.raises(ValueError):
        mp.observe([pr()], log_path=ROOT / "decisions.jsonl", policy=mp.load_policy(), stop_present=False,
                   hygiene_issues=set(), cards={})


def test_policy_file_cites_consents_and_buckets():
    pol = mp.load_policy()
    for c in pol["consents"].values():
        assert c["date"] and c["quote"] and c["quote_kind"]
    assert pol["consents"]["small_prs"]["date"] == "2026-11-14"
    assert pol["consents"]["hygiene_queue"]["date"] == "2026-11-25"
    for rule in pol["rules"]:
        assert rule["bucket"] in {"auto", "artem", "never"}
        if rule["bucket"] == "auto":
            assert rule["consent"] in pol["consents"]
    assert {p["id"] for p in pol["preconditions"]} >= {"main_green", "base_is_main", "mergeable",
                                                       "review_clean_on_head", "reviewer_not_author"}
    assert not Path(pol["observe_log"]).resolve().is_relative_to(ROOT)
