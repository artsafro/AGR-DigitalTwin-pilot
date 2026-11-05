"""Legacy characterization of closed_shells under pure translation (report #765, Proposed next tasks 1).

Pattern: new-case: translation-only closed_shells verdicts on a 0.25 m tetrahedron and a 0.125 m box.
These tests pin what the unchanged public metric returns today. They do not approve the synthetic
(2**24, 2**24, 2**24) stress coordinates, a threshold, a coordinate convention or shell eligibility.
`delivery_passed` stays false. Literals are copied from the report, not from production helpers.
"""
from __future__ import annotations

import copy

import pytest

from tests.methods.test_building_body import rb_of
from tests.methods.test_methods_catalog import mesh, mm

TETRA_VERTS = ((0.0, 0.0, 0.0), (0.25, 0.0, 0.0), (0.0, 0.25, 0.0), (0.0, 0.0, 0.25))
TETRA_FACES = ((0, 3, 2), (0, 1, 3), (0, 2, 1), (1, 2, 3))
TETRA_PERM_REV = (3, 2, 1, 0)
TETRA_PERM_SWAP = (1, 0, 2, 3)

_S = 0.125
BOX_VERTS = ((0.0, 0.0, 0.0), (_S, 0.0, 0.0), (_S, _S, 0.0), (0.0, _S, 0.0),
             (0.0, 0.0, _S), (_S, 0.0, _S), (_S, _S, _S), (0.0, _S, _S))
BOX_FACES = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))

IDENTITY = (0.0, 0.0, 0.0)
OKS = (600000.0, 7500000.0, 150.0)
STRESS = (16777216.0, 16777216.0, 16777216.0)  # SYNTHETIC, 2**24

OPEN_EDGE = {"edge not shared by exactly two triangles": 1}
ZERO_VOL = {"zero enclosed volume": 1}


def _shift(verts, d):
    return [[p[0] + d[0], p[1] + d[1], p[2] + d[2]] for p in verts]


def _reverse(faces):
    return [[a, c, b] for a, b, c in faces]


def _permute(faces, order):
    return [list(faces[i]) for i in order]


def _rb(verts, faces):
    return rb_of(mesh("SM_Test_Main", verts, [list(f) for f in faces]))


def _run(verts, faces):
    rb = _rb(verts, faces)
    before = copy.deepcopy(rb)
    out = mm.closed_shells(rb)
    assert rb == before
    return out


def _expect(share, closed, reasons):
    return {"closed_shell_share": share, "components": 1, "closed_components": closed,
            "open_reasons": reasons, "weld_m": mm.SHELL_WELD_M, "reason": None}


def _tetra_variants():
    base = [list(f) for f in TETRA_FACES]
    return {"base": base, "reverse": _reverse(base),
            "perm_rev": _permute(TETRA_FACES, TETRA_PERM_REV),
            "perm_swap": _permute(TETRA_FACES, TETRA_PERM_SWAP),
            "perm_rev_reversed": _reverse(_permute(TETRA_FACES, TETRA_PERM_REV))}


@pytest.mark.parametrize("name", ["base", "reverse", "perm_rev", "perm_swap", "perm_rev_reversed"])
@pytest.mark.parametrize("shift", [IDENTITY, OKS])
def test_tetra_closed_at_identity_and_oks_scale(name, shift):
    verts = _shift(TETRA_VERTS, shift)
    assert _run(verts, _tetra_variants()[name]) == _expect(1.0, 1, {})


@pytest.mark.parametrize("name", ["base", "reverse", "perm_rev", "perm_swap", "perm_rev_reversed"])
def test_tetra_rejected_for_zero_volume_at_synthetic_stress(name):
    verts = _shift(TETRA_VERTS, STRESS)
    assert _run(verts, _tetra_variants()[name]) == _expect(0.0, 0, ZERO_VOL)


@pytest.mark.parametrize("shift", [IDENTITY, STRESS])
def test_box_closed_at_identity_and_stress(shift):
    assert _run(_shift(BOX_VERTS, shift), BOX_FACES) == _expect(1.0, 1, {})


@pytest.mark.parametrize("shift", [IDENTITY, STRESS])
def test_open_tetra_keeps_edge_reason_at_every_shift(shift):
    assert _run(_shift(TETRA_VERTS, shift), TETRA_FACES[:3]) == _expect(0.0, 0, OPEN_EDGE)


def test_translation_is_exact_dyadic_and_inputs_unchanged():
    for verts in (TETRA_VERTS, BOX_VERTS):
        for shift in (OKS, STRESS):
            moved = _shift(verts, shift)
            for p, q in zip(verts, moved):
                assert [q[i] - shift[i] for i in range(3)] == list(p)
    assert TETRA_VERTS[1] == (0.25, 0.0, 0.0) and len(BOX_FACES) == 12
