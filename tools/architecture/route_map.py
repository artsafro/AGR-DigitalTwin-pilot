"""Excalidraw + SVG generator for the route event storms and the context maps (#1359; VPM OKS + Ground #1383;
VPM OKS / Ground context maps #1392; MAF, Flora and package/delivery routes + their context maps #1393).

Pattern: n/a | new-case: stdlib generator docs/architecture/*.yaml -> .excalidraw + .svg (Russian labels).

Inputs (source of truth): docs/architecture/contexts.yaml and one events YAML per route (ROUTE_EVENTS:
npm-oks-route, vpm-oks-route, ground-route, maf-route, flora-route, package-route .events.yaml). A route may declare `local_contexts` (id, ru, owner)
for stages whose context has no owner in contexts.yaml; they are visible only inside that route.
Context maps (CONTEXT_MAPS): contexts.yaml (NPM/OKS, drawn with the NPM route, guard allowlist) plus one map per
route (#1392: vpm-oks-contexts.yaml, ground-contexts.yaml, same schema); `--check` also proves that each route's
map lists every stage context of that route with the same owner (route_coverage). A context without a
`duplicates` key draws no duplicates box; optional `grid: "col/row"` on every context of a map places it
explicitly (all or none, columns >= 1 apart). Route boards widen a 2-line actor and push the rows below a tall
event; one-line titles/actors and <= 110 px events draw exactly as before.
Outputs (generated, never hand-edited): <route>.excalidraw/.svg per route, <map>.excalidraw/.svg per context map.
Deterministic: element ids, seeds and nonces are hashes of the YAML keys, `updated` is a constant, so the same
YAML gives the same bytes. Offline, stdlib only (no network, no PyYAML; tools/architecture/mini_yaml.py).

Usage:
  uv run python tools/architecture/route_map.py            # write all route + context files (temp + replace)
  uv run python tools/architecture/route_map.py --check    # exit 1 if a committed file differs (drift),
                                                           # or a command/D-row/path/function is unknown
PNG for Artem (offline, not committed; COORDINATION rule 57): magick -density 110 <svg> <png>.
Exit codes: 0 ok, 1 drift or unknown reference, 2 malformed YAML/schema.
"""
import argparse
import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mini_yaml  # noqa: E402
else:
    from . import mini_yaml

ROOT = Path(__file__).resolve().parents[2]
ARCH = Path("docs/architecture")
EVENTS = ARCH / "npm-oks-route.events.yaml"
VPM_EVENTS = ARCH / "vpm-oks-route.events.yaml"
GROUND_EVENTS = ARCH / "ground-route.events.yaml"
CONTEXTS = ARCH / "contexts.yaml"
VPM_CONTEXTS = ARCH / "vpm-oks-contexts.yaml"
GROUND_CONTEXTS = ARCH / "ground-contexts.yaml"
MAF_EVENTS = ARCH / "maf-route.events.yaml"            # #1393
FLORA_EVENTS = ARCH / "flora-route.events.yaml"
PACKAGE_EVENTS = ARCH / "package-route.events.yaml"
MAF_CONTEXTS = ARCH / "maf-contexts.yaml"
FLORA_CONTEXTS = ARCH / "flora-contexts.yaml"
PACKAGE_CONTEXTS = ARCH / "package-contexts.yaml"
OUTPUTS = {"route": ARCH / "npm-oks-route", "vpm-route": ARCH / "vpm-oks-route",
           "ground-route": ARCH / "ground-route", "contexts": ARCH / "contexts",
           "vpm-contexts": ARCH / "vpm-oks-contexts", "ground-contexts": ARCH / "ground-contexts",
           "maf-route": ARCH / "maf-route", "flora-route": ARCH / "flora-route",
           "package-route": ARCH / "package-route", "maf-contexts": ARCH / "maf-contexts",
           "flora-contexts": ARCH / "flora-contexts", "package-contexts": ARCH / "package-contexts"}
ROUTE_MAP_OF = {"vpm-route": "vpm-contexts", "ground-route": "ground-contexts",   # #1392: route -> its context map
                "maf-route": "maf-contexts", "flora-route": "flora-contexts",     # #1393
                "package-route": "package-contexts"}


def route_events():
    """Route name -> events YAML (read at call time so a monkeypatched path is honoured)."""
    return {"route": EVENTS, "vpm-route": VPM_EVENTS, "ground-route": GROUND_EVENTS,
            "maf-route": MAF_EVENTS, "flora-route": FLORA_EVENTS, "package-route": PACKAGE_EVENTS}


def context_maps():
    """Context map name -> YAML (#1392; read at call time like route_events)."""
    return {"contexts": CONTEXTS, "vpm-contexts": VPM_CONTEXTS, "ground-contexts": GROUND_CONTEXTS,
            "maf-contexts": MAF_CONTEXTS, "flora-contexts": FLORA_CONTEXTS, "package-contexts": PACKAGE_CONTEXTS}

COLORS = {  # Event Storming sticky colours
    "actor": "#fff3bf", "event": "#ffc078", "command": "#a5d8ff", "rule": "#d0bfff",
    "context": "#e9ecef", "hotspot": "#ffc9c9", "owner": "#b2f2bb", "kernel": "#ffec99", "title": "transparent",
    "branch": "#c3fae8",  # #1375: task-dependent branch inside a stage
}
FONT_SANS, FONT_MONO = 2, 3
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
D_ROW = re.compile(r"^D[0-9]{3}$")


class SchemaError(ValueError):
    pass


# ---------------------------------------------------------------- schema
def _need(obj, key, where, kind: type = str) -> Any:
    if not isinstance(obj, dict) or key not in obj:
        raise SchemaError(f"{where}: missing '{key}'")
    value = obj[key]
    if not isinstance(value, kind) or (kind in (str, list) and not value):
        raise SchemaError(f"{where}: '{key}' must be a non-empty {kind.__name__}")
    return value


def _ru(text, where):
    if not CYRILLIC.search(text):
        raise SchemaError(f"{where}: label {text!r} has no Russian text")
    return text


def check_schema(events, contexts):
    """Cross-reference ids inside the two YAML files; raise SchemaError naming the first bad key."""
    _ru(_need(events, "title_ru", "events"), "events.title_ru")
    actors = {}
    for i, a in enumerate(_need(events, "actors", "events", list)):
        aid = _need(a, "id", f"actors[{i}]")
        if aid in actors:
            raise SchemaError(f"actors[{i}]: duplicate id {aid!r}")
        actors[aid] = _ru(_need(a, "ru", f"actors[{i}]"), f"actors[{i}].ru")
    ctx_ids = dict(check_contexts(contexts))  # route-local contexts below stay inside this route
    return actors, _check_stages(events, ctx_ids)


def check_contexts(contexts):
    """Schema of one context map; returns {context id: ru}. SchemaError names the first bad key."""
    _ru(_need(contexts, "title_ru", "contexts"), "contexts.title_ru")
    kernel = _need(contexts, "shared_kernel", "contexts", dict)
    ctx_ids = {}
    for i, c in enumerate([kernel] + _need(contexts, "contexts", "contexts", list)):
        where = f"contexts[{i}]"
        cid = _need(c, "id", where)
        if cid in ctx_ids:
            raise SchemaError(f"{where}: duplicate context id {cid!r}")
        ctx_ids[cid] = _ru(_need(c, "ru", where), where + ".ru")
        _need(c, "owner", where)
        _ru(_need(c, "owner_ru", where), where + ".owner_ru")
        for j, f in enumerate(_need(c, "functions", where, list)):
            _need(f, "name", f"{where}.functions[{j}]")
            _ru(_need(f, "contract", f"{where}.functions[{j}]"), f"{where}.functions[{j}].contract")
        for j, d in enumerate(c.get("duplicates", [])):
            dwhere = f"{where}.duplicates[{j}]"
            at = _need(d, "at", dwhere)
            if "rule" in d:   # guard allowlist row: keyed by function, never by a bare line (#1387)
                if not re.match(r"^[^:]+\.py::([A-Za-z_][\w.]*|<module>)$", at):
                    raise SchemaError(f"{dwhere}: rule row 'at' must be path.py::function, got {at!r}")
            elif not re.match(r"^[^:]+\.py:[1-9][0-9]*$", at):
                raise SchemaError(f"{dwhere}: 'at' must be path.py:line, got {at!r}")
            if not re.match(r"^#[0-9]+$", _need(d, "issue", dwhere)):
                raise SchemaError(f"{dwhere}: 'issue' must be #<number>")
            if "rule" not in d:
                _need(d, "match", dwhere)
                _ru(_need(d, "ru", dwhere), dwhere + ".ru")
    rule_ids = {_need(r, "id", "rules") for r in _need(contexts, "rules", "contexts", list)}
    for r in contexts["rules"]:
        _ru(_need(r, "ru", "rules"), f"rules.{r['id']}.ru")
    for c in [kernel] + contexts["contexts"]:
        for d in c.get("duplicates", []):
            if "rule" in d and d["rule"] not in rule_ids:
                raise SchemaError(f"{d['at']}: unknown rule {d['rule']!r}")
    for i, rel in enumerate(contexts.get("relations", [])):
        for end in ("from", "to"):
            if _need(rel, end, f"relations[{i}]") not in ctx_ids:
                raise SchemaError(f"relations[{i}]: unknown context {rel[end]!r}")
        _ru(_need(rel, "ru", f"relations[{i}]"), f"relations[{i}].ru")
    grids = [c.get("grid") for c in contexts["contexts"]]
    if any(g is not None for g in grids):   # #1392 layout: all or none, "col/row", col 0..4 in halves, distinct
        seen = {}
        for c, g in zip(contexts["contexts"], grids):
            if not isinstance(g, str) or not re.match(r"^[0-4](\.5)?/[1-9][0-9]?$", g):
                raise SchemaError(f"context {c['id']}: 'grid' must be \"col/row\" (col 0-4, halves; row >= 1), got {g!r}")
            if g in seen:
                raise SchemaError(f"context {c['id']}: grid {g} is taken by {seen[g]}")
            seen[g] = c["id"]
        rows = {}
        for g, cid in seen.items():
            col, r = g.split("/")
            rows.setdefault(r, []).append((float(col), cid))
        for r, cols in rows.items():   # boxes are wider than half a column: one row, columns >= 1 apart
            cols.sort()
            for (c0, a), (c1, z) in zip(cols, cols[1:]):
                if c1 - c0 < 1:
                    raise SchemaError(f"context {z}: grid row {r} overlaps {a} (columns {c0} and {c1})")
    return ctx_ids


def _check_stages(events, ctx_ids):
    actors = {a["id"] for a in events["actors"]}
    if "local_contexts" in events:
        for i, c in enumerate(_need(events, "local_contexts", "events", list)):
            where = f"local_contexts[{i}]"
            cid = _need(c, "id", where)
            if cid in ctx_ids:
                raise SchemaError(f"{where}: duplicate context id {cid!r}")
            ctx_ids[cid] = _ru(_need(c, "ru", where), where + ".ru")
            _need(c, "owner", where)
    stage_ids = []
    for i, s in enumerate(_need(events, "stages", "events", list)):
        where = f"stages[{i}]"
        sid = _need(s, "id", where)
        if sid in stage_ids:
            raise SchemaError(f"{where}: duplicate stage id {sid!r}")
        stage_ids.append(sid)
        _ru(_need(s, "event_ru", where), where + ".event_ru")
        if _need(s, "actor", where) not in actors:
            raise SchemaError(f"{where}: unknown actor {s['actor']!r}")
        if _need(s, "context", where) not in ctx_ids:
            raise SchemaError(f"{where}: unknown context {s['context']!r}")
        for key in ("commands", "rules", "evidence"):
            if key in s and not (isinstance(s[key], list) and s[key] and all(isinstance(v, str) for v in s[key])):
                raise SchemaError(f"{where}: '{key}' must be a non-empty list of strings")
        _need(s, "rules", where, list)
        _need(s, "evidence", where, list)
        if "branches" in s:  # #1375: a task-dependent choice inside one stage (D292)
            branch_ids = set()
            for j, br in enumerate(_need(s, "branches", where, list)):
                bwhere = f"{where}.branches[{j}]"
                bid = _need(br, "id", bwhere)
                if bid in branch_ids:
                    raise SchemaError(f"{bwhere}: duplicate branch id {bid!r}")
                branch_ids.add(bid)
                for key in ("when_ru", "ru"):
                    _ru(_need(br, key, bwhere), f"{bwhere}.{key}")
                for key in ("rules", "evidence"):
                    _need(br, key, bwhere, list)
                for key in ("commands", "rules", "evidence"):
                    if key in br and not (isinstance(br[key], list) and br[key]
                                          and all(isinstance(v, str) for v in br[key])):
                        raise SchemaError(f"{bwhere}: '{key}' must be a non-empty list of strings")
    for i, h in enumerate(events.get("hotspots", [])):
        where = f"hotspots[{i}]"
        _need(h, "id", where)
        if _need(h, "stage", where) not in stage_ids:
            raise SchemaError(f"{where}: unknown stage {h['stage']!r}")
        _ru(_need(h, "ru", where), where + ".ru")
        _need(h, "evidence", where, list)
    return ctx_ids


def route_coverage(events, contexts, cmap):
    """#1392: problems if the route's own context map misses a stage context or names another owner for it.

    A stage context comes from contexts.yaml or the route's local_contexts; the map must list it (kernel or
    contexts) with the same owner. A malformed map raises SchemaError.
    """
    check_contexts(cmap)
    owners = {c["id"]: c["owner"] for c in [contexts["shared_kernel"]] + contexts["contexts"]}
    owners.update({c["id"]: c["owner"] for c in events.get("local_contexts", [])})
    in_map = {c["id"]: c["owner"] for c in [cmap["shared_kernel"]] + cmap["contexts"]}
    problems = []
    for cid in dict.fromkeys(s["context"] for s in events["stages"]):
        if cid not in in_map:
            problems.append(f"context map: stage context {cid!r} is missing")
        elif cid in owners and in_map[cid] != owners[cid]:
            problems.append(f"context map: {cid!r} owner {in_map[cid]} differs from the route's {owners[cid]}")
    return problems


# ---------------------------------------------------------------- references (existence)
def _dt_commands():
    import argparse as _ap
    from dt_ai.cli.main import parser
    sub = next(a for a in parser()._actions if isinstance(a, _ap._SubParsersAction))
    return sub.choices


def command_exists(command):
    """'agr <alias>' or 'dt <sub> [<choice>]' exists in today's CLI (pointer stubs do not count)."""
    words = command.split()
    if len(words) < 2:
        return False
    if words[0] == "agr":
        from dt_ai.cli import agr
        return len(words) == 2 and words[1] in set(agr.ALIASES) | {"validate", "vpm-to-npm"}
    if words[0] != "dt":
        return False
    sub = _dt_commands().get(words[1])
    if sub is None:
        return False
    if len(words) == 2:
        return True
    choices = next((a.choices for a in sub._actions if a.choices and not a.option_strings), None)
    return len(words) == 3 and choices is not None and words[2] in choices


def _top_functions(path):
    tree = ast.parse(path.read_bytes(), filename=str(path))
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def verify_references(root, events, contexts):
    """Return a list of problems: unknown command, D-row, path, owner function, or a path:line without its match."""
    root = Path(root)
    problems = []
    decisions = (root / "docs/decisions.md").read_text(encoding="utf-8")
    known_d = set(re.findall(r"^\| (D[0-9]{3}) \|", decisions, re.M))

    def d_row(d, where):
        if not D_ROW.match(d) or d not in known_d:
            problems.append(f"{where}: D-row {d} not in docs/decisions.md")

    def path(p, where):
        if not (root / p).exists():
            problems.append(f"{where}: path {p} does not exist")

    for s in events["stages"]:
        for c in s.get("commands", []):
            if not command_exists(c):
                problems.append(f"stage {s['id']}: command {c!r} is not an existing agr/dt command")
        for d in s["rules"]:
            d_row(d, f"stage {s['id']}")
        for p in s["evidence"]:
            path(p, f"stage {s['id']}")
        for br in s.get("branches", []):
            where = f"stage {s['id']} branch {br['id']}"
            for c in br.get("commands", []):
                if not command_exists(c):
                    problems.append(f"{where}: command {c!r} is not an existing agr/dt command")
            for d in br["rules"]:
                d_row(d, where)
            for p in br["evidence"]:
                path(p, where)
    for h in events.get("hotspots", []):
        for d in h.get("rules", []):
            d_row(d, f"hotspot {h['id']}")
        for p in h["evidence"]:
            path(p, f"hotspot {h['id']}")
    for r in contexts["rules"]:
        path(r["owner"], f"rule {r['id']}")
    for c in events.get("local_contexts", []):
        if not (root / c["owner"]).is_file():
            problems.append(f"local context {c['id']}: owner {c['owner']} does not exist")
    for c in [contexts["shared_kernel"]] + contexts["contexts"]:
        owner = root / c["owner"]
        if not owner.is_file():
            problems.append(f"context {c['id']}: owner {c['owner']} does not exist")
            continue
        if "area" in c:
            path(c["area"], f"context {c['id']}")
        defined = _top_functions(owner)
        for f in c["functions"]:
            if f["name"] not in defined:
                problems.append(f"context {c['id']}: {c['owner']} has no top-level function {f['name']}")
        for d in c.get("duplicates", []):
            if "rule" in d:   # path.py::function; the function itself is checked by duplicate_guard (stale row)
                rel, line = d["at"].split("::", 1)[0], None
            else:
                rel, line = d["at"].rsplit(":", 1)
            if rel == c["owner"]:
                problems.append(f"context {c['id']}: duplicate {d['at']} is the owner itself")
            if not (root / rel).is_file():
                problems.append(f"context {c['id']}: duplicate {d['at']} does not exist")
                continue
            if line is None:
                continue
            lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            if int(line) > len(lines):
                problems.append(f"context {c['id']}: {d['at']} is past the end ({len(lines)} lines)")
            elif "match" in d and d["match"] not in lines[int(line) - 1]:
                problems.append(f"context {c['id']}: {d['at']} does not contain {d['match']!r}")
    return problems


# ---------------------------------------------------------------- drawing
def _h(key, salt=""):
    return hashlib.sha1((salt + key).encode("utf-8")).hexdigest()


def wrap(text, width_px, font_size):
    """Greedy word wrap; explicit newlines kept. Width estimate 0.56 em per char (0.62 for mono)."""
    per_line = max(8, int(width_px / (font_size * 0.56)))
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            while len(word) > per_line:
                if line:
                    out.append(line)
                    line = ""
                out.append(word[:per_line])
                word = word[per_line:]
            cand = word if not line else line + " " + word
            if len(cand) > per_line and line:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line)
    return out


class Board:
    def __init__(self):
        self.elements = []
        self.by_id = {}

    def _base(self, key, kind, x, y, w, h, stroke="#1e1e1e", bg="transparent", dashed=False):
        el = {
            "id": "e" + _h(key)[:15], "type": kind, "x": round(x, 2), "y": round(y, 2),
            "width": round(w, 2), "height": round(h, 2), "angle": 0, "strokeColor": stroke,
            "backgroundColor": bg, "fillStyle": "solid", "strokeWidth": 1,
            "strokeStyle": "dashed" if dashed else "solid", "roughness": 0, "opacity": 100, "groupIds": [],
            "frameId": None, "roundness": {"type": 3} if kind == "rectangle" else None,
            "seed": int(_h(key, "seed")[:8], 16) % 2_000_000_000 + 1, "version": 1,
            "versionNonce": int(_h(key, "nonce")[:8], 16) % 2_000_000_000 + 1, "isDeleted": False,
            "boundElements": None, "updated": 1, "link": None, "locked": False,
        }
        if el["id"] in self.by_id:
            raise SchemaError(f"two drawing elements share the key {key!r}")
        self.elements.append(el)
        self.by_id[el["id"]] = el
        return el

    def _text(self, key, x, y, w, lines, size, mono, align, container=None):
        h = len(lines) * size * 1.25
        el = self._base(key + "/text", "text", x, y, w, h)
        text = "\n".join(lines)
        el.update({"text": text, "fontSize": size, "fontFamily": FONT_MONO if mono else FONT_SANS,
                   "textAlign": align, "verticalAlign": "middle" if container else "top",
                   "containerId": container, "originalText": text, "autoResize": True, "lineHeight": 1.25})
        return el

    def box(self, key, x, y, w, text, bg, size=16, mono=False, min_h=0, dashed=False, align="center"):
        lines = wrap(text, w - 16, size)
        h = max(min_h, len(lines) * size * 1.25 + 20)
        rect = self._base(key, "rectangle", x, y, w, h, bg=bg, dashed=dashed)
        txt = self._text(key, x + 8, y + (h - len(lines) * size * 1.25) / 2, w - 16, lines, size, mono, align,
                         container=rect["id"])
        rect["boundElements"] = [{"type": "text", "id": txt["id"]}]
        return rect

    def label(self, key, x, y, w, text, size=20):
        return self._text(key, x, y, w, wrap(text, w, size), size, False, "left")

    def arrow(self, key, a, b, text=None, label_w=200):
        ax, ay = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
        bx, by = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        # leave from the box edge facing the target
        if abs(bx - ax) * a["height"] >= abs(by - ay) * a["width"]:
            sx = a["x"] + (a["width"] if bx > ax else 0)
            ex = b["x"] + (0 if bx > ax else b["width"])
            sy, ey = ay, by
        else:
            sy = a["y"] + (a["height"] if by > ay else 0)
            ey = b["y"] + (0 if by > ay else b["height"])
            sx, ex = ax, bx
        el = self._base(key, "arrow", sx, sy, abs(ex - sx), abs(ey - sy))
        el.update({"roundness": {"type": 2}, "points": [[0, 0], [round(ex - sx, 2), round(ey - sy, 2)]],
                   "lastCommittedPoint": None, "startArrowhead": None, "endArrowhead": "arrow", "elbowed": False,
                   "startBinding": {"elementId": a["id"], "focus": 0, "gap": 4},
                   "endBinding": {"elementId": b["id"], "focus": 0, "gap": 4}})
        for box in (a, b):
            box["boundElements"] = (box["boundElements"] or []) + [{"type": "arrow", "id": el["id"]}]
        if text:
            lines = wrap(text, label_w, 14)
            t = self._text(key, sx + (ex - sx) / 2 - label_w / 2, sy + (ey - sy) / 2 - len(lines) * 9, label_w, lines, 14,
                           False, "center", container=el["id"])
            el["boundElements"] = [{"type": "text", "id": t["id"]}]
        return el

    def excalidraw(self):
        doc = {"type": "excalidraw", "version": 2, "source": "tools/architecture/route_map.py",
               "elements": self.elements, "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None},
               "files": {}}
        return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"

    def svg(self):
        xs = [e["x"] for e in self.elements] + [e["x"] + e["width"] for e in self.elements]
        ys = [e["y"] for e in self.elements] + [e["y"] + e["height"] for e in self.elements]
        x0, y0 = min(xs) - 30, min(ys) - 30
        w, h = max(xs) - x0 + 30, max(ys) - y0 + 30
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" '
               f'width="{w:.0f}" height="{h:.0f}" font-family="Segoe UI, Arial, sans-serif">',
               '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
               'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#1e1e1e"/></marker></defs>',
               f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{w:.0f}" height="{h:.0f}" fill="#ffffff"/>']
        texts = []
        for e in self.elements:
            if e["type"] == "rectangle":
                dash = ' stroke-dasharray="6 4"' if e["strokeStyle"] == "dashed" else ""
                fill = "none" if e["backgroundColor"] == "transparent" else e["backgroundColor"]
                out.append(f'<rect x="{e["x"]}" y="{e["y"]}" width="{e["width"]}" height="{e["height"]}" rx="8" '
                           f'fill="{fill}" stroke="{e["strokeColor"]}"{dash}/>')
            elif e["type"] == "arrow":
                (px, py) = e["points"][1]
                out.append(f'<line x1="{e["x"]}" y1="{e["y"]}" x2="{round(e["x"] + px, 2)}" '
                           f'y2="{round(e["y"] + py, 2)}" stroke="#1e1e1e" marker-end="url(#arrow)"/>')
            elif e["type"] == "text":
                texts.append(e)
        for e in texts:  # text above shapes and arrows
            size = e["fontSize"]
            anchor = {"center": "middle", "left": "start"}[e["textAlign"]]
            tx = e["x"] + e["width"] / 2 if anchor == "middle" else e["x"]
            family = ' font-family="Consolas, monospace"' if e["fontFamily"] == FONT_MONO else ""
            on_arrow = e["containerId"] and self.by_id[e["containerId"]]["type"] == "arrow"
            if on_arrow:
                out.append(f'<rect x="{e["x"] + 30}" y="{e["y"]}" width="{e["width"] - 60}" height="{e["height"]}" '
                           f'fill="#ffffff" opacity="0.9"/>')
            out.append(f'<text x="{round(tx, 2)}" y="{e["y"]}" font-size="{size}" text-anchor="{anchor}"'
                       f'{family} fill="#1e1e1e">')
            for i, line in enumerate(e["text"].split("\n")):
                out.append(f'<tspan x="{round(tx, 2)}" dy="{size * 1.25 if i else size}">{escape(line)}</tspan>')
            out.append("</text>")
        out.append("</svg>")
        return "\n".join(out) + "\n"


# ---------------------------------------------------------------- the two pictures
def route_board(events, contexts):
    actors, ctx_ru = check_schema(events, contexts)
    b = Board()
    col_w, gap = 230, 40
    title = events["title_ru"] + f" ({events['issue']})"
    # #1392: a title, actor or event that would not fit widens / pushes its row; one-line titles, one-line actors
    # and events of <= 110 px (every #1359 / #1375 box) draw exactly as before
    b.label("route/title", 40, 0, 1400 if len(wrap(title, 1400, 28)) == 1 else 2300, title, size=28)
    ev_h = max(max(110, len(wrap(f"{i + 1}. {s['event_ru']}", col_w - 16, 17)) * 17 * 1.25 + 20)
               for i, s in enumerate(events["stages"]))
    dy = max(0, 170 + ev_h + 10 - 300)
    legend = ("Легенда: жёлтый — кто действует; оранжевый — событие; голубой — команда agr/dt; "
              "сиреневый — правило (строка D решений); серый — контекст; розовый — горячая точка (здесь теряется время)")
    if any(s.get("branches") for s in events["stages"]):  # #1375; a route without branches draws as before
        legend += "; бирюзовый — ветка (выбор по задаче)"
    b.label("route/legend", 40, 44, 2300, legend, size=16)
    hot_by_stage = {}
    for hs in events.get("hotspots", []):
        hot_by_stage.setdefault(hs["stage"], []).append(hs)
    prev = None
    for i, s in enumerate(events["stages"]):
        x = 40 + i * (col_w + gap)
        k = f"route/{s['id']}"
        actor = actors[s["actor"]]
        if len(wrap(actor, col_w - 96, 15)) == 1:
            b.box(k + "/actor", x + 40, 100, col_w - 80, actor, COLORS["actor"], size=15)
        else:   # #1392 «Агент: Blender / Max / AGR Tools»: full column width keeps it at 2 lines above the event
            b.box(k + "/actor", x + 10, 100, col_w - 20, actor, COLORS["actor"], size=15)
        ev = b.box(k + "/event", x, 170, col_w, f"{i + 1}. {s['event_ru']}", COLORS["event"], size=17, min_h=110)
        if prev is not None:
            b.arrow(k + "/flow", prev, ev)
        prev = ev
        cmds = s.get("commands", [])
        if cmds:
            b.box(k + "/cmd", x, 300 + dy, col_w, "Команда:\n" + "\n".join(cmds), COLORS["command"], size=14, min_h=90)
        else:
            b.box(k + "/cmd", x, 300 + dy, col_w, "Нет команды agr/dt", COLORS["command"], size=14, min_h=90,
                  dashed=True)
        b.box(k + "/rules", x, 420 + dy, col_w, "Правила: " + ", ".join(s["rules"]), COLORS["rule"], size=14, min_h=60)
        b.box(k + "/ctx", x, 500 + dy, col_w, "Контекст: " + ctx_ru[s["context"]], COLORS["context"], size=14,
              min_h=60)
        y = 590 + dy
        for br in s.get("branches", []):
            text = f"Ветка: {br['when_ru']}\n→ {br['ru']}"
            if br.get("commands"):
                text += "\nКоманда: " + ", ".join(br["commands"])
            text += f" [{', '.join(br['rules'])}]"
            el = b.box(f"{k}/branch/{br['id']}", x, y, col_w, text, COLORS["branch"], size=13)
            y += el["height"] + 16
        for hs in hot_by_stage.get(s["id"], []):
            rules = f" [{', '.join(hs['rules'])}]" if hs.get("rules") else ""
            el = b.box(f"route/hot/{hs['id']}", x, y, col_w, "⚠ " + hs["ru"] + rules, COLORS["hotspot"], size=13)
            y += el["height"] + 16
    return b


def _dup_lines(dups, rules_ru):
    """Group duplicates by file: tagged rows as 'path: fn1, fn2 [rule]', described rows as 'path:line — ru'."""
    grouped, order, described = {}, [], []
    for d in dups:
        if "rule" in d:
            rel, fn = d["at"].split("::", 1)
            key = (rel, d["rule"])
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            if fn not in grouped[key]:
                grouped[key].append(fn)
        else:
            described.append(f"• {d['at']} — {d['ru']} ({d['issue']})")
    tagged = [f"• {rel}: {', '.join(sorted(grouped[(rel, rule)]))}" for rel, rule in order]
    return described + tagged, sorted({d["rule"] for d in dups if "rule" in d})


def contexts_board(events, contexts):
    """Context map board; `events` None = a route's own map (#1392), checked by check_contexts alone."""
    if events is None:
        check_contexts(contexts)
    else:
        check_schema(events, contexts)
    rules_ru = {r["id"]: r["ru"] for r in contexts["rules"]}
    b = Board()
    b.label("ctx/title", 40, 0, 1600, contexts["title_ru"] + f" ({contexts['issue']})", size=28)
    b.label("ctx/legend", 40, 44, 2000,
            "Легенда: зелёный — модуль-владелец и его функции (контракт: вход -> выход); жёлтый — общее ядро; "
            "розовый — дубли вне владельца (путь:строка); стрелки — что контекст передаёт дальше", size=16)
    w, gap = 470, 140
    nodes, tails = {}, {}

    def place(c, x, y, bg):
        lines = [c["ru"], "Владелец: " + c["owner"], c["owner_ru"], ""]
        lines += [f"{f['name']}: {f['contract']}" for f in c["functions"]]
        node = b.box(f"ctx/{c['id']}", x, y, w, "\n".join(lines), bg, size=14, align="left")
        nodes[c["id"]] = node
        if "duplicates" not in c:   # #1392: no duplicates key -> no pink box (an empty list still draws "0")
            tails[c["id"]] = node
            return node["height"]
        dups = c["duplicates"]
        dl, rules = _dup_lines(dups, rules_ru)
        head = f"Дубли вне владельца: {len(dups)}"
        if rules:
            head += "\nПравило проверки: " + "; ".join(rules_ru[r] for r in rules)
        dup = b.box(f"ctx/{c['id']}/dups", x, y + node["height"] + 14, w, head + "\n" + "\n".join(dl),
                    COLORS["hotspot"], size=12, align="left")
        tails[c["id"]] = dup
        return node["height"] + 14 + dup["height"]

    k = contexts["shared_kernel"]
    top = 110
    kh = place(k, 40 + (w + gap) * 1.5, top, COLORS["kernel"])
    row = top + kh + 60
    if any("grid" in c for c in contexts["contexts"]):   # #1392: explicit "col/row" cells (checked by check_contexts)
        cells = {c["id"]: tuple(float(v) for v in c["grid"].split("/")) for c in contexts["contexts"]}
        y = row
        for r in sorted({cell[1] for cell in cells.values()}):
            hs = [place(c, 40 + (w + gap) * cells[c["id"]][0], y, COLORS["owner"])
                  for c in contexts["contexts"] if cells[c["id"]][1] == r]
            y += max(hs) + 60
        return _relations(b, contexts, nodes, tails)
    heights = [place(c, 40 + i * (w + gap), row, COLORS["owner"]) for i, c in enumerate(contexts["contexts"][:4])]
    rest = contexts["contexts"][4:]
    y = row + max(heights) + 60
    for start in range(0, len(rest), 4):   # rows of 4, a short row centred (one context -> column 1.5 as before)
        chunk = rest[start:start + 4]
        hs = [place(c, 40 + (w + gap) * ((4 - len(chunk)) / 2 + i), y, COLORS["owner"]) for i, c in enumerate(chunk)]
        y += max(hs) + 60
    return _relations(b, contexts, nodes, tails)


def _relations(b, contexts, nodes, tails):
    for i, rel in enumerate(contexts.get("relations", [])):
        a, z = nodes[rel["from"]], nodes[rel["to"]]
        if a["y"] < z["y"]:      # downwards: leave from the bottom of the duplicates box, not through it
            a = tails[rel["from"]]
        elif a["y"] > z["y"]:    # upwards: arrive at the bottom of the target's duplicates box
            z = tails[rel["to"]]
        b.arrow(f"ctx/rel/{i}/{rel['from']}->{rel['to']}", a, z, rel["ru"], label_w=120)
    return b


def load_routes(root=ROOT):
    """Route name -> parsed events YAML, for every route of route_events()."""
    return {name: mini_yaml.load(Path(root) / rel) for name, rel in route_events().items()}


def load_context_maps(root=ROOT):
    """Context map name -> parsed YAML, for every map of context_maps()."""
    return {name: mini_yaml.load(Path(root) / rel) for name, rel in context_maps().items()}


def render_all(root=ROOT):
    """(routes, contexts, files): every route board, the NPM context map (drawn from the NPM route) and each
    route's own context map (#1392)."""
    root = Path(root)
    routes = load_routes(root)
    maps = load_context_maps(root)
    contexts = maps["contexts"]
    files = {}
    boards = [(name, route_board(ev, contexts)) for name, ev in routes.items()]
    boards.append(("contexts", contexts_board(routes["route"], contexts)))
    for name in ROUTE_MAP_OF.values():
        boards.append((name, contexts_board(None, maps[name])))
    for name, board in boards:
        files[OUTPUTS[name].with_suffix(".excalidraw")] = board.excalidraw()
        files[OUTPUTS[name].with_suffix(".svg")] = board.svg()
    return routes, contexts, files


def render(root=ROOT):
    """#1359 interface: (NPM route events, contexts, all files)."""
    routes, contexts, files = render_all(root)
    return routes["route"], contexts, files


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate the route/context Excalidraw + SVG from YAML (#1359, #1383, #1392)")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true", help="compare with the committed files, write nothing")
    args = ap.parse_args(argv)
    try:
        routes, contexts, files = render_all(args.root)
    except (OSError, mini_yaml.MiniYamlError, SchemaError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    inputs = {(args.root / rel).resolve() for rel in list(route_events().values()) + list(context_maps().values())}
    for rel in files:
        if (args.root / rel).resolve() in inputs:
            print(f"ERROR: output {rel} is an input", file=sys.stderr)
            return 2
    if args.check:
        try:
            problems = verify_references(args.root, {"stages": [], "hotspots": []}, contexts)  # context map
            for name, events in routes.items():
                problems += [f"{route_events()[name].name}: {p}"
                             for p in verify_references(args.root, events, contexts) if p not in problems]
            maps = load_context_maps(args.root)
            for route, name in ROUTE_MAP_OF.items():   # #1392: each route's own context map
                label = context_maps()[name].name
                problems += [f"{label}: {p}"
                             for p in verify_references(args.root, {"stages": [], "hotspots": []}, maps[name])]
                problems += [f"{label}: {p}" for p in route_coverage(routes[route], contexts, maps[name])]
        except (OSError, SyntaxError, ImportError) as exc:
            print(f"ERROR: cannot verify references: {exc}", file=sys.stderr)
            return 2
        for rel, text in files.items():
            path = args.root / rel
            if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
                problems.append(f"drift: {rel.as_posix()} differs from the generator output; rerun route_map.py")
        for p in problems:
            print(p)
        return 1 if problems else 0
    for rel, text in files.items():
        path = args.root / rel
        tmp = path.with_name(path.name + ".partial")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
        print(f"wrote {rel.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
