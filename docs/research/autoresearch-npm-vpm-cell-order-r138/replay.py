"""Observe the existing V2 cells on a fresh, parity-checked #128 replay."""
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
LABELS = ("pilot-v007", "pilot-v010")
CAP = 420
EPS = 0.01


def blob(name):
    return subprocess.check_output(["git", "show", f"{R128}:{HISTORY}/{name}"])


def require(ok, message):
    if not ok:
        raise ValueError(message)


def head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def observer(path):
    source = path.read_text(encoding="utf-8")
    marker = '    means = np.array([c["mean"] for c in cells])\n'
    require(source.count(marker) == 1, "V2 observer anchor changed")
    scope = {"__name__": "v2_observer", "captures": []}
    source = source.replace(marker, '    captures.append((cells, mask))\n' + marker)
    exec(compile(source, str(path), "exec"), scope)

    def observe(npm, vpm, width, expected=None):
        summary = scope["score_view"](npm, vpm, width, 2)
        cells, mask = scope["captures"].pop()
        if expected is not None:
            require(summary == expected, "observer summary drift")
        values = {(c["x_m"], c["z_m"]): c["mean"] for c in cells}
        require(bool(values) and len(values) == len(cells), "empty or duplicate cell keys")
        return values, (mask.shape, sha(mask.tobytes()))

    return observe


def delta_stats(left, right):
    require(left.keys() == right.keys(), "unmatched cells")
    deltas = {k: left[k] - right[k] for k in left}
    win = sum(d > EPS for d in deltas.values())
    lose = sum(d < -EPS for d in deltas.values())
    worst = max(deltas, key=deltas.get)
    return {"cells": len(deltas), "higher": win, "lower": lose, "ties": len(deltas) - win - lose,
            "higher_share": win / len(deltas), "median_delta": median(deltas.values()),
            "min_delta": min(deltas.values()), "max_delta": deltas[worst], "max_delta_xz_m": worst,
            "pair_values_sha256": sha(json.dumps([(k, left[k], right[k]) for k in sorted(left)]).encode())}


def profile_controls(s, observe, label, view, images, width, baseline, mask, live):
    npm, vpm = images["npm", view], images["vpm", view]
    np = s["np"]
    rows = {}
    for kind in ("N0", "P1"):
        if kind == "P1" and view != "south":
            require(live["controls"][kind]["changed_npm_rgb"][view] == 0, "off-target patch")
            rows[kind] = {"status": "not_exercised", "changed_npm_rgb": 0, "changed_vpm_rgb": 0}
            continue
        # Use the existing perturbation without any change in selected pixels.
        textures = {("npm", view): npm, ("vpm", view): vpm}
        mutated = vpm if kind == "N0" else s["perturb"](textures, kind, live["clean"]["views"][view]["native_px_per_m"])["npm", view]
        changed = int(np.any(mutated[..., :3] != npm[..., :3], axis=-1).sum())
        prior = live["controls"][kind]
        require(changed == prior["changed_npm_rgb"][view] > 0 and prior["vpm_equal"]
                and np.array_equal(mutated[..., 3], npm[..., 3]), f"{label} {view} {kind}: activation/parity")
        cells, observed_mask = observe(mutated, vpm, width)
        require(mask == observed_mask, f"{label} {view} {kind}: mask drift")
        row = {"status": "exercised", "changed_npm_rgb": changed, "changed_vpm_rgb": 0,
               "alpha_mask_parity": True, **delta_stats(cells, baseline)}
        if kind == "N0":
            require(all(value == 0 for value in cells.values()), "N0 not zero")
        else:
            require(row["higher"] > 0 and row["max_delta"] >= 2, f"{label}: weak P1")
        rows[kind] = row
    return rows


def read_pair(i, observed, prior, decoded, native, s, observe):
    rows, means = {}, {}
    require(observed["packages"][LABELS[0]]["camera"] == observed["packages"][LABELS[1]]["camera"],
            "cross-label camera mismatch")
    for label in LABELS:
        dst = native / f"r{i}-{label}"
        live, sealed = observed["packages"][label], prior["packages"][label]
        require(all(live[k] == sealed[k] for k in ("clean", "camera", "controls")), f"V2 parity: {dst.name}")
        images = {p.stem: s["load"](p) for p in dst.glob("*.png")}
        hashes = {f"{name}.png": sha(img.tobytes()) for name, img in images.items()}
        require(hashes == decoded[label][str(i)], f"decoded parity: {dst.name}")
        bbox = json.loads((dst / "renders.json").read_bytes())["vpm"]["bbox"]
        means[label], controls = {}, {}
        for view in s["VIEWS"]:
            axis = s["AXIS"][view]
            width = bbox[1][axis] - bbox[0][axis]
            n, v = images[f"npm_{view}"], images[f"vpm_{view}"]
            cells, mask = observe(n, v, width, live["clean"]["views"][view])
            means[label][view] = cells, mask
            controls[view] = profile_controls(s, observe, label, view, {("npm", view): n, ("vpm", view): v},
                                              width, cells, mask, live)
        rows[label] = {"decoded_rgba_sha256": hashes, "clean_v2": live["clean"], "controls": controls}
    comparisons = {}
    for view in s["VIEWS"]:
        a, am = means[LABELS[0]][view]
        b, bm = means[LABELS[1]][view]
        require(am == bm, f"cross-label mask mismatch: {view}")
        comparisons[view] = {"mask_sha256": am[1], **delta_stats(a, b)}
    return {"pair": i, "native_seconds": observed["seconds"], "labels": rows, "views": comparisons,
            "case_share": max(row["higher_share"] for row in comparisons.values())}


def spread(values):
    return {"values": values, "median": median(values), "min": min(values), "max": max(values),
            "spread": max(values) - min(values)}


def main(out):
    start = monotonic()
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "preflight", "native_calibration": "inconclusive", "hypothesis": "inconclusive",
              "measured_head": head(), "reference": R128, "variant": 2, "rounds": []}
    try:
        reference = json.loads(blob("receipt.json"))
        decoded = json.loads(blob("decoded-parity.json"))
        adapter, native = out / "r128_replay.py", out / "native"
        adapter.write_bytes(blob("replay.py"))
        result = subprocess.run([sys.executable, str(adapter), str(native)], check=False, timeout=CAP)
        evidence = json.loads((native / "receipt.json").read_bytes())
        report.update(native_status=evidence["status"], native_seconds=evidence["seconds"])
        if evidence["status"] == "budget_stop" or evidence["seconds"] > 300:
            report["status"] = "budget_stop"
            return report
        require(result.returncode == 0 and evidence["status"] == "series_complete" and evidence["input_parity"]
                and len(evidence["rounds"]) == 3, "native series or manifest parity failed")
        for key in ("versions", "scorer_sha256", "zip_sha256", "staged_sha256"):
            require(evidence[key] == reference[key], f"native {key} mismatch")
        report["manifest_parity"] = {k: evidence[k] for k in ("versions", "scorer_sha256", "zip_sha256", "staged_sha256")}
        scorer = native / "render_diff.py"
        s, observe = runpy.run_path(str(scorer)), observer(scorer)
        for i, (observed, expected) in enumerate(zip(evidence["rounds"], reference["rounds"], strict=True), 1):
            began = monotonic()
            row = read_pair(i, observed, expected, decoded, native, s, observe)
            row["cell_seconds"] = monotonic() - began
            report["rounds"].append(row)
            remaining = CAP - (monotonic() - start)
            if remaining <= 0 or (i == 1 and remaining < 2 * row["cell_seconds"] + 5):
                report["status"] = "budget_stop"
                return report
        require(head() == report["measured_head"], "measured Git head drift")
        rows = report["rounds"]
        report["higher_share"] = {v: spread([r["views"][v]["higher_share"] for r in rows]) for v in s["VIEWS"]}
        report["higher_share"]["case_max"] = spread([r["case_share"] for r in rows])
        report["hypothesis"] = "confirmed" if all(r["case_share"] <= 0.5 for r in rows) else "refuted"
        comparisons = []
        for row in rows:
            a, b = (row["labels"][k]["clean_v2"] for k in LABELS)
            comparisons.extend(a["views"][v]["cell_p95"] > b["views"][v]["cell_p95"] for v in s["VIEWS"])
            comparisons.append(a["score_facade_cell_p95"] > b["score_facade_cell_p95"])
        report["native_calibration"] = "confirmed" if all(comparisons) else "refuted"
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
        (out / "receipt.json").write_bytes((json.dumps(report, indent=2) + "\n").encode())


if __name__ == "__main__":
    receipt = main(Path(sys.argv[1]).resolve())
    print(receipt["status"], receipt["native_calibration"], receipt["hypothesis"], receipt.get("higher_share"))
    sys.exit(0 if receipt["status"] == "series_complete" else 1)
