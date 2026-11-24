"""Form check v1 - VLM pair judge, rig of #41/#45/#49 (OBSERVE only).

* Two judges: fresh Claude CLI (`claude -p`, Read only, no session persistence) and fresh Codex exec
  (`gpt-6.1-sol`, read-only sandbox, prompt via stdin - the npm shim cuts argv at the first newline, #41 repair 2).
* Each call runs in its own opaque directory holding only `X.png` / `Y.png`; variant names, paths and the truth
  never reach the judge.
* Every pair is shown in both orders (A,B) and (B,A); only order-consistent verdicts are kept, anything else is
  `no_decision` (never a pass, never an error). Unparsed answers are `not_measured`.
* Questions: the #49 equivalence question for every pair, and the 'extra recess' pair question. Never
  "matches the drawing" / "required form" (#47: a better-than question ranks render cleanliness).
* Judges do not measure depth or ~10 cm chamfers (#45: shading draws a niche at any depth; #49: both judges
  call a 0.10 m chamfer `Same`). Depth comes only from the scene detector.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CODEX_MODEL = "gpt-6.1-sol"  # #41 repair 1: the config default is rejected for this account
SPEC = ("Each image shows a building fragment as orthographic views of an untextured grey model, labelled panels: "
        "facade elevations and a plan seen from above. Both images use the same views and the same scale. "
        "White inside the grey wall means an opening.")


def equivalence_prompt(x="X.png", y="Y.png"):
    """#49 question (verbatim apart from the generic SPEC)."""
    return (f"{SPEC}\nTwo renders of a building fragment, made with the same views: render X = file {x}, render Y = "
            f"file {y} (both in the current directory). Ignore differences that come only from mesh triangulation, "
            "shading or rendering noise, and any geometric difference smaller than about 5 cm. Do X and Y show the "
            "same building form (same walls, openings, recesses and corners)? Answer Same, Different or Unsure. "
            'Reply with one line of JSON only, e.g. {"form":"Same"}.')


def recess_prompt(x="X.png", y="Y.png"):
    """'Extra recess' pair question (#41 Q1 / #45 recess family, asked as a comparison, not against a drawing)."""
    return (f"{SPEC}\nTwo renders of a building fragment, made with the same views: render X = file {x}, render Y = "
            f"file {y} (both in the current directory). Ignore differences that come only from mesh triangulation, "
            "shading or rendering noise. Does one render show a recess or niche in a wall (a wall surface set back "
            "from the facade, or a step in the outer wall line) that the other render does not show? Answer X (only "
            "X has it), Y (only Y has it), None or Unsure. Reply with one line of JSON only, e.g. "
            '{"extra_recess":"None"}.')


QUESTIONS = {"equivalence": (equivalence_prompt, "form"), "recess": (recess_prompt, "extra_recess")}


def parse(stdout):
    for s in reversed(re.findall(r"\{[^{}]*\}", stdout or "")):
        try:
            return json.loads(s)
        except ValueError:
            continue
    return None


def cell_equivalence(ab, ba):
    if ab is None or ba is None:
        return "not_measured"
    if ab == ba and ab in ("Same", "Different"):
        return ab
    return "no_decision"


def cell_recess(ab, ba):
    """AB shows X=A, Y=B; BA shows X=B, Y=A. Returns 'A' / 'B' (which one has the extra recess), 'None',
    'no_decision' or 'not_measured'."""
    if ab is None or ba is None:
        return "not_measured"
    m_ab = {"X": "A", "Y": "B", "None": "None"}.get(ab)
    m_ba = {"X": "B", "Y": "A", "None": "None"}.get(ba)
    return m_ab if m_ab is not None and m_ab == m_ba else "no_decision"


def jobs(pairs, judges=("claude", "codex"), questions=("equivalence", "recess")):
    """pairs: [{'id', 'a_png', 'b_png'}]. One fresh call per judge x question x order."""
    out = []
    for p in pairs:
        for j in judges:
            for q in questions:
                for order in ("AB", "BA"):
                    imgs = [p["a_png"], p["b_png"]] if order == "AB" else [p["b_png"], p["a_png"]]
                    out.append({"id": uuid.uuid4().hex[:10], "pair": p["id"], "judge": j, "question": q,
                                "order": order, "imgs": imgs})
    return out


def run_call(job, calls_dir, scratch_dir, timeout=420):
    calls_dir, scratch_dir = Path(calls_dir), Path(scratch_dir)
    out = calls_dir / f"{job['id']}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    d = scratch_dir / job["id"]
    d.mkdir(parents=True, exist_ok=True)
    for name, src in zip(("X.png", "Y.png"), job["imgs"]):
        shutil.copyfile(src, d / name)
    prompt = QUESTIONS[job["question"]][0]()
    if job["judge"] == "claude":
        cmd = [shutil.which("claude"), "-p", prompt, "--allowedTools", "Read", "--no-session-persistence",
               "--strict-mcp-config"]
        stdin, inp = subprocess.DEVNULL, None
    else:
        cmd = [shutil.which("codex"), "exec", "-m", CODEX_MODEL, "--skip-git-repo-check", "--ephemeral", "-s",
               "read-only", "-C", str(d), "-i", str(d / "X.png"), "-i", str(d / "Y.png"), "-"]
        stdin, inp = None, prompt
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, input=inp, stdin=stdin)
        stdout, stderr, rc = p.stdout, p.stderr[-2000:], p.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, rc = "", "TIMEOUT", -9
    parsed = parse(stdout)
    answer = (parsed or {}).get(QUESTIONS[job["question"]][1])
    rec = {**job, "prompt": prompt, "rc": rc, "wall_s": round(time.time() - t0, 1), "stdout": stdout[-3000:],
           "stderr": stderr, "parsed": parsed, "answer": answer}
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    return rec


def run(jobs_list, calls_dir, scratch_dir, workers=4):
    Path(calls_dir).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda j: run_call(j, calls_dir, scratch_dir), jobs_list))


def aggregate(records):
    """-> {pair: {judge: {'equivalence': cell, 'recess': cell}}, plus 'consensus' per question}."""
    by = {}
    for r in records:
        by.setdefault(r["pair"], {}).setdefault(r["judge"], {}).setdefault(r["question"], {})[r["order"]] = r["answer"]
    res = {}
    for pair, judges in by.items():
        res[pair] = {}
        for j, qs in judges.items():
            res[pair][j] = {q: (cell_equivalence if q == "equivalence" else cell_recess)(o.get("AB"), o.get("BA"))
                            for q, o in qs.items()}
        for q in ("equivalence", "recess"):
            cells = [res[pair][j].get(q) for j in judges]
            dec = [c for c in cells if c not in (None, "no_decision", "not_measured")]
            res[pair].setdefault("consensus", {})[q] = (dec[0] if dec and len(set(dec)) == 1 and len(dec) == len(cells)
                                                        else "split" if len(set(dec)) > 1 else "no_decision")
    return res
