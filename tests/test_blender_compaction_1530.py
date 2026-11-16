"""#1530 compaction 12: the 16 own Blender launches of tools/ + src/ call the shared launcher (`blender_command`).

Before: duplicate_guard `--table` area «Связь с DCC (Blender / 3ds Max)» held 16 live bypasses (15 files). After: each
caller builds its argv with src/dt_ai/core/blender_runner.blender_command (pinned flags incl. --disable-autoexec and
--python-exit-code 1), the rows left contexts.yaml and LIVE_BYPASS_BASELINE; the 7 jobs/ rows stay historical and
tools/library/maf_material_ids.py stays own-duty (report text, not a launch).
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402

from dt_ai.core.blender_runner import blender_command  # noqa: E402

OWNER = "src/dt_ai/core/blender_runner.py"
MOVED = {   # at -> old hash (LIVE_BYPASS_BASELINE key on origin/main 6f506951)
    "src/dt_ai/cli/shared_tools.py::command": ("5a31c914e8",),
    "tools/flora/build_flora_npm_light.py::execute": ("41b1d5662a", "83b1fa0042"),
    "tools/flora/build_flora_star.py::_blender": ("e5c254530a",),
    "tools/library/check_library.py::native_inspect": ("c85d66fb6e",),
    "tools/library/migrate_windows.py::main": ("9d1268b5a7",),
    "tools/materials/bind_ground_textures.py::_run_blender": ("707f4be9fd",),
    "tools/methods/body/run_benchmarks.py::_blender": ("18f971bee9",),
    "tools/methods/ground/build_variant.py::_blender": ("37235a2e47",),
    "tools/methods/parametric_parts/mesh_recipe.py::_blender_fbx": ("f5a8a5aa67",),
    "tools/methods/run_variant.py::run_extra": ("d4b2fad230",),
    "tools/methods/ucx/run_benchmarks.py::main": ("9c40344e89",),
    "tools/methods/windows/run_benchmarks.py::main": ("c2afb4241e",),
    "tools/research/checker_mutation.py::freeze": ("3457dc7d0e",),
    "tools/research/fbx_reader_compare.py::_blender": ("8b777603c2",),
    "tools/sintez_parity.py::run_live.run": ("56b4b34392",),
}
HISTORICAL_OR_OWN = {"jobs/KPP1/benchmark-1318/run_benchmark.py::main", "jobs/KPP1/quad-1372/run_checks.py::main",
                     "jobs/VATUTINO-SITE/run_delivery.py::main", "jobs/VATUTINO-SITE/run_delivery.py::main.dcc",
                     "jobs/VATUTINO-SITE/scene_checks.py::main", "tools/library/maf_material_ids.py::main"}


def _rows():
    return guard.rows_of(guard.load_maps(ROOT))


def test_sixteen_rows_were_moved():
    assert sum(len(h) for h in MOVED.values()) == 16


@pytest.mark.parametrize("at", sorted(MOVED))
def test_moved_caller_holds_no_own_launch_and_calls_blender_command(at):
    rel, qual = at.split("::")
    tree = guard.ast.parse((ROOT / rel).read_bytes(), filename=rel)
    assert guard._blender_hits(tree) == [], rel
    row = guard.Row("contexts", "dcc", OWNER, at, rel, qual, None, "wrapper", None, "", "#1530", "", "", "DCC",
                    "blender-launch")
    assert guard.calls_owner(ROOT, row), f"{at} does not call blender_command / run_blender"


def test_no_live_bypass_left_in_the_dcc_area():
    live = [r.at for r in _rows() if r.status == "live-bypass" and r.rule == "blender-launch"]
    assert live == []
    assert {r.at for r in _rows() if r.rule == "blender-launch"} == HISTORICAL_OR_OWN
    keys = {(at, h) for at, hs in MOVED.items() for h in hs}
    assert not {(k[1], k[2]) for k in guard.LIVE_BYPASS_BASELINE} & keys


def test_table_has_no_dcc_row():
    table = guard.bypass_table(_rows())
    assert "Связь с DCC" not in table


def test_repo_guard_green(capsys):
    assert guard.main([]) == 0, capsys.readouterr().out


# ---------------------------------------------------------------- behaviour: the argv each caller launches
class Launched(Exception):
    pass


@pytest.fixture
def capture(monkeypatch):
    seen = []

    def fake_run(cmd, *a, **k):
        seen.append(list(map(str, cmd)))
        raise Launched(cmd)
    monkeypatch.setattr(subprocess, "run", fake_run)
    return seen


def _load(rel, name):
    path = ROOT / rel
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _is_owner_line(cmd, exe, script, args):
    assert cmd == blender_command(script, args, executable=exe), cmd
    assert cmd[cmd.index("--python-exit-code") + 1] == "1"
    return True


def test_shared_tools_npm_step_is_blender_command(tmp_path):
    from dt_ai.cli import shared_tools
    exe = tmp_path / "blender.exe"
    exe.write_text("x")
    step = next(k for k, v in shared_tools.DERIVE_STEPS.items() if v[0] != "python")
    cmd = shared_tools.command(ROOT, "derive", step, ["--", "a", "b"], str(exe))
    script = ROOT / shared_tools.DERIVE_STEPS[step][1]
    assert _is_owner_line(cmd, str(exe), str(script), ["a", "b"])


def test_flora_star(capture):
    mod = _load("tools/flora/build_flora_star.py", "flora_star_1530")
    with pytest.raises(Launched):
        mod._blender(["x", "1"])
    assert _is_owner_line(capture[0], mod.BLENDER, str(Path(mod.__file__).resolve()), ["x", "1"])


def test_check_library_native_inspect(capture, tmp_path):
    mod = _load("tools/library/check_library.py", "check_library_1530")
    with pytest.raises(Launched):
        mod.native_inspect([tmp_path / "a.blend"], "B.exe")
    script = str(Path(mod.__file__).with_name("inspect_library_blender.py"))
    assert _is_owner_line(capture[0], "B.exe", script, [str(tmp_path / "a.blend")])


def test_migrate_windows_main(capture, tmp_path):
    mod = _load("tools/library/migrate_windows.py", "migrate_windows_1530")
    out = tmp_path / "v002"
    with pytest.raises(Launched):
        mod.main(["--output", str(out), "--blender", "B.exe"])
    script = str(Path(mod.__file__).with_name("build_windows_blender.py"))
    assert _is_owner_line(capture[0], "B.exe", script, [str(ROOT), str(out.resolve())])
    assert not out.exists()


def test_bind_ground_textures(capture, monkeypatch):
    mod = _load("tools/materials/bind_ground_textures.py", "bind_ground_1530")
    monkeypatch.setenv("TWINQA_BLENDER", "B.exe")
    with pytest.raises(Launched):
        mod._run_blender(Path("s.py"), ["a", 2])
    assert _is_owner_line(capture[0], "B.exe", "s.py", ["a", "2"])


def test_methods_body(capture, tmp_path):
    mod = _load("tools/methods/body/run_benchmarks.py", "body_bench_1530")
    with pytest.raises(Launched):
        mod._blender("B.exe", "m", tmp_path / "s.fbx", tmp_path / "o.fbx")
    args = ["m", str(tmp_path / "s.fbx"), str(tmp_path / "o.fbx"), mod.main_name(tmp_path / "o.fbx")]
    assert _is_owner_line(capture[0], "B.exe", str(mod.HERE / "body_blender.py"), args)


def test_methods_ground(capture, monkeypatch):
    mod = _load("tools/methods/ground/build_variant.py", "ground_variant_1530")
    monkeypatch.setenv("TWINQA_BLENDER", "B.exe")
    with pytest.raises(Launched):
        mod._blender(Path("s.py"), "a", "b")
    assert _is_owner_line(capture[0], "B.exe", "s.py", ["a", "b"])


def test_methods_run_extra(capture, monkeypatch, tmp_path):
    mod = _load("tools/methods/run_variant.py", "run_variant_1530")
    monkeypatch.setenv("TWINQA_BLENDER", "B.exe")
    with pytest.raises(Launched):
        mod.run_extra(tmp_path / "a.fbx", tmp_path)
    assert _is_owner_line(capture[0], "B.exe", str(mod.EXTRA), [str(tmp_path / "a.fbx"), str(tmp_path / "extra.json")])


def test_mesh_recipe_fbx(capture, tmp_path):
    mod = _load("tools/methods/parametric_parts/mesh_recipe.py", "mesh_recipe_1530")
    with pytest.raises(Launched):
        mod._blender_fbx(str(tmp_path / "o.fbx"), [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    cmd = capture[0]
    script = cmd[cmd.index("--python") + 1]
    assert _is_owner_line(cmd, mod._BLENDER, script, cmd[cmd.index("--") + 1:])


def test_fbx_reader_compare_keeps_isolated_config(capture, tmp_path):
    mod = _load("tools/research/fbx_reader_compare.py", "fbx_compare_1530")
    with pytest.raises(Launched):
        mod._blender(["a"], tmp_path / "scratch", 60)
    assert _is_owner_line(capture[0], mod.BLENDER, str(Path(mod.__file__).resolve()), ["a"])
