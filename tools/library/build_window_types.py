"""Build library/windows/window_types.json (issue #4) from the user's window library and KPP1.

    uv run python tools/library/build_window_types.py --type-map <type-map.json> \
        --library-v001 <curtain-types.json> --kpp1-twin <twin-data.json> --kpp1-spec <spec.json> \
        --output library/windows/window_types.json
    # K2 quality report + preview sheet «было → стало» of the library by library/windows/standard.json (#1024 J):
    uv run python tools/library/build_window_types.py --quality-of library/windows/window_types.json \
        --quality library/windows/quality.json --sheet <new>.png
    # add or rebuild a job census without the user-project inputs (existing entries kept as built):
    uv run python tools/library/build_window_types.py --base library/windows/window_types.json \
        --census-source library/windows/sources/elv-tc-vpm-census-v001.json --output library/windows/window_types.json

Pattern: none — library tooling, not a building node (REVIEW_CHECKLIST Q1: new-case).

Sources (read only; the user's .blend is not opened):
- SOSH1150 typology v003 (`jobs/REVIT-OPENINGS/outputs/openings-v003/type-map.json` in the user's
  project folder): 11 types and 6 size variants with their pane layouts;
- the untyped curtain assemblies CW_021 / CW_022 from `library-v001/curtain-types.json`;
- KPP1 facade windows from the Revit spec (spec v0.3) and their pane layout from the Revit export;
- the window file Win_Typical.max (`library/windows/sources/win-typical-max-v001.json`, read from
  3ds Max without changing it): frame extent, glass and opaque infill per object.

Duplicates (user decision 2026-10-09 [D140]): the same subdivision — fields, transoms, panes and pane
layout within SAME_M — and the same size within SAME_M are one type; the later entry keeps its
row and points to the first with `same_as`. Names are form + size, no project.

User decision 2026-10-09 [D140]: every entry is `unconfirmed` until the user confirms and names it — the
user's decisions are kept in library/windows/confirmations.json and applied here;
handing is null; CW_021, CW_022 and D04 are kept as rows marked not typed. Sections are the
vertical fields of a type, transoms the horizontal divisions of its most divided field, both from
the pane layout; opening sashes are not in the sources (null).
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

GAP_M = 0.02             # panes closer than this along an axis are in one field / row
SAME_M = 0.02            # same type: size and pane layout within 2 cm (user decision 2026-10-09 [D140])
FIELDS = {1: "однопольное", 2: "двухпольное", 3: "трёхпольное", 4: "четырёхпольное", 5: "пятипольное", 6: "шестипольное"}


def _clusters(ranges):
    """Merge intervals (a, b) that overlap or touch within GAP_M; returns the merged intervals."""
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + GAP_M:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def layout(panes, opaque=()):
    """Sections and transoms of a pane layout [[x0, z0, x1, z1], ...] (metres from the bottom left);
    `opaque` are the opaque infill rectangles among the panes."""
    if not panes:
        return None, None
    columns = _clusters([(p[0], p[2]) for p in panes])
    transoms = 0
    for a, b in columns:
        rows = _clusters([(p[1], p[3]) for p in panes if p[0] >= a - GAP_M and p[2] <= b + GAP_M])
        transoms = max(transoms, len(rows) - 1)
    # fields: the columns of the row under the fanlight, not the columns over the whole height (user rule
    # 2026-10-09: a full-width fanlight never merges the leaves under it, and a fanlight's own division never
    # adds fields). Drop only opaque-only bands below the lowest glazed band (lower panels), retaining every
    # band at or above it including an opaque upper fanlight (issue #45). The top remaining band is the fanlight
    # whatever its infill or height; fields are those of the tallest remaining band under it (or the sole band).
    bands = _clusters([(p[1], p[3]) for p in panes])
    first_glazed = next(
        (i for i, (a, b) in enumerate(bands)
         if any(p not in opaque and p[1] >= a - GAP_M and p[3] <= b + GAP_M for p in panes)),
        None,
    )
    remaining = bands[first_glazed:] if first_glazed is not None else bands
    a, b = max(remaining[:-1] or remaining, key=lambda band: band[1] - band[0])
    sections = len(_clusters([(p[0], p[2]) for p in panes if p[1] >= a - GAP_M and p[3] <= b + GAP_M]))
    return sections, transoms


def entry(id_, name, role, width, height, panes, *, source, typed=True, note=None, variant_of=None, **extra):
    sections, transoms = layout(panes)
    out = {"id": id_, "name": name, "status": "unconfirmed", "typed": typed, "role": role,
           "width_m": round(width, 3), "height_m": round(height, 3), "sections": sections, "transoms": transoms,
           "sashes": None, "handing": None, "panes": len(panes) if panes else None,
           "panes_m": [[round(c, 3) for c in p] for p in panes] if panes else None, "variant_of": variant_of,
           "source": source}
    out.update(extra)
    if note:
        out["note"] = note
    return out


def _mm(v):
    return round(v * 1000)


def max_types(source, path):
    """Window types of a 3ds Max window file (library/windows/sources/*.json): frame extent, glass,
    opaque infill; name by form + size, no project."""
    out, prefix = [], source["id_prefix"]
    for n, o in enumerate(source["objects"], 1):
        door = "Дверь" in o["object"] or "Д_" in o["object"]
        balcony = door and "Балкон" in o["object"]       # a balcony door and window in one frame (user 2026-10-09 [D140])
        fields = o["glass_m"] + o["opaque_m"]
        sections, transoms = layout(fields, o["opaque_m"])
        words = FIELDS.get(sections, f"{sections}-польн")
        if balcony:
            base = f"Балконный блок {words[:-2]}ый"
        elif door:
            base = f"Дверь {'остеклённая ' if o['glass_m'] else ''}{words[:-2]}ая"
        else:
            base = f"Окно {words}"
        extra = " с глухой фрамугой" if o["opaque_m"] else (" с фрамугой" if transoms else "")
        name = f"{base}{extra} {_mm(o['width_m'])}×{_mm(o['height_m'])}"
        out.append(entry(
            f"{prefix}-{n:02d}", name, "balcony_block" if balcony else "door" if door else "window",
            o["width_m"], o["height_m"], o["glass_m"],
            source={"object": Path(source["source"]["file"]).name, "file": Path(path).as_posix(),
                    "max_object": o["object"], "occurrences": None},
            opaque_m=o["opaque_m"] or None))
        if sections is not None:                  # members of the layout include the opaque infill
            out[-1]["sections"], out[-1]["transoms"] = sections, transoms
    return out


CENSUS_EXTRA = ("grid", "inserts", "drum", "sill_m", "opaque_infill")
EXTENSIONS_NOTE = (
    "Optional fields (window-source-census/1): `frame_finish` holds the frame colour; `grid` makes a curtain type "
    "parametric — the entry is one module (bay) of width module_m whose panes are expanded from grid.rows and "
    "repeated along the wall; `inserts` place other types (doors) in a curtain opening by rect_m; `drum` "
    "describes a revolving door (plan diameters, door and canopy heights; panes_m null); roles `gate` and "
    "`revolving_door` are census roles.")


def grid_panes(grid):
    """Glass and opaque rectangles of one curtain-wall module from its rows (mullion centred on the module edges)."""
    x0, x1 = grid["mullion_m"] / 2, grid["module_m"] - grid["mullion_m"] / 2
    glass, opaque = [], []
    for row in grid["rows"]:
        (glass if row["infill"] == "glass" else opaque).append([round(x0, 3), row["z0"], round(x1, 3), row["z1"]])
    return glass, opaque


def census_types(source, path):
    """Types of a job census (library/windows/sources/*-census-*.json, schema window-source-census/1): sizes and
    pane layouts measured from the job's FBX and album; ids <prefix>-NN in file order; names form + size."""
    if source.get("schema") != "window-source-census/1":
        raise SystemExit(f"not a census source: {path}")
    out, prefix, src = [], source["id_prefix"], source["source"]
    for n, t in enumerate(source["types"], 1):
        glass, opaque = (grid_panes(t["grid"]) if t.get("grid") else (t["glass_m"], t["opaque_m"]))
        e = entry(f"{prefix}-{n:02d}", t["name"], t["role"], t["width_m"], t["height_m"], glass,
                  source={"object": src["job"], "file": Path(path).as_posix(), "census_key": t["key"],
                          **t["provenance"], "occurrences": t["occurrences"]},
                  variant_of=t.get("variant_of"), infill=t["infill"], frame_finish=t["frame_finish"],
                  opaque_m=opaque or None, note=t.get("note"),
                  **{k: t[k] for k in CENSUS_EXTRA if k in t})
        if glass or opaque:
            e["sections"], e["transoms"] = layout(glass + opaque, opaque)
        e["unconfirmed"] = {
            "sashes": {"candidate": t["sashes_candidate"], "reason": t["sashes_reason"], "source": Path(path).as_posix()},
            "handing": {"candidate": None, "reason": "handing is per placement (the FBX has L and R instances)"}}
        out.append(e)
    return out


def _near(u, v):
    """Within SAME_M, inclusive, in whole millimetres (no binary-float edge, PR #43 review 1)."""
    return abs(round(u * 1000) - round(v * 1000)) <= round(SAME_M * 1000)


def _same(a, b):
    """Same subdivision — fields, transoms, glass and opaque infill with their layout — and size, all
    within SAME_M (user decision 2026-10-09 [D140])."""
    if (a["sections"], a["transoms"], a["panes"]) != (b["sections"], b["transoms"], b["panes"]):
        return False
    if not (_near(a["width_m"], b["width_m"]) and _near(a["height_m"], b["height_m"])):
        return False
    for key in ("panes_m", "opaque_m"):
        if not _matched(a.get(key) or [], b.get(key) or []):
            return False
    return True


def _matched(pa, pb):
    """Every rectangle of pa has its own partner in pb within SAME_M (one to one, augmenting paths),
    so a 1 mm shift never reorders the pairing (PR #43 review 2)."""
    if len(pa) != len(pb):
        return False
    ok = [[j for j, q in enumerate(pb) if all(_near(u, v) for u, v in zip(p, q))] for p in pa]
    owner = {}

    def augment(i, seen):
        for j in ok[i]:
            if j not in seen:
                seen.add(j)
                if j not in owner or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    return all(augment(i, set()) for i in range(len(pa)))


def dedupe(types):
    """Each entry that repeats an earlier typed one points to it with same_as."""
    for i, t in enumerate(types):
        first = next((u for u in types[:i] if u["typed"] and not u.get("same_as") and _same(u, t)), None)
        t["same_as"] = first["id"] if (first and t["typed"]) else None
    return types


def sosh(type_map, curtain_types):
    src = {"object": "SOSH1150", "file": "jobs/REVIT-OPENINGS/outputs/openings-v003/type-map.json (user project)"}
    out = []
    for t in type_map["types"] + type_map["size_variants"]:
        untyped = t["id"] == "D04"
        out.append(entry(
            t["id"], t["title"], t["role"], t["width_m"], t["height_m"], t["panes_m"],
            source={**src, "fbx": t["source"], "merged": t["merged_sources"], "pdf_pages": t["pdf_pages"],
                    "match": t["match"], "occurrences": t["represented_occurrences"]},
            typed=not untyped, variant_of=t.get("family"), infill=t["infill"], frame_finish=t["frame_finish"],
            note="не типизирован: взят из FBX как пример полотна, к месту на фасаде не привязан" if untyped else None))
    by_id = {c["id"]: c for c in curtain_types}
    notes = {"CW_021": "не типизирован: особое членение (3 панели, 15 импостов, 1 окно)",
             "CW_022": "не типизирован: неоднозначные наложения панелей в исходнике; габарит по bbox, не проверен"}
    for cid in ("CW_021", "CW_022"):
        c = by_id[cid]
        dims = sorted(c["dimensions"], reverse=True)
        out.append(entry(cid, None, "curtain", dims[0], dims[1] if cid == "CW_021" else c["dimensions"][2], None,
                         source={**src, "file": "jobs/REVIT-OPENINGS/outputs/library-v001/curtain-types.json (user project)",
                                 "fbx": cid, "occurrences": len(c.get("placements", [])), "bbox_m": c["dimensions"],
                                 "counts": c.get("counts")},
                         typed=False, note=notes[cid]))
    return out


def kpp1(twin_index, spec_path):
    """Facade window types of KPP1 (Revit spec), with the pane layout of the Revit export."""
    from dt_ai.spec import revit_twin
    dump = revit_twin.load(twin_index)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    groups = Counter()
    for f in spec["floors"]:
        for o in f["openings"]:
            if o.get("kind") == "window":
                groups[(o["w_m"], o["h_m"], o.get("panes"), o.get("glass_w"), o.get("glass_h"), o.get("level_to"))] += 1
    out = []
    for n, ((w, h, panes, gw, gh, level_to), count) in enumerate(sorted(groups.items(), key=lambda kv: -kv[1]), 1):
        layout_m = None
        for o in dump["openings"]:
            if (o["kind"] == "window" and o.get("panes") == panes and abs(math.dist(o["p0"], o["p1"]) - w) <= 0.01
                    and abs((o["z1"] - o["z0"]) - h) <= 0.01 and o.get("glass")):
                ux, uy = [(b - a) / math.dist(o["p0"], o["p1"]) for a, b in zip(o["p0"], o["p1"])]
                along = [sorted(((g[0] - o["p0"][0]) * ux + (g[1] - o["p0"][1]) * uy,
                                 (g[2] - o["p0"][0]) * ux + (g[3] - o["p0"][1]) * uy)) for g in o["glass"]]
                layout_m = sorted([a[0], g[4] - o["z0"], a[1], g[5] - o["z0"]] for a, g in zip(along, o["glass"]))
                break
        out.append(entry(
            f"KPP1-W{n:02d}", None, "window", w, h, layout_m,
            source={"object": "tec26-kpp1", "file": f"{Path(spec_path).as_posix()} (spec v0.3, Revit path)",
                    "revit": "ADSK_Витраж_Без разрезки_Импосты 50х100 frame wall with MEP_Окно AGS68 windows",
                    "occurrences": count, "glass_m": [gw, gh], "across_level": level_to},
            note="кандидат из KPP1-spec: проём = стена-рамка (дыра с рамой), стекло = окна AGS68"))
    return out


def confirm(types, confirmations):
    """Apply the user's decisions (status, name) to the built entries; an unknown id is an error."""
    by_id = {t["id"]: t for t in types}
    for d in confirmations["decisions"]:
        if d["id"] not in by_id:
            raise SystemExit(f"confirmation for unknown type {d['id']}")
        t = by_id[d["id"]]
        t["status"] = d["status"]
        if d.get("name"):
            t["name"] = d["name"]
        t["decision"] = {"by": d["by"], "date": d["date"], **({"note": d["note"]} if d.get("note") else {})}
    return types


def _windowgen():
    """adapters/max/agr_tools/windowgen_core.py (stdlib), the generator of win.generate (#1024 K2)."""
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "adapters" / "max" / "agr_tools" / "windowgen_core.py"
    spec = importlib.util.spec_from_file_location("agr_tools_windowgen_core_lib", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def quality(types_path, quality_path=None, sheet_path=None, standard_path=None):
    """K2: pass / quarantine / duplicate and the face axis of every type by the window standard; the quality file
    and the preview sheet are written only when asked (never over an existing file: a new sheet is a new vNNN)."""
    wg = _windowgen()
    types_path = Path(types_path)
    std_path = Path(standard_path) if standard_path else types_path.with_name("standard.json")
    types = json.loads(types_path.read_text(encoding="utf-8"))["types"]
    standard = wg.load_standard(json.loads(std_path.read_text(encoding="utf-8")))
    report = wg.library_report(types, standard)
    if quality_path:
        Path(quality_path).parent.mkdir(parents=True, exist_ok=True)
        Path(quality_path).write_text(wg.report_json(report), encoding="utf-8")
    if sheet_path:
        Path(sheet_path).parent.mkdir(parents=True, exist_ok=True)
        with Path(sheet_path).open("xb") as f:
            f.write(wg.sheet_png(types, standard, report))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quality-of", type=Path, help="window_types.json: write only the K2 quality report / sheet")
    ap.add_argument("--quality", type=Path, help="with --quality-of: quality.json to write")
    ap.add_argument("--sheet", type=Path, help="with --quality-of: preview sheet PNG to create (never overwritten)")
    ap.add_argument("--standard", type=Path, help="with --quality-of: standard.json (default: next to the types)")
    ap.add_argument("--type-map", type=Path)
    ap.add_argument("--library-v001", type=Path)
    ap.add_argument("--kpp1-twin", type=Path)
    ap.add_argument("--kpp1-spec", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--max-source", type=Path, action="append", default=[],
                    help="a 3ds Max window source (library/windows/sources/*.json); repeatable")
    ap.add_argument("--census-source", type=Path, action="append", default=[],
                    help="a job census source (library/windows/sources/*-census-*.json); repeatable")
    ap.add_argument('--sashes', type=Path, action='append', default=[],
                    help='reapply unconfirmed #246 sash readings AFTER the catalogue rebuild')
    ap.add_argument("--base", type=Path,
                    help="an existing window_types.json whose entries are kept as built (when the user-project inputs "
                         "are not on this machine); entries from the given census files are rebuilt")
    ap.add_argument("--confirmations", type=Path, default=Path(__file__).resolve().parents[2] / "library" / "windows" / "confirmations.json")
    args = ap.parse_args(argv)
    if args.quality_of:
        rep = quality(args.quality_of, args.quality, args.sheet, args.standard)
        print("window quality: {} -> {}".format(rep["counts"], args.quality or "-"))
        return
    if not args.output:
        raise SystemExit("--output is required (or --quality-of)")
    if not args.confirmations.exists():                 # never drop the user's decisions silently (PR #42 review 1)
        raise SystemExit(f"confirmations file not found: {args.confirmations}")
    if not args.base and not all((args.type_map, args.library_v001, args.kpp1_twin, args.kpp1_spec)):
        raise SystemExit("give --type-map, --library-v001, --kpp1-twin and --kpp1-spec, or --base")
    if args.sashes:
        protected = [p for p in (args.base, args.type_map, args.library_v001, args.kpp1_twin,
                                 args.kpp1_spec, args.confirmations) if p] + args.sashes + args.max_source + args.census_source
        if any(args.output.resolve() == p.resolve() or
               (args.output.exists() and p.exists() and args.output.samefile(p)) for p in protected):
            raise SystemExit('--output aliases an input; sash rebuild requires a new output')
        if args.output.exists():
            raise SystemExit('--output exists; sash rebuild requires a new output')
    max_sources, prefixes = [], set()
    for src in args.max_source:                           # one id space per source (PR #43 review 1)
        source = json.loads(src.read_text(encoding="utf-8"))
        if source["id_prefix"] in prefixes:
            raise SystemExit(f"max source given twice or prefix {source['id_prefix']} reused: {src}")
        prefixes.add(source["id_prefix"])
        max_sources.append((src, source))
    censuses = []
    for src in args.census_source:
        source = json.loads(src.read_text(encoding="utf-8"))
        if source["id_prefix"] in prefixes:
            raise SystemExit(f"census source given twice or prefix {source['id_prefix']} reused: {src}")
        prefixes.add(source["id_prefix"])
        censuses.append((src, source))
    note = ("Machine-readable window type list (archive/2026-11:docs/HARNESS_PLAN.md §6 (historical), issue #4). An entry is unconfirmed until "
            "the user confirms and names it (library/windows/confirmations.json); handing is null; sashes are not in "
            "the sources. Sizes are the rough opening with its frame (spec v0.3); panes_m are glass "
            "rectangles [x0, z0, x1, z1] from the bottom left of the opening. Built by "
            "tools/library/build_window_types.py.")
    if args.base:
        base = json.loads(args.base.read_text(encoding="utf-8"))
        rebuilt = {Path(src).as_posix() for src, _ in censuses}
        types = [t for t in base["types"] if t["source"].get("file") not in rebuilt]
        clash = {t["id"].split("-")[0] for t in types} & prefixes
        if max_sources or clash:
            raise SystemExit(f"--base keeps its entries; prefix already in the base: {sorted(clash) or 'max sources'}")
        note = base["note"]
    else:
        types = (sosh(json.loads(args.type_map.read_text(encoding="utf-8")),
                      json.loads(args.library_v001.read_text(encoding="utf-8")))
                 + kpp1(args.kpp1_twin, args.kpp1_spec))
        for src, source in max_sources:
            types += max_types(source, src)
    for src, source in censuses:
        types += census_types(source, src)
    if censuses and EXTENSIONS_NOTE not in note:
        note = f"{note} {EXTENSIONS_NOTE}"
    types = dedupe(types)
    types = confirm(types, json.loads(args.confirmations.read_text(encoding="utf-8")))
    doc = {"schema": "window-types/1", "note": note, "types": types}
    if args.sashes:
        from window_sashes import apply_sashes, _repo_path
        apply_sashes(doc, [(_repo_path(p), json.loads(p.read_text(encoding='utf-8'))) for p in args.sashes])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1) + '\n'
    if args.sashes:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    else:
        args.output.write_text(text, encoding='utf-8')
    print(f"window types: {len(types)} ({sum(t['status'] == 'confirmed' for t in types)} confirmed, "
          f"{sum(not t['typed'] for t in types)} not typed) -> {args.output}")


if __name__ == "__main__":
    main()
