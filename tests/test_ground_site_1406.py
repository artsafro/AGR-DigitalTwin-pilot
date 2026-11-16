"""#1406: Ground for any site in the D293 order (`dt ground site`) and the project zero command (`dt ground zero`).

All site data here is SYNTHETIC (generated squares, planes and DXF), never a real object.
"""
import json
import math
import random
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from shapely.geometry import box

from dt_ai.core.heights import export_z_check
from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry import ground_site as gs

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "tools/ground/build_ground_site.py"
ZERO = ROOT / "tools/ground/project_zero.py"


def plane(x, y):
    return 100.0 + 0.05 * x - 0.03 * y


def relief(w=20.0, h=20.0, n=6, margin=1.0, f=plane):
    xs = np.linspace(-margin, w + margin, n)
    ys = np.linspace(-margin, h + margin, n)
    return [(x, y, f(x, y)) for x in xs for y in ys]


def covers(inner=box(5, 5, 10, 10)):
    return [gs.Cover(1, "Lawn", [box(0, 0, 20, 20)], (96, 150, 64), "spec"),
            gs.Cover(2, "Rubber", [inner], (246, 115, 44), "hatch-bgcolor")]


def build(**kw):
    args = dict(boundary=box(0, 0, 20, 20), covers=covers(), base_id=1, relief_xyz=relief(), project_zero_m=100.0)
    args.update(kw)
    return gs.build_site(args.pop("boundary"), args.pop("covers"), args.pop("base_id"), args.pop("relief_xyz"),
                         args.pop("project_zero_m"), origin_xy=(0, 0), **args)


def test_d293_order_flat_first_then_relief_then_skirt():
    r = build()
    st = r.report["stages"]
    assert r.report["order"] == ["sources", "zero", "surfaces", "quads", "textures", "relief", "skirt", "ucx"]
    assert set(np.round(r.flat.verts[:, 2], 9)) <= {0.0, 0.006}  # flat Ground has no relief
    assert st["relief"]["flat_vertices_retained"]["missing"] == 0
    assert st["relief"]["relief_error"]["faces_over_tol"] == 0
    assert st["textures"]["tiles"]["tiles"] == [1001, 1002] and st["textures"]["tiles"]["straddling"] == 0
    assert st["skirt"]["skirt_gap_edges"] == [] and st["skirt"]["skirt_faces"] > 0
    assert st["ucx"]["status"] == "not_run" and r.report["passed"] is False
    assert r.report["geometry_status"] == "built"
    # projection: ground top follows the relief - zero, inset level on top
    top = r.mesh.level == 0
    vs = np.unique(r.mesh.faces[top])
    assert np.allclose(r.mesh.verts[vs, 2], plane(r.mesh.verts[vs, 0], r.mesh.verts[vs, 1]) - 100.0, atol=1e-6)
    ids = {i["id"]: i for i in st["surfaces"]["ids"]}
    assert ids[2]["udim"] == 1002 and ids[2]["colour_rgb"] == [246, 115, 44]


def test_skirt_takes_base_id_and_stays_in_its_tile():
    r = build()
    sk = r.mesh.level < 0
    assert set(np.array(r.mesh.slot)[sk]) == {"ID01_Lawn"}
    assert (r.mesh.uv[sk][..., 0] >= 0).all() and (r.mesh.uv[sk][..., 0] <= 1).all()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, None, "142.1"])
def test_zero_must_be_finite(value):
    with pytest.raises(ValueError, match="project_zero_m"):
        build(project_zero_m=value)


@pytest.mark.parametrize("drop,ok", [(1.0, True), (0.999999, False), (float("nan"), False), (0.0, False)])
def test_skirt_threshold(drop, ok):
    if ok:
        assert build(skirt_m=drop).report["stages"]["skirt"]["drop_m"] == 1.0
    else:
        with pytest.raises(ValueError):
            build(skirt_m=drop)


@pytest.mark.parametrize("cs,msg", [
    ([gs.Cover(1, "A", [box(0, 0, 20, 20)], (0, 0, 0), "spec"), gs.Cover(3, "B", [box(1, 1, 2, 2)], (1, 1, 1), "spec")], "without gaps"),
    ([gs.Cover(1, "A", [box(0, 0, 20, 20)], (0, 0, 0), "spec"), gs.Cover(2, "A", [box(1, 1, 2, 2)], (1, 1, 1), "spec")], "duplicate"),
    ([gs.Cover(1, "A b", [box(0, 0, 20, 20)], (0, 0, 0), "spec")], "Latin"),
    ([gs.Cover(1, "A", [box(0, 0, 20, 20)], (0, 0, 256), "spec")], "colour"),
    ([gs.Cover(1, "A", [], (0, 0, 0), "spec")], "no polygons"),
    ([], "no covers"),
])
def test_cover_ids_fail_closed(cs, msg):
    with pytest.raises(ValueError, match=msg):
        build(covers=cs)


def test_base_must_be_a_cover():
    with pytest.raises(ValueError, match="base cover ID 7"):
        build(base_id=7)


def test_cover_ids_beyond_first_udim_row_refused():
    """Review r1 P3: ID 11+ would leave the first UDIM row (1001-1010); refuse naming the limit."""
    cs = [gs.Cover(1, "A", [box(0, 0, 20, 20)], (0, 0, 0), "spec")]
    cs += [gs.Cover(i, f"C{i}", [box(i, 1, i + 0.5, 2)], (1, 1, 1), "spec") for i in range(2, 12)]
    with pytest.raises(ValueError, match="ID 11 .*1010"):
        gs.check_covers(cs, 1)
    gs.check_covers(cs[:10], 1)  # ID 10 = UDIM 1010 is the last allowed


def test_relief_miss_is_an_error_not_extrapolated():
    half = [p for p in relief() if p[0] <= 10]
    with pytest.raises(ValueError, match="outside the relief TIN"):
        build(relief_xyz=half)


def test_contradictory_relief_marks_refused():
    pts = relief() + [(-1.0, -1.0, 150.0)]
    with pytest.raises(ValueError, match="same XY and other Z"):
        build(relief_xyz=pts)


def test_unhatched_area_is_a_finding_unless_policy():
    cs = [gs.Cover(1, "Lawn", [box(0, 0, 20, 19)], (1, 2, 3), "spec"),
          gs.Cover(2, "Rubber", [box(5, 5, 10, 10)], (4, 5, 6), "spec")]
    r = build(covers=cs)
    assert r.report["geometry_status"] == "fail" and any("unhatched" in f for f in r.report["findings"])
    ok = build(covers=cs, unhatched={"cover_id": 1, "reason": "synthetic test policy"})
    assert ok.report["geometry_status"] == "built"
    with pytest.raises(ValueError, match="unhatched policy"):
        build(covers=cs, unhatched={"cover_id": 2, "reason": "x"})
    with pytest.raises(ValueError, match="unhatched policy"):
        build(covers=cs, unhatched={"cover_id": 1, "reason": " "})


def test_crop_box_fragment():
    r = build(crop_box=[0, 0, 12, 12])
    assert r.report["stages"]["sources"]["fragment"] is True
    assert abs(r.report["stages"]["sources"]["boundary_m2"] - 144.0) < 1e-6
    with pytest.raises(ValueError, match="crop_box"):
        build(crop_box=[100, 100, 120, 120])


@pytest.mark.parametrize("seed", range(12))
def test_generated_sites_invariants(seed):
    """Probe: random sites -> skirt drop >= 1 m on every outer edge, UDIM = ID, no straddle, flat vertices kept."""
    rnd = random.Random(seed)
    w, h = rnd.uniform(8, 30), rnd.uniform(8, 30)
    n = rnd.randint(1, 4)
    cs = [gs.Cover(1, "Base", [box(0, 0, w, h)], (1, 1, 1), "spec")]
    for i in range(2, n + 1):
        x0, y0 = rnd.uniform(0, w - 3), rnd.uniform(0, h - 3)
        cs.append(gs.Cover(i, f"C{i}", [box(x0, y0, min(w, x0 + rnd.uniform(1, 6)), min(h, y0 + rnd.uniform(1, 6)))],
                           (i, i, i), "spec"))
    a, b, c = rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), rnd.uniform(-0.01, 0.01)
    pts = relief(w, h, 7, 1.0, lambda x, y: 150 + a * x + b * y + c * x * y)
    r = gs.build_site(box(0, 0, w, h), cs, 1, pts, 150.0, origin_xy=(0, 0), cell=rnd.choice([2.0, 3.0, 4.0]),
                      skirt_m=rnd.choice([1.0, 1.5]))
    st = r.report["stages"]
    assert st["skirt"]["skirt_gap_edges"] == []
    assert st["textures"]["tiles"]["straddling"] == 0
    used = sorted({int(s[2:4]) for s in r.mesh.slot})
    assert st["textures"]["tiles"]["tiles"] == [1000 + i for i in used]
    for i, s in enumerate(r.mesh.slot):
        assert math.floor(r.mesh.uv[i, :, 0].min() + 1e-9) == int(s[2:4]) - 1
    assert st["relief"]["flat_vertices_retained"]["missing"] == 0
    assert st["relief"]["relief_error"]["faces_over_tol"] == 0


# ---------------------------------------------------------------- export Z / project zero


def rel(xy):
    """Synthetic relief sampler: the plane inside [-1, 21]^2, None (outside the TIN) elsewhere."""
    return [plane(x, y) if -1 <= x <= 21 and -1 <= y <= 21 else None for x, y in xy]


PTS = [(x, y, plane(x, y) - 100.0, 0) for x in (0.0, 5.0, 20.0) for y in (0.0, 7.0, 20.0)] + \
      [(6.0, 6.0, plane(6.0, 6.0) - 100.0 + 0.006, 1), (7.0, 8.0, plane(7.0, 8.0) - 100.0 + 0.012, 2)]


@pytest.mark.parametrize("shift,status", [(0.0, "pass"), (-0.90, "fail"), (-0.10, "fail"), (0.09, "fail"),
                                          (1.40, "fail"), (0.01, "pass"), (0.0101, "fail"), (-0.01, "pass"),
                                          (-0.0101, "fail")])
def test_export_z_pointwise_shift(shift, status):
    """Review r1 P1-1: shifts that keep the ground inside the relief envelope must still fail (pointwise)."""
    out = export_z_check(100.0 + shift, 0.0, PTS, rel, step_m=0.006, tol_m=0.01)
    assert out["status"] == status, out
    assert out["checked_vertices"] == len(PTS)


@pytest.mark.parametrize("shift,status", [(0.25, "pass"), (-0.25, "pass"), (0.2501, "fail"), (-0.2501, "fail")])
def test_export_z_pointwise_exactly_tol(shift, status):
    assert export_z_check(100.0 + shift, 0.0, PTS, rel, step_m=0.006, tol_m=0.25)["status"] == status


@pytest.mark.parametrize("seed", range(5))
def test_export_z_pointwise_generated_shifts(seed):
    """Probe: for random shifts s, pass <=> |s| <= tol (40 shifts per seed, envelope-preserving ones included)."""
    rng = random.Random(seed)
    for _ in range(40):
        s = rng.uniform(-1.0, 1.0)
        assert (export_z_check(100.0 + s, 0.0, PTS, rel, step_m=0.006, tol_m=0.01)["status"] == "pass") == \
            (abs(s) <= 0.01), s


def test_export_z_pointwise_one_vertex_off_and_fbx_offset():
    pts = list(PTS)
    pts[4] = (pts[4][0], pts[4][1], pts[4][2] + 0.05, 0)
    out = export_z_check(100.0, 0.0, pts, rel, step_m=0.006, tol_m=0.01)
    assert out["status"] == "fail" and "1 ground vertices" in out["findings"][0]
    lifted = [(x, y, z + 3.0, lv) for x, y, z, lv in PTS]  # +-0.000 at FBX Z 3.0
    assert export_z_check(100.0, 3.0, lifted, rel, step_m=0.006, tol_m=0.01)["status"] == "pass"
    assert export_z_check(100.0, 0.0, lifted, rel, step_m=0.006, tol_m=0.01)["status"] == "fail"


@pytest.mark.parametrize("pts,kw,msg", [
    ([(30.0, 30.0, 0.0, 0)] + PTS, {}, "outside the relief"),
    (PTS, {"step_m": 0.0}, "step_m"),
    ([(0.0, 0.0, 0.0, -1)], {}, "level"),
    ([(0.0, 0.0, 0.0, 1.5)], {}, "level"),
    ([(0.0, 0.0, float("nan"), 0)], {}, "finite"),
    ([(float("inf"), 0.0, 0.0, 0)], {}, "finite"),
    ([], {}, "no ground"),
    ([(0.0, 0.0, 0.0)], {}, "x, y, z, level"),
])
def test_export_z_pointwise_refuses(pts, kw, msg):
    args = dict(step_m=0.006, tol_m=0.01)
    args.update(kw)
    with pytest.raises(ValueError, match=msg):
        export_z_check(100.0, 0.0, pts, rel, **args)


@pytest.mark.parametrize("args", [(float("nan"), 0.0), (100.0, float("inf")), (True, 0.0)])
def test_export_z_check_refuses(args):
    with pytest.raises(ValueError):
        export_z_check(*args, PTS, rel, step_m=0.006, tol_m=0.01)
    with pytest.raises(ValueError, match="tol_m"):
        export_z_check(100.0, 0.0, PTS, rel, step_m=0.006, tol_m=-0.01)
    with pytest.raises(ValueError, match="relief_z_at"):
        export_z_check(100.0, 0.0, PTS, None, step_m=0.006, tol_m=0.01)


# ---------------------------------------------------------------- skirt gaps (edge level, review r1 P1-2)


def _skirt_quads(mesh):
    sk = np.nonzero(mesh.level < 0)[0]
    return list(zip(sk[0::2], sk[1::2]))


def _without(mesh, faces):
    keep = np.setdiff1d(np.arange(len(mesh.faces)), list(faces))
    return gc.Mesh(mesh.verts.copy(), mesh.faces[keep].copy(), [mesh.slot[i] for i in keep], mesh.level[keep].copy(),
                   mesh.uv[keep].copy(), mesh.cell, dict(mesh.report))


def test_skirt_gaps_intact_control():
    mesh = build().mesh
    assert len(_skirt_quads(mesh)) >= 4 and gs.skirt_gaps(mesh, 1.0) == []


def test_skirt_gaps_every_deleted_quad_is_one_gap():
    """Probe: deleting any one skirt quad gives exactly one gap edge (that quad's base edge)."""
    mesh = build().mesh
    for i, j in _skirt_quads(mesh):
        b, a = mesh.faces[i][:2]
        gaps = gs.skirt_gaps(_without(mesh, (i, j)), 1.0)
        assert [sorted(g["edge"]) for g in gaps] == [sorted([int(a), int(b)])], (i, gaps)
        assert gaps[0]["reason"] == "no skirt quad"


def test_skirt_gaps_deleted_half_quad():
    mesh = build().mesh
    i, j = _skirt_quads(mesh)[0]
    assert len(gs.skirt_gaps(_without(mesh, (j,)), 1.0)) == 1
    assert len(gs.skirt_gaps(_without(mesh, (i,)), 1.0)) == 1


def test_skirt_gaps_half_metre_quad():
    mesh = build().mesh
    i, j = _skirt_quads(mesh)[3]
    b, a, la = mesh.faces[i]
    na, nb = len(mesh.verts), len(mesh.verts) + 1
    verts = np.vstack([mesh.verts, mesh.verts[a] - [0, 0, 0.5], mesh.verts[b] - [0, 0, 0.5]])
    faces = mesh.faces.copy()
    faces[i] = [b, a, na]
    faces[j] = [b, na, nb]
    m2 = gc.Mesh(verts, faces, list(mesh.slot), mesh.level.copy(), mesh.uv.copy(), mesh.cell, dict(mesh.report))
    gaps = gs.skirt_gaps(m2, 1.0)
    assert [sorted(g["edge"]) for g in gaps] == [sorted([int(a), int(b)])]
    assert gaps[0]["drop_m"] == pytest.approx(0.5)
    assert gs.skirt_gaps(m2, 0.5) == []  # exactly at threshold passes


# ---------------------------------------------------------------- DXF adapter + CLI (synthetic DXF)


def make_dxf(path: Path, lawn_bg=None):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new()
    msp = doc.modelspace()
    b = msp.add_lwpolyline([(0, 0), (20, 0), (20, 20), (0, 20)], close=True)
    lawn = msp.add_hatch(color=3)
    lawn.paths.add_polyline_path([(0, 0), (20, 0), (20, 20), (0, 20)], is_closed=True)
    if lawn_bg:
        lawn.bgcolor = lawn_bg
    rub = msp.add_hatch(color=253)  # pattern colour 253 (grey) - must NOT become the ID colour
    rub.paths.add_polyline_path([(5, 5), (10, 5), (10, 10), (5, 10)], is_closed=True)
    rub.bgcolor = (246, 115, 44)
    for y in (-1.0, 7.0, 14.0, 21.0):
        msp.add_polyline3d([(x, y, plane(x, y)) for x in (-1.0, 7.0, 14.0, 21.0)], dxfattribs={"layer": "CONT"})
    doc.saveas(path)
    return b.dxf.handle, lawn.dxf.handle, rub.dxf.handle


def make_spec(tmp_path, lawn_colour=True, **extra):
    dxf = tmp_path / "site.dxf"
    hb, hl, hr = make_dxf(dxf)
    lawn = {"id": 1, "name": "Lawn", "hatches": [hl]}
    if lawn_colour:
        lawn.update(colour=[96, 150, 64], colour_reason="synthetic: lawn hatch has no bgcolor")
    spec = {"site": "SYN", "dxf": {"path": str(dxf), "sha256": gs.sha256(dxf)}, "boundary": {"handle": hb},
            "zero": {"project_zero_m": 100.0, "source": "synthetic"}, "base_id": 1,
            "covers": [lawn, {"id": 2, "name": "Rubber", "hatches": [hr]}],
            "relief": {"contour_layers": ["CONT"]}, "params": {"origin_xy": [0, 0]}}
    spec.update(extra)
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return p, spec


def run(*argv):
    return subprocess.run([sys.executable, *map(str, argv)], capture_output=True, text=True, cwd=str(ROOT))


def test_cli_fresh_process_builds_and_reads_back(tmp_path):
    spec, _ = make_spec(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    r = run(SITE, spec, tmp_path / "out")
    assert r.returncode == 0, r.stderr
    rep = json.loads((tmp_path / "out/ground-report.json").read_text(encoding="utf-8"))
    ids = {i["id"]: i for i in rep["stages"]["surfaces"]["ids"]}
    assert ids[2]["colour_rgb"] == [246, 115, 44] and ids[2]["colour_source"] == "hatch-bgcolor"
    assert ids[1]["colour_source"] == "spec"
    assert rep["readback"]["tiles"] == {"M_SYN_Ground_ID01_Lawn": [1001], "M_SYN_Ground_ID02_Rubber": [1002]}
    assert rep["project_zero_check"]["status"] == "pass" and rep["passed"] is False
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["SM_SYN_Ground.obj", "ground-flat.obj",
                                                                     "ground-report.json"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before  # inputs untouched
    assert rep["project_zero_check"]["checked_vertices"] > 0
    back = gs.read_obj(tmp_path / "out/SM_SYN_Ground.obj")
    assert {p[3] for p in back["points"]} == {0, 1}  # inset level written as group ground_inset1


@pytest.fixture(scope="module")
def built_site(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("site1406")
    spec, _ = make_spec(tmp)
    r = run(SITE, spec, tmp / "out")
    assert r.returncode == 0, r.stderr
    return spec, tmp / "out/SM_SYN_Ground.obj"


@pytest.mark.parametrize("shift,code", [(0.0, 0), (-0.90, 1), (-0.10, 1), (0.09, 1), (1.40, 1)])
def test_zero_cli_pointwise_rows(built_site, shift, code):
    """Review r1 P1-1 rows on a built site: a shift inside the relief envelope exits 1."""
    spec, obj = built_site
    z = run(ZERO, "--project-zero-m", 100.0 + shift, "--zero-source", "synthetic", "--obj", obj, "--spec", spec)
    assert z.returncode == code, z.stdout + z.stderr
    out = json.loads(z.stdout)
    assert out["checked_vertices"] > 0 and out["status"] == ("pass" if code == 0 else "fail")


def test_zero_cli_relief_points_and_outside_tin(built_site, tmp_path):
    spec, obj = built_site
    pts = tmp_path / "relief.json"
    pts.write_text(json.dumps([list(p) for p in relief()]), encoding="utf-8")
    base = ["--project-zero-m", 100.0, "--zero-source", "s", "--obj", obj]
    ok = run(ZERO, *base, "--relief-points", pts, "--origin-xy", 0, 0, "--step-m", 0.006)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    far = run(ZERO, *base, "--relief-points", pts, "--origin-xy", 100, 100, "--step-m", 0.006)
    assert far.returncode == 2 and "outside the relief" in far.stderr
    assert run(ZERO, *base, "--relief-points", pts, "--origin-xy", 0, 0).returncode == 2  # inset level, no step


def test_cli_hatch_without_bgcolor_and_no_spec_colour_refused(tmp_path):
    spec, _ = make_spec(tmp_path, lawn_colour=False)
    r = run(SITE, spec, tmp_path / "out")
    assert r.returncode == 2 and "no background colour" in r.stderr and not (tmp_path / "out").exists()


@pytest.mark.parametrize("case", ["exists", "partial", "is_spec", "is_dxf", "sha", "no_zero", "unknown_key",
                                  "zero_nan", "dup_hatch", "not_hatch"])
def test_cli_refusals_write_nothing(tmp_path, case):
    spec, data = make_spec(tmp_path)
    out = tmp_path / "out"
    if case == "exists":
        out.mkdir()
    elif case == "partial":
        (tmp_path / "out.partial").mkdir()
    elif case == "is_spec":
        out = spec
    elif case == "is_dxf":
        out = Path(data["dxf"]["path"])
    else:
        if case == "sha":
            data["dxf"]["sha256"] = "0" * 64
        elif case == "no_zero":
            del data["zero"]
        elif case == "unknown_key":
            data["extra"] = 1
        elif case == "dup_hatch":
            data["covers"][1]["hatches"].append(data["covers"][0]["hatches"][0])
        elif case == "not_hatch":
            data["covers"][1]["hatches"] = [data["boundary"]["handle"]]
        text = json.dumps(data)
        if case == "zero_nan":
            text = text.replace('"project_zero_m": 100.0', '"project_zero_m": NaN')
        spec.write_text(text, encoding="utf-8")
    before = sorted((p.name, p.is_dir() or p.read_bytes()) for p in tmp_path.iterdir())
    r = run(SITE, spec, out)
    assert r.returncode == 2, r.stdout
    assert sorted((p.name, p.is_dir() or p.read_bytes()) for p in tmp_path.iterdir()) == before


@pytest.mark.parametrize("case", ["no_relief", "zero_nan", "blank_source", "both", "nan_points", "missing_obj",
                                  "no_args", "obj_is_spec_dxf_sha"])
def test_zero_cli_refusals(built_site, tmp_path, case):
    spec, obj = built_site
    pts = tmp_path / "relief.json"
    pts.write_text(json.dumps([list(p) for p in relief()]), encoding="utf-8")
    a = {"--project-zero-m": ["100"], "--zero-source": ["s"], "--obj": [obj], "--spec": [spec]}
    if case == "no_relief":
        del a["--spec"]
    elif case == "zero_nan":
        a["--project-zero-m"] = ["nan"]
    elif case == "blank_source":
        a["--zero-source"] = [" "]
    elif case == "both":
        a.update({"--relief-points": [pts], "--origin-xy": [0, 0]})
    elif case == "nan_points":
        pts.write_text("[[0, 0, NaN], [30, 0, 1], [0, 30, 1]]", encoding="utf-8")
        del a["--spec"]
        a.update({"--relief-points": [pts], "--origin-xy": [0, 0], "--step-m": [0.006]})
    elif case == "missing_obj":
        a["--obj"] = [tmp_path / "nope.obj"]
    elif case == "no_args":
        a = {}
    elif case == "obj_is_spec_dxf_sha":
        bad = json.loads(Path(spec).read_text(encoding="utf-8"))
        bad["dxf"]["sha256"] = "0" * 64
        (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        a["--spec"] = [tmp_path / "bad.json"]
    r = run(ZERO, *[t for k, v in a.items() for t in (k, *v)])
    assert r.returncode == 2, (case, r.stdout, r.stderr)


# ---------------------------------------------------------------- routing


@pytest.mark.parametrize("argv,expected", [
    (["ground", "site", "a.json", "out"], ["ground", "site", "a.json", "out"]),
    (["ground", "zero", "--z", "1"], ["ground", "zero", "--z", "1"]),
    (["ground", "v015", "--job-dir", "j"], ["ground", "v015", "--job-dir", "j"]),
    (["ground", "--job-dir", "j"], ["ground", "v015", "--job-dir", "j"]),  # frozen Vatutino record unchanged
    (["zero", "--z", "1"], ["ground", "zero", "--z", "1"]),
])
def test_agr_ground_routing(argv, expected, monkeypatch):
    import dt_ai.cli.agr as agr
    call = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(agr.subprocess, "run", call)
    assert agr.main(argv) == 0
    call.assert_called_once_with([sys.executable, "-m", "dt_ai.cli.main", *expected], check=False)


def test_dt_ground_steps_registered():
    from dt_ai.cli import shared_tools
    for step, rel in (("site", "tools/ground/build_ground_site.py"), ("zero", "tools/ground/project_zero.py"),
                      ("v015", "tools/ground/build_ground_v015.py")):
        assert shared_tools.command(ROOT, "ground", step, [])[1].replace("\\", "/").endswith(rel)
