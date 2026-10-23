"""Readout of px/m from UV area, world area and the assigned map size (#548).

Band numbers are read from the locked standards. The closed interval is the check
(same inclusive edges as tests/qa/test_uv.py). A zero area or a zero map size is the
non-positive threshold and is an error, never a pass and never not_run.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from twinqa.profiles import load_profiles


def _mod():
    import dt_ai.ops.texel_density_readout as readout
    return readout


def _square(side_m, uv_side):
    xyz = [[0.0, 0.0, 0.0], [side_m, 0.0, 0.0], [side_m, side_m, 0.0], [0.0, side_m, 0.0]]
    uv = [[0.0, 0.0], [uv_side, 0.0], [uv_side, uv_side], [0.0, uv_side]]
    return xyz, uv


def _triangle(side_m, uv_side):
    xyz = [[0.0, 0.0, 0.0], [side_m, 0.0, 0.0], [0.0, side_m, 0.0]]
    uv = [[0.0, 0.0], [uv_side, 0.0], [0.0, uv_side]]
    return xyz, uv


def _payload(profile, map_px, xyz, uv, *, material="Brick", face_id="f0"):
    return {
        "profile": profile,
        "materials": [{"name": material, "map_px": map_px}],
        "faces": [{"id": face_id, "material": material, "xyz": xyz, "uv": uv}],
    }


def _one(profile, target, map_px=2048):
    """Unit-square world face whose area density is exactly `target` at `map_px`."""
    xyz, uv = _square(1.0, target / map_px)
    result = _mod().readout(_payload(profile, map_px, xyz, uv))
    assert len(result["faces"]) == 1
    assert result["dropped"] == []
    return result


def test_vpm_and_npm_bands_are_the_locked_standards():
    bands = _mod().density_bands()
    vpm = load_profiles().vpm["uv"]["diffuse_density_px_per_m"]
    npm = load_profiles().npm["textures"]["ground_density_px_per_square_meter"]
    assert bands["VPM"]["min"] == vpm["min"] == 512
    assert bands["VPM"]["max"] == vpm["max"] == 1706
    assert bands["NPM"]["min"] == npm["min"] == 10
    assert bands["NPM"]["max"] == npm["max"] == 40
    assert "VPM_STANDARD.yaml" in bands["VPM"]["source"]
    assert "NPM_STANDARD.yaml" in bands["NPM"]["source"]


def test_triangle_matches_ground_cake_texel_density():
    """The reported number is ground_cake.texel_density, not a second formula."""
    from dt_ai.geometry.ground_cake import texel_density

    xyz, uv = _triangle(1.25, 0.5)
    result = _mod().readout(_payload("VPM", 2048, xyz, uv))
    verts = np.asarray(xyz, dtype=np.float64)
    direct = float(texel_density(verts, np.array([[0, 1, 2]]), np.asarray(uv, dtype=np.float64)[None, :, :], 2048)[0])
    face = result["faces"][0]
    assert face["px_per_m"] == direct
    assert face["map_px"] == 2048
    assert face["px_per_m"] == pytest.approx(2048 * math.sqrt(face["uv_area"] / face["world_area_m2"]))


def test_2048_and_4096_differ_by_two_and_bands_classify():
    xyz, uv = _square(1.0, 0.5)  # 2048 -> 1024 px/m inside VPM; 4096 -> 2048 above 1706
    low = _mod().readout(_payload("VPM", 2048, xyz, uv))
    high = _mod().readout(_payload("VPM", 4096, xyz, uv))
    d2 = low["faces"][0]["px_per_m"]
    d4 = high["faces"][0]["px_per_m"]
    assert d4 == d2 * 2
    assert d4 / d2 == 2
    assert low["faces"][0]["status"] == "pass"
    assert low["passed"] is True
    assert high["faces"][0]["status"] == "fail"
    assert high["passed"] is False
    assert "not_run" not in json.dumps(low) and "not_run" not in json.dumps(high)

    vpm_inside = _one("VPM", 1024)
    vpm_below = _one("VPM", 511)
    vpm_above = _one("VPM", 1707)
    vpm_lo = _one("VPM", 512)
    vpm_hi = _one("VPM", 1706)
    assert vpm_inside["status"] == "pass"
    assert vpm_below["faces"][0]["status"] == "fail"
    assert vpm_above["faces"][0]["status"] == "fail"
    assert vpm_lo["faces"][0]["px_per_m"] == 512
    assert vpm_hi["faces"][0]["px_per_m"] == 1706
    assert vpm_lo["faces"][0]["status"] == "pass"
    assert vpm_hi["faces"][0]["status"] == "pass"

    npm_inside = _one("NPM", 20)
    npm_below = _one("NPM", 9)
    npm_above = _one("NPM", 41)
    npm_lo = _one("NPM", 10)
    npm_hi = _one("NPM", 40)
    assert npm_inside["status"] == "pass"
    assert npm_below["faces"][0]["status"] == "fail"
    assert npm_above["faces"][0]["status"] == "fail"
    assert npm_lo["faces"][0]["px_per_m"] == 10
    assert npm_hi["faces"][0]["px_per_m"] == 40
    assert npm_lo["faces"][0]["status"] == "pass"
    assert npm_hi["faces"][0]["status"] == "pass"


def test_density_scales_exactly_with_map_size_over_random_faces():
    rng = np.random.default_rng(548)
    sizes = (256, 512, 1024, 2048, 4096)
    materials, faces = [], []
    geoms = 32
    for i in range(geoms):
        a = float(rng.uniform(0.2, 5.0))
        b = float(rng.uniform(0.2, 5.0))
        xyz = [[0.0, 0.0, 0.0], [a, 0.0, 0.0], [float(rng.uniform(-0.5, 0.5)), b, float(rng.uniform(-1.0, 1.0))]]
        u = float(rng.uniform(0.05, 1.5))
        v = float(rng.uniform(0.05, 1.5))
        uv = [[0.0, 0.0], [u, 0.0], [float(rng.uniform(0.0, u * 0.2)), v]]
        for size in sizes:
            name = f"m{i}_{size}"
            materials.append({"name": name, "map_px": size})
            faces.append({"id": f"f{i}_{size}", "material": name, "xyz": xyz, "uv": uv})
    result = _mod().readout({"profile": "VPM", "materials": materials, "faces": faces})
    assert result["dropped"] == []
    by_id = {face["id"]: face["px_per_m"] for face in result["faces"]}
    checked = 0
    for i in range(geoms):
        base = by_id[f"f{i}_256"]
        for size in sizes:
            assert by_id[f"f{i}_{size}"] == base * (size / 256)
            checked += 1
        assert by_id[f"f{i}_4096"] / by_id[f"f{i}_2048"] == 2
    assert checked == geoms * len(sizes)
    print(f"linear map-size probe {checked}/{checked}")


def test_unmapped_material_is_named_and_not_a_default_or_the_first_entry():
    xyz, uv = _square(1.0, 0.25)  # would be 1024 px/m if somebody substituted 4096
    payload = {
        "profile": "VPM",
        "materials": [{"name": "First", "map_px": 4096}, {"name": "Brick", "map_px": 2048}],
        "faces": [
            {"id": "kept", "material": "Brick", "xyz": xyz, "uv": uv},
            {"id": "lost", "material": "Missing", "xyz": xyz, "uv": uv},
        ],
    }
    result = _mod().readout(payload)
    assert result["passed"] is False
    assert result["status"] == "fail"
    assert [face["id"] for face in result["faces"]] == ["kept"]
    assert result["faces"][0]["map_px"] == 2048
    assert result["faces"][0]["px_per_m"] == 512
    lost = [item for item in result["dropped"] if item.get("id") == "lost"]
    assert len(lost) == 1
    assert "Missing" in lost[0]["reason"]
    assert "4096" not in lost[0]["reason"]
    assert "not_run" not in json.dumps(result)


def test_duplicate_material_does_not_keep_the_first_map_size():
    xyz, uv = _square(1.0, 1.0)
    payload = {
        "profile": "NPM",
        "materials": [
            {"name": "Brick", "map_px": 2048},
            {"name": "Brick", "map_px": 4096},
        ],
        "faces": [{"id": "f0", "material": "Brick", "xyz": xyz, "uv": uv}],
    }
    result = _mod().readout(payload)
    assert result["faces"] == []
    assert result["passed"] is False
    text = " ".join(item["reason"] for item in result["dropped"])
    assert "Brick" in text
    assert "first" in text
    assert all(item.get("px_per_m") is None for item in result["dropped"])


def test_every_input_element_is_reported_or_dropped():
    xyz, uv = _square(1.0, 0.5)
    payload = {
        "profile": "VPM",
        "materials": [
            {"name": "Brick", "map_px": 2048},
            {"name": "Bare"},
            {"name": "Idle", "map_px": 1024},
        ],
        "faces": [
            {"id": "ok", "material": "Brick", "xyz": xyz, "uv": uv},
            {"id": "short", "material": "Brick", "xyz": xyz[:2], "uv": uv[:2]},
            {"material": "Brick", "xyz": xyz, "uv": uv},
            {"id": "nan", "material": "Brick", "xyz": [[0, 0, math.nan], [1, 0, 0], [1, 1, 0], [0, 1, 0]], "uv": uv},
        ],
    }
    result = _mod().readout(payload)
    face_indexes = {item["index"] for item in result["faces"]} | {
        item["index"] for item in result["dropped"] if item["kind"] == "face"
    }
    material_indexes = {item["index"] for item in result["materials"]} | {
        item["index"] for item in result["dropped"] if item["kind"] == "material"
    }
    assert face_indexes == {0, 1, 2, 3}
    assert material_indexes == {0, 1, 2}
    assert result["passed"] is False
    assert any("Bare" in item["reason"] for item in result["dropped"])
    assert any(item["kind"] == "material" and item["name"] == "Idle" for item in result["materials"])
    assert "not_run" not in json.dumps(result)


@pytest.mark.parametrize(
    "call",
    [
        lambda m: m.px_per_m(0.0, 1.0, 2048),
        lambda m: m.px_per_m(1.0, 0.0, 2048),
        lambda m: m.px_per_m(-0.2, 1.0, 2048),
        lambda m: m.px_per_m(1.0, -0.2, 2048),
        lambda m: m.px_per_m(1.0, 1.0, 0),
        lambda m: m.px_per_m(1.0, 1.0, -2048),
        lambda m: m.px_per_m(math.nan, 1.0, 2048),
        lambda m: m.px_per_m(1.0, math.inf, 2048),
        lambda m: m.px_per_m(1.0, 1.0, math.nan),
        lambda m: m.px_per_m(True, 1.0, 2048),
    ],
)
def test_exactly_at_nonpositive_threshold_and_nonfinite_areas_error(call):
    with pytest.raises(_mod().ReadoutError) as caught:
        call(_mod())
    text = str(caught.value)
    assert "not_run" not in text
    assert "pass" not in text.lower()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"profile": "VPM", "materials": []},
        {"profile": "VPM", "faces": []},
        {"profile": "VPM", "materials": [], "faces": []},
        {"profile": "VPM", "materials": None, "faces": []},
        {"profile": "ground", "materials": [], "faces": [{"id": "f"}]},
        {"profile": "vpm", "materials": [], "faces": [{"id": "f"}]},
        [],
        "VPM",
    ],
)
def test_empty_partial_and_unsupported_error(payload):
    with pytest.raises(_mod().ReadoutError) as caught:
        _mod().readout(payload)
    text = str(caught.value).lower()
    assert "not_run" not in text
    assert "pass" not in text


def test_cli_alias_of_input_exits_nonzero_and_writes_nothing(tmp_path):
    src, report = tmp_path / "in.json", tmp_path / "report.json"
    xyz, uv = _square(1.0, 0.5)
    body = json.dumps(_payload("VPM", 2048, xyz, uv)).encode("utf-8")
    src.write_bytes(body)
    before = src.read_bytes()
    code = _mod().main(["--input", str(src), "--output", str(src), "--report", str(report)])
    assert code != 0
    assert src.read_bytes() == before
    assert not report.exists()
    assert list(tmp_path.glob("*.partial")) == []

    out = tmp_path / "out.json"
    code = _mod().main(["--input", str(src), "--output", str(out), "--report", str(out)])
    assert code != 0
    assert not out.exists()
    assert src.read_bytes() == before
    assert list(tmp_path.glob("*.partial")) == []

    partial = tmp_path / "out.json.partial"
    partial.write_bytes(body)
    code = _mod().main(["--input", str(partial), "--output", str(out), "--report", str(report)])
    assert code != 0
    assert partial.read_bytes() == body
    assert not out.exists()
    assert not report.exists()


def test_cli_writes_distinct_output_and_report(tmp_path):
    src = tmp_path / "in.json"
    out = tmp_path / "out.json"
    report = tmp_path / "report.json"
    xyz, uv = _square(1.0, 0.5)
    payload = _payload("VPM", 2048, xyz, uv)
    raw = json.dumps(payload).encode("utf-8")
    src.write_bytes(raw)
    code = _mod().main(["--input", str(src), "--output", str(out), "--report", str(report)])
    assert code == 0
    assert src.read_bytes() == raw
    assert out.is_file() and report.is_file()
    assert out.read_bytes() != raw
    assert not list(tmp_path.glob("*.partial"))
    written = json.loads(out.read_text(encoding="utf-8"))
    summary = json.loads(report.read_text(encoding="utf-8"))
    assert written["faces"][0]["px_per_m"] == 1024
    assert summary["status"] == "pass"
    assert summary["passed"] is True
    assert summary["input_sha256"] == hashlib.sha256(raw).hexdigest()
    assert summary["counts"]["faces"] == 1
    assert summary["counts"]["dropped"] == 0
    keys = {path.resolve() for path in (src, out, report)}
    assert len(keys) == 3


def test_cli_content_failure_still_names_the_material(tmp_path, capsys):
    src, out, report = tmp_path / "in.json", tmp_path / "out.json", tmp_path / "report.json"
    payload = {
        "profile": "NPM",
        "materials": [{"name": "Paint"}],
        "faces": [{"id": "f0", "material": "Paint", "xyz": _square(1.0, 0.2)[0], "uv": _square(1.0, 0.2)[1]}],
    }
    src.write_text(json.dumps(payload), encoding="utf-8")
    code = _mod().main(["--input", str(src), "--output", str(out), "--report", str(report)])
    assert code != 0
    assert "Paint" in capsys.readouterr().err
    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved["passed"] is False
    assert any("Paint" in item["reason"] for item in saved["dropped"])
    assert "not_run" not in report.read_text(encoding="utf-8")
