"""Build the library-wide MAF material ID list from extracted FBX material data.

new-case: library-wide MAF material ID proposal (appearance-keyed clustering of
solid/patterned/placeholder materials, seeds from PR #414 and the source `ID_N`
scheme, source-backed preview swatches) for Artem's one-time approval.

Inputs (all read-only, never modified):
- `--materials`: the committed output of `tools/library/maf_material_extract.py`
  (`library/maf/fbx_materials.json`): per exported FBX, each material's base colour
  and full texture file references.
- `--catalogue`: `library/maf/catalogue.json` (931 entries; entry id / preview path /
  FBX path per MAF, used for coverage validation and swatch provenance).
- `--seed`: `jobs/VATUTINO-SITE/maf/site-maf-set.json` (PR #414): the four already-used
  site atlas names/colours, kept as authoritative library-wide candidates.
- `--ral`: `tools/materials/ral_classic.json` (display approximations).
- Implicit input: `<catalogue-dir>/audit.json` (read for source Max/Blend hashes).

Outputs (refuse to overwrite without `--overwrite`; never an input):
- `--out-json` / `--out-md` / `--out-html`.

Rules (documented so Artem reviews the proposal, not just its output):
- Coverage is fail-closed: every catalogue FBX must appear exactly once in the
  extraction, with no `error`, empty, duplicate or unknown record; otherwise the run
  exits nonzero and writes no approval output.
- Appearance is identity, never a name/basename/majority-colour: a source material is
  keyed by its full texture file references (not basenames) when textured, and by
  (name, colour) when solid. Merge happens only for demonstrated near-duplicates
  (same full texture set + same name, or an explicit `_SEEDS`/`_FAMILY_HEX` rule).
- A solid material with a semantic source name (see `_SEEDS`) is a real *solid*
  candidate named by that source; its colour is the seed colour or the FBX probe.
- A solid material is a *placeholder* (a colour-coded part marker, never assigned an
  id) when: its colour is a bright code marker, or its name is a bare integer slot, or
  its colour is a 3ds Max default diffuse grey with a generic auto name.
- Every candidate id has `status: "proposed"` and `texture_status` ("resolved" when a
  texture file exists, "unresolved" otherwise); nothing is reassigned in the library.
- Every merged group lists `merged_sources`; placeholders and unresolved texture refs
  are reported with counts and sources, never silently dropped.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

# --- Curated proposal ---------------------------------------------------------
# (name regex, id, short name, colour hex or None, note)
# Applied to a source material *name*; the id/name is a naming hint, never a merge
# key. `color` is authoritative when non-None (PR #414 / RAL); None -> FBX probe.
_SEEDS = [
    (r"^ID_1_RAL\s*9005$", "cap_black", "cap_black", "#0A0A0A",
     "source `ID_N` scheme: RAL 9005 cap"),
    (r"^ID_2\s*Лиственница", "wood_larch_dark", "wood_larch_dark", None,
     "source `ID_N` scheme: dark larch wood"),
    (r"^ID_5_Сетка$", "steel_mesh", "steel_mesh", None,
     "source `ID_N` scheme: steel mesh"),
    (r"^нержа$", "steel_stainless", "steel_stainless", None, None),
    (r"^СЕРЫЕ\s*ЗАКЛАДНЫЕ", "steel_embed_grey", "steel_embed_grey", None, None),
    (r"^фанера$", "wood_plywood", "wood_plywood", None, None),
    (r"^NATURE\s*ДЕРЕВО", "wood_nature", "wood_nature", None, None),
    (r"^Oak\s*Matt", "wood_oak_matt", "wood_oak_matt", None, None),
    (r"^Balki-wood", "wood_balki", "wood_balki", None, None),
    (r"^Bronze_Brushed", "metal_bronze", "metal_bronze", None, None),
    (r"^Plastic_Black_Matte", "plastic_black_matte", "plastic_black_matte", None, None),
    (r"^Hamut$", "cap_clamp", "cap_clamp", None, None),
    (r"^Kolpak$", "cap_black", "cap_black", "#0A0A0A", None),
    (r"^Osn$", "cap_black", "cap_black", "#0A0A0A", None),
    (r"^черный\s*мат", "cap_black", "cap_black", "#0A0A0A", None),
    (r"^Стул_Опорный", "cap_black", "cap_black", "#0A0A0A", None),
    (r"^Light$", "grey_light", "grey_light", None, None),
    (r"^серый$", "grey", "grey", None, None),
]

# FBX-observed hexes merged into a named family (near-black into cap_black, the
# dark-brown shade into wood_dark). Explicit colour near-duplicate merge.
_FAMILY_HEX = {
    "#000000": "cap_black",
    "#040405": "cap_black",
    "#080808": "cap_black",
    "#090C0D": "cap_black",
    "#0A0A0A": "cap_black",
    "#140C38": "cap_black",
    "#1D1108": "wood_dark",
}

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
_HASH_SUFFIX = re.compile(r"_[a-z0-9]{10,}$")


def _is_placeholder_hex(hexc: str) -> bool:
    r = int(hexc[1:3], 16) / 255.0
    g = int(hexc[3:5], 16) / 255.0
    b = int(hexc[5:7], 16) / 255.0
    return max(r, g, b) >= 0.7 and min(r, g, b) <= 0.35


def _norm_hex(hexc) -> str | None:
    if hexc is None:
        return None
    if not isinstance(hexc, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", hexc):
        raise SystemExit("invalid hex colour %r" % (hexc,))
    return hexc.upper()


def _norm_tex(fp: str) -> str:
    return fp.replace("\\", "/").strip()


def _tex_exists(fp: str) -> bool:
    return os.path.isfile(os.path.normpath(fp))


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9а-яё]+", "_", s)
    s = s.strip("_")
    return s or "unnamed"


def _tex_readable(fp: str) -> str:
    """Readable basename stem for a texture reference (naming only, not identity).

    The UDIM tile number (``.NNNN``) is kept: each tile is a distinct candidate and
    its short name must stay distinguishable (no silent basename collapse).
    """
    leaf = _norm_tex(fp).rsplit("/", 1)[-1]
    leaf = re.sub(r"\.(png|jpg|jpeg|tga|bmp)$", "", leaf)  # extension
    leaf = _HASH_SUFFIX.sub("", leaf)  # trailing Blender/Max auto-name hash
    return leaf


def _seed_for(name: str):
    for regex, cid, short, color, note in _SEEDS:
        if re.search(regex, name, re.IGNORECASE):
            return {"id": cid, "name": short, "color": color, "note": note}
    return None


def _appearance_key(name: str, hexc, textures):
    """Return (kind, key) for one source material instance.

    Identity is appearance, never a bare name/basename/majority-colour: textured
    materials are keyed by (name, full texture reference set); solids by
    (name, colour); only explicit seeds/families merge across names.
    """
    name = (name or "").strip() or "(none)"
    if textures:
        tex = tuple(sorted({_norm_tex(fp) for fp in textures}))
        return "patterned", ("patterned", name, tex)
    seed = _seed_for(name)
    if seed:
        return "seed", ("seed", seed["id"])
    if hexc and _is_placeholder_hex(hexc):
        return "placeholder", ("placeholder", hexc)
    if re.fullmatch(r"\d{1,2}", name):
        return "placeholder", ("placeholder", hexc or "(none)")
    if hexc in _DEFAULT_GREY and _GENERIC_NAME.match(name):
        return "placeholder", ("placeholder", hexc)
    fam = _FAMILY_HEX.get(hexc) if hexc else None
    if fam:
        return "family", ("family", fam)
    if _GENERIC_NAME.match(name):
        return "hex", ("hex", hexc)
    return "named-solid", ("named-solid", name, hexc)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _thumbnail_data_uri(path: str, size: int = 128) -> str | None:
    """Return a small JPEG data URI for a source preview, or None when unavailable."""
    try:
        from PIL import Image  # local import: only needed for the contact sheet
    except Exception:  # noqa: BLE001
        return None
    try:
        if not os.path.isfile(path):
            return None
        im = Image.open(path).convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im).convert("RGB")
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:  # noqa: BLE001 - a missing preview must not fail the run
        return None


def _assign_id(g: dict, kind: str, key) -> dict:
    """Assign a candidate id/name/colour to one appearance group."""
    if kind == "seed":
        seed = g["seed"]
        colour = seed["color"] or (sorted(g["hexes"])[0] if g["hexes"] else None)
        return {"id": seed["id"], "name": seed["name"], "color": colour,
                "color_source": "seed" if seed["color"] else
                ("fbx-default" if colour in _DEFAULT_GREY else "fbx-probe"),
                "note": seed["note"]}
    if kind == "family":
        fam = key[1]
        return {"id": fam, "name": fam, "color": _FAMILY_COLOR.get(fam),
                "color_source": "seed", "note": None}
    if kind == "hex":
        hexc = key[1] or "unknown"
        return {"id": "solid:" + (hexc.lower() if hexc != "unknown" else "unknown"),
                "name": "solid:" + (hexc.lower() if hexc != "unknown" else "unknown"),
                "color": hexc if hexc != "unknown" else None,
                "color_source": "fbx-default" if hexc in _DEFAULT_GREY else "fbx-probe",
                "note": None}
    if kind == "named-solid":
        name, hexc = key[1], key[2]
        return {"id": "solid:" + _slug(name), "name": name, "color": hexc,
                "color_source": "fbx-default" if hexc in _DEFAULT_GREY else "fbx-probe",
                "note": None}
    # patterned
    seed = _seed_for(sorted(g["names"])[0])
    if seed:
        return {"id": seed["id"], "name": seed["name"], "color": seed["color"],
                "color_source": "seed" if seed["color"] else None, "note": seed["note"]}
    texs = sorted(g["textures"])
    readable = next((_tex_readable(t) for t in texs
                     if _tex_readable(t) and _tex_readable(t) not in {"..", "maps"}), None)
    stem = readable or _slug(sorted(g["names"])[0])
    return {"id": "pattern:" + stem, "name": stem, "color": None,
            "color_source": None, "note": None}


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

    # Resolve the complete input inventory (including the implicit audit) BEFORE any
    # write, then guard every output alias against it.
    input_paths = {
        Path(args.materials).resolve(),
        Path(args.catalogue).resolve(),
        Path(args.seed).resolve(),
        Path(args.ral).resolve(),
    }
    audit_path = Path(args.catalogue).parent / "audit.json"
    audit_resolved = None
    if audit_path.exists():
        audit_resolved = audit_path.resolve()
        input_paths.add(audit_resolved)

    outs = [Path(args.out_json), Path(args.out_md), Path(args.out_html)]
    if len({o.resolve() for o in outs}) != 3:
        raise SystemExit("output paths must be distinct: " + ", ".join(str(o) for o in outs))
    for o in outs:
        if o.resolve() in input_paths:
            raise SystemExit("output path resolves to an input: " + str(o))
    if any(o.exists() for o in outs) and not args.overwrite:
        raise SystemExit("output exists; pass --overwrite to replace: "
                         + ", ".join(str(o) for o in outs if o.exists()))

    materials = json.loads(Path(args.materials).read_text(encoding="utf-8"))
    catalogue = json.loads(Path(args.catalogue).read_text(encoding="utf-8"))
    seed_set = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    json.loads(Path(args.ral).read_text(encoding="utf-8"))  # validated read

    # --- Fail-closed coverage validation -------------------------------------
    files = materials.get("files")
    if not isinstance(files, list) or not files:
        raise SystemExit("extraction has no files; expected the full catalogue coverage")
    cat_by_fbx = {}
    for e in catalogue.get("entries", []):
        fp = e.get("fbx_path")
        if not fp:
            raise SystemExit("catalogue entry without fbx_path: " + str(e.get("id")))
        leaf = Path(fp).name
        if leaf in cat_by_fbx:
            raise SystemExit("catalogue has duplicate fbx basename: " + leaf)
        cat_by_fbx[leaf] = e

    seen = set()
    for rec in files:
        fbx = rec.get("fbx")
        if not fbx:
            raise SystemExit("extraction record without 'fbx': "
                             + json.dumps(rec, ensure_ascii=False)[:200])
        if "error" in rec:
            raise SystemExit("extraction failed for FBX %r: %s" % (fbx, rec["error"]))
        if "materials" not in rec:
            raise SystemExit("extraction record without 'materials': %r" % fbx)
        if fbx in seen:
            raise SystemExit("duplicate extraction record for FBX: " + fbx)
        seen.add(fbx)
        if fbx not in cat_by_fbx:
            raise SystemExit("extraction record for unknown FBX (not in catalogue): " + fbx)
    missing = sorted(set(cat_by_fbx) - seen)
    if missing:
        raise SystemExit("incomplete extraction: %d catalogue FBX missing, first: %s"
                         % (len(missing), missing[0]))

    # --- Aggregate source materials by appearance identity --------------------
    groups = {}   # key -> {kind, names, hexes, textures, mafs, seed}
    for rec in files:
        entry = cat_by_fbx[rec["fbx"]]
        maf_id = entry.get("id") or Path(rec["fbx"]).stem
        for mat in rec.get("materials", []):
            name = (mat.get("name") or "").strip() or "(none)"
            hexc = _norm_hex(mat.get("hex"))
            tex_fps = [t["filepath"] for t in mat.get("textures", [])]
            kind, key = _appearance_key(name, hexc, tex_fps)
            g = groups.setdefault(key, {
                "kind": kind, "names": set(), "hexes": set(), "textures": set(),
                "mafs": set(), "seed": None,
            })
            g["names"].add(name)
            if hexc:
                g["hexes"].add(hexc)
            g["textures"] |= {_norm_tex(fp) for fp in tex_fps}
            g["mafs"].add(maf_id)
            if kind == "seed":
                g["seed"] = _seed_for(name)

    # --- Merge into candidate ids by semantic/colour identity -----------------
    # Placeholders are reported separately. Solid seed/family/hex groups merge on
    # their semantic id (explicit rule); named-solid and patterned groups never
    # merge across appearances (id collisions are disambiguated).
    merged = {}   # merge_key -> {kind, cand, names, hexes, textures, mafs}
    order = []
    placeholders = {}

    def _merge_key(g, kind, cand_id):
        if kind == "patterned":
            return ("patterned", tuple(sorted(g["names"])), tuple(sorted(g["textures"])))
        if kind in ("seed", "family", "hex"):
            return ("solid", cand_id)
        return ("solid", tuple(sorted(g["names"])), tuple(sorted(g["hexes"])))

    for key, g in groups.items():
        if g["kind"] == "placeholder":
            hexc = key[1]
            p = placeholders.setdefault(hexc, {"mafs": set(), "sources": set()})
            p["mafs"] |= g["mafs"]
            p["sources"] |= g["names"]
            continue
        cand = _assign_id(g, g["kind"], key)
        mk = _merge_key(g, g["kind"], cand["id"])
        if mk not in merged:
            merged[mk] = {"kind": g["kind"], "cand": cand, "names": set(),
                          "hexes": set(), "textures": set(), "mafs": set()}
            order.append(mk)
        mg = merged[mk]
        mg["names"] |= g["names"]
        mg["hexes"] |= g["hexes"]
        mg["textures"] |= g["textures"]
        mg["mafs"] |= g["mafs"]

    def cell_size(g):
        if g["kind"] == "patterned":
            return 128
        return 128 if len(g["mafs"]) >= 100 else 64

    preview_by_id = {e["id"]: e for e in catalogue.get("entries", [])}

    ids = []
    used_ids = set()
    for mk in order:
        mg = merged[mk]
        cand = mg["cand"]
        cid = cand["id"]
        if cid in used_ids:
            base, n = cid, 2
            while cid in used_ids:
                cid = "%s_%d" % (base, n)
                n += 1
        used_ids.add(cid)
        public_kind = "patterned" if mg["kind"] == "patterned" else "solid"
        tex_status = "none"
        if public_kind == "patterned":
            tex_status = "resolved" if any(_tex_exists(t) for t in mg["textures"]) else "unresolved"
        preview = None
        for maf_id in sorted(mg["mafs"]):
            entry = preview_by_id.get(maf_id)
            if entry and entry.get("preview_path"):
                pv = entry["preview_path"]
                preview = {"path": pv,
                           "sha256": sha256_file(Path(pv)) if os.path.isfile(pv) else None,
                           "style": entry.get("preview_style"),
                           "maf_id": maf_id}
                break
        ids.append({
            "id": cid,
            "name": cand["name"],
            "kind": public_kind,
            "color": cand["color"],
            "color_source": cand["color_source"],
            "textures": sorted(mg["textures"]),
            "texture_status": tex_status,
            "maf_count": len(mg["mafs"]),
            "atlas_cell": cell_size(mg),
            "merged_sources": sorted(mg["names"]),
            "preview": preview,
            "status": "proposed",
            "note": cand["note"],
        })

    existing_ids = {i["id"] for i in ids}
    for kn in _KNOWN_IDS:
        if kn["id"] not in existing_ids:
            ids.append({**kn, "textures": [], "texture_status": "none", "maf_count": 0,
                        "atlas_cell": 64, "merged_sources": [], "preview": None,
                        "status": "proposed", "color_source": "seed"})

    placeholders_out = [
        {"hex": hexc, "maf_count": len(p["mafs"]), "sources": sorted(p["sources"]),
         "status": "placeholder"}
        for hexc, p in sorted(placeholders.items(), key=lambda kv: -len(kv[1]["mafs"]))
    ]

    unresolved_tex = {}
    for i in ids:
        if i["kind"] == "patterned" and i["texture_status"] == "unresolved":
            for t in i["textures"]:
                unresolved_tex[t] = unresolved_tex.get(t, 0) + i["maf_count"]

    catalogue_entries = len(catalogue.get("entries", []))
    result = {
        "schema": "library-maf-material-ids",
        "version": "v002",
        "scope": "proposal for Artem's one-time approval; nothing reassigned in the library",
        "generated_by": "tools/library/maf_material_ids.py",
        "extraction": {
            "command": (
                "blender --background --factory-startup --python-exit-code 1 "
                "--python tools/library/maf_material_extract.py -- "
                "<FBX_DIR> <fbx_materials.json>"
            ),
            "command_then": (
                "uv run python tools/library/maf_material_ids.py "
                "--materials library/maf/fbx_materials.json "
                "--catalogue library/maf/catalogue.json "
                "--seed jobs/VATUTINO-SITE/maf/site-maf-set.json "
                "--ral tools/materials/ral_classic.json "
                "--out-json library/maf/material_ids.json --out-md library/maf/material_ids.md "
                "--out-html library/maf/material_contact_sheet.html"
            ),
            "input_hashes": {
                "library/maf/catalogue.json": sha256_file(Path(args.catalogue)),
                "library/maf/fbx_materials.json": sha256_file(Path(args.materials)),
                "jobs/VATUTINO-SITE/maf/site-maf-set.json": sha256_file(Path(args.seed)),
                "tools/materials/ral_classic.json": sha256_file(Path(args.ral)),
                "source_max (audit.json)": None,
                "source_blend (audit.json)": None,
            },
        },
        "counts": {
            "library_maf_entries": catalogue_entries,
            "extracted_files": len(files),
            "candidate_ids": len(ids),
            "solid_ids": sum(1 for i in ids if i["kind"] == "solid"),
            "patterned_ids": sum(1 for i in ids if i["kind"] == "patterned"),
            "placeholder_groups": len(placeholders_out),
            "placeholder_maf_uses": sum(p["maf_count"] for p in placeholders_out),
            "seed_ids_from_site_set": len(seed_set.get("atlas", {}).get("materials", [])),
            "unresolved_texture_refs": len(unresolved_tex),
        },
        "materials": ids,
        "placeholders": placeholders_out,
        "unresolved_textures": [{"filepath": t, "maf_count": c} for t, c in
                                sorted(unresolved_tex.items(), key=lambda kv: -kv[1])],
    }

    if audit_resolved is not None:
        audit = json.loads(audit_resolved.read_text(encoding="utf-8"))
        for sh in audit.get("source_hashes", []):
            leaf = Path(sh["path"]).name
            key = "source_max (audit.json)" if leaf.endswith(".max") else "source_blend (audit.json)"
            result["extraction"]["input_hashes"][key] = sh["sha256_before"]

    for o in outs:
        o.parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                                   encoding="utf-8", newline="\n")
    Path(args.out_md).write_text(render_md(result), encoding="utf-8", newline="\n")
    Path(args.out_html).write_text(render_html(result), encoding="utf-8", newline="\n")
    print("AGR_MAT_IDS", len(ids), "ids", len(placeholders_out), "placeholder groups",
          args.out_json)
    return 0


def render_md(result) -> str:
    lines = [
        "# MAF library material IDs (proposal)",
        "",
        f"Schema `{result['schema']}` version `{result['version']}`. {result['scope']}.",
        f"Generated by `{result['generated_by']}`.",
        "",
        "Counts: **%d** candidate ids (%d solid, %d patterned); **%d** placeholder groups "
        "(%d MAF uses) reported, not assigned; **%d** unresolved texture refs." % (
            result["counts"]["candidate_ids"], result["counts"]["solid_ids"],
            result["counts"]["patterned_ids"], result["counts"]["placeholder_groups"],
            result["counts"]["placeholder_maf_uses"], result["counts"]["unresolved_texture_refs"],
        ),
        "",
        "| id | name | kind | colour / texture | MAFs | cell | status | texture | merged sources |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in result["materials"]:
        if m["kind"] == "solid":
            src = m["color"] or "(unmeasured)"
        else:
            src = ", ".join("`%s`" % t for t in m["textures"]) if m["textures"] else "(none)"
        lines.append("| `%s` | %s | %s | %s | %d | %dx%d | %s | %s | %s |" % (
            m["id"], m["name"], m["kind"], src, m["maf_count"],
            m["atlas_cell"], m["atlas_cell"], m["status"], m["texture_status"],
            ", ".join("`%s`" % s for s in m["merged_sources"]),
        ))
    if result["placeholders"]:
        lines += ["", "## Placeholders (colour-coded part markers, not assigned)",
                  "", "| colour | MAF uses | sources |", "|---|---|---|"]
        for p in result["placeholders"]:
            lines.append("| %s | %d | %s |" % (p["hex"], p["maf_count"],
                                               ", ".join("`%s`" % s for s in p["sources"])))
    if result["unresolved_textures"]:
        lines += ["", "## Unresolved texture references (source files not found on this machine)",
                  "", "| filepath | MAF uses |", "|---|---|"]
        for u in result["unresolved_textures"]:
            lines.append("| `%s` | %d |" % (u["filepath"], u["maf_count"]))
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
            sw = ('<span style="display:inline-block;width:48px;height:48px;'
                  'background:%s;border:1px solid #999"></span>' % m["color"])
        else:
            uri = _thumbnail_data_uri(m["preview"]["path"]) if m.get("preview") else None
            if uri:
                sw = ('<img src="%s" width="96" height="96" '
                      'style="border:1px solid #999" alt="%s">' % (uri, m["id"]))
            else:
                sw = ('<span style="display:inline-block;width:48px;height:48px;'
                      'border:1px dashed #c00;text-align:center;line-height:48px;'
                      'color:#c00;font-size:9px">no&nbsp;image</span>')
        if m["kind"] == "solid":
            src_label = m["color"] or "(unmeasured)"
        else:
            src_label = ", ".join("`%s`" % t for t in m["textures"]) if m["textures"] else "(none)"
        if m["kind"] == "patterned" and m["texture_status"] == "unresolved":
            src_label += " <b>[texture unresolved]</b>"
        rows.append(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s<br><small>%s</small></td>"
            "<td>%d</td><td>%d&times;%d</td><td>%s</td><td>%s</td></tr>" % (
                m["id"], m["name"], m["kind"], sw, src_label, m["maf_count"],
                m["atlas_cell"], m["atlas_cell"], m["status"], m["texture_status"]))
    ph = []
    for p in result["placeholders"]:
        sw = ('<span style="display:inline-block;width:32px;height:20px;background:%s;'
              'border:1px solid #999"></span>' % (p["hex"] if p["hex"] else "#fff"))
        ph.append("<tr><td>%s %s</td><td>%d</td><td>%s</td></tr>" % (
            sw, p["hex"], p["maf_count"], ", ".join("`%s`" % s for s in p["sources"])))
    ur = []
    for u in result["unresolved_textures"]:
        ur.append("<tr><td><code>%s</code></td><td>%d</td></tr>" % (u["filepath"], u["maf_count"]))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>MAF library material IDs</title></head><body>"
        "<h1>MAF library material IDs (proposal)</h1>"
        "<p>%d candidate ids (%d solid, %d patterned); %d placeholder groups (not assigned); "
        "%d unresolved texture refs. Patterned swatches are source MAF previews; "
        "<b>[texture unresolved]</b> means the referenced texture file is not present on this machine.</p>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr><th>id</th><th>name</th><th>kind</th><th>swatch / source</th><th>MAFs</th>"
        "<th>cell</th><th>status</th><th>texture</th></tr>"
        "%s</table>"
        "<h2>Placeholders</h2>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr><th>swatch / colour</th><th>MAF uses</th><th>sources</th></tr>%s</table>"
        "<h2>Unresolved texture references</h2>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr><th>filepath</th><th>MAF uses</th></tr>%s</table>"
        "</body></html>"
    ) % (result["counts"]["candidate_ids"], result["counts"]["solid_ids"],
         result["counts"]["patterned_ids"], result["counts"]["placeholder_groups"],
         result["counts"]["unresolved_texture_refs"], "".join(rows), "".join(ph), "".join(ur))


if __name__ == "__main__":
    raise SystemExit(main())
