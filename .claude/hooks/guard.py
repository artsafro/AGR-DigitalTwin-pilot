"""PreToolUse guard for Claude Code, Codex and Antigravity.

Forces a user confirmation for destructive, outward, or asset-corrupting actions.
Never blocks outright; returns permission decision "ask" so the user decides.
Dual-protocol support:
- Antigravity: inputs 'toolCall', outputs {"decision": "ask"|"allow", "reason": ...}
- Claude Code: inputs 'tool_name', outputs {"hookSpecificOutput": ...} or exit 0
"""
import json
import os
import re
import sys
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


def _long(word, keep):
    """`--word` and every prefix of it down to `keep` letters (git accepts unambiguous prefixes)."""
    tail = ""
    for ch in reversed(word[keep:]):
        tail = "(?:" + re.escape(ch) + tail + ")?"
    return "--" + re.escape(word[:keep]) + tail


def _flag(long, keep, short=None):
    """A git option token (#1186 review round 1): optional quotes, then a short cluster holding `short`
    anywhere (-f, -fq, -qf, -ff) or a long-option prefix; case-sensitive; ends at whitespace, `=` or end."""
    alts = ([r"-[A-Za-z]*" + short + r"[A-Za-z]*"] if short else []) + [_long(long, keep)]
    return r"\s" + _Q + r"(?-i:" + "|".join(alts) + r")" + _Q + r"(?=[\s=]|$)"


# `git`, then any global options (-C dir, -c k=v, --no-pager, ...) up to the subcommand.
_GIT = r"\bgit\b[^|;&]*"
SHELL_RULES = [
    (GH_PREFIX + r"\bpr\s+merge\b", "gh pr merge requires the user's merge command"),
    (GH_PREFIX + r"\bdelete\b", "gh delete changes remote data"),
    (GH_REPO_SUBCOMMAND, "gh repo operations require explicit authorization"),
    (r"\bgit\b[^|;&]*\bpush\b", "git push publishes to a remote"),
    (_GIT + r"\breset\b[^|;&]*(?:--hard|" + _flag("hard", 2) + ")", "git reset --hard discards work"),
    (r"\bgit\b[^|;&]*\bclean\b", "git clean deletes untracked files"),
    (_FORCE_BRANCH_DELETE, "force branch delete"),
    (r"\bgit\b[^|;&]*\b(checkout|restore)\b[^|;&]*\s(--\s+)?\.(\s|$)", "discards working-tree changes"),
    (r"\bgit\b[^|;&]*\b(filter-branch|filter-repo|rebase|update-ref\s+-d)\b", "rewrites history/refs"),
    (_GIT + r"\blfs\s+migrate\b", "rewrites history (LFS migrate)"),
    (r"\b(rm|del|rmdir|rd|Remove-Item|ri)\b[^|;&]*(Revit[/\\\\]|Source[/\\\\]|Unreal[/\\\\]|" + PRODUCTION_EXT + ")",
     "deletes source/production assets"),
    (r"\brm\s+-[a-zA-Z]*r|\bRemove-Item\b[^|;&]*-(Recurse|Rec)|\b(rmdir|rd)\b[^|;&]*/[sS]|\brobocopy\b[^|;&]*/(MIR|PURGE)|\bfind\b[^|;&]*-delete",
     "recursive delete / mass overwrite"),
    (r"\b(winget|choco|scoop|msiexec)\b|\bnpm\s+(i|install)\s+(-g|--global)|\b(pip|uv\s+pip|uv\s+tool)\s+install\b",
     "installs software"),
    (r"\b(setx|reg\s+(add|delete)|Set-ExecutionPolicy|New-ItemProperty|Set-ItemProperty)\b", "system-level change"),
] + [
    # Ported from destructive_command_guard (core.git, core.filesystem, windows.filesystem,
    # careful_company): only what is missing above and relevant here (docs/research/guard-vs-dcg-2026-11.md).
    (_GIT + r"\breset\b[^|;&]*" + _flag("merge", 2), "git reset --merge can discard work"),
    (_GIT + r"\b(checkout|switch)\b[^|;&]*(?:" + _flag("force", 1, "f") + "|" + _flag("discard-changes", 2) + ")",
     "discards working-tree changes"),
    (_GIT + r"\bread-tree\b[^|;&]*(?:--reset|" + _flag("reset", 3) + ")", "discards working-tree changes"),
    (_GIT + r"\brm\b[^|;&]*" + _flag("force", 1, "f"), "git rm -f deletes modified files"),
    (_GIT + r"\b(reflog\s+(expire|delete)\b|gc\b[^|;&]*(?:--prune\b|" + _flag("prune", 1) + "))",
     "destroys recovery data (reflog / unreachable objects)"),
    (_GIT + r"\bstash\s+(drop|clear)\b", "deletes stash entries (the stash stack is shared by all worktrees)"),
    (_GIT + r"\blfs\s+(prune|uninstall)\b", "removes LFS objects or filters"),
    (_GIT + r"\bworktree\s+remove\b[^|;&]*" + _flag("force", 1, "f"),
     "force-removes a worktree with uncommitted work"),
    (r"(?<![-/.\w])(rm|ri|del|erase|rmdir|rd|Remove-Item)\b[^|;&]*"
     r"(?:(?-i:\s-[dfiIvR]*[rR][dfiIvR]*)|\s--recursive|\s-r(?:e(?:c(?:u(?:r(?:s(?:e)?)?)?)?)?)?)(?=[\s:]|$)"
     r"|(?<![-/.\w])(del|erase)(\.exe)?\b[^|;&]*\s/s\b"
     r"|\[\s*(System\.)?IO\.Directory\s*\]\s*::\s*['\"]?Delete\b|\.\s*Delete\s*\(\s*\$true\s*\)",
     "recursive delete / mass overwrite"),
    (r"\bformat(\.com|\.exe)?\s+(/\S+\s+)*[a-z]:(?=[\s\\/]|$)|\b(Format-Volume|Clear-Disk)\b"
     r"|\bvssadmin\b[^|;&]*\bdelete\s+shadows\b|\bwmic\b[^|;&]*\bshadowcopy\b[^|;&]*\bdelete\b"
     r"|\bWin32_ShadowCopy\b[^;&\n]*\b(Remove-WmiObject|Remove-CimInstance|Delete\s*\()",
     "erases a volume or shadow copies"),
    (r"\bClear-RecycleBin\b", "purges the Recycle Bin (earlier deletes become unrecoverable)"),
    (r"\b(Set-MpPreference|Add-MpPreference|Remove-MpPreference|Set-NetFirewallProfile|Disable-NetFirewallRule"
     r"|Disable-BitLocker|Clear-EventLog)\b|\bnetsh\b[^|;&]*\badvfirewall\b[^|;&]*\b(set|reset|delete)\b"
     r"|\bwevtutil\b[^|;&]*\s(cl|clear-log)\b", "security settings change"),
    (r"\b(powershell|pwsh)(\.exe)?\b[^|;&]*\s-(e|ec|en\w*)(?=\s|$)"
     r"|\b(iwr|irm|Invoke-WebRequest|Invoke-RestMethod|curl|wget)\b[^;&\n]*\|\s*(iex|Invoke-Expression|(ba|z)?sh)\b"
     r"|\b(iex|Invoke-Expression)\b[^;&\n]*\b(iwr|irm|Invoke-WebRequest|Invoke-RestMethod|DownloadString)\b",
     "runs encoded or downloaded code"),
    (GH_PREFIX + r"\bgist\s+create\b", "gh gist create publishes files"),
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
    main()
