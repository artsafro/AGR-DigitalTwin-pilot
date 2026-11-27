"""Replay #128 unchanged, then probe single and distributed seams in its fresh renders."""
import hashlib
import json
from pathlib import Path
import runpy
from statistics import median
import subprocess
import sys
from time import monotonic

R128 = "5c15100ee5631e2f5d75e697e14e1977a6361f3d"
HISTORY = "docs/research/autoresearch-npm-vpm-render-diff-r128"
REJECTED, REFERENCE = LABELS = ("pilot-v007", "pilot-v010")
CAP = 360


def blob(name):
    return subprocess.check_output(["git", "show", f"{R128}:{HISTORY}/{name}"])


def require(condition, message):
    if not condition:
        raise ValueError(message)


def witness(s, npm, vpm, width, clean):
    np = s["np"]
    datum = s["is_zero_line"](npm)
    common = (npm[..., 3] >= 128) & (vpm[..., 3] >= 128) & ~datum & ~s["is_zero_line"](vpm)
    y, x = np.where(common)
    anchors = [(r + 60, c + 180) for r in range(int(y.min()), int(y.max()) - 398, 400)
               for c in range(int(x.min()), int(x.max()) - 398, 400)
               if common[r:r + 400, c:c + 400].all()]
    require(len(anchors) >= 10, "insufficient full native blocks")
    require(s["score_view"](npm, vpm, width, 2) == clean, "south clean mismatch")
    vpm_digest = hashlib.sha256(vpm.tobytes()).hexdigest()
    rows = {}
    for arm, targets in (("isolated", anchors[:1]), ("distributed", anchors)):
        footprint = np.zeros_like(common)
        mutant = npm.copy()
        touched = []
        for r, c in targets:
            patch = np.s_[r:r + 280, c:c + 40]
            touched.append(int(np.any(npm[patch][..., :3] != 40, axis=-1).sum()))
            footprint[patch] = True
            mutant[patch][..., :3] = 40
        changed = np.any(npm[..., :3] != mutant[..., :3], axis=-1)
        require(all(touched) and int(changed.sum()) == sum(touched) and not (changed & ~footprint).any(),
                "dormant or out-of-scope RGB change")
        require(np.array_equal(npm[..., 3], mutant[..., 3]) and np.array_equal(datum, s["is_zero_line"](mutant)),
                "alpha or datum changed")
        scored = s["score_view"](mutant, vpm, width, 2)
        require(hashlib.sha256(vpm.tobytes()).hexdigest() == vpm_digest, "VPM changed")
        require(all(scored[k] == clean[k] for k in ("cells", "pixels", "silhouette_xor_share")), "mask coverage changed")
        rows[arm] = {"anchors_rc": targets, "changed_rgb_by_block": touched,
                     "changed_rgb": {"south": {"npm": sum(touched), "vpm": 0},
                                     **{v: {"npm": 0, "vpm": 0} for v in ("east", "north", "west")}},
                     "untouched_status": "not_exercised", "alpha_datum_mask_parity": True,
                     "score": scored, "delta": round(scored["cell_p95"] - clean["cell_p95"], 4),
                     "worst_delta": round(scored["worst_cell"]["mean"] - clean["worst_cell"]["mean"], 4)}
    return rows


def summary(values):
    return {"median": median(values), "min": min(values), "max": max(values),
            "spread": round(max(values) - min(values), 4)}


def measured_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def main(out):
    start = monotonic()
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "preflight", "calibration": "inconclusive", "hypothesis": "inconclusive",
              "measured_head": measured_head(), "reference": R128, "variant": 2, "rounds": []}
    native = out / "native"
    try:
        reference = json.loads(blob("receipt.json"))
        decoding = json.loads(blob("decoded-parity.json"))
        adapter = out / "r128_replay.py"
        adapter.write_bytes(blob("replay.py"))
        result = subprocess.run([sys.executable, str(adapter), str(native)], check=False,
                                timeout=CAP - (monotonic() - start))
        evidence = json.loads((native / "receipt.json").read_bytes())
        report.update(native_status=evidence["status"], native_seconds=evidence["seconds"])
        if evidence["status"] == "budget_stop" or evidence["seconds"] > 300:
            report["status"] = "budget_stop"
            return report
        require(evidence["status"] == "series_complete" and evidence["input_parity"] and result.returncode == 0
                and len(evidence["rounds"]) == 3, "native series incomplete or input drift")
        for k in ("versions", "scorer_sha256", "zip_sha256", "staged_sha256"):
            require(evidence[k] == reference[k], f"native {k} mismatch")
            report[k] = evidence[k]
        require(evidence["versions"] == {"python": "3.14.9", "numpy": "2.5.4", "pillow": "13.0.0"},
                "runtime drift")
        report["input_parity"] = True
        s = runpy.run_path(str(native / "render_diff.py"))
        fresh = []
        for i, (observed, expected) in enumerate(zip(evidence["rounds"], reference["rounds"], strict=True), 1):
            rows = {}
            for label in LABELS:
                dst = native / f"r{i}-{label}"
                live, prior = observed["packages"][label], expected["packages"][label]
                require(all(live[k] == prior[k] for k in ("clean", "camera", "controls")),
                        f"clean/camera/control parity failed: {dst.name}")
                decoded = {p.name: hashlib.sha256(s["load"](p).tobytes()).hexdigest() for p in dst.glob("*.png")}
                require(decoded == decoding[label][str(i)], f"decoded parity failed: {dst.name}")
                rows[label] = {"clean": live["clean"], "decoded_rgba_sha256": decoded}
            a, b = (rows[label]["clean"] for label in LABELS)
            margin = {v: round(a["views"][v]["cell_p95"] - b["views"][v]["cell_p95"], 4) for v in s["VIEWS"]}
            margin["case_max"] = round(a["score_facade_cell_p95"] - b["score_facade_cell_p95"], 4)
            fresh.append({"pair": i, "native_seconds": observed["seconds"], "margin": margin, "labels": rows})
        report["calibration"] = ("confirmed" if all(min(r["margin"].values()) > 0 for r in fresh) else "refuted")
        report["calibration_margin"] = {v: summary([r["margin"][v] for r in fresh]) for v in fresh[0]["margin"]}
        report["clean_parity"] = True
        report["rounds"] = fresh
        for row in fresh:
            pair_start = monotonic()
            for label in LABELS:
                dst = native / f"r{row['pair']}-{label}"
                bbox = json.loads((dst / "renders.json").read_bytes())["vpm"]["bbox"]
                row["labels"][label]["arms"] = witness(
                    s, s["load"](dst / "npm_south.png"), s["load"](dst / "vpm_south.png"),
                    bbox[1][0] - bbox[0][0], row["labels"][label]["clean"]["views"]["south"])
            elapsed = row["witness_seconds"] = monotonic() - pair_start
            remaining = CAP - (monotonic() - start)
            if remaining <= 0 or (row["pair"] == 1 and remaining < 2 * elapsed + 5):
                report["status"] = "budget_stop"
                return report
        require(measured_head() == report["measured_head"], "measured head drift")
        groups = {label: [r["labels"][label]["arms"] for r in fresh] for label in LABELS}
        report["isolated_delta"] = {label: summary([a["isolated"]["delta"] for a in arms])
                                    for label, arms in groups.items()}
        activated = all(a["isolated"]["worst_delta"] >= 2 and a["distributed"]["delta"] >= 2
                        for arms in groups.values() for a in arms)
        report["hypothesis"] = ("inconclusive" if not activated else
                                "confirmed" if all(v["max"] <= 0.25 for v in report["isolated_delta"].values())
                                else "refuted")
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
    print(result["status"], result["calibration"], result["hypothesis"], result.get("isolated_delta"), flush=True)
    sys.exit(0 if result["status"] == "series_complete" else 1)
