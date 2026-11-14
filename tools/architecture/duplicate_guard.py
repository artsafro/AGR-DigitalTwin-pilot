"""Duplicate guard (#1359): owned domain functions must not be re-implemented under jobs/.

Pattern: n/a | new-case: AST guard against job-local copies of owned functions (UDIM tile, delivery ZIP).

Rules (stdlib `ast`, no imports of the scanned code):
- `udim-tile`  owner adapters/max/agr_tools/udimtile_core.py (#1337). Flags the UDIM formula itself:
  an addition chain holding the constant 1001 and a `* 10` term (`1001 + u + 10 * v`), and the inverse
  `(tile - 1001) % 10` / `// 10` / `divmod(tile - 1001, 10)` / `i = tile - 1001` then `i % 10` or `i // 10`.
- `delivery-zip`  owner tools/derive/package_vpm.py (`dt derive package`, #1106). Flags a job-local
  delivery package writer: `zipfile.ZipFile(..., "w" | "x" | "a")` (mode positional or keyword).

The allowlist is the rule-tagged `duplicates` of docs/architecture/contexts.yaml: every jobs/ finding must be listed
there with its exact path:line and an issue reference, and every listed row (also the documented copies outside
jobs/) must still be found (no stale rows).
Usage: python tools/architecture/duplicate_guard.py [--root REPO] [--json]; exit 0 clean, 1 violations,
2 unreadable input (a file that does not parse is an error naming it, never skipped).
"""
import argparse
import ast
import json
import sys
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


def _const(node, value):
    return isinstance(node, ast.Constant) and type(node.value) is type(value) and node.value == value


def _add_terms(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _add_terms(node.left) + _add_terms(node.right)
    return [node]


def _is_times_ten(node):
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult) and (
        _const(node.left, 10) or _const(node.right, 10))


def _is_minus_1001(node):
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and _const(node.right, 1001)


def _udim_hits(tree):
    hits = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            terms = _add_terms(node)
            if any(_const(t, 1001) for t in terms) and any(_is_times_ten(t) for t in terms):
                hits.add(node.lineno)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.FloorDiv)) \
                and _const(node.right, 10) and _is_minus_1001(node.left):
            hits.add(node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "divmod" \
                and len(node.args) == 2 and _is_minus_1001(node.args[0]) and _const(node.args[1], 10):
            hits.add(node.lineno)
    # two-step inverse: `i = tile - 1001` then `i % 10` / `i // 10` (reported on the assignment line)
    offsets = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_minus_1001(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    offsets.setdefault(target.id, node.lineno)
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.FloorDiv)) \
                and _const(node.right, 10) and isinstance(node.left, ast.Name) and node.left.id in offsets:
            hits.add(offsets[node.left.id])
    return hits


def _is_zipfile_call(func):
    if isinstance(func, ast.Attribute) and func.attr == "ZipFile":
        return True
    return isinstance(func, ast.Name) and func.id == "ZipFile"


def _zip_hits(tree):
    hits = set()
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
                    hits.add(node.lineno)
            else:  # a computed mode cannot be proven read-only: fail closed
                hits.add(node.lineno)
    return hits


CHECKS = {"udim-tile": _udim_hits, "delivery-zip": _zip_hits}


def scan(root, scope="jobs"):
    """Return sorted findings [(rule, 'path:line')] for every *.py under root/scope; SyntaxError raises."""
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
        for rule, check in CHECKS.items():
            for line in check(tree):
                findings.add((rule, f"{rel}:{line}"))
    return sorted(findings)


def allowlist(contexts):
    """Rule-tagged duplicates of contexts.yaml -> {(rule, 'path:line'): issue}. Unknown rules raise."""
    allowed = {}
    for ctx in contexts.get("contexts", []) + [contexts.get("shared_kernel", {})]:
        for dup in ctx.get("duplicates", []):
            rule = dup.get("rule")
            if rule is None:
                continue
            if rule not in RULES:
                raise ValueError(f"unknown guard rule {rule!r} at {dup.get('at')}")
            issue = dup.get("issue", "")
            if not str(issue).startswith("#"):
                raise ValueError(f"guard allowlist entry {dup.get('at')} has no issue reference")
            key = (rule, dup["at"])
            if key in allowed:
                raise ValueError(f"duplicate allowlist entry {rule} {dup['at']}")
            allowed[key] = issue
    return allowed


def compare(findings, allowed, scope="jobs"):
    """-> (new, stale): `scope` findings not in the allowlist, allowlist rows no longer found.

    Rows outside `scope` are documentation of copies elsewhere: they must still be found (else stale), but new
    copies outside `scope` are not guarded yet."""
    found = set(findings)
    prefix = scope.rstrip("/") + "/"
    new = sorted(k for k in found - set(allowed) if k[1].startswith(prefix))
    stale = sorted(set(allowed) - found)
    return new, stale


def scan_for(root, allowed, scope="jobs"):
    """Scan `scope` plus every top-level folder an allowlist row points to."""
    tops = {scope} | {at.split("/", 1)[0] for _, at in allowed}
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
        print(json.dumps({"new": new, "stale": stale}, indent=1))
    for rule, at in new:
        print(f"NEW COPY [{rule}] {at}: use {RULES[rule]} instead (or list it in contexts.yaml with an issue)")
    for rule, at in stale:
        print(f"STALE ALLOWLIST [{rule}] {at}: not found any more; remove or fix the row in contexts.yaml")
    return 1 if new or stale else 0


if __name__ == "__main__":
    sys.exit(main())
