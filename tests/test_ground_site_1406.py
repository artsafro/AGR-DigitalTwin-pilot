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
from shapely.geometry import Polygon, box

from dt_ai.core.heights import export_z_check
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


def test_export_z_check_threshold_and_shift():
    assert export_z_check(100.0, 0.0, [0.0, 2.0], (100.0, 102.0), 0.01)["status"] == "pass"
    assert export_z_check(100.0, 0.0, [0.0, 2.0 + 0.01], (100.0, 102.0), 0.01)["status"] == "pass"  # == tol
    assert export_z_check(100.0, 0.0, [0.0, 2.0 + 0.0101], (100.0, 102.0), 0.01)["status"] == "fail"
    shifted = export_z_check(101.40, 0.0, [0.0, 2.0], (100.0, 102.0), 0.01)
    assert shifted["status"] == "fail" and shifted["h_relief"] == 101.4
    assert export_z_check(100.0, 0.0, [0.5], None)["status"] == "fail"  # unchecked is never pass


@pytest.mark.parametrize("args", [(float("nan"), 0.0, [1.0]), (100.0, float("inf"), [1.0]), (100.0, 0.0, []),
                                  (100.0, 0.0, [float("nan")]), (True, 0.0, [1.0]), (100.0, 0.0, [1.0], (2.0, 1.0))])
def test_export_z_check_refuses(args):
    with pytest.raises(ValueError):
        export_z_check(*args)


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
    z = run(ZERO, "--project-zero-m", 100, "--zero-source", "synthetic", "--obj", tmp_path / "out/SM_SYN_Ground.obj",
            "--relief-range", *rep["stages"]["zero"]["relief_abs_range_m"], "--tol-m", 0.022)
    assert z.returncode == 0, z.stdout + z.stderr
    z = run(ZERO, "--project-zero-m", 101.4, "--zero-source", "shifted", "--obj", tmp_path / "out/SM_SYN_Ground.obj",
            "--relief-range", *rep["stages"]["zero"]["relief_abs_range_m"])
    assert z.returncode == 1


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


@pytest.mark.parametrize("argv,code", [([], 2), (["--project-zero-m", "nan", "--zero-source", "s", "--z", "1",
                                                   "--relief-range", "0", "2"], 2),
                                        (["--project-zero-m", "100", "--zero-source", " ", "--z", "1",
                                          "--relief-range", "100", "102"], 2),
                                        (["--project-zero-m", "100", "--zero-source", "s", "--z", "1",
                                          "--relief-range", "100", "102"], 0),
                                        (["--project-zero-m", "100", "--zero-source", "s", "--z", "3",
                                          "--relief-range", "100", "102"], 1)])
def test_zero_cli_statuses(argv, code):
    assert run(ZERO, *argv).returncode == code


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
