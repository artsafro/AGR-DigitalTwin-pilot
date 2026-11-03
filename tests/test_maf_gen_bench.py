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
U_RUN = [[0, 2.6], [0, 0], [5.5, 0], [5.5, 2.6]]  # outer 5.8 x 2.9
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
    assert c == pytest.approx([[0.3, 2.5], [0.3, 0.3], [3.9, 0.3]], abs=1e-9)
    mesh = gen.build_bench(spec(c))
    assert gen.mesh_facts(mesh)["dims_m"][:2] == pytest.approx([3.9, 2.5], abs=1e-6)


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
