"""Decision trees per scenario skeleton (#2039): owner `docs/agents/decision-trees.json`.

For every cell of `docs/agents/skeletons.json` the tree names, stage by stage, the decision met there: question ->
branches -> who decides (AGENT by a recorded rule, quoted verbatim, or ARTEM with a picture sheet) -> next stage.
Rules: a decision id from `docs/decisions.md` (+ `docs/decisions-detail.md`) or `fact:<repo path>`; a branch with no
rule goes to ARTEM, never to an invented rule. Gap stages (no shared implementation) are flagged as manual.

Usage:
  python tools/architecture/decision_trees.py              check (exit 0 clean, 1 problems, 2 bad input)
  python tools/architecture/decision_trees.py --render     rewrite docs/agents/decision-trees/<cell>.md
  python tools/architecture/decision_trees.py --show CELL [--stage STAGE]   print what to decide at a stage
  python tools/architecture/decision_trees.py --sheets NEW_DIR   Russian PNG sheets for Artem (needs Pillow)

Pattern: n/a | new-case: tools/architecture/decision_trees.py - decision trees per scenario skeleton
"""
import argparse
import json
import re
import sys
from pathlib import Path

TREES = "docs/agents/decision-trees.json"
SKELETONS = "docs/agents/skeletons.json"
LOG = "docs/decisions.md"
DETAIL = "docs/decisions-detail.md"
MD_DIR = "docs/agents/decision-trees"
DECIDERS = ("AGENT", "ARTEM")
DID = re.compile(r"^D\d{3}$")
ROOT = Path(__file__).resolve().parents[2]


class InputError(ValueError):
    """Unreadable input (exit 2)."""


def _json(root, rel):
    try:
        return json.loads((Path(root) / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"{rel}: cannot read ({exc})") from None


def load_trees(root=ROOT):
    return _json(root, TREES)


def load_skeletons(root=ROOT):
    return _json(root, SKELETONS)


def decision_sources(root=ROOT):
    """Decision id -> its log row text plus its verbatim detail section, if any."""
    rows = {}
    for line in (Path(root) / LOG).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(D\d{3})\s*\|", line)
        if m:
            rows[m.group(1)] = line
    detail = (Path(root) / DETAIL).read_text(encoding="utf-8")
    for m in re.finditer(r"^## (D\d{3})\n(.*?)(?=^## D\d{3}\n|\Z)", detail, flags=re.S | re.M):
        if m.group(1) in rows:
            rows[m.group(1)] += "\n" + m.group(2)
    return rows


def _norm(text):
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip().lower()


def _source_text(rule, rows, root, cache):
    if DID.match(rule):
        return rows.get(rule)
    if rule.startswith("fact:"):
        rel = rule[5:].split("#", 1)[0]
        if rel not in cache:
            path = Path(root) / rel
            cache[rel] = path.read_text(encoding="utf-8") if path.is_file() else None
        return cache[rel]
    return None


def _check_node(where, node, stages, rows, root, cache, out):
    if not node.get("q") or not node.get("q_ru"):
        out.append(f"{where}: node needs q and q_ru")
    branches = node.get("branches") or []
    if not branches:
        out.append(f"{where}: node without branches")
    for i, b in enumerate(branches):
        at = f"{where} branch {i + 1}"
        decider = b.get("decider")
        if decider not in DECIDERS:
            out.append(f"{at}: decider {decider!r} not in {DECIDERS}")
        if not b.get("when") or not b.get("when_ru") or not b.get("then_ru"):
            out.append(f"{at}: needs when, when_ru, then_ru")
        rules = b.get("rule") or []
        texts = []
        for rule in rules:
            if DID.match(rule):
                if rule not in rows:
                    out.append(f"{at}: cites missing {rule}")
                    continue
            elif not rule.startswith("fact:"):
                out.append(f"{at}: rule {rule!r} is neither D<nnn> nor fact:<path>")
                continue
            text = _source_text(rule, rows, root, cache)
            if text is None:
                out.append(f"{at}: cited file of {rule} does not exist")
            else:
                texts.append(text)
        if decider == "AGENT" and not rules:
            out.append(f"{at}: AGENT branch without a rule (no rule = ARTEM)")
        quote = b.get("quote", "")
        if rules and not quote:
            out.append(f"{at}: rule cited without a verbatim quote")
        if quote and texts and not any(_norm(quote) in _norm(t) for t in texts):
            out.append(f"{at}: quote not found in {', '.join(rules)}: {quote[:60]!r}")
        if decider == "ARTEM" and not b.get("sheet"):
            out.append(f"{at}: ARTEM branch without a picture sheet")
        job = b.get("job_local")
        if job and not (Path(root) / job).exists():
            out.append(f"{at}: job_local path {job} does not exist")
        nxt = b.get("next")
        if nxt is not None and stages is not None:
            target = nxt[5:] if nxt.startswith("back:") else nxt
            if nxt != "stop" and target not in stages:
                out.append(f"{at}: next {nxt!r} is not 'stop' or a stage of the cell")


def problems(trees, skeletons, rows, root=ROOT):
    """All problems of the trees against the skeletons and the decision log; [] = clean."""
    out, cache = [], {}
    tree_cells = trees.get("cells", {})
    stage_nodes = trees.get("stages", {})
    for cell in tree_cells:
        if cell not in skeletons["cells"]:
            out.append(f"{cell}: tree for an unknown skeleton cell")
    for i, node in enumerate(trees.get("entry", [])):
        _check_node(f"entry[{i}] {node.get('id')}", node, None, rows, root, cache, out)
    for cell, spec in skeletons["cells"].items():
        if cell not in tree_cells:
            out.append(f"{cell}: skeleton cell has no tree")
            continue
        stages = spec["stages"]
        tree = tree_cells[cell]
        for i, node in enumerate(tree.get("pre", [])):
            _check_node(f"{cell}: pre[{i}] {node.get('id')}", node, stages, rows, root, cache, out)
        for sid in stages:
            node = tree.get("overrides", {}).get(sid) or stage_nodes.get(sid)
            if node is None:
                out.append(f"{cell}: stage {sid} has no decision node")
                continue
            gap = bool(skeletons["stages"].get(sid, {}).get("gap"))
            if bool(node.get("gap")) != gap:
                out.append(f"{cell}: {sid}: gap flag {bool(node.get('gap'))} != skeleton gap {gap}")
            _check_node(f"{cell}: {sid}", node, stages, rows, root, cache, out)
    for sid in stage_nodes:
        if sid not in skeletons["stages"]:
            out.append(f"stages: {sid} is not a skeleton stage")
    return out


def cell_nodes(trees, skeletons, cell):
    """Ordered (id, kind, node, default_next) for one cell: entry, pre-stage route steps, skeleton stages."""
    tree = trees["cells"][cell]
    stages = skeletons["cells"][cell]["stages"]
    seq = [(n["id"], "entry", n) for n in trees.get("entry", []) if cell not in n.get("skip_cells", [])]
    seq += [(n["id"], "pre", n) for n in tree.get("pre", [])]
    seq += [(s, "stage", tree.get("overrides", {}).get(s) or trees["stages"][s]) for s in stages]
    return [(sid, kind, node, seq[i + 1][0] if i + 1 < len(seq) else "done")
            for i, (sid, kind, node) in enumerate(seq)]


def _rules_md(b):
    ids = [r for r in b.get("rule", []) if DID.match(r)]
    facts = [f"`{r[5:]}`" for r in b.get("rule", []) if r.startswith("fact:")]
    parts = ([f"[{', '.join(ids)}]"] if ids else []) + facts
    text = " ".join(parts) if parts else "no rule"
    if b.get("quote"):
        text += f": \u00ab{b['quote']}\u00bb"
    if b.get("job_local"):
        text += f" (job-local: `{b['job_local']}`)"
    return text.replace("|", "\\|")


def _mm(text):
    return text.replace('"', "'").replace("[", "(").replace("]", ")").replace("|", "/")


def render_md(trees, skeletons, cell):
    """Deterministic Markdown for one cell: Mermaid flowchart + stage table."""
    nodes = cell_nodes(trees, skeletons, cell)
    spec = skeletons["cells"][cell]
    lines = [f"# Decision tree: `{cell}`", "",
             f"Generated from [`decision-trees.json`](../decision-trees.json) by "
             f"`python tools/architecture/decision_trees.py --render` (#2039); do not edit by hand.",
             f"Trail: `{spec['trail']}`. Stages: `skeletons.json` cell `{cell}`. AGENT = the agent decides by the "
             f"quoted rule; ARTEM = Artem decides on a picture sheet; gap = no shared step - manual.", "",
             "```mermaid", "flowchart TD"]
    for i, (sid, kind, node, nxt) in enumerate(nodes):
        label = f"{sid}{' (gap: no shared step - manual)' if node.get('gap') else ''}<br/>{_mm(node['q'])}"
        lines.append(f'  N{i}["{label}"]')
        lines.append(f"  class N{i} {'gap' if node.get('gap') else 'stage'}")
    index = {sid: i for i, (sid, _, _, _) in enumerate(nodes)}
    for i, (sid, kind, node, nxt) in enumerate(nodes):
        for j, b in enumerate(node["branches"]):
            bid = f"N{i}B{j}"
            ids = [r for r in b.get("rule", []) if DID.match(r)]
            tag = f" ({', '.join(ids)})" if ids else (" (fact)" if b.get("rule") else "")
            lines.append(f'  N{i} -->|"{_mm(b["when"])}"| {bid}("{b["decider"]}{tag}")')
            lines.append(f"  class {bid} {b['decider'].lower()}")
            target = b.get("next") or nxt
            if target == "stop":
                lines.append(f"  {bid} -.-> STOP")
            elif target.startswith("back:"):
                lines.append(f"  {bid} -.-> N{index[target[5:]]}")
            elif target in index:
                lines.append(f"  {bid} --> N{index[target]}")
            else:
                lines.append(f"  {bid} --> DONE")
    lines += ['  STOP(["stop: wait for the answer"])', '  DONE(["done"])',
              "  classDef agent fill:#d8f0d8,stroke:#2e7d32", "  classDef artem fill:#ffe0b2,stroke:#e65100",
              "  classDef gap fill:#eeeeee,stroke:#616161,stroke-dasharray:4", "  classDef stage fill:#e3f2fd,stroke:#1565c0",
              "```", "", "| # | Stage | Question | Branch | Decider | Rule | Next |", "|---|---|---|---|---|---|---|"]
    for i, (sid, kind, node, nxt) in enumerate(nodes, 1):
        name = f"`{sid}`" + (" gap: no shared step - manual" if node.get("gap") else "")
        name += "" if kind == "stage" else f" ({kind})"
        for j, b in enumerate(node["branches"]):
            first = j == 0
            lines.append("| " + " | ".join([
                str(i) if first else "", name if first else "", node["q"].replace("|", "\\|") if first else "",
                b["when"].replace("|", "\\|") + " -> " + b.get("then", b["then_ru"]).replace("|", "\\|"),
                b["decider"] + (f" (sheet: {b['sheet']})" if b["decider"] == "ARTEM" else ""),
                _rules_md(b), b.get("next") or nxt]) + " |")
    return "\n".join(lines) + "\n"


def show(trees, skeletons, cell, stage=None):
    out = []
    for sid, kind, node, nxt in cell_nodes(trees, skeletons, cell):
        if stage and sid != stage:
            continue
        out.append(f"{cell} / {sid} ({kind}{', GAP: no shared step - manual' if node.get('gap') else ''})")
        out.append(f"  Q: {node['q']}")
        for b in node["branches"]:
            out.append(f"  - if {b['when']} -> {b.get('then', b['then_ru'])}")
            out.append(f"    decider {b['decider']}; rule {_rules_md(b)}; next {b.get('next') or nxt}")
    return "\n".join(out)


# --- Russian PNG sheets for Artem (one per cell, phone-width) ---------------------------------------------
_COL = {"AGENT": ((216, 240, 216), (46, 125, 50)), "ARTEM": ((255, 224, 178), (230, 81, 0))}
_FONTS = ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
_BOLD = ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def _font(paths, size):
    from PIL import ImageFont
    for p in paths:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    raise InputError("no font with Cyrillic glyphs found")


def _ru_rule(b):
    ids = [r for r in b.get("rule", []) if DID.match(r)]
    facts = [r[5:] for r in b.get("rule", []) if r.startswith("fact:")]
    if not ids and not facts:
        return "правила нет"
    text = "правило " + ", ".join(ids + facts)
    if b.get("job_local"):
        text += " (только для этого задания)"
    return text


def render_sheet(trees, skeletons, cell, path, width=1080):
    """One tall phone-width PNG: stage boxes, branches coloured by who decides, captions in Russian."""
    from PIL import Image, ImageDraw
    f_title, f_stage, f_text, f_small = (_font(_BOLD, 46), _font(_BOLD, 34), _font(_FONTS, 30),
                                         _font(_FONTS, 25))
    pad = 28
    blocks = []
    meta = trees["cells"][cell]
    blocks.append(("title", f"Дерево решений: {cell}", f_title))
    blocks.append(("text", meta["title_ru"], f_text))
    blocks.append(("legend", "", f_small))
    for n, (sid, kind, node, nxt) in enumerate(cell_nodes(trees, skeletons, cell), 1):
        ru = node.get("ru") or skeletons["stages"].get(sid, {}).get("ru") or sid
        head = f"{n}. {ru} ({sid})" + ("  — ПРОБЕЛ: общего шага нет, вручную" if node.get("gap") else "")
        blocks.append(("stage", head, f_stage))
        blocks.append(("text", node["q_ru"], f_text))
        for b in node["branches"]:
            nx = b.get("next") or nxt
            nx_ru = "стоп до ответа" if nx == "stop" else ("назад к " + nx[5:] if nx.startswith("back:") else
                                                         ("готово" if nx == "done" else "дальше: " + nx))
            who = "АГЕНТ" if b["decider"] == "AGENT" else "АРТЁМ"
            body = f"Если {b['when_ru']} → {b['then_ru']}"
            foot = f"Решает {who}; {_ru_rule(b)}; {nx_ru}"
            if b["decider"] == "ARTEM":
                foot += f". Лист: {b.get('sheet_ru', b.get('sheet', ''))}"
            blocks.append(("branch:" + b["decider"], body, f_text, foot))
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    def lines_of(text, font, indent):
        limit = width - 2 * pad - indent - 32
        out = []
        for para in text.split("\n"):
            line = ""
            for word in para.split(" "):
                trial = f"{line} {word}".strip()
                if line and probe.textlength(trial, font=font) > limit:
                    out.append(line)
                    line = word
                else:
                    line = trial
            out.append(line)
        return [(ln, font) for ln in out]

    layout, height = [], pad
    for blk in blocks:
        kind, text, font = blk[0], blk[1], blk[2]
        if kind == "legend":
            layout.append((kind, [], height))
            height += 60
            continue
        indent = 40 if kind.startswith("branch") else 0
        rows = lines_of(text, font, indent)
        if kind.startswith("branch"):
            rows += lines_of(blk[3], f_small, indent)
        h = sum(probe.textbbox((0, 0), "Ag", font=f)[3] + 8 for _, f in rows) + (24 if kind != "text" else 8)
        layout.append((kind, rows, height))
        height += h + 12
    img = Image.new("RGB", (width, int(height + pad)), "white")
    d = ImageDraw.Draw(img)
    for kind, rows, y in layout:
        if kind == "legend":
            x = pad
            for label, dec in (("решает агент по правилу", "AGENT"), ("решает Артём по листу", "ARTEM")):
                d.rounded_rectangle((x, y, x + 36, y + 36), 6, fill=_COL[dec][0], outline=_COL[dec][1], width=3)
                d.text((x + 46, y), label, fill="black", font=f_small)
                x += 470
            continue
        box_h = sum(probe.textbbox((0, 0), "Ag", font=f)[3] + 8 for _, f in rows) + 16
        indent = 0
        if kind == "stage":
            d.rectangle((pad, y, width - pad, y + box_h), fill=(227, 242, 253), outline=(21, 101, 192), width=3)
        elif kind.startswith("branch"):
            fill, line = _COL[kind.split(":")[1]]
            indent = 40
            d.rounded_rectangle((pad + indent, y, width - pad, y + box_h), 14, fill=fill, outline=line, width=3)
        ty = y + (8 if kind != "text" and kind != "title" else 0)
        for text, font in rows:
            d.text((pad + indent + 14, ty), text, fill="black", font=font)
            ty += probe.textbbox((0, 0), "Ag", font=font)[3] + 8
    img.save(path)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--show")
    ap.add_argument("--stage")
    ap.add_argument("--sheets")
    a = ap.parse_args(argv)
    try:
        trees, skeletons, rows = load_trees(), load_skeletons(), decision_sources()
    except InputError as exc:
        print(exc, file=sys.stderr)
        return 2
    if a.show:
        if a.show not in skeletons["cells"]:
            print(f"unknown cell {a.show}", file=sys.stderr)
            return 2
        print(show(trees, skeletons, a.show, a.stage))
        return 0
    found = problems(trees, skeletons, rows)
    if found:
        print("\n".join(found))
        return 1
    if a.sheets:
        out = Path(a.sheets)
        if out.exists() and any(out.iterdir()):
            print(f"{out}: output dir must be new or empty", file=sys.stderr)
            return 2
        out.mkdir(parents=True, exist_ok=True)
        for cell in skeletons["cells"]:
            print(render_sheet(trees, skeletons, cell, out / f"{cell}.png"))
        return 0
    stale = []
    for cell in skeletons["cells"]:
        path = ROOT / MD_DIR / f"{cell}.md"
        text = render_md(trees, skeletons, cell)
        if a.render:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        elif not path.is_file() or path.read_text(encoding="utf-8") != text:
            stale.append(f"{path.relative_to(ROOT).as_posix()}: stale, run --render")
    if stale:
        print("\n".join(stale))
        return 1
    print(f"decision trees: {len(skeletons['cells'])} cells clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
