"""new-case: #1397 non-NPM UDIM owner routing and old-formula parity.

Synthetic UVs only; no scene or delivery acceptance is inferred.
"""
import ast
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from tools.architecture import duplicate_guard as guard
from tools.architecture import mini_yaml

ROOT = Path(__file__).resolve().parents[1]
LIVE = [
    "src/dt_ai/geometry/ground_cake.py",
    "tools/blender/ground_json_to_fbx.py",
    "tools/flora/build_flora_star.py",
    "tools/methods/methods_metrics.py",
    "tools/methods/windows/windows_variants.py",
    "tools/experiments/dreamsim_ac08.py",
]


@pytest.mark.parametrize("rel", LIVE)
def test_live_copy_routes_to_owner(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert [f for f in guard.scan_text(text, rel) if f.rule == "udim-tile"] == []
    assert "udimtile_core.py" in text
    allowed = guard.allowlist(mini_yaml.load(ROOT / "docs/architecture/contexts.yaml"))
    assert not [k for k in allowed if k[0] == "udim-tile" and k[1] == rel]


def test_source_raw_tile_exception_is_explicit():
    text = (ROOT / "tools/source/measure_spec_blender.py").read_text(encoding="utf-8")
    assert "not a delivery UDIM" in text
    contexts = (ROOT / "docs/architecture/contexts.yaml").read_text(encoding="utf-8")
    assert "raw tile" in contexts


def _load(rel):
    spec = importlib.util.spec_from_file_location("probe_1397_" + Path(rel).stem, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _old_tile(u, v):
    return 1001 + math.floor(u) + 10 * math.floor(v)


def _slice(rel, name, predicate, namespace):
    """Run the actual DCC-only arithmetic statements without importing bpy or launching a scene."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    nodes = [n for n in ast.walk(fn) if isinstance(n, ast.stmt) and predicate(n)]
    assert nodes
    exec(compile(ast.Module(body=nodes, type_ignores=[]), rel, "exec"), namespace)
    return namespace


def test_ground_min_corner_parity_including_closed_borders():
    from dt_ai.geometry.ground_cake import uv_tile_report
    uv, expected = [], set()
    for j in range(12):
        for i in range(10):
            for offset, width in ((0, 1), (0.25, 0.5), (-5e-10, 1)):
                uv.append([[i + offset, j], [i + width, j], [i + offset, j + 1]])
                expected.add(_old_tile(i, j))
    report = uv_tile_report(np.asarray(uv))
    assert report["triangles"] == 360
    assert report["straddling"] == report["outside_udim_range"] == 0
    assert report["tiles"] == sorted(expected)
    assert uv_tile_report(np.asarray([]))["tiles"] == []  # existing empty diagnostic, not an acceptance pass
    assert uv_tile_report(np.asarray([[[10, 0], [10.5, 0], [10, 0.5]]]))["outside_udim_range"] == 1
    assert uv_tile_report(np.asarray([[[0, 0], [1.1, 0], [0, 1]]]))["straddling"] == 1


def test_ground_blender_readback_cell_parity():
    owner = _load("adapters/max/agr_tools/udimtile_core.py")
    for j in range(12):
        for i in range(10):
            ns = {"_udimtile": owner, "tiles": set(), "tu": i, "tv": j}
            _slice(LIVE[1], "readback", lambda n: isinstance(n, ast.Expr) and
                   isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and
                   isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == "tiles", ns)
            assert ns["tiles"] == {_old_tile(i, j)}


def test_flora_and_windows_inverse_parity_and_bpy_readback():
    flora = _load(LIVE[2])
    windows = _load(LIVE[4])
    for tile in range(1001, 1101):
        expected = ((tile - 1001) % 10, (tile - 1001) // 10)
        assert flora.udim_offset(tile) == windows.tile_offset(tile) == expected
        ns = {"tile": tile, "udim_offset": flora.udim_offset}
        _slice(LIVE[2], "_bpy_build", lambda n: isinstance(n, ast.Assign) and
               isinstance(n.targets[0], ast.Tuple) and
               [getattr(e, "id", None) for e in n.targets[0].elts] == ["du", "dv"], ns)
        assert (ns["du"], ns["dv"]) == expected
    for bad in (None, True, 1000, 1101, 1001.5, float("nan"), float("inf"), "1001"):
        with pytest.raises((ValueError, TypeError)):
            flora.udim_offset(bad)
        with pytest.raises((ValueError, TypeError)):
            windows.tile_offset(bad)


def test_centroid_methods_and_experiment_parity():
    methods, experiment = _load(LIVE[3]), _load(LIVE[5])
    for j in range(12):
        for i in range(10):
            for frac in (0.0, 0.125, 0.5, 0.875):
                uv = [(i + frac, j + frac)] * 3
                expected = _old_tile(i + frac, j + frac)
                assert methods._udim(uv) == experiment._tile(uv) == expected
    crossing = [[0.9, 0], [1.2, 0], [1.2, 0.3]]
    assert methods._udim(crossing) == experiment._tile(crossing) == 1002
    for uv in ([[-1, 0]] * 3, [[10, 0]] * 3, [[0, -1]] * 3, [[float("nan"), 0]] * 3):
        assert methods._udim(uv) is None
        with pytest.raises(ValueError):
            experiment._tile(uv)
    for fn in (methods._udim, experiment._tile):
        if fn == experiment._tile:
            with pytest.warns(RuntimeWarning), pytest.raises(IndexError):
                fn([])
        else:
            with pytest.raises(ZeroDivisionError):
                fn([])
        with pytest.raises(ValueError):
            fn([[0, float("inf")]] * 3)
        with pytest.raises((ValueError, IndexError)):
            fn([[0]] * 3)


def test_source_raw_tile_preserves_arbitrary_coordinates():
    from types import SimpleNamespace
    tree = ast.parse((ROOT / "tools/source/measure_spec_blender.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "udim")
    for u, v in ((-1.25, -2.5), (10.5, 0.0), (100.5, 12.5), (0, 0)):
        ns = {"math": math, "uv": [SimpleNamespace(uv=(u, v))] * 3}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "source raw tile", "exec"), ns)
        assert ns["udim"](SimpleNamespace(loops=[0, 1, 2])) == _old_tile(u, v)


def test_fresh_process_imports_from_unrelated_working_directory(tmp_path):
    import subprocess
    import sys
    code = f"""import importlib.util
from pathlib import Path
root = Path({str(ROOT)!r})
for rel in {LIVE[2:]!r}:
    spec = importlib.util.spec_from_file_location('fresh_' + Path(rel).stem, root / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._udimtile.udim_tile(9.5, 10.5) == 1110
print('4 standalone imports; owner result 1110')
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 standalone imports" in result.stdout
