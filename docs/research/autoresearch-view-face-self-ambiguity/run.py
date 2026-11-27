"""#143 OBSERVE series: self-ambiguity gate on the pinned #141 (1D raster) and #140 (2D vector) scorers.

Usage (repo root): uv run --offline --extra cad --extra pdf-review python \
    docs/research/autoresearch-view-face-self-ambiguity/run.py <new_out_dir>
Three fresh pairs (new Blender ray casts, new PDF/DXF reads); upstream code from full Git revisions.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import median
from types import ModuleType

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sa  # noqa: E402

R141 = "3716f5395667c17f8be8737313952aaa6285615c"
R140 = "ab33b7e4249f41232501d0c05534bd2793a15358"
P141 = "docs/research/autoresearch-view-face-raster"
P140 = "docs/research/autoresearch-view-face-2d"
WITNESS = {f"{v}/crop0.25@{p}" for v in ("А.2-Е.2", "Е.2-А.2") for p in ("0.0", "1.0")}


def blob(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"])


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def outcome(pick, gt):
    return "abstain" if pick is None else "correct" if pick == gt else "wrong"


# ---------- OBR22 K02, #141 1D scorer ----------
def obr_run(up, out, variant):
    base = load(f"b141_{variant}_{out.parent.name}", up / "run.py")
    orig = base.judge

    def judge(profile, width_m, faces, gt):
        r = orig(profile, width_m, faces, gt)
        c = r["C"]
        if c["outcome"] == "abstain":
            r["SA"] = {"outcome": "abstain", "reason": "upstream"}
            return r
        win = c["best"]
        per = sa.slide_all(base.score, profile, faces[win]["profile"], base.score.SLACK_PX)
        if abs(round(float(per.max()), 4) - c["scores"][str(win)]) > 1e-9:
            raise SystemExit(f"per-offset max != upstream score: {per.max()} vs {c['scores'][str(win)]}")
        fires, s2 = sa.gate(float(per.max()), per, len(profile))
        r["SA"] = {"outcome": "abstain" if fires else c["outcome"], "reason": "periodic" if fires else "kept",
                   "self2": None if s2 is None else round(s2, 4), "sep_px": sa.separation(len(profile))}
        return r

    base.judge = judge
    sys.argv = [str(up / "run.py"), str(out), variant]
    base.main()
    res = json.loads((out / "result.json").read_text(encoding="utf-8"))
    return base, res


def obr_tally(cases, fx):
    t = {}
    for arm in ("C", "SA"):
        for kind in ("full", "crop", "mirror"):
            for grp in ("long", "short"):
                sel = [c for c in cases if c["kind"] == kind and c["view"] in fx[f"{grp}_views"]]
                cnt = Counter(c[arm]["outcome"] if arm in c else "not_exercised" for c in sel)
                t[f"{arm}/{kind}/{grp}"] = {k: cnt[k] for k in ("correct", "wrong", "abstain", "not_exercised")}
    return t


# ---------- KPP1 / AC08, #140 2D scorer ----------
class Score(float):
    pass


def k140_module(up, side):
    score = ModuleType("score")
    exec(compile((up / "score.py").read_bytes(), f"{R140}:{P140}/score.py", "exec"), vars(score))
    orig_fs, orig_dec = score.face_score, score.decide

    def face_score(view, model, occupied, slack):
        s = orig_fs(view, model, occupied, slack)
        per = sa.face_score_all(score, view, model, occupied, slack)
        m = float(per.max()) if per.size else -1.0
        if abs(m - s) > 1e-12:
            raise SystemExit(f"2D per-x max != upstream score: {m} vs {s}")
        v = Score(s)
        v.per, v.w = per, view.shape[1]
        return v

    def decide(scores):
        pick = orig_dec(scores)
        if pick is None:
            side.append({"pick": None, "reason": "upstream"})
        else:
            fires, s2 = sa.gate(float(scores[pick]), scores[pick].per, scores[pick].w)
            side.append({"pick": None if fires else pick, "reason": "periodic" if fires else "kept",
                         "self2": None if s2 is None else round(s2, 6), "sep_px": sa.separation(scores[pick].w)})
        return pick

    score.face_score, score.decide = face_score, decide
    return score


def k_tally(rows):
    t = {}
    for arm in ("B", "SA"):
        for job in ("kpp1", "ac08"):
            for scope in ("full", "partial", "mirror"):
                cnt = Counter()
                for r in rows:
                    if r["fixture"] != job or not r["case"].startswith(scope):
                        continue
                    if scope == "mirror" and not r["changed_pixels"]:
                        cnt["not_exercised"] += 1
                        continue
                    pick = r["B"] if arm == "B" else r["SA"]["pick"]
                    cnt[outcome(pick, r["gt_az"])] += 1
                t[f"{arm}.{job}.{scope}"] = {k: cnt[k] for k in ("correct", "wrong", "abstain", "not_exercised")}
    return t


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    t0 = time.monotonic()
    up1, up0 = out / "up141", out / "up140"
    up1.mkdir(), up0.mkdir()
    for n in ("run.py", "sheet.py", "score.py", "rays_win.py", "fixture.json", "receipt.json"):
        (up1 / n).write_bytes(blob(R141, f"{P141}/{n}"))
    for n in ("run.py", "score.py", "receipt.json"):
        (up0 / n).write_bytes(blob(R140, f"{P140}/{n}"))
    sys.path.insert(0, str(up1))
    oracle141 = json.loads((up1 / "receipt.json").read_text(encoding="utf-8"))
    oracleB = {(r["fixture"], r["title"], r["gt_az"], r["case"]): r["B"]
               for r in json.loads((up0 / "receipt.json").read_text(encoding="utf-8"))["views"]}
    fx = json.loads((up1 / "fixture.json").read_text(encoding="utf-8"))

    side = []
    sys.modules["score"] = k140_module(up0, side)
    k = load("run140", up0 / "run.py")
    sys.modules.pop("score")
    kdir = out / "k140"
    inputs140 = k.prepare(kdir)

    pairs, timings, status = [], [], "finished"
    for i in (1, 2, 3):
        ts = time.monotonic()
        pdir = out / f"p{i}"
        pdir.mkdir()
        obr = {}
        for variant in ("R2", "R1"):
            sys.modules.pop("score", None), sys.modules.pop("sheet", None)
            base, res = obr_run(up1, pdir / f"obr-{variant}", variant)
            stripped = [{kk: vv for kk, vv in c.items() if kk != "SA"} for c in res["cases"]]
            if stripped != oracle141[variant]["cases"]:
                raise SystemExit(f"pair {i}: #141 {variant} case parity failed")
            obr[variant] = {"cases": [{"id": c["id"], "kind": c["kind"], "view": c["view"], "gt": c["gt"],
                                       "C": c.get("C", {}).get("outcome", c.get("status")), "SA": c.get("SA")}
                                      for c in res["cases"]],
                            "tally": obr_tally(res["cases"], fx), "hashes": res["hashes"]}
        side.clear()
        k.measure(kdir, i)
        rows = json.loads((kdir / f"pair-{i}.json").read_text(encoding="utf-8"))
        k.parity(kdir, rows)
        if len(side) != len(rows):
            raise SystemExit(f"pair {i}: side {len(side)} != rows {len(rows)}")
        for r, s in zip(rows, side):
            if oracleB[(r["fixture"], r["title"], r["gt_az"], r["case"])] != r["B"]:
                raise SystemExit(f"pair {i}: #140 B parity failed at {r['title']} {r['case']}")
            r["SA"] = s
        sem = {"obr22": obr, "k140": {"rows": rows, "tally": k_tally(rows)}}
        payload = json.dumps(sem, ensure_ascii=False, sort_keys=True).encode("utf-8")
        (pdir / "pair.json").write_bytes(payload)
        el = time.monotonic() - ts
        timings.append(round(el, 3))
        pairs.append({"sha256": sha_bytes(payload), "sem": sem})
        print(f"PAIR {i}: parity ok (#141 R1+R2 {len(oracle141['R2']['cases'])}x2, #140 {len(rows)}); {el:.1f} s",
              flush=True)
        if i == 1 and time.monotonic() - t0 + 4 * el > 900:
            status = "budget_stop"
            break

    verdicts = []
    for p in pairs:
        s = p["sem"]
        r2 = {c["id"]: c for c in s["obr22"]["R2"]["cases"]}
        clean = [c for c in r2.values() if c["kind"] != "mirror"]
        ob, kt = s["obr22"]["R2"]["tally"], s["k140"]["tally"]
        b1 = all(r2[w]["C"] == "wrong" and r2[w]["SA"]["reason"] == "periodic" for w in WITNESS)
        b2 = (sum(c["SA"]["outcome"] == "wrong" for c in clean) == 0
              and ob["SA/full/long"]["correct"] == 2)
        b3 = (ob["SA/crop/long"]["correct"] >= 5 and kt["SA.kpp1.partial"]["correct"] >= 16
              and kt["SA.kpp1.full"]["correct"] >= 2
              and sum(kt[f"SA.{j}.{x}"]["wrong"] for j in ("kpp1", "ac08") for x in ("full", "partial")) == 0)
        verdicts.append({"b1_witness": b1, "b2_obr_clean": b2, "b3_collateral": b3})
    hyp = "inconclusive"
    if status == "finished":
        hyp = "confirmed" if all(all(v.values()) for v in verdicts) else "refuted"
    if len({p["sha256"] for p in pairs}) != 1:
        status = "nonidentical_repeats"
    receipt = {"schema": "view-face-self-ambiguity/1", "card": "t_7f65d2eb (#143)", "status": status,
               "hypothesis": hyp, "verdicts": verdicts, "upstream": {"r141": R141, "r140": R140},
               "inputs141": pairs[0]["sem"]["obr22"]["R2"]["hashes"], "inputs140": inputs140,
               "candidate_sha256": {n: sha_bytes((HERE / n).read_bytes()) for n in ("run.py", "sa.py")},
               "uv_lock_sha256": sha_bytes(Path("uv.lock").read_bytes()),
               "timings_s": timings, "median_s": median(timings), "total_s": round(time.monotonic() - t0, 3),
               "pair_sha256": [p["sha256"] for p in pairs], "pair1": pairs[0]["sem"]}
    (out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                      newline="\n")
    print(json.dumps({"hypothesis": hyp, "status": status, "verdicts": verdicts, "timings": timings,
                      "obr_R2": pairs[0]["sem"]["obr22"]["R2"]["tally"], "obr_R1": pairs[0]["sem"]["obr22"]["R1"]["tally"],
                      "k140": pairs[0]["sem"]["k140"]["tally"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
