"""OBSERVE candidates for tools/architecture/duplicate_guard.py scan time (t_e730ebd2).

Each candidate is applied IN-PROCESS to an already imported module object and returns an undo function.
Nothing here edits duplicate_guard.py (owned by #1486 / t_ecc3dde7 while this card runs).
"""
import ast
import types

_AST = ast.AST


def _children(node):
    """Same nodes and order as ast.iter_child_nodes(node)."""
    out = []
    for name in node._fields:
        try:
            value = getattr(node, name)
        except AttributeError:
            continue
        if isinstance(value, _AST):
            out.append(value)
        elif isinstance(value, list):
            out.extend(v for v in value if isinstance(v, _AST))
    return out


class WalkCache:
    """ast.walk with a per-tree memo: the BFS list of every walked node is computed once.

    The memo keeps the node object next to its id, so a reused id of a freed node never hits; it is cleared
    after every file (`_findings`) so memory stays bounded to one tree."""

    def __init__(self):
        self.memo = {}

    def walk(self, node):
        hit = self.memo.get(id(node))
        if hit is not None and hit[0] is node:
            return hit[1]
        order = [node]
        i = 0
        while i < len(order):   # BFS, identical order to ast.walk (deque popleft + extend children)
            order.extend(_children(order[i]))
            i += 1
        order = tuple(order)
        self.memo[id(node)] = (node, order)
        return order


def r1_walk_memo(dg):
    """R1: memoised ast.walk inside duplicate_guard only; memo cleared after each file's _findings."""
    cache = WalkCache()
    proxy = types.ModuleType("ast")
    proxy.__dict__.update(vars(ast))
    proxy.walk = cache.walk
    orig_ast, orig_findings = dg.ast, dg._findings

    def _findings(tree, rel):
        try:
            return orig_findings(tree, rel)
        finally:
            cache.memo.clear()

    dg.ast, dg._findings = proxy, _findings

    def undo():
        dg.ast, dg._findings = orig_ast, orig_findings
        cache.memo.clear()
    return undo


def m0_drop_calls(dg):
    """Mutation check of the parity guard (must FAIL parity): walk skips every ast.Call node."""
    proxy = types.ModuleType("ast")
    proxy.__dict__.update(vars(ast))
    proxy.walk = lambda node: [n for n in ast.walk(node) if not isinstance(n, ast.Call)]
    orig = dg.ast
    dg.ast = proxy

    def undo():
        dg.ast = orig
    return undo


class LazyScopes:
    """Mapping view of dg._scopes(tree) computed on the first lookup (t_b1bb763f, R4).

    _findings reads scopes only for a hit; a file without hits never pays the full recursive visit."""

    def __init__(self, tree, build):
        self.tree, self.build, self.data = tree, build, None

    def __getitem__(self, key):
        if self.data is None:
            self.data = self.build(self.tree)
        return self.data[key]


def r4_lazy_scopes(dg):
    """R4: _scopes(tree) becomes lazy - the visit runs only when _findings looks up a hit's scope."""
    orig = dg._scopes
    dg._scopes = lambda tree: LazyScopes(tree, orig)

    def undo():
        dg._scopes = orig
    return undo


def m1_scope_module(dg):
    """Mutation check of the parity guard (must FAIL parity): every scope lookup answers <module>."""
    orig = dg._scopes
    dg._scopes = lambda tree: {id(n): dg.MODULE for n in ast.walk(tree)}

    def undo():
        dg._scopes = orig
    return undo


CANDIDATES = {"r1_walk_memo": r1_walk_memo, "m0_drop_calls": m0_drop_calls,
              "r4_lazy_scopes": r4_lazy_scopes, "m1_scope_module": m1_scope_module}


def apply(dg, names):
    undos = [CANDIDATES[n](dg) for n in names]

    def undo():
        for u in reversed(undos):
            u()
    return undo
