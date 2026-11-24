"""Synthetic adapter and inherited metric witnesses (not package labels)."""
import copy

import numpy as np
import pytest

from replay import adapt_atlas, upstream


def test_cell_rebase_preserves_pixels_and_excludes_material_boundary():
    rb = {"meshes": [{"name": "Main", "face_geometry": {
        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, -1, 0]],
        "polygons": [[0, 1, 2], [1, 0, 3]],
        "polygon_uv": [[[16/64, 42/64], [24/64, 42/64], [16/64, 56/64]],
                       [[56/64, 42/64], [48/64, 42/64], [56/64, 56/64]]],
    }}]}
    old = copy.deepcopy(rb)
    atlas = np.arange(64*64*3, dtype=np.uint16).reshape(64, 64, 3)
    plan = {"atlas": 64, "cell": 32, "region": 28, "pad": 2, "finishes": {
        "panel_a": {"udim": 1001, "u0": 2/64, "v0": 34/64, "size": 28/64},
        "panel_b": {"udim": 1002, "u0": 34/64, "v0": 34/64, "size": 28/64},
    }}
    new, tiles, census = adapt_atlas(rb, atlas, plan)
    assert rb == old
    assert census == {1001: 1, 1002: 1}
    shape = new["meshes"][0]["face_geometry"]
    assert shape["polygons"] == [[0, 1, 2], [1, 0, 3]]
    assert shape["polygon_uv"][0][0] == [0.5, 0.3125]
    assert shape["polygon_uv"][1][0] == [1.75, 0.3125]
    assert np.array_equal(tiles[1002][22, 24], atlas[22, 56])
    score = upstream()["measure"]
    with pytest.raises(ValueError, match="no seam samples"):
        score(new, tiles, {1001, 1002})
    rb["meshes"][0]["face_geometry"]["polygon_uv"][1][0][0] = 20/64
    with pytest.raises(ValueError, match="unique finish"):
        adapt_atlas(rb, atlas, plan)
