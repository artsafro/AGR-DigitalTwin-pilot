"""#527 overlap gate: `dt qa xview` over inv_xview in local coordinates (synthetic geometry, not TOW02 data).

The unit cases are the synthetic builder rules of review #514 (`rootcause/louvre_top/unit_cases.py`).
"""
import json
import math

import numpy as np
import pytest

from dt_ai.cli.main import main
from dt_ai.ops import xview_gate as G


# ---- synthetic cases of review #514 (unit_cases.py) ----------------------------------------------------------------

def glass_band(cols, shift=(0, 0, 0)):
    """glass quad 10 x 3.5 m (4 corners) + band 0.55 m above on `cols` columns (corners shared)."""
    V = [(0, 0, 0), (10, 0, 0), (10, 0, 3.5), (0, 0, 3.5)]
    F = [(0, 1, 2, 3)]
    xs = np.linspace(0, 10, cols + 1)
    bot = [3] + [len(V) + i for i in range(cols - 1)] + [2]
    V += [(x, 0.0, 3.5) for x in xs[1:-1]]
    top = [len(V) + i for i in range(cols + 1)]
    V += [(x, 0.0, 4.05) for x in xs]
    F += [(bot[i], bot[i + 1], top[i + 1], top[i]) for i in range(cols)]
    if any(shift):
        V.append(tuple(np.add(V[2], shift)))
        F[0] = (0, 1, len(V) - 1, 3)            # glass corner unwelded + moved
    return V, F


def rail_soffit(dz, embed=0.012):
    """soffit 2 x 2 m at z 0 and a rail bottom 0.065 x 3.37 m entering it by `embed`, raised dz."""
    V = [(0, 0, 0), (0, 2, 0), (2, 2, 0), (2, 0, 0)]
    x0, x1 = -3.37 + embed, embed
    V += [(x0, 0.5, dz), (x0, 0.565, dz), (x1, 0.565, dz), (x1, 0.5, dz)]
    return V, [(0, 1, 2, 3), (4, 5, 6, 7)]


def part(name, V, F, loc=(0.0, 0.0, 0.0)):
    """A part as the Blender dump stores it: in-place float64 vertices + the object location."""
    loc = np.asarray(loc, dtype=np.float64)
    return G.Part(name, np.asarray(V, dtype=np.float64) + loc, tuple(tuple(f) for f in F), loc)


def one(V, F, loc=(0.0, 0.0, 0.0), coords="local"):
    return G.gate_report([part("p", V, F, loc)], "NPM", coords=coords)


def contacts(rep):
    k = rep["totals"]["face_pairs_by_kind"]
    return k["contact"] + k["area+contact"]


@pytest.mark.parametrize("dz, expected", [(0.0, 1), (0.003, 1), (0.005, 1), (0.006, 0), (0.032, 0)])
def test_rail_soffit_gap_5mm_flagged_6mm_not(dz, expected):
    assert contacts(one(*rail_soffit(dz))) == expected


def test_band_30_columns_on_glass_edge_gives_30_contacts():
    rep = one(*glass_band(30))
    assert contacts(rep) == 30
    assert rep["totals"]["vertex_pairs"] == 0


def test_band_as_one_quad_gives_no_contact():
    rep = one(*glass_band(1))
    assert contacts(rep) == 0 and rep["totals"]["face_pairs"] == 0 and rep["passed"] is True


def test_glass_corner_nudged_3mm_gives_one_contact_6mm_none():
    assert contacts(one(*glass_band(1, shift=(-0.003, 0, 0)))) == 1
    assert contacts(one(*glass_band(1, shift=(0, 0.003, 0)))) == 1
    assert contacts(one(*glass_band(1, shift=(0, 0.006, 0)))) == 0


# ---- local coordinates ---------------------------------------------------------------------------------------------

SITE = (2_201_234.567, 412_345.678, 152.25)


def test_local_subtracts_location_and_matches_origin():
    V, F = rail_soffit(0.005)
    at0, site = one(V, F), one(V, F, loc=SITE)
    assert site["coords"] == "local" and site["parts"][0]["location"] == list(SITE)
    for key in ("vertex_pairs", "overlapping_vertices", "overlapping_faces", "face_pairs"):
        assert site["totals"][key] == at0["totals"][key]
    c0, cs = at0["parts"][0]["faces"][0]["centre"], site["parts"][0]["faces"][0]["centre"]
    assert np.allclose(c0, cs, atol=1e-9)                      # centres in the checked (local) frame


def test_inplace_keeps_world_centres():
    V, F = rail_soffit(0.005)
    rep = one(V, F, loc=SITE, coords="inplace")
    c = rep["parts"][0]["faces"][0]["centre"]
    assert c[0] > 2_000_000 and contacts(rep) == 1


# ---- report content ------------------------------------------------------------------------------------------------

def test_report_lists_ids_partners_kind_and_centres():
    rep = one(*rail_soffit(0.005))
    p = rep["parts"][0]
    assert p["overlapping_faces"] == 2 and p["xview_faces"] == [1, 2]
    assert p["face_pairs"] == [{"a": 1, "b": 2, "kind": "contact", "separation_m": p["face_pairs"][0]["separation_m"],
                                "centre": p["face_pairs"][0]["centre"]}]
    f1 = p["faces"][0]
    assert f1["id"] == 1 and f1["partners"] == [2] and f1["kinds"] == ["contact"] and f1["xview"] is True
    assert np.allclose(f1["centre"], [1, 1, 0])


def test_coincident_unwelded_seam_counts_vertices_as_doubles():
    # two quads side by side, seam vertices duplicated (unwelded): 2 pairs, 4 xView vertices, weld fixes them
    V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0)]
    rep = one(V, [(0, 1, 2, 3), (4, 5, 6, 7)])
    p = rep["parts"][0]
    assert p["overlapping_vertices"] == 4 and len(p["vertex_pairs"]) == 2
    assert [vp["kind"] for vp in p["vertex_pairs"]] == ["double", "double"]
    assert p["bowtie_vertices"] == [] and rep["totals"]["bowtie_pairs"] == 0


def test_split_bowtie_corner_is_its_own_finding():
    # two triangles touching only at one corner, the corner duplicated (what Editable Poly makes of a bow-tie)
    V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 0), (2, 1, 0), (2, 2, 0)]
    rep = one(V, [(0, 1, 2), (3, 4, 5)])
    p = rep["parts"][0]
    assert p["vertex_pairs"][0]["kind"] == "bowtie" and rep["totals"]["bowtie_pairs"] == 1
    assert rep["totals"]["overlapping_vertices"] == 2 and rep["passed"] is False


def test_welded_bowtie_vertex_is_listed_with_its_fans():
    # one shared vertex, two fans: inv_xview sees no vertex pair, Poly would split it into 2 -> 2 xView vertices
    V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0), (2, 2, 0)]
    rep = one(V, [(0, 1, 2), (2, 3, 4)])
    p = rep["parts"][0]
    assert p["vertex_pairs"] == []
    assert p["bowtie_vertices"] == [{"vertex": 3, "fans": 2, "centre": [1.0, 1.0, 0.0]}]
    assert rep["totals"]["bowtie_vertices"] == 1 and rep["passed"] is False


def test_manifold_closed_box_has_no_bowtie():
    V = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    rep = one(V, F)
    assert rep["passed"] is True and rep["totals"]["bowtie_vertices"] == 0


# ---- fail-closed ---------------------------------------------------------------------------------------------------

def test_no_parts_is_an_error():
    with pytest.raises(ValueError, match="no parts"):
        G.gate_report([], "NPM")


def test_part_without_faces_fails():
    rep = G.gate_report([part("p", [(0, 0, 0)], [])], "NPM")
    assert rep["passed"] is False and rep["parts"][0]["passed"] is False


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_non_finite_vertex_is_an_error(bad):
    with pytest.raises(ValueError, match="finite"):
        one([(0, 0, 0), (1, 0, 0), (bad, 1, 0)], [(0, 1, 2)])


def test_non_finite_location_is_an_error():
    with pytest.raises(ValueError, match="finite"):
        one([(0, 0, 0), (1, 0, 0), (1, 1, 0)], [(0, 1, 2)], loc=(0, math.nan, 0))


def test_duplicate_part_names_are_an_error():
    V, F = rail_soffit(0.1)
    with pytest.raises(ValueError, match="duplicate"):
        G.gate_report([part("p", V, F), part("p", V, F)], "NPM")


def test_unknown_profile_and_coords_are_errors():
    V, F = rail_soffit(0.1)
    with pytest.raises(ValueError, match="profile"):
        G.gate_report([part("p", V, F)], "IFC")
    with pytest.raises(ValueError, match="coords"):
        G.gate_report([part("p", V, F)], "NPM", coords="world")


def test_exactly_at_threshold_is_flagged():
    assert contacts(one(*rail_soffit(G.inv_xview.FACE_M))) == 1           # <= at 5.000 mm (fail-closed)


# ---- npz input + CLI -----------------------------------------------------------------------------------------------

def write_npz(path, parts):
    G.save_npz(path, parts)
    return path


def run(argv, capsys):
    code = main(argv)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_npz_reports_overlaps_exit_1(tmp_path, capsys):
    src = write_npz(tmp_path / "a.npz", [part("rail", *rail_soffit(0.005), loc=SITE), part("band", *glass_band(1))])
    out = tmp_path / "r.json"
    code, so, _ = run(["qa", "xview", str(src), "--out", str(out)], capsys)
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert code == 1 and rep["passed"] is False and rep["coords"] == "local" and rep["profile"] == "NPM"
    assert [p["part"] for p in rep["parts"]] == ["rail", "band"]
    assert rep["totals"]["overlapping_faces"] == 2 and rep["totals"]["vertex_pairs"] == 0
    assert "Overlapping Faces 2" in so and "Overlapping Vertices 0" in so
    assert not list(tmp_path.glob("*.partial"))


def test_cli_clean_exit_0_and_parts_filter(tmp_path, capsys):
    src = write_npz(tmp_path / "a.npz", [part("rail", *rail_soffit(0.005)), part("band", *glass_band(1))])
    out = tmp_path / "r.json"
    code, _, _ = run(["qa", "xview", str(src), "--parts", "band", "--profile", "VPM", "--out", str(out)], capsys)
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0 and rep["passed"] is True and [p["part"] for p in rep["parts"]] == ["band"]
    assert rep["profile"] == "VPM"


def test_cli_unknown_part_is_error_naming_it(tmp_path, capsys):
    src = write_npz(tmp_path / "a.npz", [part("rail", *rail_soffit(0.005))])
    out = tmp_path / "r.json"
    code, _, err = run(["qa", "xview", str(src), "--parts", "nope", "--out", str(out)], capsys)
    assert code == 2 and "nope" in err and not out.exists()


def test_cli_out_equal_to_input_is_refused(tmp_path, capsys):
    src = write_npz(tmp_path / "a.npz", [part("rail", *rail_soffit(0.005))])
    before = src.read_bytes()
    code, _, err = run(["qa", "xview", str(src), "--out", str(tmp_path / "." / "a.npz")], capsys)
    assert code == 2 and "input" in err and src.read_bytes() == before


def test_cli_existing_out_is_refused(tmp_path, capsys):
    src = write_npz(tmp_path / "a.npz", [part("rail", *rail_soffit(0.005))])
    out = tmp_path / "r.json"
    out.write_text("old", encoding="utf-8")
    code, _, err = run(["qa", "xview", str(src), "--out", str(out)], capsys)
    assert code == 2 and "exists" in err and out.read_text(encoding="utf-8") == "old"


@pytest.mark.parametrize("name", ["a.obj", "a.FBXX", "a"])
def test_cli_unsupported_input_is_error(tmp_path, capsys, name):
    src = tmp_path / name
    src.write_bytes(b"x")
    code, _, err = run(["qa", "xview", str(src), "--out", str(tmp_path / "r.json")], capsys)
    assert code == 2 and "unsupported" in err and not (tmp_path / "r.json").exists()


def test_cli_missing_input_is_error(tmp_path, capsys):
    code, _, err = run(["qa", "xview", str(tmp_path / "none.npz"), "--out", str(tmp_path / "r.json")], capsys)
    assert code == 2 and not (tmp_path / "r.json").exists()


def test_cli_empty_npz_is_error(tmp_path, capsys):
    src = tmp_path / "e.npz"
    np.savez(src, names=np.array([], dtype=str))
    code, _, err = run(["qa", "xview", str(src), "--out", str(tmp_path / "r.json")], capsys)
    assert code == 2 and "no parts" in err


def test_cli_nan_npz_is_error(tmp_path, capsys):
    src = write_npz(tmp_path / "a.npz", [G.Part("p", np.array([(0, 0, 0), (1, 0, 0), (np.nan, 1, 0)], float),
                                                ((0, 1, 2),), np.zeros(3))])
    code, _, err = run(["qa", "xview", str(src), "--out", str(tmp_path / "r.json")], capsys)
    assert code == 2 and "finite" in err and not (tmp_path / "r.json").exists()


def test_legacy_single_mesh_npz(tmp_path):
    # the review #514 xcheck format: vertices + loop_total / loop_start / loop_vert, no location
    V, F = rail_soffit(0.005)
    lt = [len(f) for f in F]
    np.savez(tmp_path / "x.npz", vertices=np.array(V, float), loop_total=np.array(lt),
             loop_start=np.cumsum([0] + lt[:-1]), loop_vert=np.array([i for f in F for i in f]))
    with pytest.raises(ValueError, match="location"):
        G.gate_report(G.load_npz(tmp_path / "x.npz"), "NPM", coords="local")
    rep = G.gate_report(G.load_npz(tmp_path / "x.npz"), "NPM", coords="as-stored")
    assert contacts(rep) == 1 and rep["parts"][0]["part"] == "x"


def test_npz_with_unknown_keys_is_error(tmp_path):
    np.savez(tmp_path / "x.npz", foo=np.zeros(3))
    with pytest.raises(ValueError, match="foo"):
        G.load_npz(tmp_path / "x.npz")


def test_npz_roundtrip_keeps_float64(tmp_path):
    p = part("p", *rail_soffit(0.005), loc=SITE)
    back = G.load_npz(write_npz(tmp_path / "a.npz", [p]))[0]
    assert back.vertices.dtype == np.float64 and np.array_equal(back.vertices, p.vertices)
    assert back.faces == p.faces and np.array_equal(back.location, p.location)


def test_bad_loops_are_an_error(tmp_path):
    np.savez(tmp_path / "x.npz", names=np.array(["p"]), v0=np.zeros((3, 3)), lt0=np.array([4]),
             lv0=np.array([0, 1, 2]), loc0=np.zeros(3))
    with pytest.raises(ValueError, match="loop"):
        G.load_npz(tmp_path / "x.npz")
