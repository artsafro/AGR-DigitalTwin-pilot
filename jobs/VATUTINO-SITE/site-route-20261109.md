# Vatutino site slice (#298): route and numbers, 2026-11-09

Status: **route for Artem's choice, no build yet**, `passed=false`. Card t_5e2eb833, branch merged with
`origin/main` 2026-11-09. Unfrozen by Artem 2026-11-09 («давай блоки продолжим»); the long build waits for the
answers below. Max is not needed for the build: the earlier v003 run (prepare, Flora atlas, MAF atlas, assembly,
readback, validate, SINTEZ) ran entirely in Blender 5.1.2 headless.

## Measured inputs (real files, not estimates)

| Part | NPM tris | VPM tris | Source of the number |
|---|---:|---:|---|
| Ground v015 surface (accepted 2026-11-04, [D193]) | 46,479 | 46,479 | Triangulated accepted masters `C:/x/t_e35c49dd/ground-v015-build-v010/master-{npm,vpm}.json`, sha256 `c26b7feb…` / `59310ac9…` (re-counted today) |
| MAF v005 set, 13 positions as placed by #296 (119 instances, 2 urns out) | 55,403 | 67,731 | Exported FBX readback of the v001 assembly (`C:/x/t_5e2eb833/v001/{npm,vpm}/assembly.json`) |
| MAF «Верона» `*T3508` rows 1-10 ([D202]), not yet placed | 1,520 | 1,520 | `maf/verona-generator.md` budget (FBX readback per row) |
| Flora light v003 (#362), placed by #296 | 64,454 | 443,788 | Exported FBX readback of the v001 assembly |

The v001 assembly used Ground v014 (46,343); the MAF and Flora numbers do not depend on the Ground version
(same placement points, sinking per instance).

Urns 15E288 / 15E289 (VAT_MAF_T3510_02, 146 tris each): queried today against both v015 masters with
`dt_ai.placement.engine.GroundIndex.height` -> `None` (still outside the surface). Artem's exclusion of
2026-10-20 is bound to Ground v014 only, so v015 needs a new word.

## NPM budget options [D097], [D167] (limit 180,000, GND-04)

| Option | Content | NPM total | Margin | VPM total (GND-06 limit 4,500,000) |
|---|---|---:|---:|---:|
| **A (recommended)** | v015 + MAF v005 (2 urns excluded again) + «Верона» 10 rows + light Flora | **167,856** | 12,144 | 559,518 |
| B | A without «Верона» (placement of `*T3508` left to a later card) | 166,336 | 13,664 | 557,998 |
| C | A + the 2 urns placed after a Ground v015 fix at the cut-out edge (#295 line) | 168,148 | 11,852 | 559,810 |

Split vs the starting shares (surface 50k / MAF 60k / Flora 70k) in A: 46,479 / 56,923 / 64,454 — every share
holds. GND-06: S_ter 25,854.04 - S_pz 9,110.08 = 16,743.96 m² (> 1.5 ha) -> 4,500,000 (`ground-build-v011.md`).

## Site manifest draft (`site-manifest-draft.json`)

| Field | Value | State |
|---|---|---|
| Address token | `Vatutino` | used since v005 (`ground-build-v005.md`); confirm |
| Territorial code (4 digits, PKG-13, reg p.11 §10.1) | — | **unknown, needed from Artem**; without it V012 fails (`SM_Vatutino` vs `{code}_{Address}`) |
| NPM ZIP / Ground FBX | `{code}_Vatutino.zip` / `SM_Vatutino_Ground.fbx` | after the code |
| VPM ZIP / FBX / GeoJSON | `SM_Vatutino_Ground.zip` / `.fbx` / `.geojson` | GeoJSON not delivered in this slice [D126] |
| OKS (PKG-03: NPM ZIP = 1 Ground + 1..20 OKS FBX) | 4 large uncovered parts, 9,110.08 m², taken as footprints for S_pz | **no OKS models exist**; numbering `_01.._04` only if these are the OKS |

## Known machine findings from the v003 run (Ground v014, to recheck on the new build)

- validate_package NPM: V001 fail (FBX count 1, expected 2..21 — no OKS), V012 fail (no territorial code);
  V002-V006, V014, V015, V017 `not_run`.
- validate_package VPM: V001 fail (no GeoJSON, [D126]), V007 fail (texture names `T_Vatutino_Ground_D_<Slot>`
  vs `T_{Address}_{Diffuse|ERM|Normal}_{Slot}`); 10 stages `not_run`.
- SINTEZ AGR Checker (Blender 5.1.2, `jobs/KPP1/scripts/run_agr_checker.py`): read both ZIPs as HP only
  (no LP detected); NPM 51 verified / 15 failed / 54 undefined, VPM 54 / 12 / 54. Evidence, not the verdict.

## Questions for Artem

1. NPM budget: option A, B or C?
2. Territorial code (4 digits) for the NPM ZIP name, and the address token `Vatutino` — confirm?
3. OKS: the NPM ZIP needs at least one OKS FBX. (a) ship the site package without OKS and keep V001 as a
   recorded fail (`not passed`), or (b) wait for OKS models of the 4 footprints?
4. Urns 15E288/15E289: keep them out on Ground v015 too (extend the v014 exception), or send the cut-out edge
   back to the Ground line (option C)?
