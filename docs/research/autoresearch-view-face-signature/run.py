"""#157 OBSERVE runner: wall-signature identifiability (inner vs open walls) on 4 Revit FBX.

new-case: docs/research/autoresearch-view-face-signature/run.py - #157 OBSERVE replay runner

Research only; no product code, no delivery edits. Replay from the repository root (pilot host, inputs mounted):
    uv run --offline --locked python docs/research/autoresearch-view-face-signature/run.py <new_out_dir>
Frozen rules: ../autoresearch-view-face-signature.md.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from time import monotonic

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plan import plan_png  # noqa: E402
from score import score_model  # noqa: E402


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(out):
    out = Path(out)
    out.mkdir(parents=True)  # fresh directory only
    fx = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))
    blender = fx["blender"]["path"]
    pins = {"blender": sha(blender)}
    if pins["blender"] != fx["blender"]["sha256"]:
        raise SystemExit("Blender hash mismatch")
    for name in ("walls.py", "score.py", "plan.py", "run.py", "fixture.json"):
        pins[name] = sha(HERE / name)
    result, t0 = {"pins": pins, "models": {}}, monotonic()
    for key, row in fx["models"].items():
        if sha(row["path"]) != row["sha256"]:
            raise SystemExit(f"input SHA-256 mismatch: {key}")
        pins[key] = row["sha256"]
        tables = {}
        for order in ("fwd", "rev"):
            js = out / f"{key}.{order}.json"
            p = subprocess.run([blender, "-b", "--factory-startup", "-P", str(HERE / "walls.py"), "--",
                                row["path"], str(js), order], capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            if p.returncode or not js.exists():
                raise SystemExit(f"blender failed {key} {order}: {p.stdout[-800:]} {p.stderr[-800:]}")
            tables[order] = json.loads(js.read_text(encoding="utf-8"))
        fw, rv = tables["fwd"]["walls"], tables["rev"]["walls"]
        changed = sum(a != b for a, b in zip(fw, rv)) + abs(len(fw) - len(rv))
        same_win = tables["fwd"]["windows"] == tables["rev"]["windows"]
        plan_png(json.loads(json.dumps(tables["fwd"])), out / f"{key}.plan.png")
        res = score_model(fw, tables["fwd"]["windows"])
        res["invariance"] = {"walls_changed_fwd_vs_rev": changed, "windows_identical": same_win,
                             "windows_check": "exercised" if tables["fwd"]["windows"] else "not_exercised"}
        res["counts"] = {k: tables["fwd"][k] for k in ("tris", "vertical_sel", "classified")}
        res["counts"]["windows"] = len(tables["fwd"]["windows"])
        result["models"][key] = res
        print(key, json.dumps(res["summary"], sort_keys=True), "inv", changed, flush=True)
    result["verdict"] = verdict(result["models"])
    (out / "score.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True),
                                    encoding="utf-8")
    (out / "wall_time.txt").write_text(f"{monotonic() - t0:.3f}\n", encoding="utf-8")
    print("VERDICT", result["verdict"], "wall", round(monotonic() - t0, 1))


def verdict(models):
    gated = [models[k]["summary"] for k in ("savelovskaya", "moskovsky")]
    if any(s["inner_walls"] < 5 for s in gated):
        return "inconclusive (inner walls not exercised)"
    uniq = [s["inner_unique_B"] for s in gated]
    wrong = [s["perturbed"]["wrong_rate"] for s in gated]
    if min(uniq) < 0.5 or max(wrong) > 0.03:
        return "refuted"
    if min(uniq) >= 0.7 and max(s["perturbed"]["wrong"] for s in gated) == 0:
        return "confirmed"
    return "inconclusive"


if __name__ == "__main__":
    main(sys.argv[1])
