"""new-case: synthetic SINTEZ 1.6.1 / twinqa shared-check parity (#432).

Fixtures are synthetic, not deliveries. Each group isolates one explicitly mapped
requirement; other requirements in that group are not claimed as covered. Verdicts
retain recommendations/review separately from hard failures. Never fix a checker
or coerce an undefined vendor verdict to pass to obtain agreement.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/agr/sintez_checks_1.6.1.json"
# Focal requirement, boundary, passing value, failing value. No vendor source copied.
CASES = {
    "lp_fbx_format": ("1.1.1", "FBX binary version == 7400", 7400, 7401),
    "lp_naming_masks": ("2.10.3.3", "NPM OKS sequence begins at 001", 1, 0),
    "lp_transforms": ("2.3.14", "rotation-vector squared length <= 0.001 rad²", 0.03162, 0.03163),
    "lp_pivot": ("4.1.5", "pivot XY centre offset <= 10%", 0.2, 0.2002),
    "lp_polycount": ("2.3.6", "NPM triangles <= 150000", 150000, 150001),
    "lp_duplicates": ("2.3.7", "isolated vertices == 0", 0, 1),
    "lp_uv": ("4.1.3", "UV area > 0", 0.5, 0.0),
    "hp_meshes_transforms": ("2.3.18", "rotation-vector squared length <= 0.001 rad²", 0.03162, 0.03163),
    "hp_polycount": ("2.3.9", "VPM hard limit <= 1000000 (target 150000 separate)", 1000000, 1000001),
    "hp_duplicates": ("2.3.11", "isolated vertices == 0", 0, 1),
    "hp_naming_symbols": ("2.10.1", "non-ASCII mesh-name characters == 0", 0, 1),
    "hp_naming_masks": ("2.10.4.2", "mesh suffix == Main", "Main", "MainX"),
    "hp_json_properties": ("2.2.6", "developer is mandatory", "SYNTHETIC", ""),
    "hp_pivot": ("2.9.4a", "pivot XY centre offset <= 10%", 0.2, 0.2002),
    "hp_png": ("2.5.3.4", "256px placeholder has exactly one colour", 1, 2),
}


def inventory():
    doc = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return {c["id"]: c for c in doc["checks"] if c["status"] in ("same", "stricter")}


def fixtures():
    groups = inventory()
    if set(groups) != set(CASES):
        raise ValueError(f"shared inventory changed: {set(groups) ^ set(CASES)}")
    return [dict(id=f"{group}-{variant}", group=group, side=groups[group]["side"],
                 req_num=CASES[group][0], boundary=CASES[group][1], value=CASES[group][i],
                 variant=variant, synthetic=True)
            for group in groups for variant, i in (("pass", 2), ("fail", 3))]


def payload(case):
    """DCC-free synthetic readback and bytes from the same declarative fixture."""
    import base64
    import math
    import struct
    from io import BytesIO
    from PIL import Image
    from twinqa.profiles import load_profiles

    if case not in fixtures():
        raise ValueError("unknown or modified synthetic fixture")
    g, value = case["group"], case["value"]
    name = "SM_Synthetic_001_Main" if case["side"] == "lp" else "SM_Synthetic_Main"
    if g == "lp_naming_masks":
        name = f"SM_Synthetic_{value:03d}_Main"
    if g == "hp_naming_masks":
        name = "SM_Synthetic_" + value
    if g == "hp_naming_symbols":
        name = "SM_Synthetic" + ("А" if value else "A") + "_Main"
    mesh = dict(name=name, triangles=value if "polycount" in g else 4,
                polygon_degrees={"3": value if "polycount" in g else 4},
                rotation_euler_deg=[math.degrees(value) if "transforms" in g else 0, 0, 0],
                scale=[1, 1, 1], location=[0, 0, 0], uv_channels=1,
                udim_tiles=[1001], mirrored_uv_triangles=0, materials=[],
                bounds_m=[[-1 + (value if "pivot" in g else 0), -1, 120],
                          [1 + (value if "pivot" in g else 0), 1, 122]],
                topology=dict(tol_m=0.002, duplicates_and_self_intersections=0,
                              isolated_vertices=value if "duplicates" in g else 0,
                              isolated_edges=0, isolated_polygons=0, zero_length_edges=0))
    rb = dict(source="3101_Synthetic_01.fbx" if case["side"] == "lp" else "SM_Synthetic.fbx",
              readback_ok=True, meshes=[mesh], other_objects=[], images=[],
              fbx_units=dict(unit_scale_factor=100, original_unit_scale_factor=100))
    images = {}
    for role, colour in (("Diffuse", (120,110,100)), ("ERM", (0,170,0)), ("Normal", (128,128,255))):
        image = Image.new("RGB", (256,256), colour)
        if g == "hp_png" and value == 2 and role == "Diffuse":
            image.putpixel((0,0), (1,2,3))
        stream = BytesIO(); image.save(stream, "PNG")
        images[f"T_Synthetic_{role}_1.1001.png"] = stream.getvalue()
    stream = BytesIO(); Image.new("RGB", (256,256), (128,128,128)).save(stream, "JPEG")
    props = {k: "SYNTHETIC" for k in load_profiles().vpm["geojson"]["properties_keys"]}
    props.update(imageBase64=base64.b64encode(stream.getvalue()).decode(), other="",
                 FNO_code="123 456", cadNum="77:01:0000001:1", h_relief="120.000",
                 h_otn="10.000", h_abs="130.000", s_obsh="100.000", s_naz="100.000",
                 s_podz="0.000", spp_gns="100.000")
    if g == "hp_json_properties":
        props["developer"] = value
    geo = dict(type="FeatureCollection", features=[dict(type="ObjectFeature", properties=props,
               geometry=dict(type="Point", coordinates=[12345.678,6789.012]), Glasses=[])])
    return dict(readback=rb, images=images, geojson=json.dumps(geo).encode(),
                header=b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", value if g == "lp_fbx_format" else 7400),
                uv=[[0.1,0.1],[0.9,0.1],[0.1,0.9]] if g != "lp_uv" or value else [[0.1,0.1]]*3)


def validate_data(data):
    """Reject absent/non-finite evidence before a finding filter could hide it."""
    import math
    def finite(value):
        if isinstance(value,float) and not math.isfinite(value):
            raise ValueError("non-finite evidence")
        if isinstance(value,dict):
            for item in value.values(): finite(item)
        if isinstance(value,(list,tuple)):
            for item in value: finite(item)
    if not isinstance(data,dict) or set(data) != {"header","readback","images","geojson","uv"}:
        raise ValueError("partial or unsupported payload")
    finite(data)
    rb = data["readback"]
    if not isinstance(rb,dict) or rb.get("readback_ok") is not True or not rb.get("meshes"):
        raise ValueError("empty or failed readback")
    if not rb.get("source") or "other_objects" not in rb:
        raise ValueError("partial readback")
    for mesh in rb["meshes"]:
        required = {"name","triangles","polygon_degrees","location","scale","rotation_euler_deg","bounds_m"}
        if not isinstance(mesh,dict) or not required <= set(mesh):
            raise ValueError("partial mesh evidence")
        for field in ("location","scale","rotation_euler_deg"):
            vector = mesh[field]
            if not isinstance(vector,list) or len(vector)!=3 or any(type(v) not in (int,float) for v in vector):
                raise ValueError(f"invalid {field}")
        bounds = mesh["bounds_m"]
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(not isinstance(v, list) or len(v) != 3 for v in bounds)
                or any(type(c) not in (int, float) for v in bounds for c in v)):
            raise ValueError("invalid bounds_m: expected two numeric 3D corners")
        lo, hi = bounds
        try:
            if not all(math.isfinite(c) for v in bounds for c in v):
                raise ValueError("invalid bounds_m: non-finite corner")
            if any(a > b for a, b in zip(lo, hi)):
                raise ValueError("invalid bounds_m: inverted corners")
            for axis in (0, 1):
                size = hi[axis] - lo[axis]
                if not math.isfinite(size) or size <= 0:
                    raise ValueError("unmeasurable bounds_m: invalid X/Y span")
                # Mirror the production arithmetic, not an overflow-safe alternative:
                # a finite mathematical ratio is insufficient if the checker sees inf/NaN.
                centre = (lo[axis] + hi[axis]) / 2
                offset = abs(centre - mesh["location"][axis])
                ratio = offset / size
                percent = ratio * 100
                if not all(math.isfinite(v) for v in (centre, offset, ratio, percent)):
                    raise ValueError("unmeasurable bounds_m: non-finite pivot arithmetic")
        except ArithmeticError as exc:
            raise ValueError("unmeasurable bounds_m: pivot arithmetic overflow") from exc
        if type(mesh["triangles"]) is not int or mesh["triangles"]<=0 or not mesh["polygon_degrees"]:
            raise ValueError("empty or invalid triangle evidence")
        if type(mesh.get("uv_channels")) is not int or mesh["uv_channels"] < 1:
            raise ValueError("missing or invalid UV channel evidence")
    if not data["images"] or not all(isinstance(v,bytes) and v for v in data["images"].values()):
        raise ValueError("empty images")
    if not isinstance(data["geojson"],bytes) or not data["geojson"]:
        raise ValueError("empty geojson")
    if not isinstance(data["uv"],list) or len(data["uv"])<3:
        raise ValueError("empty UV evidence")


def evaluate(case, data):
    """Run production twinqa functions; retain raw status and observed evidence."""
    from twinqa.fbx_header import check_fbx_header
    from twinqa.geojson import geojson_findings
    from twinqa.png import vpm_texture_findings
    from twinqa.profiles import load_profiles
    from twinqa.scene import scene_findings
    from twinqa.naming import mesh_name_findings, mesh_name_violation
    from twinqa.uv import face_issue

    if case not in fixtures():
        raise ValueError("unknown or modified synthetic fixture")
    validate_data(data)
    g = case["group"]
    kind = "npm" if case["side"] == "lp" else "vpm"
    profile = load_profiles().profile(kind)
    if g == "lp_fbx_format":
        ok, observed = check_fbx_header(data["header"])
        status = "pass" if ok else "fail"
    elif g == "lp_uv":
        observed = face_issue(data["uv"], 1001, 2048, 0)
        status = "fail" if observed else "pass"
    elif g == "hp_naming_symbols":
        name = data["readback"]["meshes"][0]["name"]
        observed = mesh_name_violation(name, "vpm", "oks", name[3:-5], 254)
        status = "fail" if observed else "pass"
    elif "naming" in g:
        found = mesh_name_findings([m["name"] for m in data["readback"]["meshes"]], kind,
                                  "oks", Path(data["readback"]["source"]).stem, 254, "synthetic")
        status = found[0].status; observed = found[0].observed
    elif g == "hp_png":
        found, _ = vpm_texture_findings(data["images"], profile, "T_Synthetic")
        unsupported = [f.name for f in found if f.status != "pass" and f.name != "flat placeholder"]
        if unsupported:
            raise ValueError(f"unmapped PNG findings: {unsupported}")
        selected = [f for f in found if f.name == "flat placeholder"]
        status = "fail" if selected else "pass"
        observed = [f.observed for f in selected]
    elif g == "hp_json_properties":
        found = geojson_findings(data["geojson"], profile, False)
        unsupported = [f.name for f in found if f.status != "pass" and f.name != "developer empty"]
        if unsupported:
            raise ValueError(f"unmapped GeoJSON findings: {unsupported}")
        selected = [f for f in found if f.name == "developer empty"]
        status = "fail" if selected else "pass"
        observed = [f.observed for f in selected]
    else:
        found = scene_findings(data["readback"], kind, "oks", profile)
        label = ("applied transforms" if "transforms" in g else "pivot at geometric centre"
                 if "pivot" in g else "triangle count" if "polycount" in g else "topology defects")
        selected = [f for group in found.values() for f in group if f.name == label]
        if not selected and g == "lp_pivot":
            return dict(req_num=case["req_num"], status="not_measured",
                        observed="scene_findings only evaluates geometric-centre pivot for VPM")
        if len(selected) != 1:
            raise ValueError(f"missing or duplicate twinqa finding: {label}")
        status = selected[0].status; observed = selected[0].observed
    if status not in ("pass", "fail", "review"):
        raise ValueError(f"unmeasured twinqa status: {status}")
    return dict(req_num=case["req_num"], status=status, observed=observed)


def compare(case, report, ours):
    """Diff one explicit req_num. Reject incomplete, contradictory or undefined evidence."""
    if case not in fixtures() or not isinstance(report, dict) or report.get("error", "missing") is not None:
        raise ValueError("invalid fixture or vendor run error")
    rows = report.get(case["side"])
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("missing checklist")
    # The vendor uses Cyrillic а on this one row; preserve the original ID in evidence.
    req = case["req_num"]
    matches = [r for r in rows if r.get("req_num") in (req, "2.9.4а" if req == "2.9.4a" else req)]
    if len(matches) != 1:
        raise ValueError(f"missing or duplicate vendor requirement {req}")
    row = matches[0]
    if row.get("auto") is not True:
        raise ValueError(f"vendor requirement not measured: {req}")
    state = row.get("state")
    errors, recs = row.get("errors_count"), row.get("recommendations_count")
    if any(type(n) is not int or n < 0 for n in (errors, recs)):
        raise ValueError(f"invalid vendor counts: {req}")
    if state not in ("verified", "failed") or (state == "verified" and (errors or recs)) or (state == "failed" and not (errors or recs)):
        raise ValueError(f"unmeasured or inconsistent vendor state: {req}: {state}")
    status = "fail" if errors else "review" if recs else "pass"
    if ours.get("req_num") != req or ours.get("status") not in ("pass", "fail", "review", "not_measured"):
        raise ValueError(f"invalid twinqa result: {req}")
    return dict(fixture=case["id"], req_num=req, vendor=dict(status=status, raw=row),
                twinqa=ours, agreement=status == ours["status"])


def run_live(case, output, blender):
    """Run both lanes on one synthetic ZIP. All writes stay in a new private directory."""
    import hashlib
    import subprocess
    import zipfile
    from twinqa.io import read_json

    if case not in fixtures():
        raise ValueError("unknown fixture")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        with (output / name).open("x", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
    def run(script, args, log):
        cmd = [str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
               "--python", str(script), "--", *map(str,args)]
        with (output/log).open("x",encoding="utf-8") as f:
            completed = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=900)
        if completed.returncode:
            raise RuntimeError(f"Blender exited {completed.returncode}: {output/log}")
        return dict(command=cmd, exit_code=completed.returncode)
    data = payload(case)
    save("fixture.json", dict(case=case, mesh=data["readback"]["meshes"][0], uv=data["uv"],
                              source=data["readback"]["source"]))
    commands = [run(ROOT/"tools/blender/sintez_parity_fixture.py", [output/"fixture.json", output], "fixture.log")]
    facts = read_json((output/"readback.json").read_bytes())
    if facts.get("blender") != "5.1.2" or facts.get("extension_version") != "1.6.1":
        raise ValueError("Blender 5.1.2 / SINTEZ 1.6.1 required")
    fbx = output / data["readback"]["source"]
    if case["group"] == "lp_fbx_format":
        # Only the version number changes; 7401 retains the same 32-bit-node layout.
        raw = bytearray(fbx.read_bytes()); raw[23:27] = data["header"][23:27]
        fbx.write_bytes(raw)
    data["header"] = fbx.read_bytes()
    data["readback"] = facts["readback"]
    data["uv"] = facts["uv"]
    package = output / "packages"
    package.mkdir()
    archive_name = "3101_Synthetic" if case["side"] == "lp" else "SM_Synthetic"
    archive = package / (archive_name + ".zip")
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
        z.write(fbx,fbx.name)
        if case["side"] == "hp":
            z.writestr("SM_Synthetic.geojson",data["geojson"])
            for name, raw in data["images"].items():
                z.writestr(name,raw)
    before = hashlib.sha256(archive.read_bytes()).hexdigest()
    commands.append(run(ROOT/"jobs/KPP1/scripts/run_agr_checker.py", [package,output/"vendor.json"], "vendor.log"))
    if hashlib.sha256(archive.read_bytes()).hexdigest() != before:
        raise ValueError("synthetic ZIP changed during vendor run")
    # Read the very same archived PNG/GeoJSON/FBX bytes for the pure-Python lane.
    with zipfile.ZipFile(archive) as z:
        data["header"] = z.read(fbx.name)
        if case["side"] == "hp":
            data["images"] = {n:z.read(n) for n in z.namelist() if n.endswith(".png")}
            data["geojson"] = z.read("SM_Synthetic.geojson")
    result = compare(case, read_json((output/"vendor.json").read_bytes()), evaluate(case,data))
    result.update(synthetic=True, archive_sha256=before, commands=commands,
                  blender=facts["blender"], extension_version=facts["extension_version"])
    save("comparison.json",result)
    return result


def main(argv=None):
    """DCC-free by default; live disagreements exit 1, unusable evidence exits 2."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True,help="new evidence directory (never reused)")
    parser.add_argument("--dcc",action="store_true",help="explicitly execute SINTEZ in Blender")
    parser.add_argument("--blender",help="explicit Blender 5.1.2 executable; required with --dcc")
    parser.add_argument("--case",action="append",choices=[c["id"] for c in fixtures()])
    args = parser.parse_args(argv)
    if args.dcc and not args.blender:
        parser.error("--dcc requires --blender")
    try:
        output = args.output.resolve()
        output.mkdir(parents=True,exist_ok=False)
        rows = []
        for case in fixtures():
            if args.case and case["id"] not in args.case:
                continue
            if args.dcc:
                rows.append(run_live(case,output/case["id"],args.blender))
            else:
                rows.append(dict(fixture=case["id"],req_num=case["req_num"],
                                 twinqa=evaluate(case,payload(case)),vendor="not_measured",agreement=None))
        with (output/"summary.json").open("x",encoding="utf-8") as f:
            json.dump(dict(synthetic=True,dcc_executed=args.dcc,rows=rows),f,indent=2,allow_nan=False)
        return 1 if args.dcc and any(not r["agreement"] for r in rows) else 0
    except (OSError,ValueError,RuntimeError) as exc:
        print(f"parity error: {exc}",file=__import__('sys').stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())



