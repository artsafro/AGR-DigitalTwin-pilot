"""Replay #23's irregular-face attribution on the accepted G22 k1 v003 band."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.qa import mesh_quality_core as core  # type: ignore[import-not-found]  # noqa: E402

PARENT = "9aa36ea48d918482b4bc785b8df1c60aef3d7df2:docs/research/autoresearch-body-corner-windows-harness/r23.json"
PARENT_SHA = "ddcf27b6af9d57a43e3be81b298d8cfa4e13e60491cf43ba54908386bb1c9391"
CORE_BLOB = "7f27daca7d33b317272017577a2a38f4914fb2b7"
INPUTS = {
    "G22_k1_v003": ("C:/x/ev_1619/r3/k1_v003.mq.json", "0939980dc8e9717657f437d2c840a77e6241f27ea5171ae402677def11f80db1"),
    "63C_v001": ("C:/x/ar15/r1/tmp/63C-v001.1/dump.json", "d8e64e2a54a66b2b1b377ae4e9c1b2f21ac3e53deadd26e25f361631e88197a7"),
    "63C_v002": ("C:/x/ar15/r1/tmp/63C-v002.1/dump.json", "19ee7c2046e37a5eeff76522a4b62a3f468f4fb02f1fd210cf912a8b2274ae7e"),
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def checked(raw, expected):
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("frozen input hash mismatch")
    return json.loads(raw)


def attribution(dump, corners):
    report = dict(irregular_faces=0, irregular_area=0.0, near_faces=0, near_area=0.0)
    support = [0] * len(corners)
    by_orientation = {}
    for obj in dump["objects"]:
        for face in obj["faces"]:
            pts = [obj["verts"][idx] for idx in face]
            x, y = (sum(p[i] for p in pts) / len(pts) for i in (0, 1))
            near = [i for i, c in enumerate(corners) if math.hypot(x - c[0], y - c[1]) <= 2.0]
            for i in near:
                support[i] += 1
            if max(abs(a - 90.0) for a in core._angles(pts)) <= 15.0 + core.ANGLE_EPS_DEG:
                continue
            normal = core._newell(pts)
            area = core._norm(normal) / 2.0
            report["irregular_faces"] += 1
            report["irregular_area"] += area
            if near:
                report["near_faces"] += 1
                report["near_area"] += area
                label = "horizontal" if max(p[2] for p in pts) - min(p[2] for p in pts) <= 1e-6 else "nonhorizontal"
                key = f"{label}_{len(face)}gon"
                by_orientation[key] = by_orientation.get(key, 0) + 1
    total = report["irregular_area"]
    share = round(100 * report["near_area"] / total, 3) if total else None
    report.update(irregular_area=round(total, 6), near_area=round(report["near_area"], 6))
    return {**report, "near_area_pct": share}, support, by_orientation


def confirm_inputs():
    return {label: checked(Path(path).read_bytes(), digest) for label, (path, digest) in INPUTS.items()}


def main(out):
    if git("hash-object", "--path=tools/qa/mesh_quality_core.py", "tools/qa/mesh_quality_core.py").decode().strip() != CORE_BLOB:
        raise ValueError("frozen core blob mismatch")
    parent = checked(git("show", PARENT), PARENT_SHA)
    corners = sorted({tuple(c[:2]) for row in parent["floors"]["G22_k1_v003"]["flagged"]
                      for c in row["corners"] if c[2] > 1.0})
    if len(corners) != 6:
        raise ValueError("expected six distinct held-out corners")
    dumps = confirm_inputs()
    bad_path = INPUTS["G22_k1_v003"][0]
    try:
        checked(Path(bad_path).read_bytes(), "0" * 64)
    except ValueError as exc:
        if str(exc) != "frozen input hash mismatch":
            raise
    else:
        raise ValueError("mutated expected hash was accepted")
    runs, counts = [], []
    for _ in range(3):
        controls = {label: attribution(dumps[label], parent["corners_63C_v001"])[0]
                    for label in ("63C_v001", "63C_v002")}
        if controls != parent["attribution_63C"]:
            raise ValueError("63C control parity failure")
        accepted, support, breakdown = attribution(dumps["G22_k1_v003"], corners)
        if not all(support):
            raise ValueError(f"missing corner coverage: {support}")
        counts.append(accepted["near_faces"])
        runs.append(json.dumps(dict(controls=controls, accepted=accepted, corners=corners,
                                    corner_support=support, near_orientation_face_degrees=breakdown), sort_keys=True))
    confirm_inputs()
    if len(set(runs)) != 1:
        raise ValueError("non-identical repeats")
    result = dict(accepted_near_irregular_faces=statistics.median(counts), repeats=counts,
                  paired_spread=max(counts) - min(counts), threshold=0,
                  clean=json.loads(runs[0]), injected={"wrong_hash_refused": True},
                  inputs=INPUTS, parent=PARENT, parent_sha256=PARENT_SHA, core_blob=CORE_BLOB,
                  not_measured=["new score calibration", "native readback", "rebuild", "per-face window ownership",
                                "designer intent", "G22 k2/k3", "package parity"])
    with out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(f"accepted_near_irregular_faces={result['accepted_near_irregular_faces']}; paired_spread={result['paired_spread']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
