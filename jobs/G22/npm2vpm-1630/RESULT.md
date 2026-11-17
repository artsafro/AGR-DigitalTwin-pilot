# G22 NPM cell-ID recovery — issue 1630

## Outcome

Shared `agr npm-ids` and the `npm-to-vpm` skeleton are implemented. G22 _01/_02
have provisional ID mesh copies, numbered atlas + model wire/colour sheets and
exact native readback. This is **not a VPM delivery**. The acceptance's alternative
outcome (exact regions-mode blocking finding with a follow-up issue) is used;
no Multi/Sub, VPM UV, checker, xView or package success is claimed.

## Immutable source and answered permissions

Inputs: `C:/x/npm2vpm-g22/src/0707_Garibaldi_22_01.fbx`, `_02.fbx`, delivered
2026-11-05, plus linked diffuse atlases. Manifest:
`C:/x/npm2vpm-g22/SHA256SUMS.txt` (32 files). Originals and delivered packages stay
untouched. Blender 5.1.2 headless was selected for ID/native-copy proof; the
stdlib `npm2vpm_core.plan` regions mode was selected for conversion diagnostics
because it writes nothing and never touches another Max session.

Artem 2026-11-17 option a remains selected: corrected atlas cells first, then seam
cuts into several IDs/tiles. The orchestrator's later exact cleanup approval was
applied ONLY to zero-world-area source polygons **68903, 69759** (0-based) of
`SM_Garibaldi_22_002_Main`, on a new copy. `approved-drops.json` records both
original polygon/triangle indices and reasons; `source_polygons` / `source_triangles`
preserve the surviving lineage. This is not blanket source-geometry cleanup.

## Final evidence

Root: `G:/Мой диск/AGR-evidence/1630-npm2vpm-g22/`.

- `_01`: `t_9d398e0d-v005-01/`.
- `_02`: `t_9d398e0d-v006-02/`.

Each directory contains `mesh_ids.json`, `id_table.json`, `regions-plan.json`,
`approved-drops.json`, `diagnostic_ids.blend`, `native-exact-readback.json`,
numbered `sheet-<mesh>-0.png`, model colour/wire renders, reproduction scripts,
source verification and `SHA256SUMS.txt`. IDs are layout labels, not approved
library materials. ID0 is explicit magenta/manual, never a guessed first cell.

| Mesh suffix | Source polygons | Copy polygons | Cells | Assigned | Unassigned | Straddling / ambiguous |
|---|---:|---:|---:|---:|---:|---|
| 001_Main | 148186 | 148186 | 26 | 148186 | 0 | 0 / 0 |
| 002_Main | 73306 | 73304 | 11 | 39204 | 34100 | 0 / 0 |
| 003_Main | 51146 | 51146 | 23 | 25933 | 25213 | 0 / 0 |

Fresh native readback asserts exact local/world vertex positions, triangle topology,
per-polygon UVs, IDs and one UV channel for all three saved meshes. This proves
ID-copy fidelity and the approved two-face deletion, not source topology quality.
The original per-face arrays and exact unresolved lists remain external, not in git.

Before/After evidence uses the real delivered FBXs and new diagnostic `.blend`
copies, one shared fitted camera/settings per pair, through the existing
`tools/review/before_after.py` owner: `t_9d398e0d-before-after-01-v001/` and
`t_9d398e0d-before-after-02-v001/`. The change is provisional-ID display, not a
VPM render. Both pairs were visually inspected. The enclosing manifest hashes
are in `EVIDENCE.json`.

Final additive audit: `t_9d398e0d-v007-final-audit/audit.json` validates the saved
protocol and replays the conservative half-pixel boundary against every assigned
face. Maximum outside-cell extent is 0.1856689453125 px on mesh001 and zero on
mesh002/003; none reaches the 0.5 px cap. Final array identities/counts therefore
remain valid after that stricter guard. It rechecks all source hashes and prior
sealed manifest entries without rewriting them.

## Exact regions-mode finding

`_02`: mixed/nonrectangular cell **2** on mesh002 and **11, 14, 22** on mesh003
remain manual. They visibly contain several distinct palette/window regions.
The source-UV coverage veto prevents treating internal drawing/window lines as
material seams. Recovery reports all 59313 unresolved faces rather than guessing
library or glass semantics. Full regions plans stop with `unmapped material ID 0`
on mesh002 triangle 0 and mesh003 triangle 234. Corrected cell IDs are local to
each object, not a global library mapping.

`_01`: corrected ID4 is one coherent grey rectangle `[0,480,1081,896]`, 7384
faces / 2888.416552 m2 summed area, not several visibly glued materials. Overlapping
repeat UVs explain why summed area is not unique texture area. Its required extent
at 512 px/m is 1.039761668 x 0.310475692: it needs the approved seam policy.
The same complete regions preflight also fails IDs 2/3/6/7/8/9/12/13/16/19/22/25
on the current crop-preserving layout/metric; e.g. ID2's scaled texel interval is
512..803101.954804 px/m, ID22's is 512..696376059.885347. These are conservative
current-layout findings, **not optimal tile counts or a claim that that many
physical tiles are necessary**. The shared regions core has no source-bound
per-island seam/metric repair stage, so an output would not be a valid VPM.

No arbitrary geometric cuts or new UV-policy guesses are made to hide those
findings. Option a is recorded, not revoked or asked again. Its source-bound
implementation must run after complete material-boundary recovery and must retain
face lineage, pattern phase, texel bounds and the ID/tile limit. The exact finding
and required continuation are handed off separately; downstream gates remain
not_run on this blocked plan. Follow-up URL is recorded in the PR/card when issued.

## Software / safety

- One segmenter: `maf_atlas_cells.segment`, facade profile with source-UV coverage
  veto and mixed-region diagnostics; the default MAF profile remains unchanged.
- ID table includes atlas path, cell pixel box, ID, face count, exact unresolved
  indices, empty cells and UV-union coverage. It is not `npm_table.json` (which
  carries inverse-conversion provenance); the recovered IDs feed regions mode.
- Full intake/index/UV protocol validation precedes segmentation. Unmapped slots,
  negative/bool/out-of-range indices, duplicate objects, partial arrays and
  nonfinite data fail. JSON source and referenced atlas hashes are compared before
  publication; this detects persistent mutation, not edits restored between checks.
- Output must be a new directory distinct from all discovered inputs, including
  missing transitive references. Random private staging; exclusive output files;
  ID report last; rollback removes only this invocation's recorded files. No
  predictable `.partial` output or overwrite/replace of inputs.
- Exit 1 is diagnostic/blocked; exit 2 is invalid input/native failure. Neither is
  success. The CLI does not apply a native copy on a blocked conversion gate;
  the real G22 copies were explicitly made as diagnostics, not a gate bypass to VPM.

## Verification history

RED commits: `02a6d246` (2 missing-feature failures), `4b232378` (facade profile),
`d61f7ce0` (13 protocol/drop/path failures), `2be61af5` (native drop + skeleton,
2 failures), `9e3edcb3` (1 polygon/triangle UV disagreement failure), `19c83728`
(1 exact pixel-tolerance cap false-clean).
The focused pre-boundary run was 39 passed, 0 failed; final complete affected-test
counts/command/head are in the PR body.
Full suite: deferred to merge batch (rule 68).

Retained interrupted experiment: v005 combined command hit its 240 s driver cap
after `_01` completed; `_02` had no accepted completion. Its partial directory is
historical, not reused. A fresh `_02` v006 run completed (324 s), preserving the
incomplete prior directory. Added final protocol guards were subsequently applied
to the saved arrays; `head-protocol-validation.json` records this narrower boundary
instead of claiming the earlier segmentation ran on a later source revision.

Previous checkpoints `CHECKPOINT.md`, `RESUME.md` are historical; their pending
zero-area question is answered by the orchestrator's 2026-11-17 card comment.
