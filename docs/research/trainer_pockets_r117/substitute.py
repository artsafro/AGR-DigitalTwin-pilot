"""#117 substitute for the missing pinned G22 form_v2 key sections (OBSERVE).

The trainer's pinned `C:/x/t_563a40f7/key/heldout-{key,sections}-v001.json` (pairs_v1.json "G22 k2") is gone from
this PC (2026-11-26 evening; also not on Drive), so `agr trainer score g22-k2-stage1` now returns
`form_v2: error`. This module rebuilds the key sections by the SAME extractor (`tools/qa/form_check/blender_scene.py
extract`, same zmap) from the bank key FBX (sha 5b1e8d76..., = key `accepted_bytes.fbx` sha) and takes the key dict
from a stored detector dump (`key_used.json`, written by pairs.py with json.dump(key)). It is used only after
`parity()` reproduces every stored G22 detector row item-by-item (status and dev_m).

uv run python docs/research/trainer_pockets_r117/substitute.py parity OUT.json
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.qa.form_check import detector as D  # noqa: E402

KEY_FBX = "G:/Мой диск/AGR-evidence/1855-trainer-v0/bank/g22-k2-stage1/k2_v002r1_body_quad.fbx"
KEY_USED = "C:/x/trainer/runs/g22-k2-stage1-codex-r115-D1/score/form_v2/G22_k2/key_used.json"
ZMAP = "16.85=16.85,17.8=17.8,18.2=18.2,19.8=19.8"


def extract(fbx, ex, log):
    from dt_ai.core.blender_runner import run_blender
    from tools.qa.form_check.pairs import SCENE
    if not Path(ex).exists():
        run_blender(SCENE, ["extract", str(fbx), str(ex), ZMAP, "", ""], output_json=str(ex), log_path=str(log))
    return json.loads(Path(ex).read_text(encoding="utf-8"))


def key_and_sections(work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    key = json.loads(Path(KEY_USED).read_text(encoding="utf-8"))
    ksec = extract(KEY_FBX, work / "key.extract.json", work / "key.extract.log")["sections"]
    return key, ksec


def items(key, ksec, cand):
    raw = D.score(key, ksec, cand)
    return {k: (v["status"], v.get("dev_m")) for k, v in raw["items"].items()}


def verdict(it):
    fails = sum(s == "fail" for s, _ in it.values())
    return ("defect" if fails else "ok"), fails


def parity(out):
    key, ksec = key_and_sections(Path(out).with_suffix(""))
    rows = []
    dets = glob.glob("C:/x/trainer/runs/g22-k2-stage1-*/score/form_v2/detector.json") + \
        glob.glob("C:/x/ev_t_a457c1b6/control/rep1/*/form_v2/detector.json")
    for det in sorted(dets):
        stored = json.loads(Path(det).read_text(encoding="utf-8"))
        ex = Path(det).parent / "G22_k2" / "built.extract.json"
        if not ex.exists() or len(stored) != 1:
            rows.append({"detector": det, "status": "not_exercised", "why": "no single built extract"})
            continue
        want = {k: (v["status"], v.get("dev_m")) for k, v in stored[0]["items"].items()}
        got = items(key, ksec, json.loads(ex.read_text(encoding="utf-8")))
        diff = {k: [want.get(k), got.get(k)] for k in set(want) | set(got) if want.get(k) != got.get(k)}
        rows.append({"detector": det, "stored_verdict": stored[0]["verdict"], "items": len(want), "diff": diff,
                     "equal": not diff})
    res = {"rows": rows, "compared": sum(r.get("status") != "not_exercised" for r in rows),
           "equal": sum(bool(r.get("equal")) for r in rows)}
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"compared": res["compared"], "equal": res["equal"]}))


if __name__ == "__main__":
    if sys.argv[1:2] == ["parity"]:
        parity(sys.argv[2])
