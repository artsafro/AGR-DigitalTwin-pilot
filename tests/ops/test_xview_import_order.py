"""Pattern: none | new-case: fresh-process import-order and first-call controls for xView (#607)."""
import importlib
import importlib.machinery
import importlib.util
import itertools
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import pytest

_TARGETS = ("dt_ai.ops.inv_xview", "dt_ai.ops.inv_xview_fast", "dt_ai.ops.xview_gate")
_LAZY_IMPORT = (
    "    from dt_ai.ops.inv_xview_fast import contact_tri_pairs"
    "   # lazy: inv_xview_fast imports this module"
)
_HOIST = "from dt_ai.ops.inv_xview_fast import contact_tri_pairs\n"
# Synthetic coplanar triangles: the second overlaps the first, then sits 10 m away on X.
_DIRTY_VERTICES = (
    (0, 0, 0), (2, 0, 0), (0, 2, 0),
    (0.5, 0.5, 0), (2.5, 0.5, 0), (0.5, 2.5, 0),
)
_CLEAN_VERTICES = (
    (0, 0, 0), (2, 0, 0), (0, 2, 0),
    (10.5, 0.5, 0), (12.5, 0.5, 0), (10.5, 2.5, 0),
)
_FACES = ((0, 1, 2), (3, 4, 5))
_DIRTY = {
    "face_pairs": [[1, 2, "area+contact", 0.0]],
    "contact_faces": [1, 2],
    "fast_pairs": [[1, 2]],
    "fast_contact_faces": [1, 2],
}
_CLEAN = {
    "face_pairs": [],
    "contact_faces": [],
    "fast_pairs": [],
    "fast_contact_faces": [],
}
_TIMEOUT_S = 300

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "src").resolve()
_CHILD_BOOT = """\
import sys
from pathlib import Path

src = Path(sys.argv[1])
sys.path.insert(0, str(src))
if Path(sys.path[0]).resolve() != src.resolve():
    raise SystemExit("sys.path[0] is not the worktree src")
import importlib.util
spec = importlib.util.spec_from_file_location("xview_order_child", sys.argv[2])
if spec is None or spec.loader is None:
    raise SystemExit("cannot load the xview order child")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.child_entry(sys.argv[3:])
"""


def _order_id(order):
    return ">".join(name.rsplit(".", 1)[-1] for name in order)


def _run(child_args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    command = [
        sys.executable, "-c", _CHILD_BOOT, str(SRC), str(Path(__file__).resolve()), *child_args,
    ]
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"child exceeded {_TIMEOUT_S}s\nstdout:\n{exc.stdout}\nstderr:\n{exc.stderr}"
        ) from exc
    detail = f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    if proc.returncode != 0:
        raise AssertionError(f"child exit {proc.returncode}\n{detail}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"child stdout is not JSON\n{detail}") from exc
    return data, proc.stderr


def _check(condition, stderr, detail):
    if not condition:
        raise AssertionError(f"{detail}\nstderr:\n{stderr}")


def _bind_worktree():
    src = (Path(__file__).resolve().parents[2] / "src").resolve()
    sys.path.insert(0, str(src))
    bound = Path(sys.path[0]).resolve()
    if bound != src:
        raise AssertionError(f"sys.path[0] is {bound}, worktree src is {src}")
    pythonpath = os.environ.get("PYTHONPATH")
    if not pythonpath:
        raise AssertionError("PYTHONPATH is unset")
    first = Path(pythonpath.split(os.pathsep)[0]).resolve()
    if first != src:
        raise AssertionError(f"PYTHONPATH starts at {first}, worktree src is {src}")
    return src


def _assert_targets_absent():
    present = [name for name in _TARGETS if name in sys.modules]
    if present:
        raise AssertionError(f"targets already imported: {present}")


def _measure(vertices):
    import numpy as np
    from dt_ai.ops.inv_quads import PolyMesh

    xview = sys.modules["dt_ai.ops.inv_xview"]
    fast = sys.modules["dt_ai.ops.inv_xview_fast"]
    mesh = PolyMesh(np.asarray(vertices, float), _FACES)
    report = xview.part_report("synthetic", mesh, xview.XviewTolerance())
    listed = fast.xview_lists(np.asarray(vertices, float), _FACES)
    return report, listed


def _witness(report, listed):
    return {
        "face_pairs": [
            [int(i), int(j), kind, None if sep is None else float(sep)]
            for i, j, kind, sep in report.face_pairs
        ],
        "contact_faces": [int(i) for i in report.xview_faces],
        "fast_pairs": [[int(i), int(j)] for i, j in listed["face_pairs"]],
        "fast_contact_faces": [int(i) for i in listed["xview_faces"]],
    }


def _expect_case(report, listed, dirty):
    if dirty:
        if report.face_pairs != ((1, 2, "area+contact", 0.0),):
            raise AssertionError(f"face_pairs {report.face_pairs!r}")
        if report.xview_faces != (1, 2):
            raise AssertionError(f"contact faces {report.xview_faces!r}")
        if listed["face_pairs"] != ((1, 2),):
            raise AssertionError(f"fast pairs {listed['face_pairs']!r}")
        if listed["xview_faces"] != (1, 2):
            raise AssertionError(f"fast contact faces {listed['xview_faces']!r}")
        return
    if report.face_pairs != ():
        raise AssertionError(f"clean face_pairs {report.face_pairs!r}")
    if report.xview_faces != ():
        raise AssertionError(f"clean contact faces {report.xview_faces!r}")
    if listed["face_pairs"] != ():
        raise AssertionError(f"clean fast pairs {listed['face_pairs']!r}")
    if listed["xview_faces"] != ():
        raise AssertionError(f"clean fast contact faces {listed['xview_faces']!r}")


def _emit_order(src, order):
    for name in order:
        importlib.import_module(name)
    files = {}
    for name in _TARGETS:
        module = sys.modules[name]
        raw = getattr(module, "__file__", None)
        if not raw:
            raise AssertionError(f"{name} has no __file__")
        path = Path(raw).resolve()
        if not path.is_relative_to(src):
            raise AssertionError(f"{name} loaded from {path}, expected under {src}")
        files[name] = str(path)
    dirty_report, dirty_fast = _measure(_DIRTY_VERTICES)
    _expect_case(dirty_report, dirty_fast, dirty=True)
    clean_report, clean_fast = _measure(_CLEAN_VERTICES)
    _expect_case(clean_report, clean_fast, dirty=False)
    repeat_report, repeat_fast = _measure(_DIRTY_VERTICES)
    _expect_case(repeat_report, repeat_fast, dirty=True)
    json.dump({
        "absent_before": list(_TARGETS),
        "sys_path0": str(Path(sys.path[0]).resolve()),
        "order": list(order),
        "files": files,
        "dirty": _witness(dirty_report, dirty_fast),
        "clean": _witness(clean_report, clean_fast),
        "repeat": _witness(repeat_report, repeat_fast),
    }, sys.stdout)


class _HoistLoader:
    """Exec inv_xview from memory with the lazy contact import hoisted to module scope."""

    def __init__(self, origin, sink):
        self.origin = origin
        self.sink = sink

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        text = Path(self.origin).read_text(encoding="utf-8")
        count = text.count(_LAZY_IMPORT)
        self.sink["replacements"] = count
        if count != 1:
            raise ImportError(f"mutation replacement count {count}")
        mutated = text.replace(_LAZY_IMPORT, "", 1)
        if "\nimport math\r\n" in mutated:
            at = mutated.find("\nimport math\r\n") + 1
        elif "\nimport math\n" in mutated:
            at = mutated.find("\nimport math\n") + 1
        else:
            raise ImportError("mutation found no module-scope anchor for the hoisted import")
        mutated = mutated[:at] + _HOIST + mutated[at:]
        short = "from dt_ai.ops.inv_xview_fast import contact_tri_pairs"
        if mutated.count(short) != 1 or _LAZY_IMPORT in mutated:
            raise ImportError("mutation did not move the lazy import to module scope")
        module.__dict__.setdefault("__builtins__", __builtins__)
        exec(compile(mutated, self.origin, "exec"), module.__dict__)


class _HoistFinder:
    def __init__(self, sink):
        self.sink = sink

    def find_spec(self, fullname, path, target=None):
        if fullname != "dt_ai.ops.inv_xview":
            return None
        found = importlib.machinery.PathFinder.find_spec(fullname, path)
        if found is None or not found.origin:
            raise ImportError(f"mutation cannot resolve {fullname}")
        origin = str(Path(found.origin).resolve())
        src = Path(self.sink["src"]).resolve()
        if not Path(origin).is_relative_to(src):
            raise ImportError(f"mutation resolved {origin} outside {src}")
        return importlib.util.spec_from_loader(
            fullname, _HoistLoader(origin, self.sink), origin=origin,
        )


def _emit_mutation(src):
    order = ("dt_ai.ops.inv_xview_fast", "dt_ai.ops.inv_xview", "dt_ai.ops.xview_gate")
    sink = {"replacements": None, "src": str(src)}
    sys.meta_path.insert(0, _HoistFinder(sink))
    caught = None
    try:
        for name in order:
            importlib.import_module(name)
    except Exception as exc:
        caught = exc
    message = "" if caught is None else str(caught)
    sys.stderr.write(message + "\n")
    json.dump({
        "order": list(order),
        "replacements": sink["replacements"],
        "error_type": None if caught is None else type(caught).__name__,
        "error": message,
        "traceback": "" if caught is None else traceback.format_exc(),
    }, sys.stdout)
    sys.stdout.write("\n")
    if sink["replacements"] != 1 or type(caught) is not ImportError:
        raise SystemExit(1)
    if "partially initialized module" not in message or "circular import" not in message:
        raise SystemExit(1)
    if "No module named" in message:
        raise SystemExit(1)


def child_entry(argv):
    if len(argv) < 1:
        raise SystemExit("child mode is required")
    mode = argv[0]
    src = _bind_worktree()
    _assert_targets_absent()
    if mode == "order":
        if len(argv) != 2:
            raise SystemExit("order mode requires one comma-separated permutation")
        order = tuple(argv[1].split(","))
        if len(order) != len(_TARGETS) or set(order) != set(_TARGETS):
            raise SystemExit(f"not a permutation of the three targets: {order!r}")
        _emit_order(src, order)
        return
    if mode == "mutate":
        if len(argv) != 1:
            raise SystemExit("mutate mode takes no arguments")
        _emit_mutation(src)
        return
    raise SystemExit(f"unknown child mode {mode!r}")


@pytest.mark.parametrize("order", tuple(itertools.permutations(_TARGETS)), ids=_order_id)
def test_fresh_process_import_order(order):
    data, stderr = _run(("order", ",".join(order)))
    _check(data["absent_before"] == list(_TARGETS), stderr, f"absent_before {data['absent_before']!r}")
    _check(Path(data["sys_path0"]).resolve() == SRC, stderr, f"sys_path0 {data['sys_path0']!r}")
    _check(data["order"] == list(order), stderr, f"order {data['order']!r}")
    _check(set(data["files"]) == set(_TARGETS), stderr, f"files {data['files']!r}")
    for name in _TARGETS:
        path = Path(data["files"][name]).resolve()
        leaf = name.rsplit(".", 1)[-1]
        _check(path.relative_to(SRC).as_posix() == f"dt_ai/ops/{leaf}.py", stderr, f"{name} file {path}")
    for label, expected in (("dirty", _DIRTY), ("clean", _CLEAN), ("repeat", _DIRTY)):
        got = data[label]
        _check(set(got) == set(expected), stderr, f"{label} keys {sorted(got)}")
        for key, literal in expected.items():
            _check(got[key] == literal, stderr, f"{label}.{key} {got[key]!r} != {literal!r}")


def test_fast_first_hoisted_import_is_circular():
    data, stderr = _run(("mutate",))
    _check(data["replacements"] == 1, stderr, f"replacements {data['replacements']!r}")
    _check(data["error_type"] == "ImportError", stderr, f"error_type {data['error_type']!r}")
    _check(data["order"][0] == "dt_ai.ops.inv_xview_fast", stderr, f"order {data['order']!r}")
    blob = f"{data['error']}\n{data['traceback']}\n{stderr}"
    _check("partially initialized module" in blob, stderr, f"diagnostic {data['error']!r}")
    _check("circular import" in blob, stderr, f"diagnostic {data['error']!r}")
    _check("No module named" not in data["error"], stderr, f"dependency error {data['error']!r}")
    _check("ModuleNotFoundError" not in data["error_type"], stderr, f"error_type {data['error_type']!r}")
    disk = (SRC / "dt_ai" / "ops" / "inv_xview.py").read_text(encoding="utf-8")
    _check(disk.count(_LAZY_IMPORT) == 1, stderr, "lazy import line on disk changed")
