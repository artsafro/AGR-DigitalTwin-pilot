# Skolkovo L4 — v013: where the mast defects are, and variants (FBX only)

**`passed=false`. No new geometry, export or PR. Needs a user decision.**

## Context

Artem 2026-10-21 21:4x: "нет Revit для мачт, только FBX". The Revit audit is cancelled
(nothing was called against `П_АР_Ф.rvt` in this run). The delivered FBX is the only
geometry authority for masts and KNS. Already approved and NOT asked again: Gate 1 v010
(PartsList SHA `fca5b23b…`), two-sided source profile <=0.002 m for the five masts,
108 KNS to 10,000 triangles.

The approved plan was executed in v011 (initial route + 3 different repairs, `REPORT-v011.md`).
It still fails: BODY-J 1222-1234 per mast (limit 100), isolated kernel rollback on row 3628,
KNS best measured 65,524 triangles vs 10,000. Per the user's instruction, this run brings
measurements and variants instead of a fourth blind repair.

## Measurements (new in v013, read-only, unchanged source buffers)

Tool: `twinqa.geometry.topology.count_defects`, tol 0.002 m. Scripts/logs: Drive `353-skolkovo-l4/evidence-v013/` + `SHA256SUMS.txt`. Data and buffer SHA256:
`evidence-v013/hub-localization-v013.json`.

Each mast is 3 connected components: tip rod, middle rod, base (8 inclined legs + vertical
tube + hub cap).

| Mast (row) | Whole mesh defects | Tip rod (tris / defects) | Middle rod | Base (tris / defects) |
|---|---:|---:|---:|---:|
| 3628 | 1302 | 448 / 4 | 1850 / 0 | 8800 / 1288 |
| 3651 | 1307 | 594 / 6 | 2242 / 0 | 9104 / 1288 |
| 3674 | 1307 | 594 / 6 | 2242 / 0 | 9104 / 1288 |
| 3697 | 1296 | 448 / 4 | 1850 / 0 | 7816 / 1282 |
| 3719 | 1292 | 472 / 0 | 1850 / 0 | 7816 / 1282 |

Base of 3628: duplicates 32 vertices + 48 edges + 64 polygons, 1144 self-intersections,
88 non-manifold edges. Split at non-manifold edges into 134 sub-bodies, **every sub-body
has 0 defects** (sum 0). All defects are between members: every pair of the 8 legs
(32-62 each) and every leg vs the hub cap (198 small triangles at the hub plane, 64 each).
No pair outside the hub. So the defects sit in one small node per mast: where the
8 legs (ø~50 mm, ~1.44 m long) converge under the hub cap, row 3628 at about
`(-7.47, 64.42, 13.19..13.24)` m (consistent with the v007 witness at z=13.190).
Tips: 4-6 duplicate vertices, no intersections.

Two-sided deviation of the approved v011 profile (unchanged, from `REPORT-v011.md`):
upper bound 1.986-1.997 mm, p95 0.505-0.509 mm, all five, Z extrema exact.
The profile meets the tolerance; it does not touch the hub, so BODY-J stays.

KNS (108 components, source 90,168 tris): 43 extension arms 29,928; 40 concrete bases
17,520; 5 mast bases 26,530; 10 ESE rods 10,490; 5+5 connectors 5,700.
Best measured v011 shortlist 65,524 (62/108 eligible) vs allocation 10,000.

## Variants for the five masts

1. **Hub-node rebuild (recommended).** Rebuild only the hub node (radius ~0.15 m around
   the leg convergence, ~2-3 % of each mast surface) as one closed welded node: leg ends
   trimmed at their mutual intersection curves, duplicate hub-cap faces removed, stitched.
   Everything outside the node stays byte-identical to FBX; deviation <=0.002 m on the
   visible exterior. Needs a decision: faces that lie **inside another leg** (hidden
   interior) may be deleted — v011 conservatively treated every source face as exterior,
   which is why union routes failed the certificate/budget. Expected BODY-J: <=10 per mast
   (tips 0-6). Cost: +1-3k tris over 5 masts, from the 3,000 reserve (147,000 -> <=150,000).
2. **Members as separate meshes.** Keep FBX geometry exactly; export each mast as
   separate objects (8 legs, vertical tube, hub cap, 2 rods): measured 0 defects per
   member. Needs a new PartsList/Gate 1 (+~10 objects per mast). Risk: the crossings are
   moved between objects, not removed (v007 already warned); SINTEZ may still flag
   overlaps, open leg ends stay inside the hub.
3. **Keep masts as FBX, record the deviation.** Masts byte-identical to FBX, BODY-J
   1292-1307 per mast recorded as a known source defect in the report (V004 fail on these
   5 meshes only); continue the other 44 parts, joints, export, comparison and timings
   to finish the L4 run. Delivery stays `passed=false` until the masts are fixed.

## KNS (10,000 not reached)

- K1: per-type proxies built from the source contours (silhouette <=0.02 m, already
  approved) without the quad/texel gates for parts under 0.2 m (connectors, clamps);
  estimate 6-9k.
- K2: keep the measured shortlist (65,524) and raise the KNS allocation — does not fit
  150k without cutting other parts; needs a new Gate 1.

## Question

Which mast variant (1 / 2 / 3)? For 1: may faces hidden inside another leg be deleted?
KNS: K1 or K2?
