"""LEGACY CHARACTERIZATION of current GeoJSON FNO_code behaviour (new-case, issue pilot #692).

These tests pin what V011 does today. They are NOT desired validation policy.
A schema pass on a non-string, a Unicode digit string, or a malformed Ground
FNO_code is a known unchecked boundary, never an endorsement and never delivery
acceptance. Synthetic fixtures only; no real object.
"""
import base64
import hashlib
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from twinqa.geojson import geojson_findings
from twinqa.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "tools" / "qa" / "validate_package.py"
PROFILE = load_profiles().vpm
KEYS = tuple(PROFILE["geojson"]["properties_keys"])

PASS = (("imageBase64", "pass"), ("Glasses", "pass"), ("schema", "pass"))
FORMAT_FAIL = (("FNO_code format", "fail"), ("imageBase64", "pass"), ("Glasses", "pass"))
EMPTY_FAIL = (("FNO_code empty", "fail"), ("imageBase64", "pass"), ("Glasses", "pass"))

ARABIC_INDIC_3 = "\u0661\u0662\u0663"
FULLWIDTH_3 = "\uff11\uff12\uff13"
SUPERSCRIPT_TWO_3 = "\u00b2\u00b2\u00b2"


def _jpeg_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (256, 256), (18, 92, 160)).save(buf, format="JPEG", quality=90)
    raw = buf.getvalue()
    with Image.open(BytesIO(raw)) as img:
        assert img.format == "JPEG" and img.size == (256, 256)
    return base64.b64encode(raw).decode("ascii")


IMAGE_B64 = _jpeg_b64()


def _document(fno) -> dict:
    """Otherwise-valid App.3 document. Only FNO_code changes between cases."""
    props = {}
    for key in KEYS:
        if key == "FNO_code":
            props[key] = fno
        elif key == "imageBase64":
            props[key] = IMAGE_B64
        elif key == "other":
            props[key] = ""
        else:
            props[key] = "synthetic"
    assert list(props) == list(KEYS) and len(KEYS) == 20
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "ObjectFeature",
            "geometry": {"type": "Point", "coordinates": [12345.678, 6789.012]},
            "properties": props,
            "Glasses": [],
        }],
    }


def _payload(fno) -> bytes:
    return json.dumps(_document(fno), ensure_ascii=False).encode("utf-8")


def _control_path(tmp_path: Path, case: str, role: str, fno) -> Path:
    """Per-case folder; the stem is what selects Ground (ctl_Ground) or OKS (ctl_OKS)."""
    folder = tmp_path / case
    folder.mkdir()
    name = "ctl_Ground.geojson" if role == "Ground" else "ctl_OKS.geojson"
    path = folder / name
    path.write_bytes(_payload(fno))
    return path


def _pairs(path: Path):
    """Caller uses the filename stem, the same rule as validate_package."""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    ground = path.stem.endswith("_Ground")
    found = geojson_findings(data, PROFILE, ground)
    assert hashlib.sha256(data).hexdigest() == digest
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    return tuple((item.name, item.status) for item in found)


@pytest.mark.parametrize("fno, expected", [
    pytest.param("123", PASS, id="legacy-oks-ascii-123"),
    pytest.param("123456", PASS, id="legacy-oks-ascii-123456"),
    pytest.param("123456789", PASS, id="legacy-oks-ascii-123456789"),
    pytest.param("123 456", PASS, id="legacy-oks-ascii-spaced-123-456"),
    pytest.param("1234", FORMAT_FAIL, id="legacy-oks-ascii-1234"),
    pytest.param("abc", FORMAT_FAIL, id="legacy-oks-ascii-abc"),
    pytest.param(None, EMPTY_FAIL, id="legacy-oks-null"),
    pytest.param("", EMPTY_FAIL, id="legacy-oks-empty"),
    pytest.param(123, PASS, id="legacy-oks-int-123"),
    pytest.param(1234, PASS, id="legacy-oks-int-1234"),
    pytest.param(True, PASS, id="legacy-oks-bool-true"),
    pytest.param([], PASS, id="legacy-oks-empty-list"),
    pytest.param({}, PASS, id="legacy-oks-empty-object"),
    pytest.param(ARABIC_INDIC_3, PASS, id="legacy-oks-arabic-indic-3"),
    pytest.param(FULLWIDTH_3, PASS, id="legacy-oks-fullwidth-3"),
    pytest.param(SUPERSCRIPT_TWO_3, PASS, id="legacy-oks-superscript-two"),
])
def test_legacy_oks_fno_code_findings(tmp_path, fno, expected):
    pairs = _pairs(_control_path(tmp_path, "case", "OKS", fno))
    assert pairs == expected
    if any(status == "fail" for _, status in pairs):
        assert ("schema", "pass") not in pairs


@pytest.mark.parametrize("fno", [
    pytest.param(None, id="legacy-ground-null"),
    pytest.param("", id="legacy-ground-empty"),
    pytest.param("1234", id="legacy-ground-ascii-1234"),
    pytest.param("abc", id="legacy-ground-ascii-abc"),
])
def test_legacy_ground_fno_code_currently_passes(tmp_path, fno):
    path = _control_path(tmp_path, "case", "Ground", fno)
    assert path.name == "ctl_Ground.geojson"
    assert path.stem.endswith("_Ground")
    assert _pairs(path) == PASS


def _cli(path: Path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    proc = subprocess.run(
        [sys.executable, str(CLI), str(path), "--profile", "vpm", "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120,
    )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    report = json.loads(proc.stdout)
    return proc, report


@pytest.mark.parametrize("role, fno, expected, exit_code", [
    pytest.param("OKS", "123", PASS, 2, id="legacy-cli-oks-ascii-123"),
    pytest.param("OKS", "1234", FORMAT_FAIL, 1, id="legacy-cli-oks-ascii-1234"),
    pytest.param("OKS", 123, PASS, 2, id="legacy-cli-oks-int-123"),
    pytest.param("OKS", SUPERSCRIPT_TWO_3, PASS, 2, id="legacy-cli-oks-superscript-two"),
    pytest.param("Ground", "", PASS, 2, id="legacy-cli-ground-empty"),
    pytest.param("Ground", "1234", PASS, 2, id="legacy-cli-ground-ascii-1234"),
])
def test_legacy_cli_v011_matches_helper(tmp_path, role, fno, expected, exit_code):
    path = _control_path(tmp_path, "case", role, fno)
    assert path.name == ("ctl_Ground.geojson" if role == "Ground" else "ctl_OKS.geojson")
    proc, report = _cli(path)
    assert "Traceback" not in (proc.stderr or "")
    v011 = [stage for stage in report["stages"] if stage["id"] == "V011"]
    assert len(v011) == 1
    report_pairs = tuple((item["name"], item["status"]) for item in v011[0]["findings"])
    assert _pairs(path) == report_pairs == expected
    assert v011[0]["status"] == ("fail" if any(status == "fail" for _, status in expected) else "pass")
    assert report["passed"] is False
    assert "delivery_passed" not in report
    assert proc.returncode == exit_code
