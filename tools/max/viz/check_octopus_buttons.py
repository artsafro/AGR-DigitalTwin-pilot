"""Read-only Octopus button installation check (no MAXScript execution).

new-case: standalone Octopus XML/main-action parser and static fileIn validation.
Field names active and filein_paths match docs/agr/inventory/octopus-bindings.json.
Only literal fileIn arguments are supported; unknown expressions fail closed.
A static pass does not establish that a real Octopus click works.
"""

import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def tokenize(command):
    """Lex strings/comments so fileIn inside them cannot masquerade as a call."""
    tokens = []
    i = 0
    while i < len(command):
        if command.startswith("--", i):
            end = command.find("\n", i)
            i = len(command) if end < 0 else end
        elif command.startswith("/*", i):
            end = command.find("*/", i + 2)
            if end < 0:
                raise ValueError("unterminated MAXScript comment")
            i = end + 2
        elif command[i] == '"' or command.startswith('@"', i):
            verbatim = command[i] == "@"
            i += 2 if verbatim else 1
            value = ""
            while i < len(command) and command[i] != '"':
                if not verbatim and command[i] == "\\" and i + 1 < len(command):
                    following = command[i + 1]
                    escapes = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}
                    value += escapes.get(following, "\\" + following)
                    i += 2
                else:
                    value += command[i]
                    i += 1
            if i == len(command):
                raise ValueError("unterminated MAXScript string")
            tokens.append(("string", value))
            i += 1
        elif command[i].isspace():
            if command[i] in "\r\n":
                tokens.append(("end", ";"))
            i += 1
        else:
            word = re.match(r"#?[A-Za-z_][A-Za-z_0-9]*", command[i:])
            if word:
                tokens.append(("word", word[0]))
                i += len(word[0])
            else:
                char = command[i]
                tokens.append(("end" if char == ";" else "symbol", char))
                i += 1
    return tokens


def filein_paths(tokens, max_dirs):
    """Resolve each call independently; no eval, search-path guessing or fallback."""
    paths, errors = [], []
    for i, token in enumerate(tokens):
        if token[0] != "word" or token[1].lower() != "filein":
            continue
        tail = tokens[i + 1:]
        path = None
        consumed = 0
        if tail and tail[0][0] == "string":
            path, consumed = tail[0][1], 1
        elif (len(tail) >= 8 and [t[1].lower() for t in tail[:3]] == ["(", "(", "getdir"]
              and tail[3][0] == "word" and tail[3][1].startswith("#")
              and [t[1] for t in tail[4:6]] == [")", "+"]
              and tail[6][0] == "string" and tail[7][1] == ")"):
            key = tail[3][1][1:].lower()
            if key not in max_dirs:
                errors.append("unmapped getDir key: " + key)
                continue
            path = max_dirs[key].rstrip("/\\") + tail[6][1]
            consumed = 8
        if path is None or (len(tail) > consumed and tail[consumed][0] != "end"
                            and tail[consumed][1] != ")"):
            errors.append("unsupported fileIn argument at token " + str(i))
            continue
        if not path or any(ord(c) < 32 for c in path) or not Path(path).is_absolute():
            errors.append("fileIn path must be nonempty, absolute, without control characters: " + repr(path))
            continue
        paths.append(Path(path).as_posix())
    return paths, errors


def check_menu(menu, labels, max_dirs=None):
    """Return one diagnostic per requested label, inspecting only its first action."""
    data = Path(menu).read_bytes()
    # Decode before the declaration check, including UTF-16 menus.
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        declaration_text = data.decode("utf-16")
    else:
        declaration_text = data.decode("utf-8-sig")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", declaration_text, re.I):
        raise ValueError("DTD/entity declarations are unsupported")
    root = ET.fromstring(data)
    if root.tag != "OctopusDataWrapper":
        raise ValueError("unsupported Octopus XML root: " + root.tag)
    if not labels or any(not label.strip() for label in labels):
        raise ValueError("at least one non-empty button label is required")
    rows = []
    for label in labels:
        matches = [b for b in root.iter() if b.get("ButtonText") == label]
        errors = []
        row: dict[str, object] = dict(label=label, found=bool(matches), active=None,
                   command_nonempty=False, filein_paths=[], filein_paths_exist=False)
        if len(matches) != 1 or labels.count(label) != 1:
            errors.append("missing or duplicate button label: " + label)
        else:
            button = matches[0]
            if button.tag not in {"LocalButtonDataList", "ActionButtonDataList"}:
                errors.append("unsupported button element: " + button.tag)
            if button.get("IsActive") != "true":
                errors.append("button IsActive is not true")
            actions = button.findall("./buttonActionData/actionDataList")
            if not actions:
                errors.append("missing main action")
            else:
                action = actions[0]
                row["active"] = action.get("active")
                if row["active"] != "true":
                    errors.append("main action active is not true")
                commands = action.findall("command")
                if len(commands) != 1 or list(commands[0]):
                    errors.append("main action must have exactly one text command")
                command = action.findtext("command", "")
                row["command_nonempty"] = bool(command.strip())
                if not row["command_nonempty"]:
                    errors.append("main command is empty")
                try:
                    tokens = tokenize(command)
                    if not tokens:
                        errors.append("main command has no executable tokens")
                    paths, path_errors = filein_paths(tokens, max_dirs or {})
                    errors.extend(path_errors)
                    row["filein_paths"] = paths
                    missing = [p for p in paths if not Path(p).is_file()]
                    row["filein_paths_exist"] = not missing and not path_errors
                    errors.extend("missing fileIn target: " + p for p in missing)
                except ValueError as exc:
                    errors.append(str(exc))
        row["errors"] = errors
        row["passed"] = not errors
        rows.append(row)
    return dict(buttons=rows, passed=all(row["passed"] for row in rows))


def main(argv=None):
    """Print JSON diagnostics; exit 0 only when every requested button passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("menu", type=Path)
    parser.add_argument("labels", nargs="+")
    parser.add_argument("--max-dir", action="append", default=[], metavar="KEY=PATH",
                        help="explicit getDir mapping from the target Max configuration; repeatable")
    args = parser.parse_args(argv)
    try:
        max_dirs = {}
        for item in args.max_dir:
            key, separator, value = item.partition("=")
            key = key.lower()
            if (not separator or not re.fullmatch(r"[a-z][a-z0-9_]*", key)
                    or not Path(value).is_absolute() or key in max_dirs):
                raise ValueError("invalid or duplicate --max-dir mapping: " + item)
            max_dirs[key] = value
        report = check_menu(args.menu, args.labels, max_dirs)
    except (OSError, ValueError, ET.ParseError) as exc:
        print(json.dumps(dict(passed=False, error=str(exc)), ensure_ascii=True))
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
