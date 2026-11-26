"""Cold-entry token budget for a worker's first reads (#1015).

new-case: offline guard for the cold-entry read set measured with tiktoken o200k_base.

A cold worker reads AGENTS.md, docs/PROJECT_STATE.md, the card's area file and the
card itself before it starts. ``--write`` measures that set with tiktoken
``o200k_base`` (``uv run --no-project --with tiktoken python tools/state/entry_budget.py
--write``) and stores a receipt with chars and tokens per file. ``check`` runs offline:
each live file's tokens are estimated as ``ceil(tokens * live_chars / receipt_chars)``
(its own measured ratio), and the total must stay <= 10 000. A file that grew by more
than 25 % since the receipt fails with "re-measure". Fail closed on an empty,
partial, duplicated, out-of-tree or non-integer receipt and on a set without
AGENTS.md and docs/PROJECT_STATE.md.

``--cells`` (#1886) measures, for every cell of docs/scenarios/scenarios.json, the files a fresh
agent reads from AGENTS.md to the first command (see the block above ``COMMON``) and, with
``--walkers``, compares them with what the 2026-11-25 hygiene walkers actually read and counts
their contradictory ladder rows on that path. It writes tests/fixtures/cold_entry/cells_baseline.json.
"""
import argparse
import importlib.util
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "tests" / "fixtures" / "cold_entry" / "receipt.json"
TOKENIZER = "tiktoken o200k_base"
BUDGET = 10_000
GROWTH = 0.25
REQUIRED = ("AGENTS.md", "docs/PROJECT_STATE.md")
ENTRY = ("AGENTS.md", "docs/PROJECT_STATE.md", "docs/domain/areas/derivation.md",
         "tests/fixtures/cold_entry/card-t_9e27c5ff.md")
CARD = "t_9e27c5ff (#968 AC08 kernel: invariants relative to the source)"


class FailClosed(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _count(value, name, rel):
    if type(value) is not int or value <= 0:
        raise FailClosed(f"{name} must be a positive integer: {rel}")
    return value


def _resolve(root, rel, seen):
    if not isinstance(rel, str) or rel.strip() == "":
        raise FailClosed("empty path in receipt")
    root = Path(root).resolve()
    path = (root / rel).resolve()
    if path != root and root not in path.parents:
        raise FailClosed(f"path outside the repository: {rel}")
    key = os.path.normcase(str(path))
    if key in seen:
        raise FailClosed(f"duplicate entry file: {rel}")
    seen.add(key)
    return path


def _text(path, rel):
    if not path.is_file():
        raise FailClosed(f"partial: entry file missing: {rel}")
    with path.open(encoding="utf-8", newline="") as source:
        text = source.read().replace("\r\n", "\n")  # checkout line endings must not move the total
    if text.strip() == "":
        raise FailClosed(f"empty entry file: {rel}")
    return text


def _load(receipt):
    receipt = Path(receipt)
    if not receipt.is_file():
        raise FailClosed(f"partial: receipt missing: {receipt}")

    def _reject(token):
        raise FailClosed(f"non-finite value in receipt: {token}")

    try:
        data = json.loads(receipt.read_text(encoding="utf-8"), parse_constant=_reject)
    except ValueError as exc:
        raise FailClosed(f"unsupported receipt: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise FailClosed("unsupported receipt schema")
    if data.get("tokenizer") != TOKENIZER:
        raise FailClosed(f"tokenizer must be {TOKENIZER}")
    if type(data.get("budget")) is not int or data["budget"] != BUDGET:
        raise FailClosed(f"budget must be {BUDGET}")
    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise FailClosed("empty entry set")
    return data, files


def check(root, receipt=RECEIPT, texts=None):
    """Return (rows, total) for the live entry set; raise FailClosed past the budget.

    ``texts`` maps an entry path to candidate text measured instead of the file on disk
    (``project_state.py`` checks its output before writing it, #1222).
    """
    texts = dict(texts or {})
    data, files = _load(receipt)
    seen, rows, measured = set(), [], 0
    for row in files:
        if not isinstance(row, dict):
            raise FailClosed("unsupported receipt row")
        rel = row.get("path")
        path = _resolve(root, rel, seen)
        chars = _count(row.get("chars"), "chars", rel)
        tokens = _count(row.get("tokens"), "tokens", rel)
        measured += tokens
        if rel in texts:
            candidate = texts.pop(rel)
            if not isinstance(candidate, str) or candidate.strip() == "":
                raise FailClosed(f"empty entry file: {rel}")
            live = len(candidate.replace("\r\n", "\n"))
        else:
            live = len(_text(path, rel))
        if live > chars * (1 + GROWTH):
            raise FailClosed(f"{rel} grew {chars} -> {live} chars (> {GROWTH:.0%}); re-measure with --write")
        rows.append({"path": rel, "tokens": tokens, "chars": chars, "live_chars": live,
                     "estimate": math.ceil(tokens * live / chars)})
    if texts:
        raise FailClosed(f"candidate text for a path outside the entry set: {sorted(texts)}")
    names = {row["path"] for row in rows}
    for name in REQUIRED:
        if name not in names:
            raise FailClosed(f"entry set must contain {name}")
    if type(data.get("total_tokens")) is not int or data["total_tokens"] != measured:
        raise FailClosed(f"receipt total_tokens {data.get('total_tokens')!r} != sum {measured}")
    total = sum(row["estimate"] for row in rows)
    if total > BUDGET:
        raise FailClosed(f"over budget: {total} > {BUDGET} tokens ({TOKENIZER})")
    return rows, total


def _tiktoken_counter():
    try:
        import tiktoken
    except ImportError as exc:
        raise FailClosed("tiktoken missing: run with `uv run --no-project --with tiktoken`") from exc
    encoding = tiktoken.get_encoding("o200k_base")
    return lambda text: len(encoding.encode(text))


def write_receipt(root, rels, card, output, counter=None):
    """Measure ``rels`` and write the receipt atomically; never write onto an entry file."""
    counter = counter or _tiktoken_counter()
    seen, files = set(), []
    paths = [_resolve(root, rel, seen) for rel in rels]
    output = Path(output).resolve()
    if os.path.normcase(str(output)) in seen or any(p.exists() and output.exists()
                                                   and os.path.samefile(p, output) for p in paths):
        raise FailClosed(f"receipt path is an entry file: {output}")
    for rel, path in zip(rels, paths):
        text = _text(path, rel)
        files.append({"path": rel, "chars": len(text), "tokens": _count(counter(text), "tokens", rel)})
    data = {"schema": 1, "tokenizer": TOKENIZER, "budget": BUDGET, "card": card,
            "files": files, "total_tokens": sum(row["tokens"] for row in files)}
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    with partial.open("w", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(partial, output)
    return data


# --- per-cell entry path to the first command (#1886) ---------------------------------------
#
# A fresh agent on a production task reads, in this order (AGENTS.md "Any job", "Where things are",
# "Rules for every task"; the `scenario` skill steps 1-3): AGENTS.md, PROJECT_STATE, SKELETONS.md and
# its machine form, the scenario skill, scenarios.json, task-intake (preflight before the first
# command) and the check-level table it sends the agent to at intake (TASK_TO_MODEL.md#check-levels,
# task-intake.md lines 22/39; review r1), then the cell card, the cell `reads`, and the links of the
# card's «Read first» (or
# «Entry») section. NPM/OKS cells add routes/npm-oks.md (AGENTS.md). Ground cells read one stage
# skill (Ground / MAF / Flora), so they split into one target per stage. Links are followed one level
# deep from the card; anything else is listed in `unfollowed` with its reason, never dropped silently.

INTAKE_DOC = "docs/procedure/TASK_TO_MODEL.md"
COMMON = ("AGENTS.md", "docs/PROJECT_STATE.md", "docs/agents/SKELETONS.md", "docs/agents/skeletons.json",
          ".agents/skills/scenario/SKILL.md", "docs/scenarios/scenarios.json", "docs/agents/task-intake.md",
          INTAKE_DOC)
SCENARIOS = "docs/scenarios/scenarios.json"
STAGE_SKILLS = {"ground": ".agents/skills/model-ground/SKILL.md", "maf": ".agents/skills/model-maf/SKILL.md",
                "flora": ".agents/skills/model-flora/SKILL.md"}
NPM_OKS_ROUTE = "routes/npm-oks.md"
# Hygiene walkers of 2026-11-25 (G:/Мой диск/AGR-evidence/hygiene-20261125/w*.json) -> the targets they walked.
WALKERS = {
    "w01-oks-vpm": ["oks-vpm"], "w02-oks-npm": ["oks-npm"], "w03-oks-npm-lite": ["oks-npm-lite"],
    "w04-npm-ground": ["ground-npm:ground"], "w05-npm-maf": ["ground-npm:maf"],
    "w06-npm-flora": ["ground-npm:flora"],
    "w07-vpm-ground-maf-flora": ["ground-vpm:ground", "ground-vpm:maf", "ground-vpm:flora"],
    "w08-vpm-to-npm": ["vpm-to-npm", "npm-to-vpm"], "w09-maf-library-publish": ["maf-npm-to-vpm", "library-publish"],
    "w10-sintez-package": ["sintez-fix"],
}
STATUSES = {"ready", "partial", "missing", "contradictory"}
_SECTION = re.compile(r"^##\s+(Read first|Entry)\b.*$", re.M)
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE = re.compile(r"`([^`\s]+)`")


def _scenarios(root):
    path = Path(root) / SCENARIOS
    if not path.is_file():
        raise FailClosed(f"partial: {SCENARIOS} missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise FailClosed(f"unsupported {SCENARIOS}: {exc}") from exc
    cells = data.get("cells") if isinstance(data, dict) else None
    if not isinstance(cells, list) or not cells:
        raise FailClosed(f"no cells in {SCENARIOS}")
    out = {}
    for cell in cells:
        cid = cell.get("id") if isinstance(cell, dict) else None
        if not isinstance(cid, str) or not cid:
            raise FailClosed(f"cell without id in {SCENARIOS}")
        if cid in out:
            raise FailClosed(f"duplicate cell: {cid}")
        out[cid] = cell
    return out


def _section(text):
    match = _SECTION.search(text)
    if not match:
        return None
    rest = text[match.end():]
    end = re.search(r"^##\s", rest, re.M)
    return rest[:end.start()] if end else rest


def _follow(root, card_rel, ref, linked):
    """Return (repo path, None) or (None, reason) for one reference in the card's entry section."""
    target = ref.split("#", 1)[0]
    if re.match(r"^[a-z]+://", ref):
        return None, "url"
    if any(ch in target for ch in "<>{}*"):
        return None, "placeholder"
    if re.match(r"^[A-Za-z]:[\\/]", target) or target.startswith(("/", "\\")):
        return None, "outside repo"
    if not target:
        return None, "anchor only"
    root = Path(root).resolve()
    bases = [(root / card_rel).parent] if linked else [root, (root / card_rel).parent]
    for base in bases:
        path = (base / target).resolve()
        if path != root and root not in path.parents:
            continue
        if path.is_file():
            return path.relative_to(root).as_posix(), None
        if path.is_dir():
            return None, "directory"
    inside = any(root in (b / target).resolve().parents for b in bases)
    return None, "missing" if inside else "outside repo"


def targets(root):
    """Target ids: every cell, ground cells split per stage skill named in their card."""
    out = []
    for cid, cell in _scenarios(root).items():
        stages = _card_stages(root, cell)
        out.extend(f"{cid}:{stage}" for stage in stages) if len(stages) > 1 else out.append(cid)
    return out


def _card_stages(root, cell):
    card = cell.get("card")
    if not card:
        return []
    path = Path(root) / card
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    section = _section(text) or ""
    return [stage for stage, skill in STAGE_SKILLS.items() if skill.rsplit("/", 2)[-2] in section]


def cell_path(root, cell_id, stage=None):
    """Ordered entry files for a cell (and stage) plus the references the walk could not follow."""
    root = Path(root).resolve()
    cells = _scenarios(root)
    if cell_id not in cells:
        raise FailClosed(f"unknown cell: {cell_id}")
    if stage is not None and stage not in STAGE_SKILLS:
        raise FailClosed(f"unknown stage: {stage}")
    cell = cells[cell_id]
    files, seen, unfollowed = [], set(), []

    def add(rel, origin):
        path = _resolve(root, rel, set())
        if not path.is_file():
            raise FailClosed(f"partial: entry file missing: {rel} (from {origin})")
        rel = path.relative_to(root).as_posix()
        if rel not in seen:
            seen.add(rel)
            files.append(rel)

    for rel in COMMON:
        add(rel, "COMMON")
    card = cell.get("card")
    if cell_id.startswith("oks-npm"):
        add(NPM_OKS_ROUTE, "AGENTS.md: NPM/OKS route")
    if card:
        add(card, SCENARIOS)
    else:
        unfollowed.append({"ref": None, "from": SCENARIOS, "reason": "cell has no card"})
    reads = cell.get("reads") or []
    if not isinstance(reads, list):
        raise FailClosed(f"reads of {cell_id} must be a list")
    for rel in reads:
        add(rel, f"{SCENARIOS} reads")
    sources = [card] if card else []
    if cell_id.startswith("oks-npm") and card != NPM_OKS_ROUTE:
        sources.append(NPM_OKS_ROUTE)
    stages = _card_stages(root, cell)
    if len(stages) > 1 and stage is None:
        raise FailClosed(f"stage required for {cell_id}: one of {stages}")
    if stage is not None and stage not in stages:
        raise FailClosed(f"card of {cell_id} names no skill for stage {stage}")
    skip = {skill for name, skill in STAGE_SKILLS.items() if stage is not None and name != stage}
    for source in sources:
        section = _section(_text(root / source, source))
        if section is None:
            unfollowed.append({"ref": None, "from": source, "reason": "card has no Read first / Entry section"})
            continue
        refs = [(m.start(), m.group(1), True) for m in _LINK.finditer(section)]
        refs += [(m.start(), m.group(1), False) for m in _CODE.finditer(section)
                 if "/" in m.group(1) or "\\" in m.group(1)]
        for _, ref, linked in sorted(refs):
            rel, reason = _follow(root, source, ref, linked)
            if reason:
                unfollowed.append({"ref": ref, "from": source, "reason": reason})
            elif rel not in skip:
                add(rel, source)
    return {"files": files, "unfollowed": unfollowed}


def _sha(commit):
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise FailClosed(f"commit must be a 40-hex sha: {commit!r}")
    return commit


# --- one door (#1895): AGENTS.md -> SKELETONS index -> cell block -> passport/intake -> trail ----------------
#
# The door AGENTS.md prescribes after hygiene batch 3: the index, the printed block of the cell
# (`skeleton_guard.py --show <cell>`, counted as its printed text), task-intake (passport first, D397), the cell's
# `trail` from skeletons.json and, for a site cell, the stage skill. Area sheets and cards are read at the trail
# step that links them, after the first command. A cell without a readable trail fails closed (no default).

DOOR = ("AGENTS.md", "docs/agents/SKELETONS.md")
DOOR_INTAKE = "docs/agents/task-intake.md"


def door_path(root, cell_id, stage=None):
    """Ordered (label, text) of the one-door entry for a cell (and stage); FailClosed on any gap."""
    root = Path(root).resolve()
    guard = root / "tools" / "architecture" / "skeleton_guard.py"
    if not guard.is_file():
        raise FailClosed(f"partial: {guard.relative_to(root).as_posix()} missing (no cell block)")
    spec = importlib.util.spec_from_file_location(f"_skeleton_guard_{abs(hash(str(guard)))}", guard)
    sg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sg)
    if not hasattr(sg, "cell_block"):
        raise FailClosed("unsupported skeleton_guard: no cell_block (tree before #1895)")
    cells = _scenarios(root)
    if cell_id not in cells:
        raise FailClosed(f"unknown cell: {cell_id}")
    stages = _card_stages(root, cells[cell_id])
    if len(stages) > 1 and stage is None:
        raise FailClosed(f"stage required for {cell_id}: one of {stages}")
    if stage is not None and stage not in stages:
        raise FailClosed(f"card of {cell_id} names no skill for stage {stage}")
    try:
        skeletons = sg.load_skeletons(root)
        block = sg.cell_block(root, skeletons, cell_id)
    except (sg.ConfigError, KeyError) as exc:
        raise FailClosed(f"cell block of {cell_id}: {exc}") from exc
    rows = [(rel, _text(root / rel, rel)) for rel in DOOR]
    rows.append((f"skeleton_guard.py --show {cell_id}", block))
    trail = skeletons["cells"][cell_id]["trail"]
    for rel in (DOOR_INTAKE, trail) + ((STAGE_SKILLS[stage],) if stage else ()):
        if rel not in [r[0] for r in rows]:
            rows.append((rel, _text(root / rel, rel)))
    return rows


def measure_door(root, counter, commit):
    """Tokens of the one-door entry per target (same targets as --cells)."""
    commit = _sha(commit)
    root = Path(root).resolve()
    data = {"schema": 1, "kind": "entry_budget_door", "metric": "tokens from AGENTS.md to the first command (one door)",
            "tokenizer": TOKENIZER, "measured_on": commit, "budget": BUDGET, "targets": {}}
    for tid in targets(root):
        cell, _, stage = tid.partition(":")
        rows = [{"path": label, "chars": len(text), "tokens": _count(counter(text), "tokens", label)}
                for label, text in door_path(root, cell, stage or None)]
        total = sum(r["tokens"] for r in rows)
        data["targets"][tid] = {"cell": cell, "stage": stage or None, "files_count": len(rows),
                                "total_tokens": total, "within_budget": total <= BUDGET, "files": rows}
    return data


def measure_cells(root, counter, commit, walkers=None):
    """Measure every target's entry path; attach walker coverage when ``walkers`` is given."""
    commit = _sha(commit)
    root = Path(root).resolve()
    data = {"schema": 1, "kind": "entry_budget_cells", "metric": "tokens from AGENTS.md to the first command",
            "tokenizer": TOKENIZER, "measured_on": commit, "targets": {}}
    for tid in targets(root):
        cell, _, stage = tid.partition(":")
        path = cell_path(root, cell, stage or None)
        rows = []
        for rel in path["files"]:
            text = _text(root / rel, rel)
            rows.append({"path": rel, "chars": len(text), "tokens": _count(counter(text), "tokens", rel)})
        data["targets"][tid] = {"cell": cell, "stage": stage or None, "files_count": len(rows),
                                "total_tokens": sum(r["tokens"] for r in rows), "files": rows,
                                "unfollowed": path["unfollowed"]}
    if walkers is not None:
        data["walkers"] = {}
        for name, (obj, digest) in walkers.items():
            reports = {}
            for tid in WALKERS[name]:
                if tid not in data["targets"]:
                    raise FailClosed(f"walker {name} maps to unknown target {tid}")
                files = [f["path"] for f in data["targets"][tid]["files"]]
                reports[tid] = walker_report(obj, files, root)
            data["walkers"][name] = {"sha256": digest, "targets": reports}
        missing = set(data["targets"]) - {t for w in data["walkers"].values() for t in w["targets"]}
        if missing:
            raise FailClosed(f"targets without a walker: {sorted(missing)}")
    return data


def _rows(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _rows(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _rows(value)


def _norm(entry):
    raw = entry.get("path") or entry.get("file") if isinstance(entry, dict) else entry
    if not isinstance(raw, str) or not raw.strip():
        return None
    token = raw.strip().split()[0].replace("\\", "/").rstrip(",;")
    token = re.sub(r":\d.*$", "", token.split("#", 1)[0])
    return token[2:] if token.startswith("./") else token or None


def walker_report(obj, path_files, root):
    """Classify every doc a walker read against an entry path; count contradictory ladder rows.

    A repo file off the path lands in ``intake_off_path`` when any row with stage "intake" (case and
    surrounding spaces ignored) read it - a pre-command read the path misses - else in ``beyond_path``
    (read only at a later stage). The buckets are disjoint.
    """
    root = Path(root).resolve()
    rows = [r for r in _rows(obj) if "docs_read" in r]
    if not rows:
        raise FailClosed("walker has no docs_read rows")
    on_path = set(path_files)
    buckets = {"on_path": set(), "beyond_path": set(), "outside_repo": set(), "missing": set()}
    intake = set()
    unparsed, contradictory, on, unknown = 0, 0, 0, []
    for row in rows:
        at_intake = isinstance(row.get("stage"), str) and row["stage"].strip().lower() == "intake"
        docs = row["docs_read"] if isinstance(row["docs_read"], list) else [row["docs_read"]]
        names = []
        for entry in docs:
            name = _norm(entry)
            if name is None:
                unparsed += 1
                continue
            names.append(name)
            if re.match(r"^[A-Za-z]:/", name) or name.startswith("/"):
                buckets["outside_repo"].add(name)
                continue
            path = (root / name).resolve()
            if root not in path.parents or not path.exists():
                buckets["missing" if root in path.parents else "outside_repo"].add(name)
            elif path.relative_to(root).as_posix() in on_path:
                buckets["on_path"].add(name)
            else:
                (intake if at_intake else buckets["beyond_path"]).add(name)
        status = row.get("status")
        if status is None:
            continue
        if status not in STATUSES:
            unknown.append(status)
        elif status == "contradictory":
            contradictory += 1
            on += bool(on_path & set(names))
    buckets["beyond_path"] -= intake
    buckets["intake_off_path"] = intake
    return {**{k: sorted(v) for k, v in buckets.items()}, "unparsed": unparsed,
            "contradictory_rows": contradictory, "contradictory_on_path": on, "unknown_status": unknown}


def load_walkers(directory):
    """Read every mapped walker JSON from ``directory``; an unmapped or missing walker fails closed."""
    directory = Path(directory)
    found = {p.stem: p for p in sorted(directory.glob("w*.json"))}
    for name in found:
        if name not in WALKERS:
            raise FailClosed(f"unmapped walker: {name}")
    out = {}
    for name in WALKERS:
        if name not in found:
            raise FailClosed(f"partial: walker missing: {name}")
        raw = found[name].read_bytes()
        try:
            out[name] = (json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest())
        except ValueError as exc:
            raise FailClosed(f"unsupported walker {name}: {exc}") from exc
    return out


def write_cells(root, output, counter, commit, walkers_dir=None):
    """Measure and write the cells baseline atomically; refuse an output that is an input."""
    root = Path(root).resolve()
    output = Path(output).resolve()
    inputs = set()
    for tid in targets(root):
        cell, _, stage = tid.partition(":")
        inputs |= {os.path.normcase(str((root / rel).resolve())) for rel in cell_path(root, cell, stage or None)["files"]}
    if walkers_dir is not None:
        inputs |= {os.path.normcase(str(p.resolve())) for p in Path(walkers_dir).glob("w*.json")}
    if os.path.normcase(str(output)) in inputs:
        raise FailClosed(f"output path is an input: {output}")
    walkers = load_walkers(walkers_dir) if walkers_dir is not None else None
    data = measure_cells(root, counter, commit, walkers)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    with partial.open("w", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(partial, output)
    return data


def write_door(root, output, counter, commit):
    """Measure the one door and write it atomically; refuse an output that is an input."""
    root = Path(root).resolve()
    output = Path(output).resolve()
    inputs = {os.path.normcase(str((root / rel).resolve())) for rel in (*DOOR, DOOR_INTAKE, SCENARIOS,
                                                                       "docs/agents/skeletons.json")}
    if os.path.normcase(str(output)) in inputs or (output.exists() and output.is_dir()):
        raise FailClosed(f"output path is an input: {output}")
    data = measure_door(root, counter, commit)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    with partial.open("w", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(partial, output)
    return data


def _cells_main(args):
    if args.output is None:
        print("entry_budget: --cells needs --output", file=sys.stderr)
        return 2
    root = (args.root or ROOT).resolve()
    commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                            text=True).stdout.strip()
    try:
        if args.door:
            data = write_door(root, args.output, _tiktoken_counter(), commit)
        else:
            data = write_cells(root, args.output, _tiktoken_counter(), commit, args.walkers)
    except FailClosed as exc:
        print(f"entry_budget: {exc.reason}", file=sys.stderr)
        return 1
    for tid, target in data["targets"].items():
        walk = [w["targets"][tid] for w in data.get("walkers", {}).values() if tid in w["targets"]]
        extra = (f"\tcontradictory_on_path {walk[0]['contradictory_on_path']}"
                 f"\tintake_off_path {len(walk[0]['intake_off_path'])}") if walk else ""
        print(f"{tid}\t{target['files_count']} files\t{target['total_tokens']} tokens{extra}")
    print(f"wrote {args.output} (measured on {commit})")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cold-entry token budget (tiktoken o200k_base, <= 10000).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="offline check against the receipt")
    mode.add_argument("--write", action="store_true", help="measure with tiktoken and rewrite the receipt")
    mode.add_argument("--cells", action="store_true", help="measure every scenario cell's entry path (#1886)")
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--root", type=Path, help="--cells: repository to measure (default: this checkout)")
    parser.add_argument("--walkers", type=Path, help="--cells: directory with the hygiene walker w*.json")
    parser.add_argument("--output", type=Path, help="--cells: baseline JSON to write")
    parser.add_argument("--door", action="store_true", help="--cells: measure the one-door entry instead (#1895)")
    args = parser.parse_args(argv)
    if args.door and (not args.cells or args.walkers):
        print("entry_budget: --door needs --cells and takes no --walkers", file=sys.stderr)
        return 2
    if args.cells:
        return _cells_main(args)
    try:
        if args.write:
            data = write_receipt(ROOT, list(ENTRY), CARD, args.receipt)
            print(f"wrote {args.receipt}: {data['total_tokens']} tokens")
        rows, total = check(ROOT, args.receipt)
    except FailClosed as exc:
        print(f"entry_budget: {exc.reason}", file=sys.stderr)
        return 1
    for row in rows:
        print(f"{row['path']}\t{row['estimate']}")
    print(f"total {total} / {BUDGET} tokens ({TOKENIZER})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
