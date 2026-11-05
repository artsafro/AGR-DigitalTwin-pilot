# Lab experiment L01: `ucx.rename` (AGR Tools 0.8)

Source checked: GeoAGR 13.64 "UCX Rename" (`GeoAGR.ms:60283` button, handler `GeoAGR.ms:62907-62920`). No GeoAGR code
here (#853); job script and raw output are in the private GeoAGR repository, branch `lab-exp/L01`,
`work/lab-experiments/ucx.rename/`.

Run: 3ds Max 2024.2 via the AGR Lab runner (3dsmaxbatch), synthetic nodes. Job: `20261104-225132-d9e46cca`.

## What the source does (measured)
Strips trailing and leading digits/underscores, removes every `UCX_`, then gives each selected node
`UCX_<rest>_NNN` with Max's unique-name numbering. `UCX_SM_Tverskaya12_Main_001/002`, `..._Ground_001` stay correct;
105 pieces get `_001`..`_105` (3 digits in Max 2024).

## Defects
1. **Renames anything selected.** A render model `SM_Tverskaya12_Main` selected with its UCX became
   `UCX_SM_Tverskaya12_Main_001` (and the real UCX `_002`). Helpers, cameras and lights also become `UCX_*`.
2. Numbers follow the selection order; existing numbers are discarded (`_003,_002,_001` selected in that order -> `_001,_002,_003`).
3. Address damage by the trim rules: `UCX_SM_Tverskaya_12` -> `UCX_SM_Tverskaya_001`; `1st_Main` -> `UCX_st_Main_001`.
4. Prefix handling: `ucx_...` -> `UCX_ucx_...`; an inner `UCX_` is removed; a digits-only name -> `UCX__001`.
5. No grammar check (`SM_<Address>_(Main|Ground)`, 001..999); width depends on the Max unique-name default; an
   unselected `UCX_..._01` makes the next number `_002` (mixed widths tolerated).
6. No undo record for a script call (plan mode is `undo`).

## Recommendation
`take_fix` (as in the plan), with the fixes below being the bulk of the tool.

## Requirements the tool must meet
- VPM-2.10-4.2.b (reg 2.10.4.2, `docs/domain/requirements-2026.md:227`): collision names with Number 001..999;
  project grammar `UCX_SM_{Address}_Main_{001..999}` / `UCX_SM_{Address}_Ground_{001..999}` (`docs/domain/geometry.md:52`).
  The regulation text writes `UCX_Address_Main_Number` without `SM_` for the building; the project grammar keeps `SM_`.
- VPM-2.13-1.d (reg 2.13.1): collision pieces named by the mask.
- Plan mode `undo`: one Undo restores all names.

## Minimal acceptance test (proposal)
Scene: `SM_Addr_Main` (render model), UCX `UCX_SM_Addr_Main_003`, `UCX_SM_Addr_Main_001`, `ucx_SM_Addr_Main_7`,
`UCX_SM_Addr_Ground_01`, a Point helper; select all, run.
Pass when: the render model and the helper keep their names (reported as skipped); UCX become
`UCX_SM_Addr_Main_001..003` in a stable order (by old number) and `UCX_SM_Addr_Ground_001`; every result matches
`^UCX_SM_[A-Za-z0-9_]+_(Main|Ground)_\d{3}$`; more than 999 pieces is an error; one Undo restores all names; running
twice gives the same names.
