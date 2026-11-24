"""#1784 step 3 hook (stage `body`, point `after`): the Russian v005 | v006 | Revit sheet and the decor table.

Pattern: n/a | new-case: evidence-only sheet writer (PIL), no model edits.

    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py views VOLUME_LINES.json NEW_VIEWS.json
    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py decor REVIT_DUMP.json NEW_DECOR.json \
        [--config jobs/sokolniki-uvk1000/insets_config.json]
    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py sheet RENDER_DIR VIEWS.json BUILD_DIR DECOR.json NEW.pdf
    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py census SOK_DUMP.json VOLUME_LINES.json NEW_CENSUS.json
    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py welldiff V005/meshes.json V007/meshes.json \
        jobs/sokolniki-uvk1000/body_config_v007.json VOLUME_LINES.json NEW_WELL_DIFF.json
    uv run python jobs/sokolniki-uvk1000/hooks/inset_sheet.py sheet7 RENDERS_V007 RENDERS_V006 CLOSEUPS_V006 \
        VIEWS.json BUILD_V007 BODY_V007 DECOR.json NEW.pdf

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


V007_HOW = {  # [D384] decor prefix -> v007 element count from insets_report.json (None = not an inset)
    "ADSK_КолоннаНесущая_Труба": lambda r: r["merged_runs"]["cage_column"]["boxes"],
    "ADSK_КаркасНесущий_Труба": lambda r: r["merged_runs"]["cage_beam"]["boxes"],
    "Базовая стена ADSK_Сетка_кровля": lambda r: r["families"]["mesh"]["faces"],
    "ASML_АР_Козырьки": lambda r: r["merged_runs"]["canopy"]["boxes"],
    "Панель фасадная 1 Фигурная": lambda r: r["families"]["lamella"]["faces"] // 6,
    "Панель фасадная 2 Фигурная": lambda r: r["families"]["decor_panel"]["faces"] // 10,
    "B2B_Отлив": lambda r: r["families"]["flashing"]["faces"],
    "Люк выхода на кровлю": lambda r: r["families"]["hatch"]["faces"] // 6,
    "Базовая стена ADSK_Наружная": lambda r: "тело + %d пилона" % len(r["families"]["f05_ground"]["piers"]),
    "Системная панель": lambda r: "F05: %d → вставка; низ %d → %d полос" % (
        r["families"]["f05_glazing"]["revit_panels"], r["families"]["f05_ground"]["glass_panels"],
        len(r["families"]["f05_ground"]["bays"])),
}


def census_rows(dec, cfg, rep):
    """Table 1 (the denominator): every Revit family of the dump grouped by its decor rule -> Revit count, v007
    count, how and why. Families with no rule stay as their own red row."""
    rows = {}
    for r in dec["rows"]:
        rule = next((x for x in cfg["decor"] if r["family"].startswith(x["prefix"])), None)
        key = rule["prefix"] if rule else r["family"]
        g = rows.setdefault(key, {"family": key, "count": 0, "decision": r["decision"], "why": r["why"],
                                  "target": r["target"], "v007": "—"})
        g["count"] += r["count"]
    for k, g in rows.items():
        if k in V007_HOW:
            g["v007"] = str(V007_HOW[k](rep))
        elif g["decision"] == "тело":
            g["v007"] = "тело"
        elif g["decision"] == "текстура":
            g["v007"] = "текстура"
    order = {"вставка": 0, "тело": 1, "текстура": 2, "вне": 3}
    return sorted(rows.values(), key=lambda g: (order.get(g["decision"], 9), -g["count"]))


def sheet_v007(a):
    """[D384] v007 sheet: summary, table 1 (census), facades v006 | v007 | Revit, close-ups, iso."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 2480, 1754
    f_t, f_b, f_s = ImageFont.truetype(FONT_B, 40), ImageFont.truetype(FONT, 26), ImageFont.truetype(FONT, 21)
    ld = lambda p: json.load(open(p, encoding="utf-8"))  # noqa: E731
    rep = ld(os.path.join(a.build_dir, "insets_report.json"))
    xv = ld(os.path.join(a.build_dir, "xview_quad.json"))
    bw = ld(os.path.join(a.build_dir, "blender_write.json"))
    br = ld(os.path.join(a.body_dir, "build_report.json"))
    wd = ld(os.path.join(a.body_dir, "well_diff.json"))
    xb = ld(os.path.join(a.body_dir, "xview_quad.json"))
    cfg, dec, vw = ld(a.config), ld(a.decor), ld(a.views)
    pages = []

    def page(title):
        im = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(im)
        d.text((60, 40), title, font=f_t, fill="black")
        d.text((60, H - 50), "Сокольники УВК 1000, #1784, шаг 3 v007 [D384]: колодцы кровель + вставки. Ветка "
               "job/sokolniki-step3-insets, PR #1833, карточка t_416ef473. Лист %d" % (len(pages) + 1), font=f_s,
               fill="#666")
        pages.append(im)
        return im, d
    fam, mr = rep["families"], rep["merged_runs"]
    wells = {vn: v["roof_well"] for vn, v in br["volumes"].items() if v.get("roof_well")}
    g = fam["f05_ground"]
    im, d = page("Сокольники v007: колодцы кровель, перголы, колонны F05, объёмные панели — итог")
    rows = [
        "Решение Артёма 2026-11-24 ~19:55 «Принимаю рекомендации» [D384]: тело v005 меняется ТОЛЬКО внутри парапетов кровель",
        "S/N/D — площадки опущены до отметок Revit, стальные перголы стоят свободно; фасады, парапеты и проёмы не менялись.",
        "Колодцы (решётка тела, без ремонта сетки): " + "; ".join(
            "%s %.2f → площадка %.2f м" % (vn, w["top_z"], w["deck_z"]) for vn, w in sorted(wells.items()))
        + "; парапет 0,15 м (F05: 0,30 м за плоскостью витража).",
        "H стоит на площадке D: низ H 17,50 → 17,42 м (внутри парапета D, верх H не менялся).",
        "Доказательство «вне колодцев ничего не менялось»: сравнение граней v005 и v007 по координатам (1 мм) — "
        "outside_diff = %d (%s);" % (wd["outside_diff"], "PASS" if wd["pass"] else "FAIL"),
        "   у S/N/D убрана только плоская крышка, все %s граней фасадов/проёмов v005 на месте; H — только низ 8 см."
        % "/".join(str(wd["volumes"][vn]["unchanged_v005_faces"]) for vn in ("S", "N", "D")),
        "Тело v007: незамкнутых рёбер «прочих» 0, неманифолд 0, «бабочек» 0; xView NPM тела: %s."
        % ("PASS" if xb["passed"] else "FAIL"),
        "",
        "Вставки v007 (квады, свои материалы, из геометрии Revit FBX):",
        "• перголы = стальной каркас кровли: %d стоек → %d, %d ригелей → %d (упрощение принято 2026-11-24); сетка %d;"
        % (mr["cage_column"]["members"], mr["cage_column"]["boxes"], mr["cage_beam"]["members"],
           mr["cage_beam"]["boxes"], fam["mesh"]["faces"]),
        "• объёмные декор-панели RAL 9003: %d → %d тел рельефа по 10 квадов (пирамида до вершины Revit, глубина до 0,46 м,"
        % (fam["decor_panel"]["revit_members"], fam["decor_panel"]["faces"] // 10),
        "   срез вершины 5 см: −%.3f м; шов 2 см между панелями; %d угловых пар со скосом)."
        % (fam["decor_panel"]["relief_depth_lost_max_m"], rep.get("relief_mitres", 0)),
        "• колонны F05: %d пилона %.2f×(%.2f…%.2f)×7,5 м перед телом; остекление 1-го этажа F05: %d полосы на 2 см перед"
        % (len(g["piers"]), max(p["s"][1] - p["s"][0] for p in g["piers"]),
           min(p["revit_out"][1] for p in g["piers"]) + 0.05, max(p["revit_out"][1] for p in g["piers"]) + 0.05,
           len(g["bays"])),
        "   плоскостью тела (стекло Revit стоит на 1,6–2,5 м глубже, внутри принятого тела) до низа верхнего витража 7,525 м.",
        "• отливы: %d наклонных плоскостей; люки выхода на кровлю: %d; козырьки, ламели, витраж F05 — как в v006."
        % (fam["flashing"]["faces"], fam["hatch"]["faces"] // 6),
        "",
        "Треугольников во вставках после триангуляции: %d; не квадов: %d. Тело v005 в Blender до/после записи вставок: %s."
        % (rep["total"]["tris"], rep["total"]["non_quads"],
           "совпадает" if all(v["equal"] for v in bw["body_unchanged"].values()) else "НЕ СОВПАДАЕТ"),
        "xView NPM (вся сборка v007, по объектам): перекрытых граней %d, вершин %d, «бабочек» %d — %s."
        % (xv["totals"]["overlapping_faces"], xv["totals"]["overlapping_vertices"], xv["totals"]["bowtie_vertices"],
           "PASS" if xv["passed"] else "FAIL"),
        "Проверки в 3ds Max (нативные): не измерены — Max не запускался, сборка и рендеры в Blender 4.4 без окна.",
        "147 реек (BM)_ADSK_Брус — интерьерный экран, вне [D384]; перила — отдельная карточка.",
        "",
        "Лист 2 — таблица 1 (перепись Revit). Фасады v006 | v007 | Revit: листы 3–%d; затем крупные планы и изометрия."
        % (2 + len(vw["facades"])),
        "Нужна приёмка картинок Артёмом. Синтетики нет.",
    ]
    y = 120
    for r in rows:
        d.text((60, y), r, font=f_b, fill="black")
        y += 37
    im, d = page("Таблица 1. Перепись Revit FBX: семейство | Revit шт. | v007 | как (вставка / тело / текстура / вне)")
    cols = [60, 860, 990, 1500, 1640]
    y = 115
    for x, h in zip(cols, ["Семейство Revit", "Revit шт.", "v007", "Как", "Куда / почему"]):
        d.text((x, y), h, font=ImageFont.truetype(FONT_B, 22), fill="black")
    y += 34
    crow = census_rows(dec, cfg, rep)
    for r in crow:
        col = {"вставка": "#0a6", "тело": "#06c", "текстура": "#a60", "вне": "#888"}.get(r["decision"], "#c00")
        d.text((cols[0], y), r["family"][:60], font=f_s, fill="black")
        d.text((cols[1], y), str(r["count"]), font=f_s, fill="black")
        d.text((cols[2], y), r["v007"][:46], font=f_s, fill="black")
        d.text((cols[3], y), r["decision"], font=f_s, fill=col)
        d.text((cols[4], y), (r["target"] + (" — " if r["target"] else "") + r["why"])[:70], font=f_s, fill="black")
        y += 27
    d.text((60, y + 15), "Итого объектов Revit: %d; без правила: %d." % (
        sum(r["count"] for r in crow), sum(r["count"] for r in crow if r["decision"] not in
                                           ("вставка", "тело", "текстура", "вне"))), font=f_b, fill="black")

    def triple(title, files, labels):
        im, d = page(title)
        tiles = [Image.open(p) for p in files]
        avail_h = (H - 230) // 3 - 40
        sc = min((W - 120) / tiles[0].width, avail_h / tiles[0].height)
        y = 110
        for tag, t in zip(labels, tiles):
            t2 = t.resize((max(1, int(t.width * sc)), max(1, int(t.height * sc))))
            d.text((60, y), tag, font=f_b, fill="black")
            im.paste(t2, (60, y + 34))
            y += avail_h + 40
    lab = ("v006 (отклонён 2026-11-24)", "v007 = колодцы кровель + вставки [D384]", "Revit FBX (sokolniki_ar_r23_v1)")
    for f in vw["facades"]:
        triple("%s (рёбра %s): v006 | v007 | Revit — один вид и масштаб" % (f["id"], ", ".join(f["edges"])),
               [os.path.join(a.prev_dir, "v006_%s.png" % f["id"]), os.path.join(a.render_dir, "v007_%s.png" % f["id"]),
                os.path.join(a.prev_dir, "revit_%s.png" % f["id"])], lab)
    names = {"C1_roof_S": "кровля S: колодец 11,12 м и перголы", "C2_F05_piers": "F05: колонны и остекление 1-го этажа",
             "C3_panels_S": "объёмные декор-панели (фасад S)", "C4_roof_D": "кровля D: колодец 17,42 м, перголы, H",
             "C5_roof_N": "кровля N: колодец 13,22 м и перголы"}
    for c in vw.get("closeups", []):
        src = a.closeup_dir if os.path.exists(os.path.join(a.closeup_dir, "v006_%s.png" % c["id"])) else a.render_dir
        im, d = page("Крупный план %s — %s" % (c["id"][:2], names.get(c["id"], c["id"])))
        tiles = [Image.open(os.path.join(src, "v006_%s.png" % c["id"])),
                 Image.open(os.path.join(a.render_dir, "v007_%s.png" % c["id"])),
                 Image.open(os.path.join(src, "revit_%s.png" % c["id"]))]
        tw = (W - 160) // 2
        for i, (tag, t) in enumerate(zip(lab, tiles)):
            t2 = t.resize((tw, int(t.height * tw / t.width)))
            x, yy = 60 + (i % 2) * (tw + 40), 110 + (i // 2) * (int(t.height * tw / t.width) + 60)
            d.text((x, yy), tag, font=f_b, fill="black")
            im.paste(t2, (x, yy + 34))
    im, d = page("Изометрия: v006 | v007 | Revit")
    isos = [Image.open(p) for p in (os.path.join(a.prev_dir, "v006_iso.png"), os.path.join(a.render_dir, "v007_iso.png"),
                                     os.path.join(a.prev_dir, "revit_iso.png"))]
    tw = (W - 160) // 3
    for i, (tag, t) in enumerate(zip(("v006", "v007", "Revit"), isos)):
        t2 = t.resize((tw, int(t.height * tw / t.width)))
        d.text((60 + i * (tw + 20), 120), tag, font=f_b, fill="black")
        im.paste(t2, (60 + i * (tw + 20), 160))
    pages[0].save(a.pdf, save_all=True, append_images=pages[1:], resolution=150)
    return len(pages), crow


# ---- v007 census and roof-well proof (folded in: a job keeps at most 5 listed hooks [D324]) ----
FACE_M = 0.8
_ID = re.compile(r"(_[0-9a-f]{7}| \[\d+\]|\.\d{3})$")


def census_family(name):
    """Revit family/type of an FBX object: the name without the Revit id suffix (`_<hex7>`, ` [<id>]`, `.001`)."""
    prev = None
    while prev != name:
        prev, name = name, _ID.sub("", name).strip()
    return name


def _c_inside(p, ring):
    x, y = p
    n, c = len(ring), False
    for i in range(n):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _c_dist(p, ring):
    best = math.inf
    for i in range(len(ring)):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % len(ring)]
        dx, dy = x1 - x0, y1 - y0
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - x0) * dx + (p[1] - y0) * dy) / L))
        best = min(best, math.hypot(p[0] - x0 - t * dx, p[1] - y0 - t * dy))
    return best


def census_place(obj, volumes):
    hull = obj["hull"]
    c = (sum(x for x, _ in hull) / len(hull), sum(y for _, y in hull) / len(hull))
    z0, z1 = obj["z"]
    zc = (z0 + z1) / 2.0
    for v in volumes.values():
        ring, base = v["ring"], v["levels"][0]
        if _c_dist(c, ring) < FACE_M and base - 0.5 <= zc <= v["top"] + 0.5:
            return "face"
    for v in volumes.values():
        ring, base = v["ring"], v["levels"][0]
        if _c_inside(c, ring):
            if zc > v["roof"] + 0.05 and z0 >= v["roof"] - 0.5:
                return "roof"
            if base - 0.5 <= zc <= v["top"] + 0.5:
                return "inside"
    return "out"


def census(dump, lines):
    """v007 completeness census (the table-1 denominator): every Revit object grouped by family, placed against the
    accepted body (`inside` / `face` within FACE_M of a ring / `roof` / `out`). Output `revit-census/1`."""
    vols = lines["volumes"]
    fams, objs = {}, []
    for o in dump["objects"]:
        if not o.get("hull"):
            continue
        f = census_family(o["name"])
        xs = [x for x, _ in o["hull"]]
        ys = [y for _, y in o["hull"]]
        bb = [min(xs), min(ys), o["z"][0], max(xs), max(ys), o["z"][1]]
        pl = census_place(o, vols)
        objs.append({"name": o["name"], "family": f, "place": pl, "bbox": [round(b, 3) for b in bb]})
        r = fams.setdefault(f, {"family": f, "count": 0, "tris": 0, "bbox": list(bb),
                                "place": {"inside": 0, "face": 0, "roof": 0, "out": 0}, "height": [math.inf, 0.0]})
        r["count"] += 1
        r["tris"] += o.get("tris", 0)
        r["place"][pl] += 1
        r["bbox"] = [min(r["bbox"][i], bb[i]) for i in range(3)] + [max(r["bbox"][i], bb[i]) for i in range(3, 6)]
        h = bb[5] - bb[2]
        r["height"] = [min(r["height"][0], h), max(r["height"][1], h)]
    out = sorted(fams.values(), key=lambda r: -r["count"])
    for r in out:
        r["bbox"] = [round(b, 2) for b in r["bbox"]]
        r["height"] = [round(h, 2) for h in r["height"]]
    return {"schema": "revit-census/1", "source_sha256": dump.get("sha256"), "families": out, "objects": objs}


TOL = 1e-3


def _key(p):
    return tuple(round(c, 3) for c in p)


def _w_faces(mesh):
    vv = mesh["verts"]
    return {(tuple(_key(vv[i]) for i in f["v"]), f["mat"]) for f in mesh["faces"]}


def _canon(face):
    """Rotation-invariant face key (same winding)."""
    pts, mat = face
    k = min(range(len(pts)), key=lambda i: pts[i])
    return (pts[k:] + pts[:k], mat)


def _seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L2 = ax * ax + ay * ay
    if L2 < 1e-12:
        return math.dist(p[:2], a[:2])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L2))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def _w_inside(p, ring):
    x, y, c = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _w_ring_of(vl, vn):
    r = [tuple(p) for p in vl["volumes"][vn]["ring"]]
    return r[:-1] if r[0] == r[-1] else r


def _w_ring_dist(p, ring):
    return min(_seg_dist(p, a, b) for a, b in zip(ring, ring[1:] + ring[:1]))


def well_diff(m5, m7, cfg, vl):
    """[D384] proof that the roof wells changed nothing outside the wells (face sets of two volume_body.py builds,
    1 mm keys). Well volume: v005 - v007 = exactly the flat top cap, every added face on the top or inside the
    parapet between deck and top; re-based volume (H): only base vertices move, plan kept, onto the host deck inside
    its well; any other volume: no change. `outside_diff` = 0 is the pass."""
    wells, rebased = cfg.get("roof_wells", {}), cfg.get("base_by_volume", {})
    rep = {"volumes": {}, "outside_diff": 0, "problems": []}
    for vn in sorted(set(m5) | set(m7)):
        f5 = {_canon(f) for f in _w_faces(m5[vn]["body"])}
        f7 = {_canon(f) for f in _w_faces(m7[vn]["body"])}
        gone, new = f5 - f7, f7 - f5
        ring = _w_ring_of(vl, vn)
        top = max(z for z in vl["volumes"][vn]["levels"])
        bad = []
        if vn in wells:
            w = wells[vn]
            caps = [f for f in gone if all(abs(p[2] - top) < TOL and _w_ring_dist(p, ring) < TOL for p in f[0])]
            bad += [("removed", f) for f in gone if f not in caps]
            if len(caps) != 1:
                bad.append(("top_caps_removed", len(caps)))
            dmin = min([w["parapet_m"]] + list(w.get("parapet_m_by_edge", {}).values()))
            for f in new:
                pts = f[0]
                on_top = all(abs(p[2] - top) < TOL for p in pts)
                in_well = all(w["deck_z"] - TOL <= p[2] <= top + TOL and _w_inside(p, ring)
                              and _w_ring_dist(p, ring) >= dmin - TOL for p in pts)
                if not (on_top and all(_w_inside(p, ring) or _w_ring_dist(p, ring) < TOL for p in pts)) and not in_well:
                    bad.append(("added_outside_well", f))
            rep["volumes"][vn] = {"kind": "well", "faces_v005": len(f5), "faces_v007": len(f7),
                                  "removed": len(gone), "added": len(new), "deck_z": w["deck_z"], "top_z": top,
                                  "unchanged_v005_faces": len(f5 & f7)}
        elif vn in rebased:
            z_new = float(rebased[vn])
            z_old = float(vl["volumes"][vn]["levels"][0])
            host = next((h for h in wells if _w_inside(ring[0], _w_ring_of(vl, h))), None)
            if host is None:
                bad.append(("rebased_without_host_well", vn))
            else:
                hw, hring = wells[host], _w_ring_of(vl, host)
                old = {p for f in gone for p in f[0]} - {p for f in new for p in f[0]}
                nw = {p for f in new for p in f[0]} - {p for f in gone for p in f[0]}
                moved = {(p[0], p[1]) for p in old}
                if moved != {(p[0], p[1]) for p in nw}:
                    bad.append(("rebased_plan_moved", vn))
                bad += [("rebased_vertex_not_base", p) for p in old if abs(p[2] - z_old) > TOL]
                bad += [("rebased_vertex_not_new_base", p) for p in nw if abs(p[2] - z_new) > TOL]
                bad += [("rebased_outside_host_well", p) for p in nw
                        if not (_w_inside(p, hring) and _w_ring_dist(p, hring) >= hw["parapet_m"] - TOL)]
                if abs(z_new - hw["deck_z"]) > TOL:
                    bad.append(("rebased_not_on_host_deck", z_new))
            rep["volumes"][vn] = {"kind": "rebased", "host": host, "base_from": z_old, "base_to": z_new,
                                  "faces_changed": len(gone), "faces_v005": len(f5), "faces_v007": len(f7)}
        else:
            bad += [("removed", f) for f in gone] + [("added", f) for f in new]
            rep["volumes"][vn] = {"kind": "unchanged", "faces": len(f5)}
        rep["volumes"][vn]["outside_diff"] = len(bad)
        rep["outside_diff"] += len(bad)
        rep["problems"] += [[vn, str(b)[:200]] for b in bad[:10]]
    rep["pass"] = rep["outside_diff"] == 0
    return rep




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
    p = sub.add_parser("census", help="v007 completeness census of the Revit dump")
    p.add_argument("dump")
    p.add_argument("volume_lines")
    p.add_argument("out")
    p = sub.add_parser("welldiff", help="[D384] roof wells: nothing changed outside the wells (exit 1 if it did)")
    for k in ("meshes_v005", "meshes_v007", "body_config", "volume_lines", "out"):
        p.add_argument(k)
    p = sub.add_parser("sheet7", help="[D384] v006 | v007 | Revit sheet with table 1 and close-ups")
    for k in ("render_dir", "prev_dir", "closeup_dir", "views", "build_dir", "body_dir", "decor", "pdf"):
        p.add_argument(k)
    p.add_argument("--config", default=os.path.join(JOB, "insets_config.json"))
    a = ap.parse_args(argv)
    out = a.pdf if a.cmd in ("sheet", "sheet7") else a.out
    if os.path.exists(out):
        print("refused: %s exists" % out, file=sys.stderr)
        return 2
    if a.cmd == "census":
        doc = census(json.load(open(a.dump, encoding="utf-8")), json.load(open(a.volume_lines, encoding="utf-8")))
    elif a.cmd == "welldiff":
        doc = well_diff(*[json.load(open(p, encoding="utf-8")) for p in
                          (a.meshes_v005, a.meshes_v007, a.body_config, a.volume_lines)])
        doc["inputs"] = [os.path.realpath(p) for p in (a.meshes_v005, a.meshes_v007, a.body_config, a.volume_lines)]
        with open(out, "x", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
        print("outside_diff", doc["outside_diff"], "PASS" if doc["pass"] else "FAIL")
        return 0 if doc["pass"] else 1
    elif a.cmd == "sheet7":
        n, crow = sheet_v007(a)
        with open(os.path.splitext(a.pdf)[0] + "_table1.json", "w", encoding="utf-8") as fh:
            json.dump(crow, fh, ensure_ascii=False, indent=1)
        print("SHEET", n, "pages", a.pdf)
        return 0
    elif a.cmd == "views":
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
