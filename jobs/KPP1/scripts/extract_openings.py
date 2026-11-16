"""Derive the exterior openings spec of KPP1 from the Revit export (sidecars + object dumps).

Usage: py -3 extract_openings.py <source_dir> <census_dir>
  -> <census_dir>/openings_spec.json      (per facade: surrounds/bays, doors, portals, features, grilles)
  -> <census_dir>/openings_dropped.json   (every dumped object not in the spec, with its reason)

Facade frames (u along the facade, z up, d = depth inward from the outer cassette plane):
  S: y = -0.33, u = x     N: y = 11.33, u = x     W: x = -0.33, u = y     E: x = 27.33, u = y
Rects are [u0, u1, z0, z1] in metres (Revit internal coordinates).

Family names are compared after `norm` (casefold + Latin->Cyrillic homoglyphs), so "Cтеклопакет" with a
Latin C and "Стеклопакет" with a Cyrillic С are the same family (#1336). An object inside a curtain bay
whose family is not a window, glass or mullion is reported in openings_dropped.json, never skipped silently.
"""
import json, os, re, sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'adapters/max/agr_tools'))
from windowgen_core import assign_glass

FT = 0.3048
FEATURE_IDS = {1832606}  # north vertical fin feature: listed under "features", modeled with decor (stage 4)
# Latin letters that look like Cyrillic ones (after casefold); both sides of every name match go through it.
HOMOGLYPHS = str.maketrans("abcehkmoptxy", "авсенкмортху")


def norm(s):
    return s.casefold().translate(HOMOGLYPHS)


WINDOW, GLASS, MULLION = norm("MEP_Окно"), norm("Стеклопак"), norm("Прямоугольный импост 200х75")
DOOR, GRILLE = norm("ADSK_Дверь_"), norm("MEP_Веза_Р50")


def facade_of(lo, hi):
    if hi[1] < 0.6 and lo[1] < 0: return "S"
    if lo[1] > 10.4: return "N"
    if hi[0] < 0.6 and lo[0] < 0: return "W"
    if lo[0] > 26.4: return "E"
    return None


def rect(lo, hi, f):
    a = 1 if f in "WE" else 0
    return [round(lo[a], 3), round(hi[a], 3), round(lo[2], 3), round(hi[2], 3)]  # 1 mm: drops 0.1 mm Revit noise


def inside(r, R, tol=0.012):
    return r[0] >= R[0] - tol and r[1] <= R[1] + tol and r[2] >= R[2] - tol and r[3] <= R[3] + tol


def extract(src, cen):
    side = json.load(open(os.path.join(src, "curtain.export.json"), encoding="utf-8-sig"))
    inst = [i for t in side["types"] for i in t["instances"] if i.get("boundingBox")]
    bb = lambda i: ([i["boundingBox"]["min"][k] * FT for k in "xyz"], [i["boundingBox"]["max"][k] * FT for k in "xyz"])
    objs = []
    for g in ("curtain", "openings"):
        for o in json.load(open(os.path.join(cen, g + ".objects.json"), encoding="utf-8")):
            o["kind"] = re.sub(r"(_[0-9a-f]{7}(\.\d+)?| \[\d+\])$", "", o["name"])
            o["key"], o["group"] = norm(o["kind"]), g
            objs.append(o)

    identities = [(o['group'], o['name']) for o in objs]
    if len(set(identities)) != len(identities):
        raise ValueError('duplicate object identity in curtain/openings inventory')
    spec = {f: {"surrounds": [], "doors": [], "portals": [], "features": [], "grilles": []} for f in "SNWE"}
    used, why = set(), {}  # object index -> used in the spec / reason it is not (first reason kept)
    hosts = [i for i in inst if i["type"].startswith("ADSK_Витраж")]
    bounds = []
    for h in hosts:
        lo, hi = bb(h)
        if facade_of(lo, hi) is not None:
            bounds.append({'id': str(h['elementId']), 'min': lo, 'max': hi})
    candidates = [{'id': str(k), 'min': o['min'], 'max': o['max']} for k, o in enumerate(objs)
                  if facade_of(o['min'], o['max']) is not None
                  and (o['key'].startswith(WINDOW) or GLASS in o['key'])]
    ownership = assign_glass(bounds, candidates) if candidates else {
        'status': 'fail', 'assigned': {}, 'drops': [], 'drop_counts': {}, 'input_count': 0,
        'why': 'no exterior window/glass candidates'}
    for d in ownership['drops']:
        why[int(d['id'])] = d['reason'] + ': ' + ', '.join(d['candidates'])
    for s in inst:
        lo, hi = bb(s)
        f = facade_of(lo, hi)
        if f is None:
            continue
        R = rect(lo, hi, f)
        if s["type"].startswith("ADSK_Обрамление порталов"):
            spec[f]["portals"].append({"id": s["elementId"], "rect": R})
        elif s["type"].startswith("ADSK_Обрамление витражей"):
            mine = [k for k, o in enumerate(objs)
                    if facade_of(o["min"], o["max"]) == f and inside(rect(o["min"], o["max"], f), R)]
            bays = []
            for h in hosts:
                hl, hh = bb(h)
                if facade_of(hl, hh) != f or not inside(rect(hl, hh, f), R):
                    continue
                B = rect(hl, hh, f)
                bay = {"id": h["elementId"], "rect": B, "windows": [], "glass": []}
                for k in mine:
                    o = objs[k]
                    if not inside(rect(o["min"], o["max"], f), B):
                        continue
                    if o['key'].startswith(WINDOW) or GLASS in o['key']:
                        if k in used or ownership['assigned'].get(str(k)) != str(h['elementId']):
                            continue
                    if o["key"].startswith(WINDOW):
                        bay["windows"].append(rect(o["min"], o["max"], f)); used.add(k)
                    elif GLASS in o["key"]:
                        bay["glass"].append(rect(o["min"], o["max"], f)); used.add(k)
                    elif not o["key"].startswith(MULLION):
                        why.setdefault(k, f"unknown family in bay {h['elementId']} of surround {s['elementId']}")
                bays.append(bay)
            mull = [k for k in mine if objs[k]["key"].startswith(MULLION)]
            used.update(mull)
            for k in mine:
                why.setdefault(k, f"in surround {s['elementId']}, outside every bay, not a mullion")
            spec[f]["features" if s["elementId"] in FEATURE_IDS else "surrounds"].append({
                "id": s["elementId"], "rect": R, "bays": bays,
                "mullions": [rect(objs[k]["min"], objs[k]["max"], f) for k in mull]})

    for k, o in enumerate(objs):
        f = facade_of(o["min"], o["max"])
        if o["key"].startswith(GRILLE) and f is not None:  # vent grilles: ~1 cm proud of the cassettes -> finish only
            spec[f]["grilles"].append(rect(o["min"], o["max"], f)); used.add(k)
        elif o["key"].startswith(DOOR) and f is not None:
            r = rect(o["min"], o["max"], f)
            spec[f]["doors"].append({"name": o["kind"], "rect": [r[0], r[1], r[2], round(r[2] + 2.1, 3)],
                                     "double": norm("Двупольная") in o["key"]})
            used.add(k)
        elif f is None:
            why.setdefault(k, "on no exterior facade")
        else:
            why.setdefault(k, f"facade {f}: in no curtain surround, not a door or grille")

    dropped = [{"id": str(k), "name": objs[k]["name"], "group": objs[k]["group"], "reason": why[k]}
               for k in range(len(objs)) if k not in used]
    ownership['represented_objects'] = [{'id': str(k), 'name': objs[k]['name'], 'group': objs[k]['group']}
                                        for k in sorted(used)]
    ownership['total_objects'] = len(objs)
    return spec, dropped, ownership


def main(src, cen):
    spec, dropped, ownership = extract(src, cen)
    json.dump(spec, open(os.path.join(cen, "openings_spec.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(dropped, open(os.path.join(cen, "openings_dropped.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for f, v in spec.items():
        print(f, {k: len(x) for k, x in v.items()},
              "bays", sum(len(s["bays"]) for s in v["surrounds"]),
              "windows", sum(len(b["windows"]) for s in v["surrounds"] for b in s["bays"]),
              "glass", sum(len(b["glass"]) for s in v["surrounds"] for b in s["bays"]))
    unknown = sum(d["reason"].startswith("unknown family") for d in dropped)
    print("dropped", len(dropped), "objects; unknown families in bays:", unknown,
          "ownership:", ownership['status'])


if __name__ == "__main__":
    main(*sys.argv[1:3])
