"""UserPromptSubmit dispatcher for Claude Code: context_watch.py and `usage_log.py prompt` in one process.

  py -3 tools/hooks/prompt_hooks.py      hook input JSON on stdin (registered in .claude/settings.json)

Reads stdin once, logs a /command with usage_log.write() and prints only context_watch.check()'s output. Both stay
advisory as standalone: any failure of one part is silent and never hides the other. The two scripts keep working
on their own (usage_log.py also has post / stats / backfill and is imported by skill_gate.py).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
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
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
