"""SYNTHETIC xView incremental state lifetime characterization.

Pattern: none | new-case: serialized edit chains, retained-pair renumbering and
recovery from a rejected middle-step cache without caller mutation.
"""

from copy import deepcopy
import json

import numpy as np
import pytest

from dt_ai.ops.inv_xview import xview_state, xview_state_incremental


def _roundtrip(state):
    return json.loads(json.dumps(state, allow_nan=False))


def _scene(order, far_x, b_z):
    """One triangle per part, independent vertex IDs even for overlapping faces."""
    origins = {
        "a": (0.0, 0.0), "b": (0.0, b_z),
        "c": (far_x, 0.0), "d": (far_x, 0.003), "e": (-20.0, 0.0),
    }
    vertices, faces = [], []
    for label in order:
        x, z = origins[label]
        start = len(vertices)
        vertices.extend(((x, 0.0, z), (x + 1.0, 0.0, z), (x, 1.0, z)))
        faces.append([start, start + 1, start + 2])
    return np.asarray(vertices), faces, list(order)


def _assert_contacts(state, labels, touching):
    # Oracle uses only fixture labels and the prescribed contact pairs, not checker output.
    ids = {label: i for i, label in enumerate(labels, start=1)}
    expected = sorted(tuple(sorted((ids[a], ids[b]))) for a, b in touching)
    assert [tuple(pair[:2]) for pair in state["face_pairs"]] == expected
    for _, _, kind, separation in state["face_pairs"]:
        assert kind == "area+contact"
        assert separation == pytest.approx(0.003, rel=0, abs=1e-15)
    selection = sorted({i for pair in expected for i in pair})
    assert state["xview_faces"] == state["faces"] == selection
    assert state["vertex_pairs"] == state["vertices"] == []


@pytest.mark.parametrize(
    "base_order,far_x",
    [(tuple("abcd"), 10.0), (tuple("cadb"), 20.0)],
    ids=["adjacent-pairs", "interleaved-pairs"],
)
def test_incremental_serialized_edit_chain(base_order, far_x):
    """Each incremental output is the next input, including after failed recovery."""
    both = (("a", "b"), ("c", "d"))
    vertices, faces, labels = _scene(base_order, far_x, 0.003)
    initial_inputs = (vertices.copy(), deepcopy(faces), labels.copy())
    previous = _roundtrip(xview_state(vertices, faces, labels))
    np.testing.assert_array_equal(vertices, initial_inputs[0])
    assert (faces, labels) == initial_inputs[1:]
    _assert_contacts(previous, labels, both)
    initial = deepcopy(previous)
    history = [(previous, deepcopy(previous))]

    steps = [
        ("move-out", base_order, 0.020, ["b"], (("c", "d"),)),
        ("move-back", base_order, 0.003, ["b"], both),
        ("insert-e-before", ("e",) + base_order, 0.003, ["e"], both),
        ("remove-e-recover", base_order, 0.003, ["e"], both),
        ("remove-b", tuple(x for x in base_order if x != "b"), 0.003, ["b"], (("c", "d"),)),
        ("re-add-b", base_order, 0.003, ["b"], both),
        ("no-op", base_order, 0.003, [], both),
    ]
    for step, order, b_z, changed, touching in steps:
        vertices, faces, labels = _scene(order, far_x, b_z)
        inputs = (vertices.copy(), deepcopy(faces), labels.copy(), changed.copy())
        before = deepcopy(previous)

        if step == "remove-e-recover":
            broken = deepcopy(previous)
            del broken["face_pairs"]
            broken_before = deepcopy(broken)
            with pytest.raises(ValueError, match="previous"):
                xview_state_incremental(vertices, faces, labels, broken, changed)
            assert broken == broken_before
            assert previous == before
            np.testing.assert_array_equal(vertices, inputs[0])
            assert (faces, labels, changed) == inputs[1:]

        current = xview_state_incremental(vertices, faces, labels, previous, changed)
        assert previous == before, step
        np.testing.assert_array_equal(vertices, inputs[0], err_msg=step)
        assert (faces, labels, changed) == inputs[1:], step
        current = _roundtrip(current)
        _assert_contacts(current, labels, touching)
        # Compare ALL fields, not just selections: pair metrics, digest, summaries,
        # part hashes/counts, runs, links, vertex inventory and version/thresholds.
        assert current == _roundtrip(xview_state(vertices, faces, labels)), step
        np.testing.assert_array_equal(vertices, inputs[0], err_msg=step)
        assert (faces, labels, changed) == inputs[1:], step
        if step == "re-add-b":
            assert current == initial
        if step == "no-op":
            assert current == previous
        for old_state, snapshot in history:
            assert old_state == snapshot, step
        history.append((current, deepcopy(current)))
        previous = current
