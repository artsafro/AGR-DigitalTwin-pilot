"""Duplicate guard (#1359): owned domain functions must not be re-implemented under jobs/.

Pattern: n/a | new-case: AST guard against job-local copies of owned functions (UDIM tile, delivery ZIP).

Rules (stdlib `ast`, no imports of the scanned code):
- `udim-tile`  owner adapters/max/agr_tools/udimtile_core.py (#1337). Flags the UDIM formula itself:
  an addition chain holding the constant 1001 and a `* 10` term (`1001 + u + 10 * v`), and the inverse
  `(tile - 1001) % 10` / `// 10` / `divmod(tile - 1001, 10)` / `i = tile - 1001` then `i % 10` or `i // 10`.
  1001 and 10 also match a name bound to that int anywhere in the file (`FIRST_UDIM = 1001`, `U = 10`), and any
  job-local `def` named udim_tile / udim_of_cell / tile_origin / face_tile is a copy (PR #1368 r1).
- `delivery-zip`  owner tools/derive/package_vpm.py (`dt derive package`, #1106). Flags a job-local
  delivery package writer: `zipfile.ZipFile(..., "w" | "x" | "a")` (mode positional or keyword).

The allowlist is the rule-tagged `duplicates` of docs/architecture/contexts.yaml: every jobs/ finding must be listed
there with an issue reference, and every listed row (also the documented copies outside jobs/) must still be found
(no stale rows). A row is keyed by `at: "path.py::qualname"` - the file and the enclosing function/class
(`<module>` at top level), never by a bare line number (#1387): lines inserted above or inside the function do not
make it NEW or STALE. Optional `hash:` (10 hex, `sha1(ast.unparse(node))`, printed with every NEW COPY) pins one
copy inside the function; a row without it covers every copy of that rule in that function.
Usage: python tools/architecture/duplicate_guard.py [--root REPO] [--json]; exit 0 clean, 1 violations,
2 unreadable input (a file that does not parse is an error naming it, never skipped).
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
    "delivery-zip": "tools/derive/package_vpm.py",
}
WRITE_MODES = {"w", "x", "a"}


OWNED_NAMES = {"udim-tile": {"udim_tile", "udim_of_cell", "tile_origin", "face_tile"}}


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


CHECKS = {"udim-tile": _udim_hits, "delivery-zip": _zip_hits}
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


def compare(findings, allowed, scope="jobs"):
    """-> (new, stale): `scope` findings no row covers, allowlist rows that cover no finding.

    Rows outside `scope` are documentation of copies elsewhere: they must still be found (else stale), but new
    copies outside `scope` are not guarded yet."""
    prefix = scope.rstrip("/") + "/"
    new = sorted(f for f in set(findings) if f.path.startswith(prefix) and not any(_covers(k, f) for k in allowed))
    stale = sorted(k for k in allowed if not any(_covers(k, f) for f in findings))
    return new, stale


def scan_for(root, allowed, scope="jobs"):
    """Scan `scope` plus every top-level folder an allowlist row points to."""
    tops = {scope} | {key[1].split("/", 1)[0] for key in allowed}
    findings = []
    for top in sorted(tops):
        findings += scan(root, top)
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Duplicate guard (#1359): owned functions vs jobs/ copies")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--contexts", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        contexts = mini_yaml.load(args.contexts or args.root / "docs/architecture/contexts.yaml")
        allowed = allowlist(contexts)
        new, stale = compare(scan_for(args.root, allowed), allowed)
    except (OSError, SyntaxError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"new": [f._asdict() for f in new],
                          "stale": [dict(zip(("rule", "path", "qualname", "hash"), k)) for k in stale]}, indent=1))
    for f in new:
        print(f"NEW COPY [{f.rule}] {f.path}:{f.line} in {f.qualname} (hash {f.digest}): use {RULES[f.rule]} "
              f"instead (or list `{f.path}::{f.qualname}` in contexts.yaml with an issue)")
    for rule, path, qual, digest in stale:
        pin = f" hash {digest}" if digest else ""
        print(f"STALE ALLOWLIST [{rule}] {path}::{qual}{pin}: not found any more; remove or fix the row in "
              "contexts.yaml")
    return 1 if new or stale else 0


if __name__ == "__main__":
    sys.exit(main())
