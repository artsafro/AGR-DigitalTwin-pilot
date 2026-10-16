"""Synthetic-only Flora pipeline regressions; no generated botanical evidence."""
import importlib.util
from copy import deepcopy
from itertools import combinations
from io import BytesIO
import json
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


def test_prepare_review_and_approved_library(review, tmp_path, monkeypatch):
    directory, manifest, approvals, plan, _ = review
    assert manifest["status"] == "pending_user_review"
    html = (directory / "review.html").read_text(encoding="utf-8")
    assert "NOT approved" in html and "&amp;b=2" in html
    out = tmp_path / "library"
    approval_file = tmp_path / "synthetic-approvals.json"
    flora.write_json(approval_file, approvals)
    monkeypatch.setattr("sys.argv", ["flora", "library", "--review", str(directory),
                                   "--approvals", str(approval_file), "--out", str(out)])
    flora.main()
    result = flora.read_json(out / "library-v001.json")
    assert len(result["species"]) == 3
    for item, entry in zip(result["species"], manifest["entries"]):
        assert item["candidate_id"] == entry["candidate_id"]
        for key, mode in [("diffuse", "RGB"), ("opacity", "L")]:
            path = out / item[key]
            assert path.read_bytes() == (directory / entry[key]).read_bytes()
            with Image.open(path) as image:
                assert image.size == (2048, 2048) and image.mode == mode
                assert "transparency" not in image.info
                if mode == "L":
                    assert set(np.unique(np.asarray(image))) == {0, 255}
    assert result["approvals"] == approvals
    with pytest.raises(FileExistsError):
        flora.main()


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
        flora.publish_library(directory, approvals, out)
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
        flora.publish_library(altered, approvals, out)
    assert not out.exists()


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


# Task #221: Issue where load_approved stringifies evidence accepting null/false/0/[]/{}
# Malformed evidence regression:
# Evaluates None, False, True, 0, 1, 1.25, [], ["attestation"], {}, {"text": "attestation"},
# empty string, and whitespace including Unicode across all 3 candidate approval positions.
# Exact bounds: 17 malformed values * 3 positions = 51 test cases.
# Each case must reject with ValueError("Explicit Artem approval required: ...") and write nothing.
@pytest.mark.parametrize("position", range(3))
@pytest.mark.parametrize("evidence", [
    None,
    False,
    True,
    0,
    1,
    1.25,
    [],
    ["attestation"],
    {},
    {"text": "attestation"},
    "",
    "   ",
    "\t\n\r",
    "\u00a0",
    "\u2003",
    "\u3000",
    " \t\r\n\u00a0\u2002\u2003\u3000 ",
])
def test_publication_rejects_malformed_evidence(review, tmp_path, position, evidence):
    directory, _, original, _, _ = review
    approvals = deepcopy(original)
    approvals["approvals"][position]["evidence"] = evidence
    # JSON roundtrip simulates external JSON approvals file format and types
    approvals = json.loads(json.dumps(approvals))
    out = tmp_path / f"malformed-evidence-pos{position}"
    with pytest.raises(ValueError, match=r"Explicit.*approval required"):
        flora.publish_library(directory, approvals, out)
    assert not out.exists()


def test_publication_preserves_valid_quoted_synthetic_attestation_with_padding(review, tmp_path):
    # Valid synthetic attestations enclosed in quotes with leading and trailing whitespace padding.
    # Asserts stored evidence unchanged (not stripped or altered in library-v001.json)
    # and all diffuse and opacity published bytes exactly equal reviewed bytes.
    directory, manifest, original, _, _ = review
    approvals = deepcopy(original)
    padded_attestations = [
        '   "SYNTHETIC Artem attestation 0: verified white cut-out and proportions"   \n',
        '\t\t  "SYNTHETIC Artem attestation 1: approved 2048x2048 botanical texture"  \r\n',
        ' \u00a0 "SYNTHETIC Artem attestation 2: verified leaf detail and binary mask" \u2003 ',
    ]
    for pos, text in enumerate(padded_attestations):
        approvals["approvals"][pos]["evidence"] = text
    # JSON roundtrip verifies JSON fidelity for whitespace-padded quoted strings
    approvals = json.loads(json.dumps(approvals))
    out = tmp_path / "valid-library-padded-attestation"
    result = flora.publish_library(directory, approvals, out)

    # 1. Assert stored evidence unchanged both in memory and written manifest on disk
    for pos, text in enumerate(padded_attestations):
        assert result["approvals"]["approvals"][pos]["evidence"] == text
    saved_manifest = flora.read_json(out / "library-v001.json")
    for pos, text in enumerate(padded_attestations):
        assert saved_manifest["approvals"]["approvals"][pos]["evidence"] == text

    # 2. Assert all diffuse/opacity published bytes exactly equal reviewed bytes
    assert len(result["species"]) == len(manifest["entries"])
    for item, entry in zip(result["species"], manifest["entries"]):
        for key in ("diffuse", "opacity"):
            published_bytes = (out / item[key]).read_bytes()
            reviewed_bytes = (directory / entry[key]).read_bytes()
            assert published_bytes == reviewed_bytes


def test_generated_probe_evidence_validation_and_byte_preservation(review, tmp_path):
    # Deterministic generated probe bounds and exact counts:
    # 1. Negative rejection probe:
    #    - 24 generated JSON nonstring/whitespace evidence values beyond the parameterized test:
    #      * 6 numbers: -1, -42, -2.718, 0.0, 1e5, 1e-5
    #      * 9 nested structures: [None], [False], [0], [[]], [{"k": "v"}],
    #                             {"k": 1}, {"evidence": None}, {"nested": {}}, {"tags": ["flora"]}
    #      * 9 Unicode whitespace sequences: "\u1680", "\u2000", "\u2002", "\u2004", "\u2006",
    #                                       "\u2008", "\u200a", "\u2028\u2029", "\u202f\u205f"
    #    - Evaluated across all 3 positions: 24 values * 3 positions = 72 rejection evaluations.
    #    - Each rejection evaluation asserts: raises ValueError matching "Explicit.*approval required"
    #      and destination path does not exist (no writes).
    # 2. Positive byte-preservation probe:
    #    - 4 generated suites of valid padded quoted strings with diverse whitespace paddings
    #      (spaces, tabs, Unicode NBSP/EM spaces, CRLF mixtures).
    #    - 4 suites * 3 positions = 12 valid attestation strings tested.
    #    - Each suite asserts: stored evidence unchanged both in-memory and in library-v001.json,
    #      and published diffuse/opacity bytes exactly equal reviewed bytes for all species.
    # 3. Total probe evaluations: 72 rejection evaluations + 4 publication suites = 76 evaluations.
    directory, manifest, original, _, _ = review

    # Generated invalid values beyond parameterized test examples
    generated_invalid_values = [
        # Numbers (negative, float, zero float, scientific notation)
        -1, -42, -2.718, 0.0, 1e5, 1e-5,
        # Nested structures (lists, nested containers, dicts)
        [None], [False], [0], [[]], [{"k": "v"}],
        {"k": 1}, {"evidence": None}, {"nested": {}}, {"tags": ["flora"]},
        # Unicode whitespace characters and combinations
        "\u1680", "\u2000", "\u2002", "\u2004", "\u2006",
        "\u2008", "\u200a", "\u2028\u2029", "\u202f\u205f",
    ]
    assert len(generated_invalid_values) == 24

    # Part 1: Negative rejection probe across all 3 positions
    rejection_count = 0
    for val_idx, val in enumerate(generated_invalid_values):
        for pos in range(3):
            approvals = deepcopy(original)
            approvals["approvals"][pos]["evidence"] = val
            approvals = json.loads(json.dumps(approvals))
            out = tmp_path / f"probe_reject_{val_idx}_{pos}"
            with pytest.raises(ValueError, match=r"Explicit.*approval required"):
                flora.publish_library(directory, approvals, out)
            assert not out.exists()
            rejection_count += 1
    assert rejection_count == 72

    # Part 2: Positive byte-preservation probe with generated valid padded quoted strings
    padding_pairs = [
        ("   ", "   \n"),
        ("\t\t", "\t"),
        (" \u00a0 ", " \u2003 "),
        ("\r\n\t ", " \t\r\n"),
    ]
    assert len(padding_pairs) == 4

    for suite_idx, (left_pad, right_pad) in enumerate(padding_pairs):
        approvals = deepcopy(original)
        suite_attestations = []
        for pos in range(3):
            attestation = f'{left_pad}"SYNTHETIC probe approval suite {suite_idx} pos {pos}: verified texture"{right_pad}'
            suite_attestations.append(attestation)
            approvals["approvals"][pos]["evidence"] = attestation
        approvals = json.loads(json.dumps(approvals))
        out = tmp_path / f"probe_valid_{suite_idx}"
        result = flora.publish_library(directory, approvals, out)

        # Stored evidence unchanged
        for pos, attestation in enumerate(suite_attestations):
            assert result["approvals"]["approvals"][pos]["evidence"] == attestation
        saved_manifest = flora.read_json(out / "library-v001.json")
        for pos, attestation in enumerate(suite_attestations):
            assert saved_manifest["approvals"]["approvals"][pos]["evidence"] == attestation

        # All diffuse/opacity bytes exactly equal reviewed bytes
        assert len(result["species"]) == len(manifest["entries"])
        for item, entry in zip(result["species"], manifest["entries"]):
            for key in ("diffuse", "opacity"):
                published_bytes = (out / item[key]).read_bytes()
                reviewed_bytes = (directory / entry[key]).read_bytes()
                assert published_bytes == reviewed_bytes

