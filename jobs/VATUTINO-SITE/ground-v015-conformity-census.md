# Ground v015 strict-remesh: conformity census (NOT_DELIVERY)

Session: Claude lane, 2026-10-21/22, after Codex pause. Base `59799c6` (pushed) + positive-template
fallback in `src/dt_ai/geometry/ground_strips.py`. Input: CPU v009 masters
(`master-npm.json` sha256 `c26b7feb…26ca1a`, `master-vpm.json` `59310ac9…452eb4`), unchanged.
Gates unchanged (strict `texel_ready`, 50k surface / 180k NPM, xView 0.002/0.005, 2.2 mm, 10 mm).
Scripts: `tmp/claude-census-v001.py`, `tmp/claude-conforming-estimate-v001.py` (gitignored, copied
with outputs to `C:/x/ev_t_eb1c51ca/census-v001/`); numbers in `ground-v015-conformity-census.json`.

## 1. Local strips are not conforming (new, measured)

`local_strips` decides cuts per source face; a shared edge is only shared when both neighbours pick
the same `Fraction`. Boundary edges (used by one face) of the output:

| profile | source boundary edges / m | strips boundary edges / m | OV pairs | OV owner faces | owners < 2.05 mm thick |
|---|---|---|---|---|---|
| NPM | 8,447 / 9,776.6 | 90,332 / 47,325.0 | 179 | 282 | 94 |
| VPM | 8,447 / 9,776.6 | 88,314 / 51,031.7 | 245 | 412 | 111 |

So ~37-41 km of edges are T-junction cracks. The texel-clean strips output (Codex v007) is therefore
not a candidate even before OV; the template fallback only lowers NPM OV from 232 to 179.

## 2. Structured conforming propagation diverges (proof by fixed point)

Union-find over opposite quad edges (chords), one split count per chord, each quad requiring cell
edges <= max edge and cell pair-aspect in [1/8, 8]. The fixed point does not exist: after 200 sweeps
NPM counts have 253 digits, VPM 159. 5,536 NPM / 5,915 VPM chords diverge, driven by 1,308 / 1,331
source quads with pair-aspect > 8 (e.g. face 372 ratio 97.7, face 357 ratio 0.004) inside chord
cycles. Hence no uniform-grid conforming remesh of v009 satisfies strict texel; any conforming route
needs transition elements (count-changing quad templates, e.g. 1->3 / 2->4) that terminate chords,
which neither the strips stage nor the rejected Steiner route had.

## 3. Tongue tips are not proven infeasible

A v009 tip triangle (face 972: edges 3.0 / 13.4 / 16.2 mm, 1.12 mm thick, apex 4.8 deg) cannot be held
by a triangle at its apex (any triangle with angle a has aspect >= 1/sin a = 12 > 8), nor by rail-only
templates (Codex families and 256 positive random templates fail). A convex interior apex quad exists,
e.g. apex, rail-1 node at 3 mm, interior node at 11 mm, rail-0 node at 8 mm (all spacings >= 2.05 mm,
pair-aspect 2.7); the remainder partition is still open. This is the pinned
`test_centimetre_triangle_needs_distributed_not_clustered_staggered_rails` (now `xfail(strict=True)`).

## What remains (no gate relaxed, nothing published)

1. Conforming mesher with transition templates and interior apex quads; prove 0 open T-edges
   (boundary edges equal to source), then OV/OF, texel, budgets, relief, D150, contours.
2. Then everything in `ground-v015-strict-remesh-plan.md` step 4 (UV/IDs/export/Max xView/UCX/
   placement/review/PR). No earlier CPU, Max or texture receipt transfers.
