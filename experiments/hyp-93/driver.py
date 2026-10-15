"""Hypothesis 93: component-local signed volume vs production orientation check.

Reads the tracked box triangulation from tests/qa/test_orientation.py via ast.
Does not modify production code. Exit code is 0 for both verdicts.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from component_volume import component_signed_volumes, positive_sum
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ORIENTATION_TEST = ROOT / "tests" / "qa" / "test_orientation.py"
CHECKS_PY = ROOT / "src" / "twinqa" / "geometry" / "checks.py"
MESH_PY = ROOT / "src" / "twinqa" / "geometry" / "mesh.py"

UNIT_CUBE = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=np.float64,
)
SHIFT = np.array([600000.0, 7500000.0, 150.0], dtype=np.float64)
OUTER_VOLUME = 100.0 ** 3
INNER_VOLUME = 0.2 ** 3
VARIANTS = ("inner_outward", "inner_inverted", "inner_open", "inner_inconsistent")
PACKINGS = ("two_meshes", "one_mesh")
TRANSFORMS = ("identity", "translate", "rz37_translate")
LABELS = {"inner_outward": 1, "inner_inverted": -1, "inner_open": None, "inner_inconsistent": None}
RUNTIME_KEYS = ("baseline_s", "candidate_s")


def main() -> None:
    box_tris = _load_box_tris(ORIENTATION_TEST)
    if len(box_tris) != 12:
        raise RuntimeError(f"_BOX_TRIS has {len(box_tris)} triangles, expected 12")
    hashes = {
        "tests/qa/test_orientation.py": _sha256(ORIENTATION_TEST),
        "src/twinqa/geometry/checks.py": _sha256(CHECKS_PY),
        "src/twinqa/geometry/mesh.py": _sha256(MESH_PY),
        "experiments/hyp-93/driver.py": _sha256(HERE / "driver.py"),
        "experiments/hyp-93/component_volume.py": _sha256(HERE / "component_volume.py"),
    }
    versions = {"python": sys.version, "numpy": np.__version__}
    print(f"python {sys.version.split()[0]}")
    print(f"numpy {np.__version__}")
    for name, digest in hashes.items():
        print(f"sha256 {name} {digest}")

    repeats = []
    payloads = []
    repeat_hashes = []
    for index in range(3):
        cases = [_run_case(box_tris, variant, packing, transform)
                 for variant in VARIANTS for packing in PACKINGS for transform in TRANSFORMS]
        payload = [_without_runtime(case) for case in cases]
        digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
        repeats.append(cases)
        payloads.append(payload)
        repeat_hashes.append(digest)
        print(f"repeat {index + 1} result_sha256 {digest}")

    repeats_identical = len(set(repeat_hashes)) == 1
    failing = _failing_cases(repeats, payloads, repeats_identical)
    summary = _summary(repeats[0], repeats_identical, failing)
    medians = _median_runtimes(repeats)
    document = {
        "versions": versions,
        "input_hashes": hashes,
        "repeat_hashes": repeat_hashes,
        "repeats_identical": repeats_identical,
        "median_runtimes": medians,
        "cases": repeats[0],
        "summary": summary,
    }
    out = HERE / "results.json"
    out.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    print()
    _print_table(repeats[0])
    print()
    for name, counts in summary["requirements"].items():
        print(f"{name}: {counts['passed']}/{counts['applicable']}")
    print(f"cases_ok: {summary['cases_ok']}/{summary['cases_total']}")
    print(f"repeats_identical: {repeats_identical}")
    print(f"VERDICT: {summary['verdict']}")
    if summary["verdict"] == "REJECTED":
        print("failing cases:")
        for item in summary["failing_cases"]:
            print(f"  {item}")
    print(f"wrote {out.relative_to(ROOT).as_posix()}")


def _run_case(box_tris, variant, packing, transform) -> dict:
    outer_tris = [list(tri) for tri in box_tris]
    inner_tris, label = _inner_triangles(box_tris, variant)
    outer_v = _transform(_scaled_box(100.0, (0.0, 0.0, 0.0)), transform)
    inner_v = _transform(_scaled_box(0.2, (49.9, 49.9, 49.9)), transform)
    meshes = _pack(packing, outer_v, outer_tris, inner_v, inner_tris)

    t0 = time.perf_counter()
    baseline = checks.check_orientation(from_dump({"meshes": meshes}), {"weld_m": 0.001})
    t1 = time.perf_counter()
    components = component_signed_volumes(meshes)
    t2 = time.perf_counter()

    scene_volume = _scene_signed_volume(meshes)
    parts = _oracle(packing, len(inner_tris))
    by_key: dict[tuple, list] = {}
    for comp in components:
        key = (comp["mesh"], frozenset(comp["triangle_ids"]))
        by_key.setdefault(key, []).append(comp)
    membership_ok = set(by_key) == set(parts.values()) and all(len(rows) == 1 for rows in by_key.values())

    case = {
        "variant": variant,
        "packing": packing,
        "transform": transform,
        "label": label,
        "analytic_outer": OUTER_VOLUME,
        "analytic_inner": INNER_VOLUME,
        "baseline": {
            "status": baseline["status"],
            "value": int(baseline["value"]),
            "unjudged_meshes": [str(name) for name in baseline["details"]["unjudged_meshes"]],
            "meshes": [
                {
                    "name": str(row["name"]),
                    "winding_bad_edges": int(row["winding_bad_edges"]),
                    "outside_back_faces": int(row["outside_back_faces"]),
                    "judged_faces": int(row["judged_faces"]),
                }
                for row in baseline["details"]["meshes"]
            ],
        },
        "scene_signed_volume": scene_volume,
        "scene_sign": _sign_of(scene_volume),
        "n_components": len(components),
        "membership_ok": membership_ok,
        "positive_sum": positive_sum(components),
        "components": components,
        "outer": _part_view(_pick(by_key, parts["outer"]), OUTER_VOLUME),
        "inner": _part_view(_pick(by_key, parts["inner"]), None if label is None else INNER_VOLUME * label),
        "baseline_s": t1 - t0,
        "candidate_s": t2 - t1,
    }
    return _evaluate(case)


def _evaluate(case: dict) -> dict:
    checks_out = {}
    variant = case["variant"]
    if variant == "inner_inverted":
        baseline = case["baseline"]
        checks_out["inverted_baseline_pass_value0"] = baseline["status"] == "pass" and baseline["value"] == 0
        if case["packing"] == "two_meshes":
            row = next((mesh for mesh in baseline["meshes"] if mesh["name"] == "inner"), None)
            checks_out["inverted_inner_judged_faces_0"] = row is not None and row["judged_faces"] == 0
        checks_out["inverted_scene_volume_positive"] = case["scene_signed_volume"] > 0.0
    if variant in ("inner_outward", "inner_inverted"):
        checks_out["closed_two_components"] = case["n_components"] == 2
        checks_out["closed_membership_exact"] = case["membership_ok"] is True
        checks_out["closed_outer_sign_rel"] = _measured_sign_rel(case["outer"], 1)
        checks_out["closed_inner_sign_rel"] = _measured_sign_rel(case["inner"], case["label"])
    if variant in ("inner_open", "inner_inconsistent"):
        checks_out["defect_two_components"] = case["n_components"] == 2
        checks_out["defect_membership_exact"] = case["membership_ok"] is True
        inner = case["inner"]
        checks_out["defect_inner_not_measured"] = inner["status"] == "not_measured" and len(inner["reasons"]) > 0
        checks_out["defect_outer_sign_rel"] = _measured_sign_rel(case["outer"], 1)
    case["checks"] = checks_out
    case["case_ok"] = all(checks_out.values())
    return case


def _measured_sign_rel(part: dict, expected_sign) -> bool:
    rel = part["rel_err"]
    return part["status"] == "measured" and part["sign"] == expected_sign and rel is not None and rel <= 1e-6


def _part_view(comp: dict | None, expected: float | None) -> dict:
    if comp is None:
        return {
            "status": None,
            "sign": None,
            "signed_volume": None,
            "abs_err": None,
            "rel_err": None,
            "reasons": [],
            "n_triangles": 0,
            "triangle_ids": [],
        }
    volume = comp["signed_volume"]
    abs_err = None
    rel_err = None
    if volume is not None and expected is not None:
        abs_err = abs(volume - expected)
        rel_err = abs_err / abs(expected)
    return {
        "status": comp["status"],
        "sign": comp["sign"],
        "signed_volume": volume,
        "abs_err": abs_err,
        "rel_err": rel_err,
        "reasons": list(comp["reasons"]),
        "n_triangles": comp["n_triangles"],
        "triangle_ids": list(comp["triangle_ids"]),
    }


def _pick(by_key: dict, key: tuple):
    rows = by_key.get(key, [])
    if len(rows) == 1:
        return rows[0]
    return None


def _oracle(packing: str, n_inner: int) -> dict:
    if packing == "two_meshes":
        return {
            "outer": ("outer", frozenset(range(12))),
            "inner": ("inner", frozenset(range(n_inner))),
        }
    return {
        "outer": ("scene", frozenset(range(12))),
        "inner": ("scene", frozenset(range(12, 12 + n_inner))),
    }


def _pack(packing, outer_v, outer_tris, inner_v, inner_tris) -> list[dict]:
    if packing == "two_meshes":
        return [
            _mesh("outer", outer_v, outer_tris),
            _mesh("inner", inner_v, inner_tris),
        ]
    vertices = np.vstack((outer_v, inner_v))
    triangles = [list(tri) for tri in outer_tris] + [[a + 8, b + 8, c + 8] for a, b, c in inner_tris]
    return [_mesh("scene", vertices, triangles)]


def _mesh(name: str, vertices: np.ndarray, triangles: list) -> dict:
    copied = [[int(a), int(b), int(c)] for a, b, c in triangles]
    return {
        "name": name,
        "vertices": np.asarray(vertices, dtype=np.float64).tolist(),
        "triangles": copied,
        "material_ids": [1] * len(copied),
    }


def _inner_triangles(box_tris, variant: str):
    tris = [list(tri) for tri in box_tris]
    if variant == "inner_outward":
        return tris, 1
    if variant == "inner_inverted":
        return [[a, c, b] for a, b, c in tris], -1
    if variant == "inner_open":
        return [list(tri) for tri in tris[2:]], None
    if variant == "inner_inconsistent":
        a, b, c = tris[4]
        tris[4] = [a, c, b]
        return tris, None
    raise ValueError(variant)


def _scaled_box(scale: float, shift: tuple[float, float, float]) -> np.ndarray:
    return UNIT_CUBE * np.float64(scale) + np.asarray(shift, dtype=np.float64)


def _transform(vertices: np.ndarray, name: str) -> np.ndarray:
    verts = np.asarray(vertices, dtype=np.float64)
    if name == "identity":
        return verts.copy()
    if name == "translate":
        return verts + SHIFT
    if name == "rz37_translate":
        theta = math.radians(37.0)
        cosine, sine = math.cos(theta), math.sin(theta)
        rotation = np.array(
            [[cosine, -sine, 0.0], [sine, cosine, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        return verts @ rotation.T + SHIFT
    raise ValueError(name)


def _scene_signed_volume(meshes: list[dict]) -> float:
    chunks = [np.asarray(mesh["vertices"], dtype=np.float64) for mesh in meshes]
    reference = np.concatenate(chunks, axis=0).mean(axis=0)
    terms = []
    for mesh, verts in zip(meshes, chunks):
        for tri in mesh["triangles"]:
            a, b, c = (int(i) for i in tri)
            pa, pb, pc = verts[a] - reference, verts[b] - reference, verts[c] - reference
            terms.append(float(np.dot(pa, np.cross(pb, pc))))
    return math.fsum(terms) / 6.0


def _sign_of(volume: float):
    if volume > 0.0:
        return 1
    if volume < 0.0:
        return -1
    return None


def _load_box_tris(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_BOX_TRIS":
                    return ast.literal_eval(node.value)
    raise RuntimeError(f"_BOX_TRIS assignment not found in {path}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _without_runtime(case: dict) -> dict:
    return {key: value for key, value in case.items() if key not in RUNTIME_KEYS}


def _median_runtimes(repeats: list[list[dict]]) -> list[dict]:
    rows = []
    for index, case in enumerate(repeats[0]):
        baseline = [repeat[index]["baseline_s"] for repeat in repeats]
        candidate = [repeat[index]["candidate_s"] for repeat in repeats]
        rows.append({
            "variant": case["variant"],
            "packing": case["packing"],
            "transform": case["transform"],
            "baseline_s": statistics.median(baseline),
            "candidate_s": statistics.median(candidate),
        })
    return rows


def _summary(cases: list[dict], repeats_identical: bool, failing: list[str]) -> dict:
    applicable: dict[str, int] = {}
    passed: dict[str, int] = {}
    for case in cases:
        for name, ok in case["checks"].items():
            applicable[name] = applicable.get(name, 0) + 1
            passed[name] = passed.get(name, 0) + int(bool(ok))
    requirements = {
        name: {"passed": passed[name], "applicable": applicable[name]}
        for name in sorted(applicable)
    }
    cases_ok = sum(1 for case in cases if case["case_ok"])
    verdict = "CONFIRMED" if repeats_identical and cases_ok == len(cases) and not failing else "REJECTED"
    return {
        "requirements": requirements,
        "cases_ok": cases_ok,
        "cases_total": len(cases),
        "repeats_identical": repeats_identical,
        "failing_cases": failing,
        "verdict": verdict,
    }


def _failing_cases(repeats, payloads, repeats_identical) -> list[str]:
    failing = []
    for case in repeats[0]:
        if case["case_ok"]:
            continue
        missed = [name for name, ok in case["checks"].items() if not ok]
        failing.append(f"{case['variant']} {case['packing']} {case['transform']}: {', '.join(missed)}")
    if not repeats_identical:
        failing.append("repeats_not_identical")
        for index in range(1, len(payloads)):
            for left, right in zip(payloads[0], payloads[index]):
                if _canonical(left) != _canonical(right):
                    failing.append(
                        f"repeat {index + 1} differs: {left['variant']} {left['packing']} {left['transform']}"
                    )
    return failing


def _print_table(cases: list[dict]) -> None:
    for case in cases:
        judged = "-"
        if case["packing"] == "two_meshes":
            row = next(mesh for mesh in case["baseline"]["meshes"] if mesh["name"] == "inner")
            judged = str(row["judged_faces"])
        outer = case["outer"]
        inner = case["inner"]
        reasons = ",".join(inner["reasons"]) if inner["reasons"] else "-"
        print(
            f"{case['variant']:22} {case['packing']:12} {case['transform']:16} "
            f"base={case['baseline']['status']}/{case['baseline']['value']} "
            f"inner_judged={judged:>4} "
            f"scene_sign={_fmt_sign(case['scene_sign']):>2} "
            f"n={case['n_components']} mem={case['membership_ok']} "
            f"outer={_fmt_sign(outer['sign']):>2}/{_fmt_rel(outer['rel_err']):>9} "
            f"inner={inner['status']}/{_fmt_sign(inner['sign']):>2}/{_fmt_rel(inner['rel_err']):>9}/{reasons} "
            f"case_ok={case['case_ok']}"
        )


def _fmt_sign(sign) -> str:
    if sign is None:
        return "-"
    return f"{int(sign):+d}"


def _fmt_rel(value) -> str:
    if value is None:
        return "-"
    return f"{value:.3e}"


if __name__ == "__main__":
    main()
