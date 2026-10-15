"""E2 probe for silent CAD feature loss. Not a production reader.

Geometry is the synthetic Spec proxy (spec.json via Spec.expanded_floors), not etalon
mesh. Fail-closed support is straight closed LWPOLYLINE, closed 3D POLYLINE and POINT,
INSUNITS 4, unique layers. No self-intersection test and no semantic hole inference.
INSERT/XREF are rejected, not normalized. Xref flags and path are read and written
only on BLOCK (block.block.dxf). missing_xref is the synthetic known-missing path;
any other xref is unresolved_xref. Both mean unresolved: the path is never opened
or expanded. An empty model space, a missing block, a block cycle and a nest at
the depth limit each emit a diagnostic. The AutoLISP census is a top-level
model-space inventory reference, not a feature extractor. Native census text is
payload["log"] parsed once; stderr is scanned on its own and stdout is not combined.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASELINE_PATH = HERE.parent / "acad-coreconsole-agr-plans" / "experiment.py"
BENCHES = ("bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace")
MUTATED = ("bench-b02-corner-niche", "bench-b02t-terrace")
INPUT_NAMES = ("object.json", "etalon.json", "spec.json", "tolerances.json")
VARIANTS = ("bulge", "hatch", "nested_insert", "missing_xref", "spline", "open_contour")
CARD, BUSY_SLEEP_S, XREF_PATH, POLY_BAD = "t_a0bf33bc", 5, "C:/missing/agr-e2-xref.dwg", 2 | 4 | 16 | 32 | 64
BLOCK_DEPTH = 16
LIMITATION = (
    "Synthetic Spec proxy, not etalon geometry. Fail-closed on straight closed LWPOLYLINE, "
    "closed 3D POLYLINE and POINT only. No self-intersection test and no semantic hole inference. "
    "Native census is inventory, not features."
)
CENSUS = "\n".join([
    '(setvar "FILEDIA" 0)', '(setvar "CMDECHO" 0)',
    '(princ (strcat "\\nAGR_ID|" (getvar "ACADVER") "|" (getvar "DWGNAME") "|" (itoa (fix (getvar "INSUNITS"))) "\\n"))',
    '(setq ss (ssget "_X" \'((410 . "Model"))))',
    '(if ss (progn (setq i 0) (repeat (sslength ss) (setq e (ssname ss i) d (entget e)) '
    '(princ (strcat "\\nAGR_RAW|" (cdr (assoc 5 d)) "|" (cdr (assoc 0 d)) "|" (cdr (assoc 8 d)) "\\n")) (setq i (1+ i)))))',
    '(princ "\\nAGR_CENSUS_DONE\\n")', "(princ)",
])
ERROR_TOKENS = ("error:", "; error", "unknown command", "bad argument", "bad function", "no function definition")


def _load_base():
    spec = importlib.util.spec_from_file_location("acad_coreconsole_agr_plans", BASELINE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(BASELINE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_base()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True


def _rel(path, scratch):
    return str(Path(path).resolve().relative_to(Path(scratch).resolve())).replace("\\", "/")


def _row(entity, parents, reason=None, extra=None):
    item = {"handle": str(entity.dxf.handle), "type": entity.dxftype(), "layer": str(entity.dxf.layer),
            "parents": [str(part) for part in parents]}
    if reason:
        item["reason"] = reason
    if extra:
        item.update(extra)
    return item


def _bulge(entity):
    kind = entity.dxftype()
    if kind == "LWPOLYLINE":
        return any(abs(float(point[2])) > 1e-9 for point in entity.get_points("xyb"))
    if kind == "POLYLINE":
        return any(abs(float(vertex.dxf.bulge)) > 1e-9 for vertex in entity.vertices if vertex.dxf.hasattr("bulge"))
    return False


def _problems(entity):
    kind = entity.dxftype()
    if kind == "POINT":
        return []
    if kind not in ("LWPOLYLINE", "POLYLINE"):
        return ["unsupported_type"]
    found = []
    if kind == "POLYLINE":
        flags = int(entity.dxf.flags)
        if (flags & POLY_BAD) or not (flags & 8):
            found.append("unsupported_polyline")
    if _bulge(entity):
        found.append("curved_segment")
    if not base._closed(entity):
        found.append("open_contour")
    return found


def _extract(entity):
    kind = entity.dxftype()
    if kind == "POINT":
        loc = entity.dxf.location
        return {"layer": entity.dxf.layer, "kind": kind, "closed": False,
                "vertices_mm": [base._as_wcs(entity, loc.x, loc.y, loc.z)]}
    if kind == "LWPOLYLINE":
        elevation = float(entity.dxf.elevation)
        closed = base._closed(entity)
        verts = [base._as_wcs(entity, point[0], point[1], elevation) for point in entity.get_points("xy")]
    else:
        closed = base._closed(entity)
        verts = [base._as_wcs(entity, vertex.dxf.location.x, vertex.dxf.location.y, vertex.dxf.location.z)
                 for vertex in entity.vertices]
    return {"layer": entity.dxf.layer, "kind": kind, "closed": closed, "vertices_mm": base._drop_repeated_close(verts, closed)}


def _xref_meta(block):
    """Xref bits 4 and 8 and the path live on BLOCK only. Never touch BLOCK_RECORD."""
    if block is None:
        return None
    owner = block.block
    flags = int(owner.dxf.flags)
    if not (flags & 12):
        return None
    path = ""
    if owner.dxf.hasattr("xref_path") and owner.dxf.xref_path:
        path = str(owner.dxf.xref_path)
    return {"xref_path": path, "xref_flags": flags}


def _xref_reason(path):
    # Stored path text only. Do not resolve, expand or open it.
    if str(path or "").replace("\\", "/") == XREF_PATH:
        return "missing_xref"
    return "unresolved_xref"


def _walk(layout, doc, parents, depth, stack, inventory, diagnostics, found, layers):
    for entity in layout:
        if entity.dxftype() == "INSERT":
            name = str(entity.dxf.name)
            try:
                block = doc.blocks.get(name)
            except Exception:
                block = None
            extra = _xref_meta(block)
            inventory.append(_row(entity, parents, extra=extra))
            diagnostics.append(_row(entity, parents, "block_not_normalized", extra))
            if extra:
                diagnostics.append(_row(entity, parents, _xref_reason(extra.get("xref_path")), extra))
            if block is None:
                diagnostics.append(_row(entity, parents, "missing_block", extra))
            elif name in stack:
                diagnostics.append(_row(entity, parents, "block_cycle", extra))
            elif depth >= BLOCK_DEPTH:
                diagnostics.append(_row(entity, parents, "depth_limit", extra))
            else:
                _walk(block, doc, parents + [entity.dxf.handle], depth + 1, stack + (name,),
                      inventory, diagnostics, found, layers)
            continue
        inventory.append(_row(entity, parents))
        problems = _problems(entity)
        if problems:
            diagnostics.extend(_row(entity, parents, reason) for reason in problems)
            continue
        found.append(_extract(entity))
        layers.setdefault(entity.dxf.layer, []).append((entity, parents))


def strict_read(path):
    """One ezdxf read. Any diagnostic => accepted False and features []."""
    doc = base._import_ezdxf().readfile(path)
    units = int(doc.header.get("$INSUNITS", 0))
    inventory, diagnostics, found, layers = [], [], [], {}
    if units != 4:
        diagnostics.append({"handle": "", "type": "HEADER", "layer": "", "parents": [], "reason": "unit_mismatch", "insunits": units})
    _walk(doc.modelspace(), doc, [], 0, (), inventory, diagnostics, found, layers)
    for items in layers.values():
        if len(items) > 1:
            diagnostics.extend(_row(entity, parents, "duplicate_layer") for entity, parents in items)
    if not inventory:
        diagnostics.append({"handle": "", "type": "DOCUMENT", "layer": "", "parents": [], "reason": "empty_document"})
    return {"accepted": not diagnostics, "features": found if not diagnostics else [], "diagnostics": diagnostics,
            "inventory": inventory, "insunits": units}


def _first_contour(doc):
    return next(entity for entity in doc.modelspace() if entity.dxftype() == "LWPOLYLINE")


def _attach_missing(doc, ezdxf_mod):
    name = "MISSING_XREF"
    attach = getattr(getattr(ezdxf_mod, "xref", None), "attach", None)
    if attach is not None:
        try:
            attach(doc, block_name=name, filename=XREF_PATH)
        except Exception:
            pass
    if name not in doc.blocks:
        doc.blocks.new(name)
    block = doc.blocks.get(name)
    block.block.dxf.flags = int(block.block.dxf.flags) | 4
    block.block.dxf.xref_path = XREF_PATH
    if not any(entity.dxftype() == "INSERT" and str(entity.dxf.name) == name for entity in doc.modelspace()):
        doc.modelspace().add_blockref(name, (0, 0))


def apply_variant(path, variant):
    ezdxf_mod = base._import_ezdxf()
    doc = ezdxf_mod.readfile(path)
    contour, model = _first_contour(doc), doc.modelspace()
    if variant == "bulge":
        point = contour[0]
        contour[0] = (point[0], point[1], point[2], point[3], 0.5)
    elif variant == "hatch":
        if "hole" not in doc.layers:
            doc.layers.add("hole")
        hatch = model.add_hatch(dxfattribs={"layer": "hole"})
        outer = [(point[0], point[1]) for point in contour.get_points("xy")]
        hatch.paths.add_polyline_path(outer, is_closed=True, flags=1)
        xs, ys = [point[0] for point in outer], [point[1] for point in outer]
        span = min(max(xs) - min(xs), max(ys) - min(ys)) * 0.1 or 1.0
        cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
        square = [(cx - span, cy - span), (cx + span, cy - span), (cx + span, cy + span), (cx - span, cy + span)]
        hatch.paths.add_polyline_path(square, is_closed=True, flags=0)
    elif variant == "nested_insert":
        inner = doc.blocks.new("INNER_CONTOUR")
        inner.add_lwpolyline([(point[0], point[1]) for point in contour.get_points("xy")], close=True,
                             dxfattribs={"layer": contour.dxf.layer, "elevation": float(contour.dxf.elevation)})
        outer = doc.blocks.new("OUTER_REF")
        outer.add_blockref("INNER_CONTOUR", (0, 0), dxfattribs={"rotation": 15.0, "xscale": 2.0, "yscale": 0.5, "zscale": 1.0})
        model.add_blockref("OUTER_REF", (0, 0), dxfattribs={"rotation": 5.0, "xscale": 1.0, "yscale": 1.0, "zscale": 1.0})
    elif variant == "missing_xref":
        _attach_missing(doc, ezdxf_mod)
    elif variant == "spline":
        model.add_spline([(0, 0, 0), (100, 50, 0), (200, 0, 0)], dxfattribs={"layer": "SPLINE"})
    elif variant == "open_contour":
        contour.closed = False
    else:
        raise ValueError(variant)
    doc.saveas(path)


def _case(bench, variant, path, features, scratch):
    anomaly = {"bulge": "curved_segment", "hatch": "unsupported_type", "nested_insert": "block_not_normalized",
               "missing_xref": "missing_xref", "spline": "unsupported_type", "open_contour": "open_contour"}.get(variant)
    return {"id": f"{bench}__{variant}", "benchmark": bench, "variant": variant, "anomaly": anomaly,
            "expected_baseline": "accept" if variant == "clean" else ("reject" if variant == "open_contour" else "silent_accept"),
            "expected_strict": "accept" if variant == "clean" else "reject", "dxf": _rel(path, scratch),
            "sha256": _sha(path), "expected_features": features, "synthetic": True, "etalon_geometry": False}


def phase_prepare(scratch, repeats):
    scratch.mkdir(parents=True)
    files = []
    for name in BENCHES:
        source_dir = ROOT / "benchmark" / name
        if not (source_dir / "spec.json").is_file():
            raise FileNotFoundError(source_dir / "spec.json")
        target_dir = scratch / "inputs" / name
        target_dir.mkdir(parents=True)
        for filename in INPUT_NAMES:
            source = source_dir / filename
            if not source.is_file():
                continue
            before, target = _sha(source), target_dir / filename
            shutil.copy2(source, target)
            files.append({"benchmark": name, "file": filename, "source": str(source), "source_sha256": before,
                          "copy": str(target), "copy_sha256": _sha(target)})
    _write(scratch / "inputs" / "manifest.json", {"synthetic_proxy": True, "etalon_geometry": False, "files": files})
    cases, drawings = [], scratch / "drawings"
    drawings.mkdir()
    for name in BENCHES:
        spec = base.Spec.model_validate_json((scratch / "inputs" / name / "spec.json").read_text(encoding="utf-8"))
        features = base.build_features([spec])
        clean = drawings / f"{name}__clean.dxf"
        base.write_dxf(features, clean)
        cases.append(_case(name, "clean", clean, features, scratch))
        if name not in MUTATED:
            continue
        for variant in VARIANTS:
            path = drawings / f"{name}__{variant}.dxf"
            shutil.copy2(clean, path)
            apply_variant(path, variant)
            cases.append(_case(name, variant, path, features, scratch))
    _write(scratch / "cases.json", {"synthetic": True, "etalon_geometry": False,
                                   "geometry_source": "spec.json via Spec.expanded_floors", "limitation": LIMITATION,
                                   "repeats": repeats, "cases": cases})
    return 0 if len(cases) == 15 else 1


def _metas(scratch):
    return {case["id"]: case for case in _read(scratch / "cases.json")["cases"]}


def _baseline_ok(meta, row):
    return row["accepted"] is (meta["expected_baseline"] != "reject")


def _strict_ok(meta, row):
    reasons = {item.get("reason") for item in row["diagnostics"]}
    if meta["expected_strict"] == "accept":
        compare = row.get("compare") or {}
        dev = compare.get("max_deviation_mm")
        return row["accepted"] is True and compare.get("ok") and dev is not None and dev <= base.TOL_MM and len(row["inventory"]) == len(meta["expected_features"])
    if row["accepted"] or meta["anomaly"] not in reasons or not row["inventory"]:
        return False
    if meta["variant"] == "missing_xref" and "block_not_normalized" not in reasons:
        return False
    if meta["variant"] == "hatch" and not any(item["type"] == "HATCH" for item in row["inventory"]):
        return False
    if meta["variant"] == "spline" and not any(item["type"] == "SPLINE" for item in row["inventory"]):
        return False
    return meta["variant"] != "nested_insert" or any(len(item["parents"]) >= 2 for item in row["inventory"])


def _rejected_compare():
    return {"ok": False, "errors": ["rejected"], "max_deviation_mm": None}


def phase_measure(scratch, repeats, mode):
    base._import_ezdxf()
    metas = _metas(scratch)
    out, path = {"phase": mode, "repeats": repeats, "cases": []}, scratch / f"{mode}.json"
    for meta in _read(scratch / "cases.json")["cases"]:
        dxf, raw, result, report, error = scratch / meta["dxf"], [], None, None, None
        for _ in range(repeats):
            started = time.perf_counter()
            if mode == "baseline":
                try:
                    entities, audit = base.read_dxf(dxf)
                    report, error = base.compare_features(meta["expected_features"], entities, audit["insunits"], base.TOL_MM), None
                except base.ReadbackError as exc:
                    report = base.compare_features(meta["expected_features"], exc.entities or [], (exc.audit or {}).get("insunits"), base.TOL_MM)
                    error = str(exc)
                result = {"accepted": error is None and bool(report and report.get("ok"))}
            else:
                result = strict_read(dxf)
                report = (base.compare_features(meta["expected_features"], result["features"], result["insunits"], base.TOL_MM)
                          if result["accepted"] else _rejected_compare())
            raw.append(time.perf_counter() - started)
        row = {"id": meta["id"], "seconds_raw": raw, "seconds_median": statistics.median(raw), "accepted": result["accepted"], "compare": report}
        if mode == "baseline":
            row["error"] = error
        else:
            row["diagnostics"], row["inventory"] = result["diagnostics"], result["inventory"]
        out["cases"].append(row)
        _write(path, out)
    checker = _baseline_ok if mode == "baseline" else _strict_ok
    return 0 if all(checker(metas[row["id"]], row) for row in out["cases"]) else 1


def _expected_case_ids():
    ids = []
    for name in BENCHES:
        ids.append(f"{name}__clean")
        if name in MUTATED:
            ids.extend(f"{name}__{variant}" for variant in VARIANTS)
    return ids


def _exact_ids(ids):
    expected = _expected_case_ids()
    return len(ids) == len(expected) and len(set(ids)) == len(expected) and set(ids) == set(expected)


def _parse_census(text):
    rows, identity, done = [], None, False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("AGR_RAW|"):
            parts = stripped.split("|", 3)
            if len(parts) == 4:
                rows.append((parts[1].upper(), parts[2], parts[3]))
        elif stripped.startswith("AGR_ID|") and identity is None:
            parts = stripped.split("|", 3)
            units = None
            if len(parts) == 4:
                try:
                    units = int(float(parts[3]))
                except ValueError:
                    units = None
            if len(parts) >= 3:
                identity = {"acadver": parts[1], "dwgname": parts[2] if len(parts) > 2 else "", "insunits": units}
        elif stripped.startswith("AGR_CENSUS_DONE"):
            done = True
    return rows, identity, done


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else ""


def _error_tokens(text):
    lowered = text.lower()
    return [token for token in ERROR_TOKENS if token in lowered]


def _invoke(wrapper, dwg, script, out_json):
    cmd = [sys.executable, str(wrapper), "acad", "--card", CARD, "--dwg", str(dwg), "--file", str(script),
           "--out", str(out_json), "--timeout", "60", "--wait", "30"]
    started, timed_out = time.perf_counter(), False
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
        _stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out, _stdout, stderr, code = True, exc.stdout or "", exc.stderr or "", None
    wall = time.perf_counter() - started
    payload = None
    if Path(out_json).is_file():
        try:
            payload = json.loads(Path(out_json).read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            payload = {"unparsed": True}
    status = payload.get("status") if isinstance(payload, dict) else None
    wrapper_code = payload.get("code", payload.get("exit_code", payload.get("returncode"))) if isinstance(payload, dict) else None
    timed_out = timed_out or status == "timeout" or wrapper_code == 5 or code == 5
    # payload["log"] once. Stdout often repeats that JSON and its escaped tokens.
    log_text = payload.get("log") if isinstance(payload, dict) and isinstance(payload.get("log"), str) else ""
    stderr_text = _as_text(stderr)
    rows, identity, done = _parse_census(log_text)
    log_tokens, stderr_tokens = _error_tokens(log_text), _error_tokens(stderr_text)
    expected = [(str(entity.dxf.handle).upper(), entity.dxftype(), str(entity.dxf.layer))
                for entity in base._import_ezdxf().readfile(dwg).modelspace()]
    name = (identity or {}).get("dwgname", "").lower()
    identity_ok = bool(identity) and str(identity["acadver"]).startswith("25") and identity["insunits"] == 4 and name in {Path(dwg).name.lower(), Path(dwg).stem.lower()}
    match = Counter(rows) == Counter(expected)
    diagnostics = {"log_tokens": log_tokens, "stderr_tokens": stderr_tokens, "marker": done}
    ok = (code == 0 and status == "ok" and _as_int(wrapper_code) == 0 and not timed_out and done
          and identity_ok and match and not log_tokens and not stderr_tokens)
    if code == 3 or (isinstance(status, str) and "busy" in status.lower()):
        cause = "busy"
    elif timed_out:
        cause = "timeout"
    elif log_tokens or stderr_tokens:
        cause = "error_token"
    elif not done:
        cause = "missing_marker"
    elif not identity_ok:
        cause = "identity"
    elif not match:
        cause = "inventory_mismatch"
    elif not ok:
        cause = f"exit_{code}"
    else:
        cause = None
    return {"ok": ok, "cause": cause, "wall_s": wall, "returncode": code, "status": status, "wrapper_code": wrapper_code,
            "timeout": timed_out, "identity": identity, "identity_ok": identity_ok, "match": match,
            "diagnostics": diagnostics, "log": str(out_json),
            "inventory": [{"handle": handle, "type": kind, "layer": layer} for handle, kind, layer in rows]}


def phase_native(scratch, repeats, wrapper):
    metas = _read(scratch / "cases.json")["cases"]
    path = scratch / "native.json"
    state = _read(path) if path.is_file() else {"phase": "native", "repeats": repeats, "aborted": None, "cases": {}}
    state["aborted"], causes = None, {}
    for meta in metas:
        bucket = state["cases"].setdefault(meta["id"], {"repetitions": []})
        ok_count = sum(1 for rep in bucket["repetitions"] if rep.get("ok"))
        index = 1 + max((rep["rep"] for rep in bucket["repetitions"]), default=0)
        while ok_count < repeats and state["aborted"] is None:
            folder = scratch / "native" / meta["id"] / f"rep-{index:02d}"
            folder.mkdir(parents=True, exist_ok=True)
            dwg = folder / "copy.dxf"
            shutil.copy2(scratch / meta["dxf"], dwg)
            script = folder / "census.scr"
            base.write_script(script, CENSUS)
            attempt = _invoke(wrapper, dwg, script, folder / "census.json")
            attempt["rep"] = index
            bucket["repetitions"].append(attempt)
            _write(path, state)
            if attempt["ok"]:
                ok_count += 1
            else:
                cause = attempt["cause"] or "failed"
                causes[cause] = causes.get(cause, 0) + 1
                if causes[cause] >= 2:
                    state["aborted"] = cause
                    _write(path, state)
                elif cause == "busy":
                    time.sleep(BUSY_SLEEP_S)
            index += 1
        if state["aborted"]:
            break
    ready = state["aborted"] is None and all(
        sum(1 for rep in state["cases"].get(meta["id"], {}).get("repetitions", []) if rep.get("ok")) >= repeats for meta in metas)
    return 0 if ready else 1


def _hash_report(scratch):
    manifest, rows, unchanged = _read(scratch / "inputs" / "manifest.json"), [], True
    for item in manifest["files"]:
        source_ok = Path(item["source"]).is_file() and _sha(item["source"]) == item["source_sha256"]
        copy_ok = Path(item["copy"]).is_file() and _sha(item["copy"]) == item["copy_sha256"]
        unchanged = unchanged and source_ok and copy_ok
        rows.append({**item, "source_unchanged": source_ok, "copy_unchanged": copy_ok})
    drawings = []
    for meta in _read(scratch / "cases.json")["cases"]:
        current = _sha(scratch / meta["dxf"])
        same = current == meta["sha256"]
        unchanged = unchanged and same
        drawings.append({"id": meta["id"], "sha256": meta["sha256"], "current_sha256": current, "unchanged": same})
    return unchanged, rows, drawings


def _stored_ok(payload, metas, checker):
    if payload is None:
        return None
    rows = payload.get("cases")
    if not isinstance(rows, list) or not _exact_ids([row.get("id") for row in rows]):
        return False
    need = int(payload.get("repeats") or 0)
    if need < 3:
        return False
    for row in rows:
        samples = row.get("seconds_raw")
        if not isinstance(samples, list) or len(samples) < need:
            return False
        meta = metas.get(row["id"]) if isinstance(metas, dict) else None
        if not isinstance(meta, dict) or not checker(meta, row):
            return False
    return True


def _case_doc(scratch):
    path = scratch / "cases.json"
    if not path.is_file():
        return {"repeats": 0, "cases": []}
    payload = _read(path)
    return payload if isinstance(payload, dict) else {"repeats": 0, "cases": []}


def _native_contract(native, case_doc):
    if native is None:
        return None
    if native.get("aborted") is not None:
        return False
    listed = [case.get("id") for case in (case_doc.get("cases") or []) if isinstance(case, dict)]
    need = int(case_doc.get("repeats") or 0)
    if need < 3 or int(native.get("repeats") or 0) < 3 or not _exact_ids(listed):
        return False
    buckets = native.get("cases")
    if not isinstance(buckets, dict) or set(buckets) != set(listed):
        return False
    for case_id in listed:
        reps = buckets[case_id].get("repetitions") if isinstance(buckets[case_id], dict) else None
        if not isinstance(reps, list):
            return False
        ok_count = sum(1 for rep in reps if isinstance(rep, dict) and rep.get("ok") is True)
        if ok_count < need:
            return False
    return True


def phase_summary(scratch):
    unchanged, inputs, drawings = _hash_report(scratch)
    case_doc = _case_doc(scratch)
    metas = {case["id"]: case for case in case_doc.get("cases") or [] if isinstance(case, dict) and case.get("id")}
    baseline = _read(scratch / "baseline.json") if (scratch / "baseline.json").is_file() else None
    strict = _read(scratch / "strict.json") if (scratch / "strict.json").is_file() else None
    native = _read(scratch / "native.json") if (scratch / "native.json").is_file() else None
    baseline_ok, strict_ok = _stored_ok(baseline, metas, _baseline_ok), _stored_ok(strict, metas, _strict_ok)
    native_ok = _native_contract(native, case_doc)
    accepted = [row["compare"]["max_deviation_mm"] for row in (strict or {}).get("cases", [])
                if row.get("accepted") and (row.get("compare") or {}).get("max_deviation_mm") is not None]
    native_reps = [] if native is None else [rep for bucket in native.get("cases", {}).values() for rep in bucket.get("repetitions", [])]
    summary = {"synthetic": True, "etalon_geometry": False, "limitation": LIMITATION, "hashes_unchanged": unchanged,
               "input_hashes": inputs, "dxf_hashes": drawings, "baseline_contract": baseline_ok, "strict_contract": strict_ok,
               "native_contract": native_ok, "native_aborted": None if native is None else native.get("aborted"),
               "acceptance": {"baseline_accepted": None if baseline is None else sum(row["accepted"] for row in baseline["cases"]),
                              "strict_accepted": None if strict is None else sum(row["accepted"] for row in strict["cases"]),
                              "strict_rejected": None if strict is None else sum(not row["accepted"] for row in strict["cases"]),
                              "native_ok_reps": None if native is None else sum(bool(rep.get("ok")) for rep in native_reps)},
               "max_accepted_deviation_mm": max(accepted) if accepted else None,
               "baseline_cases": None if baseline is None else baseline["cases"],
               "strict_cases": None if strict is None else strict["cases"],
               "native_cases": None if native is None else native.get("cases")}
    _write(scratch / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("hashes_unchanged", "baseline_contract", "strict_contract", "native_contract", "acceptance", "max_accepted_deviation_mm", "native_aborted")}, indent=2))
    if not unchanged or baseline_ok is not True or strict_ok is not True or native_ok is not True:
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="E2 silent CAD feature-loss probe")
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=("prepare", "baseline", "strict", "native", "summary"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--wrapper", type=Path)
    args = parser.parse_args(argv)
    if args.repeats < 3:
        print("repeats must be >= 3", file=sys.stderr)
        return 2
    scratch = args.scratch
    if not scratch.is_absolute() or _inside(scratch, ROOT):
        print("scratch must be an absolute path outside the worktree", file=sys.stderr)
        return 2
    if args.phase == "prepare":
        if scratch.exists():
            print("scratch already exists", file=sys.stderr)
            return 2
        return phase_prepare(scratch, args.repeats)
    if not scratch.is_dir():
        print("scratch missing", file=sys.stderr)
        return 2
    if args.phase == "native":
        if args.wrapper is None:
            print("wrapper is required for native", file=sys.stderr)
            return 2
        return phase_native(scratch, args.repeats, args.wrapper)
    if args.phase == "summary":
        return phase_summary(scratch)
    return phase_measure(scratch, args.repeats, args.phase)


if __name__ == "__main__":
    sys.exit(main())
