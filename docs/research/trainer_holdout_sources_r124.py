"""Read-only #124 admission census; never opens key files or starts a practice agent."""

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

PIN = "e7cb8800ad537ca0cbad19e49ade2ea8ae1e904b"
BANK = "docs/trainer/etalons.json"
BANK_SHA = "016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635"


def digests(sources):
    hashes = [s.get("sha256") for s in sources]
    if not hashes or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes):
        return None
    return set(hashes)


def overlap(sources, tuning):
    identities = digests(sources)
    return None if identities is None else len(identities & tuning)


def main():
    started = time.monotonic()
    env = dict(os.environ, PYTHONUTF8="1")
    raw = subprocess.check_output(["git", "show", f"{PIN}:{BANK}"])
    if hashlib.sha256(raw).hexdigest() != BANK_SHA:
        raise RuntimeError("frozen bank digest mismatch")
    if json.loads(Path(BANK).read_bytes()) != json.loads(raw):
        raise RuntimeError("checked-out bank differs from frozen bank")
    subprocess.run(["git", "diff", "--exit-code", PIN, "--", "tools/trainer", "docs/trainer"], check=True)
    entries = {e["id"]: e for e in json.loads(raw)["etalons"]}
    tuning = set.union(*(digests(e["sources"]) for e in entries.values() if e["split"] == "tuning"))
    tower_a = digests(entries["63a-stage1"]["sources"])
    tower_b = entries["63b-stage1"]["sources"]
    shared = overlap(tower_b, tower_a)
    separate = overlap(entries["g22-k2-stage1"]["sources"], tower_a)
    controls = {
        "same_digest_renamed": overlap([dict(tower_b[0], path="synthetic-renamed.fbx")], tower_a),
        "new_digest": overlap([{"sha256": "0" * 64}], tower_a),
        "missing_digest": overlap([{}], tower_a),
    }
    if (shared, separate, controls) != (1, 0, {"same_digest_renamed": 1, "new_digest": 0, "missing_digest": None}):
        raise RuntimeError("source identity witness diverged")
    print(json.dumps({"tower_pair_overlap": shared, "g22_tower_a_overlap": separate, "synthetic": controls}), flush=True)
    measurements = []
    for sweep in range(1, 4):
        sweep_start = time.monotonic()
        rows = {}
        for eid, e in entries.items():
            out = Path(".r124-probe") / f"{sweep}-{eid}"
            if out.parent.exists():
                raise RuntimeError("reserved probe path already exists")
            budget = 150 - (time.monotonic() - started)
            if budget <= 0:
                raise TimeoutError("150 s series budget exhausted")
            p = subprocess.run(
                ["agr.exe" if os.name == "nt" else "agr", "trainer", "run", eid,
                 "--lane", "codex", "--out", str(out), "--dry-run"],
                env=env, capture_output=True, encoding="utf-8", timeout=budget,
            )
            if out.parent.exists():
                raise RuntimeError("dry-run unexpectedly wrote into reserved probe path")
            if p.returncode == 0 and p.stdout.strip():
                status = "admitted"
            elif p.returncode == 2 and "is not practice_ready" in p.stderr:
                status = "unscheduled"
            elif p.returncode == 2 and "source missing:" in p.stderr:
                status = "source_missing"
            else:
                raise RuntimeError(f"{eid}: unexpected exit {p.returncode}: {p.stderr}")
            collision = overlap(e["sources"], tuning)
            qualifies = (e["split"] == "held_out" and e["scenario"] in {"oks-vpm", "oks-npm"}
                         and status == "admitted" and collision == 0)
            rows[eid] = [p.returncode, status, collision, qualifies]
        if rows["63a-stage1"][1] != "admitted" or rows["63b-stage1"][1] != "unscheduled":
            raise RuntimeError(f"native admission witness diverged: {rows}")
        metric = sum(row[-1] for row in rows.values())
        measurements.append(metric)
        print(json.dumps({"sweep": sweep, "wall_s": round(time.monotonic() - sweep_start, 3), "metric": metric,
                          "rows": rows}), flush=True)
    print(json.dumps({"median": sorted(measurements)[1], "spread": max(measurements) - min(measurements),
                      "wall_s": round(time.monotonic() - started, 3), "status": "complete"}))


if __name__ == "__main__":
    main()
