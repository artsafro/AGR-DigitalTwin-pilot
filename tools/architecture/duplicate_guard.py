"""Duplicate guard (#1359): owned domain functions must not be re-implemented outside their owner.

Pattern: n/a | new-case: AST guard against job-local copies of owned functions (UDIM tile, delivery ZIP).

Rules (stdlib `ast`, no imports of the scanned code):
- `udim-tile`  owner adapters/max/agr_tools/udimtile_core.py (#1337). Flags the UDIM formula itself:
  an addition chain holding the constant 1001 and a `* 10` term (`1001 + u + 10 * v`), and the inverse
  `(tile - 1001) % 10` / `// 10` / `divmod(tile - 1001, 10)` / `i = tile - 1001` then `i % 10` or `i // 10`.
  1001 and 10 also match a name bound to that int anywhere in the file (`FIRST_UDIM = 1001`, `U = 10`), and any
  job-local `def` named udim_tile / udim_of_cell / tile_origin / face_tile is a copy (PR #1368 r1).
  #1370/#1482 also flag single-row `floor(u) + 1001`, `int(u) + 1001`, `u // 1 + 1001`,
  `[tile - 1001, 0]` or `(tile - 1001, 0.0)` origins, and `x - (tile - 1001)` local coordinates.
  Literal integer leaves and names with a single recorded integer value can sum to a split base
  (`A = 1000; A + 1 + u + 10*v`). Bare `1001 + u` and `tile - 1001` remain non-copy controls.
- `delivery-zip`  owner adapters/max/agr_tools/package_core.py (`_write_zip`, #1361/#1377): the one ZIP writer
  behind `agr package-npm` / `agr package-vpm` (tools/derive facades) and AGR Tools. Flags any other writer:
  `zipfile.ZipFile(..., "w" | "x" | "a")` (mode positional or keyword; a computed mode fails closed), including
  `from zipfile import ZipFile as Z` aliases anywhere in the file. #1370 includes `shutil.make_archive(..., 'zip')`
  and its from-import aliases; computed/missing formats fail closed, literal non-ZIP formats are not copies. Every
  delivery-zip allowlist row must say why it stays (`ru`): a historical delivery of a finished job (never rewritten)
  or an archive that is not a delivery package (MZP, benchmark, checker research, dev bundle).
- `blender-launch`  owner src/dt_ai/core/blender_runner.py (`blender_command` / `run_blender`, #1378): the one
  headless Blender launch (pinned executable, --factory-startup --disable-autoexec, isolated user config, fresh
  evidence). Flags any other Blender command line: a list/tuple display holding a headless flag (`--background`,
  `-b`) and a script flag (`--python`, `-P`, `--python-expr`, `--python-text`) as string constants, or one string
  (also an f-string part) holding both as words. Docstrings and bare string statements are not launches. Every
  blender-launch row must say why it stays (`ru`).
- `sintez-checker`  owner tools/blender/sintez_checker.py (#1379): the one launch of SINTEZ AGR Checker 1.6.1 inside
  Blender, behind `agr checker` (tools/qa/sintez_checker.py). Flags any other call of the checker entry point
  `calculate_all_checks` (attribute or bare name). Every row must say why it stays (`ru`).
- `master-qa`  owner tools/blender/qa_master.py (#1379): the one Blender master-geometry QA (quads, quad size, T-junctions,
  open edges, flipped normals). Flags any other `def world_bm` (its helper name). Every row must say why it stays.
- `vpm-uv` owner tools/blender/vpm_uv.py (#1380): shared Blender periodic VPM UV + edge-ring slicer;
  flags definitions named pack_uv / texel_cut under jobs/ + tools/ + src/. This is not the gated NPM atlas
  owner migration (#1141). KPP1/TEC26 are import shims; PSU275 imports the shared owner directly.
- `seam-seal`  owner tools/blender/seam_seal.py (#1381): the one Blender seam seal (weld + T-junction ring splits, quads
  only; moved from jobs/KPP1/scripts/seal.py, now an import shim). Flags any other `def seal` / `def ring_split` /
  `def t_junctions` (its function names). Every row must say why it stays.
- `site-placement` owner src/dt_ai/placement/site.py (#1407, [D329]): the one site placement run (`dt place site` /
  `agr place`, NPM + VPM at the same points [D293]). Flags any other `engine.place(...)` call, or a bare `place(...)`
  imported from dt_ai.placement.engine. Every row must say why it stays (`ru`).
- `window-generator` owner adapters/max/agr_tools/windowgen_core.py (#1405): definitions named build_type or
  assign_glass under jobs/ + tools/ + src/ are refused; imports/calls remain valid. No legacy copies are allowlisted.
The owner file of a rule is never a copy of that rule.

Guarded scope per rule (GUARDED): `udim-tile` jobs/ + tools/ + src/ (#1376: the live NPM-route copies in tools/
and src/ now call the owner); `delivery-zip` jobs/ + tools/ + src/ (#1377: owner settled); `blender-launch`,
`sintez-checker`, `master-qa`, `seam-seal` jobs/ + tools/ + src/ from the start (#1378, #1379, #1381). Each guarded
folder must exist (a missing one is an error, not an empty pass).
The allowlist is the rule-tagged `duplicates` of docs/architecture/contexts.yaml: every finding in a guarded scope
must be listed there with an issue reference, and every listed row (also the documented copies outside the guarded
scope, e.g. the Max cores under adapters/) must still be found (no stale rows). A row is keyed by `at: "path.py::qualname"` - the file and the enclosing function/class
(`<module>` at top level), never by a bare line number (#1387): lines inserted above or inside the function do not
make it NEW or STALE. Optional `hash:` (10 hex, `sha1(ast.unparse(node))`, printed with every NEW COPY) pins the
copies with that text inside the function; a row without it matches every copy of that rule in that function.
Optional `count:` (integer >= 1, default 1, #1396) is how many matching copies the row covers: more matching copies
than `count` -> the extra ones (last by position) are NEW COPY (an identical paste into the same function is red);
fewer -> the row is STALE. Two copies on one line are two findings (`col`).
Usage: python tools/architecture/duplicate_guard.py [--root REPO] [--json] [--table] [--copies-only]; exit 0 clean,
1 violations, 2 unreadable input (a file that does not parse is an error naming it, never skipped).

Status (#1424): every `duplicates` row of every context map (route_map.context_maps) carries `status`
live-bypass | wrapper | historical | own-duty, checked against the real call chains (call_chains.py): a live-bypass
must be reached by a live command/route, must not call its owner and must be in LIVE_BYPASS_BASELINE (a NEW one
fails, a fixed one must leave the baseline); a wrapper must call its owner (for a rule in POLICY_NAMES: one of
its policy functions); a historical row must have no live chain
and sit in a `finished_jobs` folder of contexts.yaml; own-duty needs a Russian `why`, and an own-duty row a live
command/route reaches must be in OWN_DUTY_BASELINE (#1429: same NEW/FIXED ratchet). `--table` prints the Russian
«живые обходы по областям» table and the compaction order (docs/architecture/report-1424.md). `--copies-only`
runs only the copy scan (synthetic test roots without the maps).

Historical class (#1546, [D327]): `historical_scripts` = scripts of a `finished_jobs` folder that are listed in the
frozen baseline docs/agents/job_scripts_baseline.txt, sit outside any skeleton.json folder and that no live chain
reaches (and no entrypoint names as evidence); a script added later is never historical. They are still scanned
above; the root `.ignore` holds one generated block
(`--write-ignore`) with a HISTORICAL header line per job that hides them from agent search (ripgrep). A missing,
stale or extra entry (a live script hidden) is a STATUS problem.
"""
import argparse
import ast
import hashlib
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mini_yaml  # noqa: E402
else:
    from . import mini_yaml

RULES = {
    "udim-tile": "adapters/max/agr_tools/udimtile_core.py",
    "delivery-zip": "adapters/max/agr_tools/package_core.py",
    "blender-launch": "src/dt_ai/core/blender_runner.py",
    "sintez-checker": "tools/blender/sintez_checker.py",
    "master-qa": "tools/blender/qa_master.py",
    "vpm-uv": "tools/blender/vpm_uv.py",
    "seam-seal": "tools/blender/seam_seal.py",
    "site-placement": "src/dt_ai/placement/site.py",
    "window-generator": "adapters/max/agr_tools/windowgen_core.py",
}
WRITE_MODES = {"w", "x", "a"}
SCAN_PATTERN = "*.py"
# top-level folders where a new copy fails, per rule (#1376 widened udim-tile, #1377 delivery-zip to tools/ + src/)
GUARDED = {"udim-tile": ("jobs", "tools", "src"), "delivery-zip": ("jobs", "tools", "src"),
           "blender-launch": ("jobs", "tools", "src"),   # #1378: owner exists, guarded from the start
           "sintez-checker": ("jobs", "tools", "src"), "master-qa": ("jobs", "tools", "src"),
           "vpm-uv": ("jobs", "tools", "src"),   # #1380: periodic VPM UV, not NPM atlas
           "seam-seal": ("jobs", "tools", "src"),   # #1381
           "site-placement": ("jobs", "tools", "src"),   # #1407: one site placement run, guarded from the start
           "window-generator": ("jobs", "tools", "src")}
# rules whose allowlist rows must carry a non-empty `ru` reason (#1377: why a writer stays outside the owner)
REASON_REQUIRED = {"delivery-zip", "blender-launch", "sintez-checker", "master-qa", "vpm-uv", "seam-seal",
                   "site-placement", "window-generator"}


OWNED_NAMES = {"udim-tile": {"udim_tile", "udim_of_cell", "tile_origin", "face_tile"},
               "master-qa": {"world_bm"},
               "seam-seal": {"seal", "ring_split", "t_junctions"}}
SINTEZ_ENTRY = "calculate_all_checks"   # the checker's own "Check AGR zip-files" entry point


def _int_names(tree):
    """{name: {int values}} for every `Name = <int>` / `Name: T = <int>` anywhere in the file (module, class
    and function level). A name bound to 1001 anywhere counts as 1001 (fail closed)."""
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if isinstance(value, ast.Constant) and type(value.value) is int:
            for target in targets:
                if isinstance(target, ast.Name):
                    names.setdefault(target.id, set()).add(value.value)
    return names


def _udim_hits(tree):
    consts = _int_names(tree)

    def _const(node, value):
        if isinstance(node, ast.Constant):
            return type(node.value) is type(value) and node.value == value
        return isinstance(node, ast.Name) and value in consts.get(node.id, ())

    def _add_terms(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return _add_terms(node.left) + _add_terms(node.right)
        return [node]

    def _is_times_ten(node):
        return isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult) and (
            _const(node.left, 10) or _const(node.right, 10))

    def _is_floor(node):
        return any(isinstance(n, ast.Call) and (
            isinstance(n.func, ast.Name) and n.func.id == "floor" or
            isinstance(n.func, ast.Attribute) and n.func.attr == "floor") for n in ast.walk(node))

    def _is_tile_index(node):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int"
                and len(node.args) == 1 and not node.keywords and not isinstance(node.args[0], ast.Starred)):
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.FloorDiv) and _const(node.right, 1):
            return True
        return _is_floor(node)

    def _has_base(terms):
        # Sum only unambiguous integer leaves; do not evaluate scanned code or infer arbitrary variables.
        if any(_const(t, 1001) for t in terms):
            return True
        total = 0
        for term in terms:
            if isinstance(term, ast.Constant) and type(term.value) is int:
                total += term.value
            elif isinstance(term, ast.Name) and len(values := consts.get(term.id, ())) == 1:
                total += next(iter(values))
        return total == 1001

    def _is_minus_1001(node):
        return isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and _const(node.right, 1001)

    hits = {}
    for node in ast.walk(tree):
        # a job-local definition carrying an owned function name is a copy whatever its body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in OWNED_NAMES["udim-tile"]:
            hits[id(node)] = node
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            terms = _add_terms(node)
            if _has_base(terms) and any(_is_times_ten(t) or _is_tile_index(t) for t in terms):
                hits[id(node)] = node
        # Single-row UV translation: a 2D origin vector or the scalar inverse x - (tile - 1001).
        if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) == 2 \
                and _is_minus_1001(node.elts[0]) and (_const(node.elts[1], 0) or _const(node.elts[1], 0.0)):
            hits[id(node)] = node
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and _is_minus_1001(node.right):
            hits[id(node)] = node
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.FloorDiv)) \
                and _const(node.right, 10) and _is_minus_1001(node.left):
            hits[id(node)] = node
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "divmod" \
                and len(node.args) == 2 and _is_minus_1001(node.args[0]) and _const(node.args[1], 10):
            hits[id(node)] = node
    # two-step inverse: `i = tile - 1001` then `i % 10` / `i // 10` (reported on the assignment line)
    offsets = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_minus_1001(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    offsets.setdefault(target.id, node)
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.FloorDiv)) \
                and _const(node.right, 10) and isinstance(node.left, ast.Name) and node.left.id in offsets:
            assign = offsets[node.left.id]
            hits[id(assign)] = assign
    return list(hits.values())


def _is_zipfile_call(func):
    if isinstance(func, ast.Attribute) and func.attr == "ZipFile":
        return True
    return isinstance(func, ast.Name) and func.id == "ZipFile"


def _zip_hits(tree):
    # Like integer bindings, imports count anywhere in the file (fail closed on rebinding/shadowing).
    zip_names = {"ZipFile"}
    archive_names = {"make_archive"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if node.module == "zipfile" and alias.name == "ZipFile":
                    zip_names.add(alias.asname or alias.name)
                if node.module == "shutil" and alias.name == "make_archive":
                    archive_names.add(alias.asname or alias.name)

    hits = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        archive = (isinstance(node.func, ast.Attribute) and node.func.attr == "make_archive" or
                   isinstance(node.func, ast.Name) and node.func.id in archive_names)
        zipfile = (_is_zipfile_call(node.func) or
                   isinstance(node.func, ast.Name) and node.func.id in zip_names)
        if not (archive or zipfile):
            continue
        mode = node.args[1] if len(node.args) > 1 else None
        for kw in node.keywords:
            if kw.arg == ("format" if archive else "mode"):
                mode = kw.value
        if mode is None and not archive:
            continue  # ZipFile defaults to read mode; make_archive has no default format.
        if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
            if mode.value in ({"zip"} if archive else WRITE_MODES):
                hits[id(node)] = node
        else:  # a computed mode/format cannot be proven read-only/non-ZIP: fail closed
            hits[id(node)] = node
    return list(hits.values())


HEADLESS_FLAGS = {"--background", "-b"}
SCRIPT_FLAGS = {"--python", "-P", "--python-expr", "--python-text"}


def _is_launch(words):
    return bool(words & HEADLESS_FLAGS) and bool(words & SCRIPT_FLAGS)


def _blender_hits(tree):
    """Blender command lines: a list/tuple display with a headless and a script flag (string constants), or one
    string constant holding both as words. Docstrings / bare string statements (`ast.Expr`) are prose."""
    prose = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Expr)}
    hits = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            words = {e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
            if _is_launch(words):
                hits[id(node)] = node
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose:
            if _is_launch(set(node.value.split())):
                hits[id(node)] = node
        elif isinstance(node, ast.JoinedStr) and id(node) not in prose:
            words = set(" ".join(v.value for v in node.values if isinstance(v, ast.Constant)).split())
            if _is_launch(words):
                hits[id(node)] = node
    return list(hits.values())


def _sintez_hits(tree):
    """Calls of the SINTEZ checker entry point: `<anything>.calculate_all_checks(...)` or a bare name call."""
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call) and (
        isinstance(node.func, ast.Attribute) and node.func.attr == SINTEZ_ENTRY
        or isinstance(node.func, ast.Name) and node.func.id == SINTEZ_ENTRY)]


def _master_hits(tree):
    """Definitions carrying the master-QA owner's helper name (`def world_bm`), whatever their body."""
    return [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in OWNED_NAMES["master-qa"]]


def _vpm_uv_hits(tree):
    """Definitions of the shared periodic VPM UV/slicer entry points, not mere imports or calls."""
    return [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {'pack_uv', 'texel_cut'}]


def _seal_hits(tree):
    """Definitions carrying the seam-seal owner's function names (`def seal` / `ring_split` / `t_junctions`)."""
    return [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in OWNED_NAMES["seam-seal"]]


def _place_hits(tree):
    """Calls of the placement engine run `engine.place(...)`, or a bare `place(...)` imported from
    dt_ai.placement.engine: a site run outside the one placement command is a job-local copy (#1407)."""
    bare = any(isinstance(n, ast.ImportFrom) and n.module == "dt_ai.placement.engine"
               and any(a.name == "place" and a.asname in (None, "place") for a in n.names) for n in ast.walk(tree))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call) and (
        isinstance(node.func, ast.Attribute) and node.func.attr == "place"
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "engine"
        or bare and isinstance(node.func, ast.Name) and node.func.id == "place")]


def _window_hits(tree):
    """Protect the window builder and 3D ownership entry points; mere calls are not copies."""
    return [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {'build_type', 'assign_glass'}]


CHECKS = {"udim-tile": _udim_hits, "delivery-zip": _zip_hits, "blender-launch": _blender_hits,
          "sintez-checker": _sintez_hits, "master-qa": _master_hits, "vpm-uv": _vpm_uv_hits, "seam-seal": _seal_hits,
          "site-placement": _place_hits, "window-generator": _window_hits}
MODULE = "<module>"
QUALNAME = r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*|<module>"
HASH = re.compile(r"^[0-9a-f]{10}$")
AT = re.compile(rf"^(?P<path>[^:]+\.py)::(?P<qual>{QUALNAME})$")
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

# rule, file (posix, repo-relative), enclosing def/class qualname, sha1[:10] of ast.unparse(node), first line, column
Finding = namedtuple("Finding", "rule path qualname digest line col")
# value of an allowlist key (#1396): the issue reference itself (a str, so `== "#1337"` keeps working) carrying
# `copies`, how many copies the row covers
class Allow(str):
    copies: int

    def __new__(cls, issue, copies=1):
        value = super().__new__(cls, issue)
        value.copies = copies
        return value

    @property
    def issue(self):
        return str(self)


def _scopes(tree):
    """{id(node): qualname of the def/class whose body holds it}. Decorators, defaults, annotations and bases run
    in the enclosing scope; a def's own node gets its own qualname (a copy named like the owner IS that def)."""
    out = {}

    def visit(node, qual):
        for field, value in ast.iter_fields(node):
            inner = isinstance(node, SCOPES) and field == "body"
            for child in value if isinstance(value, list) else [value]:
                if isinstance(child, ast.AST):
                    here = f"{qual}.{node.name}" if inner and qual != MODULE else node.name if inner else qual
                    out[id(child)] = here
                    if isinstance(child, SCOPES):
                        out[id(child)] = child.name if here == MODULE else f"{here}.{child.name}"
                    visit(child, here)

    visit(tree, MODULE)
    return out


def _digest(node):
    text = f"def {node.name}" if isinstance(node, SCOPES) else ast.unparse(node)
    return hashlib.sha1(" ".join(text.split()).encode("utf-8")).hexdigest()[:10]


def _findings(tree, rel):
    scopes = _scopes(tree)
    out = []
    for rule, check in CHECKS.items():
        if rel == RULES[rule]:   # the owner is not a copy of itself
            continue
        hits = check(tree)
        ids = {id(h) for h in hits}
        nested = {id(sub) for h in hits if not isinstance(h, SCOPES)
                  for sub in ast.walk(h) if sub is not h and id(sub) in ids}
        for node in hits:
            if id(node) not in nested:   # an expression inside another reported expression is the same copy
                out.append(Finding(rule, rel, scopes[id(node)], _digest(node), node.lineno, node.col_offset))
    return out


def scan_text(source, rel="<text>"):
    """Findings of one source text (tests, probes); SyntaxError raises."""
    return sorted(set(_findings(ast.parse(source, filename=rel), rel)))


def scan(root, scope="jobs"):
    """Return sorted findings [Finding] for every *.py under root/scope; SyntaxError raises naming the file."""
    root = Path(root)
    base = root / scope
    if not base.is_dir():
        raise FileNotFoundError(f"scan scope missing: {base}")
    findings = set()
    for path in sorted(base.rglob(SCAN_PATTERN)):
        rel = path.relative_to(root).as_posix()
        source = path.read_bytes()
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            raise SyntaxError(f"{rel}: cannot parse ({exc.msg}, line {exc.lineno})") from None
        findings.update(_findings(tree, rel))
    return sorted(findings)


def allowlist(contexts):
    """Rule-tagged duplicates of contexts.yaml -> {(rule, path, qualname, hash | None): Allow(issue, copies)}.

    Unknown rules, a missing issue, an `at` that is not `path.py::qualname`, a malformed hash, a `count` that is not
    an integer >= 1, a repeated row and a function row overlapping a hash row of the same function raise ValueError
    naming the row."""
    allowed = {}
    for ctx in contexts.get("contexts", []) + [contexts.get("shared_kernel", {})]:
        for dup in ctx.get("duplicates", []):
            rule = dup.get("rule")
            if rule is None:
                continue
            at = str(dup.get("at", ""))
            if rule not in RULES:
                raise ValueError(f"unknown guard rule {rule!r} at {at}")
            issue = dup.get("issue", "")
            if not re.match(r"^#[0-9]+$", str(issue)):
                raise ValueError(f"guard allowlist entry {at} has no issue reference")
            if rule in REASON_REQUIRED and not str(dup.get("ru") or "").strip():
                raise ValueError(f"guard allowlist entry {at} ({rule}) has no reason (`ru`): say why it stays "
                                 f"outside {RULES[rule]}")
            m = AT.match(at)
            if not m:
                raise ValueError(f"guard allowlist entry {at!r}: 'at' must be path.py::function (#1387), "
                                 "not a line number")
            digest = dup.get("hash")
            if digest is not None:
                digest = str(digest)   # an unquoted all-digit hash parses as int; compare as text
                if not HASH.match(digest):
                    raise ValueError(f"guard allowlist entry {at}: hash {digest!r} is not 10 lowercase hex digits")
            count = dup.get("count", 1)
            if type(count) is not int or count < 1:   # bool, quoted text, 0 and negatives are errors, never 1
                raise ValueError(f"guard allowlist entry {at}: count {count!r} is not an integer >= 1 (#1396)")
            key = (rule, m["path"], m["qual"], digest)
            if key in allowed:
                raise ValueError(f"duplicate allowlist entry {rule} {at}")
            allowed[key] = Allow(issue, count)
    for rule, path, qual, digest in allowed:
        if digest is None and any(k[:3] == (rule, path, qual) and k[3] for k in allowed):
            raise ValueError(f"allowlist entry {rule} {path}::{qual} without hash overlaps its hash rows")
    return allowed


def _covers(key, finding):
    rule, path, qual, digest = key
    return (rule, path, qual) == finding[:3] and digest in (None, finding.digest)


def _guarded(finding, scope=None):
    tops = (scope,) if scope is not None else GUARDED[finding.rule]
    return any(finding.path.startswith(top.rstrip("/") + "/") for top in tops)


def _count(value):
    """Copies a row covers: Allow.copies; a plain issue string (pre-#1396 callers) covers one."""
    return value.copies if isinstance(value, Allow) else 1


def _key_order(key):
    return tuple("" if part is None else part for part in key)


def _found(findings, key):
    """How many distinct findings a row matches (before its `count` applies)."""
    return sum(_covers(key, f) for f in set(findings))


def compare(findings, allowed, scope=None):
    """-> (new, stale): guarded findings beyond what the rows cover, rows that cover fewer findings than `count`.

    A row matches the findings of its (rule, path, qualname[, hash]) and covers the first `count` of them by position
    (#1396); the rest are new. Guarded = under GUARDED[rule] (or under `scope` for every rule when given). Rows
    outside it are documentation of copies elsewhere: they must still be found `count` times (else stale), but new
    copies there are not guarded yet."""
    findings = sorted(set(findings))
    covered, stale = set(), []
    for key in sorted(allowed, key=_key_order):
        matched = sorted((f for f in findings if _covers(key, f)), key=lambda f: (f.line, f.col))
        covered.update(matched[:_count(allowed[key])])
        if len(matched) < _count(allowed[key]):
            stale.append(key)
    return [f for f in findings if _guarded(f, scope) and f not in covered], stale


def scan_for(root, allowed, scope=None):
    """Scan every guarded folder (or `scope`) plus every top-level folder an allowlist row points to."""
    guarded = {scope} if scope is not None else {top for tops in GUARDED.values() for top in tops}
    tops = guarded | {key[1].split("/", 1)[0] for key in allowed}
    findings = []
    for top in sorted(tops):
        findings += scan(root, top)
    return findings


# ---------------------------------------------------------------- status of every duplicates row (#1424)
STATUSES = ("live-bypass", "wrapper", "historical", "own-duty", "superseded")
STEP = re.compile(r"^(#[0-9]+|-)$")
# the remaining compaction steps the live bypasses are ordered over (#1424 issue text; #1397 = step 1b, open)
COMPACTION_STEPS = ("#1379", "#1380", "#1381", "#1397", "#1404", "#1405", "#1406", "#1407", "#1410")
# Ratchet (#1424): the live bypasses known on 2026-11-15, keyed (context map, at, hash or ""). A live-bypass row not
# listed here is NEW and fails; a listed key without its live-bypass row is fixed - remove it here (tighten).
LIVE_BYPASS_BASELINE = frozenset({
    # #1593: inventory of existing run_stage.sh writers, not new build behaviour or guard rules.
    ("vpm-contexts", "jobs/KPP1/scripts/build_kpp1.py:198", ""),
    ("vpm-contexts", "jobs/KPP1/scripts/build_kpp1.py:327", ""),

    # #1441: previously missed current shell/candidate roots, not newly introduced code copies.
    ("contexts", "jobs/TEC26-OKS/scripts/package_vpm.py::<module>", "61d21d75df"),
    ("contexts", "jobs/elv-tc-vpm/scripts/package_vpm_v006.py::<module>", "99b52810a1"),

    ("package-contexts", "jobs/TEC26-OKS/scripts/package_vpm.py:50", ""),
    ("contexts", "jobs/VATUTINO-SITE/npm_code.py::rename_npm_zip", "c099bec414"),

    ("contexts", "tools/materials/npm_atlas_udim.py:785", ""),

    # blender-launch: the 16 live tools/ + src/ launches of #1378/#1424 call blender_command since #1530
})
# Ratchet (#1429): own-duty rows a live command/route reaches, keyed like LIVE_BYPASS_BASELINE. Relabelling a live copy
# own-duty is no way around the live-bypass ratchet: a live own-duty row not listed here is NEW and fails; a listed key
# without its live own-duty row (row gone, relabelled, or no live chain any more) is fixed - remove it here (tighten).
OWN_DUTY_BASELINE = frozenset({
    ("contexts", "jobs/KPP1/scripts/build_kpp1.py:194", ""),
    ("contexts", "src/dt_ai/publish/bundle.py::package", "99f325f2cd"),
    ("contexts", "tools/assets/build_maf_template.py::repack", "060ddc5ec1"),
    ("contexts", "tools/library/maf_material_ids.py::main", "7a61653774"),
    ("contexts", "tools/library/migrate_windows.py::main", "9d1268b5a7"),
    ("contexts", "tools/max/build_agr_tools.py::_zip", "7e7c2ad684"),
    ("contexts", "tools/methods/ucx/run_benchmarks.py::package", "3235a265a9"),
    ("contexts", "tools/methods/windows/run_benchmarks.py::package", "0083df7615"),
    ("contexts", "tools/research/checker_mutation.py::freeze", "3457dc7d0e"),
    ("contexts", "tools/research/checker_mutation.py::freeze", "a1ec950117"),
    ("contexts", "tools/sintez_parity.py::run_live", "28bb7ef3ef"),
    ("contexts", "tools/source/measure_spec_blender.py::udim", "ded8ff2561"),
    ("vpm-contexts", "jobs/KPP1/scripts/vpm_ucx.py:50", ""),
})
Row = namedtuple("Row", "map context owner at rel qual line status step why issue hash ru area rule",
                 defaults=(None,))
# Owner functions that ARE the duty of a rule (#1424 x #1378): a row of that rule is a wrapper only when its scope
# calls one of them; taking the executable path from blender_runner and building an own argv is still a bypass.
POLICY_NAMES = {"blender-launch": frozenset({"blender_command", "run_blender"})}


def _row_at(at):
    """-> (rel, qualname | None, line | None) of a duplicates `at` (path.py::qualname or path.py:line)."""
    if "::" in at:
        rel, qual = at.split("::", 1)
        return rel, qual, None
    rel, line = at.rsplit(":", 1)
    return rel, None, int(line)


def rows_of(maps):
    """Every duplicates row of every context map -> [Row]; a missing or unknown status, an own-duty row without a
    Russian `why`, a live-bypass row without `step` (#n or "-") raise ValueError naming the row."""
    out = []
    for name, cmap in maps.items():
        for ctx in [cmap.get("shared_kernel", {})] + cmap.get("contexts", []):
            for d in ctx.get("duplicates", []):
                at = str(d.get("at", ""))
                where = f"{name}: {at}"
                status = d.get("status")
                if status not in STATUSES:
                    raise ValueError(f"{where}: status {status!r} must be one of {', '.join(STATUSES)} (#1424)")
                why = str(d.get("why") or "").strip()
                if status in ("own-duty", "superseded") and not re.search(r"[А-Яа-яЁё]", why):
                    raise ValueError(f"{where}: {status} needs `why` in Russian: other duty or replacement draft")
                step = d.get("step")
                if status == "live-bypass" and (step is None or not STEP.match(str(step))):
                    raise ValueError(f"{where}: live-bypass needs `step` (#<compaction issue> or \"-\" = no card)")
                if status != "live-bypass" and step is not None:
                    raise ValueError(f"{where}: `step` belongs to live-bypass rows only")
                rel, qual, line = _row_at(at)
                digest = d.get("hash")
                out.append(Row(name, ctx.get("id"), ctx.get("owner"), at, rel, qual, line, status,
                               None if step is None else str(step), why, d.get("issue"),
                               "" if digest is None else str(digest), str(d.get("ru") or ""), str(ctx.get("ru") or ctx.get("id")),
                               d.get("rule")))
    return out


def _owner_path_literal(node, owner):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return False
    path = node.value.replace("\\", "/")
    return path == Path(owner).name or path.removeprefix("./") == owner


def _owner_path_binding(value, paths, owner):
    if isinstance(value, ast.Name):
        return value.id in paths
    if isinstance(value, ast.Call) and ast.unparse(value.func) == "os.path.join" and value.args:
        # The TEC26 loader anchors the path with a computed repository root.
        parts = value.args[1:]
        return (bool(parts) and not value.keywords
                and all(isinstance(p, ast.Constant) and isinstance(p.value, str) for p in parts)
                and "/".join(p.value.replace("\\", "/") for p in parts) == owner)
    return _owner_path_literal(value, owner)


def _is_owner_loader(node, owner, paths):
    """Recognize the straight-line importlib chain, without executing the helper.

    Assignment nodes serve as identities: reusing a variable spelling doesn't
    make a new spec or module the same object. Nested uses aren't witnesses.
    """
    paths = paths.copy()
    paths.difference_update(arg.arg for arg in ast.walk(node.args) if isinstance(arg, ast.arg))
    specs, modules, executed = {}, {}, set()
    for stmt in node.body:
        if isinstance(stmt, ast.Return):
            return isinstance(stmt.value, ast.Name) and modules.get(stmt.value.id, (None, None))[1] in executed

        # Invalidate names written by unsupported statements too. The cache
        # branch in the TEC26 loader doesn't rebind any of these local names.
        written = {n.id for n in ast.walk(stmt) if isinstance(n, ast.Name)
                   and isinstance(n.ctx, (ast.Store, ast.Del))}
        if isinstance(stmt, ast.Assign) and all(isinstance(t, ast.Name) for t in stmt.targets):
            value = stmt.value
            path = _owner_path_binding(value, paths, owner)
            spec = module = None
            if isinstance(value, ast.Call):
                func = ast.unparse(value.func)
                if func in ("importlib.util.spec_from_file_location", "spec_from_file_location"):
                    location = value.args[1] if len(value.args) >= 2 else next(
                        (kw.value for kw in value.keywords if kw.arg == "location"), None)
                    if ((isinstance(location, ast.Name) and location.id in paths)
                            or _owner_path_literal(location, owner)):
                        spec = stmt
                elif (func in ("importlib.util.module_from_spec", "module_from_spec")
                      and len(value.args) == 1 and isinstance(value.args[0], ast.Name)):
                    source = specs.get(value.args[0].id)
                    if source is not None:
                        module = source, stmt
        else:
            path = spec = module = None
        for name in written:
            paths.discard(name)
            specs.pop(name, None)
            modules.pop(name, None)
            if path:
                paths.add(name)
            if spec is not None:
                specs[name] = spec
            if module is not None:
                modules[name] = module

        if isinstance(stmt, ast.Expr):
            match stmt.value:
                case ast.Call(func=ast.Attribute(attr="exec_module", value=ast.Attribute(
                              attr="loader", value=ast.Name(id=spec_name))),
                              args=[ast.Name(id=module_name)], keywords=[]):
                    source, identity = modules.get(module_name, (None, None))
                    if source is not None and source is specs.get(spec_name):
                        executed.add(identity)
    return False


def _owner_names(tree, owner):
    """Names in the file bound to the owner module: imports of it or from it, and assignments whose value names the
    owner file (`_sibling('udimtile_core.py', ...)`, importlib spec of its path)."""
    stem = Path(owner).stem
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[-1] == stem:
                    names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")
            for a in node.names:
                if mod[-1:] == [stem] or a.name == stem:
                    names.add(a.asname or a.name)
        elif isinstance(node, ast.Assign):
            if any(isinstance(s, ast.Constant) and isinstance(s.value, str) and s.value.replace("\\", "/")
                   .endswith(f"{stem}.py") for s in ast.walk(node.value)):
                names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    # Use path bindings, not the broad set of owner references above, for the
    # importlib location. A diagnostic mention is not a path binding (#1486).
    paths = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            bound = _owner_path_binding(node.value, paths, owner)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    paths.discard(target.id)
                    if bound:
                        paths.add(target.id)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_owner_loader(node, owner, paths):
            names.add(node.name)
    return names


def _scope_node(tree, qual, line):
    """The def/class a row points to: by qualname, or the innermost def/class holding the line; module otherwise."""
    if qual not in (None, MODULE):
        node, parts = tree, qual.split(".")
        for part in parts:
            node = next((n for n in ast.iter_child_nodes(node) if isinstance(n, SCOPES) and n.name == part), None)
            if node is None:
                raise ValueError(f"{qual}: no such function/class")
        return node
    best = tree
    if line is not None:
        for n in ast.walk(tree):
            if isinstance(n, SCOPES) and n.lineno <= line <= n.end_lineno:
                if best is tree or n.lineno >= best.lineno:
                    best = n
    return best


def calls_owner(root, row):
    """True when the row's function (or line's enclosing def) uses a name bound to its context owner; for a rule in
    POLICY_NAMES only a use of one of its policy functions counts (`from owner import f [as g]` or `owner_mod.f`)."""
    tree = ast.parse((Path(root) / row.rel).read_bytes(), filename=row.rel)
    names = _owner_names(tree, row.owner)
    if not names:
        return False
    scope = _scope_node(tree, row.qual, row.line)
    policy = POLICY_NAMES.get(row.rule)
    if policy is None:
        return any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(scope))
    stem = Path(row.owner).stem
    imported = {a.asname or a.name: a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                and (n.module or "").split(".")[-1:] == [stem] for a in n.names}
    funcs = {local for local, name in imported.items() if name in policy}
    modules = names - set(imported)
    return any((isinstance(n, ast.Name) and n.id in funcs) or
               (isinstance(n, ast.Attribute) and n.attr in policy and isinstance(n.value, ast.Name)
                and n.value.id in modules) for n in ast.walk(scope))


def finished_jobs(root, contexts):
    """`finished_jobs` of contexts.yaml -> {job folder: evidence}; the evidence file must exist and hold `match`."""
    jobs = {}
    for i, j in enumerate(contexts.get("finished_jobs", [])):
        job, ev, match = str(j.get("job", "")), str(j.get("evidence", "")), str(j.get("match", ""))
        if not re.match(r"^jobs/[^/]+$", job) or not ev or not match:
            raise ValueError(f"finished_jobs[{i}]: needs job: jobs/<folder>, evidence and match")
        path = Path(root) / ev
        text = path.read_text(encoding="utf-8") if path.is_file() else \
            "\n".join(p.name for p in path.iterdir()) if path.is_dir() else None
        if text is None:
            raise ValueError(f"finished_jobs {job}: evidence {ev} does not exist")
        if match not in text:
            raise ValueError(f"finished_jobs {job}: evidence {ev} does not contain {match!r}")
        jobs[job] = ev
    return jobs


# Historical job scripts (#1546, [D327]): scripts of a finished (delivered) job that no live command/route reaches
# and that no entrypoint names as its evidence. They stay unchanged and every scan above still reads them; a
# generated block of the root `.ignore` hides them from agent search (ripgrep reads `.ignore` by default). The
# per-job header line of that block marks them historical (a header inside each script would shift the `path:line`
# rows of the context maps and change the script bytes recorded by the deliveries).
SCRIPT_SUFFIXES = (".py", ".ms", ".rb", ".sh", ".mjs")  # the script types jobs/ tracks (.gitignore)
IGNORE_BEGIN = "# BEGIN historical-job-scripts (#1546, [D327]) - generated: duplicate_guard.py --write-ignore"
IGNORE_END = "# END historical-job-scripts"
GLOB_CHARS = re.compile(r"([\\*?\[\]!#])")


# Frozen baseline of the job scripts at the #1546 cut (PR #1553 r1): historical/legacy is a list of script paths,
# never a whole job folder - new work lands in sub-folders of finished jobs (jobs/KPP1/<task>-<issue>/) and must
# stay visible and checked. A line is never added; removing one is allowed.
JOB_BASELINE = "docs/agents/job_scripts_baseline.txt"
SKELETON_CONFIG = "skeleton.json"


def load_job_baseline(root):
    """Frozen baseline -> frozenset of repo paths; missing/empty file, a path outside jobs/ or a duplicate raise."""
    path = Path(root) / JOB_BASELINE
    if not path.is_file():
        raise ValueError(f"{JOB_BASELINE}: missing (the frozen #1546 baseline of job scripts)")
    out = set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("/")
        if line != line.strip() or parts[0] != "jobs" or len(parts) < 3 or "\\" in line \
                or any(p in ("", ".", "..") for p in parts) or Path(line).suffix.lower() not in SCRIPT_SUFFIXES:
            raise ValueError(f"{JOB_BASELINE}:{n}: {line!r} is not a jobs/<ID>/.../<script> path")
        if line in out:
            raise ValueError(f"{JOB_BASELINE}:{n}: {line} listed twice")
        out.add(line)
    if not out:
        raise ValueError(f"{JOB_BASELINE}: empty")
    return frozenset(out)


def in_skeleton_job(root, rel):
    """True when a folder between jobs/ and the script holds skeleton.json (the job opted in to the contract)."""
    parts = rel.split("/")
    return any((Path(root).joinpath(*parts[:i]) / SKELETON_CONFIG).is_file() for i in range(2, len(parts)))


def historical_scripts(root, finished, chains, live_evidence=(), baseline=None):
    """Sorted repo paths of the historical scripts: in the frozen baseline, inside a finished job, outside any
    skeleton.json folder and not reached by a live chain (a new script in a finished job is never historical)."""
    baseline = load_job_baseline(root) if baseline is None else baseline
    out = []
    for job in sorted(finished):
        for p in sorted((Path(root) / job).rglob("*")):
            rel = p.relative_to(root).as_posix()
            if p.is_file() and p.suffix.lower() in SCRIPT_SUFFIXES and rel in baseline and rel not in chains \
                    and rel not in live_evidence and not in_skeleton_job(root, rel):
                out.append(rel)
    return out


def render_ignore_block(scripts):
    """The generated `.ignore` block: one HISTORICAL header line per job, then its anchored, escaped paths."""
    lines, job = [IGNORE_BEGIN], None
    for rel in scripts:
        this = "/".join(rel.split("/")[:2])
        if this != job:
            job = this
            lines.append(f"# HISTORICAL [D327] {job}: delivered job; scripts kept unchanged, hidden from agent search, "
                         "still scanned by duplicate_guard")
        lines.append("/" + GLOB_CHARS.sub(r"\\\1", rel).replace(" ", "\\ "))
    lines.append(IGNORE_END)
    return "\n".join(lines) + "\n"


def _ignore_parts(text):
    if text.count(IGNORE_BEGIN) != 1 or text.count(IGNORE_END) != 1 or text.index(IGNORE_END) < text.index(IGNORE_BEGIN):
        return None
    head, rest = text.split(IGNORE_BEGIN, 1)
    block, tail = rest.split(IGNORE_END, 1)
    return head, IGNORE_BEGIN + block + IGNORE_END + "\n", tail[1:] if tail.startswith("\n") else tail


def ignore_problems(root, scripts):
    """Problems of the root `.ignore` block against the historical scripts ([] when it is exactly the render)."""
    path = Path(root) / ".ignore"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    parts = _ignore_parts(text)
    if parts is None:
        return [f".ignore: no single historical-job-scripts block ({len(scripts)} historical scripts unhidden); "
                "run duplicate_guard.py --write-ignore"]
    want = render_ignore_block(scripts)
    if parts[1] == want:
        return []
    have = {ln for ln in parts[1].splitlines() if ln.startswith("/")}
    need = {ln for ln in want.splitlines() if ln.startswith("/")}
    return [f".ignore: historical block is stale: missing {sorted(need - have)[:5]} ({len(need - have)}), "
            f"extra (live or gone) {sorted(have - need)[:5]} ({len(have - need)}); run duplicate_guard.py --write-ignore"]


def write_ignore(root, scripts):
    """Replace (or append) the generated block of root/.ignore; text outside the block is kept."""
    path = Path(root) / ".ignore"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    parts = _ignore_parts(text)
    if parts is None and IGNORE_BEGIN in text:
        raise ValueError(".ignore: broken historical-job-scripts block (BEGIN/END); fix it by hand")
    head, _, tail = parts or (text + ("\n" if text and not text.endswith("\n") else ""), "", "")
    tmp = path.with_name(".ignore.partial")
    tmp.write_text(head + render_ignore_block(scripts) + tail, encoding="utf-8", newline="\n")
    tmp.replace(path)


def status_problems(root, rows, chains, roots, finished, baseline=LIVE_BYPASS_BASELINE, *,
                    own_duty_baseline=OWN_DUTY_BASELINE):
    """Problems of the declared statuses against the real call chains (#1424); [] when every row agrees.
    Live-bypass rows and own-duty rows reached by a live chain (#1429) each pass only through their own ratchet."""
    problems = []
    live_keys, own_keys = set(), set()
    for r in rows:
        where = f"{r.map}: {r.at}" + (f" hash {r.hash}" if r.hash else "")
        if not (Path(root) / r.rel).is_file():
            problems.append(f"{where}: file does not exist")
            continue
        real = (Path(root) / r.rel).resolve()
        if "\\" in r.rel or real.relative_to(Path(root).resolve()).as_posix() != r.rel:
            problems.append(f"{where}: path is an alias of {real.relative_to(Path(root).resolve()).as_posix()}; "
                            "write the repo-relative path as on disk")
            continue
        chain = chains.get(r.rel)
        via = f"{' > '.join(chain)} ({roots[chain[0]]})" if chain else ""
        wrapper = calls_owner(root, r)
        if r.status == "wrapper" and not wrapper:
            problems.append(f"{where}: status wrapper, but it does not call its owner {r.owner}")
        if r.status == "superseded" and chain:
            problems.append(f"{where}: status superseded, but a live command/route uses it: {via}")
        if r.status == "historical":
            job = "/".join(r.rel.split("/")[:2])
            if chain:
                problems.append(f"{where}: status historical, but a live command/route uses it: {via}")
            if not r.rel.startswith("jobs/") or job not in finished:
                problems.append(f"{where}: historical only inside a finished job (finished_jobs), not {job}")
        if r.status == "live-bypass":
            live_keys.add((r.map, r.at, r.hash))
            if not chain:
                problems.append(f"{where}: status live-bypass, but no live command/route reaches {r.rel}")
            if wrapper:
                problems.append(f"{where}: status live-bypass, but it calls the owner {r.owner}: wrapper")
            if (r.map, r.at, r.hash) not in baseline:
                problems.append(f"NEW LIVE BYPASS {where}: use {r.owner} instead (a live command/route must not get "
                                f"a new copy; {via})")
        if r.status == "own-duty" and chain:
            own_keys.add((r.map, r.at, r.hash))
            if (r.map, r.at, r.hash) not in own_duty_baseline:
                problems.append(f"NEW OWN-DUTY {where}: {via}: a live command/route reaches it; use {r.owner} or add "
                                "the key to OWN_DUTY_BASELINE in a reviewed change (#1429)")
    for key in sorted(baseline - live_keys):
        problems.append(f"FIXED LIVE BYPASS {key[0]}: {key[1]} {key[2]}: no live-bypass row any more; remove it from "
                        "LIVE_BYPASS_BASELINE (tighten the ratchet)")
    for key in sorted(own_duty_baseline - own_keys):
        problems.append(f"FIXED OWN-DUTY {key[0]}: {key[1]} {key[2]}: no own-duty row reached by a live command/route "
                        "any more; remove it from OWN_DUTY_BASELINE (tighten the ratchet)")
    return problems


def load_maps(root):
    """Every context map of route_map (contexts.yaml first)."""
    if __package__ in (None, ""):
        import route_map  # noqa: E402
    else:
        from . import route_map
    return {n: mini_yaml.load(Path(root) / p) for n, p in route_map.context_maps().items()}


def live_chains(root):
    if __package__ in (None, ""):
        import call_chains  # noqa: E402
    else:
        from . import call_chains
    return call_chains.load_live(root)


def bypass_table(rows, steps=COMPACTION_STEPS):
    """Russian markdown: live bypasses by area, then the remaining compaction steps ordered by live bypasses."""
    live, seen = [], set()
    for r in rows:   # one copy listed in two context maps is one bypass
        if r.status == "live-bypass" and (r.at, r.hash) not in seen:
            seen.add((r.at, r.hash))
            live.append(r)
    by_ctx = {}
    for r in live:
        by_ctx.setdefault((r.area, r.step), []).append(r)
    counts = {s: 0 for s in steps}
    for r in live:
        counts[r.step] = counts.get(r.step, 0) + 1
    total = {s: sum(1 for r in rows if r.status == s) for s in STATUSES}
    out = ["### Живые обходы по областям", "",
           f"Строк дублей во всех картах: {len(rows)}; живой обход {total['live-bypass']}, обёртка {total['wrapper']}, "
           f"исторические {total['historical']}, своя обязанность {total['own-duty']}; разных живых копий {len(live)}.",
           f"Заменённые черновики (не сдача): {total['superseded']}.",
           "",
           "| Область | Живых обходов | Файлы | Шаг сжатия |", "|---|---|---|---|"]
    for key in sorted(by_ctx, key=lambda k: (-len(by_ctx[k]), k)):
        files = sorted({r.rel for r in by_ctx[key]})
        out.append(f"| {key[0]} | {len(by_ctx[key])} | {', '.join(f'`{f}`' for f in files)} | "
                   f"{'нет карточки' if key[1] == '-' else key[1]} |")
    out += ["", "### Порядок оставшихся шагов сжатия (по живым обходам)", "",
            "| № | Шаг | Живых обходов |", "|---|---|---|"]
    order = sorted(counts, key=lambda s: (-counts[s], s == "-", steps.index(s) if s in steps else len(steps), s))
    for i, s in enumerate(order, 1):
        out.append(f"| {i} | {'нет карточки' if s == '-' else s} | {counts[s]} |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Duplicate guard (#1359): owned functions vs copies")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--contexts", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--table", action="store_true", help="print the Russian live-bypass table + compaction order")
    ap.add_argument("--copies-only", action="store_true",
                    help="only the copy scan of the allowlist (synthetic test roots); skips the #1424 status check")
    ap.add_argument("--write-ignore", action="store_true",
                    help="regenerate the historical-job-scripts block of the root .ignore (#1546) before checking")
    args = ap.parse_args(argv)
    try:
        contexts = mini_yaml.load(args.contexts or args.root / "docs/architecture/contexts.yaml")
        allowed = allowlist(contexts)
        findings = scan_for(args.root, allowed)
        new, stale = compare(findings, allowed)
        problems, rows = [], []
        if not args.copies_only:
            maps = load_maps(args.root)
            if args.contexts:
                maps["contexts"] = contexts
            rows = rows_of(maps)
            roots, chains = live_chains(args.root)
            finished = finished_jobs(args.root, contexts)
            problems = status_problems(args.root, rows, chains, roots, finished)
            evidence = {str(e.get("evidence", "")) for e in contexts.get("entrypoints", [])}
            hidden = historical_scripts(args.root, finished, chains, evidence)
            if args.write_ignore:
                write_ignore(args.root, hidden)
            problems += ignore_problems(args.root, hidden)
    except (OSError, SyntaxError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.table and rows:
        print(bypass_table(rows))
    for p in problems:
        print(f"STATUS {p}")
    if args.json:
        print(json.dumps({"new": [f._asdict() for f in new],
                          "stale": [dict(zip(("rule", "path", "qualname", "hash"), k),
                                         count=_count(allowed[k]), found=_found(findings, k)) for k in stale],
                          "status": problems}, indent=1))
    for f in new:
        row = next((k for k in allowed if _covers(k, f)), None)
        hint = (f"; the row `{f.path}::{f.qualname}` covers only count {_count(allowed[row])} of "
                f"{_found(findings, row)} copies - remove the copy or raise `count`") if row else ""
        print(f"NEW COPY [{f.rule}] {f.path}:{f.line} in {f.qualname} (hash {f.digest}): use {RULES[f.rule]} "
              f"instead (or list `{f.path}::{f.qualname}` in contexts.yaml with an issue){hint}")
    for key in stale:
        rule, path, qual, digest = key
        pin = f" hash {digest}" if digest else ""
        print(f"STALE ALLOWLIST [{rule}] {path}::{qual}{pin}: found {_found(findings, key)} of count "
              f"{_count(allowed[key])}; remove or fix the row in contexts.yaml")
    return 1 if new or stale or problems else 0


if __name__ == "__main__":
    # Russian report on a non-UTF-8 Windows console/pipe (no PYTHONUTF8): never crash on print.
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
