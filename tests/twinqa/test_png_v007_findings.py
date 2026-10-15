"""Tests for twinqa.png V007 texture findings and normal map convention heuristics.

Covers:
- normal_convention: DirectX positive correlation, OpenGL negative correlation,
  flat => flat (never directx), deterministic uncorrelated non-flat => undecided.
- vpm_texture_findings:
  - Clean complete set (emits pass finding, populates sets, no fail/review/not_run).
  - Clean complete set with Diffuse alpha and flat Normal.
  - Normal map OpenGL curl failure and undecided review.
  - Forbidden alpha in ERM and Normal tested separately.
  - Invalid square size and non-square size failures.
  - ERM R (emissive) positive at exactly 95% (review) vs below 95% (pass) and 100% (review).
  - Diffuse smaller than ERM and Normal (fail).
  - Placeholder Diffuse smaller than ERM and Normal (review).
  - Adjacent branches: malformed filename, wrong prefix, unreadable PNG, wrong color mode,
    invalid non-flat placeholder, missing map.
"""
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from twinqa.png import (
    PngFacts,
    normal_convention,
    vpm_texture_findings,
)

SYNTHETIC_PROFILE = {
    "textures": {
        "allowed_square_sizes_px": [20, 64, 128],
        "flat_placeholder": {"size_px": 32},
    }
}
PREFIX = "T_Test"


def _generate_height_normals(convention: str = "directx", size: int = 64) -> np.ndarray:
    """Generate tangent-space normals from a smooth synthetic height field with mixed derivatives.

    h(y, x) = sin(x) * sin(y) gives non-zero mixed partial derivative d^2h / (dx dy) = cos(x) * cos(y).
    """
    y, x = np.mgrid[0 : 2 * np.pi : size * 1j, 0 : 2 * np.pi : size * 1j]
    h = np.sin(x) * np.sin(y)
    nx = -np.gradient(h, axis=1) * 5.0
    ny = -np.gradient(h, axis=0) * 5.0
    nz = np.ones_like(h)
    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    nx, ny, nz = nx / norm, ny / norm, nz / norm
    r = np.clip((nx + 1.0) * 127.5, 0, 255).astype(np.uint8)
    if convention == "directx":
        g = np.clip((ny + 1.0) * 127.5, 0, 255).astype(np.uint8)
    elif convention == "opengl":
        g = np.clip((-ny + 1.0) * 127.5, 0, 255).astype(np.uint8)
    else:
        raise ValueError(f"Unknown convention: {convention}")
    b = np.clip((nz + 1.0) * 127.5, 0, 255).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def _generate_uncorrelated_normals(size: int = 64) -> np.ndarray:
    """Generate smooth non-flat normals with zero mixed correlation."""
    y, x = np.mgrid[0 : 2 * np.pi : size * 1j, 0 : 2 * np.pi : size * 1j]
    nx = 0.2 * np.sin(y)
    ny = 0.2 * np.sin(x)
    nz = np.sqrt(np.maximum(0.1, 1.0 - nx**2 - ny**2))
    r = np.clip((nx + 1.0) * 127.5, 0, 255).astype(np.uint8)
    g = np.clip((ny + 1.0) * 127.5, 0, 255).astype(np.uint8)
    b = np.clip((nz + 1.0) * 127.5, 0, 255).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)


def _generate_flat_normals(size: int = 64) -> np.ndarray:
    """Constant flat tangent-space normal pointing along +Z: (128, 128, 255)."""
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    arr[..., 0] = 128
    arr[..., 1] = 128
    arr[..., 2] = 255
    return arr


def _png_bytes_from_array(arr: np.ndarray) -> bytes:
    buf = BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


def _solid_png_bytes(color: tuple, size: tuple[int, int] = (64, 64), mode: str = "RGB") -> bytes:
    buf = BytesIO()
    Image.new(mode, size, color).save(buf, "PNG")
    return buf.getvalue()


def _make_erm_png_bytes(lit_pixels: int, total_pixels: int = 400, size: int = 20) -> bytes:
    """Create an ERM map with a precise number of non-zero R (emissive) pixels."""
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    r_flat = np.zeros(total_pixels, dtype=np.uint8)
    r_flat[:lit_pixels] = 255
    arr[..., 0] = r_flat.reshape((size, size))
    arr[..., 1] = 128  # Roughness
    arr[..., 2] = 0  # Metallic
    return _png_bytes_from_array(arr)


def _clean_vpm_set(prefix: str = PREFIX, size: int = 64) -> dict[str, bytes]:
    return {
        f"{prefix}_Diffuse_1.1001.png": _solid_png_bytes((120, 110, 100), (size, size)),
        f"{prefix}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (size, size)),
        f"{prefix}_Normal_1.1001.png": _png_bytes_from_array(_generate_height_normals("directx", size=size)),
    }


# ==============================================================================
# normal_convention tests
# ==============================================================================


def test_normal_convention_directx_positive_correlation():
    rgb = _generate_height_normals("directx", size=64)
    conv, corr = normal_convention(rgb)
    assert conv == "directx"
    assert corr > 0.3
    assert corr > 0.95


def test_normal_convention_opengl_negative_correlation():
    rgb = _generate_height_normals("opengl", size=64)
    conv, corr = normal_convention(rgb)
    assert conv == "opengl"
    assert corr < -0.3
    assert corr < -0.95


def test_normal_convention_flat_returns_flat_never_directx():
    rgb = _generate_flat_normals(size=64)
    conv, corr = normal_convention(rgb)
    assert conv == "flat"
    assert conv != "directx"
    assert corr == 0.0


def test_normal_convention_deterministic_uncorrelated_non_flat_is_undecided():
    rgb = _generate_uncorrelated_normals(size=64)
    conv, corr = normal_convention(rgb)
    assert conv == "undecided"
    assert -0.3 <= corr <= 0.3


# ==============================================================================
# Clean complete set tests
# ==============================================================================


def test_vpm_clean_complete_set_emits_pass_and_populates_sets():
    pngs = _clean_vpm_set()
    findings, sets = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)

    assert len(findings) == 1
    f = findings[0]
    assert f.name == "VPM maps"
    assert f.status == "pass"
    assert f.observed == "3 PNG: names, 8-bit, sizes, alpha rules, sets, ERM order, DirectX green"
    assert f.expected == "reg p.30-31"
    assert f.source_pdf_pages == [23, 30, 31]
    assert f.evidence == "ZIP root"
    assert not any(item.status in ("fail", "review", "not_run") for item in findings)

    assert (1, 1001) in sets
    map_facts = sets[(1, 1001)]
    assert set(map_facts.keys()) == {"Diffuse", "ERM", "Normal"}
    for kind in ("Diffuse", "ERM", "Normal"):
        facts = map_facts[kind]
        assert isinstance(facts, PngFacts)
        assert facts.name == f"{PREFIX}_{kind}_1.1001.png"
        assert facts.width == 64
        assert facts.height == 64
        assert facts.bit_depth == 8
        assert facts.color_type == 2
        assert not facts.has_alpha


def test_vpm_clean_set_with_diffuse_alpha_and_flat_normal_passes():
    pngs = {
        f"{PREFIX}_Diffuse_1.1001.png": _solid_png_bytes((120, 110, 100, 255), (64, 64), mode="RGBA"),
        f"{PREFIX}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (64, 64)),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (64, 64)),
    }
    findings, sets = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)

    assert len(findings) == 1
    assert findings[0].status == "pass"
    assert not any(item.status in ("fail", "review", "not_run") for item in findings)
    assert sets[(1, 1001)]["Diffuse"].has_alpha is True


# ==============================================================================
# Normal map OpenGL failure and undecided review in vpm_texture_findings
# ==============================================================================


def test_vpm_normal_opengl_fails():
    pngs = _clean_vpm_set()
    normal_name = f"{PREFIX}_Normal_1.1001.png"
    pngs[normal_name] = _png_bytes_from_array(_generate_height_normals("opengl", size=64))

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "DirectX normal"
    assert f.status == "fail"
    assert f.evidence == normal_name
    assert f.expected == "DirectX (Y +1..-1 -> G 0..255)"
    assert f.source_pdf_pages == [23, 30]
    assert f.conflicts == [6]
    assert "green channel is OpenGL (+Y), curl correlation" in f.observed


def test_vpm_normal_undecided_review():
    pngs = _clean_vpm_set()
    normal_name = f"{PREFIX}_Normal_1.1001.png"
    pngs[normal_name] = _png_bytes_from_array(_generate_uncorrelated_normals(size=64))

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "DirectX normal"
    assert f.status == "review"
    assert f.evidence == normal_name
    assert f.expected == "DirectX"
    assert f.source_pdf_pages == [23, 30]
    assert f.conflicts == [6]
    assert "convention undecidable, correlation" in f.observed
    assert not any(item.status == "fail" for item in findings)


# ==============================================================================
# Forbidden alpha in ERM and Normal (tested separately)
# ==============================================================================


def test_vpm_alpha_in_erm_fails():
    pngs = _clean_vpm_set()
    erm_name = f"{PREFIX}_ERM_1.1001.png"
    pngs[erm_name] = _solid_png_bytes((0, 128, 0, 255), (64, 64), mode="RGBA")

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "no alpha in ERM/Normal"
    assert f.status == "fail"
    assert f.evidence == erm_name
    assert f.observed == f"{erm_name}: alpha present"
    assert f.expected == "RGB without alpha"
    assert f.source_pdf_pages == [30]


def test_vpm_alpha_in_normal_fails():
    pngs = _clean_vpm_set()
    normal_name = f"{PREFIX}_Normal_1.1001.png"
    pngs[normal_name] = _solid_png_bytes((128, 128, 255, 255), (64, 64), mode="RGBA")

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "no alpha in ERM/Normal"
    assert f.status == "fail"
    assert f.evidence == normal_name
    assert f.observed == f"{normal_name}: alpha present"
    assert f.expected == "RGB without alpha"
    assert f.source_pdf_pages == [30]


# ==============================================================================
# Size tests: invalid square size and non-square size
# ==============================================================================


def test_vpm_invalid_square_size_fails():
    pngs = _clean_vpm_set()
    normal_name = f"{PREFIX}_Normal_1.1001.png"
    # 48x48 is square, but not in allowed_square_sizes_px [20, 64, 128] or placeholder 32
    pngs[normal_name] = _solid_png_bytes((128, 128, 255), (48, 48))

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "map size"
    assert f.status == "fail"
    assert f.evidence == normal_name
    assert f.observed == f"{normal_name}: 48x48"
    assert f.expected == "square [20, 64, 128] or 32 placeholder"
    assert f.source_pdf_pages == [30, 31]


def test_vpm_non_square_size_fails():
    pngs = _clean_vpm_set()
    normal_name = f"{PREFIX}_Normal_1.1001.png"
    # 64x48 is non-square
    pngs[normal_name] = _solid_png_bytes((128, 128, 255), (64, 48))

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "map size"
    assert f.status == "fail"
    assert f.evidence == normal_name
    assert f.observed == f"{normal_name}: 64x48"
    assert f.expected == "square [20, 64, 128] or 32 placeholder"
    assert f.source_pdf_pages == [30, 31]


# ==============================================================================
# ERM R positive threshold tests (95%, below 95%, 100%)
# ==============================================================================


def test_vpm_erm_r_positive_at_exactly_95_percent_triggers_review():
    # 20x20 = 400 pixels; exactly 380 lit pixels = 380 / 400 = 0.95 (95%)
    erm_name = f"{PREFIX}_ERM_1.1001.png"
    pngs = {
        f"{PREFIX}_Diffuse_1.1001.png": _solid_png_bytes((120, 110, 100), (20, 20)),
        erm_name: _make_erm_png_bytes(lit_pixels=380, total_pixels=400, size=20),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (20, 20)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "ERM channel order"
    assert f.status == "review"
    assert f.evidence == erm_name
    assert f.observed == f"{erm_name}: R (emissive) non-zero on 95% of pixels"
    assert f.expected == "R=Emissive (black where nothing glows), G=Roughness, B=Metallic"
    assert f.source_pdf_pages == [23, 37]
    assert not any(item.status == "fail" for item in findings)


def test_vpm_erm_r_positive_below_95_percent_passes():
    # 20x20 = 400 pixels; 379 lit pixels = 379 / 400 = 0.9475 (< 95%)
    pngs = {
        f"{PREFIX}_Diffuse_1.1001.png": _solid_png_bytes((120, 110, 100), (20, 20)),
        f"{PREFIX}_ERM_1.1001.png": _make_erm_png_bytes(lit_pixels=379, total_pixels=400, size=20),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (20, 20)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    assert len(findings) == 1
    assert findings[0].status == "pass"
    assert not any(item.status in ("fail", "review", "not_run") for item in findings)


def test_vpm_erm_r_positive_100_percent_triggers_review():
    # 20x20 = 400 pixels; 400 lit pixels = 400 / 400 = 1.0 (100%)
    erm_name = f"{PREFIX}_ERM_1.1001.png"
    pngs = {
        f"{PREFIX}_Diffuse_1.1001.png": _solid_png_bytes((120, 110, 100), (20, 20)),
        erm_name: _make_erm_png_bytes(lit_pixels=400, total_pixels=400, size=20),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (20, 20)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "ERM channel order"
    assert f.status == "review"
    assert f.evidence == erm_name
    assert f.observed == f"{erm_name}: R (emissive) non-zero on 100% of pixels"
    assert f.expected == "R=Emissive (black where nothing glows), G=Roughness, B=Metallic"
    assert f.source_pdf_pages == [23, 37]
    assert not any(item.status == "fail" for item in findings)


# ==============================================================================
# Diffuse smaller than ERM and Normal (fail vs placeholder review)
# ==============================================================================


def test_vpm_diffuse_smaller_than_erm_fails():
    diffuse_name = f"{PREFIX}_Diffuse_1.1001.png"
    pngs = {
        diffuse_name: _solid_png_bytes((120, 110, 100), (64, 64)),
        f"{PREFIX}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (128, 128)),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (64, 64)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "Diffuse >= ERM/Normal"
    assert f.status == "fail"
    assert f.evidence == diffuse_name
    assert f.observed == "slot 1 UDIM 1001: Diffuse 64 < ERM 128"
    assert f.expected == "Diffuse resolution >= ERM and Normal"
    assert f.source_pdf_pages == [30]


def test_vpm_diffuse_smaller_than_normal_fails():
    diffuse_name = f"{PREFIX}_Diffuse_1.1001.png"
    pngs = {
        diffuse_name: _solid_png_bytes((120, 110, 100), (64, 64)),
        f"{PREFIX}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (64, 64)),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (128, 128)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "Diffuse >= ERM/Normal"
    assert f.status == "fail"
    assert f.evidence == diffuse_name
    assert f.observed == "slot 1 UDIM 1001: Diffuse 64 < Normal 128"
    assert f.expected == "Diffuse resolution >= ERM and Normal"
    assert f.source_pdf_pages == [30]


def test_vpm_diffuse_smaller_than_both_erm_and_normal_fails():
    diffuse_name = f"{PREFIX}_Diffuse_1.1001.png"
    pngs = {
        diffuse_name: _solid_png_bytes((120, 110, 100), (64, 64)),
        f"{PREFIX}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (128, 128)),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (128, 128)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 2
    assert all(f.name == "Diffuse >= ERM/Normal" and f.status == "fail" for f in bad)
    observed_messages = {f.observed for f in bad}
    assert observed_messages == {
        "slot 1 UDIM 1001: Diffuse 64 < ERM 128",
        "slot 1 UDIM 1001: Diffuse 64 < Normal 128",
    }


def test_vpm_placeholder_diffuse_smaller_triggers_review_not_fail():
    diffuse_name = f"{PREFIX}_Diffuse_1.1001.png"
    # Diffuse is 32x32 flat placeholder, while ERM and Normal are full 64x64
    pngs = {
        diffuse_name: _solid_png_bytes((120, 110, 100), (32, 32)),
        f"{PREFIX}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (64, 64)),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (64, 64)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 2
    assert all(f.name == "Diffuse >= ERM/Normal" and f.status == "review" for f in bad)
    assert not any(f.status == "fail" for f in findings)
    assert all(f.evidence == diffuse_name for f in bad)
    observed_messages = {f.observed for f in bad}
    assert observed_messages == {
        "slot 1 UDIM 1001: Diffuse 32 < ERM 64",
        "slot 1 UDIM 1001: Diffuse 32 < Normal 64",
    }


# ==============================================================================
# Adjacent cheap branches
# ==============================================================================


def test_vpm_malformed_filename_fails():
    bad_name = "invalid_texture_name.png"
    pngs = {bad_name: _solid_png_bytes((128, 128, 128), (64, 64))}

    findings, sets = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    assert len(findings) == 1
    f = findings[0]
    assert f.name == "texture name"
    assert f.status == "fail"
    assert f.observed == bad_name
    assert f.expected == "T_{Address}_{Diffuse|ERM|Normal}_{Slot}.{UDIM}.png"
    assert f.source_pdf_pages == [34, 35]
    assert f.evidence == bad_name
    assert sets == {}


def test_vpm_wrong_prefix_fails():
    wrong_prefix = "T_OtherBldg"
    pngs = _clean_vpm_set(prefix=wrong_prefix)

    findings, sets = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    # All 3 maps fail with texture address, but have valid sizes, format and sets
    assert len(bad) == 3
    assert all(f.name == "texture address" and f.status == "fail" for f in bad)
    assert all(f.expected == f"{PREFIX}_..." for f in bad)
    assert all(f.source_pdf_pages == [33, 34] for f in bad)
    assert {f.evidence for f in bad} == set(pngs.keys())
    assert (1, 1001) in sets


def test_vpm_unreadable_png_fails():
    corrupt_name = f"{PREFIX}_Diffuse_1.1001.png"
    pngs = {corrupt_name: b"corrupted_non_png_bytes"}

    findings, sets = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    assert len(findings) == 1
    f = findings[0]
    assert f.name == "PNG readable"
    assert f.status == "fail"
    assert f.observed == f"{corrupt_name}: not a PNG"
    assert f.expected == "valid PNG"
    assert f.source_pdf_pages == [30]
    assert f.evidence == corrupt_name
    assert sets == {}


def test_vpm_wrong_color_mode_fails():
    diffuse_name = f"{PREFIX}_Diffuse_1.1001.png"
    pngs = _clean_vpm_set()
    # Grayscale mode 'L' gives bit_depth 8 and color_type 0 (RGB/RGBA expects 2 or 6)
    pngs[diffuse_name] = _solid_png_bytes(128, (64, 64), mode="L")

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "8-bit RGB/RGBA"
    assert f.status == "fail"
    assert f.observed == f"{diffuse_name}: bit depth 8, colour type 0"
    assert f.expected == "8 bit per channel, RGB or RGBA"
    assert f.source_pdf_pages == [30]
    assert f.evidence == diffuse_name


def test_vpm_invalid_non_flat_placeholder_fails():
    diffuse_name = f"{PREFIX}_Diffuse_1.1001.png"
    # Create 32x32 placeholder with two colours
    img = Image.new("RGB", (32, 32), (128, 128, 128))
    img.putpixel((0, 0), (255, 0, 0))
    buf = BytesIO()
    img.save(buf, "PNG")

    pngs = {
        diffuse_name: buf.getvalue(),
        f"{PREFIX}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (32, 32)),
        f"{PREFIX}_Normal_1.1001.png": _solid_png_bytes((128, 128, 255), (32, 32)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "flat placeholder"
    assert f.status == "fail"
    assert f.observed == f"{diffuse_name}: alpha or more than one colour"
    assert f.expected == "256x256, one colour, no alpha"
    assert f.source_pdf_pages == [22, 31]
    assert f.conflicts == [5]
    assert f.evidence == diffuse_name


def test_vpm_missing_map_fails():
    # Only Diffuse and ERM are provided, Normal is missing
    pngs = {
        f"{PREFIX}_Diffuse_1.1001.png": _solid_png_bytes((120, 110, 100), (64, 64)),
        f"{PREFIX}_ERM_1.1001.png": _solid_png_bytes((0, 128, 0), (64, 64)),
    }

    findings, _ = vpm_texture_findings(pngs, SYNTHETIC_PROFILE, PREFIX)
    bad = [f for f in findings if f.status in ("fail", "review")]
    assert len(bad) == 1
    f = bad[0]
    assert f.name == "map set"
    assert f.status == "fail"
    assert f.observed == "slot 1 UDIM 1001: missing ['Normal']"
    assert f.expected == "Diffuse + ERM + Normal for every used UDIM"
    assert f.source_pdf_pages == [30]
    assert f.evidence == "slot 1"
