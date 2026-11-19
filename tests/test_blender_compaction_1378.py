"""#1378 compaction step 3: one Blender launcher (src/dt_ai/core/blender_runner.py) and the blender-launch guard.

The owner builds the one headless command line (`blender_command`: pinned executable, --background, --factory-startup,
--disable-autoexec, --python-exit-code 1) and runs it with an isolated user config (`run_blender`). The 6 dcc rows of
the #1359 map are gone: 4 already delegated to the owner, the 2 VATUTINO-SITE launches now call it. The new guard
rule `blender-launch` flags any other Blender command line (`--background`/`-b` with `--python`/`-P`/...) in jobs/ +
tools/ + src/; every listed copy names why it stays (`ru`). Acceptance table: PR body.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "architecture"))
import duplicate_guard as guard  # noqa: E402
import mini_yaml  # noqa: E402
import route_map  # noqa: E402

from dt_ai.core import blender_runner  # noqa: E402

OWNER = "src/dt_ai/core/blender_runner.py"
# #1407: the placement launch moved from jobs/VATUTINO-SITE/place_site.py into the placement command
ROUTED = ["jobs/VATUTINO-SITE/flora_route_a.py", "src/dt_ai/placement/site.py"]
DELEGATES = ["src/dt_ai/core/build.py", "src/twinqa/scene.py", "tools/qa/run_benchmark.py",
             "jobs/OBR22-K02/scripts/run_profile_checks.py"]
LAUNCH = "import subprocess\nsubprocess.run([exe, '--background', '--python', s])\n"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _contexts():
    return mini_yaml.load(ROOT / route_map.CONTEXTS)


def _dcc():
    return next(c for c in _contexts()["contexts"] if c["id"] == "dcc")


def _launch_rows():
    ctxs = _contexts()
    return [d for c in ctxs["contexts"] + [ctxs["shared_kernel"]] for d in c.get("duplicates", [])
            if d.get("rule") == "blender-launch"]


def _root(tmp_path, files, contexts="contexts:\n  - id: x\n"):
    for top in ("jobs", "tools", "src"):
        (tmp_path / top).mkdir(exist_ok=True)
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    ctx = tmp_path / "contexts.yaml"
    ctx.write_text(contexts, encoding="utf-8")
    return ["--root", str(tmp_path), "--contexts", str(ctx), "--copies-only"]   # #1424: synthetic root, no maps


def _row(at, ru=None, rule="blender-launch"):
    text = f"contexts:\n  - id: x\n    duplicates:\n      - at: \"{at}\"\n        rule: {rule}\n        issue: \"#1378\"\n"
    return text + (f"        ru: \"{ru}\"\n" if ru is not None else "")


def _launches(text, rel="t.py"):
    return [f for f in guard.scan_text(text, rel) if f.rule == "blender-launch"]


# ---------------------------------------------------------------- owner and rule
def test_owner_is_blender_runner_in_guard_rule_and_context_map():
    ctxs = _contexts()
    assert guard.RULES["blender-launch"] == OWNER
    assert {r["id"]: r["owner"] for r in ctxs["rules"]}["blender-launch"] == OWNER
    assert _dcc()["owner"] == OWNER
    assert "blender_command" in {f["name"] for f in _dcc()["functions"]}


def test_blender_launch_guards_jobs_tools_src_and_requires_a_reason():
    assert set(guard.GUARDED["blender-launch"]) == {"jobs", "tools", "src"}
    assert "blender-launch" in guard.REASON_REQUIRED


def test_six_untagged_dcc_rows_left_the_map():
    rows = _dcc().get("duplicates", [])
    assert [d for d in rows if "rule" not in d] == []
    ats = {d["at"].split("::")[0].split(":")[0] for d in rows}
    assert not ats & set(ROUTED + DELEGATES)


@pytest.mark.parametrize("rel", ROUTED + DELEGATES)
def test_the_six_hold_no_own_launch_and_use_the_owner(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert _launches(text, rel) == []
    assert "blender_runner" in text or "find_blender" in text and rel == "src/twinqa/scene.py"


def test_owner_file_is_not_its_own_copy():
    assert _launches((ROOT / OWNER).read_text(encoding="utf-8"), OWNER) == []


def test_every_blender_launch_row_names_its_reason_and_this_issue():
    rows = _launch_rows()
    assert len(rows) == 10, [d["at"] for d in rows]   # 7 jobs/ + 3 tools/ own-duty; 14 tools/ + src/ call the owner (#1530)
    assert all(str(d.get("ru", "")).strip() and d["issue"] == "#1378" for d in rows), rows


def test_repo_guard_green_and_route_map_check_green(capsys):
    assert guard.main([]) == 0, capsys.readouterr().out
    assert route_map.main(["--check"]) == 0, capsys.readouterr().out


def test_fresh_process_cli_is_green_twice():
    cmd = [sys.executable, str(ROOT / "tools/architecture/duplicate_guard.py")]
    runs = [subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT) for _ in range(2)]
    assert [r.returncode for r in runs] == [0, 0] and runs[0].stdout == runs[1].stdout == ""


# ---------------------------------------------------------------- guard behaviour (acceptance rows)
@pytest.mark.parametrize("rel", ["tools/x/launch.py", "src/x/launch.py", "jobs/J/launch.py"])
@pytest.mark.parametrize("cmd", ["[exe, '--background', '--python', s, '--python-exit-code', '1']", "(exe, '-b', '-P', s)",
                                 "[exe, '-b', blend, '--python-expr', code]", "[exe, '--background', '--python-text', t]",
                                 "f'{exe} --background --python {s}'", "'blender -b -P x.py'"])
def test_new_blender_launch_in_tools_src_jobs_is_a_new_copy(tmp_path, rel, cmd, capsys):
    assert guard.main(_root(tmp_path, {rel: f"import subprocess\nsubprocess.run({cmd})\n"})) == 1
    out = capsys.readouterr().out
    assert f"NEW COPY [blender-launch] {rel}:" in out and OWNER in out


@pytest.mark.parametrize("text", [
    "subprocess.run([exe, '--background', blend, '--python-exit-code', '1'])\n",  # headless without a script: not a launch copy
    "subprocess.run([exe, '--python', s])\n",                     # script without headless
    "def f():\n    '''Run blender --background --python x.py.'''\n",  # docstring
    "'blender -b -P x.py is the old way'\n",                      # bare string statement
    "args = ['--python', s]\nflags = ['--background']\n",         # split across two lists
    "", ])
def test_not_a_launch_copy(text):
    assert _launches(text) == []


def test_one_launch_counts_once():
    assert len(_launches("cmd = [exe, '--background', '--python', s, '--', *a]\n")) == 1


def test_launch_in_adapters_is_not_new(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {"adapters/blender/x.py": LAUNCH})) == 0
    assert "NEW COPY" not in capsys.readouterr().out


def test_owner_path_in_a_scanned_root_is_not_a_copy(tmp_path):
    assert guard.main(_root(tmp_path, {OWNER: LAUNCH})) == 0


def test_listed_launch_with_reason_is_green(tmp_path):
    assert guard.main(_root(tmp_path, {"tools/x/l.py": LAUNCH}, _row("tools/x/l.py::<module>", "не маршрут"))) == 0


@pytest.mark.parametrize("ru", [None, "", "   "])
def test_launch_row_without_reason_is_an_error_naming_it(tmp_path, ru, capsys):
    assert guard.main(_root(tmp_path, {"tools/x/l.py": LAUNCH}, _row("tools/x/l.py::<module>", ru))) == 2
    assert "tools/x/l.py::<module>" in capsys.readouterr().err


def test_stale_launch_row_exits_1(tmp_path, capsys):
    assert guard.main(_root(tmp_path, {"tools/x/l.py": "x = 1\n"}, _row("tools/x/l.py::<module>", "не маршрут"))) == 1
    assert "STALE ALLOWLIST [blender-launch] tools/x/l.py::<module>" in capsys.readouterr().out


def test_existing_rules_still_fire_next_to_the_new_one(tmp_path, capsys):
    files = {"tools/a.py": "import zipfile\nzipfile.ZipFile(p, 'w')\n", "tools/b.py": "t = 1001 + u + 10 * v\n",
             "tools/c.py": LAUNCH}
    assert guard.main(_root(tmp_path, files)) == 1
    out = capsys.readouterr().out
    assert all(f"[{r}]" in out for r in ("delivery-zip", "udim-tile", "blender-launch"))


# ---------------------------------------------------------------- owner command line
def test_blender_command_is_the_pinned_headless_line(monkeypatch):
    monkeypatch.delenv("TWINQA_BLENDER", raising=False)
    cmd = blender_runner.blender_command("s.py", ["a", 1])
    assert cmd == [blender_runner.DEFAULT_BLENDER, "--background", "--factory-startup", "--disable-autoexec",
                   "--python-exit-code", "1", "--python", "s.py", "--", "a", "1"]
    monkeypatch.setenv("TWINQA_BLENDER", "C:/b/blender.exe")
    assert blender_runner.blender_command("s.py")[0] == "C:/b/blender.exe"
    assert blender_runner.blender_command("s.py", executable="D:/x.exe")[0] == "D:/x.exe"


def test_run_blender_launches_exactly_blender_command(tmp_path, monkeypatch):
    seen = {}

    def fake_run(command, **kw):
        seen["command"], seen["env"] = command, kw["env"]
        (tmp_path / "r.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(blender_runner.subprocess, "run", fake_run)
    blender_runner.run_blender("s.py", ["x"], executable="E:/b.exe", output_json=tmp_path / "r.json",
                               log_path=tmp_path / "l.log")
    assert seen["command"] == blender_runner.blender_command("s.py", ["x"], executable="E:/b.exe")
    assert all(Path(seen["env"][k]).is_relative_to(tmp_path) for k in
               ("BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS", "BLENDER_USER_DATAFILES"))


# ---------------------------------------------------------------- the two routed VATUTINO launches
@pytest.fixture
def flora(monkeypatch):
    job = _load("flora_route_a_1378", ROUTED[0])
    calls = []
    monkeypatch.setattr(job, "run_blender", lambda script, args, **kw: calls.append((script, list(args), kw)))
    return job, calls


def test_flora_export_and_readback_declare_their_outputs(flora, tmp_path):
    job, calls = flora
    job._blender("export", tmp_path / "a.blend", tmp_path / "a.fbx")
    job._blender("readback", tmp_path / "a.fbx", tmp_path / "rb.json", 1001)
    (s1, a1, k1), (_, a2, k2) = calls
    assert s1 == job.FLORA_SCRIPT and a1 == ["export", tmp_path / "a.blend", tmp_path / "a.fbx"]
    assert k1["outputs"] == [tmp_path / "a.fbx"] and k1["output_json"] is None and k1["timeout"] == 7200
    assert k2["output_json"] == tmp_path / "rb.json" and k2["outputs"] == []
    assert a2[-1] == 1001


def test_flora_site_and_species_declare_every_render(flora, tmp_path):
    job, calls = flora
    meshes = tmp_path / "meshes.json"
    meshes.write_text(json.dumps({"oak": {}, "pine": {}}), encoding="utf-8")
    job._blender("site", "b.blend", "d.png", "o.png", tmp_path)
    job._blender("species", meshes, "d", "o", "vd", "vo", tmp_path)
    site, species = calls[0][2]["outputs"], calls[1][2]["outputs"]
    assert {p.name for p in site} == {f"site_{n}.png" for n in
                                      ("oblique_SW", "oblique_SE", "oblique_NE", "oblique_NW", "top", "eye_level")}
    assert {p.name for p in species} == {f"sp_{k}_{p}.png" for k in ("oak", "pine") for p in ("npm", "vpm")}


@pytest.mark.parametrize("args", [("bake", "x"), (), ("export", "only-one")])
def test_flora_unknown_or_short_command_is_an_error_naming_it(flora, args):
    job, calls = flora
    with pytest.raises(ValueError, match="flora_v007_blender"):
        job._blender(*args)
    assert calls == []


def test_flora_species_with_empty_mesh_table_is_an_error(flora, tmp_path):
    job, calls = flora
    (tmp_path / "m.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="no species"):
        job._blender("species", tmp_path / "m.json", "d", "o", "vd", "vo", tmp_path)
    assert calls == []


def test_flora_runner_failure_stops_the_route(monkeypatch, tmp_path):
    job = _load("flora_route_a_1378f", ROUTED[0])

    def boom(*a, **k):
        raise blender_runner.BlenderRunError({"code": "nonzero_exit", "message": "Blender exit 1: bad"})

    monkeypatch.setattr(job, "run_blender", boom)
    with pytest.raises(SystemExit, match="nonzero_exit"):
        job._blender("export", tmp_path / "a.blend", tmp_path / "a.fbx")


@pytest.fixture
def place(monkeypatch):
    job = _load("place_site_1378", ROUTED[1])
    calls = []
    monkeypatch.setattr(job, "run_blender", lambda script, args, **kw: calls.append((script, list(args), kw)))
    return job, calls


def test_place_facts_and_instance_declare_outputs_and_keep_the_record(place, tmp_path):
    job, calls = place
    rec1 = job.blender("facts", tmp_path / "spec.json", tmp_path / "facts.json")
    rec2 = job.blender("instance", tmp_path / "spec.json", tmp_path / "plan.json", tmp_path / "p.blend",
                       tmp_path / "readback.json")
    (s1, _, k1), (_, _, k2) = calls
    assert s1 == job.SCRIPT and k1["output_json"] == tmp_path / "facts.json" and k1["outputs"] == []
    assert k2["output_json"] == tmp_path / "readback.json" and k2["outputs"] == [tmp_path / "p.blend"]
    assert k1["timeout"] == 3600
    for rec in (rec1, rec2):
        assert set(rec) == {"cmd", "exit_code", "seconds"} and rec["exit_code"] == 0
        assert "--background" in rec["cmd"] and "--disable-autoexec" in rec["cmd"]


@pytest.mark.parametrize("args", [("bake", "x"), (), ("facts", "spec-only")])
def test_place_unknown_or_short_command_is_an_error_naming_it(place, args):
    job, calls = place
    with pytest.raises(ValueError, match="placement_instance"):
        job.blender(*args)
    assert calls == []


def test_place_runner_failure_stops_the_run(monkeypatch, tmp_path):
    job = _load("place_site_1378f", ROUTED[1])

    def boom(*a, **k):
        raise blender_runner.BlenderRunError({"code": "timeout", "message": "Blender timed out"})

    monkeypatch.setattr(job, "run_blender", boom)
    with pytest.raises(SystemExit, match="timeout"):
        job.blender("facts", tmp_path / "spec.json", tmp_path / "facts.json")


# ---------------------------------------------------------------- real Blender (skips without the pinned install)
REAL = blender_runner.blender_executable()
PROBE = """import json, os, sys
a = sys.argv[sys.argv.index('--') + 1:]
keys = ('BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_DATAFILES')
json.dump({'cmd': a[0], 'env': {k: os.environ.get(k) for k in keys}}, open(a[2], 'w'))
"""


@pytest.mark.skipif(not Path(REAL).is_file(), reason="pinned Blender not installed")
@pytest.mark.parametrize("which", ["flora", "place"])
def test_real_blender_launch_through_the_owner_isolates_user_config(tmp_path, monkeypatch, which):
    script = tmp_path / "probe.py"
    script.write_text(PROBE, encoding="utf-8")
    out = tmp_path / "out.json"
    monkeypatch.chdir(tmp_path)   # default log dir <cwd>/logs/blender stays inside tmp
    if which == "flora":
        job = _load("flora_route_a_1378r", ROUTED[0])
        monkeypatch.setattr(job, "FLORA_SCRIPT", script)
        job._blender("readback", tmp_path / "in.fbx", out, 1001)
    else:
        job = _load("place_site_1378r", ROUTED[1])
        monkeypatch.setattr(job, "SCRIPT", script)
        assert job.blender("facts", tmp_path / "spec.json", out)["exit_code"] == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["cmd"] in ("readback", "facts")
    home = os.path.normcase(str(Path.home()))
    for key, value in data["env"].items():
        assert value and key.lower() in value and not os.path.normcase(value).startswith(
            os.path.normcase(str(Path(os.environ.get("APPDATA", home)))))
