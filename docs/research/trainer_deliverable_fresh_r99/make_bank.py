"""OBSERVE #99: scratch bank for arm D = the #95 arm-C bank + one frozen H99 sentence on kpp1-v004.

Pattern: new-case: docs/research/trainer_deliverable_fresh_r99 - OBSERVE #99 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_fresh_r99/make_bank.py BANK_R95_C.json NEW_BANK_D.json

BANK_R95_C.json must hash to R95_C_SHA (#95 `make_bank.py` of research/autoresearch-standing-95 applied to the git
bank 016aab0c...). The git bank is never edited (owner #1855/#1861). Prints the SHA-256 of the source and new bank.
"""
import hashlib
import json
import sys
from pathlib import Path

R95_C_SHA = "51c6e51e98cc5152f5f4873f948523c9f6e07981088d57bf616b13b04a5ced3a"
FIXTURE = "kpp1-v004"
CANDIDATE = (
    "Deliverable file [H99]: save the final model as one FBX named exactly `deliverable.fbx` directly in the output "
    "folder, and replace it whenever you have a better complete model; when that file exists the scorer reads only "
    "it, so intermediate, per-band or test FBX elsewhere in the output folder are ignored."
)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(src, dst):
    src, dst = Path(src), Path(dst)
    if sha(src) != R95_C_SHA:
        raise SystemExit(f"source bank hash {sha(src)} != {R95_C_SHA}")
    if dst.exists():
        raise SystemExit(f"{dst} exists; the bank is a NEW file")
    data = json.loads(src.read_text(encoding="utf-8"))
    hit = [e for e in data["etalons"] if e["id"] == FIXTURE]
    if len(hit) != 1:
        raise SystemExit(f"fixture {FIXTURE} found {len(hit)} times")
    hit[0]["task"] = hit[0]["task"].rstrip() + " " + CANDIDATE
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in (src, dst):
        print(sha(p), p)


if __name__ == "__main__":
    main(*sys.argv[1:3])
