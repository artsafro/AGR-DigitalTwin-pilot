"""One fresh #142 research pair; outputs only to a new worktree directory."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np

R141 = "3716f5395667c17f8be8737313952aaa6285615c"
R140 = "ab33b7e4249f41232501d0c05534bd2793a15358"
P141 = "docs/research/autoresearch-view-face-raster"
P140 = "docs/research/autoresearch-view-face-2d"


def blob(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"])


def upstream_edges():
    source = blob(R140, f"{P140}/score.py")
    module = SimpleNamespace()
    exec(compile(source, f"{R140}:{P140}/score.py", "exec"), vars(module))
    return module


def raster_edges(luma):
    edges = np.zeros(luma.shape, bool)
    for a, b in ((np.s_[:-1, :], np.s_[1:, :]), (np.s_[:, :-1], np.s_[:, 1:])):
        edges[a] |= luma[b] - luma[a] >= 0.15
        edges[b] |= luma[a] - luma[b] >= 0.15
    return edges


def model_edges(hit, scorer):
    depth = np.where(hit > 0, hit, np.nan)
    normals = np.zeros((*hit.shape, 3), float)
    normals[..., 2] = 1
    return scorer.mesh_edges(depth, normals)


def main(out):
    t0 = time.perf_counter()
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    upstream = out / "upstream141"
    upstream.mkdir()
    for name in ("run.py", "sheet.py", "score.py", "rays_win.py", "fixture.json"):
        (upstream / name).write_bytes(blob(R141, f"{P141}/{name}"))
    spec = importlib.util.spec_from_file_location("baseline141", upstream / "run.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the pinned baseline")
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    fx = baseline.FIX
    blender = fx["blender"]
    hashes = baseline.preflight()
    if baseline.sha(blender["path"]) != blender["sha256"]:
        raise RuntimeError("Blender executable hash mismatch")
    copy = out / "input.blend"
    shutil.copyfile(fx["inputs"]["model"]["path"], copy)
    if baseline.sha(copy) != hashes["model"]:
        raise RuntimeError("staged model hash mismatch")
    child_temp = out / "temp"
    child_temp.mkdir()
    child_env = dict(os.environ, TEMP=str(child_temp), TMP=str(child_temp), TMPDIR=str(child_temp))

    def launch(cmd, **kwargs):
        cmd = [cmd[0], "--background", "--factory-startup", "--disable-autoexec", "--threads", "1",
               "--python-exit-code", "1", str(copy), *cmd[4:]]
        return subprocess.run(cmd, **(kwargs | {"timeout": 90, "env": child_env}))

    vars(baseline)["subprocess"] = SimpleNamespace(run=launch)
    views = {}
    read_sheet = baseline.sheet.read_sheet

    def record_sheet(pdf, index, clip, max_run):
        result = read_sheet(pdf, index, clip, max_run)
        page = next(page for page in fx["pages"] if page["index"] == index)
        for view, label in zip(result["views"], page["views"], strict=True):
            views[label["id"]] = view["crop"]
        return result

    baseline.sheet.read_sheet = record_sheet
    sys.argv = [str(upstream / "run.py"), str(out / "A"), "R2"]
    baseline.main()
    a_result = json.loads((out / "A/result.json").read_text(encoding="utf-8"))
    oracle = json.loads(blob(R141, f"{P141}/receipt.json"))["R2"]["cases"]
    if a_result["cases"] != oracle:
        raise RuntimeError("R2 historical case parity failed")

    scorer = upstream_edges()
    with np.load(out / "A/rays.npz") as data:
        hits = {az: data[f"az{az:03d}_hit"] for az in fx["faces_az"]}
    edge_models = {az: model_edges(hit, scorer) for az, hit in hits.items()}
    view_edges = {key: raster_edges(luma) for key, luma in views.items()}
    cases = []
    for source in oracle:
        case = dict(source)
        edges = view_edges[case["view"]]
        if case["kind"] == "mirror":
            mirrored = edges[:, ::-1]
            case["changed_edge_px"] = int(np.count_nonzero(mirrored != edges))
            if not case["changed_edge_px"]:
                cases.append(case | {"B": {"outcome": "not_exercised"}})
                continue
            edges = mirrored
        if case["kind"] == "crop":
            frac, _, pos = case["id"].split("/crop")[-1].partition("@")
            width = round(edges.shape[1] * float(frac))
            left = round((edges.shape[1] - width) * float(pos))
            edges = edges[:, left:left + width]
        scores = {az: scorer.face_score(edges, model, hits[az] > 0, slack=6)
                  for az, model in edge_models.items()}
        answer = scorer.decide(scores)
        case["B"] = {"answer": answer, "scores": {a: round(s, 6) for a, s in scores.items()},
                     "outcome": "abstain" if answer is None else "correct" if answer == case["gt"] else "wrong"}
        cases.append(case)

    if (baseline.preflight() != hashes or baseline.sha(copy) != hashes["model"]
            or baseline.sha(blender["path"]) != blender["sha256"]):
        raise RuntimeError("input postflight mismatch")
    tally = {}
    for kind in ("full", "crop", "mirror"):
        for side in ("long", "short"):
            group = [c for c in cases if c["kind"] == kind and c["view"] in fx[f"{side}_views"]]
            tally[f"{side}/{kind}"] = {v: dict(Counter(c[k]["outcome"] for c in group))
                                       for v, k in (("A", "C"), ("B", "B"))}
    semantic = {"cases": cases, "summary": tally, "hashes": hashes | {"blender": blender["sha256"]},
                "baseline_parity_cases": len(oracle), "model_edge_pixels": {k: int(v.sum()) for k, v in edge_models.items()}}
    payload = json.dumps(semantic, ensure_ascii=False, indent=1).encode("utf-8")
    (out / "pair.json").write_bytes(payload)
    timings = {"baseline_s": a_result["wall_s"]["total"], "pair_s": round(time.perf_counter() - t0, 3),
               "pair_sha256": hashlib.sha256(payload).hexdigest()}
    (out / "timing.json").write_text(json.dumps(timings), encoding="utf-8")
    print(json.dumps(timings | {"summary": tally}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
