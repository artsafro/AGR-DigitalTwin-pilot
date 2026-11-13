"""#1337: one shared UDIM tile function (adapters/max/agr_tools/udimtile_core.py) and its four call sites.

UDIM = 1001 + u_tile + 10 * v_tile (Blender manual, "UDIM"; reg p.23, p.31 §2.1.3). Domain: u in [0, 10), v >= 0,
finite. Tiles are half-open [k, k + 1): a point exactly on u = 1.0 is in the next tile. Rows v_tile >= 10 are
defined (1101, 1102, ...); the regulation range 1001..1100 is checked by the callers. Outside the domain:
UdimDomainError (a ValueError), never None.
"""
import importlib.util
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "adapters/max/agr_tools/udimtile_core.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ut():
    return _load(CORE, "agr_tools_udimtile_core_test")


# ---- point ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("u, v, tile", [
    (0.5, 0.5, 1001), (9.5, 0.5, 1010), (0.5, 1.5, 1011), (9.5, 9.5, 1100), (3.25, 4.75, 1044)])
def test_tile_interiors(ut, u, v, tile):
    assert ut.udim_tile(u, v) == tile


@pytest.mark.parametrize("u, v, tile", [
    (0.0, 0.0, 1001), (1.0, 0.5, 1002), (0.5, 1.0, 1011), (1.0, 1.0, 1012), (9.0, 0.0, 1010),
    (math.nextafter(10.0, 0.0), 0.0, 1010), (math.nextafter(1.0, 0.0), 0.5, 1001), (0, 0, 1001)])
def test_exact_boundaries_are_half_open(ut, u, v, tile):
    assert ut.udim_tile(u, v) == tile


@pytest.mark.parametrize("u, v, tile", [(0.5, 10.0, 1101), (9.5, 10.5, 1110), (0.0, 12.0, 1121)])
def test_v_tile_10_and_above_is_defined(ut, u, v, tile):
    assert ut.udim_tile(u, v) == tile


@pytest.mark.parametrize("u, v", [
    (-0.1, 0.5), (0.5, -0.1), (-1e-12, 0.0), (10.0, 0.5), (12.0, 0.0), (math.nan, 0.5), (0.5, math.nan),
    (math.inf, 0.5), (0.5, math.inf), (-math.inf, 0.0), (True, 0.5), (0.5, False), ("0.5", 0.5), (None, 0.5)])
def test_outside_domain_is_an_error_never_none(ut, u, v):
    with pytest.raises(ut.UdimDomainError) as err:
        ut.udim_tile(u, v)
    assert isinstance(err.value, ValueError)


# ---- integer cell / origin ------------------------------------------------------------------------------------
def test_cell_and_origin_round_trip(ut):
    assert ut.udim_of_cell(0, 0) == 1001 and ut.udim_of_cell(9, 0) == 1010 and ut.udim_of_cell(0, 1) == 1011
    assert ut.udim_of_cell(0, 10) == 1101
    for tile in range(1001, 1301):
        u0, v0 = ut.tile_origin(tile)
        assert ut.udim_of_cell(u0, v0) == tile == ut.udim_tile(u0 + 0.5, v0 + 0.5) == ut.udim_tile(u0, v0)


@pytest.mark.parametrize("cu, cv", [(10, 0), (-1, 0), (0, -1), (1.5, 0), (True, 0), (0, None), (math.nan, 0)])
def test_cell_outside_domain_is_an_error(ut, cu, cv):
    with pytest.raises(ut.UdimDomainError):
        ut.udim_of_cell(cu, cv)


@pytest.mark.parametrize("tile", [1000, 0, -5, 1001.0, True, "1001", None])
def test_origin_rejects_non_tiles(ut, tile):
    with pytest.raises(ut.UdimDomainError):
        ut.tile_origin(tile)


# ---- face -----------------------------------------------------------------------------------------------------
def test_face_on_tile_borders_belongs_to_its_tile(ut):
    """Every corner of [1, 2] x [0, 1] lies on a tile line; the face is tile 1002, not a corner vote."""
    square = [(1.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0)]
    assert ut.face_tile(square) == 1002
    assert ut.face_tile([(9.0, 9.0), (10.0, 9.0), (10.0, 10.0), (9.0, 10.0)]) == 1100


def test_face_crossing_a_border(ut):
    across = [(0.5, 0.2), (1.5, 0.2), (1.5, 0.8), (0.5, 0.8)]   # centroid exactly on u = 1.0
    with pytest.raises(ut.UdimCrossTileError) as err:
        ut.face_tile(across)
    assert isinstance(err.value, ut.UdimDomainError) and "1002" in str(err.value)
    assert ut.face_tile(across, strict=False) == 1002   # defined: the tile of the centroid
    up = [(0.2, 0.9), (0.8, 0.9), (0.8, 1.6)]
    with pytest.raises(ut.UdimCrossTileError):
        ut.face_tile(up)


def test_face_within_tolerance_is_not_crossing(ut):
    assert ut.face_tile([(1.0 - 1e-9, 0.1), (1.9, 0.1), (1.9, 0.9)]) == 1002


@pytest.mark.parametrize("uvs", [
    [], [(0.5, 0.5)], [(0.5, 0.5), (0.6, 0.6)], [(0.1, 0.1), (math.nan, 0.2), (0.3, 0.3)],
    [(-0.5, 0.1), (-0.2, 0.1), (-0.2, 0.4)], [(10.1, 0.1), (10.5, 0.1), (10.5, 0.4)], None, "abc",
    [(0.1, 0.1, 0.0), (0.2, 0.2), (0.3, 0.1)]])
def test_face_outside_domain_or_malformed_is_an_error(ut, uvs):
    with pytest.raises(ut.UdimDomainError):
        ut.face_tile(uvs)
    with pytest.raises(ut.UdimDomainError):
        ut.face_tile(uvs, strict=False)


def test_probe_random_points_match_formula(ut):
    """Probe: for 20 000 random finite points the tile is the formula, or an error outside the domain."""
    rng = random.Random(1337)
    errors = ok = 0
    for _ in range(20000):
        u = rng.choice([rng.uniform(-2, 12), float(rng.randint(-1, 11))])
        v = rng.choice([rng.uniform(-2, 14), float(rng.randint(-1, 13))])
        if 0 <= u < 10 and v >= 0:
            assert ut.udim_tile(u, v) == 1001 + math.floor(u) + 10 * math.floor(v)
            ok += 1
        else:
            with pytest.raises(ut.UdimDomainError):
                ut.udim_tile(u, v)
            errors += 1
    assert ok > 5000 and errors > 3000


# ---- call sites -----------------------------------------------------------------------------------------------
def test_twinqa_udim_of_routes_to_shared_function(ut):
    from twinqa import uv
    assert Path(uv._udimtile.__file__).resolve() == CORE.resolve()
    assert uv.udim_of([[0.1, 10.1], [0.9, 10.1], [0.9, 10.9]]) == 1101   # was None before #1337
    assert uv.udim_of([[0.5, 0.2], [1.5, 0.2], [1.5, 0.8]]) == 1002      # centroid tile; cross_tile is face_issue's
    for bad in ([[-0.5, 0.1], [-0.2, 0.1], [-0.2, 0.4]], [[10.2, 0.1], [10.5, 0.1], [10.5, 0.4]],
                [[0.1, math.nan], [0.2, 0.2], [0.3, 0.1]]):
        with pytest.raises(ValueError):
            uv.udim_of(bad)


def test_uvlayout_udim_of_cell_routes_to_shared_function(ut):
    lay = _load(ROOT / "adapters/max/agr_tools/uvlayout_core.py", "agr_tools_uvlayout_core_udimtile_test")
    assert lay.udim_of_cell(3, 2) == 1024 and lay.udim_of_cell(0, 10) == 1101
    for cu, cv in ((10, 0), (-1, 0), (0, -1)):
        with pytest.raises(ValueError):
            lay.udim_of_cell(cu, cv)
    assert lay.udimtile.udim_of_cell is not None
    assert Path(lay.udimtile.__file__).resolve() == CORE.resolve()
    assert lay.piece_tile_or_zero([[1.2, 0.2], [1.8, 0.2], [1.8, 0.8]]) == 1002
    assert lay.piece_tile_or_zero([[-0.8, 0.2], [-0.2, 0.2], [-0.2, 0.8]]) == 0     # vpm.build report label kept
    assert lay.piece_tile_or_zero([[0.2, 10.2], [0.8, 10.2], [0.8, 10.8]]) == 1101  # v_tile 10: 1101, as before #1337


def test_joint_continuity_v008_uses_shared_function():
    src = (ROOT / "jobs/elv-tc-vpm/scripts/joint_continuity_v008.py").read_text(encoding="utf-8")
    assert "udimtile_core.py" in src and "1001 + int(math.floor" not in src


def test_shared_module_ships_in_the_max_package():
    build = (ROOT / "tools/max/build_agr_tools.py").read_text(encoding="utf-8")
    install = (ROOT / "adapters/max/agr_tools/install.ms").read_text(encoding="utf-8-sig")
    assert "'udimtile_core.py'" in build and '"udimtile_core.py"' in install


def test_core_is_stdlib_only():
    src = CORE.read_text(encoding="utf-8")
    imports = {line.split()[1].split(".")[0] for line in src.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"math", "numbers", "__future__"}, imports
