"""Standing #53 driver (OBSERVE). usage: python run53.py <new_out_dir>   (dir must not exist)
Hash preflight -> R_face from source JSON only (must equal the contract) -> witness W_deep (mutate53.py on a v007
copy) -> per fixture x 3 reps: frozen extract.py (fresh Blender import) -> 63B z relabel (as #51 run51.py) -> frozen
score_heldout.py (byte-identical) -> score53.py overlay -> summary + verdict. Hash postflight. Writes <out>/receipt.json."""
import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score53  # noqa: E402

BLENDER = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
DET = "C:/x/t_563a40f7/detector"
G22 = "C:/x/t_563a40f7"
EV = "G:/Мой диск/AGR-evidence/1619-body-training/tower-B"
SRC = EV + "/v002/source_sections_and_openings.json"
KEY63 = "C:/x/t_fb3a0b98-r51/key"
PINS = {
    "source63b": ("f1865bdde9ca0b3553777cf6e1d71cd8aee915998d342ec789bfc4fd6cdf47a2", SRC),
    "key63b": ("67a1ae5b88beec6eefc51d51ccdab496daa256709ec484793caee4097f6b6b14", KEY63 + "/heldout-key-v001.json"),
    "key63b_sections": ("07ce9a5bff8a9e4e82bf8346daef191ca5e0ba626ccd900aaca290a29fb698b6",
                        KEY63 + "/heldout-sections-v001.json"),
    "extract.py": ("ee50925b8a45d6b55d4409cc21893d7932ae7b76d66c3a7c7c4b6b4bb51875af", DET + "/extract.py"),
    "score_heldout.py": ("e9d6f65b6373a4fc95c91a3ea202d29cfb2f052a2aee4bfe0eb1ee1fb3d9b942", DET + "/score_heldout.py"),
}
F63 = {  # label: (verdict, fbx, sha256) — exact #51 evidence bytes
    "v007": ("accepted 2026-11-20", EV + "/v007/63B_Stage1_v007.fbx",
             "53189b830418a328f3159172c5c1c7eff826c5a9eff568cad0b9187b63332bd7"),
    "v002": ("rejected", EV + "/v002/63B_Stage1_v002.fbx", "a57cb3fb66e628e6d1fe1272d16bc592604389b52be6cb4af6a4259b75746a9d"),
    "v003": ("rejected", EV + "/v003/63B_Stage1_v003.fbx", "83f3289c70a2bf8727cc5a0a8d85d12a8f6e90c803c3c37dfc904856588211aa"),
    "v004": ("rejected 2026-11-17", EV + "/v004/63B_Stage1_v004.fbx",
             "6d22c572ab18d9722dcf2296dcca77525ae26265114ba6ff922c3d82f4ce26ae"),
    "v005": ("rejected 2026-11-18", EV + "/v005/63B_Stage1_v005.fbx",
             "a387a459a7d2be6c967e533778da37cc560cc532fe94ed470a72d850fc524fd7"),
    "v006": ("rejected 2026-11-18", EV + "/v006/63B_Stage1_v006.fbx",
             "b2b26d4448798b1174dfce9b1c7ad1386fd6acc78ce9635553e0e7ed7ba4a455"),
}
FG22 = {
    "G22_C_none": ("accepted k2 v002r1 copy", G22 + "/controls/C_none.fbx",
                   "71eb9db8699fe6b94250afd3562a724a87399092b5f2af5d24a4a607b2fc9c39"),
    "G22_C_shift_opening": ("planted", G22 + "/controls/C_shift_opening.fbx",
                            "513d5ab4b2bcb100964386109ee2104dd06c7a488774aa18c162032948fa159b"),
    "G22_C_shift_wall": ("planted", G22 + "/controls/C_shift_wall.fbx",
                         "b79ecca635ea49e2581f40d019c86ee2275bb6f1fb43565a54932ef4af418592"),
}
RFACE_FROZEN = 0.5   # contract value for all five 63B openings
REPS = 3
WALL_CAP_S = 1800
ZL = ("16.85", "17.8", "18.2", "19.8")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def flight():
    res = {k: {"sha256": sha(p), "pin": h, "ok": sha(p) == h} for k, (h, p) in PINS.items()}
    for k, (_, p, h) in (F63 | FG22).items():
        res["fbx:" + k] = {"sha256": sha(p), "pin": h, "ok": sha(p) == h}
    return res


def rface(key):
    """Deepest source wall face parallel to the facade covering >= 95 % of each opening span (source JSON only)."""
    import score_heldout as S
    ring = {r["ring_index"]: r["xy"] for r in key["contour_vertices_in_box"]}
    ref = json.load(open(SRC, encoding="utf-8"))["modules"]["A"]["reference"]
    out = {}
    for o in key["openings"]:
        a, u, _ = S.frame(ring, *o["contour_segment"])
        e0, e1 = o["edge_s_m"]
        cov = {}
        for _, (p, q) in ref:
            (t0, d0), (t1, d1) = S.local(p, a, u), S.local(q, a, u)
            if abs(d0 - d1) > 0.01 or not 0.05 < abs(d0) <= 1.5:
                continue
            ov = max(0.0, min(max(t0, t1), e1) - max(min(t0, t1), e0))
            dk = round(abs(d0), 3)
            cov[dk] = cov.get(dk, 0.0) + ov
        out[o["id"]] = max((d for d, c in cov.items() if c >= 0.95 * (e1 - e0)), default=None)
    return out


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
    pre = flight()
    receipt = {"card": "t_1276e6bc", "status": "running", "preflight": pre}
    rp = out + "/receipt.json"
    if not all(v["ok"] for v in pre.values()):
        receipt["status"] = "preflight_failed"
        json.dump(receipt, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        raise SystemExit("preflight failed: " + str([k for k, v in pre.items() if not v["ok"]]))
    key63 = json.load(open(PINS["key63b"][1], encoding="utf-8"))
    rf = rface(key63)
    json.dump(rf, open(out + "/rface.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    receipt["rface"] = rf
    if any(v is None or abs(v - RFACE_FROZEN) > 1e-9 for v in rf.values()):
        receipt["status"] = "rface_differs_from_contract"
        json.dump(receipt, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        raise SystemExit("R_face differs from the frozen contract: " + str(rf))
    shift = key63["z_shift_m"]
    real = {z: round(float(z) - shift, 2) for z in ZL}
    stage = {}
    for k, (_, p, h) in (F63 | FG22).items():
        dst = f"{out}/fixtures/{k}.fbx"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(p, dst)
        assert sha(dst) == h
        stage[k] = dst
    wdst = f"{out}/fixtures/W_deep.fbx"
    r = blender([HERE + "/mutate53.py", "--", stage["v007"], wdst], f"{out}/fixtures/W_deep.log")
    moved = [ln for ln in r.stdout.splitlines() if ln.startswith("MUTATE")]
    receipt["witness"] = {"moved": moved[0] if moved else None, "sha256": sha(wdst) if os.path.exists(wdst) else None}
    if os.path.exists(wdst):
        stage["W_deep"] = wdst
    runs = {}
    for k, fbx in stage.items():
        is63 = not k.startswith("G22")
        kp = PINS["key63b"][1] if is63 else G22 + "/key/heldout-key-v001.json"
        sums = (KEY63 if is63 else G22 + "/key") + "/SHA256SUMS.txt"
        zs = ",".join(str(real[z]) for z in ZL) if is63 else ",".join(ZL)
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
            cand = raw
            if is63:
                ex = json.load(open(raw, encoding="utf-8"))
                lab = dict(ex)
                lab["sections"] = {z: ex["sections"][str(real[z])] for z in real}
                lab["loops"] = [dict(lp, z=[round(lp["z"][0] + shift, 4), round(lp["z"][1] + shift, 4)])
                                for lp in ex["loops"]]
                cand = d + "/candidate.extract.json"
                json.dump(lab, open(cand, "w"), indent=0)
            fz = d + "/vs_key.json"
            subprocess.run([sys.executable, DET + "/score_heldout.py", kp, sums, cand, fz], capture_output=True, text=True)
            ov = score53.overlay(kp, cand, fz, d + "/overlay53.json", out + "/rface.json" if is63 else None)
            fr = json.load(open(fz, encoding="utf-8"))
            runs[k].append({"rep": rep, "status": "scored", "raw_extract_sha256": sha(raw), "vs_key_sha256": sha(fz),
                            "frozen_summaryA": fr["summary_groupA"],
                            "overlay": {kk: vv for kk, vv in ov.items() if kk != "openings"},
                            "per_opening": {p: {x: r_.get(x) for x in ("source", "sill_head_c", "depth_rim",
                                                                         "depth_vs_key", "depth_vs_face",
                                                                         "frozen_sill_head")}
                                            for p, r_ in ov["openings"].items()}})
    summary = {}
    for k, rr in runs.items():
        ok = [r_ for r_ in rr if r_["status"] == "scored"]
        f = lambda n: [r_["overlay"][n] for r_ in ok]  # noqa: E731
        summary[k] = {"verdict": (F63 | FG22).get(k, ("planted witness on v007 copy",))[0], "reps": len(ok),
                      **{n: {"median": statistics.median(f(n)) if ok else None,
                             "spread": (max(f(n)) - min(f(n))) if ok else None}
                         for n in ("nm", "frozen_sill_nm", "fails_vs_key", "fails_vs_face", "fallback_used")},
                      "frozen_measured_changed": sorted({p for r_ in ok for p in r_["overlay"]["frozen_measured_changed"]}),
                      "per_opening_identical": len({json.dumps(r_["per_opening"], sort_keys=True) for r_ in ok}) == 1,
                      "depth_rim_rep1": {p[-7:]: v["depth_rim"] for p, v in ok[0]["per_opening"].items()} if ok else None}
    # verdict pieces (contract)
    labelled = [k for k in F63]
    m1 = [sum(r_["overlay"]["nm"] for k in labelled for r_ in runs[k] if r_["rep"] == rep and r_["status"] == "scored")
          for rep in range(1, REPS + 1)]
    m1_complete = all(len([r_ for r_ in runs[k] if r_["status"] == "scored"]) == REPS for k in labelled)
    m2 = sorted({k + ":" + p for k, s in summary.items() for p in s["frozen_measured_changed"]})
    dkey = {}
    for k in labelled:
        dkey[k] = summary[k]["fails_vs_key"]["median"], summary[k]["fails_vs_face"]["median"]
    acc = dkey["v007"]
    D_key = sum(1 for k in labelled if k != "v007" and dkey[k][0] <= acc[0])
    D_face = sum(1 for k in labelled if k != "v007" and dkey[k][1] <= acc[1])
    g = runs.get("G22_C_none", [])
    m4 = [sum(v["depth_vs_key"] == "pass" for v in r_["per_opening"].values()) for r_ in g if r_["status"] == "scored"]
    g_fallback = [r_["overlay"]["fallback_used"] for r_ in g if r_["status"] == "scored"]
    # witness: target opening and locality vs v007, per rep
    wit = []
    for rw, ra in zip(runs.get("W_deep", []), runs["v007"]):
        if rw["status"] != "scored" or ra["status"] != "scored":
            continue
        tgt = [p for p in rw["per_opening"] if p.endswith("6189f94")][0]
        others = [p for p in rw["per_opening"] if p != tgt]
        changed = sum(1 for p in others for x in ("sill_head_c", "depth_rim", "depth_vs_key", "depth_vs_face")
                      if rw["per_opening"][p][x] != ra["per_opening"][p][x])
        wit.append({"rep": rw["rep"], "target_depth": (ra["per_opening"][tgt]["depth_rim"], rw["per_opening"][tgt]["depth_rim"]),
                    "target_face": (ra["per_opening"][tgt]["depth_vs_face"], rw["per_opening"][tgt]["depth_vs_face"]),
                    "others_changed": changed})
    wit_ok = bool(wit) and len(wit) == REPS and all(
        w["target_depth"][1] is not None and abs(w["target_depth"][1] - 0.71) <= 0.015 and w["target_face"] == ("pass", "fail")
        and w["others_changed"] == 0 for w in wit)
    inv = {}
    for k in ("G22_C_shift_opening", "G22_C_shift_wall"):
        inv[k] = [sum(1 for p in r_["per_opening"] if r_["per_opening"][p]["depth_rim"] != rc["per_opening"][p]["depth_rim"])
                  for r_, rc in zip(runs.get(k, []), g) if r_["status"] == "scored" and rc["status"] == "scored"]
    verdict = {"M1_nm_per_rep": m1, "M1_complete": m1_complete, "M2_frozen_measured_changed": m2,
               "D_key": D_key, "D_face": D_face, "depth_fails_median(key,face)": dkey,
               "M4_G22_pass_per_rep": m4, "G22_fallback_used_per_rep": g_fallback,
               "witness": wit, "witness_ok": wit_ok, "G22_invariance_depth_changed_vs_C_none": inv}
    confirmed = (m1_complete and m1 == [0] * REPS and not m2 and m4 == [6] * REPS and wit_ok and D_face == 0)
    refuted = (bool(m4) and min(m4) < 6) or (bool(wit) and not wit_ok) or D_face > 0
    verdict["H53"] = "confirmed" if confirmed else "refuted" if refuted else "inconclusive"
    post = flight()
    receipt |= {"status": "complete", "wall_s": round(time.time() - t0, 3), "runs": runs, "summary": summary,
                "verdict": verdict, "postflight_ok": all(v["ok"] for v in post.values()),
                "harness_sha256": {f: sha(os.path.join(HERE, f)) for f in ("run53.py", "score53.py", "mutate53.py")}}
    json.dump(receipt, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"wall_s": receipt["wall_s"], "postflight_ok": receipt["postflight_ok"],
                      "witness": receipt["witness"], "verdict": verdict}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
