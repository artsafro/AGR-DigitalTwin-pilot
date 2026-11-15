"""#1376 compaction step 1: the live NPM-route UDIM copies go through udimtile_core (#1337), and the duplicate
guard's udim-tile rule now guards tools/ and src/ as well as jobs/.

Behaviour probes compare the routed code with the formula it replaced (`1001 + u + 10 * v`, `(t - 1001) % 10`,
`// 10`) on every cell / tile of the domain, so no delivery changes; outside the domain the routed code refuses
where the old one aliased (u tile 10 -> 1011) or crashed (v = inf -> OverflowError).
"""
import ast
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402

OWNER = ROOT / "adapters/max/agr_tools/udimtile_core.py"
LIVE = ["tools/derive/export_npm.py", "tools/materials/npm_atlas_udim.py", "tools/blender/fbx_readback.py",
        "src/dt_ai/geometry/uv.py", "src/twinqa/uv.py"]


def _owner():
    spec = importlib.util.spec_from_file_location("udimtile_core_1376", OWNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _old_tile(u, v):
    return 1001 + int(math.floor(u)) + 10 * int(math.floor(v))


def _function(rel, name, **namespace):
    """Exec one top-level def of a Blender-only script (bpy is not importable here) with an explicit namespace."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {"math": math, **namespace}
    exec(compile(ast.Module(body=[node], type_ignores=[]), rel, "exec"), ns)
    return ns[name]


@pytest.mark.parametrize("rel", LIVE)
def test_live_route_file_holds_no_udim_copy(rel):
    findings = [f for f in guard.scan_text((ROOT / rel).read_text(encoding="utf-8"), rel) if f.rule == "udim-tile"]
    assert findings == []
    assert "udimtile_core.py" in (ROOT / rel).read_text(encoding="utf-8")


def test_merged_rows_left_the_allowlist():
    allowed = guard.allowlist(mini_yaml.load(ROOT / "docs/architecture/contexts.yaml"))
    assert [k for k in allowed if k[1] in LIVE] == []


def _root(tmp_path, files, contexts="contexts:\n  - id: x\n"):
    for top in ("jobs", "tools", "src"):
        (tmp_path / top).mkdir(exist_ok=True)
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text(contexts, encoding="utf-8")
    return ["--root", str(tmp_path), "--contexts", str(ctx)]


@pytest.mark.parametrize("rel", ["tools/derive/new.py", "src/dt_ai/new.py", "jobs/J/new.py"])
@pytest.mark.parametrize("code", ["t = 1001 + u + 10 * v\n", "o = divmod(t - 1001, 10)\n",
                                  "def tile_origin(t):\n    return table[t]\n"])
def test_guard_red_on_new_udim_copy_in_tools_src_jobs(tmp_path, rel, code, capsys):
    assert guard.main(_root(tmp_path, {rel: code})) == 1
    assert f"NEW COPY [udim-tile] {rel}:" in capsys.readouterr().out


@pytest.mark.parametrize("rel", ["tools/x/zipper.py", "src/x/zipper.py"])
def test_delivery_zip_rule_guards_tools_and_src_after_1377(tmp_path, rel):
    """Step 2 (package owner, #1377) merged: a ZIP writer in tools/ or src/ is a new copy now."""
    assert guard.main(_root(tmp_path, {rel: "import zipfile\nzipfile.ZipFile(p, 'w')\n"})) == 1


@pytest.mark.parametrize("top", ["tools", "src"])
def test_guard_missing_widened_scope_is_an_error(tmp_path, top):
    args = _root(tmp_path, {})
    (tmp_path / top).rmdir()
    assert guard.main(args) == 2


# Acceptance table rows (PR #1398 body) without a test above.
UDIM = "t = 1001 + u + 10 * v\n"


def test_acc_udim_copy_in_adapters_is_not_new(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {"adapters/max/x.py": UDIM})) == 0
    assert "NEW COPY" not in capsys.readouterr().out


def test_acc_zip_writer_in_jobs_is_new_copy(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {"jobs/J/zipper.py": "import zipfile\nzipfile.ZipFile(p, 'w')\n"})) == 1
    assert "NEW COPY [delivery-zip] jobs/J/zipper.py:" in capsys.readouterr().out


def test_acc_readded_tile_origin_in_twinqa_uv_is_new_copy(tmp_path, capsys):
    code = "def tile_origin(t):\n    return (t - 1001) % 10, (t - 1001) // 10\n"
    assert guard.main(_root(tmp_path, {"src/twinqa/uv.py": code})) == 1
    assert "NEW COPY [udim-tile] src/twinqa/uv.py:" in capsys.readouterr().out


def test_acc_toolsx_prefix_is_not_guarded(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {"toolsx/a.py": UDIM, "srcx/a.py": UDIM, "jobsx/a.py": UDIM})) == 0
    assert "NEW COPY" not in capsys.readouterr().out


def test_acc_stale_row_whose_copy_is_gone_exits_1(tmp_path, capsys):
    ctx = ("contexts:\n  - id: x\n    duplicates:\n      - at: \"tools/gone.py::f\"\n"
           "        rule: udim-tile\n        issue: \"#1376\"\n")
    assert guard.main(_root(tmp_path, {"tools/gone.py": "def f():\n    return 1\n"}, ctx)) == 1
    assert "STALE ALLOWLIST [udim-tile] tools/gone.py::f" in capsys.readouterr().out


def test_acc_empty_guarded_folders_without_rows_exit_0(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {})) == 0
    out = capsys.readouterr().out
    assert "NEW COPY" not in out and "STALE" not in out


@pytest.mark.parametrize("mod", ["dt_ai.geometry.uv", "twinqa.uv"])
def test_tile_origin_equals_old_formula_on_1001_1100_and_refuses_the_rest(mod):
    tile_origin = __import__(mod, fromlist=["tile_origin"]).tile_origin
    n = 0
    for t in range(900, 1250):
        if 1001 <= t <= 1100:
            assert tile_origin(t) == ((t - 1001) % 10, (t - 1001) // 10)
        else:
            with pytest.raises(ValueError):
                tile_origin(t)
        n += 1
    for bad in (True, 1001.0, "1001", None, float("nan")):
        with pytest.raises(ValueError):
            tile_origin(bad)
    assert n == 350


def test_fbx_readback_udim_equals_old_formula_and_returns_none_outside():
    udim = _function("tools/blender/fbx_readback.py", "udim", _udimtile=_owner())
    grid = [k / 4 for k in range(-8, 60)]           # u, v in [-2, 14.75], tile lines included
    for u in grid:
        for v in grid:
            want = _old_tile(u, v) if 0 <= u < 10 and v >= 0 else None
            assert udim(u, v) == want, (u, v)
    for u, v in ((math.nan, 0.5), (0.5, math.nan), (math.inf, 0.5), (0.5, math.inf), (-math.inf, 0.5)):
        assert udim(u, v) is None                      # v = inf crashed (OverflowError) before #1376


def test_export_npm_face_udim_equals_old_formula_and_refuses_alias():
    owner = _owner()
    face_udim = _function("tools/derive/export_npm.py", "face_udim", _udimtile=owner)
    grid = [k / 4 for k in range(0, 40)]
    for u in grid:
        for v in grid:
            tu, tv = math.floor(u), math.floor(v)
            assert face_udim(u, v) == (1001 + tu + 10 * tv, tu, tv), (u, v)
    for u, v in ((10.0, 0.5), (10.2, 0.5), (-0.1, 0.5), (0.5, -0.1), (math.nan, 0.5), (0.5, math.inf)):
        with pytest.raises(ValueError):                 # u 10.2 was tile 1011 = cell (0, 1): a silent alias
            face_udim(u, v)


def test_npm_atlas_udim_tile_is_the_owner_cell():
    import importlib
    sys.path.insert(0, str(ROOT / "tools" / "materials"))
    atlas = importlib.import_module("npm_atlas_udim")
    owner = _owner()
    for tu in range(10):
        for tv in range(10):
            assert atlas._udimtile.udim_of_cell(tu, tv) == owner.udim_of_cell(tu, tv) == 1001 + tu + 10 * tv


def test_max_nudge_slice_tile_origin_is_the_owner_behind_the_regulated_wrapper():
    """Full-suite regression (#1376 r0): uv.py's tile_origin now delegates to udimtile_core, so the Max bundle's
    stdlib nudge slice inlines the owner instead of extracting a self-contained `def tile_origin`."""
    sys.path.insert(0, str(ROOT / "tools" / "max"))
    import build_agr_tools as builder
    from dt_ai.geometry.uv import tile_origin
    ns = {}
    source = builder.nudge_slice()
    exec(source, ns)
    assert b"_udimtile." not in source and b"def tile_origin" not in source
    for t in list(range(900, 1250)) + [True, 1001.0, "1001", None, float("nan")]:
        try:
            want = tile_origin(t)
        except ValueError as exc:
            with pytest.raises(ValueError):
                ns["tile_origin"](t)
            assert type(exc) is ValueError
            continue
        assert ns["tile_origin"](t) == want == ((t - 1001) % 10, (t - 1001) // 10)
    uv = (ROOT / "src/dt_ai/geometry/uv.py").read_text(encoding="utf-8")
    owner = (ROOT / "adapters/max/agr_tools/udimtile_core.py").read_text(encoding="utf-8")
    for broken_tile, broken_owner in ((uv.replace("tile_origin = _regulated_tile_origin", ""), owner),
                                      (uv, owner.replace("def tile_origin(", "def tile_origin_x("))):
        with pytest.raises(ValueError):
            builder.nudge_slice(None, broken_tile, broken_owner)
