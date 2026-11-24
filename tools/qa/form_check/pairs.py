"""Form check v1 - run the detector, Artem's rules and the pair judge on Artem's accepted/rejected pairs.

usage (repo root, uv env):
  python -m tools.qa.form_check.pairs detect --out C:/x/form-check-v1/run01 [--pairs tools/qa/form_check/pairs_v1.json]
  python -m tools.qa.form_check.pairs render --out ...       # Blender renders + 2x2 judge composites
  python -m tools.qa.form_check.pairs judge  --out ... [--workers 4]
  python -m tools.qa.form_check.pairs table  --out ... [--png <sheet.png>]
OBSERVE only: reads exact bytes (SHA-256 prefix pinned), never writes next to a source, never gates delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.qa.form_check import detector as D
from tools.qa.form_check import judge as J
from tools.qa.form_check import report as P
from tools.qa.form_check import rules as R

HERE = Path(__file__).resolve().parent
EXTRACT = HERE / "extract_blender.py"
RENDER = HERE / "render_blender.py"
AUTO4 = [{"name": "V1", "caption": "V1: elevation seen from south", "dir": [0, 1, 0]},
         {"name": "V2", "caption": "V2: elevation seen from east", "dir": [-1, 0, 0]},
         {"name": "V3", "caption": "V3: elevation seen from north", "dir": [0, -1, 0]},
         {"name": "V4", "caption": "V4: elevation seen from west", "dir": [1, 0, 0]}]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pinned(path, prefix):
    full = sha256(path)
    if not full.startswith(prefix):
        raise SystemExit(f"hash mismatch: {path} {full[:16]} != {prefix}")
    return full


def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s)


# --- keys -------------------------------------------------------------------------------------------------------

def key_from_contour(spec):
    """KPP1 NW: a held-out key built from Artem's chosen contour A (body-contours/1). Straight outer faces at the
    contour levels; openings by their outer span; no reveal depth (A does not encode back reveals)."""
    ring = [{"ring_index": i, "xy": xy} for i, xy in enumerate(spec["ring"])]
    openings = []
    for o in spec["openings"]:
        a = spec["ring"][o["seg"][0]]
        b = spec["ring"][o["seg"][1]]
        ax = 0 if o["axis"] == "x" else 1
        t = sorted(abs(v - a[ax]) for v in (o["lo"], o["hi"]))
        assert abs(b[ax] - a[ax]) > 0
        openings.append({"id": o["id"], "contour_segment": o["seg"], "edge_s_m": t, "reveal_depth_m": None,
                         "sill_head_z_m": [1.125, 3.075]})
    lines = [[spec["ring"][i], spec["ring"][i + 1]] for i in range(len(spec["ring"]) - 1)]
    key = {"schema": "heldout-key/1 (form-check v1, from contour A)", "box_xy_m": spec["box"],
           "contour_vertices_in_box": ring, "openings": openings, "negatives": [],
           "profile": {"contour_z": spec["contour_z"], "opening_z": spec["opening_z"], "rim_z0": spec["rim_z0"]},
           "basis": spec["basis"]}
    return key, {z: lines for z in spec["contour_z"]}


def load_key(pair):
    if "key_from_contour" in pair:
        spec = pair["key_from_contour"]
        src = json.load(open(spec["path"], encoding="utf-8"))
        assert src["schema"] == "body-contours/1"
        return key_from_contour(spec), {"contour_sha256": pinned(spec["path"], spec["sha"])}
    key = json.load(open(pair["key"], encoding="utf-8"))
    ksec = json.load(open(pair["sections"], encoding="utf-8"))
    prov = {"key_sha256": pinned(pair["key"], pair["key_sha"]), "sections_sha256": pinned(pair["sections"], pair["sections_sha"])}
    if pair.get("amend"):
        key = {**key, "amend": pair["amend"]}
    return (key, ksec), prov


# --- Sokolniki: compare.json findings of t_57b332a4 as the known-defect ledger ------------------------------------

def ledger_items(variant, c004, c005):
    """Known defects of v004 (t_57b332a4 questions 1-4) and their state in v005 (compare_v005, D378)."""
    it = {}
    if variant == "v004":
        miss = c004["opening_status_counts"]["window"].get("missing", 0)
    else:
        miss = c005["opening_status_counts"]["v005"].get("window/missing", 0)
    it["known:F04-D02 windows missing over the N-D seam"] = D.st(miss == 0, f"window/missing = {miss}")
    for edge, f in c005["f05"].items():
        v = f[variant]
        it[f"known:F05 {edge} outer curtain wall cut in the body"] = D.st(
            v["mouth_area"] > 0, f"mouth {v['mouth_area']:.1f} m2 (IoU {v['iou']:.2f} with Revit glass, glass not cut "
                                 f"{v['glass_not_cut']:.1f} m2; IoU reported, not thresholded)")
    it["known:F06 22daf24 right side narrowed 0.268 m"] = {
        "status": "expected", "rule": "D378", "basis": "accepted as the corner edge, head +2.175, no ring (D378)"}
    if variant == "v005":
        fw = c005["facades_worse_explained"].get("F04", {})
        it["known:F04 missing area vs v004"] = {
            "status": "expected", "rule": "D378",
            "basis": f"+{fw.get('revit_wall_inside_new_mouths_m2')} m2 = Revit wall inside {fw.get('new_mouths')} new "
                     "partial mouths over the seam (D378 decision 1)"}
        unv = c005["mouths"]["v005"]["unverified"]
        it["known:mouths verified"] = (D.nm(f"unverified mouths {[u[0] for u in unv]}") if unv
                                       else D.st(True, "all mouths verified"))
        f13 = c005.get("f13") or []
        seats = c005.get("f13_seats_v005") or {}
        pres = sum(1 for r in f13 if r.get("status_v005") == "present")
        it["known:F13 one mouth per window pair, seat by section"] = D.nm(
            f"{pres}/{len(f13)} F13 nodes present, {len(seats)} mouths with seats; the seat plane is checked by "
            "section only (D378 decision 4)")
    else:
        it["known:F13 seat plane"] = D.nm("question 4 open in the v004 compare (resolved by D378 for v005)")
    return it


# --- commands ---------------------------------------------------------------------------------------------------

def cmd_detect(cfg, out):
    from dt_ai.core.blender_runner import run_blender
    results = []
    for pair in cfg["pairs"]:
        pdir = out / slug(pair["id"])
        pdir.mkdir(parents=True, exist_ok=True)
        if pair["kind"] == "ledger":
            c004 = json.load(open(pair["ledger"]["v004"]["path"], encoding="utf-8"))
            c005 = json.load(open(pair["ledger"]["v005"]["path"], encoding="utf-8"))
            prov = {k: pinned(v["path"], v["sha"]) for k, v in pair["ledger"].items()}
            for v in pair["variants"]:
                items = ledger_items(v["name"], c004, c005)
                results.append({"pair": pair["id"], "variant": v["name"], "artem": v["artem"], "cite": v["cite"],
                                "fbx_sha256": pinned(v["fbx"], v["sha"]), "provenance": prov, "source": "ledger",
                                "items": items, "verdict": D.verdict(items), "summary": D.summarize(items)})
            continue
        (key, ksec), prov = load_key(pair)
        json.dump(key, open(pdir / "key_used.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        for v in pair["variants"]:
            full = pinned(v["fbx"], v["sha"])
            ex = pdir / f"{slug(v['name'])}.extract.json"
            if not ex.exists():
                run_blender(EXTRACT, [v["fbx"], ex, pair["zmap"], v.get("name_re", ""), v.get("offset", "")],
                            output_json=ex, log_path=pdir / f"{slug(v['name'])}.extract.log")
            cand = json.load(open(ex, encoding="utf-8"))
            raw = D.score(key, ksec, cand)
            acc = [a for a in pair.get("accepted_deviations", []) if a.get("variant") == v["name"]]
            items = R.apply(raw["items"], acc)
            results.append({"pair": pair["id"], "variant": v["name"], "artem": v["artem"], "cite": v["cite"],
                            "fbx_sha256": full, "provenance": prov, "source": "scene", "items": items,
                            "raw_summary": D.summarize(raw["items"]), "openings_obs": raw["openings_obs"],
                            "verdict": D.verdict(items), "summary": D.summarize(items)})
    json.dump(results, open(out / "detector.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in results:
        print(r["pair"], r["variant"], r["artem"], r["verdict"], r["summary"])
    return results


def compose(view_dir, panels, out_png):
    from PIL import Image, ImageDraw, ImageFont
    ims = []
    for p in panels:
        im = Image.open(view_dir / f"{p['name']}.png").convert("RGBA")
        bg = Image.new("RGBA", im.size, "white")
        ims.append(Image.alpha_composite(bg, im).convert("RGB"))
    w, h = ims[0].size
    canvas = Image.new("RGB", (2 * w + 10, 2 * (h + 50)), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    for i, (p, im) in enumerate(zip(panels, ims)):
        x, y = (i % 2) * (w + 10), (i // 2) * (h + 50)
        draw.text((x + 8, y + 6), p.get("caption", p["name"]), fill="black", font=font)
        canvas.paste(im, (x, y + 40))
        draw.rectangle([x, y + 40, x + w - 1, y + 40 + h - 1], outline="black", width=2)
    canvas.save(out_png)
    return out_png


def cmd_render(cfg, out):
    from dt_ai.core.blender_runner import run_blender
    for pair in cfg["pairs"]:
        if "render" not in pair:
            continue
        pdir = out / slug(pair["id"]) / "render"
        pdir.mkdir(parents=True, exist_ok=True)
        panels = AUTO4 if pair["render"]["panels"] == "auto4" else pair["render"]["panels"]
        for v in pair["variants"]:
            pinned(v["fbx"], v["sha"])
            vd = pdir / slug(v["name"])
            vd.mkdir(exist_ok=True)
            spec = {"crop": pair["render"]["crop"], "name_re": v.get("name_re"),
                    "x_offset": [float(c) for c in v["offset"].split(",")] if v.get("offset") else None,
                    "panels": panels}
            (vd / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
            if not (vd / "render.json").exists():
                run_blender(RENDER, [v["fbx"], vd, vd / "spec.json"], output_json=vd / "render.json",
                            log_path=vd / "render.log")
            compose(vd, panels, pdir / f"{slug(v['name'])}.png")
            print("rendered", pair["id"], v["name"])


def judge_pngs(cfg, out):
    pairs = []
    for pair in cfg["pairs"]:
        ref = pair["reference"]
        if "judge_png" in pair:
            png = pair["judge_png"]
        elif "render" in pair:
            png = {v["name"]: str(out / slug(pair["id"]) / "render" / f"{slug(v['name'])}.png") for v in pair["variants"]}
        else:
            continue
        for v in pair["variants"]:
            if v["name"] != ref:
                pairs.append({"id": f"{pair['id']}|{ref}|{v['name']}", "a_png": png[ref], "b_png": png[v["name"]]})
    return pairs


def cmd_judge(cfg, out, workers):
    pairs = judge_pngs(cfg, out)
    jf = out / "judge_jobs.json"
    if jf.exists():
        jl = json.load(open(jf, encoding="utf-8"))
    else:
        jl = J.jobs(pairs)
        json.dump(jl, open(jf, "w", encoding="utf-8"), indent=1)
    recs = J.run(jl, out / "judge_calls", Path("C:/x/form-check-v1-calls"), workers=workers)
    agg = J.aggregate(recs)
    json.dump(agg, open(out / "judge.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(agg, ensure_ascii=False, indent=1))
    return agg


def nm_reasons(r):
    out = []
    for k, v in r["items"].items():
        if v["status"] == "not_measured":
            out.append(f"{k}: {v['basis']}")
    return out


def rows_from(cfg, det, agg):
    rows = []
    for r in det:
        pair = next(p for p in cfg["pairs"] if p["id"] == r["pair"])
        ref = pair["reference"]
        if r["variant"] == ref:
            jv = "reference"
        else:
            cell = (agg or {}).get(f"{r['pair']}|{ref}|{r['variant']}")
            jv = "not run" if cell is None else cell["consensus"]["equivalence"]
        judge_tool = {"Different": "defect", "Same": "ok"}.get(jv, "n/a")
        if r["variant"] == ref and r["artem"] == "accepted":
            judge_tool, jv = "n/a", "эталон пары"
        nmr = nm_reasons(r)
        rows.append({"pair": r["pair"], "variant": r["variant"], "artem": r["artem"], "detector": r["verdict"],
                     "agree_detector": P.agree(r["verdict"], r["artem"]), "judge": jv,
                     "agree_judge": P.agree(judge_tool, r["artem"]),
                     "not_measured": f"{len(nmr)}: " + "; ".join(nmr[:3]) if nmr else "-",
                     "fails": [f"{k}: {v['basis']}" for k, v in r["items"].items() if v["status"] == "fail"],
                     "expected": [f"{k}: {v['basis']}" for k, v in r["items"].items() if v["status"] == "expected"]})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["detect", "render", "judge", "table"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--pairs", default=str(HERE / "pairs_v1.json"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--png")
    a = ap.parse_args(argv)
    cfg = json.load(open(a.pairs, encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "detect":
        cmd_detect(cfg, out)
    elif a.cmd == "render":
        cmd_render(cfg, out)
    elif a.cmd == "judge":
        cmd_judge(cfg, out, a.workers)
    else:
        det = json.load(open(out / "detector.json", encoding="utf-8"))
        agg = json.load(open(out / "judge.json", encoding="utf-8")) if (out / "judge.json").exists() else None
        rows = rows_from(cfg, det, agg)
        json.dump(rows, open(out / "table.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        (out / "table.md").write_text(P.markdown_table(rows), encoding="utf-8")
        print(P.markdown_table(rows))


if __name__ == "__main__":
    main()
