"""PreToolUse guard for Claude Code, Codex and Antigravity.

Forces a user confirmation for destructive, outward, or asset-corrupting actions.
Never blocks outright; returns permission decision "ask" so the user decides.
One exception to "ask" [D223]: a one-shot merge token (written by `guard.py merge-token N "<the
user's literal command>"` after the user's chat command names PR N) lets exactly one plain
`gh pr merge N` through with an explicit "allow"; the token is consumed by that call and expires
after MERGE_TOKEN_TTL_S. Any other PR number, shape, a second call or no/expired token: "ask".
Dual-protocol support:
- Antigravity: inputs 'toolCall', outputs {"decision": "ask"|"allow", "reason": ...}
- Claude Code: inputs 'tool_name', outputs {"hookSpecificOutput": ...} or exit 0
"""
import json
import math
import os
import re
import sys
import time
from pathlib import Path

PRODUCTION_EXT = r"\.(fbx|blend|max|uasset|umap|obj|abc|usd[az]?|glb|gltf|rvt|skp|dwg|psd|exr|tiff?|png|tga)\b"

# (regex, reason) checked against shell commands (Bash and PowerShell / cmd).
# Policy: docs/agents/WORKFLOW.md#permission-matrix; DCC risk classes and
# authorization gates: docs/agents/CAPABILITIES.md#dcc-tool-risk-classes.
# Conservative lexical checks, not a shell sandbox (aliases/arbitrary code need review).
# Global gh options may precede the subcommand; never cross a shell command boundary.
GH_PREFIX = r"\bgh(?:\.exe)?\b[^|;&\n]*?"
# `repo` only as the gh subcommand (#1027): after gh, only `-R/--repo OWNER/NAME` or bare
# flags may precede it, so `--repo o/n`, `-R o/n` and branch names like `harness/repo-x`
# do not ask. `gh --repo o/n repo view` still asks: every `gh repo <subcommand>` asks.
# Tokens may be shell-quoted ('repo', "--repo", 'gh').
_Q = r"['\"]?"
GH_REPO_SUBCOMMAND = (r"\bgh(?:\.exe)?\b" + _Q +
                      r"(?:\s+" + _Q + r"(?:(?:-R|--repo)" + _Q + r"(?:\s+|=)[^\s|;&]+|--?[A-Za-z][\w-]*" + _Q + r"))*"
                      r"\s+(['\"]?)repo\1(?=\s|$)")
# Force branch delete (#1027): a delete flag (-d/--delete or a short cluster with d) and a force
# flag (-f/--force or a cluster with f) in any order/position, or -D in any cluster. Flags are
# case-sensitive (?-i:): `-d` alone is a safe delete. Long-option prefixes git accepts are covered.
_BRANCH = r"\bgit\b[^|;&]*\bbranch\b"
_FORCE_BRANCH_DELETE = (
    _BRANCH + r"(?=[^|;&]*(?-i:\s" + _Q + r"-[A-Za-z]*D))"
    r"|" + _BRANCH + r"(?=[^|;&]*(?-i:\s" + _Q + r"(?:--d(?:e(?:l(?:e(?:t(?:e)?)?)?)?)?(?=[\s='\"]|$)|-[A-Za-z]*d)))"
    r"(?=[^|;&]*(?-i:\s" + _Q + r"(?:--forc(?:e)?(?=[\s='\"]|$)|-[A-Za-z]*f)))")
MERGE_REASON = "gh pr merge requires the user's merge command"
SHELL_RULES = [
    (GH_PREFIX + r"\bpr\s+merge\b", MERGE_REASON),
    (GH_PREFIX + r"\bdelete\b", "gh delete changes remote data"),
    (GH_REPO_SUBCOMMAND, "gh repo operations require explicit authorization"),
    (r"\bgit\b[^|;&]*\bpush\b", "git push publishes to a remote"),
    (r"\bgit\b[^|;&]*\breset\b[^|;&]*--hard", "git reset --hard discards work"),
    (r"\bgit\b[^|;&]*\bclean\b", "git clean deletes untracked files"),
    (_FORCE_BRANCH_DELETE, "force branch delete"),
    (r"\bgit\b[^|;&]*\b(checkout|restore)\b[^|;&]*\s(--\s+)?\.(\s|$)", "discards working-tree changes"),
    (r"\bgit\b[^|;&]*\b(filter-branch|filter-repo|rebase|update-ref\s+-d)\b", "rewrites history/refs"),
    (r"\bgit\s+lfs\s+migrate\b", "rewrites history (LFS migrate)"),
    (r"\b(rm|del|rmdir|rd|Remove-Item|ri)\b[^|;&]*(Revit[/\\\\]|Source[/\\\\]|Unreal[/\\\\]|" + PRODUCTION_EXT + ")",
     "deletes source/production assets"),
    (r"\brm\s+-[a-zA-Z]*r|\bRemove-Item\b[^|;&]*-(Recurse|Rec)|\b(rmdir|rd)\b[^|;&]*/[sS]|\brobocopy\b[^|;&]*/(MIR|PURGE)|\bfind\b[^|;&]*-delete",
     "recursive delete / mass overwrite"),
    (r"\b(winget|choco|scoop|msiexec)\b|\bnpm\s+(i|install)\s+(-g|--global)|\b(pip|uv\s+pip|uv\s+tool)\s+install\b",
     "installs software"),
    (r"\b(setx|reg\s+(add|delete)|Set-ExecutionPolicy|New-ItemProperty|Set-ItemProperty)\b", "system-level change"),
]

HOME = Path.home()
ALLOWED_WRITE_ROOTS = [
    HOME / ".claude" / "projects",
    HOME / ".claude" / "plans",  # plan-mode plan files (#111)
    HOME / ".claude" / "skills",
    HOME / ".gemini",
    Path(os.environ.get("TEMP", HOME / "AppData/Local/Temp")) / "claude",
    Path(os.environ.get("TEMP", HOME / "AppData/Local/Temp")) / "antigravity",
]


def ask(reason: str, is_antigravity: bool) -> None:
    if is_antigravity:
        print(json.dumps({
            "decision": "ask",
            "reason": f"guard.py: {reason}"
        }))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"guard.py: {reason}",
        }}))
    sys.exit(0)


def allow_explicit(reason: str, is_antigravity: bool) -> None:
    """Explicit allow (skips the permission prompt); used only for a valid merge token [D223]."""
    if is_antigravity:
        print(json.dumps({"decision": "allow", "reason": f"guard.py: {reason}"}))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"guard.py: {reason}",
        }}))
    sys.exit(0)


def allow(is_antigravity: bool) -> None:
    if is_antigravity:
        print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def shell_reason(cmd: str):
    """Reason of the first SHELL_RULES match for a shell command, else None."""
    for pattern, reason in SHELL_RULES:
        if re.search(pattern, cmd or "", re.IGNORECASE):
            return reason
    return None


# One-shot merge token [D223] (#1028). The token covers one plain merge and nothing else: no shell
# metacharacters, no second command, no branch deletion (--delete-branch/-d), no --admin bypass.
MERGE_TOKEN_TTL_S = 600
_MERGE_FLAGS = {"--merge", "-m", "--squash", "-s", "--rebase", "-r", "--auto", "--disable-auto"}
_MERGE_VALUE_FLAGS = {"-R", "--repo", "--match-head-commit"}
_SHELL_META = re.compile(r"[;&|<>`$(){}\n\r'\"\\]")


def merge_token_dir() -> Path:
    if os.environ.get("AGR_MERGE_TOKEN_DIR"):
        return Path(os.environ["AGR_MERGE_TOKEN_DIR"])
    return Path(os.environ.get("TEMP", HOME / "AppData/Local/Temp")) / "claude" / "merge-tokens"


def _names_pr(command, n: int) -> bool:
    return isinstance(command, str) and re.search(rf"(?<!\d){n}(?!\d)", command) is not None


def _take_flags(toks, i, allowed_bare):
    """Skip flags from toks[i]; return the next index, or None on an unknown flag or missing value."""
    while i < len(toks) and toks[i].startswith("-"):
        tok = toks[i]
        name, eq, value = tok.partition("=")
        if name in _MERGE_VALUE_FLAGS:
            if eq:
                if not value:
                    return None
                i += 1
            elif i + 1 < len(toks) and not toks[i + 1].startswith("-"):
                i += 2
            else:
                return None
        elif tok in allowed_bare:
            i += 1
        else:
            return None
    return i


def plain_merge_pr(cmd):
    """PR number of one plain `gh [-R o/n] pr merge N [flags]` command, else None."""
    if not isinstance(cmd, str) or _SHELL_META.search(cmd):
        return None
    toks = cmd.split()
    if not toks or toks[0].lower() not in ("gh", "gh.exe"):
        return None
    i = _take_flags(toks, 1, set())
    if i is None or toks[i:i + 2] != ["pr", "merge"]:
        return None
    i += 2
    number = None
    while i < len(toks):
        j = _take_flags(toks, i, _MERGE_FLAGS)
        if j is None:
            return None
        if j == len(toks):
            break
        if number is not None or not re.fullmatch(r"#?\d+", toks[j]):
            return None
        number = int(toks[j].lstrip("#"))
        i = j + 1
    return number if number else None


def merge_token_allows(cmd):
    """Consume the token for the PR of a plain merge command; return the allow reason or None.

    The token file is claimed by an atomic rename before it is read, so two calls never both use
    it; an invalid or expired token is consumed as well and the call asks."""
    n = plain_merge_pr(cmd)
    if n is None:
        return None
    path = merge_token_dir() / f"pr-{n}.json"
    claim = path.with_name(f"{path.name}.claimed-{os.getpid()}-{time.time_ns()}")
    try:
        os.replace(path, claim)
    except OSError:
        return None
    try:
        data = json.loads(claim.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    finally:
        try:
            claim.unlink()
        except OSError:
            pass
    if not isinstance(data, dict):
        return None
    pr, command, created = data.get("pr"), data.get("command"), data.get("created_at")
    if type(pr) is not int or pr != n or not _names_pr(command, n):
        return None
    if isinstance(created, bool) or not isinstance(created, (int, float)) or not math.isfinite(created):
        return None
    if not 0 <= time.time() - created < MERGE_TOKEN_TTL_S:
        return None
    return f"one-shot merge token for PR #{n} [D223], user command: {command}"


def write_merge_token(argv) -> int:
    """`guard.py merge-token N "<the user's literal command>"`: write the one-shot token for PR N."""
    if len(argv) != 2 or not re.fullmatch(r"\d+", argv[0]) or int(argv[0]) <= 0:
        print('usage: guard.py merge-token <PR number> "<the user\'s literal merge command>"', file=sys.stderr)
        return 2
    n, command = int(argv[0]), argv[1]
    if not _names_pr(command, n):
        print(f"refused: the user's command does not name PR {n}", file=sys.stderr)
        return 2
    folder = merge_token_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"pr-{n}.json"
    tmp = folder / f"pr-{n}.json.partial-{os.getpid()}"
    tmp.write_text(json.dumps({"pr": n, "command": command, "created_at": time.time()}, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, target)
    print(f"merge token for PR {n}: {target} (TTL {MERGE_TOKEN_TTL_S} s, one use)")
    return 0


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, RuntimeError):
        return False


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            allow(False)
        data = json.loads(raw)
    except Exception:
        allow(False)

    is_antigravity = "toolCall" in data

    if is_antigravity:
        tool_call = data.get("toolCall", {}) or {}
        tool = tool_call.get("name", "")
        targs = tool_call.get("args", {}) or {}
        cmd = targs.get("CommandLine", "")
        target = targs.get("TargetFile", "")
    else:
        tool = data.get("tool_name", "")
        tin = data.get("tool_input", {}) or {}
        cmd = tin.get("command", "")
        target = tin.get("file_path") or tin.get("notebook_path", "")

    # 1. Shell commands
    if tool in ("Bash", "PowerShell", "run_command", "shell", "exec_command", "local_shell"):
        reason = shell_reason(cmd)
        if reason == MERGE_REASON and not any(
                re.search(pattern, cmd, re.IGNORECASE) for pattern, why in SHELL_RULES if why != MERGE_REASON):
            granted = merge_token_allows(cmd)
            if granted:
                allow_explicit(granted, is_antigravity)
        if reason:
            ask(reason, is_antigravity)

    # 2. File write/edit commands
    elif tool in ("Write", "Edit", "NotebookEdit", "write_to_file", "replace_file_content"):
        if target:
            p = Path(target)
            # Protect binary/production extensions from accidental text overwrites
            if re.search(PRODUCTION_EXT, p.name, re.IGNORECASE):
                ask(f"writing to production asset: {p.name}", is_antigravity)

            # Check boundary
            workspaces = data.get("workspacePaths", [])
            project_roots = [Path(w) for w in workspaces] if workspaces else []
            if os.environ.get("CLAUDE_PROJECT_DIR"):
                project_roots.append(Path(os.environ["CLAUDE_PROJECT_DIR"]))
            if data.get("cwd"):
                project_roots.append(Path(data["cwd"]))
            project_roots.append(Path("."))

            all_allowed = project_roots + ALLOWED_WRITE_ROOTS
            if not any(inside(p, r) for r in all_allowed):
                ask(f"write outside project/allowed folders: {target}", is_antigravity)

    allow(is_antigravity)


if __name__ == "__main__":
    if sys.argv[1:2] == ["merge-token"]:
        sys.exit(write_merge_token(sys.argv[2:]))
    main()
