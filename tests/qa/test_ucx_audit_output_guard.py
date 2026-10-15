"""The UCX audit never writes its JSON report over the model it reads (#165 review round 1, P1).

Pure guard (`output_alias_reason`), the script under plain Python (the guard runs before
`import bpy`) and, with `-m blender`, the real Blender 5.1.2 run: alias path / hard link /
import-failure path exit 4 with the input bytes unchanged; a distinct output still measures.
Every fixture is synthetic and lives in tmp_path.
"""
import hashlib
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from twinqa.geometry import ucx_audit as ua

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/blender/ucx_audit.py"
FAKE_FBX = b"Kaydara FBX Binary  \x00\x1a\x00" + bytes(range(256)) * 8  # not importable: failure path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spellings(path, rng):
    """Random equivalent spellings of `path`: `.` / `x/..` segments, case flips on Windows."""
    parts = list(path.parts)
    out = [parts[0]]
    for part in parts[1:-1]:
        out.append(part)
        if rng.random() < 0.3:
            out.append(".")
        if rng.random() < 0.3:
            out += ["zz_missing", ".."]
    name = parts[-1]
    if os.name == "nt":
        name = "".join(c.upper() if rng.random() < 0.5 else c for c in name)
    return Path(*out, name)


# --- pure guard ---------------------------------------------------------------------------

def test_same_path_is_rejected(tmp_path):
    f = tmp_path / "m.fbx"
    f.write_bytes(FAKE_FBX)
    assert ua.output_alias_reason(f, f)
    assert ua.output_alias_reason(str(f), str(f))


@pytest.mark.parametrize("seed", range(40))
def test_equivalent_spellings_are_rejected(tmp_path, seed):
    f = tmp_path / "sub" / "Model.fbx"
    f.parent.mkdir()
    f.write_bytes(FAKE_FBX)
    rng = random.Random(seed)
    assert ua.output_alias_reason(f, spellings(f, rng))
    assert ua.output_alias_reason(spellings(f, rng), f)


def test_missing_input_same_path_is_rejected(tmp_path):
    f = tmp_path / "absent.fbx"
    assert ua.output_alias_reason(f, tmp_path / "." / "absent.fbx")


def test_hard_link_is_rejected(tmp_path):
    f = tmp_path / "m.fbx"
    f.write_bytes(FAKE_FBX)
    link = tmp_path / "report.json"
    os.link(f, link)
    assert ua.output_alias_reason(f, link)
    assert ua.output_alias_reason(link, f)


def test_symlink_is_rejected(tmp_path):
    f = tmp_path / "m.fbx"
    f.write_bytes(FAKE_FBX)
    link = tmp_path / "report.json"
    try:
        link.symlink_to(f)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks not permitted here: {exc}")
    assert ua.output_alias_reason(f, link)


def test_directory_output_is_rejected(tmp_path):
    f = tmp_path / "m.fbx"
    f.write_bytes(FAKE_FBX)
    assert ua.output_alias_reason(f, tmp_path)


def test_distinct_outputs_are_allowed(tmp_path):
    f = tmp_path / "m.fbx"
    f.write_bytes(FAKE_FBX)
    copy = tmp_path / "copy.fbx"
    shutil.copyfile(f, copy)  # equal bytes, different file: allowed
    assert ua.output_alias_reason(f, tmp_path / "report.json") is None
    assert ua.output_alias_reason(f, tmp_path / "new" / "m.fbx.json") is None
    assert ua.output_alias_reason(f, copy) is None


# --- the script under plain Python: the guard runs before bpy and before any write --------

def run_plain(*args):
    return subprocess.run([sys.executable, str(SCRIPT), "--", *map(str, args)], capture_output=True,
                          text=True, timeout=120, encoding="utf-8", errors="replace")


@pytest.mark.parametrize("alias", ["same", "spelling", "hardlink"])
def test_script_refuses_alias_without_writing(tmp_path, alias):
    f = tmp_path / "m.fbx"
    f.write_bytes(FAKE_FBX)
    before = sha(f)
    if alias == "same":
        out = f
    elif alias == "spelling":
        out = spellings(f, random.Random(7))
    else:
        out = tmp_path / "report.json"
        os.link(f, out)
    r = run_plain(f, out, 10)
    assert r.returncode == 4, (r.returncode, r.stderr[-500:])
    assert "UCX_AUDIT refused" in r.stderr
    assert sha(f) == before


def test_script_refuses_missing_arguments(tmp_path):
    r = run_plain(tmp_path / "m.fbx")
    assert r.returncode == 4 and "usage" in r.stderr


# --- the real Blender run (opt-in: -m blender) ----------------------------------------------

def blender_exe():
    exe = os.environ.get("DT_BLENDER") or r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
    return exe if Path(exe).is_file() else None


MAKE_FBX = """
import bpy, sys
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
bpy.context.object.name = "SM_Synth_Main"
bpy.ops.mesh.primitive_cube_add(size=2.01, location=(0, 0, 1))
bpy.context.object.name = "UCX_SM_Synth_Main_001"
bpy.ops.export_scene.fbx(filepath=sys.argv[sys.argv.index("--") + 1], use_selection=False)
"""


def run_blender(*args):
    exe = blender_exe()
    return subprocess.run([exe, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(SCRIPT), "--", *map(str, args)], capture_output=True,
                          text=True, timeout=600, encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def synth_fbx(tmp_path_factory):
    exe = blender_exe()
    if not exe:
        pytest.skip("Blender 5.1 not found (DT_BLENDER)")
    path = tmp_path_factory.mktemp("ucx_guard") / "SM_Synth.fbx"
    r = subprocess.run([exe, "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python-expr", MAKE_FBX, "--", str(path)], capture_output=True, text=True,
                       timeout=600, encoding="utf-8", errors="replace")
    assert r.returncode == 0 and path.is_file(), r.stderr[-800:]
    return path


@pytest.mark.blender
@pytest.mark.parametrize("alias", ["same", "hardlink"])
def test_blender_refuses_alias_on_valid_fbx(tmp_path, synth_fbx, alias):
    f = tmp_path / "copy.fbx"
    shutil.copyfile(synth_fbx, f)
    before = sha(f)
    out = f if alias == "same" else tmp_path / "report.json"
    if alias == "hardlink":
        os.link(f, out)
    r = run_blender(f, out, 10)
    assert r.returncode == 4, (r.returncode, r.stdout[-500:], r.stderr[-500:])
    assert sha(f) == before


@pytest.mark.blender
def test_blender_refuses_alias_on_import_failure(tmp_path):
    if not blender_exe():
        pytest.skip("Blender 5.1 not found (DT_BLENDER)")
    f = tmp_path / "broken.fbx"
    f.write_bytes(FAKE_FBX)
    before = sha(f)
    r = run_blender(f, f, 10)
    assert r.returncode == 4, (r.returncode, r.stdout[-500:], r.stderr[-500:])
    assert sha(f) == before


@pytest.mark.blender
def test_blender_distinct_output_still_measures(tmp_path, synth_fbx):
    import json
    f = tmp_path / "copy.fbx"
    shutil.copyfile(synth_fbx, f)
    before = sha(f)
    out = tmp_path / "report.json"
    r = run_blender(f, out, 10)
    assert r.returncode == 0, (r.stdout[-500:], r.stderr[-500:])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["readback_ok"] is True and report["ucx"]["count"] == 1
    assert sha(f) == before


@pytest.mark.blender
def test_blender_import_failure_still_reports_to_distinct_output(tmp_path):
    import json
    if not blender_exe():
        pytest.skip("Blender 5.1 not found (DT_BLENDER)")
    f = tmp_path / "broken.fbx"
    f.write_bytes(FAKE_FBX)
    before = sha(f)
    out = tmp_path / "report.json"
    r = run_blender(f, out, 10)
    assert r.returncode == 2, (r.returncode, r.stderr[-500:])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["readback_ok"] is False and report.get("error")
    assert sha(f) == before
