"""Measure agent step waste in finished job sessions and board cards (issue #1273).

Pattern: new-case: read-only research measurement of agent transcripts (Claude Code job sessions and
Hermes board production cards); writes CSV/JSON summaries, never touches the sources.

Sources (read-only):
- Claude Code transcripts: ``~/.claude/projects/C--Users-artsafro*AGR-DigitalTwin*/*.jsonl``.
- Hermes board ``agr-pilot``: ``~/.hermes/kanban/boards/agr-pilot/kanban.db`` (tasks, task_runs, task_events)
  and each run's profile ``state.db`` (sessions, messages) named by its ``owner_admitted`` event.

Usage::

    python docs/research/agent-step-waste-1273/measure.py --out <dir>

Step tags (heuristic, see the report for limits):
- ``unused``: the tool result is an error (blocked command, missing file, exception): the call produced nothing
  the result used.
- ``repeated``: an identical call (same tool, same input) already ran in the session; or a render that directly
  follows another render with no edit in between (extra angle); or a pytest run with no Edit/Write/DCC call since
  the previous pytest run.
- ``necessary``: everything else.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sqlite3
import statistics
import sys

CC_ROOT = os.path.expanduser("~/.claude/projects")
BOARD_DB = os.path.expanduser("~/.hermes/kanban/boards/agr-pilot/kanban.db")

DCC = re.compile(r"^mcp__(3dsmax-mcp|blender|revit-http-2025|max-ultra-mcp)__")
RENDER_TOOL = re.compile(r"capture_viewport|capture_screen|get_view_image")
RENDER_CODE = re.compile(
    r"\brender\s*\(|bpy\.ops\.render|gw\.getViewportDib|viewport\.grab|screen_capture|capture_viewport|"
    r"\.render\.filepath|render_frame|renderSceneDialog|\brender\b[^\n]{0,80}\.(png|jpg)|"
    r"\.(png|jpg)[^\n]{0,80}\brender\b|contact[_-]?sheet|turntable|screenshot", re.I)
IMG_WRITE = re.compile(r"save|render|grab|Dib|write|capture|snapshot|export_image|bitmap", re.I)
IMG = re.compile(r"\.(png|jpe?g|webp|bmp)\b", re.I)
PYTEST = re.compile(r"\bpytest\b")
FULL = re.compile(r"suite_slot|pytest\s+(-q\s+)?(-n\s*\d+\s+)?(-p\s+\S+\s+)?(--basetemp\S*\s*)?($|[|;&])")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READONLY = {"Read", "Grep", "Glob", "ToolSearch", "Skill", "SendUserFile", "mcp__ccd_turn__update_plan"}

# Sessions that are not production jobs (harness, audits, research, letters, tooling chats).
NOT_A_JOB = re.compile(
    r"point-resume|kanban-project|ai-dev-kit|pilot-solutions|digital-twins-audit|gumroad|agent-session-retro|"
    r"repository-audit|ntr-presentation|chertanova|great-lehmann|clever-chatelet|trusting|charming|"
    r"VPM NPM проект|^harness", re.I)
SINCE = "2026-10-13"

# Board production cards (DCC/job work, finished): ids chosen in the report, newest job cards first.
BOARD_CARDS = ["t_cd0d8792", "t_dd6f4bf9", "t_b1946208", "t_d1f84643", "t_3ed57b56", "t_c9ff2af1", "t_d9171ddc",
               "t_b10ac4ee", "t_f6c68418", "t_e35c49dd", "t_96a3cc8a", "t_b4f6c33a", "t_5e2eb833"]

# Remark themes in the user's own chat messages (Russian), counted per session.
THEMES = {
    "open_scene_or_give_path": r"путь|сам\w* откр|открой",
    "too_slow_or_overdone": r"зачем|не надо|лишн|хватит|долго|быстрее|сколько можно|перемудр",
    "no_renders": r"рендер\w* (делать )?не (нужно|надо)|не нужно делать рендер",
    "seams_joints": r"\bшов|\bшвы|\bшвов|стык",
    "compare_to_reference": r"как на|референс|по образцу|сравни|фотограф\w* из альбома",
}


def _iso(x: str) -> dt.datetime:
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def analyse_cc(path: str) -> dict | None:
    """Per-session metrics of one Claude Code transcript."""
    title = None
    calls, results_err, ts, users = [], {}, [], []
    seen_ids: set[str] = set()
    tokens: collections.Counter = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            kind = o.get("type")
            if kind == "custom-title":
                title = o.get("customTitle") or o.get("title") or title
            if o.get("timestamp"):
                ts.append(o["timestamp"])
            m = o.get("message") or {}
            content = m.get("content")
            if kind == "assistant" and isinstance(content, list):
                mid = m.get("id")
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    for k, v in (m.get("usage") or {}).items():
                        if isinstance(v, int):
                            tokens[k] += v
                for b in content:
                    if b.get("type") == "tool_use":
                        calls.append((o.get("timestamp"), b["id"], b["name"], b.get("input") or {}))
            if kind == "user" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        results_err[b.get("tool_use_id")] = bool(b.get("is_error"))
            if kind == "user" and not o.get("isMeta") and not o.get("toolUseResult"):
                if isinstance(content, str):
                    txt = content
                elif isinstance(content, list):
                    txt = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
                else:
                    txt = ""
                if txt and not txt.startswith("<"):
                    users.append(txt)
    if not calls:
        return None
    seen: set[str] = set()
    tags = collections.Counter()
    c = collections.Counter()
    repeated_by: collections.Counter = collections.Counter()
    unused_by: collections.Counter = collections.Counter()
    last_render, had_test, edits_since_test = False, False, True
    ep, episodes = 0, []
    for (_, tid, name, inp) in calls:
        txt = json.dumps(inp, sort_keys=True, ensure_ascii=False)
        key = name + ":" + hashlib.sha1(txt.encode()).hexdigest()
        cmd = inp.get("command", "") if isinstance(inp, dict) else ""
        code = (inp.get("code") or inp.get("script") or "") if isinstance(inp, dict) else ""
        shell = name in ("Bash", "PowerShell")
        is_dcc = bool(DCC.match(name))
        is_render = (bool(RENDER_TOOL.search(name))
                     or (is_dcc and bool(RENDER_CODE.search(code or txt)))
                     or (shell and bool(RENDER_CODE.search(cmd)))
                     or (is_dcc and bool(IMG.search(code or txt)) and bool(IMG_WRITE.search(code or txt)))
                     or (shell and bool(re.search(r"blender|3dsmaxbatch", cmd, re.I)) and bool(IMG.search(cmd))))
        is_view = ((name == "Read" and bool(IMG.search(str(inp.get("file_path", "")))))
                   or (name == "SendUserFile" and bool(IMG.search(txt))))
        is_test = shell and bool(PYTEST.search(cmd))
        c["dcc"] += is_dcc
        c["renders"] += is_render
        c["views"] += is_view
        c["tests"] += is_test
        c["full"] += is_test and bool(FULL.search(cmd))
        c["sent_images"] += name == "SendUserFile" and bool(IMG.search(txt))
        tag = "necessary"
        if results_err.get(tid):
            tag = "unused"
        elif key in seen and not is_render:
            tag = "repeated"
        elif is_render and last_render:
            tag = "repeated"
            c["render_extra"] += 1
        elif is_test and had_test and not edits_since_test:
            tag = "repeated"
            c["test_repeat"] += 1
        seen.add(key)
        short = name.split("__")[-1]
        if tag == "repeated":
            repeated_by[short] += 1
        if tag == "unused":
            unused_by[short] += 1
        tags[tag] += 1
        if is_render:
            last_render = True
        elif not (name in READONLY or is_view):
            last_render = False
        if is_test:
            had_test, edits_since_test = True, False
        if name in EDIT_TOOLS or (is_dcc and not is_render):
            edits_since_test = True
        if is_render or is_view:
            ep += 1
        elif name in READONLY or name.startswith("mcp__ccd") or name in ("TaskStop", "Monitor"):
            pass
        else:
            if ep:
                episodes.append(ep)
            ep = 0
    if ep:
        episodes.append(ep)
    stamps = sorted(_iso(x) for x in ts)
    active = sum(min((b - a).total_seconds(), 600) for a, b in zip(stamps, stamps[1:]))
    themes = {k: sum(1 for u in users if re.search(p, u, re.I)) for k, p in THEMES.items()}
    return {
        "source": os.path.relpath(path, CC_ROOT).replace("\\", "/"),
        "title": title or "",
        "start": stamps[0].isoformat()[:16],
        "wall_h": round((stamps[-1] - stamps[0]).total_seconds() / 3600, 2),
        "active_h": round(active / 3600, 2),
        "user_msgs": len(users),
        "tool_calls": len(calls),
        "dcc_calls": c["dcc"],
        "renders": c["renders"],
        "image_views": c["views"],
        "images_sent": c["sent_images"],
        "test_runs": c["tests"],
        "full_suites": c["full"],
        "necessary": tags["necessary"],
        "repeated": tags["repeated"],
        "unused": tags["unused"],
        "waste_share": round((tags["repeated"] + tags["unused"]) / len(calls), 3),
        "img_episodes": len(episodes),
        "img_episodes_3plus": sum(1 for e in episodes if e >= 3),
        "img_extra": sum(e - 1 for e in episodes),
        "img_episode_max": max(episodes or [0]),
        "render_extra": c["render_extra"],
        "test_repeat": c["test_repeat"],
        "out_tokens": tokens["output_tokens"],
        "in_tokens": tokens["input_tokens"] + tokens["cache_read_input_tokens"] + tokens["cache_creation_input_tokens"],
        "themes": themes,
        "repeated_by": dict(repeated_by),
        "unused_by": dict(unused_by),
    }


def select_jobs(rows: list[dict]) -> list[dict]:
    """Production job sessions since SINCE with DCC use; fork copies (same title, day, DCC count) dropped."""
    cand = [r for r in rows if r["start"] >= SINCE and (r["dcc_calls"] or r["renders"])
            and not NOT_A_JOB.search(r["source"]) and not NOT_A_JOB.search(r["title"])]
    seen, out = set(), []
    for r in sorted(cand, key=lambda r: -r["tool_calls"]):
        k = (r["title"], r["start"][:10], r["dcc_calls"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return sorted(out, key=lambda r: r["start"])


def analyse_board(card_ids: list[str]) -> list[dict]:
    """Runs, review rounds and session tool calls of finished board cards (author and reviewer runs)."""
    con = sqlite3.connect(f"file:{BOARD_DB}?mode=ro", uri=True)
    conns: dict[str, sqlite3.Connection] = {}
    out = []
    for tid in card_ids:
        row = con.execute("select title,status from tasks where id=?", (tid,)).fetchone()
        if row is None:
            raise SystemExit(f"board card not found: {tid}")
        title, status = row
        runs = con.execute("select profile,started_at,ended_at from task_runs where task_id=?", (tid,)).fetchall()
        ev = collections.Counter(k for (k,) in con.execute("select kind from task_events where task_id=?", (tid,)))
        c = collections.Counter()
        seen: set[str] = set()
        for (payload,) in con.execute("select payload from task_events where task_id=? and kind='owner_admitted'", (tid,)):
            p = json.loads(payload or "{}")
            dbp, sid = p.get("db"), p.get("session_id")
            if not dbp or not sid or not os.path.exists(dbp):
                c["sessions_missing"] += 1
                continue
            if dbp not in conns:
                conns[dbp] = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
            sc = conns[dbp]
            c["sessions"] += 1
            tok = sc.execute("select input_tokens,output_tokens,cache_read_tokens from sessions where id=?", (sid,)).fetchone()
            if tok:
                c["in_tokens"] += (tok[0] or 0) + (tok[2] or 0)
                c["out_tokens"] += tok[1] or 0
            for (tc,) in sc.execute("select tool_calls from messages where session_id=? and role='assistant' "
                                    "and tool_calls is not null", (sid,)):
                try:
                    lst = json.loads(tc)
                except ValueError:
                    continue
                for call in lst:
                    f = call.get("function", call)
                    name, args = f.get("name", ""), f.get("arguments", "")
                    if isinstance(args, dict):
                        args = json.dumps(args, sort_keys=True)
                    c["tool_calls"] += 1
                    if sid + name + args in seen:
                        c["repeated"] += 1
                    seen.add(sid + name + args)
                    if name in ("terminal", "execute_code") and PYTEST.search(args):
                        c["test_runs"] += 1
                        c["full_suites"] += "suite_slot" in args
                    if name == "vision_analyze":
                        c["image_views"] += 1
                    elif name == "terminal" and re.search(r"blender|3dsmax", args, re.I) and IMG.search(args):
                        c["renders"] += 1
            c["error_results"] += sc.execute(
                "select count(*) from messages where session_id=? and role='tool' and "
                "(content like '%\"exit_code\": 1%' or content like '%\"error\": \"%')", (sid,)).fetchone()[0]
        prof = collections.Counter(r[0] for r in runs)
        out.append({
            "source": f"agr-pilot kanban.db task {tid}",
            "card": tid, "title": title, "status": status, "runs": len(runs),
            "author_runs": sum(v for k, v in prof.items() if k != "dt-reviewer"),
            "review_runs": prof.get("dt-reviewer", 0),
            "profiles": "+".join(sorted(prof)),
            "wall_h": round(sum((r[2] or r[1]) - r[1] for r in runs) / 3600, 2),
            "review_requested": ev["review_requested"], "changes_requested": ev["changes_requested"],
            "blocked": ev["blocked"], **{k: c[k] for k in ("sessions", "sessions_missing", "tool_calls", "repeated",
                                                          "error_results", "renders", "image_views", "test_runs",
                                                          "full_suites", "in_tokens", "out_tokens")},
        })
    return out


def write_csv(path: str, rows: list[dict], skip: tuple[str, ...] = ()) -> None:
    keys = [k for k in rows[0] if k not in skip]
    with open(path, "w", newline="\n", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, keys, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure agent step waste (#1273).")
    ap.add_argument("--out", required=True, help="output directory (created; must not be a source directory)")
    a = ap.parse_args(argv)
    raw = a.out
    m = re.match(r"^/([a-zA-Z])(/.*)?$", raw)
    if os.name == "nt" and m:  # MSYS/git-bash path such as /c/Users/x: would become C:\c\Users\x
        raw = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    out = os.path.abspath(raw)
    for src in (CC_ROOT, os.path.dirname(BOARD_DB), os.path.expanduser("~/.hermes/profiles")):
        if os.path.normcase(out).startswith(os.path.normcase(os.path.abspath(src))):
            print(f"refusing to write into a source directory: {out}", file=sys.stderr)
            return 2
    files = sorted(glob.glob(CC_ROOT + "/C--Users-artsafro*AGR-DigitalTwin*/*.jsonl"))
    if not files:
        print(f"no transcripts under {CC_ROOT}", file=sys.stderr)
        return 2
    rows = [r for r in (analyse_cc(f) for f in files) if r]
    jobs = select_jobs(rows)
    board = analyse_board(BOARD_CARDS)
    os.makedirs(out, exist_ok=True)
    flat = []
    for r in jobs:
        f = {k: v for k, v in r.items() if k not in ("themes", "repeated_by", "unused_by")}
        f.update({"theme_" + k: v for k, v in r["themes"].items()})
        flat.append(f)
    write_csv(os.path.join(out, "sessions.csv"), flat)
    write_csv(os.path.join(out, "board.csv"), board)
    tot = collections.Counter()
    rep, unu = collections.Counter(), collections.Counter()
    for r in jobs:
        for k in ("tool_calls", "dcc_calls", "renders", "image_views", "images_sent", "test_runs", "full_suites",
                  "repeated", "unused", "img_episodes", "img_episodes_3plus", "img_extra", "render_extra",
                  "test_repeat", "out_tokens", "in_tokens"):
            tot[k] += r[k]
        rep.update(r["repeated_by"])
        unu.update(r["unused_by"])
    summary = {
        "transcripts_scanned": len(files), "sessions_with_tools": len(rows), "job_sessions": len(jobs),
        "totals": dict(tot),
        "waste_share_overall": round((tot["repeated"] + tot["unused"]) / tot["tool_calls"], 3),
        "waste_share_median": statistics.median(r["waste_share"] for r in jobs),
        "tool_calls_median": statistics.median(r["tool_calls"] for r in jobs),
        "sessions_with_3plus_image_episode": sum(1 for r in jobs if r["img_episodes_3plus"]),
        "repeated_by_tool": dict(rep.most_common(15)), "unused_by_tool": dict(unu.most_common(10)),
        "theme_sessions": {k: sum(1 for r in jobs if r["themes"][k]) for k in THEMES},
        "theme_messages": {k: sum(r["themes"][k] for r in jobs) for k in THEMES},
        "board_cards": len(board),
        "board_changes_requested_cards": sum(1 for b in board if b["changes_requested"]),
        "board_full_suites_median": statistics.median(b["full_suites"] for b in board),
        "board_test_runs_median": statistics.median(b["test_runs"] for b in board),
    }
    with open(os.path.join(out, "summary.json"), "w", newline="\n", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps({k: summary[k] for k in ("job_sessions", "board_cards", "waste_share_overall")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
