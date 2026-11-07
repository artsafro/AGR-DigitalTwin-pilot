"""Scenario router: map a user prompt to a production cell (profile x object class) of docs/scenarios/scenarios.json.

  route(prompt)        -> {"cells": [...], "ask": str | None, "profiles": [...], "objects": [...]}
  check(payload)       -> UserPromptSubmit hook output (dict) or {}; called by tools/hooks/prompt_hooks.py
  py -3 tools/hooks/scenario_router.py "делаем ВПМ ОКС"   prints the hint for a prompt (debug)

Triggers are lower-case word prefixes («впм» matches «ВПМ», «озелен» matches «озеленение»). A prompt with both a
profile and an object class names a cell; a prompt with only one of them gets a question instead of a guess. A cell is
announced once per session (state next to the transcript, like context_watch.py); a question repeats. Advisory only.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "docs/scenarios/scenarios.json"
_WORD = re.compile(r"[0-9a-zа-яё][0-9a-zа-яё_-]*")

PROFILE_ASK = "Ask the user which profile: НПМ, НПМ упрощённый или ВПМ?"
OBJECT_ASK = "Ask the user which object class: ОКС, Ground, МАФ или Флора?"
UCX_ASK = "UCX is VPM only. Ask the user: коллизии для ОКС или для Ground?"


def load(path=TABLE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


_NPM_CLI = re.compile(r"\bnpm\s+(install|i|run|ci|test|start|publish)\b")


def _words(text):
    text = _NPM_CLI.sub(" ", (text or "").lower())      # the JavaScript package manager, not the NPM profile
    return _WORD.findall(text.replace("ё", "е"))


def _hits(words, groups):
    found = []
    for key, prefixes in groups.items():
        for prefix in prefixes:
            p = prefix.lower().replace("ё", "е")
            if (" " in p and p in " ".join(words)) or any(w.startswith(p) for w in words):
                found.append(key)
                break
    return found


def route(prompt, table=None):
    table = table or load()
    words = _words(prompt)
    profiles = _hits(words, table["profiles"])
    if "npm-lite" in profiles and "npm" in profiles:
        profiles.remove("npm")
    objects = _hits(words, table["objects"])
    kinds = []
    for obj in objects:
        kind = table["object_cell"].get(obj)
        if kind and kind not in kinds:
            kinds.append(kind)
    if "ucx" in objects and not profiles:
        profiles = ["vpm"]
    result = {"profiles": profiles, "objects": objects, "cells": [], "ask": None}
    if not profiles and not objects:
        return result
    if not profiles:
        result["ask"] = PROFILE_ASK
        return result
    if not kinds:
        result["ask"] = UCX_ASK if "ucx" in objects else OBJECT_ASK
        return result
    ids = {c["id"] for c in table["cells"]}
    for kind in kinds:
        for profile in profiles:
            cell = f"{kind}-{profile}"
            if cell not in ids and profile == "npm-lite":
                cell = f"{kind}-npm"                 # Ground is one cell for NPM and simplified NPM (NTR)
            if cell in ids and cell not in result["cells"]:
                result["cells"].append(cell)
    return result


def hint(result, table=None, seen=()):
    table = table or load()
    cells = {c["id"]: c for c in table["cells"]}
    lines = []
    for cid in result["cells"]:
        if cid in seen:
            continue
        cell = cells[cid]
        if cell["status"] == "ready":
            lines.append(f"Scenario cell `{cid}` ({cell['title']}): load the `scenario` skill and read the card "
                         f"`{cell['card']}` before work; run its minimal contract (one batch of questions).")
        else:
            reads = ", ".join(f"`{r}`" for r in cell.get("reads", []))
            lines.append(f"Scenario cell `{cid}` ({cell['title']}) has no card yet: run the task intake "
                         f"(docs/agents/task-intake.md) and start from {reads}.")
    if result["ask"]:
        lines.append(f"Scenario unclear (matched {', '.join(result['profiles'] + result['objects'])}). "
                     f"{result['ask']} Then use docs/scenarios/scenarios.json.")
    return "\n".join(lines)


def check(payload):
    prompt = payload.get("prompt") or ""
    if prompt.lstrip().startswith("/"):
        return {}
    table = load()
    result = route(prompt, table)
    if not result["cells"] and not result["ask"]:
        return {}
    transcript = payload.get("transcript_path")
    state_path = Path(f"{transcript}.scenario-router.json") if transcript else None
    state = {}
    if state_path:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if state.get("session_id") != payload.get("session_id"):
            state = {"session_id": payload.get("session_id"), "seen": []}
    text = hint(result, table, seen=set(state.get("seen", [])))
    if state_path and result["cells"]:
        state["seen"] = sorted(set(state.get("seen", [])) | set(result["cells"]))
        try:
            state_path.write_text(json.dumps(state), encoding="utf-8")
        except OSError:
            pass
    if not text:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


if __name__ == "__main__":
    r = route(" ".join(sys.argv[1:]))
    print(json.dumps(r, ensure_ascii=False))
    print(hint(r))
