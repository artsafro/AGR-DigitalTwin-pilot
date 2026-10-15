"""Hypothesis 101: relation multimaps report duplicate IFC links without picking a winner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "bim-revit-agr"))

import ifcopenshell
import ifc_probe
from dt_ai.spec.model import Spec

from relation_multimap import canonical, census

SPECS = {
    "b01": ROOT / "benchmark" / "bench-b01-box" / "spec.json",
    "b02": ROOT / "benchmark" / "bench-b02-corner-niche" / "spec.json",
    "b02t": ROOT / "benchmark" / "bench-b02t-terrace" / "spec.json",
}
UNITS = (("m", False), ("mm", True))
FAMILIES = ("void", "fill", "contain")
RELATION_CLASS = {
    "void": "IfcRelVoidsElement",
    "fill": "IfcRelFillsElement",
    "contain": "IfcRelContainedInSpatialStructure",
}


def _blank(value):
    return "" if value is None else value


def _gid(entity):
    if entity is None:
        return None
    return getattr(entity, "GlobalId", None)


def _sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _median(values):
    if not values:
        return None
    return statistics.median(values)


def _sort_records(records):
    return sorted(
        records,
        key=lambda row: (_blank(row["family"]), _blank(row["source_id"]), _blank(row["endpoint_id"]), _blank(row["relation_id"])),
    )


def _relation_records(ifc):
    """Independent raw enumeration. Does not call census."""
    found = []
    for family in FAMILIES:
        cls = RELATION_CLASS[family]
        for rel in ifc.by_type(cls):
            relation_id = getattr(rel, "GlobalId", None)
            if family == "void":
                pairs = [(_gid(getattr(rel, "RelatedOpeningElement", None)), _gid(getattr(rel, "RelatingBuildingElement", None)))]
            elif family == "fill":
                pairs = [(_gid(getattr(rel, "RelatingOpeningElement", None)), _gid(getattr(rel, "RelatedBuildingElement", None)))]
            else:
                endpoint_id = _gid(getattr(rel, "RelatingStructure", None))
                elements = list(getattr(rel, "RelatedElements", None) or [])
                sources = elements or [None]
                pairs = [(_gid(source), endpoint_id) for source in sources]
            for source_id, endpoint_id in pairs:
                found.append(
                    {
                        "family": family,
                        "relation_id": relation_id,
                        "source_id": source_id,
                        "endpoint_id": endpoint_id,
                    }
                )
    return _sort_records(found)


def _endpoint_map(records):
    maps = {family: {} for family in FAMILIES}
    for row in records:
        if row["source_id"] is None:
            continue
        bucket = maps[row["family"]].setdefault(row["source_id"], [])
        if row["endpoint_id"] not in bucket:
            bucket.append(row["endpoint_id"])
    for family in maps.values():
        for source_id, endpoints in family.items():
            family[source_id] = sorted(endpoints, key=_blank)
    return maps


def _raw_manifest(path):
    ifc = ifcopenshell.open(str(path))
    records = _relation_records(ifc)
    products = []
    for product in ifc.by_type("IfcProduct"):
        products.append(
            {
                "global_id": product.GlobalId,
                "is_wall": bool(product.is_a("IfcWall")),
                "is_window": bool(product.is_a("IfcWindow")),
                "is_opening": bool(product.is_a("IfcOpeningElement")),
                "is_storey": bool(product.is_a("IfcBuildingStorey")),
            }
        )
    relation_ids = {family: [rel.GlobalId for rel in ifc.by_type(RELATION_CLASS[family])] for family in FAMILIES}
    return {
        "records": records,
        "maps": _endpoint_map(records),
        "products": products,
        "product_ids": sorted(row["global_id"] for row in products),
        "relation_ids": relation_ids,
        "relation_counts": {family: len(ids) for family, ids in relation_ids.items()},
    }


def _ids(products, flag):
    return sorted(row["global_id"] for row in products if row[flag])


def _one_endpoint(maps, family, source_id):
    endpoints = [item for item in maps[family].get(source_id, []) if item is not None]
    if len(endpoints) != 1:
        raise RuntimeError(f"{family} {source_id} has endpoints {endpoints}")
    return endpoints[0]


def _relation_id(records, family, source_id, endpoint_id):
    found = sorted(
        row["relation_id"]
        for row in records
        if row["family"] == family and row["source_id"] == source_id and row["endpoint_id"] == endpoint_id
    )
    if not found:
        raise RuntimeError(f"no {family} relation for {source_id} -> {endpoint_id}")
    return found[0]


def _target(manifest, family):
    products = manifest["products"]
    maps = manifest["maps"]
    if family in ("void", "fill"):
        sources = [gid for gid in _ids(products, "is_opening") if any(item is not None for item in maps[family].get(gid, []))]
        if not sources:
            raise RuntimeError(f"no opening with a {family} relation")
        source_id = sources[0]
        others = _ids(products, "is_wall" if family == "void" else "is_window")
    else:
        sources = [gid for gid in _ids(products, "is_wall") if any(item is not None for item in maps["contain"].get(gid, []))]
        if not sources:
            raise RuntimeError("no contained wall")
        source_id = sources[0]
        others = _ids(products, "is_storey")
    original = _one_endpoint(maps, family, source_id)
    injected = next((gid for gid in others if gid != original), None)
    if injected is None:
        raise RuntimeError(f"no alternate {family} endpoint for {source_id}")
    return {
        "source_id": source_id,
        "original_endpoint_id": original,
        "original_relation_id": _relation_id(manifest["records"], family, source_id, original),
        "injected_endpoint_id": injected,
    }


def _has_record(records, family, relation_id, source_id, endpoint_id):
    return any(
        row["family"] == family
        and row["relation_id"] == relation_id
        and row["source_id"] == source_id
        and row["endpoint_id"] == endpoint_id
        for row in records
    )


def _inject(clean_path, dest, family, target):
    ifc = ifcopenshell.open(str(clean_path))
    original = next(rel for rel in ifc.by_type(RELATION_CLASS[family]) if rel.GlobalId == target["original_relation_id"])
    history = getattr(original, "OwnerHistory", None)
    source = ifc.by_guid(target["source_id"])
    endpoint = ifc.by_guid(target["injected_endpoint_id"])
    new_id = ifcopenshell.guid.new()
    while new_id == target["original_relation_id"]:
        new_id = ifcopenshell.guid.new()
    if family == "void":
        ifc.create_entity(
            "IfcRelVoidsElement",
            GlobalId=new_id,
            OwnerHistory=history,
            RelatingBuildingElement=endpoint,
            RelatedOpeningElement=source,
        )
    elif family == "fill":
        ifc.create_entity(
            "IfcRelFillsElement",
            GlobalId=new_id,
            OwnerHistory=history,
            RelatingOpeningElement=source,
            RelatedBuildingElement=endpoint,
        )
    else:
        ifc.create_entity(
            "IfcRelContainedInSpatialStructure",
            GlobalId=new_id,
            OwnerHistory=history,
            RelatingStructure=endpoint,
            RelatedElements=(source,),
        )
    ifc.write(str(dest))
    injection = {
        "file": Path(dest).name,
        "family": family,
        "source_id": target["source_id"],
        "original_endpoint_id": target["original_endpoint_id"],
        "original_relation_id": target["original_relation_id"],
        "injected_endpoint_id": target["injected_endpoint_id"],
        "injected_relation_id": new_id,
    }
    return injection


def _saved_flags(clean_manifest, malformed_path, injection):
    raw = _raw_manifest(malformed_path)
    family = injection["family"]
    injected = {
        "family": family,
        "relation_id": injection["injected_relation_id"],
        "source_id": injection["source_id"],
        "endpoint_id": injection["injected_endpoint_id"],
    }
    ids = raw["relation_ids"][family]
    survived = (
        injection["original_relation_id"] in ids
        and injection["injected_relation_id"] in ids
        and _has_record(raw["records"], family, injection["original_relation_id"], injection["source_id"], injection["original_endpoint_id"])
        and _has_record(raw["records"], family, injection["injected_relation_id"], injection["source_id"], injection["injected_endpoint_id"])
    )
    return raw, {
        "saved_relations_survived": survived,
        "products_kept": raw["product_ids"] == clean_manifest["product_ids"],
        "raw_records_exact": raw["records"] == _sort_records(list(clean_manifest["records"]) + [injected]),
    }


def _baseline(path):
    samples = []
    ledger = None
    error = None
    for _ in range(3):
        started = time.perf_counter()
        try:
            got = ifc_probe.read_ledger(path)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            continue
        samples.append(time.perf_counter() - started)
        ledger = got
        error = None
    return ledger, error, samples


def _geometry_issues(ledger):
    if not ledger:
        return 0
    return sum(1 for line in ledger.get("issues", []) if "geometry failed" in line)


def _issues_mentioning(ledger, source_id):
    if not ledger or not source_id:
        return []
    return [line for line in ledger.get("issues", []) if source_id in line]


def _selected(ledger, family, source_id):
    if not ledger:
        return None
    if family in ("void", "fill"):
        field = "host_id" if family == "void" else "fill_id"
        rows = ledger.get("openings", [])
    else:
        field = "storey_id"
        rows = ledger.get("walls", [])
    for row in rows:
        if row.get("global_id") == source_id:
            return row.get(field)
    return None


def _endpoint_parity(ledger, maps):
    if not ledger:
        return False
    for row in ledger.get("openings", []):
        gid = row.get("global_id")
        if maps["void"].get(gid) != [row.get("host_id")] or maps["fill"].get(gid) != [row.get("fill_id")]:
            return False
    for row in list(ledger.get("walls", [])) + list(ledger.get("windows", [])) + list(ledger.get("slabs", [])):
        if maps["contain"].get(row.get("global_id")) != [row.get("storey_id")]:
            return False
    return True


def _candidate(path):
    texts = []
    samples = []
    result = None
    for _ in range(3):
        ifc = ifcopenshell.open(str(path))
        for reverse in (False, True):
            started = time.perf_counter()
            got = census(ifc, reverse=reverse)
            samples.append(time.perf_counter() - started)
            texts.append(canonical(got))
            if reverse is False and result is None:
                result = got
    digest = hashlib.sha256(texts[0].encode("utf-8")).hexdigest()
    return result, len(set(texts)) == 1, digest, samples


def _matches(diag, injection):
    return (
        diag.get("kind") == "cardinality"
        and diag.get("family") == injection["family"]
        and diag.get("source_id") == injection["source_id"]
        and diag.get("endpoint_ids") == sorted([injection["original_endpoint_id"], injection["injected_endpoint_id"]])
        and diag.get("relation_ids") == sorted([injection["original_relation_id"], injection["injected_relation_id"]])
        and diag.get("status") == "unresolved"
        and diag.get("selected_endpoint") is None
    )


def _verdict(summary, clean):
    reasons = []
    if summary["baseline_collapsed_count"] < 1:
        reasons.append("baseline_collapsed_count < 1")
    if summary["candidate_correct_count"] != 18:
        reasons.append("candidate_correct_count != 18")
    if summary["candidate_false_positive_files"]:
        reasons.append("candidate false positives")
    if summary["candidate_false_negative_files"]:
        reasons.append("candidate false negatives")
    if summary["lost_raw_record_files"]:
        reasons.append("lost raw records")
    if summary["lost_product_files"]:
        reasons.append("lost products")
    if summary["clean_zero_diag_count"] != 6:
        reasons.append("clean_zero_diag_count != 6")
    if sum(row["candidate"]["maps_equal"] for row in clean) != 6:
        reasons.append("clean candidate maps_equal is not true on all 6")
    if sum(row["candidate"]["records_equal"] for row in clean) != 6:
        reasons.append("clean candidate records_equal is not true on all 6")
    if summary["stable_count"] != 24:
        reasons.append("stable_count != 24")
    if summary["saved_relation_loss_files"] != []:
        reasons.append("saved_relation_loss_files is not empty")
    return ("confirmed" if not reasons else "rejected"), reasons


def _write_json(path, document):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _inconclusive(results_path, out, reason):
    version = None
    try:
        version = str(ifcopenshell.version)
    except Exception:
        version = None
    document = {
        "delivery_passed": False,
        "synthetic": True,
        "ifcopenshell_version": version,
        "python": sys.version,
        "spec_sha256": {},
        "clean": [],
        "malformed": [],
        "summary": {
            "n_clean": 0,
            "n_malformed": 0,
            "baseline_collapsed_count": 0,
            "baseline_retains_both_count": 0,
            "candidate_correct_count": 0,
            "candidate_false_positive_files": [],
            "candidate_false_negative_files": [],
            "lost_raw_record_files": [],
            "lost_product_files": [],
            "clean_zero_diag_count": 0,
            "clean_endpoint_parity_count": 0,
            "stable_count": 0,
            "saved_relation_loss_files": [],
            "baseline_errors": [],
            "geometry_issue_files": [],
            "median_baseline_s": None,
            "median_candidate_s": None,
        },
        "verdict": "inconclusive",
        "verdict_reasons": [reason],
    }
    _write_json(results_path, document)
    if out is not None:
        _write_json(Path(out) / "results.json", document)
    print(json.dumps({"summary": document["summary"], "verdict": "inconclusive", "verdict_reasons": [reason]}, sort_keys=True, indent=2))


def run(out, results_path):
    missing = [name for name, path in SPECS.items() if not path.is_file()]
    if missing:
        _inconclusive(results_path, out, "missing spec: " + ", ".join(missing))
        return
    specs = {}
    spec_sha = {}
    for name, path in SPECS.items():
        raw = path.read_bytes()
        specs[name] = Spec.model_validate_json(raw)
        spec_sha[name] = hashlib.sha256(raw).hexdigest()

    clean_rows = []
    malformed_rows = []
    injections = []
    baseline_times = []
    candidate_times = []
    false_positives = []
    false_negatives = []
    lost_raw = []
    lost_products = []
    saved_loss = []
    baseline_errors = []
    geometry_files = []
    stable = 0
    collapsed = 0
    retains = 0
    correct = 0
    zero_diag = 0
    parity = 0

    for name in ("b01", "b02", "b02t"):
        for units, milli in UNITS:
            clean_path = out / f"{name}-{units}.ifc"
            ifc_probe.write_ifc(specs[name], clean_path, milli)
            manifest = _raw_manifest(clean_path)
            created = []
            for family in FAMILIES:
                dest = out / f"{name}-{units}-dup-{family}.ifc"
                injection = _inject(clean_path, dest, family, _target(manifest, family))
                raw, flags = _saved_flags(manifest, dest, injection)
                injections.append(injection)
                created.append((dest, injection, raw, flags))
            _write_json(out / "injections.json", injections)

            ledger, error, samples = _baseline(clean_path)
            baseline_times.extend(samples)
            result, order_stable, digest, cand_samples = _candidate(clean_path)
            candidate_times.extend(cand_samples)
            maps_equal = result["maps"] == manifest["maps"]
            records_equal = result["records"] == manifest["records"]
            diagnostics_count = len(result["diagnostics"])
            file_name = clean_path.name
            if error:
                baseline_errors.append(f"{file_name}: {error}")
            if _geometry_issues(ledger):
                geometry_files.append(file_name)
            if diagnostics_count == 0:
                zero_diag += 1
            else:
                false_positives.append(file_name)
            if _endpoint_parity(ledger, manifest["maps"]):
                parity += 1
            if not records_equal:
                lost_raw.append(file_name)
            if order_stable:
                stable += 1
            clean_rows.append(
                {
                    "name": name,
                    "units": units,
                    "sha256": _sha_file(clean_path),
                    "n_products": len(manifest["product_ids"]),
                    "n_raw_records": len(manifest["records"]),
                    "relation_counts": manifest["relation_counts"],
                    "baseline": {
                        "error": error,
                        "geometry_issues": _geometry_issues(ledger),
                        "endpoint_parity": _endpoint_parity(ledger, manifest["maps"]),
                        "median_s": _median(samples),
                    },
                    "candidate": {
                        "diagnostics_count": diagnostics_count,
                        "maps_equal": maps_equal,
                        "records_equal": records_equal,
                        "order_and_read_stable": order_stable,
                        "canonical_sha256": digest,
                        "median_s": _median(cand_samples),
                    },
                }
            )

            for dest, injection, raw, flags in created:
                ledger, error, samples = _baseline(dest)
                baseline_times.extend(samples)
                result, order_stable, digest, cand_samples = _candidate(dest)
                candidate_times.extend(cand_samples)
                records_equal = result["records"] == raw["records"]
                diags = result["diagnostics"]
                matched = [item for item in diags if _matches(item, injection)]
                is_correct = len(diags) == 1 and len(matched) == 1 and records_equal
                file_name = dest.name
                if error:
                    baseline_errors.append(f"{file_name}: {error}")
                if _geometry_issues(ledger):
                    geometry_files.append(file_name)
                if len(diags) > 1 or (diags and not matched):
                    false_positives.append(file_name)
                if not matched:
                    false_negatives.append(file_name)
                if not records_equal:
                    lost_raw.append(file_name)
                if not flags["products_kept"]:
                    lost_products.append(file_name)
                if not flags["saved_relations_survived"]:
                    saved_loss.append(file_name)
                if order_stable:
                    stable += 1
                if is_correct:
                    correct += 1
                selected = _selected(ledger, injection["family"], injection["source_id"])
                text = "" if ledger is None else json.dumps(ledger, sort_keys=True, separators=(",", ":"))
                keeps_both = (
                    injection["original_relation_id"] in text and injection["injected_relation_id"] in text
                )
                did_collapse = selected in {injection["original_endpoint_id"], injection["injected_endpoint_id"]} and not keeps_both
                if did_collapse:
                    collapsed += 1
                if keeps_both:
                    retains += 1
                malformed_rows.append(
                    {
                        "name": name,
                        "units": units,
                        "family": injection["family"],
                        "sha256": _sha_file(dest),
                        "injection": injection,
                        "saved_relations_survived": flags["saved_relations_survived"],
                        "products_kept": flags["products_kept"],
                        "raw_records_exact": flags["raw_records_exact"],
                        "baseline": {
                            "error": error,
                            "geometry_issues": _geometry_issues(ledger),
                            "selected_endpoint": selected,
                            "collapsed": did_collapse,
                            "retains_both_relation_ids": keeps_both,
                            "issues_mentioning_source": _issues_mentioning(ledger, injection["source_id"]),
                            "median_s": _median(samples),
                        },
                        "candidate": {
                            "diagnostics": diags,
                            "correct": is_correct,
                            "records_equal": records_equal,
                            "order_and_read_stable": order_stable,
                            "canonical_sha256": digest,
                            "median_s": _median(cand_samples),
                        },
                    }
                )

    summary = {
        "n_clean": len(clean_rows),
        "n_malformed": len(malformed_rows),
        "baseline_collapsed_count": collapsed,
        "baseline_retains_both_count": retains,
        "candidate_correct_count": correct,
        "candidate_false_positive_files": false_positives,
        "candidate_false_negative_files": false_negatives,
        "lost_raw_record_files": lost_raw,
        "lost_product_files": lost_products,
        "clean_zero_diag_count": zero_diag,
        "clean_endpoint_parity_count": parity,
        "stable_count": stable,
        "saved_relation_loss_files": saved_loss,
        "baseline_errors": baseline_errors,
        "geometry_issue_files": geometry_files,
        "median_baseline_s": _median(baseline_times),
        "median_candidate_s": _median(candidate_times),
    }
    verdict, reasons = _verdict(summary, clean_rows)
    document = {
        "delivery_passed": False,
        "synthetic": True,
        "ifcopenshell_version": str(ifcopenshell.version),
        "python": sys.version,
        "spec_sha256": spec_sha,
        "clean": clean_rows,
        "malformed": malformed_rows,
        "summary": summary,
        "verdict": verdict,
        "verdict_reasons": reasons,
    }
    _write_json(results_path, document)
    _write_json(out / "results.json", document)
    print(json.dumps({"summary": summary, "verdict": verdict, "verdict_reasons": reasons}, sort_keys=True, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run hypothesis 101 on synthetic IFC controls")
    parser.add_argument("--out", required=True)
    parser.add_argument("--results", default=str(ROOT / "experiments" / "hyp-101" / "results.json"))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"out dir already exists: {out}")
    try:
        import ifcopenshell as _ifc  # noqa: F401
    except Exception as exc:
        _inconclusive(Path(args.results), None, f"ifcopenshell import failed: {exc}")
        return 0
    os.makedirs(out)
    run(out, Path(args.results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
