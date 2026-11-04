"""new-case: pure helpers for the AC08 DreamSim advisory experiment.

Shift, planted defects, and fail-closed checks. DreamSim weights are not loaded.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "experiments"))

import dreamsim_ac08 as ds  # noqa: E402


def _rgb(h=20, w=30, fill=0.2):
    img = np.full((h, w, 3), fill, dtype=np.float64)
    if h > 5 and w > 10:
        img[5, 10] = (0.1, 0.8, 0.3)
    return img


def test_shift_moves_content_and_fills_vacated_edge_white():
    src = _rgb()
    out = ds.shift_pixels(src, 2, -1)
    assert out.shape == src.shape
    assert np.allclose(out[4, 12], (0.1, 0.8, 0.3))
    assert np.allclose(out[:, :2], 1.0)
    assert np.allclose(out[-1, :], 1.0)
    assert np.allclose(src[5, 10], (0.1, 0.8, 0.3))


@pytest.mark.parametrize("dx", [1, 2, 3])
def test_shift_one_to_three_pixels_keeps_shape(dx):
    src = _rgb()
    out = ds.shift_pixels(src, dx, 0)
    assert out.shape == src.shape
    assert np.allclose(out[5, 10 + dx], src[5, 10])
    assert np.allclose(out[:, :dx], 1.0)


def test_shifted_band_moves_only_the_band_by_0_1_m():
    src = _rgb(h=40, w=80)
    src[:, :] = 0.4
    src[20, 10] = (0.0, 0.0, 1.0)
    src[5, 10] = (1.0, 0.0, 0.0)
    out = ds.plant_shifted_band(src, px_per_m=200, metres=0.1, band_frac=(0.4, 0.7))
    assert int(round(0.1 * 200)) == 20
    assert np.allclose(out[20, 30], (0.0, 0.0, 1.0))
    assert np.allclose(out[5, 10], (1.0, 0.0, 0.0))
    assert np.allclose(out[20, :20], 1.0)
    assert np.allclose(src[20, 10], (0.0, 0.0, 1.0))


def test_wrong_colour_zone_overwrites_only_that_rectangle():
    src = _rgb(h=20, w=20, fill=0.2)
    out = ds.plant_wrong_colour(src, zone_frac=(0.25, 0.75, 0.25, 0.75), colour=(0.9, 0.1, 0.1))
    assert np.allclose(out[10, 10], (0.9, 0.1, 0.1))
    assert np.allclose(out[0, 0], 0.2)
    assert np.allclose(src[10, 10], 0.2)


def test_missing_rib_replaces_the_dark_column_with_the_neighbour():
    src = np.full((16, 24, 3), 0.7, dtype=np.float64)
    src[:, 12] = 0.05
    out = ds.plant_missing_rib(src)
    assert out[:, 12, 0].mean() > 0.5
    assert np.allclose(out[:, 11], src[:, 11])
    assert np.allclose(src[:, 12], 0.05)


def test_fail_closed_empty_nan_inf_and_shape_mismatch():
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.zeros((0, 4, 3)))
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.array([]))
    bad = _rgb()
    bad[0, 0, 0] = np.nan
    with pytest.raises(ds.InputError):
        ds.require_rgb(bad)
    bad = _rgb()
    bad[0, 0, 1] = np.inf
    with pytest.raises(ds.InputError):
        ds.require_rgb(bad)
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.zeros((4, 4)))
    with pytest.raises(ds.InputError):
        ds.require_rgb(np.zeros((4, 4, 4)))
    with pytest.raises(ds.InputError):
        ds.require_same_shape(_rgb(h=8, w=8), _rgb(h=8, w=9))


def test_output_path_equal_to_input_exits_nonzero_and_writes_nothing(tmp_path: Path):
    src = tmp_path / "in.png"
    Image.fromarray(np.full((6, 6, 3), 40, dtype=np.uint8)).save(src)
    before = src.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    with pytest.raises(SystemExit) as exc:
        ds.main(["write-array", "--input", str(src), "--output", str(src)])
    assert exc.value.code not in (0, None)
    assert src.read_bytes() == before
    assert hashlib.sha256(src.read_bytes()).hexdigest() == digest
    assert list(tmp_path.iterdir()) == [src]


def test_partial_and_unsupported_files_exit_nonzero(tmp_path: Path):
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    out = tmp_path / "out.json"
    with pytest.raises(SystemExit) as exc:
        ds.main(["write-array", "--input", str(empty), "--output", str(out)])
    assert exc.value.code not in (0, None)
    assert not out.exists()
    text = tmp_path / "note.txt"
    text.write_text("nope", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ds.main(["write-array", "--input", str(text), "--output", str(out)])
    assert exc.value.code not in (0, None)
    assert not out.exists()
    assert text.read_text(encoding="utf-8") == "nope"


def _png(path: Path) -> None:
    Image.fromarray(np.full((8, 8, 3), 120, np.uint8), "RGB").save(path, format="PNG")


def test_write_array_input_named_like_old_temp_is_kept(tmp_path: Path):
    src = tmp_path / "result.json.tmp"
    _png(src)
    before = src.read_bytes()
    assert ds.main(["write-array", "--input", str(src), "--output", str(tmp_path / "result.json")]) == 0
    assert src.read_bytes() == before
    assert (tmp_path / "result.json").exists()
    assert not list(tmp_path.glob("*.partial"))


def test_write_array_keeps_unrelated_temp_sentinel(tmp_path: Path):
    src = tmp_path / "in.png"
    _png(src)
    sentinel = tmp_path / "result.json.tmp"
    sentinel.write_text("keep")
    assert ds.main(["write-array", "--input", str(src), "--output", str(tmp_path / "result.json")]) == 0
    assert sentinel.read_text() == "keep"


def test_results_equal_csv_exits_nonzero_and_writes_nothing(tmp_path: Path):
    same = tmp_path / "x.json"
    with pytest.raises(SystemExit) as exc:
        ds.run(same, same, tmp_path / "w", tmp_path / "c")
    assert exc.value.code != 0
    assert not same.exists()


def _stub_run(monkeypatch, tmp_path, fail_after):
    img = np.full((8, 8, 3), 0.5)
    rows = [{"pilot": "v010", "tag": "vpm", "view": "north", "slide_crop": "s", "render_crop": "r"} for _ in range(2)]
    monkeypatch.setattr(ds, "_scripts", lambda: (None, None, None))
    monkeypatch.setattr(ds, "_referenced_paths", lambda: [])
    monkeypatch.setattr(ds, "_crop_destinations", lambda work: [])
    monkeypatch.setattr(ds, "measure_pilot", lambda pilot, work: [dict(r) for r in rows])
    monkeypatch.setattr(ds, "control_rows", lambda r, mm: [{"name": "shift_1", "ssim": 1.0, "dreamsim": None, "defect_crop_joints": 1, "base_crop_joints": 1}, {"name": "band", "ssim": 0.5, "dreamsim": None, "defect_crop_joints": 2, "base_crop_joints": 1}])
    monkeypatch.setattr(ds, "_controls", lambda base: [("shift_1", base), ("band", base)])
    monkeypatch.setattr(ds, "load_rgb", lambda p: img)
    monkeypatch.setattr(ds, "load_dreamsim", lambda cache: (object(), object(), 0.1, "x"))
    calls = {"n": 0}

    def dist(model, pre, a, b):
        calls["n"] += 1
        if fail_after is not None and calls["n"] > fail_after:
            raise ds.InputError("boom")
        return 0.1, 0.01

    monkeypatch.setattr(ds, "_dreamsim_distance", dist)
    monkeypatch.setattr(ds, "_weight_files", lambda cache: [])
    monkeypatch.setattr(ds, "_write_csv", lambda *a: None)
    return ds.run(tmp_path / "r.json", tmp_path / "r.csv", tmp_path / "w", tmp_path / "c")


@pytest.mark.parametrize("fail_after", [0, 1, 2, 3])
def test_run_nonzero_when_inference_fails_even_after_partial_progress(monkeypatch, tmp_path, fail_after):
    assert _stub_run(monkeypatch, tmp_path, fail_after) == 1


def test_run_zero_when_all_pairs_measured(monkeypatch, tmp_path):
    assert _stub_run(monkeypatch, tmp_path, None) == 0


def _fake_world(monkeypatch, tmp_path):
    """Spec, slide and render PNGs in scratch; the real inventory functions run on them."""
    import json

    slide = tmp_path / "slide.png"
    render = tmp_path / "rend" / "n.png"
    render.parent.mkdir()
    Image.fromarray(np.zeros((4, 4, 3), np.uint8)).save(slide)
    Image.fromarray(np.zeros((4, 4, 3), np.uint8)).save(render)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"presentation": {"image": str(slide)},
                                "facades": {"F1": {"normal": "+y"}}}))
    (tmp_path / "rend" / "renders.json").write_text(json.dumps(
        {t: {"views": {"north": {"png": "n.png"}}} for t in ("vpm", "npm")}))
    monkeypatch.setattr(ds, "SPEC", spec)
    monkeypatch.setattr(ds, "SHEET", spec)
    monkeypatch.setattr(ds, "PILOTS", {"v010": {"renders": tmp_path / "rend", "readback": spec, "panel_udim": None}})
    return slide, render


@pytest.mark.parametrize("which", ["slide", "render", "crop"])
def test_results_or_csv_equal_to_source_or_crop_exits_nonzero_before_writes(monkeypatch, tmp_path, which):
    slide, render = _fake_world(monkeypatch, tmp_path)
    work = tmp_path / "w"
    crop = work / "crops" / "v010" / "north_F1_vpm.png"
    crop.parent.mkdir(parents=True)
    crop.write_bytes(b"crop")
    target = {"slide": slide, "render": render, "crop": crop}[which]
    before = target.read_bytes()
    for as_csv in (False, True):
        res, csv_ = (tmp_path / "o.json", target) if as_csv else (target, tmp_path / "o.csv")
        with pytest.raises(SystemExit) as exc:
            ds.run(res, csv_, work, tmp_path / "c")
        assert exc.value.code != 0
        assert target.read_bytes() == before
        assert not (tmp_path / "o.json").exists() and not (tmp_path / "o.csv").exists()


def test_distinct_outputs_pass_the_guard(monkeypatch, tmp_path):
    _fake_world(monkeypatch, tmp_path)
    monkeypatch.setattr(ds, "_scripts", lambda: (None, None, None))

    def stop(*a, **k):
        raise RuntimeError("guard passed")

    monkeypatch.setattr(ds, "measure_pilot", stop)
    with pytest.raises(RuntimeError, match="guard passed"):
        ds.run(tmp_path / "o.json", tmp_path / "o.csv", tmp_path / "w", tmp_path / "c")


@pytest.mark.parametrize("which", ["slide", "render", "hardlink"])
def test_crop_destination_aliasing_a_source_exits_nonzero_before_any_write(monkeypatch, tmp_path, which):
    import json
    import os

    slide, render = _fake_world(monkeypatch, tmp_path)
    work = tmp_path / "w"
    crop_dir = work / "crops" / "v010"
    crop_dir.mkdir(parents=True)
    if which == "slide":
        crop = crop_dir / "north_F1_slide.png"
        slide.replace(crop)
        spec = json.loads(ds.SPEC.read_text())
        spec["presentation"]["image"] = str(crop)
        ds.SPEC.write_text(json.dumps(spec))
        target = crop
    elif which == "render":
        crop = crop_dir / "north_F1_vpm.png"
        render.replace(crop)
        (render.parent / "renders.json").write_text(json.dumps(
            {t: {"views": {"north": {"png": os.path.relpath(crop, render.parent)}}} for t in ("vpm", "npm")}))
        target = crop
    else:
        crop = crop_dir / "north_F1_npm.png"
        os.link(slide, crop)
        target = slide
    before = target.read_bytes()
    marker = []
    monkeypatch.setattr(ds, "measure_pilot", lambda *a, **k: marker.append(1) or [])
    with pytest.raises(SystemExit) as exc:
        ds.run(tmp_path / "o.json", tmp_path / "o.csv", work, tmp_path / "c")
    assert exc.value.code != 0
    assert not marker
    assert target.read_bytes() == before
    assert not (tmp_path / "o.json").exists() and not (tmp_path / "o.csv").exists()
