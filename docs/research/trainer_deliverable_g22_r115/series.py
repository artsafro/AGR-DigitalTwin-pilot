"""OBSERVE #115 series driver: 3 G22 pairs (C_i || D_i started together), each run scored right after it ends.

Pattern: new-case: docs/research/trainer_deliverable_g22_r115 - OBSERVE #115 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_g22_r115/series.py ROOTS_DIR [--only NAME ...]

ROOTS_DIR holds R/ (practice root), bank_C.json, bank_D.json from make_roots.py. Both arms run R/tools/trainer/trainer.py
(same origin/main commit, same scorer); arm C uses bank_C (git bank bytes), arm D bank_D (+ H99 sentence).
--built per arm = the #99 pick rule (research/autoresearch-standing-99 pick.py, blob eccedca4): arm D scores
`built/deliverable.fbx` when that exact ROOT file exists, otherwise `built/`; arm C always scores `built/`.
Writes C:/x/trainer/runs/g22-k2-stage1-codex-r115-<arm><i>/ (+ score.json); log C:/x/ev_t_a457c1b6/series.log.
Budget stop (frozen): no new pair starts later than 60 min after the series start; unstarted runs are `not_run`.
"""
import subprocess
import sys
import time
from pathlib import Path

RUNS = Path("C:/x/trainer/runs")
LOG = Path("C:/x/ev_t_a457c1b6/series.log")
ETALON = "g22-k2-stage1"
BUDGET_S = 60 * 60
NAME = "deliverable.fbx"


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def built_arg(run_dir, arm):
    built = Path(run_dir) / "built"
    if arm == "D" and built.is_dir() and NAME in {p.name for p in built.iterdir() if p.is_file()}:
        return str(built / NAME)
    return str(built)


def trainer(roots, arm):
    return ["uv", "run", "--frozen", "--quiet", "python", str(Path(roots) / "R/tools/trainer/trainer.py"),
            "--bank", str(Path(roots) / f"bank_{arm}.json")]


def main(roots, only=()):
    t0 = time.time()
    for i in (1, 2, 3):
        if time.time() - t0 > BUDGET_S:
            log(f"BUDGET STOP before pair {i}")
            break
        procs = []
        for arm in ("C", "D"):
            name = f"{ETALON}-codex-r115-{arm}{i}"
            if only and name not in only:
                continue
            cmd = [*trainer(roots, arm), "run", ETALON, "--out", str(RUNS / name), "--timeout-s", "1800"]
            log("start " + name)
            procs.append((name, arm, subprocess.Popen(cmd, stdout=open(LOG.parent / f"{name}.out", "w"),
                                                       stderr=subprocess.STDOUT)))
        for name, arm, p in procs:
            rc = p.wait()
            log(f"done {name} rc={rc}")
            built = built_arg(RUNS / name, arm)
            sc = subprocess.run([*trainer(roots, arm), "score", ETALON, "--built", built,
                                 "--out", str(RUNS / name / "score.json")], capture_output=True, text=True)
            log(f"score {name} built={built} rc={sc.returncode} {(sc.stdout + sc.stderr).strip()[-300:]}")
    log("SERIES DONE")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], tuple(a[2:]) if len(a) > 1 and a[1] == "--only" else ())
