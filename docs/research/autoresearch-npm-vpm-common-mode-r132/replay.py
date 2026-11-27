"""Apply the frozen common-mode witness to fresh renders from the pinned #128 replay."""
import hashlib
import json
from pathlib import Path
import runpy
from statistics import median
import subprocess
import sys
from time import monotonic

R128 = "5c15100ee5631e2f5d75e697e14e1977a6361f3d"
HISTORICAL = "docs/research/autoresearch-npm-vpm-render-diff-r128"
LABELS = ("pilot-v007", "pilot-v010")
PROFILES = ("npm", "vpm")


def blob(name):
    return subprocess.check_output(["git", "show", f"{R128}:{HISTORICAL}/{name}"])


def require(condition, message):
    if not condition:
        raise ValueError(message)


def witness(s, originals, width):
    np = s["np"]
    datum = {p: s["is_zero_line"](a) for p, a in originals.items()}
    common = np.logical_and.reduce([(a[..., 3] >= 128) & ~datum[p] for p, a in originals.items()])
    first = int(np.flatnonzero(common.any(axis=0))[0]) + 240
    x = np.arange(common.shape[1]) - first
    footprint = common & ((x >= 0) & (x % 240 < 12))
    def score(pair):
        return s["score_view"](pair["npm"], pair["vpm"], width, 2)["cell_p95"]

    clean = score(originals)
    arms = {}
    for arm, targets in (("npm_only", ("npm",)), ("vpm_only", ("vpm",)), ("both", PROFILES)):
        pair = {p: a.copy() for p, a in originals.items()}
        counts = {}
        for p, a in pair.items():
            original = originals[p]
            if p in targets:
                a[..., :3][footprint] = 40
            changed = np.any(a[..., :3] != original[..., :3], axis=-1)
            counts[p] = int(changed.sum())
            require(not (changed & ~footprint).any(), "unexpected RGB changes")
            require(np.array_equal(a[..., 3], original[..., 3]), "changed alpha")
            require(np.array_equal(s["is_zero_line"](a), datum[p]), "changed datum")
            require((counts[p] > 0) == (p in targets), "wrong witness activation")
        if arm == "both":
            require(np.array_equal(pair["npm"][..., :3][footprint], pair["vpm"][..., :3][footprint]),
                    "both-arm RGB mismatch")
        result = score(pair)
        arms[arm] = {"score": result, "delta": round(result - clean, 4), "changed_rgb": counts,
                     "untouched_views": {v: {p: 0 for p in PROFILES} for v in ("east", "north", "west")}}
    unilateral = min(arms[a]["delta"] for a in ("npm_only", "vpm_only"))
    return {"clean": clean, "footprint_pixels": int(footprint.sum()), "arms": arms,
            "ratio": abs(arms["both"]["delta"]) / unilateral if unilateral >= 0.25 else None}


def main(out):
    start = monotonic()
    out.mkdir(parents=True, exist_ok=False)
    native = out / "native"
    report = {"status": "preflight", "hypothesis": "inconclusive", "rounds": [], "reference": R128,
              "measured_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()}
    try:
        reference = json.loads(blob("receipt.json"))
        decoding = json.loads(blob("decoded-parity.json"))
        adapter = out / "r128_replay.py"
        adapter.write_bytes(blob("replay.py"))
        subprocess.run([sys.executable, str(adapter), str(native)], check=True, timeout=360 - (monotonic() - start))
        evidence = json.loads((native / "receipt.json").read_bytes())
        report.update({k: evidence[k] for k in ("versions", "scorer_sha256", "zip_sha256", "staged_sha256", "input_parity")})
        report.update(native_status=evidence["status"], native_seconds=evidence["seconds"])
        if evidence["status"] == "budget_stop":
            report["status"] = "budget_stop"
            return report
        require(evidence["status"] == "series_complete" and evidence["input_parity"] and len(evidence["rounds"]) == 3,
                "native series incomplete or input drift")
        require(evidence["versions"] == {"python": "3.14.9", "numpy": "2.5.4", "pillow": "13.0.0"},
                "runtime version drift")
        require(evidence["scorer_sha256"] == reference["scorer_sha256"], "scorer drift")
        s = runpy.run_path(str(native / "render_diff.py"))
        for i, (observed, expected) in enumerate(zip(evidence["rounds"], reference["rounds"], strict=True), 1):
            pair_start = monotonic()
            pair = {}
            for label in LABELS:
                dst = native / f"r{i}-{label}"
                meta = json.loads((dst / "renders.json").read_bytes())
                decoded = {p.name: hashlib.sha256(s["load"](p).tobytes()).hexdigest() for p in dst.glob("*.png")}
                require(decoded == decoding[label][str(i)], f"decoded parity failed at {dst.name}")
                live, prior = observed["packages"][label], expected["packages"][label]
                require(all(live[k] == prior[k] for k in ("clean", "camera", "controls")),
                        f"clean/camera/control parity failed at {dst.name}")
                originals = {p: s["load"](dst / f"{p}_south.png") for p in PROFILES}
                bbox = meta["vpm"]["bbox"]
                row = witness(s, originals, bbox[1][0] - bbox[0][0])
                require(row["clean"] == live["clean"]["views"]["south"]["cell_p95"], "south clean mismatch")
                pair[label] = {**row, "decoded_rgba_sha256": decoded}
            elapsed = monotonic() - pair_start
            report["rounds"].append({"labels": pair, "seconds": elapsed, "native_seconds": observed["seconds"]})
            if monotonic() - start >= 360 or (i == 1 and 360 - (monotonic() - start) < 2 * elapsed + 5):
                report["status"] = "budget_stop"
                return report
        report["labels"] = {}
        for label in LABELS:
            ratios = [r["labels"][label]["ratio"] for r in report["rounds"]]
            report["labels"][label] = None if None in ratios else {
                "median": median(ratios), "min": min(ratios), "max": max(ratios), "spread": max(ratios) - min(ratios)}
        outcomes = list(report["labels"].values())
        report["hypothesis"] = ("inconclusive" if None in outcomes else
                                "confirmed" if all(o["max"] <= 0.25 for o in outcomes) else "refuted")
        report["status"] = "series_complete"
        return report
    except subprocess.TimeoutExpired as error:
        report.update(status="budget_stop", error=str(error))
        return report
    except Exception as error:
        report.update(status="refused", error=str(error))
        raise
    finally:
        report["seconds"] = monotonic() - start
        (out / "receipt.json").write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode())


if __name__ == "__main__":
    result = main(Path(sys.argv[1]).resolve())
    print(result["status"], result["hypothesis"], result.get("labels"), flush=True)
    sys.exit(0 if result["status"] == "series_complete" else 1)
