"""Readout of px/m from UV area, world area and the assigned map size (#548).

Band numbers are read from the locked standards. The closed interval is the check
(same inclusive edges as tests/qa/test_uv.py). A zero area or a zero map size is the
non-positive threshold and is an error, never a pass and never not_run.
"""
import hashlib
import json
import math
import os
import subprocess
import sys
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


# Witness: 3x3 m square minus a 1x2 m top notch. Area is 7, not the absolute fan
# (11 from this start, 9 after rotating the ring by 4). UV is a regular octagon
# sized so a correct 7 m2 reads 1800 px/m on a 2048 map (above the VPM 1706 edge).
_WITNESS_XY = [(0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (2.0, 3.0), (2.0, 1.0), (1.0, 1.0), (1.0, 3.0), (0.0, 3.0)]
_WITNESS_UV_AREA = 7.0 * (1800.0 / 2048.0) ** 2  # 5.407333374


def _witness_uv():
    scale = math.sqrt(_WITNESS_UV_AREA / (2.0 * math.sqrt(2.0)))
    return [[math.cos(i * math.pi / 4.0) * scale, math.sin(i * math.pi / 4.0) * scale] for i in range(8)]


def _turn(points, shift, reverse):
    ring = list(points[shift:]) + list(points[:shift])
    return list(reversed(ring)) if reverse else ring


def _absolute_fan_area(xyz):
    points = np.asarray(xyz, dtype=np.float64)
    area = 0.0
    for index in range(1, len(points) - 1):
        area += 0.5 * float(np.linalg.norm(np.cross(points[index] - points[0], points[index + 1] - points[0])))
    return area


def _notch_formula(width, height, x0, x1, y0):
    return width * height - (x1 - x0) * (height - y0)


def _notch_ring(width, height, x0, x1, y0):
    return np.array(
        [[0.0, 0.0], [width, 0.0], [width, height], [x1, height], [x1, y0], [x0, y0], [x0, height], [0.0, height]],
        dtype=np.float64,
    )


def _frame(rng):
    basis, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(basis) < 0:
        basis[:, 0] *= -1
    return basis[:, 0], basis[:, 1]


def _embed(ring, origin, axis_u, axis_v):
    return origin + ring[:, :1] * axis_u + ring[:, 1:2] * axis_v


@pytest.mark.parametrize("shift", range(8))
@pytest.mark.parametrize("reverse", [False, True])
def test_concave_witness_is_1800_and_fails_for_every_rotation_and_reversal(shift, reverse):
    xyz = [[x, y, 0.0] for x, y in _turn(_WITNESS_XY, shift, reverse)]
    uv = _turn(_witness_uv(), shift, reverse)
    result = _mod().readout(_payload("VPM", 2048, xyz, uv, face_id="notch"))
    assert result["dropped"] == []
    face = result["faces"][0]
    fan = _absolute_fan_area(xyz)
    assert fan != pytest.approx(7.0)
    assert (
        round(face["world_area_m2"], 6),
        round(face["uv_area"], 9),
        round(face["px_per_m"], 1),
        face["status"],
        result["passed"],
        result["materials"][0]["status"],
    ) == (7.0, round(_WITNESS_UV_AREA, 9), 1800.0, "fail", False, "fail")
    assert "1706" in face["reason"]
    assert face["id"] == "notch"
    assert result["status"] == "fail"


def test_concave_area_matches_independent_oracle_not_the_fan():
    """Random concave notches in random planes, every cyclic start and both windings.

    The expected area is width*height minus the notch. An absolute fan from a corner
    that cannot see the whole ring disagrees; the readout must not report that fan.
    """
    rng = np.random.default_rng(548)
    materials, faces = [], []
    expected = []
    fans_that_disagree = 0
    shapes = 16
    for shape in range(shapes):
        width, height = float(rng.uniform(1.0, 8.0)), float(rng.uniform(1.0, 8.0))
        x0 = float(rng.uniform(0.15 * width, 0.4 * width))
        x1 = float(rng.uniform(0.6 * width, 0.85 * width))
        y0 = float(rng.uniform(0.2 * height, 0.7 * height))
        ring = _notch_ring(width, height, x0, x1, y0)
        area = _notch_formula(width, height, x0, x1, y0)
        origin = rng.uniform(-20.0, 20.0, size=3)
        axis_u, axis_v = _frame(rng)
        xyz = _embed(ring, origin, axis_u, axis_v)
        uv_scale = float(rng.uniform(0.02, 0.2))
        uv = ring * uv_scale
        disagreed = False
        for shift in range(8):
            for reverse in (False, True):
                world = _turn(xyz.tolist(), shift, reverse)
                texture = _turn(uv.tolist(), shift, reverse)
                name = f"n{shape}_{shift}_{int(reverse)}"
                materials.append({"name": name, "map_px": 2048 if shape % 2 == 0 else 4096})
                faces.append({"id": name, "material": name, "xyz": world, "uv": texture})
                expected.append((name, area, area * uv_scale * uv_scale, 2048 if shape % 2 == 0 else 4096))
                fan = _absolute_fan_area(world)
                if abs(fan - area) > 1e-6:
                    disagreed = True
                    fans_that_disagree += 1
        assert disagreed
    result = _mod().readout({"profile": "VPM", "materials": materials, "faces": faces})
    assert result["dropped"] == []
    by_id = {face["id"]: face for face in result["faces"]}
    checked = 0
    for name, area, uv_area, map_px in expected:
        face = by_id[name]
        assert face["world_area_m2"] == pytest.approx(area, rel=1e-9, abs=1e-9)
        assert face["uv_area"] == pytest.approx(uv_area, rel=1e-9, abs=1e-12)
        assert face["px_per_m"] == pytest.approx(map_px * math.sqrt(uv_area / area), rel=1e-9, abs=1e-6)
        assert face["map_px"] == map_px
        checked += 1
    assert checked == shapes * 8 * 2
    assert fans_that_disagree > checked // 4
    same = []
    width, height, x0, x1, y0 = 4.0, 5.0, 1.0, 2.5, 1.5
    ring = _notch_ring(width, height, x0, x1, y0)
    area = _notch_formula(width, height, x0, x1, y0)
    for map_px in (2048, 4096):
        readout = _mod().readout(_payload("VPM", map_px, [[x, y, 1.0] for x, y in ring.tolist()], (ring * 0.05).tolist()))
        same.append(readout["faces"][0]["px_per_m"])
        assert readout["faces"][0]["world_area_m2"] == pytest.approx(area)
    assert same[1] == pytest.approx(same[0] * 2)
    assert same[1] / same[0] == pytest.approx(2)
    print(f"concave area probe {checked}/{checked} fan-disagreements {fans_that_disagree}")


def _bowtie(rng):
    scale = float(rng.uniform(0.3, 6.0))
    angle = float(rng.uniform(0.0, math.pi))
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    bow = np.array([[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0]], dtype=np.float64) * scale
    return bow @ rotation.T + rng.uniform(-10.0, 10.0, size=2)


def test_self_intersecting_world_and_uv_are_rejected_by_name():
    square_xyz, square_uv = _square(1.0, 0.5)
    bow = [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
    touching = [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 1.0, 0.0], [1.0, 0.0, 0.0], [1.0, 2.0, 0.0], [0.0, 2.0, 0.0]]
    cases = {
        "bow-world": (bow, square_uv, "self-intersecting", "world"),
        "touch-world": (touching, [[0.0, 0.0], [1.0, 0.0], [1.0, 0.2], [0.4, 0.0], [0.4, 0.8], [0.0, 0.8]], "self-intersecting", "world"),
        "bow-uv": (square_xyz, [[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0]], "self-intersecting", "UV"),
    }
    materials, faces = [], []
    for name, (xyz, uv, _kind, _space) in cases.items():
        materials.append({"name": name, "map_px": 2048})
        faces.append({"id": name, "material": name, "xyz": xyz, "uv": uv})
    materials.append({"name": "ok", "map_px": 2048})
    faces.append({"id": "ok", "material": "ok", "xyz": square_xyz, "uv": square_uv})
    result = _mod().readout({"profile": "VPM", "materials": materials, "faces": faces})
    assert result["passed"] is False
    assert [face["id"] for face in result["faces"]] == ["ok"]
    assert result["faces"][0]["px_per_m"] == 1024
    for name, (_xyz, _uv, kind, space) in cases.items():
        dropped = [item for item in result["dropped"] if item.get("id") == name]
        assert len(dropped) == 1
        assert dropped[0]["px_per_m"] is None
        assert name in dropped[0]["reason"]
        assert kind in dropped[0]["reason"]
        assert space in dropped[0]["reason"]
        assert "not_run" not in dropped[0]["reason"]


def test_self_intersecting_polygons_are_rejected_across_random_bowties():
    rng = np.random.default_rng(549)
    count = 24
    materials, faces = [], []
    square_xyz, square_uv = _square(1.0, 0.25)
    for index in range(count):
        bow = _bowtie(rng)
        materials.append({"name": f"w{index}", "map_px": 2048})
        faces.append({
            "id": f"w{index}",
            "material": f"w{index}",
            "xyz": [[float(x), float(y), 0.0] for x, y in bow],
            "uv": square_uv,
        })
        materials.append({"name": f"u{index}", "map_px": 4096})
        faces.append({
            "id": f"u{index}",
            "material": f"u{index}",
            "xyz": square_xyz,
            "uv": [[float(x), float(y)] for x, y in bow],
        })
    result = _mod().readout({"profile": "NPM", "materials": materials, "faces": faces})
    assert result["faces"] == []
    assert result["passed"] is False
    assert result["status"] == "fail"
    seen = set()
    for item in result["dropped"]:
        if item["kind"] != "face":
            continue
        seen.add(item["id"])
        assert item["id"] in item["reason"]
        assert "self-intersecting" in item["reason"]
        assert item["px_per_m"] is None
        if item["id"].startswith("w"):
            assert "world" in item["reason"]
        else:
            assert "UV" in item["reason"]
    assert seen == {f"w{i}" for i in range(count)} | {f"u{i}" for i in range(count)}
    print(f"self-intersection probe {len(seen)}/{len(seen)}")


def test_nonplanar_polygon_is_rejected_and_a_micrometre_kink_is_kept():
    def quad(height):
        return [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, height], [0.0, 1.0, 0.0]]

    uv = _square(1.0, 0.5)[1]
    kinked = _mod().readout(_payload("VPM", 2048, quad(0.05), uv, face_id="kink"))
    assert kinked["faces"] == []
    assert kinked["passed"] is False
    reason = kinked["dropped"][0]["reason"]
    assert "kink" in reason and "nonplanar" in reason
    kept = _mod().readout(_payload("VPM", 2048, quad(1e-6), uv, face_id="flat"))
    assert kept["dropped"] == []
    assert kept["faces"][0]["world_area_m2"] == pytest.approx(1.0, abs=1e-6)
    assert kept["faces"][0]["status"] == "pass"

    rng = np.random.default_rng(550)
    materials, faces, expect = [], [], []
    beyond = 0
    within = 0
    for index in range(20):
        span_u, span_v = float(rng.uniform(0.5, 4.0)), float(rng.uniform(0.5, 4.0))
        ring = np.array([[0.0, 0.0], [span_u, 0.0], [span_u, span_v], [0.0, span_v]], dtype=np.float64)
        origin = rng.uniform(-5.0, 5.0, size=3)
        axis_u, axis_v = _frame(rng)
        xyz = _embed(ring, origin, axis_u, axis_v)
        normal = np.cross(axis_u, axis_v)
        xyz[2] = xyz[2] + normal * 0.05
        materials.append({"name": f"bad{index}", "map_px": 2048})
        faces.append({"id": f"bad{index}", "material": f"bad{index}", "xyz": xyz.tolist(), "uv": uv})
        expect.append(("bad", f"bad{index}"))
        beyond += 1
        flat = _embed(ring, origin + 3.0, axis_u, axis_v)
        flat[2] = flat[2] + normal * 1e-6
        materials.append({"name": f"ok{index}", "map_px": 2048})
        faces.append({"id": f"ok{index}", "material": f"ok{index}", "xyz": flat.tolist(), "uv": uv})
        expect.append(("ok", f"ok{index}", span_u * span_v))
        within += 1
    result = _mod().readout({"profile": "VPM", "materials": materials, "faces": faces})
    by_drop = {item["id"]: item for item in result["dropped"] if item["kind"] == "face"}
    by_face = {face["id"]: face for face in result["faces"]}
    for kind, *rest in expect:
        if kind == "bad":
            item = by_drop[rest[0]]
            assert rest[0] in item["reason"] and "nonplanar" in item["reason"]
            assert item["px_per_m"] is None
        else:
            face = by_face[rest[0]]
            assert face["world_area_m2"] == pytest.approx(rest[1], rel=1e-6, abs=1e-6)
    assert result["passed"] is False
    assert len(by_drop) == beyond
    print(f"planarity probe {beyond + within}/{beyond + within}")


def test_degenerate_world_and_uv_name_the_face():
    square_xyz, square_uv = _square(1.0, 0.5)
    cases = {
        "line-world": ([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]], square_uv[:3], "degenerate", "world"),
        "line-uv": (square_xyz[:3], [[0.0, 0.0], [0.4, 0.0], [0.9, 0.0]], "degenerate", "UV"),
        "repeat-world": ([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], square_uv, "degenerate", "world"),
        "repeat-uv": (square_xyz, [[0.0, 0.0], [0.5, 0.0], [0.5, 0.0], [0.0, 0.5]], "degenerate", "UV"),
    }
    materials, faces = [], []
    for name, (xyz, uv, _kind, _space) in cases.items():
        materials.append({"name": name, "map_px": 2048})
        faces.append({"id": name, "material": name, "xyz": xyz, "uv": uv})
    result = _mod().readout({"profile": "VPM", "materials": materials, "faces": faces})
    assert result["faces"] == []
    assert result["passed"] is False
    for name, (_xyz, _uv, kind, space) in cases.items():
        dropped = [item for item in result["dropped"] if item.get("id") == name]
        assert len(dropped) == 1
        assert name in dropped[0]["reason"]
        assert kind in dropped[0]["reason"]
        assert space in dropped[0]["reason"]
        assert dropped[0]["px_per_m"] is None

    rng = np.random.default_rng(551)
    materials, faces = [], []
    count = 16
    for index in range(count):
        start = rng.uniform(-2.0, 2.0, size=3)
        step = rng.normal(size=3)
        step = step / np.linalg.norm(step)
        world = [start.tolist(), (start + step).tolist(), (start + 2.2 * step).tolist()]
        materials.append({"name": f"dw{index}", "map_px": 2048})
        faces.append({"id": f"dw{index}", "material": f"dw{index}", "xyz": world, "uv": square_uv[:3]})
        texture = [[0.0, 0.0], [0.2 + 0.01 * index, 0.0], [0.8, 0.0]]
        materials.append({"name": f"du{index}", "map_px": 2048})
        faces.append({"id": f"du{index}", "material": f"du{index}", "xyz": square_xyz[:3], "uv": texture})
    probed = _mod().readout({"profile": "NPM", "materials": materials, "faces": faces})
    assert probed["faces"] == []
    named = [item for item in probed["dropped"] if item["kind"] == "face"]
    assert len(named) == count * 2
    for item in named:
        assert item["id"] in item["reason"] and "degenerate" in item["reason"]
        assert item["px_per_m"] is None
    print(f"degenerate probe {len(named)}/{len(named)}")


def test_nonfinite_and_assignment_inputs_fail_closed_across_random_cases():
    rng = np.random.default_rng(552)
    square_xyz, square_uv = _square(1.0, 0.5)
    nonfinite = 0
    for index in range(12):
        xyz = [point[:] for point in square_xyz]
        xyz[index % 4][index % 3] = math.nan if index % 2 == 0 else math.inf
        result = _mod().readout(_payload("VPM", 2048, xyz, square_uv, face_id=f"nf{index}"))
        assert result["passed"] is False and result["faces"] == []
        assert "non-finite" in result["dropped"][0]["reason"]
        assert "not_run" not in result["dropped"][0]["reason"]
        nonfinite += 1
    missing = 0
    for index in range(10):
        payload = {
            "profile": "NPM" if index % 2 else "VPM",
            "materials": [{"name": f"kept{index}", "map_px": 2048}, {"name": f"ghost{index}"}],
            "faces": [
                {"id": f"ok{index}", "material": f"kept{index}", "xyz": square_xyz, "uv": square_uv},
                {"id": f"miss{index}", "material": f"gone{index}", "xyz": square_xyz, "uv": square_uv},
            ],
        }
        result = _mod().readout(payload)
        assert result["passed"] is False
        assert [face["id"] for face in result["faces"]] == [f"ok{index}"]
        assert any(f"gone{index}" in item["reason"] for item in result["dropped"])
        missing += 1
    duplicates = 0
    for index in range(10):
        payload = {
            "profile": "VPM",
            "materials": [
                {"name": "Brick", "map_px": int(rng.choice([1024, 2048, 4096]))},
                {"name": "Brick", "map_px": int(rng.choice([512, 2048, 8192]))},
            ],
            "faces": [{"id": f"d{index}", "material": "Brick", "xyz": square_xyz, "uv": square_uv}],
        }
        result = _mod().readout(payload)
        assert result["faces"] == [] and result["passed"] is False
        assert any("Brick" in item["reason"] and "first" in item["reason"] for item in result["dropped"])
        duplicates += 1
    print(f"nonfinite probe {nonfinite}/{nonfinite}")
    print(f"assignment probe {missing + duplicates}/{missing + duplicates}")


def test_cli_publish_race_keeps_the_sentinel(tmp_path, monkeypatch):
    src = tmp_path / "in.json"
    xyz, uv = _square(1.0, 0.5)
    raw = json.dumps(_payload("VPM", 2048, xyz, uv)).encode("utf-8")
    src.write_bytes(raw)
    cases = 0
    for index, role in enumerate(("output", "report") * 3):
        work = tmp_path / f"race{index}"
        work.mkdir()
        out, report = work / "out.json", work / "report.json"
        poisoned = out if role == "output" else report
        token = b"UNRELATED SENTINEL" if index == 0 else b"UNRELATED SENTINEL-" + str(index).encode("ascii")

        def commit(partial, dest, poisoned=poisoned, token=token):
            if Path(dest) == poisoned:
                Path(dest).write_bytes(token)
            os.link(partial, dest)

        monkeypatch.setattr(_mod(), "_commit_partial", commit, raising=False)
        code = _mod().main(["--input", str(src), "--output", str(out), "--report", str(report)])
        assert code != 0
        assert token in poisoned.read_bytes()
        assert not poisoned.read_bytes().lstrip().startswith(b"{")
        assert src.read_bytes() == raw
        assert list(work.glob("*.partial")) == []
        if role == "output":
            assert out.read_bytes() == token
            assert not report.exists()
        else:
            assert report.read_bytes() == token
            written = json.loads(out.read_text(encoding="utf-8"))
            assert written["faces"][0]["px_per_m"] == 1024
        cases += 1
    print(f"publish race probe {cases}/{cases}")


def test_cli_publish_uses_link_and_does_not_replace(tmp_path, monkeypatch):
    xyz, uv = _square(1.0, 0.5)
    raw = json.dumps(_payload("VPM", 2048, xyz, uv)).encode("utf-8")
    linked = {"n": 0}
    real_link = os.link

    def spy(src, dst, *args, **kwargs):
        linked["n"] += 1
        return real_link(src, dst, *args, **kwargs)

    monkeypatch.setattr(_mod().os, "link", spy)

    def boom(*_args, **_kwargs):
        raise AssertionError("os.replace must not publish the readout")

    monkeypatch.setattr(_mod().os, "replace", boom)
    runs = 0
    for index in range(4):
        work = tmp_path / f"link{index}"
        work.mkdir()
        src, out, report = work / "in.json", work / "out.json", work / "report.json"
        src.write_bytes(raw)
        before = linked["n"]
        code = _mod().main(["--input", str(src), "--output", str(out), "--report", str(report)])
        assert code == 0
        assert linked["n"] == before + 2
        assert src.read_bytes() == raw
        assert json.loads(out.read_text(encoding="utf-8"))["faces"][0]["px_per_m"] == 1024
        assert list(work.glob("*.partial")) == []
        runs += 1
    print(f"no-replace publish probe {runs}/{runs}")


def test_cli_fresh_process_writes_the_readout(tmp_path):
    root = Path(__file__).resolve().parents[2]
    xyz, uv = _square(1.0, 0.5)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(root / "src"), env.get("PYTHONPATH", "")])
    runs = 0
    for index, map_px in enumerate((2048, 4096, 2048, 4096)):
        work = tmp_path / f"proc{index}"
        work.mkdir()
        src, out, report = work / "in.json", work / "out.json", work / "report.json"
        body = json.dumps(_payload("VPM", map_px, xyz, uv)).encode("utf-8")
        src.write_bytes(body)
        proc = subprocess.run(
            [sys.executable, "-m", "dt_ai.ops.texel_density_readout",
             "--input", str(src), "--output", str(out), "--report", str(report)],
            cwd=str(root),
            env=env,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == (0 if map_px == 2048 else 1), proc.stderr
        assert src.read_bytes() == body
        written = json.loads(out.read_text(encoding="utf-8"))
        assert written["faces"][0]["px_per_m"] == pytest.approx(map_px * 0.5)
        assert written["faces"][0]["px_per_m"] == (1024 if map_px == 2048 else 2048)
        assert list(work.glob("*.partial")) == []
        summary = json.loads(report.read_text(encoding="utf-8"))
        assert summary["input_sha256"] == hashlib.sha256(body).hexdigest()
        assert summary["passed"] is (map_px == 2048)
        runs += 1
    print(f"fresh-process probe {runs}/{runs}")


def test_cli_repeat_does_not_overwrite(tmp_path):
    src, out, report = tmp_path / "in.json", tmp_path / "out.json", tmp_path / "report.json"
    xyz, uv = _square(1.0, 0.5)
    raw = json.dumps(_payload("VPM", 2048, xyz, uv)).encode("utf-8")
    src.write_bytes(raw)
    assert _mod().main(["--input", str(src), "--output", str(out), "--report", str(report)]) == 0
    first_out, first_report = out.read_bytes(), report.read_bytes()
    repeats = 0
    for _ in range(5):
        code = _mod().main(["--input", str(src), "--output", str(out), "--report", str(report)])
        assert code != 0
        assert out.read_bytes() == first_out
        assert report.read_bytes() == first_report
        assert src.read_bytes() == raw
        assert list(tmp_path.glob("*.partial")) == []
        repeats += 1
    print(f"repeat publish probe {repeats}/{repeats}")


@pytest.mark.parametrize("offset", [0.0, 1.0, 1e3, 1e5, 1e7])
@pytest.mark.parametrize("start", [0, 1, 2, 3])
@pytest.mark.parametrize("reverse", [False, True])
def test_uv_area_is_origin_independent_for_far_offsets(offset, start, reverse):
    """Round 3 P1: unit world square, UV side .84 at (1e7,1e7) must be ~0.7056 area / ~1720.32 px/m / fail."""
    xyz, _ = _square(1.0, 1.0)
    base = [[offset, offset], [offset + 0.84, offset], [offset + 0.84, offset + 0.84], [offset, offset + 0.84]]
    uv = base[start:] + base[:start]
    pts = list(zip(xyz[start:] + xyz[:start], uv))
    if reverse:
        pts = pts[::-1]
    xs, uvs = [p[0] for p in pts], [p[1] for p in pts]
    value, uv_area, world = _mod()._measure(xs, uvs, 2048)
    assert uv_area == pytest.approx(0.7056, rel=1e-6)
    assert world == pytest.approx(1.0)
    assert value == pytest.approx(1720.32, rel=1e-6)


def test_far_offset_uv_square_fails_vpm_band_in_a_fresh_cli_process(tmp_path):
    xyz, _ = _square(1.0, 1.0)
    o = 1e7
    uv = [[o, o], [o + 0.84, o], [o + 0.84, o + 0.84], [o, o + 0.84]]
    src, out, rep = tmp_path / "in.json", tmp_path / "out.json", tmp_path / "rep.json"
    src.write_text(json.dumps(_payload("VPM", 2048, xyz, uv)), encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "dt_ai.ops.texel_density_readout", "--input", str(src),
                           "--output", str(out), "--report", str(rep)], capture_output=True, text=True)
    assert done.returncode == 1, done.stdout + done.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["faces"][0]["px_per_m"] == pytest.approx(1720.32, rel=1e-6)
