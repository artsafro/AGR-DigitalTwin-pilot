"""Throwaway AutoCAD core-console vs ezdxf measurement. Not production code.

etalon.json is metadata and hashes, not mesh geometry. Coordinates come from
spec.json (the extracted etalon proxy) through Spec.expanded_floors. Benchmark
fixtures are synthetic. Openings are wall-plane rectangles with no plan depth.
Roof contours and terrace parapets are not invented.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.spec.model import Spec  # noqa: E402

LIMITATION = (
    "etalon.json is metadata and file hashes, not geometry. "
    "spec.json is the extracted etalon proxy. Benchmark fixtures are synthetic."
)
TOL_MM = 0.01
CARD = "t_3d8b70a4"
# Editable save forms. "saveas" or "qsave".
DWG_SAVE = "saveas"
# "version-2018" keeps the requested _.DXFOUT sequence.
DXF_FORM = "version-2018"


class ReadbackError(Exception):
    def __init__(self, message, entities=None, audit=None):
        super().__init__(message)
        self.entities = entities or []
        self.audit = audit or {}


def to_mm(meters):
    return round(float(meters) * 1000.0, 6)


def bench_prefix(spec_id):
    parts = spec_id.split("-")
    return (parts[1] if len(parts) > 1 else spec_id).upper()


def spec_from_mapping(data):
    body = {k: v for k, v in data.items() if k not in ("synthetic", "note")}
    return Spec.model_validate(body)


def _xy(point, level):
    if len(point) < 2 or isinstance(point[0], dict) or isinstance(point[1], dict):
        raise ValueError(f"floor {level}: contour point must be [x, y] in metres")
    if any(isinstance(part, dict) for part in point):
        raise ValueError(f"floor {level}: rounded corners are not drawn by this prototype")
    return float(point[0]), float(point[1])


def opening_rectangle(contour_xy, opening, elev_m):
    """Closed wall-plane rectangle. No plan depth is invented."""
    x0, y0 = contour_xy[opening.wall]
    x1, y1 = contour_xy[(opening.wall + 1) % len(contour_xy)]
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        raise ValueError(f"opening wall {opening.wall} has zero length")
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    ax = x0 + ux * opening.x_m
    ay = y0 + uy * opening.x_m
    bx = x0 + ux * (opening.x_m + opening.w_m)
    by = y0 + uy * (opening.x_m + opening.w_m)
    z0 = elev_m + opening.sill_m
    z1 = z0 + opening.h_m
    return [[to_mm(ax), to_mm(ay), to_mm(z0)], [to_mm(bx), to_mm(by), to_mm(z0)],
            [to_mm(bx), to_mm(by), to_mm(z1)], [to_mm(ax), to_mm(ay), to_mm(z1)]]


def build_features(specs):
    features = []
    for spec in specs:
        prefix = bench_prefix(spec.id)
        elev = {level.name: level.elev_m for level in spec.levels}
        for floor in spec.expanded_floors():
            z = to_mm(elev[floor.level])
            ring = [[to_mm(x), to_mm(y), z] for x, y in (_xy(p, floor.level) for p in floor.contour)]
            features.append({"layer": f"{prefix}_{floor.level}_CONTOUR", "kind": "LWPOLYLINE",
                             "closed": True, "vertices_mm": ring})
            contour_m = [_xy(p, floor.level) for p in floor.contour]
            for index, opening in enumerate(floor.openings):
                features.append({"layer": f"{prefix}_{floor.level}_OPEN_{index}", "kind": "POLYLINE",
                                 "closed": True, "vertices_mm": opening_rectangle(contour_m, opening, elev[floor.level])})
        for level in spec.levels:
            features.append({"layer": f"{prefix}_{level.name}_LEVEL", "kind": "POINT", "closed": False,
                             "vertices_mm": [[0.0, 0.0, to_mm(level.elev_m)]]})
    layers = [item["layer"] for item in features]
    if len(layers) != len(set(layers)):
        raise ValueError("duplicate feature layer")
    if not features:
        raise ValueError("no features")
    return features


def ring_deviation(expected, actual):
    best = None
    for seq in (actual, list(reversed(actual))):
        for shift in range(len(seq)):
            rotated = seq[shift:] + seq[:shift]
            dev = max(math.dist(a, b) for a, b in zip(expected, rotated))
            best = dev if best is None else min(best, dev)
    return best


def compare_features(expected, actual, units, tol_mm=TOL_MM):
    errors = []
    if units != 4:
        errors.append("wrong units")
    if not actual:
        errors.append("empty readback")
    if len([e["layer"] for e in expected]) != len({e["layer"] for e in expected}):
        errors.append("duplicate expected layer")
    if len([a["layer"] for a in actual]) != len({a["layer"] for a in actual}):
        errors.append("duplicate layer")
    exp_map = {e["layer"]: e for e in expected}
    act_map = {}
    for item in actual:
        act_map.setdefault(item["layer"], item)
    if set(exp_map) - set(act_map):
        errors.append("missing")
    if set(act_map) - set(exp_map):
        errors.append("extra")
    max_dev = None
    matched = 0
    for layer, exp in exp_map.items():
        act = act_map.get(layer)
        if act is None:
            continue
        if act["kind"] != exp["kind"]:
            errors.append("wrong kind")
        if bool(act["closed"]) != bool(exp["closed"]):
            errors.append("wrong closed flag")
        if len(act["vertices_mm"]) != len(exp["vertices_mm"]):
            errors.append("point count")
            continue
        dev = (math.dist(exp["vertices_mm"][0], act["vertices_mm"][0]) if exp["kind"] == "POINT"
               else ring_deviation(exp["vertices_mm"], act["vertices_mm"]))
        matched += 1
        max_dev = dev if max_dev is None else max(max_dev, dev)
        if dev > tol_mm:
            errors.append("coordinate deviation")
    uniq = []
    for error in errors:
        if error not in uniq:
            uniq.append(error)
    return {"ok": not uniq, "errors": uniq, "max_deviation_mm": max_dev, "matched": matched,
            "expected_count": len(expected), "actual_count": len(actual),
            "point_count_expected": sum(len(e["vertices_mm"]) for e in expected),
            "point_count_actual": sum(len(a["vertices_mm"]) for a in actual)}


def _import_ezdxf():
    import ezdxf
    return ezdxf


def _closed(entity):
    for name in ("is_closed", "closed"):
        if hasattr(entity, name):
            value = getattr(entity, name)
            return bool(value() if callable(value) else value)
    return bool(int(entity.dxf.flags) & 1)


def _drop_repeated_close(vertices, closed):
    if closed and len(vertices) > 1 and math.dist(vertices[0], vertices[-1]) <= 1e-4:
        return vertices[:-1]
    return vertices


def _as_wcs(entity, x, y, z):
    extr = (0.0, 0.0, 1.0)
    if entity.dxf.hasattr("extrusion"):
        raw = entity.dxf.extrusion
        extr = (float(raw[0]), float(raw[1]), float(raw[2]))
    if abs(extr[0]) > 1e-9 or abs(extr[1]) > 1e-9 or abs(extr[2] - 1.0) > 1e-9:
        from ezdxf.math import OCS
        point = OCS(extr).to_wcs((x, y, z))
        return [float(point.x), float(point.y), float(point.z)]
    return [float(x), float(y), float(z)]


def write_dxf(features, path, ezdxf_mod=None):
    ezdxf_mod = ezdxf_mod or _import_ezdxf()
    doc = ezdxf_mod.new("R2018")
    doc.header["$INSUNITS"] = 4
    model = doc.modelspace()
    for feature in features:
        if feature["layer"] not in doc.layers:
            doc.layers.add(feature["layer"])
        attribs = {"layer": feature["layer"]}
        if feature["kind"] == "LWPOLYLINE":
            model.add_lwpolyline([(v[0], v[1]) for v in feature["vertices_mm"]], close=True,
                                 dxfattribs={**attribs, "elevation": feature["vertices_mm"][0][2]})
        elif feature["kind"] == "POLYLINE":
            model.add_polyline3d(feature["vertices_mm"], close=True, dxfattribs=attribs)
        elif feature["kind"] == "POINT":
            model.add_point(feature["vertices_mm"][0], dxfattribs=attribs)
        else:
            raise ValueError(feature["kind"])
    doc.saveas(path)


def read_dxf(path, ezdxf_mod=None, expect_count=None):
    ezdxf_mod = ezdxf_mod or _import_ezdxf()
    doc = ezdxf_mod.readfile(path)
    units = int(doc.header.get("$INSUNITS", 0))
    entities = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == "LWPOLYLINE":
            z = float(entity.dxf.elevation)
            closed = _closed(entity)
            verts = _drop_repeated_close([_as_wcs(entity, p[0], p[1], z) for p in entity.get_points("xy")], closed)
        elif kind == "POLYLINE":
            closed = _closed(entity)
            verts = _drop_repeated_close(
                [_as_wcs(entity, v.dxf.location.x, v.dxf.location.y, v.dxf.location.z) for v in entity.vertices], closed)
        elif kind == "POINT":
            loc = entity.dxf.location
            verts = [_as_wcs(entity, loc.x, loc.y, loc.z)]
            closed = False
        else:
            continue
        entities.append({"layer": entity.dxf.layer, "kind": kind, "closed": closed, "vertices_mm": verts})
    counts = {}
    for item in entities:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    audit = {"insunits": units, "counts": counts, "entities": len(entities), "bytes": Path(path).stat().st_size}
    if units != 4:
        raise ReadbackError(f"INSUNITS {units}", entities, audit)
    if not entities:
        raise ReadbackError("empty readback", entities, audit)
    if expect_count is not None and len(entities) != expect_count:
        raise ReadbackError(f"count {len(entities)} != {expect_count}", entities, audit)
    return entities, audit


def _lf(value):
    return f"{float(value):.6f}"


def _lisp(text):
    return '"' + str(text).replace("\\", "/").replace('"', "") + '"'


def _save_form(dwg, dxf):
    dwg_l, dxf_l = _lisp(dwg), _lisp(dxf)
    save = (f'(command "_.QSAVE" {dwg_l})' if DWG_SAVE == "qsave"
            else f'(command "_.SAVEAS" "_2018" {dwg_l})')
    export = f'(command "_.DXFOUT" {dxf_l} "_Version" "_2018" "16")'
    if DXF_FORM != "version-2018":
        raise ValueError("edit DXF_FORM only to a documented AutoCAD sequence")
    return save, export


def _feature_lisp(feature):
    layer = feature["layer"]
    lines = [f'(entmake (list \'(0 . "LAYER") \'(100 . "AcDbSymbolTableRecord") '
             f'\'(100 . "AcDbLayerTableRecord") (cons 2 "{layer}") \'(70 . 0) \'(62 . 7)))']
    if feature["kind"] == "LWPOLYLINE":
        pts = " ".join(f"(list 10 {_lf(v[0])} {_lf(v[1])})" for v in feature["vertices_mm"])
        lines.append(
            f'(entmake (list \'(0 . "LWPOLYLINE") \'(100 . "AcDbEntity") (cons 8 "{layer}") '
            f'\'(100 . "AcDbPolyline") (cons 90 {len(feature["vertices_mm"])}) \'(70 . 1) '
            f'(cons 38 {_lf(feature["vertices_mm"][0][2])}) {pts}))')
    elif feature["kind"] == "POLYLINE":
        lines.append(
            f'(entmake (list \'(0 . "POLYLINE") \'(100 . "AcDbEntity") (cons 8 "{layer}") '
            f'\'(100 . "AcDb3dPolyline") \'(66 . 1) \'(70 . 9)))')
        for vertex in feature["vertices_mm"]:
            lines.append(
                f'(entmake (list \'(0 . "VERTEX") \'(100 . "AcDbEntity") (cons 8 "{layer}") '
                f'\'(100 . "AcDbVertex") \'(100 . "AcDb3dPolylineVertex") '
                f'(list 10 {_lf(vertex[0])} {_lf(vertex[1])} {_lf(vertex[2])}) \'(70 . 32)))')
        lines.append(f'(entmake (list \'(0 . "SEQEND") \'(100 . "AcDbEntity") (cons 8 "{layer}")))')
    elif feature["kind"] == "POINT":
        x, y, z = feature["vertices_mm"][0]
        lines.append(
            f'(entmake (list \'(0 . "POINT") \'(100 . "AcDbEntity") (cons 8 "{layer}") '
            f'\'(100 . "AcDbPoint") (list 10 {_lf(x)} {_lf(y)} {_lf(z)})))')
    return "\n".join(lines)


HELPERS = "\n".join([
    '(defun agr-dot (s / i c o) (setq i 1 o "") (repeat (strlen s) (setq c (substr s i 1) o (strcat o (if (= c ",") "." c)) i (1+ i))) o)',
    '(defun agr-pt (p) (strcat (agr-dot (rtos (car p) 2 12)) "," (agr-dot (rtos (cadr p) 2 12)) "," (agr-dot (rtos (if (caddr p) (caddr p) 0.0) 2 12))))',
    '(defun agr-join (pts / s) (setq s "") (foreach p pts (setq s (if (= s "") (agr-pt p) (strcat s ";" (agr-pt p))))) s)',
    '(defun agr-lwpts (data elev / pts) (setq pts nil) (foreach item data (if (= (car item) 10) (setq pts (append pts (list (list (cadr item) (caddr item) elev)))))) pts)',
    '(defun agr-polypts (e / v d pts) (setq v (entnext e) pts nil) (while (and v (setq d (entget v)) (/= (cdr (assoc 0 d)) "SEQEND")) (if (= (cdr (assoc 0 d)) "VERTEX") (setq pts (append pts (list (cdr (assoc 10 d)))))) (setq v (entnext v))) pts)',
    '(defun agr-emit (e / d typ layer closed elev pts) (setq d (entget e) typ (cdr (assoc 0 d)) layer (cdr (assoc 8 d)) closed 0 pts nil) (cond ((= typ "LWPOLYLINE") (setq elev (if (assoc 38 d) (cdr (assoc 38 d)) 0.0) closed (if (= (logand (cdr (assoc 70 d)) 1) 1) 1 0) pts (agr-lwpts d elev))) ((= typ "POLYLINE") (setq closed (if (= (logand (if (assoc 70 d) (cdr (assoc 70 d)) 0) 1) 1) 1 0) pts (agr-polypts e))) ((= typ "POINT") (setq pts (list (cdr (assoc 10 d))) closed 0))) (if pts (princ (strcat "\\nAGR_ENTITY|" layer "|" typ "|" (itoa closed) "|" (agr-join pts) "\\n"))))',
    '(defun agr-walk (/ ss i) (setq ss (ssget "_X" \'((0 . "LWPOLYLINE,POLYLINE,POINT")))) (if ss (progn (setq i 0) (repeat (sslength ss) (agr-emit (ssname ss i)) (setq i (1+ i))))))',
])
IDENTITY = '(princ (strcat "\\nAGR_IDENTITY|" (getvar "ACADVER") "|" (getvar "DWGNAME") "|" (itoa (fix (getvar "INSUNITS"))) "|" (agr-dot (rtos (car (getvar "UCSORG")) 2 12)) "," (agr-dot (rtos (cadr (getvar "UCSORG")) 2 12)) "," (agr-dot (rtos (caddr (getvar "UCSORG")) 2 12)) "\\n"))'


def write_script(path, text):
    body = text.rstrip("\n") + "\n"
    path.write_bytes(body.replace("\n", "\r\n").encode("utf-8"))


def write_forms(features, dwg, dxf):
    save, export = _save_form(dwg, dxf)
    body = "\n".join([
        '(setvar "FILEDIA" 0)', '(setvar "CMDECHO" 0)', '(setvar "INSUNITS" 4)',
        HELPERS, IDENTITY, *[_feature_lisp(feature) for feature in features],
        save, export, '(princ "\\nAGR_WRITE_DONE\\n")', "(princ)",
    ])
    return body, body


def read_forms():
    body = "\n".join(['(setvar "FILEDIA" 0)', '(setvar "CMDECHO" 0)', HELPERS, IDENTITY,
                      "(agr-walk)", '(princ "\\nAGR_READ_DONE\\n")', "(princ)"])
    return body, body


def parse_readback(text):
    entities, identity = [], None
    read_done = write_done = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("AGR_ENTITY|"):
            _, layer, kind, closed, coords = stripped.split("|", 4)
            verts = []
            if coords.strip():
                verts = [[float(part) for part in item.split(",")] for item in coords.split(";") if item]
            closed_flag = closed == "1"
            entities.append({"layer": layer, "kind": kind, "closed": closed_flag,
                             "vertices_mm": _drop_repeated_close(verts, closed_flag)})
        elif stripped.startswith("AGR_READ_DONE"):
            read_done = True
        elif stripped.startswith("AGR_WRITE_DONE"):
            write_done = True
        elif stripped.startswith("AGR_IDENTITY|") and identity is None:
            parts = stripped.split("|")
            identity = {"acadver": parts[1], "dwgname": parts[2], "insunits": int(float(parts[3])), "ucsorg": parts[4]}
    return {"entities": entities, "read_done": read_done, "write_done": write_done, "identity": identity}


def _walk_seconds(node, depth=0):
    if depth > 3 or not isinstance(node, dict):
        return None
    keys = {"seconds", "elapsed_s", "elapsed", "duration_s", "duration", "wrapper_seconds"}
    for key, value in node.items():
        if key.lower() in keys and isinstance(value, (int, float)) and not isinstance(value, bool):
            return round(float(value), 1)
    for value in node.values():
        if isinstance(value, dict):
            found = _walk_seconds(value, depth + 1)
            if found is not None:
                return found
    return None


def _payload_text(payload, proc_out, proc_err):
    chunks = [proc_out or "", proc_err or ""]
    if isinstance(payload, dict):
        for key in ("stdout", "stderr", "log", "output", "text", "console", "message"):
            value = payload.get(key)
            if isinstance(value, str):
                chunks.append(value)
        for key in ("log_file", "log_path", "stdout_path"):
            value = payload.get(key)
            if isinstance(value, str) and Path(value).is_file():
                chunks.append(Path(value).read_text(encoding="utf-8", errors="replace"))
    elif isinstance(payload, str):
        chunks.append(payload)
    return "\n".join(chunks)


def file_fact(path):
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "exists": False, "bytes": 0}
    return {"path": str(path), "exists": True, "bytes": path.stat().st_size}


def run_acad(wrapper, script, log_json, dwg=None):
    cmd = [sys.executable, str(wrapper), "acad", "--card", CARD, "--file", str(script),
           "--out", str(log_json), "--timeout", "60", "--wait", "30", "--max-chars", "2000"]
    if dwg is not None:
        cmd.extend(["--dwg", str(dwg)])
    started = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        code = None
    wall = time.perf_counter() - started
    payload = None
    if Path(log_json).is_file():
        raw = Path(log_json).read_text(encoding="utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
    text = _payload_text(payload, stdout if isinstance(stdout, str) else "", stderr if isinstance(stderr, str) else "")
    parsed = parse_readback(text)
    status = payload.get("status") if isinstance(payload, dict) else None
    wrapper_code = None
    if isinstance(payload, dict):
        wrapper_code = payload.get("code", payload.get("exit_code", payload.get("returncode")))
    if status == "timeout" or wrapper_code == 5 or code == 5:
        timed_out = True
    call_ok = code == 0 and status == "ok" and wrapper_code == 0 and not timed_out
    return {"wall_s": wall, "wrapper_s": _walk_seconds(payload) if isinstance(payload, dict) else None,
            "returncode": code, "status": status, "wrapper_code": wrapper_code, "timeout": timed_out,
            "call_ok": call_ok, "parsed": parsed, "text": text}


def _clip(text, limit=2000):
    text = text or ""
    return {"text": text[:limit], "truncated": len(text) > limit}


def classify_probe(parsed, text, missing_file):
    detected = []
    lowered = (text or "").lower()
    if missing_file or any(token in lowered for token in ("no such file", "cannot find", "filenotfound", "does not exist", "not found")):
        detected.append("missing file")
    if any(token in lowered for token in ("error:", "; error", "unknown command", "bad argument", "bad function", "no function definition")):
        detected.append("error log")
    if not (parsed["read_done"] or parsed["write_done"]):
        detected.append("marker missing")
    return detected


def load_inputs(path):
    path = Path(path)
    folders = [item for item in sorted(path.iterdir()) if (item / "spec.json").is_file()] if path.is_dir() else []
    if not folders:
        raise FileNotFoundError(f"no spec.json under {path}")
    specs, notes = [], []
    for folder in folders:
        specs.append(Spec.model_validate_json((folder / "spec.json").read_text(encoding="utf-8")))
        etalon = folder / "etalon.json"
        if etalon.is_file():
            data = json.loads(etalon.read_text(encoding="utf-8"))
            notes.append({"benchmark": folder.name, "top_level_keys": sorted(data.keys()),
                          "contains_vertices": "vertices" in data, "geometry": False})
        else:
            notes.append({"benchmark": folder.name, "missing_etalon": True, "geometry": False})
    return specs, notes


def _counts(features):
    counts = {}
    for feature in features:
        counts[feature["kind"]] = counts.get(feature["kind"], 0) + 1
    return {"features": len(features), **counts}


def run_offline(features, out, repeats, ezdxf_mod):
    reps, raw = [], []
    for index in range(1, repeats + 1):
        folder = out / f"rep-{index:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "offline.dxf"
        try:
            started = time.perf_counter()
            write_dxf(features, path, ezdxf_mod)
            entities, audit = read_dxf(path, ezdxf_mod, expect_count=len(features))
            elapsed = time.perf_counter() - started
            report = compare_features(features, entities, audit["insunits"])
            error = None
        except ReadbackError as exc:
            elapsed = time.perf_counter() - started
            audit, entities = exc.audit, exc.entities
            report = compare_features(features, entities, audit.get("insunits"))
            error = str(exc)
        raw.append(elapsed)
        reps.append({"rep": index, "seconds": elapsed, "audit": audit, "compare": report, "error": error,
                     "file": file_fact(path)})
    return {"seconds_raw": raw, "seconds_median": statistics.median(raw), "repetitions": reps}


def _call_record(call, file_paths):
    parsed = call["parsed"]
    return {"wall_s": call["wall_s"], "wrapper_s": call["wrapper_s"], "returncode": call["returncode"],
            "status": call["status"], "wrapper_code": call["wrapper_code"], "timeout": call["timeout"],
            "call_ok": call["call_ok"], "write_done": parsed["write_done"], "read_done": parsed["read_done"],
            "identity": parsed["identity"], "entity_count": len(parsed["entities"]),
            "files": [file_fact(path) for path in file_paths]}


def _attach_read(call, features, file_paths):
    record = _call_record(call, file_paths)
    if call["call_ok"] and call["parsed"]["read_done"]:
        units = (call["parsed"]["identity"] or {}).get("insunits")
        record["compare"] = compare_features(features, call["parsed"]["entities"], units)
    elif call["call_ok"]:
        record["documented_open_failure"] = True
    return record


def run_native(features, out, repeats, wrapper):
    repetitions, aborted = [], None
    for index in range(1, repeats + 1):
        if aborted:
            break
        folder = out / f"rep-{index:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        dwg, dxf = folder / "native.dwg", folder / "native.dxf"
        offline = folder / "offline.dxf"
        script, lisp = write_forms(features, dwg.resolve(), dxf.resolve())
        write_script(folder / "write.lsp", lisp)
        write_script(folder / "write.scr", script)
        read_script, read_lisp = read_forms()
        write_script(folder / "read.lsp", read_lisp)
        write_script(folder / "read.scr", read_script)
        write_call = run_acad(wrapper, folder / "write.scr", folder / "write.log.json")
        row = {"rep": index, "write": _call_record(write_call, [dwg, dxf])}
        files_ok = row["write"]["files"][0]["bytes"] > 0 and row["write"]["files"][1]["bytes"] > 0
        if not write_call["call_ok"] or not write_call["parsed"]["write_done"] or not files_ok:
            row["write_failed"] = True
            aborted = "timeout on native write" if write_call["timeout"] else "native write failed"
            repetitions.append(row)
            break
        read_call = run_acad(wrapper, folder / "read.scr", folder / "read-dwg.log.json", dwg.resolve())
        row["read_dwg"] = _call_record(read_call, [dwg])
        units = (read_call["parsed"]["identity"] or {}).get("insunits")
        read_entities = read_call["parsed"]["entities"] if read_call["parsed"]["read_done"] else []
        row["read_dwg"]["compare"] = compare_features(features, read_entities, units)
        if not read_call["call_ok"]:
            aborted = "timeout on native dwg read" if read_call["timeout"] else "native dwg read failed"
            repetitions.append(row)
            break
        try:
            entities, audit = read_dxf(dxf, expect_count=len(features))
            row["ezdxf_on_native_dxf"] = {"audit": audit, "compare": compare_features(features, entities, audit["insunits"])}
        except (ReadbackError, OSError) as exc:
            entities = getattr(exc, "entities", [])
            audit = getattr(exc, "audit", {})
            row["ezdxf_on_native_dxf"] = {"error": str(exc), "audit": audit,
                                         "compare": compare_features(features, entities, audit.get("insunits"))}
        if offline.is_file():
            cross = run_acad(wrapper, folder / "read.scr", folder / "read-ezdxf-dxf.log.json", offline.resolve())
            row["native_on_ezdxf_dxf"] = _attach_read(cross, features, [offline])
            if not cross["call_ok"]:
                aborted = "timeout on native ezdxf-dxf read" if cross["timeout"] else "native ezdxf-dxf read failed"
        if aborted:
            repetitions.append(row)
            break
        own = run_acad(wrapper, folder / "read.scr", folder / "read-native-dxf.log.json", dxf.resolve())
        row["native_on_native_dxf"] = _attach_read(own, features, [dxf])
        if not own["call_ok"]:
            aborted = "timeout on native dxf read" if own["timeout"] else "native dxf read failed"
        repetitions.append(row)
        if aborted:
            break
    return {"repetitions": repetitions, "aborted": aborted}


def _probe_call(wrapper, folder, name, script_text, dwg):
    write_script(folder / f"{name}.lsp", script_text)
    write_script(folder / f"{name}.scr", script_text if script_text.startswith("(") else script_text)
    call = run_acad(wrapper, folder / f"{name}.scr", folder / f"{name}.log.json", dwg)
    missing = dwg is not None and not Path(dwg).is_file()
    detected = classify_probe(call["parsed"], call["text"], missing)
    if call["timeout"] and "error log" not in detected:
        detected.append("error log")
    return {"name": name, "detected": detected, "returncode": call["returncode"], "status": call["status"],
            "timeout": call["timeout"], "raw": _clip(call["text"])}


def run_probes(out, wrapper, offline_only, skip_acad=False):
    folder = out / "probes"
    folder.mkdir(parents=True, exist_ok=True)
    probes = []
    if skip_acad:
        probes.append({"name": "acad-probes", "skipped": True, "reason": "prior timeout"})
    elif not offline_only:
        probes.append(_probe_call(wrapper, folder, "undefined-function", "(agr-deliberate-undefined-function)\n", None))
        read_script, _ = read_forms()
        probes.append(_probe_call(wrapper, folder, "missing-dwg", read_script, folder / "missing.dwg"))
    missing = folder / "missing.dxf"
    try:
        _import_ezdxf().readfile(missing)
        probes.append({"name": "ezdxf-missing", "detected": [], "raw": {"text": "readfile returned", "truncated": False}})
    except Exception as exc:
        text = f"{type(exc).__name__}: {exc}"
        detected = ["missing file"]
        if "error" in text.lower():
            detected.append("error log")
        probes.append({"name": "ezdxf-missing", "detected": detected, "raw": {"text": text, "truncated": False}})
    return probes


def _geometry_ok(node):
    compare = node.get("compare") if isinstance(node, dict) else None
    return isinstance(compare, dict) and bool(compare.get("ok"))


def _call_succeeded(node, done_key):
    return (isinstance(node, dict) and node.get("call_ok") is True and bool(node.get(done_key))
            and not node.get("documented_open_failure"))


def results_ok(offline, native, probes, offline_only, repeats):
    reps = offline.get("repetitions") or []
    if len(reps) != repeats:
        return False
    if any(not rep["compare"]["ok"] or rep["error"] for rep in reps):
        return False
    if offline_only:
        return all(probe.get("detected") or probe.get("skipped") for probe in probes)
    if native.get("aborted") or len(native.get("repetitions") or []) != repeats:
        return False
    for rep in native["repetitions"]:
        write = rep.get("write")
        if rep.get("write_failed") or not _call_succeeded(write, "write_done"):
            return False
        files = write.get("files") or []
        if len(files) < 2 or files[0]["bytes"] <= 0 or files[1]["bytes"] <= 0:
            return False
        for key in ("read_dwg", "native_on_ezdxf_dxf", "native_on_native_dxf"):
            item = rep.get(key)
            if not _call_succeeded(item, "read_done") or not _geometry_ok(item):
                return False
        if not _geometry_ok(rep.get("ezdxf_on_native_dxf")):
            return False
    return all(probe.get("detected") or probe.get("skipped") for probe in probes)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure AutoCAD core console against ezdxf on benchmark specs")
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--wrapper", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--offline-only", action="store_true")
    args = parser.parse_args(argv)
    if args.repeats < 1:
        print("repeats must be >= 1", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"refusing existing output directory: {args.output}", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True)
    specs, notes = load_inputs(args.inputs)
    features = build_features(specs)
    expected = {"synthetic": True, "limitation": LIMITATION, "etalon_geometry": False, "insunits": 4,
                "units": "mm", "wcs": True, "expected_counts": _counts(features), "features": features}
    (args.output / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    ezdxf_mod = _import_ezdxf()
    offline = run_offline(features, args.output, args.repeats, ezdxf_mod)
    native = {"repetitions": [], "aborted": None, "skipped": bool(args.offline_only)}
    if not args.offline_only:
        native = run_native(features, args.output, args.repeats, args.wrapper)
    probes = run_probes(args.output, args.wrapper, args.offline_only, skip_acad=bool(native.get("aborted")))
    ok = results_ok(offline, native, probes, args.offline_only, args.repeats)
    results = {"ok": ok, "synthetic": True, "limitation": LIMITATION, "etalon_notes": notes,
               "inputs": str(args.inputs), "output": str(args.output), "repeats": args.repeats,
               "offline_only": bool(args.offline_only), "expected_counts": expected["expected_counts"],
               "offline": offline, "native": native, "probes": probes}
    (args.output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"ok": ok, "expected_counts": expected["expected_counts"], "output": str(args.output)}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
