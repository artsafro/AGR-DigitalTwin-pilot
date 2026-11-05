"""Parametric MAF bench generator (#790), pure geometry. All inputs here are SYNTHETIC (made-up runs), not site data."""

import importlib.util
import math
import random
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_spec = importlib.util.spec_from_file_location("maf_gen_bench", ROOT / "tools/library/maf_gen_bench.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

from dt_ai.ops.inv_xview_fast import xview_lists  # noqa: E402

MATS = {"seat": 7, "frame": 3}  # synthetic IDs; the real ones come from the approved list v005


def spec(path, **kw):
    base = dict(path=path, depth=0.6, seat_top=0.45, seat_thickness=0.065, post=0.04, post_inset=0.08,
                end_overhang=0.3, max_leg_span=1.2, materials=MATS, synthetic=True)
    base.update(kw)
    return base


STRAIGHT = [[0, 0], [6.0, 0]]
L_RUN = [[0, 2.2], [0, 0], [3.6, 0]]             # outer legs 2.5 x 3.9 at depth 0.6
U_RUN = [[0, 2.6], [0, 0], [5.2, 0], [5.2, 2.6]]  # outer 5.8 x 2.9
SKEW_L = [[0, 0], [3.0, 0], [3.0 + 2.0 * math.cos(1.2), 2.0 * math.sin(1.2)]]


def edge_use(mesh):
    use = Counter()
    for f in mesh["faces"]:
        for a, b in zip(f, f[1:] + f[:1]):
            use[(min(a, b), max(a, b))] += 1
    return use


@pytest.mark.parametrize("path,dims", [(STRAIGHT, (6.0, 0.6)), (L_RUN, (3.9, 2.5)), (U_RUN, (5.8, 2.9))])
def test_dimensions_match_plan_and_height(path, dims):
    mesh = gen.build_bench(spec(path))
    facts = gen.mesh_facts(mesh)
    assert facts["dims_m"][0] == pytest.approx(dims[0], abs=1e-6)
    assert facts["dims_m"][1] == pytest.approx(dims[1], abs=1e-6)
    assert facts["dims_m"][2] == pytest.approx(0.45, abs=1e-9)
    assert facts["min_z"] == pytest.approx(0.0, abs=1e-12)
    assert facts["centre_xy"] == pytest.approx([0.0, 0.0], abs=1e-9)


@pytest.mark.parametrize("path", [STRAIGHT, L_RUN, U_RUN, SKEW_L])
def test_quads_only_closed_manifold_one_mesh(path):
    mesh = gen.build_bench(spec(path))
    assert mesh["faces"] and all(len(f) == 4 for f in mesh["faces"])
    assert set(edge_use(mesh).values()) == {2}, "every edge is shared by exactly two faces (welded inserts)"
    facts = gen.mesh_facts(mesh)
    assert facts["quad_only"] and facts["manifold"] and facts["components"] == 1


@pytest.mark.parametrize("path", [STRAIGHT, L_RUN, U_RUN, SKEW_L])
def test_xview_clean(path):
    mesh = gen.build_bench(spec(path))
    res = xview_lists(mesh["verts"], mesh["faces"])
    assert res["xview_faces"] == () and res["vertices"] == ()


@pytest.mark.parametrize("path", [STRAIGHT, L_RUN, U_RUN, SKEW_L])
def test_outward_normals_positive_volume(path):
    mesh = gen.build_bench(spec(path))
    assert gen.signed_volume(mesh) > 0
    # the seat slab alone is depth x thickness x centreline length; posts add a little
    assert gen.signed_volume(mesh) > 0.6 * 0.065 * 5.0


def test_material_ids_only_from_input_and_every_face_mapped():
    mesh = gen.build_bench(spec(L_RUN))
    assert len(mesh["face_mat"]) == len(mesh["faces"])
    assert set(mesh["face_mat"]) == {7, 3}


def test_legs_reach_ground_and_count():
    mesh = gen.build_bench(spec(STRAIGHT))
    ground = [f for f in mesh["faces"] if all(abs(mesh["verts"][i][2]) < 1e-12 for i in f)]
    # straight 6 m: legs at 0.3 .. 5.7, span <= 1.2 -> 6 leg rows x 2 posts
    assert len(ground) == 12


def test_random_runs_stay_clean():
    rnd = random.Random(790)
    for _ in range(25):
        pts = [[0.0, 0.0]]
        ang = 0.0
        for _k in range(rnd.randint(1, 3)):
            ang += math.radians(rnd.choice([-90, 90, -60, 45]))
            L = rnd.uniform(1.6, 5.0)
            pts.append([pts[-1][0] + L * math.cos(ang), pts[-1][1] + L * math.sin(ang)])
        try:
            mesh = gen.build_bench(spec(pts))
        except ValueError:
            continue  # rejected self-approaching runs are allowed; accepted ones must be clean
        assert set(edge_use(mesh).values()) == {2}
        assert xview_lists(mesh["verts"], mesh["faces"])["xview_faces"] == ()


@pytest.mark.parametrize("bad", [
    dict(path=[]), dict(path=[[0, 0]]), dict(path=[[0, 0], [0, 0]]), dict(path=[[0, 0], [float("nan"), 1]]),
    dict(path=[[0, 0], [float("inf"), 0]]), dict(depth=0), dict(depth=-0.6), dict(seat_top=float("nan")),
    dict(seat_thickness=0.45), dict(post=0), dict(post_inset=0.27), dict(max_leg_span=0),
    dict(materials={"seat": 7}), dict(materials={"seat": 7, "frame": "x"}), dict(materials={"seat": 7, "frame": True}),
    dict(path=[[0, 0], [0.5, 0]]),                       # too short for two legs
    dict(path=[[0, 0], [3, 0], [0.2, 0.1]]),             # turn sharper than the mitre limit
    dict(path=[[0, 0], [4, 0], [4, 2], [0.2, 0.3]]),     # run returns within the seat depth: strips overlap
])
def test_fail_closed(bad):
    with pytest.raises(ValueError):
        gen.build_bench(spec(bad.pop("path", STRAIGHT), **bad))


def test_unknown_spec_key_is_an_error():
    with pytest.raises(ValueError, match="slat"):
        gen.build_bench(spec(STRAIGHT, slat_pitch=0.1))


def test_centreline_from_dwg_style_outline():
    # synthetic L outline drawn like the DWG blocks: end cap, outer edge, end cap, inner edge, closing duplicate
    outline = [[0, 2.5], [0, 0], [3.9, 0], [3.9, 0.6], [0.6, 0.6], [0.6, 2.5], [0, 2.5]]
    c = gen.centreline_from_outline(outline, 0.6)
    exp = [[0.3, 2.5], [0.3, 0.3], [3.9, 0.3]]
    got = [[round(x, 9), round(y, 9)] for x, y in c]
    assert got in (exp, exp[::-1])
    mesh = gen.build_bench(spec(c))
    assert gen.mesh_facts(mesh)["dims_m"][:2] == pytest.approx([3.9, 2.5], abs=1e-6)


def test_centreline_follows_outer_side_when_inner_side_is_skewed():
    # synthetic: like the drawn L blocks, the far cap is skewed (inner side 0.1 m short); outer legs 2.5 x 3.9 rule
    outline = [[0, 2.5], [0, 0], [3.9, 0], [3.8, 0.6], [0.6, 0.6], [0.6, 2.5]]
    c = gen.centreline_from_outline(outline, 0.6)
    dims = gen.mesh_facts(gen.build_bench(spec(c)))["dims_m"]
    assert dims[:2] == pytest.approx([3.9, 2.5], abs=1e-6)


def test_centreline_accepts_open_polyline_with_near_closing_point():
    outline = [[0, 0], [6.25, 0], [6.25, 0.6], [0, 0.6], [0.005, 0.004]]  # drawn open, end 6.4 mm off start (DWG row 5: 6.5 mm)
    dims = gen.mesh_facts(gen.build_bench(spec(gen.centreline_from_outline(outline, 0.6))))["dims_m"]
    assert dims[:2] == pytest.approx([6.25, 0.6], abs=1e-6)


@pytest.mark.parametrize("outline", [
    [[0, 0], [1, 0], [1, 1], [0, 1]],                       # no cap of the seat depth
    [[0, 0], [3, 0], [3, 0.6], [0, 0.6], [float("nan"), 0]],
    [[0, 0], [3, 0], [3, 0.6]],                             # too few points
])
def test_centreline_fail_closed(outline):
    with pytest.raises(ValueError):
        gen.centreline_from_outline(outline, 0.6)


def test_alignment_puts_longest_segment_on_x_and_reports_rotation():
    mesh = gen.build_bench(spec([[0, 0], [0, 5.0], [1.6, 5.0]]))
    assert mesh["plan_rotation_deg"] == pytest.approx(-90.0)
    assert gen.mesh_facts(mesh)["dims_m"][:2] == pytest.approx([5.3, 1.9], abs=1e-6)


BOX = dict(seat_top=0.45, seat_thickness=0.43, post=0.06, post_inset=0.03, end_overhang=0.1, max_leg_span=2.67)


@pytest.mark.parametrize("path,dims", [(STRAIGHT, (6.0, 0.6)), (L_RUN, (3.9, 2.5)), (U_RUN, (5.8, 2.9))])
def test_box_bench_on_low_feet_stays_clean(path, dims):
    """Box-bench parameters (timber body on 2 cm feet, the «Верона» passport form); runs are SYNTHETIC."""
    mesh = gen.build_bench(spec(path, **BOX))
    facts = gen.mesh_facts(mesh)
    assert facts["dims_m"] == pytest.approx([dims[0], dims[1], 0.45], abs=1e-6)
    assert facts["quad_only"] and facts["manifold"] and facts["components"] == 1
    assert xview_lists(mesh["verts"], mesh["faces"])["xview_faces"] == ()
    feet = [v for v in mesh["verts"] if v[2] == 0.0]
    assert feet and all(abs(v[2]) < 1e-12 for v in feet)
    assert gen.signed_volume(mesh) > 0


# --- clad box with modelled seams (Artem 2026-11-03: «Верона» = closed timber box, seams are geometry) ---------------
# SYNTHETIC runs; the parameter values mirror the passport reading (H 0.45, 4 courses, ~0.01 seams) but nothing here
# is site data.
CLAD = dict(depth=0.6, height=0.45, foot_height=0.02, courses=4, seam_width=0.01, seam_depth=0.02, frame_width=0.045,
            top_boards=9, foot_length=0.1, foot_inset=0.03, end_overhang=0.15, max_foot_span=2.67, materials=MATS,
            synthetic=True)


def clad(path, **kw):
    base = dict(CLAD, path=path)
    base.update(kw)
    return base


def _face_z(mesh, f):
    zs = {round(mesh["verts"][i][2], 9) for i in f}
    return zs.pop() if len(zs) == 1 else None


@pytest.mark.parametrize("path,dims", [(STRAIGHT, (6.0, 0.6)), (L_RUN, (3.9, 2.5)), (U_RUN, (5.8, 2.9))])
def test_clad_box_dimensions(path, dims):
    facts = gen.mesh_facts(gen.build_clad_box(clad(path)))
    assert facts["dims_m"] == pytest.approx([dims[0], dims[1], 0.45], abs=1e-6)
    assert facts["min_z"] == pytest.approx(0.0, abs=1e-12)
    assert facts["centre_xy"] == pytest.approx([0.0, 0.0], abs=1e-9)


@pytest.mark.parametrize("path", [STRAIGHT, L_RUN, U_RUN, SKEW_L])
def test_clad_box_quads_manifold_xview_clean(path):
    mesh = gen.build_clad_box(clad(path))
    assert mesh["faces"] and all(len(f) == 4 for f in mesh["faces"])
    assert set(edge_use(mesh).values()) == {2}, "seams are inserts into one welded body: no T-junction, no open edge"
    facts = gen.mesh_facts(mesh)
    assert facts["components"] == 1 and facts["loose_verts"] == 0
    res = xview_lists(mesh["verts"], mesh["faces"])
    assert res["xview_faces"] == () and res["vertices"] == ()
    assert len({tuple(round(c, 9) for c in v) for v in mesh["verts"]}) == len(mesh["verts"])


def _tri_area(a, b, c):
    u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    return math.hypot(u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]) / 2


@pytest.mark.parametrize("path", [STRAIGHT, L_RUN, U_RUN, SKEW_L])
def test_clad_box_quads_are_convex_and_planar(path):
    """The 3-to-1 band fill must not leave a 180-degree corner or a bow-tie: both diagonals give the same area."""
    mesh = gen.build_clad_box(clad(path))
    for f in mesh["faces"]:
        a, b, c, d = (mesh["verts"][i] for i in f)
        s1, s2 = _tri_area(a, b, c) + _tri_area(a, c, d), _tri_area(a, b, d) + _tri_area(b, c, d)
        assert s1 == pytest.approx(s2, rel=1e-9, abs=1e-12)
        assert min(_tri_area(a, b, c), _tri_area(a, c, d), _tri_area(a, b, d), _tri_area(b, c, d)) > 1e-6


@pytest.mark.parametrize("path", [STRAIGHT, L_RUN, U_RUN, SKEW_L])
def test_clad_box_outward_and_volume(path):
    mesh = gen.build_clad_box(clad(path))
    run = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    vol = gen.signed_volume(mesh)
    assert 0.9 * 0.6 * 0.43 * run < vol < 0.6 * 0.45 * (run + 0.6)


def test_clad_box_top_seams_are_geometry_and_stop_at_the_end_frame():
    mesh = gen.build_clad_box(clad(STRAIGHT))
    V = mesh["verts"]
    floors = [f for f in mesh["faces"] if _face_z(mesh, f) == round(0.45 - 0.02, 9)]
    # 9 top boards -> 10 seams (one against each side frame), one straight segment -> 10 seam floors
    assert len(floors) == 10
    for f in floors:
        ys = sorted({round(V[i][1], 9) for i in f})
        assert ys[1] - ys[0] == pytest.approx(0.01, abs=1e-9)          # seam width
        assert max(abs(V[i][0]) for i in f) == pytest.approx(3.0 - 0.045, abs=1e-9)  # stops at the end frame
    # the slat zone between the side frames: 9 boards of equal width
    slats = sorted({round(V[i][1], 9) for f in floors for i in f})
    assert slats[0] == pytest.approx(-0.3 + 0.045) and slats[-1] == pytest.approx(0.3 - 0.045)


def test_clad_box_side_courses_wrap_with_ring_seams():
    mesh = gen.build_clad_box(clad(STRAIGHT))
    V = mesh["verts"]
    # 4 courses of (0.43 - 3 * 0.01) / 4 = 0.1; ring seams at 0.12..0.13, 0.23..0.24, 0.34..0.35, 0.02 deep
    for z in (0.12, 0.13, 0.23, 0.24, 0.34, 0.35):
        ring = [v for v in V if abs(v[2] - z) < 1e-9]
        xs, ys = [v[0] for v in ring], [v[1] for v in ring]
        assert min(xs) == pytest.approx(-3.0) and max(ys) == pytest.approx(0.3)
        assert any(abs(abs(x) - 2.98) < 1e-9 for x in xs) and any(abs(abs(y) - 0.28) < 1e-9 for y in ys)


def test_clad_box_feet_are_steel_plates_let_into_the_bottom():
    mesh = gen.build_clad_box(clad(STRAIGHT))
    V = mesh["verts"]
    ground = [f for f in mesh["faces"] if _face_z(mesh, f) == 0.0]
    # straight 6 m: centres 0.15 .. 5.85, span <= 2.67 -> 4 plates 0.1 x 0.54
    assert len(ground) == 4
    for f in ground:
        xs, ys = [V[i][0] for i in f], [V[i][1] for i in f]
        assert max(xs) - min(xs) == pytest.approx(0.1) and max(ys) - min(ys) == pytest.approx(0.54)
    steel = {i for f, m in zip(mesh["faces"], mesh["face_mat"]) if m == 3 for i in f}
    assert steel and all(V[i][2] <= 0.02 + 1e-12 for i in steel)
    assert set(mesh["face_mat"]) == {7, 3}


def test_clad_box_random_runs_stay_clean():
    rnd = random.Random(7901)
    built = 0
    for _ in range(25):
        pts, ang = [[0.0, 0.0]], 0.0
        for _k in range(rnd.randint(1, 3)):
            ang += math.radians(rnd.choice([-90, 90, -60, 45]))
            L = rnd.uniform(1.6, 5.0)
            pts.append([pts[-1][0] + L * math.cos(ang), pts[-1][1] + L * math.sin(ang)])
        try:
            mesh = gen.build_clad_box(clad(pts))
        except ValueError:
            continue
        built += 1
        assert set(edge_use(mesh).values()) == {2}
        assert xview_lists(mesh["verts"], mesh["faces"])["xview_faces"] == ()
        assert gen.signed_volume(mesh) > 0
    assert built >= 10


@pytest.mark.parametrize("bad", [
    dict(courses=0), dict(courses=2.0), dict(top_boards=True), dict(top_boards=0), dict(seam_width=0),
    dict(seam_depth=0.05),                    # deeper than the 0.045 frame
    dict(top_boards=40),                      # boards narrower than the seams
    dict(foot_inset=0.3), dict(foot_length=3.0), dict(end_overhang=0.05), dict(height=0.03),
    dict(depth=float("nan")), dict(materials={"seat": 7}), dict(post=0.04),
    dict(path=[[0, 0], [0.35, 0]]),           # too short for two foot plates
])
def test_clad_box_fail_closed(bad):
    with pytest.raises(ValueError):
        gen.build_clad_box(clad(bad.pop("path", STRAIGHT), **bad))


# --- seams by texture (Artem 2026-11-03 correction: board seams are texture, the box stays simple geometry) ---------
# SYNTHETIC runs, same synthetic CLAD parameters.
def tex(path, **kw):
    return clad(path, seams="texture", **kw)


@pytest.mark.parametrize("path,dims", [(STRAIGHT, (6.0, 0.6)), (L_RUN, (3.9, 2.5)), (U_RUN, (5.8, 2.9))])
def test_texture_box_dimensions(path, dims):
    facts = gen.mesh_facts(gen.build_clad_box(tex(path)))
    assert facts["dims_m"] == pytest.approx([dims[0], dims[1], 0.45], abs=1e-6)
    assert facts["min_z"] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("path", [STRAIGHT, L_RUN, U_RUN, SKEW_L])
def test_texture_box_quads_manifold_convex_xview_clean(path):
    mesh = gen.build_clad_box(tex(path))
    assert mesh["faces"] and all(len(f) == 4 for f in mesh["faces"])
    assert set(edge_use(mesh).values()) == {2}
    facts = gen.mesh_facts(mesh)
    assert facts["components"] == 1 and facts["loose_verts"] == 0
    res = xview_lists(mesh["verts"], mesh["faces"])
    assert res["xview_faces"] == () and res["vertices"] == ()
    for f in mesh["faces"]:
        a, b, c, d = (mesh["verts"][i] for i in f)
        assert _tri_area(a, b, c) + _tri_area(a, c, d) == pytest.approx(_tri_area(a, b, d) + _tri_area(b, c, d),
                                                                         rel=1e-9, abs=1e-12)
    run = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    assert 0.6 * 0.43 * run * 0.9 < gen.signed_volume(mesh) < 0.6 * 0.45 * (run + 0.6)


def test_texture_box_has_no_seam_geometry():
    mesh = gen.build_clad_box(tex(STRAIGHT))
    assert {round(v[2], 9) for v in mesh["verts"]} == {0.0, 0.02, 0.45}
    top = [f for f in mesh["faces"] if _face_z(mesh, f) == 0.45]
    assert len(top) == 1                                   # one top quad per straight segment
    geo = gen.build_clad_box(clad(STRAIGHT))
    assert len(mesh["faces"]) < len(geo["faces"]) / 3


def _uv_faces(mesh):
    return [(f, uv, m) for f, uv, m in zip(mesh["faces"], mesh["face_uv"], mesh["face_mat"]) if uv is not None]


def test_texture_box_uv_puts_board_seams_on_the_board_grid():
    """Top: 11 boards across the depth (2 frame + 9 slats) -> t = lateral / depth over the whole pattern;
    sides: 4 courses -> t over 4/11 of the same pattern, so every seam line falls on a board joint."""
    mesh = gen.build_clad_box(tex(STRAIGHT))
    assert mesh["uv_pattern"] == {"boards": 11, "axis": "t"}
    assert len(mesh["face_uv"]) == len(mesh["faces"])
    V = mesh["verts"]
    tops = sides = 0
    for f, uv, m in _uv_faces(mesh):
        assert m == 7 and len(uv) == len(f)
        for i, (s, t) in zip(f, uv):
            assert -1e-9 <= s <= 1 + 1e-9
            if _face_z(mesh, f) == 0.45:
                assert t == pytest.approx((V[i][1] + 0.3) / 0.6, abs=1e-9)
            else:
                assert t == pytest.approx((V[i][2] - 0.02) / 0.43 * 4 / 11, abs=1e-9)
        if _face_z(mesh, f) == 0.45:
            tops += 1
        else:
            sides += 1
    assert tops == 1 and sides == 4                      # 1 top quad + the 4-face side ring
    rest = [(f, m) for f, uv, m in zip(mesh["faces"], mesh["face_uv"], mesh["face_mat"]) if uv is None]
    assert rest and all(_face_z(mesh, f) in (0.0, 0.02) or m == 3 for f, m in rest)


@pytest.mark.parametrize("path", [L_RUN, U_RUN, SKEW_L])
def test_texture_box_top_boards_turn_the_corner(path):
    mesh = gen.build_clad_box(tex(path))
    tops = [(f, uv) for f, uv, _m in _uv_faces(mesh) if _face_z(mesh, f) == 0.45]
    assert len(tops) == len(path) - 1
    for f, uv in tops:
        assert sorted(round(t, 9) for _s, t in uv) == [0.0, 0.0, 1.0, 1.0]
    # a mitre vertex shared by two segments has the same t on both: the boards run on round the corner
    seen = {}
    for f, uv in tops:
        for i, (_s, t) in zip(f, uv):
            assert seen.setdefault(i, round(t, 9)) == round(t, 9)


@pytest.mark.parametrize("bad", [dict(seams="paint"), dict(seams=None)])
def test_texture_box_fail_closed(bad):
    with pytest.raises(ValueError):
        gen.build_clad_box(clad(STRAIGHT, **bad))


# Regression (rows 2 and 4 of Vatutino): a corner a hair wider than 90 deg pushed the mitred top vertex past the
# segment's nominal length + depth/2, so s left 0..1 (1.0000336) and the writer refused the UV. SYNTHETIC runs.
OBTUSE_L = [[0, 2.2], [0, 0], [3.6, 0.0002]]                       # 90.003 deg turn
OBTUSE_U = [[-0.01, 2.6], [0, 0], [5.2, 0], [5.21, 2.6]]           # both corners ~90.2 deg
WIDE_L = [[0, 0], [5.0, 0], [5.0 + 4.0 * math.cos(1.75), 4.0 * math.sin(1.75)]]  # 100 deg turn


@pytest.mark.parametrize("path", [OBTUSE_L, OBTUSE_U, WIDE_L, L_RUN, U_RUN, SKEW_L])
def test_texture_box_uv_stays_inside_unit_square_at_any_corner(path):
    mesh = gen.build_clad_box(tex(path))
    for _f, uv, _m in _uv_faces(mesh):
        for s, t in uv:
            assert 0.0 <= s <= 1.0 and 0.0 <= t <= 1.0


# --- #819: the forms Artem rejected on 2026-11-03 are gone («Верона» = clad box A, board seams by texture) ----------
def test_rejected_forms_are_removed():
    assert not hasattr(gen, "build_bench"), "slab on posts (variant B) was rejected"
    assert not (ROOT / "jobs/VATUTINO-SITE/maf/verona-gen-b.config.json").exists()
    writer = (ROOT / "tools/blender/maf_gen_bench_build.py").read_text(encoding="utf-8")
    assert "slab_on_posts" not in writer and "build_bench" not in writer


@pytest.mark.parametrize("mode", ["geometry", "Texture", "", 1])
def test_seams_other_than_texture_are_refused_by_name(mode):
    with pytest.raises(ValueError, match="seams"):
        gen.build_clad_box(clad(STRAIGHT, seams=mode))


def test_omitted_seams_builds_the_texture_box():
    plain = gen.build_clad_box({k: v for k, v in clad(STRAIGHT).items() if k != "seams"})
    assert plain == gen.build_clad_box(clad(STRAIGHT, seams="texture"))
    assert "face_uv" in plain
