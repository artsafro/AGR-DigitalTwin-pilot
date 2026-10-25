"""Legacy characterization of the GeoJSON imageBase64 JPEG boundary (new-case, Pattern: new-case).

Pins CURRENT behaviour from docs/research/geojson-jpeg-decode-boundary.md (F2/F3/F4):

* header acceptance is not pixel acceptance: a JPEG without its final FF D9 passes ``_image``
  while an independent Pillow ``open+load`` raises OSError;
* a JPEG cut inside its header makes ``Image.open`` raise OSError, which escapes ``_image``,
  ``geojson_findings`` and ``validate()`` (no finding, no report);
* malformed base64 and a 256x256 PNG are ordinary ``imageBase64`` fail findings.

This is characterization, not approval: pixel-decode acceptance and OSError normalization stay user
decisions. Controls only (no prefix sweep). Two mutation probes show the pins bite.
"""
import base64
import copy
import hashlib
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import PIL
import pytest
from PIL import Image

import twinqa.geojson as geo
from twinqa.geojson import _image, geojson_findings
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
sys.path.insert(0, str(ROOT / "tools" / "qa"))
import validate_package  # noqa: E402

PROFILES = load_profiles()
PROFILE = PROFILES.vpm
KEYS = PROFILE["geojson"]["properties_keys"]


def _jpeg() -> bytes:
    x = np.arange(256)[None, :].repeat(256, 0)
    y = np.arange(256)[:, None].repeat(256, 1)
    arr = np.stack([x % 256, y % 256, (x * 7 + y * 13) % 256], -1).astype(np.uint8)
    buf = BytesIO()
    Image.fromarray(arr, "RGB").save(buf, format="JPEG", quality=85, subsampling=0,
                                     optimize=False, progressive=False)
    return buf.getvalue()


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (1, 2, 3)).save(buf, "PNG")
    return buf.getvalue()


CLEAN = _jpeg()
CONTROLS = {
    "clean": CLEAN,
    "no_eoi": CLEAN[:-2],
    "head100": CLEAN[:100],
    "png": _png(),
}
VALUES = {name: base64.b64encode(b).decode("ascii") for name, b in CONTROLS.items()}
VALUES["bad_b64"] = "not base64!!!"
FROZEN = {n: hashlib.sha256(v.encode()).hexdigest() for n, v in VALUES.items()}


def _load(raw: bytes):
    with Image.open(BytesIO(raw)) as img:
        img.load()
        return img.format, img.size


def _doc(value) -> dict:
    props = {k: "synthetic" for k in KEYS}
    props.update(FNO_code="123 456", other="", act_AGR="", imageBase64=value)
    return {"type": "FeatureCollection", "features": [{
        "type": "ObjectFeature",
        "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]},
        "properties": props, "Glasses": []}]}


def _bytes(value) -> bytes:
    return json.dumps(_doc(value), ensure_ascii=False).encode("utf-8")


def _image_finding(value):
    """geojson_findings imageBase64 finding, with finally-based checks on mutable arguments."""
    profile_before, names = copy.deepcopy(PROFILE), set()
    names_before = copy.deepcopy(names)
    data = _bytes(value)
    data_hash = hashlib.sha256(data).hexdigest()
    try:
        out = geojson_findings(data, PROFILE, ground=False, glass_names=names)
    finally:
        assert PROFILE == profile_before
        assert names == names_before
        assert hashlib.sha256(data).hexdigest() == data_hash
    return [f for f in out if f.name == "imageBase64"]


def _write(tmp_path, name, value) -> Path:
    p = tmp_path / f"{name}.geojson"
    p.write_bytes(_bytes(value))
    return p


def _assert_legacy_pass_no_eoi():
    """The assertion mutation probe 1 must break."""
    assert _image(VALUES["no_eoi"]).status == "pass"
    (f,) = _image_finding(VALUES["no_eoi"])
    assert f.status == "pass"


def _assert_header_oserror_escapes():
    """The assertion mutation probe 2 must break."""
    with pytest.raises(OSError):
        _image(VALUES["head100"])
    with pytest.raises(OSError):
        _image_finding(VALUES["head100"])


@pytest.fixture(autouse=True)
def _frozen():
    assert {n: hashlib.sha256(v.encode()).hexdigest() for n, v in VALUES.items()} == FROZEN
    flag = PIL.ImageFile.LOAD_TRUNCATED_IMAGES
    assert flag is False
    yield
    assert PIL.ImageFile.LOAD_TRUNCATED_IMAGES is flag
    assert {n: hashlib.sha256(v.encode()).hexdigest() for n, v in VALUES.items()} == FROZEN


def test_environment_is_recorded():
    assert PIL.__version__ and len(CLEAN) > 623
    assert CLEAN[-2:] == b"\xff\xd9"
    assert CONTROLS["no_eoi"] == CLEAN[:-2]
    assert len(CONTROLS["head100"]) == 100


def test_clean_jpeg_passes_and_loads():
    assert _image(VALUES["clean"]).status == "pass"
    (f,) = _image_finding(VALUES["clean"])
    assert f.status == "pass"
    assert _load(CLEAN) == ("JPEG", (256, 256))


def test_eoi_removed_header_pass_but_independent_load_fails():
    _assert_legacy_pass_no_eoi()
    with pytest.raises(OSError):
        _load(CONTROLS["no_eoi"])


def test_header_truncated_oserror_escapes_every_layer(tmp_path):
    _assert_header_oserror_escapes()
    with pytest.raises(OSError):
        _load(CONTROLS["head100"])
    path = _write(tmp_path, "SM_head", VALUES["head100"])
    before = path.read_bytes()
    with pytest.raises(OSError):
        validate_package.validate(path, None, PROFILES)
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["SM_head.geojson"]


@pytest.mark.parametrize("name", ["bad_b64", "png"])
def test_ordinary_fail_findings_do_not_escape(name):
    assert _image(VALUES[name]).status == "fail"
    (f,) = _image_finding(VALUES[name])
    assert f.status == "fail"


def _cli(path: Path):
    return subprocess.run([sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)


@pytest.mark.parametrize("name", ["clean", "no_eoi"])
def test_cli_report_parses_with_v011_pass(tmp_path, name):
    p = _write(tmp_path, f"SM_{name}", VALUES[name])
    before = p.read_bytes()
    r = _cli(p)
    assert "Traceback" not in r.stderr
    rep = json.loads(r.stdout)
    v011 = [s for s in rep["stages"] if s["id"] == "V011"]
    assert len(v011) == 1 and v011[0]["status"] == "pass"
    assert rep["passed"] is False
    assert r.returncode == 2
    assert p.read_bytes() == before


def test_cli_header_truncated_has_no_report(tmp_path):
    p = _write(tmp_path, "SM_head", VALUES["head100"])
    r = _cli(p)
    assert r.returncode == 1
    assert r.stdout == ""
    assert "Traceback" in r.stderr and "OSError" in r.stderr


def test_mutation_pixel_load_breaks_legacy_pass(monkeypatch):
    original = geo._image

    def loading(value):
        finding = original(value)
        if finding.status == "pass":
            with Image.open(BytesIO(base64.b64decode(value, validate=True))) as img:
                img.load()
        return finding

    monkeypatch.setattr(geo, "_image", loading)
    with pytest.raises(OSError):
        _assert_legacy_pass_no_eoi()
    monkeypatch.undo()
    _assert_legacy_pass_no_eoi()


def test_mutation_oserror_to_finding_breaks_report_loss(monkeypatch):
    original = geo._image

    def normalizing(value):
        try:
            return original(value)
        except OSError as exc:
            return geo._f("fail", "imageBase64", f"not a decodable image ({exc.__class__.__name__})",
                          "base64 of a 256x256 JPG", [54])

    monkeypatch.setattr(geo, "_image", normalizing)
    with pytest.raises(pytest.fail.Exception):
        _assert_header_oserror_escapes()
    monkeypatch.undo()
    _assert_header_oserror_escapes()
