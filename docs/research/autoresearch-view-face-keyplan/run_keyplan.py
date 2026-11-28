"""OBSERVE replay on already registered vector keyplans."""
import argparse
import hashlib
import json
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter

import pymupdf

HERE = Path(__file__).resolve().parent


def segments(drawings):
    lines = []
    for path in drawings:
        rgb = path.get("color")
        if rgb and len(rgb) == 3 and rgb[0] >= .65 and max(rgb[1:]) < .35:
            for item in path["items"]:
                if item[0] == "l":
                    lines.append((*item[1], *item[2]))
    return lines


def hits(lines, box):
    x0, y0, x1, y1 = box
    gap = .20 * min(x1 - x0, y1 - y0)
    for side, n, edge, sign, low, high in (
        ("top", 1, y0, -1, x0, x1), ("bottom", 1, y1, 1, x0, x1),
        ("left", 0, x0, -1, y0, y1), ("right", 0, x1, 1, y0, y1),
    ):
        t = 1 - n
        for i, line in enumerate(lines):
            a, b = line[n], line[n + 2]
            if abs(a - b) <= 1 and all(2 <= sign * (c - edge) <= gap for c in (a, b)):
                u, v = sorted((line[t], line[t + 2]))
                u, v = max(u, low), min(v, high)
                if u < v:
                    yield side, round((a + b) / 2), i, u, v, high - low


def decide(lines, box, frame):
    if box is None or frame is None:
        return None, {}
    groups, spans = defaultdict(list), {}
    for side, normal, _, a, b, span in hits(lines, box):
        groups[side, normal].append((a, b))
        spans[side] = span
    coverage = {}
    for (side, _), intervals in sorted(groups.items()):
        end, length = float("-inf"), 0.
        for a, b in sorted(intervals):
            if b > end:
                length += b - max(a, end)
                end = b
        coverage[side] = max(coverage.get(side, 0.), length / spans[side])
    passed = [frame[s] for s, v in coverage.items() if v >= .45]
    return (passed[0] if len(passed) == 1 else None), coverage


def perturb(lines, box, frame):
    best, _ = decide(lines, box, frame)
    if best is None:
        return dict.fromkeys(("masked", "interior", "ambiguous", "opposite_only"), lines)
    moved = {i for side, _, i, *_ in hits(lines, box) if frame[side] == best}
    side = next(s for s, az in frame.items() if az == best)
    axis = int(side in ("top", "bottom"))
    centre = (box[axis] + box[axis + 2]) / 2
    average = sum((lines[i][axis] + lines[i][axis + 2]) / 2 for i in sorted(moved)) / len(moved)
    keep = [line for i, line in enumerate(lines) if i not in moved]

    def transform(fn):
        return [tuple(fn(x) if j % 2 == axis else x for j, x in enumerate(line))
                for i, line in enumerate(lines) if i in moved]

    opposite = transform(lambda x: 2 * centre - x)
    return {"masked": keep, "interior": keep + transform(lambda x: x + centre - average),
            "ambiguous": lines + opposite, "opposite_only": keep + opposite}


def measure(fixture, root):
    rows = []
    for project, item in fixture.items():
        counts, cache = Counter(v[1] for v in item["views"]), {}
        with pymupdf.open(root / item["pdf"]) as pdf:
            for name, page, expected, kind, box in item["views"]:
                if page not in cache:
                    cache[page] = segments(pdf[page - 1].get_cdrawings())
                lines = cache[page]
                box = box if counts[page] == 1 else None
                frame, states = item["frame"], {}
                for state, seq in {"clean": lines, **perturb(lines, box, frame)}.items():
                    az, cov = decide(seq, box, frame)
                    before, after = Counter(lines), Counter(seq)
                    rev = seq[::-1]
                    states[state] = {"az": az, "coverage": cov,
                                     "removed": sum((before - after).values()),
                                     "added": sum((after - before).values()),
                                     "reversed_positions": sum(a != b for a, b in zip(seq, rev)),
                                     "reversal_parity": decide(rev, box, frame) == (az, cov)}
                rows.append(dict(project=project, view=name, expected=expected, kind=kind,
                                 registered=box is not None, raw_red_segments=len(lines), states=states))
    return rows


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def encode(obj):
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode()


def tally(rows, state):
    counts = dict.fromkeys(("correct", "wrong", "abstain", "not_exercised"), 0)
    for row in rows:
        v = row["states"][state]
        az = v["az"]
        if state != "clean" and not (v["added"] or v["removed"]):
            counts["not_exercised"] += 1
        else:
            counts["abstain" if az is None else "correct" if az == row["expected"] else "wrong"] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--evidence-root", type=Path, default=Path("G:/Мой диск/AGR-evidence"))
    args = parser.parse_args()
    spec = HERE / "fixture.json"
    fixture = json.loads(spec.read_bytes())
    pins = {args.evidence_root / v["pdf"]: v["sha256"] for v in fixture.values()}
    pins.update({p: digest(p) for p in (spec, HERE / "run_keyplan.py", HERE.parents[2] / "uv.lock")})
    if any(digest(p) != sha for p, sha in pins.items()):
        raise ValueError("input hash mismatch")
    args.out.mkdir(parents=True, exist_ok=False)
    started, times, hashes = perf_counter(), [], []
    for i in range(1, 4):
        start = perf_counter()
        rows = measure(fixture, args.evidence_root)
        times.append(round(perf_counter() - start, 4))
        payload = encode(rows)
        (args.out / f"pair-{i}.json").write_bytes(payload)
        hashes.append(hashlib.sha256(payload).hexdigest())
        if (i == 1 and times[0] > 20) or perf_counter() - started > 60:
            break
    unchanged = all(digest(p) == sha for p, sha in pins.items())
    active = [r for r in rows if r["registered"]]
    base = sum(r["states"]["masked"]["az"] == r["expected"] for r in rows)
    clean = tally(rows, "clean")
    witnesses = [r for r in active if r["view"].startswith(("p5 ", "p8 "))]
    checks = {
        "lift_ge_3": clean["correct"] - base >= 3,
        "zero_wrong": clean["wrong"] == 0,
        "elv_all_abstain": all(r["states"]["clean"]["az"] is None for r in rows if r["project"] == "elv"),
        "p5_p8": len(witnesses) == 2 and all(r["states"]["clean"]["az"] == r["expected"] for r in witnesses),
        "refuse_exercised_controls": all(tally(active, s)["abstain"] == len(active)
                                         for s in ("masked", "interior", "ambiguous")),
        "reversal_parity": all(v["reversal_parity"] for r in rows for v in r["states"].values()),
    }
    elapsed = perf_counter() - started
    complete = len(hashes) == 3 and len(set(hashes)) == 1 and unchanged and elapsed <= 60
    verdict = ("confirmed" if all(checks.values()) else "refuted") if complete else "inconclusive"
    report = dict(revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  hypothesis=verdict, run_status="complete" if complete else "incomplete", checks=checks,
                  paired_s=times, median_s=statistics.median(times), spread_s=round(max(times) - min(times), 4),
                  elapsed_s=round(elapsed, 4), hashes=hashes, inputs_unchanged=unchanged,
                  pins={str(p): sha for p, sha in pins.items()}, overall_clean=clean, baseline_correct=base,
                  baseline_abstain=sum(r["states"]["masked"]["az"] is None for r in rows),
                  variants={s: tally(rows, s) for s in rows[0]["states"]}, rows=rows)
    (args.out / "receipt.json").write_bytes(encode(report))
    print(verdict, clean, times)


if __name__ == "__main__":
    main()
