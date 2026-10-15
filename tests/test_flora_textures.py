"""Synthetic-only Flora pipeline regressions; no generated botanical evidence."""
import importlib.util
from copy import deepcopy
from itertools import combinations
from io import BytesIO
import shutil

import numpy as np
from PIL import Image, ImageDraw
import pytest

from dt_ai.materials import flora


@pytest.mark.parametrize("authorization", [None, False, 0])
def test_upscale_missing_authorization_is_not_stringified(tmp_path, authorization):
    source = tmp_path / "synthetic.png"
    image = Image.new("RGB", (1254, 1254), "white")
    ImageDraw.Draw(image).rectangle((300, 100, 900, 1200), fill=(20, 130, 40))
    image.save(source)
    out = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="authorization"):
        flora.upscale(source, out, authorization)
    assert not out.exists()


def test_authorized_upscale_records_source_and_requires_consent(tmp_path):
    source = tmp_path / "synthetic-1254.png"
    image = Image.new("RGB", (1254, 1254), "white")
    ImageDraw.Draw(image).rectangle((300, 100, 900, 1200), fill=(20, 130, 40))
    image.save(source)
    before = source.read_bytes()
    out = tmp_path / "upscaled"
    with pytest.raises(ValueError, match="authorization"):
        flora.upscale(source, out, "")
    assert not out.exists()
    record = flora.upscale(source, out, "SYNTHETIC TEST consent, not user approval")
    assert record["source_size"] == [1254, 1254]
    assert record["output_size"] == [2048, 2048]
    assert record["method"] == "Pillow LANCZOS"
    assert record["source_sha256"] == flora.digest(before)
    with Image.open(out / "source-2048.png") as result:
        assert result.size == (2048, 2048) and result.mode == "RGB"
        assert np.array_equal(np.asarray(result), np.asarray(image.resize((2048, 2048), Image.Resampling.LANCZOS)))
    plan = flora.make_plan([{"species": "SYNTHETIC"}])
    incoming = {"SYNTHETIC": {"image": str(out / "source-2048.png"),
                            "model": "SYNTHETIC", "generation_id": "SYNTHETIC",
                            "upscale_record": str(out / "upscale.json")}}
    manifest = flora.prepare(plan, incoming, tmp_path / "review")
    assert manifest["entries"][0]["upscale"] == record
    assert "1254" in (tmp_path / "review" / "review.html").read_text(encoding="utf-8")
    assert source.read_bytes() == before
    with pytest.raises(FileExistsError):
        flora.upscale(source, out, "SYNTHETIC consent")
    # A different input must not inherit another image's transformation receipt.
    with Image.open(out / "source-2048.png") as changed:
        changed.putpixel((0, 0), (0, 0, 0))
        changed.save(out / "source-2048.png")
    with pytest.raises(ValueError, match="Upscale receipt"):
        flora.prepare(plan, incoming, tmp_path / "stale-review")
    assert not (tmp_path / "stale-review").exists()


def test_flora_route_is_available():
    assert importlib.util.find_spec("dt_ai.materials.flora") is not None, (
        "Issue #190 requires a scripted, approval-gated Flora texture route"
    )


def test_cutout_all_gray_levels_and_thresholds():
    # Exhaustive 255 thresholds x 256 intensities, including near-white edges.
    levels = np.arange(256, dtype=np.uint8)
    pixels = np.repeat(levels[None, :, None], 3, axis=2)
    image = Image.fromarray(pixels)
    for threshold in range(1, 256):
        diffuse, opacity = flora.cutout(image, threshold)
        assert diffuse.mode == "RGB" and opacity.mode == "L"
        assert np.array_equal(np.asarray(diffuse), pixels)
        assert np.array_equal(np.asarray(opacity)[0], np.where(levels >= threshold, 0, 255))
        assert set(np.unique(np.asarray(opacity))) == {0, 255}


def test_cutout_never_serializes_hidden_transparency():
    # Generated probe: all 256 grayscale PNG color keys, even though mode is RGB.
    image = Image.new("RGB", (8, 8), "white")
    image.putpixel((4, 4), (20, 120, 30))
    expected = np.asarray(image).copy()
    for level in range(256):
        image.info["transparency"] = (level, level, level)
        diffuse, opacity = flora.cutout(image)
        assert np.array_equal(np.asarray(diffuse), expected)
        for result in (diffuse, opacity):
            buffer = BytesIO()
            result.save(buffer, format="PNG")
            with Image.open(BytesIO(buffer.getvalue())) as readback:
                assert "transparency" not in readback.info
                assert readback.convert("RGBA").getchannel("A").getextrema() == (255, 255)
        assert image.info["transparency"] == (level, level, level)


def test_synthetic_foliage_holes_and_nonwhite_channels():
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 8, 52, 60), fill=(30, 130, 40))
    draw.rectangle((24, 24, 32, 32), fill="white")
    draw.point((10, 10), fill=(255, 240, 255))
    _, mask = flora.cutout(image)
    assert mask.getpixel((0, 0)) == mask.getpixel((28, 28)) == 0
    assert mask.getpixel((16, 16)) == mask.getpixel((10, 10)) == 255


@pytest.mark.parametrize("mode,color", [("RGB", "white"), ("RGB", "black"),
                                            ("RGBA", "white"), ("L", 255)])
def test_bad_cutout_inputs(mode, color):
    with pytest.raises(ValueError):
        flora.cutout(Image.new(mode, (8, 8), color))


@pytest.fixture(scope="module")
def review(tmp_path_factory):
    root = tmp_path_factory.mktemp("flora-synthetic")
    image = Image.new("RGB", (2048, 2048), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((512, 100, 1536, 1950), fill=(10, 140, 30))
    draw.rectangle((800, 600, 1000, 1000), fill="white")
    source = root / "synthetic-not-a-generated-plant.png"
    image.save(source)
    species = [{"species": f"SYNTHETIC species {i}", "reference": "https://example.invalid/reference?a=1&b=2"}
               for i in range(3)]
    plan = flora.make_plan(species)
    incoming = {item["species"]: {"image": str(source), "model": "SYNTHETIC TEST ONLY",
                                 "generation_id": "NOT REAL GENERATION", "reference_image": str(source)}
                for item in species}
    destination = root / "review-v001"
    manifest = flora.prepare(plan, incoming, destination)
    # Synthetic approval fixture, never an attestation from the real user.
    approvals = {"approvals": [
        {"candidate_id": entry["candidate_id"], "decision": "approved", "reviewed_by": "Artem",
         "reviewed_at": "2026-10-15T10:00:00+03:00", "evidence": "SYNTHETIC TEST APPROVAL ONLY",
         "review_sha256": manifest["review_sha256"]}
        for entry in manifest["entries"]]}
    return destination, manifest, approvals, plan, incoming


def test_prepare_removes_png_color_key(review, tmp_path):
    _, _, _, plan, incoming = review
    source = tmp_path / "rgb-with-trns.png"
    with Image.open(next(iter(incoming.values()))["image"]) as image:
        image.save(source, transparency=(10, 140, 30))
    changed = deepcopy(incoming)
    for item in changed.values():
        item["image"] = str(source)
    out = tmp_path / "review-without-trns"
    manifest = flora.prepare(plan, changed, out)
    for entry in manifest["entries"]:
        for key in ("diffuse", "opacity"):
            with Image.open(out / entry[key]) as image:
                assert "transparency" not in image.info
                assert image.convert("RGBA").getchannel("A").getextrema() == (255, 255)


def test_prepare_review_and_approved_pack(review, tmp_path):
    directory, manifest, approvals, plan, _ = review
    assert manifest["status"] == "pending_user_review"
    html = (directory / "review.html").read_text(encoding="utf-8")
    assert "NOT approved" in html and html.count("SYNTHETIC species") == 6
    assert "&amp;b=2" in html
    assert not list(directory.glob("Flora*"))
    with pytest.raises(FileExistsError):
        flora.prepare(plan, review[4], directory)
    assert all("2048 x 2048" in s["prompt"] and s["reference"] in s["prompt"] for s in plan["species"])
    out = tmp_path / "atlas-v001"
    result = flora.pack(directory, approvals, out)
    assert len(result["placements"]) == 3
    for file, mode in [("Flora_d_1.png", "RGB"), ("Flora_o_1.png", "L")]:
        with Image.open(out / file) as image:
            assert image.size == (2048, 2048) and image.mode == mode
            if mode == "L":
                assert set(np.unique(np.asarray(image))) == {0, 255}
        assert (out / file).stat().st_size <= 3 * 1024 * 1024
        assert flora.digest((out / file).read_bytes()) == result["files_sha256"][file]
    before = (out / "Flora_d_1.png").read_bytes()
    with pytest.raises(FileExistsError):
        flora.pack(directory, approvals, out)
    assert (out / "Flora_d_1.png").read_bytes() == before


@pytest.mark.parametrize("position", range(3))
@pytest.mark.parametrize("fault", ["missing", "rejected", "pending", "wrong_user", "stale", "no_evidence", "no_date", "duplicate"])
def test_unapproved_never_enters_atlas(review, tmp_path, position, fault):
    directory, _, original, _, _ = review
    approvals = deepcopy(original)
    record = approvals["approvals"][position]
    if fault == "missing":
        approvals["approvals"].pop(position)
    elif fault == "duplicate":
        approvals["approvals"].append(deepcopy(record))
    else:
        key, value = {"rejected": ("decision", "rejected"), "pending": ("decision", "pending"),
                      "wrong_user": ("reviewed_by", "Agent"), "stale": ("review_sha256", "0" * 64),
                      "no_evidence": ("evidence", ""), "no_date": ("reviewed_at", "")}[fault]
        record[key] = value
    out = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        flora.pack(directory, approvals, out)
    assert not out.exists()


@pytest.mark.parametrize("changed", ["0_d.png", "1_o.png", "2_ref.png", "review.html", "candidates.json"])
def test_changed_review_invalidates_approval(review, tmp_path, changed):
    directory, _, approvals, _, _ = review
    altered = tmp_path / "altered"
    shutil.copytree(directory, altered)
    path = altered / changed
    if changed == "candidates.json":
        value = flora.read_json(path)
        value["entries"][0]["species"] = "Changed identity"
        flora.write_json(path, value)
    else:
        path.write_bytes(path.read_bytes() + b"changed")
    out = tmp_path / "atlas"
    with pytest.raises(ValueError):
        flora.pack(altered, approvals, out)
    assert not out.exists()


def test_pack_explicit_tile_limit_via_cli(review, tmp_path, monkeypatch):
    directory, _, approvals, _, _ = review
    approval_file = tmp_path / "synthetic-approvals.json"
    flora.write_json(approval_file, approvals)
    out = tmp_path / "limited-atlas"
    monkeypatch.setattr("sys.argv", ["flora", "pack", "--review", str(directory),
                                   "--approvals", str(approval_file), "--out", str(out),
                                   "--max-tile-size", "512"])
    flora.main()
    result = flora.read_json(out / "atlas.json")
    assert result["max_tile_size"] == 512
    assert len(result["placements"]) == 3
    for placement in result["placements"]:
        x, y, w, h = placement["rect_px"]
        assert max(w, h) == 512
        assert placement["uv_bottom_left"] == [x / 2048, 1 - (y + h) / 2048,
                                               (x + w) / 2048, 1 - y / 2048]
    with Image.open(out / "Flora_o_1.png") as mask:
        assert set(np.unique(np.asarray(mask))) == {0, 255}
    assert result["approvals"] == approvals


@pytest.mark.parametrize("limit", [0, -1, 2049, True, 1.5, None])
def test_invalid_tile_limit_rejected_before_output(tmp_path, limit):
    out = tmp_path / "invalid-limit"
    with pytest.raises(ValueError, match="max_tile_size"):
        flora.pack(tmp_path, {}, out, max_tile_size=limit)
    assert not out.exists()


def test_geometry_generated_probe():
    # 1..40 species: exhaustive rectangle pairs; includes the first 10..20.
    for count in range(1, 41):
        rects = flora.grid_regions(count)
        assert len(rects) == count
        for x, y, w, h in rects:
            assert x >= 8 and y >= 8 and x + w <= 2048 - 8 and y + h <= 2048 - 8
        for (x, y, w, h), (xx, yy, ww, hh) in combinations(rects, 2):
            assert x + w + 8 <= xx or xx + ww + 8 <= x or y + h + 8 <= yy or yy + hh + 8 <= y
    for count in (0, 2048 * 2048):
        with pytest.raises(ValueError):
            flora.grid_regions(count)


@pytest.mark.parametrize("relative", ["outputs/flora-v001", "data/flora-v001", "src/flora-v001"])
def test_repository_binary_outputs_rejected(relative):
    with pytest.raises(ValueError, match="outside"):
        flora.external_destination(flora.REPO / relative)


@pytest.mark.parametrize("size", [(1024, 1024), (2048, 1024), (2049, 2048)])
def test_generation_not_silently_upscaled(review, tmp_path, size):
    _, _, _, plan, incoming = review
    source = tmp_path / "wrong-size.png"
    Image.new("RGB", size, "white").save(source)
    changed = deepcopy(incoming)
    changed[plan["species"][0]["species"]]["image"] = str(source)
    out = tmp_path / "review"
    with pytest.raises(ValueError, match="exactly 2048"):
        flora.prepare(plan, changed, out)
    assert not out.exists()


def test_oversized_png_is_rejected_before_output(monkeypatch, tmp_path):
    rng = np.random.default_rng(190)
    noise = Image.fromarray(rng.integers(0, 256, (2048, 2048, 3), dtype=np.uint8))
    opaque = Image.new("L", (2048, 2048), 255)
    # Isolate the size gate after approval validation; this is not real approval.
    monkeypatch.setattr(flora, "load_approved", lambda *_: [
        ({"species": "SYNTHETIC noise", "candidate_id": "synthetic"}, noise, opaque)])
    out = tmp_path / "too-large"
    with pytest.raises(ValueError, match="3 MiB"):
        flora.pack(tmp_path, {}, out)
    assert not out.exists()


def test_plan_cli(monkeypatch, tmp_path):
    spec = tmp_path / "species.json"
    out = tmp_path / "plan.json"
    flora.write_json(spec, [{"species": "SYNTHETIC", "reference": "https://example.invalid/ref"}])
    monkeypatch.setattr("sys.argv", ["flora", "plan", "--species", str(spec), "--out", str(out)])
    flora.main()
    assert flora.read_json(out)["status"] == "awaiting_image_generation"
    before = out.read_bytes()
    with pytest.raises(FileExistsError):
        flora.main()
    assert out.read_bytes() == before


@pytest.mark.parametrize("species", [[], [{"species": ""}], [{"species": "x"}, {"species": "x"}]])
def test_invalid_plan(species):
    with pytest.raises(ValueError):
        flora.make_plan(species)


def test_generation_metadata_required(review, tmp_path):
    _, _, _, plan, incoming = review
    for key in ("model", "generation_id"):
        changed = deepcopy(incoming)
        changed[plan["species"][0]["species"]][key] = ""
        with pytest.raises(ValueError, match="Actual model"):
            flora.prepare(plan, changed, tmp_path / key)
        assert not (tmp_path / key).exists()
