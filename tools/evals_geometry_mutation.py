"""new-case: fixed synthetic geometry mutation recall, not a delivery certificate.

Each adapter has a named geometric scope: unrelated components must not turn a miss
into a detection. Geometry is generated in metres, serialized and loaded by from_dump.
VALID means finite, indexed, loadable triangle data, not defect-free/manifold geometry.
No checker is repaired here. UV edge_densities is a metric helper, not V009: its
512 px/m comparison is explicitly an eval adapter, not general delivery coverage.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import time
import json
from pathlib import Path
import random
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.spec.model import Spec
from twinqa.geometry import checks
from twinqa.geometry.mesh import from_dump
from twinqa.geometry.topology import count_defects
from twinqa.geometry.complexity import check_complexity
from twinqa.clearance import near_parallel_overlaps
from twinqa.uv import edge_densities

SEED = 461


def mesh(name, vertices, triangles, material=1):
    return {"name": name, "vertices": vertices, "triangles": triangles,
            "material_ids": [material] * len(triangles), "polygon_sizes": [3] * len(triangles)}


def box(name, low, high, bottom=True):
    x, y, z = low
    a, b, c = high
    v = [[x,y,z], [a,y,z], [a,b,z], [x,b,z], [x,y,c], [a,y,c], [a,b,c], [x,b,c]]
    t = [[0,2,1], [0,3,2]] if bottom else []
    t += [[0,1,5], [0,5,4], [1,2,6], [1,6,5], [2,3,7], [2,7,6], [3,0,4], [3,4,7], [4,5,6], [4,6,7]]
    return mesh(name, v, t)


def quad(name, x, z, material=1):
    return mesh(name, [[x,0,z], [x+1,0,z], [x+1,1,z], [x,1,z]], [[0,1,2], [0,2,3]], material)


def base_scene(seed=SEED):
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    # Seed changes actual coordinates, not labels, without changing defect magnitudes.
    x = random.Random(seed).uniform(20, 30)
    opening = mesh("opening", [[2,.2,.9], [3.5,.2,.9], [3.5,.2,2.4], [2,.2,2.4]],
                   [[0,1,2], [0,2,3]], 11)
    return {"source": "synthetic", "units": "m", "meshes": [
        opening, box("normal_target", [x,0,0], [x+1,1,1]),
        box("slab", [40,0,0], [44,4,.2]),
        box("wall", [41,1,.2], [43,2,2], bottom=False),
        quad("contact_a", 50, 0), quad("contact_b", 50, .01),
        quad("density", 60, 0, 21), quad("budget", 70, 0)],
        "uv": {"density": [[0,0], [.25,0], [.25,.25], [0,.25]]}, "texture_size": 4096}


# Freeze these stimuli before evaluating checker improvements. One row = one planted operation.
CASES = {
    "moved_opening": ("opening", ("opening_planes",), "window translated +0.3 m along wall"),
    "wall_slab_gap": ("wall", ("mesh_joint",), "wall lifted 0.005 m off its supporting slab"),
    "false_contact": ("contact_b", ("clearance",), "two separate panels touch; expected separation 0.01 m"),
    "flipped_normals": ("normal_target", ("orientation", "horizontal_faces"), "top face group winding reversed"),
    "sliver_triangle": ("normal_target", ("topology", "mesh_target"), "positive-area sliver, altitude 1e-10 m"),
    "duplicate_faces": ("normal_target", ("topology", "clearance_target", "mesh_target"), "duplicate top triangle offset 0.001 m (<2 mm D098 band)"),
    "low_density": ("density", ("uv_density_adapter",), "one material UV scale reduced to 256 px/m"),
    "polycount": ("budget", ("triangle_budget", "complexity"), "275x275 subdivided plane exceeds npm_min 150000 triangles"),
}


ADAPTERS = {
    "opening_planes": ("twinqa.geometry.checks.check_opening_planes", ["opening"]),
    "mesh_joint": ("twinqa.geometry.checks.check_mesh", ["wall", "slab"]),
    "mesh_target": ("twinqa.geometry.checks.check_mesh", ["normal_target"]),
    "orientation": ("twinqa.geometry.checks.check_orientation", ["normal_target"]),
    "horizontal_faces": ("twinqa.geometry.checks.check_horizontal_faces", ["normal_target"]),
    "topology": ("twinqa.geometry.topology.count_defects", ["normal_target"]),
    "clearance": ("twinqa.clearance.near_parallel_overlaps", ["contact_a", "contact_b"]),
    "clearance_target": ("twinqa.clearance.near_parallel_overlaps", ["normal_target"]),
    "uv_density_adapter": ("twinqa.uv.edge_densities", ["density"]),
    "triangle_budget": ("twinqa.geometry.checks.check_budget", None),
    "complexity": ("twinqa.geometry.complexity.check_complexity", None),
}


def corpus(seed=SEED):
    base = base_scene(seed)
    mutants = {}
    for name, (target, expected, description) in CASES.items():
        scene = copy.deepcopy(base)
        m = next(m for m in scene["meshes"] if m["name"] == target)
        if name == "moved_opening":
            m["vertices"] = [[x+.3, y, z] for x,y,z in m["vertices"]]
        elif name == "wall_slab_gap":
            m["vertices"] = [[x,y,z+.005] for x,y,z in m["vertices"]]
        elif name == "false_contact":
            m["vertices"] = [[x,y,0] for x,y,z in m["vertices"]]
        elif name == "flipped_normals":
            m["triangles"][-2:] = [t[::-1] for t in m["triangles"][-2:]]
        elif name == "sliver_triangle":
            a,b,c = m["triangles"].pop()
            p = np.asarray(m["vertices"])
            q = ((p[a]+p[b])/2 + 1e-10 * (p[c]-(p[a]+p[b])/2)).tolist()
            k = len(p)
            m["vertices"].append(q)
            m["triangles"] += [[a,b,k], [b,c,k], [c,a,k]]
        elif name == "duplicate_faces":
            points = [m["vertices"][i] for i in m["triangles"][-1]]
            k = len(m["vertices"])
            m["vertices"] += [[x,y,z+.001] for x,y,z in points]
            m["triangles"].append([k,k+1,k+2])
        elif name == "low_density":
            scene["uv"]["density"] = [[u/4,v/4] for u,v in scene["uv"]["density"]]
        elif name == "polycount":
            n = 275
            m["vertices"] = [[70+i/n, j/n, 0] for j in range(n+1) for i in range(n+1)]
            m["triangles"] = []
            for j in range(n):
                for i in range(n):
                    a = j*(n+1)+i
                    m["triangles"] += [[a,a+1,a+n+2], [a,a+n+2,a+n+1]]
        m["material_ids"] = [m["material_ids"][0]] * len(m["triangles"])
        m["polygon_sizes"] = [3] * len(m["triangles"])
        mutants[name] = {"scene": scene, "target": target, "expected": list(expected), "description": description}
    return base, mutants


def scoped(scene, names):
    selected = [m for m in scene["meshes"] if m["name"] in names]
    if {m["name"] for m in selected} != set(names):
        raise ValueError(f"missing mesh scope: {names}")
    return from_dump({"meshes": selected})


def configuration():
    spec = Spec.model_validate(json.loads((ROOT / "tests/fixtures/spec-b01-v0.3.json").read_text()))
    tol = json.loads((ROOT / "benchmark/bench-b01-box/tolerances.json").read_text())["geometry"]
    return spec, {**tol, "weld_m": spec.weld_m}, checks.load_ranges()


def validate_scene(scene):
    """Reject malformed evidence before even a checker with a narrower scope can pass."""
    try:
        if scene["source"] != "synthetic" or scene["units"] != "m":
            raise ValueError("only synthetic metre scenes supported")
        meshes = scene["meshes"]
        expected = {"opening", "normal_target", "wall", "slab", "contact_a", "contact_b", "density", "budget"}
        names = [m["name"] for m in meshes]
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError(f"duplicate, missing or unmapped mesh names: {names}")
        if set(scene["uv"]) != {"density"}:
            raise ValueError(f"unmapped UV material/mesh: {list(scene['uv'])}")
        uv = np.asarray(scene["uv"]["density"], float)
        if uv.shape != (4,2) or not np.isfinite(uv).all():
            raise ValueError("density: invalid UV coordinates")
        if type(scene["texture_size"]) is not int or scene["texture_size"] <= 0:
            raise ValueError("density: invalid texture_size")
        for m in meshes:
            v, t, mid = np.asarray(m["vertices"], float), np.asarray(m["triangles"]), np.asarray(m["material_ids"])
            name = m["name"]
            if v.ndim != 2 or v.shape[1] != 3 or not len(v) or not np.isfinite(v).all():
                raise ValueError(f"{name}: empty/nonfinite/invalid vertices")
            if t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in "iu":
                raise ValueError(f"{name}: invalid triangle indices")
            if t.min() < 0 or t.max() >= len(v) or np.any(np.diff(np.sort(t,axis=1),axis=1) == 0):
                raise ValueError(f"{name}: out-of-range/repeated triangle index")
            if mid.shape != (len(t),) or mid.dtype.kind not in "iu" or not np.isin(mid, [1,11,21]).all():
                raise ValueError(f"{name}: unmapped material ids: {m['material_ids'][:10]}")
            if m["polygon_sizes"] != [3] * len(t):
                raise ValueError(f"{name}: inconsistent polygon_sizes")
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError(f"partial or unsupported scene: {exc}") from exc


def run_checker(name, scene):
    validate_scene(scene)
    spec, tol, ranges = configuration()
    if name == "opening_planes":
        # The fixture has two windows; this diagnostic scene deliberately uses only L0.
        spec = spec.model_copy(update={"floors": spec.floors[:1]})
        return checks.check_opening_planes(scoped(scene, ["opening"]), spec, tol, ranges)
    if name == "mesh_joint":
        return checks.check_mesh(scoped(scene, ["wall", "slab"]), tol, ranges, build="from_source")
    if name == "orientation":
        return checks.check_orientation(scoped(scene, ["normal_target"]), tol)
    if name == "horizontal_faces":
        return checks.check_horizontal_faces(scoped(scene, ["normal_target"]), tol)
    if name == "mesh_target":
        return checks.check_mesh(scoped(scene, ["normal_target"]), tol, ranges)
    if name == "topology":
        soup = scoped(scene, ["normal_target"])
        counts = count_defects(soup.vertices, soup.triangles)
        # Exact V004 regulatory policy, not zero-tolerance detection of all duplicates.
        ok = counts["duplicates_and_self_intersections"] <= 100 and not any(
            counts[k] for k in ("isolated_vertices", "isolated_edges", "isolated_polygons", "zero_length_edges"))
        return checks.result(name, ok, counts, 100)
    if name in ("clearance", "clearance_target"):
        scope = ["contact_a", "contact_b"] if name == "clearance" else ["normal_target"]
        # Keep source object names and object-local indices, not flattened Soup IDs.
        faces = []
        for m in scene["meshes"]:
            if m["name"] in scope:
                corners = scoped(scene, [m["name"]]).corners()
                faces.extend({"object": m["name"], "index": i, "points": t.tolist()}
                             for i, t in enumerate(corners))
        hits = near_parallel_overlaps(faces, .005)
        return checks.result(name, not hits, len(hits), 0, {"pairs": hits})
    if name == "uv_density_adapter":
        m = next(m for m in scene["meshes"] if m["name"] == "density")
        densities = edge_densities(m["vertices"], scene["uv"]["density"], scene["texture_size"])
        return checks.result(name, min(densities) >= 512, densities, 512,
                             {"scope": "material 21 on density panel", "coverage": "metric helper + eval threshold, NOT V009"})
    if name == "triangle_budget":
        return checks.check_budget(from_dump(scene), tol)
    if name == "complexity":
        modules = {"meshes": {m["name"]: m for m in scene["meshes"]},
                   "objects": [{"mesh": m["name"], "group": "synthetic"} for m in scene["meshes"]]}
        return check_complexity(modules, {"budget": {"synthetic": tol["triangles_max"]},
            "total_max": tol["triangles_max"], "decor_groups": [], "decor_section_points_max": 12,
            "silhouette_dev_min_m": .07})
    raise ValueError(f"unsupported checker: {name}")


def is_caught(result):
    if result["status"] not in ("pass", "fail", "not_measured"):
        raise ValueError(f"unsupported checker status: {result['status']}")
    return result["status"] == "fail"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                      separators=(",", ":")).encode()).hexdigest()


INPUTS = ("tools/evals_geometry_mutation.py", "tests/fixtures/spec-b01-v0.3.json",
          "benchmark/bench-b01-box/tolerances.json",
          "standards/material_id_ranges.yaml", "src/twinqa/geometry/checks.py",
          "src/twinqa/geometry/mesh.py", "src/twinqa/geometry/topology.py",
          "src/twinqa/geometry/complexity.py", "src/twinqa/clearance.py", "src/twinqa/uv.py")


def input_hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in INPUTS}


def evaluate(seed=SEED):
    before = input_hashes()
    base, mutants = corpus(seed)
    corpus_hash = fingerprint({"base": base, "mutants": mutants})
    # Exercise the actual JSON dump reader, not just in-memory Soup construction.
    base = json.loads(json.dumps(base, allow_nan=False))
    names = sorted({n for _, expected, _ in CASES.values() for n in expected})
    base_results = [{"checker": n, **run_checker(n, base)} for n in names]
    if any(r["status"] != "pass" for r in base_results):
        raise ValueError(f"base is not clean: {base_results}")
    rows = []
    for defect, case in sorted(mutants.items()):
        results = [{"checker": n, **run_checker(n, case["scene"])} for n in case["expected"]]
        rows.append({"defect": defect, "description": case["description"], "expected": case["expected"],
                     "checks": results, "caught": any(is_caught(r) for r in results)})
    by_checker = {n: {"caught": sum(is_caught(r) for row in rows for r in row["checks"] if r["checker"] == n),
                      "total": sum(n in row["expected"] for row in rows)} for n in names}
    by_function = {}
    all_names = sorted(m["name"] for m in base["meshes"])
    adapters = {}
    for name, (function, scope) in sorted(ADAPTERS.items()):
        counts = by_function.setdefault(function, {"caught": 0, "total": 0})
        for key in counts:
            counts[key] += by_checker[name][key]
        scope = all_names if scope is None else scope
        adapters[name] = {"function": function, "scope": scope,
            "excluded": sorted(set(all_names)-set(scope)),
            "exclusion_reason": "unrelated geometric targets; not claimed as checked by this adapter"}
    if input_hashes() != before:
        raise ValueError("checker/configuration inputs changed during evaluation")
    return {"synthetic": True, "seed": seed, "corpus_sha256": corpus_hash, "input_sha256": before, "profile": "npm_min; UV diagnostic 512 px/m from issue #461",
            "adapters": adapters, "by_function": by_function,
            "base": base_results, "false_positives": 0, "defects": rows, "by_checker": by_checker,
            "summary": {"caught": sum(r["caught"] for r in rows), "total": len(rows)}}


def markdown(report):
    lines = ["# Synthetic geometry mutation recall", "", f"Seed: {report['seed']}. Synthetic data only.",
             f"Caught {report['summary']['caught']} of {report['summary']['total']} planted defects; "
             f"clean-base false positives: {report['false_positives']}.",
             f"Corpus SHA256: `{report['corpus_sha256']}`.", "",
             "| Defect | Expected checker / adapter | Verdict | Caught |",
             "|---|---|---|---|"]
    for row in report["defects"]:
        for r in row["checks"]:
            lines.append(f"| {row['defect']} | {r['checker']} | {r['status']} | {'yes' if is_caught(r) else 'MISSED'} |")
    lines += ["", "| Checker / adapter | Caught | Applicable defects |", "|---|---|---|"]
    for name, counts in report["by_checker"].items():
        lines.append(f"| {name} | {counts['caught']} | {counts['total']} |")
    lines += ["", "| Function | Caught | Applicable defects |", "|---|---|---|"]
    for name, counts in sorted(report["by_function"].items()):
        lines.append(f"| {name} | {counts['caught']} | {counts['total']} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="deterministic JSON on stdout; runtime on stderr")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    start = time.perf_counter()
    try:
        report = evaluate(args.seed)
    except (ValueError, OSError) as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, allow_nan=False) if args.json else markdown(report))
    print(f"runtime_seconds={time.perf_counter()-start:.6f}", file=sys.stderr)
    # Successful measurement includes misses, not checker errors or a dirty base.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
