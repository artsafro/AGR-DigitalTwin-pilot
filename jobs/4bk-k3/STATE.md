# 4bk-k3 — state (2026-11-14)

Status: **VPM modelling + UV in review by Artem; not passed.** Two VPM deliveries (tower K3, small stylobate),
then NPM. Requirement, decisions and quotes: `TASK.md`. Inputs: `sources.json`. Parts/Gate 1: `parts/k3_parts_v001.json`.

## Where the work is (outside git, owner's PC)

- Max scene (current): `C:\Users\artsafro\Desktop\!3D viz\!А101\63_4BK_vlad\build\3k_v004.max` (Max 2026, PID was
  563748), layer `K3_VPM_v001`: 61 part objects + 33 `K3_AC_*` + `K3_Stylo{Windows,Doors,Glass}`; Multi/Sub per part
  `MS_K3_{Typ,Band,Super,Roof,Stylo,AC}` + `M_K3_Glass`. Older: 3k_v001 (Vlad's scene + helpers), v002, v003.
  Source inbox untouched.
- Blender assembly: `…\build\blender\K3_assembly_v006.blend`; FBX `…\build\fbx\K3_assembly_v006.fbx` + manifest JSON;
  Max material scripts `…\build\fbx\k3_materials_v00{1,2,3}.ms`; textures `…\build\textures\` (Bricks1 stays in inbox).
- Part sources (scratchpad of session d1636320, temporary): `…\scratchpad\4bk_parts\{typ,band,super,roof,stylobate,
  stylobate_win,ac,tower_akp}\`, scripts in `…\scratchpad\4bk_scripts\`. Copy to the build folder before the scratch
  is cleaned.

## Versions in the current assembly

typ_uv_v003 (+ slats), band_uv_v003, super_uv_v004, roof_uv_v003, stylobate_uv_v003, stylo_win_v001, ac_v001.
Tower АКП: 3 tiles T_K3_AKP_{A,B,C} = ID2/ID11/ID12 at 512 px/m (left-edge stacking). Brick: Bricks1, 38 courses
per 3.15 m floor (1029 px/m). Stylobate brick with joints: T_K3_StyloBrick, 1 tile, 512 px/m.

## Acceptance vs Requirement (TASK.md)

| Item | State | Evidence |
|---|---|---|
| VPM of K3 (tower) by the end of the week (meeting 2026-11-11) | not met — model + UV done, review open | 3k_v004.max |
| Typical parts modelled once, textured, replicated | met | typ module ×13, band ×2 |
| Superstructure, roof + pergola + railing | met (roof v001 accepted 2026-11-12) | super_uv_v004, roof_uv_v003 |
| Small stylobate roof, canopies, stair, windows/doors | met, in review | stylobate_uv_v003, stylo_win_v001 |
| Materials per architect TZ (changed by later decisions in TASK.md) | met as decided | TASK.md sections |
| Two VPM deliveries (decision 2026-11-12) | not started (split, naming, package) | — |
| NPM | not started | — |

## Open checks

xView in Max not run; triangle count tower ≈ 146 k + 300 AC (target 150 k per OKS FBX); package (address, stem,
GeoJSON, naming) waits for Artem; UDIM renumbering contiguous at packaging; window drafts not in `library/windows/`.
