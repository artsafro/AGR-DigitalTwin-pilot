"""PreToolUse guard for Claude Code, Codex and Antigravity.

Forces a user confirmation for destructive, outward, or asset-corrupting actions.
Never blocks outright; returns permission decision "ask" so the user decides.
One exception to "ask" [D234]: a one-shot merge token (written by `guard.py merge-token N "<the
user's literal command>"` after the user's chat command names PR N) lets exactly one plain
`gh pr merge N` through with an explicit "allow"; the token is bound to the GitHub repository of
the writer's `origin`, is consumed by that call and expires after MERGE_TOKEN_TTL_S. Any other PR
number, shape or repository, a second call or no/expired token: "ask".
Dual-protocol support:
- Antigravity: inputs 'toolCall', outputs {"decision": "ask"|"allow", "reason": ...}
- Claude Code: inputs 'tool_name', outputs {"hookSpecificOutput": ...} or exit 0
"""
import json
import math
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

PRODUCTION_EXT = r"\.(fbx|blend|max|uasset|umap|obj|abc|usd[az]?|glb|gltf|rvt|skp|dwg|psd|exr|tiff?|png|tga)\b"

# (regex, reason) checked against shell commands (Bash and PowerShell / cmd).
# Policy: docs/agents/WORKFLOW.md#permission-matrix; DCC risk classes and
# authorization gates: docs/agents/CAPABILITIES.md#dcc-tool-risk-classes.
# Conservative lexical checks, not a shell sandbox (aliases/arbitrary code need review).
# git commands are not matched here: git_reasons() tokenizes them (#1186 review round 2, #1210).
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


MERGE_REASON = "gh pr merge requires the user's merge command"
SHELL_RULES = [
    (GH_PREFIX + r"\bpr\s+merge\b", MERGE_REASON),
    (GH_PREFIX + r"\bdelete\b", "gh delete changes remote data"),
    (GH_REPO_SUBCOMMAND, "gh repo operations require explicit authorization"),
    (r"\b(rm|del|rmdir|rd|Remove-Item|ri)\b[^|;&]*(Revit[/\\\\]|Source[/\\\\]|Unreal[/\\\\]|" + PRODUCTION_EXT + ")",
     "deletes source/production assets"),
    (r"\brm\s+-[a-zA-Z]*r|\bRemove-Item\b[^|;&]*-(Recurse|Rec)|\b(rmdir|rd)\b[^|;&]*/[sS]|\brobocopy\b[^|;&]*/(MIR|PURGE)|\bfind\b[^|;&]*-delete",
     "recursive delete / mass overwrite"),
    (r"\b(winget|choco|scoop|msiexec)\b|\bnpm\s+(i|install)\s+(-g|--global)|\b(pip|uv\s+pip|uv\s+tool)\s+install\b",
     "installs software"),
    (r"\b(setx|reg\s+(add|delete)|Set-ExecutionPolicy|New-ItemProperty|Set-ItemProperty)\b", "system-level change"),
] + [
    # Ported from destructive_command_guard (core.filesystem, windows.filesystem, careful_company; the
    # core.git ones are in _git_subcommand_reason): only what is missing above (docs/research/guard-vs-dcg-2026-11.md).
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


def allow_explicit(reason: str, is_antigravity: bool) -> None:
    """Explicit allow (skips the permission prompt); used only for a valid merge token [D234]."""
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


def shell_reasons(cmd: str, depth=0):
    """Reasons of every SHELL_RULES match, then of every command substitution and hazardous git command."""
    cmd = cmd or ""
    reasons = [reason for pattern, reason in SHELL_RULES if re.search(pattern, cmd, re.IGNORECASE)]
    return list(dict.fromkeys(reasons + substitution_reasons(cmd, depth) + git_reasons(cmd, depth)))


def shell_reason(cmd: str):
    """Reason of the first SHELL_RULES match or hazardous git command for a shell command, else None."""
    reasons = shell_reasons(cmd)
    return reasons[0] if reasons else None


# --- git commands: tokenized, not regex-matched (#1186 review round 2, #1210) -----------------------------
# The command is split like a shell does (quotes, separators, line continuations); each simple command
# that runs git gets its global options skipped and its subcommand and flags matched token by token.
# Two readings are unioned: POSIX (backslash escapes, backtick = command substitution) and PowerShell
# (backtick escapes, backslash is a path character). Quoted text that contains `git` and a space or a
# separator (bash -c '...', powershell -Command "...") is read again as a command.
_SEPARATORS = ";&|()\n"
_GIT_NAMES = {"git", "git.exe"}
_GIT_VALUE_GLOBALS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env",
                      "--attr-source"}
_GIT_EQ_ONLY_GLOBALS = {"--exec-path", "--list-cmds"}           # `--exec-path=dir`; bare `--exec-path` exits
_GIT_BARE_GLOBALS = {"-p", "--paginate", "-P", "--no-pager", "--bare", "--no-replace-objects",
                     "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs",
                     "--no-optional-locks", "--no-lazy-fetch", "--no-advice"}
_GIT_EXITING_GLOBALS = {"--exec-path", "--html-path", "--man-path", "--info-path",
                        "--help", "-h", "--version", "-v"}      # print and exit, or run `git help/version`
# Subcommands whose arguments are text (messages, patterns, config values), never re-read as commands.
_GIT_TEXT_SUBCOMMANDS = {"commit", "log", "show", "tag", "notes", "grep", "stash", "config", "shortlog", "merge",
                         "revert", "cherry-pick", "diff", "status", "describe", "blame", "rev-parse", "rev-list"}
_DISCARDS = "discards working-tree changes"
_RECOVERY = "destroys recovery data (reflog / unreachable objects)"
_REWRITES = "rewrites history/refs"
_MAX_DEPTH = 4
# Quoted or escaped `>`/`<` are text, not redirections: masked while tokenizing, restored on a re-read.
_MASK = {">": "\ue000", "<": "\ue001"}
_UNMASK = str.maketrans({v: k for k, v in _MASK.items()})
# Match longer operators before their single-character prefixes.
_REDIRECT_OP = re.compile(r"(?:>\||>&|<&|<>|>>?|<<?<?)")


def _mask_quoted_separators(text, escape):
    """Replace a quoted span made only of separators ('|', ";") by a word, so it cannot split a command."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if escape and ch == "\\":
            out.append("\\" + _MASK.get(text[i + 1:i + 2], text[i + 1:i + 2]))
            i += 2
            continue
        if ch in "'\"":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if escape and ch == '"' and text[j] == "\\" else 1
            body = text[i + 1:j]
            if body and set(body) <= set(_SEPARATORS + "`"):
                body = "_sep_"
            body = "".join(_MASK.get(c, c) for c in body)
            out.append(ch + body + text[j:j + 1])
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _shell_tokens(text, posix_escape):
    """Tokens of one reading of a command line; separators are tokens of their own. ValueError on bad quotes."""
    if posix_escape:
        punctuation = _SEPARATORS + "`"
    else:
        text = re.sub(r"`(.)", r"\1", text, flags=re.DOTALL)          # PowerShell escape: `x -> x
        punctuation = _SEPARATORS
    lex = shlex.shlex(_mask_quoted_separators(text, posix_escape), posix=True, punctuation_chars=punctuation)
    lex.whitespace_split = True
    lex.whitespace = " \t\r"
    lex.commenters = ""
    if not posix_escape:
        lex.escape = ""
    return list(lex)


def _join_redirections(tokens):
    """Glue `&`/`|` back into redirections (`2>&1`, `>&2`, `&>out`, `>|out`); shlex splits them off."""
    out, k = [], 0
    while k < len(tokens):
        tok, nxt = tokens[k], tokens[k + 1] if k + 1 < len(tokens) else None
        word_next = nxt is not None and not set(nxt) <= set(_SEPARATORS + "`")
        if tok in ("&", "|") and out and re.fullmatch(r"(\d*|\*)>>?", out[-1]) and word_next:
            out[-1] += tok + nxt
            k += 2
        elif tok == "&" and word_next and nxt.startswith(">"):
            out.append("&" + nxt)
            k += 2
        else:
            out.append(tok)
            k += 1
    return out


def _drop_redirections(words):
    """The words of a simple command without its redirections (`> out`, `2>/dev/null`, `*>`, `git>out` -> git)."""
    out, k = [], 0
    while k < len(words):
        word = words[k]
        pos = min((word.find(c) for c in "<>" if c in word), default=-1)
        op = _REDIRECT_OP.match(word, pos) if pos >= 0 else None
        if op is None:
            out.append(word)
            k += 1
            continue
        head = word[:pos]
        if head and not re.fullmatch(r"\d+|\*|&", head):        # `git>out`: the word before is kept
            out.append(head)
        k += 1 if word[op.end():] else 2                         # a bare operator takes the next word
    return out


def _simple_commands(tokens):
    command = []
    for tok in tokens:
        if tok and set(tok) <= set(_SEPARATORS + "`"):
            if command:
                yield command
            command = []
        else:
            command.append(tok)
    if command:
        yield command


def _is_git(word):
    word = word.strip("{}$@&").replace("\\", "/")
    return word.rsplit("/", 1)[-1].lower() in _GIT_NAMES


def _short(flags, letter):
    return any(re.fullmatch(r"-[A-Za-z]+", f.split("=", 1)[0]) and letter in f.split("=", 1)[0] for f in flags)


def _long(flags, word, keep):
    """`--word` or an unambiguous prefix of it (at least `keep` letters), with or without `=value`."""
    for f in flags:
        name = f.split("=", 1)[0]
        if name.startswith("--") and len(name) - 2 >= keep and word.startswith(name[2:]):
            return True
    return False


def _git_subcommand_reason(sub, args):
    """Reason a git subcommand with its arguments is hazardous, else None. Flags stop at `--`."""
    flags, positional = [], []
    for k, tok in enumerate(args):
        if tok == "--":
            positional += args[k + 1:]
            break
        (flags if tok.startswith("-") and tok != "-" else positional).append(tok)
    first = positional[0].lower() if positional else ""
    force = _short(flags, "f") or _long(flags, "force", 1)
    if sub == "push":
        return "git push publishes to a remote"
    if sub == "reset":
        if _long(flags, "hard", 2):
            return "git reset --hard discards work"
        if _long(flags, "merge", 2):
            return "git reset --merge can discard work"
    if sub == "clean":
        return "git clean deletes untracked files"
    if sub == "branch":
        delete = _short(flags, "d") or _long(flags, "delete", 1)
        if _short(flags, "D") or (delete and (_short(flags, "f") or _long(flags, "force", 4))):
            return "force branch delete"
    if sub in ("checkout", "restore") and "." in positional:
        return _DISCARDS
    if sub in ("checkout", "switch") and (force or _long(flags, "discard-changes", 2)):
        return _DISCARDS
    if sub == "read-tree" and _long(flags, "reset", 3):
        return _DISCARDS
    if sub == "rm" and force:
        return "git rm -f deletes modified files"
    if (sub == "reflog" and first in ("expire", "delete")) or (sub == "gc" and _long(flags, "prune", 1)):
        return _RECOVERY
    if sub == "stash" and first in ("drop", "clear"):
        return "deletes stash entries (the stash stack is shared by all worktrees)"
    if sub == "lfs" and first == "migrate":
        return "rewrites history (LFS migrate)"
    if sub == "lfs" and first in ("prune", "uninstall"):
        return "removes LFS objects or filters"
    if sub == "worktree" and first == "remove" and force:
        return "force-removes a worktree with uncommitted work"
    if sub in ("filter-branch", "filter-repo", "rebase") or (sub == "update-ref" and _short(flags, "d")):
        return _REWRITES
    if sub == "pull" and (_short(flags, "r") or _long(flags, "rebase", 1)):
        return _REWRITES
    return None


def _git_command_reason(args):
    """(reason or None, subcommand or None) of `git <args>`: global options skipped, then the subcommand."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        tok = args[i]
        name, eq, value = tok.partition("=")
        if tok in _GIT_EXITING_GLOBALS:
            return None, None
        if name in _GIT_VALUE_GLOBALS and not (eq and name.startswith("--")):
            if i + 1 >= len(args):
                return f"git {tok} without a value", None
            value, i = args[i + 1], i + 2
        elif name.startswith("--") and eq and (name in _GIT_VALUE_GLOBALS or name in _GIT_EQ_ONLY_GLOBALS):
            i += 1
        elif tok in _GIT_BARE_GLOBALS:
            i += 1
            continue
        else:
            return f"unrecognized git global option {tok}", None
        if name in ("-c", "--config-env") and value.lower().startswith("alias."):
            return "git alias defined on the command line", None
    if i >= len(args):
        return None, None
    sub = args[i].lower()
    return _git_subcommand_reason(sub, args[i + 1:]), sub


def _mentions_git(text):
    """`git` in the text once quotes, escapes and line breaks are dropped (g'i't, gi\\t, g`it)."""
    return re.search(r"git", re.sub(r"['\"\\`\r\n]", "", text or ""), re.IGNORECASE) is not None


def git_reasons(cmd, depth=0):
    """Reasons of every hazardous git command in a shell command line (fail-closed on unbalanced quotes)."""
    if not _mentions_git(cmd):
        return []
    if depth > _MAX_DEPTH:
        return ["git command nested too deep to check"]
    text = re.sub(r"\\\r?\n", "", cmd)                               # bash line continuation
    text = re.sub(r"`\r?\n", " ", text)                              # PowerShell line continuation
    readings = []
    for posix_escape in (True, False):
        try:
            readings.append(_shell_tokens(text, posix_escape))
        except ValueError:
            pass
    if not readings:
        return ["unbalanced quotes around a git command"]
    reasons = []
    for tokens in readings:
        for words in _simple_commands(_join_redirections(tokens)):
            words = _drop_redirections(words)
            text_args = set()
            for k, word in enumerate(words):
                if not _is_git(word):
                    continue
                reason, sub = _git_command_reason(words[k + 1:])
                if reason:
                    reasons.append(reason)
                if sub in _GIT_TEXT_SUBCOMMANDS:
                    text_args.update(range(k + 1, len(words)))
            for k, word in enumerate(words):
                if k not in text_args and word != cmd and re.search(r"[\s;&|()`]", word) \
                        and _mentions_git(word):
                    reasons += shell_reasons(word.translate(_UNMASK), depth + 1)
    return list(dict.fromkeys(reasons))


class _Unbalanced(ValueError):
    pass


def _substitutions(text, posix, bodies, i=0, stop=None):
    """Bodies of the `$(...)` (and, in the POSIX reading, backtick) substitutions the shell runs: unquoted or
    inside double quotes, never inside single quotes; appended to `bodies`. With stop=")" scans one body and
    returns the index after it. _Unbalanced(position) on an unclosed substitution."""
    depth, quoted, n, start = 0, False, len(text), i - 2
    escape = "\\" if posix else "`"
    while i < n:
        ch = text[i]
        if ch == escape:
            i += 2
        elif ch == "'" and not quoted:
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif ch == '"':
            quoted, i = not quoted, i + 1
        elif ch == "$" and text.startswith("(", i + 1):
            end = _substitutions(text, posix, [], i + 2, ")")
            bodies.append(text[i + 2:end - 1])
            i = end
        elif ch == "`" and posix:
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                raise _Unbalanced(i)
            bodies.append(re.sub(r"\\([`\\$])", r"\1", text[i + 1:j]))
            i = j + 1
        else:
            if stop and not quoted and ch == "(":
                depth += 1
            elif stop and not quoted and ch == ")":
                if depth == 0:
                    return i + 1
                depth -= 1
            i += 1
    if stop:
        raise _Unbalanced(start)                                  # at the `$(` opener
    return i


def substitution_reasons(cmd, depth=0):
    """Reasons of every command run by a `$(...)`/backtick substitution, read as a full shell command.

    Bash runs them unquoted and inside double quotes, PowerShell runs `$(...)` there too; both readings
    are unioned. Nested substitutions are found by the recursive check of each body. An unbalanced
    substitution whose rest mentions git asks (#1186 review round 3)."""
    if "$(" not in cmd and "`" not in cmd:
        return []
    cmd = re.sub(r"`\r?\n", " ", re.sub(r"\\\r?\n", "", cmd))          # line continuations, as in git_reasons
    reasons, bodies = [], []
    for posix in (True, False):
        try:
            _substitutions(cmd, posix, bodies)
        except _Unbalanced as error:
            if _mentions_git(cmd[error.args[0]:]):
                reasons.append("unbalanced command substitution around a git command")
    for body in dict.fromkeys(bodies):
        if depth >= _MAX_DEPTH:
            if _mentions_git(body):
                reasons.append("command substitution nested too deep to check")
            continue
        reasons += shell_reasons(body, depth + 1)
    return reasons


# One-shot merge token [D234] (#1028). The token covers one plain merge and nothing else: no shell
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


def normalize_repo(spec):
    """`host/owner/name` (lowercase, host defaults to github.com) of a repo spec or git URL, else None."""
    if not isinstance(spec, str):
        return None
    s = spec.strip()
    bare = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s, flags=re.IGNORECASE)  # https://, ssh://, git://
    bare = re.sub(r"^[^@/:]+@", "", bare)                                  # user@ / git@
    s, hosted = bare, bare != s or ":" in bare                             # a URL names its host
    s = re.sub(r"^([^/:]+):\d+/", r"\1/", s)                               # host:port/
    s = re.sub(r"^([^/:]+):", r"\1/", s)                                   # scp form host:owner/name
    s = s.rstrip("/")
    s = s[:-4] if s.lower().endswith(".git") else s
    parts = s.split("/")
    if len(parts) == 2 and not hosted:
        parts = ["github.com", *parts]
    if len(parts) != 3 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", x) and x.strip(".") for x in parts):
        return None
    return "/".join(parts).lower()


def _git(cwd, *args):
    try:
        result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def cwd_repo(cwd):
    """The repository a bare `gh pr merge` at cwd targets, else None.

    gh's own default (`gh repo set-default`: the one remote with `gh-resolved = base`) wins; without
    it every remote must point to the same repository, because gh otherwise picks among them (fork +
    upstream). No remote, no checkout or an ambiguous default gives None and the merge asks."""
    marks = _git(cwd, "config", "--get-regexp", r"^remote\..*\.gh-resolved$") or ""
    based = [line.split()[0][len("remote."):-len(".gh-resolved")] for line in marks.splitlines()
             if len(line.split()) == 2 and line.split()[1] == "base"]
    if len(based) > 1 or (marks.strip() and not based):          # ambiguous or legacy gh-resolved value
        return None
    if based:
        out = _git(cwd, "remote", "get-url", based[0])
        return normalize_repo(out.strip()) if out else None
    out = _git(cwd, "remote", "-v")
    if not out:
        return None
    repos = {normalize_repo(line.split()[1]) if len(line.split()) >= 2 else None
             for line in out.splitlines() if line.strip()}
    return repos.pop() if len(repos) == 1 and None not in repos else None


def origin_repo(cwd):
    out = _git(cwd, "remote", "get-url", "origin")
    return normalize_repo(out.strip()) if out else None


def _take_flags(toks, i, allowed_bare, values):
    """Skip flags from toks[i] (value flags go to values); next index, or None on an unknown flag/missing value."""
    while i < len(toks) and toks[i].startswith("-"):
        tok = toks[i]
        name, eq, value = tok.partition("=")
        if name in _MERGE_VALUE_FLAGS:
            if eq:
                if not value:
                    return None
                i += 1
            elif i + 1 < len(toks) and not toks[i + 1].startswith("-"):
                value = toks[i + 1]
                i += 2
            else:
                return None
            values.append((name, value))
        elif tok in allowed_bare:
            i += 1
        else:
            return None
    return i


def plain_merge_pr(cmd):
    """(PR number, -R/--repo value or None) of one plain `gh [-R o/n] pr merge N [flags]` command, else None."""
    if not isinstance(cmd, str) or _SHELL_META.search(cmd):
        return None
    toks = cmd.split()
    if not toks or toks[0].lower() not in ("gh", "gh.exe"):
        return None
    values = []
    i = _take_flags(toks, 1, set(), values)
    if i is None or toks[i:i + 2] != ["pr", "merge"]:
        return None
    i += 2
    number = None
    while i < len(toks):
        j = _take_flags(toks, i, _MERGE_FLAGS, values)
        if j is None:
            return None
        if j == len(toks):
            break
        if number is not None or not re.fullmatch(r"#?\d+", toks[j]):
            return None
        number = int(toks[j].lstrip("#"))
        i = j + 1
    repos = [v for name, v in values if name in ("-R", "--repo")]
    if not number or len(set(repos)) > 1 or (repos and normalize_repo(repos[0]) is None):
        return None
    return number, (repos[0] if repos else None)


def _read_token(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def merge_token_allows(cmd, cwd=None):
    """Consume the token for the PR of a plain merge command; return the allow reason or None.

    The target repository is the -R/--repo value, else GH_REPO, else the one repository all remotes
    of the git checkout at cwd (the hook's cwd) point to. When it is unknown or differs from the
    token's repo the call asks and the token stays. A matching token is claimed by an atomic rename
    before it is validated, so two calls never both use it; an invalid or expired token is consumed
    as well and the call asks."""
    parsed = plain_merge_pr(cmd)
    if parsed is None:
        return None
    n, repo_flag = parsed
    repo_flag = repo_flag or os.environ.get("GH_REPO") or None
    path = merge_token_dir() / f"pr-{n}.json"
    if not path.is_file():
        return None
    peek = _read_token(path)
    if peek is not None:
        target = normalize_repo(repo_flag) if repo_flag else cwd_repo(cwd or os.getcwd())
        if target is None or target != normalize_repo(peek.get("repo")):
            return None                                     # other or unknown repository: keep the token
    claim = path.with_name(f"{path.name}.claimed-{os.getpid()}-{time.time_ns()}")
    try:
        os.replace(path, claim)
    except OSError:
        return None
    try:
        data = _read_token(claim)
    finally:
        try:
            claim.unlink()
        except OSError:
            pass
    if data is None or data != peek:                        # unreadable, or rewritten since the repo check
        return None
    pr, command, created = data.get("pr"), data.get("command"), data.get("created_at")
    if type(pr) is not int or pr != n or not _names_pr(command, n):
        return None
    if isinstance(created, bool) or not isinstance(created, (int, float)) or not math.isfinite(created):
        return None
    if not 0 <= time.time() - created < MERGE_TOKEN_TTL_S:
        return None
    return f"one-shot merge token for PR #{n} in {normalize_repo(data['repo'])} [D234], user command: {command}"


def write_merge_token(argv) -> int:
    """`guard.py merge-token N "<the user's literal command>"`: write the one-shot token for PR N of
    the repository the cwd's `origin` remote points to; refuses without such a remote."""
    if len(argv) != 2 or not re.fullmatch(r"\d+", argv[0]) or int(argv[0]) <= 0:
        print('usage: guard.py merge-token <PR number> "<the user\'s literal merge command>"', file=sys.stderr)
        return 2
    n, command = int(argv[0]), argv[1]
    if not _names_pr(command, n):
        print(f"refused: the user's command does not name PR {n}", file=sys.stderr)
        return 2
    repo = origin_repo(os.getcwd())
    if repo is None:
        print("refused: no `origin` remote in the current directory to bind the token to", file=sys.stderr)
        return 2
    folder = merge_token_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"pr-{n}.json"
    tmp = folder / f"pr-{n}.json.partial-{os.getpid()}"
    tmp.write_text(json.dumps({"pr": n, "repo": repo, "command": command, "created_at": time.time()},
                              ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)
    print(f"merge token for PR {n} in {repo}: {target} (TTL {MERGE_TOKEN_TTL_S} s, one use)")
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
        reasons = shell_reasons(cmd)
        reason = reasons[0] if reasons else None
        if reason == MERGE_REASON and all(why == MERGE_REASON for why in reasons):
            hook_cwd = None if is_antigravity else data.get("cwd")
            granted = merge_token_allows(cmd, hook_cwd if isinstance(hook_cwd, str) and hook_cwd else None)
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
