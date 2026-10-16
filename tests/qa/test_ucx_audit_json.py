"""new-case: strict UCX audit JSON.

Pure-Python regression tests for tools/blender/ucx_audit.py (Task #207).
Exercises dist_stats, strict JSON serialization, and missing UCX handling via AST extraction.
"""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "tools/blender/ucx_audit.py"


def _load_script_ast() -> tuple[ast.AST, str]:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(SCRIPT_PATH)), source


def _extract_script_symbols():
    tree, _ = _load_script_ast()
    ns: dict[str, Any] = {"math": math}
    selected_nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "BANDS" for t in node.targets
        ):
            selected_nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in ("pct", "dist_stats"):
            selected_nodes.append(node)

    mod = ast.Module(body=selected_nodes, type_ignores=[])
    code = compile(mod, filename=str(SCRIPT_PATH), mode="exec")
    exec(code, ns)
    return ns["dist_stats"], ns["pct"], ns["BANDS"]


def _extract_dumps_call_node(tree: ast.AST) -> ast.Call:
    dumps_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dumps"
    ]
    assert dumps_calls, "No json.dumps call found in tools/blender/ucx_audit.py"
    return dumps_calls[-1]


def _extract_dumps_callable(tree: ast.AST):
    call_node = _extract_dumps_call_node(tree)
    fn_def = ast.FunctionDef(
        name="dump_report",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="report")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[ast.Return(value=call_node)],
        decorator_list=[],
    )
    mod = ast.Module(body=[fn_def], type_ignores=[])
    ast.fix_missing_locations(mod)
    ns: dict[str, Any] = {"json": json}
    exec(compile(mod, filename="<ast_dumps>", mode="exec"), ns)
    return ns["dump_report"]


def _strict_json_loads(payload: str) -> Any:
    def _reject_constant(c: str):
        raise ValueError(f"Strict JSON rejected non-standard constant: {c}")

    return json.loads(payload, parse_constant=_reject_constant)


def test_dist_stats_empty():
    """Empty sample list produces None without crashing."""
    dist_stats, _, _ = _extract_script_symbols()
    assert dist_stats([]) is None


def test_dist_stats_finite_control():
    """Ordinary finite-distance samples preserve existing output keys and calculated values."""
    dist_stats, _, _ = _extract_script_symbols()
    d = [0.005, 0.05, 0.25, 0.5, 1.5]
    stats = dist_stats(d)
    assert stats == {
        "n": 5,
        "le_0.01m": 0.2,
        "le_0.3m": 0.6,
        "le_1.0m": 0.8,
        "p50_m": 0.25,
        "p95_m": 1.5,
        "max_m": 1.5,
    }


def test_dist_stats_output_shape_preservation():
    """Existing output dictionary shape is preserved across finite and unavailable inputs."""
    dist_stats, _, _ = _extract_script_symbols()
    expected_keys = {"n", "le_0.01m", "le_0.3m", "le_1.0m", "p50_m", "p95_m", "max_m"}

    res_finite = dist_stats([0.1, 0.2, 0.3])
    assert res_finite.keys() == expected_keys

    res_inf = dist_stats([math.inf])
    assert res_inf.keys() == expected_keys


def test_dist_stats_missing_ucx_all_infinite():
    """Missing UCX produces null p50/p95/max (not zero, not inf), zero le-bands, and strict JSON compliance."""
    dist_stats, _, _ = _extract_script_symbols()
    d = [math.inf] * 50
    stats = dist_stats(d)

    assert stats is not None
    assert stats["n"] == 50
    # le-band fractions zero: unavailable samples never count as covered
    assert stats["le_0.01m"] == 0.0
    assert stats["le_0.3m"] == 0.0
    assert stats["le_1.0m"] == 0.0
    # p50, p95, max must be null (None in Python), not 0, not Infinity
    assert stats["p50_m"] is None
    assert stats["p95_m"] is None
    assert stats["max_m"] is None
    assert stats["p50_m"] != 0
    assert stats["p95_m"] != 0
    assert stats["max_m"] != 0


def test_no_ucx_synthetic_report_across_height_bands_strict_json():
    """Synthetic report with missing UCX across all height bands must serialize to valid standard JSON."""
    dist_stats, _, _ = _extract_script_symbols()
    tree, _ = _load_script_ast()
    dump_report = _extract_dumps_callable(tree)

    # All-infinite samples distributed across height bands
    dz = {
        "z_lt_0": [math.inf] * 10,
        "z_0_6": [math.inf] * 20,
        "z_ge_6": [math.inf] * 30,
    }
    d = dz["z_lt_0"] + dz["z_0_6"] + dz["z_ge_6"]

    report = {
        "source": "synthetic.fbx",
        "readback_ok": True,
        "pieces": [],
        "coverage": {
            "SM_Main": {
                "surface_area_m2": 150.0,
                "inside_ucx": 0.0,
                "main_to_ucx": dist_stats(d),
                "by_height": {k: dist_stats(v) for k, v in dz.items()},
            }
        },
    }

    # Height bands must all report null aggregates and 0.0 le-band coverage
    for band_name, band_stats in report["coverage"]["SM_Main"]["by_height"].items():
        assert band_stats["le_0.01m"] == 0.0
        assert band_stats["le_0.3m"] == 0.0
        assert band_stats["le_1.0m"] == 0.0
        assert band_stats["p50_m"] is None, f"{band_name} p50_m should be null"
        assert band_stats["p95_m"] is None, f"{band_name} p95_m should be null"
        assert band_stats["max_m"] is None, f"{band_name} max_m should be null"

    # Serialization via the script's extracted dumps call must yield strict RFC 8259 JSON
    serialized = dump_report(report)
    assert "Infinity" not in serialized
    assert "-Infinity" not in serialized
    assert "NaN" not in serialized

    # Strict JSON parsing rejecting constants must succeed and confirm nulls
    parsed = _strict_json_loads(serialized)
    main_cov = parsed["coverage"]["SM_Main"]["main_to_ucx"]
    assert main_cov["p50_m"] is None
    assert main_cov["p95_m"] is None
    assert main_cov["max_m"] is None
    assert main_cov["le_0.01m"] == 0.0


def test_ast_final_json_dumps_requires_allow_nan_false():
    """Final json.dumps call in tools/blender/ucx_audit.py must specify allow_nan=False."""
    tree, _ = _load_script_ast()
    call_node = _extract_dumps_call_node(tree)

    allow_nan_kws = [
        kw for kw in call_node.keywords
        if kw.arg == "allow_nan"
    ]
    assert allow_nan_kws, (
        "tools/blender/ucx_audit.py json.dumps must explicitly specify allow_nan=False"
    )
    val_node = allow_nan_kws[0].value
    assert (isinstance(val_node, ast.Constant) and val_node.value is False), (
        f"Expected allow_nan=False, got {ast.dump(val_node)}"
    )


def test_strict_writer_rejects_unrelated_nonfinite_field():
    """Extracted writer must reject nonfinite values (e.g. NaN, Inf in unrelated fields) via allow_nan=False."""
    tree, _ = _load_script_ast()
    dump_report = _extract_dumps_callable(tree)

    with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"):
        dump_report({"unrelated_nonfinite": float("nan")})

    with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"):
        dump_report({"unrelated_nonfinite": float("inf")})


def test_missing_ucx_coverage_report_plans_explanation_note():
    """Script report must plan an explicit coverage_note explaining missing UCX when pieces are empty."""
    _, source = _load_script_ast()
    # The script must plan a coverage_note in the target coverage dictionary when no UCX pieces exist
    assert "coverage_note" in source, (
        "Expected tools/blender/ucx_audit.py to plan 'coverage_note' explaining missing UCX"
    )


@pytest.mark.parametrize(
    "d, expected_le_0_01",
    [
        # Only finite 0.005 is covered; math.inf is unavailable and never counted as covered
        ([0.005, math.inf], 0.5),
        # Negative infinity is invalid/unavailable; must NEVER be counted as <= 0.01m
        ([0.005, -math.inf], 0.5),
        # NaN is unavailable and never counted as covered
        ([0.005, math.nan], 0.5),
        # None is unavailable; must not crash and never be counted as covered
        ([0.005, None], 0.5),
        # All unavailable: zero covered
        ([math.inf, -math.inf, math.nan, None], 0.0),
    ],
)
def test_dist_stats_unavailable_values_never_counted_as_covered(d, expected_le_0_01):
    """Unavailable values (inf, -inf, nan, None) must never count toward le-band coverage."""
    dist_stats, _, _ = _extract_script_symbols()
    stats = dist_stats(d)

    assert stats is not None
    assert stats["n"] == len(d)
    assert stats["le_0.01m"] == expected_le_0_01


@pytest.mark.parametrize(
    "d, expected_null_aggregates",
    [
        # All-infinite (missing UCX): p50, p95, max must all be null
        ([math.inf, math.inf], True),
        # Mixed unavailable samples where no valid finite aggregate exists: all null
        ([math.inf, -math.inf, math.nan, None], True),
        # Mixed finite and unavailable: nonfinite aggregate statistics must be null (never inf or nan)
        ([0.005, math.inf], False),
        ([0.005, math.nan], False),
    ],
)
def test_dist_stats_nonfinite_aggregate_statistics_null(d, expected_null_aggregates):
    """Any nonfinite aggregate statistic (p50/p95/max) must be null (None in JSON), never inf or nan."""
    dist_stats, _, _ = _extract_script_symbols()
    stats = dist_stats(d)

    assert stats is not None
    for k in ("p50_m", "p95_m", "max_m"):
        val = stats[k]
        if expected_null_aggregates:
            assert val is None, f"{k} must be null for all-unavailable samples, got {val}"
            assert val != 0, f"{k} must be null, not zero"
        else:
            # If an aggregate cannot be computed as a finite number, it must be null (None)
            assert val is None or (isinstance(val, (int, float)) and math.isfinite(val)), (
                f"{k} must be null or finite, got nonfinite {val}"
            )
