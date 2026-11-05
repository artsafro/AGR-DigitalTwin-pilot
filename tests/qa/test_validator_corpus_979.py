"""new-case: qa.package rework (#979, branch E3): corrupt-archive corpus and Light FBX rules of the validator.

Sources (rule ideas only, no code reproduced, #853): AGR Zipper v2.1 `AGR_Zipper.zip`
sha256 2bdd7ff2857cebfcba7a60f7e836512408e0d4d3c42758b88bd079117d35f4b7 (T06/agr_zipper_2506, measured: crashes on an
encrypted GeoJSON and a truncated archive, `../`, absolute and NUL names pass, nested VPM folders pass, a non-PNG `.png`
is only a warning, palette tRNS alpha is not seen); AGR Checker `AGR_Checker.zip`
sha256 0c1e5f7454bf9aa5183e5e9d1893f6b801b3f0123638278cbb97651748693e4d (T04/agr_checker: Light FBX rules).
Each defect: a small model of the source behaviour (strict xfail) RED, the validator GREEN. Every corrupt case ends in
its own `data.code`, never in a traceback.
"""
import json
import os
import struct
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

import validate_package as vp
from test_validator import geojson
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
PROFILES = load_profiles()
FBX = b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7400) + b"\x00" * 64
ZIPPER = pytest.param("zipper", marks=pytest.mark.xfail(strict=True, reason="source behaviour (T06/agr_zipper_2506)"))


def png(mode="RGB", size=(256, 256), **save):
    b = BytesIO()
    Image.new(mode, size, 0).save(b, "PNG", **save)
    return b.getvalue()


def palette_trns():
    b = BytesIO()
    im = Image.new("P", (256, 256), 0)
    im.putpalette([0, 0, 0, 255, 255, 255] + [0] * 762)
    im.save(b, "PNG", transparency=0)
    return b.getvalue()


def vpm_files(**extra):
    files = {"SM_X.fbx": FBX, "SM_X.geojson": geojson(), "T_X_Diffuse_1.1001.png": png(),
             "T_X_ERM_1.1001.png": png(), "T_X_Normal_1.1001.png": png()}
    files.update(extra)
    return files


def write_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    return path


def nul_zip(path):
    write_zip(path, vpm_files(**{"SM_X_Light.fbxQ../escape": FBX}))
    path.write_bytes(path.read_bytes().replace(b"SM_X_Light.fbxQ../escape", b"SM_X_Light.fbx\x00../escape"))
    return path


def encrypted_zip(path):
    write_zip(path, vpm_files())
    raw = bytearray(path.read_bytes())
    with zipfile.ZipFile(BytesIO(bytes(raw))) as z:
        for info in z.infolist():
            if info.filename.endswith(".geojson"):
                raw[info.header_offset + 6] |= 1
    at = 0
    while (at := bytes(raw).find(b"PK\x01\x02", at)) >= 0:
        n = struct.unpack_from("<H", raw, at + 28)[0]
        if bytes(raw[at + 46:at + 46 + n]).endswith(b".geojson"):
            raw[at + 8] |= 1
        at += 4
    path.write_bytes(bytes(raw))
    return path


def truncated_zip(path):
    write_zip(path, vpm_files())
    data = path.read_bytes()
    path.write_bytes(data[:len(data) * 2 // 3])
    return path


CASES = {
    "traversal": (lambda p: write_zip(p, vpm_files(**{"../SM_X_Light.fbx": FBX})), "V001", "zip_traversal"),
    "absolute": (lambda p: write_zip(p, vpm_files(**{"C:/abs/SM_X_Light.fbx": FBX})), "V001", "zip_absolute"),
    "nul": (nul_zip, "V001", "zip_nul_name"),
    "nested_vpm": (lambda p: write_zip(p, vpm_files(**{"sub/SM_X_Light.fbx": FBX})), "V001", "zip_nested"),
    "not_png": (lambda p: write_zip(p, vpm_files(**{"T_X_Diffuse_1.1001.png": b"not a png"})), "V007", "png_not_png"),
    "trns_palette": (lambda p: write_zip(p, vpm_files(**{"T_X_ERM_1.1001.png": palette_trns()})), "V007", "png_alpha"),
    "trns_rgb": (lambda p: write_zip(p, vpm_files(**{"T_X_Normal_1.1001.png": png(transparency=(0, 0, 0))})),
                 "V007", "png_alpha"),
    "truncated": (truncated_zip, "V001", "zip_unreadable"),
    "encrypted_geojson": (encrypted_zip, "V001", "zip_encrypted"),
}


def _codes(rep):
    return {(s.id, f.data.get("code")) for s in rep.stages for f in s.findings if f.status == "fail"}


@pytest.mark.parametrize("case", sorted(CASES))
def test_corpus_each_case_has_its_own_code_without_a_crash(tmp_path, case):
    make, stage, code = CASES[case]
    (tmp_path / ("c_" + case)).mkdir()
    path = make(tmp_path / ("c_" + case) / "SM_X.zip")
    rep = vp.validate(path, None, PROFILES)
    assert rep.exit_code == 1 and (stage, code) in _codes(rep), _codes(rep)


def test_corpus_codes_are_distinct_per_defect(tmp_path):
    got = {}
    for case, (make, _stage, _code) in CASES.items():
        (tmp_path / ("c_" + case)).mkdir()
        rep = vp.validate(make(tmp_path / ("c_" + case) / "SM_X.zip"), None, PROFILES)
        got[case] = {c for _s, c in _codes(rep)} - {None}
    zip_cases = ("traversal", "absolute", "nul", "nested_vpm", "truncated", "encrypted_geojson")
    firsts = [CASES[c][2] for c in zip_cases]
    assert len(set(firsts)) == len(firsts) and all(CASES[c][2] in got[c] for c in CASES)


def test_cli_reports_encrypted_and_nul_as_json_not_a_traceback(tmp_path):
    for make in (encrypted_zip, nul_zip):
        (tmp_path / make.__name__).mkdir()
        path = make(tmp_path / make.__name__ / "SM_X.zip")
        proc = subprocess.run([sys.executable, str(ROOT / "tools/qa/validate_package.py"), str(path), "--json"],
                              capture_output=True)
        assert proc.returncode == 1 and b"Traceback" not in proc.stderr
        rep = json.loads(proc.stdout.decode("utf-8"))
        assert rep["exit_code"] == 1


# ---- source behaviour models (T06 measurements, no Zipper code) -------------------------------------------------
def zipper_verdict(path):
    """AGR Zipper check_zip: basename only, zipfile truncation at NUL, RuntimeError/BadZipFile not caught."""
    with zipfile.ZipFile(path) as z:  # BadZipFile escapes (truncated archive: crash, no report)
        names = [os.path.basename(i.filename) for i in z.infolist()]
        for n in z.namelist():
            if n.endswith(".geojson"):
                z.read(n)  # RuntimeError on an encrypted member escapes
    return "fail" if len(names) != len(set(names)) else "pass"


def core_verdict(path):
    return "fail" if vp.validate(path, None, PROFILES).exit_code == 1 else "pass"


@pytest.mark.parametrize("impl", [ZIPPER, "core"])
@pytest.mark.parametrize("case", ["traversal", "absolute", "nul", "nested_vpm", "truncated", "encrypted_geojson"])
def test_zipper_defects_fail_with_a_report(tmp_path, case, impl):
    make = CASES[case][0]
    (tmp_path / ("c_" + case)).mkdir()
    path = make(tmp_path / ("c_" + case) / "SM_X.zip")
    verdict = zipper_verdict if impl == "zipper" else core_verdict
    try:
        got = verdict(path)
    except Exception as exc:  # noqa: BLE001 - a crash is not a report
        got = "crash: " + type(exc).__name__
    assert got == "fail"


def zipper_png_level(data):
    """Zipper: a not-PNG `.png` only warns; palette+tRNS is judged by colour type, not as alpha."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return "warn"
    return "fail" if data[25] in (4, 6) else "pass"


def core_png_level(data, name="T_X_ERM_1.1001.png"):
    findings, _sets = vp.vpm_texture_findings({name: data}, PROFILES.profile("vpm"), "T_X")
    return "fail" if any(f.status == "fail" and f.name in ("PNG readable", "no alpha in ERM/Normal")
                         for f in findings) else "pass"


@pytest.mark.parametrize("impl", [ZIPPER, "core"])
def test_fake_png_and_trns_alpha_fail(impl):
    level = zipper_png_level if impl == "zipper" else core_png_level
    assert level(b"not a png") == "fail" and level(palette_trns()) == "fail"
    assert level(png(transparency=(0, 0, 0))) == "fail"


# ---- Light FBX (AGR Checker rule idea) --------------------------------------------------------------------------
def _prop(v):
    if isinstance(v, bool):
        return b"C" + bytes([int(v)])
    if isinstance(v, int) and abs(v) > 2**31 - 1 or isinstance(v, int) and v > 1000:
        return b"L" + struct.pack("<q", v)
    if isinstance(v, int):
        return b"I" + struct.pack("<i", v)
    if isinstance(v, float):
        return b"D" + struct.pack("<d", v)
    raw = v.encode("latin-1") if isinstance(v, str) else v
    return b"S" + struct.pack("<I", len(raw)) + raw


def _node(name, props=(), children=(), at=0):
    body = b"".join(_prop(p) for p in props)
    head_len = 13 + len(name)
    kids, pos = b"", at + head_len + len(body)
    for c in children:
        blob = _node(*c, at=pos)
        kids += blob
        pos += len(blob)
    if children:
        kids += b"\x00" * 13
    end = at + head_len + len(body) + len(kids)
    return struct.pack("<III", end, len(props), len(body)) + bytes([len(name)]) + name.encode() + body + kids


def fbx_binary(nodes):
    out = FBX[:27]
    for n in nodes:
        out += _node(*n, at=len(out))
    return out + b"\x00" * 13


def _p(name, kind, *values):
    return ("P", (name, kind, "", "A") + tuple(values))


def light_fbx(root="SM_X_Root", lights=(("SM_X_Spot_001", 2), ("SM_X_Omni_001", 0)), root_t=(0.0, 0.0, 0.0),
              parented=True):
    objects, links = [], []
    objects.append(("Model", (5000, root + "\x00\x01Model", "Null"),
                    [("Properties70", (), [_p("Lcl Translation", "Lcl Translation", *root_t)])]))
    links.append(("C", ("OO", 5000, 0)))
    for i, (name, ltype) in enumerate(lights):
        mid, aid = 6000 + i, 7000 + i
        objects.append(("Model", (mid, name + "\x00\x01Model", "Light"), []))
        objects.append(("NodeAttribute", (aid, name + "\x00\x01NodeAttribute", "Light"),
                        [("Properties70", (), [("P", ("LightType", "enum", "", "", ltype))])]))
        links.append(("C", ("OO", aid, mid)))
        links.append(("C", ("OO", mid, 5000 if parented else 0)))
    return fbx_binary([("Objects", (), objects), ("Connections", (), links)])


def _light(data, cipher="SM_X"):
    return {f.data.get("code") for f in vp.light_findings("SM_X_Light.fbx", data, cipher, [36]) if f.status == "fail"}


def test_light_scene_reads_root_parents_and_types():
    models = vp.light_scene(light_fbx())
    names = {m["name"]: m for m in models.values()}
    assert names["SM_X_Spot_001"]["light"] == "Spot" and names["SM_X_Omni_001"]["light"] == "Omni"
    assert names["SM_X_Spot_001"]["parent"] == 5000 and names["SM_X_Root"]["parent"] == 0


def test_light_fbx_good_passes():
    assert _light(light_fbx()) == set()
    assert _light(light_fbx(root="SM_X_Ground_Root", lights=[("SM_X_Ground_Omni_002", 0)]), "SM_X_Ground") == set()


LIGHT_CASES = {
    "light_root": lambda: light_fbx(root="Root"),
    "light_root_transform": lambda: light_fbx(root_t=(1.0, 0.0, 0.0)),
    "light_parent": lambda: light_fbx(parented=False),
    "light_name": lambda: light_fbx(lights=[("SM_X_Lamp_001", 0)]),
    "light_number": lambda: light_fbx(lights=[("SM_X_Omni_051", 0)]),
    "light_type": lambda: light_fbx(lights=[("SM_X_Spot_001", 0)]),
    "light_count": lambda: light_fbx(lights=[("SM_X_Omni_{:03d}".format(i % 50 + 1), 0) for i in range(251)]),
    "light_unreadable": lambda: b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", 7400) + b"\x05",
}


@pytest.mark.parametrize("code", sorted(LIGHT_CASES))
def test_light_fbx_rules(code):
    assert code in _light(LIGHT_CASES[code]())


def test_light_rules_run_inside_the_vpm_archive(tmp_path):
    path = write_zip(tmp_path / "SM_X.zip", vpm_files(**{"SM_X_Light.fbx": light_fbx(parented=False)}))
    rep = vp.validate(path, None, PROFILES)
    assert ("V012", "light_parent") in _codes(rep)
    good = tmp_path / "ok"
    good.mkdir()
    rep = vp.validate(write_zip(good / "SM_X.zip", vpm_files(**{"SM_X_Light.fbx": light_fbx()})), None, PROFILES)
    assert not {c for _s, c in _codes(rep)} & {"light_root", "light_parent", "light_name", "light_type"}
