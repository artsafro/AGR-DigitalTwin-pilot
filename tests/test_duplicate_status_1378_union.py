"""#1424 x #1378 union: the blender-launch guard rows of main carry a #1424 status from real call chains.

Acceptance (PR #1428 rework after merging main with #1378) -> tests here:
- every #1378 blender-launch allowlist row survives the merge and has a status; the guard scan stays clean
  -> test_repo_blender_launch_rows_*
- statuses from call chains: KPP1 / VATUTINO-SITE (finished, no chain) historical; live tools/ + src/ live-bypass
  in LIVE_BYPASS_BASELINE; the report-only command text own-duty  -> test_repo_blender_launch_statuses
- taking only the executable path from blender_runner is not delegating the launch: such a row is not a wrapper
  -> test_executable_only_is_not_a_blender_launch_wrapper
- the #1359 described dcc rows main removed stay removed (they delegate since #1378), their baseline key is gone
  -> test_repo_described_dcc_rows_removed_with_their_baseline_key
- ORCH-OBR22-NPM pilot launch now builds its argv with blender_command, byte-identical  -> test_orch_*
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
sys.path.insert(0, str(ROOT / "src"))
import call_chains  # noqa: E402
import duplicate_guard as guard  # noqa: E402

BL_OWNER = "src/dt_ai/core/blender_runner.py"
HISTORICAL = {"jobs/KPP1/benchmark-1318/run_benchmark.py::main", "jobs/KPP1/quad-1372/run_checks.py::main",
              "jobs/VATUTINO-SITE/run_delivery.py::main", "jobs/VATUTINO-SITE/run_delivery.py::main.dcc",
              "jobs/VATUTINO-SITE/scene_checks.py::main"}
OWN_DUTY = {"tools/library/maf_material_ids.py::main",
            "tools/library/migrate_windows.py::main",       # #1530: source-bound to library/windows v001
            "tools/research/checker_mutation.py::freeze"}   # #1530: sealed runner sha256 (frozen measurement)


def _bl_rows():
    rows = guard.rows_of(guard.load_maps(ROOT))
    return [r for r in rows if r.rule == "blender-launch"]


def test_repo_blender_launch_rows_survive_and_the_guard_scan_is_clean():
    rows = _bl_rows()
    assert len(rows) == 10, [r.at for r in rows]   # 25 of #1378 minus ORCH-OBR22-NPM (#1424) minus 14 moved (#1530)
    allowed = guard.allowlist(guard.load_maps(ROOT)["contexts"])
    new, stale = guard.compare(guard.scan_for(ROOT, allowed), allowed)
    assert new == [] and stale == []


def test_repo_blender_launch_statuses():
    by = {}
    for r in _bl_rows():
        by.setdefault(r.status, set()).add(r.at)
    assert by.get("historical") == HISTORICAL
    assert by.get("own-duty") == OWN_DUTY
    assert "wrapper" not in by
    assert "live-bypass" not in by   # #1530: 14 live launches call blender_command, 2 hash-bound ones are own-duty


def test_repo_described_dcc_rows_removed_with_their_baseline_key():
    ats = {r.at for r in guard.rows_of(guard.load_maps(ROOT)) if r.context == "dcc"}
    for gone in ("src/dt_ai/core/build.py:16", "src/twinqa/scene.py:59", "tools/qa/run_benchmark.py:40",
                 "jobs/VATUTINO-SITE/flora_route_a.py:394", "jobs/VATUTINO-SITE/place_site.py:59",
                 "jobs/OBR22-K02/scripts/run_profile_checks.py:191"):
        assert gone not in ats
    assert not any(k[1] == "jobs/VATUTINO-SITE/place_site.py:59" for k in guard.LIVE_BYPASS_BASELINE)


def _bl_repo(tmp_path):
    files = {
        "pyproject.toml": '[project]\nname = "x"\n\n[project.scripts]\nx = "dt_ai.cli:main"\n',
        "src/dt_ai/__init__.py": "",
        "src/dt_ai/cli.py": "def main():\n    return 0\n",
        "src/dt_ai/core/__init__.py": "",
        "tools/max/build_agr_tools.py": "FILES = ('a_core.py',)\n",
        "adapters/max/agr_tools/a_core.py": "X = 1\n",
        BL_OWNER: "def blender_executable(e=None):\n    return 'b'\n\n\ndef blender_command(s, a=()):\n"
                  "    return [blender_executable(), '--background', '--python', s]\n\n\ndef run_blender(s):\n"
                  "    return s\n",
        "tools/exe_only.py": "def launch(s):\n    from dt_ai.core.blender_runner import blender_executable\n"
                             "    return [blender_executable(), '--background', '--python', s]\n",
        "tools/via_cmd.py": "from dt_ai.core.blender_runner import run_blender as headless\n\n\ndef launch(s):\n"
                            "    return headless(s)\n",
        "tools/via_mod.py": "from dt_ai.core import blender_runner\n\n\ndef launch(s):\n"
                            "    return blender_runner.blender_command(s)\n",
    }
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def _row(at, status, rule: "str | None" = "blender-launch", step=None):
    rel, qual, line = guard._row_at(at)
    return guard.Row("contexts", "dcc", BL_OWNER, at, rel, qual, line, status, step, "", "#1378", "", "", "DCC",
                     rule)


def _check(root, rows, baseline=frozenset()):
    roots, chains = call_chains.load_live(root, routes={}, context_maps={})
    return guard.status_problems(root, rows, chains, roots, {}, baseline, own_duty_baseline=frozenset())


def test_executable_only_is_not_a_blender_launch_wrapper(tmp_path):
    root = _bl_repo(tmp_path)
    assert any("does not call its owner" in p for p in _check(root, [_row("tools/exe_only.py::launch", "wrapper")]))
    key = frozenset({("contexts", "tools/exe_only.py::launch", "")})
    assert _check(root, [_row("tools/exe_only.py::launch", "live-bypass", step="-")], key) == []
    assert _check(root, [_row("tools/via_cmd.py::launch", "wrapper")]) == []
    assert _check(root, [_row("tools/via_mod.py::launch", "wrapper")]) == []
    # rows without a policy rule keep the #1424 meaning: any owner name is a call of the owner
    assert _check(root, [_row("tools/exe_only.py::launch", "wrapper", rule=None)]) == []


def test_orch_pilot_command_is_blender_command_byte_identical():
    path = ROOT / "jobs/ORCH-OBR22-NPM/scripts/run_profile_pilot.py"
    spec = importlib.util.spec_from_file_location("run_profile_pilot_1424", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from dt_ai.core.blender_runner import blender_command
    blender = Path("C:/Blender/blender.exe")
    got = mod.command(blender, "export_profile_snapshot.py", Path("C:/x/cfg.json"))
    old = [str(blender), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
           "--python", str(mod.ROOT / "tools" / "export_profile_snapshot.py"), "--", str(Path("C:/x/cfg.json"))]
    assert got == old
    assert got == blender_command(mod.ROOT / "tools" / "export_profile_snapshot.py", [Path("C:/x/cfg.json")],
                                  executable=blender)
    assert guard.scan_text(path.read_text(encoding="utf-8"), "jobs/ORCH-OBR22-NPM/scripts/run_profile_pilot.py") == []
