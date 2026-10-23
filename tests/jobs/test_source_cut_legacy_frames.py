"""new-case: legacy no-facades four-normal joint frames.

Function fixtures, not approved material allocations. One finish ``A`` in ``facade_uv``,
``P=[1, 1]``, ``joint_half_mm=4``, ``zero_m=0``, no ``facades`` block. ``cut_joint_report``
therefore takes each frame from ``joint_origin`` (minimum world coordinate on the facade axis).

One outward vertical rectangle per normal. Along-facade ``10..13.25`` (width ``3.25``),
perpendicular coordinate ``20``, ``z`` ``1..3``. Width ``3.25`` separates minimum origin ``10``
from maximum origin ``13.25``. Periodic distance is unchanged by sign reversal, so the frame,
the sign and ``u_m`` are pinned, not only ``ok``.

PR Acceptance (input -> exact expected frame/report -> test):

| input | expected frame | expected report | test |
|---|---|---|---|
| `-Y` quad `(10,20,1),(13.25,20,1),(13.25,20,3),(10,20,3)`; source only; shift `(0,0,0)` | `(0,+1,10)` | `new=0`, `checked=0`, `off=0`, `ok=True` | `test_acceptance[-Y-source]` |
| `-Y` plus bottom-edge `(11,20,1)` | `(0,+1,10)` | `new=1`, `checked=1`, `off=0`, `ok=True` | `test_acceptance[-Y-on]` |
| `-Y` plus bottom-edge `(11.125,20,1)` | `(0,+1,10)` | `new=1`, `checked=1`, `off=1`, `ok=False`; `source_polygon=0`, `u_m=+1.125`, `off_joint_m=0.125` | `test_acceptance[-Y-off]` |
| `+Y` quad `(10,20,1),(10,20,3),(13.25,20,3),(13.25,20,1)`; source only | `(0,-1,10)` | `new=0`, `checked=0`, `off=0`, `ok=True` | `test_acceptance[+Y-source]` |
| `+Y` plus `(11,20,1)` | `(0,-1,10)` | `new=1`, `checked=1`, `off=0`, `ok=True` | `test_acceptance[+Y-on]` |
| `+Y` plus `(11.125,20,1)` | `(0,-1,10)` | `new=1`, `checked=1`, `off=1`, `ok=False`; `source_polygon=0`, `u_m=-1.125`, `off_joint_m=0.125` | `test_acceptance[+Y-off]` |
| `+X` quad `(20,10,1),(20,13.25,1),(20,13.25,3),(20,10,3)`; source only | `(1,+1,10)` | `new=0`, `checked=0`, `off=0`, `ok=True` | `test_acceptance[+X-source]` |
| `+X` plus `(20,11,1)` | `(1,+1,10)` | `new=1`, `checked=1`, `off=0`, `ok=True` | `test_acceptance[+X-on]` |
| `+X` plus `(20,11.125,1)` | `(1,+1,10)` | `new=1`, `checked=1`, `off=1`, `ok=False`; `source_polygon=0`, `u_m=+1.125`, `off_joint_m=0.125` | `test_acceptance[+X-off]` |
| `-X` quad `(20,10,1),(20,10,3),(20,13.25,3),(20,13.25,1)`; source only | `(1,-1,10)` | `new=0`, `checked=0`, `off=0`, `ok=True` | `test_acceptance[-X-source]` |
| `-X` plus `(20,11,1)` | `(1,-1,10)` | `new=1`, `checked=1`, `off=0`, `ok=True` | `test_acceptance[-X-on]` |
| `-X` plus `(20,11.125,1)` | `(1,-1,10)` | `new=1`, `checked=1`, `off=1`, `ok=False`; `source_polygon=0`, `u_m=-1.125`, `off_joint_m=0.125` | `test_acceptance[-X-off]` |

Same complete reports for every cyclic face start (winding not reversed) and every
source-vertex permutation with remapped indices, including output minus literal pivot
``(8, -4, 0.5)`` plus that shift. Deep snapshots of the inputs stay unchanged.
Probes: ``test_cyclic_shift_probe`` 96/96, ``test_permutation_probe`` 576/576,
``test_literal_normal_probe`` 16/16.
"""
import copy
import itertools
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jobs/TEC26-OKS/scripts"))
import finish_map  # noqa: E402
import qa_packages  # noqa: E402

# Synthetic function fixture. Not an approved material allocation.
SPEC = {
    "zero_m": 0,
    "facade_uv": {"A": {}},
    "finishes": {"A": {"P": [1, 1], "joint_half_mm": 4}},
}

SOURCE_REPORT = {
    "ok": True,
    "new_vertices": 0,
    "checked_on_patterned_edges": 0,
    "off_joint": [],
    "off_joint_count": 0,
}
ON_REPORT = {
    "ok": True,
    "new_vertices": 1,
    "checked_on_patterned_edges": 1,
    "off_joint": [],
    "off_joint_count": 0,
}
OFF_POS = {
    "ok": False,
    "new_vertices": 1,
    "checked_on_patterned_edges": 1,
    "off_joint": [{"source_polygon": 0, "u_m": 1.125, "off_joint_m": 0.125}],
    "off_joint_count": 1,
}
OFF_NEG = {
    "ok": False,
    "new_vertices": 1,
    "checked_on_patterned_edges": 1,
    "off_joint": [{"source_polygon": 0, "u_m": -1.125, "off_joint_m": 0.125}],
    "off_joint_count": 1,
}

# Literal rings, frames, points and reports. Not derived from joint_origin.
FACES = {
    "-Y": {
        "quad": ((10, 20, 1), (13.25, 20, 1), (13.25, 20, 3), (10, 20, 3)),
        "frame": (0, 1, 10),
        "unit": (0, -1, 0),
        "on_point": (11, 20, 1),
        "off_point": (11.125, 20, 1),
        "source": SOURCE_REPORT,
        "on": ON_REPORT,
        "off": OFF_POS,
    },
    "+Y": {
        "quad": ((10, 20, 1), (10, 20, 3), (13.25, 20, 3), (13.25, 20, 1)),
        "frame": (0, -1, 10),
        "unit": (0, 1, 0),
        "on_point": (11, 20, 1),
        "off_point": (11.125, 20, 1),
        "source": SOURCE_REPORT,
        "on": ON_REPORT,
        "off": OFF_NEG,
    },
    "+X": {
        "quad": ((20, 10, 1), (20, 13.25, 1), (20, 13.25, 3), (20, 10, 3)),
        "frame": (1, 1, 10),
        "unit": (1, 0, 0),
        "on_point": (20, 11, 1),
        "off_point": (20, 11.125, 1),
        "source": SOURCE_REPORT,
        "on": ON_REPORT,
        "off": OFF_POS,
    },
    "-X": {
        "quad": ((20, 10, 1), (20, 10, 3), (20, 13.25, 3), (20, 13.25, 1)),
        "frame": (1, -1, 10),
        "unit": (-1, 0, 0),
        "on_point": (20, 11, 1),
        "off_point": (20, 11.125, 1),
        "source": SOURCE_REPORT,
        "on": ON_REPORT,
        "off": OFF_NEG,
    },
}

ACCEPTANCE = (
    ("-Y", "source"),
    ("-Y", "on"),
    ("-Y", "off"),
    ("+Y", "source"),
    ("+Y", "on"),
    ("+Y", "off"),
    ("+X", "source"),
    ("+X", "on"),
    ("+X", "off"),
    ("-X", "source"),
    ("-X", "on"),
    ("-X", "off"),
)
PIVOTS = ((0.0, 0.0, 0.0), (8.0, -4.0, 0.5))
MODES = ("source", "on", "off")


def literal_newell(ring):
    """Newell normal of a literal vertex ring. Independent of finish_map."""
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(ring):
        b = ring[(i + 1) % len(ring)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return tuple(n)


def assert_outward(ring, unit):
    n = literal_newell(ring)
    for axis in range(3):
        if unit[axis] == 0:
            assert n[axis] == 0
        else:
            assert n[axis] * unit[axis] > 0


def _world(quad, mode, row):
    pts = list(quad)
    if mode == "on":
        pts.append(row["on_point"])
    elif mode == "off":
        pts.append(row["off_point"])
    return pts


def _deliver(world, pivot):
    return [tuple(c - p for c, p in zip(pt, pivot)) for pt in world]


def _frozen_call(vertices, face, out, shift):
    """Run the legacy path and require a deep snapshot of every input to stay put."""
    src = [tuple(p) for p in vertices]
    fac = list(face)
    expected = ["A"]
    spec = copy.deepcopy(SPEC)
    output = [tuple(p) for p in out]
    sh = [shift[0], shift[1], shift[2]]
    before = copy.deepcopy((src, fac, expected, spec, output, sh))
    assert "facades" not in spec
    lo, hi = finish_map.body_plan_bbox(src, spec["zero_m"])
    frame = finish_map.joint_origin(src, fac, lo, hi)
    report = qa_packages.cut_joint_report(src, [fac], expected, spec, output, sh)
    assert (src, fac, expected, spec, output, sh) == before
    return frame, report


def _check(vertices, face, mode, row, pivot):
    frame, report = _frozen_call(vertices, face, _deliver(_world(vertices, mode, row), pivot), pivot)
    assert frame == row["frame"]
    assert report == row[mode]
    return frame, report


@pytest.mark.parametrize("normal,mode", ACCEPTANCE, ids=[f"{n}-{m}" for n, m in ACCEPTANCE])
def test_acceptance(normal, mode):
    row = FACES[normal]
    quad = row["quad"]
    assert_outward(quad, row["unit"])
    _check(quad, (0, 1, 2, 3), mode, row, (0.0, 0.0, 0.0))


def test_literal_normal_probe():
    """Every cyclic start keeps the literal outward normal (winding not reversed)."""
    n = 0
    for row in FACES.values():
        base = literal_newell(row["quad"])
        for start in range(4):
            face = (0, 1, 2, 3)[start:] + (0, 1, 2, 3)[:start]
            ring = [row["quad"][i] for i in face]
            assert literal_newell(ring) == base
            assert_outward(ring, row["unit"])
            n += 1
    assert n == 16


def test_cyclic_shift_probe():
    """All cyclic starts x 4 normals x 3 cuts x 2 shifts: same literal frame and report."""
    n = 0
    for row in FACES.values():
        quad = row["quad"]
        for start in range(4):
            face = (0, 1, 2, 3)[start:] + (0, 1, 2, 3)[:start]
            for mode in MODES:
                for pivot in PIVOTS:
                    _check(quad, face, mode, row, pivot)
                    n += 1
    assert n == 4 * 4 * 3 * 2


def test_permutation_probe():
    """Every source-vertex permutation, indices remapped, both pivots: same complete reports."""
    n = 0
    for row in FACES.values():
        quad = row["quad"]
        base = literal_newell(quad)
        for perm in itertools.permutations(range(4)):
            src = [quad[i] for i in perm]
            inv = {old: new for new, old in enumerate(perm)}
            face = [inv[i] for i in (0, 1, 2, 3)]
            assert literal_newell([src[i] for i in face]) == base
            for mode in MODES:
                for pivot in PIVOTS:
                    _check(src, face, mode, row, pivot)
                    n += 1
    assert n == 4 * 24 * 3 * 2
