"""UserPromptSubmit dispatcher for Claude Code: context_watch.py, `usage_log.py prompt`, the scenario router
(scenario_router.py, docs/scenarios/) and the acceptance nudge in one process.

  py -3 tools/hooks/prompt_hooks.py      hook input JSON on stdin (registered in .claude/settings.json)

Reads stdin once, logs a /command with usage_log.write() and prints the additional context of context_watch.check(),
of scenario_router.check() (the production cell named by the prompt) and of accept_nudge() (a prompt that accepts a result: «принято», «все норм», ... - the acceptance pattern of
tools/retro/condense_transcript.py, #1036; docs/agents/WORKFLOW.md, "Session retro"). All parts stay advisory:
any failure of one part is silent and never hides the others. The scripts keep working on their own (usage_log.py
also has post / stats / backfill and is imported by skill_gate.py).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_input import read_stdin
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "retro"))

ACCEPT_NUDGE = ("The user's message reads as accepting a result. Before this stage ends: run the "
                "`experience-transfer` skill for exactly what was accepted (docs/agents/WORKFLOW.md, \"Experience "
                "capture\"), and if the user corrected you earlier in this session, run the /retro procedure "
                "(.claude/commands/retro.md). Praise does not replace QA.")


def accept_nudge(payload):
    import condense_transcript
    prompt = payload.get("prompt") or ""
    return ACCEPT_NUDGE if condense_transcript.signal(prompt) == "+" else ""


def main():
    try:
        payload = json.loads(read_stdin() or "{}")
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    out = {}
    try:
        import context_watch
        out = context_watch.check(payload)
    except Exception:                                # advisory: never block or break a prompt
        out = {}
    try:
        import usage_log
        usage_log.write(payload)
    except Exception:                                # logging is never a reason to fail a call
        pass
    try:
        nudge = accept_nudge(payload)
    except Exception:                                # advisory
        nudge = ""
    try:
        import scenario_router
        scenario = scenario_router.check(payload).get("hookSpecificOutput", {}).get("additionalContext", "")
    except Exception:                                # advisory
        scenario = ""
    for extra in (scenario, nudge):
        if extra:
            spec = out.setdefault("hookSpecificOutput", {"hookEventName": "UserPromptSubmit"})
            spec["additionalContext"] = "\n\n".join(t for t in (spec.get("additionalContext"), extra) if t)
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
