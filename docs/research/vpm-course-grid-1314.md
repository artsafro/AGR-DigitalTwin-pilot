# VPM brick-course / edge-joint UV layout: 4BK research (#1314)

Research snapshot: 2026-11-13. **Proposal, not an approved recipe or implemented CLI.**
No production mesh, atlas code, job, material ID or domain decision was changed. No DCC,
packer or final delivery was run here. Historical agent reports below are not new measurements.

**Recommendation:** constrain physical scale, course/bond phase and seam anchors *before*
packing; stack only appearance-equivalent regions; pack their representatives without scaling,
rotation or reflection. Prefer a Blender/bmesh adapter over rewriting the existing pure cores.
One tile is a target **per selected finish cohort**, not proof that all of 4BK fits one tile.
The session's two-tile target concerned tower metal panels, not the brick tile or whole delivery.

## 1. Evidence and 4BK session

### Reproducible source boundary

- **S1:** read-only Claude transcript
  `C:/Users/artsafro/.claude/projects/C--Users-artsafro--AGR-DigitalTwin-pilot--claude-worktrees-4bk-corpus-k3-modeling-6cfe72/d1636320-7403-4d5d-a4fb-b151aa37354d.jsonl`.
  Snapshot: 2,610 lines, 28,830,413 bytes;
  SHA256 `1b68760a3eef7c383f4c4d38d41b26791803e550c622829f21fe0ac4553b8fe1`.
  Line references below are physical JSONL lines; timestamps are UTC. Read only task-relevant
  user messages and UV task results; personal/meeting material is excluded from this report.
- **S2:** local repository `C:/Users/artsafro/.AGR-DigitalTwin_pilot`, branch
  `job/4bk-k3-vpm`, frozen commit `06546d3d9691d1bcc62171ffd07aa56a6c4de9e3`.
  Read `jobs/4bk-k3/TASK.md` (Brick scale, Typical module review, Roof, UV review),
  `jobs/4bk-k3/` file inventory and branch decision rows (no matching global 4BK decision row).
  This is the explicitly requested source branch, **not merged or copied into this branch**.
  Reproduce with `git -C C:/Users/artsafro/.AGR-DigitalTwin_pilot show 06546d3d:jobs/4bk-k3/TASK.md`.
- **S3:** current implementation/domain inspected in this worktree at base
  `2a42807f` (origin/main at intake). The [UV sheet](../domain/areas/uv-atlas.md),
  [UV rules](../domain/uv-textures.md), [conflicts](../domain/conflicts.md) and linked cores
  below are the baseline. No unresolved conflict is decided here: C29's historical padding
  variant is not adopted; C11's slot boundary is outside this one-cohort study.
- **S4:** [#1296 reuse report](reuse-1296/report.md), commands 3 and 9:
  `unwrap-atlas` is proposed, not shipped; `brick-seams` still needs calibration.
  [#1281](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1281) owns recipe adoption.
  This note is input to those efforts, not a replacement agent policy.

The issue was opened on November 13; S1's relevant session actually occurred **November 12**.
S2 stops before the later consolidation verdicts in S1; its earlier ID2 multi-tile acceptance
must not be mistaken for the final target. The transcript SHA binds this observation, not a
promise that an active local transcript will remain unchanged.

### Artem's rules and corrections

| Evidence in S1 (UTC / line) | Rule / observed course correction |
|---|---|
| 11:52 / 344; 12:07 / 605 | Delivered Bricks1 already accepted; architect's marked images/PDF govern material and panel-joint placement. First unwrap one typical floor, then replicate. |
| 12:55 / 1089 | Choose **38 courses (approximately 284 × 83 mm)** instead of 37. Preserve the half-bond at repeated floor joins; do not adopt the proposed shear workaround. S2 records this explicitly. |
| 13:01 / 1199; 13:04 / 1271 | Horizontal wedge bands must be metal **ID2**; niche sidewalls brick **ID1**. Reveals **ID3** already correct: do not recolour them when fixing niche walls. |
| 13:11 / 1457; 13:13 / 1510; 13:16 / 1538 | ID2 metal also needs panel joints: **10 mm**, placed from architect's red lines. These are not the mortar gaps already in Bricks1. |
| 13:47 / 1831; 13:53 / 1944; 13:54 / 1967 | Stylobate all brick, including disputed plinth, with panel joints following openings. Keep useful cuts; draw joints on the texture rather than inventing relief geometry. |
| 14:39 / 2347 | Stack UVs to economize; ideal tower metal target **two tiles**. Bind simple Diffuse previews so the joints can actually be inspected in the viewport. |
| 14:59 / 2443 | Manual method: same texel density → horizontal orientation → align **left edges** → stack on one painted vertical joint. Existing edge cuts determine where that joint appears. |
| 15:00 / 2489 | If a long face needs an interior joint, use a separate region/tile rather than blindly adding cuts. Two functional classes: edge-joint masters vs interior-joint patterns. |
| 15:46 / 2564 | After the reported two-tile capacity failure, explicit verdict: **“Давай 3 тайла”**. This is the historical fallback; it does not authorize a new job's fallback automatically. |

### What worked, what cost extra rounds

1. **37 → 38 courses.** Agent result at S1:1053 reported broken bond at all
   1,288 floor-boundary sample pairs with 37 rows; its shear variant avoided parity loss but
   changed the pattern. Artem chose even course count instead (1089), and praised the brick
   layout (1199). This is visual approval of that brick stage, not whole-delivery acceptance.
   For the 3.15 m floor, exact pitch is `h = 3.15/38 = 0.08289473684210526 m`.
   With Bricks1's 48 rows and 4096 px: `L = 48h = 3.9789473684210526 m`,
   density `4096/L = 1029.4179894179895 px/m`. The 284 × 83 values are rounded effective
   module descriptions, not authority to overwrite the customer's bitmap with a new brick size.
2. **Shared chart, not face-local unwrap.** The early agent used cumulative contour length
   for U, height for V, integer repeat shifts and stacking in tile 1001 (S1:1053).
   It reported 38 groups, no new cuts and no vertex changes at that stage, but also many
   discontinuities at niche/funnel corners. Do not describe it as universally seamless.
   A later superstructure result (1822) reused typical-floor U at the boundary: reported
   max 0.093 px over 540 paired points, after the previous stage's horizontal mismatch.
3. **Classification before UV.** Bands initially remained brick, niche walls/reveals were
   confused, and stylobate light plinth assumptions needed explicit correction. A finish/face
   manifest would have avoided these material rounds; a better packer alone would not.
4. **Unique baking inflated tile count.** S1:2028's band result reported 12 tiles at 524 px/m
   and 98 vertical joints. S1:2063 reported stylobate 15 unique tiles at 518 px/m. These
   were agent outputs, not Artem's desired reuse strategy; temporary numbering even exceeded
   1100 for the band. Sequential delivery renumbering remains a separate step.
5. **Edge-master reuse succeeded locally.** Consolidation result S1:2511 reported stylobate
   one tile at 512 px/m: 496 panels → 24 reusable regions, 1,953 joint samples all within
   5 mm, brick stretch ≤0.22%. This is useful historical evidence for the one-tile technique,
   **not an independently reproduced benchmark** or proof of all corner continuity.
6. **Two tower-metal tiles were not enough at the required density without cuts.** Same
   result: 1,582 panels → 113 regions; two 4096 tiles required 420 px/m, with 85 panels
   (~61 m²) unplaced at 512. That **fails** today's VPM lower bound; it is not a valid
   automatic density fallback. Packing was by capacity, not the requested strict A/B classes.
7. **Approved three-tile fallback still had defects.** S1:2586 reported 512 px/m, 116 regions,
   tile fill A/B/C 95/88/74%, and removal of window hatch artifacts caused by sampling a
   neighbour's seam. But only 97.9% of 2,094 edge-joint samples were within 5 mm (45 outside);
   only 7,091/7,119 interior samples found joints, 10 faces had edge stretch up to 3.3%.
   Area density 512 on every face does **not** prove directional bounds or full seam QA.
   The reported 5 mm foreign-line guard is not a certificate of 32 px unique-island padding.

Counts above refer to different source scopes/stages (panels, faces, regions, samples). In
particular 1,582 panels, 2,316 mapped faces and 116 packed regions are not one island count.

## 2. Techniques and tools

### Technique fit (engineering assessment, not a production trial)

| Technique | Fit for one tile + course/joint constraints | Failure mode / required constraint |
|---|---|---|
| Straighten / align to shared chart | Good for planar wall strips; explicit horizontal courses and vertical anchor edge | Straightening a genuinely curved/sloped chart can stretch it. Measure Jacobian; preserve original geometry. |
| Follow Active Quads | Good seed propagation over regular quad strips | Not a packer; seed must have correct aspect/scale. Unequal quads and funnels need independent distortion checks. |
| Module-grid packing | Best for brick repeat-preserving relocation | Translate by the **full appearance repeat**, not arbitrary pixels or merely one course; half-bond usually needs two rows (or a coupled half-brick U shift). |
| Grid-snapped general packing | Useful if snapping whole rigid chart translations to allowed phase classes | Rounding every UV vertex to pixels deforms brick; snapping after packing can break margins/containment. Solve constraints together. |
| Trim / edge-master sheet | Best match to Artem's left-edge method; one joint reused by overlapping different-width panels | Same colour is insufficient: right/interior edges must not sample unwanted seams; reserve safe field, account for joint ownership and horizontal lines. |
| Stack equivalent charts | Largest historical tile saving | Match finish, module, phase, normal orientation, seam mask, unique details and all D/ERM/N maps. Shape similarity alone is not appearance equivalence. |
| Generic free rotation / relax | Poor default for directional masonry | Rotation changes course direction; Relax changes phase and scale. At most use constrained relax before anchors are frozen, then remeasure. |

### Tool table

Official pages retrieved on 2026-11-13; API capabilities are vendor/source claims unless the
local fixture verification is explicitly named. “Headless” is not synonymous with licence-free
or display-free. Current online docs may be newer than the installed program.

| Tool / route | Fit and usable operations | Licence / cost class | Scriptable / headless? Local confidence |
|---|---|---|---|
| Blender built-in UV + bmesh | Align/Straighten, Follow Active Quads, Average Island Scale, Pack Islands; disable pack scale/rotation, preserve merged overlaps | Blender GPL; no paid packer required [B1, B2, B3] | Python operators/bmesh in background; operators need correct edit selection/context. Baseline here is 5.1.2; verify its RNA before using newer online parameters. Not executed on 4BK here. |
| UVPackmaster (online v4; v3 docs still available) | Single-tile, pixel margins, rotation control, Stack Groups / Lock Overlapping; good representative packer, **not** a course-phase solver [U1–U4] | Commercial product/engine; open add-on components do not grant engine rights. Free SDK Standard exists; SDK Pro is separately licensed [U5] | Official Blender Python examples. Blender background integration and edition/engine activation need a fresh-process trial; standalone engine CLI is **not verified**. Do not claim installed v4 or buy/install it for this research. |
| Texel Density Checker (mrven) | Set/check density before anchors; companion to a packer, not seam QA [T1] | GPL-3.0 source; distribution/store pricing distinct | Blender Python add-on; no standalone packer. Version/background compatibility on 5.1.2 untested here; area density cannot replace directional checks. |
| 3ds Max Unwrap UVW | Pack / Align / Relax; manual left-edge selection directly matches the session [M1] | Proprietary commercial Autodesk application | MAXScript interfaces and pymxs host bridge; batch still needs Max/licensing. UI-dependent selection/context must be tested; no 4BK batch run here. Relax is not accepted after anchors. |
| RizomUV Virtual Spaces | Dedicated straighten, density, grouping/packing workflow; good alternate representative packer [R1] | Proprietary commercial Rizom-Lab licence | Current vendor FAQ: Python, headless and RizomUVLink; **headless requires a graphical session**. Windows Link Python 3.6–3.13 per current FAQ, not this shell's 3.14. Installed project fixture is **2024.1**, not proof of current-version parity. |
| Existing RizomUV MCP | Typed load/unfold/optimize/pack/new-version save [R2] | Requires licensed native RizomUV | Managed application, not a generic arbitrary Lua/Python endpoint. Fixture readback verified locally in the earlier project; production locks/multi-UV/complex meshes not verified. |
| Scripted bmesh / pymxs + pure cores | Strongest way to carry source-face IDs, phase classes, seam ownership and deterministic reports | Project code plus host licence; no new licence promise for third-party engines | Pure math can be headless; bmesh inside Blender, pymxs inside Max. Build adapters around existing cores, not a job-specific new packer. |

**Padding versus mips.** Normative **between unique-image islands**: at least 16 px at 2048,
32 px at 4096; tile-border margin also required [S3, reg pp.30–31]. Distinguish *inter-island gap*,
*per-side guard*, *tile margin* and *raster dilation*. A conservative proposal uses 16/32 px
per side as well (giving twice that gap); this stronger engineering choice costs area and is
not a quotation of the regulation. For a gap `g`, mip level `l` leaves `g/2^l` mip texels:
32 px becomes 2 texels at mip 4; filtering/anisotropy can need more. Choose tested mip range,
dilate each map correctly (periodic wrap for repeats), and inspect textured joins there.
Dilation is not permission to shrink the normative gap. Overlapped identical regions are
one sampling class; distinct imagery classes still require separation.

## 3. Gaps against current code

| Existing source / observed contract | Reuse | Gap for this research target |
|---|---|---|
| [npm_atlas_udim.py](../../tools/materials/npm_atlas_udim.py), docstring, `_face_texel`, shelf packing | OBJ material/UV readback, directional singular-value density, affine crop/remap, named errors | NPM conversion, sizes 1024/2048, Ground 10–40, scale search; no VPM course/seam-master constraint solver. Do not flip a profile flag and reuse its shrinking policy. |
| [derive/npm_atlas.py](../../tools/derive/npm_atlas.py), constants and `main` | Finish→region table, explicit recipe input, separate NPM opacity | Fixed 2048, 5×4 cells, `PAD=6` per cell; region texture generation, not mesh unwrapping. No VPM 4096, D/ERM/N joint-aware packing, seam proof or course grid. Six is not a VPM margin. |
| [atlas_core.py](../../adapters/max/agr_tools/atlas_core.py), `pack` | Stdlib atlas planner, input checks, fit diagnostics, directional texel helper | `npm`/`groundel` profiles, 8 px minimum, 10–40 target validation; shelf/cell logic, not VPM fixed-scale brick packing. |
| [facadeatlas_core.py](../../adapters/max/agr_tools/facadeatlas_core.py), `strip_uv`, `plan` | Closest existing NPM reuse: common zero, whole `period_by_id` shifts, stack switch; preserve physical phase | Default 39 px/m/NPM atlas, plane-region frames, not 4BK edge/interior-joint equivalence or closed-contour/half-bond constraint solver. |
| [uvlayout_core.py](../../adapters/max/agr_tools/uvlayout_core.py), `project_k6`, grid cuts, whole-tile fold | **Already implements** shared perimeter projection, fixed scale, integer shift seam metric; do not reinvent it | Cuts on integer UV grid, not arbitrary approved joint lines; content padding/edge-master semantics are separate. Defaults 3.6 m / 3600 px are existing job/tool parameters, not regulatory VPM PNG dimensions. |
| [vpm_core.py](../../adapters/max/agr_tools/vpm_core.py), options/build pipeline | Projection, rescale, UDIM split/renumber, seam and texel checks; glass 1001 | No explicit 38-course floor anchor, joint ownership, appearance-equivalence classes or constrained fit/fallback. Export map size/padding must be reconciled explicitly, not copied from defaults. |
| [texel_core.py](../../adapters/max/agr_tools/texel_core.py), `summarize` | Meter-based area-density inventory, 512–1706 VPM band, dropped-face accounting | Area density misses anisotropy; it neither packs nor proves phase. |
| [udim10_core.py](../../adapters/max/agr_tools/udim10_core.py), density/distortion | Jacobian singular values, ±1% scale and 1.02 anisotropy logic | Distortion evidence is reusable; no brick-specific seam raster classifier or island-equivalence solver. |
| [UV-09–14 and V009](../domain/areas/uv-atlas.md) | Channel count, mirror detection, archive sequential tiles, partial ring-edge density | Still missing complete automated island padding, seam-raster correspondence, unique occupancy and complete scene/archive cross-check. Existing checks must not be presented as full delivery acceptance. |

Regulation permits sequential multiple tiles, requires one **UV channel**, forbids mirrors,
and discourages rotations. Project target one UDIM per texture/finish ID is not “one tile for
all finishes” and not a universal legal ceiling. Working material IDs are not UDIM numbers.
The session's separate viewport ID2/11/12 previews do not override final material-slot rules.

## 4. Proposed procedure

Draft for a later authorized pilot, **not an instruction to modify today's 4BK job**.

1. **Freeze intake.** Snapshot copied mesh/maps with hashes, units in metres, UV channel,
   source-face/finish IDs, Bricks1 repeat, approved joint paths and stage-specific fallback.
   Select one facade cohort and list protected geometry/materials. Done: explicit manifest,
   no unknown/ID0 mappings. Preserve signed/unique elements outside stacking.
2. **Build one chart.** For the typical floor use common perimeter arc length `s` and
   `z0=4.65 m`; floor step `H=3.15 m`, course `h=H/38`. Keep Bricks1 unchanged. Transfer
   boundary U from the approved chart to adjoining parts, rather than deriving new per-face
   axes. Done: every facade face accounted for; opposite floor boundaries retain bond parity.
3. **Resolve orientation and scale once.** Rectify only planar quad strips with measured
   distortion; retain horizontal courses and outward U winding. Use no mirror/pack rotation.
   Slopes, funnels, niches and ring closure receive explicit exception rows, not hidden shear.
   Done: physical module/scale and directional density in band before packing.
4. **Classify seam masks.** Edge-master panels record joint side/ownership; interior-joint
   panels record positions relative to their own anchor. At 10 mm joint width, decide whether
   centre lies on the edge (half each side) or entirely inside one face. The historical
   implementation shifted centres by 5 mm. Done: testable expected joint mask per panel,
   no assumption that different widths can sample the same master harmlessly.
5. **Stack equivalent charts.** Group by finish + full repeat/phase + orientation + D/ERM/N
   appearance + required/forbidden joint mask. For brick-only repeats use integer lattice
   translations; for edge masters allow only translations proven to sample the intended mask.
   Do not conflate these two transformations. Done: original-face→chart→representative map.
6. **Fit representatives at frozen density.** Pack into one padded 1001 domain for this cohort;
   disable normalization, automatic resize, rotations, reflections and vertex correction.
   Origins may be on a course/repeat lattice; vertices remain at their physical offsets.
   Include safe-field guards and mip budget during the fit, not as a final UV clamp.
   Done: real occupied/padded union measured and all representatives contained.
7. **Fail with alternatives when infeasible.** Report unplaced chart IDs, required extents,
   blockers, density, available area and packing algorithm/seed; heuristic failure is not a
   mathematical impossibility proof. Try approved seam-aligned cuts only with geometry
   authorization, or approved extra tiles, or a different source-approved texture strategy.
   Never silently lower to 420, stretch, delete faces or use a brick placeholder. For the
   historical tower-metal case, the actual user fallback was three tiles at 512.
8. **Read back and accept the pilot.** Export only to a new version, reimport in a fresh process,
   compare geometry/UV/IDs/map association, measure the table below, show viewport close-ups
   of straight walls, niches, corners, floor joins and interior-joint exceptions at chosen mips.
   Done: numeric technical report **and** separate Artem visual verdict before replication.

## 5. Acceptance metrics

Proposed engineering thresholds below need pilot approval; they are **not new regulation**.
This card provides the procedure/measurement specification, not a fresh 4BK unwrap. Current
mesh hashes, true island counts, directional extrema and geometric union usage are **not measured**.

| Metric / concrete 4BK sample | Definition and proposed pass condition | Historical evidence / limitation |
|---|---|---|
| Course phase at typical-floor and superstructure joins | Shared-point paired samples and complete common-edge segments; wrapped U/V residual in **full bond repeat**, multiply by actual texture pixels. Max ≤0.1 px; report unpaired points and coverage, not just p95. Check both mortar rows and head-joint parity. | S1:1822 max 0.093 px/540 pairs; historical, not all joins or independent readback here. |
| Panel-seam alignment / width | Sample expected 10 mm paths in **exported D/ERM/N**, reconstruct centre/width in world mm. Proposed max centre error ≤5 mm at **every** required sample; report missing and false joints separately, with complete path coverage. | Three-tile metal result fails: 45/2,094 edge samples outside 5 mm; 28 interior samples missing. Stylobate historical 1,953/1,953 within 5 mm. |
| Texel density spread | Per nondegenerate triangle singular values of metre→Diffuse-pixel Jacobian: all directions within 512–1706; report min/max, p5/p50/p95, `(p95-p5)/p50`, max anisotropy. Proposed target spread ≤2%, anisotropy ≤1.02; at lower-bound target, clamp tolerance **inside** legal band. | Area=512 does not prove min directional ≥512. Historical ten metal faces up to 3.3% edge stretch are open, not passed. |
| Tile usage % | `100 * area(union(unique sampled UV polygons))/area(tile)` per tile; padded union separately. Do not sum stacked faces or bounding boxes. Report occupancy including/excluding border guards. No normative minimum; propose ≥70% as optimization goal subordinate to seam/density gates. | Agent's 95/88/74% method not frozen; label reported fill only, not certified union occupancy. New one-tile usage not measured. |
| Island count and reuse | Report topological UV components before/after, logical chart count, representative count and input-face membership; each input face mapped or explicitly rejected. Keep unique signage out of stacks. | 496 panels→24 regions is reuse evidence, **not** measured island count. All current island counts remain not measured until fresh readback. |
| Tile / padding / orientation | One cohort in padded 1001; exported multi-cohort delivery sequential, one UV channel; zero mirrors, zero unintended rotations/cross-tile faces; unique-image gap ≥16/32 px at 2K/4K and measured nonzero border margin | Historical UV-in-0..1 alone proves none of padding, joint content or slot correctness. |
| Preservation / coverage | No unapproved XYZ/topology/material changes; every face and map traced. Empty, missing maps, unsupported, NaN/inf, unknown finish, zero area, output/input alias or stale source hash → error/incomplete, never full pass. | Validate exact thresholds explicitly: 512/1706 inclusive; just outside fails. Exactly 5 mm passes the proposed inclusive seam gate. No blanket “at threshold fails” overrules valid legal boundaries. |

### Why course-grid packing is not pixel snapping

For density `rho` and tile size `T`, UV per metre is `rho/T`; course pitch in pixels is
`q = rho * H/38`. At 512 px/m, `q = 42.44210526315789 px`, not an integer.
Accumulating rounded 42 px rows loses phase. Store metres/rational repeat indices until
rasterization. For half-bond, translating one row without a half-brick U correction changes
appearance; translating two rows preserves parity. Trim-master offsets must be raster-aware:
a valid repeat translation is not necessarily a valid move across a uniquely painted panel joint.

Conservative fit example (not a real facade measurement): `T=4096`, per-side border `p=32`,
`rho=512` gives max chart side `(T-2p)/rho = 7.875 m`; at 2048 with `p=16` it is
3.9375 m. These are necessary rectangle extents, not proofs of a multi-island pack. Finite
mip checks and unique padding can force fewer courses than the bitmap's full 48-row span.

## 6. Candidate CLI contract

**Design vocabulary only; these options and `agr unwrap-atlas` do not exist yet.** Use #1296
as the CLI owner. Job-specific quantities belong in a source-bound manifest, not defaults.

| Candidate option | Contract |
|---|---|
| `--profile vpm --tile-size 4096 --tile-budget 1` | Target for selected cohort; accept only VPM 2048/4096; budget failure emits a non-passing fit report. |
| `--finish-manifest <json> --cohort <name> --units m` | Explicit face/finish/map correspondence, shared origin/chart, expected joints, protected geometry and source hashes. Unknown keys/IDs error by name. |
| `--layout course-grid` or `--layout edge-master` | Different semantics: repeat-lattice translation vs seam-mask reuse; never silently interchange. |
| `--floor-height-m 3.15 --courses-per-floor 38` | Derive exact course height; module width/repeat and half-bond come from approved Bricks1 manifest. |
| `--texel-px-m <approved> --density-band 512:1706` | Freeze physical scale, no auto-fit shrinking; brick historical ≈1029.418, metal/stylobate compact route 512. |
| `--orientation preserve --mirror forbid --stack appearance-equivalent` | Validate direction, phase, seam ownership and every map; no geometric vertex correction. |
| `--gap-px 32 --border-px 32 --mip-max <approved>` | 4096 illustration; separate gap/border/dilation fields, rescale minima for 2048; report actual measured distances. |
| `--cuts forbid --on-overflow report` | Safe default. A later explicitly approved cut plan or tile budget can be supplied in the manifest; no interactive guessing. |
| `--backend blender --seed <n> --report <new.json> --out <new-dir>` | Fresh-process reproducibility and preservation; reject input/output/report/temp aliases before writing. A backend run is not visual acceptance. |

Report proposal: source hashes + versions/options/seed, each face's chart/finish, representatives
and stack transforms, rejected/unplaced lists, seam coverage/errors, directional density,
raw/padded union usage, actual island counts, map/tile filenames and all open gates.
No `passed=true` until every mandatory technical check is measured/passing; visual acceptance
and publication remain separate fields. Missing readback is not `pass` or a successful `not_run`.

## 7. Questions for Artem

These are **future pilot approval questions**, not decisions taken in this research. None is
needed to describe the known evidence; any subsequent production card must settle them first.

1. **Pilot scope:** recommend the already compacted **stylobate brick cohort** as the first
   one-tile test, then tower brick and ID2 separately. Is “1 UDIM” per finish/cohort, not the
   whole mixed-finish facade? Historical tower metal needed the approved three-tile fallback.
2. **Seam ownership:** recommend writing down whether a 10 mm panel joint is centred on a
   shared edge or entirely on one panel. Accept the historical 5 mm centre offset, or centre it?
3. **Acceptance:** recommend max 0.1 px course/bond residual, max 5 mm panel-joint centre error
   everywhere, ≤2% density spread and ≤1.02 anisotropy, with legal directional bounds overriding
   tolerance. Approve these targets and which mip/distance viewport view is authoritative?
4. **Overflow:** recommend report-only by default, preserving density and geometry; explicit
   extra-tile approval before new cuts. For a future compact pilot, are seam-aligned loop cuts
   allowed, and is historical three-tile metal fallback still applicable to that stage?
5. **Backend:** recommend built-in Blender/bmesh plus existing cores first; optional UVPackmaster
   only after a measured benefit. Any requirement to prefer licensed Max/RizomUV for manual edits?

## Primary tool sources

Fetched online for this research (2026-11-13); capabilities only, no claimed performance trial.
Initial plain urllib Blender request returned 403; browser User-Agent succeeded. Guessed old
UVPackmaster/Rizom deep links returned 404; canonical current links below were retrieved instead.
Blender's website licence page returned 403; source COPYING was retrieved. No missing page is
used as positive evidence. Current pages are discovery evidence, not frozen host-version manuals.

- **B1:** [Blender UV editing manual](https://docs.blender.org/manual/en/latest/modeling/meshes/uv/editing.html), Pack Islands (scale, rotate, pin, merge overlaps), Align, Average Island Scale. UI parameters can drift from installed 5.1.2.
- **B2:** [Blender UV operator API](https://docs.blender.org/api/current/bpy.ops.uv.html), `align`, `follow_active_quads`, `pack_islands`; [Follow Active Quads source](https://github.com/blender/blender/blob/main/scripts/startup/bl_operators/uvcalc_follow_active.py).
- **B3:** [Blender COPYING](https://github.com/blender/blender/blob/main/COPYING), GPL; individual source headers may specify GPL-2.0-or-later.
- **U1:** [UVPackmaster v4 documentation](https://uvpackmaster.com/doc4/blender/latest/) and [script example](https://uvpackmaster.com/doc4/blender/latest/48-other-topics/3-running-from-script/); example uses `bpy.ops.uvpackmaster4`, not the v3 namespace.
- **U2:** [Stack Groups](https://uvpackmaster.com/doc4/blender/latest/20-packing-functionalities/55-stack-groups/) (similarity alignment is not semantic equivalence); [Lock Overlapping](https://uvpackmaster.com/doc4/blender/latest/20-packing-functionalities/50-lock-overlapping/).
- **U3:** [Pixel Margin](https://uvpackmaster.com/doc4/blender/latest/20-packing-functionalities/30-pixel-margin/).
- **U4:** [Island Rotation Step](https://uvpackmaster.com/doc4/blender/latest/20-packing-functionalities/80-island-rotation-step/); require disabled rotation, not merely a 90-degree step.
- **U5:** [Vendor product/licensing entry](https://uvpackmaster.com/) and [Free SDK / Pro contact](https://uvpackmaster.com/free-sdk/). Do not infer redistributable commercial engine rights from a free SDK download.
- **T1:** [Texel Density Checker source and GPL-3.0 licence](https://github.com/mrven/Blender-Texel-Density-Checker).
- **M1:** [Autodesk Unwrap UVW MAXScript transform/align methods](https://help.autodesk.com/cloudhelp/2026/ENU/MAXScript-Help/files/3ds-Max-Objects-and-Interfaces/Modifier-MAXWrapper-and/Modifier-and-SpacewarpModifier/Modifiers/UVW-Modifiers/Unwrap_UVW-Modifier/GUID-496CE46A-EBD3-40C2-9637-3F21E0F0B0FB.html). Pack/Relax are native Unwrap operations, not evidence of a course-aware solver or a display-free service.
- **R1:** [RizomUV Virtual Spaces / automation FAQ](https://www.rizomuv.com/virtual-spaces/), including graphical-session headless requirement and Link Python support.
- **R2:** [Project RizomUV capability status](../agents/CAPABILITIES.md#rizomuv--rizomuv) and [RizomUV skill](../../.agents/skills/rizomuv-mcp/SKILL.md): verified fixture boundary and typed adapter limits.
