"""Library entries for generated MAF benches (#1046): build folder -> catalogue.json["generated"] + catalogue.md section.

Pattern: new-case (generated MAF rows into the scan-built MAF catalogue; no registered pattern in
docs/domain/patterns/INDEX.md). The scan catalogue (`maf_catalogue.py`, `entries`) is left as it is; generated
models live in `generated` (one entry per distinct model) and `generated_dropped` (every build row that is not
an entry, with its reason).

Fail closed: an approved row needs a passing checks row (dimension, maf_findings, UV inside its slot) for NPM and
VPM, a structural readback and a passed xView report; every material it uses must be a key of the material
library (materials_vNNN.json) - an unmapped material is an error naming it. Outputs must not alias any input.

    uv run python tools/library/maf_gen_catalogue.py --build-dir C:/x/vatutino-maf/gen-v001/rows-v006p-3 \
        --approve 2-10 --decision D202 --materials library/materials/materials_v001.json \
        --catalogue library/maf/catalogue.json --catalogue-md library/maf/catalogue.md \
        --out-json <tmp>/catalogue.json --out-md <tmp>/catalogue.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

MD_BEGIN = "<!-- generated-maf:begin (tools/library/maf_gen_catalogue.py) -->"
MD_END = "<!-- generated-maf:end -->"
SIDES = ("npm", "vpm")
MAT_PREFIX = "MAF_"


def _read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_rows(text: str) -> set[int]:
    """'2-10' / '2,3,7-9' -> {rows}; rows are positive, ranges ascending."""
    rows: set[int] = set()
    for part in str(text).split(","):
        lo, sep, hi = part.strip().partition("-")
        if not lo.isdigit() or (sep and not hi.isdigit()):
            raise ValueError(f"rows: cannot parse {part!r} in {text!r}")
        a, b = int(lo), int(hi) if sep else int(lo)
        if a < 1 or b < a:
            raise ValueError(f"rows: bad range {part!r}")
        rows.update(range(a, b + 1))
    return rows


def load_build(build_dir: Path) -> dict:
    """build-report.json, checks.json and the per-row readback / xView files of one generator build folder."""
    d = Path(build_dir)
    report, checks = _read(d / "build-report.json"), _read(d / "checks.json")
    readback, xview = {}, {}
    for row in report.get("rows", []):
        sid = row.get("set_id")
        for side in SIDES:
            f = d / "readback" / f"{side}_{sid}.json"
            readback[(sid, side)] = _read(f) if f.is_file() else None
            x = d / "readback" / f"xview_{side}_{sid}.json"
            xview[(sid, side)] = _read(x) if x.is_file() else None
    return {"dir": str(d).replace("\\", "/"), "report": report, "checks": checks, "readback": readback,
            "xview": xview}


def _geometry_key(mesh: dict) -> str:
    """sha256 of the readback face geometry (positions, polygons, materials, UV); equal key = identical model."""
    canon = json.dumps(mesh["face_geometry"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _check_row(build: dict, row: dict, check: dict | None) -> tuple[list[str], str]:
    """Gate one approved row; returns (used material names, geometry key). Any defect: ValueError naming it."""
    sid = row["set_id"]
    if check is None:
        raise ValueError(f"row {row['row']} {sid}: no checks row")
    dims = row.get("generator_facts", {}).get("dims_m")
    if (not isinstance(dims, list) or len(dims) != 3
            or not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in dims)):
        raise ValueError(f"row {row['row']} {sid}: dims_m must be three finite positive numbers, got {dims!r}")
    used, keys = None, set()
    for side in SIDES:
        c = check.get(side) or {}
        if c.get("dimension") != "pass":
            raise ValueError(f"{sid} {side}: dimension {c.get('dimension')!r}, not pass")
        counts = c.get("maf_findings_counts") or {}
        if not counts or set(counts) != {"pass"}:
            raise ValueError(f"{sid} {side}: maf_findings {counts!r}, not all pass")
        slots = c.get("uv_slots") or {}
        mats = slots.get("materials") or {}
        if slots.get("faces_outside") != 0 or any(m.get("outside") != 0 for m in mats.values()):
            raise ValueError(f"{sid} {side}: UV faces outside the slot")
        if not mats:
            raise ValueError(f"{sid} {side}: no materials in the checks row")
        if used is not None and sorted(mats) != used:
            raise ValueError(f"{sid}: NPM and VPM use different materials {used} / {sorted(mats)}")
        used = sorted(mats)
        rb = build["readback"].get((sid, side))
        if not rb or len(rb.get("meshes") or []) != 1:
            raise ValueError(f"{sid} {side}: readback missing or not one mesh")
        mesh = rb["meshes"][0]
        rb_mats = sorted({m[len(MAT_PREFIX):] if m.startswith(MAT_PREFIX) else m
                          for m in mesh["face_geometry"]["polygon_material"]})
        if rb_mats != used:
            raise ValueError(f"{sid} {side}: readback materials {rb_mats} differ from checks {used}")
        keys.add(_geometry_key(mesh))
        xv = build["xview"].get((sid, side))
        if not xv or xv.get("passed") is not True:
            raise ValueError(f"{sid} {side}: xview report missing or not passed")
    return used, keys.pop() if len(keys) == 1 else "|".join(sorted(keys))


def build_generated(build: dict, approved: set[int], materials_doc: dict, *, decision: str) -> dict:
    """{'generated': [...], 'generated_dropped': [...]}; every build row ends in exactly one of the two."""
    report, checks = build["report"], build["checks"]
    if checks.get("verdict") != "pass":
        raise ValueError(f"checks.json verdict {checks.get('verdict')!r}, not pass")
    rows = report.get("rows") or []
    numbers = [r.get("row") for r in rows]
    dup = sorted({n for n in numbers if numbers.count(n) > 1})
    if dup:
        raise ValueError(f"build report: duplicate row {dup}")
    if not approved:
        raise ValueError("no approved rows")
    missing = sorted(set(approved) - set(numbers))
    if missing:
        raise ValueError(f"approved rows {missing} not in the build report")
    library = {m["key"]: m["library_id"] for m in materials_doc["materials"]}
    by_row = {c.get("row"): c for c in checks.get("rows", [])}
    models: dict[str, dict] = {}
    dropped = []
    for row in sorted(rows, key=lambda r: r["row"]):
        if row["row"] not in approved:
            dropped.append({"row": row["row"], "set_id": row["set_id"],
                            "reason": f"not approved: no «да» recorded for this row ({decision} covers "
                                      f"rows {_fmt_rows(approved)})"})
            continue
        used, key = _check_row(build, row, by_row.get(row["row"]))
        unmapped = [m for m in used if m not in library]
        if unmapped:
            raise ValueError(f"{row['set_id']}: material {unmapped} not in the material library")
        if key in models:
            models[key]["schedule_rows"].append(row["row"])
            models[key]["set_ids"].append(row["set_id"])
            models[key]["fbx_sha256_by_set_id"][row["set_id"]] = {s: row[s]["sha256"] for s in SIDES}
            continue
        facts = row["generator_facts"]
        models[key] = {
            "schedule_rows": [row["row"]], "set_ids": [row["set_id"]], "block": row.get("block"),
            "kind": "generated", "generator": f"tools/library/maf_gen_bench.py {report.get('form')}",
            "config": report.get("config"), "dims_m": [round(v, 4) for v in facts["dims_m"]],
            "faces": facts.get("faces"), "tris": facts.get("tris"),
            "materials": {m: library[m] for m in used},
            "npm": {"fbx": row["npm"]["fbx"], "sha256": row["npm"]["sha256"]},
            "vpm": {"fbx": row["vpm"]["fbx"], "sha256": row["vpm"]["sha256"]},
            "fbx_sha256_by_set_id": {row["set_id"]: {s: row[s]["sha256"] for s in SIDES}},
            "geometry_sha256": key, "build_dir": build["dir"],
            "checks": "pass (dimension, maf_findings, UV slots NPM+VPM; xView passed)",
            "approval": f"[{decision}]",
        }
    generated = []
    for i, entry in enumerate(models.values(), 1):
        generated.append({"id": f"MAF_GEN_{i:04d}", **entry})
    return {"generated": generated, "generated_dropped": dropped}


def _fmt_rows(rows) -> str:
    rows = sorted(rows)
    return f"{rows[0]}-{rows[-1]}" if rows == list(range(rows[0], rows[-1] + 1)) else ",".join(map(str, rows))


def render_md(gen: dict) -> str:
    lines = [MD_BEGIN, "", "## Generated MAF (one entry per distinct model)", "",
             "| id | schedule rows | set ids | dims m | tris | materials (library_id) | NPM sha256 | approval |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for e in gen["generated"]:
        mats = ", ".join(f"{k} ({v})" for k, v in e["materials"].items())
        dims = " ".join(f"{v:.3f}" for v in e["dims_m"])
        lines.append(f"| {e['id']} | {', '.join(map(str, e['schedule_rows']))} | {', '.join(e['set_ids'])} | "
                     f"{dims} | {e['tris']} | {mats} | `{e['npm']['sha256'][:12]}…` | {e['approval']} |")
    if gen["generated"]:
        lines += ["", f"Build folder: `{gen['generated'][0]['build_dir']}` (FBX not in the repo; paths and sha256 "
                      "in catalogue.json)."]
    lines += ["", "Dropped build rows:", ""]
    lines += [f"- row {d['row']} `{d['set_id']}`: {d['reason']}" for d in gen["generated_dropped"]] or ["- none"]
    lines += ["", MD_END]
    return "\n".join(lines) + "\n"


def merge_md(md: str, section: str) -> str:
    if md.count(MD_BEGIN) != md.count(MD_END) or md.count(MD_BEGIN) > 1:
        raise ValueError("catalogue.md: generated section markers are broken")
    if MD_BEGIN in md:
        head, rest = md.split(MD_BEGIN, 1)
        return head + section.rstrip("\n") + rest.split(MD_END, 1)[1]
    return md.rstrip("\n") + "\n\n" + section


def _same(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


_LIST_KEYS = ("excluded", "entries", "spec_matches", "generated", "generated_dropped")


def dump_catalogue_json(catalogue: dict) -> str:
    """Same layout as maf_audit.dump_catalogue_json (one top-level key per line, list items one per line)."""
    lines = ["{"]
    for key, value in catalogue.items():
        rendered_key = json.dumps(key, ensure_ascii=False)
        if key in _LIST_KEYS and value:
            lines.append(" %s: [" % rendered_key)
            lines.append(",\n".join("  " + json.dumps(item, ensure_ascii=False) for item in value))
            lines.append(" ],")
        else:
            lines.append(" %s: %s," % (rendered_key, json.dumps(value, ensure_ascii=False)))
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build-dir", required=True, type=Path)
    ap.add_argument("--approve", required=True, help="approved schedule rows, e.g. 2-10")
    ap.add_argument("--decision", required=True, help="decision id of the approval, e.g. D202")
    ap.add_argument("--materials", required=True, type=Path)
    ap.add_argument("--catalogue", required=True, type=Path)
    ap.add_argument("--catalogue-md", required=True, type=Path)
    ap.add_argument("--out-json", required=True, type=Path)
    ap.add_argument("--out-md", required=True, type=Path)
    a = ap.parse_args(argv)
    try:
        inputs = [a.catalogue, a.catalogue_md, a.materials, a.build_dir / "build-report.json",
                  a.build_dir / "checks.json"]
        outs = [a.out_json, a.out_md]
        build_root = os.path.normcase(os.path.realpath(a.build_dir))
        if _same(*outs) or any(_same(o, i) for o in outs for i in inputs) or any(
                os.path.commonpath([build_root, os.path.normcase(os.path.realpath(o))]) == build_root
                for o in outs):
            raise ValueError("an output path aliases an input or the other output")
        gen = build_generated(load_build(a.build_dir), parse_rows(a.approve), _read(a.materials),
                              decision=a.decision)
        catalogue = _read(a.catalogue)
        if not isinstance(catalogue.get("entries"), list):
            raise ValueError("catalogue.json without entries")
        clash = {e["id"] for e in catalogue["entries"]} & {e["id"] for e in gen["generated"]}
        if clash:
            raise ValueError(f"generated ids clash with scan entries {sorted(clash)}")
        catalogue.update(gen)
        md = merge_md(a.catalogue_md.read_text(encoding="utf-8"), render_md(gen))
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for path, text in ((a.out_json, dump_catalogue_json(catalogue)), (a.out_md, md)):
        path.with_name(path.name + ".partial").write_text(text, encoding="utf-8", newline="\n")
    for path in (a.out_json, a.out_md):
        os.replace(path.with_name(path.name + ".partial"), path)
    print(f"generated {len(gen['generated'])} entries, dropped rows {[d['row'] for d in gen['generated_dropped']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
