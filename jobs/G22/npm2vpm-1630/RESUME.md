# Issue 1630 — corrected-cell checkpoint, NOT review-ready

**Historical checkpoint: superseded by [RESULT.md](RESULT.md).** The exact two
source-face drops were approved on the card and applied only on a new diagnostic
copy. Do not repeat the answered cleanup or option-a questions below.

## Answered policy

Artem 2026-11-17 USER DECISION on this card: recheck ID4 first, then seam cuts
into several IDs/tiles (option a) if corrected IDs still overflow at 512 px/m.
Do NOT ask that overflow-policy question again. No source geometry or UV edited;
no VPM output. No PR opened.

## Latest evidence (supersedes v001/v002)

Root: `G:/Мой диск/AGR-evidence/1630-npm2vpm-g22/`.
Body _01: `t_9d398e0d-v003-01/`; body _02: `t_9d398e0d-v004-02/`.
Each has numbered `sheet-<mesh>-0.png`, real model wire/colour renders,
`mesh_ids.json`, `id_table.json`, `diagnostic_ids.blend`, native readback,
verification, `source-degenerate-faces.json`, reproduction scripts and SHA256SUMS.
Original hashes verified 32/32; both final evidence manifests verified.

| Source mesh suffix | Polygons | Candidate cells | Assigned | Unassigned | Straddling / ambiguous | Mixed regions |
|---|---:|---:|---:|---:|---|---|
| 001_Main | 148186 | 26 | 148186 | 0 | 0 / 0 | none flagged |
| 002_Main | 73306 | 11 | 39206 | 34100 | 0 / 0 | 2 |
| 003_Main | 51146 | 23 | 25933 | 25213 | 0 / 0 | 11, 14, 22 |

Mixed regions are explicitly manual: ID0/magenta, never one guessed material.
The sheet's question-mark boxes identify these non-guillotine window/palette
regions. Layout candidates are not semantic material approval. Native Blender
5.1.2 fresh readback proves exact per-polygon IDs, polygon/vertex counts and one
UV channel for all three meshes; not full UV/topology/delivery acceptance.

ID4 recheck: corrected box `[0, 480, 1081, 896]`, one coherent grey facade cell,
7384 faces / 2888.416552 m2 summed area. It was NOT several visibly different
materials glued into one cell. Repeated overlapping UV use means summed surface
area is not unique texture area. Required extent remains 1.039761668 x .310475692
at 512 px/m: option-a seam cuts are authorized, but not yet applied.

## NEW source-data decision needed

`SM_Garibaldi_22_002_Main` contains exactly TWO zero-world-area source triangles:
0-based triangles/polygons **68903 and 69759**, both corrected ID4. The other
meshes have zero. Full identities are in `source-degenerate-faces.json`.

Independent polygon-68903 witness (metres): all vertices X=3101.07763671875,
Y=460.8438415527344; Z=247.59327697753906, 246.72653198242188,
246.28271484375. World area exactly 0; UV determinant 5.375689877240575e-06.
The reusable conversion gate refuses this source geometry as unmeasurable.

Question for Artem: recommend deleting ONLY these two zero-area polygons on a
new working copy, with explicit source-face drop accounting and unchanged FBX
originals. Is that cleanup authorized, or should they be reconstructed from an
architectural source? Seam-cut approval does not authorize polygon deletion.

## Implementation / tests

Same `maf_atlas_cells.segment`, not a parallel segmenter: facade mode scores all
material transitions, vetoes cuts through source UV coverage, avoids MAF merging,
and uses shared flat-block detection to mark contrasting nonrectangular regions
manual. `agr npm-ids --profile facade` selects this configuration. Default MAF
behavior remains unchanged. Final per-face containment/union remains exact.

RED commit `4b232378`: missing facade profile, 1 expected failure. Further REDs
observed for missing UV-bound support (1) and glued interior accepted as patterned
instead of mixed (1), followed by GREEN fixes. Earlier RED `02a6d246` retained.

Affected tests:
`env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_9d398e0d-checkpoint2 tests/test_npm_ids_1630.py tests/test_maf_atlas_ids.py tests/max_tools/test_agr_tools_npm_to_vpm.py tests/max_tools/test_agr_tools_101.py tests/test_udim_compaction_1531.py tests/test_agr_cli.py`
-> **208 passed in 19.31s**.
Full suite: deferred to merge batch (rule 68).

Failed experiments retained: v002 preview needed an explicit World; its retry
rendered but runner correctly rejected the previously written .blend as stale.
Wireframe even-offset caused sliver miter spikes; final diagnostic wire disables
it. Old sheets/logs remain historical. Combined v003 command timed out at 240s
on body _02; no child remained. v004 completed from immutable v003 intake JSON
(exit 1/blocked), rather than falsely claiming a new successful FBX intake.

## Remaining before review

- Answer source cleanup; retain explicit drops and originals.
- Resolve/list nonrectangular _02 material boundaries, never guess their mapping.
- Apply authorized seam cuts to corrected per-island fit candidates; reassess
  density and <=100 IDs. Current-layout tile estimates are NOT optimal counts.
- Harden CLI indices/inputs/path aliases/mutation/atomic publication.
- Add machine/human npm-to-vpm skeleton, one job config, CAPABILITIES row
  (hotspot PR #1628 first, additive only).
- Regions-mode VPM result or exact approved follow-up disposition, then downstream
  checker/xView/package gates; no production certificate at this checkpoint.
- Hostile probes, author receipts/evals/Agent trace, one PR and dt-reviewer.
