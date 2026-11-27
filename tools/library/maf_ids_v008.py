"""MAF material ID list v008 = v007 + IDs 34-39 of the Staropetrovskiy job [D423].

New-case: `tools/library/maf_ids_version.py` takes one `add` with a spec-row move and a merge undo (v006/v007);
v008 adds six IDs and neither moves rows nor undoes a merge. Reuses the tool's hashing, flat-tile regex and refusal
rules without changing the older release pipeline.

Usage:
  uv run python -m tools.library.maf_ids_v008 --change library/maf/material_ids_v008_change.json \
      --prev-md library/maf/material_ids_v007.md --tiles-in <v007 evidence dir> --tiles-out <new dir> \
      --out-json library/maf/material_ids_v008.json --out-md library/maf/material_ids_v008.md
Input validation errors exit 2 before writing outputs.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
from pathlib import Path

from .maf_ids_version import ChangeError, FLAT_RE, sha256_file


def relocate_evidence(document: dict, markdown: str, sources: dict[str, str]) -> str:
    """Move inherited evidence pointers in the new snapshot, never in v007."""
    def records(value):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str):
                yield value
            for child in value.values():
                yield from records(child)
        elif isinstance(value, list):
            for child in value:
                yield from records(child)

    paths = list(records(document))
    used = set()
    replacements = {}
    for row in paths:
        digest = row.get("sha256")
        if digest in sources:
            if replacements.setdefault(row["path"], digest) != digest:
                raise ChangeError(f"inconsistent recorded SHA256 for {row['path']}")
            used.add(digest)
    if used != sources.keys():
        raise ChangeError("inherited evidence map contains a hash absent from the prior list")
    for digest, path in sources.items():
        if sha256_file(path) != digest:
            raise ChangeError(f"inherited evidence {path} does not match its recorded SHA256")
    for row in paths:
        old = row["path"]
        if old in replacements:
            if "sha256" in row and row["sha256"] != replacements[old]:
                raise ChangeError(f"inconsistent recorded SHA256 for {old}")
            row["path"] = sources[replacements[old]]
    for old, digest in replacements.items():
        markdown = markdown.replace(f"`{old}`", f"`{sources[digest]}`")
    return markdown


def reference_prior_missing_maps(document: dict) -> None:
    """Keep unresolved FBX paths as historical evidence in v007 only."""
    for row in document["inventory"]["missing"]:
        if re.match(r"(?i)^c:[/\\]+x[/\\]+", row.get("referenced_path", "")):
            row["referenced_path"] = "Unresolved historical reference; see material_ids_v007.json"


def apply_change(prev: dict, change: dict) -> dict:
    """Return the new ID list. Pure: ``prev`` is not modified."""
    new = copy.deepcopy(prev)
    ids = new["ids"]
    for add in change["adds"]:
        if any(e["id"] == add["id"] or e["key"] == add["key"] for e in ids):
            raise ChangeError(f"id {add['id']} or key {add['key']!r} already taken")
        nxt = max(e["id"] for e in ids) + 1
        if add["id"] != nxt:
            raise ChangeError(f"id {add['id']} is not the next free id {nxt}")
        if add["spec_rows"]:
            raise ChangeError("v008 adds carry no spec rows")
        entry = {k: add[k] for k in ("id", "key", "name_ru", "kind", "ral", "target")}
        entry.update({"cells": [], "library_materials": [], "spec_rows": [], "size": add["size"],
                      "atlas": add["atlas"], "review": list(add["review"]), "prev_id": None, "picked_patch": None,
                      "status": add["status"]})
        ids.append(entry)
    new["version"] = change["version"]
    new["approval"] = dict(change["approval"], decision=change["decision"], previous=prev["approval"])
    new["changelog"] = list(prev.get("changelog", [])) + [change["changelog"]]
    new["derived_from"] = {"path": change["from"], "version": prev["version"]}
    new["generated_by"] = "tools/library/maf_ids_v008.py"
    return new


def render_md(prev_md: str, prev: dict, change: dict) -> str:
    out, done = [], set()
    last_id = max(e["id"] for e in prev["ids"])
    lines = prev_md.splitlines()
    last_log = max(i for i, line in enumerate(lines) if line.startswith("Changelog: "))
    for i, line in enumerate(lines):
        if line.startswith(f"# MAF material IDs {prev['version']}") and "title" not in done:
            head, _, tail = line.replace(prev["version"], change["version"], 1).rpartition(")")
            line = f"{head}, {change['md_ref']}){tail}"
            done.add("title")
        out.append(line)
        if i == last_log:
            out.append(f"Changelog: {change['changelog']}")
            done.add("log")
        if line.startswith(f"| {last_id} | ") and "rows" not in done:
            for a in change["adds"]:
                target = (f"RAL {a['ral']} " if a["ral"] else "") + a["target"]
                note = " (review: " + "; ".join(a["review"]) + ")" if a["review"] else ""
                out.append(f"| {a['id']} | - | `{a['key']}` | {a['name_ru']} | {a['kind'] or '-'} | {a['size']} | "
                           f"{target} | - | 0 | - | {a['status']}{note} |")
            done.add("rows")
    missing = {"title", "log", "rows"} - done
    if missing:
        raise ChangeError(f"md anchors not found: {sorted(missing)}")
    return "\n".join(out) + "\n"


def write_tiles(change: dict, tiles_in: str, tiles_out: str, prev: dict) -> list:
    from PIL import Image
    for a in change["adds"]:  # validated before anything is written
        tile = a["tile"]
        flat = FLAT_RE.search(tile["source"])
        if not flat or flat.group(1) != tile["flat"] or tile["flat"] != a["target"]:
            raise ChangeError(f"id {a['id']}: tile source must state (flat {a['target']})")
    for t in prev["evidence"]["tiles"]:
        src = os.path.join(tiles_in, t["file"])
        if not (os.path.exists(src) and sha256_file(src) == t["sha256"]):
            raise ChangeError(f"stale or missing tile {src}")
    os.makedirs(os.path.join(tiles_out, "tiles"), exist_ok=False)
    for t in prev["evidence"]["tiles"]:
        shutil.copyfile(os.path.join(tiles_in, t["file"]), os.path.join(tiles_out, t["file"]))
    rows = []
    for a in change["adds"]:
        tile = a["tile"]
        h = tile["flat"].lstrip("#")
        path = os.path.join(tiles_out, tile["file"])
        Image.new("RGB", (tile["px"], tile["px"]), tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))).save(path)
        rows.append({"id": a["id"], "key": a["key"], "file": tile["file"], "sha256": sha256_file(path),
                     "source": tile["source"]})
    return rows


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
        for name, s in change["job_sources"].items():
            if sha256_file(s["path"]) != s["sha256"]:
                raise ChangeError(f"job source {name} {s['path']} does not match its recorded SHA256")
        prev = json.loads(Path(change["from"]).read_text(encoding="utf-8"))
        new = apply_change(prev, change)
        reference_prior_missing_maps(new)
        md = render_md(Path(args.prev_md).read_text(encoding="utf-8"), prev, change)
        md = relocate_evidence(new, md, change["inherited_evidence"])
        new["inputs"] = dict(new.get("inputs", {}), previous={"path": change["from"],
                             "sha256": sha256_file(change["from"])},
                             change={"path": args.change, "sha256": sha256_file(args.change)},
                             job_sources=change["job_sources"])
        new["evidence"]["tiles"] += write_tiles(change, args.tiles_in, args.tiles_out, prev)
        new["evidence"]["tiles_dir"] = args.tiles_out.replace("\\", "/")
    except (ChangeError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    with open(args.out_json, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    with open(args.out_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    print(json.dumps({"version": new["version"], "ids": len(new["ids"]), "added": [a["id"] for a in change["adds"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
