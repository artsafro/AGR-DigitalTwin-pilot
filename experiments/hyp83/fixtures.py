"""Frozen synthetic fixtures for #83; verdicts specified before running either method."""
from dataclasses import dataclass
import numpy as np

# Four triangles, shared XYZ but separate UV islands; units: metres and UV units.
SEAMS = (
    (0, 0, 0, 0, 0), (1, 0, 0, 0, 0), (0, 1, 0, 0, 0),
    (0, 0, 0, 1, 0), (1, 0, 0, 1, 0), (1, 1, 0, 1, 0),
    (0, 0, 0, 2, 0), (2, 0, 0, 2, 0), (2, 1, 0, 2, 0),
    (0, 0, 0, 3, 0), (3, 0, 0, 3, 0), (3, 1, 0, 3, 0),
)
UNIQUE = tuple((i, i % 3, 0, i / 16, 0) for i in range(12))
FACES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11))
# Whole-face reorder plus cyclic/reversed corner order. Exactly three fixed orders.
ORDERS = (
    tuple(range(12)),
    (8, 6, 7, 2, 0, 1, 11, 9, 10, 5, 3, 4),
    (11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)

@dataclass(frozen=True)
class Case:
    name: str
    reference: tuple
    observed: tuple
    expected: bool
    faces: tuple = FACES


def replace(rows, replacements):
    result = list(rows)
    for destination, source in replacements:
        result[destination] = rows[source]
    return tuple(result)


REPEATED = replace(SEAMS, ((6, 0),))
CASES = (
    Case('identical', UNIQUE, UNIQUE, True),
    Case('face_corner_reorder', SEAMS, tuple(SEAMS[i] for i in ORDERS[1]), True),
    Case('legitimate_repeats', REPEATED, REPEATED, True),
    Case('distinct_seam_uv', SEAMS, SEAMS, True),
    Case('replace_one_seam', SEAMS, replace(SEAMS, ((0, 3),)), False),
    Case('duplicate_two_tuples', SEAMS, replace(SEAMS, ((0, 3), (1, 4))), False),
    Case('collapse_vertex_uvs', SEAMS, replace(SEAMS, ((3, 0), (6, 0))), False),
    Case('replace_island_corner', SEAMS, replace(SEAMS, ((9, 0),)), False),
)


def arrays(case, permutation):
    # Independently reorder both sides, not just matching indices.
    reference = np.array(case.reference, dtype=float)[list(ORDERS[(permutation + 1) % 3])]
    observed = np.array(case.observed, dtype=float)[list(ORDERS[permutation])]
    return reference, observed
