"""#298: run the merged MAF (#185) and Flora (#191) scene checks with their inputs on the NPM site scene.

py -3 jobs/VATUTINO-SITE/scene_checks.py --place C:/x/t_5e2eb833/place-v004/npm \
    --prepared C:/x/t_5e2eb833/v009/npm/prepared.blend --out C:/x/t_5e2eb833/checks-v001

The delivery FBX merges MAF into one GroundEl mesh and Flora into one Flora mesh (GND-11), so the per-object
checks (MAF bbox vs specification, Flora height/crown vs schedule) cannot name an object there. This driver
exports the per-instance MAF + Flora objects of the prepared scene (the same geometry the assembly merges)
as a check FBX, reads it back in a clean Blender, and runs twinqa.scene.scene_findings with
  maf_sizes      = schedule size [x, y, z] of each MAF type (place results meta 'spec'; None -> not checked),
  flora_schedule = height: midpoint of the schedule band h_m (*T3509); crown: NOT in the schedule (gate-1 F3),
                   so the reference is the catalogue crown of the picked library model x base_scale (labelled).
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
SITE_PARTS = ROOT / "jobs/VATUTINO-SITE/site-parts.json"
EXPORT = Path(__file__).with_name("export_check_instances.py")


def catalogue_crowns(site_parts: dict) -> dict[str, float]:
    """NPM library object -> catalogue crown diameter, m (the library model, not the source)."""
    out = {}
    for pos in site_parts["flora"]:
        for c in pos.get("cands", []):
            name = (c.get("obj") or {}).get("NPM")
            if name and isinstance(c.get("crown"), (int, float)):
                out.setdefault(name, float(c["crown"]))
    return out


def build_inputs(instances: list[dict], meta: dict, crowns: dict[str, float]):
    """-> rename {blend name: check name}, flora_schedule, maf_sizes, gaps [str]."""
    rename, flora, maf, gaps = {}, {}, {}, []
    for inst in instances:
        name, lib = inst["name"], inst["library_id"]
        m = meta.get(lib)
        if m is None:
            gaps.append(f"{name}: library {lib} has no meta")
            continue
        if m["kind"] == "maf":
            dst = f"{name}_GroundEl"
            rename[name] = dst
            if m.get("spec"):
                maf[dst] = [float(v) for v in m["spec"]]
            else:
                gaps.append(f"{lib}: no schedule size ({m.get('spec_raw')})")
        elif m["kind"] == "flora":
            dst = f"Flora_{name}"
            rename[name] = dst
            band, crown = m.get("h_m"), crowns.get(lib)
            if not band or crown is None:
                gaps.append(f"{lib}: no height band or catalogue crown")
                continue
            flora[dst] = {"height_m": round((band[0] + band[1]) / 2, 4),
                          "crown_m": round(crown * float(m.get("base_scale") or 1.0), 4)}
    return rename, flora, maf, sorted(set(gaps))


def summarize(found: dict) -> list[dict]:
    """Group the MAF/Flora findings by check family: counts per status and the first fails."""
    groups = {}
    for stage, items in found.items():
        for f in items:
            if not ("MAF" in f.name or "Flora" in f.name):
                continue
            key = f.name.split(":")[0]
            g = groups.setdefault(key, {"check": key, "stage": stage, "status": Counter(), "examples": []})
            g["status"][f.status] += 1
            if f.status in ("fail", "review", "not_run") and len(g["examples"]) < 8:
                g["examples"].append(f"{f.status}: {f.observed}")
    return [dict(g, status=dict(g["status"])) for g in groups.values()]


def flora_table(meshes: list[dict], flora_schedule: dict, rename: dict, instances: list[dict], meta: dict) -> list[dict]:
    """Per library: placed count, measured height range, how many fall inside the schedule band h_m, and the
    twinqa +-20 % result vs the band midpoint (a wide band like 1.25-3.5 m fails at its ends by design)."""
    from twinqa.flora import DIM_TOL, plant_size
    lib_of = {rename[i["name"]]: i["library_id"] for i in instances if i["name"] in rename}
    rows = {}
    for m in meshes:
        want = flora_schedule.get(m["name"])
        if want is None or not m.get("bounds_m"):
            continue
        lib = lib_of[m["name"]]
        h, d = plant_size(m["bounds_m"])
        lo, hi = meta[lib]["h_m"]
        r = rows.setdefault(lib, {"library": lib, "band_m": [lo, hi], "mid_m": want["height_m"],
                                  "crown_ref_m": want["crown_m"], "n": 0, "in_band": 0, "within_20pct": 0,
                                  "h_min": h, "h_max": h, "crown_max_dev": 0.0})
        r["n"] += 1
        r["in_band"] += lo - 1e-6 <= h <= hi + 1e-6
        r["within_20pct"] += abs(h / want["height_m"] - 1) <= DIM_TOL + 1e-9 and abs(d / want["crown_m"] - 1) <= DIM_TOL + 1e-9
        r["h_min"], r["h_max"] = min(r["h_min"], h), max(r["h_max"], h)
        r["crown_max_dev"] = max(r["crown_max_dev"], abs(d / want["crown_m"] - 1))
    return [dict(r, h_min=round(r["h_min"], 3), h_max=round(r["h_max"], 3), crown_max_dev=round(r["crown_max_dev"], 3))
            for _, r in sorted(rows.items())]


def maf_table(meshes: list[dict], maf_sizes: dict, rename: dict, instances: list[dict], tol: float = 0.1) -> list[dict]:
    """Per MAF type: count, spec, the worst |plan|/|Z| bbox deviation and how many exceed the 0.1 m tolerance."""
    lib_of = {rename[i["name"]]: i["library_id"] for i in instances if i["name"] in rename}
    rows = {}
    for m in meshes:
        spec = maf_sizes.get(m["name"])
        if spec is None or not m.get("bounds_m"):
            continue
        lo, hi = m["bounds_m"]
        size = [hi[k] - lo[k] for k in range(3)]
        dev = max(abs(a - b) for a, b in zip(sorted(size[:2]), sorted(spec[:2])))
        dz = abs(size[2] - spec[2])
        r = rows.setdefault(lib_of[m["name"]], {"library": lib_of[m["name"]], "spec_m": spec, "n": 0, "over_tol": 0,
                                                "max_plan_dev_m": 0.0, "max_z_dev_m": 0.0, "measured_m": None})
        r["n"] += 1
        r["over_tol"] += max(dev, dz) > tol + 1e-9
        if max(dev, dz) >= max(r["max_plan_dev_m"], r["max_z_dev_m"]):
            r["measured_m"] = [round(v, 3) for v in size]
        r["max_plan_dev_m"], r["max_z_dev_m"] = round(max(r["max_plan_dev_m"], dev), 3), round(max(r["max_z_dev_m"], dz), 3)
    return [r for _, r in sorted(rows.items())]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", type=Path, required=True, help="placement variant dir (plan.json, ../results.json)")
    ap.add_argument("--prepared", type=Path, required=True, help="prepared.blend (pre-merge, light Flora)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    from twinqa.profiles import load_profiles
    from twinqa.scene import find_blender, readback, scene_findings

    if a.out.exists():
        raise SystemExit(f"{a.out} exists; use a new versioned folder")
    a.out.mkdir(parents=True)
    plan = json.loads((a.place / "plan.json").read_text(encoding="utf-8"))
    meta = json.loads((a.place.parent / "results.json").read_text(encoding="utf-8"))["variants"][a.place.name]["meta"]
    crowns = catalogue_crowns(json.loads(SITE_PARTS.read_text(encoding="utf-8")))
    rename, flora, maf, gaps = build_inputs(plan["instances"], meta, crowns)
    inputs = {"rename": rename, "flora_schedule": flora, "maf_sizes": maf, "gaps": gaps}
    (a.out / "inputs.json").write_text(json.dumps(inputs, indent=1, ensure_ascii=False), encoding="utf-8")

    fbx = a.out / "site_instances_check.fbx"
    (a.out / "rename.json").write_text(json.dumps(rename, indent=1), encoding="utf-8")
    cmd = [find_blender(), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(EXPORT),
           "--", str(a.prepared), str(a.out / "rename.json"), str(fbx)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    record = {"export_cmd": " ".join(cmd), "export_exit": r.returncode, "export_tail": r.stdout[-400:]}
    if r.returncode:
        (a.out / "result.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        raise SystemExit(f"export failed: {r.stderr[-1500:]}")
    exported = json.loads(Path(str(fbx) + ".json").read_text(encoding="utf-8"))
    rb = readback(fbx)
    profile = load_profiles().profile("npm")
    found = scene_findings(rb, "npm", "ground", profile, flora_schedule=flora, maf_sizes=maf)
    record.update(blender=rb.get("blender"), exported=exported["exported"], missing=exported["missing"],
                  meshes=len(rb.get("meshes", [])), gaps=gaps, summary=summarize(found),
                  flora_table=flora_table(rb.get("meshes", []), flora, rename, plan["instances"], meta),
                  maf_table=maf_table(rb.get("meshes", []), maf, rename, plan["instances"]),
                  findings={k: [f.__dict__ for f in v if "MAF" in f.name or "Flora" in f.name] for k, v in found.items()})
    (a.out / "result.json").write_text(json.dumps(record, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("blender", "exported", "meshes", "summary", "flora_table", "maf_table")},
                     ensure_ascii=False, indent=None, default=str)[:8000])
    print(f"missing {len(exported['missing'])} gaps {len(gaps)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
