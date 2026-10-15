"""Hypothesis 107: geometric wall binding versus the synthetic W0000 name contract."""

import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import time
import traceback
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.placement
import numpy as np
from dt_ai.spec.compare import compare_specs
from dt_ai.spec.model import Spec

import geo_binder

ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = ROOT / "experiments" / "revit-ifc-offline-intake" / "pilot.py"
HASH_PATHS = [
    PILOT_PATH,
    ROOT / "experiments" / "revit-ifc-offline-intake" / "test_pilot.py",
    ROOT / "benchmark" / "bench-b01-box" / "spec.json",
    ROOT / "benchmark" / "bench-b02-corner-niche" / "spec.json",
    ROOT / "benchmark" / "bench-b02t-terrace" / "spec.json",
    ROOT / "benchmark" / "bench-k01-kpp1" / "tolerances.json",
]
CASES = ("bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace")
ORDERS = ("original", "reversed", "cyclic1")
RENAME = ("null", "identical", "suffix")
FAULTS = ("shared_placement", "z_shift")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_pilot():
    spec = importlib.util.spec_from_file_location("pilot", PILOT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scrub(value):
    if isinstance(value, dict):
        return {str(key): scrub(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else "inf"
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str) or value is None or isinstance(value, bool):
        return value
    return str(value)


def canon_hash(payload):
    blob = json.dumps(scrub(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def input_hashes():
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path) for path in HASH_PATHS}


def reorder(walls, order):
    walls = list(walls)
    if order == "reversed":
        return list(reversed(walls))
    if order == "cyclic1":
        return walls[1:] + walls[:1] if walls else walls
    return walls


def opening_indices(spec):
    return {floor.level: sorted(int(op.wall) for op in floor.openings) for floor in spec.expanded_floors()}


def component_error(ref, got):
    left = {level.name: float(level.elev_m) for level in ref.levels}
    right = {level.name: float(level.elev_m) for level in got.levels}
    floors_l = {floor.level: floor for floor in ref.expanded_floors()}
    floors_r = {floor.level: floor for floor in got.expanded_floors()}
    if set(left) != set(right) or set(floors_l) != set(floors_r):
        return math.inf
    err = max((abs(left[name] - right[name]) for name in left), default=0.0)
    for level, floor in floors_l.items():
        other = floors_r[level]
        contour_l, contour_r = floor.contour or [], other.contour or []
        if len(contour_l) != len(contour_r):
            return math.inf
        for pa, pb in zip(contour_l, contour_r):
            err = max(err, abs(float(pa[0]) - float(pb[0])), abs(float(pa[1]) - float(pb[1])))
        opens_l = sorted(floor.openings, key=lambda op: (op.wall, float(op.x_m)))
        opens_r = sorted(other.openings, key=lambda op: (op.wall, float(op.x_m)))
        if len(opens_l) != len(opens_r):
            return math.inf
        for oa, ob in zip(opens_l, opens_r):
            depth_l = oa.depth_m if oa.depth_m is not None else ref.opening_depth_default_m
            depth_r = ob.depth_m if ob.depth_m is not None else got.opening_depth_default_m
            pairs = ((oa.x_m, ob.x_m), (oa.sill_m, ob.sill_m), (oa.w_m, ob.w_m), (oa.h_m, ob.h_m), (depth_l, depth_r))
            err = max([err, *(abs(float(a) - float(b)) for a, b in pairs)])
    return err


def residual_max(pairs):
    if not pairs:
        return None
    return {"origin_err": max(row[2] for row in pairs), "axis_err": max(row[3] for row in pairs)}


def storey_z(storey, building_placement, scale):
    local = np.linalg.inv(np.array(ifcopenshell.util.placement.get_local_placement(building_placement)))
    local = local @ np.array(ifcopenshell.util.placement.get_local_placement(storey.ObjectPlacement))
    return float(local[2, 3] * scale)


def run_extracts(pilot, path, target, orders=ORDERS, repeats=3):
    saved = pilot.bind_walls
    ctx = {"order": "original", "mapping": [], "residuals": []}

    def wrapper(walls, ring, storey_z_m, building_placement, scale):
        chosen = target(reorder(walls, ctx["order"]), ring, storey_z_m, building_placement, scale)
        evidence = getattr(target, "last_evidence", None)
        if evidence:
            ctx["residuals"].extend(evidence["eligible_pairs"])
        for edge, wall in chosen.items():
            ctx["mapping"].append([pilot.storey_of(wall).GlobalId, int(edge), wall.GlobalId])
        return chosen

    pilot.bind_walls = wrapper
    runs = []
    try:
        for order in orders:
            for _ in range(repeats):
                ctx.update(order=order, mapping=[], residuals=[])
                started = time.perf_counter()
                try:
                    spec, report = pilot.extract(path)
                    runs.append({
                        "status": "accept", "dt": time.perf_counter() - started, "spec": spec,
                        "mapping": sorted(ctx["mapping"]), "residuals": list(ctx["residuals"]),
                        "counts": report["counts"], "wall_m": float(report["wall_profile_vs_geom_m"]),
                        "error": None,
                    })
                except Exception as exc:
                    runs.append({
                        "status": "refuse", "dt": time.perf_counter() - started, "spec": None,
                        "mapping": sorted(ctx["mapping"]), "residuals": list(ctx["residuals"]),
                        "counts": None, "wall_m": None,
                        "error": {"type": type(exc).__name__, "message": str(exc), "evidence": getattr(exc, "evidence", None)},
                    })
    finally:
        pilot.bind_walls = saved
    return runs


def canonical(run):
    if run["status"] == "accept":
        return {"status": "accept", "mapping": run["mapping"], "spec": run["spec"].model_dump(mode="json")}
    return {"status": "refuse", "mapping": run["mapping"], "error": run["error"]}


def reduce_runs(runs, original, clean_spec, oracle_rows, ref_raw, tolerances, pilot):
    hashes = sorted({canon_hash(canonical(run)) for run in runs})
    statuses = {run["status"] for run in runs}
    head = runs[0]
    record = {
        "status": head["status"] if len(statuses) == 1 else "mixed",
        "n_runs": len(runs),
        "distinct_canonical": hashes,
        "median_s": pilot.median([run["dt"] for run in runs]),
        "error": scrub(head["error"]),
        "message_is_unsupported_wall_mapping": bool(head["error"] and head["error"]["message"] == "unsupported wall mapping"),
        "mapping": head["mapping"],
        "residual_max": residual_max(head["residuals"]),
        "residuals": head["residuals"],
    }
    if record["status"] != "accept":
        record.update(mapping_eq_oracle=False, counts_ok=False, opening_indices_ok=False,
                      max_component_error_m=None, k01_failing=None, independent_devs=None, wall_profile_vs_geom_m=None)
        return record
    expected = pilot.expect_counts(original)
    clean_idx, orig_idx = opening_indices(clean_spec), opening_indices(original)
    mapping_ok, counts_ok, index_ok, wall_ok = [], [], [], []
    err_orig, err_clean, failing, devs = [], [], [], None
    for run in runs:
        mapping_ok.append({tuple(row) for row in run["mapping"]} == {tuple(row) for row in oracle_rows})
        counts_ok.append(run["counts"] == expected)
        index_ok.append(opening_indices(run["spec"]) == clean_idx == orig_idx)
        err_orig.append(component_error(original, run["spec"]))
        err_clean.append(component_error(clean_spec, run["spec"]))
        wall_ok.append(run["wall_m"] <= 1e-3)
        compared = compare_specs(ref_raw, run["spec"].model_dump(mode="json"), {}, {}, tolerances)
        failing.append(list(compared["failing"]))
        devs = pilot.independent_devs(ref_raw, run["spec"].model_dump(mode="json"))
    record.update({
        "mapping_eq_oracle": all(mapping_ok),
        "counts_ok": all(counts_ok),
        "opening_indices_ok": all(index_ok),
        "max_component_error_m": {"vs_original": scrub(max(err_orig)), "vs_clean": scrub(max(err_clean))},
        "k01_failing": failing[0],
        "k01_ok": all(not row for row in failing),
        "independent_devs": [scrub(value) for value in devs],
        "wall_profile_vs_geom_m": scrub(max(run["wall_m"] for run in runs)),
        "wall_ok": all(wall_ok),
        "error_within_1e-5": max(err_orig) <= 1e-5 and max(err_clean) <= 1e-5,
    })
    return record


def entity_counts(file_obj):
    return {kind: len(file_obj.by_type(kind)) for kind in ("IfcWall", "IfcSlab", "IfcOpeningElement", "IfcBuildingStorey")}


def shift_z(file_obj, placement, delta):
    location = placement.RelativePlacement.Location
    coords = [float(value) for value in location.Coordinates]
    while len(coords) < 3:
        coords.append(0.0)
    coords[2] += delta
    if len(list(file_obj.get_inverse(location))) > 1:
        placement.RelativePlacement.Location = file_obj.create_entity("IfcCartesianPoint", Coordinates=tuple(coords))
    else:
        location.Coordinates = tuple(coords)
    return coords[2]


def scene(pilot, file_obj):
    scale = pilot.length_scale(file_obj)
    building = file_obj.by_type("IfcBuilding")[0].ObjectPlacement
    rings, groups, elevations = {}, {}, {}
    for storey in file_obj.by_type("IfcBuildingStorey"):
        elevations[storey.GlobalId] = storey_z(storey, building, scale)
    for slab in file_obj.by_type("IfcSlab"):
        host = pilot.storey_of(slab)
        solid = pilot.body_solid(slab)
        rings[host.GlobalId] = pilot.to_building(
            pilot.profile_ring(solid), solid.Position, slab.ObjectPlacement, building, scale)
    for wall in file_obj.by_type("IfcWall"):
        groups.setdefault(pilot.storey_of(wall).GlobalId, []).append(wall)
    return scale, building, rings, groups, elevations


def evidence_matches(evidence, manifest):
    expected = manifest["expected"]
    for key, gids in expected.get("edges_with_multiple_walls", {}).items():
        if not set(gids) <= set(evidence["edges_with_multiple_walls"].get(key, [])):
            return False
    if not set(expected.get("edges_without_wall", [])) <= set(evidence["edges_without_wall"]):
        return False
    if not set(expected.get("walls_without_edge", [])) <= set(evidence["walls_without_edge"]):
        return False
    return True


def main():
    missing = [str(path.relative_to(ROOT)) for path in HASH_PATHS if not path.is_file()]
    if missing:
        payload = {"synthetic": True, "delivery_passed": False, "verdict": {"status": "INCONCLUSIVE", "missing": missing}}
        (ROOT / "experiments" / "hyp-107" / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload["verdict"]))
        return 0
    before = input_hashes()
    pilot = load_pilot()
    binder = geo_binder.make_geometric_binder(pilot)
    tolerances = json.loads(HASH_PATHS[-1].read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="hyp107-"))
    print(f"temp {tmp}", file=sys.stderr)
    paths, specs, raws, oracle, lowest = {}, {}, {}, {}, {}
    for case in CASES:
        raw = json.loads((ROOT / "benchmark" / case / "spec.json").read_text(encoding="utf-8"))
        spec = Spec.model_validate(raw)
        ref = json.loads(json.dumps(raw))
        ref["roof"] = None
        for prefix, unit in ((None, "metre"), ("MILLI", "millimetre")):
            label = f"{spec.id}:{unit}"
            path = tmp / f"{label.replace(':', '-')}.ifc"
            pilot.generate(spec, prefix, path)
            paths[label] = path
            specs[label] = spec
            raws[label] = ref
            file_obj = ifcopenshell.open(str(path))
            scale = pilot.length_scale(file_obj)
            building = file_obj.by_type("IfcBuilding")[0].ObjectPlacement
            rows, best_gid, best_z = [], None, None
            for wall in file_obj.by_type("IfcWall"):
                storey = pilot.storey_of(wall)
                rows.append([storey.GlobalId, int(wall.Name[1:]), wall.GlobalId])
                elev = storey_z(storey, building, scale)
                if best_z is None or elev < best_z:
                    best_z, best_gid = elev, storey.GlobalId
            oracle[label] = sorted(rows)
            lowest[label] = best_gid
    clean = {}
    for label, path in list(paths.items()):
        spec, _report = pilot.extract(path)
        clean[label] = spec
    manifests = {}
    for label, path in list(paths.items()):
        file_obj = ifcopenshell.open(str(path))
        base_ids = sorted(wall.GlobalId for wall in file_obj.by_type("IfcWall"))
        base_counts = entity_counts(file_obj)
        for mode in RENAME:
            names = {}
            renamed = ifcopenshell.open(str(path))
            ordered = sorted(renamed.by_type("IfcWall"), key=lambda wall: wall.GlobalId)
            for index, wall in enumerate(ordered):
                if mode == "null":
                    wall.Name = None
                elif mode == "identical":
                    wall.Name = "Basic Wall:Generic - 200mm"
                else:
                    wall.Name = f"Basic Wall:Generic - 200mm:{348921 + 7 * index}"
                names[wall.GlobalId] = wall.Name
            dest = tmp / f"{label.replace(':', '-')}-{mode}.ifc"
            renamed.write(str(dest))
            check = ifcopenshell.open(str(dest))
            got = {wall.GlobalId: wall.Name for wall in check.by_type("IfcWall")}
            if sorted(got) != base_ids or entity_counts(check) != base_counts or got != names:
                raise RuntimeError(f"rename did not survive {label}:{mode}")
            paths[f"{label}:{mode}"] = dest
            specs[f"{label}:{mode}"] = specs[label]
            raws[f"{label}:{mode}"] = raws[label]
        walls = {row[1]: row[2] for row in oracle[label] if row[0] == lowest[label]}
        for fault in FAULTS:
            faulted = ifcopenshell.open(str(path))
            for wall in faulted.by_type("IfcWall"):
                wall.Name = None
            by_gid = {wall.GlobalId: wall for wall in faulted.by_type("IfcWall")}
            edge0, edge1 = by_gid[walls[0]], by_gid[walls[1]]
            expected_z = None
            if fault == "shared_placement":
                edge1.ObjectPlacement = edge0.ObjectPlacement
                manifest = {
                    "fault": fault, "storey_global_id": lowest[label],
                    "affected_wall_ids": sorted((walls[0], walls[1])),
                    "expected": {"edges_with_multiple_walls": {"0": sorted((walls[0], walls[1]))}, "edges_without_wall": [1]},
                }
            else:
                delta = 1.0 if label.endswith("millimetre") else 0.001
                expected_z = shift_z(faulted, edge0.ObjectPlacement, delta)
                manifest = {
                    "fault": fault, "storey_global_id": lowest[label],
                    "affected_wall_ids": [walls[0]],
                    "expected": {"walls_without_edge": [walls[0]], "edges_without_wall": [0]},
                }
            dest = tmp / f"{label.replace(':', '-')}-{fault}.ifc"
            faulted.write(str(dest))
            check = ifcopenshell.open(str(dest))
            by_gid = {wall.GlobalId: wall for wall in check.by_type("IfcWall")}
            names_ok = all(wall.Name is None for wall in by_gid.values()) and sorted(by_gid) == base_ids
            if fault == "shared_placement":
                fault_ok = by_gid[walls[0]].ObjectPlacement.id() == by_gid[walls[1]].ObjectPlacement.id()
            else:
                got_z = float(by_gid[walls[0]].ObjectPlacement.RelativePlacement.Location.Coordinates[2])
                fault_ok = abs(got_z - expected_z) <= 1e-6
            if not names_ok or not fault_ok or entity_counts(check) != base_counts:
                raise RuntimeError(f"fault did not survive {label}:{fault}")
            key = f"{label}:{fault}"
            paths[key] = dest
            manifests[key] = manifest
            specs[key] = specs[label]
            raws[key] = raws[label]
    file_hashes = {label: sha256_file(path) for label, path in sorted(paths.items())}
    print(f"files {len(paths)}", file=sys.stderr)
    original_bind = pilot.bind_walls
    baseline, candidate = {}, {}
    for label in sorted(paths):
        print(f"baseline {label}", file=sys.stderr)
        parent = ":".join(label.split(":")[:2])
        runs = run_extracts(pilot, paths[label], original_bind)
        baseline[label] = reduce_runs(runs, specs[parent], clean[parent], oracle[parent], raws[parent], tolerances, pilot)
        if label not in manifests:
            print(f"candidate {label}", file=sys.stderr)
            runs = run_extracts(pilot, paths[label], binder)
            candidate[label] = reduce_runs(runs, specs[parent], clean[parent], oracle[parent], raws[parent], tolerances, pilot)
    malformed = {}
    for label, manifest in manifests.items():
        print(f"malformed {label}", file=sys.stderr)
        hashes, bound_sets, evidences, matched, accepted, samples = [], [], [], [], [], []
        for order in ORDERS:
            for _ in range(3):
                file_obj = ifcopenshell.open(str(paths[label]))
                scale, building, rings, groups, elevations = scene(pilot, file_obj)
                started = time.perf_counter()
                bound, errors = [], {}
                for gid in sorted(groups):
                    try:
                        binder(reorder(groups[gid], order), rings[gid], elevations[gid], building, scale)
                        bound.append(gid)
                    except binder.UnresolvedBinding as exc:
                        errors[gid] = exc.evidence
                samples.append(time.perf_counter() - started)
                payload = {"bound": bound, "errors": errors}
                hashes.append(canon_hash(payload))
                bound_sets.append(bound)
                evidence = errors.get(manifest["storey_global_id"])
                evidences.append(evidence)
                matched.append(bool(evidence) and evidence_matches(evidence, manifest) and manifest["storey_global_id"] not in bound)
                accepted.append(manifest["storey_global_id"] in bound)
        parent = ":".join(label.split(":")[:2])
        end_to_end = run_extracts(pilot, paths[label], binder, orders=("original",), repeats=1)[0]
        malformed[label] = {
            "manifest_match": all(matched),
            "accepted_runs": sum(accepted),
            "n_runs": 9,
            "distinct_canonical": sorted(set(hashes)),
            "other_storeys_bound": bound_sets[0],
            "evidence": scrub(evidences[0]),
            "median_s": pilot.median(samples),
            "extract": {"status": end_to_end["status"], "error": scrub(end_to_end["error"])},
        }
    after = input_hashes()
    clean_labels = [label for label in paths if label.count(":") == 1]
    renamed = [label for label in baseline if label.split(":")[-1] in RENAME]
    originals_ok = sum(baseline[label]["status"] == "accept" for label in clean_labels)
    renamed_refused = sum(
        baseline[label]["status"] == "refuse" and baseline[label]["message_is_unsupported_wall_mapping"] for label in renamed)
    cand_labels = [label for label in candidate]
    def r2_ok(label):
        row = candidate[label]
        return (row["status"] == "accept" and row["mapping_eq_oracle"] and row["counts_ok"] and row["opening_indices_ok"]
                and row["error_within_1e-5"] and row["k01_ok"] and row["wall_ok"])
    r2_hits = sum(r2_ok(label) for label in cand_labels)
    r3_hits = sum(row["manifest_match"] and row["accepted_runs"] == 0 for row in malformed.values())
    r3_accepted = sum(row["accepted_runs"] for row in malformed.values())
    candidate_hashes = [row["distinct_canonical"] for row in candidate.values()] + [row["distinct_canonical"] for row in malformed.values()]
    baseline_hashes = [row["distinct_canonical"] for row in baseline.values()]
    r1 = originals_ok == 6 and renamed_refused == 18 and len(clean_labels) == 6 and len(renamed) == 18
    r2 = r2_hits == 24 and len(cand_labels) == 24
    r3 = r3_hits == 12 and len(malformed) == 12 and r3_accepted == 0
    r4 = (len(candidate_hashes) == 36 and all(len(item) == 1 for item in candidate_hashes)
          and len(baseline_hashes) == 36 and all(len(item) == 1 for item in baseline_hashes))
    status = "CONFIRMED" if r1 and r2 and r3 and r4 else "REJECTED"
    verdict = {
        "status": status, "R1": r1, "R2": r2, "R3": r3, "R4": r4,
        "counts": {
            "R1_baseline_accept_original": f"{originals_ok}/6",
            "R1_baseline_refuse_renamed": f"{renamed_refused}/18",
            "R2_candidate": f"{r2_hits}/24",
            "R3_refused_matching": f"{r3_hits}/12",
            "R3_accepted_runs": r3_accepted,
            "R4_candidate_files": f"{sum(len(item) == 1 for item in candidate_hashes)}/{len(candidate_hashes)}",
            "R4_baseline_files": f"{sum(len(item) == 1 for item in baseline_hashes)}/{len(baseline_hashes)}",
        },
    }
    results = {
        "synthetic": True, "delivery_passed": False,
        "versions": {"python": sys.version.split()[0], "ifcopenshell": pilot.ifc_version_text(), "numpy": np.__version__},
        "input_hashes": {"before": before, "after": after},
        "file_sha256": file_hashes,
        "oracle": oracle,
        "injection_manifests": manifests,
        "clean_extraction": {label: spec.model_dump(mode="json") for label, spec in clean.items()},
        "baseline": baseline, "candidate": candidate, "malformed": malformed,
        "verdict": verdict,
    }
    dest = ROOT / "experiments" / "hyp-107" / "results.json"
    dest.write_text(json.dumps(scrub(results), indent=2), encoding="utf-8")
    print(json.dumps(verdict))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        traceback.print_exc()
        fallback = {"synthetic": True, "delivery_passed": False, "verdict": {"status": "INCONCLUSIVE", "error": str(exc)}}
        (ROOT / "experiments" / "hyp-107" / "results.json").write_text(json.dumps(fallback, indent=2), encoding="utf-8")
        print(json.dumps(fallback["verdict"]))
        sys.exit(0)
