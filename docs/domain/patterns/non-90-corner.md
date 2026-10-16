# Corner that is not 90° (`non-90-corner`)

Status: draft. Source: `docs/HARNESS_PLAN.md` §3–§4, §7; extractor `src/dt_ai/spec/mesh.py`
(kinks, arcs); `docs/domain/geometry.md` (contour orthogonalization, corner windows). Benchmark: B02.

## Signs in the spec

- Consecutive contour edges turning other than 90°; kinks over 5° kept, 5° or less dropped on purpose.
- Rounded corner: `[x, y, {"r": r}]`. An arc is read only when its points and both walls fit one
  circle within 5 mm + 0.5 % of r.

## How to build

- Both walls end on the shared contour vertex: one vertical corner edge, shared and welded, no gap
  and no overlap.
- The corner edge carries the facade's shared Z cuts, so both walls split at the same heights.
- Engine: horizontal faces cut into trapezoids by vertical strips; side cuts carried across by share
  and kept in step with walls along y — quads, no T-junctions; a piece whose one side is a point is a
  triangle fan. Rounded corner (an arc tangent to both
  walls, chords as wall strips): not built yet.
- The shell offset (and reveals near the corner) follows the true angle, not 90°.

## Profiles

- `npm_min`: planar walls meeting at the vertex; arcs with the fewest chords that stay inside the
  silhouette threshold.
- `mid`: same corner; more chords on arcs only when the silhouette check asks for it.

## Check

- `floor_areas`, `silhouettes` (top view shows the angle), `mesh` (no non-manifold edge or overlap).

## Traps

- Never square a corner silently. Orthogonalization may move a vertex by at most 0.25 mm; a wall
  that needs more is reported, not flattened.
- An opening never runs across the corner vertex: it belongs to one wall. A corner window is two
  openings with two planes (`opening-plane`).
- Elements on a dropped small kink are still measured on the real facet.
- If the inward shell offset self-intersects at a corner, stop and ask (user decision 2026-10-09 [D033]).
- Pointed corner (an x-extreme corner between non-vertical walls, a pointed tip): a triangle fan from
  the point to the other side's cuts, no T-junction (PR #100, user 2026-10-13 [D112]).
- Strip lines closer in x than the building weld `weld_m` (3 mm, [D068]) are one line.
- Still a BuildError: a face piece with no side on a strip line or that is no trapezoid/triangle;
  cuts on the fan's side closer than `weld_m`; a face collapsing under the weld.
