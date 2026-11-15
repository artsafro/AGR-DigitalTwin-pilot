# 4bk-k3 — state (2026-11-15)

Status: **two buildings are at about 80 %.**
- Tower floor 1 (A) and the stand-alone stylobate (B): Artem accepted geometry, UV and UCX.
- Artem hand-finished both buildings into the etalon files `63_4BK_vlad/bldA.max` and `bldB.max`.
- What is left waits on Artem: naming (address), the full texture set, GeoJSON, pivot (rotation angle), canopies (his typical model).
- Artem is now working on the big tower (typical floors) by hand.

Requirement, decisions and quotes: `TASK.md`. Inputs: `sources.json`.

## Where the work is (outside git, owner's PC)

Root: `C:\Users\artsafro\Desktop\!3D viz\!А101\63_4BK_vlad\`.

- **Etalons (Artem):** `bldA.max` (sha256 5682f5f6…1d85) and `bldB.max` (sha256 2bd42fa9…993c).
- **Combined scene:** `scene_build_A_build_B_v002.max`, with layers Build_A, Build_B, UCX_A and UCX_B. Counts match the etalons.
  `scene_build_A_build_B.max` is an identical first build; Artem said to keep it.
- **Parts** in `build\gf_parts\`:
  - A: geometry `gf_body_A_v004`, `gf_windows_A\v003`, `gf_roof_A_v003`;
  - A UV: `*_uv_v003` (body) and `*_uv_v002` (windows, roof);
  - B UV: `sty_*_uv_v00x`;
  - UCX: `ucx_A\gf_ucx_A_v001.blend` (24 pieces, 316 tris) and `ucx_B\sty_ucx_B_v001.blend` (10 pieces, 148 tris).
- **Checks:** `build\gf_parts\_check\check_v006…v009.md`.
- **Etalon analyses:** `_review\max\artem_v007_analysis\ANALYSIS.md` and `_review\max\artem_final_analysis\ANALYSIS.md` (Artem confirmed the latter).
- **Tower (typical floors, earlier work):** `build\3k_v004.max`, `build\session_d1636320\4bk_parts\`.

## Acceptance vs Requirement (TASK.md)

| Item | State | Evidence |
|---|---|---|
| VPM of K3 tower | partly: floor 1 A at 80 %; typical floors in Artem's hands | bldA.max; 3k_v004.max |
| Small stylobate VPM (separate delivery, 2026-11-12) | 80 %: geometry, UV, UCX accepted | bldB.max, ucx_B report |
| Floor 1 + stylobate from Revit (2026-11-14) | met: geometry accepted (A v004, B v003) | TASK.md "accepted" sections |
| Joints / UV / IDs / UDIM | met by Artem's hand finish; final UDIM distribution by Artem | artem_final_analysis |
| UCX | met: A and B v001 accepted 2026-11-15 | ucx_*_v001_report.json |
| Canopies | not started; waiting for Artem's typical model | — |
| Naming, GeoJSON, pivot, ERM/normal | not started; waiting for address and rotation | — |
| NPM | not started | — |

## Open

- Known window defects go to a separate kanban card (TASK.md "Known window defects").
- Facade grid rule (report-only check): to write after acceptance (Artem 2026-11-15, «Сначала только отчёт»).
- Backlog Q10: shared visibility checker (Codex).
