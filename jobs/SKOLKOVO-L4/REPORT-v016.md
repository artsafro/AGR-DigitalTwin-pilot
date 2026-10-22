# Skolkovo L4 — v016: KNS K1 done — 108/108 proxies pass the gates and the kernel, 8,696 / 10,000 tris

**`passed=false`** for the building (no assembly or export yet). The K1 step itself is complete: every one of
the 108 KNS objects is replaced by an accepted proxy; no object kept as source. Masts unchanged from v015
(5/5 pass the kernel). Revit not used (decision 21:4x); the FBX stays the only geometry source.

## Recipes (`tmp/skolkovo-l4-v016/`, scripts + logs + proxies on Drive `evidence-v016/`)

All proxies are closed, consistently wound quad meshes built from the source FBX geometry only.

| Kind (count) | Recipe | How the shape is taken from the source |
|---|---|---|
| concrete base (40) | `kns_rev.revolve` K=12 | r(z) = max radial distance of exact plane sections; Douglas-Peucker 8 mm; knots lifted so the profile covers every section |
| ESE rod (10) | `kns_rev.revolve` K=6 | same, DP 8 mm; stations ≥ max(2.5 mm, side/7) so texel aspect ≤ 8 |
| extension arm (43) | `kns_arm.arm_loft` | loft of rectangles along the arm: z-range from the side silhouette, width from the top silhouette; steps become two rings; conservative strip sections at both tips |
| mast base (5) | `kns_mastbase.mastbase` | hub octagon (edge = foot width) + 8 feet with top height h(s) = highest foot silhouette (gussets folded in) + octagonal tube |
| connectors (10) | `kns_terrace.terrace` | stack of z-tiers, each the xy-bbox of the source surface inside the tier |

Acceptance per object (`kns_v016.accept` + `kns_run.with_kernel`), all must hold:
3-view silhouette certificate ≤ 0.0199 m both ways and the silhouette module's region deviation
(grid 2.5 mm) ≤ 0.0199 + 0.0025 m; BODY-J (`count_defects`, tol 2 mm) ≤ 100 and no isolated/zero-length;
quad_dominance(VPM) + texel_ready(VPM-OKS) for objects ≥ 0.2 m (K1: not for details < 0.2 m);
every edge used twice, no same-direction pair; kernel `run_operation(contour_rebuild)` isolated
(PartsList v010 operation of `rods_additional_kns_components_rod_ladder_contour_rebuild`) applied.
The kernel's `no_see_through_hole` (26 directions, 0 lost pixels) needs the proxy to cover the source in
diagonal views as well: the first outward vertex-normal offset of (0, 1, 2, 4, 7 mm) that passes all gates
is kept; silhouettes and BODY-J are re-measured at that offset.

## Results (`evidence-v016/kns-k1-v016.json`, run `kns-run-05`, 543 s)

| Kind | objects | accepted | source tris | after |
|---|---:|---:|---:|---:|
| concrete base | 40 | 40 | 17,520 | 2,720 |
| mast base | 5 | 5 | 26,530 | 1,580 |
| extension arm | 43 | 43 | 29,928 | 2,540 |
| ESE rod | 10 | 10 | 10,490 | 1,640 |
| connector wire | 5 | 5 | 4,180 | 140 |
| connector ESE | 5 | 5 | 1,520 | 76 |
| **total** | **108** | **108** | **90,168** | **8,696 / 10,000** |

- Max silhouette deviation over all objects and views 0.016 m; BODY-J 0 on all 108; winding defects 0.
- Kernel: 108/108 applied in the run; independent fresh-process recheck from the stored proxies
  (sha256 checked before use) `kernel-recheck-05.json`: 108/108 applied, 0 rolled back, 0 kept source (233 s kernel time).
- Outward offset used: 0 mm on 62 objects, 1 mm on 18, 2 mm on 8, 4 mm on 20.
- quad/texel gated objects (≥ 0.2 m): 98/98 pass; 10 connectors < 0.2 m exempt (K1).

Fail-closed probes `probe_v016.py`: 15/15 — NaN and inf input to each of the 4 builders → error;
non-round input to revolve → error; mast base without feet → error; NaN proxy → error; a flipped quad is
detected; a source scaled past the 2 cm tolerance fails the certificate while the identity passes;
the runner exits non-zero on an existing output dir and writes nothing.

Drive `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v016/`: scripts, logs, `runs/kns-run-05` (108 proxies
+ manifest), `runs/kns-run-01`; 242 files, `SHA256SUMS.txt` sha256
`279628eb659a19f4740fa235cf8656814b35b57ef9ab4d7d50c09b6a7f496b18`, `sha256sum -c` 0 mismatches.

## Repairs inside the K1 step (rule 56)

1. Revolve profile below the source → kernel `no_see_through_hole` (2 px): knots lifted to cover every section.
2. Arm loft: line sections at the tips under-covered the arrow tip (2 px): conservative strip sections at both
   ends (`strip='ends'`); one arm (3632) lost its 16 mm drop step to breakpoint clustering → keep the last
   breakpoint of a close group (`last=True`).
3. Connectors: the v015 loft proxy failed the kernel at every offset (42 px) → terrace proxy (28 tris).
4. Mast base: the vertex-max height profile missed long faces (side deviation 0.043 m) → height from the
   per-foot side silhouettes; the end knot keeps its station and the larger height.
Rejected runs kept as evidence: `kns-run-01` (no kernel gate), `aborted-kns-run-03/04` (stopped for the
repairs above).

## L5 timing (2026-10-22, wall clock)

Context 10 min; revolve + arm + mast-base recipes 35 min; kernel gate discovery + repairs 1-4 40 min;
final run 9 min + recheck 5 min; probes/report/evidence 15 min. Total ≈ 1 h 55 min.

## Next steps

1. Assemble the 49 parts on the kernel: masts (v015) + KNS proxies (this run) + the rest of the PartsList
   v010 plan; joints (291 conditional) per Gate 1.
2. Versioned export + FBX readback (`validate-delivery`), comparison with the delivered final
   (`03_LP`/`04_HP`) and the album, review tool, SINTEZ, suite via suite_slot.py, PR, dt-reviewer.
