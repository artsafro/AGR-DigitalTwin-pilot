"""Shared VPM package step (`dt derive package`): FBX + external PNG set (+ GeoJSON) -> SM_<Address>.zip.

Pattern: n/a | new-case: one shared VPM packaging tool replacing the per-job package_vpm.py copies (#1106).

Generalised from jobs/KPP1/scripts/package_vpm.py (KPP1 v005) and its PSU275 / TEC26 copies; the per-job
constants (building name, placement datum, glass proposal, deferral note) come from --object <json> instead of code.
Usage: python tools/derive/package_vpm.py <package_dir> <textures_dir> [--object object.json] [--no-geojson]
    [--deferred-note TEXT]
<package_dir> holds SM_<Address>.fbx (export_vpm). Export metadata supplies the address, Z top and thumbnail,
and must bind each packed FBX by SHA-256; re-export if no recorded hash is available.
GeoJSON follows reg App.3 (p.51-55): literal ObjectFeature, exact key order;
unknown OKS values stay "" / null and are listed as blockers in <zip>.delivery.json, never invented
(conflicts #2). --no-geojson (user decision 2026-10-07 [D224]): ZIP holds FBX + PNG only; --object is then optional.
object.json: {"name": str, "placement": Placement, "glasses": {material: {...}} (optional, default: the KPP1
clear-glass proposal)}. The ZIP and <zip>.delivery.json must not exist yet (new version, no overwrite).
Ground VPM also reserves ground-udim.json and ground-udim.md next to the ZIP; use a separate output
directory per Ground package. The tables come from the packed FBX and map names, not input tables.
"""
import argparse
import base64
import json
import math
import os
import shutil
import stat
import sys
import zipfile
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.max.agr_tools import package_core
from adapters.max.agr_tools.export_meta import address_meta_path, export_binding, export_records, load_meta

DEFAULT_NOTE = "GeoJSON deferred by the user (2026-10-07) [D224]"


def default_glasses(address):
    return {f"M_{address}_MainGlass_1": {  # Revit: ADSK_Стекло_Прозрачное бесцветное (clear); values are proposals
        "color_RGB": {"Red": 225, "Green": 235, "Blue": 235},
        "transparency": 0.2, "refraction": 1.5, "roughness": 0.05, "metallicity": 0.0}}


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def load_object(path):
    try:
        obj = json.load(open(path, encoding="utf-8"), object_pairs_hook=unique_object)
    except ValueError as exc:
        raise ValueError(f"object {path}: {exc}") from exc
    for key in ("name", "placement"):
        if key not in obj:
            raise ValueError(f"object {path}: missing {key!r}")
    unknown = set(obj) - {"name", "placement", "glasses", "source"}
    if unknown:
        raise ValueError(f"object {path}: unknown keys {sorted(unknown)}")
    from dt_ai.core.models import Placement
    try:
        obj["placement"] = Placement.model_validate(obj["placement"])
    except ValueError as exc:
        raise ValueError(f"object {path}: placement: {exc}") from exc
    if not isinstance(obj["name"], str) or not obj["name"].strip():
        raise ValueError(f"object {path}: empty name")
    return obj


def _remove_owned_file(path):
    path = Path(path)
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        # On Windows copystat can make a newly copied PNG read-only.
        if os.name != 'nt' or path.stat().st_mode & stat.S_IWRITE:
            raise
        path.chmod(stat.S_IWRITE)
        path.unlink(missing_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dt derive package", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package_dir")
    ap.add_argument("textures_dir")
    ap.add_argument('--meta', help='explicit export metadata (required when several exporter sidecars exist)')
    ap.add_argument("--object", help="object.json with name, placement, glasses (required unless --no-geojson)")
    ap.add_argument("--no-geojson", action="store_true")
    ap.add_argument("--deferred-note", default=DEFAULT_NOTE, help="delivery report blocker text with --no-geojson")
    a = ap.parse_args(argv)
    pkg, tex = a.package_dir, a.textures_dir
    if not a.no_geojson and not a.object:
        raise ValueError("GeoJSON needs --object (name, placement); pass --no-geojson to defer it")
    meta_path = address_meta_path(pkg, a.meta, prefer_oks=False)
    meta = load_meta(meta_path)
    A = meta["address"]
    stem = f"SM_{A}"
    if not os.path.isfile(os.path.join(pkg, f"{stem}.fbx")):
        raise ValueError(f"{stem}.fbx missing in {pkg}")
    pkg_names = sorted(os.listdir(pkg))
    # Match the full package stem (including a Ground suffix), not a filename prefix.
    for name in pkg_names:
        if (match := package_core.VPM_TEX.fullmatch(name)) and match['stem'] != A:
            raise ValueError(f"foreign VPM texture {name}: expected texture stem T_{A}")

    zpath = os.path.join(pkg, "..", f"{stem}.zip")
    rpath = zpath + ".delivery.json"  # per archive, never a parent-wide report (#1682)
    gpath = os.path.join(pkg, f"{stem}.geojson")
    udim = package_core.ground_udim_paths(zpath)
    for p in (zpath, rpath, rpath + '.partial', zpath + '.partial', *udim, *(p + '.partial' for p in udim)):
        if os.path.lexists(p):
            raise FileExistsError(f"output {p} already exists; choose a new version")
    if a.no_geojson and os.path.lexists(gpath):
        raise ValueError(f"--no-geojson but {gpath} exists; it would be packed (remove it or drop --no-geojson)")
    if os.path.realpath(tex) == os.path.realpath(pkg):
        raise ValueError("textures_dir aliases package_dir")
    obj = load_object(a.object) if a.object else None
    heights = obj["placement"].heights(meta["h_otn_model_max_z_m"]) if not a.no_geojson else None

    pngs = [f for f in sorted(os.listdir(tex))
            if (match := package_core.VPM_TEX.fullmatch(f)) and match['stem'] == A]
    if not pngs:
        raise ValueError(f"no T_{A}_*.png textures in {tex}")
    for target in [gpath, *(os.path.join(pkg, f) for f in pngs)]:
        if os.path.lexists(target):
            raise FileExistsError(f"output {target} already exists; choose a new version")

    table_names = {*package_core.GROUND_UDIM_FILES, *(n + '.partial' for n in package_core.GROUND_UDIM_FILES)}
    skipped_tables = [{'item': f, 'reason': 'Ground UDIM tables are package sidecars, not ZIP members'}
                      for f in pkg_names if f.casefold() in table_names]
    existing = [f for f in pkg_names if f != 'export_meta.json' and not f.endswith('.fbx.export_meta.json')
                and f.casefold() not in table_names]
    generated = pngs if a.no_geojson else [*pngs, os.path.basename(gpath)]
    members = sorted(existing + generated)
    archive = {'name': os.path.basename(zpath), 'members': [{'name': f} for f in members],
               'limit': package_core.LIMITS['vpm_ground' if udim else 'vpm_oks']}
    binding, problems = export_binding(pkg, archive['members'], export_records(pkg, meta_path, include_lights=True))
    if problems:
        raise ValueError('; '.join(problems))
    expected = {row['name']: row['zip_sha256'] for row in binding['members']}

    # Roll back only paths we own [D349]: register after exclusive creation, before writing bytes.
    # package_core owns cleanup of its own ZIP and receipt .partial files.
    with ExitStack() as rollback:
        for f in pngs:
            source, target = os.path.join(tex, f), os.path.join(pkg, f)
            with open(source, 'rb') as inp, open(target, 'xb') as out:
                rollback.callback(_remove_owned_file, target)
                shutil.copyfileobj(inp, out)
            shutil.copystat(source, target)

        props = None
        if not a.no_geojson:
            img = base64.b64encode(open(meta["thumbnail"], "rb").read()).decode("ascii")
            props = {
                "address": "", "okrug": "", "rajon": "",
                "name": obj["name"],
                "developer": "", "designer": "", "cadNum": "", "FNO_code": "", "FNO_name": "", "ZU_area": "",
                **heights,
                "s_obsh": "", "s_naz": "", "s_podz": "", "spp_gns": "", "act_AGR": "",
                "imageBase64": img, "other": "",
            }
            glasses = obj.get("glasses") or default_glasses(A)
            geo = {"type": "FeatureCollection", "features": [{
                "type": "ObjectFeature", "properties": props,
                "geometry": {"type": "Point", "coordinates": [None, None]},
                "Glasses": [glasses]}]}  # list with one object keyed by glass material (reg p.51-52 example)
            with open(gpath, "x", encoding="utf-8") as fh:
                rollback.callback(_remove_owned_file, gpath)
                json.dump(geo, fh, ensure_ascii=False, indent=2)

        written, _ = package_core._write_zip(pkg, archive, zpath, expected_sha256=expected)
        if written is None:
            raise ValueError(f'archive exceeds {archive["limit"]} bytes')
        for path in udim:
            rollback.callback(_remove_owned_file, path)
        rollback.callback(_remove_owned_file, written)

        blockers = ([k for k, v in props.items() if v == "" and k != "other"] + ["geometry.coordinates (MSK-77)"]
                    if props is not None else [a.deferred_note])
        report = {"zip": os.path.abspath(zpath), "zip_bytes": os.path.getsize(zpath),
                  "files": members, "geojson_blockers_unknown_in_source": blockers,
                  "export_binding": binding, "passed": False, "status": "packaged_not_validated",
                  "geojson_proposals": ["Glasses values (colour/transparency/refraction/roughness/metallicity)"],
                  "address_placeholder": A}
        if skipped_tables:
            report['skipped'] = skipped_tables
        if props is not None:
            report['placement'] = obj['placement'].model_dump(mode='json')
            if obj['placement'].height_system == 'unknown':
                blockers.append('placement.height_system unknown; absolute datum unconfirmed')
        report.update(package_core.delivery_receipt(zpath))
        receipt = package_core.write_delivery_report(zpath, report)
        rollback.callback(_remove_owned_file, receipt)
        print(json.dumps({k: v for k, v in report.items() if k != "files"}, ensure_ascii=False, indent=1),
              len(report["files"]), "files")
        rollback.pop_all()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
