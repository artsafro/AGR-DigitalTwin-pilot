"""new-case: offline DCC census from the frozen #1273 transcript inventory.

Reads installed source with AST/regex, never imports it or contacts a DCC.
Output must be a new directory; shell/headless calls are outside this MCP census.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics

ROUTES = {"3dsmax-mcp": "max", "max-ultra-mcp": "max", "blender": "blender",
          "revit-http-2025": "revit"}
POLLS = {"max": {"list_max_instances", "max_list_instances", "get_selected_max_instance", "max_dialogs"},
         "blender": {"get_blendfile_summary_path_info"},
         "revit": {"revit_ping", "revit_get_version", "revit_get_document_info"}}


def calls_from(text):
    """Deduplicate retransmitted tool ids, retaining first appearance order."""
    calls, ids = [], set()
    for line in text.splitlines():
        event = json.loads(line)
        blocks = (event.get("message") or {}).get("content")
        if event.get("type") != "assistant" or not isinstance(blocks, list):
            continue
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b["id"] not in ids:
                ids.add(b["id"])
                calls.append((b["name"], b.get("input") or {}))
    return calls


def context_refs(text):
    """Union of explicitly loaded ToolSearch references, not resident/token counts."""
    refs = {k: set() for k in ("max", "blender", "revit")}
    def walk(value):
        if isinstance(value, dict):
            if value.get("type") == "tool_reference":
                parts = value.get("tool_name", "").split("__", 2)
                if len(parts) == 3 and parts[0] == "mcp" and parts[1] in ROUTES:
                    refs[ROUTES[parts[1]]].add(parts[2])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    for line in text.splitlines():
        walk(json.loads(line))
    return {k: sorted(v) for k, v in refs.items()}


def measure(calls):
    output = {}
    for dcc in ("max", "blender", "revit"):
        row = dict(calls=0, polls=0, exact_repeats=0, repeated_polls=0)
        seen, names = set(), set()
        for name, args in calls:
            parts = name.split("__", 2)
            if len(parts) != 3 or parts[0] != "mcp" or ROUTES.get(parts[1]) != dcc:
                continue
            tool = parts[2]
            key = name + json.dumps(args, sort_keys=True, allow_nan=False)
            poll = tool in POLLS[dcc] and not (tool == "max_dialogs" and args.get("action", "inspect") != "inspect")
            repeated = key in seen
            row["calls"] += 1
            row["polls"] += poll
            row["exact_repeats"] += repeated
            row["repeated_polls"] += poll and repeated
            seen.add(key)
            names.add(tool)
        row["tools_observed"] = sorted(names)
        output[dcc] = row
    return output


def static_tools(paths):
    """Static decorated tool names; conditional registration remains unmeasured."""
    names = []
    for path in paths:
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
                for d in n.decorator_list
            ):
                names.append(n.name)
    return sorted(names)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--root", type=Path, default=Path.home() / ".claude/projects")
    p.add_argument("--inventory", type=Path, default=Path("docs/research/agent-step-waste-1273/data/sessions.csv"))
    args = p.parse_args()
    if args.out.exists():
        p.error("output must be a new directory; no input/output/report aliases")
    with args.inventory.open(encoding="utf-8", newline="") as f:
        inventory = list(csv.DictReader(f))
    if not inventory:
        p.error("empty inventory")
    sources = []
    for entry in inventory:
        path = args.root / entry["source"]
        if any(path.samefile(previous) for previous in sources):
            p.error("duplicate transcript: " + entry["source"])
        sources.append(path)
    rows = []
    for entry, path in zip(inventory, sources):
        data = path.read_bytes()
        rows.append(dict(source=entry["source"], title=entry["title"],
                         sha256=hashlib.sha256(data).hexdigest(), dcc=measure(calls_from(data.decode("utf-8"))),
                         loaded_tool_refs=context_refs(data.decode("utf-8"))))
    totals = {}
    for dcc in ("max", "blender", "revit"):
        active = [r["dcc"][dcc] for r in rows if r["dcc"][dcc]["calls"]]
        totals[dcc] = dict(sessions=len(active),
            **{k: sum(r[k] for r in active) for k in ("calls", "polls", "exact_repeats", "repeated_polls")},
            median_calls_active_session=statistics.median(r["calls"] for r in active) if active else None,
            tools_observed=sorted({t for r in active for t in r["tools_observed"]}))
    catalogs = {}
    for dcc, root in [
        ("max", Path.home() / "tools/3dsmax-mcp/maxmcp/tools"),
        ("blender", Path.home() / "AppData/Local/CodexMCP/BlenderLab103/venv/Lib/site-packages/blmcp/tools")]:
        paths = sorted(root.glob("*.py"))
        if not paths:
            raise FileNotFoundError(root)
        catalogs[dcc] = dict(path=str(root), tools=static_tools(paths),
            file_hashes={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in paths})
    path = Path.home() / "INTERACTIVE_TOUR/RevitMCPServer/dist/index.js"
    data = path.read_bytes()
    catalogs["revit"] = dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(),
        tools=sorted(set(re.findall(r'server\.tool\(\s*[\"\x27]([^\"\x27]+)', data.decode("utf-8")))))
    result = dict(inventory_sessions=len(rows), rows=rows, totals=totals, static_catalogs=catalogs)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "measurements.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(totals, indent=2))
    print("static catalog counts:", {k: len(v["tools"]) for k, v in catalogs.items()})


if __name__ == "__main__":
    main()
