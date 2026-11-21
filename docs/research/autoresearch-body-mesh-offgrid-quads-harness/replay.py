"""Read-only continuation of standing #28: off-grid horizontal quad area share."""
import hashlib
import json
import math
from pathlib import Path
import runpy
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
BASE = "afa6fb2017eab81ec8207efb208df7e7ea8e8ed4"
REF27 = "bd0194a8e876a2602eafc4c98e686811f04c4a0d"
REF28 = "b6e0d883"
H27 = "docs/research/autoresearch-body-mesh-horizontal-tris-harness"
H28 = "docs/research/autoresearch-body-mesh-horizontal-angles-harness"
CORE = "tools/qa/mesh_quality_core.py"
GRID = (45.0, 90.0, 135.0)
TOL = 1.0


def blob(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)


def off_grid(a):
    return min(abs(a - g) for g in GRID) > TOL


def read_quads(data, newell, angles, cos1):
    area = flagged = 0.0
    hits = quads = faces = 0
    for obj in data["objects"]:
        for face in obj["faces"]:
            pts = [obj["verts"][i] for i in face]
            nx, ny, nz = newell(pts)
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            faces += 1
            if not length or abs(nz) / length < cos1:
                continue
            area += length / 2
            if len(face) != 4:
                continue
            quads += 1
            if any(off_grid(a) for a in angles(pts)):
                hits += 1
                flagged += length / 2
    if not area > 0 or not math.isfinite(area) or not 0 <= flagged <= area:
        raise ValueError("invalid horizontal area")
    return {"area": area, "flagged_area": flagged, "flagged_faces": hits,
            "horizontal_quads": quads, "faces": faces, "Q": flagged / area}


def checked_dump(path, digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"input hash mismatch: {path}")
    return json.loads(raw)


def measure(root, ref, r28, angles):
    read = lambda data: read_quads(data, ref["newell"], angles, ref["COS1"])
    baseline = ref["measure"](root)
    if baseline != json.loads(blob(REF27, f"{H27}/r27.json")):
        raise ValueError("#27 baseline receipt parity failure")
    prior28 = json.loads(blob(REF28, f"{H28}/r28.json"))["rows"]
    rows = {}
    for name, label, rel, digest in ref["FIXTURE"]:
        path = root / rel
        data = checked_dump(path, digest)
        d28 = r28["read_shape"](data, ref["newell"], angles, ref["COS1"])["D"]
        if d28 != prior28[name]["D"]:
            raise ValueError(f"#28 D parity failure: {name}")
        samples = [read(checked_dump(path, digest)) for _ in range(3)]
        ref["require_hash"](path, digest)
        r, prior = samples[0], baseline["rows"][name]
        if any(s != r for s in samples):
            raise ValueError(f"non-repeatable reads: {name}")
        if (round(r["area"], 4), r["faces"]) != (prior["h_area"], prior["faces"]):
            raise ValueError(f"horizontal area or topology parity failure: {name}")
        qs = [s["Q"] for s in samples]
        deltas = [q - prior["H"] for q in qs]
        rows[name] = {"label": label, "path": rel, "sha256": digest, **r, "Q": median(qs),
                      "reads_Q": qs, "baseline_H": prior["H"], "baseline_D28": d28,
                      "paired_spread": max(deltas) - min(deltas)}
        if rows[name]["paired_spread"] != 0:
            raise ValueError(f"non-zero paired spread: {name}")

    try:
        checked_dump(root / ref["FIXTURE"][0][2], "0" * 64)
    except ValueError as exc:
        if not str(exc).startswith("input hash mismatch:"):
            raise
    else:
        raise ValueError("incorrect input hash was accepted")

    one = lambda v, f: read({"objects": [{"verts": v, "faces": [f]}]})["Q"]
    square = one([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], [0, 1, 2, 3])
    s = math.sqrt(0.5)
    para45 = one([[0, 0, 0], [1, 0, 0], [1 + s, s, 0], [s, s, 0]], [0, 1, 2, 3])
    t = math.radians(48)
    rhomb48 = one([[0, 0, 0], [1, 0, 0], [1 + math.cos(t), math.sin(t), 0],
                   [math.cos(t), math.sin(t), 0]], [0, 1, 2, 3])
    pent = one([[math.cos(math.radians(72 * k + 10)), math.sin(math.radians(72 * k + 10)), 0]
                for k in range(5)], [0, 1, 2, 3, 4])
    if (square, para45, rhomb48, pent) != (0.0, 0.0, 1.0, 0.0):
        raise ValueError(f"synthetic checks failed: {(square, para45, rhomb48, pent)}")

    rej = [(r["Q"], k) for k, r in rows.items() if r["label"] == "rejected"]
    acc = [(r["Q"], k) for k, r in rows.items() if r["label"] == "accepted"]
    worst_rejected, worst_accepted = min(rej), max(acc)
    margin = worst_rejected[0] - worst_accepted[0]
    ordered = sum(a > b for a, _ in rej for b, _ in acc)
    return {"variant": "horizontal Newell area share, 4-corner faces with a corner >1.0 deg off 45/90/135",
            "reference_27": REF27, "reference_28": REF28, "angle_core_revision": BASE,
            "M": margin, "baseline_M": baseline["M"], "nominates_feature": margin > 0,
            "worst_rejected": worst_rejected, "worst_accepted": worst_accepted,
            "descriptive_ordered_pairs": [ordered, len(rej) * len(acc)],
            "clean_checks": {"baseline27_exact": True, "d28_exact": True,
                             "area_and_face_count_parity": True, "square_Q": square,
                             "parallelogram45_Q": para45},
            "injected_checks": {"wrong_hash_refused": True, "rhombus48_Q": rhomb48,
                                "offgrid_pentagon_Q": pent},
            "not_measured": ["native readback", "face ownership/design intent", "non-quad off-grid faces",
                             "collapsed faces", "score recalibration", "body core changes", "package QA"],
            "rows": rows}


def main(root, out):
    if (ROOT / CORE).read_bytes().replace(b"\r\n", b"\n") != blob(BASE, CORE):
        raise ValueError("angle core differs from frozen revision")
    with TemporaryDirectory(prefix="ar29-ref-") as tmp:
        p27, p28 = Path(tmp) / "ar27.py", Path(tmp) / "ar28.py"
        p27.write_bytes(blob(REF27, f"{H27}/replay.py"))
        p28.write_bytes(blob(REF28, f"{H28}/replay.py"))
        ref, r28 = runpy.run_path(str(p27)), runpy.run_path(str(p28))
    result = measure(root, ref, r28, runpy.run_path(str(ROOT / CORE))["_angles"])
    with out.open("x", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, allow_nan=False)
        fh.write("\n")
    print(result["M"], result["descriptive_ordered_pairs"])


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:]))
