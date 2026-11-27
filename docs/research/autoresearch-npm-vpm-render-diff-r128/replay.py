"""Research-only replay: call the existing native renderer and #125 scorer unchanged."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
from zipfile import ZipFile

BASE = "9269c354ad4b2bcb8af03d2308297edfff25f079"
R125 = "9e582966c1f454f0924a70a8a386d060ef6a7ce5"
R127 = "34b5174834a21e1ed516a02439bcd1eec832404b"
DRIVE = Path("G:/Мой диск/AGR-evidence")
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
RENDERER = "jobs/TEC26-OKS/scripts/render_facades.py"
SPEC = "jobs/TEC26-OKS/AC08/vpm_textures.json"
RECEIPT = "docs/research/autoresearch-ac08-joint-gate-harness/receipt_r127.json"
SCORE = "docs/research/autoresearch-npm-vpm-render-diff-harness/render_diff.py"


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git_blob(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"])


def main(out):
    start = time.monotonic()
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "preflight", "rounds": [], "measured_head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True).strip()}
    try:
        for path in (RENDERER, SPEC, "jobs/TEC26-OKS/scripts/vpm_uv.py", "tools/blender/vpm_uv.py"):
            if Path(path).read_bytes().replace(b"\r\n", b"\n") != git_blob(BASE, path):
                raise ValueError(f"code/spec drift: {path}")
        if digest(BLENDER) != "1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5":
            raise ValueError("Blender digest mismatch")
        pinned_scorer = out / "render_diff.py"
        pinned_scorer.write_bytes(git_blob(R125, SCORE))
        report["scorer_sha256"] = digest(pinned_scorer)
        s = runpy.run_path(str(pinned_scorer))
        np = s["np"]
        from PIL import __version__ as pillow_version
        report["versions"] = {"python": sys.version.split()[0], "numpy": np.__version__, "pillow": pillow_version}
        labels = json.loads(git_blob(R127, RECEIPT))["packages"]
        originals = {}
        staged = {}
        for version, row in labels.items():
            for name, expected in row["drive_zip_sha256"].items():
                path = DRIVE / f"559-tec26-oks-ac08-{version}" / name
                originals[path] = expected
                if digest(path) != expected:
                    raise ValueError(f"ZIP digest mismatch: {path}")
                dest = out / version / ("vpm" if name.startswith("SM_") else "npm")
                dest.mkdir(parents=True)
                with ZipFile(path) as archive:
                    archive.extractall(dest)
                staged.update({p: digest(p) for p in dest.rglob("*") if p.is_file()})
        report["zip_sha256"] = {str(p): h for p, h in originals.items()}
        report["staged_sha256"] = {p.relative_to(out).as_posix(): h for p, h in staged.items()}
        report["status"] = "running"
        for repetition in range(1, 4):
            round_start = time.monotonic()
            pair = {}
            for version in labels:
                src = out / version
                dst = out / f"r{repetition}-{version}"
                with dst.with_suffix(".log").open("xb") as log:
                    subprocess.run([str(BLENDER), "--background", "--factory-startup", "--disable-autoexec",
                                    "--python-exit-code", "1", "--python", RENDERER, "--", SPEC,
                                    str(src / "vpm/SM_Nku_1.fbx"), str(src / "vpm"),
                                    str(src / "npm/0000_Nku_1_01.fbx"), str(dst)],
                                   stdout=log, stderr=subprocess.STDOUT, check=True,
                                   timeout=max(1, 295 - (time.monotonic() - start)),
                                   env={**os.environ, "PX_PER_M": "400"})
                meta = json.loads((dst / "renders.json").read_bytes())
                views = s["VIEWS"]
                cams = {tag: {v: {k: x for k, x in meta[tag]["views"][v].items() if k != "png"}
                              for v in views} for tag in ("npm", "vpm")}
                if cams["npm"] != cams["vpm"]:
                    raise ValueError(f"paired camera mismatch: {dst.name}")
                images = {(k, v): s["load"](dst / f"{k}_{v}.png") for k in cams for v in views}
                bbox = meta["vpm"]["bbox"]
                clean = s["score_package"](images, bbox, 2)
                row = {"camera": cams["vpm"], "clean": clean, "controls": {},
                       "renders_sha256": {p.name: digest(p) for p in sorted(dst.glob("*.png"))}}
                for kind in ("N0", "P1", "P2", "P3"):
                    changed = s["perturb"](images, kind, clean["views"]["south"]["native_px_per_m"])
                    counts = {v: int(np.any(changed["npm", v][..., :3] != images["npm", v][..., :3], axis=-1).sum())
                              for v in views}
                    alpha = all(np.array_equal(changed["npm", v][..., 3], images["npm", v][..., 3]) for v in views)
                    vpm = all(np.array_equal(changed["vpm", v], images["vpm", v]) for v in views)
                    score = s["score_package"](changed, bbox, 2)["score_facade_cell_p95"]
                    row["controls"][kind] = {"score": score, "changed_npm_rgb": counts, "alpha_equal": alpha,
                                             "vpm_equal": vpm}
                pair[version] = row
                print(f"{dst.name}: score={clean['score_facade_cell_p95']}", flush=True)
            elapsed = time.monotonic() - round_start
            report["rounds"].append({"seconds": elapsed, "packages": pair})
            if repetition == 1 and (elapsed > 90 or 300 - (time.monotonic() - start) < 2 * elapsed + 15):
                report["status"] = "budget_stop"
                break
        else:
            report["status"] = "series_complete"
        report["input_parity"] = all(digest(p) == h for p, h in (originals | staged).items())
    except subprocess.TimeoutExpired as error:
        report.update(status="budget_stop", error=str(error))
        raise
    except Exception as error:
        report.update(status="refused", error=str(error))
        raise
    finally:
        report["seconds"] = time.monotonic() - start
        (out / "receipt.json").write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
