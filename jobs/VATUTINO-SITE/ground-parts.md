# VATUTINO-SITE — Ground parts list (gate 1, [D125])

Issue #295, card t_d94665f2. Real project data (Vatutino, Дом 2, detailed concept 2025-06-19), not synthetic.
Status: **gate 1 approved** by the user 2026-10-19 (answers quoted on card t_d94665f2 and in the PR; answer E corrected to one 4 m mesh for both profiles). Build: `build_ground.py` -> `tools/blender/ground_json_to_fbx.py`.

## Inputs and route

| Item | Value |
|---|---|
| Adapter | `adapters/cad/spozu.py` (#195, PR #299) at `origin/main` `322574d`; config `adapters/cad/configs/vatutino_dom2.yaml` |
| Command (per file) | `uv run --extra cad python -m adapters.cad.spozu C:/x/t_d94665f2/<f>.dwg --config adapters/cad/configs/vatutino_dom2.yaml --workdir C:/x/t_d94665f2/<f>_work --json C:/x/t_d94665f2/<f>_ground_inputs.json` -> exit 0 (paving 131 s, main ~130 s; DWG -> DXF by the adapter through the AutoCAD 2025 core console) |
| Summary | `uv run --extra cad python jobs/VATUTINO-SITE/ground_parts.py paving=... main=... --out jobs/VATUTINO-SITE/ground-parts.json` -> exit 0 |
| Originals (sha256, before = after, mtime unchanged 2025-06-19) | main `64e22677454affce7071a823123b13742c8d68cd39c1ec0ee761c4cfa3b546e4`; paving `d24df23219fe1357830b3628ca31fa9acacedb158a9d3c8b9f9bc8a16cc3ece2` |
| Copies | `C:/x/t_d94665f2/main.dwg`, `paving.dwg` (same hashes) |
| Adapter DXF (local only) | main `d2c521fdef3f466e319783f24268a02cf51d140b6df200bc67ba9f520c6b995b`; paving `15d0f6470b17f4eb9fa1fa37ee9ff7f51b3c37ad3409a6805d9520da2b21756a` |
| Adapter JSON (local) | paving `69915b3f2ab4f2da643515e8d894696bfdd1c0503b8f69ba2cb34d91d91179cd`, main `fdd9c70299e634f581a93b5a060ea45898c76b6cb6d2bb53cd6dc51d7587323a` |

Numbers below are the **paving** file (the inventory's candidate master, question 7); main in brackets where it differs.

## Boundary contour

| Handle | Layer | Area m² | Perimeter m | Size m | Note |
|---|---|---|---|---|---|
| `568BF` | `ПР_ЛГР_предлагаемые` (legend «Граница проектирования») | 25 854.04 | 641.947 | 213.48 x 198.76 | 4 arcs sampled to 589 vertices; bbox x -7 700.77 … -7 487.29, y -15 387.12 … -15 188.37; same in both files. Confirmation pending (question 1) |

## Coverings -> material slot -> texture

Areas: adapter covering union inside `568BF` (hatches, holes kept, nested block content included). Slot names follow
GND-11 (`M_<Address>_Ground_<Slot>`); `<Address>` is the token asked in question B. Textures: none supplied; the NPM
(2K) and VPM (4K, UDIM) columns are placeholders until the user answers question A.

| # | Covering type | Layer(s) | Area m² | Parts / holes | Slot | NPM texture (2K) | VPM texture (4K, UDIM) |
|---|---|---|---|---|---|---|---|
| 1 | tile_light (**base**, largest) | `!_А101_плитка_светлая` | 7 348.60 (7 343.55) | 268 / 28 | `TileLight` | `T_<Address>_Ground_Diffuse_TileLight.png` placeholder | `T_<Address>_Ground_Diffuse_TileLight.1001.png` placeholder |
| 2 | mulch | `!_А101_мульча` | 3 634.47 (3 618.60) | 63 / 2 | `Mulch` | placeholder | placeholder |
| 3 | lawn_reinforced | `!_А101_укрепленный газон` | 2 460.11 (2 476.65) | 33 / 0 | `LawnReinforced` | placeholder | placeholder |
| 4 | tile_red | `!_А101_плитка_красная` | 887.81 | 7 / 0 | `TileRed` | placeholder | placeholder |
| 5 | gravel_screening | `!_А101_покр_гравийный отсев фр 2-8` | 882.42 | 13 / 4 | `Gravel` | placeholder | placeholder |
| 6 | lawn_rolled | `!_А101_озел_штрих_газон` | 871.48 (+22 invalid strips, question F) | 194 / 26 | `LawnRolled` | placeholder | placeholder |
| 7 | pebbles | `!_А101_покр_галька` | 298.51 | 3 / 0 | `Pebbles` | placeholder | placeholder |
| 8 | tile_dark | `!_А101_плитка_темная` | 130.20 (130.75) | 11 (12) / 0 | `TileDark` | placeholder | placeholder |
| 9 | flower_bed_01 … 08 | `!_А101_укрепленный цветник 0N <species>` (8 layers) | 13.29 / 19.66 / 6.31 / 6.60 / 5.54 / 5.90 / 6.39 / 5.34 = 69.03 | 29 / 0 | `FlowerBed` (one slot) or `FlowerBed01..08` (question 8) | placeholder | placeholder |
| — | decking | `!_А101_покр_декинг` | 0.00 (both hatches outside the plot; 1 closed polyline in the plot is not read, question 9) | 0 | — | — | — |

- Covered union 16 578.84 m² (main 16 575.06); **uncovered 9 275.20 m²** (main 9 278.98) in 699 parts. Four large
  parts hold 9 110.1 m² (3 345.8, 2 515.6, 1 801.6, 1 447.1 m²); the other 695 are slivers between coverings
  (the largest 85.7, 33.4 m²). Under method C the base plane covers them with the base covering unless question 3 says otherwise.
- Texture sets: 9 slots with one flower-bed slot (16 with eight) + the skirt placeholder; GND-02 allows max 20 surface sets in NPM.
- Overlaps (adapter `overlapping_coverings`, tol 0.01 m²): 15 pairs, 3.76 m² total, max tile_light / mulch 1.10 m².

## Flower beds ([D101])

The legend row says only «Цветник»; the planting schedule (`*T3509`) does not list the flower beds; the layer names carry
8 species (Щучка дернистая, Эхинацея пурпурная, Очиток видный, Тысячелистник Терракота, Шалфей дубравный, Мордовник
гмелина Snow king, Ясколка войлочная, Тимьян ползучий). Proposal by [D101]: **Ground texture** (the specification says
only flower beds), 69.03 m² in 29 parts. The species in the layer names are a reason to ask (question 8).

## Elevation source

| Item | Value |
|---|---|
| Source | preliminary vertical planning, container block `107E50` (`Д2_ВП_2024.10.10`) on frozen `!_А101_предварительная ВП`, layer `ГП_Вертикалка_ОпорнаяТочка_New`, MTEXT value |
| Points | 48 total, 48 inside, 48 distinct XY, duplicates 0, **contradictory Z 0**, not collinear |
| Z | 141.83 … 154.40 m (system not stated, question 6) |
| TIN coverage | convex hull of the 48 points = 19 748.1 m²; **6 106.0 m² (23.6 %) of the plot lies outside it**, up to 21.1 m from the hull. A TIN through the spot heights alone gives projection misses there (skill step 7 stops on any miss). The contour polylines (0.1 m step) are not read by the adapter config today (question 5) |
| Default | relief (the plot drops ~12.6 m); flat only if the user says so (question 5) |

## Curbs, steps, ramps, retaining walls (GND-07, skill step 8)

From the inventory layer map (paving file; these layers are in `ignore_layers` of the adapter config, so the adapter does not return them yet):

| Element | Layer | In plot | Height source |
|---|---|---|---|
| Garden concrete curb | `!_А101_борт_садовый_бетонный` | 95 open polylines | none in the DWG (question D) |
| Wooden curb | `!_А101_борт_деревянный` | 38 open polylines | none (question D) |
| Metal sunk curb | `!_А101_борт_металлический_заглубленный` | 26 open polylines | none (question D) |
| Stairs | `!_А101_лестница` | 10 INSERT `лестница 1..8` | none; steps not dimensioned (question D) |
| Ramps | — | none found by layer or legend | — |
| Retaining walls | — | none found by layer or legend | — |

Small height differences: [C37](../../docs/domain/conflicts.md) stays open (`review`).

## Adapter validation findings and what is done

| Finding | paving | main | Where | Action |
|---|---|---|---|---|
| `self_intersecting_contour` rolled lawn | 22 | 22 | inside the plot bbox | excluded from the area by the adapter (never repaired); 871.48 m² measured vs schedule Поз. 18 1 326.29 m² -> question F |
| `self_intersecting_contour` tile_light | 1 700 | 0 | insert `1A5755` (paving file only), x ≈ -8 000 … -8 035, **outside** the plot (x ≥ -7 700.8) | no effect on Ground; ignored as outside the boundary |
| `self_intersecting_contour` flower beds 03/07/08 | 5 | 5 | outside the plot bbox (legend / samples) | no effect; ignored |
| `overlapping_coverings` | 15 pairs, 3.76 m² | 15 pairs, 3.70 m² | edge-to-edge drawing tolerance | method C stacks layers, no stitching; level rule -> question C |
| `point_outside_boundary` | 77 | 78 | planting/MAF schedule samples and street trees | Flora/MAF scope (inventory question 2), not Ground |
| `unmapped_layer` | 44 | 44 | all inside blocks (Revit plan exports on `!_А101_ТЭТ`, bound neighbourhood plan), 0 in model space; includes `!_А101_укрепленные кустарники` (116 in blocks), `Высотные отметки`, `Уклоны в точках` | not Ground coverings; listed for the config owner; no covering read from them |
| open / degenerate contour, boundary not found / ambiguous, elevation unparsed | 0 | 0 | — | — |

## Budgets and placement (computed, not decided)

- GND-06 VPM limit: S_ter = 25 854.04 m². The limit is **4 500 000** triangles for any S_pz < 10 854.04 m² (S_ter - S_pz
  > 1.5 ha); with S_pz = the four large uncovered parts (9 110 m², if they are the house footprints) it stays 4 500 000.
- GND-05 NPM surface ≤ 50 000 polygons; 3 m cells over the plot ≈ 2 873 base cells + ≈ 1 026 upper-layer cells (9 230 m² / 9 m²) before
  contour cuts (estimate, measured after the build).
- Placement ([D126]): drawing coordinates in metres (`$INSUNITS=6`), no GEODATA; MSK-77 depends on question 6.
- UCX: #166 is open at card start -> `not checked: #166 open`; no hand-made collision.

## Questions

Inventory questions (`docs/research/spozu-vatutino-inventory.md`, "Open questions for the user"); question 2 (Flora) is out of this card.

1. **Boundary**: is `568BF` on `ПР_ЛГР_предлагаемые` (25 854.04 m²) the Ground boundary?
3. **Uncovered 9 275 m²** (four parts 3 346 / 2 516 / 1 802 / 1 447 m² + 695 slivers): what is the surface there
   (house footprints = no Ground / asphalt / default lawn)? Slivers between coverings: fill with the base covering (tile_light)?
4. **Tile types 3/4** (Gold №22 stripes, Profi №8) both on `плитка_светлая`: one material `TileLight` or two (from which data)?
5. **Heights**: is the preliminary ВП `Д2_ВП_2024.10.10` the height source (or flat, or a later VP sheet)? Spot heights
   only leave 6 106 m² (23.6 %) of the plot outside the TIN: (a) also read the contours (adapter config extension),
   (b) narrow the Ground, (c) another source?
6. **Coordinates**: georeference to MSK-77 (which system are x ≈ -7 600, y ≈ -15 300; heights Baltic?) or keep the
   drawing coordinates with a recorded local origin?
7. **Master file**: paving (`..._мощение.dwg`, matches the schedule: reinforced lawn 2 460.11 = Поз. 20) or main?
8. **Flower beds**: Ground texture per [D101] (one slot `FlowerBed`, or 8 slots by species) or Flora instances?
9. **Hatch or contour**: hatches as the covering source and closed contours only as a check (the decking contour in the plot is then dropped)?

Card questions (inputs the issue names):

- A. **Textures**: a Ground texture set per covering (NPM 2K, VPM 4K) — or permission to use placeholders for this slice?
- B. **Address token** for GND-11 names (`SM_<Address>_Ground`)?
- C. **Layer levels** (method C): (a) every covering its own level 6, 12, … 96 mm above the base; or (b) recommended —
  every covering on the base at +6 mm, +12 mm only where it lies on another covering (computed from the overlap graph)?
- D. **Curbs and stairs**: heights per curb type and stairs (none in the DWG); model all, or skip which (C37)?
- E. **Cell size**: 3 m for both profiles, or 4 m for VPM cuts ([D021])?
- F. **Rolled lawn**: the 22 self-intersecting strips (schedule 1 326.29 vs 871.48 m² measured): repair them by code
  (make-valid, reported per handle), or leave them to the base covering?
- G. Method C (layered cake) as the method for this slice — yes? (fallbacks A/B only on your yes)
