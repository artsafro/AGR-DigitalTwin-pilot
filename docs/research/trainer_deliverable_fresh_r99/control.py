"""OBSERVE #99 scorer-rule control on KPP1: accepted key vs Artem-rejected step 3, clean vs injected decoy.

Pattern: new-case: docs/research/trainer_deliverable_fresh_r99 - OBSERVE #99 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_fresh_r99/control.py NEW_DIR

Stages four copies (never edits the Drive originals): acc_clean (built/deliverable.fbx = accepted v004 key),
acc_inj (+ built/decoy.fbx = rejected step 3), rej_clean (deliverable = rejected), rej_inj (+ decoy = accepted).
Each staged dir is scored twice: arm C (directory) and arm D (`pick.built_arg`). Expected: C refuses both injected
dirs; D score of *_inj == *_clean exactly; accepted scores above rejected (calibration).
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick import built_arg  # noqa: E402

ACC = ("G:/Мой диск/AGR-evidence/1609-kpp1-package-v004/draft-b25/master/SM_Kpp_1.v004-lattice.fbx",
       "f9705f7487b4e89131ae932224e86bc82952a768aeb6b508ee33e5938d1adbb8")
REJ = ("G:/Мой диск/AGR-evidence/1609-kpp1-lattice-posts/step3/SM_Kpp_1.v004-lattice.fbx", None)
CASES = {"acc_clean": (ACC, None), "acc_inj": (ACC, REJ), "rej_clean": (REJ, None), "rej_inj": (REJ, ACC)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(out):
    out = Path(out)
    if out.exists():
        raise SystemExit(f"{out} exists; NEW dir only")
    if sha(ACC[0]) != ACC[1]:
        raise SystemExit("accepted key hash mismatch")
    res = {"inputs": {"accepted": [ACC[0], sha(ACC[0])], "rejected": [REJ[0], sha(REJ[0])]}, "cases": {}}
    for name, (dl, decoy) in CASES.items():
        built = out / name / "built"
        built.mkdir(parents=True)
        shutil.copyfile(dl[0], built / "deliverable.fbx")
        if decoy:
            shutil.copyfile(decoy[0], built / "decoy.fbx")
        row: dict = {"files": {p.name: sha(p) for p in sorted(built.iterdir())}}
        for arm in ("C", "D"):
            arg = built_arg(out / name, arm)
            sj = out / name / f"score_{arm}.json"
            p = subprocess.run(["uv", "run", "--quiet", "agr", "trainer", "score", "kpp1-v004", "--built", arg,
                                "--out", str(sj)], capture_output=True, text=True)
            sc = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
            row[arm] = {"built": Path(arg).name, "rc": p.returncode, "score": sc.get("score"),
                        "first_failing_step": sc.get("first_failing_step"),
                        "steps": {k: v.get("status") for k, v in sc.get("steps", {}).items()},
                        "tail": (p.stdout + p.stderr).strip()[-200:] if p.returncode else ""}
        res["cases"][name] = row
        print(name, json.dumps({a: (row[a]["rc"], row[a]["score"], row[a]["first_failing_step"]) for a in "CD"}))
    (out / "control.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
