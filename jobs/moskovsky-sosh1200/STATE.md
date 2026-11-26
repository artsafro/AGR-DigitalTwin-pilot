# moskovsky-sosh1200 — state

Cell `ground-npm`, trail `routes/site.md`. Stage: **Ground v003 built (IDs + textures on frozen geometry)**.
**v002 geometry accepted by the user 2026-11-26** (frozen). `passed=false`, no package; texture acceptance open.

## User decisions (2026-11-26)

- **No building-footprint hole**: footprint area capped, part of ID02 Paving (user deviation from D251 / hole
  practice for this job): `base_id 2`, `footprint_min_area 1e9`, unhatched -> ID02.
- One lawn cover ID05 (lawn, rolled lawn, hedge, shrub and flower beds; plants go on top later).
- Markings = separate closed mesh, top +8 mm, bottom −10 mm, own white material.
- **Curbs: not modelled** (user decision 2026-11-26; GND-07 practice waived for this job).
- Ultra-thin slivers: the user fixes them by hand (v002: 187 tris < 1 cm in GPZU).
- Agent recommendations accepted: rubber zones = library 27 recoloured to the RAL layer colours; shade-canopy
  spots = compacted soil.

## Ground NPM v003 (2026-11-26)

- Sources: main DWG `ed87f7f9…` -> `C:/x/moskovsky-env/inspect/school.dxf`; rubber DWG `_ резинаV1_1.dwg`
  `bbf22dce…` -> `C:/x/moskovsky-sosh1200/inspect/rubber-v1/rubber.dxf`. Same MSK-77 frame, metres.
- Specs: `specs/ground_site_v003.json`, `specs/ground_site_uncut_v003.json` (v002 adapters
  `C:/x/moskovsky-sosh1200/inspect/v002/`, re-ID only: ID03 -> ID18 CompactedSoil); markings
  `scripts/markings_uv.py` on the v002 marking mesh.
- Outputs `C:/x/moskovsky-sosh1200/outputs/ground-npm-v003/`: `gpzu/` (2 940 tris, UDIM 1001–1009 + markings 1010),
  `uncut/` (4 580 tris, 1001–1010 + markings 1011), `markings/`, `review/{gpzu,uncut}/*_review_{quad,idcolor}_v003.max`,
  `geometry-compare-v002.json` (vertices and faces identical to v002 after the re-ID).
- Textures: `C:/x/moskovsky-sosh1200/materials/npm-tiled-v002/` (2K, 37.9 px/m).

## Open gaps

1. Material bindings 19/22/42/23 and assumed periods (22/27/42/23 = 2 m) are proposals; no soil map in the library.
2. MTEXT game glyphs (74) not built; marking widths without DWG width = 0.05 m assumed.
3. Absolute Baltic mark of ±0.000 not in the DWG; paving A00F6C read even-odd (D343 scope).
4. MAF, Flora not started.

## Site NPM package v001 (stage 10, 2026-11-26): diagnostic, not passed

- Assembly `scripts/assemble_site_npm.py` (config `C:/x/moskovsky-sosh1200/outputs/site-npm-v001/assemble-config.json`):
  Ground v003 GPZU + markings, MAF v002, Flora v002 -> `package/0000_MoskovskySosh1200_Ground.fbx` (r3; r1/r2 superseded,
  `superseded_r*/WHY.txt`). MSK-77 XY, shared pivot (-9681, -7016, 0), Z 0 = ±0.000 (absolute mark open).
- ZIP `0000_MoskovskySosh1200.zip` (`agr package-npm --allow-incomplete`: no OKS -> status incomplete).
  103 707 tris (Ground 11 736 / GroundEl 47 344 + Glass 12 / Flora 44 615).
- Fails: V001 (no OKS), V003 skirt 0.018 m (markings in SM_Ground), V004 topology / MAF smoothing / 220 flipped,
  xview (GroundEl merged instances), 7 Ground PNG > 3 MiB. Open: address token, code 0000, ±0.000 mark. Passport + sources.json written.
