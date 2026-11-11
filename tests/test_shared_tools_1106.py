"""#1106: `dt derive` / `dt ground` route to one shared tool each; parity with the job scripts; fail-closed inputs.

Pattern: n/a | new-case: parity and fail-closed tests of the #1106 shared tools.
"""
import base64
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dt_ai.cli import shared_tools  # noqa: E402
from dt_ai.cli.main import parser  # noqa: E402

PKG_TOOL = ROOT / "tools/derive/package_vpm.py"
ATLAS_TOOL = ROOT / "tools/derive/npm_atlas.py"
TEC26_NOTE = "GeoJSON deferred by the user (2026-10-07, KPP; TEC26 card #559 out of scope) [D224]"


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=ROOT,
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"), **kw)


def snapshot(d):
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(Path(d).rglob("*")) if p.is_file()}


# ---- CLI routing
@pytest.mark.parametrize("kind,step,rel", [("derive", "atlas", "tools/derive/npm_atlas.py"),
                                           ("derive", "package", "tools/derive/package_vpm.py"),
                                           ("ground", "v015", "tools/ground/build_ground_v015.py")])
def test_cli_routes_each_step_to_its_one_shared_tool(kind, step, rel):
    ns = parser().parse_args([kind, step, "--", "a", "--flag"])
    argv = shared_tools.command(ROOT, ns.command, ns.step, ns.args)
    assert argv == [sys.executable, str(ROOT / rel), "a", "--flag"]


def test_npm_step_runs_blender_and_fails_closed_without_it(tmp_path):
    with pytest.raises(ValueError, match="needs Blender"):
        shared_tools.command(ROOT, "derive", "npm", ["m"], None)
    with pytest.raises(ValueError, match="not found"):
        shared_tools.command(ROOT, "derive", "npm", ["m"], str(tmp_path / "no-blender.exe"))
    fake = tmp_path / "blender.exe"
    fake.write_bytes(b"")
    argv = shared_tools.command(ROOT, "derive", "npm", ["m", "s"], str(fake))
    assert argv[0] == str(fake) and "--python-exit-code" in argv
    assert argv[argv.index("--python") + 1] == str(ROOT / "tools/derive/export_npm.py")
    assert argv[-3:] == ["--", "m", "s"]


@pytest.mark.parametrize("kind,step", [("derive", "uv"), ("ground", "v014"), ("other", "atlas")])
def test_unknown_step_is_an_error_naming_it(kind, step):
    with pytest.raises(ValueError, match=step):
        shared_tools.command(ROOT, kind, step, [])


def test_fresh_process_cli_help_and_job_shim():
    r = run([sys.executable, "-m", "dt_ai.cli.main", "ground", "v015", "--help"])
    assert r.returncode == 0 and "--job-dir" in r.stdout, r.stderr
    shim = run([sys.executable, ROOT / "jobs/VATUTINO-SITE/build_ground_v015.py", "--help"])
    assert shim.returncode == 0 and "--job-dir" in shim.stdout, shim.stderr
    r = run([sys.executable, "-m", "dt_ai.cli.main", "derive", "nope"])
    assert r.returncode != 0


# ---- package: byte parity with the job script + fail-closed
def make_pkg(base, address="Nku_1"):
    pkg = base / f"SM_{address}"
    pkg.mkdir(parents=True)
    (pkg / f"SM_{address}.fbx").write_bytes(b"FBX synthetic")
    thumb = base / "thumbnail_256.jpg"
    thumb.write_bytes(b"\xff\xd8synthetic")
    (base / "export_meta.json").write_text(json.dumps({"address": address, "h_otn_model_max_z_m": 3.5,
                                                       "thumbnail": str(thumb)}))
    return pkg


def make_tex(d, address="Nku_1"):
    d.mkdir()
    for n in ("Diffuse_1.1001", "ERM_1.1001", "Normal_1.1001"):
        (d / f"T_{address}_{n}.png").write_bytes(n.encode())
    (d / "T_Other_Diffuse_1.1001.png").write_bytes(b"not ours")
    return d


def test_package_zip_is_byte_identical_to_the_tec26_job_script(tmp_path):
    tex = make_tex(tmp_path / "tex")
    a, b = make_pkg(tmp_path / "job"), make_pkg(tmp_path / "dt")
    for p in (a, b):
        os.utime(p / "SM_Nku_1.fbx", (1_700_000_000, 1_700_000_000))
    rj = run([sys.executable, ROOT / "jobs/TEC26-OKS/scripts/package_vpm.py", a, tex, "--no-geojson"])
    rd = run([sys.executable, PKG_TOOL, b, tex, "--no-geojson", "--deferred-note", TEC26_NOTE])
    assert rj.returncode == 0 and rd.returncode == 0, rj.stderr + rd.stderr
    assert (tmp_path / "job/SM_Nku_1.zip").read_bytes() == (tmp_path / "dt/SM_Nku_1.zip").read_bytes()
    ra, rb = (json.loads((tmp_path / d / "package_report.json").read_text(encoding="utf-8")) for d in ("job", "dt"))
    ra.pop("zip"), rb.pop("zip")
    assert ra == rb
    names = zipfile.ZipFile(tmp_path / "dt/SM_Nku_1.zip").namelist()
    assert "T_Other_Diffuse_1.1001.png" not in names and len(names) == 4


def test_package_geojson_takes_object_values_not_job_constants(tmp_path):
    tex = make_tex(tmp_path / "tex")
    pkg = make_pkg(tmp_path / "p")
    obj = tmp_path / "object.json"
    obj.write_text(json.dumps({"name": "Test OKS", "h_relief": 170.5}), encoding="utf-8")
    r = run([sys.executable, PKG_TOOL, pkg, tex, "--object", obj])
    assert r.returncode == 0, r.stderr
    geo = json.loads((pkg / "SM_Nku_1.geojson").read_text(encoding="utf-8"))
    props = geo["features"][0]["properties"]
    assert props["name"] == "Test OKS" and props["h_relief"] == 170.5 and props["h_abs"] == 174.0
    assert props["imageBase64"] == base64.b64encode(b"\xff\xd8synthetic").decode()
    assert geo["features"][0]["geometry"]["coordinates"] == [None, None]


@pytest.mark.parametrize("case", ["no_object", "nan", "inf", "bool", "unknown_key", "missing_name", "empty_name",
                                  "stale_geojson", "existing_zip", "existing_report", "tex_alias", "no_textures",
                                  "no_fbx"])
def test_package_fails_closed_and_writes_nothing(tmp_path, case):
    tex = make_tex(tmp_path / "tex")
    pkg = make_pkg(tmp_path / "p")
    obj = tmp_path / "object.json"
    data = {"name": "X", "h_relief": 1.0}
    args = ["--object", obj]
    if case == "no_object":
        args = []
    elif case in ("nan", "inf"):
        obj.write_text('{"name": "X", "h_relief": %s}' % ("NaN" if case == "nan" else "Infinity"))
    elif case == "bool":
        data["h_relief"] = True
    elif case == "unknown_key":
        data["h_relif"] = 1.0
    elif case == "missing_name":
        del data["name"]
    elif case == "empty_name":
        data["name"] = " "
    elif case == "stale_geojson":
        (pkg / "SM_Nku_1.geojson").write_text("{}")
        args = ["--no-geojson"]
    elif case == "existing_zip":
        (tmp_path / "p/SM_Nku_1.zip").write_bytes(b"old")
    elif case == "existing_report":
        (tmp_path / "p/package_report.json").write_text("{}")
    elif case == "tex_alias":
        tex = pkg
        args = ["--no-geojson"]
    elif case == "no_textures":
        for f in tex.glob("T_Nku_1_*"):
            f.unlink()
    elif case == "no_fbx":
        (pkg / "SM_Nku_1.fbx").unlink()
    if not obj.exists():
        obj.write_text(json.dumps(data))
    before = snapshot(tmp_path)
    r = run([sys.executable, PKG_TOOL, pkg, tex, *args])
    assert r.returncode != 0 and "refused" in r.stderr, (r.stdout, r.stderr)
    assert snapshot(tmp_path) == before


# ---- atlas: byte parity on an accepted job spec + fail-closed
# Keep workstation assets read-only; stage verified bytes beside the temporary spec.
DRIVE_TEXTURES = Path("G:/Мой диск/AGR-evidence/tec26-oks/user-textures")


def atlas_parity_spec(spec, stage, drive_root=DRIVE_TEXTURES):
    import hashlib

    data = json.loads(spec.read_text(encoding="utf-8"))
    stage.mkdir()
    for index, finish in enumerate(data["finishes"].values()):
        source = finish.get("source_texture")
        if source is None:
            continue
        local = Path(source["path"])
        drive = drive_root / local.name
        selected = local if local.is_file() else drive
        try:
            raw = selected.read_bytes()
        except FileNotFoundError:
            pytest.skip(f"missing atlas asset {local.name}: local={local}; drive_copy={drive}")
        assert hashlib.sha256(raw).hexdigest() == source["sha256"], f"sha256 mismatch: {selected}"
        target = stage / f"source-{index}.png"
        target.write_bytes(raw)
        source["path"] = str(target)
    target_spec = stage / "spec.json"
    target_spec.write_text(json.dumps(data), encoding="utf-8")
    return target_spec


def test_atlas_parity_uses_verified_drive_copy_after_local_rename(tmp_path):
    import hashlib

    local = tmp_path / "panel.png"
    local.write_bytes(b"synthetic texture bytes; resolver does not decode")
    drive = tmp_path / "drive"
    drive.mkdir()
    raw = local.read_bytes()
    (drive / local.name).write_bytes(raw)
    local.rename(tmp_path / "panel.renamed.png")
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps({"finishes": {"Panel": {"source_texture": {
        "path": str(local), "sha256": hashlib.sha256(raw).hexdigest(),
    }}}}), encoding="utf-8")
    prepared = atlas_parity_spec(spec, tmp_path / "stage", drive)
    source = json.loads(prepared.read_text())["finishes"]["Panel"]["source_texture"]
    assert Path(source["path"]).read_bytes() == raw
    assert not local.exists()
    assert (drive / local.name).read_bytes() == raw


@pytest.mark.parametrize("local_state,drive_state", [
    (local, drive) for local in ("missing", "valid", "bad", "empty")
    for drive in ("missing", "valid", "bad", "empty")
])
def test_atlas_parity_asset_availability_matrix(tmp_path, local_state, drive_state):
    import hashlib

    raw = b"synthetic verified source"
    local, drive = tmp_path / "local/panel.png", tmp_path / "drive/panel.png"
    for path, state in ((local, local_state), (drive, drive_state)):
        path.parent.mkdir()
        if state != "missing":
            path.write_bytes(raw if state == "valid" else b"" if state == "empty" else b"corrupt")
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps({"finishes": {"Panel": {"source_texture": {
        "path": str(local), "sha256": hashlib.sha256(raw).hexdigest(),
    }}, "Solid": {"kind": "solid"}}}), encoding="utf-8")
    before = snapshot(tmp_path)
    selected = local_state if local_state != "missing" else drive_state
    if selected == "missing":
        with pytest.raises(pytest.skip.Exception, match="missing atlas asset panel.png") as exc:
            atlas_parity_spec(spec, tmp_path / "stage", drive.parent)
        assert str(local) in str(exc.value) and str(drive) in str(exc.value)
    elif selected != "valid":
        with pytest.raises(AssertionError, match="sha256 mismatch"):
            atlas_parity_spec(spec, tmp_path / "stage", drive.parent)
    else:
        prepared = atlas_parity_spec(spec, tmp_path / "stage", drive.parent)
        source = json.loads(prepared.read_text())["finishes"]["Panel"]["source_texture"]
        # Changes to the original after preparation cannot change the CLI's private input.
        (local if local_state != "missing" else drive).write_bytes(b"changed after read")
        assert Path(source["path"]).read_bytes() == raw
        (local if local_state != "missing" else drive).write_bytes(raw)
    assert all((tmp_path / name).read_bytes() == value for name, value in before.items())


def test_atlas_is_byte_identical_to_the_tec26_job_script_on_ac08(tmp_path):
    spec = atlas_parity_spec(ROOT / "jobs/TEC26-OKS/AC08/vpm_textures.json", tmp_path / "inputs")
    rj = run([sys.executable, ROOT / "jobs/TEC26-OKS/scripts/make_npm_atlas.py", spec, tmp_path / "job"])
    rd = run([sys.executable, ATLAS_TOOL, spec, tmp_path / "dt"])
    assert rj.returncode == 0 and rd.returncode == 0, rj.stderr + rd.stderr
    assert snapshot(tmp_path / "job") == snapshot(tmp_path / "dt")
    assert sorted(snapshot(tmp_path / "dt")) == ["T_Nku_1_001_Main_d_1.png", "T_Nku_1_001_Main_o_1.png", "npm_atlas.json"]


@pytest.mark.parametrize("case", ["existing_out", "out_is_spec", "out_inside_recipe", "index_zero", "index_big"])
def test_atlas_fails_closed_and_writes_nothing(tmp_path, case):
    spec = tmp_path / "spec.json"
    spec.write_bytes((ROOT / "jobs/TEC26-OKS/AC08/vpm_textures.json").read_bytes())
    out, extra = tmp_path / "out", []
    if case == "existing_out":
        out.mkdir()
    elif case == "out_is_spec":
        out = spec
    elif case == "out_inside_recipe":
        out = ROOT / "jobs/TEC26-OKS/scripts/__atlas_probe_1106"
    elif case == "index_zero":
        extra = ["--index", "0"]
    else:
        extra = ["--index", "1000"]
    before = snapshot(tmp_path)
    r = run([sys.executable, ATLAS_TOOL, spec, out, *extra])
    assert r.returncode != 0 and "refused" in r.stderr, (r.stdout, r.stderr)
    assert snapshot(tmp_path) == before
    assert not (ROOT / "jobs/TEC26-OKS/scripts/__atlas_probe_1106").exists()
