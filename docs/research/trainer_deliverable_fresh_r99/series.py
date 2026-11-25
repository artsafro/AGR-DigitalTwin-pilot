"""OBSERVE #99 series driver: 6 KPP1 practice runs (C1 D1 C2 D2 C3 D3), ONE at a time, each scored right after.

Pattern: new-case: docs/research/trainer_deliverable_fresh_r99 - OBSERVE #99 trainer practice series (research only).

uv run --frozen python docs/research/trainer_deliverable_fresh_r99/series.py BANK_C.json BANK_D.json [--only NAME ...]
Writes C:/x/trainer/runs/kpp1-v004-codex-r99-<arm><i>/ and <run>/score.json; log C:/x/ev_t_bda45f44/series.log.
One run at a time (one accoreconsole at a time, #95). Stop rule: no new launch later than STOP_S after the first.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick import built_arg  # noqa: E402

RUNS = Path("C:/x/trainer/runs")
EV = Path("C:/x/ev_t_bda45f44")
LOG = EV / "series.log"
EID = "kpp1-v004"
STOP_S = 3.5 * 3600
ORDER = [("C", 1), ("D", 1), ("C", 2), ("D", 2), ("C", 3), ("D", 3)]


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def main(bank_c, bank_d, only=()):
    t0 = time.time()
    for arm, i in ORDER:
        name = f"{EID}-codex-r99-{arm}{i}"
        if only and name not in only:
            continue
        if time.time() - t0 > STOP_S:
            log(f"BUDGET STOP before {name}")
            break
        bank = bank_c if arm == "C" else bank_d
        cmd = ["uv", "run", "--quiet", "agr", "trainer", "--bank", bank, "run", EID, "--out", str(RUNS / name),
               "--timeout-s", "1800"]
        log("start " + name)
        with open(EV / f"{name}.out", "w", encoding="utf-8") as fo:
            rc = subprocess.run(cmd, stdout=fo, stderr=subprocess.STDOUT).returncode
        log(f"done {name} rc={rc}")
        built = built_arg(RUNS / name, arm)
        sc = subprocess.run(["uv", "run", "--quiet", "agr", "trainer", "--bank", bank, "score", EID, "--built", built,
                             "--out", str(RUNS / name / "score.json")], capture_output=True, text=True)
        log(f"score {name} built={built} rc={sc.returncode} {(sc.stdout + sc.stderr).strip()[-300:]}")
    log("SERIES DONE")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], tuple(a[3:]) if len(a) > 2 and a[2] == "--only" else ())
