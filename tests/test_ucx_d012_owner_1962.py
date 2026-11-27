"""[D012] UCX budget has one owner: stdlib-only twinqa.geometry.ucx_audit (#1962).

The owner must import inside Blender 5.1 (numpy only) and slice into the Max bundle, so it is
ucx_audit, not twinqa.scene (shapely/yaml). scene, ucx_build, densify and the Blender audit script
use it; the frozen Max copy adapters/max/agr_tools/ucx_core.py [D393] stays and is pinned by parity.
"""
from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path

from dt_ai.geometry import ucx_build
from dt_ai.ops import densify
from twinqa import scene
from twinqa.geometry import ucx_audit

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [0, 1, 49_999, 50_000, 50_001, 299_999, 300_000, 1_999_999, 2_000_000, 2_000_001, 10**7]


def _expected(n: int) -> int:
    return 15_000 if n < 50_000 else min(math.ceil(n * 0.05), 100_000)


def test_owner_values_unchanged():
    assert (ucx_audit.UCX_SMALL_MODEL, ucx_audit.UCX_SMALL_LIMIT, ucx_audit.UCX_SHARE, ucx_audit.UCX_CAP) == (
        50_000, 15_000, 0.05, 100_000)
    assert [ucx_audit.ucx_triangle_limit(n) for n in SAMPLES] == [_expected(n) for n in SAMPLES]


def test_callers_use_the_owner():
    assert scene.ucx_triangle_limit is ucx_audit.ucx_triangle_limit
    assert ucx_build.ucx_triangle_limit is ucx_audit.ucx_triangle_limit
    assert densify.ucx_triangle_limit is ucx_audit.ucx_triangle_limit
    for name in ("UCX_SMALL_MODEL", "UCX_SMALL_LIMIT", "UCX_SHARE", "UCX_CAP"):
        assert getattr(scene, name) == getattr(ucx_audit, name)
    assert densify.UCX_CAP == ucx_audit.UCX_CAP


def _defines(path: Path, name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(n, ast.FunctionDef) and n.name == name for n in ast.walk(tree))


def test_no_second_definition():
    for rel in ("src/twinqa/scene.py", "src/dt_ai/geometry/ucx_build.py"):
        assert not _defines(ROOT / rel, "ucx_triangle_limit"), rel
    src = (ROOT / "tools/blender/ucx_audit.py").read_text(encoding="utf-8")
    assert "ua.ucx_triangle_limit(" in src and "15000" not in src


def test_owner_is_stdlib_only():
    tree = ast.parse((ROOT / "src/twinqa/geometry/ucx_audit.py").read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert mods <= {"__future__", "itertools", "math", "re", "os", "pathlib"}, mods


def test_frozen_max_copy_parity():
    spec = importlib.util.spec_from_file_location("ucx_core_1962", ROOT / "adapters/max/agr_tools/ucx_core.py")
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    assert [core.triangle_limit(n) for n in SAMPLES] == [ucx_audit.ucx_triangle_limit(n) for n in SAMPLES]
