# Ground v015 — 90,000-quad checkpoint, not a delivery

Issue #371; branch `improve/issue-371-ground-v015-vatutino-quad-dominant-one-m`.
Previous checkpoint: `8612bcc`; previous coarsening report: `5a181f4`.
This run checked origin/main `8d5c898`: no v015 implementation/delivery exists there.

## Authorized scope

[D170] records the card's latest instruction: Vatutino v015 alone may have up to
90,000 **surface quads**, a narrow exception to D097. The rejected coarse variants
are not reused. Relief tolerance remains 10 mm; other budgets and gates are not
waived. D150 must be re-measured against new world-coordinate junction identities.
D170 was free in origin/main, all open PR bodies/comments, and open-card comments;
D153/D154/D155 remain reserved by #373/#252/#377. Only one registry row and one
area-sheet practice bullet were added. Recheck reservations before eventual review.

## Actual measurement

Read-only input: `C:/x/ev_t_eb1c51ca/v014_rebuild/ground_master_vpm.json`.
SHA-256: `82cb1e6876ba98b92966aa7fc4242a2e9f354ee5ecdd42ed12806b57db666ae5`.
The exact reproduction script, complete counters, selected vertex/face identities
and first geometric witnesses are in `ground-v015-90000-evidence.json` next to this
report. Extract `reproduction_script` to the same worktree's ignored
`tmp/steiner-90000-diagnostic.py`, then run:

```text
uv sync
uv run python tmp/steiner-90000-diagnostic.py
```

The real command exited **0** after **353.8626 seconds**. This is successful
measurement, **not** successful model acceptance. It confirmed input bytes were
unchanged. No DCC process, source DWG, existing export, or user scene was changed.
The selected conforming mesher was not replaced by a third mesher experiment.

| Check | Measured | Verdict |
|---|---:|---|
| Surface polygons | 87,917 quads / 90,000 allowed | pass |
| All render polygons, including skirt and details | 121,233 quads | measured |
| Quad dominance, separate material slots | 12/12 pass; 0 triangles | pass |
| Render triangle-equivalent count | 242,466 | **fails NPM 180,000**, even before MAF/Flora |
| Normal corner samples below 5 mm | 0 | pass on tessellation |
| Normal triangle-centre samples below 5 mm | 0 | pass on tessellation |
| Minimum normal corner / triangle-centre gap | 5.048687 / 5.048734 mm | measured |
| Above-20-mm corner / triangle-centre sample records | 107 / 36 | new exception acceptance outstanding |
| Maximum normal corner / triangle-centre gap | 36.931266 / 33.497410 mm | measured, not accepted |
| Same-level XY overlap | 0 m² | pass |
| Ours xView vertex pairs / selected vertices | 2,789 / 4,360 | **fail** at 0.002 m |
| Ours xView polygon pairs / selected polygons | 438 / 307 | **fail** at 0.005 m |
| Ours xView contact-selected polygons | 300 | diagnostic, **not native Max evidence** |

Gap probes use the final fan tessellation of the quads, matching the documented
polygon-checker fan. They are not a separate measurement at every original quad's
centroid. Normal-band counts use the existing helper's 0.01 mm numerical margin.
The diagnostic's triangle UV placeholder is unused by the gap checker; it is not a
profile UV/readback receipt. Whole-face relief deviation, quad-centroid gaps,
material IDs, UCX and DCC acceptance remain **not measured** in this run.

### v014 seed versus selected conforming remesh

These are geometry-construction counts, not exported-file material-ID receipts.
All v015 candidate faces are quads; no triangle reasons apply to this candidate.

| Texture slot | v014 seed triangles | Candidate quads |
|---|---:|---:|
| TileLight | 21,603 | 58,511 |
| LawnRolled | 2,088 | 5,194 |
| TileRed | 3,004 | 7,492 |
| Mulch | 3,263 | 8,989 |
| TileDark | 509 | 1,237 |
| LawnReinforced | 1,311 | 3,651 |
| FlowerBed | 134 | 344 |
| Gravel | 618 | 1,678 |
| Pebbles | 291 | 821 |
| Skirt | 3,578 | 3,484 |
| Stairs | 100 | 300 |
| CurbGarden | 9,844 | 29,532 |
| Total | 46,343 | 121,233 |

### xView provenance

v014 construction offenders are retained in the card's first measurement comment:
`add_skirt` versus stairs/itself, `build_details` curb/stair intersections and
raised-covering contacts, plus `build_flat`/`clean_topology` bow-ties split by Max.
The selected quad remesh does not repair those construction steps. Its 438
polygon pairs classify as follows (slot pairs aggregated across contact/area):

| Slot pair | Candidate polygon pairs |
|---|---:|
| Mulch / CurbGarden | 14 |
| LawnReinforced / CurbGarden | 16 |
| Skirt / Skirt | 10 |
| Skirt / Stairs | 276 |
| Stairs / Stairs | 26 |
| Stairs / CurbGarden | 96 |

Steiner subdivision also creates new close vertices along existing short edges.
One actual witness: vertex 62 at `[-7493.976, -15336.36, 147.518213]` and new vertex
27448 at `[-7493.977, -15336.36, 147.51775333333333]` are **1.100588 mm** apart.
Simply converting this mesh to Editable Poly cannot make xView clean.

## Remaining budget decision

The new cap fixes the old **surface polygon** rejection only. The selected
87,917 surface quads already represent **175,834 triangles**, leaving **4,166**
triangles for skirt, stairs, curbs **and** MAF/Flora inside the unchanged NPM
180,000 whole-Ground limit. The current skirt/details add 66,632, hence the render
mesh alone exceeds the ceiling by **62,466**. The earlier checkpoint's separate
150,000 OKS/master comparison is not substituted for the Ground-specific NPM
180,000 ceiling here.

This is not a proof that every possible optimized model is infeasible. However,
it is evidence that the specifically selected checkpoint is not an acceptable
NPM model with just a 90,000-quad surface exception. A new NPM surface/detail
reduction route would go beyond the selected checkpoint and the previous
explicit stop on further mesher attempts. Ask whether to authorize that bounded
route or park the delivery; do not silently waive the 180,000 limit, delete
mandatory curb/stair geometry, or publish VPM-only as both profiles.

## Verification and continuation

- Tests-first commit `12ec137`: new decision-scope regression **1 failed** before
  D170 was recorded (missing canonical decision row), exit 1.
- After adding D170 and its area-sheet anchor:

  ```text
  env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q tests/test_ground_v015_budget_decision.py tests/test_decisions.py tests/test_ground_quads.py tests/test_ground_surface_requirement_sheet.py -p no:cacheprovider --basetemp=C:/x/t_eb1c51ca/pytest-d156-green
  ```

  **65 passed**, exit 0. This includes existing mesher tests and the global
  decision-format/anchor controls, not delivery acceptance.
- No production mesher, builder or gate was changed. General surface and NPM
  triangle budgets are preserved. No PR exists and no review is requested.
- Full suite is deferred to the eventual first-review head, not spent on an
  already rejected candidate. Native Max/Blender exports, real xView, per-face
  material-ID readbacks, whole-face relief/silhouette, UCX, placement compatibility
  and review-scene publication remain open. No final delivery receipt is claimed.
- #348 card `t_5bc043c7` is done/reviewed at `9b39e1c`, but PR #373 remains open;
  its publication code was not borrowed or merged. Before using it, link the named
  dependency and follow the authorized parent-branch integration policy, or wait
  for it on main. No #348 user visual approval is inferred from technical review.
- All started diagnostic processes exited; scratch inputs were not deleted.
