"""Experiment only. Pure-array transcription; no bpy import or production integration."""
from collections import Counter
from dataclasses import dataclass
import numpy as np

XYZ_RADIUS = 0.002
UV_LIMIT = 2e-6


@dataclass
class Result:
    accepted: bool
    cardinality: int
    edges: int
    assignment: tuple


def structure_matches(faces, reference_faces):
    return (len(faces) == len(reference_faces)
            and Counter(str(len(p)) for p in faces)
            == Counter(str(len(p)) for p in reference_faces))


def baseline(expected, corners, reference_faces, faces):
    # Source tools/check_facades_max_roundtrip.py lines 13-23.
    # NumPy Euclidean radius query substitutes only KDTree.find_range.
    max_uv = 0.0
    chosen = []
    edges = 0
    for c in corners:
        distances = np.linalg.norm(expected[:, :3] - c[:3], axis=1)
        candidates = np.flatnonzero(distances <= XYZ_RADIUS)
        if not len(candidates):
            return Result(False, len(chosen), edges, tuple(chosen))
        errors = np.max(abs(expected[candidates, 3:] - c[3:]), axis=1)
        best = int(candidates[np.argmin(errors)])
        edges += int(np.count_nonzero(errors < UV_LIMIT))
        chosen.append(best)  # Deliberately reusable, as in the original.
        max_uv = max(max_uv, float(np.max(abs(expected[best, 3:] - c[3:]))))
    return Result(max_uv < UV_LIMIT and structure_matches(faces, reference_faces),
                  len(chosen), edges, tuple(chosen))


def maximum_matching(adjacency, right_count):
    """Sparse augmenting paths, including reassignment (not first-fit consumption)."""
    from collections import deque
    left_match = [-1] * len(adjacency)
    right_match = [-1] * right_count
    for root in range(len(adjacency)):
        queue = deque([root])
        parent = {}
        seen_left = {root}
        free = None
        while queue and free is None:
            left = queue.popleft()
            for right in adjacency[left]:
                if right in parent:
                    continue
                parent[right] = left
                owner = right_match[right]
                if owner == -1:
                    free = right
                    break
                if owner not in seen_left:
                    seen_left.add(owner)
                    queue.append(owner)
        while free is not None and free != -1:
            left = parent[free]
            previous = left_match[left]
            left_match[left] = free
            right_match[free] = left
            free = previous
    return tuple(left_match)


def candidate(expected, corners, reference_faces, faces):
    # Store only eligible edges. Row-at-a-time distances avoid a dense NxN matrix;
    # radius discovery is deliberately O(N*M) in this small synthetic harness.
    adjacency = []
    for c in corners:
        nearby = np.flatnonzero(
            np.linalg.norm(expected[:, :3] - c[:3], axis=1) <= XYZ_RADIUS)
        uv_ok = np.max(abs(expected[nearby, 3:] - c[3:]), axis=1) < UV_LIMIT
        adjacency.append(tuple(int(i) for i in nearby[uv_ok]))
    assignment = maximum_matching(adjacency, len(expected))
    cardinality = sum(i >= 0 for i in assignment)
    accepted = (cardinality == len(corners) == len(expected)
                and structure_matches(faces, reference_faces))
    return Result(accepted, cardinality, sum(map(len, adjacency)), assignment)
