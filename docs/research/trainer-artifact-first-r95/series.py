"""OBSERVE #95 series driver: 12 practice runs in the frozen order, 2 at a time, then agr trainer score each.

uv run --frozen python docs/research/trainer-artifact-first-r95/series.py BANK_C.json [--only NAME ...]
Writes C:/x/trainer/runs/<etalon>-codex-r95-<arm><i>/ and <run>/score.json; log in C:/x/ev_t_04777f53/series.log.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

RUNS = Path("C:/x/trainer/runs")
LOG = Path("C:/x/ev_t_04777f53/series.log")
K, G = "kpp1-v004", "g22-k2-stage1"


def order():
    out = []
    for i in (1, 2, 3):
        out.append([(K, "B", i), (G, "C", i)])
        out.append([(K, "C", i), (G, "B", i)])
    return out


def log(msg):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def main(bank_c, only=()):
    for pair in order():
        procs = []
        for eid, arm, i in pair:
            name = f"{eid}-codex-r95-{arm}{i}"
            if only and name not in only:
                continue
            bank = ["--bank", bank_c] if arm == "C" else []
            cmd = ["uv", "run", "--quiet", "agr", "trainer", *bank, "run", eid, "--out", str(RUNS / name),
                   "--timeout-s", "1800"]
            log("start " + name)
            procs.append((name, eid, subprocess.Popen(cmd, stdout=open(LOG.parent / f"{name}.out", "w"),
                                                      stderr=subprocess.STDOUT)))
        for name, eid, p in procs:
            rc = p.wait()
            log(f"done {name} rc={rc}")
            sc = subprocess.run(["uv", "run", "--quiet", "agr", "trainer", "score", eid, "--built",
                                 str(RUNS / name / "built"), "--out", str(RUNS / name / "score.json")],
                                capture_output=True, text=True)
            log(f"score {name} rc={sc.returncode} {sc.stdout.strip()[-300:]}")
    log("SERIES DONE")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], tuple(a[2:]) if len(a) > 1 and a[1] == "--only" else ())
