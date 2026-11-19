"""KPP1 #1416: xView face pairs present after the simplification but not before -> protect.json.

Pattern: n/a | new-case: job helper; diff two `dt qa xview` reports of the same parts by face-pair centre.

  python xview_new_pairs.py <before.json> <after.json> <out protect.json> [radius_m]
Exit 1 when the after report has new pairs (protect.json written), 0 when none, 2 on bad input.
"""
import json
import math
import os
import sys


def pairs(report):
    out = {}
    for part in report["parts"]:
        loc = part.get("location") or [0.0, 0.0, 0.0]
        out[part["part"]] = [[c + l for c, l in zip(fp["centre"], loc)] for fp in part.get("face_pairs", [])]
    return out


def main(argv):
    if len(argv) < 3:
        print("usage: before.json after.json protect.json [radius_m]")
        return 2
    b_path, a_path, o_path = (os.path.realpath(p) for p in argv[:3])
    if len({b_path, a_path, o_path}) < 3 or os.path.exists(o_path):
        print("output aliases an input or exists")
        return 2
    radius = float(argv[3]) if len(argv) > 3 else 0.3
    if not math.isfinite(radius) or radius <= 0:
        print("radius must be finite > 0")
        return 2
    with open(b_path, encoding="utf-8") as f:
        before = pairs(json.load(f))
    with open(a_path, encoding="utf-8") as f:
        after = pairs(json.load(f))
    if set(before) != set(after):
        print(f"part sets differ: {sorted(set(before) ^ set(after))}")
        return 2
    new = []
    for name, pts in after.items():
        for p in pts:
            if not any(math.dist(p, q) <= 0.001 for q in before[name]):
                new.append({"part": name, "centre": p})
    print(json.dumps({"new_pairs": len(new), "by_part": {n: sum(1 for x in new if x["part"] == n) for n in after}}))
    if not new:
        return 0
    with open(o_path, "w", encoding="utf-8") as f:
        json.dump({"radius_m": radius, "points": [x["centre"] for x in new], "new_pairs": new}, f, indent=1)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
