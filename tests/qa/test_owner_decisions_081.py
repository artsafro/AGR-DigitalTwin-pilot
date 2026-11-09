"""AGR Tools 0.8.1 owner decisions (05.11.2026, team audit T04 open question 3, #908): V004 'applied transforms' and
the V013 «pivot at geometric centre» (centre XY) on real 3ds Max FBX.

Measured (C:/Temp, never committed): of the five delivery archives on Artem's laptop two carry FBX written by
3ds Max (SceneInfo ApplicationName '3ds Max'), three by Blender. Lab job 20261105-015151-c6e23463: a Max FBX imports
as the object's own transform by default and gains -90 deg X under bake_space_transform. So the 0.8.0 rule
«identity in either import mode» passed a Max object really turned +90 deg X. A Max FBX is now judged on the default
import only. Real-archive expectations: tests/qa/real_deliveries_081.json (archive name, SHA256, per-check verdicts);
the archives stay outside git and those tests skip when the files are absent.
"""
import hashlib
import json
import os
import struct
import zipfile
from pathlib import Path

import pytest

from test_scene import mesh, rb, statuses
from test_validator import PROFILES
from twinqa.fbx_header import fbx_application
from twinqa.scene import scene_findings

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "real_deliveries_081.json").read_text(encoding="utf-8"))


# ---- synthetic binary FBX 7.4 header ---------------------------------------------------------------------------
def fbx_bytes(app):
    """Minimal binary FBX 7400: FBXHeaderExtension/SceneInfo/Properties70/P LastSaved|ApplicationName = app."""
    p = ("P", ("LastSaved|ApplicationName", "KString", "", "", app), [])
    props70 = ("Properties70", (), [p])
    info = ("SceneInfo", ("GlobalInfo\x00\x01SceneInfo", "UserData"), [props70])
    ext = ("FBXHeaderExtension", (), [info])

    def build(n, offset):
        name, props, kids = n
        body = b"".join(b"S" + struct.pack("<I", len(s.encode())) + s.encode() for s in props)
        head = 13 + len(name)
        child = b""
        pos = offset + head + len(body)
        for k in kids:
            enc = build(k, pos + len(child))
            child += enc
        if kids:
            child += b"\x00" * 13
        end = offset + head + len(body) + len(child)
        return struct.pack("<III", end, len(props), len(body)) + bytes([len(name)]) + name.encode() + body + child
    head = b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7400)
    return head + build(ext, len(head)) + b"\x00" * 13


def test_fbx_application_reads_scene_info():
    assert fbx_application(fbx_bytes("3ds Max")) == "3ds Max"
    assert fbx_application(fbx_bytes("Blender (stable FBX IO)")) == "Blender (stable FBX IO)"
    assert fbx_application(b"not an fbx") is None
    assert fbx_application(fbx_bytes("3ds Max")[:60]) is None  # truncated: unknown, never raises


# ---- V004 on Max FBX ----------------------------------------------------------------------------------------------
def _v004(m, app):
    r = rb(m)
    r["fbx_application"] = app
    return [f for f in scene_findings(r, "vpm", "oks", PROFILES.vpm)["V004"] if f.name == "applied transforms"][0]


def test_v004_max_object_turned_plus_90_x_fails():
    """RED on 0.8.0: default import +90 X, baked import identity (the -90 X axis term cancels it) -> was pass."""
    m = mesh(rot=(90, 0, 0))
    m["baked_rotation_euler_deg"], m["baked_scale"] = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
    f = _v004(m, "3ds Max")
    assert f.status == "fail"
    assert "rotation [90" in f.observed and "3ds Max" in f.observed


def test_v004_max_identity_passes_and_real_z_rotation_fails():
    assert _v004(mesh(), "3ds Max").status == "pass"
    m = mesh(rot=(0, 0, -27.989))  # as SM_77_17_0120114_5803_10_3_002_Main in the real 1113 archive
    m["baked_rotation_euler_deg"], m["baked_scale"] = [-90.0, 0.0, -27.989], [1.0, 1.0, 1.0]
    assert _v004(m, "3ds Max").status == "fail"


def test_v004_blender_baked_export_still_passes():
    m = mesh(rot=(90, 0, 0), scale=(0.01, 0.01, 0.01))
    m["baked_rotation_euler_deg"], m["baked_scale"] = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
    assert _v004(m, "Blender (stable FBX IO)").status == "pass"
    assert _v004(m, None).status == "pass"  # unknown exporter keeps the 0.8.0 rule


def test_v013_centre_xy_on_max_fbx_is_measured_in_the_z_up_readback():
    """Centre XY uses the readback after the importer's axis conversion: a Y-up Max FBX is not a false fail
    (AGR_Checker checks.py:314-331 was, T04)."""
    m = mesh(loc=(0, 0, 0))
    m["bounds_m"] = [[-5.0, -3.0, 0.0], [5.0, 3.0, 12.0]]
    r = rb(m)
    r["fbx_application"] = "3ds Max"
    found = statuses(scene_findings(r, "vpm", "oks", PROFILES.vpm), "V013")
    assert found["pivot at geometric centre"] == "pass" and found["origin at FBX zero"] == "pass"


# ---- real deliveries (absent on CI: skip) -----------------------------------------------------------------------
# First 12 hex digits are enough to tell two same-name archives apart in a skip line.
_SHORT_HASH = 12


def _search_roots():
    """AGR_REAL_DELIVERIES first, then the pinned search dirs. Empty roots are ignored."""
    raw = []
    env_root = os.environ.get("AGR_REAL_DELIVERIES")
    if env_root:
        raw.append(env_root)
    raw.extend(EXPECTED["search_dirs"])
    return [root for root in raw if root]


def _archive(entry):
    """Return the first same-name file whose sha256 is the pin.

    Every search root is walked. A same-name file with any other hash is not used.
    If only those exist, skip and name each path with its short hash. If nothing
    with that name exists, skip as before. A file that cannot be hashed fails the
    test instead of being treated as the pin.
    """
    pinned = entry["sha256"]
    seen = set()
    mismatches = []
    for root in _search_roots():
        path = Path(os.path.expandvars(root)) / entry["archive"]
        if not path.is_file():
            continue
        key = str(path.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        digest = _sha(path)
        if digest == pinned:
            return path
        mismatches.append(f"{path} ({digest[:_SHORT_HASH]})")
    if mismatches:
        listed = ", ".join(mismatches)
        pytest.skip(
            f"found {len(mismatches)} same-name files, none with the pinned hash: {listed}"
        )
    pytest.skip(f"{entry['archive']} is not on this machine (real delivery, never committed)")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _put_archive(directory, name, payload):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


def _pin_search(monkeypatch, search_dirs, env=None):
    monkeypatch.setitem(EXPECTED, "search_dirs", list(search_dirs))
    if env is None:
        monkeypatch.delenv("AGR_REAL_DELIVERIES", raising=False)
    else:
        monkeypatch.setenv("AGR_REAL_DELIVERIES", env)


def test_archive_uses_matching_file_in_second_dir(tmp_path, monkeypatch):
    name = "pinned.zip"
    second = tmp_path / "second"
    good, digest = _put_archive(second, name, b"pinned-bytes")
    monkeypatch.setenv("AGR_UNIT_SECOND", str(second))
    _pin_search(monkeypatch, [str(tmp_path / "missing-first"), "%AGR_UNIT_SECOND%"])
    assert _archive({"archive": name, "sha256": digest}) == good


def test_archive_skips_when_only_a_different_hash_exists(tmp_path, monkeypatch):
    name = "pinned.zip"
    only = tmp_path / "only"
    path, digest = _put_archive(only, name, b"other-version")
    _pin_search(monkeypatch, [str(only)])
    with pytest.raises(pytest.skip.Exception) as caught:
        _archive({"archive": name, "sha256": "0" * 64})
    message = str(caught.value)
    assert message == (
        "found 1 same-name files, none with the pinned hash: "
        f"{path} ({digest[:_SHORT_HASH]})"
    )


def test_archive_skips_when_no_same_name_file_exists(tmp_path, monkeypatch):
    _pin_search(monkeypatch, [str(tmp_path / "empty")])
    (tmp_path / "empty").mkdir()
    with pytest.raises(pytest.skip.Exception) as caught:
        _archive({"archive": "missing.zip", "sha256": "ab" * 32})
    assert str(caught.value) == "missing.zip is not on this machine (real delivery, never committed)"


def test_archive_wrong_hash_in_dir1_does_not_shadow_dir2(tmp_path, monkeypatch):
    """Probe: a same-name file with the wrong hash in dir 1 never hides the pin in dir 2."""
    name = "pinned.zip"
    wrong, wrong_digest = _put_archive(tmp_path / "dir1", name, b"wrong-hash")
    right, right_digest = _put_archive(tmp_path / "dir2", name, b"right-hash")
    assert wrong_digest != right_digest
    _pin_search(monkeypatch, [str(wrong.parent), str(right.parent)])
    assert _archive({"archive": name, "sha256": right_digest}) == right


def test_archive_env_wrong_hash_does_not_shadow_a_later_pin(tmp_path, monkeypatch):
    name = "pinned.zip"
    _put_archive(tmp_path / "env", name, b"env-other")
    right, digest = _put_archive(tmp_path / "later", name, b"pinned-later")
    _pin_search(monkeypatch, [str(right.parent)], env=str(tmp_path / "env"))
    assert _archive({"archive": name, "sha256": digest}) == right


@pytest.mark.skipif(not os.environ.get("AGR_REAL_DELIVERIES"),
                    reason="opt-in: set AGR_REAL_DELIVERIES (local archives change and break the SHA pin)")
@pytest.mark.parametrize("entry", EXPECTED["archives"], ids=lambda e: e["archive"])
def test_real_delivery_identity_and_exporter(entry):
    path = _archive(entry)
    assert _sha(path) == entry["sha256"]
    with zipfile.ZipFile(path) as z:
        apps = {n: fbx_application(z.read(n)) for n in z.namelist() if n.lower().endswith(".fbx")}
    assert apps == {f["name"]: f["application"] for f in entry["fbx"]}


@pytest.mark.blender
@pytest.mark.parametrize("entry", EXPECTED["archives"], ids=lambda e: e["archive"])
def test_real_delivery_v004_and_centre_verdicts(entry):
    import validate_package as vp
    path = _archive(entry)
    report = vp.validate(path, entry["profile"], PROFILES, scene=True)
    got, fno, schema = {}, [], None
    for stage in report.stages:
        for f in stage.findings:
            if f.name in ("applied transforms", "origin at FBX zero", "pivot at geometric centre", "shared pivot"):
                got.setdefault(f.evidence or "", {})[f.name] = f.status
            if f.name in ("FNO registry", "FNO_code not in registry", "FNO_name vs registry") and f.status != "pass":
                fno.append([f.name, f.status])
            if stage.id == "V011" and f.name == "schema":
                schema = f.status
    for fbx in entry["fbx"]:
        for check, status in fbx["verdicts"].items():
            assert got.get(fbx["name"], {}).get(check) == status, (fbx["name"], check, got.get(fbx["name"]))
    if "geojson" in entry and entry["geojson"]:
        assert fno == entry["geojson"]["fno_findings"] and schema == entry["geojson"].get("schema")
