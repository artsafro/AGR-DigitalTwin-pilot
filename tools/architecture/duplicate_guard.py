"""Duplicate guard (#1359): owned domain functions must not be re-implemented outside their owner.

Pattern: n/a | new-case: AST guard against job-local copies of owned functions (UDIM tile, delivery ZIP).

Rules (stdlib `ast`, no imports of the scanned code):
- `udim-tile`  owner adapters/max/agr_tools/udimtile_core.py (#1337). Flags the UDIM formula itself:
  an addition chain holding the constant 1001 and a `* 10` term (`1001 + u + 10 * v`), and the inverse
  `(tile - 1001) % 10` / `// 10` / `divmod(tile - 1001, 10)` / `i = tile - 1001` then `i % 10` or `i // 10`.
  1001 and 10 also match a name bound to that int anywhere in the file (`FIRST_UDIM = 1001`, `U = 10`), and any
  job-local `def` named udim_tile / udim_of_cell / tile_origin / face_tile is a copy (PR #1368 r1).
- `delivery-zip`  owner adapters/max/agr_tools/package_core.py (`_write_zip`, #1361/#1377): the one ZIP writer
  behind `agr package-npm` / `agr package-vpm` (tools/derive facades) and AGR Tools. Flags any other writer:
  `zipfile.ZipFile(..., "w" | "x" | "a")` (mode positional or keyword; a computed mode fails closed). Every
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
The owner file of a rule is never a copy of that rule.

Guarded scope per rule (GUARDED): `udim-tile` jobs/ + tools/ + src/ (#1376: the live NPM-route copies in tools/
and src/ now call the owner); `delivery-zip` jobs/ + tools/ + src/ (#1377: owner settled); `blender-launch`,
`sintez-checker`, `master-qa` jobs/ + tools/ + src/ from the start (#1378, #1379). Each guarded
folder must exist (a missing one is an error, not an empty pass).
The allowlist is the rule-tagged `duplicates` of docs/architecture/contexts.yaml: every finding in a guarded scope
must be listed there with an issue reference, and every listed row (also the documented copies outside the guarded
scope, e.g. the Max cores under adapters/) must still be found (no stale rows). A row is keyed by `at: "path.py::qualname"` - the file and the enclosing function/class
(`<module>` at top level), never by a bare line number (#1387): lines inserted above or inside the function do not
make it NEW or STALE. Optional `hash:` (10 hex, `sha1(ast.unparse(node))`, printed with every NEW COPY) pins one
copy inside the function; a row without it covers every copy of that rule in that function.
Usage: python tools/architecture/duplicate_guard.py [--root REPO] [--json] [--table] [--copies-only]; exit 0 clean,
1 violations, 2 unreadable input (a file that does not parse is an error naming it, never skipped).

Status (#1424): every `duplicates` row of every context map (route_map.context_maps) carries `status`
live-bypass | wrapper | historical | own-duty, checked against the real call chains (call_chains.py): a live-bypass
must be reached by a live command/route, must not call its owner and must be in LIVE_BYPASS_BASELINE (a NEW one
fails, a fixed one must leave the baseline); a wrapper must call its owner (for a rule in POLICY_NAMES: one of
its policy functions); a historical row must have no live chain
and sit in a `finished_jobs` folder of contexts.yaml; own-duty needs a Russian `why`. `--table` prints the Russian
«живые обходы по областям» table and the compaction order (docs/architecture/report-1424.md). `--copies-only`
runs only the copy scan (synthetic test roots without the maps).
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
}
WRITE_MODES = {"w", "x", "a"}
# top-level folders where a new copy fails, per rule (#1376 widened udim-tile, #1377 delivery-zip to tools/ + src/)
GUARDED = {"udim-tile": ("jobs", "tools", "src"), "delivery-zip": ("jobs", "tools", "src"),
           "blender-launch": ("jobs", "tools", "src"),   # #1378: owner exists, guarded from the start
           "sintez-checker": ("jobs", "tools", "src"), "master-qa": ("jobs", "tools", "src")}   # #1379
# rules whose allowlist rows must carry a non-empty `ru` reason (#1377: why a writer stays outside the owner)
REASON_REQUIRED = {"delivery-zip", "blender-launch", "sintez-checker", "master-qa"}


OWNED_NAMES = {"udim-tile": {"udim_tile", "udim_of_cell", "tile_origin", "face_tile"},
               "master-qa": {"world_bm"}}
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
            if any(_const(t, 1001) for t in terms) and any(_is_times_ten(t) for t in terms):
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
    hits = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_zipfile_call(node.func):
            mode = node.args[1] if len(node.args) > 1 else None
            for kw in node.keywords:
                if kw.arg == "mode":
                    mode = kw.value
            if mode is None:
                continue
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                if mode.value in WRITE_MODES:
                    hits[id(node)] = node
            else:  # a computed mode cannot be proven read-only: fail closed
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


CHECKS = {"udim-tile": _udim_hits, "delivery-zip": _zip_hits, "blender-launch": _blender_hits,
          "sintez-checker": _sintez_hits, "master-qa": _master_hits}
MODULE = "<module>"
QUALNAME = r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*|<module>"
HASH = re.compile(r"^[0-9a-f]{10}$")
AT = re.compile(rf"^(?P<path>[^:]+\.py)::(?P<qual>{QUALNAME})$")
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

# rule, file (posix, repo-relative), enclosing def/class qualname, sha1[:10] of ast.unparse(node), first line
Finding = namedtuple("Finding", "rule path qualname digest line")


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
                out.append(Finding(rule, rel, scopes[id(node)], _digest(node), node.lineno))
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
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        source = path.read_bytes()
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            raise SyntaxError(f"{rel}: cannot parse ({exc.msg}, line {exc.lineno})") from None
        findings.update(_findings(tree, rel))
    return sorted(findings)


def allowlist(contexts):
    """Rule-tagged duplicates of contexts.yaml -> {(rule, path, qualname, hash | None): issue}.

    Unknown rules, a missing issue, an `at` that is not `path.py::qualname`, a malformed hash, a repeated row and a
    function row overlapping a hash row of the same function raise ValueError naming the row."""
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
            key = (rule, m["path"], m["qual"], digest)
            if key in allowed:
                raise ValueError(f"duplicate allowlist entry {rule} {at}")
            allowed[key] = issue
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


def compare(findings, allowed, scope=None):
    """-> (new, stale): guarded findings no row covers, allowlist rows that cover no finding.

    Guarded = under GUARDED[rule] (or under `scope` for every rule when given). Rows outside it are documentation
    of copies elsewhere: they must still be found (else stale), but new copies there are not guarded yet."""
    new = sorted(f for f in set(findings) if _guarded(f, scope) and not any(_covers(k, f) for k in allowed))
    stale = sorted(k for k in allowed if not any(_covers(k, f) for f in findings))
    return new, stale


def scan_for(root, allowed, scope=None):
    """Scan every guarded folder (or `scope`) plus every top-level folder an allowlist row points to."""
    guarded = {scope} if scope is not None else {top for tops in GUARDED.values() for top in tops}
    tops = guarded | {key[1].split("/", 1)[0] for key in allowed}
    findings = []
    for top in sorted(tops):
        findings += scan(root, top)
    return findings


# ---------------------------------------------------------------- status of every duplicates row (#1424)
STATUSES = ("live-bypass", "wrapper", "historical", "own-duty")
STEP = re.compile(r"^(#[0-9]+|-)$")
# the remaining compaction steps the live bypasses are ordered over (#1424 issue text; #1397 = step 1b, open)
COMPACTION_STEPS = ("#1379", "#1380", "#1381", "#1397", "#1404", "#1405", "#1406", "#1407", "#1410")
# Ratchet (#1424): the live bypasses known on 2026-11-15, keyed (context map, at, hash or ""). A live-bypass row not
# listed here is NEW and fails; a listed key without its live-bypass row is fixed - remove it here (tighten).
LIVE_BYPASS_BASELINE = frozenset({
    ("contexts", "adapters/max/agr_tools/atlas_core.py::pack", "402002d484"),
    ("contexts", "adapters/max/agr_tools/npm2vpm_core.py::tile_origin", "af2bc2e385"),
    ("contexts", "adapters/max/agr_tools/npm_core.py::tile_of", "ded8ff2561"),
    ("contexts", "adapters/max/agr_tools/udim_core.py::tile_origin", "af2bc2e385"),
    ("contexts", "adapters/max/agr_tools/udim_core.py::tile_origin", "fa20d4136a"),
    ("contexts", "adapters/max/agr_tools/udimplug_core.py::tile_offset", "d163d10dca"),
    ("contexts", "adapters/max/agr_tools/udimview_core.py::face_tile", "8fa30eddc4"),
    ("contexts", "adapters/max/agr_tools/uvlayout_core.py::tile_origin", "8b58df8f2d"),
    ("contexts", "adapters/max/agr_tools/uvlayout_core.py::tile_origin", "af2bc2e385"),
    ("contexts", "adapters/max/agr_tools/uvtile_core.py::tile_of_id", "2eed51e648"),
    ("contexts", "adapters/max/agr_tools/uvtile_core.py::tile_origin", "af2bc2e385"),
    ("contexts", "jobs/VATUTINO-SITE/npm_code.py::rename_npm_zip", "c099bec414"),

    ("contexts", "tools/materials/npm_atlas_udim.py:785", ""),

    # blender-launch rows of #1378 merged into #1424: live tools/ + src/ launches outside blender_command / run_blender
    ("contexts", "src/dt_ai/cli/shared_tools.py::command", "5a31c914e8"),
    ("contexts", "tools/flora/build_flora_npm_light.py::execute", "41b1d5662a"),
    ("contexts", "tools/flora/build_flora_npm_light.py::execute", "83b1fa0042"),
    ("contexts", "tools/flora/build_flora_star.py::_blender", "e5c254530a"),
    ("contexts", "tools/library/check_library.py::native_inspect", "c85d66fb6e"),
    ("contexts", "tools/library/migrate_windows.py::main", "9d1268b5a7"),
    ("contexts", "tools/materials/bind_ground_textures.py::_run_blender", "707f4be9fd"),
    ("contexts", "tools/methods/body/run_benchmarks.py::_blender", "18f971bee9"),
    ("contexts", "tools/methods/ground/build_variant.py::_blender", "37235a2e47"),
    ("contexts", "tools/methods/parametric_parts/mesh_recipe.py::_blender_fbx", "f5a8a5aa67"),
    ("contexts", "tools/methods/run_variant.py::run_extra", "d4b2fad230"),
    ("contexts", "tools/methods/ucx/run_benchmarks.py::main", "9c40344e89"),
    ("contexts", "tools/methods/windows/run_benchmarks.py::main", "c2afb4241e"),
    ("contexts", "tools/research/checker_mutation.py::freeze", "3457dc7d0e"),
    ("contexts", "tools/research/fbx_reader_compare.py::_blender", "8b777603c2"),
    ("contexts", "tools/sintez_parity.py::run_live.run", "56b4b34392"),
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
                if status == "own-duty" and not re.search(r"[А-Яа-яЁё]", why):
                    raise ValueError(f"{where}: own-duty needs `why` in Russian: which other duty, why not a copy")
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


def status_problems(root, rows, chains, roots, finished, baseline=LIVE_BYPASS_BASELINE):
    """Problems of the declared statuses against the real call chains (#1424); [] when every row agrees."""
    problems = []
    live_keys = set()
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
    for key in sorted(baseline - live_keys):
        problems.append(f"FIXED LIVE BYPASS {key[0]}: {key[1]} {key[2]}: no live-bypass row any more; remove it from "
                        "LIVE_BYPASS_BASELINE (tighten the ratchet)")
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
    args = ap.parse_args(argv)
    try:
        contexts = mini_yaml.load(args.contexts or args.root / "docs/architecture/contexts.yaml")
        allowed = allowlist(contexts)
        new, stale = compare(scan_for(args.root, allowed), allowed)
        problems, rows = [], []
        if not args.copies_only:
            maps = load_maps(args.root)
            if args.contexts:
                maps["contexts"] = contexts
            rows = rows_of(maps)
            roots, chains = live_chains(args.root)
            problems = status_problems(args.root, rows, chains, roots, finished_jobs(args.root, contexts))
    except (OSError, SyntaxError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.table and rows:
        print(bypass_table(rows))
    for p in problems:
        print(f"STATUS {p}")
    if args.json:
        print(json.dumps({"new": [f._asdict() for f in new],
                          "stale": [dict(zip(("rule", "path", "qualname", "hash"), k)) for k in stale],
                          "status": problems}, indent=1))
    for f in new:
        print(f"NEW COPY [{f.rule}] {f.path}:{f.line} in {f.qualname} (hash {f.digest}): use {RULES[f.rule]} "
              f"instead (or list `{f.path}::{f.qualname}` in contexts.yaml with an issue)")
    for rule, path, qual, digest in stale:
        pin = f" hash {digest}" if digest else ""
        print(f"STALE ALLOWLIST [{rule}] {path}::{qual}{pin}: not found any more; remove or fix the row in "
              "contexts.yaml")
    return 1 if new or stale or problems else 0


if __name__ == "__main__":
    # Russian report on a non-UTF-8 Windows console/pipe (no PYTHONUTF8): never crash on print.
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
