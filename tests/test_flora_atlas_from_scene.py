"""One Flora atlas from a placed scene: packer, UV remap, fail-closed checks."""

import importlib.util
import json
import math
import random
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "library" / "flora_atlas_from_scene.py"
MAF = ROOT / "tools" / "materials" / "atlas_maf.py"
RANGES = {
    "tree": (101, 199),
    "bush": (201, 299),
    "hedge": (301, 399),
    "flower": (401, 499),
    "climber": (501, 599),
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def flora():
    assert TOOL.is_file(), TOOL
    return _load(TOOL, "flora_atlas_from_scene")


@pytest.fixture(scope="module")
def maf():
    assert MAF.is_file(), MAF
    return _load(MAF, "atlas_maf_for_flora")


def _png(path: Path, size: tuple[int, int], color, mode: str) -> Path:
    image = Image.new(mode, size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def _species(latin, kind, material_id, diffuse, opacity, review="approved"):
    return {
        "material_id": material_id,
        "latin": latin,
        "type": kind,
        "maps": {
            "diffuse": str(diffuse),
            "opacity": str(opacity),
            "review_status": review,
        },
    }


def _catalogue(path: Path, species: list[dict]) -> Path:
    payload = {
        "schema": "flora-library-v1",
        "library_file": "C:/x/flora-library/unused.max",
        "id_ranges": {name: list(bounds) for name, bounds in RANGES.items()},
        "retired_ids": [],
        "species": species,
        "gaps": {},
        "counts": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _scene(path: Path, objects: list[dict]) -> Path:
    path.write_text(
        json.dumps({"schema": "flora-placed-v1", "objects": objects}),
        encoding="utf-8",
    )
    return path


def _quad(material_id, uvs=None):
    return {
        "material_id": material_id,
        "uvs": uvs or [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    }


def _library(tmp_path: Path):
    maps = tmp_path / "maps"
    rows = [
        ("Tilia cordata", "tree", 101, (220, 40, 40), (64, 64)),
        ("Spiraea japonica", "bush", 201, (40, 160, 60), (48, 32)),
        ("Spiraea japonica 'Goldflame'", "bush", 202, (220, 140, 20), (40, 40)),
        ("Lavandula angustifolia", "flower", 401, (90, 40, 160), (36, 24)),
    ]
    species = []
    for latin, kind, material_id, color, size in rows:
        slug = latin.lower().replace(" ", "-").replace("'", "")
        diffuse = _png(maps / slug / "diffuse-v001.png", size, color, "RGB")
        opacity = _png(maps / slug / "opacity-v001.png", size, 255, "L")
        species.append(_species(latin, kind, material_id, diffuse, opacity))
    catalogue = _catalogue(tmp_path / "catalogue.json", species)
    return catalogue, {row[2]: row for row in rows}


def _outputs(tmp_path: Path):
    out = tmp_path / "atlas"
    return out / "T_SYNTH_Flora_d_1.png", out / "T_SYNTH_Flora_o_1.png", out / "flora-atlas.json"


def _build(flora, tmp_path, objects, **extra):
    catalogue, _rows = _library(tmp_path)
    scene = _scene(tmp_path / "scene.json", objects)
    diffuse, opacity, report = _outputs(tmp_path)
    result = flora.build_atlas(
        scene,
        catalogue,
        out_diffuse=diffuse,
        out_opacity=opacity,
        out_report=report,
        address="SYNTH",
        **extra,
    )
    return result, diffuse, opacity, report


def _overlaps(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def test_reuses_maf_packer(flora, maf):
    source = TOOL.read_text(encoding="utf-8")
    assert "atlas_maf" in source
    assert "pack_uniform_tiles" in source
    filename = flora.pack_uniform_tiles.__code__.co_filename.replace("\\", "/")
    assert filename.endswith("tools/materials/atlas_maf.py")
    assert maf.pack_uniform_tiles.__code__.co_code == flora.pack_uniform_tiles.__code__.co_code


def test_regression_material_ids_survive_remap(flora, tmp_path):
    """Regression: face material IDs are unchanged by the atlas remap."""
    objects = [
        {"name": "tilia-a", "faces": [_quad(101), _quad(101, [[0.2, 0.2], [0.8, 0.2], [0.5, 0.9]])]},
        {"name": "spiraea", "faces": [_quad(201)]},
        {"name": "goldflame", "faces": [_quad(202)]},
        {"name": "lavandula", "faces": [_quad(401)]},
    ]
    result, _diffuse, _opacity, report_path = _build(flora, tmp_path, objects)
    before = [face["material_id"] for obj in objects for face in obj["faces"]]
    remapped = flora.remap_faces(
        [face for obj in objects for face in obj["faces"]],
        {row["material_id"]: row["uv"] for row in result["ids"]},
    )
    assert [face["material_id"] for face in remapped] == before
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert [row["material_id"] for row in written["ids"]] == [101, 201, 202, 401]
    assert [(row["material_id"], row["species"]) for row in written["ids"]] == [
        (101, "Tilia cordata"),
        (201, "Spiraea japonica"),
        (202, "Spiraea japonica 'Goldflame'"),
        (401, "Lavandula angustifolia"),
    ]


def test_cultivars_keep_distinct_ids_and_tiles(flora, tmp_path):
    result, diffuse, _opacity, _report = _build(
        flora,
        tmp_path,
        [
            {"name": "parent", "faces": [_quad(201)]},
            {"name": "cultivar", "faces": [_quad(202)]},
        ],
    )
    tiles = {row["material_id"]: tuple(row["tile_px"]) for row in result["ids"]}
    assert set(tiles) == {201, 202}
    assert tiles[201] != tiles[202]
    assert not _overlaps(tiles[201], tiles[202])
    image = Image.open(diffuse)
    assert image.size == (2048, 2048)
    assert image.mode == "RGB"
    assert image.getpixel((tiles[201][0] + 1, tiles[201][1] + 1)) == (40, 160, 60)
    assert image.getpixel((tiles[202][0] + 1, tiles[202][1] + 1)) == (220, 140, 20)


def test_uv_roundtrip_within_tolerance(flora):
    rng = random.Random(217)
    tile = (0.125, 0.25, 0.5, 0.75)
    for _ in range(200):
        uv = (rng.random(), rng.random())
        mapped = flora.remap_uv(uv, tile)
        delta = flora.uv_roundtrip_delta(uv, mapped, tile)
        assert flora.uv_within_tolerance(delta, 1e-6)
        assert 0.0 <= mapped[0] <= 1.0
        assert 0.0 <= mapped[1] <= 1.0


def test_uv_exactly_at_tolerance_fails(flora):
    assert flora.uv_within_tolerance(1e-6, 1e-6) is False
    assert flora.uv_within_tolerance(1e-6 - 1e-12, 1e-6) is True
    with pytest.raises(flora.FloraAtlasError):
        flora.uv_within_tolerance(float("nan"), 1e-6)
    with pytest.raises(flora.FloraAtlasError):
        flora.uv_within_tolerance(float("inf"), 1e-6)
    with pytest.raises(flora.FloraAtlasError):
        flora.uv_within_tolerance(float("-inf"), 1e-6)


def test_tile_rects_disjoint_and_inside_unit_square(flora, tmp_path):
    result, _diffuse, _opacity, _report = _build(
        flora,
        tmp_path,
        [
            {"name": "a", "faces": [_quad(101)]},
            {"name": "b", "faces": [_quad(201)]},
            {"name": "c", "faces": [_quad(202)]},
            {"name": "d", "faces": [_quad(401)]},
        ],
    )
    rects = []
    for row in result["ids"]:
        u0, v0, u1, v1 = row["uv"]
        assert 0.0 <= u0 <= u1 <= 1.0
        assert 0.0 <= v0 <= v1 <= 1.0
        x, y, w, h = row["tile_px"]
        assert x >= 0 and y >= 0 and w > 0 and h > 0
        assert x + w <= 2048 and y + h <= 2048
        rects.append((u0, v0, u1 - u0, v1 - v0))
    for index, left in enumerate(rects):
        for right in rects[index + 1:]:
            assert not _overlaps(left, right)


def test_probe_never_second_atlas(flora):
    rng = random.Random(184)
    for count in range(1, 31):
        items = [
            {
                "key": f"s{index}",
            "width": rng.randint(64, 2048),
            "height": rng.randint(64, 2048),
            }
            for index in range(count)
        ]
        packed = flora.pack_uniform_tiles(items, 2048, padding_px=0, min_long_side=1)
        assert packed["atlas_count"] == 1
        assert packed["atlas_size"] == 2048
        assert len(packed["slots"]) == count
        assert "atlases" not in packed
        rects = [(slot["x"], slot["y"], slot["w"], slot["h"]) for slot in packed["slots"]]
        for slot in packed["slots"]:
            assert slot["x"] + slot["w"] <= 2048
            assert slot["y"] + slot["h"] <= 2048
        for index, left in enumerate(rects):
            for right in rects[index + 1:]:
                assert not _overlaps(left, right)


def test_probe_same_scale_factor(flora):
    items = [
        {"key": "wide", "width": 800, "height": 200},
        {"key": "tall", "width": 100, "height": 900},
        {"key": "square", "width": 640, "height": 640},
        {"key": "small", "width": 50, "height": 80},
    ]
    packed = flora.pack_uniform_tiles(items, 2048, padding_px=0, min_long_side=1)
    num = packed["scale_numerator"]
    den = packed["scale_denominator"]
    assert packed["scale_factor"] == num / den
    assert 0 < packed["scale_factor"] <= 1
    for slot in packed["slots"]:
        assert slot["content_w"] == slot["source_w"] * num // den
        assert slot["content_h"] == slot["source_h"] * num // den


def test_probe_tiles_at_most_2048(flora):
    rng = random.Random(2048)
    for _ in range(20):
        items = [
            {"key": f"p{index}", "width": rng.randint(32, 3000), "height": rng.randint(32, 3000)}
            for index in range(rng.randint(1, 12))
        ]
        packed = flora.pack_uniform_tiles(items, 2048, padding_px=8, min_long_side=1)
        assert packed["atlas_size"] == 2048
        assert packed["atlas_count"] == 1
        for slot in packed["slots"]:
            assert slot["content_x"] >= 0 and slot["content_y"] >= 0
            assert slot["content_x"] + slot["content_w"] <= 2048
            assert slot["content_y"] + slot["content_h"] <= 2048
            assert slot["w"] <= 2048 and slot["h"] <= 2048


def test_warning_below_min_tile_and_exact_boundary(flora):
    below = flora.pack_uniform_tiles(
        [{"key": "tiny", "width": 255, "height": 100}],
        2048,
        padding_px=0,
        min_long_side=256,
    )
    assert below["scale_factor"] == 1
    assert any("255" in warning and "256" in warning for warning in below["warnings"])
    exact = flora.pack_uniform_tiles(
        [{"key": "edge", "width": 256, "height": 128}],
        2048,
        padding_px=0,
        min_long_side=256,
    )
    assert exact["warnings"] == []
    assert exact["slots"][0]["content_w"] == 256
    squares = [
        {"key": f"q{index}", "width": 2048, "height": 2048}
        for index in range(64)
    ]
    grid = flora.pack_uniform_tiles(squares, 2048, padding_px=0, min_long_side=256)
    assert grid["atlas_count"] == 1
    assert {slot["content_w"] for slot in grid["slots"]} == {256}
    assert grid["warnings"] == []
    overflow = [
        {"key": f"q{index}", "width": 2048, "height": 2048}
        for index in range(65)
    ]
    tight = flora.pack_uniform_tiles(overflow, 2048, padding_px=0, min_long_side=256)
    assert tight["atlas_count"] == 1
    assert tight["slots"][0]["content_w"] < 256
    assert tight["warnings"]


def test_fail_closed_empty_partial_unsupported_nan(flora, tmp_path, capsys):
    catalogue, _rows = _library(tmp_path)
    diffuse, opacity, report = _outputs(tmp_path)

    def run(scene_payload, catalogue_path=catalogue):
        scene = tmp_path / "bad-scene.json"
        scene.write_text(json.dumps(scene_payload), encoding="utf-8")
        code = flora.main(
            [
                "--scene-json", str(scene),
                "--catalogue", str(catalogue_path),
                "--out-dir", str(tmp_path / "out-bad"),
                "--address", "SYNTH",
            ]
        )
        captured = capsys.readouterr()
        assert code != 0
        assert captured.err.startswith("error:")
        assert not diffuse.exists()
        assert not opacity.exists()
        assert not report.exists()
        assert not (tmp_path / "out-bad").exists()

    run({"schema": "flora-placed-v1", "objects": []})
    run({"schema": "flora-placed-v1", "objects": [{"name": "empty", "faces": []}]})
    run({"schema": "flora-placed-v1", "objects": [{"name": "no-id", "faces": [{"uvs": [[0, 0], [1, 0], [0, 1]]}]}]})
    run({"schema": "flora-placed-v1", "objects": [{"name": "low", "faces": [_quad(50)]}]})
    run({"schema": "flora-placed-v1", "objects": [{"name": "high", "faces": [_quad(600)]}]})
    run({"schema": "flora-placed-v1", "objects": [{"name": "missing", "faces": [_quad(150)]}]})
    run({"schema": "flora-placed-v1", "objects": [{"name": "text", "faces": [_quad("101")]}]})
    run({
        "schema": "flora-placed-v1",
        "objects": [{"name": "nan", "faces": [_quad(101, [[float("nan"), 0.0], [1.0, 0.0], [0.0, 1.0]])]}],
    })
    run({
        "schema": "flora-placed-v1",
        "objects": [{"name": "inf", "faces": [_quad(101, [[0.0, float("inf")], [1.0, 0.0], [0.0, 1.0]])]}],
    })

    partial = json.loads(catalogue.read_text(encoding="utf-8"))
    partial["species"][0]["maps"]["opacity"] = None
    partial_path = tmp_path / "partial.json"
    partial_path.write_text(json.dumps(partial), encoding="utf-8")
    run(
        {"schema": "flora-placed-v1", "objects": [{"name": "tilia", "faces": [_quad(101)]}]},
        partial_path,
    )

    pending = json.loads(catalogue.read_text(encoding="utf-8"))
    pending["species"][0]["maps"]["review_status"] = "pending_review"
    pending_path = tmp_path / "pending.json"
    pending_path.write_text(json.dumps(pending), encoding="utf-8")
    run(
        {"schema": "flora-placed-v1", "objects": [{"name": "tilia", "faces": [_quad(101)]}]},
        pending_path,
    )

    with pytest.raises(flora.FloraAtlasError):
        flora.pack_uniform_tiles([], 2048, padding_px=0, min_long_side=256)
    with pytest.raises(flora.FloraAtlasError):
        flora.pack_uniform_tiles(
            [{"key": "bad", "width": float("nan"), "height": 10}],
            2048,
            padding_px=0,
            min_long_side=256,
        )
    with pytest.raises(flora.FloraAtlasError):
        flora.pack_uniform_tiles(
            [{"key": "bad", "width": 10, "height": float("inf")}],
            2048,
            padding_px=0,
            min_long_side=256,
        )
    with pytest.raises(flora.FloraAtlasError):
        flora.build_atlas(
            _scene(tmp_path / "ok-scene.json", [{"name": "a", "faces": [_quad(101)]}]),
            catalogue,
            out_diffuse=diffuse,
            out_opacity=opacity,
            out_report=report,
            address="SYNTH",
            atlas_size=4096,
        )


def test_output_alias_writes_nothing(flora, tmp_path, capsys):
    catalogue, _rows = _library(tmp_path)
    scene = _scene(tmp_path / "scene.json", [{"name": "a", "faces": [_quad(101)]}])
    source = Path(json.loads(catalogue.read_text(encoding="utf-8"))["species"][0]["maps"]["diffuse"])
    before = source.read_bytes()
    code = flora.main(
        [
            "--scene-json", str(scene),
            "--catalogue", str(catalogue),
            "--out-dir", str(tmp_path / "unused"),
            "--address", "SYNTH",
            "--out-diffuse", str(source),
            "--out-opacity", str(tmp_path / "opacity.png"),
            "--out-report", str(tmp_path / "report.json"),
        ]
    )
    captured = capsys.readouterr()
    assert code != 0
    assert captured.err.startswith("error:")
    assert source.read_bytes() == before
    assert not (tmp_path / "opacity.png").exists()
    assert not (tmp_path / "report.json").exists()
    assert not (tmp_path / "unused").exists()

    report_alias = catalogue
    catalogue_bytes = catalogue.read_bytes()
    code = flora.main(
        [
            "--scene-json", str(scene),
            "--catalogue", str(catalogue),
            "--out-dir", str(tmp_path / "unused2"),
            "--address", "SYNTH",
            "--out-diffuse", str(tmp_path / "diffuse.png"),
            "--out-opacity", str(tmp_path / "opacity.png"),
            "--out-report", str(report_alias),
        ]
    )
    assert code != 0
    assert catalogue.read_bytes() == catalogue_bytes
    assert not (tmp_path / "diffuse.png").exists()
    assert not (tmp_path / "opacity.png").exists()


def test_scene_hash_unchanged(flora, tmp_path):
    catalogue, _rows = _library(tmp_path)
    scene_json = _scene(tmp_path / "scene.json", [{"name": "a", "faces": [_quad(101)]}])
    scene = tmp_path / "placed.max"
    scene.write_bytes(b"MAX-COPY-not-a-real-scene")
    digest = flora.sha256_file(scene)
    diffuse, opacity, report = _outputs(tmp_path)
    result = flora.build_atlas(
        scene_json,
        catalogue,
        out_diffuse=diffuse,
        out_opacity=opacity,
        out_report=report,
        address="SYNTH",
        scene_path=scene,
    )
    assert flora.sha256_file(scene) == digest
    assert result["scene_sha256_before"] == digest
    assert result["scene_sha256_after"] == digest
    assert scene.read_bytes() == b"MAX-COPY-not-a-real-scene"


def test_one_material_diffuse_and_opacity_only(flora, tmp_path):
    result, diffuse, opacity, report_path = _build(
        flora,
        tmp_path,
        [{"name": "a", "faces": [_quad(101)]}, {"name": "b", "faces": [_quad(101)]}],
    )
    assert result["atlas_count"] == 1
    assert result["material"]["name"] == "M_SYNTH_Flora_1"
    assert set(result["material"]) == {"name", "diffuse", "opacity"}
    assert Path(result["material"]["diffuse"]) == diffuse
    assert Path(result["material"]["opacity"]) == opacity
    assert result["species_count"] == 1
    assert result["object_count"] == 2
    opacity_image = Image.open(opacity)
    assert opacity_image.mode == "L"
    assert opacity_image.size == (2048, 2048)
    tile = result["ids"][0]["tile_px"]
    assert opacity_image.getpixel((tile[0] + 1, tile[1] + 1)) == 255
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["scale_factor"] == result["scale_factor"]
    assert "warnings" in written
    assert written["ids"][0]["size_px"] == [tile[2], tile[3]]


def test_synthetic_scene_report_numbers(flora, tmp_path):
    result, _diffuse, _opacity, report_path = _build(
        flora,
        tmp_path,
        [
            {"name": "tree", "faces": [_quad(101)]},
            {"name": "bush", "faces": [_quad(201)]},
            {"name": "cultivar", "faces": [_quad(202)]},
        ],
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["species_count"] == 3
    assert report["atlas_size"] == 2048
    assert report["scale_factor"] == 1
    assert report["fill_percent"] == result["fill_percent"]
    assert 0 < report["fill_percent"] < 5
    assert {row["species"] for row in report["ids"]} == {
        "Tilia cordata",
        "Spiraea japonica",
        "Spiraea japonica 'Goldflame'",
    }


def test_unused_species_omitted(flora, tmp_path):
    result, diffuse, _opacity, _report = _build(
        flora,
        tmp_path,
        [{"name": "only-tree", "faces": [_quad(101)]}],
    )
    assert result["species_count"] == 1
    assert [row["species"] for row in result["ids"]] == ["Tilia cordata"]
    image = Image.open(diffuse)
    assert image.getpixel((0, 0)) != (40, 160, 60)


def test_scale_never_exceeds_one(flora):
    packed = flora.pack_uniform_tiles(
        [{"key": "small", "width": 16, "height": 16}],
        2048,
        padding_px=0,
        min_long_side=1,
    )
    assert packed["scale_factor"] == 1
    assert packed["slots"][0]["content_w"] == 16
    assert packed["warnings"] == []


def test_png_not_written_inside_repo(flora, tmp_path):
    catalogue, _rows = _library(tmp_path)
    scene = _scene(tmp_path / "scene.json", [{"name": "a", "faces": [_quad(101)]}])
    inside = ROOT / "tests" / "_flora_atlas_should_not_exist.png"
    with pytest.raises(flora.FloraAtlasError):
        flora.build_atlas(
            scene,
            catalogue,
            out_diffuse=inside,
            out_opacity=tmp_path / "opacity.png",
            out_report=tmp_path / "report.json",
            address="SYNTH",
        )
    assert not inside.exists()
    assert not (tmp_path / "opacity.png").exists()


def test_opacity_resized_with_the_same_tile(flora, tmp_path):
    result, diffuse, opacity, _report = _build(
        flora,
        tmp_path,
        [{"name": "bush", "faces": [_quad(201)]}],
    )
    tile = result["ids"][0]["tile_px"]
    assert Image.open(diffuse).getpixel((tile[0] + 1, tile[1] + 1)) == (40, 160, 60)
    assert Image.open(opacity).getpixel((tile[0] + 1, tile[1] + 1)) == 255
    assert result["ids"][0]["size_px"][0] == tile[2]
    assert math.isclose(result["scale_factor"], 1.0)


def test_regression_multispecies_acceptance_rows(flora, tmp_path):
    """Combined acceptance for three placed species. Inputs and expected outputs are fixed literals.

    Input faces (material_id, source px, uvs):
    - 101 Tilia cordata tree 256x256 RGB (220, 40, 40), UVs [[0,0],[1,0],[1,1],[0,1]]
    - 201 Spiraea japonica bush 256x128 RGB (40, 160, 60), UVs [[0,0],[1,0],[0.25,1]]
    - 401 Lavandula angustifolia flower 128x256 RGB (90, 40, 160), UVs [[0,0],[1,0],[0,1]]
    Opacity is 255 L at the same size. Padding 8. Min tile 256.

    Expected one 2048 atlas, scale 1, warnings [], fill 3.125%, material M_SYNTH_Flora_1.
    Tiles (x, y, w, h) and UV (u0, v0, u1, v1), image Y down, UV V up:
    - 101 [4, 4, 256, 256] UV [4/2048, 1788/2048, 260/2048, 2044/2048]
    - 201 [404, 4, 256, 128] UV [404/2048, 1916/2048, 660/2048, 2044/2048]
    - 401 [268, 4, 128, 256] UV [268/2048, 1788/2048, 396/2048, 2044/2048]
    """
    expected = [
        {
            "material_id": 101,
            "species": "Tilia cordata",
            "type": "tree",
            "color": (220, 40, 40),
            "size": (256, 256),
            "uvs": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "tile_px": [4, 4, 256, 256],
            "uv": [4 / 2048, 1788 / 2048, 260 / 2048, 2044 / 2048],
            "mapped": [
                [4 / 2048, 1788 / 2048],
                [260 / 2048, 1788 / 2048],
                [260 / 2048, 2044 / 2048],
                [4 / 2048, 2044 / 2048],
            ],
        },
        {
            "material_id": 201,
            "species": "Spiraea japonica",
            "type": "bush",
            "color": (40, 160, 60),
            "size": (256, 128),
            "uvs": [[0.0, 0.0], [1.0, 0.0], [0.25, 1.0]],
            "tile_px": [404, 4, 256, 128],
            "uv": [404 / 2048, 1916 / 2048, 660 / 2048, 2044 / 2048],
            "mapped": [
                [404 / 2048, 1916 / 2048],
                [660 / 2048, 1916 / 2048],
                [468 / 2048, 2044 / 2048],
            ],
        },
        {
            "material_id": 401,
            "species": "Lavandula angustifolia",
            "type": "flower",
            "color": (90, 40, 160),
            "size": (128, 256),
            "uvs": [[0, 0], [1, 0], [0, 1]],
            "tile_px": [268, 4, 128, 256],
            "uv": [268 / 2048, 1788 / 2048, 396 / 2048, 2044 / 2048],
            "mapped": [
                [268 / 2048, 1788 / 2048],
                [396 / 2048, 1788 / 2048],
                [268 / 2048, 2044 / 2048],
            ],
        },
    ]
    maps = tmp_path / "maps"
    species = []
    objects = []
    for row in expected:
        diffuse = _png(maps / str(row["material_id"]) / "diffuse.png", row["size"], row["color"], "RGB")
        opacity = _png(maps / str(row["material_id"]) / "opacity.png", row["size"], 255, "L")
        species.append(_species(row["species"], row["type"], row["material_id"], diffuse, opacity))
        objects.append({"name": row["species"], "faces": [_quad(row["material_id"], row["uvs"])]})
    catalogue = _catalogue(tmp_path / "catalogue.json", species)
    scene = _scene(tmp_path / "scene.json", objects)
    diffuse, opacity, report_path = _outputs(tmp_path)
    result = flora.build_atlas(
        scene,
        catalogue,
        out_diffuse=diffuse,
        out_opacity=opacity,
        out_report=report_path,
        address="SYNTH",
    )
    assert result["atlas_count"] == 1
    assert result["atlas_size"] == 2048
    assert result["scale_factor"] == 1
    assert result["warnings"] == []
    assert result["fill_percent"] == 3.125
    assert result["species_count"] == 3
    assert result["material"]["name"] == "M_SYNTH_Flora_1"
    assert set(result["material"]) == {"name", "diffuse", "opacity"}
    assert [row["material_id"] for row in result["ids"]] == [101, 201, 401]
    tiles = []
    for row, spec in zip(result["ids"], expected):
        assert row["species"] == spec["species"]
        assert row["tile_px"] == spec["tile_px"]
        assert row["size_px"] == [spec["tile_px"][2], spec["tile_px"][3]]
        assert row["source_px"] == list(spec["size"])
        assert row["uv"] == spec["uv"]
        tiles.append(tuple(row["tile_px"]))
        for uv, mapped in zip(spec["uvs"], spec["mapped"]):
            got = flora.remap_uv(uv, row["uv"])
            assert flora.uv_roundtrip_delta(uv, got, row["uv"]) < 1e-6
            assert abs(got[0] - mapped[0]) <= 1e-6
            assert abs(got[1] - mapped[1]) <= 1e-6
            assert spec["uv"][0] <= got[0] <= spec["uv"][2]
            assert spec["uv"][1] <= got[1] <= spec["uv"][3]
    for index, left in enumerate(tiles):
        for right in tiles[index + 1:]:
            assert not _overlaps(left, right)
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written["ids"][0]["tile_px"] == [4, 4, 256, 256]
    assert written["ids"][1]["size_px"] == [256, 128]
    assert written["ids"][2]["uv"] == expected[2]["uv"]
    assert written["scale_factor"] == 1
    assert written["warnings"] == []
    color = Image.open(diffuse)
    mask = Image.open(opacity)
    assert color.getpixel((5, 5)) == (220, 40, 40)
    assert color.getpixel((405, 5)) == (40, 160, 60)
    assert color.getpixel((269, 5)) == (90, 40, 160)
    assert mask.getpixel((5, 5)) == 255
    assert color.getpixel((2000, 2000)) == (0, 0, 0)
    remapped = flora.remap_faces(
        [face for obj in objects for face in obj["faces"]],
        {row["material_id"]: row["uv"] for row in result["ids"]},
    )
    assert [face["material_id"] for face in remapped] == [101, 201, 401]
    rng = random.Random(217)
    rects = {row["material_id"]: row["uv"] for row in result["ids"]}
    for _ in range(80):
        material_id = rng.choice([101, 201, 401])
        uv = (rng.random(), rng.random())
        mapped = flora.remap_uv(uv, rects[material_id])
        assert flora.uv_within_tolerance(flora.uv_roundtrip_delta(uv, mapped, rects[material_id]), 1e-6)
        u0, v0, u1, v1 = rects[material_id]
        assert u0 <= mapped[0] <= u1
        assert v0 <= mapped[1] <= v1
        for other, rect in rects.items():
            if other == material_id:
                continue
            ou0, ov0, ou1, ov1 = rect
            inside_other = ou0 <= mapped[0] <= ou1 and ov0 <= mapped[1] <= ov1
            assert not inside_other


def test_uv_outside_unit_square_writes_nothing(flora, tmp_path, capsys):
    """Negative and greater-than-one UVs are refused before any atlas file is created."""
    catalogue, _rows = _library(tmp_path)
    scene_bytes_path = tmp_path / "scene.json"
    examples = (
        [[0, 0], [2, 0], [0, 1]],
        [[-1, 0], [1, 0], [0, 1]],
        [[0, 0], [1, 0], [0, 1]],
    )
    # The in-range triangle is the control and must still pack. Out-of-range examples must not.
    control = examples[2]
    objects = [{"name": "edge", "faces": [_quad(101, control)]}]
    result, _diffuse, _opacity, _report = _build(flora, tmp_path / "control", objects)
    assert [row["material_id"] for row in result["ids"]] == [101]
    tile = result["ids"][0]["uv"]
    assert flora.remap_uv((0, 0), tile)[0] == tile[0]
    assert flora.remap_uv((1, 1), tile) == (tile[2], tile[3])

    catalogue_bytes = catalogue.read_bytes()
    diffuse_map = Path(json.loads(catalogue.read_text(encoding="utf-8"))["species"][0]["maps"]["diffuse"])
    map_bytes = diffuse_map.read_bytes()
    for uvs in examples[:2]:
        scene_bytes_path.write_text(json.dumps({
            "schema": "flora-placed-v1",
            "objects": [{"name": "bad", "faces": [_quad(101, uvs)]}],
        }), encoding="utf-8")
        out = tmp_path / "rejected"
        code = flora.main([
            "--scene-json", str(scene_bytes_path),
            "--catalogue", str(catalogue),
            "--out-dir", str(out),
            "--address", "SYNTH",
        ])
        captured = capsys.readouterr()
        assert code != 0
        assert "outside 0..1" in captured.err
        assert not out.exists()
        assert catalogue.read_bytes() == catalogue_bytes
        assert diffuse_map.read_bytes() == map_bytes
    with pytest.raises(flora.FloraAtlasError, match="outside 0..1"):
        flora.remap_uv((2, 0), (0.1, 0.2, 0.3, 0.4))
    with pytest.raises(flora.FloraAtlasError, match="outside 0..1"):
        flora.remap_uv((-1, 0), (0.1, 0.2, 0.3, 0.4))
    assert flora.remap_uv((0, 0), (0.1, 0.2, 0.3, 0.4)) == (0.1, 0.2)
    assert flora.remap_uv((1, 1), (0.1, 0.2, 0.3, 0.4)) == (0.3, 0.4)


def test_probe_uv_outside_unit_interval_never_writes(flora, tmp_path, capsys):
    catalogue, _rows = _library(tmp_path)
    scene = tmp_path / "scene.json"
    catalogue_bytes = catalogue.read_bytes()
    rng = random.Random(2048)
    for index in range(48):
        uvs = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
        slot = rng.randrange(3)
        axis = rng.randrange(2)
        uvs[slot][axis] = rng.choice([
            -1e-15,
            -1,
            -100,
            math.nextafter(0.0, -1.0),
            math.nextafter(1.0, 2.0),
            1 + 1e-15,
            2,
            40,
            float("nan") if index % 11 == 0 else 2,
        ])
        scene.write_text(json.dumps({
            "schema": "flora-placed-v1",
            "objects": [{"name": "probe", "faces": [{"material_id": 101, "uvs": uvs}]}],
        }), encoding="utf-8")
        out = tmp_path / f"probe-{index}"
        code = flora.main([
            "--scene-json", str(scene),
            "--catalogue", str(catalogue),
            "--out-dir", str(out),
            "--address", "SYNTH",
        ])
        captured = capsys.readouterr()
        assert code != 0
        assert captured.err.startswith("error:")
        assert not out.exists()
        assert catalogue.read_bytes() == catalogue_bytes


def test_max_job_source_is_a_pymxs_script():
    job = ROOT / "tools" / "library" / "flora_atlas_max_job.py"
    source = job.read_text(encoding="utf-8")
    compile(source, str(job), "exec")
    assert "pymxs" in source
    assert "saveMaxFile" in source
    assert "flora_atlas_from_scene.py" in source
