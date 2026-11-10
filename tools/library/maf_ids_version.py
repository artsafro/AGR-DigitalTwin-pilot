"""Derive the next MAF material ID list version from the previous one plus one reviewed change file.

new-case: versioned edit of an approved ID list (D181: each change is a new version with a changelog line).
v006 = v005 + ID 32 `wood_hpl_satin` (D229, #993); v007 = v006 + ID 33 `wood_pine` (D240, plan
step 2.3). The previous list, its Markdown twin and its tiles are read-only inputs; outputs refuse to overwrite. The new
tile is a flat swatch of the stated colour, or a Lanczos crop of a hash-checked source image (`tile.crop`).

Usage:
  python tools/library/maf_ids_version.py --change library/maf/material_ids_v006_change.json \
      --prev-md library/maf/material_ids_v005.md --tiles-in <v005 tiles dir parent> --tiles-out <new dir> \
      --out-json library/maf/material_ids_v006.json --out-md library/maf/material_ids_v006.md
Exit 2 and nothing written on any inconsistency (ID or key taken, id not next free, row missing).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path


FLAT_RE = re.compile(r"\(flat (#[0-9A-Fa-f]{6})\)")


class ChangeError(Exception):
    pass


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def apply_change(prev: dict, change: dict) -> dict:
    """Return the new ID list. Pure: ``prev`` is not modified."""
    new = copy.deepcopy(prev)
    add = change["add"]
    ids = new["ids"]
    if any(e["id"] == add["id"] for e in ids) or any(e["key"] == add["key"] for e in ids):
        raise ChangeError(f"id {add['id']} or key {add['key']!r} already in {prev['version']}")
    nxt = max(e["id"] for e in ids) + 1
    if add["id"] != nxt:
        raise ChangeError(f"id {add['id']} is not the next free id {nxt}")
    move = change["move_spec_rows"]
    src = next((e for e in ids if e["id"] == move["from_id"]), None)
    if src is None:
        raise ChangeError(f"id {move['from_id']} missing")
    for row in move["rows"]:
        if row not in src["spec_rows"]:
            raise ChangeError(f"{row} is not a spec row of id {move['from_id']}")
    src["spec_rows"] = [r for r in src["spec_rows"] if r not in move["rows"]]
    undo = change["undo_merge_from_key"]
    src["review"] = [r for r in src.get("review", []) if "HPL" not in r]
    src["name_ru"] = change["id14_name_ru"]
    entry = {k: add[k] for k in ("id", "key", "name_ru", "kind", "ral", "target")}
    entry.update({"cells": [], "library_materials": [], "spec_rows": list(add["spec_rows"]), "size": add["size"],
                  "atlas": add["atlas"], "review": [], "prev_id": None, "picked_patch": None,
                  "status": add["status"]})
    ids.append(entry)
    before = len(new["merges"])
    new["merges"] = [m for m in new["merges"] if m.get("from_key") != undo]
    if len(new["merges"]) != before - 1:
        raise ChangeError(f"merge from {undo!r} not found exactly once")
    rows = {f"{r['table']}#{r['row']}": r for r in new["spec_requirements"]}
    for row in add["spec_rows"]:
        if row not in rows:
            raise ChangeError(f"spec row {row} missing")
        r = rows[row]
        r["ids"] = sorted({i for i in r["ids"] if i != move["from_id"]} | {add["id"]})
    new["version"] = change["version"]
    new["approval"] = dict(change["approval"], decision=change["decision"], previous=prev["approval"])
    new["changelog"] = list(prev.get("changelog", [])) + [change["changelog"]]
    new["derived_from"] = {"path": change["from"], "version": prev["version"]}
    new["generated_by"] = "tools/library/maf_ids_version.py"
    return new


def render_md(prev_md: str, prev: dict, new: dict, change: dict) -> str:
    add = change["add"]
    old14 = next(e for e in prev["ids"] if e["id"] == change["move_spec_rows"]["from_id"])
    out, done = [], set()
    has_log = any(line.startswith("Changelog: ") for line in prev_md.splitlines())
    last_id = max(e["id"] for e in prev["ids"])
    for line in prev_md.splitlines():
        if line.startswith(f"# MAF material IDs {prev['version']}"):
            head, _, tail = line.replace(prev["version"], new["version"], 1).rpartition(")")
            line = f"{head}, {change.get('md_ref', '#993')}){tail}"
            out += [line] if has_log else [line, "", f"Changelog: {change['changelog']}", ""]
            done.add("title")
            continue
        if has_log and line.startswith("Changelog: ") and "log" not in done:
            out += [line, f"Changelog: {change['changelog']}"]
            done.add("log")
            continue
        if line.startswith(f"| {old14['id']} | ") and old14["name_ru"] in line and "row14" not in done:
            cols = line.split(" | ")
            n14 = next(e for e in new["ids"] if e["id"] == old14["id"])
            if cols[3] != old14["name_ru"] or cols[8] != str(len(old14["spec_rows"])):
                raise ChangeError("md row 14 columns differ from the JSON")
            cols[3], cols[8] = n14["name_ru"], str(len(n14["spec_rows"]))
            if not n14.get("review"):
                cols[10] = n14["status"] + " |"
            line = " | ".join(cols)
            done.add("row14")
        if line.startswith(f"| {change['undo_merge_from_key']}") or f"`{change['undo_merge_from_key']}` |" in line:
            done.add("merge")
            continue
        out.append(line)
        if line.startswith(f"| {last_id} | ") and "row32" not in done:
            out.append(f"| {add['id']} | - | `{add['key']}` | {add['name_ru']} | {add['kind']} | {add['size']} | "
                       f"{add['target']} | - | {len(add['spec_rows'])} | - | {add['status']} |")
            done.add("row32")
    missing = {"title", "row14", "merge", "row32"} | ({"log"} if has_log else set())
    missing -= done
    if missing:
        raise ChangeError(f"md anchors not found: {sorted(missing)}")
    return "\n".join(out) + "\n"


def write_tile(add: dict, tiles_in: str, tiles_out: str, prev: dict) -> dict:
    from PIL import Image
    os.makedirs(os.path.join(tiles_out, "tiles"), exist_ok=False)
    def rgb(hexs):
        h = hexs.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    targets = {e["key"]: e["target"] for e in prev["ids"]}
    for t in prev["evidence"]["tiles"]:
        src = os.path.join(tiles_in, t["file"])
        dst = os.path.join(tiles_out, t["file"])
        if os.path.exists(src) and sha256_file(src) == t["sha256"]:
            shutil.copyfile(src, dst)
        elif t.get("source", "").startswith("GAP: target colour") or FLAT_RE.search(t.get("source", "")):
            # A gap tile is a flat swatch of the target, a versioned flat tile one of its stated colour; the
            # recorded hash proves the regeneration.
            flat = FLAT_RE.search(t["source"])
            Image.new("RGB", (512, 512), rgb(flat.group(1) if flat else targets[t["key"]])).save(dst)
            if sha256_file(dst) != t["sha256"]:
                raise ChangeError(f"stale tile {src}; flat regeneration does not match the recorded SHA256")
        else:
            raise ChangeError(f"stale tile {src}")
    tile = add["tile"]
    path = os.path.join(tiles_out, tile["file"])
    if "crop" in tile:
        crop = tile["crop"]
        if sha256_file(crop["path"]) != crop["sha256"]:
            raise ChangeError(f"crop source {crop['path']} does not match its recorded SHA256")
        with Image.open(crop["path"]) as im:
            im.convert("RGB").crop(tuple(crop["box"])).resize((tile["px"], tile["px"]), Image.LANCZOS).save(path)
    else:
        Image.new("RGB", (tile["px"], tile["px"]), rgb(tile["flat"])).save(path)
    return {"id": add["id"], "key": add["key"], "file": tile["file"], "sha256": sha256_file(path),
            "source": tile["source"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for a in ("change", "prev-md", "tiles-in", "tiles-out", "out-json", "out-md"):
        ap.add_argument("--" + a, required=True)
    args = ap.parse_args(argv)
    try:
        for p in (args.out_json, args.out_md):
            if os.path.exists(p):
                raise ChangeError(f"refusing to overwrite {p}")
        change = json.loads(Path(args.change).read_text(encoding="utf-8"))
        prev = json.loads(Path(change["from"]).read_text(encoding="utf-8"))
        new = apply_change(prev, change)
        md = render_md(Path(args.prev_md).read_text(encoding="utf-8"), prev, new, change)
        new["inputs"] = dict(new.get("inputs", {}), previous={"path": change["from"],
                             "sha256": sha256_file(change["from"])},
                             change={"path": args.change, "sha256": sha256_file(args.change)})
        new["evidence"]["tiles"].append(write_tile(change["add"], args.tiles_in, args.tiles_out, prev))
    except (ChangeError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    with open(args.out_json, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    with open(args.out_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    print(json.dumps({"version": new["version"], "ids": len(new["ids"]), "added": change["add"]["id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
