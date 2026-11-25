"""new-case: execute shared route import graphs before hiding any job code (#1902)."""
from importlib.machinery import ModuleSpec
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def job_origins(root, executed, modules):
    jobs = (root / "jobs").resolve()
    candidates = set(executed)
    for mod in modules:
        if mod is not None:
            candidates.update((getattr(mod, "__file__", None),
                               getattr(getattr(mod, "__spec__", None), "origin", None)))
    paths = {Path(p).resolve() for p in candidates if p and str(p) not in {"built-in", "frozen"}
             and not str(p).startswith("<")}
    return sorted(p.relative_to(jobs).as_posix() for p in paths if p.is_relative_to(jobs))


def watch_execution():
    # exec events also see spec-loaded code not inserted into sys.modules, and
    # scripts run as __main__ whose module is gone by the end of the call.
    executed = set()
    sys.addaudithook(lambda event, args: executed.add(args[0].co_filename) if event == "exec" else None)
    return executed


def test_origin_guard_path_matrix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    safe = tmp_path / "jobs-neighbour" / "safe.py"
    for i, suffix in enumerate((".py", ".PY", ".pyc", ".pyw", ".pyd", ".so", ".loader", "")):
        job = tmp_path / "jobs" / f"Job{i}" / f"probe{suffix}"
        mod = ModuleType(f"probe{i}")
        mod.__spec__ = ModuleSpec(mod.__name__, loader=None, origin=str(job))
        origins = [safe, job, job.parent / ".." / job.parent.name / job.name, job.relative_to(tmp_path)]
        for order in (origins, origins[::-1]):
            assert job_origins(tmp_path, order, [None, mod, mod]) == [f"Job{i}/{job.name}"]
        assert job_origins(tmp_path, [safe], [mod]) == [f"Job{i}/{job.name}"]
        assert job_origins(tmp_path, [safe], []) == []
    assert job_origins(tmp_path, [], []) == []


def probe_unregistered(tmp):
    job = tmp / "jobs/Probe/dynamic.py"
    job.parent.mkdir(parents=True)
    job.write_text("answer = 42\n", encoding="utf-8")
    executed = watch_execution()
    spec = importlib.util.spec_from_file_location("unregistered_probe", job)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.answer == 42 and mod.__name__ not in sys.modules
    assert job_origins(tmp, executed, ()) == ["Probe/dynamic.py"]


def synthetic_spec():
    return {"address": "Synthetic", "zero_m": 0, "source_ids": {"1": {"finish": "Panel"}},
            "finishes": {"Panel": {"udim": 1001, "kind": "placeholder", "rgb": [30, 50, 70]}}}


def run_script(path, args, *, blender=False):
    path = Path(path).resolve()
    with patch.object(sys, "argv", [str(path), *(["--"] if blender else []), *map(str, args)]), \
         patch.object(sys, "path", [str(path.parent), *sys.path]):
        try:
            runpy.run_path(str(path), run_name="__main__")
        except SystemExit as exc:
            return exc.code or 0
    return 0


def probe_route(route, tmp):
    executed = watch_execution()
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    from dt_ai.cli import agr, main as dt, shared_tools

    mathutils = ModuleType("mathutils")
    mathutils.__dict__.update(Matrix=object, Vector=object)
    # No scene APIs: crossing into scene work instead of the real refusal is a test error.
    sys.modules.update(bpy=ModuleType("bpy"), bmesh=ModuleType("bmesh"), mathutils=mathutils)

    if route in {"oks-npm", "oks-npm-copied"}:
        master, stale = tmp / "master.blend", tmp / "other.blend"
        master.write_bytes(b"synthetic revision A")
        stale.write_bytes(b"synthetic revision B")
        spec, atlas, out = tmp / "spec.json", tmp / "atlas", tmp / "npm" / "fbx"
        doc = synthetic_spec()
        atlas_options = []
        if route == "oks-npm-copied":
            from PIL import Image

            Image.new("RGB", (8, 8), (30, 50, 70)).save(tmp / "panel.png")
            doc["finishes"]["Panel"] = {"udim": 1001, "diffuse": "panel.png"}
            atlas_options.append("--copied-udims")
        spec.write_text(json.dumps(doc), encoding="utf-8")
        steps = []

        def python_spawn(argv, **kwargs):
            if argv[1:3] == ["-m", "dt_ai.cli.main"]:
                step = argv[6] if argv[4:6] == ["--blender", sys.executable] else argv[4]
                steps.append(step)
                return subprocess.CompletedProcess(argv, dt.main(argv[3:]))
            assert Path(argv[0]) == Path(sys.executable), argv
            status = run_script(argv[1], argv[2:])
            return subprocess.CompletedProcess(argv, status if isinstance(status, int) else 1)

        def blender_spawn(script, args, *, output_json, **kwargs):
            # Run the real adapter and exporter; replace only the native process boundary.
            status = run_script(script, args, blender=True)
            assert isinstance(status, str) and "atlas_master_mismatch" in status, status
            assert not output_json.exists()
            raise shared_tools.BlenderRunError({"code": "process_exit", "message": status,
                                                "log": "synthetic import probe", "returncode": 1})

        argv = ["vpm-to-npm", "--blender", sys.executable, str(spec), str(atlas), "--master", str(master),
                *atlas_options, "--then-npm", str(stale), str(spec), str(atlas), str(out)]
        with patch.object(subprocess, "run", python_spawn), patch.object(shared_tools, "run_blender", blender_spawn):
            assert agr.main(argv) == 1
        assert steps == ["atlas", "npm"]
        assert json.loads((atlas / "npm_atlas.json").read_text())["finishes"]["Panel"]["udim"] == 1001
        assert not out.parent.exists()
    elif route == "ground-npm":
        mesh = tmp / "mesh.json"
        mesh.write_bytes(b"{}")
        status = run_script(ROOT / "tools/blender/ground_json_to_fbx.py",
                            ["build", mesh, mesh, "Synthetic", "--profile", "npm"], blender=True)
        assert isinstance(status, str) and "is the input mesh JSON" in status, status
        assert list(tmp.iterdir()) == [mesh] and mesh.read_bytes() == b"{}"
    else:
        plan, out = tmp / "absent.json", tmp / "body"

        def body_spawn(argv, **kwargs):
            script = argv[argv.index("--python") + 1]
            with pytest.raises(FileNotFoundError, match="absent.json"):
                run_script(script, argv[argv.index("--") + 1:], blender=True)
            return subprocess.CompletedProcess(argv, 1)

        with patch.object(subprocess, "run", body_spawn):
            assert agr.main(["body", str(plan), str(out), "--blender", sys.executable]) == 1
        assert not out.exists()
    offenders = job_origins(ROOT, executed, tuple(sys.modules.values()))
    assert not offenders, f"{route}: loaded job Python: {', '.join(offenders)}"
    print(f"{route}: no loaded job Python")


def fresh_probe(mode, path):
    return subprocess.run([sys.executable, "-I", "-B", __file__, mode, str(path)], cwd=path,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)


@pytest.mark.parametrize("route", ["oks-npm", "oks-npm-copied", "ground-npm", "oks-vpm-body"])
def test_live_route_has_no_job_origins(route, tmp_path):
    result = fresh_probe(route, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{route}: no loaded job Python" in result.stdout


def test_origin_guard_captures_unregistered_spec(tmp_path):
    result = fresh_probe("unregistered", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("case", ["omitted", "matching", "missing", "empty", "mismatched"])
def test_palette_requires_explicit_reference(tmp_path, case):
    spec = synthetic_spec()
    spec["kpp_palette"] = {"Panel": {"kpp_finish": "Reference", "kpp_udim": 1010}}
    source, out, master = tmp_path / "spec.json", tmp_path / "out", tmp_path / "master.blend"
    source.write_text(json.dumps(spec), encoding="utf-8")
    master.write_bytes(b"synthetic master")
    command = [sys.executable, str(ROOT / "tools/derive/npm_atlas.py"), str(source), str(out), "--master", str(master)]
    if case != "omitted":
        ref = tmp_path / "reference.json"
        command += ["--kpp-spec", str(ref)]
        if case != "missing":
            reference = {"finishes": {"Reference": {"udim": 1010, "kind": "placeholder", "rgb": [30, 50, 70]}}}
            if case == "mismatched":
                reference["finishes"]["Reference"]["rgb"] = [1, 2, 3]
            ref.write_text("{}" if case == "empty" else json.dumps(reference), encoding="utf-8")
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=60)
    if case == "matching":
        assert result.returncode == 0, result.stderr
        assert json.loads((out / "npm_atlas.json").read_text())["finishes"]["Panel"]["udim"] == 1001
    else:
        diagnostic = {"omitted": "--kpp-spec", "missing": "No such file", "empty": "finishes", "mismatched": "Panel"}
        assert result.returncode != 0 and diagnostic[case] in result.stderr, result.stderr
        assert not out.exists()
    assert {p: p.read_bytes() for p in before} == before


@pytest.mark.parametrize("parts", [("jobs",), ("jobs", "..", "jobs")])
def test_checkout_job_recipe_is_refused(tmp_path, parts):
    spec, master, out = (tmp_path / n for n in ("spec.json", "master.blend", "out"))
    spec.write_text(json.dumps(synthetic_spec()), encoding="utf-8")
    master.write_bytes(b"synthetic master")
    recipe = ROOT.joinpath(*parts, "TEC26-OKS", "scripts")
    result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/derive/npm_atlas.py"), str(spec), str(out),
                             "--master", str(master), "--recipe-dir", str(recipe)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "checkout jobs/" in result.stderr, result.stderr
    assert not out.exists()


if __name__ == "__main__":
    mode, path = sys.argv[1:]
    if mode == "unregistered":
        probe_unregistered(Path(path))
    else:
        probe_route(mode, Path(path))
