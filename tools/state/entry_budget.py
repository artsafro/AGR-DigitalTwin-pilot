"""Cold-entry token budget for a worker's first reads (#1015).

new-case: offline guard for the cold-entry read set measured with tiktoken o200k_base.

A cold worker reads AGENTS.md, docs/PROJECT_STATE.md, the card's area file and the
card itself before it starts. ``--write`` measures that set with tiktoken
``o200k_base`` (``uv run --no-project --with tiktoken python tools/state/entry_budget.py
--write``) and stores a receipt with chars and tokens per file. ``check`` runs offline:
each live file's tokens are estimated as ``ceil(tokens * live_chars / receipt_chars)``
(its own measured ratio), and the total must stay <= 10 000. A file that grew by more
than 25 % since the receipt fails with "re-measure". Fail closed on an empty,
partial, duplicated, out-of-tree or non-integer receipt and on a set without
AGENTS.md and docs/PROJECT_STATE.md.
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "tests" / "fixtures" / "cold_entry" / "receipt.json"
TOKENIZER = "tiktoken o200k_base"
BUDGET = 10_000
GROWTH = 0.25
REQUIRED = ("AGENTS.md", "docs/PROJECT_STATE.md")
ENTRY = ("AGENTS.md", "docs/PROJECT_STATE.md", "docs/domain/areas/derivation.md",
         "tests/fixtures/cold_entry/card-t_9e27c5ff.md")
CARD = "t_9e27c5ff (#968 AC08 kernel: invariants relative to the source)"


class FailClosed(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _count(value, name, rel):
    if type(value) is not int or value <= 0:
        raise FailClosed(f"{name} must be a positive integer: {rel}")
    return value


def _resolve(root, rel, seen):
    if not isinstance(rel, str) or rel.strip() == "":
        raise FailClosed("empty path in receipt")
    root = Path(root).resolve()
    path = (root / rel).resolve()
    if path != root and root not in path.parents:
        raise FailClosed(f"path outside the repository: {rel}")
    key = os.path.normcase(str(path))
    if key in seen:
        raise FailClosed(f"duplicate entry file: {rel}")
    seen.add(key)
    return path


def _text(path, rel):
    if not path.is_file():
        raise FailClosed(f"partial: entry file missing: {rel}")
    with path.open(encoding="utf-8", newline="") as source:
        text = source.read().replace("\r\n", "\n")  # checkout line endings must not move the total
    if text.strip() == "":
        raise FailClosed(f"empty entry file: {rel}")
    return text


def _load(receipt):
    receipt = Path(receipt)
    if not receipt.is_file():
        raise FailClosed(f"partial: receipt missing: {receipt}")

    def _reject(token):
        raise FailClosed(f"non-finite value in receipt: {token}")

    try:
        data = json.loads(receipt.read_text(encoding="utf-8"), parse_constant=_reject)
    except ValueError as exc:
        raise FailClosed(f"unsupported receipt: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise FailClosed("unsupported receipt schema")
    if data.get("tokenizer") != TOKENIZER:
        raise FailClosed(f"tokenizer must be {TOKENIZER}")
    if type(data.get("budget")) is not int or data["budget"] != BUDGET:
        raise FailClosed(f"budget must be {BUDGET}")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise FailClosed("empty entry set")
    return data, files


def check(root, receipt=RECEIPT, texts=None):
    """Return (rows, total) for the live entry set; raise FailClosed past the budget.

    ``texts`` maps an entry path to candidate text measured instead of the file on disk
    (``project_state.py`` checks its output before writing it, #1222).
    """
    texts = dict(texts or {})
    data, files = _load(receipt)
    seen, rows, measured = set(), [], 0
    for row in files:
        if not isinstance(row, dict):
            raise FailClosed("unsupported receipt row")
        rel = row.get("path")
        path = _resolve(root, rel, seen)
        chars = _count(row.get("chars"), "chars", rel)
        tokens = _count(row.get("tokens"), "tokens", rel)
        measured += tokens
        if rel in texts:
            candidate = texts.pop(rel)
            if not isinstance(candidate, str) or candidate.strip() == "":
                raise FailClosed(f"empty entry file: {rel}")
            live = len(candidate.replace("\r\n", "\n"))
        else:
            live = len(_text(path, rel))
        if live > chars * (1 + GROWTH):
            raise FailClosed(f"{rel} grew {chars} -> {live} chars (> {GROWTH:.0%}); re-measure with --write")
        rows.append({"path": rel, "tokens": tokens, "chars": chars, "live_chars": live,
                     "estimate": math.ceil(tokens * live / chars)})
    if texts:
        raise FailClosed(f"candidate text for a path outside the entry set: {sorted(texts)}")
    names = {row["path"] for row in rows}
    for name in REQUIRED:
        if name not in names:
            raise FailClosed(f"entry set must contain {name}")
    if type(data.get("total_tokens")) is not int or data["total_tokens"] != measured:
        raise FailClosed(f"receipt total_tokens {data.get('total_tokens')!r} != sum {measured}")
    total = sum(row["estimate"] for row in rows)
    if total > BUDGET:
        raise FailClosed(f"over budget: {total} > {BUDGET} tokens ({TOKENIZER})")
    return rows, total


def _tiktoken_counter():
    try:
        import tiktoken
    except ImportError as exc:
        raise FailClosed("tiktoken missing: run with `uv run --no-project --with tiktoken`") from exc
    encoding = tiktoken.get_encoding("o200k_base")
    return lambda text: len(encoding.encode(text))


def write_receipt(root, rels, card, output, counter=None):
    """Measure ``rels`` and write the receipt atomically; never write onto an entry file."""
    counter = counter or _tiktoken_counter()
    seen, files = set(), []
    paths = [_resolve(root, rel, seen) for rel in rels]
    output = Path(output).resolve()
    if os.path.normcase(str(output)) in seen or any(p.exists() and output.exists()
                                                   and os.path.samefile(p, output) for p in paths):
        raise FailClosed(f"receipt path is an entry file: {output}")
    for rel, path in zip(rels, paths):
        text = _text(path, rel)
        files.append({"path": rel, "chars": len(text), "tokens": _count(counter(text), "tokens", rel)})
    data = {"schema": 1, "tokenizer": TOKENIZER, "budget": BUDGET, "card": card,
            "files": files, "total_tokens": sum(row["tokens"] for row in files)}
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    with partial.open("w", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(partial, output)
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cold-entry token budget (tiktoken o200k_base, <= 10000).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="offline check against the receipt")
    mode.add_argument("--write", action="store_true", help="measure with tiktoken and rewrite the receipt")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args(argv)
    try:
        if args.write:
            data = write_receipt(ROOT, list(ENTRY), CARD, args.receipt)
            print(f"wrote {args.receipt}: {data['total_tokens']} tokens")
        rows, total = check(ROOT, args.receipt)
    except FailClosed as exc:
        print(f"entry_budget: {exc.reason}", file=sys.stderr)
        return 1
    for row in rows:
        print(f"{row['path']}\t{row['estimate']}")
    print(f"total {total} / {BUDGET} tokens ({TOKENIZER})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
