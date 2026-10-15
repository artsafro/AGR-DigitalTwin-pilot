"""One questions file per object (jobs/<object>/questions.md), merged from versioned spec reports.

Pattern: none — a working document of the harness (REVIEW_CHECKLIST Q1: new-case).

Each question keeps a stable id across spec versions. The user's answers are never lost: a row is
matched by kind, levels and wall plus its heights and position within a tolerance (numbers move a
little between versions), its Answer cell is kept, and a question that a newer spec no longer
raises stays in the file as `gone <version>`. A file whose rows cannot be read is never
overwritten. Matching maximizes the number of pairs, then minimizes total height/position drift.
Equally optimal assignments raise an ambiguous-assignment error before any file is written.
Write `\\|` for a pipe inside an answer.
"""
import re

COLUMNS = ["ID", "Status", "First", "Last", "Priority", "Kind", "Levels", "Wall", "Depth m", "Length m",
           "Facade share", "Heights m", "At (x, y)", "Answer"]
INTRO = """Merged by `dt spec merge-questions` from the versioned `<spec>.report.json` files. Each row is
geometry that is not over the full storey height, so it does not change the level contour, or a
wall break that is not a facade opening (user decisions 2026-10-08). Write the answer in the last
column (`\\|` for a pipe); ids are stable across spec versions. Status: open, answered, or
`gone <version>` when a newer spec no longer raises it (answers kept)."""
HEIGHT_TOL_M = 0.02     # the same question when heights move less than this ...
AT_TOL_M = 0.05         # ... and its position less than this
_SPLIT = re.compile(r"(?<!\\)\|")


def _cells(q):
    def show(v, fmt=str):
        return "—" if v is None else fmt(v)
    return {"Priority": q["priority"], "Kind": q["kind"], "Levels": ", ".join(q["levels"]),
            "Wall": show(q["wall"]), "Depth m": show(q["depth_m"]), "Length m": show(q["length_m"]),
            "Facade share": show(q["facade_share"], lambda s: f"{s:.1%}"),
            "Heights m": show(q["heights_m"], lambda h: f"{h[0]:.3f}–{h[1]:.3f}"),
            "At (x, y)": show(q["at"], lambda a: f"{a[0]:.2f}, {a[1]:.2f}")}


def _numbers(text):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text.replace("–", " "))] if text != "—" else []


def parse(text):
    """Title id and rows of a questions file. Raises if a table is present but no row can be read."""
    title = re.search(r"^#\s*Questions\s*[—-]\s*(\S+)", text, re.M)
    rows, table = [], False
    for line in text.splitlines():
        body = line.strip()
        if not body.startswith("|"):
            continue
        inner = body[1:]
        if inner.endswith("|") and not inner.endswith("\\|"):
            inner = inner[:-1]
        cells = [c.strip() for c in _SPLIT.split(inner)]
        if cells and cells[0] == "ID":
            if cells != COLUMNS:                     # an answer is read by its column (review 3 of PR #71)
                raise ValueError(f"questions file header is not {' | '.join(COLUMNS)}; not overwriting")
            table = True
        elif cells and re.fullmatch(r"(?i)q\d+|id", cells[0]) and not table:
            raise ValueError("questions file has question rows without its header row; not overwriting")
        elif all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        elif table and re.fullmatch(r"Q\d+", cells[0]) and len(cells) == len(COLUMNS):
            rows.append(dict(zip(COLUMNS, cells)))
        elif table:
            raise ValueError(f"questions file has an unreadable row ({body[:40]}...); not overwriting")
    return (title.group(1) if title else None), rows


def _same(row, cells):
    if (row["Kind"], row["Levels"], row["Wall"]) != (cells["Kind"], cells["Levels"], cells["Wall"]):
        return None
    h0, h1, a0, a1 = _numbers(row["Heights m"]), _numbers(cells["Heights m"]), _numbers(row["At (x, y)"]), \
        _numbers(cells["At (x, y)"])
    if len(h0) != len(h1) or len(a0) != len(a1):
        return None
    dh = max([abs(x - y) for x, y in zip(h0, h1)] or [0.0])
    da = max([abs(x - y) for x, y in zip(a0, a1)] or [0.0])
    return dh + da if dh <= HEIGHT_TOL_M and da <= AT_TOL_M else None


def _assignment(pairs, excluded=None):
    """Maximum-cardinality, minimum-distance matching by residual augmenting paths."""
    # Only candidate nodes participate; unrelated questions need no graph vertices.
    source, sink = ("source",), ("sink",)
    graph = {source: [], sink: []}

    def edge(a, b, cost):
        graph.setdefault(a, [])
        graph.setdefault(b, [])
        forward = [b, cost, 1, len(graph[b])]
        backward = [a, -cost, 0, len(graph[a])]
        graph[a].append(forward)
        graph[b].append(backward)
        return forward

    candidates = {}
    for k in sorted({k for k, i in pairs}):
        edge(source, ("new", k), 0)
    for i in sorted({i for k, i in pairs}):
        edge(("old", i), sink, 0)
    for (k, i), cost in pairs.items():
        if (k, i) != excluded:
            candidates[k, i] = edge(("new", k), ("old", i), cost)

    while True:
        distance, previous = {source: 0}, {}
        # Reverse edges have negative costs: Bellman-Ford also permits reassignment
        # of earlier pairs, unlike nearest-first matching.
        for _ in range(len(graph) - 1):
            changed = False
            for a, edges in graph.items():
                if a not in distance:
                    continue
                for index, (b, cost, capacity, reverse) in enumerate(edges):
                    if capacity and distance[a] + cost < distance.get(b, float("inf")):
                        distance[b] = distance[a] + cost
                        previous[b] = a, index
                        changed = True
            if not changed:
                break
        if sink not in distance:
            break
        b = sink
        while b != source:
            a, index = previous[b]
            forward = graph[a][index]
            forward[2] -= 1
            graph[b][forward[3]][2] += 1
            b = a

    match = {k: i for (k, i), forward in candidates.items() if not forward[2]}
    return match, sum(pairs[k, i] for k, i in match.items())


def merge(text, spec_id, version, questions):
    """New questions-file text: existing rows updated by this version's questions, new ones appended."""
    if not isinstance(questions, list):
        raise ValueError("the report has no questions list")
    title, rows = parse(text or "")
    if title and title != spec_id:
        raise ValueError(f"questions file belongs to {title}, not {spec_id}; not merging")
    cells = [_cells(q) for q in questions]
    # Heights/positions are serialized to mm/cm. Integer micrometres remove
    # binary-float noise from equal-distance assignments.
    pairs = {(k, i): round(d * 1_000_000) for k, c in enumerate(cells) for i, r in enumerate(rows)
             if (d := _same(r, c)) is not None}
    match, cost = _assignment(pairs)
    # Every different optimum omits at least one selected edge. Forbid each in
    # turn to detect global ties, including ties involving an unmatched question.
    for pair in match.items():
        alternative, other_cost = _assignment(pairs, excluded=pair)
        if len(alternative) == len(match) and other_cost == cost:
            changed = {k for k in match.keys() | alternative.keys() if match.get(k) != alternative.get(k)}
            ids = sorted({rows[m[k]]["ID"] for m in (match, alternative) for k in changed if k in m})
            raise ValueError(f"ambiguous questions assignment for {', '.join(ids)}; not merging")
    seen = set(match.values())
    for k, c in enumerate(cells):
        if k not in match:
            rows.append({"ID": f"Q{len(rows) + 1:03d}", "First": version, "Answer": ""})
            match[k] = len(rows) - 1
            seen.add(match[k])
        rows[match[k]].update(c, Last=version)
    for i, row in enumerate(rows):
        row["Status"] = "answered" if row.get("Answer") else ("open" if i in seen else f"gone {version}")
    lines = [f"# Questions — {spec_id}", "", INTRO, "",
             "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines += ["| " + " | ".join(row.get(c, "") for c in COLUMNS) + " |" for row in rows]
    return "\n".join(lines) + "\n"
