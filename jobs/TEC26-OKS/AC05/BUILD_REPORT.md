# AC05 Блок-модуль пенного пожаротушения — build-v004 (VPM + NPM)

**Status:** technical QA passed (`QA-PACKAGES PASS 43/43`); **Artem's visual acceptance is open**; `passed=false` for delivery.
Recipe: AC08 pilot-v010 (PR #574 @ed743ab), spec `vpm_textures.json`, sheet `sheet-facades.json`, dump `max-dump-005.json`.
Authority: presentation slide 35 (`C:/x/tec26-oks/pptx/facades/slide35.png`, sha256 `de3d7d96…cb96b`) + the binding
legend [D171]; Gate 1 (#562, «Принимаю»): roof RAL 7004, door/gate RAL 7004, drop below ±0.000 = wall colour.

## Legend (hatch -> material -> RAL -> texture) and every ID/region checked against it

| Legend row | Material | RAL | Texture | Finish | Source ID / region | Polygons |
|---|---|---|---|---|---|---:|
| Сэндвич-панели (blue ribbed field) | sandwich panel | 5015 | ribbed | PanelVJ45_RAL5015 | ID2, facades 1-2 (+x) / 2-1 (-x) | 16 |
| Сэндвич-панели (blue ribbed field) | sandwich panel | 5015 | ribbed | PanelVJ14_RAL5015 | ID2, facade Б-А (+y) | 3 |
| Обрамление (frame band, posts, rails, А-Б strips, drop) | edging | 5015 | plain | Frame_RAL5015 | ID1 except roof (112) + ID2 -y (3) | 115 |
| Крыльца, двери (door, end gate) | door / gate | 7004 | plain | Door_RAL7004 | ID3 (476) + ID4 (1) | 477 |
| Кровля (Gate 1) | roof | 7004 | plain | Roof_RAL7004 | ID1 up-facing, z >= 2.89 m | 15 |

No RAL 7047 sandwich, no RAL 9016 glazing on slide 35. Empty slots 5-10 stay empty. `finish_map.validate_legend` runs
before textures, build and compare.

## Rib count per facade (slide | VPM | NPM, counted on pixels)

| Facade | Normal | Slide joints | Contract ribs | VPM render | NPM render | Pitch m | Picture |
|---|---|---:|---:|---:|---:|---:|---|
| 1-2 | +x | 44 | 45 | 44 | 44 | 0.198318 | `compare/compare_east_1-2.png` |
| 2-1 | -x | 44 | 45 | 44 | 44 | 0.198318 | `compare/compare_west_2-1.png` |
| Б-А | +y | 13 | 14 | 13 | 13 | 0.159871 | `compare/compare_north_Б-А.png` |
| А-Б | -y | gate | — | plain | plain | — | `compare/compare_south_А-Б.png` |

Slide counts: `compare_facades.slide_count` on slide 35 (1-2/2-1 row at 0.9 of the body height, 44 lines at ~199 mm
over an 8.96 m field; Б-А row at half height skipping the end wall's inner frame line on each side). DWG modules
(278551 / 27A88C: 44 × 200 mm = 8.8 m, 43 interior lines) differ by one line from the slide; the slide is the authority.
Even layout over the model field (8.924311 m / 2.23819 m).

Joint/panel luminance contrast (row at 45 % height of each compare panel, `1 - joint/panel`):

| Facade | Slide | VPM | NPM |
|---|---:|---:|---:|
| 1-2 | 0.78 | 0.82 | 0.82 |
| 2-1 | 0.79 | 0.84 | 0.82 |
| Б-А | 0.96 | 0.80 | 0.81 |

Long facades meet «≥ slide». Б-А does not: the slide draws 1 px black lines; a joint dark enough to reach 0.96 loses
its blue hue and the render counter (blue mask `b - r > 25`) splits it in two (build-v002: 88 instead of 44). Kept at
0.80 and reported.

## Repairs inside the card (each a new build dir)

1. build-v001: counts 44/44/13 matched, joints too light (VPM 0.60, NPM 0.56 vs slide 0.78).
2. build-v002: joint colour (6,18,30), 10 mm: VPM 0.85 but the joints lost the blue hue -> the counter saw 88/26.
3. build-v003: joint (2,22,46): VPM 0.82, NPM still 0.69 (16 mm joint at the 2048 atlas).
4. build-v004: NPM joint 24 mm (`npm_joint_half_mm` 12): NPM 0.82. Current.

## QA and packages

`run_building.sh` -> `C:/x/tec26-oks/AC05/build-v004`: master 645 faces / 1328 tris (one edge ring at a joint of the
long field, 19 ring faces, `u_joint` 5.751 m), 0 UV overflow, 1000 px/m on both panel finishes, UCX 2 closed convex,
readback of both ZIPs, `QA-PACKAGES PASS 43/43`. Drive: `G:/Мой диск/AGR-evidence/562-tec26-oks-ac05-build-v004/`
(compare, renders, both ZIPs, max-review quads, QA JSON; `SHA256SUMS.txt`, 30 files).

## Findings and open questions for Artem

1. **А-Б gate:** slide 35 draws corrugation lines on the grey gate leaves; Gate 1 and the legend («двери» plain) keep
   the gate plain RAL 7004. Question: paint the gate corrugation lines (grey, slide count) or keep it plain?
2. **Door end of 2-1:** in the model the side door is 1.5-2.6 m from the gate end and appears at the RIGHT of the
   2-1 view; on slide 35 it is at the LEFT (near axis 2). The model plan is mirrored relative to the slide (or the
   axes differ); geometry is unchanged (colour-only scope).
3. **Perimeter-drop report** `BUILD-DROP` shows `ok=false` on 3 sides: the plan bbox includes the gate hardware
   protruding 0.086 m beyond the -y wall; the drop faces themselves cover all four walls (Gate-1 probe 4/4) and reach
   -2.004 m (`perimeter_drop_min_z` passed).
4. UCX triangulation at export and the roof colour stay the same open gates as AC08 pilot-v010.

## How to repeat

```
bash jobs/TEC26-OKS/scripts/run_building.sh jobs/TEC26-OKS/AC05 C:/x/tec26-oks/AC05/build-vNNN
blender ... render_facades.py -- jobs/TEC26-OKS/AC05/vpm_textures.json <O>/readback/vpm/SM_Bmpp_1.fbx <O>/textures-vpm \
    <O>/readback/npm/0000_Bmpp_1_01.fbx <O>/renders
uv run python jobs/TEC26-OKS/scripts/compare_facades.py jobs/TEC26-OKS/AC05/vpm_textures.json \
    jobs/TEC26-OKS/AC05/sheet-facades.json <O>/renders <O>/readback/vpm.readback.json <O>/compare
```
