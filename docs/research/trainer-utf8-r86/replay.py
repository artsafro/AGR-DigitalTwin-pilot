"""Standing #86 read-only input replay; never executes saved agent commands."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from statistics import median

from tools.trainer.trainer import count_questions

FIXTURES = {
    "kpp1-v004-codex-20261124": (
        "item_25", "a7f4358322cb44ab8d308042cb520ac13b173ff41a8d4edae44dde6f8191e461",
        "81eea996a8b0f31d263e6077d7a2d49876af991e5d5dd28850dc20dfa05c1e8b",
    ),
    "g22-k2-stage1-codex-r83-C3": (
        "item_15", "053c3a2b4c2445db68cf9460f100d43a3b00bcd56471d0b19269e1bd6fd76a6d",
        "d99e518d80d00b68dbccafb67a3102436282f53aa8cd8282ae9a89d273204301",
    ),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pinned(path, expected):
    data = path.read_bytes()
    if sha(data) != expected:
        raise ValueError(f"fixture hash mismatch: {path}")
    return data


def asset(root, name, spec):
    event_id, event_sha, file_sha = spec
    events = pinned(root / name / "events.jsonl", event_sha)
    original = pinned(root / name / "built" / "QUESTIONS.md", file_sha)
    [command] = [
        row["item"]["command"] for line in events.decode("utf-8").splitlines()
        if (row := json.loads(line))["type"] == "item.completed"
        and row["item"].get("id") == event_id
    ]
    return command.splitlines(), original


def question(name, lines, original):
    if name.startswith("kpp1-"):
        start = next(i for i, line in enumerate(lines) if "$q=@" in line) + 1
        end = next(i for i in range(start, len(lines)) if lines[i].startswith(("'@", "'\"'@", "\"'@")))
        text = "\n".join(lines[start:end])
    else:
        [line] = [line for line in lines if line.startswith("q.write_text(")]
        # The rendered event doubles backslashes. Reuse only invariant ASCII substitutions
        # from the pinned output; never evaluate the agent's f-string or execute its script.
        fields = ("p", "filehash", "approval")
        for field in fields:
            token = "`{" + field + "}`"
            rendered = f"\"'{token}'\""
            if line.count(rendered) != 1:
                raise ValueError(f"unexpected shell rendering for {field}")
            line = line.replace(rendered, token)
        call = ast.parse(line.replace("\\\\", "\\"), mode="eval").body
        if not isinstance(call, ast.Call) or not isinstance(literal := call.args[0], ast.JoinedStr):
            raise ValueError("expected a question f-string")
        native = original.decode("utf-8")
        [path] = re.findall(r"`([A-Z]:\\[^`]+\\parts\.json)`", native)
        filehash, approval = re.findall(r"\b[0-9a-f]{64}\b", native)
        substitutions: dict[str, str] = dict(zip(fields, (path, filehash, approval), strict=True))
        chunks = []
        seen = []
        for node in literal.values:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                chunks.append(node.value)
            elif (isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Name)
                  and node.conversion == -1 and node.format_spec is None):
                seen.append(node.value.id)
                chunks.append(substitutions[node.value.id])
            else:
                raise ValueError("unsupported expression in authored question")
        if tuple(seen) != fields:
            raise ValueError(f"unexpected question substitutions: {seen}")
        text = "".join(chunks)
    ending = "\r\n" if b"\r\n" in original else "\n"
    return text.replace("\n", ending)


def ps_string(text):
    return "'" + str(text).replace("'", "''") + "'"


def transport(folder, shell, text, fixed, timeout):
    child_file = folder / "out.txt"
    script_file = folder / "transport.ps1"
    child = (
        "from pathlib import Path\n"
        f"Path({str(child_file)!r}).write_text({text!r}, encoding='utf-8', newline='')\n"
    )
    setup = "$OutputEncoding = [System.Text.UTF8Encoding]::new($false)\n" if fixed else ""
    source = (
        "$ErrorActionPreference = 'Stop'\n" + setup
        + f"@'\n{child}'@ | & {ps_string(sys.executable)} -X utf8 -\n"
        + "exit $LASTEXITCODE\n"
    )
    script_file.write_text(source, encoding="utf-8-sig")
    start = time.perf_counter()
    subprocess.run([shell, "-NoProfile", "-NonInteractive", "-File", str(script_file)],
                   capture_output=True, check=True, timeout=timeout)
    return child_file.read_text(encoding="utf-8", newline=""), round(time.perf_counter() - start, 3)


def changes(a, b):
    return sum(x != y for x, y in zip(a, b, strict=True)) if len(a) == len(b) else None


def measure(inputs, root, shell):
    t0 = time.perf_counter()
    receipt = {}
    with tempfile.TemporaryDirectory(prefix="r86-", dir=root) as tmp:
        folder = Path(tmp)
        for name, (text, original, damaged) in inputs.items():
            pairs = []
            for i in range(3):
                pair = {}
                for fixed in (False, True) if i % 2 == 0 else (True, False):
                    remaining = 120 - (time.perf_counter() - t0)
                    out, seconds = transport(folder, shell, text, fixed, remaining)
                    pair["utf8" if fixed else "default"] = {
                        "changed": changes(text, out), "wall_s": seconds,
                        "sha256": sha(out.encode("utf-8")),
                        "question_count": count_questions(out),
                        "newline_count": out.count("\n"),
                        "native_match": None if original is None else out.encode("utf-8") == original,
                    }
                pairs.append(pair)
            receipt[name] = {
                "kind": "injected" if original is None else "native-damaged" if damaged else "native-clean",
                "authored_sha256": sha(text.encode("utf-8")), "questions": count_questions(text),
                "newlines": text.count("\n"), "non_ascii": sum(not c.isascii() for c in text), "pairs": pairs,
            }
    return receipt, round(time.perf_counter() - t0, 3)


def summarize(records):
    passed = True
    for record in records.values():
        pairs = record["pairs"]
        gains = []
        for pair in pairs:
            baseline, candidate = pair["default"], pair["utf8"]
            valid = baseline["changed"] is not None and candidate["changed"] == 0
            valid &= all(x["question_count"] == record["questions"] and x["newline_count"] == record["newlines"]
                         for x in pair.values())
            if record["kind"] == "native-damaged":
                valid &= baseline["native_match"] is True
            elif record["kind"] == "native-clean":
                valid &= candidate["native_match"] is True
            valid &= baseline["changed"] is not None and (baseline["changed"] > 0) == bool(record["non_ascii"])
            if baseline["changed"] is not None and candidate["changed"] is not None:
                gains.append(baseline["changed"] - candidate["changed"])
            passed &= valid
        record["paired_gain_median"] = median(gains) if len(gains) == 3 else None
        record["paired_gain_range"] = [min(gains), max(gains)] if len(gains) == 3 else None
    return "confirmed" if passed else "refuted"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--inspect-anchors", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    run_root = Path("C:/x/trainer/runs")
    inputs = {}
    for name, spec in FIXTURES.items():
        lines, original = asset(run_root, name, spec)
        if args.inspect_anchors:
            for i, line in enumerate(lines):
                if re.search(r"\$q=@|q\.write_text|StreamWriter|^.{0,3}'@", line):
                    print(name, i, ascii(line[:37]), ascii(line[-42:]))
            print("bytes", len(original), "CRLF", original.count(b"\r\n"))
            continue
        inputs[name] = (question(name, lines, original), original, name.startswith("g22-"))
    if args.inspect_anchors:
        return
    if args.out is None or args.out.exists():
        parser.error("--out must be a new file")
    tuning = next(iter(inputs.values()))[0]
    inputs["ascii"] = ("1. What is the scale?\n2. Is approval absent?\n", None, False)
    inputs["mixed-script"] = (tuning + "\nControl: é — Ё 漢\n", None, False)
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    records, wall = measure(inputs, root, shell)
    report = {"hypothesis": summarize(records), "run_status": "complete", "wall_s": wall,
              "python": sys.version.split()[0], "records": records}
    with args.out.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(report["hypothesis"], wall, {k: v["paired_gain_median"] for k, v in records.items()})


if __name__ == "__main__":
    main()
