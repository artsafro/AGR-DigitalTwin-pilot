# Flora library audit: Max Text labels to catalogue (#189)

## Question and scope

Can the supplied real 3ds Max Flora display library become a lossless, inspectable
catalogue without guessing species/profile assignments? Compare naive nearest XY
labels with a display-plane-aware rule, then archive each plant mesh separately.
This is an audit, not a modelling operation or a passed delivery. No species,
textures, production checker, standards, `data/`, or source scene is changed.

Research starting point: [Max scripting](../research/3dsmax-scripting.md),
`tools/max_profile_roundtrip.py`; source practice: the user-provided Flora grilling
notes (2026-10-15). TextPlus needs `GetPlaintextString`, not a `.text` property:
[Autodesk API](https://help.autodesk.com/cloudhelp/2017/ENU/MAXScript-Help/files/GUID-09B39BE2-1752-4715-BD00-6B623DA75F9E.htm).
The script uses a static MAXScript by-reference adapter, without interpolated input.

## Setup and reproducibility

- Branch base: `7840deb`; dedicated worktree/card `t_366e8d9d`.
- **Headless 3ds Max 2026**, actual product 2026.3 (28.3.0.30732), embedded Python
  3.11.12. Both input scenes report meters, SystemScale 1, `decodeValue('1m') = 1`.
- Only `dcc_batch.py max`, ping first, shared session lock; no live bridge and no
  safe-mode changes. The orchestrator explicitly confirmed headless-only scope.
- Desktop originals were hashed, copied to `C:/x/t_366e8d9d/`, then copies checked
  against the recorded originals. Max loads those copies, never Desktop paths.
- Outputs: new `C:/x/t_366e8d9d/assets-v001/` (MAX baseline) and `assets-v002/`
  (FBX alternative), outside Git. Test basetemps use
  **children** of the card root, never its root (pytest deletes its basetemp).
- Commands and exact script roles: [experiment README](../../experiments/flora-library-audit/README.md).
  Machine catalogue: [catalogue.json](../../experiments/flora-library-audit/catalogue.json).
- Baseline and prototype use the **same extracted nodes**, exclude the same
  envelopes/planters/references, and each pairing is timed three times. Pairing
  timing excludes Max startup, scene loading and saving; it is not a batch-speed claim.

The installed `polyunwrapper_autoload.mse` reports a CLR startup error, native exit
`4294967166` (-130). The wrapper classifies this as a startup warning. Real job
markers, current JSON, artifact hashes and readbacks—not that exit alone—determine
whether this audit ran. Both inventories also warn about missing
`mrmaterialattribs.gup` (legacy mental-ray displacement attributes). These are
preserved caveats, not repaired by changing the user's installation.

## Inventory and interpretation

| Scene | Nodes | Text / TextPlus | Plant meshes | Other nodes accounted |
|---|---:|---:|---:|---|
| FLORA_Union_v1 | 506 | 320 / 6 | 90 | 80 `Box*` envelopes (role unverified), 5 planters, 4 size cylinders, 1 particle-view helper |
| FLORIO_2BT_2022 | 69 | 23 / 0 | 46 | none |

The library contains 80 ordinary species-label display slots, co-located plant
alternatives and extra/unlabelled plants, **not 90 proven unique species**.
Do not deduplicate by nearest position or replace a raw label with a guessed name.
Tree/bush type is inferred from the display-heading regions; bush includes
ornamental perennials, and project grouping uses node-name evidence. No labelled
hedge samples were found, so hedge statistics are `n=0`, budget `null`.

Exclusion evidence, not just the `Box*` name: **80/80** have 20 triangles,
`Multi_Ground` material, and their bbox top is at/below their placement Z (within
1 mm); plants extend above that level. These are display-plinth candidates, not
assumed vegetation or UCX. Their names, positions, bboxes and material names remain
in `excluded_nodes` for review; they are not silently discarded.

Raw `LP`, `HP`, `LP -> HP` tokens are retained. Their NPM/VPM candidate interpretation
is explicit; a shared candidate participates in both descriptive profile groups.
These tokens do not establish regulatory conformity. Project `_high` / `_low`
names are retained as the basis for its profile candidates.

Library labels contain species names, triangle counts, profile/variant tokens and
notes, not height/crown-diameter strings. Missing labelled dimensions remain null;
world-bbox XYZ dimensions in meters are always recorded. The project contains
multiline `Hnnn` labels; interpreting H as centimeters is explicitly an assumption,
not a unit inferred from Max's system units. All heights and species alternatives
in a row remain available alongside the node-name H value and measured deviation.

All plant entries reference bitmap paths that Max cannot resolve at those stored
paths. The catalogue inventories materials/submaterials, original bitmap paths,
and bitmap-sharing counts (atlas **candidates**, not verified atlas pixels).
No texture search/repath/copy or new texture was attempted. SVG previews are actual
native-mesh XZ wireframe projections, **not textured botanical appearance approval**.

## Methods and baseline

1. **Baseline:** unbounded nearest mesh-pivot distance in XY, retaining ties.
2. **Prototype:** library front-facing display uses XZ. Project labels sit far left
   of two high/low mesh columns, so use Y-row distance and retain both candidates.
   The final catalogue uses bounded distance, distinguishes category headings,
   and reports ties/unpaired nodes. This is the only method evaluated for adoption.

The quality proxy is **unique agreement with the literal triangle-count label**,
not independently proven species accuracy. The library comparison does not count
the excluded boxes as plants. Project two-profile ties are expected row membership,
not permission to silently choose one species from a multiline schedule.

The three discrepancies in the ordinary triangle labels remain findings:

| Source node | Label triangles | Measured triangles | Interpretation |
|---|---:|---:|---|
| `SM_klen_tatarsky001` | 1901 | 1091 | literal source-label mismatch; not corrected |
| `Object002` (Клен Гиннала slot) | 10 | 8 | literal source-label mismatch; not corrected |
| `SM_boyaryshnyck_obyknovennyi001` | 488 | 574 | co-located alternative; ambiguous pairing, not corrected |

The audit never claims those labels are the ground truth for automatic repair.
Nine library meshes have no paired species/profile label (hidden spare linden plus
plants accompanying planters); the source names and measurements remain catalogued.

## Results

| Metric (same inputs, median of 3 pairing runs) | XY baseline | Layout-aware prototype |
|---|---:|---:|
| Library pairing runtime | 0.0218773 s | 0.0219857 s (XZ) |
| Uniquely triangle-concordant labels, including hidden TextPlus | 26/81 | 78/81 |
| Unique / ambiguous labels, before heading/distance classification | 116 / 210 | 321 / 5 |
| Project pairing runtime | 0.0007941 s | 0.0006168 s (Y row) |
| Project rows associated with both variants | 0/23 | 23/23 (explicit two-candidate ties) |

Final bounded library classification: 319 paired, 4 ambiguous, 2 category headings,
1 unpaired note. Final project classification: 23 ambiguous/two-variant rows.
Ordinary Text-only concordance is 25/80 -> 77/80; the additional hidden TextPlus
triangle count raises both numerators/denominators by one. This is not 78 proven
species assignments, only agreement with recorded count strings.

### Proposed descriptive library budgets

| Type | Profile candidates | n | Min / median / max triangles | Proposed review above |
|---|---|---:|---|---:|
| Tree | NPM | 28 | 8 / 531 / 3830 | 3900 |
| Tree | VPM | 26 | 264 / 830 / 6267 | 6300 |
| Bush/perennial | NPM | 43 | 18 / 80 / 1254 | 1300 |
| Bush/perennial | VPM | 40 | 32 / 84 / 1254 | 1300 |
| Hedge | NPM / VPM | 0 / 0 | no samples | null |

Counts overlap where a mesh is labelled `LP -> HP`; they must not be summed as
unique assets. The complete plant inventory is 90 library meshes / 49,929 triangles
and 46 project meshes / 12,186 triangles; there are 67 / 24 distinct top-level
material names respectively. Project comparison: tree NPM max 238 versus VPM 1914;
bush NPM max 979 versus VPM 5074. Project bushes mostly use 10/20 triangle low/high
pairs, unlike the library's broader variants. Name-based type grouping is an
explicit audit heuristic, not permission to substitute one library for another.
No exact mesh names are shared across the two sources.

### Native export outcome: INCOMPLETE — acceptance not met

| Attempt | Real result | Readback status |
|---|---|---|
| Per-node `saveNodes` MAX | 9 completed MAX files; 8 inter-save intervals, median **47.043 s** | not run; stopped because 136 outputs cannot fit this timebox at this cost |
| Per-node binary FBX alternative | 1 FBX file produced before cancellation; none existed at the observed 259 s checkpoint | not run; still too slow to finish all 136 outputs within the remaining time |

Both tracked native process trees were stopped, and a process query confirmed
only the pre-existing user's Max remained (PID 164400). No source save, live
command or safe-mode change was used. Partial native outputs remain outside Git,
not replaced or promoted to verified assets. The catalogue marks only the one
FBX as `produced_unverified`, all other requested FBX files `not_produced`;
missing file/preview paths are null and planned paths are explicitly separate.
The standalone final verifier is deliberately fail-closed until a complete
136-entry native readback exists. No `verification.json` or all-asset pass is claimed.

Evidence: [partial-verification.json](../../experiments/flora-library-audit/partial-verification.json).
The original and copied source hashes were checked **again after both native
attempts**, unchanged 2/2:

| Source | Bytes | SHA-256 before = after audit = copy |
|---|---:|---|
| FLORA_Union_v1.max | 19519734 | `30d7fc32fc534e7165ac1f47385cdcf2a91adb967228a087e3a9404a6e397416` |
| FLORIO_2BT_2022.max | 6041600 | `787dce8aeb7aa826c4f35c583a869e4cd89f34e035f92c4d83bd0fd696faaca8` |

**Blocker:** the required one-file-per-species/version archive and all-file
readback are not delivered. Two native export variants have failed to complete
within the card's bounded run; do not claim #189 complete. The next decision is
whether to authorize a longer native archive/performance-diagnosis run, or accept
geometry-only per-variant OBJ snapshots with material references in the catalogue
instead of self-contained native/shader assets. No third native attempt is made.

Automation caveat: while the first tracked export was active, the shared lock
file disappeared; this card never manually removed a lock. The wrapper's stale
check uses the **waiting caller's** timeout, which can be shorter than the holder's
run. This is a wrapper-side coordination risk, not fixed outside the worktree.
No further native call was launched until this card's own process tree was stopped
and only the user's pre-existing Max was observed.

## Verification already executed

- Tests-first RED commit `072feca`: missing `catalogue.py`, collection failed as
  expected. GREEN: first 7 probes passed; expanded standalone suite **11 passed**.
- Generated order-invariance probe: 41 coordinate cases, both mesh orders.
- Generated overwrite/traversal probe: 100 rejected hostile names, synthetic
  reference content unchanged; explicit existing-path refusal also tested.
- Catalogue accounting probe: 506/69 nodes and 326/23 labels accounted; 136 unique
  entry IDs, all candidate links refer to present plant handles, no delivery pass.
- Existing project suite: **3279 passed, 9 skipped, 13 deselected**, 326.45 s.
  Initial 360 s foreground attempt timed out at 94%; complete retry used a tracked
  background process. No production/test/benchmark fixture changes versus `7840deb`.
- `dt profiles check`: 3 profiles, source hash/traceability OK;
  `dt schemas --check`: 11 schemas OK.
- Regression eval receipt: `tmp/evals/flora-library-audit/report.json`, exit 2,
  0 passed / 0 failed / 10 not measured: Hermes lacks the expected Claude-format
  transcript and PR evidence files. This is not a regression-eval pass.
- CI: not run (billing lock).

## Verdict and proposed follow-up

**ADOPT, bounded to this display layout:** explicit display-plane/row pairing with
raw tokens, tie lists and unpaired records. It is preferable to XY nearest-neighbour
selection on this source; no claim is made for arbitrary library layouts.

Proposed follow-up (not an issue created): **"Flora catalogue intake: explicit
layout schema and reviewed species/profile IDs"**. Scope: promote the audit only
after a reviewed mapping for ambiguous/co-located and unlabelled entries; retain
raw source evidence, reject unknown layouts, add a hedge fixture before proposing
its budget. Keep empirical per-plant review thresholds distinct from the existing
whole-Ground regulatory budgets.

**MAYBE:** use the observed type/profile maxima as review-only planning budgets.
They are not regulatory limits and do not account for planting quantities or site
area. The NPM 180k budget covers Ground + GroundEl + Flora together; nothing here
allocates it per plant or changes a checker.

**REJECT:** automatic authoritative species substitution, textured appearance
approval or a delivery pass from this audit. Missing maps, raw ambiguities and
unverified H-token units remain explicit review items.
