"""new-case: polygon GeoJSON fixtures, valid ones parse, broken ones are broken (#885)."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / 'test-polygon' / 'geojson'


def test_valid_geojson_parses_and_passes_twinqa():
    from twinqa.geojson import geojson_findings
    from twinqa.profiles import load_profiles
    path = GEO / 'valid_oks.geojson'
    raw = path.read_bytes()
    json.loads(raw.decode('utf-8'))
    findings = geojson_findings(raw, load_profiles().vpm, ground=False, glass_names=None)
    assert findings
    assert all(f.status == 'pass' for f in findings), [(f.name, f.status, f.observed) for f in findings]


def test_broken_syntax_does_not_parse():
    raw = (GEO / 'broken_syntax.geojson').read_text(encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)


def test_broken_schema_parses_but_fails_the_checker():
    from twinqa.geojson import geojson_findings
    from twinqa.profiles import load_profiles
    raw = (GEO / 'broken_schema.geojson').read_bytes()
    json.loads(raw.decode('utf-8'))
    findings = geojson_findings(raw, load_profiles().vpm, ground=False, glass_names=None)
    assert any(f.status == 'fail' for f in findings)
