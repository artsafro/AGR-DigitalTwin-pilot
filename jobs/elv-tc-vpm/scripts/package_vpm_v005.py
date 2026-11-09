"""elv-tc-vpm delivery v005 = package_vpm_v004.py with the tex-v006 set and the delivery-v005 FBX / thumbnail;
only change: report name package_report_v005.json. All GeoJSON values as v004.
v004 header follows.
elv-tc-vpm delivery v004 = package_vpm_v003.py with the tex-v005 set (warm-beige wood) and the delivery-v004 thumbnail;
only change: report name package_report_v004.json. All GeoJSON values as v003.
v003 header follows.
elv-tc-vpm delivery v003: package SM_Elevatornaya_Vl_1_A_001.zip = package_vpm_v002.py with (user 2026-11-05):
- stem SM_Elevatornaya_Vl_1_A_001 (customer stem), textures T_Elevatornaya_Vl_1_A_001_* (tex-v004);
- address as in the customer's GeoJSON (with «; вл. 1А, стр. 1, 2, 3»; the TZ itself doubts it, R12 -> flagged);
- MSK-77 point re-derived for OUR pivot (see MSK below and delivery_report_v003.md);
- ZU_area stays 1.0386: the regulation unit is hectares (reg p.53-55, docs/domain/npm-vpm.md; SINTEZ constants: float,
  4 decimals) = 10 386 m2 (booklet sheet 42 item 1); the customer's 10386.0000 is the m2 value in the ha field;
- FNO_code / FNO_name empty (never invented); other fields as v002.
v002 header follows.
elv-tc-vpm: assemble the VPM OKS package SM_Elevatornaya_1A.zip (flat: FBX + GeoJSON + PNG). v002 = v001 +
developer (booklet sheet 2, raster title page: «ЗАСТРОЙЩИК: Генеральный директор ООО "ЛОГИСТИК-СЕРВИС"») and okrug
derived from the address (district Бирюлёво Восточное -> Южный административный округ of Moscow).

py -3 package_vpm_v003.py <delivery_dir> <textures_dir>

<delivery_dir>/package/ holds SM_Elevatornaya_1A.fbx (delivery_export_v002.py) and receives byte copies of the
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

ADDRESS = "Elevatornaya_Vl_1_A_001"
STEM = f"SM_{ADDRESS}"
out_dir, tex = Path(sys.argv[1]), Path(sys.argv[2])
pkg = out_dir / "package"
zpath = out_dir / f"{STEM}.zip"
gpath = pkg / f"{STEM}.geojson"
rep_path = out_dir / "package_report_v005.json"
for p in (zpath, gpath, rep_path):
    if p.exists():
        raise SystemExit(f"output exists, refusing to overwrite: {p}")
if not (pkg / f"{STEM}.fbx").is_file():
    raise SystemExit("run delivery_export_v005.py first")

# MSK-77 point of OUR origin (0, 0, 0). The customer's GeoJSON point [9676.355, -7135.700] is the origin of their FBX
# (their scene: Blender X = MSK y (east), Blender Y = MSK x (north); the SINTEZ checker places coordinates[0] on Blender
# X, coordinates[1] on Y: hp fix_coordinates). Rigid 2D fit of plan sections (customer-blank-v001/compare.md §3):
# p_ours = R p_theirs + t, t = (-0.064, +0.578) m, R = -0.03..-0.07 deg. Our origin in their local frame:
# p_theirs = R^-1 (0 - t) = (+0.064, -0.578) (the rotation moves this 0.58 m vector by < 1 mm), so
# MSK of our origin = (9676.355 + 0.064, -7135.700 - 0.578) = (9676.419, -7136.278).
MSK_THEIRS, T_FIT = (9676.355, -7135.700), (-0.064, 0.578)
MSK = (round(MSK_THEIRS[0] - T_FIT[0], 3), round(MSK_THEIRS[1] - T_FIT[1], 3))
assert MSK == (9676.419, -7136.278), MSK
assert all(len(repr(c).split(".")[1]) == 3 for c in MSK)   # SINTEZ hp: exactly 3 decimals in coordinates

pngs = sorted(tex.glob(f"T_{ADDRESS}_*.png"))
for f in pngs:
    dst = pkg / f.name
    if dst.exists():
        if dst.read_bytes() == f.read_bytes():
            continue                 # identical copy from an earlier run of this script (same tex-v004 set)
        raise SystemExit(f"output exists: {dst}")
    shutil.copy2(f, dst)


def srgb8(lin):
    c = lin * 12.92 if lin <= 0.0031308 else 1.055 * lin ** (1 / 2.4) - 0.055
    return int(round(max(0.0, min(1.0, c)) * 255))


# MainGlass material of build-v004 / build-v006 (unchanged) (Principled BSDF, linear Base Color 0.85/0.92/0.95, alpha 0.3, roughness 0.05,
# metallic 0, IOR 1.5); D11 glass clear. transparency: 0 = fully transparent, 1 = opaque (reg p.55 §22) -> alpha.
GLASS_LIN = (0.85, 0.92, 0.95)
glasses = {f"M_{ADDRESS}_MainGlass_1": {
    "color_RGB": {"Red": srgb8(GLASS_LIN[0]), "Green": srgb8(GLASS_LIN[1]), "Blue": srgb8(GLASS_LIN[2])},
    "transparency": 0.3, "refraction": 1.5, "roughness": 0.05,
    "metallicity": 0.84}}   # v003: [D016] / SINTEZ recommendation 0.84 (v002: 0.0 from the Blender material)

img = base64.b64encode((out_dir / "thumbnail_256.jpg").read_bytes()).decode("ascii")
props = {
    # customer GeoJSON 2026-11-05 (booklet title page wording); the TZ (R12, img_011) doubts the doubled «вл. 1А»
    "address": "г. Москва, внутригородское муниципальное образование Бирюлёво Восточное, ул. Элеваторная, вл. 1А; "
               "вл. 1А, стр. 1, 2, 3",
    "okrug": "Южный административный округ",  # derived from the address (district Бирюлёво Восточное -> ЮАО)
    "rajon": "Бирюлёво Восточное",
    "name": "Торговый центр",
    "developer": "ООО 'ЛОГИСТИК-СЕРВИС'",  # booklet sheet 2: ЗАСТРОЙЩИК; v003: typewriter apostrophe (reg p.53-55, SINTEZ)
    "designer": "ООО 'Темпро'",
    "cadNum": "77:05:0010002:6",
    "FNO_code": "",  # user decision 2026-11-04: empty for now, never invented
    "FNO_name": "",  # depends on FNO_code: TODO
    "ZU_area": 1.0386,  # hectares (reg p.53-55): sheet 42 item 1 = 10386 m2; customer wrote 10386.0000 (m2)
    "h_relief": 167.65,  # +-0.000 = 167.65 (sheets 10, 18, 19)
    "h_otn": 16.22,  # sheet 42 items 7-8
    "h_abs": 183.87,  # sheet 42 items 9-10
    "s_obsh": 8639.11,  # sheet 42 item 4
    "s_naz": 8639.11,  # sheet 42 item 4.1
    # sheet 42 item 4.2 = 0, written 0.00: SINTEZ accepts "" and 0.00 (only recommends ""), the project validator V011
    # fails "" (reg p.27: mandatory) -> 0.00 passes both
    "s_podz": 0,
    "spp_gns": 8384.6,  # sheet 42 item 3; written as 8384.60 below (SINTEZ: exactly 2 decimals)
    "act_AGR": "",
    "imageBase64": img,
    "other": "",
}
geo = {"type": "FeatureCollection", "features": [{
    "type": "ObjectFeature", "properties": props,
    "geometry": {"type": "Point", "coordinates": list(MSK)},  # MSK-77 of our 0,0,0 (derivation above)
    "Glasses": [glasses]}]}
gtxt = json.dumps(geo, ensure_ascii=False, indent=2)
assert gtxt.count('"spp_gns": 8384.6,') == 1
gtxt = gtxt.replace('"spp_gns": 8384.6,', '"spp_gns": 8384.60,')
assert gtxt.count('"s_podz": 0,') == 1
gtxt = gtxt.replace('"s_podz": 0,', '"s_podz": 0.00,')
gpath.write_text(gtxt, encoding="utf-8")

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
    "geojson_blockers": ["FNO_code - user decision: empty",
                         "FNO_name - user decision: empty"],
    "geojson_sources": {"developer": "booklet sheet 2 (raster title page): ЗАСТРОЙЩИК - Генеральный директор "
                                     "ООО \"ЛОГИСТИК-СЕРВИС\" (sheet 3 text layer: Заказчик, same company)",
                        "okrug": "derived from the address (district Бирюлёво Восточное -> Южный административный "
                                 "округ of Moscow); not stated in the booklet"},
    "geojson_proposals": ["Glasses values from the MainGlass material (D11 clear)"],
    "msk77": {"customer_point": list(MSK_THEIRS), "fit_t_theirs_to_ours_m": list(T_FIT), "ours": list(MSK),
              "rule": "ours = customer - t (their origin sits at their MSK point; p_ours = p_theirs + t)",
              "axes": "coordinates[0] = Blender X = MSK y (east), [1] = Blender Y = MSK x (north), as the customer file"},
    "flags": ["address taken from the customer GeoJSON; the TZ (R12) questions it (Yandex: Элеваторная ул., 1)",
              "ZU_area in ha per the regulation (1.0386); the customer file has 10386.0000 in the same field"],
}
rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "files"}, ensure_ascii=False, indent=1))
