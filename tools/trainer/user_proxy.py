"""User Proxy [#2066]: answers a practice-run stop ONLY with an approved answer, else records UNRESOLVED.

Pattern: n/a | new-case: trainer user proxy - a separate process that answers practice stops from approved sources.

    python ask.py "QUESTION" [--class CLASS]                  # pack.json / log.jsonl next to this file
    python user_proxy.py ask --pack PACK.json --log LOG.jsonl [--class CLASS] "QUESTION"

Role split (Artem 2026-11-27): the proxy is NOT the evaluator. It reads only its pack (approved answers, each
verbatim from a cited D-row, job decision, fact export or past-delivery key fact, built and leak-checked by the
trainer); it never reads the bank, the hidden key or the scoring criteria, never invents a product decision,
never hints the method. A question that matches exactly one pack answer gets that answer verbatim + its source;
no match or an ambiguous match is UNRESOLVED (logged; the agent continues with the documented default or
stops). Every question is appended to the log with its stop class. Stdlib only; copied as RUN/proxy/ask.py.

Stop classes (--class, optional; a matched answer's own class wins):
  missing_source_data, customer_decision, irreversible_sanction  -> justified
  answer_in_repo, allowed_technical_choice                       -> unnecessary
  tool_broken (no recovery path)                                 -> harness problem
  instructions_contradict                                        -> context problem
Exit codes: 0 answered or UNRESOLVED (both logged), 2 refused pack or invalid input (nothing logged).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

STOP_CLASSES = {"missing_source_data": "justified", "customer_decision": "justified",
                "irreversible_sanction": "justified", "answer_in_repo": "unnecessary",
                "allowed_technical_choice": "unnecessary", "tool_broken": "harness",
                "instructions_contradict": "context"}
SOURCE_KINDS = ("d_row", "job_decision", "fact_export", "delivery_key")
PACK_KEYS = {"schema", "task", "answers"}
ANSWER_KEYS = {"id", "match", "answer", "source", "source_kind", "stop_class"}
# Defence in depth (the trainer checks the same before it writes a pack): an approved answer states a decision;
# it never names code, a command, the hidden key or how the run is judged.
HINTS = re.compile(r"\.py\b|\btools/|\bsrc/|\bagr\s+[a-z]|\bhidden\s+key\b|\btrainer\b|\btoleran|\bscor(e|ing)\b"
                   r"|\betalon", re.I)


class ProxyError(ValueError):
    """Refused pack or invalid input: exit 2, nothing logged."""


def _norm(s):
    return re.sub(r"\s+", " ", str(s).lower().replace("ё", "е")).strip()


def _words(s):
    return re.findall(r"\w+", _norm(s))


def _term_ok(term, words):
    """Whole-word match: a term is one word or a phrase of consecutive words; a trailing `*` on the last
    word is a prefix (`curb*` matches `curbs`, never `subcurb`)."""
    tw = _words(term)
    star = str(term).strip().endswith("*")
    for i in range(len(words) - len(tw) + 1 if tw else 0):
        if all(words[i + j] == w or (star and j == len(tw) - 1 and words[i + j].startswith(w))
               for j, w in enumerate(tw)):
            return True
    return False


def pack_problems(pack):
    """-> list of reasons to refuse the pack (empty when it is a clean approved-answer pack)."""
    if not isinstance(pack, dict) or pack.get("schema") != "user-proxy-pack/1":
        return ["schema must be user-proxy-pack/1"]
    out = [f"pack field {k!r} is not allowed" for k in sorted(set(pack) - PACK_KEYS)]
    answers = pack.get("answers")
    if not isinstance(answers, list):
        return out + ["answers must be a list"]
    seen = set()
    for i, a in enumerate(answers):
        aid = a.get("id", f"#{i}") if isinstance(a, dict) else f"#{i}"
        if not isinstance(a, dict):
            out.append(f"{aid}: not an object")
            continue
        out += [f"{aid}: field {k!r} is not allowed" for k in sorted(set(a) - ANSWER_KEYS)]
        out += [f"{aid}: missing {k}" for k in sorted(ANSWER_KEYS - set(a))]
        if aid in seen:
            out.append(f"{aid}: duplicate id")
        seen.add(aid)
        if not (isinstance(a.get("source"), str) and a["source"].strip()):
            out.append(f"{aid}: no cited source")
        if a.get("source_kind") not in SOURCE_KINDS:
            out.append(f"{aid}: source_kind must be one of {SOURCE_KINDS}")
        if a.get("stop_class") not in STOP_CLASSES:
            out.append(f"{aid}: unknown stop_class {a.get('stop_class')!r}")
        if not (isinstance(a.get("answer"), str) and a["answer"].strip()):
            out.append(f"{aid}: empty answer")
        elif HINTS.search(a["answer"]):
            out.append(f"{aid}: answer hints the method or the evaluation ({HINTS.search(a['answer']).group(0)!r})")
        m = a.get("match")
        if not (isinstance(m, list) and m and all(isinstance(g, list) and g and all(isinstance(t, str) and t.strip()
                                                                                  for t in g) for g in m)):
            out.append(f"{aid}: match must be a non-empty list of non-empty term lists")
        else:  # review r1: one generic word ("gap", "distance") answers unrelated questions
            out += [f"{aid}: match group {g} needs at least 2 distinct terms" for g in m
                    if len({" ".join(_words(t)) for t in g}) < 2]
    return out


def load_pack(path):
    try:
        pack = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProxyError(f"pack unreadable: {exc}") from exc
    problems = pack_problems(pack)
    if problems:
        raise ProxyError("pack refused: " + "; ".join(problems))
    return pack


def matches(pack, question):
    words = _words(question)
    return [a for a in pack["answers"] if any(all(_term_ok(t, words) for t in g) for g in a["match"])]


def answer(pack, question, declared=None):
    """-> log record. Exactly one matching approved answer -> answered verbatim; else unresolved."""
    if declared is not None and declared not in STOP_CLASSES:
        raise ProxyError(f"unknown --class {declared!r}; known: {sorted(STOP_CLASSES)}")
    if not str(question).strip():
        raise ProxyError("empty question")
    hits = matches(pack, question)
    one = hits[0] if len(hits) == 1 else None
    cls = one["stop_class"] if one else (declared or "unclassified")
    return {"schema": "user-proxy-log/1", "t": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "task": pack.get("task"), "question": str(question), "declared_class": declared,
            "verdict": "answered" if one else "unresolved", "answer_id": one["id"] if one else None,
            "answer": one["answer"] if one else None, "source": one["source"] if one else None,
            "source_kind": one["source_kind"] if one else None, "candidates": [a["id"] for a in hits],
            "stop_class": cls, "stop_group": STOP_CLASSES.get(cls, "unclassified")}


def main(argv=None):
    here = Path(__file__).resolve().parent
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] != ["ask"]:
        argv = ["ask", *argv]
    ap = argparse.ArgumentParser(prog="ask.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("question", nargs="+")
    a.add_argument("--pack", default=str(here / "pack.json"))
    a.add_argument("--log", default=str(here / "log.jsonl"))
    a.add_argument("--class", dest="cls", default=None, help=", ".join(STOP_CLASSES))
    ns = ap.parse_args(argv)
    try:
        rec = answer(load_pack(ns.pack), " ".join(ns.question), ns.cls)
    except ProxyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    with open(ns.log, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if rec["verdict"] == "answered":
        print(f"ANSWER (approved, source: {rec['source']}): {rec['answer']}")
    else:
        print("UNRESOLVED: no approved answer to this question; it is recorded. Continue with the documented "
              "default or stop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
