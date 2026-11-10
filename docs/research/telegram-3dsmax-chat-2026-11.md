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
at once what to use and whether it is a good choice. Gap analysis against the repository library: pending.

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
