"""Same-part shells in open_borders_hidden. All meshes are SYNTHETIC.

A border is hidden by another part or by another shared-vertex component of the same part,
at least embed_min_m inside that shell. The component that owns the edge never hides it.
Pattern: none | new-case: same-part shell hiding for the open_borders_hidden kernel invariant.
"""
import numpy as np
import pytest

from dt_ai.ops.invariants import EMBED_MIN_M, Context, Mesh, border_edges, open_borders_hidden
from tests.ops.test_invariants import box

_FACES = ("bottom", "top", "front", "back", "left", "right")


def one_part(*meshes: Mesh) -> Mesh:
    """Concatenate shells without welding, so each keeps its own vertices."""
    verts, tris, offset = [], [], 0
    for mesh in meshes:
        verts.append(np.asarray(mesh.vertices, float))
        tris.append(np.asarray(mesh.triangles, int) + offset)
        offset += len(mesh.vertices)
    return Mesh(np.vstack(verts), np.vstack(tris))


def _embedded_pair(depth: float):
    """Closed wall and an open decor whose back rim lies `depth` metres past the wall's front (y = 0)."""
    wall = box((0, 0, 0), (4, 0.3, 3))
    decor = box((1, -0.2, 1), (2, depth, 2), drop=("back",))
    return wall, decor


def _edge_label(part: str, edge: np.ndarray) -> str:
    return f"{part}: edge {np.round(edge[0], 4).tolist()} -> {np.round(edge[1], 4).tolist()}"


def test_same_part_rim_embedded_at_least_embed_min_has_no_findings():
    """Closed box B and open box A in ONE part; A's rim is 15 mm inside B (>= 10 mm)."""
    wall, decor = _embedded_pair(0.015)
    scene = {"joined": one_part(wall, decor)}
    result = open_borders_hidden(scene, "joined", Context(embed_min_m=EMBED_MIN_M))
    assert result.passed and result.count == 0 and result.offenders == ()


def test_two_parts_with_the_same_embed_have_no_findings():
    wall, decor = _embedded_pair(0.015)
    result = open_borders_hidden({"wall": wall, "decor": decor}, "decor", Context(embed_min_m=EMBED_MIN_M))
    assert result.passed and result.count == 0 and result.offenders == ()


def test_same_part_rim_outside_names_every_rim_edge():
    wall = box((0, 0, 0), (4, 0.3, 3))
    decor = box((1, 2, 1), (2, 3, 2), drop=("back",))
    part = one_part(wall, decor)
    result = open_borders_hidden({"joined": part}, "joined", Context(embed_min_m=EMBED_MIN_M))
    edges = border_edges(part)
    assert len(edges) == 4
    assert not result.passed and result.count == 4
    assert set(result.offenders) == {_edge_label("joined", edge) for edge in edges}


def _shell_with_interior_rim() -> Mesh:
    """One shared-vertex shell: a closed box plus an open square deep inside it.

    The square shares a vertex with the box (via a stitch triangle) and no edge,
    so shared-vertex connectivity is one component. The square's rim is 0.8 m
    inside the box — deeper than embed_min — but that rim belongs to this shell.
    """
    outer = box((0, 0, 0), (2, 2, 2))
    inner = np.array([
        [0.8, 0.8, 1.0],
        [1.2, 0.8, 1.0],
        [1.2, 1.2, 1.0],
        [0.8, 1.2, 1.0],
    ], float)
    extra = np.array([[0.8, 0.8, 1.2]], float)
    vertices = np.vstack([outer.vertices, inner, extra])
    inner_tris = np.array([[8, 9, 10], [8, 10, 11]])
    stitch = np.array([[0, 8, 12]])          # touches the box and the square, shares neither of their edges
    triangles = np.vstack([outer.triangles, inner_tris, stitch])
    return Mesh(vertices, triangles)


def test_single_shell_does_not_hide_a_rim_inside_its_own_body():
    """An open box, and a shell whose own rim lies deep inside that same body, stay exposed."""
    opened = box((0, 0, 0), (1, 1, 1), drop=("top",))
    result = open_borders_hidden({"only": opened}, "only")
    assert not result.passed and result.count == len(border_edges(opened)) == 4
    assert set(result.offenders) == {_edge_label("only", edge) for edge in border_edges(opened)}

    shell = _shell_with_interior_rim()
    borders = border_edges(shell)
    inner = open_borders_hidden({"only": shell}, "only", Context(embed_min_m=EMBED_MIN_M))
    assert len(borders) > 4                       # the interior square adds rim edges
    assert not inner.passed and inner.count == len(borders)


def _samples_deep_in_box(edge: np.ndarray, lo, hi, embed: float) -> bool:
    """Independent of winding: every sample is inside the axis-aligned box, >= embed from its faces."""
    samples = np.vstack([edge[0], edge[1], edge.mean(axis=0)])
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return bool(np.all(samples >= lo + embed - 1e-9) and np.all(samples <= hi - embed + 1e-9))


@pytest.mark.parametrize("seed", range(8))
def test_probe_a_shell_never_hides_itself(seed):
    """Random open box, one component: every rim edge is reported."""
    rng = np.random.default_rng(seed)
    lo = rng.uniform(-2.0, 2.0, size=3)
    hi = lo + rng.uniform(0.3, 2.5, size=3)
    face = str(rng.choice(list(_FACES)))
    mesh = box(lo, hi, drop=(face,))
    result = open_borders_hidden({"only": mesh}, "only", Context(embed_min_m=EMBED_MIN_M))
    edges = border_edges(mesh)
    assert result.count == len(edges) == 4
    assert not result.passed
    assert set(result.offenders) == {_edge_label("only", edge) for edge in edges}


@pytest.mark.parametrize("seed", range(10))
def test_probe_same_part_reports_at_most_the_rim_outside_the_other_shell(seed):
    """Random open box beside a closed box in one part.

    Findings are exactly the rim edges that are not >= embed_min inside the closed box,
    so the count is at most the rim and never a self-hiding of that rim.
    """
    rng = np.random.default_rng(1000 + seed)
    closed_lo, closed_hi = (0.0, 0.0, 0.0), (4.0, 4.0, 4.0)
    size = rng.uniform(0.4, 0.8, size=3)
    center = rng.uniform(-1.0, 5.0, size=3)
    lo, hi = center - size / 2, center + size / 2
    face = str(rng.choice(list(_FACES)))
    part = one_part(box(closed_lo, closed_hi), box(lo, hi, drop=(face,)))
    edges = border_edges(part)
    exposed = [edge for edge in edges if not _samples_deep_in_box(edge, closed_lo, closed_hi, EMBED_MIN_M)]
    result = open_borders_hidden({"joined": part}, "joined", Context(embed_min_m=EMBED_MIN_M))
    assert result.count <= len(edges)
    assert result.count == len(exposed)
    assert set(result.offenders) == {_edge_label("joined", edge) for edge in exposed}


def test_unknown_empty_and_nonfinite_inputs_fail_closed():
    """NaN/inf never pass. An unmapped part key is an error that names the key."""
    solid = box((0, 0, 0), (1, 1, 1))
    with pytest.raises(ValueError, match="missing-part"):
        open_borders_hidden({"body": solid}, "missing-part")
    with pytest.raises(ValueError, match="missing-part"):
        open_borders_hidden({}, "missing-part")

    # An empty part has no border (a deleted part is checked by the coverage invariant, not here): unchanged.
    empty = Mesh(np.zeros((0, 3)), np.zeros((0, 3), int))
    assert open_borders_hidden({"gap": empty}, "gap").count == 0

    with pytest.raises(ValueError, match="finite"):
        Mesh([[np.nan, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
    with pytest.raises(ValueError, match="finite"):
        Mesh([[np.inf, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])

    opened = {"rim": box((0, 0, 0), (1, 1, 1), drop=("top",))}
    with pytest.raises(ValueError, match="finite"):
        open_borders_hidden(opened, "rim", Context(embed_min_m=float("nan")))
    with pytest.raises(ValueError, match="finite"):
        open_borders_hidden(opened, "rim", Context(embed_min_m=float("inf")))
    with pytest.raises(ValueError, match="finite"):
        open_borders_hidden(opened, "rim", Context(ground_z=float("nan")))
    with pytest.raises(ValueError, match="finite"):
        open_borders_hidden({"rim": solid}, "rim", Context(embed_min_m=float("nan")))
