"""Call chains of the live commands and routes (#1424): which repo files a current command or route stage reaches.

Pattern: n/a | new-case: stdlib AST reachability (imports + `.py` path strings) from the live roots, used by
duplicate_guard to derive the status of every duplicates row from real call chains, not from its path.

Live roots (`live_roots`), each with the reason shown to the user:
- console scripts of pyproject.toml (`dt`, `agr`, `agr-mcp`): the module of every `name = "pkg.mod:func"` entry;
- AGR Tools for 3ds Max: every `.py` of the MZP list `FILES` in tools/max/build_agr_tools.py (what ships in Max);
- route maps: every `.py` a route events YAML names (local context owners, stage and branch evidence) and every
  context owner of the context maps - the route uses that file today, with or without an `agr`/`dt` command;
- every script under tools/ (the shared toolbox: nothing outside jobs/ is a frozen historical copy, #1424).
Hotspot evidence is not a root: a hotspot names a problem, not a step the route runs.
Edges (`edges`): `import` / `from ... import` anywhere in the file (also lazy imports inside functions), resolved to
repo files (src/ packages with their `__init__` chain, repo-root packages, sibling modules of a script folder,
relative imports), and string literals ending in `.py` that name a repo file (repo-relative or a sibling): this is
how `agr validate`, `dt derive` and the Blender runners start scripts in a subprocess.
A file that does not parse is an error naming it (never skipped). Over-approximation is deliberate: an import that
is never executed still makes the file live (fail closed for a `historical` claim).
"""
import ast
import re
from collections import deque
from pathlib import Path

if __package__ in (None, ""):
    import mini_yaml  # noqa: E402  (tools/architecture on sys.path, see duplicate_guard)
else:
    from . import mini_yaml

PY_STRING = re.compile(r"^[\w./\\-]+\.py$")
MZP_BUILDER = "tools/max/build_agr_tools.py"
MZP_PACKAGE = "adapters/max/agr_tools"


def parse(root, rel):
    """AST of root/rel; SyntaxError names the file."""
    try:
        return ast.parse((Path(root) / rel).read_bytes(), filename=rel)
    except SyntaxError as exc:
        raise SyntaxError(f"{rel}: cannot parse ({exc.msg}, line {exc.lineno})") from None


def _module_files(root, dotted):
    """Repo files a dotted module name may be: src/ package or root package, module or package __init__,
    plus every parent package __init__ (importing a.b.c runs a/__init__ and a/b/__init__)."""
    parts = dotted.split(".")
    out = []
    for base in ("src", ""):
        top = Path(root) / base if base else Path(root)
        for i in range(1, len(parts) + 1):
            stem = "/".join(parts[:i])
            for cand in (f"{stem}.py", f"{stem}/__init__.py"):
                if (top / cand).is_file():
                    out.append(f"{base}/{cand}" if base else cand)
    return out


def edges(root, rel, tree=None):
    """Repo files root/rel reaches directly (imports + `.py` strings), sorted."""
    root = Path(root)
    tree = tree if tree is not None else parse(root, rel)
    here = Path(rel).parent
    out = set()

    def sibling(name):
        cand = (here / f"{name.replace('.', '/')}.py").as_posix()
        if (root / cand).is_file():
            out.add(cand)
        pkg = (here / name.replace(".", "/") / "__init__.py").as_posix()
        if (root / pkg).is_file():
            out.add(pkg)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.update(_module_files(root, alias.name))
                sibling(alias.name)
        elif isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names]
            if node.level:
                base = Path(rel).parent
                for _ in range(node.level - 1):
                    base = base.parent
                mod = (base / node.module.replace(".", "/")) if node.module else base
                for cand in [f"{mod.as_posix()}.py", f"{mod.as_posix()}/__init__.py"] + \
                        [f"{mod.as_posix()}/{n}.py" for n in names]:
                    if (root / cand).is_file():
                        out.add(cand)
            elif node.module:
                out.update(_module_files(root, node.module))
                sibling(node.module)
                for n in names:
                    out.update(_module_files(root, f"{node.module}.{n}"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and PY_STRING.match(node.value):
            text = node.value.replace("\\", "/")
            for cand in (text, (here / text).as_posix()):
                if (root / cand).is_file():
                    out.add(Path(cand).as_posix())
    out.discard(Path(rel).as_posix())
    return sorted(out)


def _pyproject_roots(root):
    text = (Path(root) / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^\[project\.scripts\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    roots = {}
    for name, target in re.findall(r'^([\w-]+)\s*=\s*"([\w.]+):\w+"', block.group(1) if block else "", re.M):
        files = _module_files(root, target)
        if not files:
            raise FileNotFoundError(f"pyproject.toml script {name} -> {target}: module not found")
        roots[files[-1]] = f"команда {name}"
    if not roots:
        raise ValueError("pyproject.toml has no [project.scripts]: no live command roots")
    return roots


def _mzp_roots(root):
    tree = parse(root, MZP_BUILDER)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "FILES" for t in node.targets):
            names = ast.literal_eval(node.value)
            break
    else:
        raise ValueError(f"{MZP_BUILDER}: no FILES list (AGR Tools MZP contents)")
    roots = {}
    for name in names:
        if name.endswith(".py"):
            rel = f"{MZP_PACKAGE}/{name}"
            if not (Path(root) / rel).is_file():
                raise FileNotFoundError(f"{MZP_BUILDER} FILES names missing {rel}")
            roots[rel] = "AGR Tools (MZP для Max)"
    return roots


def _route_roots(root, routes, context_maps):
    roots = {}

    def add(path, why):
        if isinstance(path, str) and path.endswith(".py") and (Path(root) / path).is_file():
            roots.setdefault(path, why)

    for name, events in routes.items():
        for c in events.get("local_contexts", []):
            add(c.get("owner"), f"маршрут {name}: владелец {c.get('id')}")
        for s in events.get("stages", []):
            for p in s.get("evidence", []):
                add(p, f"маршрут {name}: этап {s.get('id')}")
            for br in s.get("branches", []):
                for p in br.get("evidence", []):
                    add(p, f"маршрут {name}: этап {s.get('id')}/{br.get('id')}")
    for name, cmap in context_maps.items():
        # Explicit current job commands/candidates are not discovered by Python imports alone (#1441).
        # Pin the actual source command as evidence, not merely the existence of an old job script.
        for entry in cmap.get("entrypoints", []):
            rel, evidence, match = (entry.get(k) for k in ("owner", "evidence", "match"))
            if not all(isinstance(v, str) and v.strip() for v in (rel, evidence, match)):
                raise ValueError(f"{name}: entrypoint needs owner, evidence and match")
            for path in (rel, evidence):
                candidate = Path(root) / path
                if (not candidate.is_file() or candidate.resolve().relative_to(Path(root).resolve()).as_posix() != path):
                    raise ValueError(f"{name}: entrypoint missing or aliased path {path}")
            if not rel.endswith(".py") or match not in (Path(root) / evidence).read_text(encoding="utf-8"):
                raise ValueError(f"{name}: entrypoint {rel}: stale or unsupported evidence {evidence}")
            add(rel, f"команда / кандидат {evidence}: {match}")
        for c in [cmap.get("shared_kernel", {})] + cmap.get("contexts", []):
            add(c.get("owner"), f"карта {name}: владелец {c.get('id')}")
    return roots


def _tool_roots(root):
    """Every script under tools/ is a command a person or agent starts today (shared toolbox, not a job)."""
    base = Path(root) / "tools"
    if not base.is_dir():
        raise FileNotFoundError(f"live root folder missing: {base}")
    return {p.relative_to(root).as_posix(): "инструмент tools/ (свой запуск)" for p in sorted(base.rglob("*.py"))}


def live_roots(root, routes, context_maps):
    """{repo file: Russian reason} of every live root (commands, AGR Tools MZP, route maps, tools/ scripts).
    The first reason wins in this order, so a tools/ file a route names shows the route."""
    roots = {}
    for part in (_pyproject_roots(root), _mzp_roots(root), _route_roots(root, routes, context_maps),
                 _tool_roots(root)):
        for rel, why in part.items():
            roots.setdefault(rel, why)
    return roots


def reach(root, roots):
    """{repo file: chain [root, ..., file]} for every file reachable from the roots (BFS, shortest chain)."""
    chains = {}
    queue = deque()
    for rel in sorted(roots):
        chains[rel] = [rel]
        queue.append(rel)
    while queue:
        rel = queue.popleft()
        for nxt in edges(root, rel):
            if nxt not in chains and nxt.endswith(".py"):
                chains[nxt] = chains[rel] + [nxt]
                queue.append(nxt)
    return chains


def load_live(root, routes=None, context_maps=None):
    """(roots, chains) for the repo at root, reading the route and context maps of route_map when not given."""
    root = Path(root)
    if routes is None or context_maps is None:
        if __package__ in (None, ""):
            import route_map  # noqa: E402
        else:
            from . import route_map
        routes = routes if routes is not None else {
            n: mini_yaml.load(root / p) for n, p in route_map.route_events().items()}
        context_maps = context_maps if context_maps is not None else {
            n: mini_yaml.load(root / p) for n, p in route_map.context_maps().items()}
    roots = live_roots(root, routes, context_maps)
    return roots, reach(root, roots)
