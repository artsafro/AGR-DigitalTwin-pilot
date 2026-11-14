# #1315 — accepted shrubs replicated, v009/r2 (not delivered)

**`passed=false`. Cells: `ground-npm` / `ground-vpm`.** [D291] records Artem's
answer in issue comment 6880380487: v008/r2 shape/centre/Hydrangea accepted for
replication without edits. This pilot-picture gate is CLOSED, not asked again.

## Actually reproduced

- v009/r1 replaces **4,576** shrub copies with the exact accepted radial-half-card
  plus centre-strip construction. Six Acer remain unchanged. **4,582 plants and
  38 accepted-by-picture MAF** retained; candidates are still not article-matched.
- Actual exported non-UCX triangles: **157,141 NPM /617,840 VPM**: Ground58,896,
  Flora64,124/390,804, MAF34,121/168,140. NPM <=180,000; no instance deleted.
  VPM carries the same **600 UCX /6,876 triangles**, NPM none.
- v009/r2 binds one placed-scene **2048 Flora atlas**. Hydrangea/Luteus use exactly
  the cropped interim maps of the accepted pilot; Acer uses allowed Royal Red
  [D287]. Syringa and species-level Physocarpus remain explicitly **GREY** [D289].
  This is interim restoration, not recovered original maps or final VPM density.
- Fresh native Blender5.1.2 FBX import completes both profiles; it drops **39/48
  malformed MAF faces**. Do NOT call its157,102/617,792 census byte-exact. Raw FBX
  reconstruction retains157,141/617,840; **604/604 actual-export mesh arrays**
  (vertices/triangles) are exactly equal r1→r2. UV/material arrays intentionally change.
- All **4,620 placement/seating/height controls per profile** retain prior handles,
  source identities, Ground Z and heights; source points unchanged. Actual per-plant
  crown comparison to v007: **4,582/4,582 within20% each** (NPM0.883803–1.037485,
  VPM0.897742–1.051455), height delta<=5.97e-8m. Asymmetric bbox centres can shift
  71.5/115.6mm with the new fan; these are NOT planting-point movements. Native atlas
  readback confirms both NPM RGB2048 PNG maps packed, one set. Canonical library
  material IDs are **not audited**, not guessed from species order.
- **4 source +9 geometry-library +3 A101 original-map hashes unchanged**; cropped
  map copies are separately hashed. Original scenes/libraries were never written.

Actual FBXs, .blend files, raw/native readback, scripts, rejected experiments and
renders: `G:/Мой диск/AGR-evidence/1315-cold-silikatny/v009/`.
`review-sheet-v009-NOT-DELIVERED.png` shows actual site/detail plus the separate
model option below. Neutral grey comparison is geometry-only, not species-material
approval. Tiny preview is not a full-resolution review substitute.

## Technical results, not requests to approve FAILs

NPM exported-array xView **3,239 faces /1,030 vertices /669 bowties**;
Flora alone42faces/4vertices, Ground alone0/0/0. VPM whole-file xView
**49,309 faces /70 vertices /298 bowties**. r2 geometry is independently exact-equal
to r1, so these geometric counters carry forward; not UV/material acceptance.
Public validators execute on actual r2 FBXs and **FAIL**; exact machine-stage
counts/findings are in `source-wide-summary-v009-r2.json`.

NPM public Flora aggregate topology falls from historical v007 **787,273** to
**41,370** duplicates/self-intersections, still >100 per mesh. Isolated fans passing
did NOT prove a joined hedge pass. VPM contact classification includes **33,931
cross-plant pairs**, **94,823 same-MAF-instance pairs**,114 Ground/MAF,36 Flora/MAF,
45 cross-MAF and136 internal-UCX pairs. Nothing is excluded as 'intended'.

Two rejected VPM diagnostics are retained, not promoted: one used wrong area7872;
its retry used the correct9568.799640m2 but a filter that missed native `.001`
material names. Final r2 uses source area12958.738864−3389.939224 and the actual
`M_SIL13_Ground_[1-9].001` filter. Neither diagnostic failure is a source decision.

## Three bounded non-shape hedge repair attempts

Actual eight nearest same-species plants around handle `33FC3FE+33FC417_11`:

| Route | Measured result | Disposition |
|---|---|---|
| Baseline replicated r2 construction | 42 self-intersections,112 NPM triangles | Actual dense group, not synthetic source data |
| Common Z rotation, unchanged points/heights | 34 self-intersections | Rejected, not a topology repair |
| Crown factor0.8, unchanged points/heights | 21 self-intersections | Rejected, still crosses |
| Exact intersection imprint +1e-7m coordinate identity | 7 combined defects;35 xView faces;310 triangles | Rejected; no silent welding/threshold waiver |

Separate copied-MAF exact-imprint experiment also remains rejected: sampled
same-object changes project to **237,654 NPM >180,000**, and xView still fails.
This is a projection, NOT a built237k site or proof that all possible repairs fail.

## New model-owner choice: crown trimming, not C44 waiver

A separate geometry-only option clips each derived plant to a disjoint local
Voronoi cell with a **6mm inter-cell gap**. NOT applied to the site. The actual eight
points/heights/plant identities remain. Fresh native-export/readback **112 NPM /
672 VPM triangles**, public xView **0 faces/0 vertices/0 bowties** both profiles;
actual-array topology **0 defects** both. No species maps/UV/profile-material pass
is claimed for this geometry-only option. The comparison columns are translated
for display; exported candidate coordinates remain the actual site coordinates.

But individual crowns shrink outside the retained80% baseline band:

| Profile / handle suffix | Original crown m | Option crown m | Retained |
|---|---:|---:|---:|
| NPM /2687 |0.710655|0.511823|72.0%|
| VPM /11 |0.717869|0.569779|79.4%|
| VPM /2687 |0.759418|0.517049|68.1%|

The80% probe is against the previously accepted individual library-copy bbox, not
an invented planting-schedule crown value. [D289] retains accepted crown ranges;
[D291] accepts the displayed isolated construction **without edits**. A worker
cannot silently spend those limits on overlap clipping, equate retained source IDs
with unchanged visible crowns, or call a group silhouette unchanged without a
measurement. This is why the option needs a model decision, not approval of a FAIL.

**Question/recommendation to Artem:** permit a job-scoped crown-trim representation
for overlapping hedge plants, as this separate eight-plant option, retaining all
plant IDs/counts/points/heights but allowing the disclosed individual-crown loss
(and requiring measured full-site losses plus new visual review before delivery)?
Recommend this narrow option, no topology/checker waiver. Otherwise keep individual
crowns and choose a different hedge representation/placement constraint explicitly.
Accepted r2 shrub construction and v006/r5 composition are not reopened.

## Per-area reproduction / remaining ownership

| Area | Reproduced this continuation | Blocker: value / limit / owner |
|---|---|---|
| Ground | Same source-derived58,896tri master, exact actual-export geometry; public checks rerun | Skirt reports6mm vs>=1m; curbs/details/materials/UV/UDIM remain worker-owned |
| UCX | Same600VPM-only hulls/6,876tri, noneNPM; source-array carry-forward is exact | Internal xView136pairs plus historical wide-neighbour/continuous-coverage work; worker. Prior175,688samples<=79.836mm is historical sampled evidence, NOT new continuous proof |
| MAF | All38 same library copies/10schedule rows retained; failed exact-imprint experiment measured | Actual topology/normals, native39/48face loss, unused `.001` material names and22schedule gaps; worker/source, not a new approval request |
| Flora | All4,582points retained,4,576accepted derived shrubs built; one actual interim atlas; native/raw readback | Joined41,370defects vs100 and cell-option individual crowns68.1–79.4% vs retained80%; model-owner choice for crown clipping, implementation/QA remain worker-owned |

Source gaps remain Abies1, Red Sunset4,22MAFrows and133m2 flowerbed without rates;
missing exact maps stay grey, no substitute species. Final textured visual review
and complete SINTEZ remain separate. No PR/review/readiness increase claimed.

## Historical comparison (report-only, after this build)

No earlier Silikatny geometry/drivers were consumed as construction hints. Only
this job's own frozen continuations, source/library copies and shared procedures.
Historical PR descriptions read after the actual v009 build, not their branches:

- **#906 Vatutino Ground v015**: accepted Ground-only route A,12fixedIDs,xView0/0,
  exact master-bound texel exception. Our Ground0/0 alone does not reproduce its
  complete accepted material/skirt/quad contract; whole-site FAILs remain. No D193
  exception transfers to this new master.
- **#969 Elevatornaya VPM OKS**: accepted building/window/lighting delivery v005,
  not a Ground/MAF/Flora etalon. Compare source→Gate1→pilot→export/readback→acceptance
  discipline, not triangle counts or species. Its job-specific exemptions do not
  transfer to Silikatny.
- **#1178 Flora route A**: merged stars/one2048atlas/placement/readback and visual
  gate. This run has an actual one-atlas readback and retained planting controls,
  but the new dense joined hedge still fails; no inherited acceptance. No historical
  model topology or runtime was remeasured, so no speedup/equivalence claim.

## Execution / receipts

Job-local new/adapted Python drivers only, sealed under v009; **no shared module or
checker change**. Production route: one headless build (r1), one material-only build
(r2), fresh native and raw readbacks per profile/version, public xView and package
validators, three bounded repair probes and the separate crown-option pilot.
`source-wide-summary-v009-r2.json` / `evidence-v009.json` bind exact counts, paths,
SHA256s and retained errors. This is not a claimed cold one-command shared tool.

Decision regression: before the new applicability anchor, affected docs/decision
suite **1failed/114passed (D291 unanchored)**; anchor then **115passed**. Real-source
Flora aggregate RED remains41370>100; only the isolated exported cell-option checks
are GREEN. Full suite is deferred until a finished PR via suite_slot; shared code
was not changed and no delivery acceptance is implied by documentation tests.
