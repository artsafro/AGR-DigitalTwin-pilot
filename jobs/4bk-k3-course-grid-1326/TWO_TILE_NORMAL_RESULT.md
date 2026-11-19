# Actual two-tile source-relief candidate (#1326)

**Historical v071–100 snapshot.** Artem confirmed v096's Normal/joint/course visual direction on 2026-11-15 10:12 [D310]. Do not repeat that target question. Continue at [NUMERICAL_REPAIR_RESULT.md](NUMERICAL_REPAIR_RESULT.md) for the repaired geometry and NEW thin-colour-core images. Immutable v071–165 files retain earlier D302/D306 spellings; only current tracked citations were renumbered after #1419/#1418 collisions.

**NOT passed. Technical QA is RED. No replication, delivery acceptance, PR or code review.**

## Answered policies and scope

Artem's 2026-11-15 08:10 «да, принимаю» authorizes **two sequential UDIM tiles**
for this stylobate-brick pilot [D304]. It supersedes only the initial one-tile
budget [D309]. Original joint relief is required [D295]; minimal outer-bevel
support cuts on a new copy remain authorized [D303]. The four original stair
faces are only the specifically accepted source baseline [D296], not a waiver
of new contacts or other source pairs. Do not ask any of these questions again.

Canonical registry spellings are now D309/D303/D304. Immutable v071–100 evidence,
materials and filenames retain D293/D297/D301 where they used the earlier
spellings. The D301 reservation race was resolved from board timestamps:
#1315 08:19:14, this card 08:19:16; this card renumbered itself. Earlier D293/D297
collided with #1402/#1401. No decision content or frozen evidence was rewritten.

Scenario `oks-vpm`, level `full`. Blender **5.1.2 background** plus existing
course-grid/UV cores avoids touching daytime Max. Open only on «открой».
Protected ID7 and source files were not edited. No extra plain-brick grid cuts,
third tile, rotation/mirror packing, density fallback or source overwrite.

## Working artifacts — real, not a packing diagram

Root: `G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/`.

- Native picture candidate: `normal-v096/stylobate_two_tiles_textured_v096.blend`.
- Explicitly selected export copy: `normal-v097/stylobate_two_tiles_textured_v097.blend`.
- Read-back FBX: `normal-v097/stylobate_pilot_v097_QA_OPEN.fbx`.
- Six real **4096×4096** maps: `normal-v092/T_1326_Stylo_{Diffuse,ERM,Normal}.{1001,1002}.png`.
- Four **lit** source/candidate pairs (straight wall, corner, floor join, niche):
  `normal-v096/source-vs-two-UDIM-lit-QA-OPEN.png` (1600×2560).
- Same-camera actual grazing-light relief comparison:
  `normal-v096/original-vs-restored-relief-QA-OPEN.png`.
- Native/FBX association: `normal-v099/fbx-readback.json`.
- Fresh imported triangle and saved-UV metrics: `normal-v100/metrics.json`.
- Fresh independent frozen-colour PNG oracle:
  `normal-v094/independent-all-faces-png-check.json`.
- Hashes/complete continuation: `two-tile-checkpoint-v100.json` and versioned
  external `normal-v101/` seal; earlier failed versions remain separate.

These pictures were visually inspected. The joint relief is visible; the
candidate is no longer the earlier neutral-Normal band. The chart deliberately
changes brick phase versus the old delivery. This observation is not Artem's
visual verdict or a full Normal-frame/interval certificate.

## What the actual bake does

The Bricks1 input bitmaps remain byte-unchanged. Base colour/ERM/Normal are sampled
with the exact **48 × 3.15/38 m** appearance repeat and **512.1 px/m** frozen input.
Original signed relief is recovered from the frozen delivered Normal against its
explicit no-groove baseline, then transported between encoded source/target
R/G tangent axes and composed with the new unchanged Bricks1 base. The saved
Blender material performs the original DirectX-green display conversion and links
**TILED 1001/1002** images for all three roles, Non-Color for ERM/Normal.

Colour alpha is inferred from frozen delivered Diffuse against the separately
replayed base, with replay-supported/actual dark-pixel classification. It is NOT
an exact replay claim: reconstructed source Diffuse has **4,976 pixels above one
RGB error**, max **28 RGB**. Those residuals and the 75 independent PNG misses
remain repairs. The **158 one-byte Normal residual pixels** outside measured
bevel remain unclassified quantization, not extra cut authority.

The intended colour joint remains **10 mm owner-inside, centre 5 mm inward**.
The wider Normal-support zone is not a wider colour seam. Guarded geometry was
simplified before offset/tessellation and source corners anchored; all **771**
active pixel-cell/colour supports were checked. This subset does not prove full
bilinear halo coverage or native topology: those are separate open gates.

Source-relative protected texture paths were repaired **as links only** to their
existing named original files (with hashes) on the new copy, not painted grey or
replaced. v096 renders no longer contain the earlier missing-ID4 magenta artefact.

## Fresh measurements (research section 5)

| Metric | Fresh result and scope | Verdict |
|---|---|---|
| Source membership | 771/771 brick sources, 803/803 support members, 751/751 appearance groups; all 2,015 source identities in imported FBX; no source-identity drop | membership covered; not topology/surface pass |
| Export association | **4,299/4,299** native polygons matched in a clean FBX process, both meshes, exact UV delta 0; max XYZ **9.004957 µm**; material association matched; one UV channel per imported mesh | narrow export-association match only |
| Native topological UV components | source **500**, candidate **1,423**, shared vertex-edge UV endpoint tolerance 1e-7 | measured; not appearance-class count |
| 1001 unique sampled/padded union | **58.518760% / 86.250282%**, 236 classes including shared brick | measured on saved native UVs |
| 1002 unique sampled/padded union | **11.566041% / 49.145237%**, 516 classes | measured on saved native UVs |
| True unique-class gap / border | 1001 **33.872931 / 32.813274 px**; 1002 **34.881253 / 49.984375 px**; all classes resolved, no UV-class errors | gap/border subset green; image/mesh gates separate |
| Actual imported directional density | **5,685 target triangles**, **16 degenerate**, 5,669 nonzero measured; **319 failures** against 512–1706 and anisotropy<=1.02. Min **3.375097**, max **28,061.075026 px/m**, max anisotropy **1,979.016526** | **FAIL**, dominated by forced tiny native diagonals; input density was not lowered |
| Density percentile spread | 0.0001170349 ratio; this excludes degenerate triangles | NOT a pass: bad extrema/degenerates win |
| Mirrors / invalid UV polygons | **16 mirrored triangles**, 0 invalid UV polygons | **FAIL**; a valid polygon does not certify native tessellation |
| Independent frozen-PNG mask correspondence | **696/771** pass, **75 missing** beyond 5 mm, **0 false**; all native pieces sampled, 0 refusal; old v045 was 669/771 | **FAIL**; narrow rotated/low/cap/50-mm-band/stair traces still require source-bound sampling repair/classification |
| Actual exported xView | stairs 12 faces / 0 vertices / 1 bow-tie; walls 3 faces / 407 vertices (223 pairs) / 0 bow-ties | **FAIL**. Original four-face baseline does NOT cover all new source pairs |
| Course/bond edge residual, complete joint centre/width and all-map interval/Normal oracle | input chart/repeat retained; no new everywhere-valid certificate after native/bake changes | open; do NOT reuse v045's historical green counts |
| Preservation | 10/10 frozen source hashes and v045 native/FBX checked; source corner prefix retained. Protected boundaries are subdivided, not claimed byte-identical | full surface/topology certificate open |
| Visual verdict | four actual lit pairs + actual relief comparison available | **Artem gate open**, separate from the red technical repairs |

Raw xView: `normal-v097/xview.json`. Raw directional witnesses:
`normal-v100/directional-triangles.json`. Actual FBX triangles were reimported
and captured separately in v099; the density calculation does NOT inherit the
native sidecar's triangulation after replacing only polygon coordinates.

## Executed repairs and bounded rejections

1. Cell-first v071 initially refused a collapsed connectivity cell. Polygon-first
   v071 then saved self-intersecting n-gons and failed xView (exit 2). Retained,
   never promoted. v072 used explicit bounded connectivity accounting, but its
   native diagonals and unused/sub-2mm nodes failed.
2. Post-tessellation node coalescence v074 cleared many close vertices but created
   wall contact overlaps/inverted cells; **rejected**. It is not the current copy.
3. Simplifying **before** guarded offset, anchoring original corners and checking
   actual frozen active support reduced 6,323 native cells to **3,055**. Raw guard
   loss and active support were kept separate; no source identity was waived.
4. Source-local fan interpolation replaced world-float32/inverse-matrix round trips.
   World round trips created micrometre cap needles. The reusable helper returns
   original corners exactly and retains warped source fans. Saved local geometry
   and float64 world readback are separate from source-global rounding envelopes.
5. Exact repeated-vertex loops are split into all lobes, not discarded. Polygon-first
   v087/088/089 still exposed native pinches/unrepresentable triangulation; retained
   as rejected alternatives, not promoted over v085/v096/v097. Explicit local
   triangulation v086 retains **27 refusals**; it is a repair plan, NOT an applied
   complete mesh. The final imported candidate itself still has the red metrics above.
6. Initial bake v091 incorrectly compared a source affine residual in UV units.
   v092 measures the residual in metres and applies the existing **20 µm** gate;
   751 classes baked, no implicit first-entry source choice. An absent Blender
   World caused the v095 render setup to refuse; a NEW v096 world/copy fixed it.

## Reusable executable and code tests

`tools/materials/course_grid_pages.py` wraps the existing page assembler and
course-grid cores, not a new job-only packer or the future `agr unwrap-atlas` CLI.
It consumes explicit source hashes, immutable partitions/fold/member placements
and a declared tile budget. It rejects aliases (including hardlinks), duplicate
inputs/JSON keys, stale source/plan hashes, empty sources, NaN/inf, existing output
or `.partial`, and source mutation during planning. Output is always a candidate
with `passed=false`; zero CLI exit is NOT geometry/map/QA acceptance.

Actual fresh-process replay:

```text
uv run python -m tools.materials.course_grid_pages --recipe "G:/Мой диск/AGR-evidence/1326-stylobate-course-grid/normal-v098/recipe.json" --out <NEW layout.json> --report <NEW report.json>
```

v098's saved invocation produced **1,644 plan pieces**, 771 sources, 803 support
members and verified 10 frozen sources. Its face plan is exactly equal to the
plan used by the actual candidate. Reuse a NEW output/report path when replaying.
Baking/native construction drivers are retained with their inputs outside git;
turning the entire source-field bake/native finalization into the reusable
execution contract remains unfinished, not satisfied by this planner alone.

Tests-first commits: `d6ce190a` page membership/budget, `8937b559` source-local
fan interpolation, `7740fb28` exact pinch cycles, `e4839283` fresh CLI/path/hash
contract. All demonstrated missing-API/module RED before implementation.
New targeted tests: **35 passed** before the final affected run; final exact
command/counts are in `two-tile-checkpoint-v100.json`.

Full suite: deferred to merge batch (rule 68).
No eval/PR/review receipt is claimed on this incomplete pilot. Before eventual
review, merge current main without rebase, rerun affected tests/probes/evals,
check canonical decision IDs, push and open the one PR.

## Current user gate and continuation

The required visual verdict is now on an **actual source-Normal two-page copy**,
not the older Diffuse-only v014 and not the numeric fit diagram. Ask whether
v096's visible original relief, colour seams and course direction are acceptable
as the pilot's visual direction. **This does not ask Artem to approve or waive
any red native, density, mirror, PNG or all-map gate.** No replication follows.

After that verdict, continue the in-scope technical work on NEW **v102+** outputs:
source-bound sampling for the 75 remaining PNG cases; pre-tessellation source
noding/repartition (not v074 welding) and actual imported triangle quality;
new xView source pairs beyond D296; independent full Normal-frame/support,
carrier/junction/centre-width/mip measurements; source/protected surface proof;
reusable bake/native finalization; fresh final export/readback and exact final
visual/QA receipts. Never ask the two-tile, original-Normal or bevel-cut question
again, and never turn visual direction approval into technical acceptance.
