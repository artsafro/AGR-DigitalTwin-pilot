# Ground v015 approved-notch checkpoint — #371

**Not delivered; no PR, review queue entry or acceptance receipt.** The exact
notch decision is resolved. A VPM policy choice is now required before profile
integration; known technical export failures are retained below, not waived.

Start `f336062`; merged `origin/main@766d3f6` via `77df6d2`. The only conflict
was independent D153/D154 versus D156/D157 rows; both were retained. D164–D168
remain reserved by #489 / PR #492; this branch records only its own D169.

## Approved contour deviation — separate acceptance row [D169]

Artem, card #371 comment 2026-10-21 16:58: **«принимаю»**; the orchestrator explicitly
permits closing footprint hole 0 by XY A=`(-7691.007,-15248.688)`,
B=`(-7691.2305,-15248.001)`, C=`(-7691.016,-15248.688)`.
Area **0.0030915000000045403 m²**; sampled closing-edge distance from the
original outline **4.317305 mm**. This is an approved local contour correction,
**not** an increase of the 2.2 mm outline, 10 mm relief or 0.002/0.005 m xView
thresholds. Source adapter and v014 source mesh bytes remain unchanged.
`ground-notch-approval-v015.json` pins their separate SHA-256 values.

`ground_cake.close_base_notch` adds precisely one TileLight base triangle using
three exact existing vertices and two oppositely oriented open boundary edges.
No vertex is moved, no disconnected fan is split/displaced, no material winner is
chosen. It refuses missing/ambiguous coordinates, missing approval text, occupied
base area, mixed slot ownership and unsupported/partial/nonfinite inputs. The
construction primitive does not authenticate approvals; the job must supply the
source-bound approved coordinates. Production `build_ground.py` is not integrated.

## Measured geometry, before profile/export integration

| Check | Result |
|---|---:|
| Ours indexed polygon xView, 2/5 mm | **0 OV / 0 OF**, predecessor 0 / 1 |
| Base outline open-edge failures / nonmanifold edges | **0 / 0**, predecessor 1 / 0 |
| Surface polygons | 20,150 / 50,000 |
| Quads / triangles | 19,223 / 8,006; **29.402475%** triangles |
| Whole geometry triangle-equivalent, excluding placed MAF/Flora | 46,452 / 180,000 |
| Original triangle-seed relief | max **9.963067 mm**, 0 faces >10 mm |
| Projection misses / faces outside material tolerance | 0 / 0 |
| Normal gaps <5 mm, vertices / centres | 0 / 0 |
| Raw normal gaps >20 mm, vertices / centres | 18 / 6; D150 re-pin **not certified** |
| Same-level overlap | 0 m² |
| Uncovered beyond 2.2 mm | 0 m² |
| Raw outside-surface area beyond 2.2 mm | **0.0000014891367327287466 m²**, not zero/not signed off |
| Disconnected-fan risks | 59 indexed risks; no fan displacement |

The source/approved-outline comparison keeps the small raw outside-area residual
visible near B. A high-resolution buffer replay retains it; it is not silently
rounded to zero or claimed as an additional approved deviation. Open-edge midpoint
counts are not a complete Hausdorff proof. Full v014-to-v015 silhouette/detail
certification remains open.

## Native and independent readback — diagnostic only

Live **3ds Max 2024.2.5**, metres, originally untitled/7 objects/saveRequired=false,
pinned PID 114060. No headless process was started alongside the user's open Max.
The diagnostic uses `holdMaxFile` / `fetchMaxFile quiet:true`; only new task-owned
paths receive `.max`, FBX and reports. Empty mesh → `convertToPoly`, then explicit
`polyop.createVert/createPolygon` avoids starting from an already triangulated
whole mesh. Shared-fan synthetic control: 5 vertices / 2 polygons / native OV 0.

| Readback | Vertices | Polygons | Native OV IDs | Native OF IDs |
|---|---:|---:|---:|---:|
| Constructed Editable Poly | 27,414 | 27,229 | **0** | **0** |
| Exported diagnostic FBX → fresh Max import → Editable Poly | 27,414 | 27,229 | **0** | **0** |

FBX exported with `Triangulate=false`. Blender **5.1.2** fresh-process readback:
19,223 quads / 8,006 triangles, same polygon memberships/winding up to cyclic
rotation. Every one of 27,229 material IDs matches its expected slot; all 12 slots
are used, no extra slot. Native-coordinate float32 error max **0.009034 mm**.

**Export is not clean under every required check:** Max/FBX rotates 6,474 quad
corner cycles and thus changes the fixed-fan diagonal. Running our area checker on
those actual reimported polygons gives **0 OV / 44 OF**, all area-only; native
contact selection remains 0/0. Blender's actual `loop_triangles` give **24 surface
triangles >10 mm relief**, maximum **12.193213 mm**. These are technical pairing/
tessellation failures to fix without changing the 10 mm or xView thresholds;
native zero alone is not acceptance. No new source-model decision is requested for
these repairs. Final UV/maps/profile export, UCX and placement are not measured.

| Slot | Max ID | Blender slot (0-based) | Diagnostic faces |
|---|---:|---:|---:|
| CurbGarden | 1 | 0 | 5,129 |
| FlowerBed | 2 | 1 | 85 |
| Gravel | 3 | 2 | 398 |
| LawnReinforced | 4 | 3 | 811 |
| LawnRolled | 5 | 4 | 1,411 |
| Mulch | 6 | 5 | 2,123 |
| Pebbles | 7 | 6 | 215 |
| Skirt | 8 | 7 | 1,878 |
| Stairs | 9 | 8 | 72 |
| TileDark | 10 | 9 | 289 |
| TileLight | 11 | 10 | 13,040 |
| TileRed | 12 | 11 | 1,778 |

### Failures/repairs retained, not interpreted from exit code alone

- `Editable_Poly()` is not creatable in Max 2024; empty mesh → convertToPoly works.
- Script v001 used reserved `of`; parser refused it before geometry construction.
- Script v002 attempted to define read-only `measure`; bridge transport returned
  success but result contained `__MCP_MS_ERR__`. No native receipt was accepted.
- Script v003 produced the direct receipt and diagnostic files; one stale call to
  built-in `measure` failed to produce an FBX receipt despite a DONE marker. A
  separate fresh import/readback program generated and verified the missing report.
- Immediate Drive ZIP readback gave transient `BadZipFile`. A subsequent read-only
  CRC check and every-member SHA-256 verification succeeded; archive not rewritten.
- At final read-only inspection the wrapper selected new PID 145840 with 40 objects;
  explicit old PID 114060 was unavailable. No write was sent to the new instance.
  Preserve the completed pinned-114060 receipts; re-identify app/document/units and
  pin explicitly on resume rather than assuming the previous target still exists.

## Required user choice: D157 scope versus strict VPM D129

D157 explicitly authorizes **Ground NPM** source-preserving pairing with up to
35% residual triangles over the whole Ground; pure quads remain a VPM goal.
It does **not** explicitly replace the VPM D129 policy (0 unneeded/mergeable
triangles and ≤5% needed per part). Do not silently extend the NPM exception to VPM,
turn a goal into a waiver, or change `inv_quads` thresholds/classification.

With correct surface profile UV and common metric detail UV for pairing:

| Profile | Quads | Triangles | Triangle share | Surface density px/m | VPM tile check |
|---|---:|---:|---:|---|---|
| NPM | 19,223 | 8,006 | 29.402475% | 11.553–30 | not applicable to NPM world-repeat UV |
| VPM | 18,524 | 9,404 | 33.672300% | 589.497–1441.221 | 1001; 0 straddling |

Raw VPM `quad_dominance` fails **12/12 slots**, 8,480 offender entries including
5 per-part share-cap entries. Raw NPM has 7,098 entries before applying its
explicit paired-Ground exception. The generic invariant is unchanged; neither
raw result is relabelled pass. UV seams can leave geometrically mergeable pairs;
per-slot reasons are recorded rather than claiming every residual is D129-needed.

| Slot | v014 triangles | VPM paired quads | VPM triangles | Needed odd / pole | Unneeded / mergeable |
|---|---:|---:|---:|---:|---:|
| CurbGarden | 9,844 | 4,703 | 426 | 122 / 0 | 304 / 0 |
| FlowerBed | 134 | 45 | 44 | 8 / 0 | 32 / 4 |
| Gravel | 618 | 204 | 210 | 16 / 0 | 180 / 14 |
| LawnReinforced | 1,311 | 459 | 393 | 33 / 0 | 328 / 32 |
| LawnRolled | 2,088 | 650 | 788 | 132 / 0 | 640 / 16 |
| Mulch | 3,263 | 1,083 | 1,097 | 84 / 17 | 942 / 54 |
| Pebbles | 291 | 71 | 149 | 11 / 0 | 132 / 6 |
| Skirt | 3,578 | 1,789 | 89 | 19 / 0 | 68 / 2 |
| Stairs | 100 | 64 | 8 | 4 / 0 | 4 / 0 |
| TileDark | 509 | 218 | 73 | 23 / 0 | 50 / 0 |
| TileLight | 21,603 | 8,045 | 5,509 | 313 / 15 | 4,885 / 296 |
| TileRed | 3,004 | 1,193 | 618 | 130 / 2 | 468 / 18 |

**Question:** for v015, does the same source-preserving paired-residual exception
apply to **VPM** too (≤35% over the whole Ground, with per-slot reason reporting,
not a claim all residuals are D129-needed), or must VPM keep the strict original
D129 and use a different conforming quad construction? No relief/budget/xView
relaxation or extra blind session is requested. Known export repairs remain
mandatory whichever policy is chosen.

## Verification and continuation

- Tests-first `897c0e3`: **10 failed → 10 passed** (closure).
- Policy regression in `b3e6a04`: **1 failed → pass** after D169/data added.
- Final focused suite: **254 passed / 0 failed, 9.65 s**, including all prior
  Ground regressions plus `tests/test_ground_notch_{closure,approval}.py` and
  `tests/test_decisions.py`; exact command/log in the archive.
- Full suite not run: no first review requested and profile acceptance is unresolved.
- No PR, headless-Max acceptance, final FBX/.max delivery or pending.json publication.

Evidence: `ground-v015-approved-notch-evidence.json`; binary archive and checksum:

`G:/Мой диск/AGR-evidence/371-ground-v015-approved-notch-20261021/checkpoint-evidence-v001.zip`

SHA-256 `212025ae8711a8a75e3c0a3faae32a544cbd5a52cb72d5c357de1f0ae1a5bd05`,
9,172,794 bytes; adjacent `SHA256SUMS.txt`; CRC and all 44 member hashes verified.
Restore only into fresh scratch paths. Reproduction includes the exact frozen
predecessor arrays, source copies, programs and native diagnostics; no Git LFS.
Native files have no final profile UV/maps and must never be published as delivery.

After the user's VPM disposition: repair export-diagonal/independent-area failures
with new regressions, settle the raw outline residual without a silent exception,
re-pin D150 by world coordinates, integrate the production builder and profile
UV/maps, rerun both native/independent exported-file checks, UCX/placement and
review publication, then one slot-wrapped full suite and review request.
