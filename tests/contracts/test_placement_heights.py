"""new-case: explicit vertical datum independent of horizontal CRS (#1330)."""
import pytest
from pydantic import ValidationError
from dt_ai.core.models import Placement

SOURCE = {"file": "R1.rvt", "locator": "Level ±0.000; D262"}


def placement(**kw):
    return dict(coordinate_system="MSK-77", project_zero_m=171.05,
                source={"kind": "model", "reference": "R1.rvt"}, status="proposed", **kw)


@pytest.mark.parametrize("fields", [{}, {"height_system": "unknown"}, {"height_source": SOURCE}])
def test_height_requires_provenance(fields):
    with pytest.raises(ValidationError, match="height"):
        Placement.model_validate(placement(**fields))


def test_height_formula():
    p = Placement.model_validate(placement(height_system="unknown", height_source=SOURCE,
        project_zero_fbx_z_m=-0.3, project_zero_fbx_source=SOURCE))
    assert p.heights(8.35) == {"h_relief": 171.05, "h_otn": 8.65, "h_abs": 179.7}


@pytest.mark.parametrize('system', ['MSK-77', 'BSV77', '', 'unknown\n'])
def test_height_system_enum(system):
    with pytest.raises(ValidationError):
        Placement.model_validate(placement(height_system=system, height_source=SOURCE))


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), True, '171.05'])
def test_bad_height(value):
    d = placement(height_system='unknown', height_source=SOURCE)
    d['project_zero_m'] = value
    with pytest.raises(ValidationError):
        Placement.model_validate(d)


def test_generated_height_formula():
    for zero in (169.65, 171.05, -10.0):
        for offset in (-1.4, 0.0, 1.4):
            d = placement(height_system='unknown', height_source=SOURCE,
                          project_zero_fbx_z_m=offset, project_zero_fbx_source=SOURCE)
            d['project_zero_m'] = zero
            p = Placement.model_validate(d)
            from decimal import Decimal
            expected = float(Decimal(str(zero)) + Decimal('8.65'))
            assert p.heights(offset + 8.65)['h_abs'] == expected


def test_kpp1_real_datum():
    import json
    from pathlib import Path
    d = json.loads(Path('jobs/KPP1/site-1255/height-datum.json').read_text(encoding='utf-8'))
    assert Placement.model_validate(d).heights(8.65) == {'h_relief': 171.05, 'h_otn': 8.65, 'h_abs': 179.7}
    import importlib.util
    spec = importlib.util.spec_from_file_location('kpp1_placement_heights', 'jobs/KPP1/site-1255/place_package.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.derive_heights(8.65) == {'h_relief': 171.05, 'h_otn': 8.65, 'h_abs': 179.7}


def test_schema_requires_height_provenance():
    import jsonschema
    schema = Placement.model_json_schema()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(placement(), schema)
