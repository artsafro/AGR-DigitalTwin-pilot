"""OBSERVE #95: scratch practice bank for arm C (one frozen sentence appended to the task of the two fixtures).

uv run --frozen python docs/research/trainer-artifact-first-r95/make_bank.py SRC_BANK.json NEW_BANK.json

The git bank is never edited (owner #1855/#1861). Prints the SHA-256 of the source and the new bank.
"""
import hashlib
import json
import sys
from pathlib import Path

FIXTURES = ("kpp1-v004", "g22-k2-stage1")
CANDIDATE = (
    "Practice deliverable order [H95]: write the body FBX into the output folder FIRST, built from the sources you "
    "can already read with the shared body route (contour or crop -> BodyPlan -> `agr body`), before finishes, "
    "GeoJSON, UCX or packaging. A missing source or a decision needed only by a later stage goes to QUESTIONS.md "
    "and does not stop the body FBX; then continue with the remaining stages."
)


def main(src, dst):
    src, dst = Path(src), Path(dst)
    if dst.exists():
        raise SystemExit(f"{dst} exists; the bank is a NEW file")
    data = json.loads(src.read_text(encoding="utf-8"))
    hit = 0
    for e in data["etalons"]:
        if e["id"] in FIXTURES:
            e["task"] = e["task"].rstrip() + " " + CANDIDATE
            hit += 1
    if hit != len(FIXTURES):
        raise SystemExit(f"fixtures found {hit}/{len(FIXTURES)}")
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in (src, dst):
        print(hashlib.sha256(p.read_bytes()).hexdigest(), p)


if __name__ == "__main__":
    main(*sys.argv[1:3])
