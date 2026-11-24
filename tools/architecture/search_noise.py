"""Agent-search noise (#1614, [D327]): hide historical job data and unlinked docs, measure what search sees.

Pattern: n/a | new-case: generated `.ignore` block for historical job data + unlinked docs, and an rg visibility measure.

A fresh agent searches the repo with ripgrep, which reads the root `.ignore`. #1546 hid the delivered-job scripts
(duplicate_guard's block). This module owns a second generated block:
- historical job DATA: every tracked non-script file of a delivered job (`finished_jobs` of contexts.yaml) except
  the job-root identity files (KEEP_NAMES), paths an open issue still uses (`live_paths` of
  docs/architecture/search-noise.yaml), skeleton.json folders (new work) and files a live surface reaches;
- historical DOCS: every tracked docs/ file that no entry doc, scenario, route, skill or live code reaches.
  Dated plan status overrides visibility. `--check-docs` validates the existing route index's ownership
  table, plan headers and visibility; adding a path to the generated ignore block cannot waive ownership.
"Live surface" (`live_closure`): the entry docs, routes/, docs/scenarios/, .agents/skills/ and the non-test code
(tools/, src/, adapters/, schemas/, standards/), followed transitively through the files they name (markdown links,
`backticked` paths, bare repo paths). Job files are leaves: a delivered job's report keeps nothing else alive.
Nothing is deleted or rewritten; `rg --no-ignore-dot` still finds everything.
Every jobs/<ID> folder must be classified exactly once: delivered (`finished_jobs`) or `kept_jobs` with a reason.
`--move-evidence DEST` moves large data of the hidden set (rule 57) to DEST/<job>/ with a copy-verified sha256,
writes `jobs/<ID>/EVIDENCE-MOVED.json` (path + sha256 + evidence path) and DEST/<job>/SHA256SUMS.txt.
`--measure` reports the files visible to `rg --files` (total, non-test, jobs, job scripts, docs).
"""
import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import duplicate_guard as dg  # noqa: E402
import mini_yaml  # noqa: E402

BEGIN = "# BEGIN historical-data (#1614, [D327]) - generated: search_noise.py --write-ignore"
END = "# END historical-data"
CONFIG = "docs/architecture/search-noise.yaml"
CONTEXTS = "docs/architecture/contexts.yaml"
DOC_INDEX = "docs/architecture/README.md"
DOC_SECTION = "## Documentation ownership"
DOC_TABLE = ("| Topic | Owner | Related |", "|---|---|---|")
DOC_EXEMPT = frozenset({"docs/decisions.md", "docs/PROJECT_STATE.md"})
_INDEX_LINK = re.compile(r"\[[^\]\n]+\]\(([^()\s]+)\)")
_PLAN_STATUS = re.compile(r"(active|done|superseded by (\S+)) \(([0-9]{4}-[0-9]{2}-[0-9]{2})\)")
MANIFEST = "EVIDENCE-MOVED.json"
ENTRY_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md", "GLOSSARY.md", "docs/PROJECT_STATE.md")
ENTRY_DIRS = ("routes/", "docs/scenarios/", ".agents/skills/")
CODE_DIRS = ("tools/", "src/", "adapters/", "schemas/", "standards/")
TEXT_SUFFIXES = (".md", ".json", ".yaml", ".yml", ".txt", ".toml", ".csv") + dg.SCRIPT_SUFFIXES
KEEP_NAMES = frozenset({"STATE.md", "LESSONS.md", "README.md", "TASK.md", "REPORT.md", "PASSPORT.md", "job.yaml",
                        "passport.json", "sources.json", "object.json", "materials.json", "skeleton.json", MANIFEST})
MOVE_MIN_BYTES = 64 * 1024
MOVE_SUFFIXES = (".json", ".txt")
MAX_READ = 4 * 1024 * 1024
_REF = re.compile(r"\]\(<?([^)\s>]+)|`([^`\s]+)`|(?<![\w/.\-])((?:docs|jobs|routes|tools|src|adapters|benchmark|"
                  r"standards|schemas|experiments|test-polygon|library|evals|technical_library)/[\w./@+\-]+)")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def is_test(rel):
    """True for test code and fixtures (tests/, test/, test_*.py, *_test.py, conftest.py)."""
    parts = rel.split("/")
    name = parts[-1]
    return any(p in ("tests", "test") for p in parts[:-1]) or name.startswith("test_") \
        or name.endswith("_test.py") or name == "conftest.py"


def tracked(root):
    """Sorted tracked repo paths (`git ls-files`); not a git work tree is an error (never a filesystem guess)."""
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    if r.returncode != 0:
        raise ValueError(f"{root}: git ls-files failed: {r.stderr.decode('utf-8', 'replace').strip()}")
    files = sorted(p for p in r.stdout.decode("utf-8").split("\0") if p)
    return [p for p in files if (Path(root) / p).is_file()]


def _doc_sections(text):
    return ("\n" + text).partition("\n" + DOC_SECTION + "\n")


def refs(root, rel, fileset, dirs):
    """Tracked files named by `rel`: link targets, backticked and bare repo paths, relative or from the root; a
    named directory keeps its README.md / INDEX.md."""
    path = Path(root) / rel
    if not rel.endswith(TEXT_SUFFIXES) or path.stat().st_size > MAX_READ:
        return set()
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return set()
    if rel == DOC_INDEX:
        # The ownership inventory is a lookup, not a dependency of every route or job.
        text = _doc_sections(text)[0]
    here, out = rel.rsplit("/", 1)[0] if "/" in rel else "", set()
    for m in _REF.finditer(text):
        raw = next(g for g in m.groups() if g).split("#")[0].split("?")[0].strip("'\"").rstrip(".,;:'\"")
        if not raw or "://" in raw:
            continue
        for cand in (os.path.normpath(os.path.join(here, raw)), os.path.normpath(raw.lstrip("/"))):
            cand = cand.replace("\\", "/")
            if cand in fileset:
                out.add(cand)
            elif cand.rstrip("/") in dirs:
                out.update(f"{cand.rstrip('/')}/{n}" for n in ("README.md", "INDEX.md")
                           if f"{cand.rstrip('/')}/{n}" in fileset)
    return out


def live_roots(files):
    """Entry docs, routes, scenarios, skills and the non-test code."""
    return sorted(f for f in files if f in ENTRY_FILES or f.startswith(ENTRY_DIRS)
                  or (f.startswith(CODE_DIRS) and not is_test(f)))


def live_closure(root, files):
    """Every tracked file a live root reaches through named paths. Only roots and reached markdown docs outside
    jobs/ propagate: a reached inventory (yaml/json/txt baseline, context map) or job file is a leaf, so a list of
    every path does not make everything live."""
    fileset = set(files)
    dirs = {f.rsplit("/", i)[0] for f in files for i in range(1, f.count("/") + 1)}
    seen = set(live_roots(files))
    frontier = sorted(seen)
    while frontier:
        nxt = []
        for f in frontier:
            for r in sorted(refs(root, f, fileset, dirs)):
                if r not in seen:
                    seen.add(r)
                    if r.endswith(".md") and not r.startswith("jobs/"):
                        nxt.append(r)
        frontier = nxt
    return seen


def entry_named(root, files):
    """Files named directly by an entry doc, route, scenario or skill (not by code or by a reached doc)."""
    fileset = set(files)
    dirs = {f.rsplit("/", i)[0] for f in files for i in range(1, f.count("/") + 1)}
    out = set()
    for f in files:
        if f in ENTRY_FILES or f.startswith(ENTRY_DIRS):
            out |= refs(root, f, fileset, dirs)
    return out


def load_config(root, files):
    """Read kept jobs, live paths and the exact legacy doc exemption cut."""
    cfg = mini_yaml.load(Path(root) / CONFIG)
    if not isinstance(cfg, dict):
        raise ValueError(f"{CONFIG}: expected a mapping")
    unknown = set(cfg) - {"kept_jobs", "live_paths", "legacy_hidden_docs"}
    if unknown:
        raise ValueError(f"{CONFIG}: unknown keys {sorted(unknown)}")
    kept, parts = {}, {}
    for i, e in enumerate(cfg.get("kept_jobs") or []):
        job, ru = str(e.get("job", "")), str(e.get("ru", "")).strip()
        if not re.match(r"^jobs/[^/]+$", job) or not ru:
            raise ValueError(f"{CONFIG}: kept_jobs[{i}] needs job: jobs/<folder> and ru")
        if job in kept:
            raise ValueError(f"{CONFIG}: kept_jobs {job} listed twice")
        kept[job] = ru
    for i, e in enumerate(cfg.get("live_paths") or []):
        path, ru = str(e.get("path", "")).rstrip("/"), str(e.get("ru", "")).strip()
        if not re.match(r"^(jobs|docs)/[^/]+(/[^/]+)*$", path) or ".." in path.split("/") or not ru:
            raise ValueError(f"{CONFIG}: live_paths[{i}] needs path: jobs/... or docs/... and ru")
        if path in parts:
            raise ValueError(f"{CONFIG}: live_paths {path} listed twice")
        if path not in files and not any(f.startswith(path + "/") for f in files):
            raise ValueError(f"{CONFIG}: live_paths {path} holds no tracked file")
        parts[path] = ru
    legacy = cfg.get("legacy_hidden_docs", [])
    if (not isinstance(legacy, list)
            or any(not isinstance(p, str) or not p.startswith("docs/") or "\\" in p
                   or posixpath.normpath(p) != p for p in legacy)
            or len(set(legacy)) != len(legacy)):
        raise ValueError(f"{CONFIG}: legacy_hidden_docs must list unique canonical docs paths")
    return kept, parts, set(legacy)


def job_folders(files):
    return sorted({"/".join(f.split("/")[:2]) for f in files if f.startswith("jobs/") and f.count("/") >= 2})


def classification_problems(files, finished, kept, parts):
    """Every jobs/<ID> folder is delivered xor kept; a live part lies inside a delivered job."""
    out = []
    for job in job_folders(files):
        if job in finished and job in kept:
            out.append(f"{job}: both delivered (finished_jobs) and kept_jobs; pick one")
        elif job not in finished and job not in kept:
            out.append(f"{job}: unclassified; add it to finished_jobs ({CONTEXTS}) or kept_jobs ({CONFIG})")
    for job in sorted(set(kept) - set(job_folders(files))):
        out.append(f"{CONFIG}: kept_jobs {job} holds no tracked file")
    for path in sorted(parts):
        if path.startswith("jobs/") and "/".join(path.split("/")[:2]) not in finished:
            out.append(f"{CONFIG}: live_paths {path} is not inside a delivered job (finished_jobs)")
    return out


def under(f, paths):
    """True when f is one of the paths or inside one of them."""
    return any(f == p or f.startswith(p + "/") for p in paths)


def historical_job_data(root, files, finished, parts, live):
    """Hidden non-script files of the delivered jobs (scripts belong to duplicate_guard's block)."""
    out = []
    for f in files:
        job = "/".join(f.split("/")[:2])
        if job not in finished or f.lower().endswith(dg.SCRIPT_SUFFIXES) or f in live or f.rsplit("/", 1)[1][:1] == ".":
            continue
        if f.count("/") == 2 and f.rsplit("/", 1)[1] in KEEP_NAMES:
            continue
        if under(f, parts) or dg.in_skeleton_job(root, f):
            continue
        out.append(f)
    return out


def historical_docs(files, live, parts=()):
    return [f for f in files if f.startswith("docs/") and f not in live and not is_test(f) and not under(f, parts)]


def _is_plan(rel):
    name = posixpath.basename(rel)
    return (rel == "docs/backlog.md" or rel.startswith("docs/plans/")
            or (rel.startswith("docs/research/") and "roadmap" in name.lower()))


def _json_pairs(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise ValueError("duplicate JSON keys")
    return obj


def plan_statuses(root, files):
    """Read each plan once; malformed or unsupported plans are named rather than treated as inactive."""
    statuses, successors, problems = {}, {}, []
    fileset = set(files)
    for rel in files:
        if not _is_plan(rel):
            continue
        try:
            path = root / rel
            if path.suffix == ".md":
                lines = path.read_text(encoding="utf-8").splitlines()
                headers = [line for line in lines if line.strip()]
                if (len(headers) < 2 or not headers[0].startswith("# ")
                        or not headers[1].startswith("Status: ")
                        or (len(headers) > 2 and headers[2].startswith("Status:"))):
                    raise ValueError("expected one Status header after the title")
                raw = headers[1].removeprefix("Status: ")
            elif path.suffix == ".json":
                obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_pairs)
                if not isinstance(obj, dict) or not all(isinstance(obj.get(k), str) for k in ("status", "status_date")):
                    raise ValueError("expected string status and status_date fields")
                raw = f"{obj['status']} ({obj['status_date']})"
            else:
                raise ValueError("expected a Markdown or JSON plan")
            match = _PLAN_STATUS.fullmatch(raw)
            if not match:
                raise ValueError("expected active, done or superseded by <repo path>, followed by (YYYY-MM-DD)")
            status, successor, day = match.groups()
            date.fromisoformat(day)
            if successor and (successor == rel or successor not in fileset):
                raise ValueError(f"replacement {successor} must be a different canonical tracked path")
            if successor:
                successors[rel] = successor
            statuses[rel] = status
        except (OSError, ValueError) as exc:
            problems.append(f"{rel}: invalid plan status ({exc})")
    seen = set()
    for rel in successors:
        chain = {}
        current = rel
        while current in successors and current not in seen:
            if current in chain:
                loop = list(chain)[chain[current]:]
                problems.append(f"{current}: cyclic plan replacements: {' -> '.join([*loop, current])}")
                break
            chain[current] = len(chain)
            current = successors[current]
        seen.update(chain)
    return statuses, problems


def _ownership_rows(root, files):
    """Read the final ownership table in the existing route index, or reject its exact malformed locator."""
    path = root / DOC_INDEX
    text = path.read_text(encoding="utf-8") if DOC_INDEX in files else ""
    before, marker, section = _doc_sections(text)
    if not marker or DOC_SECTION in before.splitlines() or DOC_SECTION in section.splitlines():
        return {}, [f"{DOC_INDEX}: missing ownership table or duplicate heading"]
    lines = [line for line in section.splitlines() if line.strip()]
    if tuple(lines[:2]) != DOC_TABLE or len(lines) < 3:
        return {}, [f"{DOC_INDEX}: empty ownership table or invalid columns"]
    indexed, topics, problems = {}, set(), []
    parent = posixpath.dirname(DOC_INDEX)
    for line in lines[2:]:
        row = re.fullmatch(r"\| ([a-z0-9][a-z0-9/-]*) \| (.+?) \|(.*?)\|", line)
        if not row:
            problems.append(f"{DOC_INDEX}: malformed ownership row: {line}")
            continue
        topic, owner, related = row.groups()
        cells = [owner, *related.strip().split(", ")] if related.strip() else [owner]
        if topic in topics:
            problems.append(f"{DOC_INDEX}: duplicate topic {topic}")
        topics.add(topic)
        paths = []
        for cell in cells:
            link = _INDEX_LINK.fullmatch(cell)
            if not link:
                problems.append(f"{DOC_INDEX}: malformed ownership row for {topic}: {cell}")
                paths.append(None)
                continue
            raw = link[1]
            rel = posixpath.normpath(posixpath.join(parent, raw))
            if not rel.startswith("docs/") or rel not in files or posixpath.relpath(rel, parent) != raw:
                problems.append(f"{DOC_INDEX}: {raw}: not a canonical tracked docs path")
                paths.append(None)
            else:
                paths.append(rel)
        if paths[0]:
            for rel in filter(None, paths):
                if rel in indexed:
                    problems.append(f"{rel}: multiple ownership rows")
                indexed[rel] = paths[0]
    return indexed, problems


def generated_doc(rel, files):
    """Route-map views belong to their tracked YAML source, not to a second owner row."""
    route = re.fullmatch(r"(docs/architecture/[^/]+-route)(?:-owners\.md|(?:-scheme)?\.(?:svg|excalidraw))", rel)
    if route:
        return route[1] + ".events.yaml" in files
    context = re.fullmatch(r"(docs/architecture/(?:[^/]+-)?contexts)\.(?:svg|excalidraw)", rel)
    return bool(context and context[1] + ".yaml" in files)


def docs_problems(root, st):
    """Require an owner row or indexed companion with a direct owner reference, not just an ignore entry."""
    files = set(st["files"])
    indexed, problems = _ownership_rows(root, files)
    problems.extend(st["plan_problems"])
    ignore = root / ".ignore"
    block = _parts(ignore.read_text(encoding="utf-8")) if ignore.is_file() else None
    hidden = set(block[1].splitlines()) if block else set()
    legacy = {f for f in st["legacy_docs"] & set(st["docs"]) if not _is_plan(f) and _pattern(f) in hidden}
    for rel in sorted(files - indexed.keys() - legacy - DOC_EXEMPT):
        if rel.startswith("docs/") and not generated_doc(rel, files):
            problems.append(f"{rel}: missing ownership row in {DOC_INDEX}")
    for rel, owner in indexed.items():
        if rel != owner and owner not in refs(root, rel, files, set()):
            problems.append(f"{rel}: must link to owner {owner}")
    for rel, status in st["statuses"].items():
        if (_pattern(rel) in hidden) != (status != "active"):
            problems.append(f"{rel}: plan visibility does not match status; run search_noise.py --write-ignore")
    return problems


def _pattern(rel):
    return "/" + dg.GLOB_CHARS.sub(r"\\\1", rel).replace(" ", "\\ ")


def render_block(data, docs):
    lines, job = [BEGIN], None
    for rel in data:
        this = "/".join(rel.split("/")[:2])
        if this != job:
            job = this
            lines.append(f"# HISTORICAL [D327] {job}: data of a delivered job (#1614); files unchanged, hidden from "
                         "agent search")
        lines.append(_pattern(rel))
    if docs:
        lines.append("# HISTORICAL [D327] docs: unreached docs (#1614) and inactive plans (#1856); hidden from agent search")
        lines.extend(_pattern(rel) for rel in docs)
    lines.append(END)
    return "\n".join(lines) + "\n"


def _parts(text):
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        return None
    head, rest = text.split(BEGIN, 1)
    block, tail = rest.split(END, 1)
    return head, BEGIN + block + END + "\n", tail[1:] if tail.startswith("\n") else tail


def block_problems(root, data, docs):
    path = Path(root) / ".ignore"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    parts = _parts(text)
    if parts is None:
        return [f".ignore: no single historical-data block ({len(data)} data files, {len(docs)} docs unhidden); "
                "run search_noise.py --write-ignore"]
    want = render_block(data, docs)
    if parts[1] == want:
        return []
    have = {ln for ln in parts[1].splitlines() if ln.startswith("/")}
    need = {ln for ln in want.splitlines() if ln.startswith("/")}
    if have - need:
        return [f".ignore: historical-data block hides live or gone paths {sorted(have - need)[:5]} "
                f"({len(have - need)}); run search_noise.py --write-ignore"]
    return []


def pending(root, data, docs):
    """Historical paths not yet in the block: a new unreached doc or new job data stays visible (never hidden by
    surprise) until the next --write-ignore; reported, not a failure."""
    path = Path(root) / ".ignore"
    parts = _parts(path.read_text(encoding="utf-8")) if path.is_file() else None
    have = {ln for ln in parts[1].splitlines() if ln.startswith("/")} if parts else set()
    return sorted(ln for ln in render_block(data, docs).splitlines() if ln.startswith("/") and ln not in have)


def write_block(root, data, docs):
    path = Path(root) / ".ignore"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    parts = _parts(text)
    if parts is None and (BEGIN in text or END in text):
        raise ValueError(".ignore: broken historical-data block (BEGIN/END); fix it by hand")
    head, _, tail = parts or (text + ("\n" if text and not text.endswith("\n") else ""), "", "")
    tmp = path.with_name(".ignore.partial")
    tmp.write_text(head + render_block(data, docs) + tail, encoding="utf-8", newline="\n")
    tmp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_problems(root, files):
    """Each EVIDENCE-MOVED.json: well-formed rows of its own job whose repo copy is gone."""
    out = []
    for m in (f for f in files if f.count("/") == 2 and f.endswith("/" + MANIFEST)):
        job = m.rsplit("/", 1)[0]
        try:
            rows = json.loads((Path(root) / m).read_text(encoding="utf-8"))["files"]
        except (ValueError, KeyError, TypeError) as exc:
            out.append(f"{m}: unreadable manifest ({exc})")
            continue
        seen = set()
        for i, r in enumerate(rows):
            p = str(r.get("path", "")) if isinstance(r, dict) else ""
            if not p.startswith(job + "/") or ".." in p.split("/") or not _SHA.match(str(r.get("sha256", ""))) \
                    or not str(r.get("evidence", "")) or not isinstance(r.get("bytes"), int):
                out.append(f"{m}: row {i} needs path inside {job}, sha256, bytes and evidence")
            elif p in seen:
                out.append(f"{m}: {p} listed twice")
            elif (Path(root) / p).exists():
                out.append(f"{m}: {p} is listed as moved but is still in the repo")
            seen.add(p)
    return out


def move_candidates(root, files, data):
    """Large JSON/TXT files of the hidden data that no tracked non-test file outside their job names: by repo path,
    by path inside the job, or by file name when that name is unique in the repo. Tests that read a moved file go
    through `evidence_path` (repo copy, else the verified evidence copy, else skip)."""
    big = [f for f in data if f.lower().endswith(MOVE_SUFFIXES) and (Path(root) / f).stat().st_size >= MOVE_MIN_BYTES]
    counts = {}
    for f in files:
        counts[f.rsplit("/", 1)[-1]] = counts.get(f.rsplit("/", 1)[-1], 0) + 1
    keys = {f: [f, f.split("/", 2)[2]] + ([f.rsplit("/", 1)[1]] if counts[f.rsplit("/", 1)[1]] == 1 else [])
            for f in big}
    hits = {f: [] for f in big}
    for other in files:
        if is_test(other) or not other.endswith(TEXT_SUFFIXES) or (Path(root) / other).stat().st_size > MAX_READ:
            continue
        try:
            text = (Path(root) / other).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for f in big:
            if not other.startswith("/".join(f.split("/")[:2]) + "/") and any(k in text for k in keys[f]):
                hits[f].append(other)
    return [f for f in big if not hits[f]], {f: v for f, v in hits.items() if v}


def move_evidence(root, files, rels, dest):
    """Copy each file to DEST/<job>/<path in job>, verify sha256, record it in the job manifest and SHA256SUMS.txt,
    then remove the repo copy. A destination inside the repo or an existing copy with other bytes is an error and
    nothing is moved."""
    root, dest = Path(root).resolve(), Path(dest).resolve()
    if dest == root or root in dest.parents or dest in root.parents:
        raise ValueError(f"evidence destination {dest} overlaps the repo {root}")
    plan = []
    if len(set(rels)) != len(rels):
        raise ValueError(f"evidence move: duplicated input {sorted({r for r in rels if rels.count(r) > 1})}")
    for rel in rels:
        if rel not in files or not rel.startswith("jobs/") or rel.count("/") < 2:
            raise ValueError(f"{rel}: not a tracked job file")
        src = root / rel
        job_id, inner = rel.split("/")[1], rel.split("/", 2)[2]
        dst = dest / job_id / inner
        digest = sha256(src)
        if dst.exists() and sha256(dst) != digest:
            raise ValueError(f"{dst}: exists with other bytes than {rel}; nothing moved")
        plan.append((rel, src, dst, digest))
    for rel, src, dst, digest in plan:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            tmp = dst.with_name(dst.name + ".partial")
            shutil.copyfile(src, tmp)
            tmp.replace(dst)
        if sha256(dst) != digest:
            raise ValueError(f"{dst}: copy does not match {rel}; repo copy kept")
    by_job = {}
    for rel, src, dst, digest in plan:
        by_job.setdefault(rel.split("/")[1], []).append(
            {"path": rel, "sha256": digest, "bytes": src.stat().st_size, "evidence": dst.as_posix()})
    for job_id, rows in by_job.items():
        mpath = root / "jobs" / job_id / MANIFEST
        old = json.loads(mpath.read_text(encoding="utf-8"))["files"] if mpath.is_file() else []
        merged = {r["path"]: r for r in old + rows}
        doc = {"issue": "#1614", "rule": "COORDINATION_RULES 57: job data lives in the evidence store",
               "evidence_root": (dest / job_id).as_posix(), "files": [merged[k] for k in sorted(merged)]}
        mpath.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        sums = dest / job_id / "SHA256SUMS.txt"
        lines = dict(ln.split("  ", 1)[::-1] for ln in sums.read_text(encoding="utf-8").splitlines() if "  " in ln) \
            if sums.is_file() else {}
        for r in rows:
            lines[r["path"].split("/", 2)[2]] = r["sha256"]
        sums.write_text("".join(f"{h}  {p}\n" for p, h in sorted(lines.items())), encoding="utf-8", newline="\n")
    for rel, src, dst, digest in plan:
        src.unlink()
    return [r for rows in by_job.values() for r in rows]


def evidence_path(root, rel):
    """Path to read a job file: the repo copy, else its evidence-store copy when the job manifest lists it and the
    sha256 matches, else None (callers skip). A listed copy with other bytes is an error, never a silent read."""
    p = Path(root) / rel
    if p.is_file():
        return p
    mpath = Path(root) / "/".join(rel.split("/")[:2]) / MANIFEST
    if not mpath.is_file():
        return None
    row = next((r for r in json.loads(mpath.read_text(encoding="utf-8"))["files"] if r.get("path") == rel), None)
    if row is None:
        return None
    ev = Path(row["evidence"])
    if not ev.is_file():
        return None
    if sha256(ev) != row["sha256"]:
        raise ValueError(f"{rel}: evidence copy {ev} sha256 differs from {MANIFEST}")
    return ev


def verify_evidence(root, files):
    """Every manifest row has its evidence copy with the recorded sha256 (missing store -> listed, never a pass)."""
    out, n = [], 0
    for m in (f for f in files if f.count("/") == 2 and f.endswith("/" + MANIFEST)):
        for r in json.loads((Path(root) / m).read_text(encoding="utf-8"))["files"]:
            n += 1
            ev = Path(r["evidence"])
            if not ev.is_file():
                out.append(f"{r['path']}: evidence copy {ev} missing")
            elif sha256(ev) != r["sha256"]:
                out.append(f"{r['path']}: evidence copy {ev} sha256 differs")
    return n, out


def measure(root):
    """Files `rg --files` lists from the root (what agent search sees)."""
    rg = shutil.which("rg")
    if rg is None:
        raise ValueError("ripgrep (rg) not on PATH: cannot measure agent search")
    r = subprocess.run([rg, "--files", "--path-separator", "/"], cwd=root, capture_output=True)
    if r.returncode not in (0, 1):
        raise ValueError(f"rg --files failed ({r.returncode}): {r.stderr.decode('utf-8', 'replace').strip()}")
    vis = [ln for ln in r.stdout.decode("utf-8").splitlines() if ln]
    non_test = [f for f in vis if not is_test(f)]
    jobs = [f for f in vis if f.startswith("jobs/")]
    return {"visible": len(vis), "visible_non_test": len(non_test), "jobs_visible": len(jobs),
            "job_scripts_visible": len([f for f in jobs if f.lower().endswith(dg.SCRIPT_SUFFIXES)]),
            "docs_visible": len([f for f in vis if f.startswith("docs/")]),
            "scripts_visible_non_test": len([f for f in non_test if f.lower().endswith(dg.SCRIPT_SUFFIXES)])}


def state(root):
    files = tracked(root)
    contexts = mini_yaml.load(Path(root) / CONTEXTS)
    finished = dg.finished_jobs(root, contexts)
    kept, parts, legacy = load_config(root, files)
    live = live_closure(root, files)
    statuses, plan_problems = plan_statuses(root, files)
    live.update(rel for rel, status in statuses.items() if status == "active")
    inactive = {rel for rel, status in statuses.items() if status != "active"}
    live.difference_update(inactive)
    data = historical_job_data(root, files, finished, parts, live)
    return {"files": files, "contexts": contexts, "finished": finished, "kept": kept, "parts": parts, "live": live,
            "data": data, "docs": sorted(set(historical_docs(files, live, parts)) | inactive),
            "legacy_docs": legacy, "statuses": statuses, "plan_problems": plan_problems}


def hidden_scripts_per_job(root):
    """Counts of the duplicate_guard historical-job-scripts block of .ignore, per job."""
    path = Path(root) / ".ignore"
    parts = dg._ignore_parts(path.read_text(encoding="utf-8")) if path.is_file() else None
    out = {}
    for ln in (parts[1].splitlines() if parts else []):
        if ln.startswith("/jobs/"):
            job = "/".join(ln[1:].split("/")[:2])
            out[job] = out.get(job, 0) + 1
    return out


def table(st, root):
    """Russian table: every job folder, its class and reason; hidden script/data counts per delivered job."""
    hidden, scripts = {}, hidden_scripts_per_job(root)
    for f in st["data"]:
        hidden["/".join(f.split("/")[:2])] = hidden.get("/".join(f.split("/")[:2]), 0) + 1
    rows = ["| Работа | Класс | Причина | Скрыто скриптов / данных |", "|---|---|---|---|"]
    ev = {str(j.get("job")): (str(j.get("evidence")), str(j.get("match"))) for j in st["contexts"]["finished_jobs"]}
    for job in job_folders(st["files"]):
        if job in st["finished"]:
            e, m = ev[job]
            live = [f"`{p}` — {ru}" for p, ru in st["parts"].items() if p == job or p.startswith(job + "/")]
            why = f"сдана: `{e}` содержит «{m}»" + ("; видимы: " + "; ".join(live) if live else "")
            rows.append(f"| `{job}` | историческая | {why} | {scripts.get(job, 0)} / {hidden.get(job, 0)} |")
        else:
            rows.append(f"| `{job}` | живая/оставлена | {st['kept'].get(job, 'НЕ КЛАССИФИЦИРОВАНА')} | 0 / 0 |")
    return "\n".join(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Agent-search noise (#1614): historical data/docs block + measure")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--check-docs", action="store_true", help="check doc ownership, plan headers and plan visibility")
    ap.add_argument("--write-ignore", action="store_true", help="regenerate the historical-data block of .ignore")
    ap.add_argument("--measure", action="store_true", help="print the files visible to rg --files (JSON)")
    ap.add_argument("--table", action="store_true", help="print the Russian job classification table")
    ap.add_argument("--candidates", action="store_true", help="print the large hidden data files to move (JSON)")
    ap.add_argument("--move-evidence", type=Path, metavar="DEST", help="move the candidates to DEST/<job>/")
    ap.add_argument("--verify-evidence", action="store_true", help="check every manifest row against its copy")
    args = ap.parse_args(argv)
    try:
        if args.check_docs:
            if args.write_ignore or args.move_evidence:
                raise ValueError("--check-docs is read-only; run write options separately")
            problems = docs_problems(args.root, state(args.root))
            for problem in problems:
                print(f"PROBLEM {problem}")
            print(f"search_noise docs: {len(problems)} problems")
            return 1 if problems else 0
        if args.measure:
            print(json.dumps(measure(args.root), indent=1))
            return 0
        st = state(args.root)
        if args.candidates or args.move_evidence:
            move, kept = move_candidates(args.root, st["files"], st["data"])
            if args.candidates:
                print(json.dumps({"move": move, "kept_named_elsewhere": kept}, indent=1, ensure_ascii=False))
            if args.move_evidence:
                rows = move_evidence(args.root, st["files"], move, args.move_evidence)
                print(f"moved {len(rows)} files to {args.move_evidence}")
                st = state(args.root)
        if args.verify_evidence:
            n, bad = verify_evidence(args.root, st["files"])
            for p in bad:
                print(f"EVIDENCE {p}")
            print(f"evidence: {n - len(bad)}/{n} copies verified")
            if bad or n == 0:
                return 1
        if args.write_ignore:
            write_block(args.root, st["data"], st["docs"])
        if args.table:
            print(table(st, args.root))
        problems = classification_problems(st["files"], st["finished"], st["kept"], st["parts"]) \
            + block_problems(args.root, st["data"], st["docs"]) + manifest_problems(args.root, st["files"])
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"PROBLEM {p}")
    print(f"search_noise: {len(st['data'])} historical data files, {len(st['docs'])} historical docs, "
          f"{len(pending(args.root, st['data'], st['docs']))} pending (visible until --write-ignore), "
          f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
