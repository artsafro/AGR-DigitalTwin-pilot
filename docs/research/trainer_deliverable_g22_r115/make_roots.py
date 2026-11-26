"""OBSERVE #115: the scratch practice root (main + the #97 promoted Revit NPZ adapter) and the arm-D bank.

Pattern: new-case: docs/research/trainer_deliverable_g22_r115 - OBSERVE #115 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_g22_r115/make_roots.py SRC_REPO DST_DIR

Adapted copy of research/autoresearch-standing-97 `make_candidate.py` (blob 3bfa83dd): the SKELETONS row that names
`floor_from_dump.py` moved to docs/agents/SKELETONS-stages.md on main (hygiene batches), text unchanged. Creates
DST_DIR/R = `git clone --shared` of BASE + ONE commit (the two hooks copied to tools/methods/body, two path lines fixed,
the stage row naming the adapter by path) and points R's origin/main at it (agr trainer run archives origin/main of
the repo that holds trainer.py). Writes DST_DIR/bank_C.json (byte copy of the git bank) and DST_DIR/bank_D.json
(the same bank + the #99 H99 sentence, verbatim, appended to the g22-k2-stage1 task). Never edits SRC_REPO.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

BASE = "55b885c1b9ccdbe53df2c0d6ade9d4e5bd8ca364"
BANK_SHA = "016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635"
FIXTURE = "g22-k2-stage1"
HOOKS = "jobs/garibaldi22/body-training-1619/hooks"
# H99 sentence, verbatim from research/autoresearch-standing-99 make_bank.py (frozen on KPP1, never tuned on G22).
CANDIDATE = (
    "Deliverable file [H99]: save the final model as one FBX named exactly `deliverable.fbx` directly in the output "
    "folder, and replace it whenever you have a better complete model; when that file exists the scorer reads only "
    "it, so intermediate, per-band or test FBX elsewhere in the output folder are ignored."
)
EDITS = {
    "tools/methods/body/module_build.py": [
        ('_CORE_DIR = Path(__file__).resolve().parents[4] / "tools" / "methods" / "body"',
         "_CORE_DIR = Path(__file__).resolve().parent"),
        ("ROOT = Path(__file__).resolve().parents[4]", "ROOT = Path(__file__).resolve().parents[3]"),
    ],
    "docs/agents/SKELETONS-stages.md": [
        ("Revit `floor_from_dump.py`", "Revit NPZ crop `tools/methods/body/floor_from_dump.py`"),
    ],
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def main(src, out):
    out = Path(out)
    r = out / "R"
    if r.exists():
        raise SystemExit(f"{r} exists; the practice root is a NEW folder")
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(src), str(r)], check=True)
    git(r, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", BASE)
    for name in ("floor_from_dump.py", "module_build.py"):
        (r / "tools/methods/body" / name).write_bytes((r / HOOKS / name).read_bytes())
    for rel, pairs in EDITS.items():
        p = r / rel
        t = p.read_text(encoding="utf-8")
        for old, new in pairs:
            if t.count(old) != 1:
                raise SystemExit(f"{rel}: expected one {old!r}, found {t.count(old)}")
            t = t.replace(old, new)
        p.write_bytes(t.encode("utf-8"))
    git(r, "add", "-A")
    git(r, "-c", "user.name=r115", "-c", "user.email=r115@local", "commit", "-q", "--no-verify", "-m",
        "r115 root: #97 adapter promoted to tools/methods/body, stage row 3 names it by path")
    head = git(r, "rev-parse", "HEAD")
    git(r, "update-ref", "refs/remotes/origin/main", head)
    bank = r / "docs/trainer/etalons.json"
    if sha(bank) != BANK_SHA:
        raise SystemExit(f"bank {sha(bank)} != {BANK_SHA}")
    (out / "bank_C.json").write_bytes(bank.read_bytes())
    data = json.loads(bank.read_text(encoding="utf-8"))
    hit = [e for e in data["etalons"] if e["id"] == FIXTURE]
    if len(hit) != 1:
        raise SystemExit(f"fixture {FIXTURE} found {len(hit)} times")
    hit[0]["task"] = hit[0]["task"].rstrip() + " " + CANDIDATE
    (out / "bank_D.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("root", head, "tree", git(r, "rev-parse", "HEAD^{tree}"))
    for p in ("bank_C.json", "bank_D.json"):
        print(sha(out / p), p)
    print(git(r, "diff", "--stat", BASE, head))


if __name__ == "__main__":
    main(*sys.argv[1:3])
