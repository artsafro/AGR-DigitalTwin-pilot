"""Run the VPM-to-NPM geometry stages on a delivered FBX copy (#1737).

new-case: prepare a fresh NPM master, then delegate atlas, export and UV readback to agr vpm-to-npm.
Packaging and delivery QA are separate skeleton stages.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dt_ai.core.blender_runner import blender_command, blender_executable
from tools.derive.vpm_npm_core import VpmNpmError, budget_ladder


def write_json(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False)


def run(job, out, exe=None):
    exe = blender_executable(exe)
    sk = json.loads((Path(job) / "skeleton.json").read_text(encoding="utf-8"))
    if sk.get("scenario") != "vpm-to-npm":
        raise VpmNpmError("skeleton scenario must be vpm-to-npm")
    cfg = sk["config"]
    vpm = Path(cfg["vpm"]).resolve(strict=True)
    out = Path(out).resolve()
    glass = cfg["glass"]
    if not isinstance(glass, list) or not glass or any(not isinstance(n, str) or not n for n in glass):
        raise VpmNpmError("glass must be a nonempty list of object names")
    if len(set(glass)) != len(glass):
        raise VpmNpmError("duplicate glass object names")
    atlas = cfg["atlas"]
    diffuse = atlas["diffuse"]
    if atlas.get("size", 2048) != 2048 or not isinstance(diffuse, str) or diffuse.count("<UDIM>") != 1:
        raise VpmNpmError("atlas requires size 2048 and a diffuse pattern with one <UDIM>")
    npm = cfg["npm"]
    address, prefix, index = npm["address"], npm["prefix"], npm["index"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", address) or not re.fullmatch(r"[0-9]{4}", prefix):
        raise VpmNpmError("invalid NPM address or district prefix")
    if type(index) is not int or not 1 <= index <= 20:
        raise VpmNpmError("NPM index must be 1..20")
    budget = cfg["budget"] if cfg["budget"] is not None else 150000
    budget_ladder(0, budget, {})  # validate even before native work
    out.mkdir(parents=True, exist_ok=False)
    master = out / "master.blend"
    frozen = out / "config.json"
    write_json(frozen, cfg)
    command = blender_command(str(ROOT / "tools/blender/vpm_to_npm_bl.py"),
                              [str(vpm), str(frozen), str(out)], executable=exe)
    subprocess.run(command, check=True)
    prepared = json.loads((out / "prepare.json").read_text(encoding="utf-8"))
    rem = prepared["remove_interiors"]
    rem["dropped_by_reason"] = dict(Counter(d["reason"] for d in rem["drops"]))
    report = {"vpm": str(vpm), "master": str(master), "tris_count": prepared["tris_count"],
              "remove_interiors": rem}
    tris = rem["tris_after"] + prepared["glass"]["tris"]
    # Conservative pre-export gate: do not export an over-budget master in the absence of job-specific hooks.
    report["budget_ladder"] = ladder = budget_ladder(tris, budget, {})
    report_path = out / "vpm_to_npm_report.json"
    if not ladder["within"]:
        write_json(report_path, report)
        return 1
    opacity = atlas.get("opacity", {})
    tiles = prepared["tile_names"]
    if opacity.keys() - tiles.keys():
        raise VpmNpmError(f"opacity names unused tiles: {sorted(opacity.keys() - tiles.keys())}")
    finishes = {}
    for tile, name in tiles.items():
        finish = {"udim": int(tile), "diffuse": str(vpm.parent / diffuse.replace("<UDIM>", tile))}
        if tile in opacity:
            finish["opacity"] = str(vpm.parent / opacity[tile])
        finishes[name] = finish
    spec = out / "texture_spec.json"
    write_json(spec, {"address": address, "finishes": finishes})
    atlas_dir = out / "atlas"
    options = ["--address", address, "--index", str(index)]
    subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", "vpm-to-npm", "--blender", exe,
                    str(spec), str(atlas_dir), "--master", str(master), "--copied-udims", "--glass-white", *options,
                    "--then-npm", str(master), str(spec), str(atlas_dir), str(out / "npm"), prefix, *options],
                   cwd=ROOT, check=True)
    meta = json.loads((out / "export_npm_meta.json").read_text(encoding="utf-8"))
    report.update(npm_fbx=meta["fbx"], npm_tris=meta["main_tris"] + meta["glass_tris"],
                  glass_merge={**prepared["glass"], **meta["glass_white"]}, atlas=str(atlas_dir / "npm_atlas.json"))
    write_json(report_path, report)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--job", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blender")
    a = ap.parse_args(argv)
    try:
        return run(a.job, a.out, a.blender)
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
