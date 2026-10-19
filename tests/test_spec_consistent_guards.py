"""Unit tests for Spec.consistent and extract_exterior input guards (synthetic data)."""

import copy
import json
from pathlib import Path
import re

import pytest

np = pytest.importorskip("numpy")
shapely = pytest.importorskip("shapely")
from shapely.geometry import MultiPolygon, Polygon

from dt_ai.geometry.exterior import extract_exterior
from dt_ai.spec.model import Spec

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "spec-b01-v0.3.json"


@pytest.fixture
def b01_fixture() -> dict:
    """Return a fresh dictionary loaded via json.load (not deepcopied until test)."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_unmutated_b01_validates(b01_fixture: dict):
    spec = Spec.model_validate(b01_fixture)
    assert spec.id == "bench-b01-box" and spec.spec_version == "0.3"
    assert len(spec.levels) == 3 and len(spec.floors) == 2


# ---------------------------------------------------------------------------
# Spec.consistent Guard Cases & Helpers
# ---------------------------------------------------------------------------

def _valid_decor(**overrides) -> dict:
    item = {
        "kind": "band", "level": "L0", "wall": 0, "x_m": 1.0, "w_m": 1.0,
        "z_m": 1.0, "h_m": 0.5, "projection_m": 0.2, "texture": False,
    }
    item.update(overrides)
    return item


def _valid_roof_structure(**overrides) -> dict:
    item = {
        "kind": "screen", "outline": [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]], "z_top_m": 8.0,
    }
    item.update(overrides)
    return item


def _mut_plate_gap(d: dict):
    d["plate_gap_m"], d["weld_m"] = 0.002, 0.003


def _mut_terrace_version(d: dict):
    d["terraces"] = [{"level": "L1", "parapet_h_m": 0.5}]


def _mut_decor_version(d: dict):
    d["decor"] = [_valid_decor()]


def _mut_roof_structures_version(d: dict):
    d["roof_structures"] = [_valid_roof_structure()]


def _mut_parapet_thickness_version(d: dict):
    d["roof"]["parapet_thickness_m"] = 0.3


def _mut_old_opening_depth_v02(d: dict):
    d["spec_version"] = "0.2"
    d["floors"][0]["openings"][0].pop("glass_w", None)
    d["floors"][0]["openings"][0].pop("glass_h", None)
    d["floors"][0]["openings"][0]["depth_m"] = None


def _mut_old_opening_depth_v01(d: dict):
    d["spec_version"] = "0.1"
    d["floors"][0]["openings"][0].pop("glass_w", None)
    d["floors"][0]["openings"][0].pop("glass_h", None)
    d["floors"][0]["openings"][0]["depth_m"] = None


def _mut_glass_version_v02(d: dict):
    d["spec_version"] = "0.2"
    d["floors"][0]["openings"][0].update({"depth_m": 0.2, "glass_w": 1.36})


def _mut_across_level_v01(d: dict):
    d["spec_version"] = "0.1"
    d["floors"][0]["openings"][0].pop("glass_w", None)
    d["floors"][0]["openings"][0].pop("glass_h", None)
    d["floors"][0]["openings"][0].update({"depth_m": 0.2, "level_from": "L0", "level_to": "L1"})


def _mut_roof_structure_top_not_above(d: dict):
    d["spec_version"] = "0.7"
    d["roof_structures"] = [_valid_roof_structure(z_top_m=6.6)]


def _mut_terrace_first_floor(d: dict):
    d["spec_version"] = "0.4"
    d["terraces"] = [{"level": "L0", "parapet_h_m": 0.5}]


def _mut_terrace_roof(d: dict):
    d["spec_version"] = "0.4"
    d["terraces"] = [{"level": "roof", "parapet_h_m": 0.5}]


def _mut_terrace_duplicate(d: dict):
    d["spec_version"] = "0.4"
    d["terraces"] = [{"level": "L1", "parapet_h_m": 0.5}, {"level": "L1", "parapet_h_m": 0.6}]


def _mut_duplicate_level_names(d: dict):
    d["levels"].insert(2, {"name": "extra", "elev_m": 4.0})
    d["levels"].insert(3, {"name": "extra", "elev_m": 5.0})


def _mut_unsorted_elevations(d: dict):
    d["levels"][0]["elev_m"] = 5.0


def _mut_unknown_floor_level(d: dict):
    d["floors"][0]["level"] = "LX"


def _mut_unknown_floor_typical_of(d: dict):
    d["floors"][1]["typical_of"] = "LX"


def _mut_unknown_floor_repeat_to(d: dict):
    d["floors"][1]["repeat_to"] = "LX"


def _mut_unpaired_opening_level_from(d: dict):
    d["floors"][0]["openings"][0].update({"level_from": "L0", "level_to": None})


def _mut_unpaired_opening_level_to(d: dict):
    d["floors"][0]["openings"][0].update({"level_from": None, "level_to": "L1"})


def _mut_wrong_opening_level_from(d: dict):
    d["floors"][0]["openings"][0].update({"level_from": "L1", "level_to": "roof"})


def _mut_opening_level_to_unknown(d: dict):
    d["floors"][0]["openings"][0].update({"level_from": "L0", "level_to": "L_UNKNOWN"})


def _mut_opening_level_to_same(d: dict):
    d["floors"][0]["openings"][0].update({"level_from": "L0", "level_to": "L0"})


def _mut_opening_level_to_below(d: dict):
    d["levels"].insert(0, {"name": "B1", "elev_m": -3.0})
    d["floors"][0]["openings"][0].update({"level_from": "L0", "level_to": "B1"})


def _mut_typical_of_not_full(d: dict):
    d["levels"].insert(2, {"name": "L2", "elev_m": 5.0})
    d["floors"].append({"level": "L2", "typical_of": "L1"})


def _mut_typical_of_same_level(d: dict):
    d["floors"][1]["typical_of"] = "L1"


def _mut_typical_of_level_above(d: dict):
    d["levels"].insert(2, {"name": "L2", "elev_m": 5.0})
    d["floors"].append({"level": "L2", "contour": list(d["floors"][0]["contour"])})
    d["floors"][1]["typical_of"] = "L2"


def _mut_typical_floor_with_openings(d: dict):
    d["floors"][1]["openings"] = copy.deepcopy(d["floors"][0]["openings"])


def _mut_repeat_to_below(d: dict):
    d["floors"][1]["repeat_to"] = "L0"


def _mut_floor_reaches_roof_via_repeat(d: dict):
    d["floors"][1]["repeat_to"] = "roof"


def _mut_floor_defined_at_roof(d: dict):
    d["floors"].append({"level": "roof", "contour": list(d["floors"][0]["contour"])})


def _mut_duplicate_level_owners(d: dict):
    d["floors"].append({"level": "L0", "contour": [[0, 0], [5, 0], [5, 5], [0, 5]]})


def _mut_decor_on_roof(d: dict):
    d["spec_version"] = "0.5"
    d["decor"] = [_valid_decor(level="roof")]


def _mut_decor_unknown_level(d: dict):
    d["spec_version"] = "0.5"
    d["decor"] = [_valid_decor(level="LX")]


def _mut_decor_no_floor(d: dict):
    d["spec_version"] = "0.5"
    d["levels"].insert(2, {"name": "L_empty", "elev_m": 4.5})
    d["decor"] = [_valid_decor(level="L_empty")]


def _mut_decor_invalid_wall(d: dict):
    d["spec_version"] = "0.5"
    d["decor"] = [_valid_decor(wall=10)]


SPEC_GUARD_CASES = [
    pytest.param(_mut_plate_gap, re.escape("plate_gap_m 0.002 m must be larger than weld_m 0.003 m"), id="plate-gap-le-weld"),
    pytest.param(_mut_terrace_version, re.escape("terraces need spec_version 0.4"), id="version-gate-terrace"),
    pytest.param(_mut_decor_version, re.escape("decor needs spec_version 0.5"), id="version-gate-decor"),
    pytest.param(_mut_roof_structures_version, re.escape("roof_structures need spec_version 0.7"), id="version-gate-roof-structures"),
    pytest.param(_mut_parapet_thickness_version, re.escape("roof.parapet_thickness_m needs spec_version 0.6"), id="version-gate-parapet-thickness"),
    pytest.param(_mut_old_opening_depth_v02, re.escape("spec 0.2: every opening has depth_m (optional from 0.3)"), id="version-gate-opening-depth-v02"),
    pytest.param(_mut_old_opening_depth_v01, re.escape("spec 0.1: every opening has depth_m (optional from 0.3)"), id="version-gate-opening-depth-v01"),
    pytest.param(_mut_glass_version_v02, re.escape("glass_w / glass_h need spec_version 0.3"), id="version-gate-glass-v02"),
    pytest.param(_mut_across_level_v01, re.escape("openings across levels need spec_version 0.2"), id="version-gate-across-level-v01"),
    pytest.param(_mut_roof_structure_top_not_above, re.escape("roof structure: top 6.6 m is not above the roof level"), id="roof-structure-top-not-above-roof"),
    pytest.param(_mut_terrace_first_floor, re.escape("terrace at L0: a terrace lies at a level between the first and the roof"), id="terrace-invalid-level-first-floor"),
    pytest.param(_mut_terrace_roof, re.escape("terrace at roof: a terrace lies at a level between the first and the roof"), id="terrace-invalid-level-roof"),
    pytest.param(_mut_terrace_duplicate, re.escape("terrace at L1 is given twice"), id="terrace-duplicate-level"),
    pytest.param(_mut_duplicate_level_names, re.escape("level names must be unique"), id="duplicate-level-names"),
    pytest.param(_mut_unsorted_elevations, re.escape("levels must be sorted by elevation"), id="unsorted-elevations"),
    pytest.param(_mut_unknown_floor_level, re.escape("floor refers to unknown level LX"), id="unknown-floor-level"),
    pytest.param(_mut_unknown_floor_typical_of, re.escape("floor refers to unknown level LX"), id="unknown-floor-typical-of"),
    pytest.param(_mut_unknown_floor_repeat_to, re.escape("floor refers to unknown level LX"), id="unknown-floor-repeat-to"),
    pytest.param(_mut_unpaired_opening_level_from, re.escape("floor L0: an opening across levels needs level_from and level_to"), id="unpaired-opening-level-from-only"),
    pytest.param(_mut_unpaired_opening_level_to, re.escape("floor L0: an opening across levels needs level_from and level_to"), id="unpaired-opening-level-to-only"),
    pytest.param(_mut_wrong_opening_level_from, re.escape("floor L0: level_from must be the floor and level_to a level above it"), id="wrong-opening-level-from"),
    pytest.param(_mut_opening_level_to_unknown, re.escape("floor L0: level_from must be the floor and level_to a level above it"), id="opening-level-to-unknown"),
    pytest.param(_mut_opening_level_to_same, re.escape("floor L0: level_from must be the floor and level_to a level above it"), id="opening-level-to-same-as-from"),
    pytest.param(_mut_opening_level_to_below, re.escape("floor L0: level_from must be the floor and level_to a level above it"), id="opening-level-to-below-from"),
    pytest.param(_mut_typical_of_not_full, re.escape("floor L2: typical_of must be a full floor below it"), id="typical-of-not-full-floor"),
    pytest.param(_mut_typical_of_same_level, re.escape("floor L1: typical_of must be a full floor below it"), id="typical-of-same-level"),
    pytest.param(_mut_typical_of_level_above, re.escape("floor L1: typical_of must be a full floor below it"), id="typical-of-level-above"),
    pytest.param(_mut_typical_floor_with_openings, re.escape("floor L1: a typical entry carries no openings of its own"), id="typical-floor-with-own-openings"),
    pytest.param(_mut_repeat_to_below, re.escape("floor L1: repeat_to is below the floor"), id="repeat-to-below-floor"),
    pytest.param(_mut_floor_reaches_roof_via_repeat, re.escape("floor L1: floors stop below the top level roof"), id="floor-reaches-roof-via-repeat"),
    pytest.param(_mut_floor_defined_at_roof, re.escape("floor roof: floors stop below the top level roof"), id="floor-defined-at-roof"),
    pytest.param(_mut_duplicate_level_owners, re.escape("level L0 is given twice (L0 and L0)"), id="duplicate-level-owners"),
    pytest.param(_mut_decor_on_roof, re.escape("decor at roof: a decor element stands on a floor level"), id="decor-stands-on-roof"),
    pytest.param(_mut_decor_unknown_level, re.escape("decor at LX: a decor element stands on a floor level"), id="decor-unknown-level"),
    pytest.param(_mut_decor_no_floor, re.escape("decor at L_empty: no floor at that level"), id="decor-no-floor-at-level"),
    pytest.param(_mut_decor_invalid_wall, re.escape("decor at L0: wall 10, the contour has 4"), id="decor-invalid-wall-index"),
]


@pytest.mark.parametrize("mutator,expected_match", SPEC_GUARD_CASES)
def test_spec_consistent_guards(b01_fixture: dict, mutator, expected_match: str):
    spec_dict = copy.deepcopy(b01_fixture)
    mutator(spec_dict)
    with pytest.raises(ValueError, match=expected_match):
        Spec.model_validate(spec_dict)


# ---------------------------------------------------------------------------
# Exterior Adapter Input Guards & Wall-Top Behavior
# ---------------------------------------------------------------------------

def synthetic_exterior_fixture() -> dict:
    owner = np.ones((3, 3, 1), dtype=np.int32)
    owner[1, 1, :] = 0
    return {
        "owner": owner,
        "x": np.array([0.0, 0.2, 1.8, 2.0]),
        "y": np.array([0.0, 0.2, 1.8, 2.0]),
        "z": np.array([0.0, 2.9]),
        "angle": 0.0,
    }


def synthetic_exterior_params(**overrides) -> dict:
    params = {
        "height_m": 3.0, "coordinate_budget_m": 0.001, "microgap_closure_m": 0.001,
        "opening_match_m": 0.005, "window_plane_distance_m": 0.5,
        "wall_top_policy": "extend_to_height_record_unmatched_top_gaps",
        "units": "m", "height_basis": "synthetic fixture, not real project data",
    }
    params.update(overrides)
    return params


def synthetic_shell_grid() -> dict:
    x = np.array([0.0, 0.2, 1.0, 2.0, 3.8, 4.0])
    y = np.array([0.0, 0.2, 1.8, 2.0])
    z = np.array([0.0, 0.8, 2.9])
    owner = np.zeros((len(x) - 1, len(y) - 1, len(z) - 1), dtype=np.int32)
    owner[0, :, :] = 11   # left
    owner[-1, :, :] = 12  # right
    owner[:, 0, :] = 13   # front
    owner[:, -1, :] = 14  # back
    owner[2, 0, 1] = 0    # missing front upper cell
    return {"owner": owner, "x": x, "y": y, "z": z, "angle": 0.0}


def test_exterior_positive_baseline_preserves_inputs():
    data = synthetic_exterior_fixture()
    saved = {k: data[k].copy() for k in ("owner", "x", "y", "z")}
    windows = [{"id": "synthetic-win-base", "min": [0.0, 0.0, 0.5], "max": [0.2, 0.2, 1.5]}]
    windows_copy = copy.deepcopy(windows)

    result, report = extract_exterior(data, windows, **synthetic_exterior_params())

    assert len(result["vertices"]) > 0 and len(result["faces"]) > 0
    assert report["facade_runs"] == 4
    for k in ("owner", "x", "y", "z"):
        assert np.array_equal(data[k], saved[k])
    assert windows == windows_copy


@pytest.mark.parametrize(
    "microgap_val",
    [-1.0, float("nan"), float("inf"), -float("inf")],
    ids=["negative-microgap", "nan-microgap", "pos-inf-microgap", "neg-inf-microgap"],
)
def test_exterior_invalid_microgap_rejected(microgap_val: float):
    data = synthetic_exterior_fixture()
    params = synthetic_exterior_params(microgap_closure_m=microgap_val)
    with pytest.raises(ValueError, match=re.escape("Invalid microgap closure")):
        extract_exterior(data, [], **params)


INVALID_WINDOW_CASES = [
    pytest.param({"id": 101, "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0]}, id="non-string-id"),
    pytest.param({"id": "", "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0]}, id="empty-id"),
    pytest.param({"id": "synthetic-w1", "min": [0.0, 0.0], "max": [1.0, 1.0, 1.0]}, id="bad-min-shape-2d"),
    pytest.param({"id": "synthetic-w2", "min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0, 1.0]}, id="bad-max-shape-4d"),
    pytest.param({"id": "synthetic-w3", "min": [float("nan"), 0.0, 0.0], "max": [1.0, 1.0, 1.0]}, id="nan-in-min"),
    pytest.param({"id": "synthetic-w4", "min": [0.0, 0.0, 0.0], "max": [1.0, float("inf"), 1.0]}, id="inf-in-max"),
    pytest.param({"id": "synthetic-w5", "min": [2.0, 0.0, 0.0], "max": [1.0, 0.2, 1.0]}, id="reversed-bounds"),
]


@pytest.mark.parametrize("bad_window", INVALID_WINDOW_CASES)
def test_exterior_invalid_window_bounds_rejected(bad_window: dict):
    data = synthetic_exterior_fixture()
    with pytest.raises(ValueError, match=re.escape("Invalid explicitly selected window bounds")):
        extract_exterior(data, [bad_window], **synthetic_exterior_params())


def test_exterior_footprint_repair_split_guard_rejected(monkeypatch: pytest.MonkeyPatch):
    """Trigger footprint repair split guard via explicit fault injection (not natural geometry)."""
    data = synthetic_exterior_fixture()
    real_buffer = Polygon.buffer

    def split_buffer(self, distance, **kwargs):
        res = real_buffer(self, distance, **kwargs)
        if distance < 0:
            # Fault injection on negative-distance repair call (not demonstrated natural geometry)
            poly1 = shapely.box(0.0, 0.0, 1.0, 1.0)
            poly2 = shapely.box(2.0, 2.0, 3.0, 3.0)
            return MultiPolygon([poly1, poly2])
        return res

    monkeypatch.setattr(Polygon, "buffer", split_buffer)
    with pytest.raises(ValueError, match=re.escape("Exterior footprint repair split the component")):
        extract_exterior(data, [], **synthetic_exterior_params())


@pytest.mark.parametrize(
    "matched",
    [pytest.param(False, id="unmatched-gap-filled"), pytest.param(True, id="matched-gap-clipped-at-top")],
)
def test_exterior_wall_top_gap_unmatched_vs_matched(matched: bool):
    data = synthetic_shell_grid()
    saved_owner = data["owner"].copy()
    params = synthetic_exterior_params(height_m=3.0)
    windows = [{"id": "synthetic-window-top", "min": [1.0, 0.0, 0.8], "max": [2.0, 0.2, 2.9]}] if matched else []

    arrays, report = extract_exterior(data, windows, **params)
    assert np.array_equal(data["owner"], saved_owner)

    quads = arrays["vertices"][arrays["faces"]]
    front_quads = quads[np.all(np.isclose(quads[:, :, 1], 0.0), axis=1)]
    front_area = sum((f[:, 0].max() - f[:, 0].min()) * (f[:, 2].max() - f[:, 2].min()) for f in front_quads)

    overlap_area = sum(
        np.prod(np.maximum(0.0, np.minimum(f[:, [0, 2]].max(axis=0), [2.0, 3.0]) - np.maximum(f[:, [0, 2]].min(axis=0), [1.0, 0.8])))
        for f in front_quads
    )
    all_openings = [o for run in report["profiles"] for o in run["openings"]]

    if not matched:
        assert len(report["excluded_wall_top_gaps"]) == 1
        gap = report["excluded_wall_top_gaps"][0]
        assert gap["reason"] == "unmatched wall-top termination; façade uses full level height"
        assert np.allclose(gap["source_bounds_m"], [1.0, 0.8, 2.0, 2.9])
        assert len(all_openings) == 0
        assert np.isclose(front_area, 12.0)
        assert np.isclose(overlap_area, (2.0 - 1.0) * (3.0 - 0.8))
    else:
        assert len(report["excluded_wall_top_gaps"]) == 0
        assert len(all_openings) == 1
        op = all_openings[0]
        assert op["kind"] == "clipped_at_top"
        assert op["source_window_ids"] == ["synthetic-window-top"]
        op_geom = shapely.from_geojson(op["geometry_geojson"])
        assert np.allclose(op_geom.bounds, [1.0, 0.8, 2.0, 3.0])
        assert np.isclose(overlap_area, 0.0)
        assert np.isclose(front_area, 12.0 - 2.2)
