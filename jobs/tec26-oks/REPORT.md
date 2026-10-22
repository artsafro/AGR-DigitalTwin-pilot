# TEC26 OKS 3 truba — texture foundation

Issue 560, this run only. The laid-out scene was not opened. Acceptance items 3 and 4
(full VPM + NPM package, mesh/material/UCX names on the exported models, overlap /
normals / doubles / readback, renders) are **not done**.

## Finishes

Source directory (read only):
`C:\Users\artsafro\Desktop\!3D viz\Dima_Andrew\2_kotelnya\Vlad_OKS\maps_truba`.

Measured with PIL on the source files. Diffuse texels in the normalised set are these
values, not a repaint onto the KPP sRGB sample. Distance is Euclidean RGB to the nearest
KPP1 sample in `jobs/KPP1/scripts/vpm_textures.json`.

| Finish | Source | RGB | RAL | Status | UDIM | id | NPM slot |
|---|---|---|---|---|---|---|---|
| Paint_Red | `red.png` 256 RGB | 195, 65, 65 | none adopted | assumption | 1001 | 1 | 1 |
| Band_RAL5015 | `blu.png` 256 RGB | 0, 124, 176 | RAL 5015 | assumption | 1002 | 2 | 2 |
| Band_RAL7047 | `gray.png` 256 RGB | 208, 208, 208 | RAL 7047 | exact KPP sRGB | 1003 | 3 | 3 |
| Band_RAL7004 | `dark_gray.png` 256 RGB | 173, 173, 173 | RAL 7004 | assumption | 1004 | 4 | 4 |
| Band_RAL7004_Dark | `dark_gray2.png` 256 RGB | 128, 128, 128 | RAL 7004 | assumption | 1005 | 5 | 5 |
| Railing_Steel | `railing_10mx1_2m_8posts_RGBA_2048.png` 4096 RGBA | copied, not a swatch | none | assumption | 1006 | 26 | 6 |

Nearest KPP sample when the pptx gives no truba RAL:

| Finish | Nearest KPP finish | KPP RGB | Distance | Adopted? |
|---|---|---|---|---|
| Paint_Red | Plinth_RAL7004 | 150, 153, 146 | 127.79 | No. Not a red. Source kept. |
| Band_RAL5015 | Cassette_RAL5015 | 34, 113, 179 | 35.86 | Label only. Source kept. |
| Band_RAL7047 | Cassette_RAL7047 | 208, 208, 208 | 0 | Yes, same bytes. |
| Band_RAL7004 | Plinth_RAL7004 | 150, 153, 146 | 40.72 | Label only. Closer than RAL 7047 (60.62). |
| Band_RAL7004_Dark | Grille_RAL7004 | 120, 122, 117 | 14.87 | Label only. Same code as the lighter band, separate tile. |
| Railing_Steel | Railing_Alpha (no RAL) | 125, 127, 130 | n/a (texture) | No RAL. KPP railing body is uncoded steel; handrail RAL 1021 is a different finish. |

One VPM material, six UDIM tiles. There is no glass, so tile 1001 is the red paint,
not a glass slot.

## Album

File: `ТЭЦ26 на РР (1).pptx` (61 slides), read with python-pptx (text frames, tables, notes)
and a byte search of every zip member for `труб`.

Slides that mention `труб`: **none**.

The colour statement is slide 58 (explanatory note), not a chimney drawing:

> Основной колористический принцип, заложенный в проекте — активное использование цветов,
> определенных как основные цвета оформления для производственных объектов компании «Газпром» -
> RAL 5015, RAL 9016, RAL 7047 и RAL 7004.

Slides 57-61 are the cooling tower, that note, the technical-economic tables and the parking
calculation. Slides 9-10 use the word «цвет» for landscape materials. No slide assigns a RAL
to the truba. RAL 9016 and RAL 1021 are in the KPP palette and are not used here: nothing in
the six maps is that white or that yellow.

## Naming

Regulation forms (`docs/domain/geometry.md`), address chosen as `Truba_1` (same pattern as
`Kpp_1`). NPM number `003` is OKS 3. These names are the spec for the DCC export; they are
not yet applied to a Max scene.

| Role | Name |
|---|---|
| VPM mesh | `SM_Truba_1_Main` |
| NPM mesh | `SM_Truba_1_003_Main` |
| VPM material | `M_Truba_1_Main_1` |
| NPM material | `M_Truba_1_003_Main_1` |
| UCX | `UCX_SM_Truba_1_Main_001` (further hulls `_002`…; railings ≤ 5 cm get no hull) |
| NPM maps | `T_Truba_1_003_Main_{d\|r\|m\|o}_{1..6}.png` (no `_n_`) |
| VPM maps | `T_Truba_1_{Diffuse\|ERM\|Normal}_1.{1001..1006}.png` |

Map rules written by `make_textures.py`. NPM and VPM are separate sets.

- NPM maps are 24-bit RGB. No alpha in any NPM image [D020]. No NPM normal [D014].
- Solid NPM diffuse and opacity: 256 px. Opacity plate is white.
- Railing NPM diffuse and opacity: source capped at 2048. Opacity is the alpha channel replicated into R=G=B.
- NPM roughness and metallic: 128 px constant plates.
- VPM railing Diffuse: source size (4096) RGBA, alpha kept (cutout lives in Diffuse alpha).
- VPM solid Diffuse: 256 px RGB. ERM and Normal: 256 px RGB, no alpha. ERM = (0, roughness, metallic). Normal = (128, 128, 255), DirectX flat.
- Roughness / metallic proposals, not measurements: paint 0.60 / 0, bands 0.50 / 0, railing 0.45 / 1 (KPP1 railing body).
- `--sums`, `--out`, the materials JSON, each source and each planned output are refused when any two are the same file (resolved path or hard link), before any directory or file is created.

Outputs: `C:/x/tec26-oks/textures-v001/` and `C:/x/tec26-oks/SHA256SUMS.txt`.

## What is NOT yet done

The DCC phase needs the #558 census. It is not started here, and no result below was fabricated.

- Open `truba.max` and check that the Multi/Sub slots match these six finishes.
- Export the VPM package and the NPM package (FBX, maps, names above).
- Build `UCX_SM_Truba_1_Main_###`.
- Overlap, normals, doubled vertices, readback, SINTEZ.
- Renders for Artem.

Until that phase, issue 560 items 3 and 4 stay open.
