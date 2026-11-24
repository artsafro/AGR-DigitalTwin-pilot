"""Trainer v0 [D387] (#1855): etalon bank, practice runs on a fresh agent, scoring against the hidden key.

Pattern: n/a | new-case: trainer v0 - practice-run recorder and step scorer over existing checkers.

    uv run agr trainer check                      # etalons.json is well-formed (exit 0 / 2)
    uv run agr trainer run ETALON --lane codex --out NEW_DIR [--timeout-s 1800] [--dry-run]
    uv run agr trainer score ETALON --built FILE.fbx|DIR --out NEW.json [--png NEW.png] [--vlm] [--date D]
    uv run agr trainer calibrate --out NEW_DIR    # accepted vs rejected of every scorable etalon
    uv run agr trainer ledger [--add SCORE.json --lane L --run RUN_DIR]   # headline: share passed first try

A practice run gets ONLY the task text and the source copies (never the key, rejected versions or the job's
history: those repo paths are removed from the disposable worktree). Score steps run the existing checkers in
order - artifact (FBX header), readback (`tools/blender/fbx_readback.py`), bounds, topology (quads), form
(surface deviation built<->key, Blender BVH), form_v2 (`tools/qa/form_check` detector when the etalon has a
form-check pair), vlm (form-check pair judge, both orders; only with --vlm), package (`agr validate`). Only
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
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / "docs/trainer/etalons.json"
LEDGER = ROOT / "docs/trainer/ledger.json"
STEPS = ("artifact", "readback", "bounds", "topology", "form", "form_v2", "vlm", "package")
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
        for r in e.get("rejected", []):
            if not r.get("reason") or not r.get("date"):
                out.append(f"{name}: rejected {r.get('version')} needs reason + date")
    return out


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
    for item in [e["key"], *e.get("rejected", [])]:
        for k in ("path", "sha256"):
            v = item.get(k)
            if v:
                toks.add(str(v))
                if k == "path":
                    toks.add(Path(v).name)
    return {t for t in toks if len(t) >= 6} | set(e.get("hidden_repo_paths", []))


# The bank itself and the form-check pair registry name every key; a practice worktree never contains them.
ALWAYS_HIDDEN = ("docs/trainer", "tools/qa/form_check/pairs_v1.json")


def scan_tokens(e):
    """Content tokens of the hidden key and rejected versions: file names, full paths (both slash forms), sha256
    and its 12-char prefix (pairs_v1.json pins by prefix). Lower-case; matched case-insensitively."""
    toks = set()
    for item in [e["key"], *e.get("rejected", []), e.get("calibration_accepted") or {}]:
        if item.get("path"):
            p = str(item["path"])
            toks |= {p, p.replace("/", "\\"), Path(p).name}
        if item.get("sha256"):
            toks |= {item["sha256"], item["sha256"][:12]}
    return sorted(t.lower() for t in toks if len(t) >= 6)


def leaking_files(wt, tokens):
    """Tracked files of the worktree whose bytes contain any token -> {rel: [tokens]}."""
    rels = subprocess.run(["git", "-C", str(wt), "ls-files", "-z"], capture_output=True, text=True,
                          check=True).stdout.split("\0")
    rels += subprocess.run(["git", "-C", str(wt), "ls-files", "-z", "--others", "--exclude-standard"],
                           capture_output=True, text=True, check=True).stdout.split("\0")
    hits = {}
    for rel in sorted({r for r in rels if r}):
        f = Path(wt) / rel
        if not f.is_file():
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


def task_text(e, inputs_dir, out_dir):
    """The only prompt a practice agent receives."""
    lines = [e["task"].strip(), "", f"Inputs (copies of the customer sources, read-only): {inputs_dir}"]
    lines += [f"- {Path(s['path']).name}  sha256 {s['sha256']}" for s in e["sources"]]
    lines += ["", f"Write every result into {out_dir} (new files only).",
              f"Deliverable: {e.get('deliverable', 'one FBX of the result')} in that folder.",
              "Follow AGENTS.md and docs/agents/SKELETONS.md. You run headless: nobody answers questions; when a",
              "decision only the user can make blocks you, write the question into QUESTIONS.md in the output",
              "folder and continue with the documented default or stop. Do not commit or push."]
    text = "\n".join(lines) + "\n"
    leaks = [t for t in secret_tokens(e) if t in text]
    if leaks:
        raise TrainerError(f"task text would leak the key: {sorted(leaks)}")
    return text


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
    text = task_text(e, inputs, built)
    if a.dry_run:
        print(text)
        return 0
    inputs.mkdir(parents=True)
    built.mkdir()
    for s in e["sources"]:
        dst = inputs / Path(s["path"]).name
        shutil.copyfile(s["path"], dst)
        if sha256(dst) != s["sha256"]:
            raise TrainerError(f"source hash mismatch: {s['path']}")
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "origin/main"], capture_output=True, text=True,
                          check=True).stdout.strip()
    subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(wt), head], check=True,
                   capture_output=True)
    scrubbed = scrub_worktree(wt, e)  # the job's history and every file naming the key stay out of the session
    (out / "prompt.txt").write_text(text, encoding="utf-8")
    cmd = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--disable", "memories", "-m",
           LANES[a.lane]["model"], "-c", "model_reasoning_effort=high", "--dangerously-bypass-approvals-and-sandbox",
           "--skip-git-repo-check", "-C", str(wt), "--add-dir", str(out), "--json", "-o", str(out / "last.txt"), "-"]
    t0 = time.time()
    with open(out / "events.jsonl", "w", encoding="utf-8") as ev, open(out / "stderr.txt", "w", encoding="utf-8") as er:
        try:
            p = subprocess.run(cmd if os.name != "nt" else [shutil.which("codex") or "codex", *cmd[1:]],
                               input=text, stdout=ev, stderr=er, text=True, encoding="utf-8", timeout=a.timeout_s)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    wall = round(time.time() - t0, 1)
    tok, cmds, msgs = parse_events((out / "events.jsonl").read_text(encoding="utf-8", errors="replace").splitlines())
    scen = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))["cells"].get(
        e["scenario"], {}).get("stages", [])
    used, bypassed = stages_used(cmds, scen)
    code, code_files = new_code_lines(wt)
    qfile = built / "QUESTIONS.md"
    questions = count_questions(qfile.read_text(encoding="utf-8")) if qfile.exists() else 0
    rec = {"schema": "trainer-run/1", "etalon": e["id"], "lane": a.lane, "model": LANES[a.lane]["model"],
           "origin_main": head, "exit": rc, "wall_s": wall, "tokens": tok, "commands": len(cmds),
           "questions": questions, "stages_used": used, "stages_bypassed": bypassed,
           "new_code_lines_outside_hooks": code, "new_code_files": code_files,
           "built_files": sorted(p.name for p in built.iterdir()), "hidden_repo_paths": e.get("hidden_repo_paths", []),
           "scrubbed_files": scrubbed,
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
    """Passed-step share, then the form deviation as tie-break (lower is better). Used for ranking only."""
    counted = [s for s in STEPS if s in steps and steps[s]["status"] != "not_applicable"]
    passed = sum(steps[s]["status"] == "pass" for s in counted)
    p95 = steps.get("form", {}).get("p95_m")
    return round(passed / len(counted), 4) if counted else 0.0, (p95 if isinstance(p95, (int, float)) else math.inf)


def _blender():
    from dt_ai.core.blender_runner import DEFAULT_BLENDER
    return os.environ.get("TWINQA_BLENDER") or str(DEFAULT_BLENDER)


def _bl(script, args, log):
    p = subprocess.run([_blender(), "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                        str(script), "--", *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
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
    steps = {}
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
        steps["vlm"] = vlm_step(e, fbx, key, work) if vlm else step("not_run", reason="pass --vlm (2 judge calls)")
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
    ap.add_argument("--bank", default=str(BANK))
    a = ap.parse_args(argv)
    try:
        bank = load_bank(a.bank)
        if a.cmd == "check":
            print(json.dumps({"etalons": len(bank["etalons"]),
                              "practice_ready": [e["id"] for e in bank["etalons"] if e["practice_ready"]]}))
            return 0
        if a.cmd == "run":
            return cmd_run(a, bank)
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
    except TrainerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
