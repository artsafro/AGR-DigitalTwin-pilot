"""Build the library-wide MAF material ID list from extracted FBX material data.

new-case: library-wide MAF material ID proposal (cluster near-duplicates, classify
solid/patterned/placeholder, seed names/colours from PR #414 and the source `ID_N`
scheme) for Artem's one-time approval.

Inputs (all read-only, never modified):
- `--materials`: the output of `tools/library/maf_material_extract.py`
  (`fbx_materials.json`): per exported FBX, each material's base colour and texture refs.
- `--catalogue`: `library/maf/catalogue.json` (931 entries; used for the entry count and
  the source provenance hashes).
- `--seed`: `jobs/VATUTINO-SITE/maf/site-maf-set.json` (PR #414): the four already-used
  site atlas names/colours, kept as authoritative library-wide candidates.
- `--ral`: `tools/materials/ral_classic.json` (display approximations).

Outputs (refuse to overwrite without `--overwrite`):
- `--out-json` / `--out-md` / `--out-html` (`library/maf/material_ids.json`,
  `.md`, and the `material_contact_sheet.html`).

Rules (documented so Artem reviews the proposal, not just its output):
- A source material with any texture image is *patterned*; keyed by canonical texture
  stems (basename, lower-cased, `.1001`-style and extension stripped).
- A solid material with a semantic source name (see `_SEEDS`) is a real *solid*
  candidate named by that source; its colour is the seed colour or the FBX probe.
- A solid material is a *placeholder* (a colour-coded part marker, never assigned an id)
  when: its colour is a bright code marker (max channel >= 0.7 and min <= 0.35), or its
  name is a bare integer slot, or its colour is a 3ds Max default diffuse grey
  (#808080 / #969696 / #CCCCCC) with a generic auto name ("Material #N").
- Remaining solids are real candidates keyed by colour; near-black shades merge into
  `cap_black` (RAL 9005) and the dark-brown shade into `wood_dark`.
- The four site atlas materials already used in PR #414 (`_KNOWN_IDS`) are always listed
  as candidates even though no raw library material is literally named after them.
- Every merged group lists `merged_sources`; placeholders are reported with counts and
  sources, never silently dropped. Every candidate id has `status: "proposed"`; nothing
  is reassigned in the library.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# --- Curated proposal ---------------------------------------------------------
# (name regex, id, short name, kind, colour hex or None, texture stems or None)
# Applied in order; the first matching regex wins for a source material name.
# `color` is authoritative when non-None (PR #414 / RAL); None -> probe / texture.
_SEEDS = [
    # Source `ID_N` scheme (already present in the Max scene).
    (r"^ID_1_RAL\s*9005$", "cap_black", "cap_black", "patterned", "#0A0A0A", ["id_1_ral 9005"]),
    (r"^ID_2\s*Лиственница", "wood_larch_dark", "wood_larch_dark", "patterned", None, ["id_2_лиственница_черная_f"]),
    (r"^ID_5_Сетка$", "steel_mesh", "steel_mesh", "patterned", None, ["id_5_сетка_d", "id_5_сетка_o"]),
    # Semantic solid names -> solid families (FBX colour is a probe / default).
    (r"^нержа$", "steel_stainless", "steel_stainless", "solid", None, None),
    (r"^СЕРЫЕ\s*ЗАКЛАДНЫЕ", "steel_embed_grey", "steel_embed_grey", "solid", None, None),
    (r"^фанера$", "wood_plywood", "wood_plywood", "solid", None, None),
    (r"^NATURE\s*ДЕРЕВО", "wood_nature", "wood_nature", "solid", None, None),
    (r"^Oak\s*Matt", "wood_oak_matt", "wood_oak_matt", "solid", None, None),
    (r"^Balki-wood", "wood_balki", "wood_balki", "solid", None, None),
    (r"^Bronze_Brushed", "metal_bronze", "metal_bronze", "solid", None, None),
    (r"^Plastic_Black_Matte", "plastic_black_matte", "plastic_black_matte", "solid", None, None),
    (r"^Hamut$", "cap_clamp", "cap_clamp", "solid", None, None),
    (r"^Kolpak$", "cap_black", "cap_black", "solid", "#0A0A0A", None),
    (r"^Osn$", "cap_black", "cap_black", "solid", "#0A0A0A", None),
    (r"^черный\s*мат", "cap_black", "cap_black", "solid", "#0A0A0A", None),
    (r"^Стул_Опорный", "cap_black", "cap_black", "solid", "#0A0A0A", None),
    (r"^Light$", "grey_light", "grey_light", "solid", None, None),
    (r"^серый$", "grey", "grey", "solid", None, None),
]

# FBX-observed hexes merged into a named family (near-black into cap_black, the
# light-grey steel tone into steel_light_grey). Colour-only near-duplicate merge.
_FAMILY_HEX = {
    "#000000": "cap_black",
    "#040405": "cap_black",
    "#080808": "cap_black",
    "#090C0D": "cap_black",
    "#0A0A0A": "cap_black",
    "#140C38": "cap_black",
    "#1D1108": "wood_dark",
}

# Authoritative colours for the named families (RAL display approximation / PR #414).
_FAMILY_COLOR = {
    "cap_black": "#0A0A0A",           # RAL 9005
    "wood_dark": "#1D1108",           # FBX probe (dark wood)
}

# Site atlas materials already used and approved in PR #414. They are semantic IDs the
# site schedule assigns from the library's placeholder materials; the raw library carries
# no material literally named this, so they are added as candidates with no raw count.
_KNOWN_IDS = [
    {"id": "steel_ral7047", "name": "steel_ral7047", "kind": "solid", "color": "#D0D0D0",
     "note": "site atlas (PR #414): schedule steel, powder coat RAL 7047"},
    {"id": "larch_light_oak", "name": "larch_light_oak", "kind": "solid", "color": "#C49A6C",
     "note": "site atlas (PR #414): schedule larch, oil + lacquer 'light oak'"},
    {"id": "hpl_satin_wood", "name": "hpl_satin_wood", "kind": "solid", "color": "#B4825A",
     "note": "site atlas (PR #414): schedule *T3510/26 HPL 'satin wood'"},
    {"id": "rope_pp", "name": "rope_pp", "kind": "solid", "color": "#7A7A7A",
     "note": "site atlas (PR #414): schedule *T3510/28 polypropylene rope"},
]

# 3ds Max default diffuse greys: colour carries no appearance information.
_DEFAULT_GREY = {"#808080", "#969696", "#CCCCCC"}
_GENERIC_NAME = re.compile(r"^(?:Material\s*#?\d+.*|\d+\s*-\s*Default.*|_auto_\d+.*|Me)$")

# Colour-coding markers: the library's per-part placeholder colours.
def _is_placeholder_hex(hexc: str) -> bool:
    r = int(hexc[1:3], 16) / 255.0
    g = int(hexc[3:5], 16) / 255.0
    b = int(hexc[5:7], 16) / 255.0
    return max(r, g, b) >= 0.7 and min(r, g, b) <= 0.35


def _tex_stems(filepaths):
    stems = []
    for fp in filepaths:
        stem = Path(fp).name.lower()
        stem = re.sub(r"\.\d+\.(png|jpg|tga|bmp)$", "", stem)
        stem = re.sub(r"\.(png|jpg|tga|bmp)$", "", stem)
        if stem in {"", ".", ".."}:
            continue  # broken/relative texture reference (e.g. fbx\..\..)
        stems.append(stem)
    return tuple(sorted(set(stems)))


def _seed_for(name: str):
    for regex, cid, short, kind, color, stems in _SEEDS:
        if re.search(regex, name, re.IGNORECASE):
            return {"id": cid, "name": short, "kind": kind, "color": color, "texture_stems": list(stems) if stems else None}
    return None


def classify(name: str, hexc, texture_filepaths):
    """Classify one source material into (kind, key, seed).

    kind is ``"solid"``, ``"patterned"`` or ``"placeholder"``; `key` is the merge
    identity; `seed` is the matched curated rule or None.
    """
    seed = _seed_for(name)
    stems = _tex_stems(texture_filepaths) if texture_filepaths else None
    if texture_filepaths and not stems:
        # Textured but every reference is broken/unresolved: one group keyed by that fact.
        return ("patterned", "pattern:unresolved", seed)
    if stems:
        if seed and seed["texture_stems"]:
            return ("patterned", seed["id"], seed)
        return ("patterned", "pattern:" + ",".join(stems), seed)
    # Solid.
    if seed:
        return ("solid", seed["id"], seed)
    if hexc and _is_placeholder_hex(hexc):
        return ("placeholder", hexc, seed)
    if re.fullmatch(r"\d{1,2}", name.strip()):
        return ("placeholder", hexc or "(none)", seed)
    if hexc in _DEFAULT_GREY and _GENERIC_NAME.match(name.strip()):
        return ("placeholder", hexc, seed)
    fam = _FAMILY_HEX.get(hexc) if hexc else None
    if fam:
        return ("solid", fam, {"id": fam, "name": fam, "kind": "solid",
                               "color": _FAMILY_COLOR.get(fam), "texture_stems": None})
    return ("solid", "solid:" + (hexc or "unknown"), seed)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", required=True)
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--seed", required=True)
    ap.add_argument("--ral", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-html", required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    outs = [Path(args.out_json), Path(args.out_md), Path(args.out_html)]
    if len({o.resolve() for o in outs}) != 3:
        raise SystemExit("output paths must be distinct: "
                         + ", ".join(str(o) for o in outs))
    ins = {Path(args.materials).resolve(), Path(args.catalogue).resolve(),
           Path(args.seed).resolve(), Path(args.ral).resolve()}
    for o in outs:
        if o.resolve() in ins:
            raise SystemExit("output path resolves to an input: " + str(o))
    if any(o.exists() for o in outs) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite to replace: " + ", ".join(str(o) for o in outs if o.exists()))

    materials = json.loads(Path(args.materials).read_text(encoding="utf-8"))
    catalogue = json.loads(Path(args.catalogue).read_text(encoding="utf-8"))
    seed_set = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    ral = json.loads(Path(args.ral).read_text(encoding="utf-8"))

    for rec in materials.get("files", []):
        for mat in rec.get("materials", []):
            h = mat.get("hex")
            if h is not None and (not isinstance(h, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", h)):
                raise SystemExit("invalid hex colour %r on material %r" % (h, mat.get("name")))

    # Aggregate source materials: key -> (names, hexes, texture filepaths, maf ids).
    src = {}
    for rec in materials["files"]:
        fbx = rec.get("fbx", "")
        parts = fbx.split("_")
        maf_id = "_".join(parts[:2]) if len(parts) >= 2 else fbx
        for mat in rec.get("materials", []):
            name = (mat.get("name") or "").strip() or "(none)"
            g = src.setdefault(name, {"hex": {}, "tex": set(), "mafs": set()})
            g["mafs"].add(maf_id)
            if mat.get("hex"):
                g["hex"][mat.get("hex")] = g["hex"].get(mat.get("hex"), 0) + 1
            for t in mat.get("textures", []):
                g["tex"].add(t["filepath"])

    # Classify and group by merge key.
    groups = {}   # key -> {"id", "name", "kind", "color", "textures", "sources", "mafs"}
    placeholders = {}  # hex -> {"mafs", "sources"}
    for name, g in src.items():
        hexc = max(g["hex"], key=g["hex"].get) if g["hex"] else None
        kind, key, seed = classify(name, hexc, list(g["tex"]))
        if kind == "placeholder":
            p = placeholders.setdefault(hexc or "(none)", {"mafs": set(), "sources": set()})
            p["mafs"] |= g["mafs"]
            p["sources"].add(name)
            continue
        grp = groups.setdefault(key, {
            "id": key, "name": key, "kind": kind, "color": None,
            "texture_stems": [], "sources": set(), "mafs": set(), "color_source": None,
        })
        grp["sources"].add(name)
        grp["mafs"] |= g["mafs"]
        if kind == "patterned":
            if seed and seed["texture_stems"]:
                grp["texture_stems"] = sorted(set(grp["texture_stems"]) | set(seed["texture_stems"]))
            else:
                grp["texture_stems"] = sorted(set(grp["texture_stems"]) | set(_tex_stems(list(g["tex"]))))
        if seed:
            grp["id"] = seed["id"]
            grp["name"] = seed["name"]
            if seed["color"]:
                grp["color"] = seed["color"]
                grp["color_source"] = "seed"
        if grp["color"] is None and hexc:
            grp["color"] = hexc
            grp["color_source"] = "fbx-default" if hexc in _DEFAULT_GREY else "fbx-probe"

    # Finalise groups into ordered candidate ids (solid first, then patterned).
    def cell_size(grp):
        if grp["kind"] == "patterned":
            return 128
        return 128 if len(grp["mafs"]) >= 100 else 64

    ids = []
    for key in sorted(groups, key=lambda k: (groups[k]["kind"] != "solid", -len(groups[k]["mafs"]))):
        g = groups[key]
        ids.append({
            "id": g["id"],
            "name": g["name"],
            "kind": g["kind"],
            "color": g["color"],
            "color_source": g["color_source"],
            "textures": g["texture_stems"],
            "maf_count": len(g["mafs"]),
            "atlas_cell": cell_size(g),
            "merged_sources": sorted(g["sources"]),
            "status": "proposed",
            "note": None,
        })

    # Site-approved semantic ids (PR #414) with no raw library source are still candidates.
    existing_ids = {i["id"] for i in ids}
    for kn in _KNOWN_IDS:
        if kn["id"] not in existing_ids:
            ids.append({**kn, "textures": [], "maf_count": 0, "atlas_cell": 64,
                        "merged_sources": [], "status": "proposed", "color_source": "seed"})

    placeholders_out = [
        {"hex": hexc, "maf_count": len(p["mafs"]), "sources": sorted(p["sources"]), "status": "placeholder"}
        for hexc, p in sorted(placeholders.items(), key=lambda kv: -len(kv[1]["mafs"]))
    ]

    catalogue_entries = len(catalogue.get("entries", []))
    result = {
        "schema": "library-maf-material-ids",
        "version": "v001",
        "scope": "proposal for Artem's one-time approval; nothing reassigned in the library",
        "generated_by": "tools/library/maf_material_ids.py",
        "extraction": {
            "command": (
                "blender --background --factory-startup --python-exit-code 1 "
                "--python tools/library/maf_material_extract.py -- <FBX_DIR> <fbx_materials.json>"
            ),
            "command_then": (
                "uv run python tools/library/maf_material_ids.py --materials <fbx_materials.json> "
                "--catalogue library/maf/catalogue.json --seed jobs/VATUTINO-SITE/maf/site-maf-set.json "
                "--ral tools/materials/ral_classic.json "
                "--out-json library/maf/material_ids.json --out-md library/maf/material_ids.md "
                "--out-html library/maf/material_contact_sheet.html"
            ),
            "input_hashes": {
                "library/maf/catalogue.json": sha256_file(Path(args.catalogue)),
                "jobs/VATUTINO-SITE/maf/site-maf-set.json": sha256_file(Path(args.seed)),
                "tools/materials/ral_classic.json": sha256_file(Path(args.ral)),
                args.materials: sha256_file(Path(args.materials)),
                "source_max (audit.json)": None,
                "source_blend (audit.json)": None,
            },
        },
        "counts": {
            "library_maf_entries": catalogue_entries,
            "candidate_ids": len(ids),
            "solid_ids": sum(1 for i in ids if i["kind"] == "solid"),
            "patterned_ids": sum(1 for i in ids if i["kind"] == "patterned"),
            "placeholder_groups": len(placeholders_out),
            "placeholder_maf_uses": sum(p["maf_count"] for p in placeholders_out),
            "seed_ids_from_site_set": len(seed_set.get("atlas", {}).get("materials", [])),
        },
        "materials": ids,
        "placeholders": placeholders_out,
    }
    # Source hashes come from the library audit (no DCC read here).
    audit = None
    audit_path = Path(args.catalogue).parent / "audit.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        for sh in audit.get("source_hashes", []):
            leaf = Path(sh["path"]).name
            result["extraction"]["input_hashes"]["source_max (audit.json)" if leaf.endswith(".max") else "source_blend (audit.json)"] = sh["sha256_before"]

    for o in outs:
        o.parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    Path(args.out_md).write_text(render_md(result), encoding="utf-8", newline="\n")
    Path(args.out_html).write_text(render_html(result), encoding="utf-8", newline="\n")
    print("AGR_MAT_IDS", len(ids), "ids", len(placeholders_out), "placeholder groups", args.out_json)
    return 0


def render_md(result) -> str:
    lines = [
        "# MAF library material IDs (proposal)",
        "",
        f"Schema `{result['schema']}` version `{result['version']}`. {result['scope']}.",
        f"Generated by `{result['generated_by']}`.",
        "",
        "Counts: **%d** candidate ids (%d solid, %d patterned); **%d** placeholder groups "
        "(%d MAF uses) reported, not assigned." % (
            result["counts"]["candidate_ids"], result["counts"]["solid_ids"],
            result["counts"]["patterned_ids"], result["counts"]["placeholder_groups"],
            result["counts"]["placeholder_maf_uses"],
        ),
        "",
        "| id | name | kind | colour / texture | MAFs | cell | status | merged sources |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in result["materials"]:
        if m["kind"] == "solid":
            src = m["color"] or "(unmeasured)"
        else:
            src = ", ".join(m["textures"]) if m["textures"] else "(unresolved texture)"
        lines.append("| `%s` | %s | %s | %s | %d | %dx%d | %s | %s |" % (
            m["id"], m["name"], m["kind"], src, m["maf_count"],
            m["atlas_cell"], m["atlas_cell"], m["status"],
            ", ".join("`%s`" % s for s in m["merged_sources"]),
        ))
    if result["placeholders"]:
        lines += ["", "## Placeholders (colour-coded part markers, not assigned)",
                  "", "| colour | MAF uses | sources |", "|---|---|---|"]
        for p in result["placeholders"]:
            lines.append("| %s | %d | %s |" % (p["hex"], p["maf_count"], ", ".join("`%s`" % s for s in p["sources"])))
    notes = [m for m in result["materials"] if m.get("note")]
    if notes:
        lines += ["", "## Notes", ""]
        for m in notes:
            lines.append("- `%s`: %s" % (m["id"], m["note"]))
    lines += ["", "## Reproducibility", "", "```bash",
              result["extraction"]["command"], result["extraction"]["command_then"], "```", "",
              "Input hashes:", ""]
    for k, v in result["extraction"]["input_hashes"].items():
        lines.append("- `%s`: `%s`" % (k, v))
    lines.append("")
    return "\n".join(lines)


def render_html(result) -> str:
    rows = []
    for m in result["materials"]:
        if m["kind"] == "solid" and m["color"]:
            sw = '<span style="display:inline-block;width:40px;height:24px;background:%s;border:1px solid #999"></span>' % m["color"]
            src = m["color"]
        else:
            tint = m["color"] or "#888888"
            sw = '<span style="display:inline-block;width:40px;height:24px;background:%s;border:1px solid #999"></span>' % tint
            src = ", ".join(m["textures"]) if m["textures"] else "(texture)"
        rows.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s %s</td><td>%d</td><td>%d&times;%d</td><td>%s</td></tr>" % (
            m["id"], m["name"], m["kind"], sw, src, m["maf_count"],
            m["atlas_cell"], m["atlas_cell"], m["status"]))
    ph = []
    for p in result["placeholders"]:
        sw = '<span style="display:inline-block;width:40px;height:24px;background:%s;border:1px solid #999"></span>' % (p["hex"] if p["hex"] else "#fff")
        ph.append("<tr><td>%s %s</td><td>%d</td><td>%s</td></tr>" % (
            sw, p["hex"], p["maf_count"], ", ".join("`%s`" % s for s in p["sources"])))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>MAF library material IDs</title></head><body>"
        "<h1>MAF library material IDs (proposal)</h1>"
        "<p>%d candidate ids; %d placeholder groups (not assigned).</p>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr><th>id</th><th>name</th><th>kind</th><th>swatch / source</th><th>MAFs</th><th>cell</th><th>status</th></tr>"
        "%s</table>"
        "<h2>Placeholders</h2>"
        "<table border='1' cellspacing='0' cellpadding='4'><tr><th>swatch / colour</th><th>MAF uses</th><th>sources</th></tr>%s</table>"
        "</body></html>"
    ) % (result["counts"]["candidate_ids"], result["counts"]["placeholder_groups"],
         "".join(rows), "".join(ph))


if __name__ == "__main__":
    raise SystemExit(main())
