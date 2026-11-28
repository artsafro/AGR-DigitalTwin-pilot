from pathlib import Path
import runpy

import numpy as np
import pytest


@pytest.fixture
def clip():
    return runpy.run_path(str(Path(__file__).with_name('run.py')))['clip_band']


def test_clip_preserves_and_trims_without_adding_edges(clip):
    source = np.array([[1., -1., 2., -1.], [2., -3., 3., -1.],
                       [3., -1., 4., -3.], [5., -3., 6., -3.],
                       [7., -2., 7., -3.], [1., -2., 2., -2.]])
    out, count = clip(source, -2.)
    np.testing.assert_array_equal(out, [[1, -1, 2, -1], [2.5, -2, 3, -1],
                                        [3, -1, 3.5, -2], [1, -2, 2, -2]])
    assert count == {'trimmed': 2, 'dropped': 2}
    assert source[1, 1] == -3


def test_unchanged_and_empty_controls(clip):
    source = np.array([[1., -1., 2., -1.]])
    out, count = clip(source, -2.)
    np.testing.assert_array_equal(out, source)
    assert count == {'trimmed': 0, 'dropped': 0}
    out, count = clip(source, 0.)
    assert out.shape == (0, 4)
    assert count == {'trimmed': 0, 'dropped': 1}
