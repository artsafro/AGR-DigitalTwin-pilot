"""Standing #51 driver (OBSERVE): frozen t_563a40f7 detector on 63B, source-only key.
usage: python run51.py <new_out_dir>          (dir must not exist)
Steps: hash preflight (source, key, detector, FBX) -> witnesses (mutate63b.py on a v007 copy) -> per variant x 3
repetitions: extract.py (fresh Blender import, real z) -> relabel z to the frozen labels -> score_heldout.py
(byte-identical) -> summary. Hash postflight. Writes <out>/receipt.json."""
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
DET = "C:/x/t_563a40f7/detector"
DET_SUMS = "C:/x/t_563a40f7/SHA256SUMS.txt"
EV = "G:/Мой диск/AGR-evidence/1619-body-training/tower-B"
SRC = EV + "/v002/source_sections_and_openings.json"
KEY = "C:/x/t_fb3a0b98-r51/key"
PINS = {  # frozen in the contract before any measurement
    "source": ("f1865bdde9ca0b3553777cf6e1d71cd8aee915998d342ec789bfc4fd6cdf47a2", SRC),
    "key": ("67a1ae5b88beec6eefc51d51ccdab496daa256709ec484793caee4097f6b6b14", KEY + "/heldout-key-v001.json"),
    "key_sections": ("07ce9a5bff8a9e4e82bf8346daef191ca5e0ba626ccd900aaca290a29fb698b6",
                     KEY + "/heldout-sections-v001.json"),
}
VARIANTS = {  # label: (Artem verdict, evidence FBX, sha256 from the evidence SHA256SUMS.txt)
    "v007": ("accepted 2026-11-20", EV + "/v007/63B_Stage1_v007.fbx",
             "53189b830418a328f3159172c5c1c7eff826c5a9eff568cad0b9187b63332bd7"),
    "v002": ("rejected", EV + "/v002/63B_Stage1_v002.fbx",
             "a57cb3fb66e628e6d1fe1272d16bc592604389b52be6cb4af6a4259b75746a9d"),
    "v003": ("rejected", EV + "/v003/63B_Stage1_v003.fbx",
             "83f3289c70a2bf8727cc5a0a8d85d12a8f6e90c803c3c37dfc904856588211aa"),
    "v004": ("rejected 2026-11-17", EV + "/v004/63B_Stage1_v004.fbx",
             "6d22c572ab18d9722dcf2296dcca77525ae26265114ba6ff922c3d82f4ce26ae"),
    "v005": ("rejected 2026-11-18", EV + "/v005/63B_Stage1_v005.fbx",
             "a387a459a7d2be6c967e533778da37cc560cc532fe94ed470a72d850fc524fd7"),
    "v006": ("rejected 2026-11-18", EV + "/v006/63B_Stage1_v006.fbx",
             "b2b26d4448798b1174dfce9b1c7ad1386fd6acc78ce9635553e0e7ed7ba4a455"),
}
WITNESSES = ["shift_opening", "shift_wall"]
REPS = 3
WALL_CAP_S = 3600


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def det_hashes():
    want = {}
    for line in open(DET_SUMS, encoding="utf-8"):
        if line.strip():
            h, name = line.split(None, 1)
            want[name.strip().lstrip("*").removeprefix("./")] = h
    out = {}
    for f in ("extract.py", "score_heldout.py"):
        got = sha(os.path.join(DET, f))
        exp = want.get("detector/" + f)
        out[f] = {"sha256": got, "frozen": exp, "ok": got == exp}
    return out


def preflight(fbxs):
    res = {k: {"sha256": sha(p), "pin": h, "ok": sha(p) == h} for k, (h, p) in PINS.items()}
    res |= {"fbx:" + k: {"sha256": sha(p), "pin": h, "ok": sha(p) == h} for k, (p, h) in fbxs.items()}
    res |= {"detector:" + k: v for k, v in det_hashes().items()}
    return res


def blender(args, log):
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    open(log, "w", encoding="utf-8").write(r.stdout + "\n--stderr--\n" + r.stderr)
    return r


def main(out):
    if os.path.exists(out):
        raise SystemExit("out dir exists")
    os.makedirs(out)
    t0 = time.time()
    key = json.load(open(PINS["key"][1], encoding="utf-8"))
    shift = key["z_shift_m"]
    real = {z: round(float(z) - shift, 2) for z in ("16.85", "17.8", "18.2", "19.8")}
    fbxs = {k: (p, h) for k, (_, p, h) in VARIANTS.items()}
    pre = preflight(fbxs)
    receipt = {"card": "t_fb3a0b98", "status": "running", "preflight": pre, "label_to_real_z": real}
    if not all(v["ok"] for v in pre.values()):
        receipt["status"] = "preflight_failed"
        json.dump(receipt, open(out + "/receipt.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        raise SystemExit("preflight failed: " + str([k for k, v in pre.items() if not v["ok"]]))
    # stage fixtures (copies; scorer hashes the copy it reads)
    stage = {}
    for k, (p, h) in fbxs.items():
        dst = f"{out}/fixtures/{k}.fbx"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(p, dst)
        assert sha(dst) == h
        stage[k] = dst
    wit = {}
    for m in WITNESSES:
        dst = f"{out}/fixtures/W_{m}.fbx"
        r = blender([HERE + "/mutate63b.py", "--", stage["v007"], m, dst], f"{out}/fixtures/W_{m}.log")
        moved = [ln for ln in r.stdout.splitlines() if ln.startswith("MUTATE")]
        wit["W_" + m] = {"moved": moved[0] if moved else None, "sha256": sha(dst) if os.path.exists(dst) else None}
        if os.path.exists(dst):
            stage["W_" + m] = dst
    receipt["witnesses"] = wit
    runs = {}
    zs = ",".join(str(real[z]) for z in ("16.85", "17.8", "18.2", "19.8"))
    for k, fbx in stage.items():
        runs[k] = []
        for rep in range(1, REPS + 1):
            if time.time() - t0 > WALL_CAP_S:
                runs[k].append({"rep": rep, "status": "budget_stop"})
                continue
            d = f"{out}/{k}/rep{rep}"
            os.makedirs(d)
            raw = d + "/raw.extract.json"
            r = blender([DET + "/extract.py", "--", fbx, raw, zs], d + "/extract.log")
            if not os.path.exists(raw) or "EXTRACT" not in r.stdout:
                runs[k].append({"rep": rep, "status": "extract_failed"})
                continue
            ex = json.load(open(raw, encoding="utf-8"))
            lab = dict(ex)
            lab["sections"] = {z: ex["sections"][str(real[z])] for z in real}
            lab["loops"] = [dict(lp, z=[round(lp["z"][0] + shift, 4), round(lp["z"][1] + shift, 4)])
                            for lp in ex["loops"]]
            cand = d + "/candidate.extract.json"
            json.dump(lab, open(cand, "w"), indent=0)
            sc = d + "/vs_key.json"
            subprocess.run([sys.executable, DET + "/score_heldout.py", PINS["key"][1], KEY + "/SHA256SUMS.txt", cand, sc],
                           capture_output=True, text=True)
            res = json.load(open(sc, encoding="utf-8"))
            items = res["items"]
            F_items = [n for n in items if n.startswith("contour@") or n == "openings:no_extra_in_box" or
                       any(n.endswith(s) for s in (":present", ":edges", ":sill_head"))]
            runs[k].append({
                "rep": rep, "status": "scored", "raw_extract_sha256": sha(raw), "vs_key_sha256": sha(sc),
                "F": sum(items[n]["status"] == "fail" for n in F_items),
                "F_not_measured": sum(items[n]["status"] == "not_measured" for n in F_items),
                "F_items": len(F_items), "openings": res["openings"], "extras": res["extra_openings"],
                "reveal_depth": {n: items[n]["status"] + ": " + items[n]["basis"] for n in items
                                 if n.endswith(":reveal_depth")},
                "scope": items.get("scope:no_fills_stage1", {}).get("status"),
                "non_pass": {n: v["status"] + ": " + v["basis"][:160] for n, v in items.items()
                             if v["status"] != "pass" and n in F_items},
                "faces": ex.get("faces"), "objects": len(ex.get("objects", []))})
    summary = {}
    for k, rr in runs.items():
        ok = [r for r in rr if r["status"] == "scored"]
        Fs = [r["F"] for r in ok]
        summary[k] = {"verdict": VARIANTS.get(k, ("planted witness on v007 copy",))[0],
                      "reps_scored": len(ok), "F_median": statistics.median(Fs) if Fs else None,
                      "F_spread": (max(Fs) - min(Fs)) if Fs else None,
                      "F_nm_median": statistics.median(r["F_not_measured"] for r in ok) if ok else None,
                      "openings_rep1": ok[0]["openings"] if ok else None,
                      "payload_identical": len({json.dumps(r["non_pass"], sort_keys=True) for r in ok}) == 1 if ok else None}
    post = preflight(fbxs)
    receipt |= {"status": "complete", "wall_s": round(time.time() - t0, 3), "runs": runs, "summary": summary,
                "postflight_ok": all(v["ok"] for v in post.values())}
    json.dump(receipt, open(out + "/receipt.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"wall_s": receipt["wall_s"], "postflight_ok": receipt["postflight_ok"], "witnesses": wit,
                      "summary": summary}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
