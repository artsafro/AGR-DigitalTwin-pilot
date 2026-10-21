"""Contract: every test that can launch real 3ds Max carries the opt-in ``max`` marker (#518).

Pattern: n/a | new-case: issue-518 AST scan keeps real-Max tests out of the default pytest lane.

A test "launches real Max" when its body, a module-level helper it calls or a module-level fixture
it requests (transitively):
- calls ``X.default_adapter()`` unless an earlier top-level ``monkeypatch.setattr(X, '_call', fake)``
  of the same function still holds: same receiver, ``fake`` is not the real transport, nothing
  restores/reads ``_call``, calls a restorer or rebinds ``X``; any weaker evidence counts as a launch, or
- references a ``dcc_batch.py`` path: a string literal ending in ``dcc_batch.py``, the ``DCC_BATCH``
  attribute, or a module-level name bound to a ``dcc_batch.py`` path.
Such a test without ``@pytest.mark.max`` (function, class, or the effective = last, unambiguous module
``pytestmark``; every mark is distrusted when anything reads/mutates ``pytestmark``) fails this
contract, because the default ``addopts`` deselects ``max`` and nothing else keeps it off the shared
cross-card Max lock.
"""
from __future__ import annotations

import ast
import itertools
import re
from pathlib import Path

import pytest
from _pytest.mark.expression import Expression

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
DCC_BATCH_LITERAL = re.compile(r"(^|[\\/])dcc_batch\.py$")
LANE_MARKERS = ("blender", "dcc", "acad", "perf", "max")


def _is_max_mark(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        node = node.func
    return (isinstance(node, ast.Attribute) and node.attr == "max"
            and isinstance(node.value, ast.Attribute) and node.value.attr == "mark")


def _marked(decorators: list[ast.expr]) -> bool:
    return any(_is_max_mark(d) for d in decorators)


def _pytestmark_bindings(node: ast.AST) -> list[ast.AST]:
    """Every node under ``node`` that (re)binds or deletes the name ``pytestmark``."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id == "pytestmark" and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.append(n)
        elif isinstance(n, (ast.Import, ast.ImportFrom)) and any(
                (i.asname or i.name.split(".")[0]) == "pytestmark" for i in n.names):
            out.append(n)
        elif isinstance(n, (ast.Global, ast.Nonlocal)) and "pytestmark" in n.names:
            out.append(n)
    return out


def _marks_mutable(tree: ast.Module) -> bool:
    """True when anything READS ``pytestmark`` (name or attribute): ``pytestmark.clear()``, an alias,
    ``test_a.pytestmark.pop()`` ... can change the effective marks without a rebinding, so no mark
    in the module is trusted (fail closed)."""
    return any((isinstance(n, ast.Name) and n.id == "pytestmark" and isinstance(n.ctx, ast.Load))
               or (isinstance(n, ast.Attribute) and n.attr == "pytestmark") for n in ast.walk(tree))


def _module_marked(tree: ast.Module) -> bool:
    """Effective module mark = the LAST binding of ``pytestmark``; fail closed when it is ambiguous.

    Marked only when every binding is a top-level ``pytestmark = ...`` statement, the last one
    carries ``max`` as a literal mark expression (not an alias name) and nothing reads or mutates
    ``pytestmark``. A reset (``pytestmark = []``), an augmented, conditional, deleted, imported,
    ``global`` or nested binding, or ``pytestmark.clear()`` makes the module count as unmarked.
    """
    if _marks_mutable(tree):
        return False
    top = [s for s in tree.body if _pytestmark_bindings(s)]
    plain = [s for s in top if (isinstance(s, ast.Assign) and len(s.targets) == 1
                                and isinstance(s.targets[0], ast.Name))
             or (isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name))]
    if not top or plain != top or len(_pytestmark_bindings(tree)) != len(top):
        return False
    last = top[-1]
    value = last.value
    if value is None:
        return False
    values = value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value]
    return any(_is_max_mark(v) for v in values)


def _dcc_batch_names(tree: ast.Module) -> set[str]:
    names = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and not isinstance(stmt.value, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and DCC_BATCH_LITERAL.search(n.value)
                   for n in ast.walk(stmt.value)):
                names.update(t.id for t in stmt.targets if isinstance(t, ast.Name))
    return names


RESTORERS = {"undo", "reload", "delattr", "stopall", "context"}  # calls that may restore the real _call


def _is_call_token(node: ast.AST) -> bool:
    """``X._call`` (any context) or the string ``'_call'``: a read, write or restore of the transport."""
    return ((isinstance(node, ast.Attribute) and node.attr == "_call")
            or (isinstance(node, ast.Constant) and node.value == "_call"))


def _bound_names(node: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out.update((i.asname or i.name.split(".")[0]) for i in n.names)
    return out


def _binding_stmts(tree: ast.Module) -> dict[str, list[ast.AST]]:
    """Every name -> the statements (anywhere in the module) that bind it."""
    out: dict[str, list[ast.AST]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.stmt) and not isinstance(n, (ast.Module,)):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = {n.name}
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor,
                                ast.With, ast.AsyncWith, ast.Import, ast.ImportFrom, ast.Delete)):
                names = _bound_names(n) if not isinstance(n, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith)) \
                    else _bound_names(getattr(n, "target", None) or ast.Tuple(
                        elts=[i.optional_vars for i in n.items if i.optional_vars], ctx=ast.Store()))
            else:
                continue
            for name in names:
                out.setdefault(name, []).append(n)
        elif isinstance(n, ast.NamedExpr):
            out.setdefault(n.target.id, []).append(n)
    return out


def _tainted_names(tree: ast.Module) -> set[str]:
    """Names that may hold the real transport: bound (anywhere) by code that touches ``_call`` or a
    tainted name; computed to a fixpoint (``orig = m._call; fake = orig`` taints both)."""
    bindings = _binding_stmts(tree)
    tainted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, stmts in bindings.items():
            if name in tainted:
                continue
            if any(_is_call_token(n) or (isinstance(n, ast.Name) and n.id in tainted and n.id != name)
                   for s in stmts for n in ast.walk(s)):
                tainted.add(name)
                changed = True
    return tainted


def _call_patch_target(stmt: ast.stmt, func: ast.AST, tainted: set[str]) -> str | None:
    """``ast.dump`` of X for a top-level ``monkeypatch.setattr(X, '_call', <fake>)``, else None.

    ``monkeypatch`` must be a parameter of ``func``; ``<fake>`` must not touch ``_call`` or a
    tainted name (``max_adapter._call``, ``original``, ``lambda *a: original(*a)`` are no-op or
    restoring patches, not mocks)."""
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return None
    call = stmt.value
    params = {a.arg for a in getattr(func, "args", ast.arguments(args=[], kwonlyargs=[])).args}
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == "setattr"
            and isinstance(call.func.value, ast.Name) and call.func.value.id == "monkeypatch"
            and "monkeypatch" in params and len(call.args) == 3 and not call.keywords):
        return None
    receiver, name, value = call.args
    if not (isinstance(name, ast.Constant) and name.value == "_call" and isinstance(receiver, ast.Name)):
        return None
    if any(_is_call_token(n) or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(value)):
        return None
    return receiver.id


def _launches(node: ast.AST):
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            callee = n.func
            name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", None)
            if name == "default_adapter":
                yield callee


def _direct_hit(func: ast.AST, dcc_names: set[str], tainted: set[str], helper_tampered: bool = False) -> bool:
    """True when ``func`` may launch real Max.

    ``X.default_adapter()`` counts as mocked only when ALL of these hold (else it is a launch):
    - an EARLIER top-level statement of the same function is ``monkeypatch.setattr(X, '_call', fake)``
      for the very same receiver name ``X`` with a ``fake`` that is not the real transport;
    - no other statement of the function touches ``_call`` (restore ``X._call = original``,
      ``setattr``/``delattr``/``vars(X)['_call']``, reading it) or calls a restorer (``undo``, ``reload``...);
    - no module-level helper/fixture the function reaches touches ``_call`` or calls a restorer;
    - ``X`` is not rebound after the patch nor anywhere nested (a re-import gives the real module).
    """
    body = getattr(func, "body", [])
    proofs = {i: _call_patch_target(s, func, tainted) for i, s in enumerate(body)}
    proof_names = {id(s.value.args[1]) for i, s in enumerate(body) if proofs[i] is not None}
    tampered = any(
        (_is_call_token(n) and id(n) not in proof_names)
        or (isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", None)) in RESTORERS)
        for n in ast.walk(func))
    tampered = tampered or helper_tampered
    nested_binds = {g for n in ast.walk(func) if isinstance(n, (ast.Global, ast.Nonlocal)) for g in n.names}
    nested_binds |= {b for n in ast.walk(func) if n is not func
                     and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))
                     for b in _bound_names(n)}
    patched: set[str] = set()
    for i, stmt in enumerate(body):
        rebinds = _bound_names(stmt) | nested_binds
        for callee in _launches(stmt):
            if tampered or not isinstance(callee, ast.Attribute) or not isinstance(callee.value, ast.Name) \
                    or callee.value.id not in patched:
                return True
        patched -= rebinds
        if proofs[i] is not None:
            patched.add(proofs[i])
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and node.id in dcc_names:
            return True
        elif isinstance(node, ast.Attribute) and node.attr == "DCC_BATCH":
            return True
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and DCC_BATCH_LITERAL.search(node.value):
            return True
    return False


def scan_source(source: str, label: str = "<src>") -> list[str]:
    """Return ``label::test`` ids that launch real Max without the ``max`` marker."""
    tree = ast.parse(source)
    dcc_names = _dcc_batch_names(tree)
    helpers = {s.name: s for s in tree.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))}
    tainted = _tainted_names(tree)
    memo: dict[str, bool] = {}

    def callees(func: ast.AST) -> set[str]:
        called = {n.func.id for n in ast.walk(func) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            called |= {a.arg for a in func.args.args + func.args.kwonlyargs}  # requested fixtures
        return called & helpers.keys()

    def helper_tampered(func: ast.AST) -> bool:
        """A reachable module-level helper/fixture touches ``_call`` or calls a restorer."""
        todo, seen = list(callees(func)), set()
        while todo:
            name = todo.pop()
            if name in seen:
                continue
            seen.add(name)
            if any(_is_call_token(n) or (isinstance(n, ast.Call)
                   and getattr(n.func, "attr", getattr(n.func, "id", None)) in RESTORERS)
                   for n in ast.walk(helpers[name])):
                return True
            todo.extend(callees(helpers[name]))
        return False

    def hits(func: ast.AST, seen: frozenset[str]) -> bool:
        if _direct_hit(func, dcc_names, tainted, helper_tampered(func)):
            return True
        for name in sorted(callees(func) - seen):
            if name not in memo:
                memo[name] = hits(helpers[name], seen | {name})
            if memo[name]:
                return True
        return False

    module_marked = _module_marked(tree)
    trust_marks = not _marks_mutable(tree)
    found = []
    candidates = [(s, False, "") for s in tree.body]
    while candidates:
        stmt, class_marked, prefix = candidates.pop(0)
        if isinstance(stmt, ast.ClassDef) and stmt.name.startswith("Test"):
            candidates.extend((s, class_marked or _marked(stmt.decorator_list), f"{prefix}{stmt.name}::")
                              for s in stmt.body)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name.startswith("test"):
            if not (module_marked or (trust_marks and (class_marked or _marked(stmt.decorator_list)))) \
                    and hits(stmt, frozenset({stmt.name})):
                found.append(f"{label}::{prefix}{stmt.name}")
    return found


def _repo_violations() -> list[str]:
    out = []
    for path in sorted(TESTS.rglob("*.py")):
        out += scan_source(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix())
    return out


def test_no_unmarked_real_max_test_in_tests():
    assert _repo_violations() == []


def test_scanner_finds_the_known_real_max_tests_when_unmarked():
    """Non-vacuous: stripping the marker re-exposes exactly the #518 leaks."""
    expected = {
        "tests/test_review_publish.py": "test_max_dependent_merge_skips_when_max_absent",
        "tests/test_review_round2.py": "test_real_max_keeps_fbx_mesh_named_review_camera",
    }
    for rel, name in expected.items():
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert f"@pytest.mark.max\ndef {name}(" in source
        stripped = source.replace(f"@pytest.mark.max\ndef {name}(", f"def {name}(")
        assert f"{rel}::{name}" in scan_source(stripped, rel)


SYNTHETIC = {
    "default_adapter_unmarked": ("import max_adapter\ndef test_a():\n    max_adapter.default_adapter().selftest(1, 2, 3)\n", 1),
    "default_adapter_marked": ("import pytest\n@pytest.mark.max\ndef test_a():\n    m.default_adapter().build()\n", 0),
    "marker_called_form": ("import pytest\n@pytest.mark.max()\ndef test_a():\n    m.default_adapter()\n", 0),
    "module_pytestmark": ("import pytest\npytestmark = [pytest.mark.dcc, pytest.mark.max]\ndef test_a():\n    m.default_adapter()\n", 0),
    "module_pytestmark_other": ("import pytest\npytestmark = pytest.mark.dcc\ndef test_a():\n    m.default_adapter()\n", 1),
    "class_marked": ("import pytest\n@pytest.mark.max\nclass TestA:\n    def test_a(self):\n        m.default_adapter()\n", 0),
    "class_unmarked": ("class TestA:\n    def test_a(self):\n        m.default_adapter()\n", 1),
    "helper_literal": ("def _run(a):\n    a._call([a.SCRIPTS / 'dcc_batch.py', 'max'])\ndef test_a():\n    _run(1)\n", 1),
    "helper_chain": ("def _b():\n    run('C:/x/dcc_batch.py')\ndef _a():\n    _b()\ndef test_a():\n    _a()\n", 1),
    "recursive_helper": ("def _a():\n    _a()\ndef test_a():\n    _a()\n", 0),
    "fixture_launch": ("import pytest\n@pytest.fixture\ndef scene():\n    return m.default_adapter().selftest()\ndef test_a(scene):\n    pass\n", 1),
    "module_const_name": ("from pathlib import Path\nDCC = Path(r'C:/s/dcc_batch.py')\ndef test_a():\n    run([str(DCC)])\n", 1),
    "attribute_DCC_BATCH": ("def test_a():\n    run([mod.DCC_BATCH, 'max'])\n", 1),
    "monkeypatched_call": ("def test_a(monkeypatch):\n    monkeypatch.setattr(m, '_call', f)\n    m.default_adapter()\n", 0),
    # review round 1 (PR #522) bypass witnesses: each must report the unmarked test
    "patch_unrelated_module": ("def test_live(monkeypatch):\n    monkeypatch.setattr(other_module, '_call', fake)\n"
                               "    max_adapter.default_adapter().selftest()\n", 1),
    "patch_unreachable_if_false": ("def test_live(monkeypatch):\n    if False:\n"
                                   "        monkeypatch.setattr(max_adapter, '_call', fake)\n"
                                   "    max_adapter.default_adapter().selftest()\n", 1),
    "pytestmark_reset_after_max": ("import pytest\npytestmark = pytest.mark.max\npytestmark = []\n"
                                   "def test_live():\n    max_adapter.default_adapter().selftest()\n", 1),
    # review round 2 (PR #522) bypass witnesses: each must report the unmarked test
    "patch_then_restore_original": ("def test_live(monkeypatch):\n    original = max_adapter._call\n"
                                    "    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                                    "    max_adapter._call = original\n    max_adapter.default_adapter().selftest()\n", 1),
    "patch_call_to_itself": ("def test_live(monkeypatch):\n"
                             "    monkeypatch.setattr(max_adapter, '_call', max_adapter._call)\n"
                             "    max_adapter.default_adapter().selftest()\n", 1),
    "pytestmark_list_cleared": ("import pytest\npytestmark = [pytest.mark.max]\npytestmark.clear()\n"
                                "def test_live():\n    max_adapter.default_adapter().selftest()\n", 1),
    # further round-2 edges: stale/no-op proof and mutable marks
    "patch_wrapper_of_original": ("ORIG = max_adapter._call\ndef test_live(monkeypatch):\n"
                                  "    monkeypatch.setattr(max_adapter, '_call', lambda *a: ORIG(*a))\n"
                                  "    max_adapter.default_adapter()\n", 1),
    "patch_alias_chain_of_original": ("ORIG = max_adapter._call\nFAKE = ORIG\ndef test_live(monkeypatch):\n"
                                      "    monkeypatch.setattr(max_adapter, '_call', FAKE)\n"
                                      "    max_adapter.default_adapter()\n", 1),
    "patch_value_getattr": ("def test_live(monkeypatch):\n"
                            "    monkeypatch.setattr(max_adapter, '_call', getattr(max_adapter, '_call'))\n"
                            "    max_adapter.default_adapter()\n", 1),
    "restore_by_builtin_setattr": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                                   "    setattr(max_adapter, '_call', orig)\n    max_adapter.default_adapter()\n", 1),
    "restore_by_vars_dict": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                             "    vars(max_adapter)['_call'] = orig\n    max_adapter.default_adapter()\n", 1),
    "restore_in_called_helper": ("def _restore():\n    max_adapter._call = ORIG\ndef test_live(monkeypatch):\n"
                                 "    monkeypatch.setattr(max_adapter, '_call', fake)\n    _restore()\n"
                                 "    max_adapter.default_adapter()\n", 1),
    "reload_after_patch": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                           "    importlib.reload(max_adapter)\n    max_adapter.default_adapter()\n", 1),
    "reimport_after_patch": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                             "    import max_adapter\n    max_adapter.default_adapter()\n", 1),
    "receiver_rebound_in_nested_def": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                                       "    def swap():\n        global max_adapter\n        import max_adapter\n"
                                       "    swap()\n    max_adapter.default_adapter()\n", 1),
    "setattr_on_non_monkeypatch": ("def test_live(monkeypatch):\n    obj.setattr(max_adapter, '_call', fake)\n"
                                   "    max_adapter.default_adapter()\n", 1),
    "monkeypatch_not_a_parameter": ("def test_live():\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                                    "    max_adapter.default_adapter()\n", 1),
    "decorator_mark_list_cleared": ("import pytest\n@pytest.mark.max\ndef test_live():\n"
                                    "    max_adapter.default_adapter()\ntest_live.pytestmark.clear()\n", 1),
    "pytestmark_alias_name": ("import pytest\nMARKS = [pytest.mark.max]\npytestmark = MARKS\n"
                              "def test_live():\n    max_adapter.default_adapter()\n", 1),
    "pytestmark_read_into_alias": ("import pytest\npytestmark = [pytest.mark.max]\nm2 = pytestmark\n"
                                   "def test_live():\n    max_adapter.default_adapter()\n", 1),
    "mocked_control_nested_fake": ("def test_live(monkeypatch):\n    import max_adapter\n"
                                   "    def live_probe(args):\n        return None\n"
                                   "    monkeypatch.setattr(max_adapter, '_call', live_probe)\n"
                                   "    adapter = max_adapter.default_adapter()\n", 0),
    # further fail-closed edges of the same two rules
    "patch_after_launch": ("def test_live(monkeypatch):\n    max_adapter.default_adapter()\n"
                           "    monkeypatch.setattr(max_adapter, '_call', fake)\n", 1),
    "patch_then_undo": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                        "    monkeypatch.undo()\n    max_adapter.default_adapter()\n", 1),
    "patch_other_attr_same_module": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_run', fake)\n"
                                     "    max_adapter.default_adapter()\n", 1),
    "bare_default_adapter_patched": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                                     "    default_adapter()\n", 1),
    "patch_in_try_block": ("def test_live(monkeypatch):\n    try:\n        monkeypatch.setattr(max_adapter, '_call', fake)\n"
                           "    except Exception:\n        pass\n    max_adapter.default_adapter()\n", 1),
    "mocked_control_real_shape": ("def test_live(monkeypatch):\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                                  "    monkeypatch.setattr(max_adapter, 'max_batch_path', p)\n"
                                  "    adapter = max_adapter.default_adapter()\n", 0),
    "pytestmark_max_after_reset": ("import pytest\npytestmark = []\npytestmark = [pytest.mark.max]\n"
                                   "def test_live():\n    m.default_adapter()\n", 0),
    "pytestmark_augmented": ("import pytest\npytestmark = [pytest.mark.max]\npytestmark += []\n"
                             "def test_live():\n    m.default_adapter()\n", 1),
    "pytestmark_conditional": ("import pytest\nif X:\n    pytestmark = pytest.mark.max\n"
                               "def test_live():\n    m.default_adapter()\n", 1),
    "pytestmark_deleted": ("import pytest\npytestmark = pytest.mark.max\ndel pytestmark\n"
                           "def test_live():\n    m.default_adapter()\n", 1),
    "pytestmark_rebound_in_function": ("import pytest\npytestmark = pytest.mark.max\ndef _f():\n"
                                       "    global pytestmark\n    pytestmark = []\n"
                                       "def test_live():\n    m.default_adapter()\n", 1),
    "pytestmark_reset_after_tests": ("import pytest\npytestmark = pytest.mark.max\n"
                                     "def test_live():\n    m.default_adapter()\npytestmark = []\n", 1),
    "mention_in_message": ("def test_a():\n    raise AssertionError('dcc_batch must not run')\n", 0),
    "skip_message_mentions_py": ("import pytest\ndef test_a():\n    pytest.skip('needs dcc_batch.py and Max')\n", 0),
    "route_tuple_constant": ("TOOLS = ('dcc_batch.py', 'ezdxf')\ndef test_a():\n    assert TOOLS\n", 0),
    "non_test_function": ("def helper():\n    m.default_adapter().selftest()\n", 0),
    "empty_module": ("", 0),
    "other_marker_only": ("import pytest\n@pytest.mark.dcc\ndef test_a():\n    m.default_adapter()\n", 1),
}


@pytest.mark.parametrize("case", sorted(SYNTHETIC))
def test_scanner_synthetic(case):
    source, violations = SYNTHETIC[case]
    assert len(scan_source(source)) == violations


PATCHES = {  # name -> (statements before the launch, statements after it, proves mocking)
    "none": ("", "", False),
    "same_receiver": ("    monkeypatch.setattr(max_adapter, '_call', fake)\n", "", True),
    "other_module": ("    monkeypatch.setattr(other_module, '_call', fake)\n", "", False),
    "if_false": ("    if False:\n        monkeypatch.setattr(max_adapter, '_call', fake)\n", "", False),
    "after_launch": ("", "    monkeypatch.setattr(max_adapter, '_call', fake)\n", False),
    "restored": ("    original = max_adapter._call\n    monkeypatch.setattr(max_adapter, '_call', fake)\n"
                 "    max_adapter._call = original\n", "", False),
    "noop_self": ("    monkeypatch.setattr(max_adapter, '_call', max_adapter._call)\n", "", False),
    "undone": ("    monkeypatch.setattr(max_adapter, '_call', fake)\n    monkeypatch.undo()\n", "", False),
}
MODULE_MARKS = {  # name -> (module header, effective module max mark, decorator marks still trusted)
    "none": ("", False, True),
    "max": ("pytestmark = pytest.mark.max\n", True, True),
    "max_then_reset": ("pytestmark = pytest.mark.max\npytestmark = []\n", False, True),
    "reset_then_max": ("pytestmark = []\npytestmark = [pytest.mark.dcc, pytest.mark.max]\n", True, True),
    "max_then_clear": ("pytestmark = [pytest.mark.max]\npytestmark.clear()\n", False, False),
}


def test_scanner_brute_force_patch_and_module_mark_combinations():
    """8 patch shapes x 5 module-mark histories x 2 decorators = 80 sources; violation iff neither proof holds."""
    checked = 0
    for (pname, (before, after, mocked)), (mname, (header, marked, trusted)), decorated in itertools.product(
            PATCHES.items(), MODULE_MARKS.items(), (False, True)):
        source = ("import pytest\n" + header + ("@pytest.mark.max\n" if decorated else "")
                  + "def test_live(monkeypatch):\n" + before
                  + "    max_adapter.default_adapter().selftest()\n" + after)
        expected = [] if (mocked or marked or (decorated and trusted)) else ["<src>::test_live"]
        assert scan_source(source) == expected, (pname, mname, decorated)
        checked += 1
    assert checked == 80


def test_max_marker_registered_with_description(pytestconfig):
    markers = {str(m).split(":", 1)[0].strip(): str(m) for m in pytestconfig.getini("markers")}
    assert markers["max"] == "max: opt-in real 3ds Max batch process via dcc_batch.py; select with -m max"


def _default_expression(pytestconfig) -> str:
    addopts = pytestconfig.getini("addopts")
    assert addopts[0] == "-m" and len(addopts) == 2, addopts
    return addopts[1]


def test_default_expression_deselects_every_max_combination(pytestconfig):
    """Brute force over all 32 lane-marker sets: any set with ``max`` (or another lane) is deselected."""
    expression = Expression.compile(_default_expression(pytestconfig))
    for size in range(len(LANE_MARKERS) + 1):
        for marks in itertools.combinations(LANE_MARKERS, size):
            selected = expression.evaluate(lambda name, marks=marks, **_: name in marks)
            assert selected is (not marks), marks
