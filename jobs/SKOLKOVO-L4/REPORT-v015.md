# Skolkovo L4 — v015: mast fold repair 3 (5/5 masts pass the kernel), KNS K1 loft started

**`passed=false`. Masts: 5/5 pass the kernel. KNS K1: 92/108 measured, 14 accepted; concrete bases,
ESE rods and mast bases have no accepted proxy yet. No export, no PR.** Revit not used (decision 21:4x).

## Masts 3697 / 3719 — repair 3 (`tmp/skolkovo-l4-v014/repair3.py`, Drive `evidence-v015/scripts/`)

- Locator `locate_fold.py`: the kernel's own `near_parallel_overlaps` (same direction, 5 mm) on the faces
  within 0.5 m of the hub. Before: 2 pairs on each (3697: 6812/9749, 8233/9749; 3719: 9687/9834,
  9687/9945); control 3628: 0 pairs — matches the v014 kernel rollback `no_close_overlap 2`.
- Cause: a flipped sliver (3697: vertices 3690-4574-4569; vertex 4569 lies 0.07 mm on the wrong side of the
  edge) on the tube facet next to the node — left by the repair-2 weld.
- Repair: grow the edge-connected in-plane patch (vertex distance to the facet plane < 0.1 mm; 17 / 15
  triangles, 1 flipped each), take its single boundary loop (7 vertices), re-triangulate by constrained
  Delaunay (5 triangles). No vertex moved or added; 6 / 5 interior patch-only vertices dropped.
  Zero deviation is proven by area: 2D union of the old patch = loop polygon = new triangles,
  238.708 / 238.704 mm², symmetric difference 0.0 mm². Fail-closed (exit 2): pinched or multi-loop
  boundary, non-simple loop, area mismatch, triangulation adding a vertex, output == input.
  First run failed closed on "boundary vertex used twice" (the flipped sliver was outside the patch);
  fixed by in-plane membership by vertex distance instead of normal direction.

| Mast | tris v014 → v015 | edge use | BODY-J (≤100) | kernel contour_rebuild |
|---|---|---|---:|---|
| 3697 | 10120 → 10108 | all 2 (closed) | 60 | **applied** (0/0/0/0, 219 s) |
| 3719 | 10068 → 10058 | all 2 (closed) | 53 | **applied** (0/0/0/0, 219 s) |

Masts total 55,230 (source) → 54,934. 3628/3651/3674 unchanged from v014 (applied). Deviation numbers of
v014 stand (the repaired region has zero deviation by the area proof). Hashes:
`evidence-v015/mast-repair3-kns-v015.json`.

## KNS K1 (decision 22:57) — loft proxy, partial (`tmp/skolkovo-l4-v015/kns_loft.py`)

Recipe: per connected component (whole object when its max extent < 0.2 m), a lofted K-gon (K 4-12) along
the principal axis or the thin axis, from exact plane sections of the source mesh; quads only; Douglas-Peucker
on the support values (8 mm); widths ≥ max/7 and sides ≥ 2.5 mm; stations ≥ 2.5 mm apart (mode `min`) or
moved to ≥ width/7 ≤ 15 mm (mode `shift`). Accepted when the 3-view silhouette certificate (0.0199 buffer
both ways, as the v011 audit), BODY-J ≤ 100 and no isolated/zero-length pass, plus quad_dominance(VPM) and
texel_ready(VPM-OKS) for objects ≥ 0.2 m. Not accepted → source kept and reported.

Run interrupted at object 93/108 (time box; the next object hung in the K/axis loop).

| Type | measured | accepted | source tris | after |
|---|---:|---:|---:|---:|
| connector wire (<0.2 m) | 5 | 5 | 4,180 | 140 |
| connector ESE (<0.2 m) | 5 | 5 | 1,520 | 60 |
| extension arm (0.72 m) | 35 | 4 | 24,360 | 21,784 |
| concrete base (Ø0.5 m) | 33 | 0 | 14,454 | 14,454 |
| ESE rod (0.38 m) | 9 | 0 | 9,441 | 9,441 |
| mast base (1.3 m) | 5 | 0 | 26,530 | 26,530 |

Why the rest fail (measured on samples, try logs in Drive `evidence-v015/kns`):
- concrete base (round, Ø0.5 then frustum): K ≤ 8 loft misses the top view (0.021-0.106 m Hausdorff);
  K = 12 passes the silhouette but BODY-J 170-685 (thin-axis loft rings too close). Next: a revolved
  proxy around the vertical axis (Ø0.5 → frustum, 12-16 sides, 2 bands, fan caps = pole_fan), ~50-70 tris.
- extension arm: the upright K = 4 box fails the side views by 0.03-0.05 m on most arms (end drop + arrow
  tip); a two-piece proxy (bar + drop) per arm is the next try.
- ESE rod: the 1.9 mm spike forces texel aspect > 8 or the BODY-J 2 mm weld; the step moves of `shift`
  push the disc silhouette over 0.02 m. Next: revolve with a capped minimum radius.
- mast base: convex sections fill between the legs (top view 0.44-0.46 m). Next: split the main component
  into legs by section connectivity before lofting.

## L5 timing (2026-10-22, wall clock)

Context 10 min; fold locate + repair 3 25 min; kernel 2 × 219 s parallel; KNS K1 recipe and tries 45 min;
full KNS run 7 min (interrupted); report/evidence 15 min. Total ≈ 1 h 50 min.

## Next steps

1. KNS: revolve proxy (concrete, ESE), two-piece arms, leg split for mast bases; then whole-KNS sum
   vs 10,000 and kernel per object.
2. Then: 49 parts / joints on the kernel, versioned export + FBX readback, comparison with the delivered
   final and the album, review tool, SINTEZ, suite via suite_slot.py, PR, dt-reviewer.
