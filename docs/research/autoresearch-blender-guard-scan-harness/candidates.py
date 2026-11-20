"""Candidates for the Blender exit-code guard scan bench (standing #11, t_95ce9e1f).

Each candidate is ``make(g) -> callable(source) -> list[(lineno, kind)]`` built over the guard module ``g``
(baseline helpers and regexes are reused, never copied), so it can replace ``g._scan_py_source``.
"""
from __future__ import annotations

import ast
from collections import deque
from typing import Any


def r1_one_walk(g, _direct_only=False):
    """One BFS (``ast.walk`` order); flags aggregated bottom-up from string constants."""
    AST = ast.AST
    Constant, List, Tuple, Call = ast.Constant, ast.List, ast.Tuple, ast.Call
    Import, ImportFrom = ast.Import, ast.ImportFrom
    bg_re, ex_re = g._BACKGROUND.search, g._EXIT_CODE.search
    exec_modules, exec_attrs = g._EXEC_MODULES, g._EXEC_ATTRS

    def scan(source: str):
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            return []
        bindings = dict(g._SEED_BINDINGS)
        parent: list[int] = []
        bits: list[int] = []
        lits: list[tuple[int, Any]] = []
        calls: list[tuple[int, Any]] = []
        todo: deque[tuple[Any, int]] = deque([(tree, -1)])
        pop, push = todo.popleft, todo.append
        i = -1
        while todo:
            node, up = pop()
            i += 1
            parent.append(up)
            bits.append(0)
            cls = type(node)
            if cls is Constant:
                v = node.value
                if isinstance(v, str):
                    b = (1 if bg_re(v) else 0) | (2 if ex_re(v) else 0)
                    j = up
                    while b and j >= 0:
                        new = b & ~bits[j]
                        if not new:
                            break
                        bits[j] |= new
                        b = new
                        j = -1 if _direct_only else parent[j]
            elif cls is List or cls is Tuple:
                lits.append((i, node))
            elif cls is Call:
                calls.append((i, node))
            elif cls is Import:
                for alias in node.names:
                    if alias.name in exec_modules:
                        bindings[alias.asname or alias.name] = ("module", alias.name)
            elif cls is ImportFrom:
                mod = node.module or ""
                if mod in exec_modules:
                    for alias in node.names:
                        if alias.name == "*":
                            for attr in exec_attrs:
                                bindings[attr] = ("attr", mod, attr)
                            continue
                        if alias.name in exec_attrs:
                            bindings[alias.asname or alias.name] = ("attr", mod, alias.name)
            for name in node._fields:
                try:
                    field = getattr(node, name)
                except AttributeError:
                    continue
                if isinstance(field, AST):
                    push((field, i))
                elif isinstance(field, list):
                    for item in field:
                        if isinstance(item, AST):
                            push((item, i))
        out: list[tuple[int, int, str]] = []
        for idx, node in lits:
            if bits[idx] == 1:
                out.append((idx, node.lineno, "python argv literal"))
        for idx, node in calls:
            if g._is_exec_call(node, bindings):
                command = g._command_string_arg(node)
                if command is not None and g._shell_violates(command):
                    out.append((idx, node.lineno, "python command string"))
        out.sort()
        return [(ln, kind) for _i, ln, kind in out]

    return scan


def m0_direct_children_only(g):
    """Mutation witness: R1 with propagation stopped at the direct parent (must FAIL generated parity)."""
    return r1_one_walk(g, _direct_only=True)


CANDIDATES = {"r1_one_walk": r1_one_walk, "m0_direct_children_only": m0_direct_children_only}
