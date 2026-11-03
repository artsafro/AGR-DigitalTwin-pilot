"""new-case: research #769: rectified slide overlay (jobs/TEC26-OKS/scripts/slide_overlay.py) - synthetic probes run everywhere,
the real AC08 slide 49 / pilot-v010 renders only where they are on this PC. Nothing here is a gate."""
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "jobs/TEC26-OKS/scripts"
sys.path.insert(0, str(SCRIPTS))

import slide_overlay as so  # noqa: E402

AC08 = ROOT / "jobs/TEC26-OKS/AC08"
SPEC_P, SHEET_P = AC08 / "vpm_textures.json", AC08 / "sheet-facades.json"
SPEC = json.loads(SPEC_P.read_text(encoding="utf-8"))
SHEET = json.loads(SHEET_P.read_text(encoding="utf-8"))
PILOT = Path("C:/x/tec26-oks/AC08/pilot-v010")
RENDERS, VRB_P = PILOT / "renders", PILOT / "readback/vpm.readback.json"
SLIDE = Path(SPEC["presentation"]["image"])
needs_real = pytest.mark.skipif(not (SLIDE.exists() and VRB_P.exists() and (RENDERS / "renders.json").exists()),
                                reason="slide 49 / pilot-v010 renders not on this PC")
CLI = [sys.executable, str(SCRIPTS / "slide_overlay.py"), str(SPEC_P), str(SHEET_P), str(RENDERS), str(VRB_P)]


# ---------------------------------------------------------------- homography ---------------------------------------
def test_homography_recovers_random_projective_maps():
    """Probe: 300 seeded random homographies (perspective terms up to 1e-3/px) map 4 random corners; the DLT fit
    back-projects them within 1e-6 px and reproduces the map on 50 other points."""
    rng = np.random.default_rng(769)
    worst = 0.0
    for _ in range(300):
        H = np.eye(3) + rng.normal(0, 0.2, (3, 3))
        H[2, :2] = rng.uniform(-1e-3, 1e-3, 2)
        H[2, 2] = 1.0
        src = np.array([[0, 0], [400, 0], [400, 150], [0, 150]], float) + rng.uniform(-20, 20, (4, 2))
        dst = so.apply_h(H, src)
        Hf = so.homography(src, dst)
        pts = rng.uniform(0, 400, (50, 2))
        worst = max(worst, np.abs(so.apply_h(Hf, src) - dst).max(), np.abs(so.apply_h(Hf, pts) - so.apply_h(H, pts)).max())
    assert worst < 1e-6, worst


@pytest.mark.parametrize("src,dst,match", [
    ([[0, 0], [1, 0], [1, 1]], [[0, 0], [1, 0], [1, 1]], ">= 4"),
    ([[0, 0], [1, 0], [1, 1], [np.nan, 1]], [[0, 0], [1, 0], [1, 1], [0, 1]], "non-finite"),
    ([[0, 0], [1, 0], [1, 1], [0, 1]], [[0, 0], [1, 0], [np.inf, 1], [0, 1]], "non-finite"),
    ([[0, 0], [1, 0], [2, 0], [0, 1]], [[0, 0], [1, 0], [1, 1], [0, 1]], "collinear"),
    ([[0, 0], [0, 0], [0, 0], [0, 0]], [[0, 0], [1, 0], [1, 1], [0, 1]], "collinear|coincide"),
    ([], [], ">= 4"),
])
def test_homography_fail_closed(src, dst, match):
    with pytest.raises(ValueError, match=match):
        so.homography(np.asarray(src, float).reshape(-1, 2), np.asarray(dst, float).reshape(-1, 2))


# ---------------------------------------------------------------- verdict -------------------------------------------
@pytest.mark.parametrize("offs,ok", [
    ({"a": 2.0, "b": -2.0}, True),                 # exactly at the issue's "<= 2 px": pass
    ({"a": 2.0 + 1e-9}, False), ({"a": -2.0 - 1e-9}, False),
    ({"a": float("nan")}, False), ({"a": float("inf")}, False), ({}, False),
    ({"a": 0.0, "b": 1.9, "c": float("nan")}, False),
])
def test_verdict_threshold_and_fail_closed(offs, ok):
    assert so.verdict(offs, 2.0) is ok


# ---------------------------------------------------------------- measurement on synthetic rectified images ---------
def _synthetic_rect(field, ribs=30, pxm=200.0, body=(-3.0294, 3.0294, -0.0408, 2.5502), outline=True,
                    blue=(40, 110, 180), line=(20, 40, 60)):
    """SYNTHETIC rectified facade: blue body, field outline lines and evenly spaced joint lines drawn with exact
    area coverage (sub-pixel), white outside."""
    fr = so.frame(body, pxm)
    u = fr["u0"] + (np.arange(fr["w"]) + 0.5) / pxm
    z = fr["z_top"] - (np.arange(fr["h"]) + 0.5) / pxm
    img = np.full((fr["h"], fr["w"], 3), 255.0)
    inb = ((z >= body[2]) & (z <= body[3]))[:, None] & ((u >= body[0]) & (u <= body[1]))[None, :]
    img[inb] = blue
    w = 1.0 / pxm                                                   # 1 px wide lines

    def cover(c, x):
        return np.clip(np.minimum(x + 0.5 / pxm, c + w / 2) - np.maximum(x - 0.5 / pxm, c - w / 2), 0, None) * pxm

    lo, hi, zb, zt = field
    zin = ((z >= zb) & (z <= zt))[:, None]
    uin = ((u >= lo) & (u <= hi))[None, :]
    xs = [lo, hi] if outline else []
    xs += [lo + k * (hi - lo) / ribs for k in range(1, ribs)]
    au = sum(cover(c, u) for c in xs) if xs else np.zeros_like(u)          # lines never overlap: one coverage row
    az = (cover(zb, z) + cover(zt, z)) if outline else np.zeros_like(z)
    a = np.clip(au[None, :] * zin + az[:, None] * uin, 0, 1)[..., None]
    return img * (1 - a) + np.asarray(line, float) * a, fr, body


def test_measure_is_subpixel_on_synthetic_lines():
    """Probe: 40 seeded field layouts (outline anywhere 0.06-0.14 m inside the body); measured outline positions are
    within 0.05 px of the drawn ones, joints counted = ribs - 1."""
    rng = np.random.default_rng(1)
    worst = 0.0
    for _ in range(40):
        f = (-3.0294 + rng.uniform(0.06, 0.14), 3.0294 - rng.uniform(0.06, 0.14),
             -0.0408 + rng.uniform(0.11, 0.19), 2.5502 - rng.uniform(0.11, 0.19))
        img, fr, body = _synthetic_rect(f)
        m = so.measure(img, fr, body, so.RENDER_DARK)
        got = (m["field_left"], m["field_right"], m["field_bottom"], m["field_top"])
        worst = max(worst, max(abs(a - b) * 200 for a, b in zip(got, f)))
        assert len(m["joints_u"]) == 29
    assert worst < 0.05, worst


def test_measure_planted_shift_sweep():
    """Probe: a field outline shifted by d (0..0.1 m, 21 steps) moves the measured edge by 200 d px (+-0.05) and the
    verdict flips exactly where |200 d| exceeds 2 px."""
    base = (-2.93, 2.93, 0.113, 2.399)
    img0, fr, body = _synthetic_rect(base)
    m0 = so.measure(img0, fr, body, so.RENDER_DARK)
    for d in np.linspace(0, 0.1, 21):
        img, _, _ = _synthetic_rect((base[0], base[1], base[2], base[3] - d))
        m = so.measure(img, fr, body, so.RENDER_DARK)
        off = {e: (m0[e] - m[e]) * 200 for e in so.EDGES}
        assert abs(off["field_top"] - 200 * d) < 0.05, (d, off)
        assert so.verdict(off, 2.0) is bool(200 * d <= 2.0 + 1e-6), (d, off)


def test_measure_fail_closed():
    """No field outline, an empty frame and a NaN image refuse instead of returning edges."""
    img, fr, body = _synthetic_rect((-2.93, 2.93, 0.113, 2.399), ribs=1, outline=False)
    with pytest.raises(ValueError, match="field outline"):
        so.measure(img, fr, body, so.RENDER_DARK)
    with pytest.raises(ValueError, match="empty|non-finite|field outline"):
        so.measure(np.full_like(img, np.nan), fr, body, so.RENDER_DARK)
    with pytest.raises(ValueError, match="empty|non-finite"):
        so.dark_lines(np.array([]), np.array([]))


# ---------------------------------------------------------------- CLI refusals (fresh process) ---------------------
def _cli(out, *extra):
    return subprocess.run(CLI + [str(out), *extra], capture_output=True, text=True, timeout=120)


def test_cli_refuses_existing_alias_and_bad_args(tmp_path):
    existing = tmp_path / "exists"
    existing.mkdir()
    (existing / "keep.txt").write_text("x")
    r = _cli(existing)
    assert r.returncode == 2 and "refusing to overwrite" in r.stderr
    assert [p.name for p in existing.iterdir()] == ["keep.txt"]
    r = subprocess.run(CLI[:6] + [str(AC08)], capture_output=True, text=True, timeout=120)  # out = spec's folder
    assert r.returncode == 2 and "aliases input" in r.stderr
    r = subprocess.run(CLI[:6] + [str(SPEC_P)], capture_output=True, text=True, timeout=120)  # out = the spec file
    assert r.returncode == 2 and "aliases input" in r.stderr
    for bad in (["--plant-u", "nan"], ["--plant-top-band", "inf"], ["--register", "both"], ["--facade", "Z-9"],
                ["--px-per-m", "0"], ["--tol-px", "nan"]):
        out = tmp_path / ("o" + str(abs(hash(tuple(bad)))))
        r = _cli(out, *bad)
        assert r.returncode == 2, (bad, r.stdout, r.stderr)
        assert not out.exists() and not Path(str(out) + ".partial").exists(), bad
    r = subprocess.run(CLI[:4], capture_output=True, text=True, timeout=60)
    assert r.returncode == 2


# ---------------------------------------------------------------- real AC08 slide 49 vs pilot-v010 VPM ---------------
@pytest.fixture(scope="module")
def real():
    from PIL import Image
    return (np.asarray(Image.open(SLIDE).convert("RGB")), json.loads(VRB_P.read_text(encoding="utf-8")))


def _run(real, **kw):
    slide, vrb = real
    return so.run(SPEC, SHEET, str(RENDERS), vrb, slide=slide, **kw)[0]


@pytest.fixture(scope="module")
def base(real):
    return _run(real)


@needs_real
def test_real_facade_1_2_overlay_passes_and_ribs_agree(base):
    """Acceptance: slide 49 facade 1-2 rectified at 200 px/m onto the VPM facade plane; every band edge within 2 px;
    29 joints by joint_count on the rectified slide = on the VPM render = contract ribs - 1."""
    r = base
    assert r["px_per_m"] == 200.0 and r["frame_px"] == [round((r["model_body_uz_m"][1] - r["model_body_uz_m"][0]
                                                               + 0.6) * 200), 660]
    assert r["corner_backprojection_max_m"] < 1e-9
    assert r["pass"] and r["max_band_edge_offset_px"] <= 2.0, r["band_edge_offset_px"]
    assert r["rib_counts"]["slide"]["joints_found"] == r["rib_counts"]["vpm"]["joints_found"] == 29
    assert r["ribs_agree"] and r["rib_counts"]["vpm"]["ok"]


@needs_real
@pytest.mark.parametrize("kw,edge", [({"plant_u": 0.1}, "field_right"), ({"plant_u": -0.1}, "field_left"),
                                     ({"plant_top_band": 0.1}, "field_top")])
def test_real_planted_0_1_m_shift_fails(real, base, kw, edge):
    """A planted 0.1 m shift (whole facade along u, or the top band 0.1 m taller) fails; the shifted edge moves by
    20 px (+-1) from its unplanted offset."""
    b = base["band_edge_offset_px"]
    key = {"plant_u": "plant_u", "plant_top_band": "plant_band"}[next(iter(kw))]
    r = _run(real, **{key: next(iter(kw.values()))})
    assert not r["pass"]
    assert abs(abs(r["band_edge_offset_px"][edge] - b[edge]) - 20) <= 1, (edge, b, r["band_edge_offset_px"])


@needs_real
def test_real_datum_registration_shows_the_model_offset(real, base):
    """Registered on the drawing's own body at +-0.000 instead of the model body, both horizontal bands move by the
    model's 40.8 mm (8.2 px) body offset below +-0.000 and the overlay fails - position, not count."""
    m, d = base, _run(real, register="datum")
    assert not d["pass"]
    for e in ("field_top", "field_bottom"):
        assert abs((d["band_edge_offset_px"][e] - m["band_edge_offset_px"][e]) - 0.0408 * 200) < 1.0, (e, d, m)


@needs_real
def test_real_cli_headless_under_60_s(tmp_path):
    """Fresh-process CLI on the real inputs: exit 0, overlay.json + 3 PNGs, wall time <= 60 s, no .partial left."""
    out = tmp_path / "ov"
    t = time.perf_counter()
    r = _cli(out)
    wall = time.perf_counter() - t
    assert r.returncode == 0, r.stderr
    assert wall <= 60, wall
    rep = json.loads((out / "overlay.json").read_text(encoding="utf-8"))
    assert rep["pass"] and rep["seconds"] <= 60
    assert rep["inputs_sha256"]["slide"] == SPEC["presentation"]["image_sha256"]
    assert sorted(p.name for p in out.iterdir()) == ["overlay.json", "overlay.png", "slide_rect.png", "vpm_rect.png"]
    assert not Path(str(out) + ".partial").exists()


@needs_real
@pytest.mark.parametrize("offset,expected", [
    (2.0, True), (-2.0, True),
    (2.0 - 1e-9, True), (-2.0 + 1e-9, True),
    (2.0 + 1e-9, False), (-2.0 - 1e-9, False),
])
def test_run_report_threshold_uses_unrounded_offsets(tmp_path, monkeypatch, offset, expected):
    """Deterministic measurement injection through real run(), JSON publication and main's exit status.

    Only the top-edge measurement is injected (SYNTHETIC); all other measurements, rib counts,
    rectification, input hashes and output publication use the real assets. Zero is the injected
    VPM datum to avoid subtractive cancellation at the exact inclusive boundary.
    """
    measure = so.measure

    def measured_top(rect, fr, body, dark):
        result = measure(rect, fr, body, dark)
        result["field_top"] = offset / 200.0 if dark == so.SLIDE_DARK else 0.0
        return result

    monkeypatch.setattr(so, "measure", measured_top)
    out = tmp_path / "threshold"
    code = so.main(CLI[2:] + [str(out)])
    rep = json.loads((out / "overlay.json").read_text(encoding="utf-8"))
    assert rep["pass"] is expected, rep["band_edge_offset_px"]
    assert code == (0 if expected else 1)
    assert rep["band_edge_offset_px"]["field_top"] == pytest.approx(offset, abs=1e-13)
    assert rep["max_band_edge_offset_px"] == pytest.approx(abs(offset), abs=1e-13)
    assert rep["ribs_agree"] and rep["rib_counts"]["vpm"]["joints_found"] == 29
    assert not Path(str(out) + ".partial").exists()


@needs_real
def test_real_cli_just_over_threshold_fails(tmp_path):
    """R1 real false-clean witness: 2.0001409617482757 px must not round into a pass."""
    out = tmp_path / "just-over"
    r = _cli(out, "--plant-u", "0.00929457717743987")
    rep = json.loads((out / "overlay.json").read_text(encoding="utf-8"))
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert not rep["pass"]
    assert 2.0 < rep["band_edge_offset_px"]["field_left"] < 2.0005
    assert rep["max_band_edge_offset_px"] > 2.0
    assert not Path(str(out) + ".partial").exists()


@needs_real
def test_cli_refuses_a_leftover_partial_and_keeps_it(tmp_path):
    """Hostile self-review: a stale `<out>.partial` from an earlier crash is a refusal (exit 2), never exit 1 (which
    reads as a measured overlay fail); the stale folder and its content are left untouched, `<out>` is not created."""
    out = tmp_path / "ov"
    part = Path(str(out) + ".partial")
    part.mkdir()
    (part / "stale.txt").write_text("x")
    r = _cli(out)
    assert r.returncode == 2 and "partial" in r.stderr, (r.returncode, r.stderr[-300:])
    assert not out.exists() and [p.name for p in part.iterdir()] == ["stale.txt"]
