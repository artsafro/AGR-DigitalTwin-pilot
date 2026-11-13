"""twinqa.uv_features: features (alpha holes) per UV face on a synthetic 2-island RGBA texture."""
import numpy as np
import pytest
from PIL import Image

from twinqa.uv_features import count_features_per_face, label_features, measure_features_per_face, read_uv_csv

SIZE = 256


def _square(u0, v0, u1, v1, du=0.0):
    return [(u0 + du, v0), (u1 + du, v0), (u1 + du, v1), (u0 + du, v1)]


A_UV = _square(0.05, 0.55, 0.45, 0.95)  # pixels x,y in ~13..115
B_UV = _square(0.55, 0.05, 0.95, 0.45)  # pixels x,y in ~141..243


def _row(name, face, mat, uv):
    return ",".join([name, str(face), str(mat)] + [f"{c:.6f}" for p in uv for c in p])


def _texture(tmp_path, mode="RGBA"):
    alpha = np.full((SIZE, SIZE), 255, np.uint8)
    for x in (30, 60, 90):  # island A: 3 holes
        alpha[60:66, x:x + 6] = 0
    for x in (150, 165, 180, 195, 210):  # island B: 5 holes
        alpha[200:204, x:x + 4] = 10
    rgba = np.dstack([np.full((SIZE, SIZE, 3), 128, np.uint8), alpha])
    img = Image.fromarray(rgba, "RGBA")
    path = tmp_path / f"tex_{mode}.png"
    (img if mode == "RGBA" else img.convert(mode)).save(path)
    return path


@pytest.fixture
def csv(tmp_path):
    p = tmp_path / "uv.csv"
    p.write_text(_row("A", 0, 1, A_UV) + "\n" + _row("B", 0, 2, B_UV) + "\n", encoding="utf-8")
    return p


def test_a_expected_counts_match_zero_findings(tmp_path, csv):
    rows = read_uv_csv(csv)
    assert count_features_per_face(rows, _texture(tmp_path), expected={"A": 3, "B": 5}, tile=1001) == []


def test_b_one_mismatch_for_b(tmp_path, csv):
    out = count_features_per_face(read_uv_csv(csv), _texture(tmp_path), expected={"A": 3, "B": 4}, tile=1001)
    assert [f.name for f in out] == ["uv_features.mismatch"]
    f = out[0]
    assert f.status == "fail" and f.data["name"] == "B" and f.data["count"] == 5 and f.expected.startswith("4")


def test_expected_by_material_id(tmp_path, csv):
    out = count_features_per_face(read_uv_csv(csv), _texture(tmp_path), expected={1: 3, 2: 5}, tile=1001)
    assert out == []


def test_c_face_in_next_tile_names_1002(tmp_path):
    rows = [_row("A", 0, 1, A_UV), _row("B", 0, 2, B_UV), _row("C", 0, 3, _square(0.05, 0.55, 0.45, 0.95, du=1))]
    out = count_features_per_face(rows, _texture(tmp_path), tile=1001)
    assert [f.name for f in out] == ["uv_features.wrong_tile"]
    assert "1002" in out[0].observed and out[0].data["tile"] == 1002


def test_d_texture_without_alpha_is_error_finding(tmp_path, csv):
    out = count_features_per_face(read_uv_csv(csv), _texture(tmp_path, "RGB"), expected={"A": 3, "B": 5})
    assert [(f.name, f.status) for f in out] == [("uv_features.texture", "fail")]
    assert "alpha" in out[0].observed


def test_fail_closed_inputs(tmp_path, csv):
    tex = _texture(tmp_path)
    assert [f.name for f in count_features_per_face([], tex)] == ["uv_features.input"]
    assert [f.name for f in count_features_per_face(read_uv_csv(csv), tmp_path / "missing.png")] == [
        "uv_features.texture"]
    nan = _row("A", 0, 1, A_UV).replace("0.050000", "nan", 1)
    out = count_features_per_face([nan, _row("A", 0, 1, A_UV), _row("A", 0, 1, A_UV)], tex)
    assert [f.name for f in out] == ["uv_features.invalid_row", "uv_features.duplicate_face",
                                     "uv_features.unassigned"]  # island B holes: no B face given
    # unmapped face and unused expected key are errors naming them, never a default
    out = count_features_per_face(read_uv_csv(csv), tex, expected={"A": 3, "Z": 1})
    assert sorted(f.name for f in out) == ["uv_features.expected_unused", "uv_features.unmapped"]
    assert any(f.data.get("key") == "Z" for f in out) and any(f.data.get("name") == "B" for f in out)
    with pytest.raises(ValueError):
        count_features_per_face(read_uv_csv(csv), tex, tile=999)
    with pytest.raises(ValueError):
        count_features_per_face(read_uv_csv(csv), tex, expected={"A": -1})


def test_cross_tile_vertex(tmp_path):
    rows = [_row("A", 0, 1, [(0.5, 0.5), (1.2, 0.5), (0.5, 0.9)])]
    out = count_features_per_face(rows, _texture(tmp_path), tile=1001)
    assert [f.name for f in out] == ["uv_features.cross_tile", "uv_features.unassigned"]


def test_label_threshold_and_connectivity():
    a = np.full((8, 8), 255, np.uint8)
    a[1, 1] = 127  # feature
    a[1, 4] = 128  # exactly at threshold: not a feature
    a[5, 5] = a[6, 6] = 0  # diagonal only: two blobs under 4-connectivity
    a[3, 1:4] = 0
    a[4, 3] = 0  # L shape: one blob
    c = label_features(a, 128)
    assert len(c) == 4
    assert any(np.allclose(p, (1.5, 1.5)) for p in c)


def _opaque_with_hole(tmp_path, rows, cols):
    alpha = np.full((SIZE, SIZE), 255, np.uint8)
    alpha[rows[0]:rows[1], cols[0]:cols[1]] = 0
    path = tmp_path / "hole.png"
    Image.fromarray(np.dstack([np.full((SIZE, SIZE, 3), 128, np.uint8), alpha]), "RGBA").save(path)
    return path


def test_boundary_centroid_is_assigned_once_by_tie_rule(tmp_path):
    # review P1(1): hole centred at px (128,128) lies on the shared diagonal of Q,0 and Q,1
    tex = _opaque_with_hole(tmp_path, (124, 132), (124, 132))
    rows = [_row("Q", 0, 1, [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75)]),
            _row("Q", 1, 1, [(0.25, 0.25), (0.75, 0.75), (0.25, 0.75)])]
    for ordered in (rows, list(reversed(rows))):  # tie rule does not depend on row order
        out = count_features_per_face(ordered, tex, expected={"Q": 0})
        assert [(f.name, f.data["face"], f.data["count"]) for f in out] == [("uv_features.mismatch", 0, 1)]


def test_feature_outside_every_face_is_unassigned_finding(tmp_path):
    # review P1(2): hole at rows 10..14, cols 200..204 is outside face A (UV square 0..0.5)
    tex = _opaque_with_hole(tmp_path, (10, 15), (200, 205))
    out = count_features_per_face([_row("A", 0, 1, _square(0, 0, 0.5, 0.5))], tex, expected={"A": 0}, tile=1001)
    assert [(f.name, f.status) for f in out] == [("uv_features.unassigned", "fail")]
    assert out[0].data["count"] == 1 and out[0].data["centroids_px"] == [(202.5, 12.5)]


def _island_on_transparent(tmp_path, holes):
    # issue #1078(1): alpha 0 background, opaque island px 64..192 with holes
    alpha = np.zeros((SIZE, SIZE), np.uint8)
    alpha[64:192, 64:192] = 255
    for r, c in holes:
        alpha[r:r + 6, c:c + 6] = 0
    path = tmp_path / "island.png"
    Image.fromarray(np.dstack([np.full((SIZE, SIZE, 3), 128, np.uint8), alpha]), "RGBA").save(path)
    return path


def test_transparent_background_is_not_a_feature(tmp_path):
    tex = _island_on_transparent(tmp_path, [(90, 90), (150, 150)])
    rows = [_row("A", 0, 1, _square(0.25, 0.25, 0.75, 0.75))]
    assert count_features_per_face(rows, tex, expected={"A": 2}, tile=1001) == []
    m = measure_features_per_face(rows, tex, tile=1001)
    assert [(c["name"], c["face"], c["count"]) for c in m["counts"]] == [("A", 0, 2)]
    assert m["border_features"] == 1 and m["findings"] == []


def test_border_blob_never_counted_any_edge(tmp_path):
    # generated: a blob touching each edge (and a corner) is excluded; an interior hole is counted
    for rows_, cols_ in [((0, 5), (100, 110)), ((251, 256), (100, 110)), ((100, 110), (0, 5)),
                         ((100, 110), (251, 256)), ((0, 4), (0, 4)), ((250, 256), (250, 256))]:
        alpha = np.full((SIZE, SIZE), 255, np.uint8)
        alpha[rows_[0]:rows_[1], cols_[0]:cols_[1]] = 0
        alpha[60:66, 60:66] = 0
        path = tmp_path / "edge.png"
        Image.fromarray(np.dstack([np.full((SIZE, SIZE, 3), 128, np.uint8), alpha]), "RGBA").save(path)
        m = measure_features_per_face([_row("F", 0, 1, _square(0, 0, 1, 1))], path, tile=1001)
        assert m["counts"][0]["count"] == 1 and m["border_features"] == 1, (rows_, cols_)
        assert m["findings"] == []


@pytest.mark.parametrize("uv", [
    [(0, 0), (1, 1), (1, 0), (0, 1)],          # self-intersecting bow-tie
    [(0.1, 0.1), (0.5, 0.5), (0.9, 0.9)],      # zero area, collinear
    [(0.2, 0.2), (0.2, 0.2), (0.2, 0.2)],      # zero area, one point
    [(0.1, 0.7), (0.5, 0.3), (0.9, 0.7), (0.3, 0.1)],  # pinched: vertex 1 on edge 2-3, shapely says valid
    [(0.1, 0.1), (0.9, 0.1), (0.5, 0.1 + 1e-9)],      # sliver below tolerance
])
def test_invalid_polygon_is_reported(tmp_path, uv):
    tex = _opaque_with_hole(tmp_path, (300, 300), (300, 300))  # no features
    out = count_features_per_face([_row("X", 0, 1, uv)], tex, expected={"X": 0})
    assert [(f.name, f.status, f.data["face"]) for f in out] == [("uv_features.invalid_polygon", "fail", 0)]
    out = count_features_per_face([_row("X", 0, 1, uv)], tex)
    assert [f.name for f in out] == ["uv_features.invalid_polygon"]


def test_expected_none_returns_counts(tmp_path, csv):
    tex = _texture(tmp_path)
    m = measure_features_per_face(read_uv_csv(csv), tex)
    assert m["findings"] == []
    assert [(c["name"], c["face"], c["material"], c["count"]) for c in m["counts"]] == [
        ("A", 0, "1", 3), ("B", 0, "2", 5)]
    assert count_features_per_face(read_uv_csv(csv), tex) == m["findings"]
    assert "expected=None" in count_features_per_face.__doc__


def test_combined_background_invalid_and_counts(tmp_path):
    # all three #1078 fixes together with the earlier unassigned / tie rules
    tex = _island_on_transparent(tmp_path, [(90, 90), (150, 150), (66, 180)])
    rows = [_row("A", 0, 1, _square(0.25, 0.25, 0.75, 0.6)), _row("Z", 0, 1, [(0, 0), (1, 1), (1, 0), (0, 1)])]
    m = measure_features_per_face(rows, tex, expected={"A": 1, "Z": 0})
    assert sorted(f.name for f in m["findings"]) == ["uv_features.invalid_polygon", "uv_features.unassigned"]
    assert [(c["name"], c["count"]) for c in m["counts"]] == [("A", 1)]
    assert m["border_features"] == 1


@pytest.mark.parametrize("uv, observed", [
    ([(0.2, 10.2), (0.8, 10.2), (0.8, 10.8)], "tile 1101"),            # v_tile = 10: was None before #1337
    ([(-0.8, 0.2), (-0.2, 0.2), (-0.2, 0.8)], "centroid outside UDIM grid"),
    ([(10.2, 0.2), (10.8, 0.2), (10.8, 0.8)], "centroid outside UDIM grid")])
def test_face_outside_regulation_grid_is_wrong_tile_never_a_crash(tmp_path, uv, observed):
    """#1337: udim_of no longer returns None; off-grid and v_tile >= 10 faces stay one wrong_tile finding."""
    for tile in (1001, None):
        out = count_features_per_face([_row("A", 0, 1, uv)], _texture(tmp_path), tile=tile)
        assert [f.name for f in out] == ["uv_features.wrong_tile"], out
        assert observed in out[0].observed
