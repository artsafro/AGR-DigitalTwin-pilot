"""OBSERVE #115 static control of the #99 pick rule on G22 files (no agent): witness, accepted control, perturbations.

Pattern: new-case: docs/research/trainer_deliverable_g22_r115 - OBSERVE #115 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_g22_r115/control.py ROOTS_DIR OUT_JSON [REPS]

Scores with ROOTS_DIR/R/tools/trainer/trainer.py `score()` and bank_D.json (the scorer is main's, unchanged). Each case
is a NEW folder under C:/x/ev_t_a457c1b6/control/<rep>/ built from pinned inputs (SHA-256 checked first). The arm-D
rule = `built/deliverable.fbx` if that ROOT file exists, else the folder (trainer refuses several FBX). The arm-C
rule = the folder. allow_key=True only where the accepted key itself is the deliverable (calibration, as calibrate()).
"""
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

EV = Path("C:/x/ev_t_a457c1b6/control")
BANK = "G:/Мой диск/AGR-evidence/1855-trainer-v0/bank/g22-k2-stage1"
RUNS = Path("C:/x/trainer/runs")
INPUTS = {
    "accepted": (f"{BANK}/k2_v002r1_body_quad.fbx", "5b1e8d76c81de07dd62a94a1419a1f0bb6f5c82bd069592c2453f21b94f0f200"),
    "rejected": (f"{BANK}/k2_v001_body_quad.fbx", "8e97a80af2de0a22fae5d689a193762fe5ff2d90eb4b83106e35d5c78a5eb519"),
    "typical": (str(RUNS / "g22-k2-stage1-codex-r97-C2/built/typical/body.fbx"),
                "223f5bf0c562775d2847ed3e1b6c7a6b0d055d33711f541543ed8f33f73ed6be"),
    "module": (str(RUNS / "g22-k2-stage1-codex-r97-C1/built/module/body.fbx"),
               "c74148d00c3805c806f14c443bad9f7790b41538dc7f9f515f0f5451eae9dc4d"),
}
NAME = "deliverable.fbx"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pick(built, arm):
    built = Path(built)
    if arm == "D" and built.is_dir() and NAME in {p.name for p in built.iterdir() if p.is_file()}:
        return built / NAME
    return built


def case_dir(root, files):
    """files: {relative path: input name}."""
    root.mkdir(parents=True)
    for rel, src in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(INPUTS[src][0], root / rel)
    return root


CASES = {  # name: (files, allow_key)
    "W_witness": ({NAME: "typical", "module/body.fbx": "module"}, False),
    "A_accepted": ({NAME: "accepted", "module/body.fbx": "module"}, True),
    "R_rejected": ({NAME: "rejected", "module/body.fbx": "module"}, False),
    "P1_absent": ({"typical/body.fbx": "typical", "module/body.fbx": "module"}, False),
    "P2_module_named": ({NAME: "module", "typical/body.fbx": "typical"}, False),
    "P3_nested_only": ({"typical/" + NAME: "typical", "module/body.fbx": "module"}, False),
}
DIRECT = {"accepted": True, "rejected": False, "typical": False, "module": False}


def run_score(tr, e, built, out, allow_key):
    try:
        r = tr.score(e, str(built), str(out), allow_key=allow_key)
        return {"status": "scored", "first_failing_step": r["first_failing_step"], "score": r["score"],
                "form_p95_m": r["form_p95_m"]}
    except tr.TrainerError as ex:
        return {"status": "refused", "error": str(ex)[:160]}


def main(roots, out_json, reps=3):
    pins = {}
    for k, (p, want) in INPUTS.items():
        pins[k] = {"path": p, "sha256": sha(p)}
        if want and pins[k]["sha256"] != want:
            raise SystemExit(f"{k}: {pins[k]['sha256']} != {want}")
    spec = importlib.util.spec_from_file_location("trainer_r115", Path(roots) / "R/tools/trainer/trainer.py")
    assert spec is not None and spec.loader is not None
    tr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tr)
    e = tr.etalon(tr.load_bank(str(Path(roots) / "bank_D.json")), "g22-k2-stage1")
    res = {"inputs": pins, "reps": []}
    for rep in range(1, int(reps) + 1):
        base = EV / f"rep{rep}"
        if base.exists():
            raise SystemExit(f"{base} exists; control folders are NEW")
        row = {"direct": {}, "cases": {}}
        for k, ak in DIRECT.items():
            row["direct"][k] = run_score(tr, e, INPUTS[k][0], base / f"direct_{k}", ak)
        for name, (files, ak) in CASES.items():
            d = case_dir(base / "in" / name, files)
            row["cases"][name] = {arm: run_score(tr, e, pick(d, arm), base / f"{name}_{arm}", ak) for arm in "CD"}
        res["reps"].append(row)
        print(json.dumps(row, ensure_ascii=False))
    Path(out_json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:4])
