"""Run every windows-glazing variant on the benchmark objects and append the measured rows (#721).

Pattern: new-case: methods-catalog batch for the windows-glazing class (#721).

    uv run python tools/methods/windows/run_benchmarks.py [--bench kpp1 ...] [--variant ...] \\
        [--out C:/x/methods/windows-glazing] [--results docs/methods/windows-glazing/results.jsonl]

Per (benchmark, variant): checks the source sha256 against benchmark/methods/benchmarks.json, builds the
variant in a fresh factory Blender (build_variant_blender.py) into <out>/<bench>/<variant>/<FBX name>
(the source is never written), packs a ZIP with the source package's textures plus the variant's generated
diffuse PNG the driver wrote and bound to the new material (tiled package: `<diffuse stem>.<new tile>.png`,
1024 px; untiled: `T_<FBX stem>_<kind>.png` at the side of the package's single diffuse), then measures it with
tools/methods/run_variant.py in a fresh process. Variant `source-as-is` measures a copy of the source
package itself (no build) as the reference row. Rows are written only by run_variant.py: a failed build
appends nothing and makes the batch exit 1. Then RESULTS.md is regenerated.

New UDIM tile: tiled package = highest diffuse tile + 1; untiled package (one diffuse map) = 1002, measured
against that single diffuse map's side (run_variant's package rule). Glass source of an object without a
*_MainGlass mesh: its untiled metallic map (`*_m_*` texture of the benchmark), glass white per WIN-08.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE.parent))

import results_md  # noqa: E402
import run_variant  # noqa: E402
from safe_write import check_target, refuse_aliases, same_file  # noqa: E402

_spec = importlib.util.spec_from_file_location("methods_ucx_batch", HERE.parent / "ucx" / "run_benchmarks.py")
ucx_batch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ucx_batch)
_spec = importlib.util.spec_from_file_location("methods_windows_variants", HERE / "windows_variants.py")
wv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wv)

CLASS = "windows-glazing"
BASELINE = "source-as-is"  # the benchmark source itself, measured the same way: the reference every variant is read against
DEFAULT_BENCH = ("kpp1", "ac08", "tow02")
TILE_RE = re.compile(r"(?i)^(.*diffuse.*)\.(1\d{3})\.png$")


def diffuse_tiles(bench: dict) -> tuple[str | None, list[int]]:
    """(stem of the tiled diffuse PNGs, their tiles) of a ZIP source; (None, []) for an untiled source."""
    src = bench["source"]
    if src["kind"] != "zip":
        return None, []
    with zipfile.ZipFile(src["local_path"]) as z:
        hits = [TILE_RE.match(Path(n).name) for n in z.namelist()]
    hits = [h for h in hits if h]
    stems = {h.group(1) for h in hits}
    if len(stems) > 1:
        raise run_variant.Refused(f"{bench['id']}: several diffuse sets {sorted(stems)}")
    return (stems.pop() if stems else None), sorted(int(h.group(2)) for h in hits)


def new_tile(bench: dict) -> int:
    _, tiles = diffuse_tiles(bench)
    return max(tiles) + 1 if tiles else 1002


def glass_map(bench: dict) -> Path | None:
    maps = [Path(t["local_path"]) for t in bench["source"].get("textures") or []
            if re.search(r"(?i)_m_\d+\.png$", t["local_path"])]
    if len(maps) > 1:
        raise run_variant.Refused(f"{bench['id']}: several metallic maps {maps}")
    return maps[0] if maps else None


def texture_plan(bench: dict, out: Path, variant: str, tile: int) -> tuple[str, int]:
    """(file name, side px) of the variant's generated diffuse, written by the driver next to `out`."""
    from PIL import Image

    stem, _ = diffuse_tiles(bench)
    if stem:
        return f"{stem}.{tile}.png", 1024
    diffuse = [Path(t["local_path"]) for t in bench["source"].get("textures") or []
               if re.search(r"(?i)(diffuse|_d_\d)", Path(t["local_path"]).stem)]
    if len(diffuse) != 1:
        raise run_variant.Refused(f"{bench['id']}: untiled package needs exactly one diffuse map, found {diffuse}")
    with Image.open(diffuse[0]) as im:
        side = im.size[0]
    return f"T_{out.stem}_{wv.GEN_MATERIAL[variant]}.png", side


def package(bench: dict, fbx: Path, report: dict) -> Path:
    """ucx_batch.package + the driver's generated PNG (report `texture`), refused on a name already packed."""
    out = ucx_batch.package(bench, fbx)
    name = report.get("texture")
    if name:
        png = fbx.with_name(name)
        if not png.is_file() or wv_sha(png) != report.get("texture_sha256"):
            raise run_variant.Refused(f"{bench['id']}: generated texture {png} missing or not the bound one")
        if out.suffix.lower() != ".zip":
            raise run_variant.Refused(f"{bench['id']}: a generated texture needs a ZIP package")
        with zipfile.ZipFile(out, "a", zipfile.ZIP_DEFLATED) as z:
            if name in z.namelist():
                raise run_variant.Refused(f"{bench['id']}: {name} is already in the source package")
            z.write(png, name)
    return out


def wv_sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(a, benches: list[dict]) -> list[tuple]:
    """Preflight with no side effect: (bench, source, variant, out, report, tile, glass map) per run; every
    destination checked against the protected inputs and against each other."""
    runs, dests = [], [a.results, a.results.with_name("RESULTS.md")]
    for bid in a.bench or DEFAULT_BENCH:
        bench = run_variant.load_benchmark(a.benchmarks, bid, CLASS)
        src = ucx_batch.source_fbx(bench)
        tile, gmap = new_tile(bench), glass_map(bench)
        for variant in a.variant or (BASELINE,) + wv.VARIANTS:
            if variant not in (BASELINE,) + wv.VARIANTS:
                raise run_variant.Refused(f"unknown variant {variant!r}; known: {[BASELINE, *wv.VARIANTS]}")
            out = a.out / bid / variant / bench["source"].get("output_name", src.name)
            rep = out.with_name(out.name + ".variant.json")
            tex = texture_plan(bench, out, variant, tile) if variant != BASELINE else None
            runs.append((bench, src, variant, out, rep, tile, gmap, tex))
            dests += [out, rep, out.with_suffix(".zip")] + \
                ([out.with_name(tex[0])] if tex else [])
    refuse_aliases(dests, ucx_batch.protected_inputs(a.benchmarks, benches))
    for i, d in enumerate(dests):
        for e in dests[i + 1:]:
            if same_file(d, e):
                raise run_variant.Refused(f"two planned destinations are the same file: {d} and {e}")
    for d in dests:
        check_target(d)
    return runs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bench", action="append")
    ap.add_argument("--variant", action="append")
    ap.add_argument("--out", type=Path, default=Path("C:/x/methods") / CLASS)
    ap.add_argument("--results", type=Path, default=ROOT / "docs" / "methods" / CLASS / "results.jsonl")
    ap.add_argument("--benchmarks", type=Path, default=run_variant.BENCHMARKS)
    a = ap.parse_args(argv)
    try:
        benches = json.loads(a.benchmarks.read_text(encoding="utf-8"))["objects"]
        runs = plan(a, benches)  # every check before the first mkdir / unlink / build
    except (run_variant.Refused, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"RUN_BENCHMARKS refused: {exc}", file=sys.stderr)
        return 4
    from dt_ai.core.blender_runner import blender_executable

    blender = blender_executable()
    codes = []
    for bench, src, variant, out, rep, tile, gmap, tex in runs:
        bid = bench["id"]
        out.parent.mkdir(parents=True, exist_ok=True)
        for stale in [out, rep, out.with_suffix(".zip")] + ([out.with_name(tex[0])] if tex else []):
            stale.unlink(missing_ok=True)  # planned destinations only; preflight proved none is an input
        if variant == BASELINE:  # copy, never write next to the source; no build, so no wall time
            shutil.copyfile(src, out)
            target = package(bench, out, {})
            r = subprocess.run([sys.executable, str(HERE.parent / "run_variant.py"), str(target), "--bench", bid,
                                "--class", CLASS, "--variant", variant, "--results", str(a.results),
                                "--benchmarks", str(a.benchmarks)], capture_output=True, text=True, timeout=3600)
            print(f"{bid} {variant}: {(r.stdout + r.stderr).strip()[-300:]}")
            codes.append(r.returncode)
            continue
        cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
               str(HERE / "build_variant_blender.py"), "--", str(src), str(out), variant, f"tile={tile}",
               f"texture={tex[0]}", f"texture_side={tex[1]}"]
        if gmap:
            cmd.append(f"glass_map={gmap}")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        report = json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else {}
        if proc.returncode != 0 or not report.get("ok") or not out.is_file():
            print(f"{bid} {variant}: build failed, no row: {report.get('error') or proc.stderr[-300:]}")
            codes.append(2)
            continue
        try:
            target = package(bench, out, report)
        except run_variant.Refused as exc:
            print(f"{bid} {variant}: package refused, no row: {exc}")
            codes.append(2)
            continue
        r = subprocess.run([sys.executable, str(HERE.parent / "run_variant.py"), str(target), "--bench", bid,
                            "--class", CLASS, "--variant", variant, "--variant-report", str(rep),
                            "--results", str(a.results), "--benchmarks", str(a.benchmarks)],
                           capture_output=True, text=True, timeout=3600)
        print(f"{bid} {variant}: openings {report.get('openings')}: {(r.stdout + r.stderr).strip()[-300:]}")
        codes.append(r.returncode)
    results_md.write(a.results)
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
