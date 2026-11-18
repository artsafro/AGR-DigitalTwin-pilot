"""Round 5 review r1 of the #1619 body training polygon (PR #1660 P1): the jamb UV keeps UV/geo = 1 at any facade
angle (module_build.jamb_uv) and the read-back reports per-face UV/geo ratios per class with defects outside
[0.99, 1.01] (readback_openings.edge_uv_ratios / main).

Pattern: n/a | new-case: tests of the #1619 jamb UV and the UV/geo read-back.
"""

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "jobs" / "garibaldi22" / "body-training-1619" / "hooks"
RESEARCH = ROOT / "docs" / "research" / "body-training-1619"
TEX = 3.0


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build_mod = _load(HOOKS / "module_build.py", "module_build_1619r6")  # pure helpers only
rb_mod = _load(RESEARCH / "readback_openings.py", "readback_openings_1619r6")


def _jambs(ang, r, turn=0.0):
    """Both jamb quads of a window run along `ang` (optionally turning by `turn` at its middle point)."""
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    c2, s2 = math.cos(math.radians(ang + turn)), math.sin(math.radians(ang + turn))
    a = (12.0, -7.0)
    b = (a[0] + 1.1 * c, a[1] + 1.1 * s)
    run = [a, b, (b[0] + 0.9 * c2, b[1] + 0.9 * s2)]
    inner = build_mod.inner_offset(run, r)
    z0, z1 = 0.9, 2.4
    out = []
    for o, i in ((run[0], inner[0]), (run[-1], inner[-1])):
        quad = [(o[0], o[1], z0), (i[0], i[1], z0), (i[0], i[1], z1), (o[0], o[1], z1)]
        out.append((quad, [build_mod.jamb_uv(p, o, i, TEX) for p in quad]))
    return out


def _uv_area(uv):
    return 0.5 * abs(sum(uv[k][0] * uv[(k + 1) % 4][1] - uv[(k + 1) % 4][0] * uv[k][1] for k in range(4)))


@pytest.mark.parametrize("r", [0.10, 0.15])
@pytest.mark.parametrize("ang", [0, 39, 45, 90, 135, 225, 300])
@pytest.mark.parametrize("turn", [0.0, 60.0])
def test_jamb_uv_span_equals_depth_at_any_facade_angle(ang, r, turn):
    for quad, uv in _jambs(ang, r, turn):
        span = max(u for u, _ in uv) - min(u for u, _ in uv)
        assert span / (r / TEX) == pytest.approx(1.0, abs=1e-6)
        assert (max(v for _, v in uv) - min(v for _, v in uv)) == pytest.approx(1.5 / TEX, abs=1e-9)
        assert _uv_area(uv) > 0.5 * (r / TEX) * (1.5 / TEX)  # no degenerate UV
        rs = rb_mod.edge_uv_ratios(quad, uv, TEX)
        assert all(abs(x - 1.0) < 1e-6 for x in rs) and not rb_mod.uv_defect(rs)


@pytest.mark.parametrize("ang", [39, 45, 135])
def test_old_xy_sum_uv_is_flagged_by_the_readback(ang):
    """Witness of the P1: u = (x + y) / T squeezes (or collapses at 45 deg) the jamb; the read-back must flag it."""
    for quad, _ in _jambs(ang, 0.15):
        old = [((p[0] + p[1]) / TEX, p[2] / TEX) for p in quad]
        assert rb_mod.uv_defect(rb_mod.edge_uv_ratios(quad, old, TEX))


@pytest.mark.parametrize("co,outer,inner,tex,msg", [
    ((0, 0, 0), (0, 0), (0.1, 0), 0.0, "tex_m > 0"),
    ((0, 0, 0), (0, 0), (0.1, 0), -3.0, "tex_m > 0"),
    ((0, 0, 0), (0, 0), (0.1, 0), float("nan"), "finite"),
    ((float("nan"), 0, 0), (0, 0), (0.1, 0), 3.0, "finite"),
    ((0, 0, float("inf")), (0, 0), (0.1, 0), 3.0, "finite"),
    ((0, 0, 0), (0, 0), (float("nan"), 0), 3.0, "finite"),
    ((0, 0, 0), (1, 1), (1, 1), 3.0, "zero-length"),
])
def test_jamb_uv_fails_closed(co, outer, inner, tex, msg):
    with pytest.raises(ValueError, match=msg):
        build_mod.jamb_uv(co, outer, inner, tex)


SQ = [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]


@pytest.mark.parametrize("P,UV,tex,msg", [
    (SQ, [(0, 0), (1, 0), (1, 1)], 1.0, "does not match"),
    (SQ, [], 1.0, "does not match"),
    (SQ, [(0, 0), (1, 0), (1, float("nan")), (0, 1)], 1.0, "non-finite"),
    ([(0, 0, 0), (0, 0, 0), (1, 0, 1), (0, 0, 1)], [(0, 0), (1, 0), (1, 1), (0, 1)], 1.0, "zero-length"),
    (SQ, [(0, 0), (1, 0), (1, 1), (0, 1)], 0.0, "tex_m"),
    (SQ, [(0, 0), (1, 0), (1, 1), (0, 1)], float("inf"), "tex_m"),
])
def test_edge_uv_ratios_fails_closed(P, UV, tex, msg):
    with pytest.raises(ValueError, match=msg):
        rb_mod.edge_uv_ratios(P, UV, tex)


@pytest.mark.parametrize("ratios,defect", [
    ([1.0] * 4, False), ([0.99, 1.0, 1.01, 1.0], False), ([0.98999, 1.0, 1.0, 1.0], True),
    ([1.0, 1.01001, 1.0, 1.0], True), ([1.0, float("nan"), 1.0, 1.0], True), ([0.0] * 4, True),
])
def test_uv_defect_threshold_is_inclusive_and_nan_fails(ratios, defect):
    assert rb_mod.uv_defect(ratios) is defect


def _dump(tmp_path, jamb_squeeze):
    """Synthetic (not object data): one wall quad on the y=0 facade of a 10 m square + one jamb quad 0.15 m deep."""
    V = np.array([(2, 0, 0), (4, 0, 0), (4, 0, 3), (2, 0, 3),
                  (5, 0, 0), (5, 0.15, 0), (5, 0.15, 3), (5, 0, 3)], dtype=float)
    uv = [(2 / 3, 0), (4 / 3, 0), (4 / 3, 1), (2 / 3, 1),
          (0, 0), (0.05 * jamb_squeeze, 0), (0.05 * jamb_squeeze, 1), (0, 1)]
    p = tmp_path / "dump.npz"
    np.savez(p, verts=V, fn=np.array([4, 4]), fi=np.arange(8), mats=np.array([0, 0]), names=np.array(["WALL_DARK"]),
             uvn=np.array([4, 4]), uvf=np.array(uv, dtype=float))
    fl = tmp_path / "floor.json"
    fl.write_text(json.dumps({"rings": [{"xy": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
                              "windows": [[0, 4.0, 6.0, 0, 1, 0.15]], "floors": 1, "wall_tile_m": 3.0}))
    return str(p), str(fl)


def test_readback_reports_uv_geo_per_class_and_fails_on_a_squeezed_jamb(tmp_path):
    d, fl = _dump(tmp_path, 1.0)
    out = tmp_path / "ok.json"
    assert rb_mod.main([d, fl, str(out)]) == 0
    rep = json.loads(out.read_text())
    assert rep["uv_geo"]["wall"] == {"faces": 1, "min": 1.0, "max": 1.0, "defects": 0}
    assert rep["uv_geo"]["jamb"] == {"faces": 1, "min": 1.0, "max": 1.0, "defects": 0}
    assert rep["uv_geo_defects"] == 0
    (tmp_path / "bad").mkdir()
    d2, fl2 = _dump(tmp_path / "bad", 0.15)
    bad = tmp_path / "bad.json"
    assert rb_mod.main([d2, fl2, str(bad)]) == 1
    rep = json.loads(bad.read_text())
    assert rep["uv_geo"]["jamb"]["defects"] == 1 and rep["uv_geo"]["jamb"]["min"] == pytest.approx(0.15)
    assert rep["uv_geo"]["wall"]["defects"] == 0 and rep["uv_geo_defects"] == 1


def test_readback_counts_a_face_without_uv_as_a_defect(tmp_path):
    d, fl = _dump(tmp_path, 1.0)
    z = dict(np.load(d))
    z["uvn"], z["uvf"] = np.array([4, 0]), z["uvf"][:4]
    np.savez(d, **z)
    out = tmp_path / "o.json"
    assert rb_mod.main([d, fl, str(out)]) == 1
    assert json.loads(out.read_text())["uv_missing_or_bad_faces"] == 1


def test_readback_refuses_an_existing_output_and_leaves_inputs(tmp_path):
    d, fl = _dump(tmp_path, 1.0)
    before = Path(fl).read_bytes()
    with pytest.raises(FileExistsError):
        rb_mod.main([d, fl, fl])
    assert Path(fl).read_bytes() == before
