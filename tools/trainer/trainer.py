"""Trainer v0 [D387] (#1855): etalon bank, practice runs on a fresh agent, scoring against the hidden key.

Pattern: n/a | new-case: trainer v0 - practice-run recorder and step scorer over existing checkers.

    uv run agr trainer check                      # etalons.json is well-formed (exit 0 / 2)
    uv run agr trainer run ETALON --lane codex --out NEW_DIR [--timeout-s 1800] [--dry-run] [--proxy]
    uv run agr trainer metrics RUN_DIR [--score SCORE.json] [--usd-per-mtok IN OUT]   # [#2066] per-run metrics
    uv run agr trainer score ETALON --built FILE.fbx|DIR --out NEW.json [--png NEW.png] [--vlm] [--date D]
    uv run agr trainer calibrate --out NEW_DIR    # accepted vs rejected of every scorable etalon
    uv run agr trainer ledger [--add SCORE.json --lane L --run RUN_DIR]   # headline: share passed first try
    uv run agr trainer ab ETALON --ab OLD_DIR NEW_DIR --scope INVARIANT|DOMAIN --out NEW_DIR   # [D415] A/B probe

A practice run gets ONLY the task text and the source copies (with --proxy also the User Proxy command
`RUN/proxy/ask.py`, tools/trainer/user_proxy.py [#2066]; never the key, rejected versions or the job's
history: the practice dir is `git archive` + scrub + `git init` with one commit, no origin). Score steps run the existing checkers in
order - artifact (FBX header), readback (`tools/blender/fbx_readback.py`), bounds, topology (quads), form
(surface deviation built<->key, Blender BVH), form_v2 (`tools/qa/form_check` detector when the etalon has a
form-check pair), ucx (UCX present + [D012] budget; target ucx only), vlm (form-check pair judge, both orders; only with --vlm), package (`agr validate`). Only
`pass` counts; `not_run` / `not_measured` / `error` are non-pass, and the first non-pass step is reported.
Exit codes: 0 scored (any verdict), 2 invalid input or alias; `run` exits 0 when the session was recorded.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / "docs/trainer/etalons.json"
LEDGER = ROOT / "docs/trainer/ledger.json"
STEPS = ("holdout", "artifact", "readback", "bounds", "topology", "form", "form_v2", "ucx", "vlm", "package")
STATUSES = {"pass", "fail", "not_run", "not_measured", "error", "not_applicable"}
TOL = {"bounds_m": 0.10, "form_p95_m": 0.05, "form_max_m": 0.30, "quad_share_drop": 0.02}
LANES = {"codex": {"model": "gpt-6.1-terra"}}
# Skeleton stage signatures in agent commands (SKELETONS.md tables); used/bypassed is measured, not claimed.
STAGE_SIGNS = {"sources-dwg": r"plan_from_dxf|dwg_to_dxf", "inspect": r"agr inspect", "body": r"agr body|body_lattice",
               "mesh-quality": r"mesh_quality_observe", "udim": r"udimtile", "vpm-uv": r"vpm_uv",
               "master-qa": r"master_topology", "readback": r"fbx_readback|qa xview",
               "verifier": r"verifier(_views)?\.py", "derive-npm": r"vpm-to-npm|derive (atlas|npm)",
               "build-manifest": r"build-manifest", "package": r"package-(n|v)pm", "validate": r"agr validate|validate_package",
               "checker": r"agr checker|sintez_checker", "skeleton-guard": r"skeleton_guard"}


class TrainerError(ValueError):
    """Invalid input: exit 2, nothing written."""


# ---------------------------------------------------------------- bank
REQ = ("id", "object", "scenario", "status", "practice_ready", "split", "task", "sources", "key", "rejected",
       "dcc_only_steps", "evidence")
DRIVE_BANK_RE = re.compile(r"^[Gg]:/Мой диск/AGR-[^/]+/.+")


def _is_drive_bank_path(path):
    """True only for concrete file paths under G:/Мой диск/AGR-* (no traversal or empty segments)."""
    if not isinstance(path, str) or not path:
        return False
    norm = path.replace("\\", "/")
    if norm.endswith("/"):
        return False
    parts = norm.split("/")
    if any(seg in ("", ".", "..") for seg in parts[1:]):
        return False
    return bool(DRIVE_BANK_RE.fullmatch(norm))


def _practice_paths(e):
    """External file paths declared on an etalon entry."""
    out = []
    for s in e.get("sources", []):
        if isinstance(s, dict):
            out.append(("source", s.get("path")))
    key = e.get("key")
    if isinstance(key, dict):
        out.append(("key", key.get("path")))
        for k, v in key.items():
            if k.startswith("package_") and not k.endswith("_sha256"):
                out.append((f"key.{k}", v))
    for field in ("rejected", "superseded"):
        for item in e.get(field, []):
            if isinstance(item, dict):
                out.append((field, item.get("path")))
    for field in ("stage2_key", "calibration_accepted"):
        item = e.get(field)
        if isinstance(item, dict):
            out.append((field, item.get("path")))
    if e.get("source_png") is not None:
        out.append(("source_png", e["source_png"]))
    return out


def load_bank(path=BANK):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TrainerError(f"{path}: {exc}") from exc
    problems = bank_problems(data)
    if problems:
        raise TrainerError("; ".join(problems))
    return data


def bank_problems(data):
    out = []
    ents = data.get("etalons") if isinstance(data, dict) else None
    if not isinstance(ents, list) or not ents:
        return ["etalons: missing or empty list"]
    seen = set()
    for i, e in enumerate(ents):
        name = e.get("id", f"#{i}") if isinstance(e, dict) else f"#{i}"
        if not isinstance(e, dict):
            out.append(f"{name}: not an object")
            continue
        out += [f"{name}: missing {k}" for k in REQ if k not in e]
        if name in seen:
            out.append(f"{name}: duplicate id")
        seen.add(name)
        if e.get("split") not in ("tuning", "held_out"):
            out.append(f"{name}: split must be tuning|held_out")
        if e.get("status") not in ("complete", "incomplete"):
            out.append(f"{name}: status must be complete|incomplete")
        if e.get("practice_ready") and e.get("status") != "complete":
            out.append(f"{name}: practice_ready needs status complete")
        for s in e.get("sources", []) + ([e["key"]] if isinstance(e.get("key"), dict) else []):
            sha = s.get("sha256")
            if e.get("practice_ready") and not (isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)):
                out.append(f"{name}: {s.get('path')} has no sha256")
        if e.get("practice_ready"):
            for role, p in _practice_paths(e):
                if not _is_drive_bank_path(p):
                    out.append(f"{name}: {role} path {p!r} is outside G:/Мой диск/AGR-*")
        for r in e.get("rejected", []):
            if not r.get("reason") or not r.get("date"):
                out.append(f"{name}: rejected {r.get('version')} needs reason + date")
        if "proxy_answers" in e:
            try:
                proxy_pack(e)
            except TrainerError as exc:
                out.append(f"{name}: {exc}")
    return out + stage_problems(data)


def etalon(bank, eid):
    for e in bank["etalons"]:
        if e["id"] == eid:
            return e
    raise TrainerError(f"unknown etalon {eid!r}; known: {', '.join(x['id'] for x in bank['etalons'])}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- practice run
def secret_tokens(e):
    """Strings that must never reach the agent: key + rejected paths, file names and hashes, hidden repo paths."""
    toks = set()
    for item in [e["key"], *e.get("rejected", []), *e.get("key_aliases", [])]:
        for k in ("path", "sha256"):
            v = item.get(k)
            if v:
                toks.add(str(v))
                if k == "path":
                    toks.add(Path(v).name)
    return {t for t in toks if len(t) >= 6} | set(e.get("hidden_repo_paths", []))


# The bank itself and the form-check pair registry name every key; a practice worktree never contains them.
# tools/trainer (the scorer) names the held-out KEYS_DIR (#1955: isolation by context), so it is hidden too.
ALWAYS_HIDDEN = ("docs/trainer", "tools/qa/form_check/pairs_v1.json", "tools/trainer")


def scan_tokens(e):
    """Content tokens of the hidden key and rejected versions: file names, full paths (both slash forms), sha256
    and its 12-char prefix (pairs_v1.json pins by prefix). Lower-case; matched case-insensitively."""
    toks = set()
    # key_aliases [#2066]: other copies of the key (the accepted delivery folder) that a run must not reach either.
    for item in [e["key"], *e.get("rejected", []), e.get("calibration_accepted") or {}, *e.get("key_aliases", [])]:
        if item.get("path"):
            p = str(item["path"])
            toks |= {p, p.replace("/", "\\"), Path(p).name}
        if item.get("sha256"):
            toks |= {item["sha256"], item["sha256"][:12]}
    toks |= {KEYS_DIR, KEYS_DIR.replace("/", "\\"), KEYS_DIR.replace("/", "\\\\")}  # #1955: never name the keys dir
    return sorted(t.lower() for t in toks if len(t) >= 6)


def leaking_files(wt, tokens):
    """Every file under wt (outside .git/) whose bytes contain any token -> {rel: [tokens]}."""
    hits = {}
    for f in sorted(Path(wt).rglob("*")):
        rel = f.relative_to(wt).as_posix()
        if ".git" in f.relative_to(wt).parts or not f.is_file() or f.is_symlink():
            continue
        low = f.read_bytes().decode("utf-8", errors="replace").lower()
        found = [t for t in tokens if t in low]
        if found:
            hits[rel] = found
    return hits


def scrub_worktree(wt, e):
    """Remove ALWAYS_HIDDEN + the etalon's hidden_repo_paths, then every file that still names the key or a
    rejected version. A second scan must be clean, else TrainerError (exit 2) naming the file. -> removed list."""
    removed = []
    for rel in [*ALWAYS_HIDDEN, *e.get("hidden_repo_paths", [])]:
        p = Path(wt) / rel
        if p.is_dir():
            shutil.rmtree(p)
            removed.append(rel + "/")
        elif p.is_file():
            p.unlink()
            removed.append(rel)
    tokens = scan_tokens(e)
    for rel, found in leaking_files(wt, tokens).items():
        (Path(wt) / rel).unlink()
        removed.append(f"{rel} (names {found[0]})")
    left = leaking_files(wt, tokens)
    if left:
        rel, found = next(iter(left.items()))
        raise TrainerError(f"practice worktree still names the key: {rel} contains {found[0]!r}")
    return removed


def practice_tree(root, head, dst, e):
    """The practice repo: `git archive <head>` extracted into a NEW dst, scrubbed, then `git init` + ONE commit
    of the scrubbed tree - no origin, no history, no shared index/refs with root, so neither `git show
    HEAD:<hidden>` nor `git log --all` reaches the key. -> scrubbed list. Refusal (TrainerError) before commit."""
    import tarfile
    dst = Path(dst)
    if dst.exists():
        raise TrainerError(f"{dst} exists; a practice tree is a NEW folder")
    dst.mkdir(parents=True)
    p = subprocess.Popen(["git", "-C", str(root), "archive", "--format=tar", head], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=p.stdout, mode="r|") as tar:
        tar.extractall(dst, filter="data")
    if p.wait() != 0:
        raise TrainerError(f"git archive {head} failed in {root}")
    scrubbed = scrub_worktree(dst, e)
    env = {**os.environ, "GIT_AUTHOR_NAME": "trainer", "GIT_AUTHOR_EMAIL": "trainer@local",
           "GIT_COMMITTER_NAME": "trainer", "GIT_COMMITTER_EMAIL": "trainer@local"}
    for args in (["init", "-q"], ["config", "core.autocrlf", "false"], ["add", "-A", "-f"],
                 ["commit", "-q", "--no-verify", "-m", "practice tree"]):
        subprocess.run(["git", "-C", str(dst), *args], check=True, capture_output=True, env=env)
    left = leaking_files(dst, scan_tokens(e))
    if left:  # defensive: the committed tree is the scanned tree
        raise TrainerError(f"practice tree still names the key: {next(iter(left))}")
    return scrubbed


def task_text(e, inputs_dir, out_dir, proxy=None):
    """The only prompt a practice agent receives. proxy = RUN/proxy dir when the User Proxy [#2066] answers."""
    lines = [e["task"].strip(), "", f"Inputs (copies of the customer sources, read-only): {inputs_dir}"]
    lines += [f"- {Path(s['path']).name}  sha256 {s['sha256']}" for s in e["sources"]]
    lines += ["", f"Write every result into {out_dir} (new files only).",
              f"Deliverable: {e.get('deliverable', 'one FBX of the result')} in that folder."]
    if proxy is None:
        lines += ["Follow AGENTS.md and docs/agents/SKELETONS.md. You run headless: nobody answers questions; when a",
                  "decision only the user can make blocks you, write the question into QUESTIONS.md in the output",
                  "folder and continue with the documented default or stop. Do not commit or push."]
    else:
        ask = (Path(proxy) / "ask.py").as_posix()
        lines += ["Follow AGENTS.md and docs/agents/SKELETONS.md. You run without a live user. When a decision only",
                  f"the user can make blocks you, ask it: python \"{ask}\" \"<one question>\". The reply is either an",
                  "approved answer with its source or UNRESOLVED (nobody has decided it): then continue with the",
                  "documented default or stop, and write the question into QUESTIONS.md in the output folder.",
                  "Do not commit or push."]
    lines += ["DCC [D389]: AutoCAD Core Console (accoreconsole, headless DWG->DXF via the skeleton's converter)",
              "and Blender are allowed; live 3ds Max is NOT available in a practice run.",
              "Practice gates [D391]: this is a trainer practice run (agr trainer run), not a real job. Where Gate 1",
              "(PartsList confirmation) or BM-12 (first module accepted before replication) would stop you, confirm it",
              "yourself and continue to the deliverable: write parts.json (a valid PartsList, status draft, gate1",
              "empty) in the output folder and add to QUESTIONS.md the line `gate1=practice-self parts.json",
              "sha256=<file SHA-256> approval_sha256=<PartsList.approval_sha256()>`; after the first module add",
              "`bm12=practice-self <module file> sha256=<file SHA-256>`. The hidden-key score replaces the user's",
              "confirmation; it is not acceptance and is valid only inside agr trainer run, never in a real job."]
    if any(Path(s["path"]).suffix.lower() == ".dwg" for s in e["sources"]):
        lines += ["For sources-dwg use dwg_to_dxf.py with --timeout 60 on an isolated DWG copy, with a new",
                  "ASCII work directory and output paths inside the workspace. Run one console at a time.",
                  "Run dxf_intake.py with the source, DXF and dwg-to-dxf/1 receipt before plan_from_dxf.py.",
                  "On any conversion or intake failure, stop at sources-dwg; retain the receipt and log,",
                  "report the source hash and reason, and do not escalate or launch a host fallback."]
    text = "\n".join(lines) + "\n"
    leaks = [t for t in secret_tokens(e) if t in text]
    if KEYS_DIR in _norm(text):
        leaks.append(KEYS_DIR)
    if leaks:
        raise TrainerError(f"task text would leak the key: {sorted(leaks)}")
    return text


# ---------------------------------------------------------------- user proxy [#2066]
# The proxy (tools/trainer/user_proxy.py, copied as RUN/proxy/ask.py) is a separate process with only its pack.
# The trainer builds the pack from the etalon's `proxy_answers` and refuses it unless every answer is verbatim in
# its cited approved source and names neither the key nor the evaluator. The proxy never sees this module.
PROXY_SRC = Path(__file__).resolve().parent / "user_proxy.py"
EVALUATOR_WORDS = (*TOL, "form_v2", "surface_dev", "pairs_v1", "etalon", "first_failing", "held_out", "holdout")


def _flat(s):
    return re.sub(r"\s+", " ", str(s).replace("**", "").replace("`", "")).strip().lower()


def _decision_rows():
    rows = {}
    for line in (ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(D\d+)\s*\|", line)
        if m:
            rows[m.group(1)] = line
    return rows


def proxy_source_text(a, rows=None):
    """Approved text an answer must quote verbatim: a D-row or a repo file (job decisions / fact export)."""
    kind, src = a.get("source_kind"), str(a.get("source", ""))
    if kind == "d_row":
        rows = rows if rows is not None else _decision_rows()
        if src not in rows:
            raise TrainerError(f"proxy answer {a.get('id')}: unknown decision {src!r}")
        return rows[src]
    if kind in ("job_decision", "fact_export"):
        rel = src.split("#", 1)[0]
        f = (ROOT / rel).resolve()
        if Path(rel).is_absolute() or ROOT.resolve() not in f.parents or not f.is_file():
            raise TrainerError(f"proxy answer {a.get('id')}: source file {rel!r} is not a repo file")
        return f.read_text(encoding="utf-8")
    raise TrainerError(f"proxy answer {a.get('id')}: source_kind {kind!r} needs a source text")


def proxy_pack(e):
    """-> user-proxy-pack/1 for the etalon. TrainerError on an invented, leaking or evaluator-naming answer.
    delivery_key answers quote the etalon's accepted-key record (`key.accepted`)."""
    import user_proxy
    rows = _decision_rows()
    tokens = scan_tokens(e)
    answers = []
    for a in e.get("proxy_answers", []):
        text = e["key"].get("accepted", "") if a.get("source_kind") == "delivery_key" else proxy_source_text(a, rows)
        low = json.dumps(a, ensure_ascii=False).lower()
        found = [t for t in tokens if t in low]
        if found:
            raise TrainerError(f"proxy answer {a.get('id')} names the key: {found[0]!r}")
        if _flat(a.get("answer", "")) not in _flat(text):
            raise TrainerError(f"proxy answer {a.get('id')}: not verbatim in its source {a.get('source')!r}")
        crit = [w for w in EVALUATOR_WORDS if w.lower() in low]
        if crit:
            raise TrainerError(f"proxy answer {a.get('id')} names the evaluator: {crit[0]!r}")
        answers.append({k: a[k] for k in sorted(user_proxy.ANSWER_KEYS) if k in a})
    pack = {"schema": "user-proxy-pack/1", "task": e["id"], "answers": answers}
    problems = user_proxy.pack_problems(pack)
    if problems:
        raise TrainerError("proxy pack refused: " + "; ".join(problems))
    return pack


def install_proxy(run_dir, e):
    """RUN/proxy/{ask.py, pack.json}: the proxy process and its approved answers, nothing else. -> dir."""
    d = Path(run_dir) / "proxy"
    d.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(PROXY_SRC, d / "ask.py")
    (d / "pack.json").write_text(json.dumps(proxy_pack(e), ensure_ascii=False, indent=1), encoding="utf-8")
    left = leaking_files(d, scan_tokens(e))
    if left:
        raise TrainerError(f"proxy dir names the key: {next(iter(left))}")
    return d


# ---------------------------------------------------------------- stage-task set [#2066]
STAGE_SETS = {"dev": "tuning", "holdout": "held_out"}


def stage_tasks(bank):
    return (bank.get("stage_tasks") or {}).get("tasks", [])


def stage_problems(bank):
    """dev ~75 % (split tuning) / holdout ~25 % (split held_out, at least one unfamiliar project never in dev)."""
    tasks = stage_tasks(bank)
    if not tasks:
        return []
    ents = {e.get("id"): e for e in bank.get("etalons", []) if isinstance(e, dict)}
    out = []
    for t in tasks:
        tid = t.get("id")
        if t.get("set") not in STAGE_SETS:
            out.append(f"stage {tid}: set must be dev|holdout")
            continue
        e = ents.get(tid)
        if e is None:
            out.append(f"stage {tid}: unknown etalon")
            continue
        if e.get("split") != STAGE_SETS[t["set"]]:
            out.append(f"stage {tid}: {t['set']} needs split {STAGE_SETS[t['set']]}")
        if not e.get("practice_ready"):
            out.append(f"stage {tid}: etalon is not practice_ready")
        bad = [m for m in t.get("metrics", []) if m not in STEPS]
        if bad or not t.get("metrics"):
            out.append(f"stage {tid}: unknown metric {bad or 'none'}")
        if not t.get("project") or not isinstance(t.get("familiar"), bool):
            out.append(f"stage {tid}: needs project and familiar")
    dev_projects = {t.get("project") for t in tasks if t.get("set") == "dev"}
    if not any(t.get("set") == "holdout" and t.get("familiar") is False and t.get("project") not in dev_projects
               for t in tasks):
        out.append("stage set: needs an unfamiliar holdout (a project never in the dev set)")
    return out


# ---------------------------------------------------------------- per-run metrics [#2066]
def _command_items(lines):
    out = []
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        ev = ev.get("ev", ev) if isinstance(ev, dict) else {}
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed" and item.get("type") == "command_execution":
            out.append(item)
    return out


PROXY_PACK_READ = re.compile(r"proxy[/\\]+(pack\.json|log\.jsonl)", re.I)


def stage_metrics(run_dir, score_json=None, usd_per_mtok=None):
    """success, quality score, human interventions, stops by class, tokens/cost, wall time, repeats/errors."""
    run = Path(run_dir)
    r = json.loads((run / "run.json").read_text(encoding="utf-8"))
    ev = run / "events.jsonl"
    items = _command_items(ev.read_text(encoding="utf-8", errors="replace").splitlines()) if ev.is_file() else []
    cmds = [str(i.get("command", "")) for i in items]
    counts = {}
    for c in cmds:
        counts[c] = counts.get(c, 0) + 1
    failed = sum(1 for i in items if (isinstance(i.get("exit_code"), int) and i["exit_code"] != 0)
                 or i.get("status") == "failed")
    log_f = run / "proxy" / "log.jsonl"
    log = [json.loads(x) for x in log_f.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if log_f.is_file() else []
    by_group, unnecessary = {}, {}
    for x in log:
        by_group[x["stop_group"]] = by_group.get(x["stop_group"], 0) + 1
        if x["stop_group"] == "unnecessary":
            unnecessary[x["stop_class"]] = unnecessary.get(x["stop_class"], 0) + 1
    sc = json.loads(Path(score_json).read_text(encoding="utf-8")) if score_json else None
    tok = r.get("tokens", {})
    cost = None
    if usd_per_mtok:
        cost = round((tok.get("input_tokens", 0) * usd_per_mtok[0] + tok.get("output_tokens", 0) * usd_per_mtok[1])
                     / 1e6, 6)
    return {"schema": "trainer-stage-metrics/1", "etalon": r.get("etalon"), "exit": r.get("exit"),
            "success": sc["passed"] if sc else None, "quality_score": sc["score"] if sc else None,
            "first_failing_step": sc["first_failing_step"] if sc else None,
            "proxy": (run / "proxy").is_dir(), "stops": len(log),
            "human_interventions": sum(x["verdict"] == "answered" for x in log),
            "unresolved": sum(x["verdict"] == "unresolved" for x in log),
            "stops_by_group": by_group, "unnecessary_stops": unnecessary,
            "tokens": tok, "cost_usd": cost, "wall_s": r.get("wall_s"), "commands": len(cmds),
            "repeated_commands": sum(1 for n in counts.values() if n > 1), "failed_commands": failed,
            "proxy_pack_reads": sum(1 for c in cmds if PROXY_PACK_READ.search(c))}


# #1955 (orchestrator 2026-11-26): the scorer-only held-out keys (form_v2 key + sections) live on Drive under this
# folder, same Windows account as the builder. Isolation is by context, not ACL: the prompt never names it and the
# scorer fails any run whose builder transcript touches it (`holdout` step). A real ACL is an open item for Artem.
KEYS_DIR = "1855-trainer-v0/keys"


def _norm(s):
    return str(s).replace("\\\\", "/").replace("\\", "/").lower()


def key_markers():
    """Lower-case strings that identify a held-out key read without the literal KEYS_DIR (review #1970 P1-2:
    `cd .../1855-trainer-v0 && cat keys/...`, Join-Path, globs, `find -name heldout-*`): KEYS_DIR, the `heldout-`
    stem, and the basename + pinned sha prefix of every pairs_v1 key/sections file under KEYS_DIR."""
    marks = {KEYS_DIR, "heldout-"}
    cfg = json.loads((ROOT / "tools/qa/form_check/pairs_v1.json").read_text(encoding="utf-8"))
    for pair in cfg.get("pairs", []):
        for f in ("key", "sections"):
            if KEYS_DIR in _norm(pair.get(f, "")):
                marks.add(_norm(pair[f]).rsplit("/", 1)[-1])
                if pair.get(f + "_sha"):
                    marks.add(str(pair[f + "_sha"]).lower())
    return marks


_KEYS_PARENT = KEYS_DIR.split("/")[0]
# a `keys` path component, or a `k...` component carrying a glob (`k*`, `k"*`, `ke?s`); bank dirs such as
# `k2_v002r1` carry no glob and stay clean
_KEYS_COMPONENT = re.compile(r"""(?:^|[\s/"'(,=])(?:keys|k[\w"'-]*[*?\[][^/\s"')]*)(?=[/\s"')]|$)""")
# A literal ancestor of the held-out keys is unsafe unless it continues directly into the bank.
# This also flags cd-to-parent followed by a relative bank path, and the visible ancestor in a
# split path. This is a text audit: it does not resolve variables or evaluate concatenations.
_END = r"""(?=[/\s"')|;&]|$)"""
_BANK = f"{_KEYS_PARENT}/bank{_END}"
_EVIDENCE_BANK = f"agr-evidence/{_BANK}"
# Anchor drive aliases at token start, not inside paths such as C:/g/notes.txt.
# Windows g: also matches drive-relative paths; only the rooted bank path is known safe.
_DRIVE_ROOT = (
    r"""(?:^|[\s"'(,=;|&])(?:-[\w-]+:)?"""
    r"(?:(?:(?:microsoft\.powershell\.core/)?filesystem::)?(?://?\?/)?g:"
    rf"|/(?:cygdrive/|mnt/)?g{_END})"
)
_PARENT_NOT_BANK = re.compile(
    rf"{_DRIVE_ROOT}(?!/мой диск/{_EVIDENCE_BANK})"
    rf"|(?<![\w-])мой диск(?![\w-])(?!/{_EVIDENCE_BANK})"
    rf"|agr-evidence(?!/{_BANK})|{_KEYS_PARENT}(?!/bank{_END})"
)
# A bank-qualified path must not traverse back to a parent.
_DOTDOT = re.compile(r"(?:agr-evidence|1855-trainer-v0)/[^\s\"']*(?:^|/)\.\.(?:/|[\s\"']|$)")


def _reads_key(cmd, marks):
    c = _norm(cmd)
    if any(m in c for m in marks):
        return True
    if _PARENT_NOT_BANK.search(c) or _DOTDOT.search(c):
        return True
    return _KEYS_PARENT in c and bool(_KEYS_COMPONENT.search(c))  # `1855-trainer-v0` + a keys component


def key_dir_reads(run_dir):
    """Builder commands in run_dir/events.jsonl that read the held-out keys (any slash form or case; see
    key_markers and _KEYS_COMPONENT) -> list. None when the run has no transcript."""
    ev = Path(run_dir) / "events.jsonl"
    if not ev.is_file():
        return None
    _, cmds, _ = parse_events(ev.read_text(encoding="utf-8", errors="replace").splitlines())
    marks = key_markers()
    return [c for c in cmds if _reads_key(c, marks)]


def holdout_step(built):
    """A trainer run dir (the nearest ancestor of built with run.json) must have a transcript free of KEYS_DIR reads."""
    run = next((p for p in Path(built).resolve().parents if (p / "run.json").is_file()), None)
    if run is None:
        return step("not_applicable", reason="not inside a trainer run dir (no run.json): no builder transcript")
    reads = key_dir_reads(run)
    if reads is None:
        return step("error", reason=f"trainer run without events.jsonl: {run}")
    return step("fail" if reads else "pass", key_dir_reads=len(reads), commands=reads[:5])


def parse_events(lines):
    """codex exec --json events (optionally wrapped as {"t", "ev"}) -> metrics."""
    tok = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    cmds, msgs = [], []
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        ev = ev.get("ev", ev) if isinstance(ev, dict) else {}
        if ev.get("type") == "turn.completed":
            for k in tok:
                tok[k] += int(ev.get("usage", {}).get(k, 0) or 0)
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed":
            if item.get("type") == "command_execution":
                cmds.append(str(item.get("command", "")))
            elif item.get("type") == "agent_message":
                msgs.append(str(item.get("text", "")))
    return tok, cmds, msgs


def count_questions(text):
    """Numbered/bulleted items of QUESTIONS.md; else lines with '?'."""
    items = [ln for ln in text.splitlines() if re.match(r"\s*(\d+[.)]|[-*])\s", ln)]
    return len(items) if items else sum("?" in ln for ln in text.splitlines())


def stages_used(cmds, scenario_stages):
    joined = "\n".join(cmds)
    used = [s for s, rx in STAGE_SIGNS.items() if re.search(rx, joined)]
    return used, [s for s in scenario_stages if s in STAGE_SIGNS and s not in used]


def new_code_lines(wt):
    """Added .py lines outside jobs/*/hooks/ in the disposable worktree (tracked diff + untracked files)."""
    total, files = 0, []
    num = subprocess.run(["git", "-C", str(wt), "diff", "--numstat"], capture_output=True, text=True).stdout
    for line in num.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[2].endswith(".py") and not re.match(r"jobs/.+/hooks/", parts[2]) \
                and parts[0].isdigit() and int(parts[0]) > 0:
            total += int(parts[0])
            files.append(parts[2])
    unt = subprocess.run(["git", "-C", str(wt), "ls-files", "--others", "--exclude-standard"],
                         capture_output=True, text=True).stdout
    for rel in unt.splitlines():
        if rel.endswith(".py") and not re.match(r"jobs/.+/hooks/", rel):
            total += len((Path(wt) / rel).read_text(encoding="utf-8", errors="replace").splitlines())
            files.append(rel)
    return total, files


def apply_overlay(wt, variant_dir, e):
    """[D415] Lay a harness variant (repo-relative files) over the practice tree and commit it as a second
    commit, so the agent's own diff (new_code_lines) stays separate. Refused (TrainerError) when a file names the
    key or a rejected version. Empty variant = baseline, no commit. -> {rel: sha256}."""
    from trainer_ab import AbError, variant_files
    try:
        files = variant_files(variant_dir)
    except AbError as exc:
        raise TrainerError(str(exc)) from exc
    if not files:
        return {}
    tokens = scan_tokens(e)
    for rel in files:
        low = (Path(variant_dir) / rel).read_bytes().decode("utf-8", errors="replace").lower()
        found = [t for t in tokens if t in low]
        if found:
            raise TrainerError(f"harness variant names the key: {rel} contains {found[0]!r}")
    for rel in files:
        dst = Path(wt) / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(variant_dir) / rel, dst)
    env = {**os.environ, "GIT_AUTHOR_NAME": "trainer", "GIT_AUTHOR_EMAIL": "trainer@local",
           "GIT_COMMITTER_NAME": "trainer", "GIT_COMMITTER_EMAIL": "trainer@local"}
    for args in (["add", "-A", "-f"], ["commit", "-q", "--no-verify", "--allow-empty", "-m", "harness variant"]):
        subprocess.run(["git", "-C", str(wt), *args], check=True, capture_output=True, env=env)
    return files


def origin_main_head():
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "origin/main"], capture_output=True, text=True,
                          check=True).stdout.strip()


def _windows_profile():
    if os.name != "nt":
        return None
    import ctypes

    # Codex resolves the Windows profile through the shell API, not USERPROFILE.
    profile = ctypes.create_unicode_buffer(260)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x28, None, 0, profile)  # CSIDL_PROFILE
    if result != 0 or not profile.value:
        raise TrainerError(f"cannot locate Windows profile for skill isolation (HRESULT {result})")
    return Path(profile.value)


def _windows_skill_config():
    profile = _windows_profile()
    if profile is None:
        return []
    root = profile / ".agents" / "skills"
    # Codex follows directory aliases and matches canonical SKILL.md paths. Visit each
    # physical directory once, including linked skill directories, without reading skill text.
    todo, seen, paths = [root], set(), set()
    while todo:
        directory = todo.pop().resolve()
        if directory in seen:
            continue
        seen.add(directory)
        try:
            for child in directory.iterdir():
                if child.is_dir():
                    todo.append(child)
                elif child.name == "SKILL.md" and child.is_file():
                    paths.add(child.resolve().as_posix())
        except FileNotFoundError:
            if directory != root.resolve():
                raise
    if not paths:
        return []
    entries = ",".join(f"{{path={json.dumps(path, ensure_ascii=False)},enabled=false}}" for path in sorted(paths))
    return ["-c", f"skills.config=[{entries}]"]


def _run_windows_codex(cmd, *, input, stdout, stderr, timeout, env):
    # A seekable stdin keeps the timeout independent of whether the launcher reads the prompt.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as prompt:
        prompt.write(input)
        prompt.seek(0)
        with subprocess.Popen(cmd, stdin=prompt, stdout=stdout, stderr=stderr, env=env) as child:
            try:
                return child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # npm's .CMD launches descendants. Kill the tree while its root still exists.
                try:
                    cleanup = subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], timeout=10,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                             encoding="oem", errors="replace")
                    if cleanup.returncode:
                        print(f"Trainer: taskkill exited {cleanup.returncode}; child tree cleanup unverified: "
                              f"{cleanup.stderr.strip()}", file=stderr)
                except (OSError, subprocess.TimeoutExpired) as error:
                    print(f"Trainer: child tree cleanup failed: {error}", file=stderr)
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                raise


def cmd_run(a, bank):
    e = etalon(bank, a.etalon)
    if not e["practice_ready"]:
        raise TrainerError(f"{e['id']} is not practice_ready ({e.get('missing', 'incomplete')})")
    if a.lane not in LANES:
        raise TrainerError(f"unknown lane {a.lane!r}; known: {sorted(LANES)}")
    out = Path(a.out).resolve()
    if out.exists():
        raise TrainerError(f"{out} exists; a run writes a NEW folder")
    for s in e["sources"]:
        if not Path(s["path"]).is_file():
            raise TrainerError(f"source missing: {s['path']}")
    inputs, built, wt = out / "inputs", out / "built", out / "wt"
    use_proxy = bool(getattr(a, "proxy", False))
    text = task_text(e, inputs, built, proxy=out / "proxy" if use_proxy else None)
    if a.dry_run:
        if use_proxy:
            n = len(proxy_pack(e)["answers"])  # built and leak-checked, not written
            print(f"[proxy: {n} approved answers; pack checked, nothing written]")
        print(text)
        return 0
    inputs.mkdir(parents=True)
    built.mkdir()
    for s in e["sources"]:
        dst = inputs / Path(s["path"]).name
        shutil.copyfile(s["path"], dst)
        if sha256(dst) != s["sha256"]:
            raise TrainerError(f"source hash mismatch: {s['path']}")
    head = getattr(a, "head", None) or origin_main_head()
    # archive -> scrub -> git init + one commit: no shared index/history/refs with ROOT, no origin
    scrubbed = practice_tree(ROOT, head, wt, e)
    overlay = apply_overlay(wt, a.overlay, e) if getattr(a, "overlay", None) else None
    if use_proxy:
        install_proxy(out, e)
    (out / "prompt.txt").write_text(text, encoding="utf-8")
    cmd = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--disable", "memories", "-m",
           LANES[a.lane]["model"], "-c", "model_reasoning_effort=high", "--dangerously-bypass-approvals-and-sandbox",
           "--skip-git-repo-check", "-C", str(wt), "--add-dir", str(out), "--json", "-o", str(out / "last.txt"),
           *_windows_skill_config(), "-"]
    t0 = time.time()
    # --ignore-user-config does not suppress home skill discovery. Redirect both POSIX and
    # Windows homes for the child only, leaving the practice repository's own skills in place.
    auth = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "auth.json"
    # Windows sharing violations must not mask the exit receipt. Report any surviving directory below.
    with tempfile.TemporaryDirectory(prefix="trainer-codex-", ignore_cleanup_errors=os.name == "nt") as private:
        home = Path(private).resolve()
        codex_home = home / ".codex"
        codex_home.mkdir()
        if auth.is_file():
            # Preserve file-backed login, not user config, skills or session data. Keep it out of the run evidence.
            shutil.copyfile(auth, codex_home / "auth.json")
        env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "CODEX_HOME": str(codex_home)}
        with (out / "events.jsonl").open("w", encoding="utf-8") as ev, \
                (out / "stderr.txt").open("w", encoding="utf-8") as er:
            try:
                if os.name == "nt":
                    rc = _run_windows_codex([shutil.which("codex") or "codex", *cmd[1:]], input=text,
                                            stdout=ev, stderr=er, timeout=a.timeout_s, env=env)
                else:
                    rc = subprocess.run(cmd, input=text, stdout=ev, stderr=er, text=True, encoding="utf-8",
                                        timeout=a.timeout_s, env=env).returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
    if home.exists():
        message = f"Trainer: temporary Codex home cleanup incomplete; inspect and remove {home}"
        with (out / "stderr.txt").open("a", encoding="utf-8") as er:
            print(message, file=er)
        if rc != "timeout":
            raise TrainerError(message)
    wall = round(time.time() - t0, 1)
    tok, cmds, msgs = parse_events((out / "events.jsonl").read_text(encoding="utf-8", errors="replace").splitlines())
    scen = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))["cells"].get(
        e["scenario"], {}).get("stages", [])
    used, bypassed = stages_used(cmds, scen)
    code, code_files = new_code_lines(wt)
    qfile = built / "QUESTIONS.md"
    questions = count_questions(qfile.read_text(encoding="utf-8")) if qfile.exists() else 0
    rec = {"schema": "trainer-run/1", "etalon": e["id"], "lane": a.lane, "model": LANES[a.lane]["model"],
           "origin_main": head, "proxy": use_proxy, "exit": rc, "wall_s": wall, "tokens": tok, "commands": len(cmds),
           "questions": questions, "stages_used": used, "stages_bypassed": bypassed,
           "new_code_lines_outside_hooks": code, "new_code_files": code_files,
           "built_files": sorted(p.name for p in built.iterdir()), "hidden_repo_paths": e.get("hidden_repo_paths", []),
           "scrubbed_files": scrubbed,
           "harness_variant": None if overlay is None else {"dir": str(a.overlay).replace("\\", "/"), "files": overlay},
           "last_message": (out / "last.txt").read_text(encoding="utf-8", errors="replace")[-2000:]
           if (out / "last.txt").exists() else ""}
    (out / "run.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rec[k] for k in ("etalon", "exit", "wall_s", "tokens", "stages_used", "built_files")}))
    return 0


# ---------------------------------------------------------------- scoring
def step(status, **numbers):
    if status not in STATUSES:
        raise TrainerError(f"unknown status {status}")
    return {"status": status, **numbers}


def first_failing(steps):
    for name in STEPS:
        if name in steps and steps[name]["status"] not in ("pass", "not_applicable"):
            return name
    return None


def bounds_step(built_rb, key_rb):
    def box(rb):
        lo = [min(m["bounds_m"][0][i] for m in rb["meshes"]) for i in range(3)]
        hi = [max(m["bounds_m"][1][i] for m in rb["meshes"]) for i in range(3)]
        return lo + hi
    vals = box(built_rb) + box(key_rb)
    if not all(math.isfinite(v) for v in vals):
        return step("error", reason="non-finite bounds")
    dev = max(abs(a - b) for a, b in zip(vals[:6], vals[6:]))
    return step("pass" if dev <= TOL["bounds_m"] else "fail", max_corner_dev_m=round(dev, 4), tol_m=TOL["bounds_m"])


def ucx_step(built_rb, key_rb):
    """[#2066] UCX of one body: built has UCX_ meshes and their triangles fit the [D012] budget of its model
    triangles (reg p.36-37). The key's UCX count is reported, not gated."""
    from twinqa.geometry.ucx_audit import ucx_triangle_limit

    def split(rb):
        ucx = [m for m in rb["meshes"] if str(m.get("name", "")).upper().startswith("UCX_")]
        model = sum(int(m.get("triangles", 0)) for m in rb["meshes"] if m not in ucx)
        return ucx, model
    ucx, model = split(built_rb)
    kucx, _ = split(key_rb)
    tris = sum(int(m.get("triangles", 0)) for m in ucx)
    limit = ucx_triangle_limit(model)
    ok = bool(ucx) and tris <= limit
    return step("pass" if ok else "fail", ucx_meshes=len(ucx), ucx_triangles=tris, ucx_limit=limit,
                model_triangles=model, key_ucx_meshes=len(kucx))


def quad_share(rb):
    polys = sum(m["polygons"] for m in rb["meshes"])
    quads = sum(int(m.get("polygon_degrees", {}).get("4", 0)) for m in rb["meshes"])
    return quads / polys if polys else float("nan")


def topology_step(built_rb, key_rb):
    b, k = quad_share(built_rb), quad_share(key_rb)
    if not (math.isfinite(b) and math.isfinite(k)):
        return step("error", reason="no polygons")
    ok = b >= k - TOL["quad_share_drop"]
    return step("pass" if ok else "fail", quad_share=round(b, 4), key_quad_share=round(k, 4),
                polygons=sum(m["polygons"] for m in built_rb["meshes"]),
                key_polygons=sum(m["polygons"] for m in key_rb["meshes"]))


def form_step(dev):
    """dev = {'built_to_key': {p95,max,n}, 'key_to_built': {...}} from tools/trainer/surface_dev.py."""
    try:
        nums = [dev[d][k] for d in ("built_to_key", "key_to_built") for k in ("p95", "max")]
        n = min(dev["built_to_key"]["n"], dev["key_to_built"]["n"])
    except (KeyError, TypeError):
        return step("error", reason="incomplete deviation report")
    if n <= 0 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in nums):
        return step("error", reason="empty or non-finite deviation")
    p95 = max(nums[0], nums[2])
    mx = max(nums[1], nums[3])
    ok = p95 <= TOL["form_p95_m"] and mx <= TOL["form_max_m"]
    return step("pass" if ok else "fail", p95_m=round(p95, 4), max_m=round(mx, 4), samples=n,
                tol_p95_m=TOL["form_p95_m"], tol_max_m=TOL["form_max_m"])


def score_value(steps):
    """Passed-step share, then the form deviation as tie-break (lower is better). Used for ranking only.
    `holdout` is a gate (first_failing_step/passed), not a quality step: kept out of the share so earlier scores
    stay comparable."""
    counted = [s for s in STEPS if s in steps and s != "holdout" and steps[s]["status"] != "not_applicable"]
    passed = sum(steps[s]["status"] == "pass" for s in counted)
    p95 = steps.get("form", {}).get("p95_m")
    return round(passed / len(counted), 4) if counted else 0.0, (p95 if isinstance(p95, (int, float)) else math.inf)


def _blender():
    from dt_ai.core.blender_runner import DEFAULT_BLENDER
    return os.environ.get("TWINQA_BLENDER") or str(DEFAULT_BLENDER)


def _bl(script, args, log):
    from dt_ai.core.blender_runner import blender_command
    p = subprocess.run(blender_command(script, args, executable=_blender()), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    Path(log).write_text(p.stdout[-20000:] + p.stderr[-5000:], encoding="utf-8")
    return p.returncode


def readback(fbx, out_json, work):
    if not Path(out_json).exists():
        _bl(ROOT / "tools/blender/fbx_readback.py", [fbx, out_json], work / (Path(out_json).stem + ".log"))
    try:
        rb = json.loads(Path(out_json).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rb if rb.get("readback_ok") and rb.get("meshes") else None


def pick_built(built, e):
    p = Path(built)
    if p.is_file():
        return p, None
    if not p.is_dir():
        raise TrainerError(f"built result not found: {p}")
    fbx = sorted(p.rglob("*.fbx"))
    want = e.get("built_fbx_glob")
    if want:
        fbx = [f for f in fbx if f.match(want)]
    zips = sorted(p.rglob("*.zip"))
    if len(fbx) > 1:
        raise TrainerError(f"several FBX in {p}: {[f.name for f in fbx]}; pass --built FILE")
    return (fbx[0] if fbx else None), (zips[0] if zips else None)


def score(e, built, out_dir, vlm=False, allow_key=False):
    """-> report dict. out_dir is a NEW work folder. allow_key only for calibration (accepted scored vs itself)."""
    work = Path(out_dir)
    work.mkdir(parents=True, exist_ok=False)
    key = Path(e["key"]["path"])
    fbx, zip_ = pick_built(built, e)
    steps = {"holdout": holdout_step(built)}
    if fbx is None or not fbx.is_file():
        steps["artifact"] = step("fail", reason="no FBX in the built result")
    else:
        if not allow_key and (fbx.resolve() == key.resolve() or sha256(fbx) == e["key"].get("sha256")):
            steps["artifact"] = step("fail", reason="built result IS the key (copied, not built)")
        else:
            head = fbx.read_bytes()[:23]
            steps["artifact"] = step("pass" if head.startswith(b"Kaydara FBX Binary") else "fail",
                                     bytes=fbx.stat().st_size, sha256=sha256(fbx))
    brb = krb = None
    if steps["artifact"]["status"] == "pass":
        brb = readback(fbx, work / "built.readback.json", work)
        krb = readback(key, work / "key.readback.json", work)
        steps["readback"] = step("pass" if brb else "fail", meshes=len(brb["meshes"]) if brb else 0) if krb \
            else step("error", reason=f"key readback failed: {key}")
    if brb and krb:
        steps["bounds"] = bounds_step(brb, krb)
        steps["topology"] = topology_step(brb, krb)
        rc = _bl(ROOT / "tools/trainer/surface_dev.py", [fbx, key, work / "form.json"], work / "form.log")
        try:
            steps["form"] = form_step(json.loads((work / "form.json").read_text(encoding="utf-8"))) if rc == 0 \
                else step("error", reason=f"surface_dev exit {rc}")
        except (OSError, ValueError):
            steps["form"] = step("error", reason="no form.json")
        steps["form_v2"] = form_v2_step(e, fbx, work)
        if e.get("target") == "ucx":
            steps["ucx"] = ucx_step(brb, krb)
        steps["vlm"] = vlm_step(e, fbx, key, work) if vlm else step("not_run", reason="pass --vlm (2 judge calls)")
    if e.get("target") != "ucx":  # [#2066] kept out of the share so earlier scores stay comparable
        steps["ucx"] = step("not_applicable", reason="etalon target is not ucx")
    if e.get("target") == "package":
        steps["package"] = package_step(e, zip_, work)
    else:
        steps["package"] = step("not_applicable", reason="etalon target is not a package")
    for s in STEPS:
        steps.setdefault(s, step("not_run", reason="an earlier step did not pass"))
    value, tie = score_value(steps)
    return {"schema": "trainer-score/1", "etalon": e["id"], "built": str(fbx) if fbx else str(built),
            "key_sha256": e["key"].get("sha256"), "steps": steps, "first_failing_step": first_failing(steps),
            "passed": first_failing(steps) is None, "score": value, "form_p95_m": None if tie == math.inf else tie,
            "tolerances": TOL}


FORM_V2_MAP = {"ok": "pass", "defect": "fail", "not_measured": "not_measured"}


def form_v2_verdict(det, pid):
    """detector.json rows -> step. The detector says ok/defect/not_measured; anything else is an error, never pass."""
    if not isinstance(det, list):
        return step("error", reason="detector.json is not a list of rows")
    rows = [r for r in det if isinstance(r, dict) and r.get("pair") == pid and r.get("variant") == "built"]
    if len(rows) != 1:
        return step("error", reason=f"detector.json has {len(rows)} rows for pair {pid!r} variant 'built' (need 1)")
    v = rows[0].get("verdict")
    if v not in FORM_V2_MAP:
        return step("error", reason=f"unknown detector verdict {v!r}")
    return step(FORM_V2_MAP[v], verdict=v, summary=rows[0].get("summary"))


def _form_v2_detect(pairs_json, out):
    """Run the form-check v2 detector in a fresh process; ROOT (+src) on PYTHONPATH so `tools` is importable."""
    paths = [str(ROOT), str(ROOT / "src"), os.environ.get("PYTHONPATH", "")]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in paths if p))
    return subprocess.run([sys.executable, "-m", "tools.qa.form_check.pairs", "detect", "--out", str(out),
                           "--pairs", str(pairs_json)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT, env=env)


def form_v2_step(e, fbx, work, detect=None):
    pid = e.get("form_check_pair")
    if not pid:
        return step("not_applicable", reason="etalon has no form-check v2 key")
    cfg = json.loads((ROOT / "tools/qa/form_check/pairs_v1.json").read_text(encoding="utf-8"))
    pair = next((p for p in cfg["pairs"] if p["id"] == pid), None)
    if pair is None:
        return step("error", reason=f"form-check pair {pid!r} not in pairs_v1.json")
    if pair.get("kind") != "scene":
        return step("error", reason=f"form-check pair {pid!r} is kind {pair.get('kind')!r}; only 'scene' scores an FBX")
    one = dict(pair, variants=[{"name": "built", "fbx": str(fbx), "sha": sha256(fbx), "artem": "n/a",
                                "cite": "trainer"}], reference="built")
    one.pop("render", None)
    one.pop("accepted_deviations", None)  # Artem's per-version waivers never carry over to a new build
    tmp = work / "form_v2_pairs.json"
    tmp.write_text(json.dumps({**cfg, "pairs": [one]}, ensure_ascii=False), encoding="utf-8")
    try:
        p = (detect or _form_v2_detect)(tmp, work / "form_v2")
    except Exception as exc:  # noqa: BLE001 - a crashed detector is an error step, never a pass
        return step("error", reason=f"form-check detect crashed: {type(exc).__name__}: {exc}")
    (work / "form_v2.log").write_text((p.stdout or "")[-8000:] + (p.stderr or "")[-8000:], encoding="utf-8")
    if p.returncode != 0:
        tail = ((p.stderr or "").strip().splitlines() or [""])[-1][:300]
        return step("error", reason=f"form-check detect exit {p.returncode}: {tail}")
    try:
        det = json.loads((work / "form_v2" / "detector.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return step("error", reason="form-check detect wrote no readable detector.json")
    return form_v2_verdict(det, pid)


def vlm_step(e, fbx, key, work):
    sys.path.insert(0, str(ROOT / "tools/qa/form_check"))
    import judge  # noqa: E402  (form check pair judge, both orders)
    pngs = {}
    for name, f in (("built", fbx), ("key", key)):
        d = work / f"render_{name}"
        d.mkdir()
        spec = {"crop": "bbox", "name_re": None, "x_offset": None,
                "panels": [{"name": "V1", "dir": [0.6, 1, -0.45]}]}
        (d / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        _bl(ROOT / "tools/qa/form_check/blender_scene.py", ["render", f, d, d / "spec.json"], d / "render.log")
        if not (d / "V1.png").exists():
            return step("error", reason=f"render failed for {name}")
        pngs[name] = str(d / "V1.png")
    jl = judge.jobs([{"id": e["id"], "a_png": pngs["built"], "b_png": pngs["key"]}], judges=("claude",),
                    questions=("equivalence",))
    agg = judge.aggregate(judge.run(jl, work / "vlm_calls", work / "vlm_scratch", workers=2))
    cell = agg.get(e["id"], {}).get("claude", {}).get("equivalence")
    status = "pass" if cell == "Same" else ("fail" if cell == "Different" else "not_measured")
    return step(status, judge="claude", orders="AB+BA", cell=cell, built_png=pngs["built"], key_png=pngs["key"])


def package_step(e, zip_, work):
    if zip_ is None:
        return step("fail", reason="no ZIP package in the built result")
    rep = work / "validate.json"
    p = subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", "validate", str(zip_), "--profile",
                        e.get("profile", "npm").lower(), "--json"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT)
    rep.write_text(p.stdout, encoding="utf-8")
    m = re.search(r'"passed":\s*(true|false)', p.stdout)
    if not m:
        return step("error", reason=f"agr validate exit {p.returncode}, no passed field")
    return step("pass" if m.group(1) == "true" else "fail", validate_exit=p.returncode)


# ---------------------------------------------------------------- sheet, calibration, ledger
RU = {"artifact": "файл", "readback": "чтение FBX", "bounds": "габариты", "topology": "квады", "form": "форма",
      "form_v2": "форма v2", "vlm": "VLM-судья", "package": "пакет", "pass": "да", "fail": "НЕТ",
      "not_run": "не запускалось", "not_measured": "не измерено", "error": "ошибка", "not_applicable": "н/п"}


def sheet(rep, e, png, built_png=None, key_png=None, source_png=None):
    from PIL import Image, ImageDraw, ImageFont

    def font(sz):
        for f in ("arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(f, sz)
            except OSError:
                continue
        return ImageFont.load_default()
    W, H = 1800, 1100
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((30, 20), f"Тренажёр v0 [D387] — {e['object']} ({e['id']}): построено | ключ | источник", fill="black",
           font=font(34))
    for i, (cap, path) in enumerate((("построено", built_png), ("ключ (принято Артёмом)", key_png),
                                     ("источник", source_png))):
        x = 30 + i * 590
        d.rectangle((x, 80, x + 570, 560), outline="#999")
        d.text((x + 10, 85), cap, fill="black", font=font(24))
        if path and Path(path).exists():
            t = Image.open(path).convert("RGB")
            t.thumbnail((550, 430))
            im.paste(t, (x + 10, 120))
        else:
            d.text((x + 10, 300), "нет изображения", fill="#888", font=font(22))
    y = 590
    ff = rep["first_failing_step"]
    d.text((30, y), f"Первый непройденный этап: {RU.get(ff, ff) if ff else 'нет — пройдено'};  "
                    f"доля пройденных этапов {rep['score']:.2f}", fill="#b00" if ff else "#070", font=font(28))
    y += 50
    for s in STEPS:
        st = rep["steps"][s]
        nums = ", ".join(f"{k}={v}" for k, v in st.items() if k not in ("status", "built_png", "key_png", "sha256"))
        d.text((30, y), f"{RU[s]:<14} {RU[st['status']]:<14} {nums[:120]}", fill="black", font=font(22))
        y += 34
    d.text((30, H - 40), "Наблюдение, не приёмка: пройденные шаги не заменяют решение Артёма.", fill="#555",
           font=font(20))
    im.save(png)


def calibrate(bank, out):
    rows = []
    for e in bank["etalons"]:
        ra = None
        for r in e.get("rejected", []):
            if not (r.get("path", "").lower().endswith(".fbx") and Path(r["path"]).is_file()
                    and Path(e["key"]["path"]).is_file()):
                continue
            acc_path = e.get("calibration_accepted", {}).get("path") or e["key"]["path"]
            ra = ra or score(e, acc_path, out / f"{e['id']}__accepted", allow_key=True)
            rr = score(e, r["path"], out / f"{e['id']}__{r['version']}")
            rows.append({"etalon": e["id"], "accepted": Path(acc_path).name, "rejected": r["version"],
                         "acc_score": ra["score"], "acc_p95": ra["form_p95_m"], "rej_score": rr["score"],
                         "rej_p95": rr["form_p95_m"], "rej_first_failing": rr["first_failing_step"],
                         "acc_form_v2": ra["steps"]["form_v2"]["status"],
                         "rej_form_v2": rr["steps"]["form_v2"]["status"], "ranked_ok": rank_ok(ra, rr)})
    return rows


def rank_ok(acc, rej):
    """Accepted strictly above rejected (more passed steps, or equal and a smaller form p95) AND the rejected
    version does not pass: with the accepted bytes as the key the ranking alone is near-tautological."""
    a = (acc["score"], -(acc["form_p95_m"] if acc["form_p95_m"] is not None else math.inf))
    r = (rej["score"], -(rej["form_p95_m"] if rej["form_p95_m"] is not None else math.inf))
    return a > r and rej["first_failing_step"] is not None


def run_metrics(run_dir):
    """Ledger columns from RUN/run.json (recorded by `run`); questions recounted from built/QUESTIONS.md."""
    if not run_dir or not (Path(run_dir) / "run.json").is_file():
        return {}
    r = json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))
    q = Path(run_dir) / "built" / "QUESTIONS.md"
    return {"wall_s": r["wall_s"], "tokens_in": r["tokens"]["input_tokens"], "tokens_out": r["tokens"]["output_tokens"],
            "questions": count_questions(q.read_text(encoding="utf-8")) if q.exists() else r["questions"],
            "stages_used": r["stages_used"], "new_code_lines": r["new_code_lines_outside_hooks"], "exit": r["exit"]}


def headline(rows):
    first = {}
    for r in sorted(rows, key=lambda r: r["date"]):
        first.setdefault(r["etalon"], r)
    n = len(first)
    ok = sum(1 for r in first.values() if r["first_failing_step"] is None)
    return {"etalons_tried": n, "passed_first_try": ok, "share": round(ok / n, 4) if n else None}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agr trainer", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    r = sub.add_parser("run")
    r.add_argument("etalon")
    r.add_argument("--lane", default="codex")
    r.add_argument("--out", required=True)
    r.add_argument("--timeout-s", type=int, default=1800)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--proxy", action="store_true", help="[#2066] User Proxy answers stops from approved sources")
    mt = sub.add_parser("metrics", help="[#2066] per-run metrics: success, quality, stops by class, cost, repeats")
    mt.add_argument("run")
    mt.add_argument("--score")
    mt.add_argument("--usd-per-mtok", nargs=2, type=float, metavar=("IN", "OUT"))
    s = sub.add_parser("score")
    s.add_argument("etalon")
    s.add_argument("--built", required=True)
    s.add_argument("--out", required=True, help="NEW report JSON; its work folder is OUT minus .json")
    s.add_argument("--png")
    s.add_argument("--vlm", action="store_true")
    c = sub.add_parser("calibrate")
    c.add_argument("--out", required=True)
    lg = sub.add_parser("ledger")
    lg.add_argument("--add")
    lg.add_argument("--lane")
    lg.add_argument("--run")
    lg.add_argument("--date", default=dt.date.today().isoformat())
    ab = sub.add_parser("ab", help="[D415] A/B probe of one harness edit on one etalon")
    ab.add_argument("etalon")
    ab.add_argument("--ab", nargs=2, metavar=("OLD_DIR", "NEW_DIR"), required=True)
    ab.add_argument("--scope", required=True, help="INVARIANT (entry, context, tools) or DOMAIN (OKS/Ground/...)")
    ab.add_argument("--lane", default="codex")
    ab.add_argument("--out", required=True)
    ab.add_argument("--timeout-s", type=int, default=1800)
    ab.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bank", default=str(BANK))
    a = ap.parse_args(argv)
    try:
        bank = load_bank(a.bank)
        if a.cmd == "check":
            print(json.dumps({"etalons": len(bank["etalons"]),
                              "practice_ready": [e["id"] for e in bank["etalons"] if e["practice_ready"]],
                              "stage_tasks": {t["id"]: t["set"] for t in stage_tasks(bank)}}))
            return 0
        if a.cmd == "run":
            return cmd_run(a, bank)
        if a.cmd == "metrics":
            if not (Path(a.run) / "run.json").is_file():
                raise TrainerError(f"{a.run}: no run.json (not a trainer run dir)")
            print(json.dumps(stage_metrics(a.run, a.score, a.usd_per_mtok), ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "ab":
            import trainer_ab
            if a.lane not in LANES:
                raise TrainerError(f"unknown lane {a.lane!r}; known: {sorted(LANES)}")
            a.old, a.new = a.ab
            return trainer_ab.cmd_ab(a, bank, run_fn=cmd_run, score_fn=lambda e, b, w: score(e, b, w),
                                     head_fn=origin_main_head)
        if a.cmd == "score":
            e = etalon(bank, a.etalon)
            out = Path(a.out).resolve()
            if out.suffix != ".json" or out.exists():
                raise TrainerError(f"--out must be a NEW .json path: {out}")
            ins = {Path(a.built).resolve(), Path(e["key"]["path"]).resolve(), *(Path(x["path"]).resolve()
                                                                                for x in e["sources"])}
            if out in ins or (a.png and Path(a.png).resolve() in ins | {out}):
                raise TrainerError("an output path aliases an input")
            rep = score(e, a.built, out.with_suffix(""), vlm=a.vlm)
            out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            if a.png:
                v = rep["steps"]["vlm"]
                sheet(rep, e, a.png, v.get("built_png"), v.get("key_png"), e.get("source_png"))
            print(json.dumps({k: rep[k] for k in ("etalon", "first_failing_step", "score", "form_p95_m")}))
            return 0
        if a.cmd == "calibrate":
            out = Path(a.out).resolve()
            if out.exists():
                raise TrainerError(f"{out} exists")
            rows = calibrate(bank, out)
            (out / "calibration.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
            print(json.dumps(rows, indent=1))
            return 0 if rows and all(r["ranked_ok"] for r in rows) else 1
        if a.cmd == "ledger":
            data = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"rows": []}
            if a.add:
                rep = json.loads(Path(a.add).read_text(encoding="utf-8"))
                if not a.lane:
                    raise TrainerError("--add needs --lane")
                data["rows"].append({"etalon": rep["etalon"], "lane": a.lane, "date": a.date,
                                     "first_failing_step": rep["first_failing_step"], "score": rep["score"],
                                     "report": str(Path(a.add)).replace("\\", "/"),
                                     "run": (a.run or "").replace("\\", "/"), **run_metrics(a.run)})
                LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(json.dumps(headline(data["rows"])))
            return 0
    except ValueError as exc:  # TrainerError, trainer_ab.AbError
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
