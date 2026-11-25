"""Trainer A/B probe of one harness edit [D411] (#1924, Harness2 arXiv 2610.14224).

Pattern: n/a | new-case: A/B contrast of two harness variants (rule/skill/doc text) on one trainer etalon.

    uv run agr trainer ab ETALON --ab OLD_DIR NEW_DIR --scope INVARIANT|DOMAIN --out NEW_DIR [--lane codex]
                          [--timeout-s 1800] [--dry-run]

OLD_DIR / NEW_DIR are harness variants: folders of repo-relative files laid over the practice tree (the
`git archive` of origin/main) before the agent starts; an empty folder is the unchanged baseline. Both arms run
the SAME etalon, lane, model and origin/main commit, one after the other; each is scored with `score`
(Blender / Core Console only, never Max). One contrast report `OUT/ab.json` + `OUT/ab.md`: per score step and
per skeleton stage pass/fail with a verdict, first-command tokens, wrong-turns (commands with a non-zero exit),
input tokens, deliverable diff, and the verdict of the edit:
  fixed      a step/stage goes non-pass -> pass (or bypassed -> used) and nothing regresses
  regressed  any step/stage goes pass -> non-pass (or used -> bypassed); a mixed result is regressed
  unchanged  no step/stage changes
  inconclusive  an arm did not finish (timeout, non-zero exit) or could not be scored - never unchanged.
`--scope` tags the edit INVARIANT (entry, context, tools) or DOMAIN (OKS/Ground/MAF/Flora); the two are probed
in separate A/B runs and a path that disagrees with the tag is listed in `scope_warnings`.
Exit codes: 0 report written (any verdict), 2 invalid input (nothing written).
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

SCOPES = ("INVARIANT", "DOMAIN")
STEP_STATUSES = {"pass", "fail", "not_run", "not_measured", "error", "not_applicable"}
DOMAIN_HINT = re.compile(r"(^|[/_.-])(oks|ground|maf|flora|npm|vpm|ucx|site|facade|body)([/_.-]|$)", re.I)
HIDDEN = ("docs/trainer", "tools/qa/form_check/pairs_v1.json")
STEP_ORDER = ("artifact", "readback", "bounds", "topology", "form", "form_v2", "vlm", "package")


class AbError(ValueError):
    """Invalid A/B input: exit 2, nothing written."""


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def variant_files(d):
    """{repo-relative posix path: sha256} of every file in a variant folder; symlinks and .git are refused."""
    d = Path(d)
    out = {}
    for f in sorted(d.rglob("*")):
        rel = f.relative_to(d)
        if f.is_symlink():
            raise AbError(f"variant {d} holds a symlink: {rel.as_posix()}")
        if ".git" in rel.parts:
            raise AbError(f"variant {d} touches .git: {rel.as_posix()}")
        if f.is_file():
            out[rel.as_posix()] = _sha(f)
    return out


def _inside(a, b):
    return a == b or b in a.parents


def check_variants(old, new, out, scope, e):
    """Validate the two variants and the output folder -> {scope, old_files, new_files, edits, scope_warnings}."""
    if scope not in SCOPES:
        raise AbError(f"unknown --scope {scope!r}; one of {list(SCOPES)} (probe INVARIANT and DOMAIN separately)")
    old, new, out = Path(old).resolve(), Path(new).resolve(), Path(out).resolve()
    for d in (old, new):
        if not d.is_dir():
            raise AbError(f"variant is not a folder: {d}")
    if old == new:
        raise AbError(f"--ab OLD and NEW are the same folder: {old}")
    for d in (old, new):
        if _inside(out, d) or _inside(d, out):
            raise AbError(f"--out {out} is inside a variant or holds one: {d}")
    if out.exists():
        raise AbError(f"{out} exists; an A/B writes a NEW folder")
    of, nf = variant_files(old), variant_files(new)
    hidden = [*HIDDEN, *e.get("hidden_repo_paths", [])]
    for rel in sorted(set(of) | set(nf)):
        for h in hidden:
            if rel == h or rel.startswith(h.rstrip("/") + "/"):
                raise AbError(f"variant file {rel} is under a hidden practice path {h}")
    edits = sorted(r for r in set(of) | set(nf) if of.get(r) != nf.get(r))
    if not edits:
        raise AbError("variants are identical: nothing to probe")
    from trainer import scan_tokens  # lazy: trainer imports this module lazily too
    tokens = scan_tokens(e)
    for d, files in ((old, of), (new, nf)):
        for rel in files:
            low = (d / rel).read_bytes().decode("utf-8", errors="replace").lower()
            found = [t for t in tokens if t in low]
            if found:
                raise AbError(f"variant file {rel} names the key: {found[0]!r}")
    if scope == "INVARIANT":
        warn = [r for r in edits if DOMAIN_HINT.search(r)]
    else:
        warn = [r for r in edits if not DOMAIN_HINT.search(r)]
    return {"scope": scope, "old_files": of, "new_files": nf, "edits": edits, "scope_warnings": warn}


# ---------------------------------------------------------------- arm record
def _command_tokens(cmd):
    """First 4 tokens of the command the agent typed (powershell -Command / bash -lc wrappers unwrapped)."""
    m = re.search(r"(?:-Command|-lc|-c)\s+(['\"])(.*)\1\s*$", cmd, re.S)
    inner = m.group(2) if m else cmd
    try:
        toks = shlex.split(inner, posix=True)
    except ValueError:
        toks = inner.split()
    return toks[:4]


def _exit_code(item):
    code = item.get("exit_code")
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def arm_record(run_dir, score_rep):
    """One arm: run.json + events.jsonl + built/ + its score report -> comparable record."""
    d = Path(run_dir)
    try:
        run = json.loads((d / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AbError(f"arm {d}: unreadable run.json ({exc})") from exc
    cmds = []
    ev_path = d / "events.jsonl"
    lines = ev_path.read_text(encoding="utf-8", errors="replace").splitlines() if ev_path.is_file() else []
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        ev = ev.get("ev", ev) if isinstance(ev, dict) else {}
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed" and item.get("type") == "command_execution":
            cmds.append(item)
    wrong = sum(1 for c in cmds if (_exit_code(c) not in (0, None)) or c.get("status") in ("failed", "declined"))
    built = d / "built"
    deliv = {f.relative_to(built).as_posix(): _sha(f) for f in sorted(built.rglob("*")) if f.is_file()} \
        if built.is_dir() else {}
    first = str(cmds[0].get("command", "")) if cmds else ""
    return {"run_dir": str(d).replace("\\", "/"), "exit": run.get("exit"), "lane": run.get("lane"),
            "model": run.get("model"), "origin_main": run.get("origin_main"),
            "tokens_in": int((run.get("tokens") or {}).get("input_tokens", 0) or 0),
            "commands": len(cmds), "wrong_turns": wrong, "first_command": first[:300],
            "first_command_tokens": _command_tokens(first) if first else [],
            "stages_used": list(run.get("stages_used", [])), "stages_bypassed": list(run.get("stages_bypassed", [])),
            "questions": run.get("questions"), "deliverable": deliv, "score": score_rep,
            "harness_variant": run.get("harness_variant")}


# ---------------------------------------------------------------- contrast
def step_verdict(old, new):
    for s in (old, new):
        if s not in STEP_STATUSES:
            raise AbError(f"unknown step status {s!r}")
    if old != "pass" and new == "pass":
        return "fixed"
    if old == "pass" and new != "pass":
        return "regressed"
    return "unchanged"


def _stage_state(arm, s):
    return "used" if s in arm["stages_used"] else "bypassed" if s in arm["stages_bypassed"] else "absent"


def _incomplete(name, arm):
    if arm["exit"] != 0:
        return f"{name} arm did not finish (exit {arm['exit']})"
    sc = arm["score"]
    if not isinstance(sc, dict) or "error" in sc or "steps" not in sc:
        return f"{name} arm not scored: {(sc or {}).get('error', 'no score') if isinstance(sc, dict) else sc}"
    return None


def contrast(old, new, variants):
    """Two arm records + the variant check -> the contrast report (schema trainer-ab/1)."""
    reasons = [r for r in (_incomplete("old", old), _incomplete("new", new)) if r]
    steps, stages = {}, {}
    if not reasons:
        names = [s for s in STEP_ORDER if s in old["score"]["steps"] or s in new["score"]["steps"]]
        names += sorted((set(old["score"]["steps"]) | set(new["score"]["steps"])) - set(names))
        for s in names:
            o = old["score"]["steps"].get(s, {}).get("status", "not_run")
            n = new["score"]["steps"].get(s, {}).get("status", "not_run")
            steps[s] = {"old": o, "new": n, "verdict": step_verdict(o, n)}
    for s in sorted(set(old["stages_used"] + old["stages_bypassed"] + new["stages_used"] + new["stages_bypassed"])):
        o, n = _stage_state(old, s), _stage_state(new, s)
        v = "fixed" if (o != "used" and n == "used") else "regressed" if (o == "used" and n != "used") \
            else "unchanged"
        stages[s] = {"old": o, "new": n, "verdict": v}
    od, nd = old["deliverable"], new["deliverable"]
    deliverable = {"added": sorted(set(nd) - set(od)), "removed": sorted(set(od) - set(nd)),
                   "changed": sorted(k for k in set(od) & set(nd) if od[k] != nd[k]),
                   "same": sorted(k for k in set(od) & set(nd) if od[k] == nd[k])}
    vs = [x["verdict"] for x in (*steps.values(), *stages.values())]
    if reasons:
        verdict = "inconclusive"
    elif "regressed" in vs:
        verdict = "regressed"
    elif "fixed" in vs:
        verdict = "fixed"
    else:
        verdict = "unchanged"

    def delta(k):
        return {"old": old[k], "new": new[k], "delta": new[k] - old[k]}

    return {"schema": "trainer-ab/1", "verdict": verdict, "inconclusive_reason": "; ".join(reasons) or None,
            "edit": {"scope": variants["scope"], "files": variants["edits"],
                     "scope_warnings": variants["scope_warnings"], "verdict": verdict},
            "steps": steps, "stages": stages, "wrong_turns": delta("wrong_turns"), "tokens_in": delta("tokens_in"),
            "commands": delta("commands"),
            "first_command_tokens": {"old": old["first_command_tokens"], "new": new["first_command_tokens"]},
            "first_command": {"old": old["first_command"], "new": new["first_command"]},
            "first_failing_step": {"old": (old["score"] or {}).get("first_failing_step"),
                                   "new": (new["score"] or {}).get("first_failing_step")},
            "deliverable": deliverable, "old": old, "new": new}


def render_md(rep):
    """Human contrast sheet (English; the JSON is the machine record)."""
    e = rep["edit"]
    lines = [f"# Trainer A/B [D411] - {rep.get('etalon', '?')}", "",
             f"Verdict: **{rep['verdict']}**" + (f" ({rep['inconclusive_reason']})" if rep["inconclusive_reason"]
                                                 else ""),
             f"Edit ({e['scope']}): {', '.join(e['files'])}",
             f"Lane / model: {rep['old']['lane']} / {rep['old']['model']}; origin/main {rep.get('origin_main')}", ""]
    if e["scope_warnings"]:
        lines += [f"Scope warnings (path disagrees with {e['scope']}): {', '.join(e['scope_warnings'])}", ""]
    lines += ["| step | old | new | verdict |", "|---|---|---|---|"]
    lines += [f"| {s} | {v['old']} | {v['new']} | {v['verdict']} |" for s, v in rep["steps"].items()]
    lines += ["", "| skeleton stage | old | new | verdict |", "|---|---|---|---|"]
    lines += [f"| {s} | {v['old']} | {v['new']} | {v['verdict']} |" for s, v in rep["stages"].items()]
    lines += ["", "| metric | old | new | delta |", "|---|---|---|---|"]
    lines += [f"| {k} | {rep[k]['old']} | {rep[k]['new']} | {rep[k]['delta']} |"
              for k in ("wrong_turns", "commands", "tokens_in")]
    ff = rep["first_command_tokens"]
    lines += ["", f"First command tokens: old `{' '.join(ff['old'])}` / new `{' '.join(ff['new'])}`",
              f"First failing step: old {rep['first_failing_step']['old']} / new {rep['first_failing_step']['new']}",
              "", "Deliverable diff: " + "; ".join(f"{k} {v}" for k, v in rep["deliverable"].items()), ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- orchestration
def cmd_ab(a, bank, run_fn, score_fn, head_fn):
    """Validate, run old then new on one origin/main commit, score both, write OUT/ab.json + OUT/ab.md."""
    from argparse import Namespace
    e = next((x for x in bank["etalons"] if x["id"] == a.etalon), None)
    if e is None:
        raise AbError(f"unknown etalon {a.etalon!r}")
    if not e.get("practice_ready"):
        raise AbError(f"{e['id']} is not practice_ready")
    variants = check_variants(a.old, a.new, a.out, a.scope, e)
    out = Path(a.out).resolve()
    if a.dry_run:
        print(json.dumps({k: variants[k] for k in ("scope", "edits", "scope_warnings")}))
        return 0
    head = head_fn()
    out.mkdir(parents=True)
    arms = {}
    for name, overlay in (("old", a.old), ("new", a.new)):
        try:
            run_fn(Namespace(etalon=a.etalon, lane=a.lane, out=str(out / name), timeout_s=a.timeout_s,
                             dry_run=False, overlay=str(Path(overlay).resolve()), head=head), bank)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            rep = {"schema": "trainer-ab/1", "etalon": e["id"], "verdict": "inconclusive", "origin_main": head,
                   "inconclusive_reason": f"{name} arm failed before recording: {exc}"}
            (out / "ab.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps(rep), file=sys.stderr)
            return 1
        try:
            rep = score_fn(e, str(out / name / "built"), out / name / "score")
        except ValueError as exc:  # TrainerError (several FBX, missing built): the arm is not scored
            rep = {"error": str(exc)}
        (out / name / "score.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        arms[name] = arm_record(out / name, rep)
    rep = contrast(arms["old"], arms["new"], variants)
    rep.update({"etalon": e["id"], "lane": a.lane, "origin_main": head, "variants": {"old": str(a.old),
                                                                                    "new": str(a.new)}})
    for name in ("old", "new"):
        if arms[name]["origin_main"] not in (None, head):
            rep["verdict"] = rep["edit"]["verdict"] = "inconclusive"
            rep["inconclusive_reason"] = f"{name} arm ran on {arms[name]['origin_main']}, not {head}"
    (out / "ab.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "ab.md").write_text(render_md(rep), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("etalon", "verdict", "wrong_turns", "tokens_in")}))
    return 0
