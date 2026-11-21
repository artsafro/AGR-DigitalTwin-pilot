"""Standing #9 t_a334c185 (new-case: duplicate_guard walk memo + lazy scopes/int names): the scan's memoised
`_walk` must visit exactly what `ast.walk` visits, in the same order, and must not outlive one file's scan;
lazy `_scopes` / `_int_names` must still produce qualnames and named-constant hits.
Timing and full-repo parity: docs/research/autoresearch-repo-guards-adopt.md.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/architecture"))
import duplicate_guard as dg  # noqa: E402

SOURCE = '''
BASE = 1001


class Packer:
    def tile(self, u, v):
        return BASE + int(u) + 10 * int(v)


def f(x, *a, k=1, **kw):
    """doc"""
    return [y async for y in x] if x else {k: v for k, v in kw.items()}
'''


def test_walk_matches_ast_walk_order_on_real_files():
    for rel in (ROOT / "tools/architecture/duplicate_guard.py", Path(__file__)):
        tree = ast.parse(rel.read_text(encoding="utf-8"))
        try:
            assert list(dg._walk(tree)) == list(ast.walk(tree))
            inner = tree.body[-1]
            assert list(dg._walk(inner)) == list(ast.walk(inner))
            assert dg._walk(tree) is dg._walk(tree)   # memo hit
        finally:
            dg._WALKS.clear()


def test_memo_is_cleared_after_each_file_scan():
    dg._WALKS.clear()
    findings = dg.scan_text(SOURCE, "jobs/X/a.py")
    assert dg._WALKS == {}
    # lazy _int_names: BASE = 1001 still resolves; lazy _scopes: the qualname is still the method's
    assert [(f.rule, f.qualname) for f in findings] == [("udim-tile", "Packer.tile")]


def test_memo_is_cleared_when_the_scan_raises(monkeypatch):
    def boom(tree):
        dg._walk(tree)
        raise RuntimeError("check failed")

    monkeypatch.setitem(dg.CHECKS, "udim-tile", boom)
    dg._WALKS.clear()
    try:
        dg.scan_text(SOURCE, "jobs/X/a.py")
    except RuntimeError:
        pass
    assert dg._WALKS == {}


def test_no_hit_file_never_builds_scopes_or_int_names(monkeypatch):
    """Edge (review r1): a file with no rule hit returns [] without building the lazy tables."""
    calls = []
    monkeypatch.setattr(dg, "_scopes", lambda tree: calls.append("scopes") or {})
    monkeypatch.setattr(dg, "_int_names", lambda tree: calls.append("int_names") or {})
    dg._WALKS.clear()
    assert dg.scan_text("def g(a, b):\n    return a + b\n", "jobs/X/b.py") == []
    assert "scopes" not in calls          # _scopes is built only on the first hit
    calls.clear()
    assert dg.scan_text("def h():\n    return [1, 2]\n", "jobs/X/c.py") == []
    assert calls == []                    # no Name lookup -> _int_names is never built either
    assert dg._WALKS == {}
