"""Fixed synthetic mutation benchmark derived from every regression PASS reference.

Evidence carries no mutation labels. Case metadata lives only in the returned report.
No third-party dependencies; run with ``python tools/evals_mutation.py --json``.
Freeze this file and corpus before optimizing graders. --guard requires a frozen
manifest supplied by --lock and rejects false failures, uncertainty or drift.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from twinqa.evals.graders import GRADERS, EvidenceError  # noqa: E402

SEED = 117


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def records_of(bundle):
    return [json.loads(line) for line in bundle["transcript"].splitlines() if line.strip()]


def block(record):
    content = record.get("message", {}).get("content")
    return content if isinstance(content, list) else []


def assistant(*blocks, **extra):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}, **extra}


def call(name, args, ident):
    return assistant({"type": "tool_use", "name": name, "input": args, "id": ident})


def result(ident, content="ok", error=False):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": ident, "content": content, "is_error": error}]}}


def transcript(bundle, records):
    bundle["transcript"] = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    return bundle


def references():
    for path in sorted((ROOT / "evals").glob("*/task.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec["suite"] != "regression":
            continue
        for ref in spec["references"]:
            bundle = {key: (path.parent / rule["path"]).read_text(encoding="utf-8")
                      for key, rule in ref["evidence"].items()}
            yield spec["grader"], ref["name"], ref["verdict"], bundle


def variants(grader, original, rng):
    """Return (kind, violating, bundle). All transformations preserve unrelated evidence."""
    suffix = f"{rng.getrandbits(64):016x}"
    if "transcript" in original:
        source = records_of(original)
        if grader == "no_hook_denial":
            for kind, decision, legacy, side in [
                ("reject_decision", "reject", False, False), ("deny_decision", "deny", False, False),
                ("legacy_error", None, True, False), ("decision_without_result", "deny", False, False),
                ("subagent_denial", "reject", False, True)]:
                rec = result(suffix, "PreToolUse:Bash hook error: pipeline gate blocked", True)
                if not legacy:
                    rec["permissionDecision"] = {"decision": decision, "source": "hook"}
                if kind == "decision_without_result":
                    rec["message"]["content"] = "Tool refused by pipeline gate"
                rec["isSidechain"] = side
                yield kind, True, transcript(copy.deepcopy(original), source + [rec])
        elif grader == "dcc_skill_loaded":
            for kind in ("wrong_skill", "failed_skill", "sidechain_load", "late_load", "quoted_command"):
                recs = copy.deepcopy(source)
                si = next(i for i, r in enumerate(recs) if any(b.get("name") == "Skill" for b in block(r)))
                ident = block(recs[si])[0]["id"]
                ri = next(i for i, r in enumerate(recs) if any(b.get("tool_use_id") == ident for b in block(r)))
                if kind == "wrong_skill":
                    block(recs[si])[0]["input"]["skill"] = "blender-mcp"
                elif kind == "failed_skill":
                    block(recs[ri])[0]["is_error"] = True
                    recs[ri]["toolUseResult"]["success"] = False
                elif kind == "sidechain_load":
                    recs[si]["isSidechain"] = recs[ri]["isSidechain"] = True
                elif kind == "late_load":
                    recs.append(recs.pop(ri))
                else:
                    recs[si] = assistant({"type": "text", "text":
                        "The documentation says <command-name>/3dsmax-mcp-dev</command-name>."})
                yield kind, True, transcript(copy.deepcopy(original), recs)
        elif grader == "engine_checked":
            for kind in ("wrong_checker", "sidechain_checker", "premature_checker", "failed_checker", "late_checker_result"):
                recs = copy.deepcopy(source)
                ci = next(i for i, r in enumerate(recs) if any(b.get("input", {}).get("subagent_type") == "independent-checker" for b in block(r)))
                ident = block(recs[ci])[0]["id"]
                ri = next(i for i, r in enumerate(recs) if any(b.get("tool_use_id") == ident for b in block(r)))
                if kind == "wrong_checker":
                    block(recs[ci])[0]["input"]["subagent_type"] = "general-purpose"
                elif kind == "sidechain_checker":
                    recs[ci]["isSidechain"] = recs[ri]["isSidechain"] = True
                elif kind == "premature_checker":
                    pair = [recs[ci], recs[ri]]
                    recs = recs[:ci] + recs[ri + 1:]
                    recs[2:2] = pair
                elif kind == "failed_checker":
                    block(recs[ri])[0].update(is_error=True, content="Task failed: unavailable checker")
                else:
                    recs.append(recs.pop(ri))
                yield kind, True, transcript(copy.deepcopy(original), recs)
        elif grader == "source_inspected":
            for kind in ("wrong_agent", "wrong_basename", "wrong_directory", "sidechain_inspector", "failed_inspector"):
                recs = copy.deepcopy(source)
                ci = next(i for i, r in enumerate(recs) if any(b.get("input", {}).get("subagent_type") == "source-inspector" for b in block(r)))
                args = block(recs[ci])[0]["input"]
                if kind == "wrong_agent":
                    args["subagent_type"] = "general-purpose"
                elif kind == "wrong_basename":
                    args["prompt"] = args["prompt"].replace("source.max", "previous.max")
                elif kind == "wrong_directory":
                    args["prompt"] = args["prompt"].replace("obj03", "obj04")
                elif kind == "sidechain_inspector":
                    recs[ci]["isSidechain"] = True
                else:
                    ident = block(recs[ci])[0]["id"]
                    ri = next(i for i, r in enumerate(recs) if any(b.get("tool_use_id") == ident for b in block(r)))
                    block(recs[ri])[0].update(is_error=True, content="Inspection failed: source could not be read")
                yield kind, True, transcript(copy.deepcopy(original), recs)
        elif grader == "failure_stop":
            for kind in ("same_cause", "three_causes", "cd_alias", "output_alias", "quoted_stop"):
                burst = []
                count = 3 if kind == "three_causes" else 2
                for i in range(count + 1):
                    cmd = "python tools/check_mesh.py --object " + suffix
                    if kind == "cd_alias":
                        cmd = 'cd "C:/work" && ' + cmd
                    if kind == "output_alias":
                        cmd += f" --output runs/{i}"
                    burst.append(call("Bash", {"command": cmd}, f"{suffix}-{i}"))
                    if i < count:
                        cause = f"Error: missing field {chr(97 + i)}" if kind == "three_causes" else "AssertionError: invalid normal"
                        burst.append(result(f"{suffix}-{i}", cause, True))
                        if kind == "quoted_stop" and i == count - 1:
                            burst.append(assistant({"type": "text", "text":
                                'The diagnostic contains the phrase "stop record"; I will rerun immediately.'}))
                yield kind, True, transcript(copy.deepcopy(original), source + burst)
        elif grader == "branch_name":
            for kind, branch in [("auto", "codex/quiet-otter-a12b34"), ("invalid_type", "bug/mesh-check"),
                                 ("missing_area", "fix/mesh"), ("incomplete_job", "job/school"), ("main_typo", "main-old")]:
                recs = copy.deepcopy(source)
                ci = next(i for i, r in enumerate(recs) if any(b.get("name") == "Bash" and "git commit" in b.get("input", {}).get("command", "") for b in block(r)))
                recs[ci]["gitBranch"] = branch
                yield kind, True, transcript(copy.deepcopy(original), recs)
        elif grader == "routine_question":
            for kind, question in [
                ("algorithm", "Which algorithm should I use for triangulation?"),
                ("cache", "Which cache strategy should I use for model indexing?"),
                ("pr_structure", "How should I split the PR?"),
                ("hint_threshold", "Which hint threshold should I use?"),
                ("report_format", "Which report format should I use?")]:
                yield kind, True, transcript(copy.deepcopy(original), source + [
                    call("AskUserQuestion", {"questions": [{"question": question}]}, suffix)])
        # Equivalent serialization / unrelated record movement retain complete source evidence.
        yield "key_order", False, transcript(copy.deepcopy(original), [dict(reversed(list(r.items()))) for r in source])
        recs = copy.deepcopy(source)
        # Move an existing metadata-only record, never a causally ordered conversation event.
        meta = next(i for i, rec in enumerate(recs) if rec["type"] not in ("assistant", "user"))
        recs.append(recs.pop(meta))
        yield "unrelated_reordering", False, transcript(copy.deepcopy(original), recs)
        if grader not in ("no_hook_denial",):
            # Uninspected, unchecked, unskilled subagent work is out of procedural scope.
            side = [call("mcp__3dsmax__read", {}, suffix),
                    call("Read", {"file_path": "incoming/unseen.max"}, suffix + "r"),
                    call("Bash", {"command": "python tools/qa/run_benchmark.py"}, suffix + "b"),
                    call("AskUserQuestion", {"questions": [{"question": "Which algorithm?"}]}, suffix + "q")]
            for rec in side:
                rec.update(isSidechain=True, gitBranch="harness/evals-mutation")
            yield "sidechain", False, transcript(copy.deepcopy(original), source + side)
    else:
        view = json.loads(original["pr"])
        if grader == "pr_agent_trace":
            for kind in ("missing_field", "empty_value", "placeholder", "missing_heading", "broken_field_separator"):
                new = copy.deepcopy(view)
                body = new["body"]
                if kind == "missing_field":
                    body = re.sub(r"(?m)^- Sessions:.*\n?", "", body)
                elif kind == "empty_value":
                    body = re.sub(r"(?m)^- Written by:.*", "- Written by: ", body)
                elif kind == "placeholder":
                    body = re.sub(r"(?m)^- Commands:.*", "- Commands: <commands>", body)
                elif kind == "missing_heading":
                    body = body.replace("## Agent trace", "## Execution notes")
                else:
                    body = body.replace("- Retries:", "- Retries =")
                new["body"] = body
                yield kind, True, {**original, "pr": json.dumps(new, ensure_ascii=False)}
        elif grader == "pr_numeric_literals":
            for kind, code in [("integer", "LIMIT = 731"), ("float", "EPS = 0.0731"),
                               ("hex", "MASK = 0xAD17"), ("fstring", 'label = f"{731}"'),
                               ("nested_format", 'label = f"{value:{731}}"')]:
                patch = "\ndiff --git a/src/twinqa/mesh_policy.py b/src/twinqa/mesh_policy.py\n--- a/src/twinqa/mesh_policy.py\n+++ b/src/twinqa/mesh_policy.py\n@@ -0,0 +1 @@\n+" + code + "\n"
                yield kind, True, {**original, "diff": original["diff"] + patch}
        elif grader == "pr_review_rounds":
            for kind, heading in [("plain_review", "Review round 4"), ("codex_review", "Codex review, round 5"),
                                  ("verdict", "Round 6 verdict: changes needed"),
                                  ("markdown", "**Codex review, round 4**"),
                                  ("leading_blank", "\n\n## Review round 7")]:
                new = copy.deepcopy(view)
                new["comments"].append({"body": heading + "\nPlease fix the findings.", "url": "https://example.invalid/" + suffix})
                yield kind, True, {**original, "pr": json.dumps(new, ensure_ascii=False)}
        yield "key_order", False, {**original, "pr": json.dumps(dict(reversed(list(view.items()))), ensure_ascii=False)}
        new = copy.deepcopy(view)
        # Some recorded PRs have no comments. Add neutral prose so reversal is observable.
        comments = new.get("comments", []) + [{"body": "Thanks for the context."}, {"body": "The attachment is readable."}]
        new["comments"] = list(reversed(comments))
        yield "unrelated_reordering", False, {**original, "pr": json.dumps(new, ensure_ascii=False)}


def corpus(seed=SEED):
    rng = random.Random(seed)
    cases = []
    for grader, name, verdict, original in references():
        if verdict != "pass":
            continue
        for kind, violating, bundle in variants(grader, original, rng):
            cases.append({"grader": grader, "reference": name, "kind": kind, "violating": violating,
                          "bundle": bundle, "original_sha256": digest(encode(original))})
    return cases


def grade(grader, bundle, directory, rng):
    evidence = {}
    for key, content in bundle.items():
        path = directory / f"{rng.getrandbits(128):032x}"
        path.write_text(content, encoding="utf-8")
        evidence[key] = [path]
    try:
        return GRADERS[grader][0](evidence)["passed"]
    except EvidenceError:
        return None


def summarize(outcomes):
    mutants = [o for o in outcomes if o["violating"]]
    controls = [o for o in outcomes if not o["violating"]]
    kills = sum(o["passed"] is False for o in mutants)
    false = sum(o["passed"] is False for o in controls)
    uncertain = sum(o["passed"] is None for o in outcomes)
    return {"mutants": len(mutants), "controls": len(controls), "kills": kills,
            "killed": kills / len(mutants) if mutants else 0,
            "false_fail_count": false, "false_fail": false / len(controls) if controls else 0,
            "uncertain": uncertain, "survivors": sum(o["passed"] is True for o in mutants)}


def evaluate(seed=SEED):
    start = time.perf_counter()
    cases = corpus(seed)
    rng = random.Random(seed + 1)
    outcomes, refs = [], []
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        for case in cases:
            passed = grade(case["grader"], case["bundle"], directory, rng)
            outcomes.append({k: v for k, v in case.items() if k != "bundle"} | {"passed": passed})
        for grader, name, verdict, bundle in references():
            refs.append({"grader": grader, "reference": name, "expected": verdict == "pass",
                         "passed": grade(grader, bundle, directory, rng)})
    per_grader = {g: summarize([o for o in outcomes if o["grader"] == g]) for g in sorted(GRADERS)}
    per_kind = {g: {kind: summarize([o for o in outcomes if o["grader"] == g and o["kind"] == kind])
                    for kind in sorted({o["kind"] for o in outcomes if o["grader"] == g})} for g in sorted(GRADERS)}
    return {**summarize(outcomes), "seed": seed, "corpus_sha256": digest(encode(cases)),
            "tool_sha256": digest(Path(__file__).read_bytes()), "per_grader": per_grader,
            "per_kind": per_kind, "outcomes": outcomes, "references": refs,
            "reference_mismatches": sum(r["passed"] is not r["expected"] for r in refs),
            "runtime": time.perf_counter() - start}


def guard(report, lock):
    return (report["false_fail"] == 0 and report["uncertain"] == 0
            and report["reference_mismatches"] == 0
            and all(report[key] == lock[key] for key in ("tool_sha256", "corpus_sha256", "seed")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--guard", action="store_true")
    parser.add_argument("--lock", type=Path, default=ROOT / ".autoresearch-local/frozen.json")
    args = parser.parse_args()
    report = evaluate()
    if args.guard:
        try:
            lock = json.loads(args.lock.read_text(encoding="utf-8"))
            report["guard_passed"] = guard(report, lock)
        except (OSError, KeyError, ValueError):
            report["guard_passed"] = False
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not args.guard or report["guard_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
