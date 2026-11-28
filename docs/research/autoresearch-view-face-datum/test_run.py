import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location('datum162', Path(__file__).with_name('run.py'))
assert SPEC is not None and SPEC.loader is not None
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def test_registers_project_datum_without_stretching_missing_rows():
    # Page rows 12–15 cover the bottom four metres; top two are outside the clip.
    glass = np.ones((4, 2))
    mask = RUN.register(glass, 12, 1, ((16, 0), (10, 6)), 6, 1)
    assert mask.shape == (6, 2)
    np.testing.assert_array_equal(mask[:, 0], [0, 0, 1, 1, 1, 1])


def test_nonzero_second_datum_and_translation():
    glass = np.eye(4)
    mask = RUN.register(glass, 20, 2, ((12, 0), (10, 4)), 4, 1)
    np.testing.assert_array_equal(mask, glass)
    shifted = RUN.register(glass, 20, 2, ((12, -1), (10, 3)), 4, 1)
    np.testing.assert_array_equal(shifted[1:], glass[:-1])
    assert not shifted[0].any()


def test_missing_or_reversed_datum_refuses():
    params = (np.ones((2, 2)), 0, 1)
    assert RUN.register(*params, None, 6, 1) is None
    with pytest.raises(ValueError, match='anchors'):
        RUN.register(*params, ((10, 0), (12, 4)), 6, 1)
