"""Merge-policy classifier (#2038): which bucket a PR takes under docs/agents/MERGE_POLICY.yaml.

new-case: tools/merge_policy.py - read-only merge-policy classifier (no existing pattern).

READ-ONLY. It has no merge capability: the only gh calls allowed are `gh pr view` and `gh pr list`
(`gh_json` raises PermissionError on anything else). Buckets: auto (merges by itself after a CLEAN review
on the current head, under one of Artem's standing consents), artem (only on Artem's explicit word),
never (no automation may merge). Preconditions are reported separately and never change the bucket.

    uv run python tools/merge_policy.py classify --pr 2033 [--json] [--no-card]
    uv run python tools/merge_policy.py observe [--log C:/x/merge-policy-observe/decisions.jsonl]
    uv run python tools/merge_policy.py backtest --limit 10 [--json]

observe: one JSON line per open PR appended to a log OUTSIDE the repo - what it WOULD do; nothing merges.
backtest: classifies recently merged PRs and compares with the lane that actually merged them
(kpi/manual_merge_*.json: hygauto*/redfix* = automatic lane, other batches = Artem's word).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs" / "agents" / "MERGE_POLICY.yaml"
KANBAN_KPI = Path(r"C:/Users/artsafro/hermes_kanban/kpi")
PR_FIELDS = ("number,title,body,baseRefName,headRefName,headRefOid,isDraft,mergeable,additions,deletions,"
             "files,comments,closingIssuesReferences")
READ_ONLY_GH = {("pr", "view"), ("pr", "list")}
NEGATION = re.compile(r"\b(no|not|never|without|none|nor|n't)\b[^.;\n]{0,40}$", re.I)
# A reviewer verdict: "## Review rN ...: CLEAN at <sha>" / "... — **CHANGES NEEDED** ...". Only comments of this shape
# count as a review; an author's "## Review fixes: clean up ..." is not a verdict (#2038 r1 P1-3).
VERDICT_HEAD = re.compile(r"^#+\s*Review\s+r\d+\b", re.I)
VERDICT_CLEAN = re.compile(r"(?:[:—–\-]|\*\*|@\s*`?[0-9a-f]{7,40}`?)\s*\**\s*CLEAN\b")  # uppercase token, not "not clean"
VERDICT_SHA = re.compile(r"(?:\bat|@|\bhead)\W{0,3}([0-9a-f]{7,40})\b", re.I)
PROFILE = re.compile(r"\b(dt-[a-z]+(?:-[a-z]+)*)\b")
QUOTES = "\"'`«“"


def load_policy(path: Path | str | None = None) -> dict:
    return yaml.safe_load(Path(path or POLICY).read_text(encoding="utf-8"))


def gh_json(*args: str):
    """Read-only gh: only `pr view` / `pr list`. Anything else (merge, edit, api, review...) is refused."""
    if tuple(args[:2]) not in READ_ONLY_GH:
        raise PermissionError(f"merge_policy is read-only; refused: gh {' '.join(args[:3])}")
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {(r.stderr or r.stdout).strip()[:300]}")
    return json.loads(r.stdout or "null")


def _match(path: str, globs) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


def _sentence(text: str, start: int, end: int) -> str:
    a = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    ends = [i for i in (text.find(".", end), text.find("\n", end)) if i != -1]
    b = min(ends) if ends else len(text)
    return text[a:b].strip()[:200]


def _text_hits(patterns, text: str) -> list[str]:
    hits = []
    for pat in patterns or ():
        for m in re.finditer(pat, text, re.I):
            prefix = text[max(0, m.start() - 60):m.start()]
            if prefix[-1:] in QUOTES:  # a quoted mention ("changes a delivered model") names the rule, not the PR
                continue
            prefix = re.split(r"[.;\n]", prefix)[-1]
            if NEGATION.search(prefix):
                continue
            hits.append(f'"{_sentence(text, m.start(), m.end())}"')
            break
    return hits


def linked_issues(pr: dict) -> set[int]:
    nums = {i["number"] for i in pr.get("closingIssuesReferences") or [] if i.get("number")}
    nums |= {int(x) for x in re.findall(r"(?:Refs|Closes|Fixes|Resolves)\s+(?:[\w.-]+/[\w.-]+)?#(\d+)",
                                        pr.get("body") or "", re.I)}
    return nums


def author_profile(pr: dict) -> str | None:
    body = pr.get("body") or ""
    m = re.search(r"Written by:[^\n]*\((dt-[a-z-]+)", body) or re.search(r"Agent trace:\s*(dt-[a-z-]+)", body)
    return m.group(1) if m else None


def _same_sha(a: str, b: str) -> bool:
    """Shas match on the full length of the shorter one, minimum 7 chars (#2038 r2 P3)."""
    a, b = a.strip().lower(), b.strip().lower()
    n = min(len(a), len(b))
    return n >= 7 and a[:n] == b[:n]


def last_review(comments) -> dict | None:
    """The last reviewer VERDICT comment (VERDICT_HEAD); other comments with "review" in a heading are skipped."""
    for c in reversed(comments or []):
        body = (c.get("body") or "").strip()
        first = body.splitlines()[0] if body else ""
        if not VERDICT_HEAD.search(first):
            continue
        text = body[:4000]
        p1 = re.search(r"P1/P2/P3\s*=\s*(\d+)", text)
        head = VERDICT_SHA.search(first) or VERDICT_SHA.search(text)
        who = re.search(r"Reviewer:\s*\**\s*(dt-[a-z-]+)", text) or PROFILE.search(first)
        clean = bool(VERDICT_CLEAN.search(first)) and not re.search(r"changes (needed|requested)", first, re.I)
        return {"clean": clean, "p1": int(p1.group(1)) if p1 else None, "head": head.group(1) if head else None,
                "reviewer": who.group(1) if who else None, "first_line": first[:160]}
    return None


def _rule_hits(rule: dict, pr: dict, files: list[str], text: str, ctx: dict) -> list[str]:
    ev: list[str] = []
    if "head_branch" in rule and fnmatch.fnmatchcase(pr.get("headRefName") or "", rule["head_branch"]):
        ev.append(f"head branch {pr.get('headRefName')} ~ {rule['head_branch']}")
    if rule.get("paths"):
        hit = [f for f in files if _match(f, rule["paths"])]
        if hit:
            ev.append("paths: " + ", ".join(hit[:3]) + (f" (+{len(hit) - 3})" if len(hit) > 3 else ""))
    if rule.get("text"):
        ev += [f"text: {h}" for h in _text_hits(rule["text"], text)]
    if rule.get("hygiene_issue"):
        hit = sorted(linked_issues(pr) & ctx["hygiene_issues"])
        if hit:
            ev.append("hygiene queue issue(s): " + ", ".join(f"#{n}" for n in hit))
    if rule.get("card_needs_input"):
        m = re.search(r"needs_input", ctx["card_text"] or "")
        if m:
            ev.append(f'card: "{_sentence(ctx["card_text"], m.start(), m.end())}"')
    if rule.get("all_paths") and files and all(_match(f, rule["all_paths"]) for f in files):
        ev.append(f"all {len(files)} file(s) under " + ", ".join(rule["all_paths"]))
    lines = (pr.get("additions") or 0) + (pr.get("deletions") or 0)
    if rule.get("max_lines") and lines <= ctx["max_lines"]:
        ev.append(f"{lines} changed lines <= {ctx['max_lines']}")
    if rule.get("over_max_lines"):  # paths AND size: both must hold
        if lines <= ctx["max_lines"] or not any(e.startswith("paths: ") for e in ev):
            return []
        ev.append(f"{lines} changed lines > {ctx['max_lines']}")
    return ev


def classify(pr: dict, *, policy: dict, stop_present: bool, hygiene_issues: set[int], card_text: str | None = None) -> dict:
    """Classify with checked card text (empty if no match), or None if unchecked."""
    files = [f["path"] if isinstance(f, dict) else f for f in pr.get("files") or []]
    text = "\n".join([pr.get("title") or "", pr.get("body") or "", card_text or ""])
    ctx = {"hygiene_issues": set(hygiene_issues), "card_text": card_text, "max_lines": policy["max_small_lines"]}
    matched = {}
    for rule in policy["rules"]:
        ev = _rule_hits(rule, pr, files, text, ctx)
        if ev:
            matched[rule["id"]] = ev
    decided = next((r for r in policy["rules"] if r["id"] in matched
                    and not any(u in matched for u in r.get("unless", []))), None)
    if decided:
        bucket, rule_id = decided["bucket"], decided["id"]
        reasons = [{"rule": rule_id, "bucket": bucket, "why": decided["why"], "consent": decided.get("consent"),
                    "evidence": matched[rule_id]}]
    else:
        bucket, rule_id = policy["default_bucket"], "default"
        reasons = [{"rule": "default", "bucket": bucket, "why": policy["default_reason"], "consent": None,
                    "evidence": [f"{len(files)} file(s), {(pr.get('additions') or 0) + (pr.get('deletions') or 0)} lines"]}]
    reasons += [{"rule": k, "bucket": next(r["bucket"] for r in policy["rules"] if r["id"] == k), "also_matched": True,
                 "evidence": v} for k, v in matched.items() if k != rule_id]

    fails = []
    if bucket == "auto" and decided and decided.get("consent") == "small_prs" and card_text is None:
        bucket = "artem"
        reasons[0].update(bucket=bucket, why="card not checked", consent=None)
        fails.append({"id": "card_checked", "reason": "card not checked"})
    if stop_present and rule_id != "red_main_fix":
        fails.append({"id": "main_green", "reason": "STOP_AUTOMERGE present: main red or paused"})
    base = pr.get("baseRefName")
    if base != policy["main_branch"]:
        fails.append({"id": "base_is_main", "reason": f"stacked on {base}: refuse; retarget to main after {base} merges"})
    if pr.get("isDraft"):
        fails.append({"id": "not_draft", "reason": "draft PR"})
    if pr.get("mergeable") != "MERGEABLE":
        fails.append({"id": "mergeable", "reason": f"mergeable = {pr.get('mergeable')}"})
    rv = last_review(pr.get("comments"))
    head = pr.get("headRefOid") or ""
    if rv is None:
        fails.append({"id": "review_clean_on_head", "reason": "no review comment"})
    else:
        if not rv["clean"] or rv["p1"] != 0:
            why = "has no P1/P2/P3 count" if rv["clean"] and rv["p1"] is None else "is not CLEAN"
            fails.append({"id": "review_clean_on_head", "reason": f"last review verdict {why}: {rv['first_line']}"})
        elif not rv["head"] or not head or not _same_sha(head, rv["head"]):
            fails.append({"id": "review_clean_on_head",
                          "reason": f"review names head {rv['head']}, PR head is {head[:8]}"})
    author = author_profile(pr)
    reviewer = rv["reviewer"] if rv else None
    if not author or not reviewer:  # fail closed (#2038 r1 P1-4)
        fails.append({"id": "reviewer_not_author", "reason": "author/reviewer profile unknown: "
                      f"author {author or '? (no Written by / Agent trace profile in body)'}, "
                      f"reviewer {reviewer or '? (no Reviewer: dt-* in the verdict)'}"})
    elif author == reviewer:
        fails.append({"id": "reviewer_not_author", "reason": f"reviewer {reviewer} = author {author}"})
    return {"pr": pr.get("number"), "title": (pr.get("title") or "")[:100], "head": head[:8], "base": base,
            "bucket": bucket, "rule": rule_id, "reasons": reasons, "failed_preconditions": fails,
            "would_merge": bucket == "auto" and not fails, "mode": policy.get("mode", "observe"),
            "author": author, "reviewer": reviewer, "card_checked": card_text is not None}


# ---- environment readers (all read-only) ----

def stop_present(policy: dict) -> bool:
    return Path(policy["stop_file"]).exists()


def hygiene_issues(policy: dict) -> set[int]:
    p = Path(policy["hygiene_queue_file"])
    if not p.exists():
        return set()
    return set(json.loads(p.read_text(encoding="utf-8")).get("issues", []))


HERMES = "C:/Users/artsafro/.hermes/bin/hermes.exe"


def _hermes() -> str:
    return HERMES if Path(HERMES).exists() else "hermes"


def kanban_cards() -> dict | None:
    """branch -> card, via `hermes kanban list` (read-only). None = lookup unavailable (e.g. inside a worker,
    where Hermes refuses board access)."""
    try:
        out = subprocess.run([_hermes(), "kanban", "--board", "agr-pilot", "list", "--json"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=120, check=True).stdout
        if "[" not in out:
            return None
        cards = json.loads(out[out.find("["):])
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return {c["branch_name"]: c for c in cards if c.get("branch_name")}


def lookup_card_text(cards: dict | None, branch: str | None) -> str | None:
    if cards is None:
        return None
    card = cards.get(branch)
    if card is None:
        return ""
    try:
        out = subprocess.run([_hermes(), "kanban", "--board", "agr-pilot", "show", card["id"]], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=120, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return out if out.strip() else None


def observe(prs, *, log_path, policy, stop_present: bool, hygiene_issues: set[int], cards: dict | None) -> list[dict]:
    log = Path(log_path).resolve()
    if log.is_relative_to(ROOT.resolve()):
        raise ValueError(f"observe log must be outside the repository: {log}")
    log.parent.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    rows = []
    for p in sorted(prs, key=lambda x: x["number"]):
        res = classify(p, policy=policy, stop_present=stop_present, hygiene_issues=hygiene_issues,
                       card_text=lookup_card_text(cards, p.get("headRefName")))
        rows.append({"ts": ts, **res})
    with log.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def actual_lane(n: int, comments) -> tuple[str, str]:
    """How a merged PR actually merged: from kpi/manual_merge_*.json batch names, else review comments."""
    for f in sorted(glob.glob(str(KANBAN_KPI / "manual_merge_*.json"))):
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        merged = data.get("merged") if isinstance(data, dict) else None
        name = Path(f).stem.removeprefix("manual_merge_")
        if merged is True:  # older records: the PR number is in the batch name
            merged = [int(x) for x in re.findall(r"(\d{3,5})$", name)]
        if isinstance(merged, list) and n in merged:
            if name.startswith(("hygauto", "redfix")):
                return "auto", f"{Path(f).name} (automatic lane)"
            return "artem", f"{Path(f).name} (batch on Artem's word)"
    # No fallback to review phrases: "Merge waits for Artem" is reviewer boilerplate (#2038 r1 P3).
    return "unknown", "no kpi/manual_merge_*.json record"


def backtest(limit: int, policy: dict) -> dict:
    prs = gh_json("pr", "list", "-R", policy["repo"], "--state", "merged", "--limit", str(limit), "--json", PR_FIELDS)
    hyg, rows = hygiene_issues(policy), []
    for p in prs:
        res = classify(p, policy=policy, stop_present=False, hygiene_issues=hyg)
        lane, src = actual_lane(p["number"], p.get("comments"))
        policy_lane = "auto" if res["bucket"] == "auto" else "artem"  # never is a stricter artem
        rows.append({"pr": p["number"], "title": res["title"][:60], "bucket": res["bucket"], "rule": res["rule"],
                     "actual": lane, "source": src, "agree": None if lane == "unknown" else policy_lane == lane})
    known = [r for r in rows if r["agree"] is not None]
    pct = round(100 * sum(r["agree"] for r in known) / len(known)) if known else None
    return {"rows": rows, "agreement_pct": pct, "known": len(known)}


def _print_classify(res: dict) -> None:
    print(f"PR #{res['pr']} {res['title']}\nbucket: {res['bucket']} (rule {res['rule']}), would merge: "
          f"{res['would_merge']} [mode {res['mode']}: nothing is merged]")
    if res.get("card_checked") is False:
        print("  note: Kanban card not checked")
    for r in res["reasons"]:
        tag = "also" if r.get("also_matched") else "why"
        print(f"  {tag}: {r['rule']} -> {r['bucket']}: " + "; ".join(r["evidence"]))
    for f in res["failed_preconditions"]:
        print(f"  FAILED {f['id']}: {f['reason']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    c.add_argument("--pr", type=int, required=True)
    c.add_argument("--json", action="store_true")
    c.add_argument("--no-card", action="store_true", help="skip the Kanban card lookup")
    o = sub.add_parser("observe")
    o.add_argument("--log", default=None)
    o.add_argument("--no-card", action="store_true")
    b = sub.add_parser("backtest")
    b.add_argument("--limit", type=int, default=10)
    b.add_argument("--json", action="store_true")
    for s in (c, o, b):
        s.add_argument("--policy", default=None)
    a = ap.parse_args(argv)
    pol = load_policy(a.policy)
    if a.cmd == "classify":
        p = gh_json("pr", "view", str(a.pr), "-R", pol["repo"], "--json", PR_FIELDS)
        cards = None if a.no_card else kanban_cards()
        res = classify(p, policy=pol, stop_present=stop_present(pol), hygiene_issues=hygiene_issues(pol),
                       card_text=lookup_card_text(cards, p.get("headRefName")))
        print(json.dumps(res, ensure_ascii=False, indent=1)) if a.json else _print_classify(res)
    elif a.cmd == "observe":
        prs = gh_json("pr", "list", "-R", pol["repo"], "--state", "open", "--limit", "200", "--json", PR_FIELDS)
        rows = observe(prs, log_path=a.log or pol["observe_log"], policy=pol, stop_present=stop_present(pol),
                       hygiene_issues=hygiene_issues(pol), cards=None if a.no_card else kanban_cards())
        print(f"observe: {len(rows)} open PR(s) -> {a.log or pol['observe_log']}; would merge: "
              + (", ".join(f"#{r['pr']}" for r in rows if r["would_merge"]) or "none")
              + ("; some Kanban cards not checked" if any(not r["card_checked"] for r in rows) else ""))
    else:
        res = backtest(a.limit, pol)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            print("| PR | policy bucket (rule) | actual | source | agree |\n|---|---|---|---|---|")
            for r in res["rows"]:
                ag = "n/a" if r["agree"] is None else ("yes" if r["agree"] else "NO")
                print(f"| #{r['pr']} {r['title']} | {r['bucket']} ({r['rule']}) | {r['actual']} | {r['source']} | {ag} |")
            print(f"agreement: {res['agreement_pct']}% of {res['known']} PRs with a known merge lane")
    return 0


if __name__ == "__main__":
    sys.exit(main())
