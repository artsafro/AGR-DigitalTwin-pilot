"""OBSERVE #97 series driver: 3 pairs (B_i || C_i) of G22 practice runs, then the BASE scorer on each.

Pattern: new-case: docs/research/trainer-g22-adapter-r97 - OBSERVE #97 trainer practice series (research only).

uv run --frozen python docs/research/trainer-g22-adapter-r97/series.py ROOTS_DIR [--only NAME ...]
ROOTS_DIR holds B/ and C/ from make_candidate.py. Arm A runs ROOTS_DIR/A/tools/trainer/trainer.py (its origin/main is
the arm's commit); both arms are scored by ROOTS_DIR/B's (unchanged base) scorer. Writes
C:/x/trainer/runs/g22-k2-stage1-codex-r97-<arm><i>/ (+ score.json); log C:/x/ev_t_a9ae5284/series.log.
Budget stop (frozen): no new pair starts after 150 min from the series start; unstarted runs are `not_run`.
"""
import subprocess
import sys
import time
from pathlib import Path

RUNS = Path("C:/x/trainer/runs")
LOG = Path("C:/x/ev_t_a9ae5284/series.log")
ETALON = "g22-k2-stage1"
BUDGET_S = 150 * 60


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def trainer(roots, arm):
    return ["uv", "run", "--frozen", "--quiet", "python", str(Path(roots) / arm / "tools/trainer/trainer.py")]


def main(roots, only=()):
    t0 = time.time()
    for i in (1, 2, 3):
        if time.time() - t0 > BUDGET_S:
            log(f"BUDGET STOP before pair {i}")
            break
        procs = []
        for arm in ("B", "C"):
            name = f"{ETALON}-codex-r97-{arm}{i}"
            if only and name not in only:
                continue
            cmd = [*trainer(roots, arm), "run", ETALON, "--out", str(RUNS / name), "--timeout-s", "1800"]
            log("start " + name)
            procs.append((name, subprocess.Popen(cmd, stdout=open(LOG.parent / f"{name}.out", "w"),
                                                 stderr=subprocess.STDOUT)))
        for name, p in procs:
            rc = p.wait()
            log(f"done {name} rc={rc}")
            sc = subprocess.run([*trainer(roots, "B"), "score", ETALON, "--built", str(RUNS / name / "built"),
                                 "--out", str(RUNS / name / "score.json")], capture_output=True, text=True)
            log(f"score {name} rc={sc.returncode} {(sc.stdout + sc.stderr).strip()[-300:]}")
    log("SERIES DONE")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], tuple(a[2:]) if len(a) > 1 and a[1] == "--only" else ())
