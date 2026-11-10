# Research: Telegram group «3ds Max» — what applies to this repository (2026-11-10)

Source: public Telegram group «3ds Max» (chat id 1145626314), read 2026-10-21 … 2026-11-10 (~3000 messages)
plus a keyword sweep of the whole history (AI, MCP, Codex, Claude, Gumroad, GitHub). Links checked on 2026-11-10.
Message ids below are Telegram ids in that group. Community claims are unverified unless marked "checked".

## Summary

The group turned in October 2026 from a Max help chat into a vibe-coding workshop: members write Max plugins
with Codex / Claude / DeepSeek and share them on Gumroad, 3ddd and Telegram. MCP use is rare. Nothing there
replaces a tool we already have; the value is a few ideas and one update. The user reviewed the list on
2026-11-10 and accepted the items below; Max Ultra MCP stays out (we keep `3dsmax-mcp`), opencode is not wanted,
render-by-camera / HDRI and AI post-processing are already covered.

## Accepted (2026-11-10, user)

| # | Idea | Source (msg id) | Backlog |
|---|---|---|---|
| 1 | Update `3dsmax-mcp` v1.7.5 → v1.7.8 (busy/hung Max diagnostics, restarted-Max following, unsaved-scene refusal for reset/open scripts, replace_material options, multi-view capture) — checked: upstream tag `v1.7.8`, 2026-11-07, MIT | 816228 | H14 |
| 2 | An agent builds a plugin, starts Max and runs its tests itself — for us: live smoke tests of AGR Tools / `agr-mcp` in a pinned Max after each change | 852622 | Q9 |
| 3 | Scene analyser: rank objects by size, find near-identical meshes and replace them with instances; reducer that keeps UV (~55 % fewer faces claimed) | 850362–850364 | P15 |
| 4 | Raster plan → walls by contrast (plugin by Samandari Khurshed, no release yet) | 849264, 849274 | IN9 |
| 5 | FenceFit03.dlm (Aid Yan): modifier that fits RailClone sub-evenly fence segments to terrain — candidate for Ground / MAF fences | 850182–850183 | P16 |
| 6 | Link Info «Inherit» locks do not survive FBX export; bake transforms before export | 849776–849785 | Q10 |
| 7 | Own asset catalog (models, materials, textures, previews, relink without Max); today Project Manager covers it, own catalog later | 852081, 852140, 852317 | P17 |

## For `max-ui` (separate repository `C:\x\max-ui`)

- Pie Menu (RUST_CG, free, Python, `Install.ms`): rustcg.gumroad.com/l/3dsMaxPieMenu — multi-menus by object /
  sub-object level, replaces the quad menu (849927, 850072, 850266).
- BMove (RUST_CG, free, Max 2024+): Blender-style G/R/S transforms, works in Edit Poly (852579).
- flowstate (cl0nazepamm, GPL-3.0 with Max SDK linking exception, Max 2026/2027): C++ GUP plugins — fast
  parameter edit, shader creation, modifier access, mouse viewport navigation. Checked on GitHub.
- What members want from their own Max UI (850987–850992): transform panel, group property editing,
  asset browser (models, materials, textures, modifiers), quick render settings, free-placed buttons, mouse gestures.

## Team topic «Материалы» (group «АГР - Holding», topic root 20948, 126 messages, 2025-11-30 … 2026-10-16)

A texture dump the team reuses, not rules. Message ids are in that group; nothing downloaded except one txt.

- MAF atlas ID map «айди по мафам.txt» (53408) + `_atlas_maf_high_low_frame_id.png` (53407): 15 slots — metal
  RAL 9005 / 7016 / 7004 / 9002, glossy steel, orange / light-green / red paint, WOOD1 oak, WOOD2 pine, black rubber,
  opacity strips, opacity chain-link, profiled sheet, log cut. Candidate for a data file `slot → material → RAL`.
- Placeholder sets ERM / Normal / Diffuse (solid PNG ≤ 4 KB, UDIM): interior, lighting, roofs, glossy and matte
  metal, address plates, gates, address template `T_Template_Address_001` (20949–20956, 27158–27904, 21001–21003).
- Flora textures, ~20 species (29188–29523, 61626–61632, 66203–66207, 92669, 92681).
- Ground tiles and surfaces, tile 4×4 (brick 3×3): `T_Domashniy_Ground_D.1001–1018` (123173–123190), paving,
  asphalt, concrete, wood (64381, 69812, 58971, 69811), `плитка.fbx` (107806–107808).
- Opacity meshes and fences (51178, 42371, 66210, 66211, 111223–111224); the 4K mesh in 102408 is AI-generated
  (synthetic).
- External «ALL textures» Yandex Disk folder (69813): content and licence not checked.
- Most files carry a real address / cadastral number in the name; rename to neutral names before a shared library.

Main goal for this topic (user, 2026-11-10): fill the missing sets of the materials library, so an agent knows
at once what to use and whether it is a good choice.

Gap analysis against the repository library (2026-11-10, media not opened — resolution, alpha and tiling unchecked):

- The tables exist, the maps do not: `library/materials/materials_v002.json` (42 rows, mostly `proposed`) and
  `ground_v001.json` (11 rows) point at `G:\Мой диск\AGR-assets\materials\`, which is absent; flora `maps.json`
  points at `C:\x\flora-library\v001\maps\`, also absent. MAF IDs `library/maf/material_ids_v005.json` (31 ids,
  [D181]) already cover all 15 slots of «айди по мафам.txt» (pine only as «WOOD medium»).
- Take after rename / resize / check: OKS placeholders (20949–20956), glossy and matte metal ERM (27158–27161),
  address plates and template (27883–27886, 21001–21003), gates (27901–27904), MAF atlas source for a 512 bake
  (53407 + 53408), flora — 12 files, new species: daisy white / yellow, lavender, wheat, loosestrife, yarrow
  (61626–61632, 66203–66207), tiling surfaces concrete / paving / wood / asphalt (58971, 64381, 69811, 69812;
  check 1000 px/m [D207]), tile and brick (107806–107813; tile 4 m vs the 3.6 m grid), opacity meshes and fences
  (42371, 66210, 111223, 111224, 66211; 700 px not a power of two; SheetMetal001 licence to check).
- Reference only: `T_Domashniy_Ground_D.1001–1018` and other per-object sets (real addresses, 4 m step).
- Skip: 102408 (AI-generated), 28663–28674 (unknown content) until reviewed; Yandex «ALL textures» (69813) needs
  an inventory first.
- Missing in both sources: maps for the 42 + 11 table rows, built placeholders NPM 128 / VPM 256, gravel, pebbles,
  mulch, rubber crumb, roll lawn, roofs (Logicroof, Solo, profiled sheet), facade masks (cassette 600, tile
  600×1200, panel V1200), pine, maps for the 61 flora species, VPM normals for tiling materials.
- Proposed layout (not approved): originals to `G:\Мой диск\AGR-assets\_inbox\telegram-materials-2026-11\`,
  processed maps to `materials\v001\<library_id>_<key>\`, placeholders to `materials\placeholders\v001\`, flora to
  `flora\v003\maps\<slug>\`; a manifest `library/materials/maps_v001.json` (file, sha256, size, px/m, source msg
  id, synthetic flag) in git; no binaries in git (H9).

### Downloaded to the inbox (2026-11-10, user «Да, скачать»)

42 originals in `G:\Мой диск\AGR-assets\_inbox\telegram-materials-2026-11\` as `<msgid>_<original name>`, with
`manifest.json` (msg id, category, label, bytes, sha256, width × height, mode). Unprocessed; names still carry real
addresses. What the files show against `docs/domain/areas/textures.md`:

| Group | Measured | Fit / work needed |
|---|---|---|
| OKS placeholders, address plates 1016, metal ERM (20949–20956, 27159, 27161, 27884–27886) | 256 × 256 RGB, ≤ 3.4 KB | VPM placeholder size as is; NPM needs 128 × 128 copies; rename |
| Address template, gates Diffuse / Normal (21001–21003, 27903–27904) | 4096 × 4096 RGB | VPM size; gates ERM 27902 is 256 palette (P) → convert to RGB |
| MAF atlas 53407 + ID map 53408 | 4096 RGB, 14.4 MB; 15 slots | source only; bake the 512 set by `material_ids_v005.json`; WOOD2 pine = MAF №11/23/25/26/28–31 |
| Flora, 12 species | 4096 RGBA (yarrow 2048), 1.2–6.0 MB | split into diffuse RGB + `_o` opacity, downsize for the ≤ 2048 Flora atlas |
| Ground surfaces concrete / paving / wood / asphalt | 4096 RGB, 7.9–14.8 MB | over 3 MiB: VPM source only; check px/m against [D207]; concrete is JPG |
| Tile (zip not extracted, FBX 34 MB), brick 2048 RGB | — | tile 4 m vs the 3.6 m grid |
| Opacity / fences | 2048 L, 700² RGBA, 2048 × 2560, 2048 × 640, 900² RGB | not powers of two except SheetMetal; convert to single-channel `_o`; SheetMetal001 licence to check |

## Topic «Нейротипс» (group «АГР - Holding», root 8283) — AI for 3D sources

Keyword-sampled (225 messages found; the topic is not read in full). Mostly a news feed of model releases.

- Channels worth subscribing: @neuroviza (neural networks for 3D visualisation), @gracehoppers (Rhino /
  Grasshopper + Claude Code, Rhino MCP, building generation), @sintez_space (AGR add-ons for Blender, AI viz).
  Skim: @acidcrunch, @tips_ai, Dark Max, «ArchViz 3dsmax Corona UE AI», «AI в архвизе». Skip: @petsproject
  (main repost source, generic), @bezsmuzi.
- Items for the pipeline: 103786 (cutting agent token use in Blender: quiet logs, short QA, one render per
  iteration, STATE.md), 125308 (m/agentic3d community on agents for 3D / BIM / digital twins), 115898 (Scenario:
  3D generator returning a named-parts `.blend` with PBR — try on MAF placeholders), 126081 (GPT-6.1 Terra: 3D
  from drawings — try on MAF), 56041 (Claude to Unreal), 103547 (B2MAX Blender → Max).
- Items for archviz: 61518 (3ds Max render elements → ComfyUI FLUX + ControlNet + IPAdapter, mask inpaint →
  Photoshop), 122390 / 118125 (upscale to 4K–8K), Kimi + Tripo FBX furniture from a collage (seen in @neuroviza).

### Other «АГР - Holding» topics — user decisions 2026-11-10

- Skipped: the new NPM+VPM requirements PDF (83926), the IFC-from-2026-12-01 post (127513), the window atlas rule
  (105052), SintezAgrChecker 1.3 / 1.5 (our checker covers more), AlexYo_AssetImporter (already in use).
- Noted as usable, not adopted (the user runs other scripts): `AGR_Loop_Cleaner_v3.ms` (127657, removes extra
  edge loops on OKS), `Import_HP_from_coordinates.ms` (126500, places high-poly by JSON coordinates).
- In use by the user: `UDIM Viewer_V1.4.ms` (112216) — loads normals by coordinates together with materials.

## Not taken

Max Ultra MCP (licence unclear: page says Free and «requires purchase»; we keep `3dsmax-mcp`), opencode,
rea, DragShift, allesimfluss sources (incomplete), UV Unfoldr ($39, manual UV; we have RizomUV via MCP),
render-by-camera / HDRI automation and AI render post-processing (already covered).
