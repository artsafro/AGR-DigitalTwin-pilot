"""Step 0 of the OKS trail: propose a split of a customer Revit FBX into logical layers [D390] (#1867).

Pattern: n/a | new-case: shared scene-prepare core - Revit family/material rules from one data file
(library/scene_layers/revit_layers_v001.json) + position vs the building envelope -> one layer per object, census,
Russian review sheet; Blender side tools/methods/body/scene_prepare_blender.py writes the layered .blend and the
proposed FBX for Artem's correction in 3ds Max. Ports the job-local v007 census (#1784, PR #1833 inset_sheet.census)
family/place logic into a shared module.

    agr scene prepare SRC.fbx --out NEW_DIR [--rules R.json] [--dump DUMP.json] [--blender EXE] [--no-blend]
                      [--compare census_v007.json]

The split is a PROPOSAL: objects no rule names go to 00_РЕШИТЬ_ЧЕЛОВЕКУ (never guessed); Artem corrects the split in
Max and saves `<job>_split_ACCEPTED`; later stages read only the accepted layers. Exit 0 = written and nothing to
decide, 1 = written with objects in 00_РЕШИТЬ_ЧЕЛОВЕКУ (listed in census.md), 2 = refused/error (nothing published).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES = ROOT / "library/scene_layers/revit_layers_v001.json"
BLENDER_SCRIPT = ROOT / "tools/methods/body/scene_prepare_blender.py"
DUMP_SCRIPT = ROOT / "tools/methods/body/revit_fbx_dump_blender.py"
# Revit FBX crash Blender 5.1.2 (#1784 intake); 4.4 is the Revit-FBX import version unless --blender/env says otherwise.
REVIT_BLENDER = "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe"
LAYERS = ("UNCLASSIFIED", "BODY", "WINDOWS", "DOORS", "CURTAIN_WALL", "DECOR", "RAILINGS", "ROOF_EQUIPMENT", "SITE",
          "INTERIOR_OUT")
PLACES = ("inside", "face", "roof", "out")
_ID = re.compile(r"(_[0-9a-f]{7}| \[\d+\]|\.\d{3})$")


class ScenePrepareError(ValueError):
    """Refusal with a message naming the offending record/rule."""


def family_of(name: str) -> str:
    """Revit family/type of an FBX object: the name without the Revit id suffix (`_<hex7>`, ` [<id>]`, `.001`)."""
    prev = None
    while prev != name:
        prev, name = name, _ID.sub("", name).strip()
    return name


def _compile(rule, key, where, ids):
    try:
        rule["_re"] = re.compile(rule[key])
    except (re.error, KeyError, TypeError) as exc:
        raise ScenePrepareError(f"{where}: bad regex {rule.get(key)!r}: {exc}") from exc
    if "min_z0_above_base_m" in rule and not (_finite(rule["min_z0_above_base_m"]) and rule["min_z0_above_base_m"] >= 0):
        raise ScenePrepareError(f"{where}: min_z0_above_base_m must be a finite number >= 0")
    if "flag" in rule:
        fl = rule["flag"]
        if not (isinstance(fl, dict) and isinstance(fl.get("key"), str) and fl["key"] and isinstance(fl.get("ru"), str)
                and fl["ru"] and set(fl.get("places", PLACES)) <= set(PLACES)):
            raise ScenePrepareError(f"{where}: flag needs non-empty key and ru strings and places from {PLACES}")
    if "below_parapet" in rule and (rule["below_parapet"] not in ids or rule["below_parapet"] == "UNCLASSIFIED"):
        raise ScenePrepareError(f"{where}: below_parapet: unknown layer {rule['below_parapet']!r}")
    if rule.get("decide"):
        return
    if ("layer" in rule) == ("by_place" in rule):
        raise ScenePrepareError(f"{where}: needs exactly one of layer / by_place")
    targets = [rule["layer"]] if "layer" in rule else []
    if "by_place" in rule:
        bp = rule["by_place"]
        if not isinstance(bp, dict) or set(bp) != set(PLACES):
            missing = sorted(set(PLACES) - set(bp or {}))
            raise ScenePrepareError(f"{where}: by_place must map exactly {PLACES}; missing {missing}, got {sorted(bp)}")
        targets = list(bp.values())
    for t in targets:
        if t not in ids:
            raise ScenePrepareError(f"{where}: unknown layer {t!r}")
        if t == "UNCLASSIFIED":
            raise ScenePrepareError(f"{where}: UNCLASSIFIED is not a rule target; use decide: true")


def load_rules(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "agr-scene-layers/1":
        raise ScenePrepareError(f"rules schema must be agr-scene-layers/1, got {data.get('schema')!r}")
    ids = [la.get("id") for la in data.get("layers", [])]
    if tuple(ids) != LAYERS:
        raise ScenePrepareError(f"rules layers must be exactly {LAYERS}, got {ids}")
    for la in data["layers"]:
        if not la.get("ru") or not la.get("max_layer") or len(la.get("color", [])) != 3:
            raise ScenePrepareError(f"layer {la['id']}: needs ru, max_layer and an RGB color")
    env = data.get("envelope") or {}
    for k in ("families", "slabs", "wall_top", "wall_top_m", "close_m", "face_m", "z_margin_m", "min_area_m2",
              "parapet_max_m"):
        if k not in env:
            raise ScenePrepareError(f"envelope.{k} missing")
    for k in ("wall_top_m", "close_m", "face_m", "z_margin_m", "min_area_m2", "parapet_max_m"):
        if not (isinstance(env[k], (int, float)) and math.isfinite(env[k]) and env[k] >= 0):
            raise ScenePrepareError(f"envelope.{k} must be a finite number >= 0")
    env["_re"] = [re.compile(p) for p in env["families"]]
    env["_slab_re"] = [re.compile(p) for p in env["slabs"]]
    for i, r in enumerate(data.get("rules", [])):
        _compile(r, "family", f"rules[{i}]", ids)
    for i, r in enumerate(data.get("material_rules", [])):
        _compile(r, "material", f"material_rules[{i}]", ids)
    data["_path"] = str(path)
    data["_sha256"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return data


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _check_record(o):
    name = o.get("name")
    if not isinstance(name, str) or not name:
        raise ScenePrepareError(f"object without a name: {str(o)[:80]}")
    hull = o.get("hull")
    if hull == [] and o.get("z") is None:
        return False
    z = o.get("z")
    if not (isinstance(z, list) and len(z) == 2 and all(map(_finite, z)) and z[0] <= z[1]):
        raise ScenePrepareError(f"object {name!r}: bad z {z!r}")
    if not (isinstance(hull, list) and len(hull) >= 2 and all(
            isinstance(p, list) and len(p) == 2 and all(map(_finite, p)) for p in hull)):
        raise ScenePrepareError(f"object {name!r}: bad hull")
    return True


def _envelope(objs, env):
    from shapely.geometry import MultiPoint, Polygon
    from shapely.ops import unary_union
    parts = [MultiPoint([tuple(p) for p in o["hull"]]).convex_hull.buffer(env["close_m"], join_style="mitre")
             for o in objs if any(r.search(o["family"]) for r in env["_re"])]
    if not parts:
        raise ScenePrepareError(f"no envelope objects (families {env['families']}): cannot place objects vs envelope")
    merged = unary_union(parts).buffer(-env["close_m"], join_style="mitre")
    polys = [Polygon(g.exterior) for g in getattr(merged, "geoms", [merged]) if not g.is_empty]
    polys = [p for p in polys if p.area >= env["min_area_m2"]]
    if not polys:
        raise ScenePrepareError(f"envelope has no part >= {env['min_area_m2']} m2")
    return unary_union(polys)


def _slabs_at(c, slabs, tree):
    from shapely.geometry import Point
    pt = Point(c)
    return [slabs[i] for i in tree.query(pt) if slabs[i]["_poly"].covers(pt)]


def _place(o, c, foot, env, slabs_here, base, top):
    """inside / face / roof / out of one object (centroid c) vs the envelope footprint.

    face = centroid strictly < face_m from the footprint boundary and its centre not above the local envelope top
    (+ z_margin); roof = near the footprint, standing on an above-ground slab/roof covering c (its top <= z0 +
    z_margin) with no slab/roof covering c above the object's centre."""
    from shapely.geometry import Point
    z0, z1 = o["z"]
    zc = (z0 + z1) / 2.0
    pt = Point(c)
    d = foot.boundary.distance(pt)
    near = foot.covers(pt) or d < env["face_m"]
    if d < env["face_m"] and base - env["z_margin_m"] <= zc <= top + env["z_margin_m"]:
        return "face", None
    under = [s for s in slabs_here if base + env["z_margin_m"] < s["z"][1] <= z0 + env["z_margin_m"]]
    if near and under and not any(s["z"][0] >= zc for s in slabs_here):
        return "roof", max(under, key=lambda s: s["z"][1])
    if foot.covers(pt):
        return "inside", None
    return "out", None


def _parapet_top(slab, walls, wtree, env):
    """Top of the parapet around the roof `slab`: the highest envelope wall touching the slab outline whose top is
    above the roof and at most parapet_max_m above it (a taller wall is a storey wall, not a parapet); None if none."""
    s_top = slab["z"][1]
    ring = slab["_poly"].boundary.buffer(env["close_m"])
    tops = [walls[i]["z"][1] for i in wtree.query(ring) if walls[i]["_poly"].intersects(ring)
            and s_top < walls[i]["z"][1] <= s_top + env["parapet_max_m"]]
    return max(tops) if tops else None


def _apply(rule, place, hidden=False):
    if rule.get("decide"):
        return "UNCLASSIFIED"
    if hidden and place == "roof" and "below_parapet" in rule:
        return rule["below_parapet"]
    return rule["layer"] if "layer" in rule else rule["by_place"][place]


def classify(dump: dict, rules: dict) -> dict:
    """Every dump object -> one layer (or the drop list with its reason). Raises ScenePrepareError on bad input."""
    from shapely.geometry import MultiPoint
    from shapely.strtree import STRtree
    if not isinstance(dump, dict) or dump.get("schema") != "revit-fbx-dump/1":
        raise ScenePrepareError(f"dump schema must be revit-fbx-dump/1, got {dump.get('schema') if isinstance(dump, dict) else dump!r}")
    objects = dump.get("objects") or []
    if not objects:
        raise ScenePrepareError("dump has no objects")
    seen, geo, dropped = set(), [], []
    for o in objects:
        ok = _check_record(o)
        if o["name"] in seen:
            raise ScenePrepareError(f"duplicate object name {o['name']!r}")
        seen.add(o["name"])
        if not ok:
            dropped.append({"name": o["name"], "reason": "no_geometry"})
            continue
        geo.append(dict(o, family=family_of(o["name"])))
    env = rules["envelope"]
    foot = _envelope(geo, env)
    env_objs = [o for o in geo if any(r.search(o["family"]) for r in env["_re"])]
    slabs = [o for o in geo if any(r.search(o["family"]) for r in env["_slab_re"])]
    for o in env_objs + slabs:
        o["_poly"] = MultiPoint([tuple(p) for p in o["hull"]]).convex_hull
    tree = STRtree([o["_poly"] for o in slabs])
    walls = [o for o in env_objs if re.search(env["wall_top"], o["family"])]
    wtree = STRtree([o["_poly"] for o in walls]) if walls else None
    inside_env = [o for o in env_objs if foot.buffer(env["face_m"]).covers(o["_poly"].centroid)]
    base = min(o["z"][0] for o in inside_env) if inside_env else 0.0
    gtop = max(o["z"][1] for o in inside_env) if inside_env else 0.0
    out_objs, unclassified = [], []
    for o in geo:
        c = (sum(x for x, _ in o["hull"]) / len(o["hull"]), sum(y for _, y in o["hull"]) / len(o["hull"]))
        top = gtop
        if wtree is not None:
            from shapely.geometry import Point
            near_w = [walls[i]["z"][1] for i in wtree.query(Point(c).buffer(env["wall_top_m"]))]
            top = max(near_w) if near_w else gtop
        place, roof_slab = _place(o, c, foot, env, _slabs_at(c, slabs, tree), base, top)
        ptop = _parapet_top(roof_slab, walls, wtree, env) if roof_slab is not None and wtree is not None else None
        hidden = ptop is not None and o["z"][1] <= ptop
        layer, rule_ref, conf, why, flag = "UNCLASSIFIED", None, "none", "no family or material rule matched", None
        for i, r in enumerate(rules.get("rules", [])):
            if r["_re"].search(o["family"]) and o["z"][0] - base >= r.get("min_z0_above_base_m", -math.inf):
                layer, rule_ref, conf = _apply(r, place, hidden), f"rules[{i}]", "name"
                why = r.get("why") if r.get("decide") else None
                fl = r.get("flag")
                if fl and place in fl.get("places", PLACES):
                    flag = fl
                break
        else:
            for i, r in enumerate(rules.get("material_rules", [])):
                if any(r["_re"].search(m) for m in o.get("materials") or []):
                    layer, rule_ref, conf, why = _apply(r, place, hidden), f"material_rules[{i}]", "material", None
                    break
        rec = {"name": o["name"], "family": o["family"], "layer": layer, "place": place, "rule": rule_ref,
               "confidence": conf, "materials": o.get("materials", []), "tris": o.get("tris", 0),
               "parapet_top": ptop, "flag": flag["key"] if flag else None,
               "bbox": [round(v, 3) for v in (min(x for x, _ in o["hull"]), min(y for _, y in o["hull"]), o["z"][0],
                                              max(x for x, _ in o["hull"]), max(y for _, y in o["hull"]), o["z"][1])]}
        if layer == "UNCLASSIFIED":
            unclassified.append({"name": o["name"], "family": o["family"]})
            rec["why"] = why
        out_objs.append(rec)
    layers = []
    for la in rules["layers"]:
        mine = [o for o in out_objs if o["layer"] == la["id"]]
        fam = {}
        for o in mine:
            fam[o["family"]] = fam.get(o["family"], 0) + 1
        bb = None
        if mine:
            bb = [round(min(o["bbox"][i] for o in mine), 2) for i in range(3)] + \
                 [round(max(o["bbox"][i] for o in mine), 2) for i in range(3, 6)]
        layers.append({"id": la["id"], "max_layer": la["max_layer"], "ru": la["ru"], "color": la["color"],
                       "count": len(mine), "tris": sum(o["tris"] or 0 for o in mine), "bbox": bb,
                       "families": [{"family": f, "count": n} for f, n in sorted(fam.items(), key=lambda t: (-t[1], t[0]))]})
    flags = {}
    for r in rules.get("rules", []):
        if r.get("flag"):
            flags.setdefault(r["flag"]["key"], {"key": r["flag"]["key"], "ru": r["flag"]["ru"], "count": 0,
                                                "layers": {}, "families": {}})
    for o in out_objs:
        if o["flag"]:
            f = flags[o["flag"]]
            f["count"] += 1
            f["layers"][o["layer"]] = f["layers"].get(o["layer"], 0) + 1
            f["families"][o["family"]] = f["families"].get(o["family"], 0) + 1
    return {"schema": "agr-scene-census/1", "status": "proposed", "source": dump.get("source"),
            "source_sha256": dump.get("sha256"), "rules": rules.get("_path"), "rules_sha256": rules.get("_sha256"),
            "envelope": {"area_m2": round(foot.area, 2), "parts": len(getattr(foot, "geoms", [foot])),
                         "base_z": base, "top_z": gtop, "objects": len(env_objs)},
            "layers": layers, "flags": list(flags.values()), "objects": out_objs, "dropped": dropped,
            "unclassified": unclassified}


def census_markdown(census: dict, rules: dict) -> str:
    lines = ["# Шаг 0 — предлагаемая раскладка исходника по слоям [D390]", "",
             f"Источник: `{census.get('source')}` (sha256 `{str(census.get('source_sha256'))[:12]}…`), "
             f"правила `{Path(str(census.get('rules'))).name}` (sha256 `{str(census.get('rules_sha256'))[:12]}…`).",
             f"Объектов: {len(census['objects'])}, без геометрии (в списке сброса): {len(census['dropped'])}. "
             f"Неклассифицировано: {len(census['unclassified'])}.",
             "Статус: ПРЕДЛОЖЕНИЕ. Артём правит раскладку в 3ds Max и сохраняет `<job>_split_ACCEPTED`; "
             "дальнейшие этапы читают только принятые слои.", "",
             "| Слой Max | Слой | Объектов | Семейств | Треуг. | bbox (м) | Семейства (шт.) |", "|---|---|---:|---:|---:|---|---|"]
    for la in census["layers"]:
        fams = "; ".join(f"{f['family']} ({f['count']})" for f in la["families"][:12])
        if len(la["families"]) > 12:
            fams += f"; … ещё {len(la['families']) - 12}"
        bb = "—" if not la["bbox"] else " ".join(f"{v:g}" for v in la["bbox"])
        lines.append(f"| {la['max_layer']} | {la['ru']} | {la['count']} | {len(la['families'])} | {la['tris']} | {bb} | {fams} |")
    if census.get("flags"):
        ru = {la["id"]: la["max_layer"] for la in census["layers"]}
        lines += ["", "## Отмечено на листе (решение по умолчанию, Артём может переложить в Max)", "",
                  "| Метка | Что | Объектов | Куда легли |", "|---|---|---:|---|"]
        for k, f in enumerate(census["flags"], 1):
            lay = ", ".join(f"{ru[l]} {n}" for l, n in sorted(f["layers"].items(), key=lambda t: -t[1])) or "—"
            lines.append(f"| {k} | {f['ru']} | {f['count']} | {lay} |")
    if census["unclassified"]:
        lines += ["", "## 00_РЕШИТЬ_ЧЕЛОВЕКУ", ""]
        lines += [f"- `{u['name']}` ({u['family']})" for u in census["unclassified"]]
    if census["dropped"]:
        lines += ["", "## Сброшено (с причиной)", ""] + [f"- `{d['name']}`: {d['reason']}" for d in census["dropped"]]
    return "\n".join(lines) + "\n"


def compare_census(census: dict, other: dict) -> list:
    """Family-by-family comparison with a `revit-census/1` (v007): counts and where each family landed."""
    by_fam = {}
    for o in census["objects"]:
        by_fam.setdefault(o["family"], {}).setdefault(o["layer"], 0)
        by_fam[o["family"]][o["layer"]] += 1
    rows = []
    for f in other.get("families", []):
        layers = by_fam.get(f["family"], {})
        rows.append({"family": f["family"], "v007_count": f["count"], "v007_place": f.get("place"),
                     "count": sum(layers.values()), "count_match": sum(layers.values()) == f["count"], "layers": layers})
    known = {f["family"] for f in other.get("families", [])}
    for fam, layers in sorted(by_fam.items()):
        if fam not in known:
            rows.append({"family": fam, "v007_count": 0, "v007_place": None, "count": sum(layers.values()),
                         "count_match": False, "layers": layers})
    return rows


def compare_markdown(rows, rules) -> str:
    ru = {la["id"]: la["max_layer"] for la in rules["layers"]}
    out = ["| Семейство Revit | v007 шт. | v007 внутри/фасад/кровля/вне | шаг 0 шт. | слои шага 0 |", "|---|---:|---|---:|---|"]
    for r in rows:
        p = r["v007_place"] or {}
        pl = "/".join(str(p.get(k, 0)) for k in PLACES) if p else "—"
        lay = ", ".join(f"{ru[k]} {v}" for k, v in sorted(r["layers"].items(), key=lambda t: -t[1])) or "—"
        out.append(f"| {r['family']} | {r['v007_count']} | {pl} | {r['count']} | {lay} |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- sheet

def _font(size, bold=False):
    from PIL import ImageFont
    for f in (("arialbd.ttf" if bold else "arial.ttf"), "segoeui.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _plan_image(census, size, only=None, box=None, highlight=None):
    """Plan view of object bboxes coloured by layer (fallback when there are no Blender renders); with `highlight`
    (a flag key) the other objects are light grey and the flagged ones keep their layer colour with a red outline."""
    from PIL import Image, ImageDraw
    col = {la["id"]: tuple(la["color"]) for la in census["layers"]}
    objs = [o for o in census["objects"] if only is None or o["layer"] in only]
    hot = highlight is not None
    if hot and box is None:  # crop to the flagged objects + 10 m of context
        mine_bb = [o["bbox"] for o in objs if o.get("flag") == highlight] or [o["bbox"] for o in objs]
        box = [min(b[0] for b in mine_bb) - 10, min(b[1] for b in mine_bb) - 10,
               max(b[3] for b in mine_bb) + 10, max(b[4] for b in mine_bb) + 10]
    if box is None:
        box = [min(o["bbox"][0] for o in objs), min(o["bbox"][1] for o in objs),
               max(o["bbox"][3] for o in objs), max(o["bbox"][4] for o in objs)]
    w, h = size
    s = min((w - 20) / max(box[2] - box[0], 1e-6), (h - 20) / max(box[3] - box[1], 1e-6))
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    for o in sorted(objs, key=lambda o: (hot and o.get("flag") == highlight, o["bbox"][5])):
        b = o["bbox"]
        x0, x1 = 10 + (b[0] - box[0]) * s, 10 + (b[3] - box[0]) * s
        y0, y1 = h - 10 - (b[4] - box[1]) * s, h - 10 - (b[1] - box[1]) * s
        mine = hot and o.get("flag") == highlight
        rect = [x0, y0, max(x1, x0 + 1), max(y1, y0 + 1)]
        if hot and not mine:  # context: thin grey outline only, so a large slab cannot hide the flagged objects
            d.rectangle(rect, outline=(200, 200, 200))
        else:
            d.rectangle(rect, fill=col[o["layer"]], outline=(230, 0, 0) if mine else None, width=1)
    return img


def closeup_layers(census, n=4):
    """The n smallest non-empty layers (by count) other than INTERIOR_OUT - the ones a reviewer would miss."""
    cand = [la for la in census["layers"] if la["count"] and la["id"] not in ("INTERIOR_OUT",)]
    return [la["id"] for la in sorted(cand, key=lambda la: (la["count"], la["id"]))[:n]]


def make_sheet(census, out_png, renders=None, title=""):
    from PIL import Image, ImageDraw
    renders = renders or {}
    flags = [f for f in census.get("flags", []) if f["count"]]
    W, H = 2400, 1500 + (560 if flags else 0)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((30, 20), title or "Шаг 0: раскладка исходника по слоям — ПРЕДЛОЖЕНИЕ для приёмки", fill=(0, 0, 0), font=_font(34, True))
    d.text((30, 66), f"{Path(str(census.get('source'))).name}  sha256 {str(census.get('source_sha256'))[:12]}…  объектов "
                     f"{len(census['objects'])}, решить человеку: {len(census['unclassified'])}, без геометрии: "
                     f"{len(census['dropped'])}  [D390]", fill=(60, 60, 60), font=_font(22))
    main = renders.get("overview")
    img = Image.open(main).convert("RGB") if main and Path(main).is_file() else _plan_image(census, (1500, 940))
    img.thumbnail((1500, 940))
    sheet.paste(img, (30, 110))
    y = 120
    d.text((1560, y - 10), "Слои (цвет | слой Max | объектов | семейств)", fill=(0, 0, 0), font=_font(24, True))
    y += 30
    for la in census["layers"]:
        d.rectangle([1560, y + 4, 1600, y + 34], fill=tuple(la["color"]), outline=(0, 0, 0))
        d.text((1612, y), f"{la['max_layer']}  {la['count']} / {len(la['families'])}", fill=(0, 0, 0), font=_font(24, True))
        d.text((1612, y + 30), la["ru"], fill=(70, 70, 70), font=_font(18))
        y += 82
    ids = closeup_layers(census)
    cw = (W - 60 - 20 * (len(ids) - 1)) // max(len(ids), 1) if ids else 0
    names = {la["id"]: la for la in census["layers"]}
    for k, lid in enumerate(ids):
        x = 30 + k * (cw + 20)
        p = renders.get(lid)
        im = Image.open(p).convert("RGB") if p and Path(p).is_file() else _plan_image(census, (cw, 380), only={lid})
        im.thumbnail((cw, 380))
        sheet.paste(im, (x, 1090))
        d.rectangle([x, 1060, x + 30, 1084], fill=tuple(names[lid]["color"]), outline=(0, 0, 0))
        d.text((x + 40, 1058), f"Крупно: {names[lid]['max_layer']} ({names[lid]['count']})", fill=(0, 0, 0), font=_font(22, True))
    if flags:
        d.text((30, 1490), "Отмечено на проверку (решение по умолчанию; в плане красная обводка, остальное серым):",
               fill=(200, 0, 0), font=_font(26, True))
        fw = (W - 60 - 20 * (len(flags) - 1)) // len(flags)
        for k, f in enumerate(flags):
            x = 30 + k * (fw + 20)
            lay = ", ".join(f"{names[l]['max_layer']} {n}" for l, n in sorted(f["layers"].items(), key=lambda t: -t[1]))
            d.text((x, 1530), f"{k + 1}. {f['count']} шт.: {lay}", fill=(0, 0, 0), font=_font(20, True))
            words, line, ty = f["ru"].split(), "", 1558
            for wd in words:  # wrap the Russian label to the panel width
                if d.textlength(line + " " + wd, font=_font(18)) > fw and line:
                    d.text((x, ty), line, fill=(70, 70, 70), font=_font(18))
                    line, ty = wd, ty + 22
                else:
                    line = (line + " " + wd).strip()
            d.text((x, ty), line, fill=(70, 70, 70), font=_font(18))
            im = _plan_image(census, (fw, 360), highlight=f["key"])
            sheet.paste(im, (x, 1630))
            d.rectangle([x, 1630, x + fw - 1, 1989], outline=(200, 0, 0), width=2)
    sheet.save(out_png)
    return out_png


# ---------------------------------------------------------------- CLI

def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _blender(script, args, exe):
    from dt_ai.core.blender_runner import blender_command
    exe = exe or os.environ.get("AGR_SCENE_BLENDER") or REVIT_BLENDER
    r = subprocess.run(blender_command(script, args, executable=exe), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise ScenePrepareError(f"Blender {Path(script).name} failed ({r.returncode}): {(r.stdout + r.stderr)[-1500:]}")
    return r


def prepare(src, out, rules_path=None, dump_path=None, blender=None, no_blend=False, compare=None) -> int:
    src, out = Path(src).resolve(), Path(out).resolve()
    if not src.is_file():
        raise ScenePrepareError(f"source not found: {src}")
    partial = Path(str(out) + ".partial")
    if out == src or src.is_relative_to(out) or out.exists() or partial.exists():
        raise ScenePrepareError(f"--out must be a new directory (exists or is/contains the source): {out}")
    rules = load_rules(rules_path or DEFAULT_RULES)
    sha0 = _sha(src)
    dump = None
    if dump_path:
        dump = json.loads(Path(dump_path).read_text(encoding="utf-8"))
        if dump.get("sha256") != sha0:
            raise ScenePrepareError(f"dump sha256 {dump.get('sha256')} is not the source sha256 {sha0}")
        classify(dump, rules)  # validate before creating anything
    partial.mkdir(parents=True)
    try:
        if dump_path:
            shutil.copyfile(dump_path, partial / "dump.json")
        else:
            _blender(DUMP_SCRIPT, [src, partial / "dump.json"], blender)
            dump = json.loads((partial / "dump.json").read_text(encoding="utf-8"))
        census = classify(dump, rules)
        renders = {}
        if not no_blend:
            assign = {"layers": [{k: la[k] for k in ("id", "max_layer", "color")} for la in rules["layers"]],
                      "objects": {o["name"]: o["layer"] for o in census["objects"]},
                      "closeups": closeup_layers(census)}
            (partial / "assign.json").write_text(json.dumps(assign, ensure_ascii=False), encoding="utf-8")
            _blender(BLENDER_SCRIPT, [src, partial / "assign.json", partial], blender)
            rep = json.loads((partial / "blend_report.json").read_text(encoding="utf-8"))
            if rep["missing"] or rep["unassigned"]:
                raise ScenePrepareError(f"blend mismatch: missing {rep['missing'][:5]} unassigned {rep['unassigned'][:5]}")
            renders = {k: str(partial / v) for k, v in rep.get("renders", {}).items()}
            census["blend"] = {"collections": rep["collections"], "nonmesh": rep.get("nonmesh", 0)}
        if _sha(src) != sha0:
            raise ScenePrepareError("source changed during the run")
        (partial / "census.json").write_text(json.dumps(census, ensure_ascii=False, indent=1), encoding="utf-8")
        md = census_markdown(census, rules)
        if compare:
            rows = compare_census(census, json.loads(Path(compare).read_text(encoding="utf-8")))
            (partial / "compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
            md += "\n## Сравнение с census_v007 (семейство за семейством)\n\n" + compare_markdown(rows, rules)
        (partial / "census.md").write_text(md, encoding="utf-8")
        make_sheet(census, partial / "sheet.png", renders)
    except BaseException:
        print(f"ERROR: run failed; partial output kept for inspection: {partial}", file=sys.stderr)
        raise
    os.replace(partial, out)
    n = len(census["unclassified"])
    print(f"SCENE_PREPARE {'OK' if n == 0 else 'DECIDE'} objects={len(census['objects'])} unclassified={n} "
          f"dropped={len(census['dropped'])} out={out}")
    for la in census["layers"]:
        print(f"  {la['max_layer']:28} {la['count']:6d}")
    return 0 if n == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agr scene", description="Step 0: split a customer Revit FBX into logical layers [D390]")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="propose the layer split: census.json/md, sheet.png, scene_layers.blend, split_PROPOSED.fbx")
    p.add_argument("source")
    p.add_argument("--out", required=True)
    p.add_argument("--rules")
    p.add_argument("--dump", help="existing revit-fbx-dump/1 of the same source (sha256 checked)")
    p.add_argument("--blender")
    p.add_argument("--no-blend", action="store_true", help="census + plan sheet only, no .blend/FBX/renders")
    p.add_argument("--compare", help="a revit-census/1 (e.g. census_v007.json) to compare family by family")
    a = ap.parse_args(argv)
    try:
        return prepare(a.source, a.out, a.rules, a.dump, a.blender, a.no_blend, a.compare)
    except (ScenePrepareError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
