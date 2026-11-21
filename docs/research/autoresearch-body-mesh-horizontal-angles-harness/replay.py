"""Read-only continuation of standing #27 with one alternate shape feature."""
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
REFERENCE = "bd0194a8e876a2602eafc4c98e686811f04c4a0d"
HARNESS = "docs/research/autoresearch-body-mesh-horizontal-tris-harness"
CORE = "tools/qa/mesh_quality_core.py"


def blob(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)


def read_shape(data, newell, angles, cos1):
    area = flagged = 0.0
    tris = hits = faces = 0
    for obj in data["objects"]:
        for face in obj["faces"]:
            pts = [obj["verts"][i] for i in face]
            nx, ny, nz = newell(pts)
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            faces += 1
            tris += len(face) == 3
            if not length or abs(nz) / length < cos1:
                continue
            area += length / 2
            if any(a < 5 or a > 175 for a in angles(pts)):
                hits += 1
                flagged += length / 2
    if not area > 0 or not math.isfinite(area) or not 0 <= flagged <= area:
        raise ValueError("invalid horizontal area")
    return {"area": area, "flagged_area": flagged, "flagged_faces": hits,
            "triangles": tris, "faces": faces, "D": flagged / area}


def checked_dump(path, digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"input hash mismatch: {path}")
    return json.loads(raw)


def measure(root, ref, angles):
    read = lambda data: read_shape(data, ref["newell"], angles, ref["COS1"])
    baseline = ref["measure"](root)
    if baseline != json.loads(blob(REFERENCE, f"{HARNESS}/r27.json")):
        raise ValueError("#27 baseline receipt parity failure")
    rows = {}
    for name, label, rel, digest in ref["FIXTURE"]:
        path = root / rel
        samples = [read(checked_dump(path, digest)) for _ in range(3)]
        ref["require_hash"](path, digest)
        r, prior = samples[0], baseline["rows"][name]
        if any(s != r for s in samples):
            raise ValueError(f"non-repeatable reads: {name}")
        if (round(r["area"], 4), r["triangles"], r["faces"]) != (
            prior["h_area"], prior["triangles"], prior["faces"]
        ):
            raise ValueError(f"horizontal area or topology parity failure: {name}")
        ds = [s["D"] for s in samples]
        # Baseline requires all three H reads to be exactly identical.
        deltas = [d - prior["H"] for d in ds]
        rows[name] = {"label": label, "path": rel, "sha256": digest, **r,
                      "D": median(ds), "baseline_H": prior["H"], "reads_D": ds,
                      "paired_spread": max(deltas) - min(deltas)}

    first_sample = root / ref["FIXTURE"][0][2]
    try:
        checked_dump(first_sample, "0" * 64)
    except ValueError as exc:
        if not str(exc).startswith("input hash mismatch:"):
            raise
    else:
        raise ValueError("incorrect input hash was accepted")

    square = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    clean = read({"objects": [{"verts": square, "faces": [[0, 1, 2, 3]]}]})
    split = read({"objects": [{"verts": square + [[0.5, 0, 0]], "faces": [[0, 4, 1, 2, 3]]}]})
    if (clean["D"], split["D"], clean["area"], split["area"]) != (0.0, 1.0, 1.0, 1.0):
        raise ValueError("synthetic angle/area check failed")
    worst_rejected = min((r["D"], k) for k, r in rows.items() if r["label"] == "rejected")
    worst_accepted = max((r["D"], k) for k, r in rows.items() if r["label"] == "accepted")
    margin = worst_rejected[0] - worst_accepted[0]
    return {"variant": "horizontal Newell area share, any corner <5 or >175 degrees",
            "reference": REFERENCE, "angle_core_revision": BASE,
            "M": margin, "baseline_M": baseline["M"], "nominates_feature": margin > 0,
            "worst_rejected": worst_rejected, "worst_accepted": worst_accepted,
            "clean_checks": {"baseline_exact": True, "candidate_area_and_counts_parity": True,
                             "square_D": clean["D"]},
            "injected_checks": {"wrong_hash_refused": True, "collinear_vertex_D": split["D"],
                                "area_unchanged": True},
            "not_measured": ["native readback", "face ownership/design intent", "fully collapsed faces",
                             "score recalibration", "body core changes", "package QA"], "rows": rows}


def main(root, out):
    if (ROOT / CORE).read_bytes().replace(b"\r\n", b"\n") != blob(BASE, CORE):
        raise ValueError("angle core differs from frozen revision")
    with TemporaryDirectory(prefix="ar28-ref-") as tmp:
        path = Path(tmp) / "ar27.py"
        path.write_bytes(blob(REFERENCE, f"{HARNESS}/replay.py"))
        ref = runpy.run_path(str(path))
    result = measure(root, ref, runpy.run_path(str(ROOT / CORE))["_angles"])
    with out.open("x", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, allow_nan=False)
        fh.write("\n")
    print(result["M"])


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:]))
