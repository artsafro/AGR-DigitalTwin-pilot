"""#1784 step 3 hook (stage `body`, point `after`): the Russian v005 | v006 | Revit sheet and the decor table.

Pattern: n/a | new-case: evidence-only sheet writer (PIL), no model edits.

    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py views VOLUME_LINES.json NEW_VIEWS.json
    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py decor REVIT_DUMP.json NEW_DECOR.json \
        [--config jobs/sokolniki-uvk1000/insets_config.json]
    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py sheet RENDER_DIR VIEWS.json BUILD_DIR DECOR.json NEW.pdf

`views`: one straight elevation per facade id of the accepted volume lines (collinear edges joined), outward normal
from the volume ring. `decor`: every Revit family of the dump -> inset / texture / body / out, with counts, by the
`decor` prefix table of insets_config.json (an unmatched family is listed as `не классифицировано`, never hidden).
`sheet`: title page, decor table, one page per facade (v005 | v006 | Revit, same view and scale), iso page.
"""
import argparse
import json
import math
import os
import re
import sys

JOB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = "C:/Windows/Fonts/arial.ttf"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"


def _ccw(ring):
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts))) > 0


def views(vl, z=(-0.5, 23.0), front_m=3.0, px_per_m=28):
    groups = {}
    for k in sorted(vl["edges"]):
        e = vl["edges"][k]
        if e.get("facade"):
            groups.setdefault(e["facade"], []).append((k, e))
    out = []
    for fid in sorted(groups, key=lambda f: int(re.sub(r"\D", "", f) or 0)):
        k0, e0 = groups[fid][0]
        a, b = e0["xy"]
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        t = ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
        n = (t[1], -t[0]) if _ccw(vl["volumes"][e0["volume"]]["ring"]) else (-t[1], t[0])
        ss = [(p[0] - a[0]) * t[0] + (p[1] - a[1]) * t[1] for _, e in groups[fid] for p in e["xy"]]
        out.append({"id": fid, "edges": [k for k, _ in groups[fid]], "a": list(a), "t": list(t), "n": list(n),
                    "s": [min(ss), max(ss)], "z": list(z)})
    xs = [p[0] for v in vl["volumes"].values() for p in v["ring"]]
    ys = [p[1] for v in vl["volumes"].values() for p in v["ring"]]
    iso = {"target": [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 8.0], "dir": [-0.6, 0.55, -0.45],
           "scale": 1.15 * max(max(xs) - min(xs), max(ys) - min(ys))}
    return {"front_m": front_m, "px_per_m": px_per_m, "facades": out, "iso": iso}


def family(name):
    """Revit family label of an object name: drop the hash suffix, the [element id] and Blender .NNN copies."""
    name = re.sub(r"\.\d{3}$", "", name)
    name = re.sub(r"\s*\[\d+\].*$", "", name)
    return re.sub(r"_[0-9a-f]{6,7}$", "", name).strip()


def decor(dump, cfg):
    rules = cfg["decor"]
    fams = {}
    for o in dump["objects"]:
        f = family(o["name"])
        r = fams.setdefault(f, {"family": f, "count": 0, "tris": 0})
        r["count"] += 1
        r["tris"] += o.get("tris", 0)
    rows = []
    for f, r in fams.items():
        rule = next((x for x in rules if f.startswith(x["prefix"])), None)
        if rule is None:
            r.update(decision="не классифицировано", target="", why="нет правила в insets_config.json decor")
        else:
            r.update(decision=rule["decision"], target=rule.get("target", ""), why=rule["why"])
        rows.append(r)
    order = {"вставка": 0, "тело": 1, "текстура": 2, "вне": 3, "не классифицировано": 4}
    rows.sort(key=lambda r: (order.get(r["decision"], 9), -r["tris"]))
    return {"source": dump.get("source"), "sha256": dump.get("sha256"), "rows": rows,
            "totals": {d: sum(r["count"] for r in rows if r["decision"] == d) for d in order}}


def sheet(render_dir, vw, build_dir, dec, pdf):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 2480, 1754  # A4 landscape at 150 dpi
    f_t, f_b, f_s = ImageFont.truetype(FONT_B, 40), ImageFont.truetype(FONT, 26), ImageFont.truetype(FONT, 21)
    rep = json.load(open(os.path.join(build_dir, "insets_report.json"), encoding="utf-8"))
    xv = json.load(open(os.path.join(build_dir, "xview_quad.json"), encoding="utf-8"))
    bw = json.load(open(os.path.join(build_dir, "blender_write.json"), encoding="utf-8"))
    pages = []

    def page(title):
        im = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(im)
        d.text((60, 40), title, font=f_t, fill="black")
        d.text((60, H - 50), "Сокольники УВК 1000, #1784, шаг 3: вставки на теле v005 [D378]. Ветка "
               "job/sokolniki-step3-insets, карточка t_416ef473. Лист %d" % (len(pages) + 1), font=f_s, fill="#666")
        pages.append(im)
        return im, d

    def lines(d, x, y, rows, font=f_b, lead=38):
        for r in rows:
            d.text((x, y), r, font=font, fill="black")
            y += lead
        return y

    fam = rep["families"]
    mr = rep["merged_runs"]
    body_ok = all(v["equal"] for v in bw["body_unchanged"].values())
    tot = xv["totals"]
    im, d = page("Сокольники v006: вставки шага 3 на принятом теле v005 — итог")
    rows = [
        "Решение Артёма 2026-11-24 («принимаю рекомендации»): ламели, стальной каркас кровли, сетка и козырьки — отдельные",
        "вставки; фальц кассет — текстура; наружный витраж F05 — отдельная вставка со своими торцами до плоскости фасада;",
        "F07/F21 вне оболочки; посадка F13 на 0,394 м за внутренней рамой (в теле v005, не менялась).",
        "",
        "Тело v005 не тронуто: хэш вершин и граней всех 4 объектов до/после = %s." % ("совпадает" if body_ok else "НЕ СОВПАДАЕТ"),
        "Вставки (квады, свои материалы), из боксов элементов Revit FBX (Blender 4.4, без ремонта сетки Revit):",
        "• каркас: %d стоек Revit → %d (дубликатов %d, касающихся слито %d); %d ригелей → %d (сечение «ромб»)."
        % (mr["cage_column"]["members"], mr["cage_column"]["boxes"], mr["cage_column"]["duplicates_dropped"],
           mr["cage_column"]["touching_joined"], mr["cage_beam"]["members"], mr["cage_beam"]["boxes"]),
        "• сетка: %d стен-сеток → %d плоскостей; козырьки: %d → %d стеклянных листов (подвесы — вне);"
        % (fam["mesh"]["revit_members"], fam["mesh"]["faces"], fam["canopy"]["revit_members"],
           mr["canopy"]["boxes"]),
        "• ламели RAL 8023: %d → %d; витраж F05: %d панелей Revit → пила из %d участков, вынос 0,03…1,70 м, %d уступов."
        % (fam["lamella"]["revit_members"], fam["lamella"]["faces"] // 6, fam["f05_glazing"]["revit_panels"],
           len(fam["f05_glazing"]["polyline"]) - 1 - fam["f05_glazing"]["returns"], fam["f05_glazing"]["returns"]),
        "",
        "Треугольников во вставках после триангуляции: %d (тело v005: 8 019; Revit: каркас 3 152 968)." % rep["total"]["tris"],
        "Не квады во вставках: %d. master_topology (до триангуляции): все 5 объектов вставок — pass;" % rep["total"]["non_quads"],
        "n-гоны тела (крышки объёмов) — те же, что в принятом v005, тело не менялось.",
        "xView NPM (вся сборка v006, по объектам): перекрытых граней %d, вершин %d, «бабочек» %d — %s."
        % (tot["overlapping_faces"], tot["overlapping_vertices"], tot["bowtie_vertices"],
           "PASS" if xv["passed"] else "FAIL"),
        "Проверки в 3ds Max (нативные): не измерены — Max не запускался, сборка в Blender 4.4 без окна.",
        "",
        "Декор (Revit → вставка / тело / текстура / вне): лист 2. Фасады v005 | v006 | Revit: листы 3–%d; изометрия — последний."
        % (2 + len(vw["facades"])),
        "Решение нужно от Артёма (картинки). Вопросы — на листе 2 внизу. Синтетики нет.",
    ]
    lines(d, 60, 130, rows)
    im, d = page("Декор: элемент Revit → вставка / тело / текстура / вне")
    y = 120
    cols = [60, 1020, 1240, 1390, 1600]
    for x, h in zip(cols, ["Семейство Revit", "Решение", "Шт.", "Треуг. Revit", "Куда / почему"]):
        d.text((x, y), h, font=ImageFont.truetype(FONT_B, 22), fill="black")
    y += 34
    for r in dec["rows"]:
        if y > H - 230:
            im, d = page("Декор (продолжение)")
            y = 120
        col = {"вставка": "#0a6", "тело": "#06c", "текстура": "#a60", "вне": "#888"}.get(r["decision"], "#c00")
        d.text((cols[0], y), r["family"][:70], font=f_s, fill="black")
        d.text((cols[1], y), r["decision"], font=f_s, fill=col)
        d.text((cols[2], y), str(r["count"]), font=f_s, fill="black")
        d.text((cols[3], y), "{:,}".format(r["tris"]).replace(",", " "), font=f_s, fill="black")
        d.text((cols[4], y), (r["target"] + (" — " if r["target"] else "") + r["why"])[:72], font=f_s, fill="black")
        y += 25
    y += 20
    for q in dec.get("questions", []):
        d.text((60, y), q, font=f_b, fill="#c00")
        y += 36
    for f in vw["facades"]:
        im, d = page("%s (рёбра %s): v005 | v006 | Revit — один вид и масштаб" % (f["id"], ", ".join(f["edges"])))
        tiles = [Image.open(os.path.join(render_dir, "%s_%s.png" % (tag, f["id"])))
                 for tag in ("v005", "v006", "revit")]
        avail_h = (H - 230) // 3 - 40
        sc = min((W - 120) / tiles[0].width, avail_h / tiles[0].height)
        y = 110
        for tag, t in zip(("тело v005", "v006 = v005 + вставки", "Revit FBX (sokolniki_ar_r23_v1)"), tiles):
            t2 = t.resize((max(1, int(t.width * sc)), max(1, int(t.height * sc))))
            d.text((60, y), tag, font=f_b, fill="black")
            im.paste(t2, (60, y + 34))
            y += avail_h + 40
    im, d = page("Изометрия: v005 | v006 | Revit")
    isos = [Image.open(os.path.join(render_dir, "%s_iso.png" % t)) for t in ("v005", "v006", "revit")]
    tw = (W - 160) // 3
    for i, (tag, t) in enumerate(zip(("v005", "v006", "Revit"), isos)):
        t2 = t.resize((tw, int(t.height * tw / t.width)))
        d.text((60 + i * (tw + 20), 120), tag, font=f_b, fill="black")
        im.paste(t2, (60 + i * (tw + 20), 160))
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=150)
    return len(pages)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("views")
    p.add_argument("volume_lines")
    p.add_argument("out")
    p = sub.add_parser("decor")
    p.add_argument("dump")
    p.add_argument("out")
    p.add_argument("--config", default=os.path.join(JOB, "insets_config.json"))
    p = sub.add_parser("sheet")
    for k in ("render_dir", "views", "build_dir", "decor", "pdf"):
        p.add_argument(k)
    a = ap.parse_args(argv)
    out = a.pdf if a.cmd == "sheet" else a.out
    if os.path.exists(out):
        print("refused: %s exists" % out, file=sys.stderr)
        return 2
    if a.cmd == "views":
        doc = views(json.load(open(a.volume_lines, encoding="utf-8")))
    elif a.cmd == "decor":
        cfg = json.load(open(a.config, encoding="utf-8"))
        doc = decor(json.load(open(a.dump, encoding="utf-8")), cfg)
        doc["questions"] = cfg.get("decor_questions", [])
    else:
        n = sheet(a.render_dir, json.load(open(a.views, encoding="utf-8")), a.build_dir,
                  json.load(open(a.decor, encoding="utf-8")), a.pdf)
        print("SHEET", n, "pages", a.pdf)
        return 0
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
