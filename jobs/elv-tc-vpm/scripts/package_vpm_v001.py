"""elv-tc-vpm: assemble the VPM OKS package SM_Elevatornaya_1A.zip (flat: FBX + GeoJSON + PNG).

py -3 package_vpm_v001.py <delivery_dir> <textures_dir>

<delivery_dir>/package/ holds SM_Elevatornaya_1A.fbx (delivery_export_v001.py) and receives byte copies of the
T_Elevatornaya_1A_*.png set and the GeoJSON; the ZIP is written to <delivery_dir>/SM_Elevatornaya_1A.zip.
Never overwrites. GeoJSON per reg App.3 (p.51-55), literal ObjectFeature, exact key order (VPM_STANDARD.yaml).
Values only from the sources (booklet 27.01.2025: sheets 1, 3, 5, 10, 18, 19, 41, 42); unknown values stay empty
and are listed as blockers - never invented [D011]: FNO_code empty by user decision 2026-11-04, MSK-77 point
not derivable from the sources (null, documented TODO).
"""
import base64
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ADDRESS = "Elevatornaya_1A"
STEM = f"SM_{ADDRESS}"
out_dir, tex = Path(sys.argv[1]), Path(sys.argv[2])
pkg = out_dir / "package"
zpath = out_dir / f"{STEM}.zip"
gpath = pkg / f"{STEM}.geojson"
rep_path = out_dir / "package_report_v001.json"
for p in (zpath, gpath, rep_path):
    if p.exists():
        raise SystemExit(f"output exists, refusing to overwrite: {p}")
if not (pkg / f"{STEM}.fbx").is_file():
    raise SystemExit("run delivery_export_v001.py first")

pngs = sorted(tex.glob(f"T_{ADDRESS}_*.png"))
for f in pngs:
    dst = pkg / f.name
    if dst.exists():
        raise SystemExit(f"output exists: {dst}")
    shutil.copy2(f, dst)


def srgb8(lin):
    c = lin * 12.92 if lin <= 0.0031308 else 1.055 * lin ** (1 / 2.4) - 0.055
    return int(round(max(0.0, min(1.0, c)) * 255))


# MainGlass material of build-v004 (Principled BSDF, linear Base Color 0.85/0.92/0.95, alpha 0.3, roughness 0.05,
# metallic 0, IOR 1.5); D11 glass clear. transparency: 0 = fully transparent, 1 = opaque (reg p.55 §22) -> alpha.
GLASS_LIN = (0.85, 0.92, 0.95)
glasses = {f"M_{ADDRESS}_MainGlass_1": {
    "color_RGB": {"Red": srgb8(GLASS_LIN[0]), "Green": srgb8(GLASS_LIN[1]), "Blue": srgb8(GLASS_LIN[2])},
    "transparency": 0.3, "refraction": 1.5, "roughness": 0.05, "metallicity": 0.0}}

img = base64.b64encode((out_dir / "thumbnail_256.jpg").read_bytes()).decode("ascii")
props = {
    "address": "г. Москва, внутригородское муниципальное образование Бирюлёво Восточное, ул. Элеваторная, вл. 1А",
    "okrug": "",  # not stated in the booklet: TODO from the customer (do not infer)
    "rajon": "Бирюлёво Восточное",
    "name": "Торговый центр",
    "developer": "",  # booklet names only the customer (Заказчик ООО 'ЛОГИСТИК-СЕРВИС'), not the developer: TODO
    "designer": "ООО 'Темпро'",
    "cadNum": "77:05:0010002:6",
    "FNO_code": "",  # user decision 2026-11-04: empty for now, never invented
    "FNO_name": "",  # depends on FNO_code: TODO
    "ZU_area": 1.0386,  # sheet 42 item 1: 10386 m2
    "h_relief": 167.65,  # +-0.000 = 167.65 (sheets 10, 18, 19)
    "h_otn": 16.22,  # sheet 42 items 7-8
    "h_abs": 183.87,  # sheet 42 items 9-10
    "s_obsh": 8639.11,  # sheet 42 item 4
    "s_naz": 8639.11,  # sheet 42 item 4.1
    "s_podz": 0,  # sheet 42 item 4.2
    "spp_gns": 8384.6,  # sheet 42 item 3
    "act_AGR": "",
    "imageBase64": img,
    "other": "",
}
geo = {"type": "FeatureCollection", "features": [{
    "type": "ObjectFeature", "properties": props,
    "geometry": {"type": "Point", "coordinates": [None, None]},  # MSK-77 point: TODO (sources give no building point)
    "Glasses": [glasses]}]}
gpath.write_text(json.dumps(geo, ensure_ascii=False, indent=2), encoding="utf-8")

files = sorted(p for p in pkg.iterdir() if p.is_file())
with zipfile.ZipFile(zpath, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in files:
        z.write(f, f.name)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


report = {
    "zip": str(zpath), "zip_bytes": zpath.stat().st_size, "zip_sha256": sha(zpath),
    "limit_bytes": 500 * 1024 ** 2,
    "files": [{"name": f.name, "bytes": f.stat().st_size, "sha256": sha(f)} for f in files],
    "png_count": len(pngs),
    "geojson_blockers": ["geometry.coordinates (MSK-77) - not in sources", "FNO_code - user decision: empty",
                         "FNO_name", "okrug - not in booklet", "developer - booklet names only the customer"],
    "geojson_proposals": ["Glasses values from the MainGlass material (D11 clear)"],
}
rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "files"}, ensure_ascii=False, indent=1))
