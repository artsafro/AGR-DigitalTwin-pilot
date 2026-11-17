"""NPM/VPM delivery validator: findings per stage V001-V017 (standards/DELIVERY_VALIDATOR.yaml).

    py -3 tools/qa/validate_package.py <package.zip | model.fbx | model.geojson> [--profile npm|vpm] [--json] [--scene]
        [--master work.fbx]

Without --profile the profile comes from the name grammar ({code4}_{Address} NPM, SM_{Address} VPM); only a name
that matches neither falls back to the content (lab L04, #908).
Exit code: 0 passed (every blocking machine stage ran and passed), 1 any fail,
2 only review / not_run remain. Stages that need the FBX scene (units, triangles,
UV islands, UCX, coordinates) are not_run unless --scene runs the Blender readback
(tools/blender/fbx_readback.py) on every FBX.
Manual stages (V015-V017) always need a signed review.
--master reads the quad work FBX back (DER-03, [D021], [D198]): V003 "master quads" / "master quad size";
with --scene and no --master that part of V003 stays not_run.
Build manifest (#1423): a ZIP is checked against `<stem>.build.json` beside it (or --build-manifest FILE) in V001
"build manifest": different master revisions, a master changed since the build (--master hash), zipped bytes or
check-report hashes that differ, or a required check not run / not finished / not passed -> fail; no manifest ->
not_run (never pass); no --master -> not_run manifest_master_unchecked (stale check did not run; an NPM ZIP: fail manifest_master_missing, #1637); a package with OKS and Ground members takes `--master oks=PATH --master ground=PATH` ([D328]). Format and writer: adapters/max/agr_tools/build_manifest.py, `agr build-manifest`.

    py -3 tools/qa/validate_package.py --recheck old_report.json --output new_report.json [--recheck-target copy.zip] [--standards DIR] [--json]

Recheck (issue #511): is a stored report's verdict still true now? current (target sha256 and
standards digest unchanged; exit = the stored exit code), stale_standards (exit 3),
evidence_missing (target gone or changed; exit 4). The result is written to a NEW file
(never over an existing file, the old report or the target); bad input exits 2 and writes nothing.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.max.agr_tools import build_manifest  # noqa: E402  (#1423 delivery set consistency)

from twinqa.bundle import BundleError, read_bundle, size_status  # noqa: E402
from twinqa.fbx_header import check_fbx_header  # noqa: E402
from twinqa.geojson import geojson_findings  # noqa: E402
from twinqa.master import master_findings  # noqa: E402
from twinqa.io import digest, json_bytes  # noqa: E402
from twinqa.png import npm_texture_findings, vpm_texture_findings  # noqa: E402
from twinqa.profiles import (DEFAULT_STANDARDS, expected_stages, load_profiles, read_snapshot,  # noqa: E402
                             snapshot_digest, snapshot_validator)
from twinqa.report import Finding, Stage, ValidationReport, code_commit, recheck, recheck_summary  # noqa: E402
from twinqa.scene import check_ground_area, check_ground_materials, readback, scene_findings  # noqa: E402
from twinqa.npm_uv import NAME as NPM_UV_NAME, load_layout, npm_uv_findings  # noqa: E402
from twinqa.uv import sequential_tiles  # noqa: E402


def load_z_meta(path: Path):
    """--export-meta through the shared ExportMeta owner (adapters/max/agr_tools/export_meta.py, #1342)."""
    import importlib.util
    owner = Path(__file__).resolve().parents[2] / "adapters" / "max" / "agr_tools" / "export_meta.py"
    spec = importlib.util.spec_from_file_location("agr_export_meta_owner", owner)
    if spec is None or spec.loader is None:
        raise ValueError(f"export_meta owner missing: {owner}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module.load_z_meta(path)
    if not isinstance(payload, dict):
        raise ValueError(f"export_meta {path}: expected a JSON object at top level")
    return payload


STEM = re.compile(r"^[A-Za-z0-9_]+$")
NPM_ARCHIVE = re.compile(r"^(?P<code>[0-9]{4})_(?P<address>[A-Za-z0-9_]+)$")
VPM_STEM = re.compile(r"^SM_[A-Za-z0-9_]+$")
SCENE_NOTE = "needs the FBX scene: run tools/blender readback"


def profile_from_name(name: str) -> str | None:
    """Profile from the archive/FBX name grammar (lab L04, #908): NPM `{code4}_{Address}[...]`, VPM `SM_{Address}[...]`.
    None when the name matches neither; only then is the profile guessed from the content."""
    stem = Path(name).stem
    if NPM_ARCHIVE.match(stem):
        return "npm"
    if VPM_STEM.match(stem):
        return "vpm"
    return None


def _no_texture_findings(found: dict, role: str, name: str, rb: dict):
    """NPM textures are embedded in the FBX (reg p.9 §5.1). A readback with no image at all is not an
    'all embedded' pass (lab L04: vacuous V006 pass): OKS FBX fail, Ground FBX review (GroundGlass is untextured)."""
    if rb.get("images"):
        return
    status = "review" if role == "ground" else "fail"
    v6 = [f for f in found.get("V006", []) if f.name != "embedded textures"]
    v6.append(finding(status, "embedded textures", f"{name}: no texture in the FBX",
                      "PNG atlases embedded in FBX", [9], name))
    found["V006"] = v6


# ---- ZIP corpus codes (#979 qa.package rework; T06/agr_zipper_2506: the Zipper crashed or let these pass) ------
ZIP_CODES = ("zip_unreadable", "zip_encrypted", "zip_nul_name", "zip_unsupported_method", "zip_traversal",
             "zip_absolute", "zip_backslash", "zip_duplicate", "zip_bad_member", "zip_bad_utf8", "zip_too_large",
             "zip_nested")
ZIP_METHODS = (0, 8, 12, 14)  # stored, deflate, bzip2, lzma: the methods zipfile reads
CHECKER = "AGR_Checker.zip sha256 0c1e5f7454bf9aa5183e5e9d1893f6b801b3f0123638278cbb97651748693e4d (rule idea only)"


def zip_precheck(target: Path) -> tuple[str, str] | None:
    """(code, observed) for an archive the bundle reader must not open, else None.

    zipfile cuts a member name at NUL (`SM_X.fbx\\x00../escape` reads as `SM_X.fbx`), raises RuntimeError on an
    encrypted member and NotImplementedError on an unsupported method: all are named here, before any member is read
    (the Zipper crashed or passed, T06; the PR #675 witnesses recorded the escapes). The raw tail after a NUL is never
    echoed."""
    import zipfile
    try:
        with zipfile.ZipFile(target) as z:
            infos = z.infolist()
    except UnicodeDecodeError:
        return None  # the bundle reader names the member (bad UTF-8)
    except (zipfile.BadZipFile, OSError, EOFError, ValueError) as exc:
        return "zip_unreadable", f"not a readable ZIP (broken or truncated): {exc}"
    for info in infos:
        if "\x00" in info.orig_filename:
            return "zip_nul_name", f"member name with NUL (read as {info.filename!r})"
    enc = [i.filename for i in infos if i.flag_bits & 0x1]
    if enc:
        return "zip_encrypted", f"encrypted member(s): {', '.join(enc[:5])}"
    odd = [f"{i.filename} (method {i.compress_type})" for i in infos if i.compress_type not in ZIP_METHODS]
    if odd:
        return "zip_unsupported_method", f"unsupported compression: {', '.join(odd[:5])}"
    return None


def bundle_code(exc) -> str:
    text = str(exc)
    if isinstance(exc.__cause__, UnicodeDecodeError):
        return "zip_bad_utf8"
    if text.startswith("Unsafe ZIP path"):
        name = text.split(": ", 1)[-1]
        p = PurePosixPath(name)
        if ".." in p.parts:
            return "zip_traversal"
        if p.is_absolute() or ":" in name:
            return "zip_absolute"
        return "zip_backslash"
    if text.startswith("Duplicate"):
        return "zip_duplicate"
    if text.startswith("Uncompressed"):
        return "zip_too_large"
    if text.startswith("Broken ZIP member"):
        return "zip_bad_member"
    return "zip_unreadable"


# ---- Light FBX (rule idea of AGR Checker: one Root, lights parented, <a>_[Spot|Omni]_NNN) -------------------------
LIGHT_MAX = 250
LIGHT_NUMBER_MAX = 50
LIGHT_TYPES = {0: "Omni", 1: "Directional", 2: "Spot", 3: "Area", 4: "Volume"}


def _fbx_props(data: bytes, node: dict) -> list:
    from twinqa.fbx_header import _parse_props
    return [v for _code, v in _parse_props(data, node["props_at"], node["props_end"], node["num_props"])]


def _fbx_children(data: bytes, node: dict, version: int) -> list[dict]:
    from twinqa.fbx_header import _iter_nodes
    return list(_iter_nodes(data, node["props_end"], node["end_offset"], version))


def _p70(data: bytes, node: dict, version: int) -> dict:
    out = {}
    for child in _fbx_children(data, node, version):
        if child["name"] != "Properties70":
            continue
        for p in _fbx_children(data, child, version):
            if p["name"] == "P":
                vals = _fbx_props(data, p)
                if vals and isinstance(vals[0], str):
                    out[vals[0]] = vals[4:]
    return out


def light_scene(data: bytes) -> dict:
    """Models of a binary FBX: {id: {name, kind, parent, light, t, r, s}} (stdlib walk; ValueError if unreadable)."""
    from twinqa.fbx_header import _FbxError, _iter_nodes, fbx_header
    kind, version = fbx_header(data)
    if kind != "binary":
        raise ValueError("not a binary FBX")
    try:
        top = {n["name"]: n for n in _iter_nodes(data, 27, len(data), version)}
        models, attrs, links = {}, {}, []
        for node in _fbx_children(data, top["Objects"], version) if "Objects" in top else []:
            vals = _fbx_props(data, node)
            if node["name"] == "Model" and len(vals) >= 3:
                p = _p70(data, node, version)
                models[vals[0]] = {"name": str(vals[1]).split("\x00", 1)[0], "kind": vals[2], "parent": 0,
                                   "light": None, "t": tuple(p.get("Lcl Translation", (0.0, 0.0, 0.0))),
                                   "r": tuple(p.get("Lcl Rotation", (0.0, 0.0, 0.0))),
                                   "s": tuple(p.get("Lcl Scaling", (1.0, 1.0, 1.0)))}
            elif node["name"] == "NodeAttribute" and len(vals) >= 3 and vals[2] == "Light":
                lt = _p70(data, node, version).get("LightType", [0])
                attrs[vals[0]] = LIGHT_TYPES.get(int(lt[0]) if lt else 0, "Other")
        for node in _fbx_children(data, top["Connections"], version) if "Connections" in top else []:
            vals = _fbx_props(data, node)
            if len(vals) >= 3 and vals[0] == "OO":
                links.append((vals[1], vals[2]))
    except (_FbxError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"unreadable FBX scene: {exc}") from exc
    for child, parent in links:
        if child in attrs and parent in models:
            models[parent]["light"] = attrs[child]
        elif child in models:
            models[child]["parent"] = parent
    return models


def light_findings(name: str, data: bytes, cipher: str, pages) -> list:
    """Light FBX of a VPM set (`SM_<a>[_Ground]_Light.fbx`): exactly one `<cipher>_Root` (`_Ground_Root` for Ground)
    with reset transforms, every light parented to it, names `<cipher>_[Spot|Omni]_NNN` 001..050, <= 250 lights,
    the name type equal to the light type. Idea of AGR Checker (T04, measured); no checker code is reproduced."""
    try:
        models = light_scene(data)
    except ValueError as exc:
        return [finding("fail", "light FBX scene", f"{name}: {exc}", "binary FBX with a Root and lights", pages,
                        CHECKER, data={"code": "light_unreadable"})]
    out = []
    lights = [m for m in models.values() if m["light"] is not None]
    roots = [(k, m) for k, m in models.items() if m["light"] is None and m["parent"] == 0]
    want_root = f"{cipher}_Root"

    def bad(code, observed, expected):
        out.append(finding("fail", "light FBX", f"{name}: {observed}", expected, pages, CHECKER, data={"code": code}))
    if len(roots) != 1:
        bad("light_root", f"{len(roots)} root objects {[m['name'] for _k, m in roots][:5]}", f"exactly one {want_root}")
    else:
        rid, root = roots[0]
        if root["name"] != want_root:
            bad("light_root", f"root {root['name']!r}", want_root)
        reset = (all(abs(float(v)) < 1e-6 for v in root["t"] + root["r"])
                 and all(abs(float(v) - 1.0) < 1e-6 for v in root["s"]))
        if not reset:
            bad("light_root_transform", f"root t={root['t']} r={root['r']} s={root['s']}", "reset transforms")
        orphans = sorted(m["name"] for m in lights if m["parent"] != rid)
        if orphans:
            bad("light_parent", f"not under the root: {orphans[:5]}", f"every light parented to {want_root}")
    if len(lights) > LIGHT_MAX:
        bad("light_count", f"{len(lights)} lights", f"<= {LIGHT_MAX}")
    pat = re.compile(rf"^{re.escape(cipher)}_(Spot|Omni)_(\d{{3}})$")
    for m in sorted(lights, key=lambda x: x["name"]):
        hit = pat.match(m["name"])
        if not hit:
            bad("light_name", f"{m['name']!r}", f"{cipher}_[Spot|Omni]_NNN")
            continue
        if not 1 <= int(hit.group(2)) <= LIGHT_NUMBER_MAX:
            bad("light_number", f"{m['name']}", f"number 001..{LIGHT_NUMBER_MAX:03d}")
        actual = "Spot" if m["light"] == "Spot" else "Omni" if m["light"] == "Omni" else m["light"]
        if hit.group(1) != actual:
            bad("light_type", f"{m['name']} is a {m['light']} light", f"name type {hit.group(1)} = light type")
    if not out:
        out.append(finding("pass", "light FBX", f"{name}: root {want_root}, {len(lights)} light(s)",
                           "one Root, lights parented, <a>_[Spot|Omni]_NNN", pages, CHECKER))
    return out


def finding(status, name, observed, expected, pages, evidence="", conflicts=(), data=None):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts),
                   data={} if data is None else data)


def build_stages(profiles, kind: str) -> dict[str, Stage]:
    stages = {}
    for spec in profiles.validator["stages"]:
        if spec["scope"] not in ("both", kind.upper()):
            continue
        pages = spec.get("source_pdf_pages", [])
        if isinstance(pages, dict):
            pages = pages.get(kind.upper(), [])
        stages[spec["id"]] = Stage(spec["id"], spec["check"], spec["gate"], list(pages))
    return stages


def check_fbx_headers(stage: Stage, fbx: dict[str, bytes]):
    for name, data in sorted(fbx.items()):
        ok, observed = check_fbx_header(data)
        stage.findings.append(finding("pass" if ok else "fail", "FBX header", f"{name}: {observed}",
                                      "binary FBX 7400 (7.4/2014)", stage.source_pdf_pages, name))
    stage.findings.append(finding("not_run", "units and scale", "1 unit = 1 m not read from the scene",
                                  "1 unit = 1 m, scale 1:1", stage.source_pdf_pages, SCENE_NOTE))


def validate_vpm_zip(stem: str, files: dict[str, bytes], profile: dict, st: dict[str, Stage]) -> dict:
    """Archive-level VPM checks; returns {(slot, udim): Diffuse side px} for the V009 scene density."""
    ground = stem.endswith("_Ground")
    address = stem[3:-len("_Ground")] if ground else stem[3:]
    fbx = {n: d for n, d in files.items() if n.lower().endswith(".fbx")}
    pngs = {n: d for n, d in files.items() if n.lower().endswith(".png")}
    geo = {n: d for n, d in files.items() if n.lower().endswith(".geojson")}
    other = sorted(set(files) - set(fbx) - set(pngs) - set(geo))

    v1, pages = st["V001"], st["V001"].source_pdf_pages
    nested = [n for n in files if len(PurePosixPath(n).parts) > 1]
    if nested:
        v1.findings.append(finding("fail", "flat archive", f"{len(nested)} file(s) in folders, e.g. {nested[0]}",
                                   "files in the ZIP root", pages, data={"code": "zip_nested"}))
    if other:
        v1.findings.append(finding("fail", "foreign files", ", ".join(other[:5]), "FBX, optional Light FBX, GeoJSON, PNG only", pages))
    main, light = f"{stem}.fbx", f"{stem}_Light.fbx"
    if main not in fbx:
        v1.findings.append(finding("fail", "main FBX", f"{sorted(fbx)}", main, pages))
    extra_fbx = sorted(set(fbx) - {main, light})
    if extra_fbx:
        v1.findings.append(finding("fail", "FBX set", f"unexpected {extra_fbx}", f"{main} and optional {light}", pages))
    if f"{stem}.geojson" not in geo or len(geo) != 1:
        v1.findings.append(finding("fail", "GeoJSON", f"{sorted(geo) or 'none'}", f"exactly {stem}.geojson", pages))
    lo, hi = profile["archive"]["png_count_range"]
    if not lo <= len(pngs) <= hi:
        v1.findings.append(finding("fail", "PNG count", str(len(pngs)), f"{lo}..{hi}", pages))

    v12, npages = st["V012"], st["V012"].source_pdf_pages
    if not STEM.match(stem) or not stem.startswith("SM_") or len(stem) > profile["naming"]["max_characters"]:
        v12.findings.append(finding("fail", "archive name", stem, "SM_{Address}[_Ground], A-Z a-z 0-9 _", npages))
    elif ground:
        v12.findings.append(finding("pass", "archive name", stem, "SM_{Address}_Ground", npages))
    else:
        # Free-standing buildings need an _001.. index (reg p.26 §3.7), not encoded: conflict #20
        v12.findings.append(finding("review", "archive name", stem, "SM_{Address}; _001.. index for free-standing buildings",
                                    npages, conflicts=[20]))

    if main in fbx:
        check_fbx_headers(st["V002"], {k: v for k, v in fbx.items() if k in (main, light)})
    if light in fbx:
        v12.findings.extend(light_findings(light, fbx[light], stem, npages))
    prefix = f"T_{address}_Ground" if ground else f"T_{address}"
    findings, sets = vpm_texture_findings(pngs, profile, prefix)
    st["V007"].findings.extend(findings)

    v8 = st["V008"]
    for slot in sorted({s for s, _ in sets}):
        tiles = sorted(u for s, u in sets if s == slot)
        ok = sequential_tiles(tiles)
        v8.findings.append(finding("pass" if ok else "fail", "UDIM sequence", f"slot {slot}: {tiles}",
                                   "1001..1100 sequential without gaps", v8.source_pdf_pages))
    v8.findings.append(finding("not_run", "UV channel and islands", "single UV channel, mirroring, glass in 1001",
                               "one UV channel, no mirrored islands, glass only in 1001", v8.source_pdf_pages, SCENE_NOTE))

    if f"{stem}.geojson" in geo:
        st["V011"].findings.extend(geojson_findings(
            geo[f"{stem}.geojson"], profile, ground, source_name=f"{stem}.geojson"))
    st["V009"].findings.append(finding("not_run", "texel density", "UV and polygon lengths not read from the scene",
                                       "512..1706 px/m Diffuse [D160]", st["V009"].source_pdf_pages, SCENE_NOTE))
    return {key: maps["Diffuse"].width for key, maps in sets.items() if "Diffuse" in maps}


def validate_npm_zip(stem: str, files: dict[str, bytes], profile: dict, st: dict[str, Stage]):
    v1, pages = st["V001"], st["V001"].source_pdf_pages
    nested = [n for n in files if len(PurePosixPath(n).parts) > 1]
    if nested:
        v1.findings.append(finding("fail", "flat archive", f"{len(nested)} file(s) in folders, e.g. {nested[0]}",
                                   "files in the ZIP root", pages, data={"code": "zip_nested"}))
    fbx = {n: d for n, d in files.items() if n.lower().endswith(".fbx")}
    other = sorted(set(files) - set(fbx))
    if other:
        # NPM textures are embedded in the FBX (reg p.9 §5.1); anything else is foreign
        v1.findings.append(finding("fail", "foreign files", ", ".join(other[:5]), "FBX only (textures embedded)", pages))
    count = profile["archive"]["fbx_total"]
    if not count["min"] <= len(fbx) <= count["max"]:
        v1.findings.append(finding("fail", "FBX count", str(len(fbx)), f"{count['min']}..{count['max']} (1 Ground + 1..20 OKS)", pages))
    m = NPM_ARCHIVE.match(stem)
    v12 = st["V012"]
    if not m:
        v12.findings.append(finding("fail", "archive name", stem, "{territory_code_4}_{Address}", v12.source_pdf_pages))
    else:
        ground_name, part = f"{stem}_Ground.fbx", re.compile(rf"^{re.escape(stem)}_(0[1-9]|1[0-9]|20)\.fbx$")
        if ground_name not in fbx:
            v1.findings.append(finding("fail", "Ground FBX", f"{sorted(fbx)}", ground_name, pages))
        bad = sorted(n for n in fbx if n != ground_name and not part.match(n))
        v12.findings.append(finding("fail" if bad else "pass", "FBX names", f"{bad or 'all match'}",
                                    f"{stem}_01..20.fbx and {ground_name}", v12.source_pdf_pages))
    check_fbx_headers(st["V002"], fbx)
    st["V006"].findings.append(finding("not_run", "embedded atlases", "PNG inside FBX not extracted",
                                       "sizes, <= 3 MB, no alpha, 8 px padding", st["V006"].source_pdf_pages, SCENE_NOTE))


def fbx_role(name: str) -> str:
    stem = Path(name).stem
    return "light" if stem.endswith("_Light") else "ground" if stem.endswith("_Ground") else "oks"


def add_scene(st: dict[str, Stage], kind: str, profile: dict, fbx: dict[str, bytes], notes: list[str],
              ground_area_m2: float | None = None, footprint_holes=None, diffuse_px: dict | None = None,
              ground_materials: list[str] | None = None, export_meta=None, npm_atlas: dict | None = None):
    """Blender readback of each FBX; replaces the scene not_run placeholders it covers.
    npm_atlas {FBX name: npm_atlas.json dict} feeds the NPM V006 "UV atlas padding" readback (#1580); an NPM
    OKS/Ground FBX without one keeps that finding not_run.
    ground_area_m2 (site minus OKS footprint) selects the VPM Ground triangle band (reg p.29)
    and is the expected top-down area for the Ground footprint-coverage finding.
    footprint_holes is an optional list of XY rings for the footprint-hole coverage finding.
    ground_materials is an optional allow-list (names or globs): only those faces feed both footprint findings.
    diffuse_px {(slot, udim): side px} from the archive Diffuse PNGs feeds the VPM V009 texel density."""
    import tempfile
    # Archive-wide placeholders become independent per-file coverage, never a
    # claim that one readable FBX represents all siblings. Empty inventories keep
    # the original placeholders.
    covered = {"V002": "units and scale", "V008": "UV channel and islands",
               "V006": "embedded atlases", "V009": "texel density"}
    if fbx:
        for stage_id, placeholder in covered.items():
            if stage_id in st:
                st[stage_id].findings = [f for f in st[stage_id].findings
                                         if not (f.name == placeholder and f.evidence == SCENE_NOTE)]
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in sorted(fbx.items()):
            role = fbx_role(name)
            required = {"V002", "V003", "V004", "V005"}
            if kind == "npm":
                required.add("V006")
            if role != "light":
                required.add("V013")
                if kind == "vpm":
                    required.update(("V008", "V009", "V010"))
            pending = {}
            for stage_id in sorted(required & st.keys()):
                pending[stage_id] = finding("not_run", covered.get(stage_id, "scene checks"),
                                            f"{name}: no scene result", st[stage_id].check,
                                            st[stage_id].source_pdf_pages, name)
                st[stage_id].findings.append(pending[stage_id])
            path = Path(tmp) / Path(name).name
            path.write_bytes(data)
            try:
                rb = readback(path)
            except (OSError, RuntimeError) as exc:
                # one unreadable FBX must not hide the others (team audit T04: a _Light import error ended the loop)
                notes.append(f"scene readback skipped for {name}: {exc}")
                continue
            height_meta = None
            if export_meta is not None:
                unknown = set(export_meta) - set(fbx)
                height_meta = export_meta.get(name)
                if unknown:
                    height_meta = {'error': f'unmapped export_meta filenames: {sorted(unknown)}'}
                elif not isinstance(height_meta, dict) or height_meta.get('fbx_sha256') != digest(data):
                    height_meta = {'error': f'{name}: missing/stale export_meta fbx_sha256 or record'}
            found = scene_findings(rb, kind, fbx_role(name), profile, ground_area_m2=ground_area_m2,
                                   footprint_holes=footprint_holes, diffuse_px=diffuse_px,
                                   ground_materials=ground_materials,
                                   export_meta=height_meta)
            if kind == "npm":
                _no_texture_findings(found, fbx_role(name), name, rb)
                if role != "light":
                    # #1580: the 8 px padding of the V006 stub is read from the exported UVs, never dropped
                    atlas = (npm_atlas or {}).get(name)
                    found.setdefault("V006", []).extend(npm_uv_findings(rb, atlas, name) if atlas is not None else [
                        finding("not_run", NPM_UV_NAME, f"{name}: npm_atlas.json not given "
                                f"(--npm-atlas {name}=PATH)", "every face inside its atlas region, "
                                "8 px padding (reg p.9 §5.4)", [9], name)])
            for stage_id, findings in found.items():
                if stage_id in st:
                    if findings and stage_id in pending:
                        st[stage_id].findings.remove(pending[stage_id])
                    st[stage_id].findings.extend(findings)
            notes.append(f"scene readback: {name} in Blender {rb.get('blender')}")


def add_build_manifest(st: dict[str, Stage], target: Path, data: bytes, files: dict[str, bytes],
                       master: Path | dict | None, manifest: Path | None, notes: list[str], kind: str | None = None):
    """V001 "build manifest" findings of one ZIP (#1423); the manifest file and the master are read, never written.

    master: one path, or {role: path} ([D328]: OKS master, Ground source)."""
    path = manifest if manifest is not None else Path(build_manifest.manifest_path(target))
    if os.path.normcase(str(path.resolve())) == os.path.normcase(str(target.resolve())):
        raise ValueError(f"build manifest {path} is the package itself")
    raw = path.read_bytes() if path.is_file() else None
    if manifest is not None and raw is None:
        raise ValueError(f"build manifest {manifest} does not exist")
    members = {n: digest(d) for n, d in files.items()}
    master_sha = build_manifest.master_hashes(master)
    v1 = st["V001"]
    rows = build_manifest.manifest_findings(raw, members, target.name, digest(data), master_sha,
                                            str(path.resolve().parent))
    if kind == "npm" and raw is not None and master is None:
        # #1637: an NPM ZIP with a build manifest and no --master is a fail, not a not_run wait like V015-V017
        rows = [("fail", "manifest_master_missing",
                 f"manifest_master_missing: NPM package {target.name} has build manifest {path.name} but no --master "
                 "was given, so the build master was not compared with the current master; rerun with --master PATH "
                 "(--master oks=PATH --master ground=PATH for OKS + Ground)")] + [
            r for r in rows if r[1] != "manifest_master_unchecked"]
    for status, code, detail in rows:
        v1.findings.append(finding(status, "build manifest", detail, "one master revision; hashes of every zipped "
                                   "artifact and check report match; required checks passed (#1423)",
                                   v1.source_pdf_pages, path.name, data={"code": code} if status != "pass" else None))
    if raw is not None:
        notes.append(f"build manifest: {path.name}")


def add_master(st: dict[str, Stage], kind: str, master: Path | None, notes: list[str]):
    """DER-03 quad master: read the work FBX back, or leave V003 'master quads' not_run ([D021], [D198])."""
    if "V003" not in st:
        return
    if master is None:
        st["V003"].findings.append(finding("not_run", "master quads", "quad work FBX not given (--master)",
                                           "quad master; VPM faces <= 4 m [D021]", [8, 29], "DER-03"))
        return
    try:
        rb = readback(master)
    except (OSError, RuntimeError) as exc:
        notes.append(f"master readback skipped for {master.name}: {exc}")
        st["V003"].findings.append(finding("not_run", "master quads", f"{master.name}: readback failed",
                                           "quad master; VPM faces <= 4 m [D021]", [8, 29], "DER-03"))
        return
    st["V003"].findings.extend(master_findings(rb, kind))
    notes.append(f"master readback: {master.name} in Blender {rb.get('blender')}")


def _resolve_npm_atlas(npm_atlas, target: Path, files: dict, kind, scene: bool, notes: list[str]) -> dict:
    """{FBX name: loaded npm_atlas.json} for add_scene (#1580); every key must name an FBX of the target."""
    if not npm_atlas:
        return {}
    if not scene or kind != "npm" or target.suffix.lower() not in (".zip", ".fbx"):
        notes.append("npm_atlas unused: the UV atlas padding check runs on an NPM --scene readback of a ZIP or FBX")
        return {}
    names = [n for n in files if n.lower().endswith(".fbx")] if target.suffix.lower() == ".zip" else [target.name]
    out = {}
    for key, path in (npm_atlas.items() if isinstance(npm_atlas, dict) else npm_atlas):
        if key is None:
            oks = [n for n in names if fbx_role(n) == "oks"]
            if len(oks) != 1:
                raise ValueError(f"--npm-atlas without FBX=: needs exactly one OKS FBX, found {sorted(oks)}")
            key = oks[0]
        if key not in names:
            raise ValueError(f"--npm-atlas {key}: no such FBX in {target.name} ({sorted(names)})")
        if key in out:
            raise ValueError(f"--npm-atlas {key} given twice")
        path = Path(path)
        try:
            atlas = json.loads(path.read_text(encoding="utf-8"))
            load_layout(atlas)
        except (OSError, ValueError) as exc:
            raise ValueError(f"--npm-atlas {key}={path}: {exc}") from None
        out[key] = atlas
    return out


def validate(target: Path, kind: str | None, profiles, scene: bool = False,
             ground_area_m2: float | None = None, footprint_holes=None,
             master: Path | dict | None = None, ground_materials: list[str] | None = None, export_meta=None,
             manifest: Path | None = None, npm_atlas: dict | list | None = None) -> ValidationReport:
    """npm_atlas {FBX name | None: npm_atlas.json path} or [(name | None, path)] (#1580): None = the single FBX
    target / the only OKS FBX of the ZIP; a name that is not an FBX of the target, a name given twice, or an unusable
    layout raises ValueError."""
    if export_meta is not None and not isinstance(export_meta, dict):
        raise ValueError("export_meta must map exact FBX filenames to bounds_m records")
    if ground_area_m2 is not None:
        check_ground_area(ground_area_m2)
    if ground_materials is not None:
        ground_materials = check_ground_materials(ground_materials)
    data = target.read_bytes()
    suffix = target.suffix.lower()
    files, notes = {}, []
    if suffix == ".geojson":
        kind = "vpm"
    elif kind is None and suffix in (".zip", ".fbx"):
        kind = profile_from_name(target.name)
        if kind is not None:
            notes.append(f"profile {kind.upper()} from the name grammar of {target.name}")
    if kind is None and suffix in (".fbx", ".png"):
        kind = "npm"
    if suffix == ".zip":
        early = zip_precheck(target)
        if early is not None:
            kind = kind or "vpm"
            st = build_stages(profiles, kind)
            st["V001"].findings.append(finding("fail", "ZIP", f"{target.name}: {early[1]}", "readable ZIP, safe paths",
                                               st["V001"].source_pdf_pages, data={"code": early[0]}))
            return report(target, data, kind, profiles, st, notes)
        try:
            files = read_bundle(target, max_uncompressed=4 * 10**9)
        except BundleError as exc:
            kind = kind or "vpm"
            st = build_stages(profiles, kind)
            cause = exc.__cause__
            observed = str(exc)
            extra = {"code": bundle_code(exc)}
            if isinstance(cause, UnicodeDecodeError):
                member = exc.member if isinstance(getattr(exc, "member", None), str) else ""
                observed = f"V001 {target.name}: {exc}"
                extra.update({
                    "rule_id": "V001",
                    "file": target.name,
                    "member": member,
                    "exception_class": type(cause).__name__,
                    "message": str(cause),
                })
            st["V001"].findings.append(finding(
                "fail", "ZIP", observed, "readable ZIP, safe paths", st["V001"].source_pdf_pages, data=extra))
            return report(target, data, kind, profiles, st, notes)
        if kind is None:
            kind = "vpm" if any(n.lower().endswith((".geojson", ".png")) for n in files) else "npm"
            notes.append(f"profile auto-detected as {kind.upper()} from archive content "
                         "(the name matches neither {code4}_{Address} nor SM_{Address})")
    profile = profiles.profile(kind)
    st = build_stages(profiles, kind)
    atlases = _resolve_npm_atlas(npm_atlas, target, files, kind, scene, notes)

    if suffix == ".zip":
        archive = profile["archive"]
        limit = archive.get("max_bytes") or (archive["ground_max_bytes"] if target.stem.endswith("_Ground") else archive["oks_max_bytes"])
        status, observed = size_status(len(data), limit)
        st["V001"].findings.append(finding(status, "archive size", observed, f"<= {limit} B",
                                           st["V001"].source_pdf_pages, conflicts=[]))
        diffuse_px = (validate_vpm_zip if kind == "vpm" else validate_npm_zip)(target.stem, files, profile, st)
        add_build_manifest(st, target, data, files, master, manifest, notes, kind)
        if scene:
            add_scene(st, kind, profile, {n: d for n, d in files.items() if n.lower().endswith(".fbx")}, notes,
                      ground_area_m2, footprint_holes, diffuse_px, ground_materials, export_meta, atlases)
    elif suffix == ".fbx":
        check_fbx_headers(st["V002"], {target.name: data})
        if scene:
            add_scene(st, kind, profile, {target.name: data}, notes, ground_area_m2, footprint_holes,
                      ground_materials=ground_materials, export_meta=export_meta, npm_atlas=atlases)
        else:
            notes.append("single FBX: header only; add --scene for the Blender readback")
    elif suffix == ".geojson":
        st["V011"].findings.extend(geojson_findings(
            data, profile, target.stem.endswith("_Ground"), source_name=target.name))
        notes.append("single GeoJSON: only V011 applies")
    elif suffix == ".png" and kind == "npm":
        st["V006"].findings.extend(npm_texture_findings({target.name: data}, profile))
    else:
        notes.append(f"unsupported file type {suffix}")
    # A scene readback of an FBX/ZIP consumes the area: VPM selects the triangle band, and both
    # profiles check Ground footprint coverage. Anywhere else the value is unused.
    scene_readback = bool(scene and kind in ("vpm", "npm") and suffix in (".zip", ".fbx"))
    quad = master.get('oks') if isinstance(master, dict) else master
    if isinstance(quad, list):
        notes.append('multiple OKS sources: quad master not selected; V003 master check remains not_run')
        quad = None  # [D332]: independent dependencies are not permission to choose the first source.
    elif quad is not None:
        quad = Path(quad)
    if scene_readback:
        add_master(st, kind, quad, notes)
    elif quad is not None:
        notes.append(f"master {quad.name} unused: the master check runs with --scene on a ZIP or FBX")
    if ground_area_m2 is not None and not scene_readback:
        notes.append(f"ground_area_m2 {ground_area_m2} unused: the VPM Ground band applies only to a VPM --scene readback")
    if footprint_holes is not None and not scene_readback:
        notes.append("footprint_holes unused: the footprint-hole check applies only to a --scene readback")
    if ground_materials is not None and not scene_readback:
        notes.append("ground_materials unused: the footprint checks apply only to a --scene readback")
    return report(target, data, kind, profiles, st, notes)


def _ground_materials_arg(text: str) -> list[str]:
    """Comma-separated material names or fnmatch globs; empty entries are an error."""
    items = [item.strip() for item in text.split(",")]
    if not items or any(not item for item in items):
        raise argparse.ArgumentTypeError(f"ground_materials entry must be a non-empty name or glob, got {text!r}")
    return items


def _holes_arg(text: str):
    """JSON list of footprint-hole rings: [[[x, y], ...], ...]."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"footprint_holes must be JSON: {exc.msg}") from None
    if not isinstance(data, list) or not data:
        raise argparse.ArgumentTypeError("footprint_holes must be a non-empty JSON list of rings")
    return data


def _area_arg(text: str) -> float:
    try:
        return check_ground_area(float(text))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


FINDING_CODES = {"PNG readable": "png_not_png", "no alpha in ERM/Normal": "png_alpha", "no alpha": "png_alpha",
                 "8-bit RGB/RGBA": "png_format", "flat placeholder": "png_placeholder",
                 "foreign files": "foreign_files", "flat archive": "zip_nested"}


def report(target, data, kind, profiles, stages, notes) -> ValidationReport:
    """Every failed finding of a known kind carries data.code (qa.package corpus: one code per defect, #979)."""
    for stage in stages.values():
        for f in stage.findings:
            if f.status == "fail" and "code" not in f.data and f.name in FINDING_CODES:
                f.data["code"] = FINDING_CODES[f.name]
    return ValidationReport(kind, str(target), digest(data), profiles.pdf_sha256, profiles.pdf_verified,
                            list(stages.values()), notes, profiles.standards_sha256, code_commit())


def write_new(out: Path, data: bytes, inputs: list[Path]):
    """Write `data` to a new file `out` via `out.partial`; refuse any alias of an input or an existing file."""
    partial = Path(str(out) + ".partial")
    taken = {os.path.normcase(str(p.resolve())) for p in inputs}
    for path in (out, partial):
        if os.path.normcase(str(path.resolve())) in taken:
            raise ValueError(f"output {path} is an input")
        if path.exists():
            raise ValueError(f"output {path} already exists; recheck never overwrites")
    with open(partial, "xb") as fh:
        fh.write(data)
    try:
        os.link(partial, out)  # fails if `out` appeared meanwhile: no clobber
    finally:
        partial.unlink()


def run_recheck(old: Path, out: Path, standards: Path, as_json: bool, target: Path | None = None) -> int:
    try:
        old_bytes = old.read_bytes()
        snap = read_snapshot(standards)  # digest and stage schema from the same bytes
        validator = snapshot_validator(snap)
        result = recheck(old_bytes, str(old), snapshot_digest(snap), code_commit(),
                         expected_stages=lambda kind: expected_stages(validator, kind), recheck_target=target)
        stored_target = Path(json.loads(old_bytes)["target"])
        write_new(out, json_bytes(result), [old, stored_target, Path(result["target"])])
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Error: recheck: {exc}", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else recheck_summary(result))
    return result["exit_code"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", type=Path, nargs="?")
    ap.add_argument("--profile", choices=["npm", "vpm"])
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--standards", type=Path, help="standards folder (default: <repo>/standards)")
    ap.add_argument("--scene", action="store_true", help="read every FBX back in background Blender")
    ap.add_argument("--export-meta", type=Path,
                    help="exporter export_meta.json with fbx_records (#1342), or a JSON mapping exact FBX "
                         "filenames to {bounds_m, fbx_sha256}; feeds V013 Z bounds")
    ap.add_argument("--recheck", type=Path, metavar="OLD_REPORT", help="re-read a stored report.json (needs --output)")
    ap.add_argument("--recheck-target", type=Path, metavar="ZIP", help="check this copy instead of the stored target")
    ap.add_argument("--output", type=Path, help="new file for the recheck result (never an existing file)")
    ap.add_argument("--ground-area-m2", type=_area_arg, metavar="M2",
                    help="VPM Ground area = site minus OKS footprint, m2 (reg p.29 triangle band; without it: review)")
    ap.add_argument("--master", action="append", metavar="WORK_FBX | ROLE=PATH",
                    help="quad work FBX of this delivery (DER-03, [D198]); read back with --scene. Build manifest "
                         "stale check per role: --master oks=PATH --master ground=PATH ([D328], #1525)")
    ap.add_argument("--build-manifest", type=Path, metavar="FILE",
                    help="build manifest of a ZIP (default: <stem>.build.json beside it; #1423)")
    ap.add_argument("--footprint-holes", type=_holes_arg, default=None, metavar="JSON",
                    help="JSON list of OKS footprint-hole rings [[[x,y],...], ...]; hole coverage is not_run without it")
    ap.add_argument("--ground-materials", type=_ground_materials_arg, action="append", default=None,
                    metavar="NAMES",
                    help="Ground material names or fnmatch globs (comma-separated, repeatable); only those faces "
                         "feed the footprint area and hole checks (default: every non-UCX render face)")
    ap.add_argument("--npm-atlas", action="append", default=None, metavar="[FBX=]NPM_ATLAS_JSON",
                    help="npm_atlas.json of an NPM OKS FBX (repeatable; FBX= may be omitted for a single FBX or a ZIP "
                         "with one OKS FBX): with --scene, V006 reads the exported UVs against its regions and the "
                         "8 px padding (#1580); without it that finding stays not_run")
    args = ap.parse_args(argv)
    if args.ground_materials is not None:
        args.ground_materials = [item for group in args.ground_materials for item in group]
    if args.recheck is not None:
        if (args.target is not None or args.output is None or args.profile or args.scene
                or args.ground_area_m2 is not None or args.footprint_holes is not None or args.master is not None
                or args.ground_materials is not None or args.export_meta is not None
                or args.build_manifest is not None or args.npm_atlas is not None):
            ap.error("--recheck takes only --recheck-target, --output, --standards and --json")
        return run_recheck(args.recheck, args.output, args.standards or DEFAULT_STANDARDS, args.json,
                           args.recheck_target)
    if args.recheck_target is not None:
        ap.error("--recheck-target is only for --recheck")
    if args.output is not None:
        ap.error("--output is only for --recheck")
    if args.target is None:
        ap.error("target is required")
    if not args.target.is_file():
        print(f"Error: {args.target} does not exist", file=sys.stderr)
        return 1
    profiles = load_profiles(args.standards) if args.standards else load_profiles()
    if args.master is not None:
        try:
            parsed = build_manifest.master_args(args.master)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        args.master = ({r: [Path(p) for p in paths] if isinstance(paths, list) else Path(paths)
                        for r, paths in parsed.items()} if isinstance(parsed, dict) else Path(parsed))
        paths = [p for ps in args.master.values() for p in (ps if isinstance(ps, list) else [ps])] if isinstance(args.master, dict) else [args.master]
        for p in paths:
            if not p.is_file():
                print(f"Error: {p} does not exist", file=sys.stderr)
                return 1
    if args.build_manifest is not None and args.target.suffix.lower() != ".zip":
        print("Error: --build-manifest applies to a ZIP package", file=sys.stderr)
        return 2
    try:
        export_meta = load_z_meta(args.export_meta) if args.export_meta is not None else None
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    npm_atlas = None
    if args.npm_atlas is not None:  # FBX=PATH when the part before the first '=' names an FBX, else a bare PATH
        npm_atlas = [tuple(item.split("=", 1)) if item.split("=", 1)[0].lower().endswith(".fbx") and "=" in item
                     else (None, item) for item in args.npm_atlas]
    try:
        result = validate(args.target, args.profile, profiles, args.scene, args.ground_area_m2,
                          args.footprint_holes, args.master, ground_materials=args.ground_materials,
                          export_meta=export_meta, manifest=args.build_manifest, npm_atlas=npm_atlas)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) if args.json else result.summary())
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
