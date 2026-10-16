"""Contract of the `model-maf` project skill (#182).

The skill is an agent procedure: specification and SPOZU points -> library pick -> model from the reference ->
dimension check -> NPM light version -> one 512 atlas -> hard edges -> placement with sinking -> checks, each step
with a tool route, a Needs marker and a completion criterion, and links instead of copied rule text.
`skill_findings` is the checker; the generated mutations prove it rejects each kind of breakage, not only that the
real file passes. The procedure probes below implement the dimension, seating, smoothing and atlas rules in pure
Python (no DCC) and check them against generated inputs.
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import re
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/model-maf/SKILL.md"
SHEET = ROOT / "docs/domain/areas/groundel-maf.md"
DECISIONS = ROOT / "docs/decisions.md"
CONFLICTS = ROOT / "docs/domain/conflicts.md"

# (step number, words its heading must contain), in procedure order.
STEPS = [
    (1, ("specification", "spozu", "maf points")),
    (2, ("pick", "library")),
    (3, ("model", "reference")),
    (4, ("check", "specification")),
    (5, ("light version", "npm")),
    (6, ("shared", "512", "atlas")),
    (7, ("hard edges", "angle")),
    (8, ("placement", "spozu", "sinking")),
    (9, ("checks", "handover")),
]
STEP_TOKENS = {
    1: ("DXFOUT", "ezdxf", "rotation", "$INSUNITS"),
    2: ("library/maf/catalogue.json", "spec_matches", "npm_matches", "visual selection", "МАФы_Union_ALLin.max"),
    3: ("manufacturer picture", "legend scheme", "separate verify line"),
    4: ("10 cm", "[D094]", "colour", "material layout", "construction", "review"),
    5: ("fewer segments", "round parts", "[D097]", "npm_matches"),
    6: ("512", "64", "128", "patterned", "atlas_maf.py"),
    7: ("30-45", "360/N"),
    8: ("lowest point", "10 cm", "[D095]", "[D096]", "project", "bottom faces", "rotation", "downhill"),
    9: ("separate", "verify line", "validate-delivery", "[D096]"),
}
ROUTE_TOOLS = (
    "dcc_batch.py acad", "ezdxf", "dcc_batch.py max", "3ds Max batch", "Blender headless",
    "atlas_maf.py", "validate_package.py", "catalogue",
)
NEEDS = ("headless", "live", "human")
VERIFY_STEPS = (3, 9)
STEP_RE = re.compile(r"^### Step (\d+) — (.+)$", re.M)
LINK_RE = re.compile(r"\]\(([^)#\s]+)(#[^)\s]*)?\)")
DIM_EPS = 1e-9


def _steps(text: str) -> list[tuple[int, str, str]]:
    marks = list(STEP_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        tail = text.find("\n## ", m.end())
        if tail != -1 and tail < end:
            end = tail
        out.append((int(m.group(1)), m.group(2), text[m.end():end]))
    return out


def _shingles(text: str, n: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[\wА-Яа-яЁё]+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _rule_text() -> str:
    """Rule text the skill must link, not copy: the sheet's MAF rows and every decision line."""
    sheet = [line for line in SHEET.read_text(encoding="utf-8").splitlines() if line.startswith("| MAF-")]
    decisions = [line for line in DECISIONS.read_text(encoding="utf-8").splitlines() if line.startswith("| D")]
    return "\n".join(sheet + decisions)


def skill_findings(text: str, base: Path = SKILL.parent) -> list[str]:
    found: list[str] = []
    lines = text.splitlines()
    parts = text.split("---", 2)
    if not lines or lines[0] != "---" or len(parts) < 3 or "name: model-maf" not in parts[1]:
        found.append("frontmatter: missing `name: model-maf`")
    steps = _steps(text)
    numbers = [n for n, _, _ in steps]
    if numbers != [n for n, _ in STEPS]:
        found.append(f"steps: expected 1..9 in order, got {numbers}")
    by_number = {n: (title, body) for n, title, body in steps}
    for n, words in STEPS:
        if n not in by_number:
            continue
        title, body = by_number[n]
        for word in words:
            if word not in title.lower():
                found.append(f"step {n}: heading lacks {word!r}")
        for token in STEP_TOKENS[n]:
            if token not in body:
                found.append(f"step {n}: body lacks {token!r}")
        if n in VERIFY_STEPS and "separate verify line" not in body:
            found.append(f"step {n}: missing separate verify line for an individually made MAF")
        route = re.search(r"^- Route: (.+(?:\n  .+)*)", body, re.M)
        if not route or not any(tool in route.group(1) for tool in ROUTE_TOOLS):
            found.append(f"step {n}: no `- Route:` line naming an existing tool route")
        need = re.search(r"^- Needs: (.+)$", body, re.M)
        if not need or not any(re.search(rf"\b{m}\b", need.group(1)) for m in NEEDS):
            found.append(f"step {n}: no `- Needs:` line with headless/live/human")
        elif n == 3 and not re.search(r"\bhuman\b", need.group(1)):
            found.append("step 3: `- Needs:` does not mark the user (human)")
        if not re.search(r"^- Done when: .+", body, re.M):
            found.append(f"step {n}: no completion criterion")
    targets = {}
    for m in LINK_RE.finditer(text):
        if m.group(1).startswith("http"):
            continue
        path = (base / m.group(1)).resolve()
        targets[m.group(1)] = path
        if not path.exists():
            found.append(f"link: {m.group(1)} does not exist")
        elif m.group(2) and m.group(2) != "#":
            anchor = m.group(2)[1:]
            heads = {re.sub(r"[^\w\- ]", "", h.strip("# ").lower()).replace(" ", "-")
                     for h in path.read_text(encoding="utf-8").splitlines() if h.startswith("#")}
            if anchor not in heads:
                found.append(f"link: anchor #{anchor} not in {m.group(1)}")
    names = {Path(t).name for t in targets}
    for required in ("groundel-maf.md", "decisions.md"):
        if required not in names:
            found.append(f"link: no link to {required}")
    decided = set(re.findall(r"^\| (D\d+) ", DECISIONS.read_text(encoding="utf-8"), re.M))
    for d in set(re.findall(r"\[(D\d+)\]", text)) - decided:
        found.append(f"decision {d} is not in docs/decisions.md")
    conflict_ids = set(re.findall(r"^(\d+)\. ", CONFLICTS.read_text(encoding="utf-8"), re.M))
    for c in set(re.findall(r"\bC(\d+)\b", text)) - conflict_ids:
        found.append(f"conflict C{c} is not in docs/domain/conflicts.md")
    copied = _shingles(text) & _shingles(_rule_text())
    if copied:
        found.append(f"rule text copied: {' '.join(sorted(copied)[0])!r} (+{len(copied) - 1})")
    if "«" in text and re.search(r"«[^»]{40,}»", text):
        found.append("rule text copied: long «quotation»")
    return found


@pytest.fixture(scope="module")
def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_exists_with_frontmatter(text):
    assert text.splitlines()[0] == "---" and "name: model-maf" in text.split("---")[1]


def test_skill_has_no_findings(text):
    assert skill_findings(text) == []


def test_steps_in_issue_order(text):
    assert [n for n, _, _ in _steps(text)] == list(range(1, 10))


def test_every_step_has_route_needs_done(text):
    for n, _, body in _steps(text):
        assert re.search(r"^- Route: ", body, re.M), n
        assert re.search(r"^- Needs: (headless|live|human)", body, re.M), n
        assert re.search(r"^- Done when: ", body, re.M), n


def test_individually_made_maf_has_a_separate_verify_line(text):
    bodies = {n: body for n, _, body in _steps(text)}
    for n in VERIFY_STEPS:
        assert "separate verify line" in bodies[n], n
        assert "individually made" in bodies[n], n
    need = re.search(r"^- Needs: (.+)$", bodies[3], re.M)
    assert need and re.search(r"\bhuman\b", need.group(1))


def test_empty_input_rejected():
    found = skill_findings("")
    assert any(f.startswith("frontmatter") for f in found)
    assert any(f.startswith("steps:") for f in found)
    assert any(f.startswith("link:") for f in found)


def _mutations(text: str):
    steps = _steps(text)
    block = {n: f"### Step {n} — {title}{body}" for n, title, body in steps}
    for n in block:
        yield f"drop step {n}", text.replace(block[n], "")
    for (a, *_), (b, *_) in zip(steps, steps[1:]):
        yield f"swap {a}/{b}", text.replace(block[a] + block[b], block[b] + block[a])
    for n, title, body in steps:
        for prefix in ("- Route: ", "- Needs: ", "- Done when: "):
            line = next(ln for ln in body.splitlines() if ln.startswith(prefix))
            yield f"step {n} no {prefix.strip()}", text.replace(block[n], block[n].replace(line, ""))
        need = next(ln for ln in body.splitlines() if ln.startswith("- Needs: "))
        yield f"step {n} bogus needs", text.replace(block[n], block[n].replace(need, "- Needs: maybe"))
    for n, tokens in STEP_TOKENS.items():
        for token in tokens:
            yield f"step {n} lacks {token}", text.replace(block[n], block[n].replace(token, "X"))
    yield "broken link", text.replace("docs/domain/areas/groundel-maf.md)", "docs/domain/areas/groundel-mafs.md)", 1)
    yield "broken anchor", text.replace("#project-practice", "#project-practise")
    yield "unknown decision", text.replace("[D094]", "[D9094]", 1)
    rows = [ln for ln in SHEET.read_text(encoding="utf-8").splitlines() if ln.startswith("| MAF-")]
    for i, row in enumerate(rows):
        cell = max(row.split(" | ")[2:5], key=len)
        yield f"copied MAF row {i + 1}", text + "\n" + cell + "\n"
    for n in VERIFY_STEPS:
        yield f"step {n} no separate verify line", text.replace(
            block[n], block[n].replace("separate verify line", "X"))


def test_generated_mutations_are_rejected(text):
    mutations = list(_mutations(text))
    unchanged = [name for name, mutated in mutations if mutated == text]
    missed = [name for name, mutated in mutations if mutated != text and not skill_findings(mutated)]
    assert not unchanged, unchanged
    assert not missed, f"{len(missed)}/{len(mutations)} mutations passed: {missed}"
    assert len(mutations) >= 100


# ---- Procedure probes (pure Python, no DCC). ------------------------------------------------------------------

def dimension_verdict(model_lwh, spec_lwh, tol=0.10) -> str:
    """Pass when the best plan orientation (L/W may swap, H may not) is within tol. Missing spec -> review."""
    if any(value is None for value in spec_lwh):
        return "review"
    orientations = (model_lwh, (model_lwh[1], model_lwh[0], model_lwh[2]))
    best = min(max(abs(m - s) for m, s in zip(option, spec_lwh)) for option in orientations)
    return "pass" if best <= tol + DIM_EPS else "fail"


def _reference_verdict(model_lwh, spec_lwh, tol=0.10) -> str:
    """Brute force: min over the two L/W orientations of the max absolute deviation."""
    if any(value is None for value in spec_lwh):
        return "review"
    direct = max(abs(m - s) for m, s in zip(model_lwh, spec_lwh))
    swapped = max(abs(m - s) for m, s in zip((model_lwh[1], model_lwh[0], model_lwh[2]), spec_lwh))
    return "pass" if min(direct, swapped) <= tol + DIM_EPS else "fail"


def _verdict_without_swap(model_lwh, spec_lwh, tol=0.10) -> str:
    if any(value is None for value in spec_lwh):
        return "review"
    direct = max(abs(m - s) for m, s in zip(model_lwh, spec_lwh))
    return "pass" if direct <= tol + DIM_EPS else "fail"


def _closed_box(x0, y0, z0, x1, y1, z1):
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = [
        (0, 3, 2, 1),  # bottom, outward normal -Z
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    return verts, faces


def _offset_faces(verts, faces, start):
    return verts, [tuple(i + start for i in face) for face in faces]


def _unit_normal(verts, face):
    a, b, c = (verts[i] for i in face[:3])
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


class Tin:
    """Triangle mesh Ground. `height` is None outside coverage; calling raises ValueError there."""

    def __init__(self, points, triangles):
        self.points = tuple((float(x), float(y), float(z)) for x, y, z in points)
        self.triangles = tuple(tuple(tri) for tri in triangles)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        self._bounds = (min(xs), max(xs), min(ys), max(ys))

    def height(self, x, y):
        minx, maxx, miny, maxy = self._bounds
        if x < minx - 1e-9 or x > maxx + 1e-9 or y < miny - 1e-9 or y > maxy + 1e-9:
            return None
        for tri in self.triangles:
            z = _bary_z(self.points, tri, x, y)
            if z is not None:
                return z
        return None

    def __call__(self, x, y):
        z = self.height(x, y)
        if z is None:
            raise ValueError(f"outside TIN coverage: {(x, y)}")
        return z


def _bary_z(points, tri, x, y, eps=1e-9):
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = (points[i] for i in tri)
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(den) < 1e-18:
        return None
    w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / den
    w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / den
    w2 = 1.0 - w0 - w1
    if w0 >= -eps and w1 >= -eps and w2 >= -eps:
        return w0 * z0 + w1 * z1 + w2 * z2
    return None


def _plane_tin(a, b, c, half=100.0):
    """Two triangles over the square [-half, half]^2 on the plane z = a*x + b*y + c."""
    corners = ((-half, -half), (half, -half), (half, half), (-half, half))
    points = [(x, y, a * x + b * y + c) for x, y in corners]
    return Tin(points, ((0, 1, 2), (0, 2, 3)))


def _depression_tin(cx, cy, rx, ry, depth, a=0.0, b=0.0, c=0.0, half=100.0):
    """Plane plus a diamond pit: centre `depth` below the plane, four corners on the plane.

    Four inner triangles plus the eight named links from the diamond to the square:
    (S0,S1,Sd), (S1,S2,E), (S2,S3,N), (S3,S0,W), (S1,E,Sd), (S2,N,E), (S3,W,N), (S0,Sd,W).
    """
    def pz(x, y, drop=0.0):
        return a * x + b * y + c - drop

    s0 = (-half, -half, pz(-half, -half))
    s1 = (half, -half, pz(half, -half))
    s2 = (half, half, pz(half, half))
    s3 = (-half, half, pz(-half, half))
    sd = (cx, cy - ry, pz(cx, cy - ry))
    east = (cx + rx, cy, pz(cx + rx, cy))
    north = (cx, cy + ry, pz(cx, cy + ry))
    west = (cx - rx, cy, pz(cx - rx, cy))
    centre = (cx, cy, pz(cx, cy, depth))
    points = (s0, s1, s2, s3, sd, east, north, west, centre)
    triangles = (
        (4, 5, 8), (5, 6, 8), (6, 7, 8), (7, 4, 8),
        (0, 1, 4), (1, 2, 5), (2, 3, 6), (3, 0, 7),
        (1, 5, 4), (2, 6, 5), (3, 7, 6), (0, 4, 7),
    )
    return Tin(points, triangles)


def _point_in_poly(x, y, poly, eps=1e-9):
    """Even-odd test. Points on the outline count as inside."""
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if _on_segment(x, y, x1, y1, x2, y2, eps):
            return True
    inside = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xinter = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xinter:
                inside = not inside
    return inside


def _on_segment(px, py, ax, ay, bx, by, eps=1e-9):
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > eps * max(1.0, math.hypot(bx - ax, by - ay)):
        return False
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    if dot < -eps:
        return False
    length2 = (bx - ax) ** 2 + (by - ay) ** 2
    return dot <= length2 + eps * max(1.0, math.sqrt(length2))


def _segment_hit(p, q, r, s, eps=1e-12):
    """Intersection of segments pq and rs, or None when parallel or disjoint."""
    rx, ry = q[0] - p[0], q[1] - p[1]
    sx, sy = s[0] - r[0], s[1] - r[1]
    den = rx * sy - ry * sx
    scale = max(1.0, math.hypot(rx, ry), math.hypot(sx, sy))
    if abs(den) <= eps * scale:
        return None
    qpx, qpy = r[0] - p[0], r[1] - p[1]
    t = (qpx * sy - qpy * sx) / den
    u = (qpx * ry - qpy * rx) / den
    if -eps <= t <= 1.0 + eps and -eps <= u <= 1.0 + eps:
        return (p[0] + t * rx, p[1] + t * ry)
    return None


def _plane_z_at(verts, face, x, y):
    p0, p1, p2 = (verts[i] for i in face[:3])
    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nz = ux * vy - uy * vx
    return p0[2] - ((uy * vz - uz * vy) * (x - p0[0]) + (uz * vx - ux * vz) * (y - p0[1])) / nz


def _tin_edges(ground):
    seen = set()
    edges = []
    for i, j, k in ground.triangles:
        for a, b in ((i, j), (j, k), (k, i)):
            key = (a, b) if a < b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            pa, pb = ground.points[key[0]], ground.points[key[1]]
            edges.append(((pa[0], pa[1]), (pb[0], pb[1])))
    return edges


def _tin_boundary_edges(ground):
    """XY segments of edges that belong to exactly one triangle (border or a hole rim)."""
    counts: dict[tuple[int, int], int] = {}
    for i, j, k in ground.triangles:
        for a, b in ((i, j), (j, k), (k, i)):
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    segments = []
    for a, b in counts:
        if counts[(a, b)] != 1:
            continue
        pa, pb = ground.points[a], ground.points[b]
        segments.append(((pa[0], pa[1]), (pb[0], pb[1])))
    return segments


def _boundary_meets_footprint(ground, poly) -> bool:
    """True when a coverage-boundary edge has an end in the polygon or cuts an outline side."""
    outline = list(zip(poly, poly[1:] + poly[:1]))
    for a, b in _tin_boundary_edges(ground):
        if _point_in_poly(a[0], a[1], poly) or _point_in_poly(b[0], b[1], poly):
            return True
        for side in outline:
            if _segment_hit(a, b, side[0], side[1]) is not None:
                return True
    return False


def _witnesses_strictly_under(seated, face, ground) -> bool:
    """Round-2 rule: every gap witness is strictly under the Ground and inside coverage.

    Witnesses are the face vertices, TIN vertices on the outline, and TIN-edge crossings
    with the outline. A witness outside the mesh fails the check. No coverage precondition.
    """
    poly = [(seated[i][0], seated[i][1]) for i in face]
    candidates = list(poly)
    for px, py, _pz in ground.points:
        if _point_in_poly(px, py, poly):
            candidates.append((px, py))
    outline = list(zip(poly, poly[1:] + poly[:1]))
    for edge in _tin_edges(ground):
        for side in outline:
            hit = _segment_hit(edge[0], edge[1], side[0], side[1])
            if hit is not None:
                candidates.append(hit)
    for x, y in candidates:
        h = ground.height(x, y)
        if h is None:
            return False
        if not (_plane_z_at(seated, face, x, y) < h - 1e-9):
            return False
    return True


def _footprint_strictly_under(seated, face, ground) -> bool:
    """True only when coverage is proven and every gap witness is strictly under the Ground.

    Coverage is a separate precondition, before the height proof. For interior-disjoint
    triangles, the boundary of the covered area consists of boundary edges; if the face
    vertices are covered and no boundary edge meets the convex footprint, the whole
    footprint is covered. Non-conforming meshes (T-junctions) only make more edges look
    like boundary, so the rule stays conservative. Only then the witness height loop runs.
    """
    poly = [(seated[i][0], seated[i][1]) for i in face]
    for index in face:
        x, y, _z = seated[index]
        if ground.height(x, y) is None:
            return False
    if _boundary_meets_footprint(ground, poly):
        return False
    return _witnesses_strictly_under(seated, face, ground)


def _place(vertices, insert_xy, rotation_deg, ground):
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    px, py, pz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs) + 0.10
    theta = math.radians(rotation_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    ix, iy = insert_xy
    tx, ty, tz = ix - px, iy - py, ground(ix, iy) - pz
    seated = []
    for x, y, z in vertices:
        dx, dy = x - px, y - py
        rx = px + dx * cos_t - dy * sin_t
        ry = py + dx * sin_t + dy * cos_t
        seated.append((rx + tx, ry + ty, z + tz))
    return seated


def _split_bottoms(seated, faces, predicate):
    deleted, exposed, kept = [], [], []
    for face in faces:
        if _unit_normal(seated, face)[2] < -0.5:
            if predicate(face):
                deleted.append(face)
            else:
                exposed.append(face)
                kept.append(face)
        else:
            kept.append(face)
    return kept, deleted, exposed


def seat_maf(vertices, faces, insert_xy, rotation_deg, ground):
    """Pivot to bbox centre XY and zmin+0.10, rotate about it, drop the pivot onto the Ground.

    `ground` is a Tin. A face whose unit normal has n_z < -0.5 is a bottom. It is deleted only
    when the Ground covers the whole footprint and that footprint is strictly under the Ground.
    Coverage comes first: every face vertex has a Ground height, and no boundary edge (an edge
    of exactly one triangle — the mesh border or a hole) meets the closed outline. For
    interior-disjoint triangles that proves a convex footprint is covered; T-junctions only add
    boundary edges, so the test stays conservative. Only then every face vertex, every TIN
    vertex inside or on the outline, and every TIN-edge crossing with the outline must have a
    TIN height strictly above the face plane (z_face < height - 1e-9). Exactly on the Ground
    stays. Missing coverage keeps the face and lists it as exposed (review).
    """
    if not vertices or not faces:
        return [], [], [], []
    seated = _place(vertices, insert_xy, rotation_deg, ground)
    kept, deleted, exposed = _split_bottoms(
        seated, faces, lambda face: _footprint_strictly_under(seated, face, ground))
    return seated, kept, deleted, exposed


def _witness_only_seat(vertices, faces, insert_xy, rotation_deg, ground):
    """Round-2 rule: witness heights only, with no coverage precondition. Unsafe on holes."""
    if not vertices or not faces:
        return [], [], [], []
    seated = _place(vertices, insert_xy, rotation_deg, ground)
    kept, deleted, exposed = _split_bottoms(
        seated, faces, lambda face: _witnesses_strictly_under(seated, face, ground))
    return seated, kept, deleted, exposed


def _vertex_only_seat(vertices, faces, insert_xy, rotation_deg, ground):
    """Old rule: delete a bottom when every vertex is strictly below the Ground at its own XY."""
    if not vertices or not faces:
        return [], [], [], []
    seated = _place(vertices, insert_xy, rotation_deg, ground)

    def below(face):
        for index in face:
            x, y, z = seated[index]
            h = ground.height(x, y)
            if h is None or not (z < h):
                return False
        return True

    kept, deleted, exposed = _split_bottoms(seated, faces, below)
    return seated, kept, deleted, exposed


def _centre_only_seat(vertices, faces, insert_xy, rotation_deg, ground):
    """Negative control: vertices plus the face centroid, nothing in between."""
    if not vertices or not faces:
        return [], [], [], []
    seated = _place(vertices, insert_xy, rotation_deg, ground)

    def below(face):
        points = [seated[i] for i in face]
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        cz = sum(p[2] for p in points) / len(points)
        points.append((cx, cy, cz))
        for x, y, z in points:
            h = ground.height(x, y)
            if h is None or not (z < h):
                return False
        return True

    kept, deleted, exposed = _split_bottoms(seated, faces, below)
    return seated, kept, deleted, exposed


def _delete_every_bottom(vertices, faces, insert_xy, rotation_deg, ground):
    """Negative control: deletes bottom faces even when a vertex stays at or above the Ground."""
    seated, kept, deleted, exposed = seat_maf(vertices, faces, insert_xy, rotation_deg, ground)
    deleted = list(deleted) + list(exposed)
    exposed_set = set(exposed)
    kept = [face for face in kept if face not in exposed_set]
    return seated, kept, deleted, []


def _no_visible_hole(seated, deleted, ground) -> bool:
    """Sample each deleted face on a barycentric grid. Outside coverage is a hole.

    Independent of the candidate-point deletion rule: fan-triangulate, then a grid of at
    least 40 subdivisions per triangle, including edges and vertices. Every sample must
    sit strictly below the TIN.
    """
    n = 40
    inv = 1.0 / n
    for face in deleted:
        count = len(face)
        for t in range(1, count - 1):
            a = seated[face[0]]
            b = seated[face[t]]
            c = seated[face[t + 1]]
            for i in range(n + 1):
                for j in range(n + 1 - i):
                    k = n - i - j
                    x = (i * a[0] + j * b[0] + k * c[0]) * inv
                    y = (i * a[1] + j * b[1] + k * c[1]) * inv
                    z = (i * a[2] + j * b[2] + k * c[2]) * inv
                    h = ground.height(x, y)
                    if h is None or not (z < h):
                        return False
    return True


def _random_maf(rng: random.Random):
    """1-4 closed-box legs under one closed-box top. Every leg bottom sits on z = 0."""
    n_legs = rng.randint(1, 4)
    top_w = rng.uniform(0.6, 2.4)
    top_d = rng.uniform(0.5, 1.2)
    top_h = rng.uniform(0.05, 0.25)
    leg_h = rng.uniform(0.25, 1.1)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for i in range(n_legs):
        lx = rng.uniform(0.05, 0.16)
        ly = rng.uniform(0.05, 0.16)
        cx = -top_w / 2 + (i + 0.5) * top_w / n_legs
        span = top_d / 2 - ly / 2
        cy = rng.uniform(-span, span)
        box_v, box_f = _offset_faces(*_closed_box(cx - lx / 2, cy - ly / 2, 0.0, cx + lx / 2, cy + ly / 2, leg_h), len(verts))
        verts.extend(box_v)
        faces.extend(box_f)
    top_v, top_f = _offset_faces(
        *_closed_box(-top_w / 2, -top_d / 2, leg_h, top_w / 2, top_d / 2, leg_h + top_h), len(verts))
    verts.extend(top_v)
    faces.extend(top_f)
    return verts, faces


def _bench():
    """2 m wide footprint, bottom on z = 0, centred on the origin."""
    return _closed_box(-1.0, -0.2, 0.0, 1.0, 0.2, 0.45)


def _pivot_holds(original, seated, insert_xy, rotation_deg, ground) -> bool:
    xs = [v[0] for v in original]
    ys = [v[1] for v in original]
    zs = [v[2] for v in original]
    px, py, pz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs) + 0.10
    dz = seated[0][2] - original[0][2]
    ix, iy = insert_xy
    if abs((pz + dz) - ground(ix, iy)) > 1e-9:
        return False
    for origin, moved in zip(original, seated):
        if abs((moved[2] - origin[2]) - dz) > 1e-9:
            return False
        before = (origin[0] - px) ** 2 + (origin[1] - py) ** 2
        after = (moved[0] - ix) ** 2 + (moved[1] - iy) ** 2
        if abs(before - after) > 1e-8:
            return False
    farthest = max(range(len(original)), key=lambda i: (original[i][0] - px) ** 2 + (original[i][1] - py) ** 2)
    ox, oy, _ = original[farthest]
    sx, sy, _ = seated[farthest]
    if (ox - px) ** 2 + (oy - py) ** 2 > 1e-8:
        delta = (math.atan2(sy - iy, sx - ix) - math.atan2(oy - py, ox - px)) % (2 * math.pi)
        expect = math.radians(rotation_deg) % (2 * math.pi)
        err = min(abs(delta - expect), 2 * math.pi - abs(delta - expect))
        if err > 1e-6:
            return False
    return True


def _zmin_bottoms(original, faces, seated):
    zmin = min(v[2] for v in original)
    found = []
    for face in faces:
        if _unit_normal(seated, face)[2] >= -0.5:
            continue
        if all(abs(original[i][2] - zmin) < 1e-9 for i in face):
            found.append(face)
    return found


def test_dimension_edges_and_random_reference():
    assert dimension_verdict((1.10, 2.0, 3.0), (1.0, 2.0, 3.0)) == "pass"
    assert dimension_verdict((1.1001, 2.0, 3.0), (1.0, 2.0, 3.0)) == "fail"
    assert dimension_verdict((1.0, 2.0, 3.10), (1.0, 2.0, 3.0)) == "pass"
    assert dimension_verdict((1.0, 2.0, 3.1001), (1.0, 2.0, 3.0)) == "fail"
    # Plan swap is allowed; swapping height with length is not.
    assert dimension_verdict((2.10, 1.0, 3.0), (1.0, 2.0, 3.0)) == "pass"
    assert dimension_verdict((3.0, 2.0, 1.0), (1.0, 2.0, 3.0)) == "fail"
    assert dimension_verdict((0.94, 0.40, 0.40), (0.40, 0.40, 0.94)) == "fail"
    assert dimension_verdict((1.0, 2.0, 3.0), (1.0, None, 3.0)) == "review"
    assert dimension_verdict((1.0, 2.0, 3.0), (None, None, None)) == "review"
    # Negative control: ignoring the L/W swap disagrees with the reference.
    swapped = ((2.0, 1.0, 3.0), (1.0, 2.0, 3.0))
    assert dimension_verdict(*swapped) == _reference_verdict(*swapped) == "pass"
    assert _verdict_without_swap(*swapped) == "fail"

    rng = random.Random(182)
    disagreements = 0
    for _ in range(2000):
        spec = [rng.uniform(0.2, 4.0) for _ in range(3)]
        model = [value + rng.uniform(-0.3, 0.3) for value in spec]
        if rng.random() < 0.5:
            model[0], model[1] = model[1], model[0]
        if rng.random() < 0.08:
            spec[rng.randrange(3)] = None
        spec_t, model_t = tuple(spec), tuple(model)
        assert dimension_verdict(model_t, spec_t) == _reference_verdict(model_t, spec_t)
        if all(value is not None for value in spec_t):
            if dimension_verdict(model_t, spec_t) != _verdict_without_swap(model_t, spec_t):
                disagreements += 1
    assert disagreements > 0


def test_seat_random_mafs_and_slope_bench():
    rng = random.Random(182)
    flat_cases = 0
    for case in range(1000):
        verts, faces = _random_maf(rng)
        flat = rng.random() < 0.5
        slope_x = 0.0 if flat else rng.uniform(-0.3, 0.3)
        slope_y = 0.0 if flat else rng.uniform(-0.3, 0.3)
        offset = rng.uniform(-2.0, 2.0)
        ground = _plane_tin(slope_x, slope_y, offset)
        insert = (rng.uniform(-20.0, 20.0), rng.uniform(-20.0, 20.0))
        rotation = rng.uniform(0.0, 360.0)
        seated, kept, deleted, exposed = seat_maf(verts, faces, insert, rotation, ground)
        assert _pivot_holds(verts, seated, insert, rotation, ground), case
        assert _no_visible_hole(seated, deleted, ground), case
        zmin_faces = _zmin_bottoms(verts, faces, seated)
        assert zmin_faces, case
        if flat:
            flat_cases += 1
            assert abs(min(v[2] for v in seated) - (ground(*insert) - 0.10)) < 1e-9, case
            assert all(face in deleted for face in zmin_faces), case
            assert not any(face in exposed for face in zmin_faces), case
        assert len(kept) + len(deleted) == len(faces)
    assert flat_cases > 0

    def _plane(slope):
        return _plane_tin(slope, 0.0, 0.0)

    wide, wide_faces = _bench()
    steep, kept_s, deleted_s, exposed_s = seat_maf(wide, wide_faces, (0.0, 0.0), 0.0, _plane(0.15))
    assert exposed_s and not deleted_s
    assert _no_visible_hole(steep, deleted_s, _plane(0.15))
    mild, kept_m, deleted_m, exposed_m = seat_maf(wide, wide_faces, (0.0, 0.0), 0.0, _plane(0.05))
    assert exposed_m == [] and len(deleted_m) == 1 and deleted_m[0] in wide_faces
    assert _pivot_holds(wide, mild, (0.0, 0.0), 0.0, _plane(0.05))
    # A vertex that lands exactly on the Ground is not strictly below, so the bottom stays exposed.
    level, _, deleted_l, exposed_l = seat_maf(wide, wide_faces, (0.0, 0.0), 0.0, _plane(0.10))
    assert exposed_l and not deleted_l
    assert not _no_visible_hole(level, exposed_l, _plane(0.10))
    # Negative control: deleting every bottom opens a visible hole on the steep slope.
    bad_seated, _, bad_deleted, _ = _delete_every_bottom(wide, wide_faces, (0.0, 0.0), 0.0, _plane(0.15))
    assert not _no_visible_hole(bad_seated, bad_deleted, _plane(0.15))


def test_seat_empty_mesh():
    ground = _plane_tin(0.0, 0.0, 1.0)
    assert seat_maf([], [], (0.0, 0.0), 0.0, ground) == ([], [], [], [])
    assert seat_maf([(0.0, 0.0, 0.0)], [], (0.0, 0.0), 15.0, ground) == ([], [], [], [])


def _reviewer_lambda(x, y):
    return -0.30 * max(0.0, 1.0 - abs(x - 0.5) / 0.2 - abs(y) / 0.15)


def test_depression_tin_matches_reviewer_lambda():
    tin = _depression_tin(0.5, 0.0, 0.2, 0.15, 0.30)
    for i in range(-40, 61):
        for j in range(-20, 21):
            x, y = i * 0.05, j * 0.05
            h = tin.height(x, y)
            assert h is not None, (x, y)
            assert abs(h - _reviewer_lambda(x, y)) < 1e-9, (x, y, h)
    assert abs(tin(0.5, 0.0) - (-0.30)) < 1e-12
    assert tin.height(0.5, 0.0) == tin(0.5, 0.0)
    assert tin.height(250.0, 0.0) is None
    with pytest.raises(ValueError):
        tin(250.0, 0.0)
    sloped = _depression_tin(0.5, 0.0, 0.2, 0.15, 0.30, a=0.02, b=-0.01, c=1.5)
    for x, y in ((0.5, 0.0), (0.7, 0.0), (0.0, 0.0), (-3.0, 2.0)):
        expect = 0.02 * x - 0.01 * y + 1.5 + _reviewer_lambda(x, y)
        assert abs(sloped(x, y) - expect) < 1e-9


def _offcentre_pit(verts, faces, rotation, insert, rng):
    """World XY of a barycentric sample inside a zmin bottom, away from its centre and vertices."""
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    px, py = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    theta = math.radians(rotation)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    ix, iy = insert
    xy = []
    for x, y, _z in verts:
        dx, dy = x - px, y - py
        xy.append((px + dx * cos_t - dy * sin_t + ix - px, py + dx * sin_t + dy * cos_t + iy - py))
    zmin = min(v[2] for v in verts)
    bottoms = [
        face for face in faces
        if _unit_normal(verts, face)[2] < -0.5 and all(abs(verts[i][2] - zmin) < 1e-9 for i in face)
    ]
    rng.shuffle(bottoms)
    n = 40
    for face in bottoms:
        centroid = (
            sum(xy[i][0] for i in face) / len(face),
            sum(xy[i][1] for i in face) / len(face),
        )
        for _ in range(16):
            i = rng.randint(6, 16)
            j = rng.randint(6, 16)
            k = n - i - j
            if k < 6:
                continue
            p0, p1, p2 = xy[face[0]], xy[face[1]], xy[face[2]]
            x = (i * p0[0] + j * p1[0] + k * p2[0]) / n
            y = (i * p0[1] + j * p1[1] + k * p2[1]) / n
            if math.hypot(x - ix, y - iy) < 0.05:
                continue
            if math.hypot(x - centroid[0], y - centroid[1]) < 0.01:
                continue
            if any(math.hypot(x - xy[v][0], y - xy[v][1]) < 0.01 for v in face):
                continue
            return (x, y)
    return None


def test_seat_depression_under_bottom_is_kept():
    wide, wide_faces = _bench()
    bottom = wide_faces[0]
    ground = _depression_tin(0.5, 0.0, 0.2, 0.15, 0.30)
    seated, _kept, deleted, exposed = seat_maf(wide, wide_faces, (0.0, 0.0), 0.0, ground)
    assert bottom not in deleted and bottom in exposed
    assert all(abs(seated[i][2] - (-0.10)) < 1e-9 for i in bottom)
    assert not _no_visible_hole(seated, [bottom], ground)
    old_seated, _k, old_deleted, _e = _vertex_only_seat(wide, wide_faces, (0.0, 0.0), 0.0, ground)
    assert bottom in old_deleted
    assert not _no_visible_hole(old_seated, old_deleted, ground)

    rng = random.Random(182)
    unsafe_vertex = 0
    unsafe_centre = 0
    deleted_cases = 0
    for case in range(500):
        verts, faces = _random_maf(rng)
        insert = (rng.uniform(-20.0, 20.0), rng.uniform(-20.0, 20.0))
        rotation = rng.uniform(0.0, 360.0)
        slope_x = rng.uniform(-0.05, 0.05)
        slope_y = rng.uniform(-0.05, 0.05)
        offset = rng.uniform(-1.0, 1.0)
        kind = case % 3
        pit = None if kind == 1 else _offcentre_pit(verts, faces, rotation, insert, rng)
        if pit is None:
            cx, cy = insert[0] + 30.0, insert[1] + 12.0
            depth, rx, ry = 0.30, 0.40, 0.30
        else:
            cx, cy = pit
            rx = ry = 0.004
            depth = 0.30 if kind == 0 else rng.uniform(0.005, 0.02)
        ground = _depression_tin(cx, cy, rx, ry, depth, slope_x, slope_y, offset)
        seated, _kept, deleted, _exposed = seat_maf(verts, faces, insert, rotation, ground)
        assert _pivot_holds(verts, seated, insert, rotation, ground), case
        assert _no_visible_hole(seated, deleted, ground), case
        if deleted:
            deleted_cases += 1
        if pit is not None and kind == 0:
            v_seated, _vk, v_deleted, _ve = _vertex_only_seat(verts, faces, insert, rotation, ground)
            if not _no_visible_hole(v_seated, v_deleted, ground):
                unsafe_vertex += 1
            c_seated, _ck, c_deleted, _ce = _centre_only_seat(verts, faces, insert, rotation, ground)
            if not _no_visible_hole(c_seated, c_deleted, ground):
                unsafe_centre += 1
    assert unsafe_vertex > 0
    assert unsafe_centre > 0
    assert deleted_cases > 0


def test_seat_bottom_partly_outside_coverage_is_kept():
    wide, wide_faces = _bench()
    bottom = wide_faces[0]
    # Insert (0, 0) is covered; the bench's x=-1 edge is not.
    ground = Tin(
        ((-0.25, -50.0, 0.0), (50.0, -50.0, 0.0), (50.0, 50.0, 0.0), (-0.25, 50.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
    )
    _seated, _kept, deleted, exposed = seat_maf(wide, wide_faces, (0.0, 0.0), 0.0, ground)
    assert bottom not in deleted and bottom in exposed


def _square_ring_tin(insert, gap_dx, gap_dy, half_w, half_h, a, b, c, half=5.0):
    """Square ring over insert ± half. Outer corners 0..3, gap corners 4..7.

    Eight triangles follow the internal-gap reproducer. Heights are the plane z = a*x + b*y + c.
    The inner rectangle sits strictly inside the outer square, so the triangles do not overlap
    and leave the gap uncovered.
    """
    if half_w <= 0 or half_h <= 0:
        raise ValueError("degenerate gap")
    ix, iy = insert
    gx, gy = ix + gap_dx, iy + gap_dy
    corners = (
        (ix - half, iy - half),
        (ix + half, iy - half),
        (ix + half, iy + half),
        (ix - half, iy + half),
        (gx - half_w, gy - half_h),
        (gx + half_w, gy - half_h),
        (gx + half_w, gy + half_h),
        (gx - half_w, gy + half_h),
    )
    if not all(ix - half < x < ix + half and iy - half < y < iy + half for x, y in corners[4:]):
        raise ValueError("gap is not strictly inside the outer square")
    points = [(x, y, a * x + b * y + c) for x, y in corners]
    triangles = (
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    )
    tin = Tin(points, triangles)
    if tin.height(gx, gy) is not None:
        raise ValueError("gap centre is covered")
    for tri in triangles:
        mx = sum(points[i][0] for i in tri) / 3
        my = sum(points[i][1] for i in tri) / 3
        owners = sum(1 for other in triangles if _bary_z(points, other, mx, my) is not None)
        if owners != 1:
            raise ValueError(f"triangle {tri} centroid is owned by {owners} triangles")
        area2 = (
            (points[tri[1]][0] - points[tri[0]][0]) * (points[tri[2]][1] - points[tri[0]][1])
            - (points[tri[2]][0] - points[tri[0]][0]) * (points[tri[1]][1] - points[tri[0]][1])
        )
        if abs(area2) < 1e-12:
            raise ValueError(f"triangle {tri} is degenerate")
    return tin


def _ring_slope(rng, case):
    """Flat in two thirds of cases; a mild slope in the other third. Offset always in [-1, 1]."""
    c = rng.uniform(-1.0, 1.0)
    if case % 3 != 0:
        return 0.0, 0.0, c
    a = rng.uniform(-0.05, 0.05)
    b = rng.uniform(-0.05, 0.05)
    if abs(a) < 1e-6 and abs(b) < 1e-6:
        a = 0.02
    return a, b, c


def _rect_fully_outside(poly, cx, cy, half_w, half_h) -> bool:
    rect = [
        (cx - half_w, cy - half_h),
        (cx + half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    ]
    if any(_point_in_poly(x, y, poly) for x, y in rect):
        return False
    if any(_point_in_poly(x, y, rect) for x, y in poly):
        return False
    outline = list(zip(poly, poly[1:] + poly[:1]))
    sides = list(zip(rect, rect[1:] + rect[:1]))
    for a, b in outline:
        for c, d in sides:
            if _segment_hit(a, b, c, d) is not None:
                return False
    return True


def test_seat_internal_gap_reproducer():
    v, f = _bench()
    g = Tin(
        [(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0),
         (.35, -.1, 0), (.65, -.1, 0), (.65, .1, 0), (.35, .1, 0)],
        [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
         (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)],
    )
    s, _kept, deleted, exposed = seat_maf(v, f, (0, 0), 0, g)
    assert g.height(.5, 0) is None
    assert f[0] not in deleted and f[0] in exposed
    assert _no_visible_hole(s, deleted, g)
    ws, _wk, w_deleted, _we = _witness_only_seat(v, f, (0, 0), 0, g)
    assert f[0] in w_deleted
    assert not _no_visible_hole(ws, w_deleted, g)


def test_seat_internal_gaps_generated():
    rng = random.Random(27702)
    n = 200
    unsafe = 0
    for case in range(n):
        verts, faces = _bench()
        bottom = faces[0]
        insert = (rng.uniform(-3.0, 3.0), rng.uniform(-3.0, 3.0))
        gap_dx = rng.uniform(0.25, 0.7)
        gap_dy = rng.uniform(-0.06, 0.06)
        half_w = rng.uniform(0.08, 0.15)
        a, b, c = _ring_slope(rng, case)
        ground = _square_ring_tin(insert, gap_dx, gap_dy, half_w, 0.10, a, b, c)
        seated, _kept, deleted, exposed = seat_maf(verts, faces, insert, 0.0, ground)
        assert bottom not in deleted and bottom in exposed, case
        assert _no_visible_hole(seated, deleted, ground), case
        assert _pivot_holds(verts, seated, insert, 0.0, ground), case
        w_seated, _wk, w_deleted, _we = _witness_only_seat(verts, faces, insert, 0.0, ground)
        if bottom in w_deleted and not _no_visible_hole(w_seated, w_deleted, ground):
            unsafe += 1
    assert unsafe == n

    outside_deleted = 0
    sloped = 0
    accepted = 0
    draws = 0
    while accepted < n:
        draws += 1
        assert draws < n * 20
        verts, faces = _bench()
        bottom = faces[0]
        insert = (rng.uniform(-3.0, 3.0), rng.uniform(-3.0, 3.0))
        gap_dx = rng.uniform(-1.5, 1.5)
        gap_dy = rng.uniform(-0.5, 0.5)
        half_w = rng.uniform(0.08, 0.15)
        if abs(gap_dx) <= half_w and abs(gap_dy) <= 0.10:
            continue
        a, b, c = _ring_slope(rng, accepted)
        if a != 0.0 or b != 0.0:
            sloped += 1
        rotation = rng.uniform(0.0, 360.0)
        ground = _square_ring_tin(insert, gap_dx, gap_dy, half_w, 0.10, a, b, c)
        seated, _kept, deleted, _exposed = seat_maf(verts, faces, insert, rotation, ground)
        assert _no_visible_hole(seated, deleted, ground), accepted
        assert _pivot_holds(verts, seated, insert, rotation, ground), accepted
        poly = [(seated[i][0], seated[i][1]) for i in bottom]
        if _rect_fully_outside(poly, insert[0] + gap_dx, insert[1] + gap_dy, half_w, 0.10) and bottom in deleted:
            outside_deleted += 1
        accepted += 1
    assert outside_deleted > 0
    assert sloped > 0


def _prism_side_normals(n: int):
    radius, z0, z1 = 1.0, 0.0, 1.0
    ring = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        ring.append((radius * math.cos(angle), radius * math.sin(angle)))
    verts = [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
    # Caps close the prism; the angle is measured on the side faces only.
    faces = []
    normals = []
    for i in range(n):
        j = (i + 1) % n
        face = (i, j, n + j, n + i)
        faces.append(face)
        normals.append(_unit_normal(verts, face))
    faces.append(tuple(range(n)))
    faces.append(tuple(range(2 * n - 1, n - 1, -1)))
    assert len(faces) == n + 2
    return normals


def _angle_deg(a, b) -> float:
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.degrees(math.acos(dot))


def test_smoothing_angle_matches_360_over_n():
    strict_misses = []
    for n in range(3, 65):
        normals = _prism_side_normals(n)
        angles = [_angle_deg(normals[i], normals[(i + 1) % n]) for i in range(n)]
        expect = 360.0 / n
        assert all(abs(angle - expect) < 1e-4 for angle in angles), n
        # The skill's band is strict: 360/N below 45 degrees iff N >= 9, below 30 degrees iff N >= 13.
        assert (expect < 45.0) == (n >= 9), n
        assert (expect < 30.0) == (n >= 13), n
        # Negative control: a non-strict threshold smooths N = 8 at 45 degrees and N = 12 at 30.
        if (expect <= 45.0) != (n >= 9) or (expect <= 30.0) != (n >= 13):
            strict_misses.append(n)
    assert 8 in strict_misses and 12 in strict_misses


def _load_atlas():
    path = ROOT / "tools" / "materials" / "atlas_maf.py"
    spec = importlib.util.spec_from_file_location("atlas_maf_skill_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _slots_overlap(slots) -> bool:
    boxes = [(slot.x, slot.y, slot.size, slot.size) for slot in slots]
    for i, (ax, ay, aw, ah) in enumerate(boxes):
        for bx, by, bw, bh in boxes[i + 1:]:
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                return True
    return False


def _solid_size_problems(slots, expected: dict[str, int]) -> list[str]:
    by_name = {slot.name: slot.size for slot in slots}
    return [name for name, size in expected.items() if by_name.get(name) != size]


def test_urn_atlas_route():
    from PIL import Image

    atlas = _load_atlas()
    with tempfile.TemporaryDirectory(prefix="maf-atlas-") as folder:
        tmp_path = Path(folder)
        Image.new("RGB", (128, 128), (150, 96, 48)).save(tmp_path / "wood_slat.png")
        payload = {
            "materials": [
                {"name": "wood_slat", "kind": "patterned", "texture": "wood_slat.png", "size": 128},
                {"name": "metal", "kind": "solid", "color": "RAL 9005", "size": 64},
                {"name": "body", "kind": "solid", "color": "#5A5A5A", "size": 128},
            ]
        }
        list_path = tmp_path / "urn.json"
        list_path.write_text(json.dumps(payload), encoding="utf-8")
        materials, atlas_size, padding = atlas.load_material_list(list_path)
        assert atlas_size == 512 and padding == 8
        slots = atlas.plan_atlas(materials, atlas_size, padding)
        image = atlas.render_atlas(slots, materials, atlas_size, padding)
        assert image.size == (512, 512) and image.mode == "RGB"
        by_name = {slot.name: slot for slot in slots}
        assert by_name["metal"].size == 64 and by_name["metal"].kind == "solid"
        assert by_name["body"].size == 128 and by_name["body"].kind == "solid"
        assert by_name["wood_slat"].kind == "patterned" and by_name["wood_slat"].size >= 128
        assert not _slots_overlap(slots)
        assert _solid_size_problems(slots, {"metal": 64, "body": 128}) == []
        # Negative controls: grown solids and a pair of overlapping squares are caught.
        assert _solid_size_problems(slots, {"metal": 128}) == ["metal"]
        overlap = [atlas.Slot("a", "solid", 0, 0, 128), atlas.Slot("b", "solid", 64, 0, 128)]
        assert _slots_overlap(overlap)
        assert not _slots_overlap([atlas.Slot("a", "solid", 0, 0, 64), atlas.Slot("b", "solid", 64, 0, 64)])
