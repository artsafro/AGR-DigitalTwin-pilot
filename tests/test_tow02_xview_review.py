"""new-case: native MAXScript runner contract for TOW02 review #514.

Synthetic scenes only. Opt-in: AGR_TOW02_NATIVE=1 pytest -m max ...
The harness executes the real runner, replacing only its output root and process quit.
Live Max is held/restored; source fixtures are never overwritten by the runner.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "jobs/vyatskaya-tow02/scripts/xview_review.ms"
MAX_EXEC = Path("C:/Users/artsafro/hermes_kanban/scripts/max_exec.py")
pytestmark = pytest.mark.max


def ms_string(value):
    return json.dumps(str(value).replace("\\", "/"))


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    if os.environ.get("AGR_TOW02_NATIVE") != "1":
        pytest.skip("opt-in live Max synthetic contract")
    out = tmp_path_factory.mktemp("tow02-native")
    source = RUNNER.read_text(encoding="utf-8")
    specs = [
        ("existing", "scene.max", "013_Main", ""),
        ("missing", "scene.max", "013_Mian", ""),
        ("nonmesh", "scene.max", "Point_Helper", ""),
        ("default", "scene.max", "", ""),
        ("repeat", "scene.max", "013_Main", ""),
        ("fbx", "scene.fbx", "013_Main", ""),
        ("weld", "scene.max", "013_Main", "weld"),
        ("weldpoly", "scene.max", "013_Main", "weldpoly"),
        ("empty", "empty.max", "", ""),
        ("unsupported", "scene.txt", "013_Main", ""),
        ("badmode", "scene.max", "013_Main", "bogus"),
        ("partial", "", "013_Main", ""),
    ]
    specs.extend((f"generated{i}", "scene.max", f"013_Missing_{i}", "") for i in range(5))
    (out / "jobs.txt").write_text("\n".join(
        f"{label}|{(out / path).as_posix() if path else ''}|{node}|{mode}"
        for label, path, node, mode in specs
    ), encoding="ascii")
    run = source.replace('systemTools.getEnvVariable "TOW02_XV_OUT"', ms_string(out))
    run = run.replace("quitMax #noPrompt", "()")
    (out / "runner.ms").write_text(run, encoding="utf-8")
    # Fault injection at the native API boundary, not a Python reimplementation.
    for label, patched in [
        ("unavailable", run.replace('nm == "Overlapping Faces"', 'nm == "Unavailable checker"')),
        ("failed", run.replace("local rv = xViewChecker.getCurrentReturnVal()", "local rv = #Failed")),
    ]:
        sub = out / label
        sub.mkdir()
        (sub / "jobs.txt").write_text(f"{label}|{(out / 'scene.max').as_posix()}|013_Main|", encoding="ascii")
        (sub / "runner.ms").write_text(patched.replace(ms_string(out), ms_string(sub)), encoding="utf-8")
    guard_calls = []
    for label, lines, sentinel in [
        ("stale", "existing|{scene}|013_Main|", "existing.json"),
        ("duplicate", "again|{scene}|013_Main|\nagain|{scene}|013_Main|", None),
        ("traversal", "../escape|{scene}|013_Main|", None),
        ("done", "existing|{scene}|013_Main|", "done.txt"),
        ("emptyjobs", "", None),
        ("absentalias", "absentalias|{self}|013_Main|", None),
        ("case_duplicate", "again|{scene}|013_Main|\nAGAIN|{scene}|013_Main|", None),
    ]:
        sub = out / label
        sub.mkdir()
        (sub / "jobs.txt").write_text(lines.format(scene=(out / "scene.max").as_posix(),
                                                  self=(sub / f"{label}.json").as_posix()), encoding="ascii")
        if sentinel:
            (sub / sentinel).write_text("DO NOT OVERWRITE", encoding="ascii")
        (sub / "runner.ms").write_text(run.replace(ms_string(out), ms_string(sub)), encoding="utf-8")
        guard_calls.append(f'''(
          local rejected = false
          try (fileIn {ms_string(sub / 'runner.ms')}) catch (rejected = true)
          local f = createFile {ms_string(sub / 'guard.txt')}
          format "%" rejected to:f
          close f
        )''')
    setup = f'''(
      holdMaxFile()
      local failure = undefined
      try (
        resetMaxFile #noPrompt
        units.systemType = #meters
        units.systemScale = 1.0
        saveMaxFile {ms_string(out / 'empty.max')} quiet:true
        local small = box name:"013_Main" width:1 length:1 height:1
        convertToPoly small
        local big = sphere name:"030_Main" radius:2 pos:[10,0,0] segs:16
        convertToPoly big
        point name:"Point_Helper" pos:[20,0,0]
        saveMaxFile {ms_string(out / 'scene.max')} quiet:true
        select small
        exportFile {ms_string(out / 'scene.fbx')} #noPrompt selectedOnly:true using:FBXEXP
        copyFile {ms_string(out / 'scene.max')} {ms_string(out / 'scene-before.max')}
        copyFile {ms_string(out / 'scene.fbx')} {ms_string(out / 'scene-before.fbx')}
        local f = createFile {ms_string(out / 'scene.txt')}
        format "unsupported" to:f
        close f
        fileIn {ms_string(out / 'runner.ms')}
        fileIn {ms_string(out / 'unavailable/runner.ms')}
        fileIn {ms_string(out / 'failed/runner.ms')};
        {';'.join(guard_calls)}
      ) catch (failure = getCurrentException())
      fetchMaxFile quiet:true
      if failure != undefined then throw failure
      "TOW02_NATIVE_DONE"
    )'''
    script = out / "contract.ms"
    script.write_text(setup, encoding="utf-8")
    env = dict(os.environ)
    # The worker must pin the inspected live PID, never choose another/newest GUI.
    assert env.get("MCP_MAX_PID"), "pin inspected Max PID before native tests"
    result = subprocess.run([sys.executable, str(MAX_EXEC), "--file", str(script),
                             "--card", "t_87373483", "--timeout", "180"],
                            capture_output=True, text=True, encoding="utf-8", env=env, timeout=240)
    (out / "transport.json").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"]["success"], payload
    assert "TOW02_NATIVE_DONE" in payload["result"]["result"], payload
    rows = {label: json.loads((out / f"{label}.json").read_text()) for label, *_ in specs}
    for label in ("unavailable", "failed"):
        rows[label] = json.loads((out / label / f"{label}.json").read_text())
    rows["_out"] = out
    return rows


def error(row, word):
    assert word.lower() in row.get("error", "").lower(), row
    assert "facesCheck" not in row and "verticesCheck" not in row, row


def checked(row, name):
    assert "error" not in row, row
    assert row["node"] == name
    assert row["faces"] > 0
    assert row["facesCheck"]["type"] != "#Failed"
    assert row["verticesCheck"]["type"] != "#Failed"


def test_explicit_existing(native):
    checked(native["existing"], "013_Main")


def test_explicit_missing(native):
    error(native["missing"], "013_Mian")


@pytest.mark.parametrize("i", range(5))
def test_generated_missing_targets(native, i):
    error(native[f"generated{i}"], f"013_Missing_{i}")


def test_explicit_nonmesh(native):
    error(native["nonmesh"], "Point_Helper")


def test_omitted_target(native):
    checked(native["default"], "030_Main")


def test_fbx(native):
    checked(native["fbx"], "013_Main")


def test_weld(native):
    checked(native["weld"], "013_Main")
    assert native["weld"]["weldedVerts"] >= 0
    assert native["weld"]["tris"] == native["weld"]["faces"]


def test_weldpoly(native):
    checked(native["weldpoly"], "013_Main")
    assert native["weldpoly"]["weldedVerts"] >= 0
    assert native["weldpoly"]["tris"] == 0


def test_reset_repeat(native):
    checked(native["existing"], "013_Main")
    error(native["missing"], "013_Mian")
    error(native["nonmesh"], "Point_Helper")
    checked(native["default"], "030_Main")
    checked(native["repeat"], "013_Main")
    assert native["existing"]["faces"] == native["repeat"]["faces"] == 6


def test_empty(native):
    error(native["empty"], "mesh")


@pytest.mark.parametrize("label,word", [("unsupported", "extension"), ("badmode", "bogus"), ("partial", "path")])
def test_invalid_job(native, label, word):
    error(native[label], word)


def test_checker_unavailable(native):
    error(native["unavailable"], "checker")


def test_checker_failed(native):
    error(native["failed"], "Failed")


@pytest.mark.parametrize("label,sentinel", [("stale", "existing.json"), ("duplicate", None),
                                            ("traversal", None), ("done", "done.txt"),
                                            ("emptyjobs", None), ("absentalias", None), ("case_duplicate", None)])
def test_no_clobber_preflight(native, label, sentinel):
    out = native["_out"]
    assert (out / label / "guard.txt").read_text() == "true"
    if sentinel:
        assert (out / label / sentinel).read_text() == "DO NOT OVERWRITE"
    assert not (out / "escape.json").exists()


def test_source_bytes_preserved(native):
    for ext in ("max", "fbx"):
        out = native["_out"]
        assert hashlib.sha256((out / f"scene.{ext}").read_bytes()).digest() == hashlib.sha256(
            (out / f"scene-before.{ext}").read_bytes()).digest()


@pytest.mark.parametrize("kind", ["hardlink", "resolved"])
def test_output_input_alias(native, kind):
    out = native["_out"]
    sub = out / f"alias-{kind}"
    sub.mkdir()
    original = out / "scene.max"
    destination = sub / "alias.json"
    if kind == "hardlink":
        os.link(original, destination)
        input_path = original
    else:
        destination.write_bytes(original.read_bytes())
        input_path = sub / "." / "alias.json"
    before = destination.read_bytes()
    (sub / "jobs.txt").write_text(f"alias|{input_path.as_posix()}|013_Main|", encoding="ascii")
    source = RUNNER.read_text(encoding="utf-8").replace(
        'systemTools.getEnvVariable "TOW02_XV_OUT"', ms_string(sub)).replace("quitMax #noPrompt", "()")
    script = sub / "runner.ms"
    script.write_text(source, encoding="utf-8")
    result = subprocess.run([sys.executable, str(MAX_EXEC), "--file", str(script),
                             "--card", "t_87373483", "--timeout", "30"],
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    payload = json.loads(result.stdout)
    assert "Existing report: alias" in payload["result"]["result"], payload
    assert destination.read_bytes() == before == original.read_bytes()
    assert not (sub / "done.txt").exists()
