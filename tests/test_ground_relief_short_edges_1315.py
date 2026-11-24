"""#1315 Ground core relief stage: no edge <= 2 mm born from sub-grid TIN border slivers (SIL13 short edges).

Pattern: n/a | new-case: tests/test_ground_relief_short_edges_1315.py - relief-stage short-edge regressions.
Synthetic data below copies the SIL13 TIN pattern (border marks nearly collinear, height < 1 mm, 0.2 m Z jump);
it is SYNTHETIC, never a real object. The ``job`` test reads the real SIL13 source when it is on this PC.
"""
import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry import ground_site as gs

TOL = 0.002  # inv_xview NPM vertex tolerance, the #35 Qe edge threshold
# SIL13 t63/t64 pattern: the border mark (25.0, 0.163) sits 0.4 mm inside the hull chord, 0.2 m higher
SLIVER_PTS = [(0, -0.5, 0.0), (25.0, 0.163, 0.2), (37.731, 0.5, 0.0), (0, 20, 0.5), (37.731, 20, 0.4), (18, 10, 0.3)]
SIL13_SPEC = Path(__file__).parent / "fixtures/ground_1738/sil13-shared.json"


def _short_edges(verts, faces, limit=TOL):
    e = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1), axis=0)
    return int((np.linalg.norm(verts[e[:, 0]] - verts[e[:, 1]], axis=1) <= limit).sum())


def _heights(tin):
    q = tin.pts[tin.tris][:, :, :2]
    ln = np.linalg.norm(q - np.roll(q, -1, axis=1), axis=2).max(axis=1)
    d1, d2 = q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]
    return np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / ln


def test_build_tin_peels_border_sliver_keeps_points():
    raw = gc.build_tin(SLIVER_PTS)
    peeled = gc.build_tin(SLIVER_PTS, peel_slivers=True)
    assert (_heights(raw) <= 0.001).sum() == 1 and raw.slivers_peeled == 0  # default unchanged (v015 bytes)
    assert peeled.slivers_peeled == 1 and len(peeled.tris) == len(raw.tris) - 1
    assert (_heights(peeled) > 0.001).all()
    assert len(peeled.pts) == len(raw.pts) and set(np.unique(peeled.tris)) == set(range(len(peeled.pts)))


def test_peel_never_drops_inner_thin_triangle():
    # a thin triangle with neighbours on all three sides lies between marks (not a hull artefact): kept, reported
    P = np.array([(0, 0, 0), (10, 0.0005, 0.2), (20, 0, 0), (10, 10, 1), (10, -10, 1)], float)
    tris = np.array([[0, 1, 2], [0, 3, 1], [1, 3, 2], [0, 2, 4]])
    kept, peeled, inner = gc._peel_border_slivers(P, tris, 0.001)
    assert (peeled, inner) == (0, 1) and kept.tolist() == tris.tolist()


@pytest.mark.parametrize("cell", [3.0, 4.0])
def test_relief_stage_adds_no_short_edges_over_border_sliver(cell):
    site = box(0.5, 0.0, 37.0, 19.0)
    r = gs.build_site(site, [gs.Cover(1, "Base", [site], (10, 10, 10), "spec")], 1, SLIVER_PTS, 0.0,
                      origin_xy=(0.0, 0.0), surfaces="shared", cell=cell,
                      relief_extension={"max_m": 1.0, "reason": "synthetic test strip outside the hull"})
    m = r.mesh
    assert _short_edges(m.verts, m.faces) == 0
    assert r.report["stages"]["zero"]["tin_slivers_peeled"] == 1
    assert r.report["stages"]["relief"]["relief_error"].get("over_tol", 0) == 0


def _sil13_dxf():
    spec = json.loads(SIL13_SPEC.read_text(encoding="utf-8"))
    return spec, Path(spec["dxf"]["path"])


@pytest.mark.job
@pytest.mark.skipif(not _sil13_dxf()[1].exists(), reason="SIL13 source DXF (Google Drive) not on this PC")
def test_sil13_core_ground_has_no_short_edges(tmp_path):
    """SIL13 shared core (#1738 spec): before the fix 185 edges <= 2 mm (167 relief), 414 xView vertex pairs."""
    import ezdxf
    spec, dxf = _sil13_dxf()
    assert gs.sha256(dxf) == spec["dxf"]["sha256"]
    doc = ezdxf.readfile(str(dxf))
    p = spec["params"]
    chord = float(p.get("chord", 0.02))
    r = gs.build_site(gs.boundary_from_dxf(doc, spec["boundary"]["handle"]),
                      gs.covers_from_dxf(doc, spec["covers"], max(chord, 0.002)), spec["base_id"],
                      gs.relief_from_dxf(doc, spec["relief"]), spec["zero"]["project_zero_m"],
                      origin_xy=p.get("origin_xy"), crop_box=spec.get("crop_box"), unhatched=spec.get("unhatched"),
                      **{k: v for k, v in p.items() if k != "origin_xy"})
    m = r.mesh
    assert _short_edges(m.verts, m.faces) == 0
    assert not r.report["stages"]["skirt"]["skirt_gap_edges"]
    from dt_ai.ops.inv_xview import mesh_report
    xv = mesh_report(m.verts, m.faces, profile="NPM-GROUND", part="SM_SIL13_Ground")
    assert (xv["vertex_pairs"], xv["face_pairs"]) == (0, 0)  # before the #1315 rim-step cut: (0, 2) skirt contacts


# review r1 P1: peeling must never orphan a source mark (its Z would be lost silently)
ORPHAN_CASES = {
    "mark_on_hull_chord": [(0, 0, 0), (20, 0, 0), (10, 0, 0), (10, 0.0008, 0.3), (0, 20, 0.5), (20, 20, 0.4)],
    "two_marks_in_sliver": [(0, 0, 0), (20, 0, 0), (10, 0.0004, 0.3), (10, 0.0009, 0.0), (0, 20, 0.5),
                            (20, 20, 0.4), (10, 10, 0.2)],
}


@pytest.mark.parametrize("name", sorted(ORPHAN_CASES))
def test_peel_keeps_every_source_mark(name):
    pts = ORPHAN_CASES[name]
    tin = gc.build_tin(pts, peel_slivers=True)
    assert set(np.unique(tin.tris)) == set(range(len(tin.pts)))  # no mark without a triangle
    assert tin.slivers_inner >= 1  # the thin triangle kept to hold the mark is reported
    z, hit = gc.ReliefSampler(tin).sample(tin.pts[:, :2])
    assert hit.all() and np.allclose(z, tin.pts[:, 2], atol=1e-9)
