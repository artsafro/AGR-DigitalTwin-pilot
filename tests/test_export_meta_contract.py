"""new-case: strict shared export metadata contract (#1361)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool():
    path = ROOT / 'tools/derive/export_meta.py'
    assert path.is_file(), 'shared export_meta validator is missing'
    spec = importlib.util.spec_from_file_location('export_meta_1361', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_metadata_unknown_key_is_named():
    with pytest.raises(ValueError, match='h_otn_typo'):
        tool().validate_meta({'address': 'Synthetic', 'h_otn_model_max_z_m': 3.5,
                              'thumbnail': 'unknown', 'h_otn_typo': 3.5})


def test_metadata_missing_field_is_named():
    with pytest.raises(ValueError, match='address'):
        tool().validate_meta({'h_otn_model_max_z_m': 3.5, 'thumbnail': 'unknown'})
