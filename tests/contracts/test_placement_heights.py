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
