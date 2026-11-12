# 4bk-k3 — source analysis (2026-11-12)

Measured from `STLB-04_RR_K3_FSD.fbx` (own FBX reader, cross-checked with headless Blender 5.1.2 import: same bbox,
1 031 348 tris, no materials). Z below in the **Max frame** (Max Z = FBX Z − 0.150; floor-2 slab top 4.65).
FBX XY is tower-local (X −16.37..16.37, Y −0.10..37.10); in `3k.max` it sits at the Revit link dummy [95.15, 30.99].
Scripts, mesh dumps and plan sections (Z 6.3 / 25 / 45 / 55 / 60): scratch `4bk_fbx/` (not in git).

## Plan

- Inverted trapezoid mirrored about X = 0, 32.53 × 37.00 m; 4 corners R 1.50 (north 110°, south 70°).
- North side 29.53: 10.25 + notch 9.03 wide, 1.00 deep + 10.25. Slanted sides 20° off Y: 12.73 + 1.0 jog + 8.45
  (set back 1 m) + 1.0 jog + 15.00. South side 4.80.
- Depths on a typical floor: brick plane 0; «кирпич_АКП» and «Шт_фасад» −0.25; windows −0.50.

## Typical floor (2–7, 9–12, 14–16) — identical

- 33 windows: ОК-10-19 ×9, ОК-15-19 ×8, ОК-17-19 ×8, ОК-19-19 ×6, ОК-23-19 ×2; window +0.68..+2.65 over floor base.
- «Семейство1» strips ×10 (base..+0.70), «Семейство2» ×10 (+2.65..+3.15).
- Slats (imposts 50×50, actual 54×54): 8 groups / 102 per floor, 13 slats (12 north) at 0.100 pitch, turned 15° to the
  facade; plane −0.244 (slanted sides), −0.27 (north); Z +0.70..+3.15 (north groups stop at +2.65).
- Floor 2 = typical (only interior walls extra; bare 0.20 slab edge below). Floors 7, 12 add «ПЕР-001» (band bottom
  edge 23.18..23.78 / 38.93..39.53). Floor 16 adds 4 balcony doors ББ and terrace slabs 51.60..52.13.
- ≈27 k source tris per typical floor (windows 18.4 k).

## Band floors 8 and 13 — one module (offset 15.75)

| Layer | Z (floor 8) | Plane |
|---|---|---|
| ПЕР-001 | 23.18–23.78 | — |
| violet outer skin | 23.55–24.25 | 0 |
| Отлив_7024 | 24.25–24.47 | ring over the recess sill |
| recessed violet wall | 24.355–26.19 | **−1.25** |
| windows (34: ОК-10-16 ×10, ОК-17-16 ×10, ОК-19-16 ×2, ОК-10/15/17/23-19 ×9) | 24.23/24.43–26.20 | −1.50 |
| AC baskets ×6 | 24.42–26.15 | to −0.75 |
| soffit ПЕР-004 | 26.19–26.20 | — |
| top violet skin + Семейство2 ×5 + Семейство3 ×12 | 26.20–26.70 | 0 / −0.10 |

Slats on band floors: 2 middle groups (26) at 24.25..26.70, plane −1.246. Violet layers curve with the corners
(recess arc radius not measured).

## Superstructure 17–18 and roof

- Smaller footprint (Z 55: north edge y≈32.8, south y≈3.8). Walls: brick, АКП, violet ×11, «Утеплитель 120_Штукатурка
  ral 7024» (51.90–52.60), «Ламели фиолетовый». New window ОК-08-19 ×4 per floor.
- Terrace floor 17: ЛЛУ 1100 railing 52.40–53.20 (glass inferred from the type name), Отлив_Парапет.
- Helper levels: 52.71 = top of roof insulation over floor 16 (terrace / floor-17 base); 58.20 = top of floor 18 walls,
  base of roof brick walls; 59.80 = top of НВФ 1200 parapet railing (posts + 192 bars) and brick parapets;
  60.36 = 3rd member of the north screen frame; 62.20 = top of screen frames («Обобщенные модели 4/5/6», members 60 mm)
  and caps.
- Pergola: 16 columns (tile grey, 0.30×0.27 / 0.20×0.25, 58.60–61.30), canopy ПЕР3 61.30–61.60 (17.3 × 21.5) with 33
  battens 0.1×0.1. Roof: ЖБ+500 slabs, upturns «Кровля_заводится на 600», 14 equipment plinths (guess).

## Budget

Source 1.03 M tris; AC baskets 574 k (56 %, ≈28.6 k each) → must be replaced by light baskets in VPM.
Target ≤ 150 000 tris per OKS FBX [D161].

## Joints from the architect's images (red lines; calibrated on level lines, ±2–3 cm)

Red marks exist only for АКП and stylobate cladding; none on brick, plaster or roof. Crops: scratch `4bk_joints/`.

- **Rule (inferred from all images):** АКП vertical joints continue pilaster edges and window reveals, panel width
  ≤ ~1.95 m; horizontal joints at window head and sill, none at floor level; superstructure panels run through two
  floors (~4.89 m) with verticals only.
- **Band floors 8/13 (2.jpg, 1.jpg):** top strip 0.50, bottom strip 0.67; widths from the edge to the axis
  1.74 / 1.20 / 1.92 / 1.28 / 1.93 / 0.67 / 3.23* / 0.60 / 1.00 / 0.70 / 1.00 / 0.80 / 1.00 / 0.50 / 1.91 / 1.32 /
  0.67 / 1.91 / 1.30 / 1.92 / 1.19 / 1.74 (*3.23 likely a missed joint = 1.91 + 1.32). Joints run from level to level
  (39.30–42.45).
- **Central composition (2.jpg, 3.jpg):** two full-height АКП strips 0.70 and 0.80 with a 1.00 window column; one
  horizontal joint per floor at the sill; pier between paired windows 0.67 wide, joints at head and sill.
- **Rounded corners (Screenshot_1):** radial joints, 3 per 90° arc (tangent points + middle), continuous through the
  recess, the lip top and face; the 0.5 top strip on the arc is one bent panel. Brick runs round the arc in
  continuous courses.
- **Window on brick:** brick → ~3 cm reveal edge in АКП colour → ~6.8 cm frame RAL 7024. No separate surround; the
  «рамка» in the note is the reveal surface. Reveal colour: scheme RAL 020 30 20 vs note АКП RGB 122 92 96 — open.
- **Brick:** stretcher bond, half offset; the Revit hatch shows 75 mm courses (42 per floor) vs the scheme «280×85»;
  customer's accepted Bricks1 is used as delivered.
- **Stylobate (1 эт_2.jpg):** RAL 7024 annex, one horizontal joint at opening heads (4.02 m), verticals at reveals,
  widths 1.0–2.0; porcelain under windows ≈0.5 grid (eye estimate); K3 floor 1 АКП band 1.04 over the shopfronts.
- **Other:** pergola posts ~0.2 at 3.80–3.84 pitch, beam ~0.29, АКП colour; terrace railing posts RAL 7024;
  slats pitch 0.10 (6.5 cm slat + 3.5 cm gap), АКП colour; AC grilles ~0.94 × 0.55 dark.
