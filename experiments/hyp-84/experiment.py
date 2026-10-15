"""Hypothesis 84: WCS transforms of synthetic benchmark plans through ezdxf and AutoCAD.

Written by Cursor (grok-4.7-medium). Isolated experiment. Benchmark fixtures are synthetic.
The oracle reads raw spec JSON; the writer reuses the legacy six-decimal encoder.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics
import subprocess
import sys
import time
from decimal import Decimal, localcontext
from pathlib import Path

TOL_MM = 0.01
ORDER = ("identity", "rotation37", "translation", "rotation37_then_translation")
SHIFT_M = (Decimal(600000), Decimal(7500000), Decimal(150))
EXPECTED = {"entities": 21, "coordinates": 69, "LWPOLYLINE": 6, "POLYLINE": 6, "POINT": 9}
PI = Decimal("3.1415926535897932384626433832795028841971693993751058209749445923078164")
BUSY_WAIT_S = 1.0
BUSY_RETRIES = 3
_TRIG = None


def _legacy():
    path = Path(__file__).resolve().parents[1] / "acad-coreconsole-agr-plans" / "experiment.py"
    spec = importlib.util.spec_from_file_location("hyp84_legacy_acad", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = _legacy()
CENSUS = (
    '(defun agr-vertcount (e / v d n) (setq v (entnext e) n 0) '
    '(while (and v (setq d (entget v)) (/= (cdr (assoc 0 d)) "SEQEND")) '
    '(if (= (cdr (assoc 0 d)) "VERTEX") (setq n (1+ n))) (setq v (entnext v))) n)'
    '\n(defun agr-census (/ e d typ layer flags n) (setq e (entnext)) (while e '
    '(setq d (entget e) typ (cdr (assoc 0 d))) (if (and typ (/= typ "VERTEX") '
    '(/= typ "SEQEND") (/= (cdr (assoc 67 d)) 1)) (progn (setq layer (if (assoc 8 d) '
    '(cdr (assoc 8 d)) "") flags (if (assoc 70 d) (itoa (cdr (assoc 70 d))) "-") n '
    '(cond ((= typ "LWPOLYLINE") (if (assoc 90 d) (cdr (assoc 90 d)) 0)) '
    '((= typ "POLYLINE") (agr-vertcount e)) ((= typ "POINT") 1) (t 0))) '
    '(princ (strcat "\\nAGR_CENSUS|" typ "|" layer "|" flags "|" (itoa n) "\\n")))) '
    '(setq e (entnext e))))'
)
legacy.HELPERS = legacy.HELPERS + "\n" + CENSUS


def reader_script():
    body, _ = legacy.read_forms()
    needle = '(princ "\\nAGR_READ_DONE\\n")'
    if needle not in body or "(agr-census)" in body:
        raise RuntimeError("legacy read form is not the expected marker script")
    return body.replace(needle, "(agr-census)\n" + needle, 1)


def _d(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def trig37():
    global _TRIG
    if _TRIG is None:
        with localcontext() as ctx:
            ctx.prec = 50
            angle = Decimal(37) * PI / Decimal(180)
            _TRIG = (_series(angle, True), _series(angle, False))
    return _TRIG


def _series(angle, cosine):
    with localcontext() as ctx:
        ctx.prec = 50
        term = Decimal(1) if cosine else angle
        total = term
        k = 0 if cosine else 1
        for _ in range(80):
            term = -term * angle * angle / (Decimal(k + 1) * Decimal(k + 2))
            k += 2
            total += term
        return total


def transform_metres(x, y, z, name):
    rotate = name in ("rotation37", "rotation37_then_translation")
    shift = name in ("translation", "rotation37_then_translation")
    with localcontext() as ctx:
        ctx.prec = 50
        x, y, z = _d(x), _d(y), _d(z)
        if rotate:
            cos_a, sin_a = trig37()
            x, y = x * cos_a - y * sin_a, x * sin_a + y * cos_a
        if shift:
            x, y, z = x + SHIFT_M[0], y + SHIFT_M[1], z + SHIFT_M[2]
        return x, y, z


def _mm(x, y, z):
    return [float(x * 1000), float(y * 1000), float(z * 1000)]


def _writer_mm(x, y, z, name):
    rotate = name in ("rotation37", "rotation37_then_translation")
    shift = name in ("translation", "rotation37_then_translation")
    x, y, z = float(x), float(y), float(z)
    if rotate:
        cos_a, sin_a = math.cos(math.radians(37.0)), math.sin(math.radians(37.0))
        x, y = cos_a * x - sin_a * y, sin_a * x + cos_a * y
    if shift:
        x, y, z = x + 600000.0, y + 7500000.0, z + 150.0
    return [round(x * 1000.0, 6), round(y * 1000.0, 6), round(z * 1000.0, 6)]


def expand_floors(raw):
    names = [item["name"] for item in raw["levels"]]
    full = {item["level"]: item for item in raw["floors"] if item.get("contour") is not None}
    floors = []
    for item in raw["floors"]:
        if item.get("contour") is not None:
            floors.append(item)
            continue
        first = names.index(item["level"])
        last = names.index(item.get("repeat_to") or item["level"])
        template = full[item["typical_of"]]
        for index in range(first, last + 1):
            floors.append({"level": names[index], "contour": template["contour"],
                           "openings": template.get("openings") or []})
    return floors


def _ring(contour, level):
    points = []
    for point in contour:
        if len(point) < 2 or isinstance(point[0], dict) or isinstance(point[1], dict):
            raise ValueError(f"floor {level}: contour point must be [x, y] in metres")
        points.append((_d(point[0]), _d(point[1])))
    return points


def _opening(contour, opening, elev):
    wall = int(opening["wall"])
    x0, y0 = contour[wall]
    x1, y1 = contour[(wall + 1) % len(contour)]
    dx, dy = x1 - x0, y1 - y0
    with localcontext() as ctx:
        ctx.prec = 50
        length = (dx * dx + dy * dy).sqrt()
        if length == 0:
            raise ValueError("opening wall has zero length")
        ux, uy = dx / length, dy / length
        start, width = _d(opening["x_m"]), _d(opening["w_m"])
        z0, z1 = elev + _d(opening["sill_m"]), elev + _d(opening["sill_m"]) + _d(opening["h_m"])
        ax, ay = x0 + ux * start, y0 + uy * start
        bx, by = x0 + ux * (start + width), y0 + uy * (start + width)
    return [(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)]


def oracle_features(raws, name):
    features = []
    elev = {}
    for raw in raws:
        prefix = (raw["id"].split("-")[1] if "-" in raw["id"] else raw["id"]).upper()
        elev = {item["name"]: _d(item["elev_m"]) for item in raw["levels"]}
        for floor in expand_floors(raw):
            ring = _ring(floor["contour"], floor["level"])
            z = elev[floor["level"]]
            features.append(_feature(f"{prefix}_{floor['level']}_CONTOUR", "LWPOLYLINE", True,
                                     [(x, y, z) for x, y in ring], "contour", name))
            for index, opening in enumerate(floor.get("openings") or []):
                features.append(_feature(f"{prefix}_{floor['level']}_OPEN_{index}", "POLYLINE", True,
                                         _opening(ring, opening, z), "opening", name))
        for level in raw["levels"]:
            features.append(_feature(f"{prefix}_{level['name']}_LEVEL", "POINT", False,
                                     [(Decimal(0), Decimal(0), elev[level["name"]])], "level", name))
    return features


def _feature(layer, kind, closed, metres, group, name):
    vertices = [_mm(*transform_metres(x, y, z, name)) for x, y, z in metres]
    return {"layer": layer, "kind": kind, "closed": closed, "vertices_mm": vertices, "group": group}


def inventory(features):
    kinds = {}
    for item in features:
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
    layers = [item["layer"] for item in features]
    return {"entities": len(features), "coordinates": sum(len(item["vertices_mm"]) for item in features),
            "LWPOLYLINE": kinds.get("LWPOLYLINE", 0), "POLYLINE": kinds.get("POLYLINE", 0),
            "POINT": kinds.get("POINT", 0), "unique_layers": len(layers) == len(set(layers))}


def inventory_ok(features):
    found = inventory(features)
    return found["unique_layers"] and all(found[key] == value for key, value in EXPECTED.items())


def writer_features(specs, name):
    original = legacy.to_mm
    legacy.to_mm = lambda meters: float(meters)
    try:
        metres = legacy.build_features(specs)
    finally:
        legacy.to_mm = original
    features = []
    for item in metres:
        vertices = [_writer_mm(x, y, z, name) for x, y, z in item["vertices_mm"]]
        features.append({**item, "vertices_mm": vertices})
    return features


def load_inputs(path):
    folders = [item for item in sorted(Path(path).iterdir()) if (item / "spec.json").is_file()]
    if not folders:
        raise FileNotFoundError(f"no spec.json under {path}")
    specs, raws = [], []
    for folder in folders:
        text = (folder / "spec.json").read_text(encoding="utf-8")
        raws.append(json.loads(text, parse_float=Decimal))
        specs.append(legacy.spec_from_mapping(json.loads(text)))
    return specs, raws


def _finite(entities):
    for item in entities or []:
        for vertex in item.get("vertices_mm") or []:
            if len(vertex) < 3 or not all(isinstance(number, (int, float)) and math.isfinite(number)
                                          for number in vertex[:3]):
                return False
    return bool(entities)


def _classes(expected, actual):
    found = {}
    for group in ("contour", "opening", "level"):
        exp = [item for item in expected if item.get("group") == group]
        act = [item for item in actual if _group_name(item["layer"]) == group]
        report = legacy.compare_features(exp, act, 4)
        found[group] = _num(report.get("max_deviation_mm"))
    return found


def _group_name(layer):
    if layer.endswith("_CONTOUR"):
        return "contour"
    if "_OPEN_" in layer:
        return "opening"
    if layer.endswith("_LEVEL"):
        return "level"
    return "other"


def _num(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def _hist(entities):
    kinds = {}
    for item in entities or []:
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
    return {"entities": len(entities or []), "coordinates": sum(len(item["vertices_mm"]) for item in entities or []),
            "kinds": kinds}


def expected_flag(kind):
    return {"LWPOLYLINE": 1, "POLYLINE": 9, "POINT": None}[kind]


def census_matches(features, rows):
    if len(rows) != len(features):
        return False
    found = {}
    for row in rows:
        found[(row["layer"], row["kind"])] = row
    if len(found) != len(rows):
        return False
    for feature in features:
        row = found.get((feature["layer"], feature["kind"]))
        if row is None or row["flags"] != expected_flag(feature["kind"]):
            return False
        if row["raw_vertices"] != len(feature["vertices_mm"]):
            return False
    return True


def parse_census(text):
    rows = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("AGR_CENSUS|"):
            continue
        _, kind, layer, flags, count = stripped.split("|", 4)
        rows.append({"kind": kind, "layer": layer, "flags": None if flags == "-" else int(flags),
                     "raw_vertices": int(count)})
    return rows


def _ezdxf_flags(entity):
    if entity.dxftype() == "POINT" or not entity.dxf.hasattr("flags"):
        return None
    return int(entity.dxf.flags)


def _raw_vertices(entity):
    kind = entity.dxftype()
    if kind == "LWPOLYLINE":
        return len(entity)
    if kind == "POLYLINE":
        return len(list(entity.vertices))
    if kind == "POINT":
        return 1
    return 0


def audit_dxf(path):
    doc = legacy._import_ezdxf().readfile(path)
    space = doc.modelspace()
    rows = [{"kind": entity.dxftype(), "layer": entity.dxf.layer, "flags": _ezdxf_flags(entity),
             "raw_vertices": _raw_vertices(entity)} for entity in space]
    count_before = len(rows)
    auditor = doc.audit()
    errors, fixes = len(auditor.errors), len(auditor.fixes)
    return {"count_before": count_before, "count_after": len(list(doc.modelspace())), "errors": errors,
            "fixes": fixes, "rows": rows, "insunits": int(doc.header.get("$INSUNITS", 0)),
            "ok": errors == 0 and fixes == 0}


def evaluate(oracle, actual, units):
    report = legacy.compare_features(oracle, actual, units)
    errors = list(report["errors"])
    if not _finite(actual) or not _finite(oracle):
        errors.append("nonfinite")
    report = {**report, "ok": not errors, "errors": errors, "max_deviation_mm": _num(report.get("max_deviation_mm"))}
    return {"ok": report["ok"], "compare": report, "classes": _classes(oracle, actual), "actual": _hist(actual),
            "units": units}


def _as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def identity_ok(identity):
    if not isinstance(identity, dict):
        return False
    version = str(identity.get("acadver") or "")
    if not version.startswith("25.0") or identity.get("insunits") != 4:
        return False
    try:
        parts = [float(item) for item in str(identity.get("ucsorg")).split(",")]
    except (TypeError, ValueError):
        return False
    return len(parts) == 3 and all(part == 0.0 for part in parts)


def run_native_call(wrapper, card, script, log_json, dwg=None, expect="read"):
    retries = []
    while True:
        command = [sys.executable, str(wrapper), "acad", "--card", str(card), "--file", str(script),
                   "--out", str(log_json), "--timeout", "60", "--wait", "30", "--max-chars", "1000"]
        if dwg is not None:
            command.extend(["--dwg", str(dwg)])
        started = time.perf_counter()
        timed_out = False
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=120,
                                  encoding="utf-8", errors="replace")
            code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out, code = True, None
        wall = time.perf_counter() - started
        payload, log = _read_log(Path(log_json))
        parsed = legacy.parse_readback(log)
        status = payload.get("status") if isinstance(payload, dict) else None
        wrapper_code = None
        if isinstance(payload, dict):
            wrapper_code = _as_int(payload.get("code", payload.get("exit_code", payload.get("returncode"))))
        busy = code == 3 or wrapper_code == 3
        if busy and len(retries) < BUSY_RETRIES:
            retries.append({"wall_s": wall, "returncode": code, "status": status, "wrapper_code": wrapper_code})
            time.sleep(BUSY_WAIT_S)
            continue
        marker = parsed["write_done"] if expect == "write" else parsed["read_done"]
        call_ok = (code == 0 and status == "ok" and wrapper_code == 0 and not timed_out and not busy
                   and marker and identity_ok(parsed["identity"]))
        return {"called": True, "wall_s": wall, "returncode": code, "status": status,
                "wrapper_code": wrapper_code, "timeout": timed_out, "busy": busy, "retries": retries,
                "call_ok": call_ok, "write_done": parsed["write_done"], "read_done": parsed["read_done"],
                "identity": parsed["identity"], "identity_ok": identity_ok(parsed["identity"]),
                "parsed": parsed, "census": parse_census(log)}


def _read_log(path):
    if not path.is_file():
        return None, ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None, ""
    if not isinstance(payload, dict) or not isinstance(payload.get("log"), str):
        return payload if isinstance(payload, dict) else None, ""
    return payload, payload["log"]


def _file_fact(path):
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "exists": False, "bytes": 0}
    return {"path": str(path), "exists": True, "bytes": path.stat().st_size}


def _offline(written, oracle, path):
    started = time.perf_counter()
    legacy.write_dxf(written, path)
    write_s = time.perf_counter() - started
    started = time.perf_counter()
    try:
        entities, basic = legacy.read_dxf(path, expect_count=len(oracle))
        error = None
    except legacy.ReadbackError as exc:
        entities, basic, error = exc.entities, exc.audit, str(exc)
    read_s = time.perf_counter() - started
    audited = audit_dxf(path)
    verdict = evaluate(oracle, entities, basic.get("insunits"))
    census_ok = census_matches(oracle, audited["rows"])
    ok = (verdict["ok"] and census_ok and audited["ok"] and audited["count_before"] == len(oracle)
          and audited["insunits"] == 4 and error is None)
    return {**verdict, "called": True, "ok": ok, "write_s": write_s, "read_s": read_s,
            "seconds": write_s + read_s, "file": _file_fact(path), "audit": {key: audited[key] for key in
            ("count_before", "count_after", "errors", "fixes", "insunits", "ok")},
            "census_ok": census_ok, "read_error": error}


def _native_read(wrapper, card, script, log_json, drawing, oracle):
    call = run_native_call(wrapper, card, script, log_json, drawing, expect="read")
    entities = call["parsed"]["entities"] if call["parsed"]["read_done"] else []
    units = (call["identity"] or {}).get("insunits")
    verdict = evaluate(oracle, entities, units)
    census_ok = census_matches(oracle, call["census"])
    ok = call["call_ok"] and verdict["ok"] and census_ok and _file_fact(drawing)["bytes"] > 0
    public = {key: call[key] for key in ("called", "wall_s", "returncode", "status", "wrapper_code", "timeout",
                                         "busy", "retries", "call_ok", "write_done", "read_done", "identity",
                                         "identity_ok")}
    return {**public, **verdict, "ok": ok, "census_ok": census_ok, "file": _file_fact(drawing)}


def run_one(name, rep, specs, raws, folder, wrapper, card):
    folder.mkdir(parents=True, exist_ok=True)
    row = {"transform": name, "rep": rep, "ok": False, "exception": None}
    try:
        oracle = oracle_features(raws, name)
        written = writer_features(specs, name)
    except Exception as exc:
        row["exception"] = f"{type(exc).__name__}: {exc}"
        return row
    row["inventory"] = inventory(oracle)
    row["inventory_ok"] = inventory_ok(oracle)
    dwg, dxf = folder / "native.dwg", folder / "native.dxf"
    offline_path = folder / "offline.dxf"
    try:
        script, _ = legacy.write_forms(written, dwg.resolve(), dxf.resolve())
        legacy.write_script(folder / "write.scr", script)
        legacy.write_script(folder / "read.scr", reader_script())
    except Exception as exc:
        row["exception"] = f"{type(exc).__name__}: {exc}"
        return row
    stages = (
        ("offline", lambda: _offline(written, oracle, offline_path)),
        ("native_write", lambda: _native_write(wrapper, card, folder / "write.scr", folder / "write.log.json",
                                              [dwg, dxf])),
        ("read_dwg", lambda: _native_read(wrapper, card, folder / "read.scr", folder / "read-dwg.log.json", dwg, oracle)),
        ("ezdxf_native", lambda: _ezdxf_native(dxf, oracle)),
        ("native_offline_dxf", lambda: _native_read(wrapper, card, folder / "read.scr",
                                                   folder / "read-offline-dxf.log.json", offline_path, oracle)),
        ("native_native_dxf", lambda: _native_read(wrapper, card, folder / "read.scr",
                                                  folder / "read-native-dxf.log.json", dxf, oracle)),
    )
    for key, action in stages:
        try:
            row[key] = action()
        except Exception as exc:
            row[key] = {"called": False, "ok": False, "exception": f"{type(exc).__name__}: {exc}"}
    row["ok"] = row_ok(row)
    return row


def _native_write(wrapper, card, script, log_json, paths):
    call = run_native_call(wrapper, card, script, log_json, expect="write")
    files = [_file_fact(path) for path in paths]
    ok = call["call_ok"] and all(item["bytes"] > 0 for item in files)
    public = {key: call[key] for key in ("called", "wall_s", "returncode", "status", "wrapper_code", "timeout",
                                         "busy", "retries", "call_ok", "write_done", "read_done", "identity",
                                         "identity_ok")}
    return {**public, "ok": ok, "files": files}


def _ezdxf_native(path, oracle):
    started = time.perf_counter()
    try:
        entities, basic = legacy.read_dxf(path, expect_count=len(oracle))
        error = None
    except legacy.ReadbackError as exc:
        entities, basic, error = exc.entities, exc.audit, str(exc)
    read_s = time.perf_counter() - started
    audited = audit_dxf(path)
    verdict = evaluate(oracle, entities, basic.get("insunits"))
    census_ok = census_matches(oracle, audited["rows"])
    ok = (verdict["ok"] and census_ok and audited["ok"] and audited["count_before"] == len(oracle)
          and audited["insunits"] == 4 and error is None and _file_fact(path)["bytes"] > 0)
    return {**verdict, "called": True, "ok": ok, "read_s": read_s, "file": _file_fact(path),
            "census_ok": census_ok, "read_error": error, "audit": {key: audited[key] for key in
            ("count_before", "count_after", "errors", "fixes", "insunits", "ok")}}


def row_ok(row):
    if row.get("exception") or not row.get("inventory_ok"):
        return False
    keys = ("offline", "native_write", "read_dwg", "ezdxf_native", "native_offline_dxf", "native_native_dxf")
    return all(isinstance(row.get(key), dict) and row[key].get("called") and row[key].get("ok") for key in keys)


def _median(values):
    clean = [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]
    if len(clean) < 3:
        return None
    return statistics.median(clean)


def judge(state):
    reasons = []
    rows = state.get("rows") or []
    if state.get("exception"):
        reasons.append("exception")
    if len(rows) != len(ORDER) * state["repeats"]:
        reasons.append("missing row")
    for row in rows:
        if not row.get("ok"):
            reasons.append(f"{row.get('transform')} rep {row.get('rep')} rejected")
        for key in ("offline", "native_write", "read_dwg", "ezdxf_native", "native_offline_dxf", "native_native_dxf"):
            if not (isinstance(row.get(key), dict) and row[key].get("called")):
                reasons.append(f"missing {key}")
    medians = (state.get("aggregate") or {}).get("medians") or {}
    for name in ORDER:
        for key, value in (medians.get(name) or {}).items():
            if value is None:
                reasons.append(f"median {name} {key}")
    if state["repeats"] < 3:
        reasons.append("repeats below 3")
    unique = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    return unique


def aggregate(state):
    medians, maxima, versions = {}, {}, []
    for name in ORDER:
        chosen = [row for row in state.get("rows") or [] if row.get("transform") == name]
        medians[name] = {
            "offline_s": _median([((row.get("offline") or {}).get("seconds")) for row in chosen]),
            "write_wall_s": _median([((row.get("native_write") or {}).get("wall_s")) for row in chosen]),
            "dwg_wall_s": _median([((row.get("read_dwg") or {}).get("wall_s")) for row in chosen]),
            "ezdxf_native_s": _median([((row.get("ezdxf_native") or {}).get("read_s")) for row in chosen]),
            "native_offline_dxf_s": _median([((row.get("native_offline_dxf") or {}).get("wall_s")) for row in chosen]),
            "native_native_dxf_s": _median([((row.get("native_native_dxf") or {}).get("wall_s")) for row in chosen]),
        }
        maxima[name] = {key: [((row.get(key) or {}).get("classes")) for row in chosen]
                        for key in ("offline", "read_dwg", "ezdxf_native", "native_offline_dxf", "native_native_dxf")}
        for row in chosen:
            for key in ("native_write", "read_dwg", "native_offline_dxf", "native_native_dxf"):
                identity = (row.get(key) or {}).get("identity")
                if identity and identity.get("acadver") not in versions:
                    versions.append(identity.get("acadver"))
    return {"medians": medians, "class_max_mm": maxima, "acadver": versions,
            "summary": "Four WCS transforms of synthetic B01/B02/B02t plans, INSUNITS 4, "
                       "five geometry reads per repetition, tolerance 0.01 mm."}


def _persist(path, state):
    path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def run_matrix(specs, raws, output, wrapper, card, repeats, state):
    for name in ORDER:
        for rep in range(1, repeats + 1):
            row = run_one(name, rep, specs, raws, output / name / f"rep-{rep:02d}", wrapper, card)
            state["rows"].append({key: value for key, value in row.items() if key != "parsed"})
            state["aggregate"] = aggregate(state)
            state["reasons"] = judge(state)
            state["verdict"] = "rejected"
            _persist(output / "results.json", state)
            print(json.dumps({"transform": name, "rep": rep, "ok": row["ok"]}, default=str), flush=True)
    state["reasons"] = judge(state)
    state["verdict"] = "accepted" if not state["reasons"] else "rejected"
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hypothesis 84 transformed plan round trip")
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--wrapper", required=True, type=Path)
    parser.add_argument("--card", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args(argv)
    if args.repeats < 1 or not str(args.card).strip():
        print("card and a positive repeat count are required", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"refusing existing output path: {args.output}", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True)
    state = {"hypothesis": 84, "author": "Cursor (grok-4.7-medium)", "verdict": "rejected", "ok": False,
             "card": args.card, "inputs": str(args.inputs), "output": str(args.output),
             "wrapper": str(args.wrapper), "repeats": args.repeats, "insunits": 4, "tolerance_mm": TOL_MM,
             "expected_inventory": EXPECTED, "transforms": list(ORDER), "sequential": True,
             "native_command": {"timeout": "60", "wait": "30", "max_chars": "1000", "log": "payload.log"},
             "rows": [], "reasons": [], "exception": None}
    try:
        specs, raws = load_inputs(args.inputs)
        state["ezdxf_version"] = legacy._import_ezdxf().__version__
        run_matrix(specs, raws, args.output, args.wrapper, args.card, args.repeats, state)
    except Exception as exc:
        state["exception"] = f"{type(exc).__name__}: {exc}"
        state["verdict"] = "rejected"
    finally:
        try:
            state["aggregate"] = aggregate(state)
            state["reasons"] = judge(state)
        except Exception as exc:
            state["exception"] = state.get("exception") or f"{type(exc).__name__}: {exc}"
            state["reasons"] = ["exception"]
        state["verdict"] = "accepted" if not state["reasons"] else "rejected"
        state["ok"] = state["verdict"] == "accepted"
        _persist(args.output / "results.json", state)
    print(json.dumps({"verdict": state["verdict"], "output": str(args.output)}), flush=True)
    return 0 if state["verdict"] == "accepted" else 1


if __name__ == "__main__":
    sys.exit(main())
