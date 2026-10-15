"""Offline check of hypothesis 100. Fixtures and oracle are synthetic."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import decoder  # noqa: E402

DRAWINGS = ("default", "neg_z", "tilted")
LAYERS = ("P_POINT", "P_3D", "P_LW")
NORMALS = {
    "default": (0.0, 0.0, 1.0),
    "neg_z": (0.0, 0.0, -1.0),
    "tilted": (0.0, 0.6, 0.8),
}
POINT_WCS = (123.0, 456.0, 789.0)
POLY3D_WCS = (
    (100.0, 200.0, 300.0),
    (1100.0, 200.0, 300.0),
    (1100.0, 200.0, 1300.0),
    (100.0, 200.0, 1300.0),
)
LW_XY = (
    (100.0, 200.0),
    (1100.0, 200.0),
    (1100.0, 700.0),
    (100.0, 700.0),
)
LW_ELEVATION = 300.0
# Hard-coded OCS bases. Not computed from a normal, and not taken from ezdxf.
OCS_BASES = {
    "default": {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "N": (0.0, 0.0, 1.0)},
    "neg_z": {"X": (-1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "N": (0.0, 0.0, -1.0)},
    "tilted": {"X": (-1.0, 0.0, 0.0), "Y": (0.0, -0.8, 0.6), "N": (0.0, 0.6, 0.8)},
}
EXPECTED = {
    "P_POINT": {"kind": "POINT", "closed": False, "vertex_count": 1},
    "P_3D": {"kind": "POLYLINE", "closed": True, "vertex_count": 4},
    "P_LW": {"kind": "LWPOLYLINE", "closed": True, "vertex_count": 4},
}
SOURCE_PATHS = (
    "experiments/bim-autocad-agr/experiment.py",
    "experiments/acad-coreconsole-agr-plans/experiment.py",
    "experiments/hyp-100/decoder.py",
    "experiments/hyp-100/driver.py",
)
ERR_MM = 0.01
EQ_TOL = 1e-9
EXTRUSION_TOL = 1e-9
RAW_TYPES = {"POINT", "POLYLINE", "LWPOLYLINE"}

baseline_read = decoder.bim.strict_read


def _xyz(value):
    return [float(value[0]), float(value[1]), float(value[2])]


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def _struct_sha256(obj):
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(blob.encode("utf-8"))


def lw_oracle(drawing):
    """x*X + y*Y + 300*N with the hard-coded bases for this drawing."""
    axes = OCS_BASES[drawing]
    x_axis, y_axis, normal = axes["X"], axes["Y"], axes["N"]
    points = []
    for x, y in LW_XY:
        points.append([
            x * x_axis[0] + y * y_axis[0] + LW_ELEVATION * normal[0],
            x * x_axis[1] + y * y_axis[1] + LW_ELEVATION * normal[1],
            x * x_axis[2] + y * y_axis[2] + LW_ELEVATION * normal[2],
        ])
    return points


def oracle_for(drawing):
    return {
        "P_POINT": [_xyz(POINT_WCS)],
        "P_3D": [_xyz(point) for point in POLY3D_WCS],
        "P_LW": lw_oracle(drawing),
    }


def _source_hashes():
    return {rel: _sha256_file(ROOT / rel) for rel in SOURCE_PATHS}


def _write_drawing(ezdxf_mod, drawing, path):
    normal = NORMALS[drawing]
    doc = ezdxf_mod.new("R2018")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_point(POINT_WCS, dxfattribs={"layer": "P_POINT", "extrusion": normal})
    msp.add_polyline3d(
        POLY3D_WCS,
        close=True,
        dxfattribs={"layer": "P_3D", "extrusion": normal},
    )
    msp.add_lwpolyline(
        LW_XY,
        format="xy",
        close=True,
        dxfattribs={"layer": "P_LW", "elevation": LW_ELEVATION, "extrusion": normal},
    )
    doc.saveas(path)


def _native_entity(entity):
    raw = entity.dxf.extrusion
    item = {
        "dxftype": entity.dxftype(),
        "layer": str(entity.dxf.layer),
        "handle": str(entity.dxf.handle),
        "extrusion": [float(raw[0]), float(raw[1]), float(raw[2])],
        "has_extrusion": bool(entity.dxf.hasattr("extrusion")),
    }
    kind = entity.dxftype()
    if kind == "POLYLINE":
        item["flags"] = int(entity.dxf.flags)
        item["is_3d_polyline"] = bool(entity.is_3d_polyline)
    elif kind == "LWPOLYLINE":
        item["flags"] = int(entity.dxf.flags)
        item["elevation"] = float(entity.dxf.elevation)
        item["closed"] = bool(entity.closed)
        item["points_xyseb"] = [[float(value) for value in row] for row in entity.get_points("xyseb")]
    return item


def _raw_group_codes(text):
    lines = text.splitlines()
    if len(lines) % 2 == 1:
        lines = lines[:-1]
    entities = []
    current = None
    for index in range(0, len(lines), 2):
        code = lines[index].strip()
        value = lines[index + 1].strip()
        if code == "0":
            if current is not None:
                entities.append(current)
            current = {"dxftype": value, "codes": {}}
            continue
        if current is None:
            continue
        current["codes"].setdefault(code, []).append(value)
    if current is not None:
        entities.append(current)
    rows = []
    for entity in entities:
        if entity["dxftype"] not in RAW_TYPES:
            continue
        codes = entity["codes"]
        layer_values = codes.get("8") or [""]
        rows.append({
            "dxftype": entity["dxftype"],
            "layer": layer_values[0],
            "210": codes.get("210"),
            "220": codes.get("220"),
            "230": codes.get("230"),
            "70": codes.get("70"),
        })
    return rows


def _near(a, b, tol):
    return abs(float(a) - float(b)) <= tol


def _verts_near(left, right, tol):
    if left == right:
        return True
    if len(left) != len(right):
        return False
    for p, q in zip(left, right):
        if len(p) != len(q):
            return False
        if any(not _near(x, y, tol) for x, y in zip(p, q)):
            return False
    return True


def _score_feature(feature, oracle_vertices):
    vertices = feature["vertices_mm"]
    paired = min(len(vertices), len(oracle_vertices))
    errors = [math.dist(vertices[i], oracle_vertices[i]) for i in range(paired)]
    return {
        "layer": str(feature["layer"]),
        "kind": feature["kind"],
        "closed": bool(feature["closed"]),
        "vertex_count": len(vertices),
        "vertices_mm": vertices,
        "errors_mm": errors,
        "max_error_mm": max(errors) if errors else None,
    }


def _score_read(payload, oracle):
    features = [_score_feature(feature, oracle.get(str(feature["layer"]), [])) for feature in payload["features"]]
    got = {feature["layer"] for feature in features}
    expected = set(LAYERS)
    return {
        "accepted": bool(payload["accepted"]),
        "diagnostics": payload["diagnostics"],
        "insunits": payload["insunits"],
        "feature_count": len(features),
        "missing_layers": [layer for layer in LAYERS if layer not in got],
        "extra_layers": sorted(got - expected),
        "features": features,
    }


def _run_repetition(ezdxf_mod, rep_index):
    scratch = tempfile.mkdtemp(prefix=f"hyp100-rep{rep_index}-")
    try:
        paths = {}
        for drawing in DRAWINGS:
            path = Path(scratch) / f"{drawing}.dxf"
            _write_drawing(ezdxf_mod, drawing, path)
            paths[drawing] = path
        dxf_sha256 = {drawing: _sha256_file(path) for drawing, path in paths.items()}
        drawings = {}
        readers = {"baseline": {}, "candidate": {}}
        for drawing, path in paths.items():
            doc = ezdxf_mod.readfile(path)
            entities = [_native_entity(entity) for entity in doc.modelspace()]
            raw_rows = _raw_group_codes(path.read_text(encoding="utf-8"))
            drawings[drawing] = {"entities": entities, "raw_group_codes": raw_rows}
            oracle = oracle_for(drawing)
            readers["baseline"][drawing] = _score_read(baseline_read(path), oracle)
            readers["candidate"][drawing] = _score_read(decoder.candidate_read(path), oracle)
        return {"rep": rep_index, "dxf_sha256": dxf_sha256, "drawings": drawings, "readers": readers}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _strip_handles(obj):
    if isinstance(obj, dict):
        return {key: _strip_handles(value) for key, value in obj.items() if key != "handle"}
    if isinstance(obj, list):
        return [_strip_handles(value) for value in obj]
    return obj


def _comparable(rep):
    return _strip_handles({
        "drawings": rep["drawings"],
        "readers": rep["readers"],
    })


def _serialization_ok(rep):
    for drawing in DRAWINGS:
        observed = rep["drawings"][drawing]
        entities = observed["entities"]
        by_layer = {entity["layer"]: entity for entity in entities}
        if len(entities) != 3 or set(by_layer) != set(LAYERS):
            return False
        normal = NORMALS[drawing]
        for entity in entities:
            extrusion = entity["extrusion"]
            if len(extrusion) != 3 or any(not _near(extrusion[i], normal[i], EXTRUSION_TOL) for i in range(3)):
                return False
        flags = int(by_layer["P_3D"]["flags"])
        if (flags & 8) == 0 or (flags & 1) == 0:
            return False
        if drawing == "default":
            continue
        for layer in LAYERS:
            rows = [row for row in observed["raw_group_codes"] if row["layer"] == layer]
            if not rows:
                return False
            for row in rows:
                if not row["210"] or not row["220"] or not row["230"]:
                    return False
    return True


def _drawing_expected(result):
    if result["accepted"] is not True or result["diagnostics"] or result["insunits"] != 4:
        return False
    if result["feature_count"] != 3 or result["missing_layers"] or result["extra_layers"]:
        return False
    by_layer = {feature["layer"]: feature for feature in result["features"]}
    if set(by_layer) != set(LAYERS):
        return False
    for layer, spec in EXPECTED.items():
        feature = by_layer[layer]
        if feature["kind"] != spec["kind"] or feature["closed"] is not spec["closed"]:
            return False
        if feature["vertex_count"] != spec["vertex_count"] or len(feature["errors_mm"]) != spec["vertex_count"]:
            return False
        if any(error > ERR_MM for error in feature["errors_mm"]):
            return False
    return True


def _baseline_blind_spot(baseline):
    if not all(baseline[drawing]["accepted"] for drawing in DRAWINGS):
        return False
    for drawing in ("neg_z", "tilted"):
        for feature in baseline[drawing]["features"]:
            if feature["kind"] not in ("POINT", "POLYLINE"):
                continue
            error = feature["max_error_mm"]
            if error is not None and error > ERR_MM:
                return True
    return False


def _candidate_ok(candidate):
    return all(_drawing_expected(candidate[drawing]) for drawing in DRAWINGS)


def _default_unchanged(baseline, candidate):
    left = {feature["layer"]: feature for feature in baseline["default"]["features"]}
    right = {feature["layer"]: feature for feature in candidate["default"]["features"]}
    if set(left) != set(LAYERS) or set(right) != set(LAYERS):
        return False
    for layer in LAYERS:
        a, b = left[layer], right[layer]
        if a["kind"] != b["kind"] or a["closed"] is not b["closed"]:
            return False
        if not _verts_near(a["vertices_mm"], b["vertices_mm"], EQ_TOL):
            return False
    return True


def _summary_table(readers):
    table = {}
    for reader, drawings in readers.items():
        table[reader] = {}
        for drawing, result in drawings.items():
            table[reader][drawing] = {feature["layer"]: feature["max_error_mm"] for feature in result["features"]}
            for layer in LAYERS:
                table[reader][drawing].setdefault(layer, None)
    return table


def _fixtures():
    return {
        "label": "synthetic",
        "dxf_version": "R2018",
        "insunits": 4,
        "normals": {name: _xyz(vector) for name, vector in NORMALS.items()},
        "point_wcs": _xyz(POINT_WCS),
        "polyline3d_wcs": [_xyz(point) for point in POLY3D_WCS],
        "lwpolyline_xy": [[float(x), float(y)] for x, y in LW_XY],
        "lwpolyline_elevation": LW_ELEVATION,
        "lwpolyline_format": "xy",
        "ocs_bases": {
            name: {axis: _xyz(vector) for axis, vector in axes.items()}
            for name, axes in OCS_BASES.items()
        },
        "expected_features": EXPECTED,
    }


def _public_rep(rep, full):
    item = {"rep": rep["rep"], "dxf_sha256": rep["dxf_sha256"]}
    if full:
        item["drawings"] = rep["drawings"]
    else:
        item["observation_sha256"] = _struct_sha256(_strip_handles(rep["drawings"]))
    item["comparable_sha256"] = _struct_sha256(_comparable(rep))
    return item


def _print_summary(table, decisions, hashes_identical, verdict):
    header = f"{'reader':<12}{'drawing':<10}" + "".join(f"{layer:>14}" for layer in LAYERS)
    print(header)
    for reader in ("baseline", "candidate"):
        for drawing in DRAWINGS:
            cells = []
            for layer in LAYERS:
                value = table[reader][drawing].get(layer)
                cells.append(f"{'missing':>14}" if value is None else f"{value:>14.6g}")
            print(f"{reader:<12}{drawing:<10}" + "".join(cells))
    for name in (
        "baseline_blind_spot",
        "candidate_ok",
        "default_unchanged",
        "serialization_ok",
        "reps_agree",
    ):
        print(f"{name}={decisions[name]}")
    print(f"dxf_sha256_identical_across_reps={hashes_identical}")
    print(f"verdict={verdict}")


def _write_results(payload):
    path = HERE / "results.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("wrote experiments/hyp-100/results.json")


def _inconclusive(versions, source_hashes, reason):
    payload = {
        "synthetic": True,
        "delivery_passed": False,
        "versions": versions,
        "source_hashes": source_hashes,
        "fixtures": _fixtures(),
        "oracle": {drawing: oracle_for(drawing) for drawing in DRAWINGS},
        "repetitions": [],
        "dxf_sha256_identical_across_reps": None,
        "rep1_readers": {},
        "summary_table": {},
        "decisions": {
            "baseline_blind_spot": False,
            "candidate_ok": False,
            "default_unchanged": False,
            "serialization_ok": False,
            "reps_agree": False,
        },
        "verdict": "INCONCLUSIVE",
        "inconclusive_reason": reason,
    }
    _write_results(payload)
    print(f"verdict=INCONCLUSIVE")
    print(reason)
    return 0


def main():
    versions = {"ezdxf": None, "python": sys.version}
    source_hashes = _source_hashes()
    try:
        import ezdxf
    except ImportError as exc:
        return _inconclusive(versions, source_hashes, f"missing dependency: {exc}")
    versions["ezdxf"] = ezdxf.__version__
    dependency_error = None
    reps = []
    if ezdxf.__version__ == "1.4.3":
        try:
            reps = [_run_repetition(ezdxf, index) for index in (1, 2, 3)]
        except ImportError as exc:
            dependency_error = f"missing dependency: {exc}"
    if ezdxf.__version__ != "1.4.3" or dependency_error is not None:
        reason = dependency_error or f"ezdxf version {ezdxf.__version__} != 1.4.3"
        return _inconclusive(versions, source_hashes, reason)

    comparables = [_comparable(rep) for rep in reps]
    reps_agree = all(item == comparables[0] for item in comparables[1:])
    hashes_identical = all(rep["dxf_sha256"] == reps[0]["dxf_sha256"] for rep in reps[1:])
    baseline = reps[0]["readers"]["baseline"]
    candidate = reps[0]["readers"]["candidate"]
    decisions = {
        "baseline_blind_spot": _baseline_blind_spot(baseline),
        "candidate_ok": _candidate_ok(candidate),
        "default_unchanged": _default_unchanged(baseline, candidate),
        "serialization_ok": _serialization_ok(reps[0]),
        "reps_agree": reps_agree,
    }
    if all(decisions.values()):
        verdict = "CONFIRMED"
    else:
        verdict = "REJECTED"
    table = _summary_table(reps[0]["readers"])
    payload = {
        "synthetic": True,
        "delivery_passed": False,
        "versions": versions,
        "source_hashes": source_hashes,
        "fixtures": _fixtures(),
        "oracle": {drawing: oracle_for(drawing) for drawing in DRAWINGS},
        "repetitions": [_public_rep(rep, full=(rep["rep"] == 1)) for rep in reps],
        "dxf_sha256_identical_across_reps": hashes_identical,
        "rep1_readers": reps[0]["readers"],
        "summary_table": table,
        "decisions": decisions,
        "verdict": verdict,
    }
    _write_results(payload)
    _print_summary(table, decisions, hashes_identical, verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
